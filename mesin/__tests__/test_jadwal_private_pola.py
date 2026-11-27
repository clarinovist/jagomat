"""Pola Private (2 hari + 1 jam): validasi, kepemilikan, satu pengajuan aktif, persetujuan 8 pertemuan, dan migrasi aditif.

Domain pada DB sintetis (tanpa HTTP). Data sintetis saja: akun, anak, guru, dan admin buatan. DB private di direktori
sementara (conftest mengarahkan JADWAL_PRIVATE_DB), DB admin-control dari kelas_kit.
"""
import os
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

import jadwal_dasar as jd
import jadwal_private as jp
import jadwal_private_dasar as dsr
import jadwal_private_pola as jpp
import jadwal_private_pola_aturan as aturan
import jadwal_private_pola_setujui as jps
import jadwal_store as js
import kelas_kit
import pesanan_dasar as d
import schema_jadwal
from harian_mutasi_kit import uji_mutasi
from pesanan_kit import AKUN_A, AKUN_B

ADMIN = "admin_sintetis"
GURU_A = "akun_" + "7" * 32
SAH = frozenset({GURU_A})
KINI = "2026-11-25T03:00:00"  # Rabu 10.00 WIB; order sintetis aktif sampai sekitar 20 Des 2026
KAMIS_JUMAT_15 = (3, 4)      # Kamis dan Jumat, jam 15.00 WIB: offset 0,1,7,8,14,15,21,22 hari
TES_MUTASI = "test_pola_minggu_ditolak"


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


def _isian(hari, jam="15:00") -> dict:
    return {**{"hari_%d" % h: "1" for h in hari}, "jam": jam}


def _order(kon, siswa=1, akun=AKUN_A):
    return kelas_kit.lunas(kon, siswa, "private", n=1, akun=akun).order_id


def _pola_db() -> list:
    with closing(sqlite3.connect(str(_berkas_privat()))) as koneksi:
        koneksi.row_factory = sqlite3.Row
        return [dict(b) for b in koneksi.execute(
            "SELECT id,order_id,hari_a,hari_b,jam,status FROM private_pola_pengajuan ORDER BY id")]


def _jumlah(kon, tabel: str) -> int:
    return kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]


def _pertemuan_wib(kon, order_id: str) -> list:
    """(tanggal, jam) WIB per pertemuan, diurutkan menurut nomor `ke`."""
    sesi = js.ringkas_order(kon, order_id)["sesi"]
    return [jd.tanggal_jam_wib(s["mulai"]) for s in sorted(sesi, key=lambda s: s["ke"])]


# --- validasi murni ----------------------------------------------------------------------------

@pytest.mark.parametrize("hari,jam", [
    ([1, 1], "15:00"),      # hari sama
    ([0, 6], "15:00"),      # Minggu tidak dibuka
    ([1], "15:00"),         # kurang dari dua hari
    ([0, 1, 2], "15:00"),   # lebih dari dua hari
    ([1, 3], "18:00"),      # jam di luar daftar
    ([1, 3], None),         # jam kosong
    ([1, True], "15:00"),   # bool bukan hari
])
def test_pola_tidak_sah_ditolak(hari, jam):
    with pytest.raises(jd.JadwalTidakSah):
        aturan.periksa_pola(hari, jam)


def test_pola_sah_diurutkan_naik():
    assert aturan.periksa_pola([3, 1], "16:00") == (1, 3, "16:00")


def test_hari_dan_jam_dari_form_menerima_checkbox_dan_radio_saja():
    hari, jam = aturan.hari_dan_jam_dari_form({"hari_3": "1", "hari_1": "1", "jam": "17:00"})
    assert (sorted(hari), jam) == ([1, 3], "17:00")
    with pytest.raises(jd.JadwalTidakSah):
        aturan.hari_dan_jam_dari_form({"hari_1": "2", "jam": "17:00"})
    with pytest.raises(jd.JadwalTidakSah):
        aturan.hari_dan_jam_dari_form({"minggu": "1", "jam": "17:00"})


def test_delapan_pertemuan_bergantian_urut_kalender_2x_seminggu():
    tanggal = aturan.tanggal_pertemuan(date(2026, 11, 26), *KAMIS_JUMAT_15)
    selisih = [(t - tanggal[0]).days for t in tanggal]
    assert len(tanggal) == 8 and selisih == [0, 1, 7, 8, 14, 15, 21, 22]
    assert all(t.weekday() in (3, 4) for t in tanggal)


def test_tanggal_mulai_harus_jatuh_pada_hari_pola():
    with pytest.raises(jd.JadwalTidakSah):
        aturan.tanggal_pertemuan(date(2026, 11, 25), *KAMIS_JUMAT_15)  # Rabu bukan Kamis/Jumat


