"""Daftar tunggu Mini Class (F2c): masuk/keluar, satu entri per order, urutan, 404 identik, migrasi aditif, dan admin hapus.

Domain pada DB sintetis, lalu HTTP nyata untuk rute murid dan admin. Data sintetis saja (akun, anak, guru, dan admin
buatan). DB private di direktori sementara (conftest mengarahkan JADWAL_PRIVATE_DB), DB admin-control dari kelas_kit.
"""
from __future__ import annotations

import html
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import admin_antrean_tunggu
import admin_store
import auth
import jadwal_dasar as jd
import jadwal_pilih as jp
import jadwal_private_dasar as dsr
import jadwal_store as js
import jadwal_tunggu_mini as jt
import kelas_kit
import kelas_putusan
import kelas_store
import pesanan_dasar as d
import schema_jadwal
from admin_pesanan_kit import login_admin, minta_admin
from bukti_kit import JPEG, PNG
from harian_mutasi_kit import uji_mutasi
from kelas_http_kit import (ADMIN, AWAL, M, bukti_terakhir, buat_dan_unggah, buat_murid, halaman,  # noqa: F401
                            jam, kidup, kirim, kmati, server, token)
from pesanan_kit import AKUN_A, AKUN_B

ADMIN_DOMAIN = "admin_sintetis"
GURU = "akun_" + "9" * 32
LOKASI = "https://meet.google.com/abc-defg-hij"
KINI = "2026-11-25T03:00:00"          # akses lunas kelas_kit sampai sekitar 20 Des 2026 (UTC naif)
TES_MUTASI = "test_kelompok_tutup_atau_lewat_akses_404_tanpa_berkas"
JUDUL = "Pilih jadwal kelas"
MASUK = M + "/tunggu"
KELUAR = M + "/tunggu/keluar"
KELOMPOK_ADMIN = "/admin/kelas/kelompok"
HAPUS_ADMIN = "/admin/kelas/kelompok/tunggu/hapus"
LOKASI_ADMIN = "https://zoom.us/j/111222333"


# --- fixture dan pembantu domain -------------------------------------------------------------

@pytest.fixture()
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    return path


@pytest.fixture()
def kon(db):
    with js.buka(db, tulis_data=True) as koneksi:
        yield koneksi


def _berkas() -> Path:
    return dsr.path_db(None)


def _kelompok(kon, nama="Mini A", kuota=1, tanggal="2026-11-26", dibuat=kelas_kit.KINI):
    return js.buat_kelompok(kon, ADMIN_DOMAIN, nama=nama, lokasi=LOKASI, guru_id=GURU, kuota=kuota,
                            tanggal=tanggal, jam="09:00", sekarang=dibuat)


def _penuhkan(kon, kid: str, siswa: int = 8, n: int = 2) -> None:
    """Isi satu-satunya kursi kelompok `kid` dengan anak lain milik AKUN_A."""
    kelas_kit.lunas(kon, siswa=siswa, n=n)
    jp.pilih_kelompok(kon, AKUN_A, siswa, kid, KINI)


def _baris_tunggu() -> list:
    if not _berkas().exists():                 # baca tidak pernah membuat berkas
        return []
    with closing(sqlite3.connect(str(_berkas()))) as koneksi:
        koneksi.row_factory = sqlite3.Row
        return [dict(b) for b in koneksi.execute(
            "SELECT id,order_id,kelompok_id,status,diputuskan_oleh FROM tunggu_mini ORDER BY id")]


def _jumlah_tunggu_aktif() -> int:
    return sum(1 for b in _baris_tunggu() if b["status"] == "menunggu")


# --- domain: masuk, urutan, dan satu entri per order ------------------------------------------

def test_masuk_kelompok_penuh_dan_urutan_menurut_urutan_masuk(kon):
    kid = _kelompok(kon)
    _penuhkan(kon, kid)
    kelas_kit.lunas(kon, siswa=7, n=1)
    kelas_kit.lunas(kon, siswa=9, n=3, akun=AKUN_B)
    jt.masuk(kon, AKUN_B, 9, kid, "2026-11-25T03:01:00")
    jt.masuk(kon, AKUN_A, 7, kid, "2026-11-25T03:02:00")
    assert jt.status_tunggu(kon, AKUN_B, 9, KINI).saya == jt.TungguSaya(kid, 1)
    assert jt.status_tunggu(kon, AKUN_A, 7, KINI).saya == jt.TungguSaya(kid, 2)


