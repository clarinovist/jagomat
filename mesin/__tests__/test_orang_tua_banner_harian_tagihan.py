"""Banner tagihan Latihan Harian yang belum dibayar di halaman orang tua (data sintetis; unit dan HTTP nyata).

Hanya untuk order belum_bayar atau ditolak yang jendela bayarnya masih terbuka. Tidak tampil saat menunggu verifikasi,
lunas, kedaluwarsa, tanpa order, sakelar LATIHAN_HARIAN mati, atau murid les. Tanpa id order, nama anak, dan nominal.
"""
from __future__ import annotations

import pytest

import database
import harian_langganan_putusan as putusan
import harian_langganan_store as store
import lembaga_store
import orang_tua_data
import orang_tua_pages
from harian_kit import (buat, buat_murid, hidup, jam, mati, minta_mentah, satu_order, server,  # noqa: F401
                        unggah)

T0 = "2026-11-23T03:00:00"             # order dibuat; jendela bayar 24 jam
SESUDAH_T0 = "2026-11-23T04:00:00"     # masih dalam jendela bayar
KEDALUWARSA = "2026-11-24T03:00:00"    # tepat habis jendela bayar
AKUN = "akun_" + "a" * 32
ANAK = "Anak Sintetis"
JALUR = "/murid/orang-tua"
PENANDA = 'id="ortu-harian-tagihan-banner"'


@pytest.fixture
def kon(tmp_path, monkeypatch):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada.db"))
    monkeypatch.setenv("LATIHAN_HARIAN", "1")
    monkeypatch.delenv("OSN_LEMBAGA_ANTREAN", raising=False)
    with database.buka(jalur) as k:
        yield k


def _anak(kon, nama=ANAK, pemilik="guru"):
    siswa = kon.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES (?, 'P3', ?)", (nama, pemilik)).lastrowid
    kon.commit()
    return siswa


def _tagihan(kon, siswa, waktu=T0):
    return store.buat_tagihan(kon, siswa, "bulanan", waktu)


def _bukti(kon, siswa, waktu=T0):
    n = kon.execute("SELECT COUNT(*) FROM harian_bukti").fetchone()[0] + 1
    return store.catat_bukti(kon, siswa, "image/png", 10, "%064x" % n, "%032x" % n, waktu)


def _halaman(kon, siswa, kini):
    data = orang_tua_data.kumpulkan(kon, AKUN, siswa, kini)
    return orang_tua_pages.halaman_isi(data, False).decode()


def _banner(html):
    awal = html.index(PENANDA)
    return html[awal:html.index("</p>", awal)]


# --- unit: keadaan tagihan dan gerbang ---------------------------------------------------------

def test_belum_bayar_menampilkan_banner_dengan_nama_paket_dan_tautan_bayar(kon):
    # Arrange
    siswa = _anak(kon)
    _tagihan(kon, siswa)
    # Act
    html = _halaman(kon, siswa, SESUDAH_T0)
    # Assert
    assert PENANDA in html
    banner = _banner(html)
    assert "Belum dibayar" in banner and "Tagihan Latihan Harian Bulanan belum dibayar." in banner
    assert 'href="/murid/langganan"' in banner and "Lanjutkan pembayaran" in banner


def test_bukti_ditolak_menampilkan_bukti_belum_sesuai(kon):
    # Arrange
    siswa = _anak(kon)
    order = _tagihan(kon, siswa)["order_id"]
    bukti = _bukti(kon, siswa)
    putusan.tolak(kon, order, "admin_sintetis", "Nominal tidak cocok", SESUDAH_T0, bukti_dilihat=bukti["bukti_id"])
    # Act
    banner = _banner(_halaman(kon, siswa, SESUDAH_T0))
    # Assert
    assert "Bukti belum sesuai" in banner and "bukti ditolak." in banner
    assert 'href="/murid/langganan"' in banner and "Lanjutkan pembayaran" in banner


def test_bukti_menunggu_verifikasi_tanpa_banner(kon):
    siswa = _anak(kon)
    _tagihan(kon, siswa)
    _bukti(kon, siswa)
    assert PENANDA not in _halaman(kon, siswa, SESUDAH_T0)


def test_tagihan_lunas_tanpa_banner(kon):
    siswa = _anak(kon)
    order = _tagihan(kon, siswa)["order_id"]
    bukti = _bukti(kon, siswa)
    putusan.setujui(kon, order, "admin_sintetis", SESUDAH_T0, bukti_dilihat=bukti["bukti_id"])
    assert PENANDA not in _halaman(kon, siswa, SESUDAH_T0)


