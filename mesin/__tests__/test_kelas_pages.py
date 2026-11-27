"""Halaman pilih dan tagihan Paket Belajar 1 Bulan (murni render, data sintetis)."""
import re
from html import escape as _escape
from pathlib import Path

import pytest

import kelas_pages as halaman
import paket_belajar_katalog as k
from jadwal_pilih import PilihanKelompok

AKHIR = "2026-12-23T03:00:00"
KEDALUWARSA = "2026-11-25T03:00:00"
ORDER = "kls_" + "a" * 32
KATA_TERLARANG = ("kunci", "malrule", "diagnosis", "kontak", "wali", "pendamping", "garansi")
STATUS_TERBUKA = (k.STATUS_BELUM_BAYAR, k.STATUS_MENUNGGU, k.STATUS_DITOLAK)


def _token(aksi):
    return "tok." + aksi


def _kartu(kode, *, deposit=False, terbuka=False):
    return k.KartuPaket(k.ambil(kode), k.hitung_rincian(kode, potongan_deposit=_potongan(deposit)), terbuka)


def _potongan(deposit: bool) -> int:
    return k.RUPIAH_DEPOSIT if deposit else 0


def _tagihan(kode=k.KODE_PRIVATE, status=k.STATUS_BELUM_BAYAR, *, deposit=False, unik=427,
             bukti=0, berakhir=None):
    r = k.hitung_rincian(kode, potongan_deposit=_potongan(deposit))
    return k.TagihanKelas(ORDER, kode, r, unik, r.nominal + unik, status, KEDALUWARSA, bukti, berakhir)


def _pilih(kartu, tagihan=None, **kw):
    daftar = () if tagihan is None else (tagihan,)
    return halaman.halaman_pilih_paket(kartu, daftar, _token, **kw).decode().split("</head>", 1)[1]


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
    for harapan in ("Private", "Mini Class", "8 pertemuan x 60 menit", "maksimal 5 anak", "Rp640.000", "Rp300.000"):
        assert harapan in teks


def test_semua_paket_online_dan_hanya_mini_menyebut_zoom_atau_meet():
    private, mini = _pilih(_dua_kartu()).split('<section class="lg-paket">')[1:3]
    assert "online" in private.lower() and "offline" not in private.lower()
    assert "offline" not in mini.lower() and "online" in mini.lower()
    assert "Zoom atau Google Meet" in mini and "Zoom" not in private


def test_tautan_meeting_hanya_dijanjikan_di_mini_dan_tanpa_lokasi_fisik():
    private, mini = _pilih(_dua_kartu()).split('<section class="lg-paket">')[1:3]
    assert "Kelas berlangsung online lewat Zoom atau Google Meet. Tautan dikirim setelah Anda daftar." in _teks(mini)
    assert "Lokasi" not in _teks(mini)
    assert "Lokasi" not in _teks(private) and "Zoom" not in _teks(private)


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
    assert "Rp591.000" in teks and "Rp251.000" in teks


def test_tanpa_potongan_tidak_ada_baris_rincian_khusus():
    teks = _teks(_pilih(_dua_kartu()))
    assert "deposit" not in teks.lower() and "Diskon" not in teks


def test_tidak_ada_label_diskon_anak_kedua_di_kartu():
    teks = _teks(_pilih(_dua_kartu(deposit=True)))
    assert "anak kedua" not in teks.lower() and "diskon" not in teks.lower()
    assert "Sudah dipotong deposit Peta Rp49.000" in teks and "Rp251.000" in teks


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
    assert halaman.halaman_pilih_paket([], (), _token).startswith(b"<!DOCTYPE html>")


# --- tagihan -----------------------------------------------------------------------------------

def test_tagihan_polos_memuat_harga_total_kode_unik_dan_jendela():
    teks = _teks(_tagih(_tagihan()))
    assert "Rp640.000" in teks and "Rp640.427" in teks and "427" in teks
    assert "25 November 2026" in teks and "Bayar dalam 24 jam sejak tagihan dibuat." in teks


