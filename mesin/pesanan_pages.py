"""Halaman pesanan Paket Coba (funnel Fase 3c-3): status pesanan dan pesan jujur.

Hanya HTML native (tanpa JS). Renderer murni: tidak membuka basis data, tidak membuat
token, dan tidak menghubungi provider; `pesanan_http` memberi nilai yang sudah
diputuskan. Batas isi:

- Nominal hanya satu: `pesanan_dasar.RUPIAH_PAKET` (lewat kalimat harga disetujui
  `funnel_pages.COPY_HARGA`). Tidak ada nominal dari form, URL, atau provider.
- `sudah_dibayar` hanya menyatakan pembayaran diterima; tidak ada akses laporan,
  latihan, atau konsultasi di fase ini. Tidak ada tombol "saya sudah bayar" yang
  mengubah status: satu-satunya tombol periksa meminta server menanyakan provider.
- Gambar QR hanya `<img src="/pesanan/qr">` (same-origin); URL provider tidak tampil.
- Nama anak tampil di badan halaman (di-escape), tidak pernah di URL atau pesan galat.
"""
from __future__ import annotations

from cek_pages import RUTE_HASIL, _a, _bungkus, _e, _kepala
from funnel_pages import COPY_HARGA
from pesanan_dasar import (
    STATUS_BELUM_BAYAR, STATUS_DIREFUND, STATUS_DITOLAK, STATUS_KEDALUWARSA,
    STATUS_MENUNGGU_VERIFIKASI, STATUS_PERLU_DIPERIKSA, STATUS_SUDAH_DIBAYAR,
)
from pesanan_transfer_pages import COPY_JUDUL_QRIS, COPY_PETUNJUK_QRIS, COPY_STATUS_PILIH

RUTE_STATUS = "/pesanan"
RUTE_QR = "/pesanan/qr"
RUTE_PERIKSA = "/pesanan/periksa"
RUTE_ULANG = "/pesanan/ulang"
RUTE_BUAT = "/pesanan/buat"
RUTE_KONTAK = "/akun/kontak"
ALIS = "PAKET COBA"
ID_JUDUL = "judul-pesanan"

COPY_JUDUL = "Pesanan Peta Kemampuan"
COPY_TUTUP = (
    "Pembayaran Peta Kemampuan belum dibuka. Belum ada tagihan yang dibuat, jadi tidak ada "
    "yang perlu Anda bayar sekarang."
)
COPY_TUTUP_SUDAH_BAYAR = (
    "Jika Anda sudah pernah membayar, pembayaran itu tetap tercatat. "
    "Hubungi tim lewat WhatsApp bila ada yang perlu dipastikan."
)
# Selaras COPY_PEMBATALAN (Keputusan 18: tanpa refund untuk Peta Kemampuan, kecuali laporan terlambat).
COPY_REFUND = (
    "Peta Kemampuan tidak dapat dikembalikan; Rp49.000 menjadi voucher program belajar bila Anda "
    "lanjut. Bila laporan terlambat lebih dari 3×24 jam dari jam terbit yang kami kabari, Anda boleh "
    "memilih menunggu atau uang kembali. Hubungi tim lewat WhatsApp."
)
COPY_KUOTA_HABIS = (
    "Pendaftaran Peta Kemampuan sedang dihentikan sementara; "
    "akun dan hasil yang sudah ada tetap bisa dibuka."
)
COPY_BUTUH_KONTAK = (
    "Nomor WhatsApp Anda belum tersimpan. Kami butuh nomor itu untuk menghubungi Anda "
    "setelah pembayaran. Lengkapi dulu nomornya, lalu kembali ke hasil cek."
)
COPY_CEK_BELUM_SELESAI = (
    "Peta Kemampuan dibuka setelah cek gratis anak selesai. Cek belum selesai, jadi belum "
    "ada pesanan yang dibuat."
)
COPY_BELUM_SIAP = (
    "Pesanan belum bisa diproses sekarang. Tidak ada yang berubah; coba lagi nanti "
    "atau hubungi tim lewat WhatsApp."
)
COPY_BENTROK = (
    "Pesanan Anda perlu dicek tim sebelum bisa dilanjutkan. Tidak perlu membayar lagi; "
    "tim akan menghubungi lewat WhatsApp."
)
COPY_BATAS_ULANG = (
    "Pembayaran ini tidak bisa dibuat ulang lagi dari halaman ini. "
    "Hubungi tim lewat WhatsApp."
)
COPY_FORM_TIDAK_SAH = "Form tidak sah atau sudah kedaluwarsa. Muat ulang halaman, lalu coba lagi."
COPY_TERLALU_BANYAK = "Terlalu banyak permintaan. Coba lagi sebentar."

