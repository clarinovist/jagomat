"""Halaman /murid/langganan gaya ceria (F3): pilih paket, tagihan, status (murni render, data sintetis)."""
import re
from types import MappingProxyType, SimpleNamespace

import pytest

import harian_langganan_dasar as dasar
import harian_langganan_pages as halaman
import harian_langganan_ringkas as ringkas
import pesanan_murid_pages

BERAKHIR = "2026-12-23T03:00:00"
REKENING = SimpleNamespace(nama_bank="Bank Contoh", nomor_label="1234 5678 90", atas_nama="PT Contoh Sintetis")


def _token(aksi):
    return "tok." + aksi


def _tampil(status=dasar.STATUS_BELUM_BAYAR, paket="bulanan", alasan=None, jumlah_bukti=0, boleh=True):
    return SimpleNamespace(paket=dasar.PAKET[paket], nominal=dasar.PAKET[paket].rupiah + 427, status=status,
                           kedaluwarsa="2026-11-25T03:00:00", alasan_tolak=alasan, jumlah_bukti=jumlah_bukti,
                           boleh_unggah=boleh)


def _gratis():
    return ringkas.Ringkasan("gratis", None, 0, None)


def _aktif(tagihan=None):
    return ringkas.Ringkasan("langganan", BERAKHIR, 20, tagihan)


def _halaman(r, tampil=None, rekening=REKENING) -> str:
    """Hanya `<body>`: CSS di `<head>` memuat nama kelas dan kata yang bukan teks tampil."""
    return halaman.halaman_langganan(r, tampil, rekening, _token).decode().split("</head>", 1)[1]


