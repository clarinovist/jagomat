"""Kartu "Voucher dan laporan" di halaman status pesanan pembeli (V4a): kode voucher, tenggat, janji terbit laporan.

Hanya HTML native (tanpa JS). Renderer murni: menerima `purna.KeadaanPurna` yang sudah dibaca pemanggil dan token form
pilihan; tidak membuka DB dan tidak membuat token. Isi kartu hanya kode TURUNAN dan waktu (WIB lewat
`pesanan_transfer_pages.waktu_wib`, helper yang sudah ada). Tanpa kontak, tanpa kunci/malrule/diagnosis, tanpa
operasi_id atau order_id: kartu ini tampil di permukaan murid.

Tombol pilihan (menunggu / uang kembali) hanya dirender bila `tombol_tampil`: permukaan punya rute pilih (murid; guru
lama `None`), keadaan `bisa_pilih`, dan pilihan belum `uang_kembali` (final). UI memakai `k.pilihan`, bukan hanya
`bisa_pilih`, karena `bisa_pilih` tetap True sesudah memilih uang kembali.
"""
from __future__ import annotations

from cek_pages import _a, _e
import purna
from pesanan_permukaan import Rute
from pesanan_transfer_pages import waktu_wib

ID_KARTU = "kartu-voucher"
COPY_JUDUL = "Voucher dan laporan"
COPY_STATUS_VOUCHER = {
    purna.VOUCHER_BELUM_LUNAS: "Voucher aktif setelah pembayaran diterima.",
    purna.VOUCHER_AKTIF: "Voucher aktif. Pakai kode ini bila Anda lanjut ke kelas bersama Guru.",
    purna.VOUCHER_DIPAKAI: "Voucher sudah dipakai.",
    purna.VOUCHER_KEDALUWARSA: "Voucher sudah kedaluwarsa.",
    purna.VOUCHER_BATAL: "Voucher tidak berlaku lagi karena uang dikembalikan atau diminta kembali.",
}
COPY_TERBIT = "Laporan sudah terbit."
COPY_JANJI = "Laporan lengkap dijanjikan terbit "
COPY_TERLAMBAT = (
    "Laporan belum terbit dan sudah lewat batas waktu. Mohon maaf atas keterlambatan. "
    "Anda boleh memilih tetap menunggu atau meminta uang kembali penuh."
)
COPY_MEMILIH_MENUNGGU = "Anda memilih menunggu."
COPY_UANG_KEMBALI_DICATAT = "Permintaan uang kembali dicatat. Tim akan menghubungi Anda."
COPY_TOMBOL = {
    purna.PILIHAN_MENUNGGU: "Tetap menunggu",
    purna.PILIHAN_UANG_KEMBALI: "Minta uang kembali",
}
_KELAS_TOMBOL = {purna.PILIHAN_MENUNGGU: "tombol-utama-akun", purna.PILIHAN_UANG_KEMBALI: "tombol-sekunder"}


def tombol_tampil(k, rute: Rute) -> bool:
    """True bila form pilihan boleh dirender (dan token pilihnya perlu dibuat)."""
    return rute.pilih is not None and k.bisa_pilih and k.pilihan != purna.PILIHAN_UANG_KEMBALI


def _baris(teks: str) -> str:
    return f'<p class="funnel-catatan-st">{_e(teks)}</p>'


def _pilihan_tersedia(k) -> tuple:
    """Pilihan yang ditawarkan: keduanya bila belum memilih, hanya uang kembali bila sudah memilih menunggu."""
    if k.pilihan == purna.PILIHAN_MENUNGGU:
        return (purna.PILIHAN_UANG_KEMBALI,)
    return (purna.PILIHAN_MENUNGGU, purna.PILIHAN_UANG_KEMBALI)


def _form_pilih(k, rute: Rute, token: str) -> str:
    tombol = "".join(
        f'<button type="submit" name="pilihan" value="{_a(nilai)}" class="{_KELAS_TOMBOL[nilai]}">'
        f"{_e(COPY_TOMBOL[nilai])}</button> "
        for nilai in _pilihan_tersedia(k))
    return (f'<form method="post" action="{_a(rute.pilih)}">'
            f'<input type="hidden" name="token" value="{_a(token)}">'
            f'<p class="akun-aksi-sandi">{tombol}</p></form>')


def teks_janji(k) -> str:
    """Satu kalimat status laporan: sudah terbit, atau janji terbit (WIB)."""
    return COPY_TERBIT if k.terbit is not None else COPY_JANJI + waktu_wib(k.janji_terbit)


def _blok_laporan(k) -> str:
    janji = _baris(teks_janji(k))
    return janji + (_baris(COPY_TERLAMBAT) if k.terlambat else "")


def _catatan_pilihan(k) -> str:
    """Kalimat pilihan yang sudah dicatat (uang kembali final; menunggu hanya selama laporan belum terbit)."""
    if k.pilihan == purna.PILIHAN_UANG_KEMBALI:
        return _baris(COPY_UANG_KEMBALI_DICATAT)
    if k.pilihan == purna.PILIHAN_MENUNGGU and k.terbit is None:
        return _baris(COPY_MEMILIH_MENUNGGU)
    return ""


def _blok_pilihan(k, rute: Rute, token) -> str:
    catatan = _catatan_pilihan(k)
    if token is None or not tombol_tampil(k, rute):
        return catatan
    return catatan + _form_pilih(k, rute, token)


def kartu_voucher(k, rute: Rute, token_pilih) -> str:
    """Kartu voucher dan laporan untuk order lunas; `token_pilih` hanya dipakai bila tombol tampil."""
    isi = (
        f"<h2>{_e(COPY_JUDUL)}</h2>"
        f'<p class="funnel-catatan-st"><b>Kode voucher:</b> <code>{_e(k.kode)}</code></p>'
        + _baris(COPY_STATUS_VOUCHER[k.voucher])
        + _baris("Berlaku hingga " + waktu_wib(k.berlaku_hingga))
        + _blok_laporan(k)
        + _blok_pilihan(k, rute, token_pilih)
    )
    return f'<div class="kartu-st" id="{ID_KARTU}">{isi}</div>'
