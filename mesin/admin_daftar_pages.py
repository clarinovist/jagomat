"""Daftar Keluarga dan Siswa panel admin; murni, tanpa I/O dan tanpa JavaScript.

Komponen bersama (chip berhitungan, avatar, pill kondisi, kartu tabel) dipakai
kedua halaman. Pencarian tetap POST agar nama tidak masuk URL.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple
from urllib.parse import urlencode

import admin_queries as Q
from admin_komponen import e, hidden_filter, kepala_cari, opsi, pager, waktu
from admin_labels import LABEL_STATUS, label_status
from learning_profile import label_kelas_sekolah

LABEL_KATEGORI = {
    "orang_tua": "Orang Tua",
    "pengelola": "Pengelola",
    "pemilik_tanpa_akun": "Pemilik tanpa akun",
    "pemilik_kosong": "Pemilik kosong",
}
URUTAN_NAMA = "Diurutkan menurut nama."
STATUS_DARI_CHIP_SISWA = ("perlu_perhatian", "normal", "student_without_login", "owner_without_account")
KONDISI_LAINNYA_SISWA = ("owner_empty", "legacy_login_unverified", "legacy_same_name_ambiguous")
OPSI_KATEGORI = (
    ("semua", "Semua"), ("orang_tua", "Orang Tua"), ("pemilik_tanpa_akun", "Pemilik tanpa akun"),
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
    ``data.jumlah_facet`` (populasi yang sama dengan tabel); bila kosong, hanya
    chip aktif yang menampilkan total.
    """
    if data.cari:
        return '<p class="admin-meta">%d hasil pencarian. Gunakan filter lanjutan untuk mempertahankan pencarian privat.</p>' % data.total
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
    return '<nav class="admin-chip-baris" aria-label="Filter cepat">%s</nav>' % "".join(chips)


def avatar(nama: str, *, kapital: bool = False) -> str:
    inisial = (nama or "?")[:1]
    return '<span class="admin-avatar" aria-hidden="true">%s</span>' % e(inisial.upper() if kapital else inisial)


def pill_kondisi(status: Sequence[str]) -> str:
    if not status:
        return '<span class="admin-badge bien">Normal</span>'
    return "".join(
        '<span class="admin-badge perhatian">%s</span>' % e(label_status(kode)) for kode in status
    )


def sel_nama(nama: str, href: Optional[str], *, kapital: bool = False) -> str:
    isi = '<a href="%s">%s</a>' % (e(href), e(nama)) if href else e(nama)
    return '<div class="admin-sel-nama">%s%s</div>' % (avatar(nama, kapital=kapital), isi)


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
        '<button class="admin-tombol" type="submit">Cari</button></form>%s</div>'
        % (id_form, kelas, e(section), e(csrf), tersembunyi, e(label), e(cari), e(label), aksi)
    )
    panel = (
        '<details class="admin-filter-lanjutan"%s><summary>Filter lanjutan</summary><div>%s'
        '<button class="admin-tombol" type="submit" form="%s">Terapkan</button></div></details>'
        % (" open" if terbuka else "", lanjutan.replace("<select ", '<select form="%s" ' % id_form), id_form)
    )
    return kepala_cari(pencarian) + panel


