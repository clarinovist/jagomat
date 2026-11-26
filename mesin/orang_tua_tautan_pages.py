"""Render kartu 'Kode anak untuk guru' di halaman orang tua dan jawaban POST kode. Murni render, tanpa DB.

Kode mentah hanya muncul di `halaman_kode_baru` (sekali, pada respons POST buat/ganti). Kartu tidak pernah memuat kode,
hash, atau id akun: hanya tanggal kode aktif dan peran pembuatnya ("admin" atau "Ayah/Bunda").

TITIK SISIP (3b-3 persetujuan, langkah berikutnya): daftar permintaan menunggu dirender di `kartu`, sesudah form.
"""

from __future__ import annotations

import html
from typing import Dict, Optional

from orang_tua_style import RUTE
from pesanan_transfer_pages import waktu_wib
from support_pages import halaman_pesan_murid

RUTE_KODE = RUTE + "/kode"
TINDAKAN_BUAT = "buat"
TINDAKAN_GANTI = "ganti"
TINDAKAN_CABUT = "cabut"
JUDUL_KARTU = "Kode anak untuk guru"
COPY_KARTU = ("Guru memasukkan kode ini untuk memasukkan anak ke kelompok Mini miliknya. "
              "Kode tidak bisa dilihat lagi setelah dibuat.")
COPY_BELUM = "Belum ada kode aktif."
COPY_TAK_TERBACA = "Kode anak belum bisa ditampilkan sekarang. Muat ulang halaman, ya."
COPY_GANTI = "Ganti kode mematikan kode yang sudah diberikan ke guru."
COPY_PEMBUAT = {"admin": "admin", "orang_tua": "Ayah/Bunda"}
LABEL_BUAT = "Buat kode"
LABEL_GANTI = "Ganti kode"
LABEL_CABUT = "Cabut kode"
COPY_BELUM_PIN = "Pasang PIN halaman Ayah/Bunda dulu, lalu buka halaman ini dengan PIN."
JUDUL_KODE_BARU = "Kode anak baru"
COPY_KODE_BARU = ("Catat sekarang. Kode ini hanya tampil sekali, dan kode lama tidak bisa dilihat lagi. "
                  "Ganti kode mematikan kode yang sudah diberikan ke guru.")
JUDUL_CABUT = "Kode anak dicabut"
COPY_CABUT = "Guru tidak bisa lagi memakai kode itu. Buat kode baru kalau perlu."
JUDUL_BASI = "Kode belum bisa diproses"
TEKS_BASI = "Keadaan kode sudah berubah. Muat ulang halaman, lalu coba lagi."
JUDUL_ANAK = "Kode anak tidak bisa dibuat"
TEKS_ANAK = "Akun anak ini sudah tidak aktif, jadi kode tidak bisa dibuat atau diganti."
JUDUL_TUNGGU = "Belum bisa diproses"
TEKS_TUNGGU = "Kode anak belum bisa diproses sekarang. Coba lagi sebentar."
JUDUL_BELUM_PIN = "PIN belum dipasang"
KALIMAT_KEMBALI = "Kembali ke halaman Ayah/Bunda"


def _e(teks) -> str:
    return html.escape(str(teks), quote=True)


def _formulir(tindakan: str, label: str, token: str, kode_id: Optional[int] = None) -> str:
    kode_html = f'<input type="hidden" name="kode_id" value="{_e(kode_id)}">' if kode_id is not None else ""
    return (f'<form method="post" action="{_e(RUTE_KODE)}">'
            f'<input type="hidden" name="tindakan" value="{_e(tindakan)}">{kode_html}'
            f'<input type="hidden" name="token" value="{_e(token)}">'
            f'<button type="submit" class="ortu-tombol-st">{_e(label)}</button></form>')


def _baris_aktif(aktif: dict) -> str:
    pembuat = COPY_PEMBUAT.get(aktif["peran"], COPY_PEMBUAT["orang_tua"])
    return f"<p>Kode aktif sejak {_e(waktu_wib(aktif['dibuat']))}, dibuat oleh {_e(pembuat)}.</p>"


def _isi_kartu(aktif: Optional[dict], tokens: Dict[str, str]) -> str:
    if aktif is None:
        return f"<p>{_e(COPY_BELUM)}</p>" + _formulir(TINDAKAN_BUAT, LABEL_BUAT, tokens[TINDAKAN_BUAT])
    return (_baris_aktif(aktif)
            + f"<p>{_e(COPY_GANTI)}</p>"
            + _formulir(TINDAKAN_GANTI, LABEL_GANTI, tokens[TINDAKAN_GANTI], aktif["id"])
            + _formulir(TINDAKAN_CABUT, LABEL_CABUT, tokens[TINDAKAN_CABUT], aktif["id"]))


def _bungkus(isi: str) -> str:
    return (f'<section class="ortu-kartu-st" id="ortu-kode-guru"><h2>{_e(JUDUL_KARTU)}</h2>'
            f"<p>{_e(COPY_KARTU)}</p>{isi}</section>")


def kartu(aktif: Optional[dict], tokens: Dict[str, str]) -> str:
    """Kartu kode anak. `aktif` = {"id", "dibuat", "peran"} atau None; `tokens` berisi token per tindakan yang tampil."""
    return _bungkus(_isi_kartu(aktif, tokens))


def kartu_tak_terbaca() -> str:
    """Kartu tanpa form bila keadaan kode tidak bisa dibaca: tidak pernah menampilkan 'belum ada kode' yang keliru."""
    return _bungkus(f"<p>{_e(COPY_TAK_TERBACA)}</p>")


def halaman_kode_baru(kode_tampil: str) -> bytes:
    """Jawaban POST buat/ganti: kode tampil sekali. Hanya dikirim sebagai respons langsung (no-store), tanpa redirect."""
    isi = (f"<h1>{_e(JUDUL_KODE_BARU)}</h1><p>{_e(COPY_KODE_BARU)}</p>"
           f"<p><strong>{_e(kode_tampil)}</strong></p>"
           f'<p><a href="{_e(RUTE)}">{_e(KALIMAT_KEMBALI)}</a></p>')
    return halaman_pesan_murid(JUDUL_KODE_BARU, isi)


def halaman_cabut() -> bytes:
    """Jawaban POST cabut: tanpa kode."""
    isi = f"<h1>{_e(JUDUL_CABUT)}</h1><p>{_e(COPY_CABUT)}</p><p><a href=\"{_e(RUTE)}\">{_e(KALIMAT_KEMBALI)}</a></p>"
    return halaman_pesan_murid(JUDUL_CABUT, isi)


def halaman_info(judul: str, teks: str) -> bytes:
    """Pesan singkat untuk keadaan kode yang basi atau belum bisa diproses. Tidak memuat kode, token, atau id."""
    isi = f"<h1>{_e(judul)}</h1><p>{_e(teks)}</p><p><a href=\"{_e(RUTE)}\">{_e(KALIMAT_KEMBALI)}</a></p>"
    return halaman_pesan_murid(judul, isi)


def halaman_belum_pin() -> bytes:
    """Jawaban POST saat PIN belum dipasang: kode tidak dibuat. Tanpa data anak."""
    return halaman_info(JUDUL_BELUM_PIN, COPY_BELUM_PIN)