def test_masuk_kelompok_belum_penuh_ditolak_409_tanpa_berkas_dibuat(kon):
    kid = _kelompok(kon, kuota=2)
    kelas_kit.lunas(kon, siswa=7)
    with pytest.raises(jd.JadwalKonflik):
        jt.masuk(kon, AKUN_A, 7, kid, KINI)
    assert not _berkas().exists()


def test_satu_entri_per_order_dan_masuk_daftar_lain_menggantikan(kon):
    kid_a, kid_b = _kelompok(kon, "Mini A"), _kelompok(kon, "Mini B")
    _penuhkan(kon, kid_a, siswa=8, n=2)
    _penuhkan(kon, kid_b, siswa=9, n=3)
    kelas_kit.lunas(kon, siswa=7, n=1)
    jt.masuk(kon, AKUN_A, 7, kid_a, "2026-11-25T03:01:00")
    jt.masuk(kon, AKUN_A, 7, kid_b, "2026-11-25T03:02:00")
    baris = _baris_tunggu()
    assert [(b["kelompok_id"], b["status"]) for b in baris] == [(kid_a, "dibatalkan"), (kid_b, "menunggu")]
    assert baris[0]["diputuskan_oleh"] == dsr.PELAKU_SISTEM
    assert jt.status_tunggu(kon, AKUN_A, 7, KINI).saya == jt.TungguSaya(kid_b, 1)


def test_masuk_ulang_kelompok_sama_tidak_mengubah_posisi(kon):
    kid = _kelompok(kon)
    _penuhkan(kon, kid)
    kelas_kit.lunas(kon, siswa=9, n=3, akun=AKUN_B)
    kelas_kit.lunas(kon, siswa=7, n=1)
    jt.masuk(kon, AKUN_B, 9, kid, "2026-11-25T03:01:00")
    jt.masuk(kon, AKUN_A, 7, kid, "2026-11-25T03:02:00")
    sebelum = _baris_tunggu()
    jt.masuk(kon, AKUN_A, 7, kid, "2026-11-25T03:09:00")        # klik ganda: tidak pindah ke belakang
    assert _baris_tunggu() == sebelum
    assert jt.status_tunggu(kon, AKUN_A, 7, KINI).saya == jt.TungguSaya(kid, 2)


def test_penempatan_menyembunyikan_entri_dari_urutan_dan_hitungan_antrean(kon, db):
    kid, kid_c = _kelompok(kon, "Mini A"), _kelompok(kon, "Mini C", kuota=5)
    _penuhkan(kon, kid)
    tagihan_9 = kelas_kit.lunas(kon, siswa=9, n=3, akun=AKUN_B)
    tagihan_7 = kelas_kit.lunas(kon, siswa=7, n=1)
    jt.masuk(kon, AKUN_A, 7, kid, "2026-11-25T03:01:00")
    jt.masuk(kon, AKUN_B, 9, kid, "2026-11-25T03:02:00")
    assert jt.jumlah_menunggu_kursi(kon) == 2
    js.tempatkan(kon, ADMIN_DOMAIN, tagihan_7.order_id, kelompok_id=kid_c, sekarang=KINI)
    assert jt.status_tunggu(kon, AKUN_B, 9, KINI).saya == jt.TungguSaya(kid, 1)
    assert jt.status_tunggu(kon, AKUN_A, 7, KINI).saya is None
    assert jt.jumlah_menunggu_kursi(kon) == 1
    assert admin_antrean_tunggu.jumlah(db) == 1
    entri = {e.order_id: e for e in jt.daftar_admin(kon, kid)}
    assert (entri[tagihan_7.order_id].urutan, entri[tagihan_7.order_id].sudah_ditempatkan) == (None, True)
    assert (entri[tagihan_9.order_id].urutan, entri[tagihan_9.order_id].sudah_ditempatkan) == (1, False)


def test_butir_antrean_menunggu_kursi_hanya_angka_tanpa_nama_anak(kon, db):
    import admin_antrean as antrean_admin
    kid = _kelompok(kon)
    _penuhkan(kon, kid)
    tagihan = kelas_kit.lunas(kon, siswa=7, n=1)
    jt.masuk(kon, AKUN_A, 7, kid, KINI)
    (butir,) = antrean_admin._item_tunggu_mini(db, 0.0)
    assert (butir.tingkat, butir.judul, butir.jalur) == ("tinjau", "1 anak menunggu kursi Mini Class", "/admin/kelas")
    assert tagihan.order_id not in repr(butir)


def test_antrean_fungsi_murni_menjaga_urutan_masuk():
    assert jt.antrean(["o1", "o2", "o3"], {"o2"}) == ("o1", "o3")
    assert jt.antrean([], set()) == ()