COPY_STATUS = {
    STATUS_BELUM_BAYAR: ("Menunggu pembayaran",
                         "Pindai kode QRIS dengan aplikasi pembayaran Anda. Status berubah "
                         "setelah pembayaran terverifikasi, bukan saat Anda menekan tombol."),
    STATUS_SUDAH_DIBAYAR: ("Pembayaran diterima", "Pembayaran diterima. Akses laporan lengkap menyusul."),
    STATUS_PERLU_DIPERIKSA: ("Pembayaran sedang diperiksa",
                             "Pembayaran Anda sedang diperiksa tim. Tidak perlu membayar lagi; "
                             "tim akan menghubungi lewat WhatsApp."),
    STATUS_KEDALUWARSA: ("Waktu pembayaran habis",
                         "Waktu pembayaran habis dan belum ada pembayaran yang tercatat."),
    STATUS_DIREFUND: ("Pembayaran dikembalikan", "Pembayaran ini sudah dikembalikan oleh tim."),
    STATUS_MENUNGGU_VERIFIKASI: ("Bukti diterima, menunggu pemeriksaan",
                                 "Bukti transfer Anda sudah kami terima dan sedang diperiksa tim. "
                                 "Tidak perlu membayar lagi."),
    STATUS_DITOLAK: ("Bukti belum sesuai",
                     "Bukti transfer Anda belum bisa diterima. Periksa alasannya, lalu unggah ulang "
                     "atau hubungi tim lewat WhatsApp."),
}
# Status belum bayar bila jalur transfer ikut ditawarkan (QRIS, bila ada, menjadi pilihan kedua).
COPY_STATUS_PILIH_CARA = ("Menunggu pembayaran", COPY_STATUS_PILIH)
COPY_QR_BELUM_ADA = "Kode QR belum tersedia saat ini."
COPY_BELUM_TERPERIKSA = (
    "Status terbaru belum bisa diperiksa ke penyedia pembayaran sekarang. "
    "Tampilan ini belum tentu yang terbaru."
)
COPY_ALT_QR = "Kode QRIS untuk membayar Peta Kemampuan"
COPY_TOMBOL = {
    "periksa": "Periksa status pembayaran",
    "buat": "Coba lagi",
    "ulang": "Buat ulang pembayaran",
}
AKSI_RUTE = {"periksa": RUTE_PERIKSA, "buat": RUTE_BUAT, "ulang": RUTE_ULANG}
UKURAN_QR = 240


def _kartu(isi: str) -> str:
    return f'<div class="kartu-st">{isi}</div>'


def _tautan(tujuan) -> str:
    if not tujuan:
        return ""
    href, label = tujuan
    return f'<p class="akun-aksi-sandi"><a href="{_a(href)}">{_e(label)}</a></p>'


def _catatan_refund() -> str:
    return f'<p class="funnel-catatan-st">{_e(COPY_REFUND)}</p>'


def halaman_tertutup(ident) -> bytes:
    """Gerbang pembayaran tertutup: status jujur, tanpa form, tanpa nama atau data order."""
    isi = (
        _kepala(ALIS, COPY_JUDUL, ID_JUDUL)
        + _kartu(f"<h2>Belum dibuka</h2><p>{_e(COPY_TUTUP)}</p><p>{_e(COPY_TUTUP_SUDAH_BAYAR)}</p>")
        + _catatan_refund()
    )
    return _bungkus(ident, COPY_JUDUL, ID_JUDUL, isi)


