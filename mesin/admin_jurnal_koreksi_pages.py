"""Render halaman koreksi admin atas kehadiran dan jurnal pertemuan (2b). Murni render: tanpa I/O.

View-model disusun `admin_jurnal_koreksi_http`: `judul`, `ke`, `mulai`, `menit`, `keterangan` (kode alasan dari
`guru_pertemuan_aturan` atau None), `anggota` (`nama`, `handle`, `status_terkini`), `topik_terkini`, `opsi_topik`
(pasangan (id, label)), `riwayat` (hasil `admin_jurnal_koreksi_baca.susun_riwayat`), `aksi_form` dan `token`
(None = baca-saja), dan `pesan` (banner dari kode tetap). Tanpa order_id, siswa_id, atau id akun. Semua nilai dinamis
di-escape; waktu tampil WIB. Form native tanpa JS; status selalu berupa teks.
"""
from __future__ import annotations

import html
from typing import Mapping, Optional

import guru_pertemuan_aturan as aturan
from pesanan_transfer_pages import waktu_wib

RUTE = "/admin/jadwal/jurnal"
PERAN_ADMIN = "admin"
JUDUL = "Koreksi kehadiran dan jurnal"
SUBJUDUL = "Koreksi pertemuan yang sudah mulai. Setiap koreksi tercatat atas nama admin di riwayat."
LABEL_STATUS = {"hadir": "Hadir", "izin": "Izin", "tidak_hadir": "Tidak hadir"}
LABEL_TOPIK = "Topik pertemuan"
COPY_TOPIK_KOSONG = "Pilih topik"
COPY_BELUM_DICATAT = "Belum dicatat"
COPY_BELUM_ANAK = "Belum ada anak di pertemuan ini. Koreksi hanya mengubah topik."
COPY_BACA_SAJA = "Tampilan baca-saja. Masuk melalui formulir pengelola untuk mengoreksi."
COPY_TOMBOL = "Simpan koreksi"
COPY_TERSIMPAN = "Koreksi tersimpan."
COPY_KETERANGAN = {
    aturan.ALASAN_DIBATALKAN: "Pertemuan ini dibatalkan, jadi tidak ada yang bisa dikoreksi.",
    aturan.ALASAN_BELUM_MULAI: "Pertemuan belum dimulai. Kehadiran dan jurnal bisa dikoreksi setelah pertemuan mulai.",
}
JUDUL_KEADAAN = "Keadaan terkini"
JUDUL_RIWAYAT = "Riwayat"
COPY_RIWAYAT_KOSONG = "Belum ada riwayat untuk pertemuan ini."
COPY_KOREKSI_ADMIN = "Koreksi admin"
COPY_CATATAN_GURU = "Catatan guru: "
COPY_KEMBALI = "Kembali ke jurnal pertemuan"
COPY_TIDAK_SIAP = "Jurnal pertemuan belum bisa dibaca di server. Coba lagi beberapa saat."


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _label_status(status: Optional[str]) -> str:
    return LABEL_STATUS.get(status, COPY_BELUM_DICATAT)


def _label_topik(view: Mapping) -> str:
    return dict(view["opsi_topik"]).get(view["topik_terkini"], COPY_BELUM_DICATAT)


def _banner(pesan: Optional[str]) -> str:
    if not pesan:
        return ""
    return f'<p class="admin-ket" role="status">{_e(pesan)}</p>'


def _kepala(view: Mapping) -> str:
    return ('<section class="admin-kartu">'
            f'<h2>{_e(view["judul"])}</h2>'
            f'<p class="admin-meta">Pertemuan {int(view["ke"])} · {_e(waktu_wib(view["mulai"]))}'
            f' · {int(view["menit"])} menit</p>'
            f'{_banner(view["pesan"])}</section>')


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
        radio.append(f'<label><input type="radio" name="anak_{_e(handle)}" value="{_e(nilai)}" required{centang}>'
                     f' {_e(LABEL_STATUS[nilai])}</label>')
    return "".join(radio)


def _fieldset_anak(anak: Mapping) -> str:
    return (f'<fieldset><legend>{_e(anak["nama"])}</legend>'
            f'{_pilihan_status(anak["handle"], anak["status_terkini"])}</fieldset>')


def _form(view: Mapping) -> str:
    anak = "".join(_fieldset_anak(a) for a in view["anggota"])
    return (f'<form method="post" action="{_e(view["aksi_form"])}">'
            f'<input type="hidden" name="token" value="{_e(view["token"])}">'
            f'<label for="topik">{_e(LABEL_TOPIK)}</label>'
            f'<select id="topik" name="topik" required>'
            f'{_opsi_topik(view["opsi_topik"], view["topik_terkini"])}</select>'
            f'{anak}'
            f'<button class="admin-tombol" type="submit">{_e(COPY_TOMBOL)}</button></form>')


def _baca_saja(view: Mapping) -> str:
    baris = "".join(f"<li>{_e(a['nama'])} · Status: {_e(_label_status(a['status_terkini']))}</li>"
                    for a in view["anggota"])
    return f"<ul>{baris}</ul>" if baris else ""


def _isi_kartu_koreksi(view: Mapping) -> str:
    """Form bila boleh diisi; selain itu penjelasan dan daftar anak baca-saja."""
    if view["aksi_form"] is not None:
        teks = "" if view["anggota"] else f'<p class="admin-ket">{_e(COPY_BELUM_ANAK)}</p>'
        return teks + _form(view)
    alasan = COPY_KETERANGAN.get(view["keterangan"], COPY_BACA_SAJA)
    return f'<p class="admin-ket">{_e(alasan)}</p>' + _baca_saja(view)


def _kartu_koreksi(view: Mapping) -> str:
    return ('<section class="admin-kartu">'
            f'<h2>{_e(JUDUL_KEADAAN)}</h2>'
            f'<p class="admin-meta">Topik terkini: {_e(_label_topik(view))}</p>'
            f'{_isi_kartu_koreksi(view)}</section>')


def _judul_entri(entri: Mapping) -> str:
    if entri["peran"] == PERAN_ADMIN:
        return COPY_KOREKSI_ADMIN
    return COPY_CATATAN_GURU + entri["pelaku"]


def _entri_riwayat(entri: Mapping) -> str:
    perubahan = "".join(f"<li>{_e(baris)}</li>" for baris in entri["perubahan"])
    return (f'<li><p><strong>{_e(_judul_entri(entri))}</strong> · {_e(waktu_wib(entri["pada"]))}</p>'
            f'<ul>{perubahan}</ul></li>')


def _kartu_riwayat(view: Mapping) -> str:
    if not view["riwayat"]:
        badan = f'<p class="admin-kosong">{_e(COPY_RIWAYAT_KOSONG)}</p>'
    else:
        badan = "<ol>" + "".join(_entri_riwayat(e) for e in view["riwayat"]) + "</ol>"
    return f'<section class="admin-kartu"><h2>{_e(JUDUL_RIWAYAT)}</h2>{badan}</section>'


def halaman(view: Mapping) -> str:
    """Isi halaman (tanpa shell admin): kepala, keadaan dan formulir, riwayat, lalu tautan kembali."""
    return "".join([
        _kepala(view),
        _kartu_koreksi(view),
        _kartu_riwayat(view),
        f'<p><a class="admin-tautan" href="{_e(RUTE)}">{_e(COPY_KEMBALI)}</a></p>',
    ])


def halaman_tidak_siap() -> str:
    return f'<section class="admin-kartu"><h2>{_e(JUDUL)}</h2><p>{_e(COPY_TIDAK_SIAP)}</p></section>'
