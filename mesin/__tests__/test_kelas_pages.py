"""Halaman pilih dan tagihan Paket Belajar 1 Bulan (murni render, data sintetis)."""
import re
from pathlib import Path

import kelas_pages as halaman
import paket_belajar_katalog as k

AKHIR = "2026-12-23T03:00:00"
KEDALUWARSA = "2026-11-25T03:00:00"
ORDER = "kls_" + "a" * 32
KATA_TERLARANG = ("kunci", "malrule", "diagnosis", "kontak", "wali", "pendamping", "garansi")
STATUS_TERBUKA = (k.STATUS_BELUM_BAYAR, k.STATUS_MENUNGGU, k.STATUS_DITOLAK)


def _token(aksi):
    return "tok." + aksi


def _kartu(kode, *, deposit=False, kedua=False, terbuka=False):
    return k.KartuPaket(k.ambil(kode), k.hitung_rincian(kode, deposit_aktif=deposit, anak_kedua=kedua), terbuka)


def _tagihan(kode=k.KODE_PRIVATE, status=k.STATUS_BELUM_BAYAR, *, deposit=False, kedua=False, unik=427,
             bukti=0, berakhir=None):
    r = k.hitung_rincian(kode, deposit_aktif=deposit, anak_kedua=kedua)
    return k.TagihanKelas(ORDER, kode, r, unik, r.nominal + unik, status, KEDALUWARSA, bukti, berakhir)


def _pilih(kartu, tagihan=None, **kw):
    return halaman.halaman_pilih_paket(kartu, tagihan, _token, **kw).decode().split("</head>", 1)[1]


def _tagih(tagihan, rekening="Bank Contoh 1234 5678 atas nama PT Sintetis", **kw):
    paket = k.ambil(tagihan.kode_paket)
    return halaman.halaman_tagihan(tagihan, paket, rekening, _token, **kw).decode().split("</head>", 1)[1]


