"""Masa paket per anak (`kelas_masa`) dan tampilan banner perpanjang (`kelas_pages.banner_orang_tua`).

Semua data sintetis dari `kelas_kit`. Pembacaan dibuktikan baca-saja: jumlah baris kelas tidak berubah.
"""
from __future__ import annotations

import pytest

import kelas_masa as masa
import kelas_pages as halaman
import pesanan_dasar as d
from kelas_kit import (AKUN_A, AKUN_B, KINI, SESUDAH_UPLOAD, baris, db_kelas, kon_kelas, lunas, menunggu,  # noqa: F401
                       setuju, tagih)

MULAI = SESUDAH_UPLOAD                  # akses satu bulan mulai di sini
BERAKHIR = "2026-12-20T09:30:00"        # satu bulan kalender WIB setelah MULAI
HABIS_KINI = "2026-12-21T09:30:00"      # sesudah BERAKHIR


def _masa(kon, sekarang, akun=AKUN_A, siswa=1):
    return masa.masa_paket_anak(kon, akun, siswa, sekarang)


def _status(kon, sekarang, akun=AKUN_A, siswa=1):
    return [(m.kode_paket, m.status) for m in _masa(kon, sekarang, akun, siswa)]


# --- status dan sisa hari ------------------------------------------------------------------------------

def test_akses_lama_jauh_dari_batas_berstatus_aktif_dengan_sisa_hari_utuh(kon_kelas):
    lunas(kon_kelas, 1, "mini", 1)
    (m,) = _masa(kon_kelas, "2026-11-30T09:30:00")
    assert (m.kode_paket, m.berakhir, m.sisa_hari, m.status) == ("mini", BERAKHIR, 20, masa.STATUS_AKTIF)


@pytest.mark.parametrize("sekarang,sisa,status", [
    ("2026-12-17T09:30:00", 3, masa.STATUS_SEGERA),    # batas atas: sisa tepat 3 hari
    ("2026-12-17T09:30:01", 3, masa.STATUS_SEGERA),    # 2 hari 23:59:59 dibulatkan ke atas menjadi 3
    ("2026-12-17T09:29:59", 4, masa.STATUS_AKTIF),     # 3 hari + 1 detik: sisa 4, belum segera
    ("2026-12-16T09:30:00", 4, masa.STATUS_AKTIF),     # 4 hari: bukan segera
    ("2026-12-19T09:30:00", 1, masa.STATUS_SEGERA),
])
def test_segera_hanya_pada_tiga_hari_terakhir_dengan_pembulatan_ke_atas(kon_kelas, sekarang, sisa, status):
    lunas(kon_kelas, 1, "mini", 1)
    (m,) = _masa(kon_kelas, sekarang)
    assert (m.sisa_hari, m.status) == (sisa, status)


@pytest.mark.parametrize("sekarang", [BERAKHIR, HABIS_KINI])
def test_habis_tepat_saat_berakhir_dan_sesudahnya_dengan_sisa_nol(kon_kelas, sekarang):
    lunas(kon_kelas, 1, "mini", 1)
    (m,) = _masa(kon_kelas, sekarang)
    assert (m.sisa_hari, m.status, m.berakhir) == (0, masa.STATUS_HABIS, BERAKHIR)


def test_pindah_paket_tidak_menandai_paket_lama_berakhir(kon_kelas):
    lunas(kon_kelas, 1, "private", 1)
    lunas(kon_kelas, 1, "mini", 2, putus="2026-11-20T09:35:00")
    hasil = _status(kon_kelas, HABIS_KINI)
    assert hasil == [("mini", masa.STATUS_HABIS)]


def test_tanpa_akses_tidak_ada_masa_sama_sekali(kon_kelas):
    assert _masa(kon_kelas, KINI) == ()


def test_dua_paket_masing_masing_punya_masa_dalam_urutan_katalog(kon_kelas):
    lunas(kon_kelas, 1, "private", 1)
    lunas(kon_kelas, 1, "mini", 2)
    assert _status(kon_kelas, "2026-12-18T09:30:00") == [("private", masa.STATUS_SEGERA),
                                                          ("mini", masa.STATUS_SEGERA)]


