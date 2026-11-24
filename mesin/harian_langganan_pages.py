"""Render halaman langganan Latihan Harian untuk murid (orang tua memakai akun anak) dan blok halaman orang tua.

Murni render: tanpa DB, tanpa token buatan sendiri (pemanggil menyuntik `token_untuk(aksi)`), tanpa JS baru.
Aturan isi:

- Nominal hanya dari tagihan ledger (harga paket + kode unik) dan disorot harus persis; harga paket dari
  konstanta domain, bukan dari form. Rekening hanya tampil bersama tagihan.
- Hemat tahunan dan setara per bulan dihitung dari `PAKET` saat render (tanpa angka tulis tangan).
- Alasan penolakan admin tampil ter-escape. Nomor WhatsApp, nama berkas, dan id order tidak pernah dirender.
- Satu aksi satu tombol: status menentukan hanya satu form (pilih paket, atau unggah bukti).
- Satu maskot per layar, dan status tidak pernah hanya warna (selalu ada lencana atau teks).
"""
from __future__ import annotations

from typing import Callable, Optional

import playful_components as C
from cek_pages import _a, _e
from format_tanggal import tanggal_pendek
import harian_langganan_dasar as h
import harian_langganan_ringkas as ringkas
import harian_langganan_style
import pesanan_murid_pages
from harian_pages import teks_harga_ortu
from pesanan_transfer_pages import (COPY_ATURAN, COPY_BERKAS_BESAR, COPY_BERKAS_KOSONG, COPY_BERKAS_TAK_TERBACA,
                                    COPY_LABEL_BERKAS, COPY_TIPE_TIDAK_DIDUKUNG, rupiah, waktu_wib)
from playful_style import GAYA_CERIA

RUTE = "/murid/langganan"
RUTE_BUAT = RUTE + "/buat"
RUTE_BUKTI = RUTE + "/bukti"
AKSI_BUAT = "harian_buat:"
AKSI_BUKTI = "harian_bukti"
ID_JUDUL = "judul-langganan"
COPY_JUDUL = "Langganan Latihan Harian"
COPY_JUDUL_STATUS = "Status langganan"
_ACCEPT_BUKTI = "image/jpeg,image/png,application/pdf"
_PEMBULATAN_SETARA = 1000  # "sekitar": setara per bulan dibulatkan ke ribuan terdekat