def test_tanggal_mulai_default_terdekat_minimal_24_jam():
    assert aturan.tanggal_mulai_default(KINI, *KAMIS_JUMAT_15, "15:00") == "2026-11-26"


# --- ajukan dan batalkan --------------------------------------------------------------------

def test_pola_kedua_menggantikan_yang_pertama_satu_diajukan_per_order(kon):
    oid = _order(kon)
    jpp.ajukan(kon, AKUN_A, 1, _isian((1, 3), "16:00"), KINI)
    jpp.ajukan(kon, AKUN_A, 1, _isian((0, 5), "19:00"), KINI)
    assert [(p["order_id"], p["hari_a"], p["hari_b"], p["jam"], p["status"]) for p in _pola_db()] == [
        (oid, 1, 3, "16:00", "dibatalkan"), (oid, 0, 5, "19:00", "diajukan")]


def test_pola_baru_membatalkan_pengajuan_slot_lama_yang_masih_diajukan(kon):
    oid = _order(kon)
    slot = jp.buat_slot(ADMIN, GURU_A, "2026-11-26", "10:00", KINI, SAH)
    jp.ajukan(kon, AKUN_A, 1, slot, KINI, SAH)
    jpp.ajukan(kon, AKUN_A, 1, _isian((1, 3)), KINI)
    lama = [b["status"] for b in _berkas_baca("private_pengajuan") if b["order_id"] == oid]
    assert lama == ["dibatalkan"]


def _berkas_baca(tabel: str) -> list:
    with closing(sqlite3.connect(str(_berkas_privat()))) as koneksi:
        koneksi.row_factory = sqlite3.Row
        return [dict(b) for b in koneksi.execute("SELECT * FROM %s ORDER BY id" % tabel)]


def test_bukan_pemilik_dan_tanpa_order_404_tanpa_berkas_dibuat(kon):
    _order(kon, siswa=1, akun=AKUN_A)
    with pytest.raises(d.PesananTidakDitemukan):
        jpp.ajukan(kon, AKUN_B, 1, _isian((1, 3)), KINI)     # anak milik akun lain
    with pytest.raises(d.PesananTidakDitemukan):
        jpp.ajukan(kon, AKUN_A, 2, _isian((1, 3)), KINI)     # anak tanpa order Private
    assert not _berkas_privat().exists()                    # tanpa efek samping: berkas belum dibuat


def test_batalkan_pola_hanya_yang_diajukan_dan_tanpa_pilihan_konflik(kon):
    _order(kon)
    with pytest.raises(jd.JadwalKonflik):
        jpp.batalkan(kon, AKUN_A, 1, KINI)                   # belum ada berkas
    jpp.ajukan(kon, AKUN_A, 1, _isian((1, 3)), KINI)
    jpp.batalkan(kon, AKUN_A, 1, KINI)
    assert [p["status"] for p in _pola_db()] == ["dibatalkan"]
    with pytest.raises(jd.JadwalKonflik):
        jpp.batalkan(kon, AKUN_A, 1, KINI)                   # sudah tidak ada yang diajukan


# --- persetujuan admin ---------------------------------------------------------------------

def test_setujui_pola_menempatkan_delapan_pertemuan_di_hari_dan_jam_pola(kon):
    oid = _order(kon)
    pid = jpp.ajukan(kon, AKUN_A, 1, _isian(KAMIS_JUMAT_15), KINI)
    jps.setujui(kon, ADMIN, pid, GURU_A, "2026-11-26", KINI, SAH)
    pertemuan = _pertemuan_wib(kon, oid)
    assert [t for t, _ in pertemuan] == ["2026-11-26", "2026-11-27", "2026-12-03", "2026-12-04",
                                         "2026-12-10", "2026-12-11", "2026-12-17", "2026-12-18"]
    assert {jam for _, jam in pertemuan} == {"15:00"}
    assert [p["status"] for p in _pola_db()] == ["disetujui"]


def test_setujui_pola_gagal_di_tengah_tidak_meninggalkan_penempatan_setengah_jadi(kon, monkeypatch):
    oid = _order(kon)
    pid = jpp.ajukan(kon, AKUN_A, 1, _isian(KAMIS_JUMAT_15), KINI)

    def _gagal(*_args, **_kwargs):
        raise RuntimeError("uji: gagal setelah penempatan")

    asli = jps._pindahkan_pertemuan
    monkeypatch.setattr(jps, "_pindahkan_pertemuan", _gagal)
    with pytest.raises(RuntimeError):
        jps.setujui(kon, ADMIN, pid, GURU_A, "2026-11-26", KINI, SAH)
    assert _jumlah(kon, "jadwal_penempatan") == 0 and _jumlah(kon, "jadwal_pertemuan") == 0
    assert [p["status"] for p in _pola_db()] == ["diajukan"]
    monkeypatch.setattr(jps, "_pindahkan_pertemuan", asli)   # pulih: setujui berikutnya berhasil
    jps.setujui(kon, ADMIN, pid, GURU_A, "2026-11-26", KINI, SAH)
    assert _jumlah(kon, "jadwal_pertemuan") == 8