def render_keluarga(
    data: Q.HalamanKeluarga, *, csrf: str = "", tampilkan_aksi: bool = True
) -> str:
    baris_semua = []
    for item in data.item:
        href = "/admin?section=keluarga&id=%s" % item.id_akun if item.id_akun is not None else None
        label_aksi = "Kelola akun" if tampilkan_aksi and item.kategori == "orang_tua" else "Lihat detail"
        kelola = '<a href="%s">%s</a>' % (e(href), label_aksi) if href else "—"
        baris_semua.append(
            '<tr><td>%s</td><td>%s</td><td data-angka>%d</td><td data-angka>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (
                sel_nama(item.pengguna or "Pemilik kosong", None),
                e(LABEL_KATEGORI[item.kategori]),
                item.jumlah_siswa,
                item.jumlah_sesi,
                waktu(item.aktivitas_terakhir),
                pill_kondisi(item.status),
                kelola,
            )
        )
    baris = "".join(baris_semua) or '<tr><td colspan="7" class="admin-kosong">Tidak ada keluarga yang cocok.</td></tr>'
    lanjutan = (
        '<label>Kategori akun<select name="kategori">%s</select></label>'
        '<label>Aktivitas terakhir<select name="aktivitas">%s</select></label>'
        % (
            "".join(opsi(nilai, label, data.kategori) for nilai, label in OPSI_KATEGORI),
            "".join(opsi(nilai, label, data.aktivitas) for nilai, label in OPSI_AKTIVITAS),
        )
    )
    # Chip aktif tetap ikut submit pencarian karena selectnya sudah tidak ada.
    tersembunyi = hidden_filter({"status": data.status, "memiliki_anak": data.memiliki_anak})
    buat = (
        '<a class="admin-tombol" href="/admin/tinjau?aksi=account_teacher_create">Buat akun orang tua</a>'
        if tampilkan_aksi else ""
    )
    filter_data = {
        "cari": data.cari, "memiliki_anak": data.memiliki_anak, "status": data.status,
        **_filter_aktif(data, ("kategori", "aktivitas")),
    }
    kepala = (
        '<th scope="col">Akun/pemilik</th>', '<th scope="col">Kategori</th>',
        '<th scope="col" data-angka>Siswa</th>', '<th scope="col" data-angka>Sesi</th>',
        '<th scope="col">Aktivitas terakhir</th>', '<th scope="col">Kondisi</th>',
        '<th scope="col">Tindakan</th>',
    )
    return (
        _bar_cari(
            "keluarga", csrf, data.cari, "Cari alias akun", lanjutan, buat,
            tersembunyi=tersembunyi, terbuka=bool(_filter_aktif(data, ("kategori", "aktivitas"))),
        )
        + ("" if csrf or not buat else '<p>%s</p>' % buat)
        + chip_daftar("keluarga", data, (
            ("Semua", {"status": "semua", "memiliki_anak": "semua"}, "semua"),
            ("Perlu perhatian", {"status": "perlu_perhatian", "memiliki_anak": "semua"}, "perlu_perhatian"),
            ("Belum memiliki siswa", {"status": "semua", "memiliki_anak": "tidak"}, "tanpa_siswa"),
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


def render_siswa(
    data: Q.HalamanSiswa, keluarga: Sequence[Q.KeluargaRingkas], *, csrf: str = ""
) -> str:
    opsi_keluarga = opsi("", "Semua keluarga", data.keluarga_id) + "".join(
        opsi(item.id_akun or "", item.pengguna, data.keluarga_id)
        for item in keluarga if item.id_akun is not None
    )
    # Chip dan select memakai satu parameter ``status``: nilai dari chip harus
    # tetap terkirim agar Terapkan tidak menimpanya menjadi "Semua".
    pilihan_pertama = (
        opsi(data.status, "Sesuai chip di atas", data.status)
        if data.status in STATUS_DARI_CHIP_SISWA else opsi("semua", "Semua", data.status)
    )
    lanjutan = (
        '<label>Profil parameter<select name="tingkat">%s%s</select></label>'
        '<label>Keluarga<select name="keluarga_id">%s</select></label>'
        '<label>Kondisi lainnya<select name="status">%s%s</select></label>'
        % (
            opsi("", "Semua profil", data.tingkat),
            "".join(opsi(level, level, data.tingkat) for level in ("P3", "P4", "P5", "P6")),
            opsi_keluarga,
            pilihan_pertama,
            "".join(opsi(kode, LABEL_STATUS[kode], data.status) for kode in KONDISI_LAINNYA_SISWA),
        )
    )
    baris = "".join(
        '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td data-angka>%d</td><td>%s</td><td>%s</td></tr>'
        % (
            sel_nama(item.nama, "/admin?section=siswa&id=%d" % item.id, kapital=True),
            (
                '<span class="admin-redup">Belum diisi</span>' if item.kelas_sekolah is None
                else e(label_kelas_sekolah(item.kelas_sekolah))
            ),
            e(item.pemilik or "Pemilik kosong"),
            e(item.login_pengguna) if item.login_pengguna else '<span class="admin-redup">Belum ada login tertaut</span>',
            item.jumlah_sesi,
            pill_kondisi(item.status),
            '<a href="/admin?section=siswa&amp;id=%d">%s</a>' % (item.id, "Tinjau" if item.status else "Buka"),
        )
        for item in data.item
    ) or '<tr><td colspan="7" class="admin-kosong">Tidak ada siswa yang cocok.</td></tr>'
    filter_data = {
        "cari": data.cari, "tingkat": data.tingkat,
        "keluarga_id": data.keluarga_id, "status": data.status,
    }
    kepala = (
        '<th scope="col">Siswa</th>', '<th scope="col">Kelas sekolah</th>',
        '<th scope="col">Keluarga</th>', '<th scope="col">Login</th>',
        '<th scope="col" data-angka>Sesi</th>', '<th scope="col">Kondisi</th>',
        '<th scope="col">Tindakan</th>',
    )
    catatan = (
        '<p class="admin-meta admin-kartu-catatan">Login tertaut adalah akun yang dihubungkan langsung ke profil siswa. '
        'Akun lama yang belum tertaut mungkin masih bisa masuk melalui kecocokan nama; periksa sebelum membuat akun baru.</p>'
    )
    return (
        _bar_cari("siswa", csrf, data.cari, "Cari nama, login, atau keluarga", lanjutan, kelas=" admin-form-siswa",
            terbuka=bool(data.tingkat or data.keluarga_id or data.status in KONDISI_LAINNYA_SISWA),
        )
        + chip_daftar("siswa", data, (
            ("Semua", {"status": "semua"}, "semua"),
            ("Perlu perhatian", {"status": "perlu_perhatian"}, "perlu_perhatian"),
            ("Belum ada login tertaut", {"status": "student_without_login"}, "student_without_login"),
            ("Pemilik tanpa akun", {"status": "owner_without_account"}, "owner_without_account"),
            ("Normal", {"status": "normal"}, "normal"),
        ))
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