def test_tagihan_deposit_menunjukkan_potongan_tanpa_diskon():
    deposit = _teks(_tagih(_tagihan(deposit=True)))
    assert "Rp49.000" in deposit and "Rp591.427" in deposit and "Diskon" not in deposit
    mini = _teks(_tagih(_tagihan(k.KODE_MINI, deposit=True)))
    assert "Rp49.000" in mini and "Rp251.427" in mini and "Diskon" not in mini and "anak kedua" not in mini.lower()


def test_form_unggah_bukti_hanya_saat_belum_aktif_dan_bisa_diunggah():
    for status in (k.STATUS_BELUM_BAYAR, k.STATUS_DITOLAK):
        html = _tagih(_tagihan(status=status))
        assert 'action="/murid/paket/bukti?kode=private"' in html and 'enctype="multipart/form-data"' in html
        assert 'name="berkas"' in html and 'name="token" value="tok.kelas_bukti:private"' in html
    for status in (k.STATUS_MENUNGGU, k.STATUS_AKTIF, k.STATUS_KEDALUWARSA):
        assert "<form" not in _tagih(_tagihan(status=status, berakhir=AKHIR))


def test_lencana_status_tagihan():
    cocok = {k.STATUS_BELUM_BAYAR: "Menunggu pembayaran", k.STATUS_MENUNGGU: "Menunggu verifikasi",
             k.STATUS_DITOLAK: "Ditolak", k.STATUS_KEDALUWARSA: "Kedaluwarsa"}
    for status, label in cocok.items():
        assert label in _teks(_tagih(_tagihan(status=status)))
    assert "Aktif sampai 23 Des 2026" in _teks(_tagih(_tagihan(status=k.STATUS_AKTIF, berakhir=AKHIR)))


def test_tagihan_mini_menyebut_zoom_atau_meet_tanpa_lokasi_fisik():
    teks = _teks(_tagih(_tagihan(k.KODE_MINI)))
    assert "offline" not in teks.lower() and "Kelas berlangsung online lewat Zoom atau Google Meet. Tautan dikirim setelah Anda daftar." in teks
    assert "Lokasi diumumkan" not in teks


def test_rekening_ter_escape_dan_galat_tampil():
    html = _tagih(_tagihan(), rekening="<img src=x onerror=1>", galat="<script>")
    assert "<img src=x" not in html and "<script>" not in html


def test_order_id_tidak_dirender():
    assert ORDER not in _tagih(_tagihan())


# --- lintas halaman ----------------------------------------------------------------------------

