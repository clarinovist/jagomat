"""Render kartu 'Kode anak untuk guru' di halaman orang tua dan jawaban POST kode. Murni render, tanpa DB.

Kode mentah hanya muncul di `halaman_kode_baru` (sekali, pada respons POST buat/ganti). Kartu tidak pernah memuat kode,
hash, atau id akun: hanya tanggal kode aktif dan peran pembuatnya ("admin" atau "Ayah/Bunda").

Permintaan guru yang menunggu (3b-3) dirender di `bagian_menunggu`, sesudah form kode di dalam kartu. Setiap form
putusan memuat hanya `permintaan_id`, `hasil`, dan `token`. Form ganti/cabut memuat centang konfirmasi wajib.
"""

from __future__ import annotations

import html
from typing import Dict, Optional

from orang_tua_style import RUTE
from pesanan_transfer_pages import waktu_wib
from support_pages import halaman_pesan_murid

RUTE_KODE = RUTE + "/kode"
RUTE_PUTUSAN = RUTE + "/tautan"
TINDAKAN_BUAT = "buat"
TINDAKAN_GANTI = "ganti"
TINDAKAN_CABUT = "cabut"
HASIL_SETUJU = "setuju"
HASIL_TOLAK = "tolak"
COPY_KONFIRMASI_UBAH = "Kode yang sudah diberikan ke guru akan mati; permintaan yang menunggu dibatalkan."
JUDUL_MENUNGGU = "Permintaan guru menunggu"
COPY_MENUNGGU = ("Guru mengajukan anak ini untuk masuk kelompoknya. Setuju menempatkan anak ke kelompok itu; "
                 "tolak membatalkan permintaan.")
COPY_KOSONG_MENUNGGU = "Belum ada permintaan guru yang menunggu."
COPY_MENUNGGU_TAK_TERBACA = "Permintaan guru belum bisa ditampilkan sekarang. Muat ulang halaman, ya."
LABEL_SETUJU = "Setuju"
LABEL_TOLAK = "Tolak"
JUDUL_SETUJU = "Permintaan disetujui"
TEKS_SETUJU = "Anak sudah masuk kelompok itu. Guru bisa melihat anak di kelasnya."
JUDUL_TOLAK = "Permintaan ditolak"
TEKS_TOLAK = "Anak tidak masuk kelompok itu. Guru yang sama baru bisa mengajukan lagi setelah 7 hari."
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


def _konfirmasi_html(tindakan: str) -> str:
    """Centang wajib untuk tindakan yang mematikan kode lama (ganti, cabut). Server juga menolak tanpa centang."""
    if tindakan == TINDAKAN_BUAT:
        return ""
    return ('<label class="ortu-konfirmasi-st"><input type="checkbox" name="konfirmasi" value="1" required>'
            f'<span>{_e(COPY_KONFIRMASI_UBAH)}</span></label>')


def _formulir(tindakan: str, label: str, token: str, kode_id: Optional[int] = None) -> str:
    kode_html = f'<input type="hidden" name="kode_id" value="{_e(kode_id)}">' if kode_id is not None else ""
    return (f'<form method="post" action="{_e(RUTE_KODE)}">'
            f'<input type="hidden" name="tindakan" value="{_e(tindakan)}">{kode_html}'
            f'<input type="hidden" name="token" value="{_e(token)}">{_konfirmasi_html(tindakan)}'
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


def kartu(aktif: Optional[dict], tokens: Dict[str, str], menunggu_html: str = "") -> str:
    """Kartu kode anak. `aktif` = {"id", "dibuat", "peran"} atau None; `tokens` berisi token per tindakan yang tampil."""
    return _bungkus(_isi_kartu(aktif, tokens) + menunggu_html)


def kartu_tak_terbaca() -> str:
    """Kartu tanpa form bila keadaan kode tidak bisa dibaca: tidak pernah menampilkan 'belum ada kode' yang keliru."""
    return _bungkus(f"<p>{_e(COPY_TAK_TERBACA)}</p>")


def _formulir_putusan(permintaan_id: int, hasil: str, label: str, token: str) -> str:
    return (f'<form method="post" action="{_e(RUTE_PUTUSAN)}">'
            f'<input type="hidden" name="permintaan_id" value="{_e(permintaan_id)}">'
            f'<input type="hidden" name="hasil" value="{_e(hasil)}">'
            f'<input type="hidden" name="token" value="{_e(token)}">'
            f'<button type="submit" class="ortu-tombol-st">{_e(label)}</button></form>')


def _baris_menunggu(baris: dict) -> str:
    """Satu permintaan: guru, kelompok, pertemuan pertama, waktu pengajuan, batas, dan dua form putusan."""
    tokens = baris["tokens"]
    rincian = [f"<p><strong>{_e(baris['guru'])}</strong> mengajukan anak ini untuk "
               f"<strong>{_e(baris['kelompok'])}</strong>.</p>"]
    if baris["mulai"]:
        rincian.append(f"<p>Pertemuan pertama {_e(waktu_wib(baris['mulai']))}.</p>")
    rincian.append(f"<p>Diajukan {_e(waktu_wib(baris['dibuat']))}. "
                   f"Berlaku sampai {_e(waktu_wib(baris['kedaluwarsa']))}.</p>")
    return ('<li class="ortu-permintaan-st">' + "".join(rincian)
            + _formulir_putusan(baris["id"], HASIL_SETUJU, LABEL_SETUJU, tokens[HASIL_SETUJU])
            + _formulir_putusan(baris["id"], HASIL_TOLAK, LABEL_TOLAK, tokens[HASIL_TOLAK]) + "</li>")


def _bungkus_menunggu(isi: str) -> str:
    return f'<div id="ortu-tautan-menunggu"><h3>{_e(JUDUL_MENUNGGU)}</h3>{isi}</div>'


def bagian_menunggu(baris: list) -> str:
    """Daftar permintaan menunggu. `baris` = dict hasil `orang_tua_putusan_daftar` plus `tokens` per hasil."""
    if not baris:
        return _bungkus_menunggu(f"<p>{_e(COPY_KOSONG_MENUNGGU)}</p>")
    daftar = "".join(_baris_menunggu(b) for b in baris)
    return _bungkus_menunggu(f"<p>{_e(COPY_MENUNGGU)}</p><ul>{daftar}</ul>")


def bagian_menunggu_tak_terbaca() -> str:
    """Bagian permintaan bila data kelompok/guru belum bisa dibaca; kartu kode tetap tampil."""
    return _bungkus_menunggu(f"<p>{_e(COPY_MENUNGGU_TAK_TERBACA)}</p>")


def halaman_putusan(hasil: str) -> bytes:
    """Jawaban sukses setuju/tolak: 200 tanpa data anak, guru, atau id."""
    if hasil == HASIL_SETUJU:
        return halaman_info(JUDUL_SETUJU, TEKS_SETUJU)
    return halaman_info(JUDUL_TOLAK, TEKS_TOLAK)


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
