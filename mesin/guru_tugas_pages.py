"""Render halaman guru tugas untuk anak tertaut (Fase 3c): murni render, tanpa DB, HTTP, atau berkas.

Daftar anak (`halaman_daftar`): tiap item `nama` (nama login anak, K6) dan `order_id` (hanya untuk href).
Halaman anak (`halaman_anak`): `nama`, `order_id`, `opsi_topik` (pasangan (id, label); None atau kosong = tanpa
form), `hari_ini` dan `tenggat_maks` (YYYY-MM-DD, untuk atribut input tanggal), `token`, `tugas` (daftar view-model
dengan `topik` berlabel, `tenggat`, `status_tenggat`, `selesai`, `benar`, `total`; None = daftar tak terbaca).

Tanpa `siswa_id`, `sesi_id`, atau id akun di badan halaman. Semua nilai di-escape. Tanpa JS. Status selalu berupa
teks, tidak hanya warna. Skor `benar dari total` hanya tampil bila sesi sudah selesai (keputusan Pemilik T2/K11).
"""
from __future__ import annotations

import html
from datetime import date
from typing import List, Optional

import design_tokens as T
from teacher_shell import _halaman_stitch

RUTE_TUGAS = "/guru/tugas"
RUTE_JADWAL = "/guru/jadwal"
KELAS_BUNGKUS = "tugas-guru-st"
BULAN = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)
LABEL_TENGGAT = {"tanpa": "Tanpa tenggat", "berjalan": "Tenggat", "lewat": "Lewat tenggat"}
COPY_BELUM_DIKERJAKAN = "Belum dikerjakan"
COPY_SELESAI = "Selesai"
COPY_TANPA_ANAK = "Belum ada anak tertaut. Anak muncul di sini setelah masuk kelas Anda."
COPY_TUGAS_KOSONG = "Belum ada tugas untuk anak ini."
COPY_TUGAS_TIDAK_TERBACA = "Daftar tugas belum bisa dibaca sekarang. Muat ulang halaman nanti."
COPY_TOPIK_TIDAK_TERSEDIA = "Pilihan topik belum bisa dimuat sekarang. Coba lagi nanti."
COPY_TOPIK_KOSONG = "Belum ada topik yang bisa ditugaskan."
COPY_TOMBOL = "Beri tugas"
COPY_PILIH_TOPIK = "Pilih topik"
COPY_KEMBALI_DAFTAR = "Kembali ke daftar anak"
COPY_KEMBALI_JADWAL = "Kembali ke Jadwal saya"

GAYA = f"""<style>
.tugas-st {{ display: grid; gap: {T.SP_4}; }}
.tugas-st h1 {{ margin: 0 0 {T.SP_2}; }}
.tugas-alis-st {{ color: {T.TEKS_SUBTLE}; font-size: {T.UKURAN_TEKS_LABEL}; letter-spacing: .04em; margin: 0; }}
.tugas-meta-st {{ color: {T.TEKS_SUBTLE}; font-size: {T.UKURAN_TEKS_LABEL}; margin: 0; }}
.tugas-kartu-st {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_4}; display: grid; gap: {T.SP_3}; }}
.tugas-kartu-st h2 {{ margin: 0; font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.tugas-form-st {{ display: grid; gap: {T.SP_3}; margin: 0; }}
.tugas-form-st select, .tugas-form-st input {{ padding: {T.SP_2}; border: {T.TEBAL_GARIS} solid {T.BORDER_INTERAKTIF};
  border-radius: {T.RADIUS_KECIL}; font: inherit; max-width: 100%; }}
.tugas-daftar-st {{ list-style: none; margin: 0; padding: 0; display: grid; gap: {T.SP_3}; }}
.tugas-daftar-st li {{ border-bottom: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; padding-bottom: {T.SP_2}; }}
.tugas-tombol-st {{ background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; border: 0;
  border-radius: {T.RADIUS_KECIL}; padding: {T.SP_3} {T.SP_5}; font: inherit; font-weight: 600;
  cursor: pointer; justify-self: start; }}
.tugas-tautan-st {{ color: {T.AKSEN_TEAL_TUA}; }}
.tugas-st :focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
</style>"""


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _p(teks: str, kelas: str = "") -> str:
    atribut = f' class="{kelas}"' if kelas else ""
    return f"<p{atribut}>{_e(teks)}</p>"


def tanggal_id(tanggal: str) -> str:
    """'2026-11-25' menjadi '25 November 2026'. Tanggal dari penyimpanan sudah tervalidasi pemanggil."""
    hari = date.fromisoformat(tanggal)
    return f"{hari.day} {BULAN[hari.month - 1]} {hari.year}"


def _teks_tenggat(tugas: dict) -> str:
    status = tugas["status_tenggat"]
    if status == "tanpa":
        return LABEL_TENGGAT["tanpa"]
    return f"{LABEL_TENGGAT[status]} {tanggal_id(tugas['tenggat'])}"


def _teks_hasil(tugas: dict) -> str:
    """Status selalu teks. Skor hanya bila sesi sudah selesai."""
    if not tugas["selesai"]:
        return COPY_BELUM_DIKERJAKAN
    return f"{COPY_SELESAI} · Benar {int(tugas['benar'])} dari {int(tugas['total'])}"


