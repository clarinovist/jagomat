"""Renderer HTML murni halaman admin "Profil guru peninjau" (tanpa DB, tanpa data anak)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from admin_guru_tab import TAB_PROFIL, tab_guru
from admin_komponen import e
import profil_guru_settings as pg

PESAN_BELUM_SIAP = "Penyimpanan profil guru belum disiapkan oleh pengelola rilis."
AKSI_TAMBAH = "/admin/profil-guru/tambah"
AKSI_UBAH = "/admin/profil-guru/ubah"
AKSI_HAPUS = "/admin/profil-guru/hapus"
CATATAN = (
    "Isi hanya dengan persetujuan tertulis guru yang bersangkutan. Hanya nama, latar pendidikan, "
    "dan lama mengajar; tanpa foto, kontak, atau data anak. Profil baru tersembunyi sampai "
    "Anda mencentang \"Tampilkan di halaman publik\"."
)


@dataclass(frozen=True)
class TokenForm:
    """Token CSRF dan tinjauan bertanda tangan yang sudah dibuat lapisan HTTP."""
    csrf: str
    tambah: str
    ubah: Mapping[int, str] = field(default_factory=dict)
    hapus: Mapping[int, str] = field(default_factory=dict)


def _tersembunyi(csrf: str, token: str) -> str:
    return ('<input type="hidden" name="csrf" value="%s">'
            '<input type="hidden" name="tinjauan" value="%s">') % (e(csrf), e(token))


def _kolom_reauth() -> str:
    return ('<label>Sandi admin saat ini<input type="password" name="reauth" required '
            'autocomplete="current-password"></label>')


def _kolom_isian(profil: Optional[pg.ProfilGuru], urutan_awal: int) -> str:
    def nilai(nama):
        return e(getattr(profil, nama)) if profil else ""

    urutan = profil.urutan if profil else urutan_awal
    return (
        '<label>Nama guru<input name="nama" maxlength="%d" value="%s" required></label>'
        '<label>Latar pendidikan<input name="latar" maxlength="%d" value="%s" required></label>'
        '<label>Lama mengajar<input name="lama_mengajar" maxlength="%d" value="%s" required></label>'
        '<label>Urutan tampil (%d sampai %d)<input name="urutan" type="number" min="%d" max="%d" '
        'value="%d" required></label>'
        '<label><input type="checkbox" name="tampil" value="1"%s> Tampilkan di halaman publik</label>'
    ) % (
        pg.BATAS_NAMA, nilai("nama"), pg.BATAS_LATAR, nilai("latar"), pg.BATAS_LAMA,
        nilai("lama_mengajar"), pg.URUTAN_MIN, pg.URUTAN_MAKS, pg.URUTAN_MIN, pg.URUTAN_MAKS,
        urutan, " checked" if profil and profil.tampil else "",
    )


def _form_tambah(token: TokenForm, jumlah: int) -> str:
    if jumlah >= pg.BATAS_BARIS:
        return ('<section class="admin-kartu"><h2>Tambah profil guru</h2><p class="admin-meta">'
                'Daftar penuh: maksimal %d profil. Hapus satu profil untuk menambah yang baru.</p></section>'
                % pg.BATAS_BARIS)
    return (
        '<section class="admin-kartu"><h2>Tambah profil guru</h2>'
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s">%s%s%s'
        '<button class="admin-tombol" type="submit">Tambah profil</button></form></section>'
    ) % (AKSI_TAMBAH, _tersembunyi(token.csrf, token.tambah), _kolom_isian(None, jumlah + 1), _kolom_reauth())


def _konfirmasi_hapus(profil: pg.ProfilGuru) -> str:
    dampak = ("Kartu guru ini langsung hilang dari halaman publik. " if profil.tampil
              else "Profil ini tidak sedang tampil di halaman publik. ")
    return ("Hapus profil \"%s\" secara permanen? %sJejak audit tetap tersimpan; "
            "tindakan tidak dapat dibatalkan." % (profil.nama, dampak))


def _form_hapus(profil: pg.ProfilGuru, token: TokenForm) -> str:
    return (
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s" data-konfirmasi="%s">'
        '%s%s<button class="admin-tombol admin-bahaya" type="submit">Hapus profil</button></form>'
    ) % (AKSI_HAPUS, e(_konfirmasi_hapus(profil)), _tersembunyi(token.csrf, token.hapus[profil.id]),
         _kolom_reauth())


def _kartu_baris(profil: pg.ProfilGuru, token: Optional[TokenForm]) -> str:
    status = ('<span class="admin-badge">Tampil di halaman publik</span>' if profil.tampil
              else '<span class="admin-badge">Tersembunyi</span>')
    ringkas = ('<p class="admin-meta">%s · %s</p>') % (e(profil.latar), e(profil.lama_mengajar))
    forms = ""
    if token is not None and profil.id in token.ubah and profil.id in token.hapus:
        forms = (
            '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s">%s%s%s'
            '<button class="admin-tombol" type="submit">Simpan perubahan</button></form>%s'
        ) % (AKSI_UBAH, _tersembunyi(token.csrf, token.ubah[profil.id]), _kolom_isian(profil, 1),
             _kolom_reauth(), _form_hapus(profil, token))
    return ('<section class="admin-kartu"><div class="admin-kartu-kepala"><h2>%s</h2>%s</div>%s%s</section>'
            % (e(profil.nama), status, ringkas, forms))


def _daftar(profil: Sequence[pg.ProfilGuru], token: Optional[TokenForm]) -> str:
    if not profil:
        return '<section class="admin-kartu"><p class="admin-kosong">Belum ada profil guru.</p></section>'
    return "".join(_kartu_baris(p, token) for p in profil)


def halaman(profil: Optional[Sequence[pg.ProfilGuru]], token: Optional[TokenForm] = None,
            feedback: str = "") -> str:
    """``profil`` None = penyimpanan belum siap; ``token`` None = hanya baca (tanpa form)."""
    tab = tab_guru(TAB_PROFIL)
    if profil is None:
        return tab + ('<section class="admin-kartu admin-catatan" role="status" aria-atomic="true">'
                      '<h2>Penyimpanan belum siap</h2><p>%s</p></section>' % e(PESAN_BELUM_SIAP))
    status = ('<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(feedback)
              if feedback else "")
    catatan = '<section class="admin-kartu admin-catatan"><p class="admin-meta">%s</p></section>' % e(CATATAN)
    tambah = _form_tambah(token, len(profil)) if token is not None else ""
    return tab + status + catatan + _daftar(profil, token) + tambah
