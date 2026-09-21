"""Renderer murni kandidat pusat kendali admin readonly.

Tidak ada pemeriksaan principal, header HTTP, routing, atau mutasi di modul ini.
Integration wajib melakukan palang admin sebelum membangun DTO. Seluruh fungsi
menerima proyeksi ``admin_queries`` yang sudah membuang credential.
"""

from __future__ import annotations

import html
from typing import Mapping, Optional, Sequence, Tuple
from urllib.parse import urlencode

import admin_queries as Q
import brand
from admin_style import GAYA_ADMIN
import design_tokens as T
import learning_profile_ui
from learning_profile import label_kelas_sekolah


SECTION = (
    ("ringkasan", "Ringkasan", "/admin"),
    ("keluarga", "Keluarga", "/admin?section=keluarga"),
    ("siswa", "Siswa", "/admin?section=siswa"),
    ("pendaftaran", "Pendaftaran", "/admin?section=pendaftaran"),
    ("ai", "AI", "/admin/ai"),
    ("riwayat", "Riwayat admin", "/admin?section=riwayat"),
)
SECTION_LOKAL = frozenset(item[0] for item in SECTION if item[0] != "ai")
SKRIP_KONFIRMASI_LOGIN = """document.querySelectorAll('form[data-konfirmasi-login]').forEach(function(f){f.addEventListener('submit',function(e){if(!window.confirm(f.dataset.konfirmasiLogin)){e.preventDefault();}});});"""

LABEL_STATUS = {
    "account_missing_id": "ID akun belum tersedia",
    "no_students": "Belum memiliki siswa",
    "student_without_login": "Siswa belum punya login eksplisit",
    "duplicate_explicit_login": "Lebih dari satu login menunjuk siswa",
    "owner_without_account": "Pemilik tidak memiliki akun",
    "owner_empty": "Pemilik siswa kosong",
    "owner_admin": "Dimiliki akun pengelola",
    "orphan_login": "Login menunjuk siswa yang tidak ada",
    "legacy_orphan_login": "Login warisan tidak punya kandidat siswa",
    "legacy_login_unverified": "Login warisan belum terverifikasi",
    "legacy_same_name_ambiguous": "Nama warisan cocok ke beberapa siswa",
}
LABEL_KATEGORI = {
    "orang_tua": "Orang Tua",
    "pengelola": "Pengelola",
    "pemilik_tanpa_akun": "Pemilik tanpa akun",
    "pemilik_kosong": "Pemilik kosong",
}


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _judul_section(section: str) -> Tuple[str, str]:
    if section == "keluarga":
        return "Keluarga", "Daftar akun orang tua dan kepemilikan siswa."
    if section == "siswa":
        return "Siswa", "Identitas administratif, kelas, keluarga, dan status login."
    if section == "pendaftaran":
        return "Pendaftaran", "Status pengaturan pendaftaran mandiri."
    if section == "riwayat":
        return "Riwayat admin", "Riwayat tindakan panel mulai dari cutover fitur."
    return "Ringkasan", "Kondisi operasional lintas keluarga tanpa menilai progres belajar."


def _nav(section: str) -> str:
    return "".join(
        '<a href="%s"%s>%s</a>' % (
            _e(jalur),
            ' aria-current="page"' if sid == section else "",
            _e(label),
        )
        for sid, label, jalur in SECTION
    )


def halaman_admin(
    section: str,
    isi: str,
    *,
    pengguna: str,
    judul: Optional[str] = None,
    subjudul: Optional[str] = None,
    skrip_sandi: str = "",
) -> bytes:
    """Frame privat tanpa aset eksternal atau JS.

    Fase tulis kelak harus menambah script approved lewat API bertipe dan CSP
    yang ditetapkan lapisan HTTP, bukan menyisipkan input request ke ``head``.
    Frame readonly ini sengaja tidak menetapkan CSP yang akan memblokir kontrak
    tersebut diam-diam.
    """
    if section not in SECTION_LOKAL and section != "ai":
        section = "ringkasan"
        judul = None
        subjudul = None
    judul_bawaan, sub_bawaan = _judul_section(section)
    judul = judul_bawaan if judul is None else judul
    subjudul = sub_bawaan if subjudul is None else subjudul
    dokumen = f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta name="referrer" content="no-referrer">
