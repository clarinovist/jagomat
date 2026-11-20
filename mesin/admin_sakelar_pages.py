"""Renderer murni halaman admin sakelar fitur (tanpa I/O, tanpa JS baru).

Tiap sakelar satu kartu: label, status efektif, sumber, revisi, dampak, dan satu form tombol. Form hanya
membawa csrf, tinjauan, dan sandi ulang; nama, target, dan revisi hidup di tinjauan bertanda tangan, bukan
di field. Prasyarat yang belum terpenuhi hanya ditampilkan di sini sebagai kenyamanan; penegakannya di server.
Semua nilai dinamis di-escape.
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence, Tuple

from admin_komponen import e
from feature_switch import Sakelar
import sakelar_registry

RUTE = "/admin/sakelar"
JUDUL = "Sakelar fitur"
SUBJUDUL = "Empat sakelar fitur yang dapat diubah admin tanpa deploy. Nilai admin menang atas env."
AKSI_UBAH = "ubah_sakelar"

COPY_HASIL = {
    "tersimpan": "Sakelar tersimpan. Perubahan berlaku dalam beberapa detik.",
    "pendaftaran_tersimpan": "Pengaturan pendaftaran mandiri tersimpan.",
}
KODE_HASIL = frozenset(COPY_HASIL)
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk mengubah sakelar."
COPY_CATATAN = (
    "Perubahan pertama menyimpan nilai env saat ini untuk keempat sakelar; sesudah itu nilai admin menang "
    "atas env dan mengubah env tidak lagi berpengaruh."
)
COPY_TIDAK_SIAP = (
    "Database sakelar tidak dapat dibaca atau skemanya tidak dikenali di server ini. Tidak ada yang diubah. "
    "Operator perlu memeriksa berkas sakelar sebelum sakelar bisa dilihat atau diubah."
)
COPY_GALAT_KONFLIK = (
    "Sakelar sudah diubah sejak halaman ini dibuka. Buka ulang halaman sakelar, periksa nilai terbaru, "
    "lalu coba lagi. Tidak ada yang diubah."
)
COPY_GALAT_ISIAN = "Permintaan ubah sakelar tidak sah. Tidak ada yang diubah."
COPY_PRASYARAT = "Sakelar belum bisa dinyalakan karena prasyarat belum terpenuhi. Tidak ada yang diubah."
LABEL_SUMBER = {"db": "Admin (DB)", "env": "Env (belum diatur admin)"}

Token = Tuple[str, str]


def _hidden(csrf: str, tinjauan: str) -> str:
    return ('<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            % (e(csrf), e(tinjauan)))


def _form(sakelar: Sakelar, token: Token) -> str:
    teks = "Matikan" if sakelar.aktif else "Nyalakan"
    return (
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s">%s'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required '
        'autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">%s</button></form>' % (RUTE, _hidden(*token), teks))


def _tombol_terkunci() -> str:
    return '<button class="admin-tombol" type="button" disabled>Nyalakan</button>'


def _prasyarat(belum: Sequence[str]) -> str:
    daftar = "".join("<li>%s</li>" % e(teks) for teks in belum)
    return '<p class="admin-meta">Prasyarat belum terpenuhi:</p><ul class="admin-meta">%s</ul>' % daftar


def _tindakan(sakelar: Sakelar, tokens: Optional[Mapping[str, Token]], belum: Sequence[str]) -> str:
    if tokens is None:
        return ""
    if sakelar.nama in tokens:
        return _form(sakelar, tokens[sakelar.nama])
    return _tombol_terkunci() + (_prasyarat(belum) if belum else "")


def _kartu(sakelar: Sakelar, tokens: Optional[Mapping[str, Token]], prasyarat: Mapping[str, Sequence[str]]) -> str:
    info = sakelar_registry.info(sakelar.nama)
    belum = () if sakelar.aktif else tuple(prasyarat.get(sakelar.nama, ()))
    return (
        '<section class="admin-kartu"><h2>%s</h2>'
        '<p><strong>%s</strong> <span class="admin-meta">Sumber: %s. Revisi %d.</span></p>'
        '<p>%s</p>%s</section>'
        % (e(info.label), "Aktif" if sakelar.aktif else "Mati", e(LABEL_SUMBER.get(sakelar.sumber, sakelar.sumber)),
           sakelar.revisi, e(info.dampak), _tindakan(sakelar, tokens, belum)))


def _umpan_balik(hasil: Optional[str]) -> str:
    if hasil not in COPY_HASIL:
        return ""
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_HASIL[hasil])


def halaman(daftar: Sequence[Sakelar], tokens: Optional[Mapping[str, Token]], *,
            prasyarat: Optional[Mapping[str, Sequence[str]]] = None, hasil: Optional[str] = None) -> str:
    """Isi section sakelar. `tokens` = {nama: (csrf, tinjauan)} untuk baris yang boleh diubah, atau None
    (baca-saja, tanpa form); baris tanpa token memakai tombol nonaktif dan menampilkan `prasyarat`."""
    sisa = {} if prasyarat is None else prasyarat
    catatan = e(COPY_TANPA_SESI) if tokens is None else e(COPY_CATATAN)
    return (_umpan_balik(hasil) + '<p class="admin-meta">%s</p>' % catatan
            + "".join(_kartu(s, tokens, sisa) for s in daftar))


def halaman_galat() -> str:
    return ('<section class="admin-kartu admin-galat" role="alert"><h2>Belum siap</h2><p>%s</p></section>'
            % e(COPY_TIDAK_SIAP))


COPY_PENDAFTARAN_GALAT = (
    "Pengaturan pendaftaran mandiri belum bisa dibaca di server ini. Tidak ada yang diubah. "
    "Operator perlu memeriksa penyimpanan admin."
)


def halaman_pendaftaran_galat() -> str:
    return ('<section class="admin-kartu admin-galat" id="pendaftaran" role="alert"><h2>Pendaftaran mandiri: belum siap</h2>'
            '<p>%s</p></section>' % e(COPY_PENDAFTARAN_GALAT))


def halaman_pendaftaran_baca(dibuka: bool) -> str:
    """Sesi tanpa kuki (baca-saja): status saja, tanpa form."""
    return ('<section class="admin-kartu" id="pendaftaran"><h2>Pendaftaran mandiri: %s</h2>'
            '<p class="admin-meta">%s</p></section>' % ("dibuka" if dibuka else "ditutup", e(COPY_TANPA_SESI)))
