"""Renderer HTML murni halaman admin "Ubah pemetaan CP" satu grup (tanpa JS, tanpa DB, tanpa I/O).

Form edit memuat 12 baris tetap (`butir_N` + `cocok_N`); baris dengan butir kosong dilewati saat simpan.
Form hanya membawa csrf, tinjauan, sandi ulang, dan isian baris: grup target dan revisi hidup di tinjauan
bertanda tangan, bukan di field. Semua nilai dinamis di-escape.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional, Sequence, Tuple

import admin_kurikulum_pages as peta_ui
from admin_komponen import e
from admin_kurikulum_tab import TAB_DETAIL_CP, tab_kurikulum
import kurikulum_cp as cp
from kurikulum_override import MAKS_PASANGAN_CP, SUMBER_ADMIN, ItemCP, RiwayatCP

RUTE = "/admin/kurikulum/cp"
RUTE_KEMBALIKAN = "/admin/kurikulum/cp/kembalikan"
AKSI_UBAH_CP = "ubah_cp_kurikulum"
AKSI_KEMBALIKAN_CP = "kembalikan_cp_kurikulum"
JUDUL = "Ubah pemetaan CP"
SUBJUDUL = "Butir CP Merdeka yang dilatih satu grup soal. Langsung berlaku, tercatat, dan bisa dikembalikan."
KECOCOKAN_BAWAAN = "sebagian"
MAKS_TEKS_OPSI = 60
FIELD_UBAH = frozenset(
    "%s_%d" % (nama, no) for nama in ("butir", "cocok") for no in range(1, MAKS_PASANGAN_CP + 1))

COPY_HASIL = {
    "tersimpan": "Pemetaan CP tersimpan dan langsung berlaku.",
    "dikembalikan": "Pemetaan CP dikembalikan ke bawaan kode.",
}
KODE_HASIL = frozenset(COPY_HASIL)
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk mengubah pemetaan."
COPY_PETUNJUK = (
    "Pilih sampai %d butir CP yang dilatih grup ini beserta tingkat kecocokannya; biarkan baris yang tak "
    "dipakai kosong. Jika semua baris dikosongkan, grup menjadi di luar CP (pengayaan)." % MAKS_PASANGAN_CP
)
COPY_GALAT_KONFLIK = (
    "Pemetaan grup ini sudah diubah sejak halaman dibuka. Buka ulang halaman ubah, periksa nilai terbaru, "
    "lalu coba lagi. Tidak ada yang diubah."
)
COPY_GALAT_ISIAN = (
    "Isian pemetaan CP tidak sah: butir atau kecocokan tidak dikenal, atau ada butir ganda. "
    "Tidak ada yang diubah."
)
COPY_TIDAK_SIAP = (
    "Database kurikulum tidak dapat diubah atau skemanya tidak dikenali di server ini. "
    "Tidak ada yang diubah. Operator perlu memeriksa berkas kurikulum."
)

Token = Tuple[str, str]


def _hidden(csrf: str, tinjauan: str) -> str:
    return ('<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            % (e(csrf), e(tinjauan)))


def _potong(teks: str) -> str:
    return teks if len(teks) <= MAKS_TEKS_OPSI else teks[:MAKS_TEKS_OPSI - 1].rstrip() + "…"


@lru_cache(maxsize=1)
def _opsi_butir() -> Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...]:
    """((label kelompok, ((id, teks opsi), ...)), ...) per fase dan elemen, urut CAPAIAN."""
    kelompok = []
    for butir in cp.CAPAIAN:
        label = "Fase %s (%s) · %s" % (butir.fase, cp.FASE[butir.fase], cp.ELEMEN[butir.elemen])
        if not kelompok or kelompok[-1][0] != label:
            kelompok.append((label, []))
        kelompok[-1][1].append((butir.id, "%s — %s" % (butir.id, _potong(butir.teks))))
    return tuple((label, tuple(isi)) for label, isi in kelompok)


def _select_butir(no: int, terpilih: str) -> str:
    grup = "".join(
        '<optgroup label="%s">%s</optgroup>' % (e(label), "".join(
            '<option value="%s"%s>%s</option>' % (e(cid), " selected" if cid == terpilih else "", e(teks))
            for cid, teks in isi))
        for label, isi in _opsi_butir())
    return ('<label>Butir CP %d<select name="butir_%d"><option value=""%s>—</option>%s</select></label>'
            % (no, no, " selected" if not terpilih else "", grup))


def _select_cocok(no: int, terpilih: str) -> str:
    opsi = "".join(
        '<option value="%s"%s>%s</option>' % (e(k), " selected" if k == terpilih else "", e(k))
        for k in cp.KECOCOKAN)
    return '<label>Kecocokan %d<select name="cocok_%d">%s</select></label>' % (no, no, opsi)


def _baris_form(no: int, isi: Sequence[Tuple[str, str]]) -> str:
    butir, cocok = isi[no - 1] if no <= len(isi) else ("", KECOCOKAN_BAWAAN)
    return "<li>%s%s</li>" % (_select_butir(no, butir), _select_cocok(no, cocok))


def _form_ubah(item: ItemCP, token: Token) -> str:
    baris = "".join(_baris_form(no, item.efektif) for no in range(1, MAKS_PASANGAN_CP + 1))
    return (
        '<form class="admin-form-bagian" method="post" action="%s">%s'
        '<ul class="kurikulum-daftar" aria-label="Butir CP grup ini">%s</ul>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required '
        'autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Simpan</button></form>' % (RUTE, _hidden(*token), baris))


def _form_kembalikan(token: Token) -> str:
    return (
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s">%s'
        '<p class="admin-meta">Mengembalikan pemetaan grup ini ke nilai bawaan kode. Perubahan admin '
        'sebelumnya tetap tercatat di riwayat.</p>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required '
        'autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Kembalikan ke bawaan</button></form>'
        % (RUTE_KEMBALIKAN, _hidden(*token)))


def _teks_isi(isi: Sequence[Tuple[str, str]]) -> str:
    if not isi:
        return peta_ui.DI_LUAR_CP
    return ", ".join("%s (%s)" % (cid, cocok) for cid, cocok in isi)


def _nilai(judul: str, isi: Sequence[Tuple[str, str]]) -> str:
    daftar = "<br>".join(
        "<code>%s</code> %s <span class=\"admin-meta\">(%s)</span>" % (e(cid), e(cp.butir(cid).teks), e(cocok))
        for cid, cocok in isi) or '<span class="admin-meta">%s</span>' % e(peta_ui.DI_LUAR_CP)
    return "<dt>%s</dt><dd>%s</dd>" % (e(judul), daftar)


def _kepala(item: ItemCP, nama_topik: str, nama_grup: str, pola: Sequence[str]) -> str:
    templat = ", ".join("<code>%s</code>" % e(p) for p in pola) or "-"
    return (
        '<section class="admin-kartu"><h2>%s · %s <code>%s</code></h2>'
        '<p class="admin-meta">Template pola grup: %s</p>'
        '<p class="admin-meta">Sumber: %s.</p>'
        '<dl class="admin-rincian">%s%s</dl></section>' % (
            e(nama_topik), e(nama_grup), e(item.grup_kode), templat, e(peta_ui._sumber_grup(item)),
            _nilai("Bawaan kode", item.bawaan), _nilai("Efektif sekarang", item.efektif)))


def _umpan_balik(hasil: Optional[str]) -> str:
    if hasil not in COPY_HASIL:
        return ""
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_HASIL[hasil])


def _riwayat(daftar: Sequence[RiwayatCP]) -> str:
    if not daftar:
        isi = '<p class="admin-meta">Belum ada perubahan tercatat untuk grup ini.</p>'
    else:
        isi = '<ul class="kurikulum-daftar" aria-label="Riwayat perubahan">%s</ul>' % "".join(
            '<li><p class="kurikulum-kepala">Revisi %d · %s · <code>%s</code></p>'
            '<p class="admin-meta">%s → %s</p></li>' % (
                r.revisi, e(r.dibuat), e(r.actor_id), e(_teks_isi(r.lama)), e(_teks_isi(r.baru)))
            for r in daftar)
    return '<section class="admin-kartu"><h2>Riwayat terakhir</h2>%s</section>' % isi


def _tindakan(item: ItemCP, token_ubah: Optional[Token], token_kembalikan: Optional[Token]) -> str:
    if token_ubah is None:
        return '<section class="admin-kartu"><p class="admin-meta">%s</p></section>' % e(COPY_TANPA_SESI)
    kembalikan = ""
    if item.sumber == SUMBER_ADMIN and token_kembalikan is not None:
        kembalikan = '<section class="admin-kartu"><h2>Kembalikan ke bawaan</h2>%s</section>' % (
            _form_kembalikan(token_kembalikan))
    return (
        '<section class="admin-kartu"><h2>Ubah pemetaan</h2><p class="admin-meta">%s</p>%s</section>%s'
        % (e(COPY_PETUNJUK), _form_ubah(item, token_ubah), kembalikan))


def halaman_edit(item: ItemCP, *, nama_topik: str, nama_grup: str, pola: Sequence[str],
                 riwayat: Sequence[RiwayatCP], token_ubah: Optional[Token],
                 token_kembalikan: Optional[Token], hasil: Optional[str] = None) -> str:
    """Isi halaman ubah satu grup. Token `(csrf, tinjauan)` None = sesi tanpa kuki (baca-saja, tanpa form)."""
    return (
        tab_kurikulum(TAB_DETAIL_CP) + _umpan_balik(hasil)
        + '<p><a href="/admin/kurikulum/cp-detail">&larr; Kembali ke Detail CP</a></p>'
        + _kepala(item, nama_topik, nama_grup, pola)
        + _tindakan(item, token_ubah, token_kembalikan) + _riwayat(riwayat)
    )