COPY_AKTIF = "Latihan Harian tanpa batas aktif sampai %s."
COPY_AKTIF_JUDUL = "Tanpa batas sampai %s"
COPY_AKTIF_ISI = "Anak bisa mulai sesi Latihan Harian kapan saja."
COPY_LES = "Anak ini murid les, jadi Latihan Harian tanpa batas tanpa perlu berlangganan."
COPY_LES_JUDUL = "Tanpa batas lewat les"
COPY_GRATIS = "Belum berlangganan. Anak tetap bisa 1 sesi Latihan Harian gratis setiap hari."
COPY_GRATIS_JUDUL = "Belum berlangganan"
COPY_GRATIS_ISI = "Anak tetap bisa 1 sesi Latihan Harian gratis setiap hari."
COPY_LABEL_KARTU = "Langganan Latihan Harian"
COPY_TOMBOL_LIHAT_PAKET = "Lihat paket"
COPY_TOMBOL_PERPANJANG = "Perpanjang"
COPY_TOMBOL_LANJUT_BAYAR = "Lanjutkan pembayaran"
COPY_TOMBOL_LIHAT_STATUS = "Lihat status"
COPY_PENGANTAR = "Pilih paket, lalu transfer ke rekening kami dan unggah bukti transfernya. Tim akan memeriksa bukti Anda."
COPY_PENGANTAR_PERPANJANG = "Perpanjangan menyambung dari tanggal berakhir, jadi hari yang tersisa tidak hilang."
COPY_JUDUL_PILIH = "Pilih paket"
COPY_SAPA_PILIH = "Pilih yang cocok ya, Ayah/Bunda!"
COPY_SAPA_AKTIF_AWAL = "Yeay! Langganan "
COPY_SAPA_AKTIF_TEBAL = "aktif"
COPY_BELUM_DIBUKA = "Pembayaran langganan belum dibuka. Coba lagi nanti."
COPY_JUDUL_TAGIHAN = "Bayar lewat transfer"
COPY_MENUNGGU_JUDUL = "Bukti sudah kami terima"
COPY_MENUNGGU_ISI = "Tim akan memeriksanya; langganan aktif setelah bukti disetujui."
COPY_LENCANA_MENUNGGU = "Menunggu pemeriksaan"
COPY_SAPA_MENUNGGU = "Tenang ya, tim sedang memeriksa buktimu."
COPY_LENCANA_BELUM_BAYAR = "Menunggu pembayaran"
COPY_JUDUL_BELUM_BAYAR = "Tagihan sedang berjalan"
COPY_LENCANA_DITOLAK = "Bukti perlu diperbaiki"
COPY_DITOLAK_JUDUL = "Bukti terakhir belum sesuai"
COPY_ALASAN_TIM = "Alasan dari tim:"
COPY_LENCANA_LES = "Dari les"
COPY_LENCANA_AKTIF = "Aktif"
COPY_LENCANA_SEGERA = "Berakhir %d hari lagi"
COPY_JUDUL_SEGERA = "Perpanjang supaya latihan tidak terputus"
COPY_BATAS_BUKTI = "Batas bukti untuk tagihan ini sudah tercapai. Hubungi tim bila masih perlu bantuan."
COPY_TOMBOL_UNGGAH = "Unggah bukti"
COPY_TOMBOL_UNGGAH_ULANG = "Unggah ulang bukti"
COPY_REKENING_KOSONG = "Rekening tujuan belum tersedia. Hubungi tim sebelum mentransfer."
COPY_TULIS_TRANSFER = "Transfer persis ya. Tiga angka terakhir = kode unik."
COPY_LABEL_NOMINAL = "Nominal yang harus Anda transfer:"
COPY_LANGKAH = ("Transfer", "Unggah bukti", "Aktif")
COPY_GAGAL_BUAT = "Tagihan belum bisa dibuat. Selesaikan tagihan yang sedang berjalan, atau coba lagi nanti."
COPY_KODE_HABIS = "Tagihan belum bisa dibuat sekarang. Coba lagi nanti atau hubungi tim."
COPY_TIDAK_TERIMA = "Tidak ada tagihan yang sedang menerima bukti. Buat tagihan dulu, atau waktu pembayaran sudah habis."
COPY_BELUM_SIAP = "Belum bisa diproses sekarang. Coba lagi nanti."
COPY_ISIAN_TIDAK_SAH = "Isian tidak sah. Muat ulang halaman, lalu coba lagi."
COPY_BERKAS = {"kosong": COPY_BERKAS_KOSONG, "besar": COPY_BERKAS_BESAR, "tipe": COPY_TIPE_TIDAK_DIDUKUNG,
               "terbaca": COPY_BERKAS_TAK_TERBACA}

TokenUntuk = Callable[[str], str]


def _p(teks: str) -> str:
    return f"<p>{_e(teks)}</p>"


def _kartu(isi: str) -> str:
    return f'<section class="lg-kartu">{isi}</section>'


def _catatan(teks: str) -> str:
    return f'<p class="lg-kecil">{_e(teks)}</p>'


def _tombol(teks: str) -> str:
    return f'<button type="submit" class="ceria-tombol">{_e(teks)}</button>'


def tanggal_berakhir(berakhir: str) -> str:
    return tanggal_pendek(h.tanggal_wib(berakhir))


def kalimat_status(r: ringkas.Ringkasan) -> str:
    """Satu kalimat status akses (dipakai halaman langganan dan kartu halaman orang tua)."""
    if r.langganan_aktif and r.berakhir:
        return COPY_AKTIF % tanggal_berakhir(r.berakhir)
    return COPY_LES if r.sumber == "les" else COPY_GRATIS


