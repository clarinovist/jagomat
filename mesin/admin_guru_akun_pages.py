"""Halaman daftar dan kelola akun guru admin; murni, tanpa I/O dan tanpa JavaScript.

Aksi memakai alur tinjauan yang sudah ada (`/admin/tinjau?aksi=...&id=...&dari=guru` lalu `POST /admin/akun`: token tinjauan, CSRF,
sandi ulang admin); halaman ini hanya menautkan. Tanpa kredensial, hash, atau kontak.
"""
from __future__ import annotations

import time
from typing import Optional, Sequence

import admin_guru_akun as G
from admin_daftar_pages import kartu_tabel, sel_aktivitas, sel_nama
from admin_guru_tab import TAB_AKUN, tab_guru
from admin_komponen import e

RUTE = "/admin?section=guru"
RUTE_BUAT = "/admin/tinjau?aksi=account_teacher_create"
RUTE_LEMBAGA = "/admin/lembaga"
RUTE_NONAKTIFKAN = "/admin/guru/nonaktifkan"
RUTE_AKTIFKAN = "/admin/guru/aktifkan"
JUDUL = "Akun guru"
SUBJUDUL = "Guru yang bisa masuk ke aplikasi, lembaga tempatnya, dan tindakan akun."
CATATAN_KELUARGA = "Akun orang tua dari pendaftaran lama ada di menu Keluarga, bukan di sini."
COPY_TANPA_LEMBAGA = "Belum masuk lembaga"
COPY_KOSONG = "Belum ada guru yang cocok."
COPY_TAHAN_HAPUS = "Hapus login tidak tersedia: akun ini masih %s lembaga %s. Lepaskan atau bubarkan lembaganya dulu."
LABEL_SARING = (
    ("semua", "Semua guru"), ("belum_lembaga", "Belum masuk lembaga"),
    ("mandiri", "Daftar sendiri"), ("di_lembaga", "Di lembaga"), ("nonaktif", "Nonaktif"),
)
COPY_TAHAN_NONAKTIF = "Nonaktifkan tidak tersedia: akun ini masih pemilik lembaga %s. Pindahkan atau bubarkan lembaganya dulu."
COPY_NONAKTIF = "Akun nonaktif: tidak bisa masuk. Dinonaktifkan oleh %s%s."


def alamat_guru(id_akun: str) -> str:
    return "%s&id=%s" % (RUTE, id_akun)


def alamat_tinjau(aksi: str, id_akun: str) -> str:
    return "/admin/tinjau?aksi=%s&id=%s&dari=guru" % (aksi, id_akun)


def _chip(saring: str, hitungan: dict, aktif: str) -> str:
    return "".join(
        '<a class="admin-chip%s" href="%s"%s>%s <span class="admin-chip-hitung">%d</span></a>' % (
            " aktif" if kode == aktif else "", e(RUTE if kode == "semua" else "%s&status=%s" % (RUTE, kode)),
            ' aria-current="true"' if kode == aktif else "", e(label), hitungan.get(kode, 0))
        for kode, label in LABEL_SARING)


def _lembaga(g: G.GuruRingkas) -> str:
    if g.lembaga is None:
        return '<span class="admin-redup">%s</span>' % e(COPY_TANPA_LEMBAGA)
    return '%s <span class="admin-badge">%s</span>' % (e(g.lembaga), e(g.peran_lembaga))


def _lencana_nonaktif(g: G.GuruRingkas) -> str:
    return ' <span class="admin-badge">Nonaktif</span>' if g.nonaktif else ""


def _baris(g: G.GuruRingkas, sekarang) -> str:
    return (
        '<tr><td>%s</td><td>%s</td><td data-angka>%d</td><td>%s</td><td><a class="admin-tautan" href="%s" '
        'aria-label="Kelola guru %s">Kelola</a></td></tr>' % (
            sel_nama(g.pengguna, None, sub=G.LABEL_ASAL[g.asal]) + _lencana_nonaktif(g), _lembaga(g), g.jumlah_siswa,
            sel_aktivitas(g.aktivitas_terakhir, sekarang), e(alamat_guru(g.id_akun)), e(g.pengguna)))


def render_daftar(daftar: Sequence[G.GuruRingkas], saring: str, hitungan: dict, *, sekarang=None,
                  tampilkan_aksi: bool = True) -> str:
    baris = "".join(_baris(g, sekarang) for g in daftar) or (
        '<tr><td colspan="5" class="admin-kosong">%s</td></tr>' % e(COPY_KOSONG))
    kepala = ('<th scope="col">Guru</th>', '<th scope="col">Lembaga</th>', '<th scope="col" data-angka>Anak</th>',
              '<th scope="col">Aktivitas terakhir</th>', '<th scope="col">Tindakan</th>')
    buat = ('<p><a class="admin-tautan admin-tautan-kecil" href="%s">Buat akun guru</a></p>' % e(RUTE_BUAT)
            if tampilkan_aksi else "")
    return (tab_guru(TAB_AKUN) + buat + '<div class="admin-chip-baris">%s</div>' % _chip(saring, hitungan, saring)
            + kartu_tabel("Daftar guru", kepala, baris, '<p class="admin-meta">%s</p>' % e(CATATAN_KELUARGA),
                          keterangan="Diurutkan menurut nama."))