# --- order terbuka: pembeli sedang memperpanjang ---------------------------------------------------------

def test_order_belum_bayar_menyembunyikan_paket_itu_dan_tidak_paket_lain(kon_kelas):
    lunas(kon_kelas, 1, "private", 1)
    lunas(kon_kelas, 1, "mini", 2)
    tagih(kon_kelas, 1, "mini", sekarang=HABIS_KINI)
    assert _status(kon_kelas, HABIS_KINI) == [("private", masa.STATUS_HABIS)]


def test_order_menunggu_bukti_juga_menyembunyikan_banner(kon_kelas):
    lunas(kon_kelas, 1, "mini", 1)
    menunggu(kon_kelas, 1, "mini", 2, sekarang=HABIS_KINI, unggah_pada=HABIS_KINI)
    assert _masa(kon_kelas, HABIS_KINI) == ()


# --- perpanjangan yang sudah disetujui tetapi belum mulai ----------------------------------------------

def test_perpanjangan_disetujui_belum_mulai_tidak_memicu_banner(kon_kelas):
    lunas(kon_kelas, 1, "mini", 1)
    assert _status(kon_kelas, "2026-12-17T09:30:00") == [("mini", masa.STATUS_SEGERA)]   # kontrol tanpa perpanjangan
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 2, sekarang="2026-12-17T09:00:00",
                              unggah_pada="2026-12-17T09:10:00")
    setuju(kon_kelas, tagihan, bukti, sekarang="2026-12-17T09:20:00")
    (m,) = _masa(kon_kelas, "2026-12-17T09:30:00")
    assert (m.berakhir, m.status) == ("2027-01-20T09:30:00", masa.STATUS_AKTIF)


# --- kepemilikan dan baca-saja --------------------------------------------------------------------------

def test_akses_milik_akun_lain_tidak_terbaca_dan_pembacaan_tanpa_tulis(kon_kelas):
    lunas(kon_kelas, 1, "mini", 1, akun=AKUN_B)
    sebelum = baris(kon_kelas, "kelas_akses") + baris(kon_kelas, "kelas_order")
    assert _masa(kon_kelas, HABIS_KINI, akun=AKUN_A) == ()
    (m,) = _masa(kon_kelas, HABIS_KINI, akun=AKUN_B)
    assert m.status == masa.STATUS_HABIS
    assert baris(kon_kelas, "kelas_akses") + baris(kon_kelas, "kelas_order") == sebelum


@pytest.mark.parametrize("akun,siswa", [("", 1), ("bukan akun", 1), (AKUN_A, 0), (AKUN_A, "1")])
def test_masukan_tidak_sah_ditolak(kon_kelas, akun, siswa):
    with pytest.raises(d.PesananDataTidakSah):
        masa.masa_paket_anak(kon_kelas, akun, siswa, KINI)


# --- banner halaman orang tua (render murni) --------------------------------------------------------------

def _m(kode, status, sisa, nama="Private"):
    return masa.MasaPaket(kode, nama, BERAKHIR, sisa, status)


def test_banner_kosong_bila_tak_ada_paket_yang_perlu_perhatian():
    assert halaman.banner_orang_tua((), "Raka") == ""
    assert halaman.banner_orang_tua((_m("mini", masa.STATUS_AKTIF, 20, "Mini Class"),), "Raka") == ""


def test_banner_segera_menyebut_sisa_hari_dan_tautan_perpanjang():
    isi = halaman.banner_orang_tua((_m("private", masa.STATUS_SEGERA, 3),), "Raka")
    assert 'id="ortu-paket-banner"' in isi and 'role="status"' in isi and isi.startswith("<p ")
    assert "Segera berakhir" in isi and "Paket Private Raka berakhir 3 hari lagi." in isi
    assert '<a href="/murid/paket">Perpanjang</a>' in isi