# --- domain: 404 identik dan tanpa efek samping -----------------------------------------------

def _keadaan_tak_layak(kon, keadaan: str):
    """Kembalikan (akun, siswa, kelompok_id) yang tidak memenuhi syarat masuk daftar tunggu."""
    kid = _kelompok(kon)
    _penuhkan(kon, kid)
    if keadaan == "akun_lain":
        kelas_kit.lunas(kon, siswa=7, n=1)
        return AKUN_B, 7, kid
    if keadaan == "tanpa_order":
        return AKUN_A, 7, kid
    if keadaan == "private":
        kelas_kit.lunas(kon, siswa=7, paket="private")
        return AKUN_A, 7, kid
    if keadaan == "sudah_ditempatkan":
        tagihan = kelas_kit.lunas(kon, siswa=7)
        kid_lain = _kelompok(kon, "Mini Lain", kuota=5)
        js.tempatkan(kon, ADMIN_DOMAIN, tagihan.order_id, kelompok_id=kid_lain, sekarang=KINI)
        return AKUN_A, 7, kid
    raise AssertionError(keadaan)


@pytest.mark.parametrize("keadaan", ["akun_lain", "tanpa_order", "private", "sudah_ditempatkan"])
def test_masuk_tak_layak_404_identik_tanpa_efek(kon, keadaan):
    akun, siswa, kid = _keadaan_tak_layak(kon, keadaan)
    with pytest.raises(d.PesananTidakDitemukan):
        jt.masuk(kon, akun, siswa, kid, KINI)
    assert not _berkas().exists()


def test_kelompok_tutup_atau_lewat_akses_404_tanpa_berkas(kon):
    kelas_kit.lunas(kon, siswa=7)
    kid_tutup = _kelompok(kon, "Sudah berjalan", tanggal="2026-11-20", dibuat="2026-11-10T00:00:00")
    with pytest.raises(d.PesananTidakDitemukan):
        jt.masuk(kon, AKUN_A, 7, kid_tutup, KINI)
    assert not _berkas().exists()


def test_keluar_akun_lain_dan_tanpa_entri_404_tanpa_efek(kon):
    kid = _kelompok(kon)
    _penuhkan(kon, kid)
    kelas_kit.lunas(kon, siswa=7)
    jt.masuk(kon, AKUN_A, 7, kid, "2026-11-25T03:01:00")
    with pytest.raises(d.PesananTidakDitemukan):
        jt.keluar(kon, AKUN_B, 7, KINI)
    assert [b["status"] for b in _baris_tunggu()] == ["menunggu"]
    jt.keluar(kon, AKUN_A, 7, KINI)
    with pytest.raises(d.PesananTidakDitemukan):
        jt.keluar(kon, AKUN_A, 7, KINI)                      # tidak ada entri lagi
    assert [(b["status"], b["diputuskan_oleh"]) for b in _baris_tunggu()] == [("dibatalkan", dsr.PELAKU_ORANG_TUA)]


# --- domain: admin, transisi, dan migrasi -----------------------------------------------------

def test_admin_hapus_hanya_dari_menunggu_dan_status_dihapus_admin(kon):
    kid = _kelompok(kon)
    _penuhkan(kon, kid)
    kelas_kit.lunas(kon, siswa=7)
    jt.masuk(kon, AKUN_A, 7, kid, KINI)
    entri_id = jt.daftar_admin(kon, kid)[0].id
    jt.hapus_admin(ADMIN_DOMAIN, entri_id, KINI)
    assert (_baris_tunggu()[0]["status"], _baris_tunggu()[0]["diputuskan_oleh"]) == ("dihapus_admin", ADMIN_DOMAIN)
    with pytest.raises(jd.JadwalKonflik):
        jt.hapus_admin(ADMIN_DOMAIN, entri_id, KINI)
    with pytest.raises(jd.JadwalTidakDitemukan):
        jt.hapus_admin(ADMIN_DOMAIN, 999, KINI)


def test_trigger_menolak_transisi_dan_ubah_kolom_terkunci(kon):
    kid = _kelompok(kon)
    _penuhkan(kon, kid)
    kelas_kit.lunas(kon, siswa=7)
    jt.masuk(kon, AKUN_A, 7, kid, KINI)
    entri_id = _baris_tunggu()[0]["id"]
    with closing(sqlite3.connect(str(_berkas()))) as koneksi:
        with pytest.raises(sqlite3.Error):
            koneksi.execute("UPDATE tunggu_mini SET kelompok_id=? WHERE id=?", ("klp_" + "0" * 32, entri_id))
        koneksi.rollback()
        koneksi.execute("UPDATE tunggu_mini SET status='dibatalkan' WHERE id=?", (entri_id,))
        koneksi.commit()
        with pytest.raises(sqlite3.Error):
            koneksi.execute("UPDATE tunggu_mini SET status='menunggu' WHERE id=?", (entri_id,))
        koneksi.rollback()


