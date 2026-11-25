"""Jadwal private: orang tua mengajukan slot, admin menyetujui (domain pada DB sintetis, tanpa HTTP).

Semua data sintetis: akun, anak, dan admin buatan. DB private di direktori sementara (conftest mengarahkan
JADWAL_PRIVATE_DB), DB admin-control dari kelas_kit.
"""
import os
import sqlite3
import stat
from contextlib import closing
from dataclasses import fields
from pathlib import Path

import pytest

import jadwal_dasar as jd
import jadwal_private as jp
import jadwal_private_dasar as dsr
import jadwal_store as js
import kelas_kit
import pesanan_dasar as d
import schema_jadwal
from pesanan_kit import AKUN_A, AKUN_B

ADMIN = "admin_sintetis"
GURU_A = "akun_" + "7" * 32
GURU_B = "akun_" + "6" * 32
SAH = frozenset({GURU_A, GURU_B})
KINI = "2026-11-25T03:00:00"          # 10.00 WIB 25 Nov; akses order sintetis 20 Nov 09.30 s.d. 20 Des 09.30 UTC
KINI_LAMA = "2026-11-23T00:00:00"     # untuk tes yang perlu jarak lebih dari 24 jam dari slot
SLOT_10 = ("2026-11-26", "10:00")     # 03.00 UTC = tepat KINI + 24 jam (batas boleh)
MULAI_10 = "2026-11-26T03:00:00"


@pytest.fixture()
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    return path


@pytest.fixture()
def kon(db):
    with js.buka(db, tulis_data=True) as koneksi:
        yield koneksi


def _berkas_privat() -> Path:
    return Path(os.environ["JADWAL_PRIVATE_DB"])


def _tabel(tabel) -> list:
    path = _berkas_privat()
    if not path.exists():
        return []
    with closing(sqlite3.connect(str(path))) as koneksi:
        koneksi.row_factory = sqlite3.Row
        return [dict(baris) for baris in koneksi.execute(f"SELECT * FROM {tabel} ORDER BY id")]


def _jumlah_penempatan(kon) -> int:
    return kon.execute("SELECT COUNT(*) FROM jadwal_penempatan").fetchone()[0]


def _keadaan(kon):
    return (_tabel("private_slot"), _tabel("private_pengajuan"), _jumlah_penempatan(kon),
            kon.execute("SELECT COUNT(*) FROM jadwal_pertemuan").fetchone()[0])


def _slot(tanggal=SLOT_10[0], jam=SLOT_10[1], guru=GURU_A, sekarang=KINI, sah=SAH):
    return jp.buat_slot(ADMIN, guru, tanggal, jam, sekarang, sah)


def _order(kon, siswa=1, n=1, akun=AKUN_A):
    return kelas_kit.lunas(kon, siswa, "private", n=n, akun=akun).order_id


def _ajukan(kon, slot_id, siswa=1, akun=AKUN_A, sekarang=KINI):
    return jp.ajukan(kon, akun, siswa, slot_id, sekarang, SAH)


def _status_pengajuan_dari(pid) -> str:
    return next(baris["status"] for baris in _tabel("private_pengajuan") if baris["id"] == pid)


def _slot_terbuka_ids(kon, oid, sekarang=KINI):
    return [s.slot_id for s in jp.slot_terbuka_untuk(kon, oid, sekarang, SAH)]


# --- slot (admin) ----------------------------------------------------------------------------

def test_buat_slot_menyimpan_mulai_wib_dan_menit_private():
    # Act
    slot_id = _slot()
    # Assert
    (baris,) = _tabel("private_slot")
    assert baris["id"] == slot_id
    assert baris["mulai"] == MULAI_10
    assert baris["menit"] == 60
    assert baris["guru_id"] == GURU_A


def test_buat_slot_guru_tidak_aktif_ditolak_tanpa_menulis():
    with pytest.raises(jd.JadwalTidakSah):
        jp.buat_slot(ADMIN, GURU_B, *SLOT_10, KINI, frozenset({GURU_A}))
    assert not _berkas_privat().exists()


def test_buat_slot_waktu_lampau_ditolak_tanpa_menulis():
    with pytest.raises(jd.JadwalTidakSah):
        _slot(tanggal="2026-11-24")
    assert not _berkas_privat().exists()


def test_buat_slot_guru_dan_waktu_sama_menjadi_konflik():
    _slot()
    with pytest.raises(jd.JadwalKonflik):
        _slot()
    assert len(_tabel("private_slot")) == 1