def _teks(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _dua_kartu(**kw):
    return [_kartu(k.KODE_PRIVATE, **kw), _kartu(k.KODE_MINI, **kw)]


# --- pilih paket -------------------------------------------------------------------------------

def test_dua_kartu_memuat_nama_isi_dan_harga_normal():
    teks = _teks(_pilih(_dua_kartu()))
    for harapan in ("Private", "Mini Class", "8 pertemuan x 60 menit", "maksimal 5 anak", "Rp640.000", "Rp250.000"):
        assert harapan in teks


def test_mode_online_untuk_private_dan_offline_untuk_mini():
    private, mini = _pilih(_dua_kartu()).split('<section class="lg-paket">')[1:3]
    assert "online" in private.lower() and "offline" not in private.lower()
    assert "offline" in mini.lower() and "online" not in mini.lower()


def test_lokasi_hanya_diumumkan_di_mini_dan_tidak_dikarang():
    private, mini = _pilih(_dua_kartu()).split('<section class="lg-paket">')[1:3]
    assert "Lokasi diumumkan setelah pendaftaran" in _teks(mini)
    assert "Lokasi" not in _teks(private)


def test_form_daftar_memuat_token_dan_kode_paket_tanpa_nominal():
    html = _pilih(_dua_kartu())
    assert html.count('action="/murid/paket/buat"') == 2
    assert 'name="token" value="tok.kelas_buat:private"' in html
    assert 'name="kode" value="mini"' in html
    assert 'name="nominal"' not in html and 'name="rupiah"' not in html
    assert "Daftar paket ini" in html


def test_rincian_deposit_tampil_dan_total_bulan_pertama():
    teks = _teks(_pilih(_dua_kartu(deposit=True)))
    assert "Sudah dipotong deposit Peta Rp49.000" in teks
    assert "Rp591.000" in teks and "Rp201.000" in teks


def test_rincian_diskon_anak_kedua():
    teks = _teks(_pilih(_dua_kartu(kedua=True)))
    assert "Diskon anak kedua 20%" in teks
    assert "Rp512.000" in teks and "Rp200.000" in teks
    assert "deposit" not in teks.lower()


def test_tanpa_potongan_tidak_ada_baris_rincian_khusus():
    teks = _teks(_pilih(_dua_kartu()))
    assert "deposit" not in teks.lower() and "Diskon" not in teks


def test_tagihan_terbuka_mengganti_form_dengan_catatan():
    html = _pilih(_dua_kartu(terbuka=True), _tagihan())
    assert "<form" not in html
    assert "tagihan" in _teks(html).lower()


def test_status_tampil_sebagai_teks_di_halaman_pilih():
    cocok = {k.STATUS_BELUM_BAYAR: "Menunggu pembayaran", k.STATUS_MENUNGGU: "Menunggu verifikasi",
             k.STATUS_DITOLAK: "Ditolak", k.STATUS_KEDALUWARSA: "Kedaluwarsa",
             k.STATUS_AKTIF: "Aktif sampai 23 Des 2026"}
    for status, label in cocok.items():
        tagihan = _tagihan(status=status, berakhir=AKHIR if status == k.STATUS_AKTIF else None)
        assert label in _teks(_pilih(_dua_kartu(terbuka=status in STATUS_TERBUKA), tagihan))


def test_galat_dan_kabar_tampil_ter_escape():
    html = _pilih(_dua_kartu(), galat="<script>x</script>", kabar="ok <b>")
    assert "<script>x" not in html and "&lt;script&gt;" in html
    assert "ok <b>" not in html


def test_pilih_tanpa_kartu_tidak_pecah():
    assert halaman.halaman_pilih_paket([], None, _token).startswith(b"<!DOCTYPE html>")


# --- tagihan -----------------------------------------------------------------------------------

def test_tagihan_polos_memuat_harga_total_kode_unik_dan_jendela():
    teks = _teks(_tagih(_tagihan()))
    assert "Rp640.000" in teks and "Rp640.427" in teks and "427" in teks
    assert "25 November 2026" in teks


def test_tagihan_deposit_dan_diskon_menunjukkan_potongan():
    deposit = _teks(_tagih(_tagihan(deposit=True)))
    assert "Rp49.000" in deposit and "Rp591.427" in deposit and "Diskon" not in deposit
    kedua = _teks(_tagih(_tagihan(k.KODE_MINI, kedua=True)))
    assert "Rp50.000" in kedua and "Rp200.427" in kedua


def test_form_unggah_bukti_hanya_saat_belum_aktif_dan_bisa_diunggah():
    for status in (k.STATUS_BELUM_BAYAR, k.STATUS_DITOLAK):
        html = _tagih(_tagihan(status=status))
        assert 'action="/murid/paket/bukti"' in html and 'enctype="multipart/form-data"' in html
        assert 'name="berkas"' in html and 'name="token" value="tok.kelas_bukti"' in html
    for status in (k.STATUS_MENUNGGU, k.STATUS_AKTIF, k.STATUS_KEDALUWARSA):
        assert "<form" not in _tagih(_tagihan(status=status, berakhir=AKHIR))


def test_lencana_status_tagihan():
    cocok = {k.STATUS_BELUM_BAYAR: "Menunggu pembayaran", k.STATUS_MENUNGGU: "Menunggu verifikasi",
             k.STATUS_DITOLAK: "Ditolak", k.STATUS_KEDALUWARSA: "Kedaluwarsa"}
    for status, label in cocok.items():
        assert label in _teks(_tagih(_tagihan(status=status)))
    assert "Aktif sampai 23 Des 2026" in _teks(_tagih(_tagihan(status=k.STATUS_AKTIF, berakhir=AKHIR)))


def test_tagihan_mini_menyebut_offline_dan_lokasi_belum_dikarang():
    teks = _teks(_tagih(_tagihan(k.KODE_MINI)))
    assert "offline" in teks.lower() and "Lokasi diumumkan setelah pendaftaran" in teks


def test_rekening_ter_escape_dan_galat_tampil():
    html = _tagih(_tagihan(), rekening="<img src=x onerror=1>", galat="<script>")
    assert "<img src=x" not in html and "<script>" not in html


def test_order_id_tidak_dirender():
    assert ORDER not in _tagih(_tagihan())


# --- lintas halaman ----------------------------------------------------------------------------

def test_tanpa_kata_terlarang_dan_tanpa_klaim():
    semua = [_pilih(_dua_kartu(deposit=True)), _pilih(_dua_kartu(kedua=True)), _tagih(_tagihan()),
             _tagih(_tagihan(k.KODE_MINI, status=k.STATUS_MENUNGGU))]
    for html in semua:
        teks = _teks(html).lower()
        for kata in KATA_TERLARANG + ("nilai naik", "peringkat", "pasti"):
            assert kata not in teks, kata


def test_modul_tanpa_hex_warna_dan_tanpa_skrip_baru():
    sumber = Path(halaman.__file__).read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", sumber)
    assert "<script" not in _pilih(_dua_kartu()) and "<script" not in _tagih(_tagihan())


def test_rute():
    assert halaman.RUTE == "/murid/paket" and halaman.RUTE_BUAT == "/murid/paket/buat"
    assert halaman.RUTE_BUKTI == "/murid/paket/bukti"


# --- info dan kalimat aktif (dipakai lapisan HTTP) -----------------------------------------------

def test_halaman_info_escape_dan_tautan_kembali():
    html = halaman.halaman_info("Judul <b>", "Isi & <script>").decode().split("</head>", 1)[1]
    assert "<script>" not in html and "&lt;script&gt;" in html and "Judul &lt;b&gt;" in html
    assert 'href="/murid/paket"' in html and "<form" not in html


def test_kalimat_aktif_memuat_nama_paket_dan_tanggal():
    teks = halaman.kalimat_aktif("Private", AKHIR)
    assert teks == "Paket Private aktif sampai 23 Des 2026."
