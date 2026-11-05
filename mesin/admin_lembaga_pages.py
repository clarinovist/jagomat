"""Renderer HTML murni halaman admin "Lembaga les" (tanpa JS, tanpa data anak)."""
from __future__ import annotations

from typing import Sequence, Tuple

from admin_komponen import e

BATAS_NAMA = 80


def _pilihan(nama_guru: Sequence[str]) -> str:
    return "".join('<option value="%s">%s</option>' % (e(n), e(n)) for n in nama_guru)


def _form_buat(csrf: str, calon: Sequence[str]) -> str:
    if not csrf:
        return ""
    if not calon:
        return ('<section class="admin-kartu"><h2>Buat lembaga</h2>'
                '<p class="admin-meta">Belum ada akun guru yang bebas untuk dijadikan pemilik.</p></section>')
    return (
        '<section class="admin-kartu"><h2>Buat lembaga</h2>'
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="/admin/lembaga/buat">'
        '<input type="hidden" name="csrf" value="%s">'
        '<label>Nama lembaga<input name="nama" maxlength="%d" required></label>'
        '<label>Pemilik les (akun guru)<select name="pemilik" required>%s</select></label>'
        '<button class="admin-tombol" type="submit">Buat lembaga</button></form></section>'
    ) % (e(csrf), BATAS_NAMA, _pilihan(calon))


def _form_anggota(csrf: str, lembaga_id: int, aksi: str, tombol: str, pilihan: Sequence[str],
                  konfirmasi: str = "") -> str:
    if not csrf or not pilihan:
        return ""
    atribut = ' data-konfirmasi="%s"' % e(konfirmasi) if konfirmasi else ""
    return (
        '<form class="admin-form-cari" method="post" action="/admin/lembaga/%s"%s>'
        '<input type="hidden" name="csrf" value="%s">'
        '<input type="hidden" name="lembaga_id" value="%d">'
        '<label><span class="admin-sr">Guru</span><select name="guru" required>%s</select></label>'
        '<button class="admin-tombol admin-tombol-sekunder" type="submit">%s</button></form>'
    ) % (aksi, atribut, e(csrf), int(lembaga_id), _pilihan(pilihan), e(tombol))


def _form_bubarkan(csrf: str, lembaga_id: int, nama: str) -> str:
    if not csrf:
        return ""
    return (
        '<form method="post" action="/admin/lembaga/bubarkan" data-konfirmasi="%s">'
        '<input type="hidden" name="csrf" value="%s">'
        '<input type="hidden" name="lembaga_id" value="%d">'
        '<button class="admin-tombol admin-bahaya" type="submit">Bubarkan lembaga</button></form>'
    ) % (e("Bubarkan lembaga %s? Keanggotaan dihapus; anak tetap milik gurunya masing-masing "
           "dan jejak pemindahan tetap tersimpan." % nama), e(csrf), int(lembaga_id))


def _kartu(baris, anggota: Tuple[str, ...], csrf: str, calon: Sequence[str]) -> str:
    daftar = "".join("<li>%s</li>" % e(g) for g in anggota) or (
        '<li class="admin-kosong">Belum ada anggota.</li>')
    return (
        '<section class="admin-kartu"><div class="admin-kartu-kepala"><h2>%s</h2>'
        '<span class="admin-meta">Pemilik les: %s</span></div>'
        '<p class="admin-meta">Guru anggota</p><ul>%s</ul>%s%s%s</section>'
    ) % (
        e(baris["nama"]), e(baris["pemilik"]), daftar,
        _form_anggota(csrf, baris["id"], "anggota", "Tambah anggota", calon),
        _form_anggota(csrf, baris["id"], "lepas", "Lepas anggota", anggota,
                      "Lepas guru ini dari lembaga? Anak yang sudah dipindahkan tetap milik gurunya."),
        _form_bubarkan(csrf, baris["id"], baris["nama"]),
    )


def halaman(lembaga: Sequence[tuple], calon: Sequence[str], csrf: str) -> str:
    """``lembaga`` = [(baris, anggota)], ``calon`` = guru yang belum terikat."""
    isi = "".join(_kartu(b, a, csrf, calon) for b, a in lembaga) or (
        '<section class="admin-kartu"><p class="admin-kosong">Belum ada lembaga.</p></section>')
    catatan = (
        '<section class="admin-kartu admin-catatan"><p class="admin-meta">Pemilik les melihat '
        "ringkasan agregat dan boleh memindahkan anak antar guru lembaganya, tanpa akses ke "
        "isi belajar anak. Satu guru hanya boleh masuk satu lembaga; akun admin tidak bisa "
        "menjadi pemilik atau anggota.</p></section>"
    )
    return _form_buat(csrf, calon) + isi + catatan
