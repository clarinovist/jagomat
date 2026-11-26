"""Render tautan kode anak untuk guru: bagian di detail kelas dan halaman jawaban POST. Murni render, tanpa DB.

View-model hanya berisi teks, waktu, dan status. Tidak ada akun_id, siswa_id, kode, atau hash. Nama login anak hanya
muncul pada status `setuju` (dan pada halaman sukses POST). Semua nilai dinamis di-escape. Tanpa JS.
Halaman gagal dibuat dari teks tetap: byte-nya sama untuk setiap kegagalan kode (lihat `guru_tautan_http`).
"""

from __future__ import annotations

import html
from typing import Optional, Sequence

import guru_tautan_aturan as aturan
from pesanan_transfer_pages import waktu_wib
from support_pages import halaman_pesan

RUTE_KELAS = "/guru/kelas"
JUDUL_BAGIAN = "Tambah anak dengan kode"
COPY_BAGIAN = ("Minta kode dari orang tua anak. Permintaan dikirim ke orang tua untuk disetujui; "
               "anak masuk kelas setelah orang tua menyetujui.")
COPY_KOSONG_PERMINTAAN = "Belum ada permintaan untuk kelas ini."
LABEL_TOMBOL = "Ajukan ke orang tua"
JUDUL_GAGAL = "Kode tidak bisa dipakai"
TEKS_GAGAL = ("Periksa kode dari orang tua lalu coba lagi. "
              "Kode yang sudah diganti atau dicabut tidak bisa dipakai.")
JUDUL_BERHASIL = "Permintaan terkirim"
STATUS_LABEL = {
    aturan.STATUS_MENUNGGU: "Menunggu persetujuan orang tua",
    aturan.STATUS_SETUJU: "Disetujui orang tua",
    aturan.STATUS_TOLAK: "Ditolak orang tua",
    aturan.STATUS_KEDALUWARSA: "Kedaluwarsa",
    aturan.STATUS_BATAL: "Dibatalkan (kode diganti atau dicabut)",
}


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _formulir(kelompok_id: str, token: str) -> str:
    aksi = _e(f"{RUTE_KELAS}/{kelompok_id}/tautan")
    return (f'<form method="post" action="{aksi}">'
            '<p><label for="kode-anak">Kode anak</label></p>'
            '<p><input id="kode-anak" name="kode" type="text" autocomplete="off" '
            'autocapitalize="characters" spellcheck="false" required></p>'
            f'<input type="hidden" name="token" value="{_e(token)}">'
            f'<p><button type="submit">{LABEL_TOMBOL}</button></p></form>')


def _baris_permintaan(permintaan: dict) -> str:
    teks = f"Permintaan {waktu_wib(permintaan['dibuat'])} · {STATUS_LABEL[permintaan['status']]}"
    if permintaan.get("anak"):
        teks += f" · Anak: {permintaan['anak']}"
    return f"<li>{_e(teks)}</li>"


def _daftar_permintaan(permintaan: Sequence[dict]) -> str:
    if not permintaan:
        return f'<p class="jadwal-meta-st">{_e(COPY_KOSONG_PERMINTAAN)}</p>'
    return '<ol class="jadwal-daftar-st">' + "".join(_baris_permintaan(p) for p in permintaan) + "</ol>"


def bagian_tautan(kelompok_id: str, token: Optional[str], pesan_tutup: Optional[str],
                  permintaan: Sequence[dict]) -> str:
    """Bagian 'Tambah anak dengan kode' dan daftar permintaan kelompok itu.

    `token` None berarti kelompok tidak menerima anak sekarang: form tidak dirender dan `pesan_tutup` ditampilkan.
    `permintaan` tiap item: `dibuat` (UTC baku), `status` (salah satu STATUS_*), `anak` (nama login atau None).
    """
    if token is None:
        isi_form = f'<p class="jadwal-meta-st">{_e(pesan_tutup or "")}</p>'
    else:
        isi_form = _formulir(kelompok_id, token)
    return ('<section class="jadwal-kartu-st" aria-label="Tambah anak dengan kode">'
            f"<h2>{_e(JUDUL_BAGIAN)}</h2>"
            f'<p class="jadwal-meta-st">{_e(COPY_BAGIAN)}</p>'
            f"{isi_form}</section>"
            '<section class="jadwal-kartu-st" aria-label="Permintaan kode anak">'
            "<h2>Permintaan</h2>"
            f"{_daftar_permintaan(permintaan)}</section>")


def halaman_gagal() -> bytes:
    """Satu-satunya jawaban untuk kode yang tidak bisa dipakai. Teks tetap: tidak memuat kode, token, atau hitungan."""
    return halaman_pesan(JUDUL_GAGAL, f"<h1>{_e(JUDUL_GAGAL)}</h1><p>{_e(TEKS_GAGAL)}</p>")


def halaman_berhasil(nama_login: str, kedaluwarsa: str, kelompok_id: str) -> bytes:
    """Jawaban sukses: nama login anak dan status menunggu. Hanya dikirim langsung pada respons POST sukses."""
    isi = (f"<h1>{_e(JUDUL_BERHASIL)}</h1>"
           f"<p>Permintaan untuk <strong>{_e(nama_login)}</strong> sudah dikirim ke orang tua.</p>"
           "<p>Status: menunggu persetujuan orang tua. "
           f"Berlaku sampai {_e(waktu_wib(kedaluwarsa))}.</p>"
           f'<p><a href="{_e(RUTE_KELAS + "/" + kelompok_id)}">Kembali ke kelas</a></p>')
    return halaman_pesan(JUDUL_BERHASIL, isi)


def halaman_info(judul: str, teks: str) -> bytes:
    """Pesan singkat untuk kondisi kelompok atau laju (bukan kegagalan kode)."""
    return halaman_pesan(judul, f"<h1>{_e(judul)}</h1><p>{_e(teks)}</p>")
