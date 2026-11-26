"""Render halaman catat kehadiran & jurnal pertemuan guru (Fase 2a-2): murni render, tanpa DB, HTTP, atau berkas.

View-model tanpa id internal: `judul`, `ke`, `mulai`, `menit`, `anggota` (`nama`, `handle`, `status_terkini`,
`akses_habis`), `topik_terkini`, `opsi_topik` (pasangan (id, label)), `aksi_form` dan `token` (None = halaman
baca-saja), `pesan` (banner, mis. tersimpan), dan `keterangan` (alasan baca-saja). Semua nilai di-escape; waktu
tampil WIB lewat `waktu_wib`. Form native tanpa JS; status selalu berupa teks, bukan hanya warna.
"""
from __future__ import annotations

import html
from typing import Optional

import design_tokens as T
import guru_pertemuan_aturan as aturan
from pesanan_transfer_pages import waktu_wib
from teacher_shell import _halaman_stitch

KELAS_BUNGKUS = "pertemuan-guru-st"
RUTE_JADWAL = "/guru/jadwal"
LABEL_STATUS = {"hadir": "Hadir", "izin": "Izin", "tidak_hadir": "Tidak hadir"}
COPY_TOPIK_KOSONG = "Pilih topik"
COPY_BELUM_DICATAT = "Belum dicatat"
COPY_AKSES_HABIS = "Akses habis"
COPY_TOMBOL = "Simpan"
COPY_KEMBALI = "Kembali ke Jadwal saya"

GAYA = f"""<style>
.pertemuan-st {{ display: grid; gap: {T.SP_4}; }}
.pertemuan-st h1 {{ margin: 0 0 {T.SP_2}; }}
.pertemuan-alis-st {{ color: {T.TEKS_SUBTLE}; font-size: {T.UKURAN_TEKS_LABEL}; letter-spacing: .04em; margin: 0; }}
.pertemuan-meta-st {{ color: {T.TEKS_SUBTLE}; font-size: {T.UKURAN_TEKS_LABEL}; margin: 0; }}
.pertemuan-kartu-st {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_4}; display: grid; gap: {T.SP_3}; }}
.pertemuan-kartu-st h2 {{ margin: 0; font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.pertemuan-banner-st {{ background: {T.LATAR_TERSIMPAN}; color: {T.TEKS_TERSIMPAN};
  border: {T.TEBAL_GARIS} solid {T.BORDER_TERSIMPAN}; border-radius: {T.RADIUS_KECIL}; padding: {T.SP_3}; margin: 0; }}
.pertemuan-form-st {{ display: grid; gap: {T.SP_4}; margin: 0; }}
.pertemuan-form-st select {{ padding: {T.SP_2}; border: {T.TEBAL_GARIS} solid {T.BORDER_INTERAKTIF};
  border-radius: {T.RADIUS_KECIL}; font: inherit; max-width: 100%; }}
.pertemuan-anak-st {{ border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL};
  padding: {T.SP_3}; display: grid; gap: {T.SP_2}; margin: 0; }}
.pertemuan-anak-st legend {{ font-weight: 600; padding: 0 {T.SP_1}; }}
.pertemuan-pilihan-st {{ display: inline-flex; gap: {T.SP_2}; align-items: center; margin-right: {T.SP_3}; }}
.pertemuan-daftar-st {{ margin: 0; padding-left: {T.SP_5}; }}
.pertemuan-tombol-st {{ background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; border: 0;
  border-radius: {T.RADIUS_KECIL}; padding: {T.SP_3} {T.SP_5}; font: inherit; font-weight: 600;
  cursor: pointer; justify-self: start; }}
.pertemuan-tautan-st {{ color: {T.AKSEN_TEAL_TUA}; }}
.pertemuan-st :focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
</style>"""


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _label_status(status: Optional[str]) -> str:
    return LABEL_STATUS.get(status, COPY_BELUM_DICATAT)


def _label_topik(tampilan: dict) -> str:
    """Label topik terkini dari opsi yang sudah diturunkan server; None atau tak dikenal = belum dicatat."""
    return dict(tampilan["opsi_topik"]).get(tampilan["topik_terkini"], COPY_BELUM_DICATAT)


def _tanda_akses(anak: dict) -> str:
    """Teks 'Akses habis' bila masa akses lewat, supaya status tidak hanya tampil lewat warna."""
    return (" · " + COPY_AKSES_HABIS) if anak["akses_habis"] else ""