def test_slot_mulai_kurang_dari_24_jam_tidak_ditawarkan_dan_ditolak_saat_ajukan(kon):
    oid = _order(kon)
    dekat = _slot(jam="09:00")                 # 02.00 UTC: kurang dari 24 jam dari KINI
    jauh = _slot(jam="10:00")
    assert _slot_terbuka_ids(kon, oid) == [jauh]
    with pytest.raises(jd.JadwalKonflik):
        _ajukan(kon, dekat)
    assert _tabel("private_pengajuan") == []


def test_slot_pertemuan_ke8_melewati_masa_akses_tidak_ditawarkan(kon):
    oid = _order(kon)
    batas_pas = _slot(jam="16:30")             # ke-8 = 20 Des 09.30 UTC, tepat di batas akses
    _slot(tanggal="2026-11-27")                # ke-8 = 21 Des: melewati akses
    assert _slot_terbuka_ids(kon, oid) == [batas_pas]


def test_guru_tidak_aktif_tidak_ditawarkan(kon):
    oid = _order(kon)
    guru_a = _slot(guru=GURU_A)
    guru_b = _slot(guru=GURU_B, jam="16:30")
    assert set(_slot_terbuka_ids(kon, oid)) == {guru_a, guru_b}
    sah_a = frozenset({GURU_A})
    assert [s.slot_id for s in jp.slot_terbuka_untuk(kon, oid, KINI, sah_a)] == [guru_a]


def test_slot_dibatalkan_tidak_ditawarkan(kon):
    oid = _order(kon)
    sid = _slot()
    jp.batalkan_slot(kon, ADMIN, sid, KINI, SAH)
    assert _slot_terbuka_ids(kon, oid) == []


def test_slot_terbuka_tidak_memuat_guru_id(kon):
    oid = _order(kon)
    _slot()
    (item,) = jp.slot_terbuka_untuk(kon, oid, KINI, SAH)
    assert {f.name for f in fields(item)} == {"slot_id", "mulai", "menit"}


def test_slot_terbuka_dibatasi_jumlah_maksimum(kon):
    oid = _order(kon)
    _slot(jam="10:00")
    _slot(jam="11:00")
    _slot(jam="12:00")
    assert len(jp.slot_terbuka_untuk(kon, oid, KINI, SAH, maks=2)) == 2


def test_daftar_slot_admin_memberi_status_turunan(kon):
    _order(kon, siswa=1, n=1)
    oid_y = _order(kon, siswa=2, n=2)
    diajukan = _slot(jam="10:00")
    terisi = _slot(jam="16:30")
    dibatalkan = _slot(jam="11:00", guru=GURU_B)
    lewat = jp.buat_slot(ADMIN, GURU_A, "2026-11-24", "10:00", KINI_LAMA, SAH)
    terbuka = _slot(tanggal="2026-11-27", guru=GURU_B)
    _ajukan(kon, diajukan, siswa=1)
    js.tempatkan(kon, ADMIN, oid_y, guru_id=GURU_A, tanggal="2026-11-26", jam="16:30", sekarang=KINI)
    jp.batalkan_slot(kon, ADMIN, dibatalkan, KINI, SAH)
    status = {s.slot_id: s.status for s in jp.daftar_slot_admin(kon, KINI, SAH)}
    assert status == {diajukan: "diajukan", terisi: "terisi", dibatalkan: "dibatalkan",
                      lewat: "lewat", terbuka: "terbuka"}


# --- order dan pengajuan (orang tua) ---------------------------------------------------------

def test_order_milik_akun_atau_anak_lain_tidak_bisa_mengajukan(kon):
    _order(kon, siswa=1, akun=AKUN_A)
    sid = _slot()
    sebelum = _keadaan(kon)
    with pytest.raises(d.PesananTidakDitemukan):
        jp.ajukan(kon, AKUN_B, 1, sid, KINI, SAH)
    assert _keadaan(kon) == sebelum


def test_anak_tanpa_order_private_aktif_tidak_bisa_mengajukan(kon):
    kelas_kit.lunas(kon, 2, "mini", n=1, akun=AKUN_A)      # hanya Mini
    kelas_kit.tagih(kon, 3, "private", akun=AKUN_A)        # Private belum bayar
    sid = _slot()
    assert jp.order_boleh_mengajukan(kon, AKUN_A, 2, KINI) is None
    assert jp.order_boleh_mengajukan(kon, AKUN_A, 3, KINI) is None
    with pytest.raises(jd.JadwalKonflik):
        _ajukan(kon, sid, siswa=2)
    assert _tabel("private_pengajuan") == []


