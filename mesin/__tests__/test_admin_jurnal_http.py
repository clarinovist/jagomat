"""Halaman admin baca-saja `/admin/jadwal/jurnal` (jurnal pertemuan): akses, konten, dan tanpa efek samping.

Data sintetis (kelas_kit di DB admin sementara lewat kidup). Jam dipatok lewat `admin_jurnal_http._sekarang`; catatan
di GURU_PERTEMUAN_DB sementara. Bagian pure render (admin_jurnal_pages) diuji tanpa DB.
"""
from __future__ import annotations

import hashlib
from contextlib import closing
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

import admin_antrean_jurnal as aj
import admin_jurnal_http as jh
import admin_jurnal_pages as ui
import admin_store
import auth
import guru_pertemuan_aturan as aturan
import jadwal_store as js
import kelas_kit
import pesanan
import schema_jadwal
from admin_pesanan_kit import login_admin, minta_admin
from cek_http_kit import AKUN_A as AKUN_GURU_BASIC
from cek_http_kit import minta_mentah
from kelas_http_kit import jam, kidup, kmati, server  # noqa: F401

RUTE = jh.RUTE
TAK_ADA = "/admin/tidak-ada"
ADMIN_SINTETIS = "admin_sintetis"
CUTOFF = "2026-11-20T00:00:00"
KINI = "2026-11-27T12:00:00"
TEPAT_AKSI = "2026-11-26T11:00:00"
MASA_DEPAN = "2026-11-28T09:00:00"
MENIT = 60


def _epoch(baku: str) -> float:
    return datetime.strptime(baku, aturan.FORMAT_WAKTU).replace(tzinfo=timezone.utc).timestamp()


@pytest.fixture()
def siap(kidup, monkeypatch, tmp_path):  # noqa: F811
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    monkeypatch.setenv("GURU_PERTEMUAN_DB", str(_berkas_catatan(tmp_path)))
    monkeypatch.setattr(jh, "_sekarang", lambda: _epoch(KINI))
    return kidup


@pytest.fixture()
def admin(siap):
    return login_admin(siap)


def _berkas_catatan(tmp_path) -> Path:
    return tmp_path / "guru-pertemuan.db"


