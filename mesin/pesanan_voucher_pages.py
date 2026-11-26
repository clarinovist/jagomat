"""Kartu "Deposit dan laporan" di halaman status pesanan pembeli: deposit Rp49.000, masa berlaku, janji terbit laporan.

Hanya HTML native (tanpa JS) dan TANPA tombol atau form apa pun: tidak ada pilihan pembeli dan tidak ada uang kembali
otomatis (keputusan Pemilik 24 Nov 2026); Rp49.000 menjadi deposit yang memotong tagihan kelas bersama Guru.
Renderer murni: menerima `purna.KeadaanPurna` yang sudah dibaca pemanggil; tidak membuka DB dan tidak membuat token.
Isi kartu hanya nominal deposit (dari `pesanan_dasar.RUPIAH_PAKET`), status turunan, dan waktu (WIB lewat
`pesanan_transfer_pages.waktu_wib`). Kode voucher internal TIDAK ditampilkan ke pembeli (tetap ada di domain dan
admin). Tanpa kontak, tanpa kunci/malrule/diagnosis, tanpa operasi_id atau order_id: kartu ini tampil di permukaan
murid.
"""
from __future__ import annotations

from cek_pages import _e
import pesanan_dasar
import purna
from pesanan_transfer_pages import rupiah, waktu_wib

ID_KARTU = "kartu-voucher"
COPY_JUDUL = "Potongan dan laporan"
COPY_DEPOSIT = "Potongan "
COPY_POTONGAN = "Memotong tagihan bulan pertama kelas bersama Guru bila Anda mendaftar."
COPY_BERLAKU = "Berlaku hingga "
COPY_STATUS_VOUCHER = {
    purna.VOUCHER_BELUM_LUNAS: "Potongan aktif setelah pembayaran diterima.",
    purna.VOUCHER_AKTIF: "Potongan aktif.",
    purna.VOUCHER_DIPAKAI: "Potongan sudah terpakai.",
    purna.VOUCHER_KEDALUWARSA: "Potongan sudah kedaluwarsa.",
    purna.VOUCHER_BATAL: "Potongan tidak berlaku lagi karena uang sudah dikembalikan.",
    purna.VOUCHER_DITAHAN: "Potongan ditahan sampai pembayaran selesai diperiksa tim.",
}
COPY_TERBIT = "Laporan sudah terbit."
COPY_JANJI = "Laporan langsung terbit setelah pembayaran terverifikasi."
COPY_TERLAMBAT = "Laporan belum terbit. Hubungi tim lewat WhatsApp; kami bantu sampai laporan Anda terbit."


def _baris(teks: str) -> str:
    return f'<p class="funnel-catatan-st">{_e(teks)}</p>'


def teks_janji(k) -> str:
    """Satu kalimat status laporan: sudah terbit, atau laporan terbit otomatis setelah pembayaran terverifikasi."""
    if k.terbit is not None:
        return COPY_TERBIT
    return COPY_TERLAMBAT if k.terlambat else COPY_JANJI


def _blok_laporan(k) -> str:
    return _baris(teks_janji(k))


def kartu_voucher(k) -> str:
    """Kartu deposit dan laporan untuk order lunas (tanpa tombol, tanpa kode voucher)."""
    isi = (
        f"<h2>{_e(COPY_JUDUL)}</h2>"
        f'<p class="funnel-catatan-st"><b>{_e(COPY_DEPOSIT + rupiah(pesanan_dasar.RUPIAH_PAKET))}</b></p>'
        + _baris(COPY_POTONGAN)
        + _baris(COPY_BERLAKU + waktu_wib(k.berlaku_hingga))
        + _baris(COPY_STATUS_VOUCHER[k.voucher])
        + _blok_laporan(k)
    )
    return f'<div class="kartu-st" id="{ID_KARTU}">{isi}</div>'
