"""Daftar Keluarga dan Siswa panel admin; murni, tanpa I/O dan tanpa JavaScript.

Komponen bersama (chip berhitungan, avatar, pill kondisi, kartu tabel) dipakai
kedua halaman. Pencarian tetap POST agar nama tidak masuk URL.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple
from urllib.parse import urlencode

import admin_queries as Q
from admin_komponen import badge_status, e, hidden_filter, kepala_cari, opsi, pager, waktu
from admin_labels import LABEL_STATUS, label_status, relatif
from learning_profile import label_kelas_sekolah
from templates import LEVEL_TINGKAT

LABEL_KATEGORI = {
    "orang_tua": "Orang tua",
    "pengelola": "Akun pengelola",
    "pemilik_tanpa_akun": "Belum punya akun",
    "pemilik_kosong": "Belum punya pemilik",
}
# Kondisi yang bukan peringatan: ditampilkan netral dengan label pendek.
LABEL_KONDISI_NETRAL = {"student_without_login": "Tanpa login"}
CATATAN_TANPA_LOGIN = "Siswa tanpa login itu normal: anak masuk lewat QR atau tautan dari guru."
LABEL_CARA_QR = "QR / tautan HP"
LABEL_CARA_LOGIN = "Punya login"
URUTAN_NAMA = "Diurutkan menurut nama."
STATUS_DARI_CHIP_SISWA = ("perlu_perhatian", "normal", "student_without_login", "owner_without_account")
KONDISI_LAINNYA_SISWA = Q.KONDISI_AKUN_LAMA
OPSI_KATEGORI = (
    ("semua", "Semua"), ("orang_tua", "Orang tua"), ("pemilik_tanpa_akun", "Belum punya akun"),
)
OPSI_AKTIVITAS = (
    ("kapan_saja", "Kapan saja"), ("7_hari", "7 hari terakhir"),
    ("30_hari", "30 hari terakhir"), ("belum_pernah", "Belum pernah"),
)
BAWAAN_FILTER = {"kategori": "semua", "aktivitas": "kapan_saja"}


def _filter_aktif(data, nama_filter) -> dict:
    """Filter lanjutan non-bawaan yang ikut tautan chip dan pager."""
    return {
        nama: getattr(data, nama) for nama in nama_filter
        if hasattr(data, nama) and getattr(data, nama) != BAWAAN_FILTER[nama]
    }


def chip_daftar(section, data, daftar_chip) -> str:
    """Chip hanya mengarah ke filter publik; pencarian nama tetap di form POST.

    ``daftar_chip`` berisi (label, filter, kunci_facet). Hitungan berasal dari
    ``data.jumlah_facet`` (populasi yang sama dengan tabel, termasuk saat
    mencari); bila kosong, hanya chip aktif yang menampilkan total. Set chip
    sama di mode cari; tautannya tidak membawa kata kunci (tetap privat).
    """
    dasar = {"section": section}
    for nama in ("memiliki_anak", "status", "tingkat", "keluarga_id"):
        if hasattr(data, nama):
            dasar[nama] = getattr(data, nama)
    dasar.update(_filter_aktif(data, ("kategori", "aktivitas")))
    facet = dict(data.jumlah_facet)
    chips = []
    for label, nilai, kunci in daftar_chip:
        query = dict(dasar, **nilai)
        aktif = all(getattr(data, k) == v for k, v in nilai.items())
        if kunci in facet:
            jumlah = '<span class="admin-cnt">%d</span>' % facet[kunci]
        elif aktif:
            jumlah = '<span class="admin-cnt">%d</span>' % data.total
        else:
            jumlah = ""
        chips.append(
            '<a class="admin-chip"%s href="/admin?%s">%s%s</a>' % (
                ' aria-current="true"' if aktif else "",
                e(urlencode(query)), e(label), jumlah,
            )
        )
    catatan = (
        '<p class="admin-meta">%d hasil pencarian. Filter lanjutan mempertahankan pencarian; '
        'filter cepat menampilkan daftar tanpa kata kunci.</p>' % data.total
    ) if data.cari else ""
    return catatan + '<nav class="admin-chip-baris" aria-label="Filter cepat">%s</nav>' % "".join(chips)


def avatar(nama: str, *, kapital: bool = False) -> str:
    inisial = (nama or "?")[:1]
    return '<span class="admin-avatar" aria-hidden="true">%s</span>' % e(inisial.upper() if kapital else inisial)


def pill_kondisi(status: Sequence[str], netral: Sequence[str] = ()) -> str:
    """Pil kondisi; kode di ``netral`` tampil netral (bukan peringatan) dengan label pendek."""
    if not status:
        return badge_status(())
    return "".join(
        '<span class="admin-badge">%s</span>' % e(LABEL_KONDISI_NETRAL.get(kode, label_status(kode)))
        if kode in netral else
        '<span class="admin-badge perhatian">%s</span>' % e(label_status(kode))
        for kode in status
    )


def sel_nama(nama: str, href: Optional[str], *, kapital: bool = False, sub: str = "") -> str:
    isi = '<a href="%s">%s</a>' % (e(href), e(nama)) if href else e(nama)
    if sub:
        isi = '<span class="admin-sel-teks"><span>%s</span><span class="admin-sel-sub">%s</span></span>' % (isi, e(sub))
    return '<div class="admin-sel-nama">%s%s</div>' % (avatar(nama, kapital=kapital), isi)


def sel_aktivitas(nilai: Optional[str], sekarang=None) -> str:
    """Aktivitas terakhir relatif; tanggal lengkap tetap tersedia di tooltip."""
    teks = relatif(nilai, sekarang)
    if nilai in (None, ""):
        return '<span class="admin-redup">%s</span>' % e(teks)
    return '<span title="%s">%s</span>' % (waktu(nilai), e(teks))


def tombol_buka(href: Optional[str], label: str) -> str:
    if not href:
        return "—"
    return '<a class="admin-tautan" href="%s" aria-label="%s">Buka</a>' % (e(href), e(label))


def kartu_tabel(
    judul: str, kepala: Tuple[str, ...], baris: str, kaki: str, *,
    catatan: str = "", keterangan: str = URUTAN_NAMA,
) -> str:
    """Kartu daftar: judul + keterangan, tabel dengan ``th scope``, kaki pager."""
    th = "".join(kepala)
    return (
        '<section class="admin-kartu admin-kartu-tabel"><div class="admin-kartu-kepala">'
        '<h2>%s</h2><span class="admin-meta">%s</span></div>%s'
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="%s"><table class="admin-tabel">'
        '<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
        '<div class="admin-kartu-kaki">%s</div></section>'
        % (e(judul), e(keterangan), catatan, e(judul), th, baris, kaki)
    )


def _bar_cari(
    section: str, csrf: str, cari: str, label: str, lanjutan: str, aksi: str = "",
    kelas: str = "", tersembunyi: str = "", terbuka: bool = False,
) -> str:
    """Form pencarian (pindah ke baris judul) + panel Filter lanjutan di bawah header.

    Select panel memakai atribut ``form`` agar tetap terkirim bersama pencarian.
    """
    if not csrf:
        return '<p class="admin-meta">Tampilan baca-saja. Masuk melalui formulir untuk mencari dan mengelola akun.</p>'
    id_form = "form-cari-" + section
    pencarian = (
        '<div class="admin-grup-cari"><form id="%s" class="admin-form-cari%s" method="post" action="/admin">'
        '<input type="hidden" name="mode" value="cari"><input type="hidden" name="section" value="%s">'
        '<input type="hidden" name="csrf" value="%s">%s'
        '<label class="admin-cari"><span class="admin-sr">%s</span>'
        '<input name="cari" maxlength="80" value="%s" autocomplete="off" placeholder="%s"></label>'
        '<button class="admin-tombol admin-tombol-sekunder" type="submit">Cari</button></form>%s</div>'
        % (id_form, kelas, e(section), e(csrf), tersembunyi, e(label), e(cari), e(label), aksi)
    )
    panel = (
        '<details class="admin-filter-lanjutan"%s><summary>Filter lanjutan</summary><div>%s'
        '<button class="admin-tombol admin-tombol-sekunder" type="submit" form="%s">Terapkan</button></div></details>'
        % (" open" if terbuka else "", lanjutan.replace("<select ", '<select form="%s" ' % id_form), id_form)
    )
    return kepala_cari(pencarian) + panel




def _opsi_semua(pilihan, kini) -> str:
    return "".join(opsi(nilai, label, kini) for nilai, label in pilihan)


def _baris_keluarga(item, tampilkan_aksi: bool, sekarang) -> str:
    href = "/admin?section=keluarga&id=%s" % item.id_akun if item.id_akun is not None else None
    nama = item.pengguna or "Pemilik kosong"
    sub = "%s · %d sesi" % (LABEL_KATEGORI[item.kategori], item.jumlah_sesi)
    return (
        '<tr><td>%s</td><td data-angka>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (
            sel_nama(nama, None, sub=sub),
            item.jumlah_siswa,
            sel_aktivitas(item.aktivitas_terakhir, sekarang),
            pill_kondisi(item.status),
            tombol_buka(href, "Buka keluarga %s" % nama),
        )
    )


OPSI_KONDISI_KELUARGA = (
    ("semua", "Semua"), ("perlu_perhatian", "Perlu perhatian"), ("normal", "Normal"),
)
OPSI_MEMILIKI_SISWA = (
    ("semua", "Semua"), ("ya", "Memiliki siswa"), ("tidak", "Belum ada siswa"),
)


def render_keluarga(
    data: Q.HalamanKeluarga, *, csrf: str = "", tampilkan_aksi: bool = True, sekarang=None
) -> str:
    baris = "".join(_baris_keluarga(item, tampilkan_aksi, sekarang) for item in data.item) or (
        '<tr><td colspan="5" class="admin-kosong">Tidak ada keluarga yang cocok.</td></tr>'
    )
    # Kontrak form POST tidak berubah: saat tidak mencari, kondisi dan "memiliki siswa"
    # ikut sebagai hidden dari chip; saat mencari keduanya menjadi select agar bisa dilepas
    # tanpa memasukkan kata kunci ke URL. Chip tetap tampil di kedua mode.
    lanjutan = (
        '<label>Kategori akun<select name="kategori">%s</select></label>'
        '<label>Aktivitas terakhir<select name="aktivitas">%s</select></label>'
        % (_opsi_semua(OPSI_KATEGORI, data.kategori), _opsi_semua(OPSI_AKTIVITAS, data.aktivitas))
    )
    if data.cari:
        lanjutan += (
            '<label>Kondisi<select name="status">%s</select></label>'
            '<label>Memiliki siswa<select name="memiliki_anak">%s</select></label>'
            % (_opsi_semua(OPSI_KONDISI_KELUARGA, data.status), _opsi_semua(OPSI_MEMILIKI_SISWA, data.memiliki_anak))
        )
    tersembunyi = "" if data.cari else hidden_filter({"status": data.status, "memiliki_anak": data.memiliki_anak})
    buat = (
        '<a class="admin-tautan admin-tautan-kecil" href="/admin/tinjau?aksi=account_teacher_create">Buat akun guru</a>'
        if tampilkan_aksi else ""
    )
    filter_data = {
        "cari": data.cari, "memiliki_anak": data.memiliki_anak, "status": data.status,
        **_filter_aktif(data, ("kategori", "aktivitas")),
    }
    kepala = (
        '<th scope="col">Keluarga</th>', '<th scope="col" data-angka>Siswa</th>',
        '<th scope="col">Aktivitas terakhir</th>', '<th scope="col">Kondisi</th>',
        '<th scope="col">Tindakan</th>',
    )
    return (
        _bar_cari(
            "keluarga", csrf, data.cari, "Cari alias akun", lanjutan, buat,
            tersembunyi=tersembunyi, terbuka=bool(data.cari or _filter_aktif(data, ("kategori", "aktivitas"))),
        )
        + ("" if csrf or not buat else '<p>%s</p>' % buat)
        + chip_daftar("keluarga", data, (
            ("Semua", {"status": "semua", "memiliki_anak": "semua"}, "semua"),
            ("Perlu perhatian", {"status": "perlu_perhatian", "memiliki_anak": "semua"}, "perlu_perhatian"),
            ("Belum ada siswa", {"status": "semua", "memiliki_anak": "tidak"}, "tanpa_siswa"),
            ("Normal", {"status": "normal", "memiliki_anak": "semua"}, "normal"),
        ))
        + kartu_tabel(
            "Daftar keluarga", kepala, baris,
            pager(
                section="keluarga", halaman=data.halaman,
                jumlah_halaman=data.jumlah_halaman, total=data.total,
                filter_data=filter_data, via_post=bool(data.cari), csrf=csrf,
            ),
        )
    )


def _cara_masuk(item) -> str:
    if not item.login_pengguna:
        return '<span class="admin-badge">%s</span>' % LABEL_CARA_QR
    return '<span class="admin-badge">%s</span><span class="admin-sel-sub">%s</span>' % (
        LABEL_CARA_LOGIN, e(item.login_pengguna),
    )


def _baris_siswa(item) -> str:
    return (
        '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td data-angka>%d</td><td>%s</td><td>%s</td></tr>'
        % (
            sel_nama(item.nama, "/admin?section=siswa&id=%d" % item.id, kapital=True),
            (
                '<span class="admin-redup">Belum diisi</span>' if item.kelas_sekolah is None
                else e(label_kelas_sekolah(item.kelas_sekolah))
            ),
            e(item.pemilik or "Pemilik kosong"),
            _cara_masuk(item),
            item.jumlah_sesi,
            pill_kondisi(item.status, netral=tuple(LABEL_KONDISI_NETRAL)),
            tombol_buka("/admin?section=siswa&id=%d" % item.id, "Buka siswa %s" % item.nama),
        )
    )


OPSI_STATUS_SISWA = (
    ("semua", "Semua"), ("perlu_perhatian", "Perlu perhatian"), ("normal", "Normal"),
    ("student_without_login", "Tanpa login"), ("owner_without_account", "Pemilik tanpa akun"),
)


def _akun_lama(data: Q.HalamanSiswa) -> str:
    """Kondisi akun lama dikumpulkan di satu <details>; tiap kondisi tetap bisa difilter."""
    facet = dict(data.jumlah_facet)
    dasar = {"section": "siswa"}
    dasar.update({k: getattr(data, k) for k in ("tingkat", "keluarga_id") if getattr(data, k)})
    tautan = "".join(
        '<a class="admin-chip"%s href="/admin?%s">%s<span class="admin-cnt">%d</span></a>' % (
            ' aria-current="true"' if data.status == kode else "",
            e(urlencode(dict(dasar, status=kode))), e(LABEL_STATUS[kode]), facet.get(kode, 0),
        )
        for kode in KONDISI_LAINNYA_SISWA
    )
    total = sum(facet.get(kode, 0) for kode in KONDISI_LAINNYA_SISWA)
    return (
        '<details class="admin-lipat-kecil admin-akun-lama"%s><summary>Akun lama yang perlu dicocokkan (%d)</summary>'
        '<nav class="admin-chip-baris" aria-label="Kondisi akun lama">%s</nav></details>'
        % (" open" if data.status in KONDISI_LAINNYA_SISWA else "", total, tautan)
    )


def render_siswa(
    data: Q.HalamanSiswa, keluarga: Sequence[Q.KeluargaRingkas], *, csrf: str = ""
) -> str:
    opsi_keluarga = opsi("", "Semua keluarga", data.keluarga_id) + "".join(
        opsi(item.id_akun or "", item.pengguna, data.keluarga_id)
        for item in keluarga if item.id_akun is not None
    )
    # Set filter sama di mode cari dan non-cari; ``status`` selalu memuat semua pilihan
    # agar Terapkan tidak menimpa nilai yang datang dari chip.
    lanjutan = (
        '<label>Level soal<select name="tingkat">%s%s</select></label>'
        '<label>Keluarga<select name="keluarga_id">%s</select></label>'
        '<label>Kondisi<select name="status">%s%s</select></label>'
        % (
            opsi("", "Semua level", data.tingkat),
            "".join(opsi(level, level, data.tingkat) for level in LEVEL_TINGKAT),
            opsi_keluarga,
            _opsi_semua(OPSI_STATUS_SISWA, data.status),
            "".join(opsi(kode, LABEL_STATUS[kode], data.status) for kode in KONDISI_LAINNYA_SISWA),
        )
    )
    baris = "".join(_baris_siswa(item) for item in data.item) or (
        '<tr><td colspan="7" class="admin-kosong">Tidak ada siswa yang cocok.</td></tr>'
    )
    filter_data = {
        "cari": data.cari, "tingkat": data.tingkat,
        "keluarga_id": data.keluarga_id, "status": data.status,
    }
    kepala = (
        '<th scope="col">Siswa</th>', '<th scope="col">Kelas sekolah</th>',
        '<th scope="col">Keluarga</th>', '<th scope="col">Cara masuk</th>',
        '<th scope="col" data-angka>Sesi</th>', '<th scope="col">Kondisi</th>',
        '<th scope="col">Tindakan</th>',
    )
    catatan = (
        '<details class="admin-lipat-kecil admin-kartu-catatan"><summary>Tentang login tertaut dan kecocokan nama</summary>'
        '<p class="admin-meta">Login tertaut adalah akun yang dihubungkan langsung ke profil siswa. '
        'Akun lama yang belum tertaut mungkin masih bisa masuk melalui kecocokan nama; periksa sebelum membuat akun baru.</p>'
        '</details>'
    )
    return (
        _bar_cari("siswa", csrf, data.cari, "Cari nama, login, atau keluarga", lanjutan, kelas=" admin-form-siswa",
            terbuka=bool(data.cari or data.tingkat or data.keluarga_id or data.status in KONDISI_LAINNYA_SISWA),
        )
        + chip_daftar("siswa", data, (
            ("Semua", {"status": "semua"}, "semua"),
            ("Perlu perhatian", {"status": "perlu_perhatian"}, "perlu_perhatian"),
            ("Tanpa login", {"status": "student_without_login"}, "student_without_login"),
            ("Pemilik tanpa akun", {"status": "owner_without_account"}, "owner_without_account"),
            ("Normal", {"status": "normal"}, "normal"),
        ))
        + '<p class="admin-banner-info">%s</p>' % e(CATATAN_TANPA_LOGIN)
        + _akun_lama(data)
        + kartu_tabel(
            "Daftar siswa", kepala, baris,
            pager(
                section="siswa", halaman=data.halaman,
                jumlah_halaman=data.jumlah_halaman, total=data.total,
                filter_data=filter_data, via_post=bool(data.cari), csrf=csrf,
            ),
            catatan=catatan,
        )
    )
