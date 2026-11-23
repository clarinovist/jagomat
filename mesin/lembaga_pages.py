"""Halaman pemilik les `/lembaga`: ringkasan agregat per guru dan form pindah anak.

Hanya agregat (nama anak, jumlah sesi, tanggal sesi terakhir, jumlah menunggu
konfirmasi). Tidak ada jawaban, kode diagnosis, kunci, laporan, atau tautan ke
halaman sesi/anak guru lain. Pesan hanya dari kode tetap, bukan isian pengguna.
"""
from __future__ import annotations

import html
from typing import Sequence

import design_tokens as T
from form_style import GAYA_SELECT
from lembaga_store import BATAS_PINDAH_BANYAK, GuruRingkas
from teacher_shell import _halaman_stitch

PESAN = {
    "pindah_ok": "Anak sudah dipindahkan ke guru tujuan. Bila namanya kembar dengan anak "
                 "guru tujuan, nama diberi nomor, misalnya (2).",
    "bentrok_nama": "Guru tujuan sudah punya terlalu banyak anak dengan nama yang sama, "
                    "sehingga nomor pembeda habis. Ubah salah satu nama dulu, lalu coba lagi.",
    "sesi_berjalan": "Anak masih punya sesi yang sedang berjalan atau belum "
                     "dikonfirmasi. Selesaikan dan konfirmasi dulu sebelum dipindahkan.",
    "sama": "Anak itu sudah dimiliki guru tersebut.",
    "banyak_ok": "{jumlah} anak dipindahkan ke {ke}. Bila ada nama yang kembar dengan anak guru "
                 "tujuan, nama diberi nomor, misalnya (2).",
    "banyak_sama": "{jumlah} anak yang Anda pilih sudah dipegang guru tujuan, jadi tidak ada anak "
                   "yang dipindahkan. Hapus centang anak itu lalu coba lagi.",
    "banyak_sesi": "{jumlah} anak yang Anda pilih masih punya sesi yang sedang berjalan atau belum "
                   "dikonfirmasi, jadi tidak ada anak yang dipindahkan. Selesaikan dan konfirmasi "
                   "sesinya dulu, atau hapus centang anak itu.",
    "banyak_nama": "Guru tujuan sudah punya terlalu banyak anak dengan nama yang sama, sehingga "
                   "nomor pembeda habis. Tidak ada anak yang dipindahkan.",
    "banyak_terlalu": "Terlalu banyak anak dipilih sekaligus (maksimal %d per pindah), jadi tidak ada "
                      "anak yang dipindahkan. Pilih lebih sedikit lalu coba lagi." % BATAS_PINDAH_BANYAK,
}
ID_FORM_BANYAK = "form-pindah-banyak"

GAYA = f"""<style>
.lembaga-st {{ display: grid; gap: {T.SP_4}; }}
.lembaga-guru-st {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_4}; }}
.lembaga-guru-st h2 {{ margin: 0 0 {T.SP_2}; }}
.lembaga-tabel-st {{ width: 100%; border-collapse: collapse; }}
.lembaga-tabel-st th, .lembaga-tabel-st td {{ text-align: left; padding: {T.SP_2};
  border-bottom: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; vertical-align: middle; }}
.lembaga-tabel-st thead th {{ color: {T.TEKS_SUBTLE}; font-weight: 600; }}
.lembaga-pindah-st {{ display: flex; gap: {T.SP_2}; align-items: center; flex-wrap: wrap; }}
.lembaga-pindah-st label {{ display: flex; flex-direction: column; gap: {T.SP_1}; min-width: 0; }}
.lembaga-pindah-st select {{ min-height: {T.TINGGI_KONTROL}; min-width: 10rem; max-width: 100%;
  padding: {T.SP_2} {T.SP_3}; border: {T.TEBAL_GARIS} solid {T.BORDER_KONTROL};
  border-radius: {T.RADIUS_SEDANG}; background-color: {T.LATAR_KARTU}; color: {T.TEKS_UTAMA};
  font: inherit; font-size: {T.UKURAN_BADAN_LAYAR}; }}
.lembaga-pindah-st select:focus-visible {{ outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 2px; }}
.lembaga-pilih-st input {{ width: 1.25rem; height: 1.25rem; }}
.lembaga-meta-st {{ color: {T.TEKS_SUBTLE}; font-size: {T.UKURAN_TEKS_LABEL}; }}
@media (max-width: 560px) {{
  .lembaga-guru-st {{ padding: {T.SP_3}; }}
  .lembaga-tabel-st, .lembaga-tabel-st tbody, .lembaga-tabel-st tr,
  .lembaga-tabel-st th, .lembaga-tabel-st td {{ display: block; width: 100%; box-sizing: border-box; }}
  .lembaga-tabel-st thead {{ position: absolute; width: 1px; height: 1px; overflow: hidden;
    clip: rect(0 0 0 0); white-space: nowrap; }}
  .lembaga-tabel-st tr {{ border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS};
    border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_2}; margin-bottom: {T.SP_3}; }}
  .lembaga-tabel-st th[scope="row"] {{ font-size: {T.UKURAN_BAGIAN_DEWASA}; border-bottom: 0; }}
  .lembaga-tabel-st td {{ display: flex; justify-content: space-between; gap: {T.SP_3}; }}
  .lembaga-tabel-st td[data-label]::before {{ content: attr(data-label); color: {T.TEKS_SUBTLE}; }}
  .lembaga-tabel-st td.lembaga-aksi-st {{ display: block; border-bottom: 0; }}
  .lembaga-pindah-st {{ flex-direction: column; align-items: stretch; }}
  .lembaga-pindah-st select, .lembaga-pindah-st button {{ width: 100%; }}
}}
{GAYA_SELECT}
</style>"""


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _form_pindah(siswa_id: int, nama: str, tujuan: Sequence[str]) -> str:
    if not tujuan:
        return '<span class="lembaga-meta-st">Belum ada guru lain.</span>'
    opsi = "".join(f'<option value="{_e(guru)}">{_e(guru)}</option>' for guru in tujuan)
    return (
        '<form class="lembaga-pindah-st" method="post" action="/lembaga/pindah">'
        f'<input type="hidden" name="siswa_id" value="{int(siswa_id)}">'
        f'<label><span class="lembaga-meta-st">Pindahkan {_e(nama)} ke</span> '
        f'<select name="ke" required>{opsi}</select></label>'
        '<button class="guru-tambah-st" type="submit">Pindahkan</button></form>'
    )