def test_order_yang_sudah_ditempatkan_manual_tidak_ditawarkan_kembali(kon):
    oid = _order(kon)
    js.tempatkan(kon, ADMIN, oid, guru_id=GURU_B, tanggal="2026-11-26", jam="10:00", sekarang=KINI)
    assert jp.order_boleh_mengajukan(kon, AKUN_A, 1, KINI) is None


def test_ajukan_membuat_pengajuan_diajukan_yang_menahan_slot(kon):
    _order(kon, siswa=1, n=1)
    _order(kon, siswa=2, n=2)
    sid = _slot()
    pid = _ajukan(kon, sid, siswa=1)
    with pytest.raises(jd.JadwalKonflik):
        _ajukan(kon, sid, siswa=2)
    assert _status_pengajuan_dari(pid) == "diajukan"
    assert len(_tabel("private_pengajuan")) == 1


def test_ajukan_kedua_menggantikan_pengajuan_pertama(kon):
    _order(kon)
    pertama = _slot(jam="10:00")
    kedua = _slot(jam="16:30")
    id_pertama = _ajukan(kon, pertama)
    id_kedua = _ajukan(kon, kedua)
    assert _status_pengajuan_dari(id_pertama) == "dibatalkan"
    assert _status_pengajuan_dari(id_kedua) == "diajukan"
    assert _tabel("private_pengajuan")[0]["diputuskan_oleh"] == "sistem"


def test_batalkan_pengajuan_hanya_milik_anak_itu(kon):
    _order(kon, siswa=1, n=1)
    _order(kon, siswa=2, n=2)
    pid = _ajukan(kon, _slot(), siswa=1)
    with pytest.raises(d.PesananTidakDitemukan):
        jp.batalkan_pengajuan(kon, AKUN_B, 1, KINI)
    with pytest.raises(d.PesananTidakDitemukan):
        jp.batalkan_pengajuan(kon, AKUN_A, 2, KINI)
    assert _status_pengajuan_dari(pid) == "diajukan"
    jp.batalkan_pengajuan(kon, AKUN_A, 1, KINI)
    assert _status_pengajuan_dari(pid) == "dibatalkan"
    assert _tabel("private_pengajuan")[0]["diputuskan_oleh"] == "orang_tua"


def test_status_pengajuan_menampilkan_pengajuan_terakhir_order(kon):
    _order(kon)
    assert jp.status_pengajuan(kon, AKUN_A, 1, KINI) is None
    pid = _ajukan(kon, _slot())
    status = jp.status_pengajuan(kon, AKUN_A, 1, KINI)
    assert (status.pengajuan_id, status.status, status.mulai) == (pid, "diajukan", MULAI_10)


# --- persetujuan (admin) ---------------------------------------------------------------------

def test_setujui_membuat_penempatan_dan_delapan_pertemuan_sama_dengan_tempatkan_langsung(kon):
    oid_x = _order(kon, siswa=1, n=1)
    oid_y = _order(kon, siswa=2, n=2)
    pid = _ajukan(kon, _slot(), siswa=1)
    jp.setujui(kon, ADMIN, pid, KINI, SAH)
    js.tempatkan(kon, ADMIN, oid_y, guru_id=GURU_A, tanggal=SLOT_10[0], jam=SLOT_10[1], sekarang=KINI)
    hasil_x = js.ringkas_order(kon, oid_x)
    hasil_y = js.ringkas_order(kon, oid_y)
    ringkas = [(s["ke"], s["mulai"], s["menit"]) for s in hasil_x["sesi"]]
    assert ringkas == [(s["ke"], s["mulai"], s["menit"]) for s in hasil_y["sesi"]]
    assert len(ringkas) == 8 and hasil_x["guru_id"] == GURU_A
    assert _status_pengajuan_dari(pid) == "disetujui"