# --- hemat dan setara per bulan: dihitung dari PAKET, bukan tulis tangan ----------------------

def hitung_hemat(paket: h.Paket) -> Optional[tuple]:
    """(setara per bulan terbulat, hemat) paket multi-bulan terhadap harga bulanan, atau None bila tak berhemat."""
    bulanan = h.PAKET.get(h.PAKET_BULANAN)
    if bulanan is None or paket.bulan <= 1 or paket.kode == bulanan.kode:
        return None
    hemat = bulanan.rupiah // bulanan.bulan * paket.bulan - paket.rupiah
    if hemat <= 0:
        return None
    setara = round(paket.rupiah / paket.bulan / _PEMBULATAN_SETARA) * _PEMBULATAN_SETARA
    return setara, hemat


# --- keadaan status di halaman langganan ------------------------------------------------------

def _kartu_status_biasa(r: ringkas.Ringkasan) -> str:
    if r.sumber == "les":
        return C.kartu_status("hijau", COPY_LENCANA_LES, COPY_LES_JUDUL, _p(COPY_LES), level=2)
    return _kartu(f"<h2>{_e(COPY_JUDUL_STATUS)}</h2>{_p(kalimat_status(r))}")


def _hero_aktif(r: ringkas.Ringkasan) -> str:
    sapa = C.maskot_bicara("merayakan", COPY_SAPA_AKTIF_AWAL, COPY_SAPA_AKTIF_TEBAL, "!")
    judul = f'<h2 class="ceria-sr">{_e(COPY_JUDUL_STATUS)}</h2>'
    return C.hero(judul + sapa + _p(kalimat_status(r)), konfeti=True)


def _kartu_menunggu(r: ringkas.Ringkasan) -> str:
    sapa = C.maskot_bicara("berpikir", COPY_SAPA_MENUNGGU)
    tambahan = _p(kalimat_status(r)) if r.langganan_aktif else ""
    kartu = C.kartu_status("kuning", COPY_LENCANA_MENUNGGU, COPY_MENUNGGU_JUDUL, _p(COPY_MENUNGGU_ISI) + tambahan,
                           level=2)
    return sapa + kartu


def _status_dan_maskot(r: ringkas.Ringkasan, tampil) -> tuple:
    """(markup status, apakah sudah memuat maskot). Menunggu didahulukan atas aktif (perpanjangan sedang diperiksa)."""
    if tampil is not None and tampil.status == h.STATUS_MENUNGGU:
        return _kartu_menunggu(r), True
    if r.langganan_aktif:
        return _hero_aktif(r), True
    return _kartu_status_biasa(r), False


# --- pilih paket ------------------------------------------------------------------------------

def _teks_tombol_paket(paket: h.Paket, perpanjang: bool) -> str:
    return "%s %s %s" % ("Perpanjang" if perpanjang else "Pilih", paket.nama, rupiah(paket.rupiah))


def _form_paket(paket: h.Paket, token_untuk: TokenUntuk, perpanjang: bool) -> str:
    return (f'<form method="post" action="{RUTE_BUAT}">'
            f'<input type="hidden" name="token" value="{_a(token_untuk(AKSI_BUAT + paket.kode))}">'
            f'<input type="hidden" name="paket" value="{_a(paket.kode)}">'
            f'{_tombol(_teks_tombol_paket(paket, perpanjang))}</form>')


def _keterangan_paket(paket: h.Paket) -> str:
    isi = f'<p class="lg-ket">Berlaku {paket.bulan} bulan</p>'
    hemat = hitung_hemat(paket)
    if hemat is not None:
        isi += (f'<p class="lg-ket">Setara sekitar {_e(rupiah(hemat[0]))}/bulan</p>'
                f'<p class="lg-hemat">Hemat {_e(rupiah(hemat[1]))}</p>')
    return isi