def _sel_pilih(anak, tujuan: Sequence[str]) -> str:
    """Kotak centang native untuk pindah banyak, tertaut ke form di luar tabel (atribut form)."""
    if not tujuan:
        return ""
    return (
        '<td class="lembaga-pilih-st" data-label="Pilih">'
        f'<input type="checkbox" name="siswa_id" value="{int(anak.siswa_id)}" '
        f'form="{ID_FORM_BANYAK}" aria-label="Pilih {_e(anak.nama)}"></td>'
    )


def _form_banyak(semua: Sequence[str]) -> str:
    """Satu form di luar tabel (form tidak boleh bersarang): tujuan + tombol; centang di tiap baris."""
    opsi = "".join(f'<option value="{_e(guru)}">{_e(guru)}</option>' for guru in semua)
    return (
        f'<form class="lembaga-guru-st lembaga-pindah-st" id="{ID_FORM_BANYAK}" method="post" '
        'action="/lembaga/pindah-banyak">'
        '<label><span class="lembaga-meta-st">Pindahkan semua anak yang dicentang di tabel '
        f'(maksimal {BATAS_PINDAH_BANYAK}) ke</span> <select name="ke" required>{opsi}</select></label>'
        '<button class="guru-tambah-st" type="submit">Pindahkan yang dicentang</button></form>'
    )


def _baris_anak(anak, tujuan: Sequence[str]) -> str:
    terakhir = _e(anak.sesi_terakhir) if anak.sesi_terakhir else "&mdash;"
    return (
        f'<tr><th scope="row">{_e(anak.nama)}</th>{_sel_pilih(anak, tujuan)}'
        f'<td data-label="Sesi">{anak.jumlah_sesi}</td>'
        f'<td data-label="Sesi terakhir">{terakhir}</td>'
        f'<td data-label="Menunggu konfirmasi">{anak.menunggu_konfirmasi}</td>'
        f'<td class="lembaga-aksi-st">{_form_pindah(anak.siswa_id, anak.nama, tujuan)}</td></tr>'
    )


def _bagian_guru(guru: GuruRingkas, semua: Sequence[str], pemilik: str) -> str:
    tujuan = [g for g in semua if g != guru.guru]
    label = _e(guru.guru) + (" (pemilik les)" if guru.guru == pemilik else "")
    if guru.anak:
        isi = (
            '<table class="lembaga-tabel-st"><thead><tr>'
            '<th scope="col">Anak</th>' + ('<th scope="col">Pilih</th>' if tujuan else "")
            + '<th scope="col">Sesi</th>'
            '<th scope="col">Sesi terakhir</th><th scope="col">Menunggu konfirmasi</th>'
            '<th scope="col">Pindahkan</th></tr></thead><tbody>'
            + "".join(_baris_anak(a, tujuan) for a in guru.anak)
            + "</tbody></table>"
        )
    else:
        isi = '<p class="lembaga-meta-st">Belum ada anak.</p>'
    return f'<section class="lembaga-guru-st" aria-label="Guru {label}"><h2>{label}</h2>{isi}</section>'


def _teks_pesan(kode_pesan: str, jumlah: int, ke: str) -> str:
    """Teks pesan dari kode tetap; kosong bila kode asing atau parameter yang dibutuhkan tak ada."""
    templat = PESAN.get(kode_pesan, "")
    if ("{jumlah}" in templat and jumlah <= 0) or ("{ke}" in templat and not ke):
        return ""
    return templat.format(jumlah=jumlah, ke=ke)


def halaman(lembaga, ringkas: Sequence[GuruRingkas], kode_pesan: str, ident,
            jumlah: int = 0, ke: str = "") -> bytes:
    semua = [g.guru for g in ringkas]
    pesan = _teks_pesan(kode_pesan, jumlah, ke)
    kabar = (
        '<div class="st-banner-sukses" role="status"><span class="ikon" aria-hidden="true">'
        f"✓</span><span>{_e(pesan)}</span></div>" if pesan else ""
    )
    jumlah_anak = sum(len(g.anak) for g in ringkas)
    isi = (
        GAYA + '<main aria-labelledby="judul-lembaga" class="lembaga-st">'
        '<header class="guru-sapaan-st"><div><p class="guru-alis-st">LEMBAGA LES</p>'
        f'<h1 id="judul-lembaga">{_e(lembaga["nama"])}</h1>'
        f"<p>{len(ringkas)} guru, {jumlah_anak} anak. Halaman ini hanya menampilkan "
        "ringkasan; isi belajar anak tetap dilihat oleh gurunya sendiri.</p></div></header>"
        + kabar
        + (_form_banyak(semua) if len(semua) > 1 and jumlah_anak else "")
        + "".join(_bagian_guru(g, semua, lembaga["pemilik"]) for g in ringkas)
        + '<p><a class="guru-tambah-st" href="/guru">Kembali ke ruang guru</a></p></main>'
    )
    return _halaman_stitch("Lembaga les", isi, ident=ident, kelas_bungkus="guru-beranda-st", privat=True)