def test_setujui_pola_ditolak_bila_pertemuan_terakhir_melewati_masa_akses(kon):
    oid = _order(kon)
    pid = jpp.ajukan(kon, AKUN_A, 1, _isian((1, 3)), KINI)
    with pytest.raises(jd.JadwalTidakSah):
        jps.setujui(kon, ADMIN, pid, GURU_A, "2026-12-15", KINI, SAH)   # 8 pertemuan melewati 20 Des
    assert _jumlah(kon, "jadwal_penempatan") == 0 and _jumlah(kon, "jadwal_pertemuan") == 0
    assert [p["status"] for p in _pola_db()] == ["diajukan"]


def test_tolak_pola_lalu_tidak_bisa_disetujui(kon):
    _order(kon)
    pid = jpp.ajukan(kon, AKUN_A, 1, _isian((1, 3)), KINI)
    jpp.tolak(ADMIN, pid, KINI)
    with pytest.raises(jd.JadwalKonflik):
        jps.setujui(kon, ADMIN, pid, GURU_A, "2026-11-26", KINI, SAH)


# --- migrasi aditif -----------------------------------------------------------------------

def test_migrasi_aditif_pada_berkas_v1_berisi_data_dan_idempoten(kon):
    path = _berkas_privat()
    with closing(sqlite3.connect(str(path))) as lama:    # berkas v1 seperti image lama membuatnya
        for ddl in dsr._DDL:
            lama.execute(ddl)
        lama.execute("PRAGMA user_version = 1")
        lama.execute("INSERT INTO private_slot(guru_id,mulai,menit,dibuat,dibuat_oleh) VALUES(?,?,?,?,?)",
                     (GURU_A, "2026-11-26T08:00:00", 60, KINI, ADMIN))
        lama.commit()
    assert dsr.dengan_baca(path, lambda k: dsr.ada_tabel(k, "private_pola_pengajuan"), None) is False
    jp.buat_slot(ADMIN, GURU_A, "2026-11-27", "10:00", KINI, SAH)     # tulis pertama: DDL tambahan terpasang
    jp.buat_slot(ADMIN, GURU_A, "2026-11-28", "10:00", KINI, SAH)     # tulis kedua: idempoten, tanpa galat
    with closing(sqlite3.connect(str(path))) as baca:
        assert baca.execute("PRAGMA user_version").fetchone()[0] == 1
        assert baca.execute("SELECT COUNT(*) FROM private_slot").fetchone()[0] == 3
    assert dsr.dengan_baca(path, lambda k: dsr.ada_tabel(k, "private_pola_pengajuan"), None) is True


def test_baca_berkas_v1_tanpa_tabel_pola_kosong_dan_tidak_menulis(tmp_path):
    path = _berkas_privat()
    with closing(sqlite3.connect(str(path))) as lama:
        for ddl in dsr._DDL:
            lama.execute(ddl)
        lama.execute("PRAGMA user_version = 1")
        lama.commit()
    assert jpp.terbaru_order("ada-order") is None
    assert jpp.antrean_admin(KINI) == ()
    assert jpp.jumlah_menunggu() == 0
    assert dsr.dengan_baca(path, lambda k: dsr.ada_tabel(k, "private_pola_pengajuan"), None) is False


# --- mutasi sekali: guard hari pada validasi pola -----------------------------------------------

def test_guard_hari_pola_merah_saat_dimatikan(tmp_path):
    """Guard Minggu (HARI_BOLEH) dimatikan di salinan terisolasi: tes harus merah, lalu hijau lagi."""
    salin = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", Path(__file__).name)
    ganti = [("    if any(type(nilai) is not int or nilai not in dsr.HARI_BOLEH for nilai in hari) or len(set(hari)) != 2:",
              "    if any(type(nilai) is not int for nilai in hari) or len(set(hari)) != 2:")]
    uji_mutasi(tmp_path, "jadwal_private_pola_aturan.py", ganti, Path(__file__).name, TES_MUTASI, salin)


def test_pola_minggu_ditolak():
    with pytest.raises(jd.JadwalTidakSah):
        aturan.periksa_pola([0, 6], "15:00")