def _teks(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _maskot(html: str) -> int:
    return html.count('class="ceria-maskot"')


# --- pilih paket -------------------------------------------------------------------------------

def test_pilih_paket_dua_form_native_dengan_teks_tombol_lama():
    html = _halaman(_gratis())
    assert html.count('action="/murid/langganan/buat"') == 2 and html.count("<form") == 2
    assert "Pilih Bulanan Rp39.000" in html and "Pilih Tahunan Rp349.000" in html
    assert 'value="tok.harian_buat:bulanan"' in html and 'value="tok.harian_buat:tahunan"' in html
    assert html.count('<button type="submit"') == 2 and "Pilih yang cocok ya, Ayah/Bunda!" in html


def test_pilih_paket_tahunan_paling_hemat_dihitung_dari_paket():
    teks = _teks(_halaman(_gratis()))
    assert "Paling hemat" in teks and "Setara sekitar Rp29.000/bulan" in teks and "Hemat Rp119.000" in teks
    assert teks.count("Paling hemat") == 1 and teks.count("Hemat Rp") == 1


def test_hemat_dan_setara_bukan_angka_tulis_tangan(monkeypatch):
    paket = MappingProxyType({
        "bulanan": dasar.Paket("bulanan", "Bulanan", 50000, 1),
        "tahunan": dasar.Paket("tahunan", "Tahunan", 480000, 12),
    })
    monkeypatch.setattr(dasar, "PAKET", paket)
    teks = _teks(_halaman(_gratis()))
    assert "Hemat Rp120.000" in teks and "Setara sekitar Rp40.000/bulan" in teks
    assert "Rp119.000" not in teks and "Rp29.000" not in teks
    assert "Pilih Tahunan Rp480.000" in teks


@pytest.mark.parametrize("harga_tahunan", [600000, 650000])
def test_tanpa_hemat_stiker_dan_angka_hemat_disembunyikan(monkeypatch, harga_tahunan):
    monkeypatch.setattr(dasar, "PAKET", MappingProxyType({
        "bulanan": dasar.Paket("bulanan", "Bulanan", 50000, 1),
        "tahunan": dasar.Paket("tahunan", "Tahunan", harga_tahunan, 12)}))
    teks = _teks(_halaman(_gratis()))
    assert "Paling hemat" not in teks and "Hemat Rp" not in teks and "Setara sekitar" not in teks


def test_hitung_hemat_membulatkan_setara_ke_ribuan():
    tahunan = dasar.PAKET["tahunan"]
    assert halaman.hitung_hemat(tahunan) == (29000, 119000)
    assert halaman.hitung_hemat(dasar.PAKET["bulanan"]) is None


def test_perpanjang_mengganti_teks_tombol_dan_hanya_satu_maskot():
    html = _halaman(_aktif())
    assert "Perpanjang Bulanan Rp39.000" in html and "Perpanjang Tahunan Rp349.000" in html
    assert "Pilih Bulanan" not in html and _maskot(html) == 1  # hero aktif; "menunjuk" tidak ikut


# --- tagihan -----------------------------------------------------------------------------------

def test_tagihan_nominal_besar_catatan_tulisan_tangan_dan_langkah():
    html = _halaman(_gratis(), _tampil())
    assert '<p class="lg-nominal"><strong>Rp39.427</strong></p>' in html
    assert "Transfer persis ya. Tiga angka terakhir = kode unik." in html and 'class="lg-tulis"' in html
    assert re.findall(r"<li[^>]*>(\d [^<]+)", html) == ["1 Transfer", "2 Unggah bukti", "3 Aktif"]
    assert 'aria-current="step"' in html and "(langkah sekarang)" in html
    assert "Bank Contoh" in html and "1234 5678 90" in html and "PT Contoh Sintetis" in html
    assert "25 November 2026 pukul 10.00 WIB" in _teks(html) and "lg-kertas" in html


def test_tagihan_form_unggah_tetap_fungsional():
    html = _halaman(_gratis(), _tampil())
    assert 'action="/murid/langganan/bukti"' in html and 'enctype="multipart/form-data"' in html
    assert 'name="berkas" accept="image/jpeg,image/png,application/pdf" required' in html
    assert 'name="token" value="tok.harian_bukti"' in html and ">Unggah bukti<" in html and _maskot(html) == 0


def test_tagihan_tanpa_rekening_tidak_menampilkan_form_dan_tidak_mengarang_rincian():
    html = _halaman(_gratis(), _tampil(), rekening=None)
    assert "Rekening tujuan belum tersedia" in html and "<form" not in html and "lg-nominal" not in html


def test_langkah_mengikuti_status_tagihan():
    pos = {s: re.search(r'<li aria-current="step">(\d)', _halaman(_gratis(), _tampil(s))).group(1)
           for s in (dasar.STATUS_BELUM_BAYAR, dasar.STATUS_DITOLAK, dasar.STATUS_MENUNGGU)}
    assert pos == {dasar.STATUS_BELUM_BAYAR: "1", dasar.STATUS_DITOLAK: "2", dasar.STATUS_MENUNGGU: "3"}


# --- status ------------------------------------------------------------------------------------

def test_menunggu_kartu_kuning_dengan_satu_maskot_menunggu():
    html = _halaman(_gratis(), _tampil(dasar.STATUS_MENUNGGU, jumlah_bukti=1))
    assert "ceria-status-kuning" in html and "Menunggu pemeriksaan" in html and "Bukti sudah kami terima" in html
    assert _maskot(html) == 1 and "maskot-menunggu-v4" in html and html.count("Bukti sudah kami terima") == 1


def test_ditolak_menampilkan_alasan_ter_escape_dan_unggah_ulang():
    html = _halaman(_gratis(), _tampil(dasar.STATUS_DITOLAK, alasan="<i>kurang</i>", jumlah_bukti=1))
    assert "&lt;i&gt;kurang&lt;/i&gt;" in html and "<i>kurang</i>" not in html
    assert "ceria-status-koral" in html and ">Unggah ulang bukti<" in html and _maskot(html) == 0


def test_aktif_hero_dengan_maskot_merayakan_dan_konfeti_tanpa_tombol_pilih():
    html = _halaman(_aktif(), _tampil())
    assert "ceria-hero" in html and "ceria-konfeti" in html and "maskot-merayakan" in html and _maskot(html) == 1
    assert "Latihan Harian tanpa batas aktif sampai 23 Des 2026." in _teks(html) and "Pilih Bulanan" not in html


def test_menunggu_saat_aktif_tetap_satu_maskot_dan_menyebut_tanggal():
    html = _halaman(_aktif(), _tampil(dasar.STATUS_MENUNGGU, jumlah_bukti=1))
    assert _maskot(html) == 1 and "ceria-hero" not in html and "aktif sampai 23 Des 2026" in html


def test_murid_les_kartu_hijau_dan_pilih_paket_tetap_satu_maskot():
    html = _halaman(ringkas.Ringkasan("les", None, 0, None))
    assert "ceria-status-hijau" in html and "Dari les" in html and _maskot(html) == 1


def test_paket_belum_dibuka_tanpa_form():
    html = _halaman(_gratis(), rekening=None)
    assert "Pembayaran langganan belum dibuka" in html and "<form" not in html and _maskot(html) == 0


@pytest.mark.parametrize("r,tampil", [(_gratis(), None), (_gratis(), _tampil()), (_aktif(), None),
                                      (_gratis(), _tampil(dasar.STATUS_MENUNGGU))])
def test_semua_keadaan_tanpa_skrip_dan_tanpa_data_terlarang(r, tampil):
    html = _halaman(r, tampil)
    assert "<script" not in html and html.count('id="judul-langganan"') == 1
    for terlarang in ("wa.me", "tel:", "hor_", "diagnos", "malrule"):
        assert terlarang not in html.lower()


def test_halaman_info_tetap_punya_tautan_kembali_dan_tanpa_form():
    html = halaman.halaman_info("Judul <b>", "Isi & teks").decode()
    assert "Judul &lt;b&gt;" in html and "Isi &amp; teks" in html and 'href="/murid/langganan"' in html
    assert "<form" not in html


# --- pembungkus bersama dengan halaman Peta pesanan --------------------------------------------

def test_halaman_murid_tanpa_css_tambahan_identik_dengan_bentuk_lama():
    badan = '<h1 id="j">X</h1><p>isi</p>'
    polos = pesanan_murid_pages.halaman_murid("Judul", "j", badan, "/murid", "Beranda")
    assert polos == pesanan_murid_pages.halaman_murid("Judul", "j", badan, "/murid", "Beranda", css_tambahan="")
    assert b"ceria-" not in polos and b"lg-kartu" not in polos


def test_css_tambahan_hanya_menambah_css_setelah_gaya_akun():
    badan = '<h1 id="j">X</h1>'
    polos = pesanan_murid_pages.halaman_murid("J", "j", badan, "/murid", "Beranda").decode()
    tambah = pesanan_murid_pages.halaman_murid("J", "j", badan, "/murid", "Beranda", css_tambahan=".zzz{}").decode()
    assert tambah.replace(".zzz{}", "", 1) == polos and tambah.count(".zzz{}") == 1


def test_halaman_murid_bawaan_sama_dengan_rakitan_lama_tanpa_parameter():
    """Halaman Peta pesanan (pemanggil lain) tidak berubah: <head> = gaya_stitch + GAYA_AKUN, tanpa tambahan."""
    import brand
    from account_style import GAYA_AKUN
    from murid_shell import PANAH_KEMBALI, aksi_topbar, bungkus_murid, kepala_murid, topbar_murid
    from style_stitch import gaya_stitch
    badan = '<h1 id="j">X</h1><p>isi</p>'
    topbar = topbar_murid(aksi_topbar("/murid", "Beranda", PANAH_KEMBALI))
    utama = (f'<main class="{pesanan_murid_pages.KELAS_UTAMA}" aria-labelledby="j">{badan}</main>')
    lama = f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand.judul("Judul")}</title>
{brand.tag_kepala()}{kepala_murid(gaya_stitch() + GAYA_AKUN)}</head>
<body class="st">{bungkus_murid(topbar + utama)}</body></html>""".encode()
    assert pesanan_murid_pages.halaman_murid("Judul", "j", badan, "/murid", "Beranda") == lama


def test_nilai_berkutip_ter_escape_di_atribut_dan_teks():
    html = halaman.halaman_langganan(_gratis(), None, REKENING, lambda aksi: '" onfocus="x').decode()
    assert '" onfocus' not in html and 'value="&quot; onfocus=&quot;x"' in html
    tolak = _halaman(_gratis(), _tampil(dasar.STATUS_DITOLAK, alasan='" onclick="y'))
    assert "&quot; onclick=&quot;y" in tolak and '" onclick' not in tolak


def test_modul_tak_lagi_memakai_escape_tanpa_kutip_dari_cek_pages():
    from pathlib import Path
    sumber = Path(halaman.__file__).read_text()
    assert "cek_pages" not in sumber
    assert halaman._e('a"b') == "a&quot;b"