def _baris_tugas(tugas: dict) -> str:
    return (f'<li class="tugas-baris-st"><strong>{_e(tugas["topik"])}</strong>'
            f'<p class="tugas-meta-st">{_e(_teks_tenggat(tugas))} · {_e(_teks_hasil(tugas))}</p></li>')


def _bagian_tugas(tugas: Optional[List[dict]]) -> str:
    if tugas is None:
        isi = _p(COPY_TUGAS_TIDAK_TERBACA, "tugas-meta-st")
    elif not tugas:
        isi = _p(COPY_TUGAS_KOSONG, "tugas-meta-st")
    else:
        isi = '<ol class="tugas-daftar-st">' + "".join(_baris_tugas(t) for t in tugas) + "</ol>"
    return ('<section class="tugas-kartu-st" aria-label="Tugas yang sudah diberikan">'
            f"<h2>Tugas yang sudah diberikan</h2>{isi}</section>")


def _opsi_topik(opsi: list) -> str:
    baris = [f'<option value="" disabled selected>{_e(COPY_PILIH_TOPIK)}</option>']
    for id_topik, label in opsi:
        baris.append(f'<option value="{_e(id_topik)}">{_e(label)}</option>')
    return "".join(baris)


def _form(tampilan: dict) -> str:
    return (f'<form class="tugas-form-st" method="post" action="{_e(RUTE_TUGAS)}/{_e(tampilan["order_id"])}">'
            f'<input type="hidden" name="token" value="{_e(tampilan["token"])}">'
            '<label for="topik">Topik latihan</label>'
            f'<select id="topik" name="topik" required>{_opsi_topik(tampilan["opsi_topik"])}</select>'
            '<label for="tenggat">Tenggat (opsional)</label>'
            f'<input id="tenggat" type="date" name="tenggat" min="{_e(tampilan["hari_ini"])}" '
            f'max="{_e(tampilan["tenggat_maks"])}">'
            f'<button class="tugas-tombol-st" type="submit">{_e(COPY_TOMBOL)}</button></form>')


def _bagian_form(tampilan: dict) -> str:
    """Form bila topik tersedia; selain itu hanya teks umum tanpa tombol kirim."""
    opsi = tampilan["opsi_topik"]
    if opsi is None:
        isi = _p(COPY_TOPIK_TIDAK_TERSEDIA, "tugas-meta-st")
    elif not opsi:
        isi = _p(COPY_TOPIK_KOSONG, "tugas-meta-st")
    else:
        isi = _form(tampilan)
    return ('<section class="tugas-kartu-st" aria-label="Tugas baru">'
            f"<h2>Tugas baru</h2>{isi}</section>")


def halaman_anak(ident, tampilan: dict) -> bytes:
    """Form tugas baru dan daftar tugas guru ini untuk satu anak."""
    isi = ('<main aria-labelledby="judul-tugas" class="tugas-st">'
           '<header><p class="tugas-alis-st">RUANG GURU</p>'
           f'<h1 id="judul-tugas">Tugas untuk {_e(tampilan["nama"])}</h1>'
           '<p class="tugas-meta-st">Tugas latihan untuk anak yang Anda ajar. '
           "Hasil hanya tampil setelah anak mengirim latihan.</p></header>"
           f'{_bagian_form(tampilan)}{_bagian_tugas(tampilan["tugas"])}'
           f'<p><a class="tugas-tautan-st" href="{RUTE_TUGAS}">{_e(COPY_KEMBALI_DAFTAR)}</a></p></main>')
    return _halaman_stitch("Tugas untuk anak", GAYA + isi, ident=ident, kelas_bungkus=KELAS_BUNGKUS, privat=True)


def _baris_anak(anak: dict) -> str:
    return (f'<li><a class="tugas-tautan-st" href="{_e(RUTE_TUGAS)}/{_e(anak["order_id"])}">'
            f"{_e(anak['nama'])}</a></li>")


def _daftar_anak(anak: List[dict]) -> str:
    if not anak:
        return _p(COPY_TANPA_ANAK, "tugas-meta-st")
    return '<ul class="tugas-daftar-st">' + "".join(_baris_anak(a) for a in anak) + "</ul>"


def halaman_daftar(ident, anak: List[dict]) -> bytes:
    """Daftar anak tertaut ke guru (`nama`, `order_id`). Tiap nama menjadi tautan ke halaman anak."""
    isi = ('<main aria-labelledby="judul-tugas" class="tugas-st">'
           '<header><p class="tugas-alis-st">RUANG GURU</p>'
           '<h1 id="judul-tugas">Tugas untuk anak</h1>'
           "<p>Pilih anak untuk memberi tugas latihan. Hanya anak yang sedang Anda ajar yang tampil.</p></header>"
           '<section class="tugas-kartu-st" aria-label="Daftar anak"><h2>Anak yang Anda ajar</h2>'
           f"{_daftar_anak(anak)}</section>"
           f'<p><a class="tugas-tautan-st" href="{RUTE_JADWAL}">{_e(COPY_KEMBALI_JADWAL)}</a></p></main>')
    return _halaman_stitch("Tugas untuk anak", GAYA + isi, ident=ident, kelas_bungkus=KELAS_BUNGKUS, privat=True)