def _tanggal(epoch) -> str:
    return time.strftime(" pada %d-%m-%Y", time.gmtime(epoch)) if type(epoch) is int else ""


def _kartu_nonaktif(g: G.GuruRingkas) -> str:
    return (
        '<section class="admin-kartu"><h2>Akun nonaktif</h2><p>%s</p><p class="admin-aksi-baca">'
        '<a class="admin-tautan" href="%s?id=%s">Aktifkan kembali</a></p></section>'
        % (e(COPY_NONAKTIF % (g.nonaktif_oleh or "admin", _tanggal(g.nonaktif_pada))), e(RUTE_AKTIFKAN), e(g.id_akun)))


def _tautan_nonaktifkan(g: G.GuruRingkas) -> str:
    if g.peran_lembaga == G.PERAN_KOORDINATOR:
        return '<p class="admin-meta">%s</p>' % e(COPY_TAHAN_NONAKTIF % g.lembaga)
    return '<a class="admin-tautan admin-bahaya" href="%s?id=%s">Nonaktifkan akun</a>' % (e(RUTE_NONAKTIFKAN), e(g.id_akun))


def _tautan_aksi(g: G.GuruRingkas) -> str:
    if g.nonaktif:
        return _kartu_nonaktif(g)
    hapus = (
        '<p class="admin-meta">%s</p>' % e(COPY_TAHAN_HAPUS % (
            "pemilik" if g.peran_lembaga == G.PERAN_KOORDINATOR else "anggota", g.lembaga))
        if g.lembaga else
        '<a class="admin-tautan admin-bahaya" href="%s">Tinjau penghapusan login</a>' % e(
            alamat_tinjau("account_login_delete", g.id_akun)))
    lembaga = "" if g.lembaga else '<a class="admin-tautan" href="%s">Tambah ke lembaga</a>' % e(RUTE_LEMBAGA)
    siswa = ('<a class="admin-tautan" href="/admin?section=keluarga&id=%s">Lihat anak</a>' % e(g.id_akun)
             if g.jumlah_siswa else "")
    return (
        '<section class="admin-kartu"><h2>Tindakan</h2><p class="admin-aksi-baca">'
        '<a class="admin-tautan" href="%s">Reset sandi</a>'
        '<a class="admin-tautan" href="%s">Keluarkan perangkat</a>%s%s%s%s</p>'
        '<p class="admin-meta">Setiap tindakan meminta sandi admin dan tercatat di Riwayat admin.</p></section>' % (
            e(alamat_tinjau("account_password_reset", g.id_akun)),
            e(alamat_tinjau("account_session_revoke", g.id_akun)), hapus, lembaga, siswa, _tautan_nonaktifkan(g)))


def _tautan_jurnal(g: G.GuruRingkas) -> str:
    return '<p class="admin-meta"><a class="admin-tautan" href="%s">Lihat jurnal status</a></p>' % e(
        "/admin?section=riwayat&sumber=guru&id=%s" % g.id_akun)


def render_detail(g: G.GuruRingkas, *, tindakan: Optional[str] = None, sekarang=None) -> str:
    """Identitas guru + tindakan. `tindakan` (formulir dari alur tinjauan) menggantikan tautan aksi."""
    return (
        tab_guru(TAB_AKUN)
        + '<p class="admin-jejak"><a href="%s">← Kembali ke daftar guru</a></p>' % e(RUTE)
        + '<section class="admin-kartu"><h2>Identitas guru</h2><dl class="admin-rincian">'
          '<dt>Nama pengguna</dt><dd>%s</dd><dt>Asal akun</dt><dd>%s</dd><dt>Lembaga</dt><dd>%s</dd>'
          '<dt>Jumlah anak</dt><dd>%d</dd><dt>Jumlah sesi</dt><dd>%d</dd><dt>Aktivitas terakhir</dt><dd>%s</dd></dl></section>'
        % (e(g.pengguna) + _lencana_nonaktif(g), e(G.LABEL_ASAL[g.asal]), _lembaga(g), g.jumlah_siswa, g.jumlah_sesi,
           sel_aktivitas(g.aktivitas_terakhir, sekarang))
        + _tautan_jurnal(g)
        + (tindakan if tindakan is not None else _tautan_aksi(g)))