def _kartu_paket(paket: h.Paket, token_untuk: TokenUntuk, perpanjang: bool) -> str:
    hemat = hitung_hemat(paket) is not None
    stiker = C.stiker("Paling hemat", "kanan") if hemat else ""
    kelas = "lg-paket lg-paket-hemat" if hemat else "lg-paket"
    return (f'<section class="{kelas}">{stiker}<div class="lg-paket-kepala"><div class="lg-paket-nama">'
            f'<h3>{_e(paket.nama)}</h3>{_keterangan_paket(paket)}</div>'
            f'<p class="lg-harga">{_e(rupiah(paket.rupiah))}</p></div>'
            f'{_form_paket(paket, token_untuk, perpanjang)}</section>')


def _kartu_pilih(r: ringkas.Ringkasan, token_untuk: TokenUntuk, dengan_maskot: bool) -> str:
    pengantar = COPY_PENGANTAR + (" " + COPY_PENGANTAR_PERPANJANG if r.langganan_aktif else "")
    sapa = C.maskot_bicara("menunjuk", COPY_SAPA_PILIH) if dengan_maskot else ""
    kartu = "".join(_kartu_paket(p, token_untuk, r.langganan_aktif) for p in h.PAKET.values())
    return (f'{sapa}<div class="lg-pilih-judul"><h2>{_e(COPY_JUDUL_PILIH)}</h2>{_p(pengantar)}</div>{kartu}')


# --- tagihan ----------------------------------------------------------------------------------

def _langkah(indeks_sekarang: int) -> str:
    """Langkah mini 1 Transfer, 2 Unggah bukti, 3 Aktif; langkah sekarang bertanda aria-current dan teks."""
    butir = []
    for n, nama in enumerate(COPY_LANGKAH):
        if n < indeks_sekarang:
            butir.append(f'<li class="lg-selesai">{n + 1} {_e(nama)}<span class="ceria-sr"> (selesai)</span></li>')
        elif n == indeks_sekarang:
            butir.append(f'<li aria-current="step">{n + 1} {_e(nama)}<span class="ceria-sr"> (langkah sekarang)</span></li>')
        else:
            butir.append(f"<li>{n + 1} {_e(nama)}</li>")
    return f'<ol class="lg-langkah" aria-label="Langkah pembayaran">{"".join(butir)}</ol>'


def _langkah_untuk(status: str) -> int:
    if status == h.STATUS_MENUNGGU:
        return 2
    return 1 if status == h.STATUS_DITOLAK else 0


def _rincian(tampil, rekening) -> str:
    if rekening is None:
        return _catatan(COPY_REKENING_KOSONG)
    return (
        f'<p class="lg-kecil">Paket: <strong>{_e(tampil.paket.nama)}</strong></p>'
        f'<p class="lg-kecil">{_e(COPY_LABEL_NOMINAL)}</p>'
        f'<p class="lg-nominal"><strong>{_e(rupiah(tampil.nominal))}</strong></p>'
        f'<p class="lg-tulis">{_e(COPY_TULIS_TRANSFER)}</p><hr class="lg-pemisah">'
        '<div class="lg-rincian">'
        f"<p>Bank: <strong>{_e(rekening.nama_bank)}</strong></p>"
        f"<p>Nomor rekening: <strong>{_e(rekening.nomor_label)}</strong></p>"
        f"<p>Atas nama: <strong>{_e(rekening.atas_nama)}</strong></p>"
        f"<p>Batas waktu: <strong>{_e(waktu_wib(tampil.kedaluwarsa))}</strong></p></div>")


def _form_unggah(token: str, ulang: bool) -> str:
    return (
        f'<form method="post" action="{RUTE_BUKTI}" enctype="multipart/form-data">'
        f'<input type="hidden" name="token" value="{_a(token)}">'
        f'<label class="lg-berkas">{_e(COPY_LABEL_BERKAS)}'
        f'<input type="file" name="berkas" accept="{_ACCEPT_BUKTI}" required></label>'
        f'{_tombol(COPY_TOMBOL_UNGGAH_ULANG if ulang else COPY_TOMBOL_UNGGAH)}</form>')