def test_migrasi_tambahan_idempoten_pada_berkas_v1_dan_berkas_f2b(kon):
    kid = _kelompok(kon)
    _penuhkan(kon, kid)
    kelas_kit.lunas(kon, siswa=7, n=1)
    path = _berkas()
    with closing(sqlite3.connect(str(path))) as lama:           # berkas v1 seperti image lama membuatnya
        for ddl in dsr._DDL:
            lama.execute(ddl)
        lama.execute("PRAGMA user_version = 1")
        lama.commit()
    assert jt.jumlah_menunggu_kursi(kon) == 0                   # v1 tanpa tabel: kosong, tanpa galat
    assert dsr.dengan_baca(path, lambda k: dsr.ada_tabel(k, jt.TABEL), None) is False
    with closing(sqlite3.connect(str(path))) as f2b:            # berkas yang sudah berisi tabel pola F2b
        for ddl in dsr._DDL_POLA:
            f2b.execute(ddl)
        f2b.commit()
    jt.masuk(kon, AKUN_A, 7, kid, KINI)                         # tulis pertama: DDL tambahan terpasang
    jt.masuk(kon, AKUN_A, 7, kid, "2026-11-25T03:05:00")        # tulis kedua: idempoten
    assert dsr.dengan_baca(path, lambda k: dsr.ada_tabel(k, jt.TABEL), None) is True
    with closing(sqlite3.connect(str(path))) as baca:
        assert baca.execute("PRAGMA user_version").fetchone()[0] == 1
        assert baca.execute("SELECT COUNT(*) FROM tunggu_mini").fetchone()[0] == 1


def test_antrean_admin_nol_bila_berkas_private_tak_terbaca(db):
    with closing(sqlite3.connect(str(_berkas()))) as rusak:
        rusak.execute("PRAGMA user_version = 99")
        rusak.commit()
    assert admin_antrean_tunggu.jumlah(db) == 0


def test_mutasi_guard_kelayakan_kelompok_merah_saat_dimatikan(tmp_path):
    """Kelompok di luar daftar pilihan (tutup / lewat masa akses) dianggap penuh di salinan terisolasi: tes harus merah."""
    salin = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", Path(__file__).name)
    ganti = [("        if pilihan.kelompok_id == kelompok_id:\n            return pilihan.penuh\n    raise jd.JadwalTidakDitemukan()",
              "        if pilihan.kelompok_id == kelompok_id:\n            return pilihan.penuh\n    return True")]
    uji_mutasi(tmp_path, "jadwal_tunggu_mini.py", ganti, Path(__file__).name, TES_MUTASI, salin)


# --- HTTP murid ---------------------------------------------------------------------------------

@pytest.fixture()
def siap(kidup):  # noqa: F811
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    kidup.a = buat_murid(kidup, "murid-a", "Anak Alfa")
    kidup.b = buat_murid(kidup, "murid-b", "Anak Beta")
    return kidup


def _aktifkan(server, murid, kode="mini", isi=JPEG):
    order_id = buat_dan_unggah(server, murid, kode, isi)
    with kelas_store.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_putusan.setujui(kon, order_id, ADMIN, AWAL, bukti_dilihat=bukti_terakhir(order_id))
    return order_id


def _kelompok_http(nama="Mini A", kuota=1, tanggal="2026-11-24"):
    guru = auth.cari_akun("guru-b")["id_akun"]                 # akun guru sintetis yang terdaftar (seperti tes admin)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi=LOKASI, guru_id=guru, kuota=kuota, tanggal=tanggal,
                                jam="09:00", sekarang=AWAL)


def _pilih(server, murid, kelompok_id):
    return kirim(server, M + "/jadwal", murid, {"token": token(murid.akun, "jadwal_pilih:" + kelompok_id),
                                               "kelompok": kelompok_id})


def _masuk(server, murid, kelompok_id, *, tok=None):
    data = {"token": token(murid.akun, "jadwal_tunggu_masuk:" + kelompok_id) if tok is None else tok,
            "kelompok": kelompok_id}
    return kirim(server, MASUK, murid, data)


def _keluar(server, murid, *, tok=None):
    data = {"token": token(murid.akun, "jadwal_tunggu_keluar") if tok is None else tok}
    return kirim(server, KELUAR, murid, data)