def test_banner_habis_menyebut_sudah_berakhir_dan_jadwal_baru():
    isi = halaman.banner_orang_tua((_m("mini", masa.STATUS_HABIS, 0, "Mini Class"),), "Raka")
    assert "Sudah berakhir" in isi and "Paket Mini Class Raka sudah berakhir." in isi
    assert "untuk mendapat jadwal baru." in isi and '<a href="/murid/paket">Perpanjang</a>' in isi


def test_nama_anak_dan_nama_paket_di_escape():
    isi = halaman.banner_orang_tua((_m("private", masa.STATUS_SEGERA, 2, "<b>Paket</b>"),),
                                   "<img src=x onerror=1>")
    assert "<img" not in isi and "<b>Paket" not in isi
    assert "&lt;img src=x onerror=1&gt;" in isi and "&lt;b&gt;Paket&lt;/b&gt;" in isi


def test_dua_paket_satu_elemen_dengan_satu_baris_per_paket():
    isi = halaman.banner_orang_tua((_m("private", masa.STATUS_SEGERA, 2),
                                    _m("mini", masa.STATUS_HABIS, 0, "Mini Class")), "Raka")
    assert isi.count('id="ortu-paket-banner"') == 1
    assert isi.count("<br>") == 1 and isi.count("Perpanjang") == 2


# --- tagihan belum dibayar (butir QA #3, notifikasi gantung) ----------------------------------------------

def test_tagihan_belum_dibayar_terbaca_dan_hilang_setelah_bukti_menunggu(kon_kelas):
    from kelas_kit import tagih, unggah
    tagih(kon_kelas, paket="mini")
    (item,) = masa.tagihan_belum_dibayar(kon_kelas, AKUN_A, 1, KINI)
    assert (item.kode_paket, item.nama, item.status) == ("mini", "Mini Class", "belum_bayar")
    unggah(kon_kelas, paket="mini", sekarang=SESUDAH_UPLOAD)
    assert masa.tagihan_belum_dibayar(kon_kelas, AKUN_A, 1, SESUDAH_UPLOAD) == ()


def test_tagihan_ditolak_masih_terbaca_selama_jendela_terbuka(kon_kelas):
    import kelas_putusan
    from kelas_kit import ADMIN
    tagihan, bukti_id = menunggu(kon_kelas, paket="mini")
    kelas_putusan.tolak(kon_kelas, tagihan.order_id, ADMIN, "Nominal kurang", SESUDAH_UPLOAD, bukti_dilihat=bukti_id)
    (item,) = masa.tagihan_belum_dibayar(kon_kelas, AKUN_A, 1, SESUDAH_UPLOAD)
    assert item.status == "ditolak"


def test_tagihan_kedaluwarsa_dan_akun_lain_tidak_terbaca(kon_kelas):
    from kelas_kit import SESUDAH_JENDELA, tagih
    tagih(kon_kelas, paket="private")
    assert masa.tagihan_belum_dibayar(kon_kelas, AKUN_B, 1, KINI) == ()
    assert masa.tagihan_belum_dibayar(kon_kelas, AKUN_A, 1, SESUDAH_JENDELA) == ()


def test_banner_tagihan_kosong_dan_escape():
    assert halaman.banner_tagihan((), "Anak") == ""
    item = masa.TagihanBelumBayar("mini", "Mini <b>", "2026-11-21T09:00:00", "belum_bayar")
    isi = halaman.banner_tagihan((item,), "<script>")
    assert "<script>" not in isi and "&lt;script&gt;" in isi and "Mini &lt;b&gt;" in isi


def test_banner_hanya_tagihan_terbaru_setelah_ganti_paket(kon_kelas):
    import kelas_ganti
    from kelas_kit import pilih_pertama, tagih
    tagih(kon_kelas, paket="mini")
    kelas_ganti.ganti_paket(kon_kelas, AKUN_A, 1, "private", SESUDAH_UPLOAD, acak=pilih_pertama)
    (item,) = masa.tagihan_belum_dibayar(kon_kelas, AKUN_A, 1, SESUDAH_UPLOAD)
    assert item.kode_paket == "private"