def test_setujui_idempoten_setelah_gagal_commit_privat_tanpa_tempatkan_dua_kali(kon, monkeypatch):
    _order(kon)
    pid = _ajukan(kon, _slot())
    tempatkan_asli = js.tempatkan
    tandai_asli = jp._tandai_disetujui
    panggilan = []

    def tempatkan_hitung(*args, **kwargs):
        panggilan.append(1)
        return tempatkan_asli(*args, **kwargs)

    def gagal_tandai(*args, **kwargs):
        raise sqlite3.OperationalError("simulasi galat commit")

    monkeypatch.setattr(js, "tempatkan", tempatkan_hitung)
    monkeypatch.setattr(jp, "_tandai_disetujui", gagal_tandai)
    with pytest.raises(dsr.GalatJadwalPrivate):
        jp.setujui(kon, ADMIN, pid, KINI, SAH)
    assert _jumlah_penempatan(kon) == 1
    assert _status_pengajuan_dari(pid) == "diajukan"
    monkeypatch.setattr(jp, "_tandai_disetujui", tandai_asli)
    jp.setujui(kon, ADMIN, pid, KINI, SAH)
    assert len(panggilan) == 1
    assert _status_pengajuan_dari(pid) == "disetujui"


def test_setujui_pengajuan_yang_sudah_ditolak_ditolak_tanpa_penempatan(kon):
    _order(kon)
    pid = _ajukan(kon, _slot())
    jp.tolak(ADMIN, pid, KINI)
    with pytest.raises(jd.JadwalKonflik):
        jp.setujui(kon, ADMIN, pid, KINI, SAH)
    assert _jumlah_penempatan(kon) == 0


def test_penempatan_manual_lain_membuat_pengajuan_basi_dan_setujui_ditolak(kon):
    oid = _order(kon)
    sid = _slot(jam="10:00")
    pid = _ajukan(kon, sid)
    js.tempatkan(kon, ADMIN, oid, guru_id=GURU_B, tanggal="2026-11-26", jam="16:30", sekarang=KINI)
    (entri,) = jp.antrean_admin(kon, KINI, SAH)
    assert entri.basi is True and entri.alasan_basi == "paket sudah punya jadwal"
    assert jp.jumlah_menunggu(kon, KINI, SAH) == 0
    _order(kon, siswa=2, n=2)
    _ajukan(kon, sid, siswa=2)                 # pengajuan basi tidak menahan slot
    with pytest.raises(jd.JadwalKonflik):
        jp.setujui(kon, ADMIN, pid, KINI, SAH)
    assert _status_pengajuan_dari(pid) == "diajukan"
    assert _jumlah_penempatan(kon) == 1


def test_penempatan_manual_pada_slot_sama_disetujui_tanpa_tempatkan_ulang(kon, monkeypatch):
    oid = _order(kon)
    pid = _ajukan(kon, _slot())
    js.tempatkan(kon, ADMIN, oid, guru_id=GURU_A, tanggal=SLOT_10[0], jam=SLOT_10[1], sekarang=KINI)
    (entri,) = jp.antrean_admin(kon, KINI, SAH)
    assert entri.basi is False
    panggilan = []
    monkeypatch.setattr(js, "tempatkan", lambda *a, **k: panggilan.append(1))
    jp.setujui(kon, ADMIN, pid, KINI, SAH)
    assert panggilan == []
    assert _status_pengajuan_dari(pid) == "disetujui"
    assert _jumlah_penempatan(kon) == 1


def test_setujui_ditolak_bila_slot_sudah_terisi_order_lain(kon):
    _order(kon, siswa=1, n=1)
    oid_c = _order(kon, siswa=2, n=2)
    pid_b = _ajukan(kon, _slot(), siswa=1)
    js.tempatkan(kon, ADMIN, oid_c, guru_id=GURU_A, tanggal=SLOT_10[0], jam=SLOT_10[1], sekarang=KINI)
    (entri,) = jp.antrean_admin(kon, KINI, SAH)
    assert entri.pengajuan_id == pid_b and entri.basi is True and entri.alasan_basi == "slot sudah terisi"
    with pytest.raises(jd.JadwalKonflik):
        jp.setujui(kon, ADMIN, pid_b, KINI, SAH)
    assert _status_pengajuan_dari(pid_b) == "diajukan"
    assert _jumlah_penempatan(kon) == 1


def test_tolak_pengajuan_basi_diperbolehkan(kon):
    oid = _order(kon)
    pid = _ajukan(kon, _slot(jam="10:00"))
    js.tempatkan(kon, ADMIN, oid, guru_id=GURU_B, tanggal="2026-11-26", jam="16:30", sekarang=KINI)
    jp.tolak(ADMIN, pid, KINI)
    assert _status_pengajuan_dari(pid) == "ditolak"


