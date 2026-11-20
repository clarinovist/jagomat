"""Bar tab "Topik cek", "Kurikulum Merdeka", dan "Detail CP": tiga halaman admin di rute masing-masing, satu butir menu.

Tab adalah tautan GET biasa (tanpa JS); halaman yang sedang dibuka ditandai ``aria-current``.
"""
from __future__ import annotations

from admin_komponen import e

TAB_CEK_TOPIK = "cek-topik"
TAB_KURIKULUM = "kurikulum"
TAB_DETAIL_CP = "cp-detail"
_TAB = (
    (TAB_CEK_TOPIK, "Topik cek", "/admin/cek-topik"),
    (TAB_KURIKULUM, "Kurikulum Merdeka", "/admin/kurikulum"),
    (TAB_DETAIL_CP, "Detail CP", "/admin/kurikulum/cp-detail"),
)


def tab_kurikulum(aktif: str) -> str:
    """Bar tab dengan ``aktif`` ditandai; nilai selain tiga kode di atas tidak menandai apa pun."""
    return '<div class="admin-tab-baris" role="group" aria-label="Topik dan kurikulum">%s</div>' % "".join(
        '<a class="admin-tab" href="%s"%s>%s</a>' % (
            href, ' aria-current="page"' if kode == aktif else "", e(nama))
        for kode, nama, href in _TAB
    )
