"""Renderer murni blok "Kode anak untuk guru" di detail order Paket Belajar admin (Fase 3b-5). Tanpa I/O.

Blok hanya memuat keadaan kode aktif: tanggal pembuatan dan peran pembuat ("admin" atau "orang tua"). Kode mentah,
hash, id akun, dan id siswa TIDAK pernah masuk ke blok ini. Kode mentah hanya muncul di `halaman_kode_baru`, sekali,
pada respons POST buat/ganti. Semua nilai dinamis di-escape.
"""

from __future__ import annotations

import html
from typing import Mapping, Optional

from pesanan_transfer_pages import waktu_wib

RUTE_KODE = "/admin/kelas/kode-anak"
RUTE_DETAIL = "/admin/kelas/verifikasi"
TINDAKAN_BUAT = "buat"
TINDAKAN_GANTI = "ganti"
TINDAKAN_CABUT = "cabut"
JUDUL_KARTU = "Kode anak untuk guru"
COPY_KARTU = ("Guru memasukkan kode ini untuk memasukkan anak ke kelompok Mini miliknya. "
              "Kode hanya tampil sekali saat dibuat dan tidak bisa dilihat lagi.")
COPY_BELUM = "Belum ada kode aktif."
COPY_TAK_TERBACA = "Kode anak belum bisa ditampilkan sekarang. Muat ulang halaman, ya."
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk membuat atau mengganti kode."
COPY_PEMBUAT = {"admin": "admin", "orang_tua": "orang tua"}
COPY_DAMPAK = ("Ganti atau cabut mematikan kode yang sudah diberikan ke guru, dan permintaan guru yang menunggu "
               "ikut dibatalkan.")
LABEL_BUAT = "Buat kode"
LABEL_GANTI = "Ganti kode"
LABEL_CABUT = "Cabut semua kode anak ini"
KONFIRMASI_GANTI = ("Ganti kode anak ini? Kode yang sudah diberikan ke guru tidak berlaku lagi, dan permintaan guru "
                    "yang menunggu dibatalkan. Kode baru tampil sekali.")
KONFIRMASI_CABUT = ("Cabut semua kode anak ini? Kode yang sudah diberikan ke guru tidak berlaku lagi, dan permintaan "
                    "guru yang menunggu dibatalkan. Tidak bisa dibatalkan.")
JUDUL_KODE_BARU = "Kode anak baru"
COPY_KODE_BARU = "Teruskan ke guru sekarang. Kode ini hanya tampil sekali dan tidak bisa dilihat lagi."
JUDUL_CABUT = "Kode anak dicabut"
COPY_CABUT = "Guru tidak bisa lagi memakai kode itu. Buat kode baru kalau perlu."
KALIMAT_KEMBALI = "Kembali ke detail order"


def _e(teks) -> str:
    return html.escape(str(teks), quote=True)


def _formulir(order_id: str, tindakan: str, label: str, token: str, *, kode_id: Optional[int] = None,
              konfirmasi: str = "", kelas: str = "admin-tombol") -> str:
    kode_html = f'<input type="hidden" name="kode_id" value="{_e(kode_id)}">' if kode_id is not None else ""
    atribut = f' data-konfirmasi="{_e(konfirmasi)}"' if konfirmasi else ""
    return (f'<form method="post" action="{_e(RUTE_KODE)}"{atribut}>'
            f'<input type="hidden" name="tindakan" value="{_e(tindakan)}">'
            f'<input type="hidden" name="order_id" value="{_e(order_id)}">{kode_html}'
            f'<input type="hidden" name="token" value="{_e(token)}">'
            f'<button class="{_e(kelas)}" type="submit">{_e(label)}</button></form>')


def _teks_aktif(aktif: Mapping) -> str:
    pembuat = COPY_PEMBUAT.get(aktif["peran"], COPY_PEMBUAT["orang_tua"])
    return f"<p>Kode aktif sejak {_e(waktu_wib(aktif['dibuat']))}, dibuat oleh {_e(pembuat)}.</p>"


def _isi_formulir(order_id: str, aktif: Optional[Mapping], tokens: Mapping) -> str:
    """Formulir buat (tanpa aktif) atau ganti dan cabut (dengan `kode_id` aktif dan konfirmasi)."""
    if aktif is None:
        return _formulir(order_id, TINDAKAN_BUAT, LABEL_BUAT, tokens[TINDAKAN_BUAT])
    ganti = _formulir(order_id, TINDAKAN_GANTI, LABEL_GANTI, tokens[TINDAKAN_GANTI], kode_id=aktif["id"],
                      konfirmasi=KONFIRMASI_GANTI)
    cabut = _formulir(order_id, TINDAKAN_CABUT, LABEL_CABUT, tokens[TINDAKAN_CABUT],
                      konfirmasi=KONFIRMASI_CABUT, kelas="admin-tombol admin-bahaya-garis")
    return f'<p class="admin-meta">{_e(COPY_DAMPAK)}</p>' + ganti + cabut


def _bungkus(isi: str) -> str:
    return (f'<section class="admin-kartu" id="admin-kode-anak"><h2>{_e(JUDUL_KARTU)}</h2>'
            f'<p class="admin-meta">{_e(COPY_KARTU)}</p>{isi}</section>')


def blok(order_id: str, aktif: Optional[Mapping], tokens: Optional[Mapping]) -> str:
    """Blok kode anak. `aktif` = {"id", "dibuat", "peran"} atau None; `tokens` = {tindakan: token} atau None
    (sesi bukan kuki: tampilan baca-saja tanpa formulir)."""
    teks = f"<p>{_e(COPY_BELUM)}</p>" if aktif is None else _teks_aktif(aktif)
    if tokens is None:
        return _bungkus(teks + f'<p class="admin-meta">{_e(COPY_TANPA_SESI)}</p>')
    return _bungkus(teks + _isi_formulir(order_id, aktif, tokens))


def blok_tak_terbaca() -> str:
    """Blok tanpa formulir bila keadaan kode tidak bisa dibaca: tidak pernah menampilkan 'belum ada kode' yang keliru."""
    return _bungkus(f"<p>{_e(COPY_TAK_TERBACA)}</p>")


def _kembali(order_id: str) -> str:
    return f'<p><a class="admin-tautan" href="{_e(RUTE_DETAIL)}?order={_e(order_id)}">{_e(KALIMAT_KEMBALI)}</a></p>'


def halaman_kode_baru(order_id: str, kode_tampil: str) -> str:
    """Isi respons buat/ganti: kode tampil sekali. Hanya dikirim sebagai respons langsung (no-store), tanpa redirect."""
    return ('<section class="admin-kartu">'
            f"<h2>{_e(JUDUL_KODE_BARU)}</h2><p>{_e(COPY_KODE_BARU)}</p>"
            f"<p><strong>{_e(kode_tampil)}</strong></p>{_kembali(order_id)}</section>")


def halaman_cabut(order_id: str) -> str:
    """Isi respons cabut: tanpa kode."""
    return ('<section class="admin-kartu">'
            f"<h2>{_e(JUDUL_CABUT)}</h2><p>{_e(COPY_CABUT)}</p>{_kembali(order_id)}</section>")