def test_batalkan_slot_ditolak_bila_pengajuan_masih_menahan_lalu_boleh_setelah_ditolak(kon):
    _order(kon)
    sid = _slot()
    pid = _ajukan(kon, sid)
    with pytest.raises(jd.JadwalKonflik):
        jp.batalkan_slot(kon, ADMIN, sid, KINI, SAH)
    jp.tolak(ADMIN, pid, KINI)
    jp.batalkan_slot(kon, ADMIN, sid, KINI, SAH)
    assert _tabel("private_slot")[0]["dibatalkan"] == 1


def test_batalkan_slot_tetap_boleh_bila_pengajuan_sudah_basi(kon):
    oid = _order(kon)
    sid = _slot(jam="10:00")
    _ajukan(kon, sid)
    js.tempatkan(kon, ADMIN, oid, guru_id=GURU_B, tanggal="2026-11-26", jam="16:30", sekarang=KINI)
    jp.batalkan_slot(kon, ADMIN, sid, KINI, SAH)
    assert _tabel("private_slot")[0]["dibatalkan"] == 1


def test_lepas_setelah_disetujui_membebaskan_slot_dan_order_boleh_mengajukan_lagi(kon):
    oid = _order(kon)
    sid = _slot()
    pid = _ajukan(kon, sid)
    jp.setujui(kon, ADMIN, pid, KINI, SAH)
    dibuat = js.ringkas_order(kon, oid)["dibuat"]
    js.lepas_penempatan(kon, ADMIN, oid, versi=dibuat, sekarang=KINI)
    assert jp.order_boleh_mengajukan(kon, AKUN_A, 1, KINI) == oid
    assert sid in _slot_terbuka_ids(kon, oid)


def test_perpanjangan_saat_penempatan_lama_masih_berjalan_tidak_ditawarkan(kon):
    oid_lama = _order(kon, siswa=1, n=1)
    pid = _ajukan(kon, _slot())
    jp.setujui(kon, ADMIN, pid, KINI, SAH)
    oid_baru = _order(kon, siswa=1, n=2)
    assert oid_lama != oid_baru
    assert jp.order_boleh_mengajukan(kon, AKUN_A, 1, KINI) is None


# --- waktu dan basi -------------------------------------------------------------------------

def test_antrean_menandai_pengajuan_basi_bila_slot_dibatalkan(kon):
    _order(kon)
    sid = _slot()
    _ajukan(kon, sid)
    sah_b = frozenset({GURU_B})
    jp.batalkan_slot(kon, ADMIN, sid, KINI, sah_b)     # guru slot tidak aktif: pengajuan basi, tak menahan slot
    (entri,) = jp.antrean_admin(kon, KINI, sah_b)
    assert entri.basi is True and entri.alasan_basi == "slot sudah dibatalkan"


def test_pengajuan_private_basi_bila_anak_ditempatkan_di_mini_lalu_tidak_menahan_slot(kon):
    _order(kon, siswa=1, n=1)
    pid = _ajukan(kon, _slot())
    oid_mini = kelas_kit.lunas(kon, 1, "mini", n=2, akun=AKUN_A).order_id
    kid = js.buat_kelompok(kon, ADMIN, nama="Mini A", lokasi="Ruang 1", guru_id=GURU_B, kuota=5,
                           tanggal="2026-11-26", jam="09:00", sekarang=KINI)
    js.tempatkan(kon, ADMIN, oid_mini, kelompok_id=kid, sekarang=KINI)
    (entri,) = jp.antrean_admin(kon, KINI, SAH)
    assert entri.pengajuan_id == pid and entri.basi is True
    assert entri.alasan_basi == "anak sudah punya jadwal di paket lain"
    assert jp.jumlah_menunggu(kon, KINI, SAH) == 0
    with pytest.raises(jd.JadwalKonflik):
        jp.setujui(kon, ADMIN, pid, KINI, SAH)
    assert _status_pengajuan_dari(pid) == "diajukan"


def test_slot_lewat_saat_pending_menjadi_basi_dan_setujui_ditolak(kon):
    _order(kon)
    pid = _ajukan(kon, _slot(jam="10:00"))
    sesudah = "2026-11-26T05:00:00"            # 12.00 WIB: slot sudah lewat
    (entri,) = jp.antrean_admin(kon, sesudah, SAH)
    assert entri.basi is True and entri.alasan_basi == "waktu mulai sudah lewat"
    assert jp.jumlah_menunggu(kon, sesudah, SAH) == 0
    with pytest.raises(jd.JadwalKonflik):
        jp.setujui(kon, ADMIN, pid, sesudah, SAH)