def test_tanpa_kata_terlarang_dan_tanpa_klaim():
    semua = [_pilih(_dua_kartu(deposit=True)), _pilih(_dua_kartu()), _tagih(_tagihan()),
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


# --- kartu jadwal pertemuan untuk orang tua --------------------------------------------------------

def _jadwal(lokasi="Online", batal=(), mulai="2026-11-24T02:00:00"):
    sesi = [{"ke": n, "mulai": mulai if n == 1 else "2026-12-%02dT09:30:00" % n, "menit": 60,
             "dibatalkan": n in batal} for n in range(1, 9)]
    return {"lokasi": lokasi, "sesi": sesi}


def test_kartu_jadwal_memuat_lokasi_delapan_pertemuan_waktu_wib_dan_label_dibatalkan():
    html = _pilih(_dua_kartu(), jadwal=_jadwal("Ruang Melati", batal=(3,)))
    teks = _teks(html)
    assert "Jadwal pertemuan" in teks and "Lokasi: Ruang Melati" in teks
    assert len(re.findall(r"Pertemuan [1-8] ·", teks)) == 8
    assert "Pertemuan 1 · 24 November 2026 pukul 09.00 WIB" in teks    # 02:00 UTC = 09.00 WIB
    assert teks.count("Dibatalkan") == 1
    assert re.search(r"Pertemuan 3 · [^·]+WIB · Dibatalkan", teks)


def test_tanpa_jadwal_tidak_ada_kartu_jadwal():
    assert "Jadwal pertemuan" not in _teks(_pilih(_dua_kartu()))
    assert "Jadwal pertemuan" not in _teks(_pilih(_dua_kartu(), jadwal=None))


def test_kelompok_penuh_tampil_sebagai_penuh_tanpa_form_dan_semua_penuh_diberi_kabar():
    penuh = PilihanKelompok("klp_" + "1" * 32, "Mini A", "2026-11-26T02:00:00", 0, True)
    isi = _pilih(_dua_kartu(), pilihan_jadwal=(penuh,))
    teks = _teks(isi)
    assert "Mini A" in teks and "penuh" in teks and "Semua kelompok sedang penuh." in teks
    assert 'name="kelompok"' not in isi and "Pilih kelompok ini" not in teks


def test_kelompok_terbuka_tetap_punya_form_dan_tanpa_kabar_penuh():
    terbuka = PilihanKelompok("klp_" + "2" * 32, "Mini B", "2026-11-26T02:00:00", 3, False)
    penuh = PilihanKelompok("klp_" + "1" * 32, "Mini A", "2026-11-26T02:00:00", 0, True)
    isi = _pilih(_dua_kartu(), pilihan_jadwal=(terbuka, penuh))
    assert 'value="klp_' + "2" * 32 + '"' in isi and 'value="klp_' + "1" * 32 + '"' not in isi
    assert "sisa 3 kursi" in _teks(isi) and "Semua kelompok sedang penuh." not in _teks(isi)


def test_kartu_jadwal_escape_lokasi_dan_tanpa_skrip():
    html = _pilih(_dua_kartu(), jadwal=_jadwal("<script>alert(1)</script>"))
    assert "<script>alert" not in html and "&lt;script&gt;" in html


def test_kartu_jadwal_tautan_sah_jadi_anchor_aman_dan_teks_tautan():
    html = _pilih(_dua_kartu(), jadwal=_jadwal("https://zoom.us/j/123456789"))
    assert 'href="https://zoom.us/j/123456789"' in html
    assert 'target="_blank" rel="noopener noreferrer nofollow"' in html
    teks = _teks(html)
    assert "Tautan kelas: https://zoom.us/j/123456789" in teks and "Lokasi:" not in teks


def test_kartu_jadwal_tautan_sah_diescape_di_atribut():
    tautan = "https://us02web.zoom.us/j/123?pwd=abc&x=1"
    html = _pilih(_dua_kartu(), jadwal=_jadwal(tautan))
    assert 'href="%s"' % _escape(tautan, quote=True) in html
    assert "&amp;x=1" in html and 'href="https://us02web.zoom.us/j/123?pwd=abc&x=1"' not in html


@pytest.mark.parametrize("lokasi", [
    "javascript:alert(1)", "https://evil.example/", "http://zoom.us/j/1",
    "data:text/html,<b>x</b>", "Ruang Melati", "<script>alert(1)</script>",
])
def test_kartu_jadwal_lokasi_tak_sah_di_db_tidak_pernah_jadi_anchor(lokasi):
    html = _pilih(_dua_kartu(), jadwal=_jadwal(lokasi))
    assert 'target="_blank"' not in html
    assert 'href="%s"' % _escape(lokasi, quote=True) not in html
    assert "<script>" not in html and "Lokasi: " in _teks(html)


def test_kartu_jadwal_private_online_tetap_teks_lokasi_tanpa_anchor():
    html = _pilih(_dua_kartu(), jadwal=_jadwal("Online"))
    assert "Lokasi: Online" in _teks(html) and 'target="_blank"' not in html


def test_kartu_jadwal_tanpa_hex_id_dan_guru():
    html = _pilih(_dua_kartu(), jadwal=_jadwal())
    for gejala in ("akun_", "klp_", "kor_"):
        assert gejala not in html
    assert "Jadwal pertemuan" in _teks(html) and "<script" not in html


def test_teks_aktif_lama_dipertahankan_di_kartu_status():
    html = _tagih(_tagihan(status=k.STATUS_AKTIF, berakhir=AKHIR))
    assert "Penjadwalan pertemuan diatur tim setelah pembayaran disetujui." in _teks(html)


# --- daftar: kartu tagihan terbuka, pemulihan, dan tautan per kode paket ------------------------------

def test_kartu_tagihan_terbuka_memuat_total_status_teks_dan_tautan_per_kode():
    html = _pilih(_dua_kartu(terbuka=True), _tagihan(k.KODE_MINI, unik=7))
    teks = _teks(html)
    assert "Rp300.007" in teks and "Menunggu pembayaran" in teks
    assert 'href="/murid/paket/tagihan?kode=mini"' in html and "Lanjutkan pembayaran" in teks
    assert "Hapus tagihan" not in teks and "/murid/paket/hapus" not in html


def test_kartu_hapus_hanya_bila_belum_bayar_tanpa_bukti_dan_diizinkan():
    belum = _pilih(_dua_kartu(terbuka=True), _tagihan(k.KODE_MINI), boleh_hapus=True)
    assert 'href="/murid/paket/hapus?kode=mini"' in belum and "Hapus tagihan" in _teks(belum)
    ada_bukti = _pilih(_dua_kartu(terbuka=True), _tagihan(k.KODE_MINI, bukti=1), boleh_hapus=True)
    assert "/murid/paket/hapus" not in ada_bukti
    tanpa_izin = _pilih(_dua_kartu(terbuka=True), _tagihan(k.KODE_MINI), boleh_hapus=False)
    assert "/murid/paket/hapus" not in tanpa_izin


def test_tagihan_terbuka_sebagai_penanda_di_kartu_paket_tanpa_tombol_daftar():
    html = _pilih(_dua_kartu(terbuka=True), _tagihan(k.KODE_PRIVATE))
    assert html.count("Tagihan paket ini ada di atas.") == 2 and 'action="/murid/paket/buat"' not in html


def test_paket_dibatalkan_memberi_catatan_pulih_dan_tetap_bisa_didaftar():
    html = _pilih(_dua_kartu(), dibatalkan={k.KODE_MINI: AKHIR})
    teks = _teks(html)
    assert "Memilih lagi memulihkan tagihan yang tadi dihapus (sisa waktu bayar:" in teks
    assert 'action="/murid/paket/buat"' in html


def test_halaman_tagihan_dengan_formulir_unggah_terikat_kode_paket():
    html = _tagih(_tagihan(k.KODE_MINI))
    assert 'action="/murid/paket/bukti?kode=mini"' in html and 'value="tok.kelas_bukti:mini"' in html
    assert 'href="/murid/paket"' in html


def test_status_dibatalkan_tampil_teks_tanpa_keyerror_dan_tanpa_pembayaran():
    html = _tagih(_tagihan(k.KODE_MINI, status=k.STATUS_DIBATALKAN))
    teks = _teks(html)
    assert "Dibatalkan" in teks and "Tagihan ini sudah dihapus" in teks
    assert "Total yang harus Anda transfer" not in teks and 'action="/murid/paket/bukti' not in html


def test_konfirmasi_hapus_memuat_akibat_uang_paket_dan_tombol_post():
    html = halaman.halaman_konfirmasi_hapus(_tagihan(k.KODE_PRIVATE), k.ambil(k.KODE_PRIVATE), _token).decode()
    teks = _teks(html)
    assert "Private" in teks and "Rp" in teks and "Ya, hapus tagihan" in teks
    assert halaman.COPY_AKIBAT_HAPUS in teks and 'action="/murid/paket/hapus"' in html
    assert 'value="tok.kelas_hapus:private"' in html and 'href="/murid/paket/tagihan?kode=private"' in html
    assert "kor_" not in html
