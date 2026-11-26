"""Hapus tagihan Paket Belajar dan pilih ulang lewat HTTP nyata (data sintetis).

Hapus hanya untuk tagihan belum_bayar tanpa bukti, lewat halaman konfirmasi dengan akibat uang. Tanpa tabel catatan tombol
hapus tidak tampil dan POST ditolak tanpa tulis. Tiap kasus membuktikan efek (atau ketiadaannya) dari DB, bukan hanya kode status.
"""
from __future__ import annotations

import re

import pytest

from bukti_kit import JPEG
from kelas_http_kit import (M, baca_admin, buat, buat_murid, halaman, hapus_halaman, hapus_tagihan, hitung, jam, kidup, kmati,  # noqa: F401
                            pasang_catatan, peta_lunas_untuk, server, tagihan_halaman, token, unggah)

TAUTAN_MINI = 'href="/murid/paket/tagihan?kode=mini"'
TAUTAN_PRIVATE = 'href="/murid/paket/tagihan?kode=private"'
AKIBAT_UANG = "Jangan transfer ke tagihan ini setelah dihapus."
AKIBAT_TERLANJUR = ("Bila Anda sudah terlanjur mentransfer, hubungi tim lewat WhatsApp dulu sebelum menghapus.")
COPY_KONFLIK_PILIH = "belum bisa dipilih lagi sampai waktu bayar tagihan sebelumnya habis"


def _teks(isi):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", isi.rsplit("</style>", 1)[-1]))


def _catatan():
    return [r["aksi"] for r in baca_admin("SELECT aksi FROM tagihan_catatan ORDER BY id")]


@pytest.fixture()
def siap(kidup):
    """Server dengan tabel catatan tagihan terpasang (batal/pulih aktif)."""
    pasang_catatan()
    return kidup


@pytest.fixture()
def anak(siap):
    murid = buat_murid(siap, "murid-a", "Anak Alfa")
    assert buat(siap, murid, "mini")[0] == 303
    return murid


# --- tanpa tabel catatan: gagal tertutup -------------------------------------------------------------

def test_tanpa_tabel_catatan_tombol_hapus_tidak_tampil_dan_post_ditolak_tanpa_tulis(kidup):
    murid = buat_murid(kidup, "murid-a", "Anak Alfa")
    assert buat(kidup, murid, "mini")[0] == 303
    assert TAUTAN_MINI in halaman(kidup, murid) and "/murid/paket/hapus?kode=mini" not in halaman(kidup, murid)
    assert hapus_halaman(kidup, murid, "mini")[0] == 404
    awal = hitung()
    assert hapus_tagihan(kidup, murid, "mini")[0] == 409
    assert hitung() == awal and baca_admin("SELECT COUNT(*) AS n FROM kelas_order")[0]["n"] == 1


# --- halaman konfirmasi -----------------------------------------------------------------------------

def test_konfirmasi_hapus_memuat_akibat_uang_dan_tombol_post(siap, anak):
    kode, isi, _ = hapus_halaman(siap, anak, "mini")
    t = _teks(isi)
    assert kode == 200 and "Ya, hapus tagihan" in t and "Mini Class" in t
    assert AKIBAT_UANG in t and AKIBAT_TERLANJUR in t
    assert 'action="/murid/paket/hapus"' in isi and 'href="/murid/paket/tagihan?kode=mini"' in isi
    assert "kor_" not in isi and _catatan() == []


def test_konfirmasi_hapus_404_bila_tagihan_sudah_ada_bukti_tanpa_tulis(siap, anak):
    assert unggah(siap, anak, JPEG)[0] == 303
    kode_tanpa, isi_tanpa, _ = hapus_halaman(siap, anak, "private")
    kode, isi, _ = hapus_halaman(siap, anak, "mini")
    assert (kode, kode_tanpa) == (404, 404) and isi == isi_tanpa
    assert _catatan() == []


# --- POST hapus ---------------------------------------------------------------------------------------