def _banner(pesan: Optional[str]) -> str:
    if not pesan:
        return ""
    return f'<p class="pertemuan-banner-st" role="status">{_e(pesan)}</p>'


def _opsi_topik(opsi, terpilih: Optional[str]) -> str:
    kosong = " selected" if terpilih is None else ""
    baris = [f'<option value="" disabled{kosong}>{_e(COPY_TOPIK_KOSONG)}</option>']
    for id_topik, label in opsi:
        pilih = " selected" if id_topik == terpilih else ""
        baris.append(f'<option value="{_e(id_topik)}"{pilih}>{_e(label)}</option>')
    return "".join(baris)


def _pilihan_status(handle: str, terpilih: Optional[str]) -> str:
    """Tiga radio wajib per anak; label berupa teks, nilai tetap dari aturan."""
    radio = []
    for nilai in aturan.STATUS_KEHADIRAN:
        centang = " checked" if nilai == terpilih else ""
        radio.append(
            f'<label class="pertemuan-pilihan-st"><input type="radio" name="anak_{_e(handle)}" '
            f'value="{_e(nilai)}" required{centang}> {_e(LABEL_STATUS[nilai])}</label>'
        )
    return "".join(radio)


def _fieldset_anak(anak: dict) -> str:
    return (f'<fieldset class="pertemuan-anak-st"><legend>{_e(anak["nama"])}{_e(_tanda_akses(anak))}</legend>'
            f'{_pilihan_status(anak["handle"], anak["status_terkini"])}</fieldset>')


def _form(tampilan: dict) -> str:
    anak = "".join(_fieldset_anak(a) for a in tampilan["anggota"])
    return (f'<form class="pertemuan-form-st" method="post" action="{_e(tampilan["aksi_form"])}">'
            f'<input type="hidden" name="token" value="{_e(tampilan["token"])}">'
            '<label for="topik">Topik pertemuan</label>'
            f'<select id="topik" name="topik" required>{_opsi_topik(tampilan["opsi_topik"], tampilan["topik_terkini"])}'
            "</select>"
            f"{anak}"
            f'<button class="pertemuan-tombol-st" type="submit">{_e(COPY_TOMBOL)}</button></form>')


def _badan_form(tampilan: dict) -> str:
    return ('<section class="pertemuan-kartu-st" aria-label="Catat kehadiran dan jurnal">'
            "<h2>Catat kehadiran dan jurnal</h2>"
            f'<p class="pertemuan-meta-st">Terakhir dicatat: {_e(_label_topik(tampilan))}</p>'
            f"{_form(tampilan)}</section>")


def _baris_baca_saja(anak: dict) -> str:
    return f"<li>{_e(anak['nama'])}{_e(_tanda_akses(anak))} · Status: {_e(_label_status(anak['status_terkini']))}</li>"


def _badan_baca_saja(tampilan: dict) -> str:
    baris = "".join(_baris_baca_saja(a) for a in tampilan["anggota"])
    daftar = f'<ul class="pertemuan-daftar-st">{baris}</ul>' if baris else ""
    return ('<section class="pertemuan-kartu-st" aria-label="Keadaan pertemuan">'
            "<h2>Hanya dibaca</h2>"
            f'<p class="pertemuan-meta-st">{_e(tampilan["keterangan"])}</p>'
            f'<p class="pertemuan-meta-st">Topik: {_e(_label_topik(tampilan))}</p>{daftar}</section>')


def halaman_pertemuan(ident, tampilan: dict) -> bytes:
    """Halaman form bila `aksi_form` ada; selain itu halaman baca-saja tanpa form dan tanpa token."""
    badan = _badan_form(tampilan) if tampilan["aksi_form"] is not None else _badan_baca_saja(tampilan)
    isi = ('<main aria-labelledby="judul-pertemuan" class="pertemuan-st">'
           '<header><p class="pertemuan-alis-st">RUANG GURU</p>'
           f'<h1 id="judul-pertemuan">{_e(tampilan["judul"])}</h1>'
           f'<p class="pertemuan-meta-st">Pertemuan {int(tampilan["ke"])} · {_e(waktu_wib(tampilan["mulai"]))}'
           f' · {int(tampilan["menit"])} menit</p></header>'
           f'{_banner(tampilan["pesan"])}{badan}'
           f'<p><a class="pertemuan-tautan-st" href="{RUTE_JADWAL}">{_e(COPY_KEMBALI)}</a></p></main>')
    return _halaman_stitch("Catat pertemuan", GAYA + isi, ident=ident, kelas_bungkus=KELAS_BUNGKUS, privat=True)
