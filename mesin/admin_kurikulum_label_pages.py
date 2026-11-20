"""Renderer HTML murni halaman admin "Ubah label awam" satu topik (tanpa JS, tanpa DB, tanpa I/O).

Label awam adalah teks topik yang dilihat anak dan orang tua. Form hanya membawa csrf, tinjauan, sandi
ulang, dan satu field `label`: topik target dan revisi hidup di tinjauan bertanda tangan, bukan di field.
Semua nilai dinamis di-escape.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple
from urllib.parse import urlencode

from admin_komponen import e
from admin_kurikulum_tab import TAB_DETAIL_CP, tab_kurikulum
from kurikulum_override import MAKS_LABEL, SUMBER_ADMIN, ItemLabel, RiwayatLabel

RUTE = "/admin/kurikulum/label"
RUTE_KEMBALIKAN = "/admin/kurikulum/label/kembalikan"
RUTE_DETAIL_CP = "/admin/kurikulum/cp-detail"
AKSI_UBAH_LABEL = "ubah_label_kurikulum"
AKSI_KEMBALIKAN_LABEL = "kembalikan_label_kurikulum"
JUDUL = "Ubah label awam"
SUBJUDUL = "Nama topik yang dilihat anak dan orang tua. Langsung berlaku, tercatat, dan bisa dikembalikan."
FIELD_UBAH = frozenset({"label"})

COPY_HASIL = {
    "tersimpan": "Label awam tersimpan dan langsung berlaku untuk hasil cek berikutnya.",
    "dikembalikan": "Label awam dikembalikan ke bawaan kode.",
}
KODE_HASIL = frozenset(COPY_HASIL)
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk mengubah label."
COPY_CATATAN_BERLAKU = (
    "Label baru berlaku untuk hasil cek yang dinilai setelah ini; hasil lama tetap memakai label lama. "
    "Layar anak langsung memakai label baru."
)
COPY_PETUNJUK = (
    "Tulis label baru, 1-%d karakter. Label tidak boleh sama dengan label topik lain "
    "(huruf besar-kecil dianggap sama) atau dengan nama resmi sebuah topik." % MAKS_LABEL
)
COPY_GALAT_KONFLIK = (
    "Label topik ini sudah diubah sejak halaman dibuka. Buka ulang halaman ubah, periksa nilai terbaru, "
    "lalu coba lagi. Tidak ada yang diubah."
)
COPY_GALAT_ISIAN = (
    "Label tidak sah: harus 1-%d karakter tanpa karakter kontrol, belum dipakai topik lain, dan tidak "
    "sama dengan nama resmi sebuah topik. Tidak ada yang diubah." % MAKS_LABEL
)
COPY_TIDAK_SIAP = (
    "Database kurikulum tidak dapat diubah atau skemanya tidak dikenali di server ini. "
    "Tidak ada yang diubah. Operator perlu memeriksa berkas kurikulum."
)

Token = Tuple[str, str]


def url_ubah(topik_id: str, hasil: Optional[str] = None) -> str:
    """URL halaman ubah label satu topik (`topik` di-encode; `hasil` opsional kode banner)."""
    kueri = {"topik": topik_id}
    if hasil:
        kueri["hasil"] = hasil
    return "%s?%s" % (RUTE, urlencode(kueri))


def _hidden(csrf: str, tinjauan: str) -> str:
    return ('<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            % (e(csrf), e(tinjauan)))


def _sumber(item: ItemLabel) -> str:
    if item.sumber != SUMBER_ADMIN:
        return "bawaan kode"
    return "diubah admin, revisi %d, %s" % (item.revisi, item.diperbarui or "waktu tak tercatat")


def _form_ubah(item: ItemLabel, token: Token) -> str:
    return (
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s">%s'
        '<label>Label awam baru<input type="text" name="label" value="%s" maxlength="%d" required '
        'autocomplete="off"></label>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required '
        'autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Simpan</button></form>'
        % (RUTE, _hidden(*token), e(item.efektif), MAKS_LABEL))


def _form_kembalikan(token: Token) -> str:
    return (
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s">%s'
        '<p class="admin-meta">Mengembalikan label topik ini ke nilai bawaan kode. Perubahan admin '
        'sebelumnya tetap tercatat di riwayat.</p>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required '
        'autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Kembalikan ke bawaan</button></form>'
        % (RUTE_KEMBALIKAN, _hidden(*token)))


def _kepala(item: ItemLabel, nama_resmi: str) -> str:
    return (
        '<section class="admin-kartu"><h2>%s <code>%s</code></h2>'
        '<p class="admin-meta">Sumber: %s.</p>'
        '<dl class="admin-rincian"><dt>Bawaan kode</dt><dd>%s</dd>'
        '<dt>Efektif sekarang</dt><dd>%s</dd></dl>'
        '<p class="admin-meta">%s</p></section>' % (
            e(nama_resmi), e(item.topik_id), e(_sumber(item)), e(item.bawaan), e(item.efektif),
            e(COPY_CATATAN_BERLAKU)))


def _umpan_balik(hasil: Optional[str]) -> str:
    if hasil not in COPY_HASIL:
        return ""
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_HASIL[hasil])


def _riwayat(daftar: Sequence[RiwayatLabel]) -> str:
    if not daftar:
        isi = '<p class="admin-meta">Belum ada perubahan tercatat untuk topik ini.</p>'
    else:
        isi = '<ul class="kurikulum-daftar" aria-label="Riwayat perubahan">%s</ul>' % "".join(
            '<li><p class="kurikulum-kepala">Revisi %d · %s · <code>%s</code></p>'
            '<p class="admin-meta">%s → %s</p></li>' % (
                r.revisi, e(r.dibuat), e(r.actor_id), e(r.lama), e(r.baru))
            for r in daftar)
    return '<section class="admin-kartu"><h2>Riwayat terakhir</h2>%s</section>' % isi


def _tindakan(item: ItemLabel, token_ubah: Optional[Token], token_kembalikan: Optional[Token]) -> str:
    if token_ubah is None:
        return '<section class="admin-kartu"><p class="admin-meta">%s</p></section>' % e(COPY_TANPA_SESI)
    kembalikan = ""
    if item.sumber == SUMBER_ADMIN and token_kembalikan is not None:
        kembalikan = '<section class="admin-kartu"><h2>Kembalikan ke bawaan</h2>%s</section>' % (
            _form_kembalikan(token_kembalikan))
    return (
        '<section class="admin-kartu"><h2>Ubah label</h2><p class="admin-meta">%s</p>%s</section>%s'
        % (e(COPY_PETUNJUK), _form_ubah(item, token_ubah), kembalikan))


def halaman_edit(item: ItemLabel, *, nama_resmi: str, riwayat: Sequence[RiwayatLabel],
                 token_ubah: Optional[Token], token_kembalikan: Optional[Token],
                 hasil: Optional[str] = None) -> str:
    """Isi halaman ubah satu topik. Token `(csrf, tinjauan)` None = sesi tanpa kuki (baca-saja, tanpa form)."""
    return (
        tab_kurikulum(TAB_DETAIL_CP) + _umpan_balik(hasil)
        + '<p><a href="%s">&larr; Kembali ke Detail CP</a></p>' % RUTE_DETAIL_CP
        + _kepala(item, nama_resmi)
        + _tindakan(item, token_ubah, token_kembalikan) + _riwayat(riwayat)
    )