def test_jendela_bayar_lewat_tanpa_banner(kon):
    siswa = _anak(kon)
    _tagihan(kon, siswa)
    assert PENANDA not in _halaman(kon, siswa, KEDALUWARSA)


def test_tanpa_order_tanpa_banner(kon):
    siswa = _anak(kon)
    assert PENANDA not in _halaman(kon, siswa, SESUDAH_T0)


def test_sakelar_latihan_harian_mati_tanpa_banner(kon, monkeypatch):
    siswa = _anak(kon)
    _tagihan(kon, siswa)
    monkeypatch.delenv("LATIHAN_HARIAN")
    html = _halaman(kon, siswa, SESUDAH_T0)
    assert PENANDA not in html and "ortu-langganan" not in html


def test_murid_les_tanpa_banner_walau_ada_tagihan_terbuka(kon, monkeypatch):
    lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik="koordinator-uji")
    kon.execute("INSERT INTO anggota_lembaga (lembaga_id, guru) VALUES (1, 'guru-anggota')")
    kon.commit()
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", "1")
    siswa = _anak(kon, pemilik="guru-anggota")
    _tagihan(kon, siswa)
    html = _halaman(kon, siswa, SESUDAH_T0)
    assert "murid les" in html and PENANDA not in html


def test_banner_tidak_memuat_id_order_nama_anak_atau_nominal(kon):
    siswa = _anak(kon, "Anak Rahasia")
    order = _tagihan(kon, siswa)["order_id"]
    banner = _banner(_halaman(kon, siswa, SESUDAH_T0))
    assert order not in banner and "hor_" not in banner
    assert "Anak Rahasia" not in banner and "Rp" not in banner


def test_tagihan_anak_lain_tidak_muncul(kon):
    anak_a = _anak(kon, "Anak A")
    anak_b = _anak(kon, "Anak B")
    _tagihan(kon, anak_a)
    assert PENANDA in _halaman(kon, anak_a, SESUDAH_T0)
    assert PENANDA not in _halaman(kon, anak_b, SESUDAH_T0)


# --- HTTP nyata: /murid/orang-tua dengan akun murid sintetis --------------------------------------

@pytest.fixture()
def murid(hidup, jam, monkeypatch):
    """Akun murid bertaut ke anak sintetis; jam halaman orang tua mengikuti jam uji (order dibuat di jam yang sama)."""
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setattr(orang_tua_data, "_sekarang_baku", jam)
    return buat_murid(hidup, "murid-banner-harian", ANAK)


def _halaman_http(server_uji, murid):
    kode, isi, _ = minta_mentah(server_uji, JALUR, murid.akun)
    assert kode == 200
    return isi


def test_http_belum_bayar_menampilkan_banner(hidup, murid):
    assert buat(hidup, murid)[0] == 303
    assert PENANDA in _halaman_http(hidup, murid)


def test_http_tanpa_order_tanpa_banner(hidup, murid):
    assert PENANDA not in _halaman_http(hidup, murid)


def test_http_bukti_menunggu_tanpa_banner(hidup, murid):
    assert buat(hidup, murid)[0] == 303
    assert unggah(hidup, murid)[0] == 303
    assert PENANDA not in _halaman_http(hidup, murid)


def test_http_ditolak_menampilkan_bukti_belum_sesuai(hidup, murid, jam):
    assert buat(hidup, murid)[0] == 303
    assert unggah(hidup, murid)[0] == 303
    order = satu_order(hidup)["id"]
    with hidup.buka() as kon:
        bukti = kon.execute("SELECT MAX(id) FROM harian_bukti").fetchone()[0]
        putusan.tolak(kon, order, "admin_sintetis", "Nominal tidak cocok", jam(), bukti_dilihat=bukti)
    assert "Bukti belum sesuai" in _banner(_halaman_http(hidup, murid))


def test_http_banner_tidak_memuat_id_order(hidup, murid):
    assert buat(hidup, murid)[0] == 303
    order = satu_order(hidup)["id"]
    assert order not in _banner(_halaman_http(hidup, murid))


def test_http_sakelar_mati_tanpa_banner(hidup, murid, monkeypatch):
    assert buat(hidup, murid)[0] == 303
    monkeypatch.delenv("LATIHAN_HARIAN")
    assert PENANDA not in _halaman_http(hidup, murid)


def test_http_tagihan_anak_lain_tidak_muncul_di_akun_murid_ini(hidup, murid):
    lain = buat_murid(hidup, "murid-banner-lain", "Anak Lain")
    assert buat(hidup, lain)[0] == 303
    assert PENANDA not in _halaman_http(hidup, murid)
    assert PENANDA in _halaman_http(hidup, lain)
