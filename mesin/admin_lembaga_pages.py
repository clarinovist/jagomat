"""Renderer HTML murni halaman admin "Lembaga les" (tanpa JS, tanpa data anak).

Setiap aksi tulis membawa token CSRF, tinjauan bertanda tangan per aksi, dan kolom sandi
admin (`reauth`). Panel "Kelola" per lembaga tertutup secara bawaan, jadi kolom sandi
tidak terlihat bersamaan di halaman daftar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence, Tuple

from admin_komponen import e

BATAS_NAMA = 80
AKSI_BUAT = "lembaga_buat"
AKSI_TAMBAH = "lembaga_tambah"
AKSI_LEPAS = "lembaga_lepas"
AKSI_BUBARKAN = "lembaga_bubarkan"
COPY_NAMA_TIDAK_COCOK = "Nama lembaga yang diketik tidak cocok. Tidak ada yang dibubarkan."
COPY_LEPAS_SESI_BERJALAN = (
    "Guru ini belum bisa dilepas: masih ada anaknya dengan sesi yang sedang berjalan atau belum "
    "dikonfirmasi. Selesaikan dan konfirmasi sesinya dulu, lalu lepas lagi. Tidak ada yang diubah."
)
COPY_LEPAS_NAMA_HABIS = (
    "Guru ini belum bisa dilepas: nama salah satu anaknya sudah terlalu banyak kembar di pemilik "
    "les, sehingga nomor pembeda habis. Ubah nama anak itu dulu. Tidak ada yang diubah."
)


def teks_konfirmasi_lepas(guru: str, jumlah_anak: int) -> str:
    """Teks `confirm()` lepas anggota; menyebut ke mana anaknya pergi."""
    if jumlah_anak <= 0:
        return "Lepas %s dari lembaga?" % guru
    return "Lepas %s dari lembaga? %d anak akan kembali ke antrean lembaga (pemilik les)." % (
        guru, jumlah_anak)


@dataclass(frozen=True)
class TokenLembaga:
    """Token CSRF dan tinjauan bertanda tangan yang sudah dibuat lapisan HTTP."""
    csrf: str
    buat: str
    tambah: Mapping[int, str] = field(default_factory=dict)
    lepas: Mapping[Tuple[int, str], str] = field(default_factory=dict)
    anak_guru: Mapping[str, int] = field(default_factory=dict)
    bubarkan: Mapping[int, str] = field(default_factory=dict)


def _pilihan(nama_guru: Sequence[str]) -> str:
    return "".join('<option value="%s">%s</option>' % (e(n), e(n)) for n in nama_guru)


def _tersembunyi(csrf: str, tinjauan: str, lembaga_id: Optional[int] = None) -> str:
    isi = ('<input type="hidden" name="csrf" value="%s">'
           '<input type="hidden" name="tinjauan" value="%s">') % (e(csrf), e(tinjauan))
    if lembaga_id is not None:
        isi += '<input type="hidden" name="lembaga_id" value="%d">' % int(lembaga_id)
    return isi


def _kolom_sandi() -> str:
    return ('<label>Sandi admin saat ini<input type="password" name="reauth" required '
            'autocomplete="current-password"></label>')


def _form_buat(token: Optional[TokenLembaga], calon: Sequence[str]) -> str:
    if token is None:
        return ""
    if not calon:
        return ('<section class="admin-kartu"><h2>Buat lembaga</h2>'
                '<p class="admin-meta">Belum ada akun guru yang bebas untuk dijadikan pemilik.</p></section>')
    return (
        '<details class="admin-kartu admin-lembaga-buat"><summary>Buat lembaga</summary>'
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="/admin/lembaga/buat">%s'
        '<label>Nama lembaga (maksimal %d huruf)<input name="nama" maxlength="%d" required></label>'
        '<label>Pemilik les (akun guru)<select name="pemilik" required>%s</select></label>%s'
        '<button class="admin-tombol" type="submit">Buat lembaga</button></form></details>'
    ) % (_tersembunyi(token.csrf, token.buat), BATAS_NAMA, BATAS_NAMA, _pilihan(calon), _kolom_sandi())


def _form_lepas(token: TokenLembaga, lembaga_id: int, guru: str) -> str:
    tinjauan = token.lepas.get((lembaga_id, guru))
    if tinjauan is None:
        return ""
    return (
        '<form class="admin-form-cari admin-lembaga-lepas" method="post" action="/admin/lembaga/lepas" '
        'data-konfirmasi="%s">%s<input type="hidden" name="guru" value="%s">'
        '<span class="admin-lembaga-nama">%s</span>%s'
        '<button class="admin-tombol admin-tombol-sekunder" type="submit">Lepas</button></form>'
    ) % (
        e(teks_konfirmasi_lepas(guru, token.anak_guru.get(guru, 0))),
        _tersembunyi(token.csrf, tinjauan, lembaga_id), e(guru), e(guru), _kolom_sandi(),
    )


def _bagian_anggota(token: TokenLembaga, lembaga_id: int, anggota: Tuple[str, ...]) -> str:
    isi = "".join(_form_lepas(token, lembaga_id, g) for g in anggota) or (
        '<p class="admin-kosong">Belum ada anggota.</p>')
    return '<div class="admin-bagian"><h3>Anggota</h3>%s</div>' % isi


def _form_tambah(token: TokenLembaga, lembaga_id: int, calon: Sequence[str]) -> str:
    tinjauan = token.tambah.get(lembaga_id)
    if tinjauan is None:
        return ""
    if not calon:
        return ('<div class="admin-bagian"><h3>Tambah guru</h3>'
                '<p class="admin-meta">Semua guru sudah terikat pada lembaga.</p></div>')
    return (
        '<div class="admin-bagian"><h3>Tambah guru</h3>'
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="/admin/lembaga/anggota">%s'
        '<label>Guru yang belum bergabung<select name="guru" required>%s</select></label>%s'
        '<button class="admin-tombol admin-tombol-sekunder" type="submit">Tambah guru</button></form></div>'
    ) % (_tersembunyi(token.csrf, tinjauan, lembaga_id), _pilihan(calon), _kolom_sandi())


def _zona_bahaya(token: TokenLembaga, lembaga_id: int, nama: str) -> str:
    tinjauan = token.bubarkan.get(lembaga_id)
    if tinjauan is None:
        return ""
    return (
        '<details class="admin-lembaga-bahaya"><summary>Bubarkan lembaga</summary>'
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="/admin/lembaga/bubarkan" '
        'data-konfirmasi="%s">%s'
        '<p class="admin-meta">Keanggotaan dihapus; akun guru tidak ikut terhapus, anak tetap milik gurunya, '
        'dan jejak pemindahan tetap tersimpan. Ketik nama lembaga persis (<strong>%s</strong>) untuk memastikan.</p>'
        '<label>Nama lembaga<input name="konfirmasi_nama" autocomplete="off" required></label>%s'
        '<button class="admin-tombol admin-bahaya" type="submit">Bubarkan lembaga</button></form></details>'
    ) % (
        e("Bubarkan lembaga %s? Keanggotaan dihapus; anak tetap milik gurunya masing-masing "
          "dan jejak pemindahan tetap tersimpan." % nama),
        _tersembunyi(token.csrf, tinjauan, lembaga_id), e(nama), _kolom_sandi(),
    )


def _kelola(token: Optional[TokenLembaga], baris, anggota: Tuple[str, ...], calon: Sequence[str]) -> str:
    if token is None:
        return ""
    lembaga_id = int(baris["id"])
    return (
        '<details class="admin-lembaga-kelola"><summary>Kelola</summary>%s%s%s</details>'
    ) % (_bagian_anggota(token, lembaga_id, anggota), _form_tambah(token, lembaga_id, calon),
         _zona_bahaya(token, lembaga_id, baris["nama"]))


def _kartu(baris, anggota: Tuple[str, ...], token: Optional[TokenLembaga], calon: Sequence[str]) -> str:
    chip = "".join('<li class="admin-badge">%s</li>' % e(g) for g in anggota) or (
        '<li class="admin-kosong">Belum ada guru anggota.</li>')
    return (
        '<section class="admin-kartu admin-lembaga"><div class="admin-kartu-kepala"><h2>%s</h2>'
        '<span class="admin-meta">Pemilik les: %s · %d guru</span></div>'
        '<ul class="admin-lembaga-anggota">%s</ul>%s</section>'
    ) % (e(baris["nama"]), e(baris["pemilik"]), len(anggota), chip, _kelola(token, baris, anggota, calon))


def halaman(lembaga: Sequence[tuple], calon: Sequence[str], token: Optional[TokenLembaga]) -> str:
    """``lembaga`` = [(baris, anggota)], ``calon`` = guru yang belum terikat.

    ``token`` None (sesi bukan cookie) = halaman hanya-baca tanpa form tulis.
    """
    isi = "".join(_kartu(b, a, token, calon) for b, a in lembaga) or (
        '<section class="admin-kartu"><p class="admin-kosong">Belum ada lembaga.</p></section>')
    catatan = (
        '<section class="admin-kartu admin-catatan"><p class="admin-meta">Pemilik les melihat '
        "ringkasan agregat dan boleh memindahkan anak antar guru lembaganya, tanpa akses ke "
        "isi belajar anak. Satu guru hanya boleh masuk satu lembaga; akun admin tidak bisa "
        "menjadi pemilik atau anggota. Setiap perubahan meminta sandi admin.</p></section>"
    )
    return _form_buat(token, calon) + isi + catatan
