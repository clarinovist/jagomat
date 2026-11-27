"""Render halaman guru `Jadwal tetap saya` (usulan jadwal mingguan): murni render, tanpa DB, HTTP, atau berkas.

View-model (`halaman_tetap`): `tidak_terbaca` (True = hanya pesan aman, tanpa data dan tanpa formulir), `aktif` (tuple
blok atau None), `menunggu` (tuple blok atau None), `ditolak` (bool), `pilihan` (tuple blok untuk isian awal formulir),
`token` (None = tanpa formulir), dan `tersimpan` (bool). Blok = tuple (hari, mulai, selesai) menit WIB yang sudah
divalidasi pemanggil lewat `guru_jadwal_tetap_aturan`.

Tanpa id akun, id usulan, atau data anak di HTML. Semua nilai di-escape. Tanpa JS. Formulir memuat tepat
`KUNCI_FORM` (28 select) dan tiap select punya opsi kosong "tidak ada" supaya setiap kunci selalu terkirim.
"""
from __future__ import annotations

import html
from typing import Optional, Sequence

import design_tokens as T
import guru_jadwal_tetap_aturan as aturan
from teacher_shell import _halaman_stitch

RUTE = "/guru/jadwal-tetap"
RUTE_JADWAL = "/guru/jadwal"
KELAS_BUNGKUS = "jadwal-tetap-guru-st"
COPY_ALIS = "RUANG GURU"
COPY_JUDUL = "Jadwal tetap saya"
COPY_PENGANTAR = ("Jadwal tetap adalah jam mengajar mingguan Anda. Anda mengusulkan jadwal, "
                  "dan admin yang menetapkannya.")
COPY_BELUM_ADA = "Belum ada jadwal tetap."
COPY_AKTIF_KOSONG = "Jadwal tetap dikosongkan: tidak ada jam mengajar tetap."
COPY_MENUNGGU = "Menunggu penetapan admin"
COPY_USULAN_KOSONG = "Usulan ini kosong: tidak ada jam mengajar."
COPY_DITOLAK = "Usulan terakhir ditolak admin."
COPY_TIDAK_TERBACA = "Jadwal tetap belum bisa dibaca sekarang. Muat ulang halaman nanti."
COPY_TERSIMPAN = "Usulan jadwal sudah diterima."
COPY_FORM_JUDUL = "Usulkan jadwal"
COPY_FORM_PETUNJUK = ("Isi jam mulai dan selesai tiap blok. Jam dalam kelipatan 30 menit, minimal 60 menit. "
                      "Kosongkan blok yang tidak dipakai.")
COPY_TIDAK_ADA = "tidak ada"
COPY_TOMBOL = "Kirim usulan"
COPY_KEMBALI = "Kembali ke Jadwal saya"

GAYA = f"""<style>
.jt-st {{ display: grid; gap: {T.SP_4}; }}
.jt-st h1 {{ margin: 0 0 {T.SP_2}; }}
.jt-alis-st {{ color: {T.TEKS_SUBTLE}; font-size: {T.UKURAN_TEKS_LABEL}; letter-spacing: .04em; margin: 0; }}
.jt-meta-st {{ color: {T.TEKS_SUBTLE}; font-size: {T.UKURAN_TEKS_LABEL}; margin: 0; }}
.jt-kartu-st {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_4}; display: grid; gap: {T.SP_3}; }}
.jt-kartu-st h2 {{ margin: 0; font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.jt-daftar-st {{ list-style: none; margin: 0; padding: 0; display: grid; gap: {T.SP_2}; }}
.jt-form-st {{ display: grid; gap: {T.SP_3}; margin: 0; }}
.jt-hari-st {{ border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL};
  padding: {T.SP_3}; display: grid; gap: {T.SP_2}; margin: 0; }}
.jt-hari-st legend {{ font-weight: 600; padding: 0 {T.SP_2}; }}
.jt-blok-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; align-items: center; }}
.jt-form-st label {{ color: {T.TEKS_SUBTLE}; font-size: {T.UKURAN_TEKS_LABEL}; }}
.jt-form-st select {{ padding: {T.SP_2}; border: {T.TEBAL_GARIS} solid {T.BORDER_INTERAKTIF};
  border-radius: {T.RADIUS_KECIL}; font: inherit; max-width: 100%; }}
.jt-tombol-st {{ background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; border: 0;
  border-radius: {T.RADIUS_KECIL}; padding: {T.SP_3} {T.SP_5}; font: inherit; font-weight: 600;
  cursor: pointer; justify-self: start; }}
.jt-tautan-st {{ color: {T.AKSEN_TEAL_TUA}; }}
.jt-st :focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
</style>"""


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _p(teks: str, kelas: str = "") -> str:
    atribut = f' class="{kelas}"' if kelas else ""
    return f"<p{atribut}>{_e(teks)}</p>"


def _nama_hari(hari: int) -> str:
    return aturan.NAMA_HARI[hari - 1]


def _nama_field(hari: int, slot: str, ujung: str) -> str:
    """Nama field formulir. Harus sama dengan `aturan.KUNCI_FORM`; tes formulir menjaga kontrak ini."""
    return f"h{hari}{slot}_{ujung}"


def label_blok(blok: tuple) -> str:
    """Satu blok sebagai teks, misalnya 'Senin 08.00-10.00 WIB'."""
    hari, mulai, selesai = blok
    return f"{_nama_hari(hari)} {aturan.label_menit(mulai)}-{aturan.label_menit(selesai)} WIB"


def _daftar_blok(blok: Sequence[tuple]) -> str:
    return '<ul class="jt-daftar-st">' + "".join(f"<li>{_e(label_blok(b))}</li>" for b in blok) + "</ul>"