<title>{_e(judul)} · {_e(T.NAMA_PRODUK)}</title>
{brand.tag_kepala(cetak=True)}
<style>{GAYA_ADMIN}</style></head>
<body class="admin-readonly"><a class="admin-lompat" href="#konten-admin">Lewati navigasi</a>
<div class="admin-bungkus"><header class="admin-topbar">
<a class="admin-brand" href="/admin">{_e(T.NAMA_PRODUK)} · Panel Pengelola</a>
<details class="menu-pengguna"><summary>{_e(pengguna)} <span class="admin-badge">Pengelola</span></summary>
<div class="menu-isi"><a href="/akun?section=akun">Ganti sandi</a>
<form method="post" action="/keluar"><button type="submit">Keluar</button></form></div></details></header>
<header class="admin-kepala"><p class="admin-alis">Ruang pengelola</p>
<h1 id="judul-admin">{_e(judul)}</h1><p class="admin-sub">{_e(subjudul)}</p></header>
<nav class="admin-nav" aria-label="Bagian panel pengelola">{_nav(section)}</nav>
<main id="konten-admin" aria-labelledby="judul-admin">{isi}</main>
<footer class="admin-footer">Tampilan privat · Data operasional, bukan penilaian kemampuan anak.</footer>
</div>{'<script>' + skrip_sandi + '</script>' if skrip_sandi else ''}</body></html>"""
    return dokumen.encode("utf-8")


def _badge_status(status: Sequence[str]) -> str:
    if not status:
        return '<span class="admin-badge">Normal</span>'
    return "".join(
        '<span class="admin-badge perhatian">%s</span>'
        % _e(LABEL_STATUS.get(kode, "Perlu ditinjau"))
        for kode in status
    )


def _waktu(nilai: Optional[str]) -> str:
    return "—" if not nilai else _e(nilai)


def render_ringkasan(data: Q.RingkasanAdmin, *, status_layanan: str = "") -> str:
    kartu = (
        (data.jumlah_keluarga, "akun orang tua terdaftar"),
        (data.jumlah_siswa, "siswa"),
        (data.jumlah_login_murid, "login murid"),
        (data.jumlah_sesi, "catatan sesi"),
    )
    stat = "".join(
        '<article class="admin-stat"><strong>%d</strong><span>%s</span></article>'
        % (jumlah, _e(label))
        for jumlah, label in kartu
    )
    perhatian = (
        "".join(
            '<li><strong>%d</strong> %s</li>'
            % (item.jumlah, _e(LABEL_STATUS.get(item.kode, "Perlu ditinjau")))
            for item in data.perhatian
        )
        or "<li>Tidak ada kondisi administratif yang perlu perhatian.</li>"
    )
    login_bermasalah = "".join(
        '<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (
            _e(item.pengguna),
            _e(LABEL_STATUS.get(item.status, "Perlu ditinjau")),
            _e(item.jumlah_kandidat),
        )
        for item in data.login_bermasalah
    ) or '<tr><td colspan="3" class="admin-kosong">Tidak ada login yang perlu ditinjau.</td></tr>'
    aktivitas = "".join(
        '<tr><td><a href="/sesi/%d">Sesi %d</a></td>'
        '<td><a href="/anak/%d">%s</a></td><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (
            item.sesi_id,
            item.sesi_id,
            item.siswa_id,
            _e(item.nama_siswa),
            _e(item.pemilik or "Pemilik kosong"),
            _e(item.waktu_aktivitas),
            '<span class="admin-badge batal">Dibatalkan</span>'
            if item.dibatalkan else '<span class="admin-badge">Tercatat</span>',
        )
        for item in data.aktivitas_terbaru
    ) or '<tr><td colspan="5" class="admin-kosong">Belum ada aktivitas sesi.</td></tr>'
    return (
        '<section class="admin-grid-stat" aria-label="Jumlah administratif">%s</section>' % stat
        + status_layanan
        + '<section class="admin-kartu admin-catatan"><h2>Definisi angka</h2>'
        '<p>Catatan sesi mencakup sesi dibatalkan. Jendela 7/30 hari memakai '
        '<code>selesai → mulai → dibuat → tanggal</code> dalam waktu WIB. '
        'Angka ini tidak menyatakan anak sedang online, sudah belajar, atau lulus.</p>'
        '<p><strong>%d</strong> sesi dalam 7 hari · <strong>%d</strong> dalam 30 hari · '
        '<strong>%d</strong> dibatalkan.</p></section>'
        % (data.sesi_7_hari, data.sesi_30_hari, data.sesi_dibatalkan)
        + '<section class="admin-kartu"><h2>Perlu perhatian</h2>'
        '<ul class="admin-daftar-status">%s</ul></section>' % perhatian
        + '<section class="admin-kartu"><h2>Login perlu perhatian</h2>'
        '<p class="admin-meta">Maksimal 25 login ditampilkan. Daftar ini tidak memperbaiki atau mengaitkan akun otomatis.</p>'
        '<div class="admin-tabel-wrap"><table class="admin-tabel">'
        '<thead><tr><th>Alias login</th><th>Kondisi</th><th>Kandidat nama</th></tr></thead>'
        '<tbody>%s</tbody></table></div></section>' % login_bermasalah
        + '<section class="admin-kartu"><h2>Aktivitas sesi terbaru</h2>'
        '<p class="admin-meta">Maksimal 10 catatan administratif terbaru.</p>'
        '<div class="admin-tabel-wrap"><table class="admin-tabel">'
        '<thead><tr><th>Sesi</th><th>Siswa</th><th>Keluarga</th><th>Waktu</th><th>Status</th></tr></thead>'
        '<tbody>%s</tbody></table></div></section>' % aktivitas
    )


def _opsi(nilai: str, label: str, kini: str) -> str:
    return '<option value="%s"%s>%s</option>' % (
        _e(nilai), ' selected' if nilai == kini else "", _e(label)
    )


def _hidden_filter(filter_data: Mapping[str, str]) -> str:
    return "".join(
        '<input type="hidden" name="%s" value="%s">' % (_e(kunci), _e(nilai))
        for kunci, nilai in filter_data.items()
        if nilai
    )


def _pager(
    *,
    section: str,
    halaman: int,
    jumlah_halaman: int,
    total: int,
    filter_data: Mapping[str, str],
    via_post: bool,
    csrf: str = "",
) -> str:
    if jumlah_halaman <= 1:
        return '<p class="admin-meta">%d hasil.</p>' % total
    kontrol = []
    for target, label in ((halaman - 1, "Sebelumnya"), (halaman + 1, "Berikutnya")):
        if target < 1 or target > jumlah_halaman:
            continue
        if via_post:
            kontrol.append(
                '<form method="post" action="/admin">'
                '<input type="hidden" name="mode" value="cari">'
                '<input type="hidden" name="section" value="%s">%s'
                '<input type="hidden" name="csrf" value="%s">'
                '<input type="hidden" name="halaman" value="%d">'
                '<button type="submit">%s</button></form>'
                % (_e(section), _hidden_filter(filter_data), _e(csrf), target, _e(label))
            )
        else:
            query = {"section": section, "halaman": target}
            query.update({k: v for k, v in filter_data.items() if v})
            kontrol.append(
                '<a class="admin-tautan" href="/admin?%s">%s</a>'
                % (_e(urlencode(query)), _e(label))
            )
    return (
        '<div class="admin-pager"><span>Halaman %d dari %d · %d hasil</span><div class="admin-aksi-baca">%s</div></div>'
        % (halaman, jumlah_halaman, total, "".join(kontrol))
    )


def render_keluarga(
    data: Q.HalamanKeluarga, *, csrf: str = "", tampilkan_aksi: bool = True
) -> str:
    baris_semua = []
    for item in data.item:
        label = _e(item.pengguna or "Pemilik kosong")
        kelola = (
            '<a href="/admin?section=keluarga&amp;id=%s">%s</a>'
            % (_e(item.id_akun), 'Kelola akun' if tampilkan_aksi and item.kategori == 'orang_tua' else 'Lihat detail')
            if item.id_akun is not None else '—'
        )
        baris_semua.append(
            '<tr><td>%s</td><td>%s</td><td data-angka>%d</td><td data-angka>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (
                label,
                _e(LABEL_KATEGORI[item.kategori]),
                item.jumlah_siswa,
                item.jumlah_sesi,
                _waktu(item.aktivitas_terakhir),
                _badge_status(item.status),
                kelola,
            )
        )
    baris = "".join(baris_semua) or '<tr><td colspan="7" class="admin-kosong">Tidak ada keluarga yang cocok.</td></tr>'
    form = (
        '<section class="admin-kartu"><h2>Cari dan saring keluarga</h2>'
        '<form class="admin-form-cari" method="post" action="/admin">'
        '<input type="hidden" name="mode" value="cari"><input type="hidden" name="section" value="keluarga">'
        '<input type="hidden" name="csrf" value="%s">'
        '<label>Cari alias akun<input name="cari" maxlength="80" value="%s" autocomplete="off"></label>'
        '<label>Kepemilikan siswa<select name="memiliki_anak">%s%s%s</select></label>'
        '<label>Kondisi akses<select name="status">%s%s</select></label>'
        '<button class="admin-tombol" type="submit">Cari</button></form></section>'
        % (
            _e(csrf), _e(data.cari),
            _opsi("semua", "Semua", data.memiliki_anak),
            _opsi("ya", "Memiliki siswa", data.memiliki_anak),
            _opsi("tidak", "Belum memiliki siswa", data.memiliki_anak),
            _opsi("semua", "Semua", data.status),
            _opsi("perlu_perhatian", "Perlu perhatian", data.status),
        )
    )
    if not csrf:
        form = '<p class="admin-meta">Tampilan baca-saja. Masuk melalui formulir untuk mencari dan mengelola akun.</p>'
    filter_data = {
        "cari": data.cari,
        "memiliki_anak": data.memiliki_anak,
        "status": data.status,
    }
    return (
        form
        + (
            '<p><a class="admin-tautan" href="/admin/tinjau?aksi=account_teacher_create">Buat akun orang tua</a></p>'
            if tampilkan_aksi else ""
        )
        + '<section class="admin-kartu"><h2>Daftar keluarga</h2>'
        '<div class="admin-tabel-wrap"><table class="admin-tabel">'
        '<thead><tr><th>Akun/pemilik</th><th>Kategori</th><th>Siswa</th><th>Sesi</th><th>Aktivitas terakhir</th><th>Kondisi</th><th>Tindakan</th></tr></thead>'
        '<tbody>%s</tbody></table></div>%s</section>'
        % (
            baris,
            _pager(
                section="keluarga", halaman=data.halaman,
                jumlah_halaman=data.jumlah_halaman, total=data.total,
                filter_data=filter_data, via_post=bool(data.cari), csrf=csrf,
            ),
        )
    )


def render_siswa(
    data: Q.HalamanSiswa, keluarga: Sequence[Q.KeluargaRingkas], *, csrf: str = ""
) -> str:
    opsi_keluarga = _opsi("", "Semua keluarga", data.keluarga_id) + "".join(
        _opsi(item.id_akun or "", item.pengguna, data.keluarga_id)
        for item in keluarga if item.id_akun is not None
    )
    form = (
        '<section class="admin-kartu"><h2>Cari dan saring siswa</h2>'
        '<form class="admin-form-cari admin-form-siswa" method="post" action="/admin">'
        '<input type="hidden" name="mode" value="cari"><input type="hidden" name="section" value="siswa">'
        '<input type="hidden" name="csrf" value="%s">'
        '<label>Cari nama, login, atau keluarga<input name="cari" maxlength="80" value="%s" autocomplete="off"></label>'
        '<label>Profil parameter<select name="tingkat">%s%s</select></label>'
        '<label>Keluarga<select name="keluarga_id">%s</select></label>'
        '<label>Kondisi<select name="status">%s%s</select></label>'
        '<button class="admin-tombol" type="submit">Cari</button></form></section>'
        % (
            _e(csrf), _e(data.cari),
            _opsi("", "Semua profil", data.tingkat),
            "".join(_opsi(level, level, data.tingkat) for level in ("P3", "P4", "P5", "P6")),
            opsi_keluarga,
            _opsi("semua", "Semua", data.status),
            "".join(
                _opsi(kode, LABEL_STATUS[kode], data.status)
                for kode in (
                    "student_without_login", "owner_without_account", "owner_empty",
                    "legacy_login_unverified", "legacy_same_name_ambiguous",
                )
            ),
        )
    )
    baris = "".join(
        '<tr><td><a href="/admin?section=siswa&amp;id=%d">%s</a></td><td>%s</td>'
        '<td>%s</td><td>%s</td><td data-angka>%d</td><td>%s</td></tr>'
        % (
            item.id,
            _e(item.nama),
            _e(label_kelas_sekolah(item.kelas_sekolah)),
            _e(item.pemilik or "Pemilik kosong"),
            _e(item.login_pengguna or "Belum ada login eksplisit"),
            item.jumlah_sesi,
            _badge_status(item.status),
        )
        for item in data.item
    ) or '<tr><td colspan="6" class="admin-kosong">Tidak ada siswa yang cocok.</td></tr>'
    if not csrf:
        form = '<p class="admin-meta">Tampilan baca-saja. Masuk melalui formulir untuk mencari dan mengelola akun.</p>'
    filter_data = {
        "cari": data.cari,
        "tingkat": data.tingkat,
        "keluarga_id": data.keluarga_id,
        "status": data.status,
    }
    return (
        form
        + '<section class="admin-kartu"><h2>Daftar siswa</h2>'
        '<div class="admin-tabel-wrap"><table class="admin-tabel">'
        '<thead><tr><th>Siswa</th><th>Kelas sekolah</th><th>Keluarga</th><th>Login</th><th>Sesi</th><th>Kondisi</th></tr></thead>'
        '<tbody>%s</tbody></table></div>%s</section>'
        % (
            baris,
            _pager(
                section="siswa", halaman=data.halaman,
                jumlah_halaman=data.jumlah_halaman, total=data.total,
                filter_data=filter_data, via_post=bool(data.cari), csrf=csrf,
            ),
        )
    )


def render_detail_keluarga(
    data: Q.DetailKeluarga, *, tindakan: Optional[str] = None
) -> str:
    keluarga = data.keluarga
    siswa = data.siswa
    baris = "".join(
        '<tr><td><a href="/admin?section=siswa&amp;id=%d">%s</a></td>'
        '<td>%s</td><td data-angka>%d</td><td>%s</td></tr>'
        % (item.id, _e(item.nama), _e(label_kelas_sekolah(item.kelas_sekolah)), item.jumlah_sesi, _badge_status(item.status))
        for item in siswa.item
    ) or '<tr><td colspan="4" class="admin-kosong">Keluarga ini belum memiliki siswa.</td></tr>'
    if tindakan is None and keluarga.kategori == "orang_tua" and keluarga.id_akun:
        target = _e(keluarga.id_akun)
        tindakan = (
            '<p class="admin-aksi-baca">'
            '<a class="admin-tautan" href="/admin/tinjau?aksi=account_password_reset&amp;id=%s">Reset sandi</a>'
            '<a class="admin-tautan" href="/admin/tinjau?aksi=account_session_revoke&amp;id=%s">Keluarkan perangkat</a>'
            '<a class="admin-tautan admin-bahaya" href="/admin/tinjau?aksi=account_login_delete&amp;id=%s">Tinjau penghapusan login</a></p>'
            '<p class="admin-meta">Hanya akses login orang tua yang dihapus. Data siswa dan riwayat tetap tersimpan; akun login murid tidak ikut dihapus.</p>'
            % (target, target, target)
        )
    return (
        '<p><a href="/admin?section=keluarga">← Kembali ke daftar keluarga</a></p>'
        '<section class="admin-kartu"><h2>Identitas keluarga</h2><dl class="admin-rincian">'
        '<dt>Alias akun</dt><dd>%s</dd><dt>ID generasi</dt><dd>%s</dd>'
        '<dt>Kategori</dt><dd>%s</dd><dt>Jumlah siswa</dt><dd>%d</dd>'
        '<dt>Jumlah sesi</dt><dd>%d</dd><dt>Aktivitas terakhir</dt><dd>%s</dd>'
        '<dt>Kondisi</dt><dd>%s</dd></dl></section>'
        % (
            _e(keluarga.pengguna), _e(keluarga.id_akun or "Belum tersedia"),
            _e(LABEL_KATEGORI[keluarga.kategori]), keluarga.jumlah_siswa,
            keluarga.jumlah_sesi, _waktu(keluarga.aktivitas_terakhir),
            _badge_status(keluarga.status),
        )
        + tindakan
        + '<section class="admin-kartu"><h2>Siswa dalam keluarga</h2>'
        '<div class="admin-tabel-wrap"><table class="admin-tabel">'
        '<thead><tr><th>Siswa</th><th>Kelas sekolah</th><th>Sesi</th><th>Kondisi</th></tr></thead>'
        '<tbody>%s</tbody></table></div>%s</section>'
        % (
            baris,
            _pager(
                section="keluarga", halaman=siswa.halaman,
                jumlah_halaman=siswa.jumlah_halaman, total=siswa.total,
                filter_data={"id": keluarga.id_akun or ""}, via_post=False,
            ),
        )
    )


def render_detail_siswa(data: Q.DetailSiswa, *, tindakan: Optional[str] = None) -> str:
    siswa = data.siswa
    sesi = "".join(
        '<tr><td><a href="/sesi/%d">Sesi %d</a></td><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (
            item.id, item.id, _e('Profil ' + item.tingkat), _e(item.waktu_aktivitas),
            '<span class="admin-badge batal">Dibatalkan</span>'
            if item.dibatalkan else '<span class="admin-badge">Tercatat</span>',
        )
        for item in data.sesi_terbaru
    ) or '<tr><td colspan="4" class="admin-kosong">Belum ada sesi.</td></tr>'
    if tindakan is None:
        if siswa.login_id:
            login = (
                '<a class="admin-tautan" href="/admin/tinjau?aksi=account_password_reset&amp;id=%s">Reset sandi login</a>'
                '<a class="admin-tautan" href="/admin/tinjau?aksi=account_session_revoke&amp;id=%s">Keluarkan perangkat</a>'
                '<a class="admin-tautan admin-bahaya" href="/admin/tinjau?aksi=account_login_delete&amp;id=%s">Hapus login</a>'
                % (_e(siswa.login_id), _e(siswa.login_id), _e(siswa.login_id))
            )
        else:
            login = '<a class="admin-tautan" href="/admin/tinjau?aksi=student_login_create&amp;id=%d">Buat login murid</a>' % siswa.id
        tindakan = (
            '<p class="admin-aksi-baca"><a class="admin-tautan" '
            'href="/admin/tinjau?aksi=student_school_grade_update&amp;id=%d">Ubah kelas sekolah</a>%s</p>'
            % (siswa.id, login)
        )
    return (
        '<p><a href="/admin?section=siswa">← Kembali ke daftar siswa</a></p>'
        '<section class="admin-kartu"><h2>Identitas siswa</h2><dl class="admin-rincian">'
        '<dt>Nama panggilan</dt><dd>%s</dd><dt>ID siswa</dt><dd>%d</dd>'
        '<dt>Kelas sekolah</dt><dd>%s</dd><dt>Konteks latihan</dt><dd>Profil %s</dd>'
        '<dt>Keluarga</dt><dd>%s</dd>'
        '<dt>Login eksplisit</dt><dd>%s</dd><dt>Jumlah sesi</dt><dd>%d</dd>'
        '<dt>Kondisi</dt><dd>%s</dd></dl>'
        '<div class="admin-aksi-baca"><a class="admin-tautan" href="/anak/%d">Buka profil</a>'
        '<a class="admin-tautan" href="/laporan/%d">Buka laporan</a></div></section>'
        % (
            _e(siswa.nama), siswa.id, _e(label_kelas_sekolah(siswa.kelas_sekolah)), _e(siswa.tingkat),
            _e(siswa.pemilik or "Pemilik kosong"),
            _e(siswa.login_pengguna or "Belum ada login eksplisit"),
            siswa.jumlah_sesi, _badge_status(siswa.status), siswa.id, siswa.id,
        )
        + tindakan
        + '<section class="admin-kartu"><h2>Aktivitas sesi terbaru</h2>'
        '<p class="admin-meta">Kelas sekolah tidak menentukan kemampuan atau konteks soal lama. '
        'Data P3–P6 lama tidak dipakai untuk menebak kelas. '
        'Riwayat administratif saja; bukan status belajar atau kelulusan.</p>'
        '<div class="admin-tabel-wrap"><table class="admin-tabel">'
        '<thead><tr><th>Sesi</th><th>Profil parameter sesi</th><th>Waktu</th><th>Status</th></tr></thead>'
        '<tbody>%s</tbody></table></div></section>' % sesi
    )


def form_buat_keluarga(csrf: str, token: str) -> str:
    return (
        '<p><a href="/admin?section=keluarga">← Kembali ke daftar keluarga</a></p>'
        '<section class="admin-kartu"><h2>Buat akun orang tua</h2>'
        '<p class="admin-meta">Alias baru tidak boleh mengambil alih keluarga lama.</p>'
        '<form method="post" action="/admin/akun">'
        '<input type="hidden" name="aksi" value="account_teacher_create">'
        '<input type="hidden" name="csrf" value="%s">'
        '<input type="hidden" name="tinjauan" value="%s">'
        '<label>Alias akun<input name="alias" required maxlength="40" autocomplete="off"></label>'
        '<label>Sandi baru<input type="password" name="sandi_baru" required minlength="12" autocomplete="new-password"></label>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Buat akun orang tua</button>'
        '</form></section>' % (_e(csrf), _e(token))
    )


def form_tindakan_akun(
    pengguna: str, peran: str, csrf: str, tokens: Mapping[str, str],
    *, kembali: str = "/admin?section=keluarga", jumlah_siswa=None, jumlah_sesi=None,
) -> str:
    if peran not in ("guru", "murid"):
        return '<section class="admin-kartu admin-catatan"><p>Akun pengelola hanya dapat dibaca.</p></section>'
    target = _e(pengguna)
    bagian = []
    if "account_password_reset" in tokens:
        bagian.append(
            '<form method="post" action="/admin/akun"><h3>Setel ulang sandi</h3>'
            '<input type="hidden" name="aksi" value="account_password_reset">'
            '<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            '<label>Sandi baru untuk %s<input type="password" name="sandi_baru" minlength="%d" required autocomplete="new-password"></label>'
            '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
            '<button class="admin-tombol" type="submit">Setel ulang sandi</button></form>'
            % (_e(csrf), _e(tokens["account_password_reset"]), target, 8 if peran == "murid" else 12)
        )
    if "account_session_revoke" in tokens:
        bagian.append(
            '<form method="post" action="/admin/akun"><h3>Keluarkan dari semua perangkat</h3>'
            '<input type="hidden" name="aksi" value="account_session_revoke">'
            '<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
            '<label><input type="checkbox" name="konfirmasi" value="1" required> Saya memahami semua cookie akun ini langsung tidak berlaku.</label>'
            '<button class="admin-tombol" type="submit">Keluarkan perangkat</button></form>'
            % (_e(csrf), _e(tokens["account_session_revoke"]))
        )
    if "account_login_delete" in tokens:
        judul = 'Hapus akun login orang tua' if peran == 'guru' else 'Hapus login murid'
        konsekuensi = ('Akun login ' + pengguna + ' akan dihapus dan tidak dapat masuk lagi. '
                       'Data siswa dan riwayat tetap tersimpan.'
                       + (' Akun login murid tidak ikut dihapus.' if peran == 'guru' else ''))
        rekap = ('<p><strong>%d profil siswa</strong> dan <strong>%d sesi latihan</strong> tetap tersimpan. '
                 'Data tidak otomatis dipindahkan ke akun lain.</p>' % (jumlah_siswa, jumlah_sesi)
                 if peran == 'guru' and jumlah_siswa is not None and jumlah_sesi is not None else '')
        bagian.append(
            '<form method="post" action="/admin/akun" data-konfirmasi-login="%s"><h3>%s</h3>'
            '<p class="admin-meta">Target: <strong>%s</strong> · %s</p>'
            '<div class="admin-kartu admin-catatan"><p>%s</p>%s'
            '<p>Ini bukan penghapusan seluruh data keluarga atau pembersihan data dummy.</p></div>'
            '<input type="hidden" name="aksi" value="account_login_delete">'
            '<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
            '<label><input type="checkbox" name="konfirmasi" value="1" required> Saya memahami hanya login yang dihapus; data siswa dan riwayat tetap ada.</label>'
            '<a class="admin-tautan" href="%s">Batal, kembali ke akun</a> '
            '<button class="admin-tombol admin-bahaya" type="submit">%s</button></form>'
            % (_e(konsekuensi), judul, target, 'Orang Tua' if peran == 'guru' else 'Murid',
               _e(konsekuensi), rekap, _e(csrf), _e(tokens["account_login_delete"]), _e(kembali), judul)
        )
    return '<section class="admin-kartu admin-form-tindakan"><h2>Tindakan akun</h2>%s</section>' % "".join(bagian)


def form_kelas_sekolah(data: Q.DetailSiswa, csrf: str, token: str) -> str:
    """Aksi baru metadata, bukan form ubah level warisan."""
    return (
        '<section class="admin-kartu"><h2>Ubah kelas sekolah</h2>'
        '<p id="keterangan-kelas">%s</p>'
        '<form method="post" action="/admin/siswa">'
        '<input type="hidden" name="csrf" value="%s">'
        '<input type="hidden" name="tinjauan" value="%s">'
        '<input type="hidden" name="aksi" value="student_school_grade_update">'
        '<input type="hidden" name="revisi_profil" value="%d">'
        '<label for="admin-kelas-sekolah">Kelas sekolah (opsional)</label>'
        '<select id="admin-kelas-sekolah" name="kelas_sekolah" aria-describedby="keterangan-kelas">%s</select>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Simpan kelas sekolah</button>'
        '</form></section>'
    ) % (_e(learning_profile_ui.KETERANGAN_KELAS), _e(csrf), _e(token),
         data.siswa.revisi_profil, learning_profile_ui.opsi_kelas(data.siswa.kelas_sekolah))


def form_tindakan_siswa(data: Q.DetailSiswa, csrf: str, token_level: str, token_login: str = "") -> str:
    siswa = data.siswa
    level = "".join(
        '<option value="%s"%s>%s</option>' % (
            _e(nilai), ' selected' if nilai == siswa.tingkat else '', _e(nilai)
        ) for nilai in ("P3", "P4", "P5", "P6")
    )
    hasil = (
        '<section class="admin-kartu admin-form-tindakan"><h2>Tindakan siswa</h2>'
        '<form method="post" action="/admin/siswa">'
        '<input type="hidden" name="aksi" value="student_level_update">'
        '<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
        '<label>Profil parameter baru<select name="tingkat_baru">%s</select></label>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Ubah profil parameter warisan</button></form>'
        % (_e(csrf), _e(token_level), level)
    )
    if not token_level:
        hasil = '<section class="admin-kartu admin-form-tindakan"><h2>Tindakan siswa</h2>'
    if token_login:
        hasil += (
            '<form method="post" action="/admin/akun"><h3>Pulihkan login murid</h3>'
            '<input type="hidden" name="aksi" value="student_login_create">'
            '<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            '<label>Alias login<input name="alias" required maxlength="40" autocomplete="off"></label>'
            '<label>Sandi baru<input type="password" name="sandi_baru" required minlength="8" autocomplete="new-password"></label>'
            '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
            '<button class="admin-tombol" type="submit">Buat login murid</button></form>'
            % (_e(csrf), _e(token_login))
        )
    return hasil + '</section>'


def form_hapus_siswa(csrf, token):
    return (
        '<section class="admin-kartu"><h2>Hapus profil siswa kosong</h2>'
        '<p>Hanya profil tanpa riwayat atau referensi terlindungi yang boleh dihapus. Pemeriksaan diulang saat konfirmasi.</p>'
        '<form method="post" action="/admin/siswa"><input type="hidden" name="aksi" value="student_delete">'
        '<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<label><input type="checkbox" name="konfirmasi" value="1" required> Saya memahami login dan profil siswa kosong dihapus; tindakan ini tidak dapat dibatalkan.</label>'
        '<button class="admin-tombol admin-bahaya" type="submit">Hapus login dan profil siswa kosong</button></form></section>'
        % (_e(csrf), _e(token)))


def render_pendaftaran(status, *, csrf: str, token: str) -> str:
    checked = " checked" if status.dibuka else ""
    return (
        '<section class="admin-kartu"><h2>Status pendaftaran mandiri</h2>'
        '<p>Status saat ini: <strong>%s</strong>. Perubahan tidak memengaruhi login existing.</p>'
        '<form method="post" action="/admin/pendaftaran">'
        '<input type="hidden" name="aksi" value="registration_config_update">'
        '<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
        '<label><input type="checkbox" name="dibuka" value="1"%s> Buka pendaftaran baru</label>'
        '<label>Pesan saat ditutup<select name="pesan_kode">'
        '<option value="closed_standard"%s>Pendaftaran baru sedang ditutup</option>'
        '<option value="closed_maintenance"%s>Pendaftaran sementara ditutup untuk pemeliharaan</option>'
        '</select></label>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Simpan pengaturan</button>'
        '</form></section>' % (
            "Dibuka" if status.dibuka else "Ditutup", _e(csrf), _e(token), checked,
            ' selected' if status.pesan_kode == 'closed_standard' else '',
            ' selected' if status.pesan_kode == 'closed_maintenance' else '',
        )
    )


def render_bulk_awal(csrf: str, token: str) -> str:
    return (
        '<p><a class="admin-tautan" href="/admin/bulk/pilih?peran=guru">Kelola akun orang tua terpilih</a></p>'
        '<section class="admin-kartu"><h2>Buat akun orang tua massal</h2>'
        '<p class="admin-meta">CSV UTF-8 satu kolom <code>pengguna</code>; maksimal 100 akun dan 64 KiB. Tahap ini hanya meninjau alias, bukan membuat akun.</p>'
        '<p><a href="/admin/bulk/templat">Unduh templat CSV kosong</a></p>'
        '<form method="post" action="/admin/bulk/impor" enctype="multipart/form-data">'
        '<input type="hidden" name="aksi" value="bulk_teacher_create">'
        '<input type="hidden" name="csrf" value="%s">'
        '<input type="hidden" name="tinjauan" value="%s">'
        '<label>File CSV<input type="file" name="csv" accept=".csv,text/csv" required></label>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Tinjau batch</button>'
        '</form></section>' % (_e(csrf), _e(token))
    )


def render_bulk_batch(batch, hasil, csrf, tokens, aliases):
    label = {
        'pending': 'Belum diproses', 'succeeded': 'Berhasil', 'conflict': 'Konflik — tinjau ulang',
        'uncertain': 'Tak pasti — perlu pemeriksaan', 'cancelled': 'Dibatalkan',
        'failed_before_commit': 'Gagal sebelum tulis', 'ready': 'Siap ditinjau',
        'running': 'Sedang diproses', 'partial': 'Sebagian selesai',
        'stopped': 'Dihentikan', 'attention': 'Perlu pemeriksaan',
    }
    aksi = {'account_teacher_create': 'Buat orang tua', 'account_password_reset': 'Reset sandi unik',
            'account_session_revoke': 'Keluarkan perangkat'}[batch.aksi]
    fresh = {x.item_id: x.credential_sekali for x in hasil if x.credential_sekali}
    hitung = {}
    for item in batch.item:
        hitung[item.status] = hitung.get(item.status, 0) + 1
    ringkas = ' · '.join('%d %s' % (n, label.get(k, k).lower()) for k, n in hitung.items())
    baris = []
    belum_diserahkan = []
    for nomor, item in enumerate(batch.item, 1):
        # Janitor boleh membuang draft selesai sebelum respons fresh dirender.
        # Pasangan akses fresh tetap memakai alias akun saat ini via ID hasil;
        # GET/replay fallback tetap hanya metadata ID tanpa alias.
        alias = (item.alias_valid or aliases.get(item.hasil_id or item.target_id, item.target_id)
                 if batch.draft_tersedia or item.item_id in fresh else item.hasil_id or item.target_id)
        sandi = fresh.get(item.item_id)
        akses = 'Tidak ada sandi baru untuk tindakan ini.'
        if batch.aksi != 'account_session_revoke':
            akses = 'Belum dibuat.' if item.status == 'pending' else 'Akses perlu diserahkan ulang lewat reset individual bila hasil pertama hilang.'
            if item.credential_status == 'confirmed':
                akses = 'Penyerahan telah dikonfirmasi pengelola.'
            elif item.status == 'succeeded':
                belum_diserahkan.append(item.item_id)
            if sandi:
                akses = '<input type="password" readonly value="%s" aria-label="Sandi baru"><p>Penyerahan belum dikonfirmasi.</p>' % _e(sandi)
        tautan = ('<a href="/admin/tinjau?aksi=account_password_reset&amp;id=%s">Tinjau reset individual</a>'
                  % _e(item.hasil_id or item.target_id)) if (item.status == 'succeeded' and not sandi
                    and item.credential_status == 'unconfirmed') else ''
        baris.append('<tr><td>%d. %s</td><td>%s</td><td>%s %s</td></tr>' % (
            nomor, _e(alias), _e(label.get(item.status, item.status)), akses, tautan))
    isi = ('<section class="admin-kartu"><h2>%s · %d akun</h2><p>Status: <strong>%s</strong>.</p>'
        '<p class="admin-meta">%s</p>'
        '<p>Semua target sudah dibekukan. Sandi acak hanya pada respons POST pertama; '
        'tidak disimpan untuk dibaca ulang. Kirim akses secara privat. Sukses bukan bukti akses telah diserahkan.</p>'
        '<p>Reset mencabut sesi lama. Cabut sesi hanya mengeluarkan cookie, bukan memblokir login baru '
        'atau Basic dengan sandi yang masih sah. Data siswa dan riwayat tetap ada.</p>'
        '<div class="admin-tabel-wrap"><table class="admin-tabel"><thead><tr><th>Akun</th><th>Hasil</th><th>Akses</th></tr></thead>'
        '<tbody>%s</tbody></table></div>'
        '<p><a href="/admin/bulk/hasil?id=%s">Lihat status tanpa sandi</a></p>'
        % (_e(aksi), len(batch.item), _e(label.get(batch.status, batch.status)), _e(ringkas), ''.join(baris), _e(batch.batch_id)))
    def form(jalur, token, teks, dampak, tambahan=''):
        return ('<form method="post" action="/admin/bulk/%s">'
            '<input type="hidden" name="batch_id" value="%s"><input type="hidden" name="csrf" value="%s">'
            '<input type="hidden" name="tinjauan" value="%s">%s'
            '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
            '<label><input type="checkbox" name="konfirmasi" value="1" required> %s</label>'
            '<button class="admin-tombol" type="submit">%s</button></form>'
            % (jalur, _e(batch.batch_id), _e(csrf), _e(token), tambahan, _e(dampak), _e(teks)))
    if not batch.draft_tersedia:
        isi += '<p class="admin-catatan">Draft alias sudah tidak tersedia. Hasil ini berasal dari metadata tersimpan tanpa sandi. Item yang belum pasti tidak dijalankan ulang otomatis.</p>'
    if batch.boleh_proses:
        tombol = 'Pulihkan kelompok yang sama' if batch.kelompok_aktif_id else 'Proses kelompok berikutnya'
        isi += form('proses', tokens['process'], tombol,
            'Saya menyetujui tindakan pada maksimal 10 akun berikutnya dan dampak pencabutan sesi; hasil selesai tidak dibatalkan.')
    if batch.status in ('ready', 'partial', 'attention'):
        isi += form('hentikan', tokens['stop'], 'Hentikan item yang belum mulai',
            'Item yang belum mulai dibatalkan; perubahan yang sudah selesai tetap tercatat.')
    if belum_diserahkan:
        isi += form('serahkan', tokens['handover'], 'Konfirmasi akses telah diserahkan',
            'Saya sudah menyerahkan akses akun berhasil yang belum dikonfirmasi melalui kanal privat.',
            '<input type="hidden" name="item_ids" value="%s">' % _e(','.join(belum_diserahkan)))
    if batch.status == 'running':
        isi += '<p role="alert">Kelompok belum memiliki hasil final. Pemulihan hanya menggunakan identitas kelompok yang sama dan memeriksa receipt; jangan membuat batch pengganti.</p>'
    if batch.status == 'attention':
        isi += '<p role="alert">Hasil tak pasti ditahan. Jangan mengulang batch; pemeriksaan receipt oleh operator diperlukan.</p>'
    return isi + '</section>'


def _nav_riwayat():
    return ('<p class="admin-aksi-baca"><a class="admin-tautan" href="/admin?section=riwayat">Tindakan akun dan siswa</a>'
            '<a class="admin-tautan" href="/admin?section=riwayat&amp;sumber=batch">Riwayat batch</a>'
            '<a class="admin-tautan" href="/admin?section=riwayat&amp;sumber=ai">Riwayat AI</a></p>')


def render_riwayat(data, *, filter_data=None) -> str:
    from datetime import datetime, timedelta, timezone
    filter_data = {k: v for k, v in (filter_data or {}).items()
                   if k in ('actor_id', 'aksi', 'status', 'mulai', 'selesai')}
    label = {
        "account_password_reset": "Reset sandi",
        "account_session_revoke": "Cabut sesi",
        "account_login_delete": "Hapus login",
        "account_teacher_create": "Buat orang tua",
        "student_login_create": "Buat login murid",
        "student_level_update": "Ubah profil parameter warisan",
        "student_school_grade_update": "Ubah kelas sekolah", "student_delete": "Hapus siswa kosong",
        "registration_config_update": "Ubah pendaftaran",
    }
    baris = "".join(
        '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            _e(datetime.fromtimestamp(item.dibuat, timezone(timedelta(hours=7))).strftime('%d/%m/%Y %H:%M WIB')),
            _e(item.actor_id), _e(label.get(item.aksi, item.aksi)),
            _e(item.target_id), _e(item.status),
        ) for item in data.item
    ) or '<tr><td colspan="5" class="admin-kosong">Belum ada tindakan admin.</td></tr>'
    return (
        _nav_riwayat() + '<section class="admin-kartu"><h2>Riwayat tindakan</h2>'
        '<p class="admin-meta">Riwayat dimulai saat fitur aktif; bukan semua aktivitas belajar. Tidak ada kejadian lama yang direka ulang.</p>'
        '<form method="get" action="/admin" class="admin-form-cari">'
        '<input type="hidden" name="section" value="riwayat">'
        '<label>Mulai (WIB)<input type="date" name="mulai" value="%s"></label>'
        '<label>Sampai (WIB)<input type="date" name="selesai" value="%s"></label>'
        '<label>ID pengelola<input name="actor_id" value="%s" maxlength="80"></label>'
        '<label>Aksi<select name="aksi">%s</select></label>'
        '<button class="admin-tombol">Saring riwayat</button></form>'
        '<div class="admin-tabel-wrap"><table class="admin-tabel"><thead><tr>'
        '<th>Waktu</th><th>Actor</th><th>Aksi</th><th>Target</th><th>Status</th>'
        '</tr></thead><tbody>%s</tbody></table></div>'
        '%s</section>'
        % (_e(filter_data.get('mulai', '')), _e(filter_data.get('selesai', '')),
           _e(filter_data.get('actor_id', '')),
           _opsi('', 'Semua aksi', filter_data.get('aksi', '')) + ''.join(
               _opsi(k, v, filter_data.get('aksi', '')) for k, v in label.items()),
           baris, _pager(section='riwayat', halaman=data.halaman,
               jumlah_halaman=data.jumlah_halaman, total=data.total,
               filter_data=filter_data, via_post=False))
    )


def render_riwayat_ai(data, *, filter_data=None):
    from datetime import datetime, timedelta, timezone
    filter_data = {k: v for k, v in (filter_data or {}).items()
                   if k in ('actor_id', 'aksi', 'mulai', 'selesai')}
    label = {'ai_settings_update': 'Ubah pengaturan AI', 'ai_synthetic_test': 'Tes sintetis AI'}
    baris = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        _e(datetime.fromtimestamp(x.dibuat, timezone(timedelta(hours=7))).strftime('%d/%m/%Y %H:%M WIB')),
        _e(x.actor_id or 'Tidak tercatat (sebelum metadata)'), _e(label[x.aksi]), _e(x.status),
        _e(x.operasi_id or ('Revisi %s (sebelum metadata operasi)' % x.revisi if x.revisi else 'Sebelum metadata operasi')),
    ) for x in data.item) or '<tr><td colspan="5">Belum ada riwayat AI.</td></tr>'
    return (
        _nav_riwayat() + '<section class="admin-kartu"><h2>Riwayat dari penyimpanan AI</h2>'
        '<p>Pengaturan dikelompokkan per operasi atau revisi. Identitas tes lama yang belum tercatat tidak ditebak.</p>'
        '<form method="get" action="/admin" class="admin-form-cari">'
        '<input type="hidden" name="section" value="riwayat"><input type="hidden" name="sumber" value="ai">'
        '<label>Mulai (WIB)<input type="date" name="mulai" value="%s"></label>'
        '<label>Sampai (WIB)<input type="date" name="selesai" value="%s"></label>'
        '<label>ID pengelola<input name="actor_id" maxlength="80" value="%s"></label>'
        '<label>Aksi<select name="aksi">%s</select></label><button class="admin-tombol">Saring riwayat</button></form>'
        '<div class="admin-tabel-wrap"><table class="admin-tabel"><thead><tr><th>Waktu</th><th>Actor</th><th>Aksi</th><th>Status</th><th>Referensi</th></tr></thead>'
        '<tbody>%s</tbody></table></div>%s</section>'
        % (_e(filter_data.get('mulai', '')), _e(filter_data.get('selesai', '')), _e(filter_data.get('actor_id', '')),
           _opsi('', 'Semua aksi', filter_data.get('aksi', '')) + ''.join(
               _opsi(k, v, filter_data.get('aksi', '')) for k, v in label.items()), baris,
           _pager(section='riwayat', halaman=data.halaman, total=data.total,
               jumlah_halaman=data.jumlah_halaman,
               filter_data=dict(filter_data, sumber='ai'), via_post=False)))


def _label_status_batch(status):
    return {'pending': 'Belum diproses', 'succeeded': 'Berhasil', 'failed_before_commit': 'Gagal sebelum tulis',
            'conflict': 'Konflik', 'uncertain': 'Belum pasti', 'cancelled': 'Dibatalkan',
            'ready': 'Siap', 'running': 'Sedang diproses', 'partial': 'Sebagian selesai',
            'stopped': 'Dihentikan', 'attention': 'Perlu pemeriksaan', 'completed': 'Selesai'}.get(status, status)


def _waktu_audit_batch(epoch):
    from datetime import datetime, timedelta, timezone
    return datetime.fromtimestamp(epoch, timezone(timedelta(hours=7))).strftime('%d/%m/%Y %H:%M WIB')


def render_audit_batch(data, *, filter_data=None):
    filters = {k: v for k, v in (filter_data or {}).items()
               if k in ('actor_id', 'aksi', 'status', 'mulai', 'selesai')}
    baris = ''.join('<tr><td><a href="/admin?section=riwayat&amp;sumber=batch&amp;id=%s">%s</a></td>'
        '<td>%s</td><td>%s</td><td>%d</td><td>%s</td><td>%s</td></tr>' % (
            _e(x.batch_id), _e(x.batch_id), _e(x.actor_id),
            _e({'account_teacher_create': 'Buat orang tua', 'account_password_reset': 'Reset sandi',
                'account_session_revoke': 'Cabut sesi'}.get(x.aksi, x.aksi)), x.jumlah_total,
            _e(' · '.join('%d %s' % (n, _label_status_batch(status)) for status, n in x.jumlah_status)),
            _e(_waktu_audit_batch(x.dibuat))) for x in data.item)
    baris = baris or '<tr><td colspan="6">Belum ada batch.</td></tr>'
    form = ('<form method="get" action="/admin" class="admin-form-cari">'
        '<input type="hidden" name="section" value="riwayat"><input type="hidden" name="sumber" value="batch">'
        '<label>ID pengelola<input name="actor_id" maxlength="80" value="%s"></label>'
        '<label>Mulai WIB<input type="date" name="mulai" value="%s"></label>'
        '<label>Sampai WIB<input type="date" name="selesai" value="%s"></label>'
        '<label>Aksi<select name="aksi">%s</select></label>'
        '<label>Status<select name="status">%s</select></label>'
        '<button class="admin-tombol">Saring batch</button></form>'
        % (_e(filters.get('actor_id', '')), _e(filters.get('mulai', '')), _e(filters.get('selesai', '')),
           _opsi('', 'Semua aksi', filters.get('aksi', '')) + ''.join(_opsi(k, v, filters.get('aksi', ''))
               for k, v in (('account_teacher_create', 'Buat orang tua'), ('account_password_reset', 'Reset sandi'), ('account_session_revoke', 'Cabut sesi'))),
           _opsi('', 'Semua status', filters.get('status', '')) + ''.join(_opsi(k, _label_status_batch(k), filters.get('status', ''))
               for k in ('ready', 'running', 'partial', 'stopped', 'succeeded', 'attention'))))
    return (_nav_riwayat() + '<section class="admin-kartu"><h2>Riwayat batch tersimpan</h2>'
        '<p>Metadata operasi tanpa alias, sandi, atau isi draft. Satu batch dapat memiliki beberapa kelompok dan hasil parsial.</p>'
        + form + '<div class="admin-tabel-wrap"><table class="admin-tabel"><thead><tr><th>Batch</th><th>Actor</th>'
        '<th>Aksi</th><th>Target</th><th>Hasil</th><th>Waktu</th></tr></thead><tbody>' + baris + '</tbody></table></div>'
        + _pager(section='riwayat', halaman=data.halaman, jumlah_halaman=data.jumlah_halaman,
                 total=data.total, filter_data=dict(filters, sumber='batch'), via_post=False) + '</section>')


def render_audit_batch_detail(data):
    batch = data.batch
    item = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        _e(x.item_id), _e(x.operasi_id), _e(x.hasil_id or x.target_id), _e(_label_status_batch(x.status)),
        _e({'confirmed': 'Sudah dikonfirmasi (confirmed)', 'unconfirmed': 'Belum dikonfirmasi',
            'not_applicable': 'Tidak berlaku'}.get(x.credential_status, x.credential_status))
    ) for x in data.item)
    kelompok = ''.join('<li>%s · %s · %d item: %s</li>' % (
        _e(x.kelompok_id), _e(_label_status_batch(x.status)), len(x.item_ids), _e(', '.join(x.item_ids))
    ) for x in data.kelompok) or '<li>Belum ada kelompok.</li>'
    penyerahan = ''.join('<li>%s · %s · %d item · %s</li>' % (
        _e(x.operasi_id), _e(x.actor_id), x.jumlah, _e(_waktu_audit_batch(x.dibuat))
    ) for x in data.penyerahan) or '<li>Belum ada konfirmasi penyerahan.</li>'
    return (_nav_riwayat() + '<section class="admin-kartu"><h2>Metadata batch %s</h2>'
        '<p>Actor: %s · Aksi: %s · Status: %s · %d target.</p>'
        '<p>Tampilan audit hanya-baca; bukan akses untuk mengambil alih draft sesi lain.</p>'
        '<div class="admin-tabel-wrap"><table class="admin-tabel"><thead><tr><th>Item</th><th>Operasi</th>'
        '<th>Target/hasil</th><th>Status</th><th>Penyerahan</th></tr></thead><tbody>%s</tbody></table></div>'
        '<h3>Kelompok</h3><ul>%s</ul><h3>Konfirmasi penyerahan</h3><ul>%s</ul></section>'
        % (_e(batch.batch_id), _e(batch.actor_id), _e(batch.aksi), _e(_label_status_batch(batch.status)), batch.jumlah_total,
           item, kelompok, penyerahan))


def render_hasil_credential(alias: str, sandi: str) -> str:
    return (
        '<section class="admin-kartu admin-catatan"><h2>Simpan akses sekarang</h2>'
        '<p>Sandi ini hanya ditampilkan pada respons ini dan tidak dapat dibaca ulang.</p>'
        '<dl class="admin-rincian"><dt>Alias</dt><dd>%s</dd>'
        '<dt>Sandi baru</dt><dd><input type="password" readonly value="%s" aria-label="Sandi baru"></dd></dl>'
        '<p><a class="admin-tautan" href="/admin?section=keluarga">Selesai</a></p></section>'
        % (_e(alias), _e(sandi))
    )