def _teks(isi: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", isi.rsplit("</style>", 1)[-1]))


def _siapkan_penuh(siap, server, jam):
    """Kelompok 1 kursi yang sudah diisi anak a; anak b sudah bayar dan belum punya kursi."""
    _aktifkan(server, siap.a)
    jam.maju_jam(1)
    _aktifkan(server, siap.b, isi=PNG)
    kid = _kelompok_http()
    assert _pilih(server, siap.a, kid)[0] == 303
    return kid


def test_penuh_tampil_tombol_masuk_lalu_urutan_dan_tombol_keluar(siap, server, jam):
    kid = _siapkan_penuh(siap, server, jam)
    t = _teks(halaman(siap, siap.b))
    assert JUDUL in t and "penuh" in t and "Masuk daftar tunggu" in t and "Pilih kelompok ini" not in t
    assert _masuk(server, siap.b, kid)[0] == 303
    t = _teks(halaman(siap, siap.b))
    assert "Anda di daftar tunggu kelompok Mini A. Urutan 1." in t and "Keluar dari daftar tunggu" in t
    assert "Masuk daftar tunggu" not in t
    assert _jumlah_tunggu_aktif() == 1


def test_masuk_dan_keluar_token_salah_ditolak_tanpa_efek(siap, server, jam):
    kid = _siapkan_penuh(siap, server, jam)
    assert _masuk(server, siap.b, kid, tok="salah")[0] == 403
    assert _masuk(server, siap.b, kid, tok=token(siap.b.akun, "jadwal_tunggu_masuk:klp_" + "0" * 32))[0] == 403
    assert _keluar(server, siap.b, tok="salah")[0] == 403
    assert _baris_tunggu() == []


def test_keluar_anak_lain_404_dan_entri_tetap(siap, server, jam):
    kid = _siapkan_penuh(siap, server, jam)
    assert _masuk(server, siap.b, kid)[0] == 303
    kode, _isi, _tajuk = _keluar(server, siap.a)                # sesi a tidak punya entri
    assert kode == 404
    assert [b["status"] for b in _baris_tunggu()] == ["menunggu"]


def test_kartu_tanpa_tombol_tunggu_saat_berkas_tak_terbaca_dan_pilih_tetap_ada(siap, server, jam):
    _aktifkan(server, siap.a)
    jam.maju_jam(1)
    _aktifkan(server, siap.b, isi=PNG)
    kid_penuh = _kelompok_http("Mini Penuh", kuota=1)
    assert _pilih(server, siap.b, kid_penuh)[0] == 303          # b mengisi kursi; a masih belum punya kursi
    kid_bebas = _kelompok_http("Mini Bebas", kuota=5, tanggal="2026-11-25")
    with closing(sqlite3.connect(str(_berkas()))) as rusak:     # berkas dengan versi skema asing
        rusak.execute("PRAGMA user_version = 99")
        rusak.commit()
    isi = halaman(siap, siap.a)
    t = _teks(isi)
    assert JUDUL in t and "Mini Penuh" in t and "penuh" in t and "Mini Bebas" in t
    assert "Pilih kelompok ini" in t and kid_bebas in isi
    assert "Masuk daftar tunggu" not in t and 'action="%s"' % MASUK not in isi


def test_admin_hapus_entri_dengan_tinjauan_bertanda_tangan(siap, server, jam):
    kid = _siapkan_penuh(siap, server, jam)
    assert _masuk(server, siap.b, kid)[0] == 303
    cookie = login_admin(siap)
    kode, isi, _ = minta_admin(server, "%s?id=%s" % (KELOMPOK_ADMIN, kid), cookie)
    assert kode == 200 and "Daftar tunggu Mini Class" in isi and "menunggu kursi" in isi
    assert "Anak Beta" not in isi and "murid-b" not in isi        # tanpa nama anak di halaman admin
    form = re.search(r'<form method="post" action="%s"[^>]*>(.*?)</form>' % re.escape(HAPUS_ADMIN), isi, re.S)
    assert form is not None
    sah = {nama: html.unescape(nilai) for nama, nilai in re.findall(r'name="(csrf|tinjauan)" value="([^"]*)"', form.group(1))}
    assert minta_admin(server, HAPUS_ADMIN, cookie, {**sah, "csrf": "salah"})[0] != 303
    assert _baris_tunggu()[0]["status"] == "menunggu"
    assert minta_admin(server, HAPUS_ADMIN, cookie, sah)[0] == 303
    assert _baris_tunggu()[0]["status"] == "dihapus_admin"