def _kartu_ditolak(alasan: Optional[str]) -> str:
    isi = f"<p>{_e(COPY_ALASAN_TIM)} <strong>{_e(alasan)}</strong></p>" if alasan else ""
    return C.kartu_status("koral", COPY_LENCANA_DITOLAK, COPY_DITOLAK_JUDUL, isi, level=2)


def _kartu_tagihan(tampil, rekening, token_untuk: TokenUntuk) -> str:
    ditolak = _kartu_ditolak(tampil.alasan_tolak) if tampil.status == h.STATUS_DITOLAK and tampil.alasan_tolak else ""
    isi = f"<h2>{_e(COPY_JUDUL_TAGIHAN)}</h2>{_langkah(_langkah_untuk(tampil.status))}{_rincian(tampil, rekening)}"
    if tampil.status != h.STATUS_MENUNGGU:
        isi += _catatan(COPY_ATURAN)
    if rekening is not None and tampil.boleh_unggah:
        isi += _form_unggah(token_untuk(AKSI_BUKTI), tampil.status == h.STATUS_DITOLAK)
    elif tampil.jumlah_bukti >= h.MAKS_BUKTI:
        isi += _catatan(COPY_BATAS_BUKTI)
    return ditolak + f'<section class="lg-kartu lg-kertas">{isi}</section>'


# --- rakitan halaman --------------------------------------------------------------------------

def _badan(r: ringkas.Ringkasan, tampil, rekening, token_untuk: TokenUntuk) -> str:
    status, ada_maskot = _status_dan_maskot(r, tampil)
    if tampil is not None:
        return status + _kartu_tagihan(tampil, rekening, token_untuk)
    if rekening is None:
        return status + _kartu(f"<h2>{_e(COPY_JUDUL_TAGIHAN)}</h2>{_p(COPY_BELUM_DIBUKA)}")
    return status + _kartu_pilih(r, token_untuk, dengan_maskot=not ada_maskot)


def halaman_langganan(r: ringkas.Ringkasan, tampil, rekening, token_untuk: TokenUntuk) -> bytes:
    """Halaman /murid/langganan: status akses + (pilih paket | tagihan terbuka)."""
    return _bungkus(_badan(r, tampil, rekening, token_untuk))


def halaman_info(judul: str, teks: str) -> bytes:
    """Pesan tetap tanpa form, dengan tautan kembali ke halaman langganan."""
    isi = (_kartu(f"<h2>{_e(judul)}</h2>{_p(teks)}")
           + f'<p class="lg-kembali"><a href="{RUTE}">Kembali ke langganan</a></p>')
    return _bungkus(isi)


def _bungkus(isi: str) -> bytes:
    badan = f'<div class="lg-isi"><h1 id="{ID_JUDUL}">{_e(COPY_JUDUL)}</h1>{isi}</div>'
    css = GAYA_CERIA + harian_langganan_style.GAYA_LANGGANAN_HARIAN
    return pesanan_murid_pages.halaman_murid(COPY_JUDUL, ID_JUDUL, badan, "/murid", "Beranda", css_tambahan=css)


# --- halaman orang tua: banner dan kartu enam keadaan -----------------------------------------

def banner_orang_tua(r: Optional[ringkas.Ringkasan], nama_anak: str) -> str:
    """Banner 'berakhir N hari lagi' bila langganan aktif dan sisa <= HARI_PENGINGAT; selain itu ''."""
    if r is None or not r.perlu_pengingat:
        return ""
    teks = "Latihan Harian %s berakhir %d hari lagi." % (nama_anak or "anak", r.sisa_hari)
    return (f'<p class="ortu-banner-st" id="ortu-langganan-banner" role="status">'
            f'{C.lencana("Segera berakhir", "koral")} {_e(teks)} <a href="{RUTE}">Perpanjang</a></p>')


