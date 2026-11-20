"""Bar tab "Guru & pemakaian": dua halaman admin di rute masing-masing, satu butir menu.

Tab adalah tautan GET biasa (tanpa JS); halaman yang sedang dibuka ditandai ``aria-current``.
"""
from __future__ import annotations

from admin_komponen import e

TAB_PEMAKAIAN = "pemakaian"
TAB_PROFIL = "profil"
_TAB = (
    (TAB_PEMAKAIAN, "Pemakaian", "/admin/pemakaian"),
    (TAB_PROFIL, "Profil guru peninjau", "/admin/profil-guru"),
)


def tab_guru(aktif: str) -> str:
    """Bar tab dengan ``aktif`` ditandai; nilai selain dua kode di atas tidak menandai apa pun."""
    return '<div class="admin-tab-baris" role="group" aria-label="Guru dan pemakaian">%s</div>' % "".join(
        '<a class="admin-tab" href="%s"%s>%s</a>' % (
            href, ' aria-current="page"' if kode == aktif else "", e(nama))
        for kode, nama, href in _TAB
    )