def test_order_kedaluwarsa_saat_pending_menjadi_basi(kon):
    _order(kon)
    _ajukan(kon, _slot(jam="16:30"))
    (entri,) = jp.antrean_admin(kon, "2026-12-21T00:00:00", SAH)
    assert entri.basi is True and entri.alasan_basi == "masa akses paket sudah berakhir"


def test_konversi_wib_ke_utc_dan_kembali_utuh_lintas_hari():
    baku = "2026-11-25T22:30:00"               # 05.30 WIB 26 Nov
    tanggal, jam = jd.tanggal_jam_wib(baku)
    assert (tanggal, jam) == ("2026-11-26", "05:30")
    assert jd.pertemuan_pertama(tanggal, jam, KINI_LAMA) == baku


def test_setujui_slot_05_30_wib_menyimpan_mulai_utc_yang_sama(kon):
    oid = _order(kon)
    sid = jp.buat_slot(ADMIN, GURU_A, "2026-11-26", "05:30", KINI_LAMA, SAH)
    pid = _ajukan(kon, sid, sekarang=KINI_LAMA)
    jp.setujui(kon, ADMIN, pid, KINI_LAMA, SAH)
    assert js.ringkas_order(kon, oid)["sesi"][0]["mulai"] == "2026-11-25T22:30:00"


# --- skema, penyimpanan, dan privasi --------------------------------------------------------

def test_skema_menolak_hapus_slot_dan_ubah_status_akhir_tetapi_izinkan_batal(kon):
    _order(kon)
    sid = _slot()
    pid = _ajukan(kon, sid)
    jp.tolak(ADMIN, pid, KINI)
    with closing(sqlite3.connect(str(_berkas_privat()))) as koneksi:
        with pytest.raises(sqlite3.Error):
            koneksi.execute("DELETE FROM private_slot")
        with pytest.raises(sqlite3.Error):
            koneksi.execute("UPDATE private_slot SET mulai='2026-12-01T00:00:00'")
        with pytest.raises(sqlite3.Error):
            koneksi.execute("UPDATE private_pengajuan SET status='diajukan'")
        koneksi.rollback()
        koneksi.execute("UPDATE private_slot SET dibatalkan=1 WHERE id=?", (sid,))
        koneksi.commit()
    assert _tabel("private_slot")[0]["dibatalkan"] == 1


def test_baca_tanpa_berkas_tidak_membuat_berkas(kon):
    oid = _order(kon)
    assert jp.slot_terbuka_untuk(kon, oid, KINI, SAH) == ()
    assert jp.antrean_admin(kon, KINI, SAH) == ()
    assert jp.jumlah_menunggu(kon, KINI, SAH) == 0
    assert jp.daftar_slot_admin(kon, KINI, SAH) == ()
    assert jp.status_pengajuan(kon, AKUN_A, 1, KINI) is None
    assert not _berkas_privat().exists()


def test_berkas_rusak_menjadi_galat_jadwal_private(kon):
    oid = _order(kon)
    _berkas_privat().write_bytes(b"ini bukan basis data sqlite" * 64)
    with pytest.raises(dsr.GalatJadwalPrivate):
        jp.slot_terbuka_untuk(kon, oid, KINI, SAH)
    with pytest.raises(dsr.GalatJadwalPrivate):
        _slot()


def test_versi_skema_tidak_dikenali_menjadi_galat(kon):
    _slot()
    with closing(sqlite3.connect(str(_berkas_privat()))) as koneksi:
        koneksi.execute("PRAGMA user_version = 2")
    with pytest.raises(dsr.GalatJadwalPrivate):
        jp.daftar_slot_admin(kon, KINI, SAH)


def test_berkas_baru_dibuat_0600_dan_tanpa_wal(kon):
    _slot()
    path = _berkas_privat()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with closing(sqlite3.connect(str(path))) as koneksi:
        assert koneksi.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


def test_berkas_tidak_memuat_identitas_anak_atau_akun(kon):
    oid = _order(kon)
    _ajukan(kon, _slot())
    with closing(sqlite3.connect(str(_berkas_privat()))) as koneksi:
        kolom = {baris[1] for tabel in ("private_slot", "private_pengajuan")
                 for baris in koneksi.execute(f"PRAGMA table_info({tabel})")}
        isi = [str(nilai) for tabel in ("private_slot", "private_pengajuan")
               for baris in koneksi.execute(f"SELECT * FROM {tabel}") for nilai in baris]
    assert not kolom & {"akun_id", "siswa_id"}
    assert not any(AKUN_A in nilai or AKUN_B in nilai for nilai in isi)
    assert oid in isi