def test_hapus_sukses_lalu_daftar_tanpa_tagihan_dan_halaman_tagihan_404(siap, anak):
    kode, _, tajuk = hapus_tagihan(siap, anak, "mini")
    assert (kode, tajuk["Location"]) == (303, M)
    assert _catatan() == ["batal"]
    isi = halaman(siap, anak)
    assert TAUTAN_MINI not in isi and "Daftar paket ini" in _teks(isi)
    assert "Memilih lagi memulihkan tagihan yang tadi dihapus" in _teks(isi) and "kor_" not in isi
    assert tagihan_halaman(siap, anak, "mini")[0] == 404


def test_hapus_hanya_paket_yang_dipilih_dan_tagihan_lain_tetap_terbuka(siap, anak):
    assert buat(siap, anak, "private")[0] == 303
    assert hapus_tagihan(siap, anak, "mini")[0] == 303
    isi = halaman(siap, anak)
    assert TAUTAN_PRIVATE in isi and TAUTAN_MINI not in isi
    assert _catatan() == ["batal"]


def test_token_salah_atau_untuk_aksi_atau_kode_lain_403_tanpa_efek(siap, anak):
    kandidat = ("1.salah", token(anak.akun, "kelas_buat:mini"), token(anak.akun, "kelas_hapus:private"))
    for tok in kandidat:
        assert hapus_tagihan(siap, anak, "mini", tok=tok)[0] == 403, tok
    assert _catatan() == [] and tagihan_halaman(siap, anak, "mini")[0] == 200


def test_kode_asing_400_tanpa_efek(siap, anak):
    assert hapus_tagihan(siap, anak, "gratis", tok=token(anak.akun, "kelas_hapus:gratis"))[0] == 400
    assert _catatan() == []


def test_akun_lain_404_identik_dan_tanpa_efek(siap, anak):
    lain = buat_murid(siap, "murid-b", "Anak Beta")
    dengan_tagihan_milik_lain = hapus_tagihan(siap, lain, "mini")
    tanpa_tagihan = hapus_tagihan(siap, lain, "private")
    assert dengan_tagihan_milik_lain[0] == tanpa_tagihan[0] == 404
    assert dengan_tagihan_milik_lain[1] == tanpa_tagihan[1]
    assert _catatan() == [] and tagihan_halaman(siap, anak, "mini")[0] == 200


def test_bukti_sudah_ada_409_tanpa_tulis(siap, anak):
    assert unggah(siap, anak, JPEG)[0] == 303
    awal = hitung()
    assert hapus_tagihan(siap, anak, "mini")[0] == 409
    assert _catatan() == [] and hitung() == awal


# --- pilih ulang memulihkan tagihan ---------------------------------------------------------------

def test_pilih_ulang_setelah_hapus_memulihkan_tagihan_yang_sama_tanpa_order_baru(siap, anak):
    (asli,) = baca_admin("SELECT id FROM kelas_order")
    assert hapus_tagihan(siap, anak, "mini")[0] == 303
    assert buat(siap, anak, "mini")[0] == 303
    assert baca_admin("SELECT id FROM kelas_order") == [asli]
    assert _catatan() == ["batal", "pulih"]
    assert _teks(halaman(siap, anak)).count("Menunggu pembayaran") == 1


def test_pilih_ulang_ditolak_bila_deposit_sudah_dipakai_tagihan_lain_pesan_jelas(siap):
    murid = buat_murid(siap, "murid-e", "Anak Epsilon")
    peta_lunas_untuk(murid)
    assert buat(siap, murid, "mini")[0] == 303                 # mini memegang deposit Peta
    assert hapus_tagihan(siap, murid, "mini")[0] == 303
    assert buat(siap, murid, "private")[0] == 303              # private mengambil deposit
    awal = baca_admin("SELECT COUNT(*) AS n FROM kelas_order")[0]["n"]
    kode, isi, _ = buat(siap, murid, "mini")
    assert kode == 409 and COPY_KONFLIK_PILIH in _teks(isi)
    assert baca_admin("SELECT COUNT(*) AS n FROM kelas_order")[0]["n"] == awal
    assert _catatan() == ["batal"]