def halaman_info(ident, judul: str, teks: str, tautan=None) -> bytes:
    """Pesan tetap tanpa form (kontak kosong, kuota habis, cek belum selesai, galat)."""
    isi = (
        _kepala(ALIS, COPY_JUDUL, ID_JUDUL)
        + _kartu(f"<h2>{_e(judul)}</h2><p>{_e(teks)}</p>")
        + _tautan(tautan)
    )
    return _bungkus(ident, COPY_JUDUL, ID_JUDUL, isi)


def _blok_qr(pilihan_kedua: bool = False) -> str:
    gambar = (
        f'<p><img src="{RUTE_QR}" alt="{_a(COPY_ALT_QR)}" width="{UKURAN_QR}" '
        f'height="{UKURAN_QR}"></p>'
    )
    if not pilihan_kedua:
        return gambar
    return f"<h2>{_e(COPY_JUDUL_QRIS)}</h2><p>{_e(COPY_PETUNJUK_QRIS)}</p>" + gambar


def _form(aksi: str, token: str) -> str:
    return (
        f'<form method="post" action="{AKSI_RUTE[aksi]}">'
        f'<input type="hidden" name="token" value="{_a(token)}">'
        '<p class="akun-aksi-sandi">'
        f'<button type="submit" class="tombol-utama-akun">{_e(COPY_TOMBOL[aksi])}</button></p>'
        "</form>"
    )


def _catatan_status(tampilan: dict) -> str:
    teks = []
    if (tampilan["status"] == STATUS_BELUM_BAYAR and not tampilan["qr"] and not tampilan["boleh_ulang"]
            and tampilan.get("qris", True)):
        teks.append(COPY_QR_BELUM_ADA)
    if tampilan["belum_terperiksa"]:
        teks.append(COPY_BELUM_TERPERIKSA)
    return "".join(f'<p class="funnel-catatan-st">{_e(t)}</p>' for t in teks)


def halaman_status(ident, tampilan: dict, token) -> bytes:
    """Status pesanan milik akun sesi.

    `tampilan`: status (salah satu status turunan), nama_anak, qr (bool), aksi (None,
    'periksa', 'buat', atau 'ulang'), boleh_ulang, belum_terperiksa. `token` hanya
    dipakai bila `aksi` ada. Satu aksi satu tombol. Opsional (jalur transfer):
    `blok_transfer` (HTML kartu transfer dari `pesanan_transfer_pages`, tampil sebelum QRIS)
    dan `qris` (False bila gerbang Midtrans tertutup: tanpa catatan QR).
    """
    transfer = tampilan.get("blok_transfer", "")
    pilih_cara = bool(transfer) and tampilan["status"] == STATUS_BELUM_BAYAR
    judul, kalimat = COPY_STATUS_PILIH_CARA if pilih_cara else COPY_STATUS[tampilan["status"]]
    isi = (
        _kepala(ALIS, COPY_JUDUL, ID_JUDUL, tampilan["nama_anak"])
        + _kartu(f"<h2>{_e(judul)}</h2><p>{_e(kalimat)}</p>"
                 f'<p class="funnel-catatan-st">{_e(COPY_HARGA)}</p>')
    )
    isi += transfer
    if tampilan["qr"]:
        isi += _kartu(_blok_qr(pilihan_kedua=bool(transfer)))
    isi += _catatan_status(tampilan)
    if tampilan["aksi"] is not None:
        isi += _kartu(_form(tampilan["aksi"], token))
    isi += _catatan_refund()
    return _bungkus(ident, COPY_JUDUL, ID_JUDUL, isi)


def tautan_hasil():
    return (RUTE_HASIL, "Kembali ke hasil cek")


def tautan_kontak():
    return (RUTE_KONTAK, "Lengkapi nomor WhatsApp")