def _kartu_navy_belum() -> str:
    """Belum berlangganan: kartu navy; harga 'mulai ...' dari PAKET."""
    isi = (f"{_p(COPY_GRATIS_ISI)}"
           f'<p>Buka latihan {C.sorot("tanpa batas")} {_e(teks_harga_ortu())}.</p>')
    return C.kartu_navy(_e(COPY_GRATIS_JUDUL), isi, RUTE, COPY_TOMBOL_LIHAT_PAKET, label=COPY_LABEL_KARTU,
                        id_="ortu-langganan")


def _ke_langganan(teks: str) -> tuple:
    return RUTE, teks


def _kartu_ortu_tagihan(r: ringkas.Ringkasan) -> Optional[str]:
    """Kartu untuk tagihan terbuka (ditolak, menunggu, belum bayar), atau None bila tak ada tagihan."""
    if r.status_tagihan == h.STATUS_DITOLAK:
        isi = f"<p>{_e(COPY_ALASAN_TIM)} <strong>{_e(r.alasan_tolak)}</strong></p>" if r.alasan_tolak else ""
        return C.kartu_status("koral", COPY_LENCANA_DITOLAK, COPY_DITOLAK_JUDUL, isi + _p(kalimat_status(r)),
                              id_="ortu-langganan", tombol=_ke_langganan(COPY_TOMBOL_UNGGAH_ULANG))
    if r.status_tagihan == h.STATUS_MENUNGGU:
        return C.kartu_status("kuning", COPY_LENCANA_MENUNGGU, COPY_MENUNGGU_JUDUL,
                              _p(COPY_MENUNGGU_ISI) + _p(kalimat_status(r)),
                              id_="ortu-langganan", tombol=_ke_langganan(COPY_TOMBOL_LIHAT_STATUS))
    if r.status_tagihan is not None:
        return C.kartu_status("kuning", COPY_LENCANA_BELUM_BAYAR, COPY_JUDUL_BELUM_BAYAR, _p(kalimat_status(r)),
                              id_="ortu-langganan", tombol=_ke_langganan(COPY_TOMBOL_LANJUT_BAYAR))
    return None


def _kartu_ortu_aktif(r: ringkas.Ringkasan) -> str:
    """Aktif (hijau) atau segera berakhir (koral lembut); keduanya dengan tombol Perpanjang."""
    tombol = _ke_langganan(COPY_TOMBOL_PERPANJANG)
    if r.perlu_pengingat:
        isi = _p(kalimat_status(r)) + _p(COPY_PENGANTAR_PERPANJANG)
        return C.kartu_status("koral", COPY_LENCANA_SEGERA % r.sisa_hari, COPY_JUDUL_SEGERA, isi,
                              id_="ortu-langganan", tombol=tombol)
    return C.kartu_status("hijau", COPY_LENCANA_AKTIF, COPY_AKTIF_JUDUL % tanggal_berakhir(r.berakhir or ""),
                          _p(COPY_AKTIF_ISI), id_="ortu-langganan", tombol=tombol)


def kartu_orang_tua(r: Optional[ringkas.Ringkasan]) -> str:
    """Kartu status langganan enam keadaan + paling banyak satu tombol ke halaman langganan; '' bila fitur mati (r None).

    Urutan: les, tagihan terbuka (ditolak, menunggu, belum bayar), aktif (segera berakhir atau tidak), belum berlangganan.
    """
    if r is None:
        return ""
    if r.sumber == "les":
        return C.kartu_status("hijau", COPY_LENCANA_LES, COPY_LES_JUDUL, _p(COPY_LES), id_="ortu-langganan")
    kartu_tagihan = _kartu_ortu_tagihan(r)
    if kartu_tagihan is not None:
        return kartu_tagihan
    return _kartu_ortu_aktif(r) if r.langganan_aktif and r.berakhir else _kartu_navy_belum()