def _isi_aktif(aktif) -> str:
    """None = belum pernah ada jadwal; tuple kosong = jadwal aktif yang sengaja dikosongkan (nol blok)."""
    if aktif is None:
        return _p(COPY_BELUM_ADA, "jt-meta-st")
    if not aktif:
        return _p(COPY_AKTIF_KOSONG, "jt-meta-st")
    return _daftar_blok(aktif)


def _bagian_aktif(aktif) -> str:
    isi = _isi_aktif(aktif)
    return ('<section class="jt-kartu-st" aria-label="Jadwal tetap saat ini">'
            f"<h2>Jadwal tetap saat ini</h2>{isi}</section>")


def _isi_usulan(menunggu) -> str:
    if menunggu is None:
        return ""
    if not menunggu:
        return _p(COPY_MENUNGGU, "jt-meta-st") + _p(COPY_USULAN_KOSONG, "jt-meta-st")
    return _p(COPY_MENUNGGU, "jt-meta-st") + _daftar_blok(menunggu)


def _bagian_status(menunggu, ditolak: bool) -> str:
    if menunggu is not None:
        isi = _isi_usulan(menunggu)
    elif ditolak:
        isi = _p(COPY_DITOLAK, "jt-meta-st")
    else:
        return ""
    return ('<section class="jt-kartu-st" aria-label="Usulan jadwal">'
            f"<h2>Usulan Anda</h2>{isi}</section>")


def _opsi(menit: int, terpilih: Optional[int]) -> str:
    tanda = " selected" if menit == terpilih else ""
    return f'<option value="{menit}"{tanda}>{aturan.label_menit(menit)}</option>'


def _select(nama: str, label: str, opsi: Sequence[int], terpilih: Optional[int]) -> str:
    isi = [f'<option value="">{COPY_TIDAK_ADA}</option>'] + [_opsi(menit, terpilih) for menit in opsi]
    return (f'<label for="{nama}">{_e(label)}</label>'
            f'<select id="{nama}" name="{nama}">{"".join(isi)}</select>')


def _blok_form(hari: int, nomor: int, slot: str, blok: Optional[tuple]) -> str:
    mulai, selesai = (None, None) if blok is None else (blok[1], blok[2])
    awal = f"{_nama_hari(hari)} blok {nomor}"
    return ('<div class="jt-blok-st">'
            + _select(_nama_field(hari, slot, "m"), f"{awal} mulai", aturan.opsi_mulai(), mulai)
            + _select(_nama_field(hari, slot, "s"), f"{awal} selesai", aturan.opsi_selesai(), selesai)
            + "</div>")


def _hari_form(hari: int, pilihan: Sequence[tuple]) -> str:
    """Satu hari: dua blok. Blok pertama mengisi slot `a`, blok kedua slot `b`, sesuai urutan kanonik."""
    blok_hari = [blok for blok in pilihan if blok[0] == hari]
    per_slot = dict(zip(aturan.SLOT_FORM, blok_hari))
    blok_html = "".join(
        _blok_form(hari, nomor, slot, per_slot.get(slot))
        for nomor, slot in enumerate(aturan.SLOT_FORM, start=1)
    )
    return f'<fieldset class="jt-hari-st"><legend>{_e(_nama_hari(hari))}</legend>{blok_html}</fieldset>'


def _bagian_form(token: Optional[str], pilihan: Sequence[tuple]) -> str:
    if token is None:
        return ""
    hari_html = "".join(_hari_form(hari, pilihan) for hari in range(aturan.HARI_MIN, aturan.HARI_MAKS + 1))
    return ('<section class="jt-kartu-st" aria-label="Usulkan jadwal">'
            f"<h2>{_e(COPY_FORM_JUDUL)}</h2>{_p(COPY_FORM_PETUNJUK, 'jt-meta-st')}"
            f'<form class="jt-form-st" method="post" action="{RUTE}">'
            f'<input type="hidden" name="token" value="{_e(token)}">'
            f"{hari_html}"
            f'<button class="jt-tombol-st" type="submit">{_e(COPY_TOMBOL)}</button></form></section>')


def _kabar_tersimpan(tersimpan: bool) -> str:
    if not tersimpan:
        return ""
    return f'<p class="jt-meta-st" role="status">{_e(COPY_TERSIMPAN)}</p>'


def _isi_utama(tampilan: dict) -> str:
    if tampilan["tidak_terbaca"]:
        return ('<section class="jt-kartu-st" aria-label="Galat baca">'
                f"{_p(COPY_TIDAK_TERBACA, 'jt-meta-st')}</section>")
    return (_bagian_aktif(tampilan["aktif"])
            + _bagian_status(tampilan["menunggu"], tampilan["ditolak"])
            + _bagian_form(tampilan["token"], tampilan["pilihan"]))


def halaman_tetap(ident, tampilan: dict) -> bytes:
    """Jadwal tetap aktif, usulan menunggu atau ditolak, dan formulir usulan (lihat docstring modul)."""
    isi = ('<main aria-labelledby="judul-jadwal-tetap" class="jt-st">'
           f'<header><p class="jt-alis-st">{_e(COPY_ALIS)}</p>'
           f'<h1 id="judul-jadwal-tetap">{_e(COPY_JUDUL)}</h1>'
           f"<p>{_e(COPY_PENGANTAR)}</p></header>"
           f"{_kabar_tersimpan(tampilan['tersimpan'])}"
           f"{_isi_utama(tampilan)}"
           f'<p><a class="jt-tautan-st" href="{RUTE_JADWAL}">{_e(COPY_KEMBALI)}</a></p></main>')
    return _halaman_stitch(COPY_JUDUL, GAYA + isi, ident=ident, kelas_bungkus=KELAS_BUNGKUS, privat=True)