def _hash_berkas(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _guru_id(nama: str) -> str:
    return auth.cari_akun(nama)["id_akun"]


def _privat_berjadwal(siswa: int, guru: str, mulai: str) -> str:
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        tagihan = kelas_kit.lunas(kon, siswa, "private", n=siswa)  # n = benih sha bukti: harus unik per order
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        js.tempatkan(kon, ADMIN_SINTETIS, tagihan.order_id, guru_id=_guru_id(guru), tanggal="2026-11-23",
                     jam="16:30", sekarang=kelas_kit.SESUDAH_UPLOAD)
        kon.execute("UPDATE jadwal_pertemuan SET mulai=?, menit=?, dibatalkan=0 WHERE order_id=? AND ke=1",
                    (mulai, MENIT, tagihan.order_id))
        kon.execute("UPDATE jadwal_pertemuan SET mulai=?, menit=?, dibatalkan=0 WHERE order_id=? AND ke>1",
                    (MASA_DEPAN, MENIT, tagihan.order_id))
        kon.commit()
    return tagihan.order_id


def _aktifkan_cutoff(monkeypatch):
    monkeypatch.setattr(aturan, "PERTEMUAN_WAJIB_SEJAK", CUTOFF)


# --- akses ----------------------------------------------------------------------------------

def test_anonim_dan_guru_mendapat_404_identik_dengan_rute_tak_dikenal(siap):
    acuan = minta_mentah(siap, TAK_ADA, None, None)[:2]
    for akun in (None, AKUN_GURU_BASIC):
        assert minta_mentah(siap, RUTE, akun, None)[:2] == acuan


def test_query_tidak_dikenal_di_halaman_jurnal_404(siap, admin):
    assert minta_admin(siap, RUTE + "?x=1", admin)[0] == 404


# --- konten ---------------------------------------------------------------------------------

def test_admin_melihat_banner_belum_aktif_saat_cutoff_kosong(siap, admin):
    kode, isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 200
    assert "Jurnal pertemuan" in isi
    assert ui.BANNER_BELUM in isi
    assert "Perlu diisi (0)" in isi


def test_banner_aktif_dan_baris_pertemuan_tampil_tanpa_id_anak(siap, admin, monkeypatch):
    _aktifkan_cutoff(monkeypatch)
    order_id = _privat_berjadwal(1, "guru-b", TEPAT_AKSI)
    kode, isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 200
    assert "Peringatan aktif untuk pertemuan mulai 20 November 2026 pukul 07.00 WIB" in isi
    assert "Perlu diisi (1)" in isi
    assert "26 November 2026 pukul 18.00 WIB" in isi
    assert "Private" in isi and "guru-b" in isi
    assert order_id not in isi
    assert "kor_" not in isi and "klp_" not in isi and "akun_" not in isi


def test_halaman_kosong_menampilkan_keadaan_ramah(siap, admin, monkeypatch):
    _aktifkan_cutoff(monkeypatch)
    kode, isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 200
    assert "Perlu diisi (0)" in isi
    assert ui.COPY_KOSONG_PERLU in isi


def test_pembacaan_tidak_mengubah_db_admin_dan_tidak_membuat_catatan(siap, admin, monkeypatch, tmp_path):
    _aktifkan_cutoff(monkeypatch)
    _privat_berjadwal(1, "guru-b", TEPAT_AKSI)
    sebelum = _hash_berkas(admin_store.BAWAAN)
    kode, _isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 200
    assert _hash_berkas(admin_store.BAWAAN) == sebelum
    assert not _berkas_catatan(tmp_path).exists()


def test_batas_tampil_dan_teks_terpotong(siap, admin, monkeypatch):
    _aktifkan_cutoff(monkeypatch)
    monkeypatch.setattr(aj, "BATAS_TAMPIL", 1)
    _privat_berjadwal(1, "guru-b", TEPAT_AKSI)
    _privat_berjadwal(2, "guru-b", "2026-11-25T10:00:00")
    kode, isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 200
    assert "Menampilkan 1 terbaru dari 2" in isi
    assert "25 November 2026" not in isi


def test_galat_baca_catatan_menampilkan_peringatan(siap, admin, monkeypatch, tmp_path):
    _aktifkan_cutoff(monkeypatch)
    _privat_berjadwal(1, "guru-b", TEPAT_AKSI)
    _berkas_catatan(tmp_path).write_bytes(b"bukan sqlite " * 100)
    kode, isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 200
    assert ui.COPY_CATATAN_TIDAK_TERBACA in isi
    assert "Perlu diisi (0)" in isi


def test_db_admin_tak_terbaca_menjawab_503(siap, admin, monkeypatch):
    _aktifkan_cutoff(monkeypatch)

    def gagal(*_args, **_kwargs):
        raise admin_store.StoreBelumSiap("uji")

    monkeypatch.setattr(aj, "daftar", gagal)
    kode, _isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 503


# --- render murni (tanpa DB) ------------------------------------------------------------------

def _daftar_contoh(**ubah):
    dasar = {
        "aktif": True, "sejak": CUTOFF, "catatan_terbaca": True,
        "perlu_diisi": [{"jenis": "privat", "nama": "Private", "ke": 2, "mulai": TEPAT_AKSI,
                         "guru_id": "akun_" + "a" * 32}],
        "total_perlu_diisi": 1,
        "riwayat": [], "total_riwayat": 0, "riwayat_terpotong": False,
    }
    return {**dasar, **ubah}


def test_render_guru_tanpa_peta_tampil_sebagai_guru_tidak_aktif():
    isi = ui.halaman(_daftar_contoh(), {})
    assert "Guru tidak aktif" in isi
    assert "akun_" not in isi


def test_render_escape_nama_kelompok():
    item = {"jenis": "kelompok", "nama": "<b>x</b>", "ke": 1, "mulai": TEPAT_AKSI, "guru_id": "akun_" + "a" * 32}
    isi = ui.halaman(_daftar_contoh(perlu_diisi=[item], total_perlu_diisi=1), {"akun_" + "a" * 32: "guru-x"})
    assert "<b>x</b>" not in isi
    assert "&lt;b&gt;x&lt;/b&gt;" in isi


def test_render_banner_belum_aktif_dan_catatan_tidak_terbaca():
    isi = ui.halaman(_daftar_contoh(aktif=False, sejak=None, perlu_diisi=[], total_perlu_diisi=0), {})
    assert ui.BANNER_BELUM in isi
    isi_rusak = ui.halaman(_daftar_contoh(catatan_terbaca=False), {})
    assert ui.COPY_CATATAN_TIDAK_TERBACA in isi_rusak


def test_render_teks_terpotong_memakai_panjang_daftar_dan_total():
    item = {"jenis": "privat", "nama": "Private", "ke": 1, "mulai": TEPAT_AKSI, "guru_id": "akun_" + "a" * 32}
    isi = ui.halaman(_daftar_contoh(perlu_diisi=[item, item], total_perlu_diisi=5), {})
    assert "Menampilkan 2 terbaru dari 5" in isi


def test_render_riwayat_terpotong_menampilkan_catatan():
    isi = ui.halaman(_daftar_contoh(riwayat_terpotong=True), {})
    assert ui.COPY_RIWAYAT_TERPOTONG in isi
