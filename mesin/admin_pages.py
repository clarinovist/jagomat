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
import admin_labels as L
from admin_antrean_pages import AntreanAdmin, SinyalNav, render_antrean
from admin_ikon import ikon
from admin_labels import LABEL_STATUS
from admin_komponen import badge_status as _badge_status, e as _e, hidden_filter as _hidden_filter, opsi as _opsi, pager as _pager, pisah_kepala_cari as _pisah_kepala_cari, waktu as _waktu
from admin_daftar_pages import render_keluarga, render_siswa  # noqa: F401 (API publik admin_pages)
from admin_riwayat_pages import nav_riwayat, render_audit_batch, render_riwayat, render_riwayat_ai  # noqa: F401 (API publik admin_pages)
import brand
from admin_style import GAYA_ADMIN
import design_tokens as T
import learning_profile_ui
from learning_profile import label_kelas_sekolah


SECTION = (
    ("ringkasan", "Ringkasan", "/admin"),
    ("perhatian", "Perlu ditangani", "/admin?section=perhatian"),
    ("keluarga", "Keluarga", "/admin?section=keluarga"),
    ("siswa", "Siswa", "/admin?section=siswa"),
    ("pendaftaran", "Pendaftaran", "/admin?section=pendaftaran"),
    ("langganan", "Langganan & invoice", "/admin?section=langganan"),
    ("kpi", "KPI uji coba", "/admin?section=kpi"),
    ("riset", "Riset konsumen", "/admin/riset"),
    ("operasional", "Operasional", "/admin?section=operasional"),
    ("ai", "AI", "/admin/ai"),
    ("riwayat", "Riwayat admin", "/admin?section=riwayat"),
)
GRUP_SECTION = (
    ("Pusat kendali", ("ringkasan",)),
    ("Pengguna", ("keluarga", "siswa")),
    ("Layanan", ("pendaftaran", "langganan")),
    ("Analitik", ("kpi", "riset")),
    ("Sistem", ("operasional", "ai", "riwayat")),
)
SECTION_LOKAL = frozenset(item[0] for item in SECTION if item[0] != "ai")
_PANAH_MENU = (
    '<svg class="admin-panah" aria-hidden="true" focusable="false" width="12" height="12" viewBox="0 0 12 12" '
    'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M2.5 4.5 6 8l3.5-3.5"/></svg>'
)
SKRIP_KONFIRMASI_LOGIN = """document.querySelectorAll('form[data-konfirmasi-login],form[data-konfirmasi]').forEach(function(f){f.addEventListener('submit',function(e){if(!window.confirm(f.dataset.konfirmasiLogin||f.dataset.konfirmasi)){e.preventDefault();}});});"""

LABEL_KATEGORI = {
    "orang_tua": "Orang Tua",
    "pengelola": "Pengelola",
    "pemilik_tanpa_akun": "Pemilik tanpa akun",
    "pemilik_kosong": "Pemilik kosong",
}


def _judul_section(section: str) -> Tuple[str, str]:
    if section == "keluarga":
        return "Keluarga", "Daftar akun orang tua dan kepemilikan siswa."
    if section == "siswa":
        return "Siswa", "Identitas administratif, kelas, keluarga, dan status login."
    if section == "pendaftaran":
        return "Pendaftaran", "Status pengaturan pendaftaran mandiri."
    if section == "riwayat":
        return "Riwayat admin", "Tindakan pengelola yang tercatat sejak fitur diaktifkan."
    if section == "riset":
        return "Riset konsumen", "Data wawancara eksploratif anonim untuk keputusan produk."
    judul, subjudul = {
        'ringkasan': ('Ringkasan', L.hari_ini()),
        'perhatian': ('Perlu ditangani', 'Periksa hasil operasi yang memerlukan keputusan.'),
        'langganan': ('Langganan', 'Catatan langganan dan akses keluarga.'),
        'operasional': ('Operasional', 'Kesiapan layanan dan pengaturan operasional.'),
        'kpi': ('KPI uji coba', 'Angka agregat untuk memahami penggunaan, bukan menilai anak.'),
        'ai': ('Pengaturan AI', 'Kesiapan, batas biaya, dan pemakaian panggilan Jagomat.'),
    }.get(section, ('Ringkasan', L.hari_ini()))
    return judul, subjudul


def _badge_nav(sinyal: Optional[SinyalNav], sid: str) -> str:
    if sinyal is None:
        return ""
    if sid == "ringkasan" and sinyal.total:
        return ('<span class="admin-nav-badge">%d<span class="admin-sr"> hal menunggu keputusan</span></span>'
                % sinyal.total)
    if sid == "operasional" and sinyal.operasional_perhatian:
        return '<span class="admin-nav-titik" role="img" aria-label="Perlu perhatian"></span>'
    return ""


def _tautan_nav(sid: str, label: str, jalur: str, aktif: bool, sinyal: Optional[SinyalNav]) -> str:
    return '<li><a href="%s"%s>%s<span class="admin-nav-label-menu">%s</span>%s</a></li>' % (
        _e(jalur), ' aria-current="page"' if aktif else "", ikon(sid), _e(label), _badge_nav(sinyal, sid))


def _nav(section: str, sinyal: Optional[SinyalNav] = None) -> str:
    section = 'ringkasan' if section == 'perhatian' else section
    section_data = {sid: (label, jalur) for sid, label, jalur in SECTION}
    grup = []
    for label_grup, daftar_section in GRUP_SECTION:
        tautan = "".join(
            _tautan_nav(sid, section_data[sid][0], section_data[sid][1], sid == section, sinyal)
            for sid in daftar_section
        )
        if label_grup == "Pusat kendali":
            grup.append('<li class="admin-nav-utama"><ul class="admin-nav-pilihan" '
                        'aria-label="Menu utama">%s</ul></li>' % tautan)
        else:
            grup.append('<li class="admin-nav-grup"><p class="admin-nav-label">%s</p>'
                        '<ul class="admin-nav-anak" aria-label="%s">%s</ul></li>'
                        % (_e(label_grup), _e(label_grup), tautan))
    return '<ul class="admin-nav-daftar">%s</ul>' % "".join(grup)


def _badge_mendesak(sinyal: Optional[SinyalNav]) -> str:
    if sinyal is None or not sinyal.mendesak:
        return ""
    return ('<span class="admin-nav-badge admin-nav-badge-mendesak">%d<span class="admin-sr"> item mendesak</span></span>'
            % sinyal.mendesak)


def _label_section(section: str) -> str:
    return next(label for sid, label, _jalur in SECTION if sid == section)


def halaman_admin(
    section: str,
    isi: str,
    *,
    pengguna: str,
    judul: Optional[str] = None,
    subjudul: Optional[str] = None,
    skrip_sandi: str = "",
    sinyal: Optional[SinyalNav] = None,
    aksi_header: str = "",
    tema: str = "sistem",
    csrf_tema: str = "",
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
    if tema not in ("sistem", "terang", "gelap"):
        tema = "sistem"
    tema_label = {"sistem": "Sistem", "terang": "Terang", "gelap": "Gelap"}
    pilihan_tema = "".join(
        '<button type="submit" name="tema" value="%s"%s>%s</button>' % (
            nilai, ' aria-pressed="true"' if nilai == tema else "", label,
        )
        for nilai, label in tema_label.items()
    )
    form_tema = (
        '<form class="admin-tema" method="post" action="/admin/tema">'
        '<span>Tampilan</span><div class="admin-tema-pilihan">%s</div>'
        '<input type="hidden" name="token_tema" value="%s"></form>'
        % (pilihan_tema, _e(csrf_tema))
        if csrf_tema else ""
    )
    judul_bawaan, sub_bawaan = _judul_section(section)
    judul = judul_bawaan if judul is None else judul
    subjudul = sub_bawaan if subjudul is None else subjudul
    isi, pencarian = _pisah_kepala_cari(isi)
    if aksi_header or pencarian:
        blok_aksi = f'<div class="admin-aksi-header">{aksi_header}</div>' if aksi_header else ""
        kepala = (f'<header class="admin-kepala admin-kepala-aksi"><div><h1 id="judul-admin">{_e(judul)}</h1>'
                  f'<p class="admin-sub">{_e(subjudul)}</p></div>{pencarian}{blok_aksi}</header>')
    else:
        kepala = f'<header class="admin-kepala"><h1 id="judul-admin">{_e(judul)}</h1><p class="admin-sub">{_e(subjudul)}</p></header>'
    dokumen = f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta name="referrer" content="no-referrer">
<title>{_e(judul)} · {_e(T.NAMA_PRODUK)}</title>
{brand.tag_kepala(cetak=True)}
<style>{GAYA_ADMIN}</style></head>
<body class="admin-readonly" data-tema="{tema}"><a class="admin-lompat" href="#konten-admin">Lewati navigasi</a>
<div class="admin-bungkus"><div class="admin-layout"><aside class="admin-sidebar">
<a class="admin-brand" href="/admin">{brand.mark('topbar')}
<span><strong>{_e(T.NAMA_PRODUK)}</strong><small>Panel Pengelola</small></span></a>
<nav class="admin-nav admin-menu" aria-label="Bagian panel pengelola">{_nav(section, sinyal)}</nav>
</aside>
<section class="admin-utama"><header class="admin-topbar">
<a class="admin-brand admin-brand-mobile" href="/admin">{brand.mark('topbar')}<strong>{_e(T.NAMA_PRODUK)}</strong></a>
<details class="admin-nav-mobile"><summary><span>Menu pengelola</span><strong>{_e(_label_section(section))}</strong>{_badge_mendesak(sinyal)}</summary>
<nav class="admin-menu" aria-label="Bagian panel pengelola seluler">{_nav(section, sinyal)}</nav></details>
<details class="menu-pengguna"><summary><span class="admin-identitas"><span class="admin-peran">Pengelola</span><span class="admin-nama">{_e(pengguna)}</span></span>{_PANAH_MENU}</summary>
<div class="menu-isi">{form_tema}<a href="/akun?section=akun">Ganti sandi</a>
<form method="post" action="/keluar"><button type="submit">Keluar</button></form></div></details></header>
{kepala}
<main id="konten-admin" tabindex="-1" aria-labelledby="judul-admin">{isi}</main>
<footer class="admin-footer">Tampilan privat · Data operasional, bukan penilaian kemampuan anak.</footer>
</section></div></div>{'<script>' + skrip_sandi + '</script>' if skrip_sandi else ''}</body></html>"""
    return dokumen.encode("utf-8")


NADA_LAYANAN = frozenset(("baik", "netral", "perhatian"))


def _status_layanan(nilai):
    """Terima teks atau pasangan (teks, nada); nada asing jatuh ke netral."""
    teks, nada = nilai if isinstance(nilai, tuple) else (nilai, "netral")
    teks = str(teks)
    return teks[:1].upper() + teks[1:], nada if nada in NADA_LAYANAN else "netral"


def _kartu_layanan(status_layanan) -> str:
    kartu = []
    for label, nilai in (status_layanan or {"Status layanan": "belum tersedia"}).items():
        teks, nada = _status_layanan(nilai)
        kartu.append(
            '<div class="admin-layanan-kartu admin-layanan-%s"><dt>%s</dt>'
            '<dd><span class="admin-titik" aria-hidden="true"></span>%s</dd></div>'
            % (nada, _e(label), _e(teks))
        )
    return "".join(kartu)


def _aktivitas_ringkasan(items):
    """Kelompok berurutan, tanpa menyortir atau mengubah makna catatan sesi."""
    kelompok = []
    for item in items[:10]:
        dt = L.waktu(item.waktu_aktivitas)
        kunci = (item.siswa_id, dt.date() if dt else item.sesi_id, item.dibatalkan)
        if kelompok and kelompok[-1][0] == kunci:
            kelompok[-1][1].append(item)
        else:
            kelompok.append((kunci, [item]))
    baris = []
    for _kunci, sesi in kelompok:
        item = sesi[0]
        tautan = ' · '.join('<a href="/sesi/%d">Sesi %d</a>' % (s.sesi_id, s.sesi_id) for s in sesi)
        label = '%d sesi: ' % len(sesi) if len(sesi) > 1 else ''
        rentang = _waktu(sesi[-1].waktu_aktivitas)
        if len(sesi) > 1:
            rentang += ' – ' + _waktu(item.waktu_aktivitas)
        pil = ('<span class="admin-pil admin-pil-batal">Dibatalkan</span>' if item.dibatalkan
               else '<span class="admin-pil">Tercatat</span>')
        baris.append(
            '<li class="admin-aktivitas-baris"><div class="admin-aktivitas-isi">'
            '<span class="admin-aktivitas-judul-baris"><a class="admin-aktivitas-judul" href="/anak/%d?section=riwayat">%s</a> · %s%s</span>'
            '<span class="admin-meta">%s</span></div>'
            '<span class="admin-aktivitas-waktu">%s</span>%s</li>' % (
                item.siswa_id, _e(item.nama_siswa), label, tautan,
                _e('Keluarga ' + item.pemilik if item.pemilik else 'Pemilik kosong'), rentang, pil))
    return ''.join(baris) or '<li class="admin-kosong"><strong>Belum ada aktivitas sesi.</strong><br>Catatan muncul setelah sesi pertama dibuat.</li>'


def render_ringkasan(
    data: Q.RingkasanAdmin, *, status_layanan: Optional[Mapping[str, object]] = None,
    antrean: Optional[AntreanAdmin] = None,
) -> str:
    """Hierarki keputusan dengan data proyeksi; tidak mengklaim layanan online."""
    stat = "".join(
        '<div><dt>%s</dt><dd>%d</dd></div>' % (_e(label), jumlah)
        for jumlah, label in (
            (data.jumlah_keluarga, "Akun orang tua"),
            (data.jumlah_siswa, "Siswa terdaftar"),
            (data.jumlah_login_murid, "Login murid"),
            (data.sesi_7_hari, "Sesi 7 hari terakhir"),
        )
    )
    aktivitas = _aktivitas_ringkasan(data.aktivitas_terbaru)
    login_detail = ""
    if data.login_bermasalah:
        baris = "".join('<li><strong>%s</strong><span>%s · %d kandidat nama</span></li>' % (
            _e(item.pengguna), _e(LABEL_STATUS.get(item.status, "Perlu ditinjau")), item.jumlah_kandidat)
            for item in data.login_bermasalah)
        login_detail = (
            '<details class="admin-kartu admin-login-detail" id="login-perlu-perhatian">'
            '<summary>Login perlu perhatian</summary>'
            '<p class="admin-meta">Maksimal 25 login ditampilkan. Daftar ini tidak memperbaiki atau mengaitkan akun otomatis.</p>'
            '<ul>%s</ul></details>' % baris
        )
    return (
        '<div class="admin-ringkasan">'
        + render_antrean(antrean if antrean is not None else AntreanAdmin())
        + '<section class="admin-layanan" aria-labelledby="judul-layanan"><header class="admin-seksi-kepala">'
        '<h2 id="judul-layanan">Kondisi layanan</h2>'
        '<span class="admin-meta">Konfigurasi bukan jaminan provider sedang online. '
        'Bukti backup tidak menyatakan jadwal atau salinan luar server.</span></header>'
        '<dl>%s</dl>' % _kartu_layanan(status_layanan)
        + '<a class="admin-layanan-cta" href="/admin?section=operasional">Buka operasional <span aria-hidden="true">→</span></a></section>'
        '<div class="admin-pendukung"><section class="admin-kartu admin-angka-kartu" aria-labelledby="judul-angka">'
        '<h2 id="judul-angka">Jumlah administratif</h2>'
        '<dl class="admin-angka-daftar" aria-label="Jumlah administratif">%s</dl>' % stat
        + '<p class="admin-meta">Angka adalah konteks, bukan target. '
        'Data administratif tidak menyatakan anak sedang online, sudah belajar, atau lulus.</p></section>'
        '<section class="admin-kartu admin-aktivitas" aria-labelledby="judul-aktivitas">'
        '<header class="admin-seksi-kepala"><h2 id="judul-aktivitas">Aktivitas sesi terbaru</h2>'
        '<span class="admin-meta">Maksimal 10 catatan · dikelompokkan per siswa/hari</span></header>'
        '<ul>%s</ul></section></div>' % aktivitas
        + login_detail
        + '<details class="admin-kartu admin-catatan admin-definisi"><summary>Tentang angka ringkasan</summary>'
        '<p>Catatan sesi mencakup sesi dibatalkan. Jendela 7/30 hari memakai '
        '<code>selesai → mulai → dibuat → tanggal</code> dalam waktu WIB. '
        'Jumlah login adalah akun murid, bukan jumlah siswa yang sudah bisa masuk.</p>'
        '<p>Seluruh catatan sesi: <strong>%d</strong> · <strong>%d</strong> dalam 7 hari · '
        '<strong>%d</strong> dalam 30 hari · <strong>%d</strong> dibatalkan.</p></details></div>'
        % (data.jumlah_sesi, data.sesi_7_hari, data.sesi_30_hari, data.sesi_dibatalkan)
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
        '<p class="admin-jejak"><a href="/admin?section=keluarga">← Kembali ke daftar keluarga</a></p>'
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
        + (tindakan or '')
        + '<section class="admin-kartu"><h2>Siswa dalam keluarga</h2>'
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="Siswa dalam keluarga"><table class="admin-tabel">'
        '<thead><tr><th scope="col">Siswa</th><th scope="col">Kelas sekolah</th><th scope="col">Sesi</th><th scope="col">Kondisi</th></tr></thead>'
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
        '<p class="admin-jejak"><a href="/admin?section=siswa">← Kembali ke daftar siswa</a></p>'
        '<section class="admin-kartu"><h2>Identitas siswa</h2><dl class="admin-rincian">'
        '<dt>Nama panggilan</dt><dd>%s</dd><dt>ID siswa</dt><dd>%d</dd>'
        '<dt>Kelas sekolah</dt><dd>%s</dd><dt>Konteks latihan</dt><dd>Profil %s</dd>'
        '<dt>Keluarga</dt><dd>%s</dd>'
        '<dt>Login eksplisit</dt><dd>%s</dd><dt>Jumlah sesi</dt><dd>%d</dd>'
        '<dt>Kondisi</dt><dd>%s</dd></dl>'
        '<div class="admin-aksi-baca"><a class="admin-tautan" href="/anak/%d?section=rencana">Buka profil</a>'
        '<a class="admin-tautan" href="/anak/%d?section=perkembangan">Buka laporan</a></div></section>'
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
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="Aktivitas sesi terbaru"><table class="admin-tabel">'
        '<thead><tr><th scope="col">Sesi</th><th scope="col">Profil parameter sesi</th><th scope="col">Waktu</th><th scope="col">Status</th></tr></thead>'
        '<tbody>%s</tbody></table></div></section>' % sesi
    )


def form_buat_keluarga(csrf: str, token: str) -> str:
    return (
        '<p class="admin-jejak"><a href="/admin?section=keluarga">← Kembali ke daftar keluarga</a></p>'
        '<section class="admin-kartu admin-form-pendek"><h2>Buat akun orang tua</h2>'
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
            '<p class="admin-meta">Reset hanya boleh dilanjutkan setelah pemohon diverifikasi melalui hubungan independen. WhatsApp, nama akun, atau informasi anak bukan bukti tunggal.</p>'
            '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
            '<label><input type="checkbox" name="verifikasi_independen" value="1" required> Verifikasi independen pemohon sudah selesai.</label>'
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
    return '<section class="admin-kartu admin-form-tindakan admin-form-pendek"><h2>Tindakan akun</h2>%s</section>' % "".join(bagian)


def form_kelas_sekolah(data: Q.DetailSiswa, csrf: str, token: str) -> str:
    """Aksi baru metadata, bukan form ubah level warisan."""
    return (
        '<section class="admin-kartu admin-form-pendek"><h2>Ubah kelas sekolah</h2>'
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
        '<section class="admin-kartu admin-form-tindakan admin-form-pendek"><h2>Tindakan siswa</h2>'
        '<form method="post" action="/admin/siswa">'
        '<input type="hidden" name="aksi" value="student_level_update">'
        '<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
        '<label>Profil parameter baru<select name="tingkat_baru">%s</select></label>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Ubah profil parameter warisan</button></form>'
        % (_e(csrf), _e(token_level), level)
    )
    if not token_level:
        hasil = '<section class="admin-kartu admin-form-tindakan admin-form-pendek"><h2>Tindakan siswa</h2>'
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
        '<section class="admin-kartu admin-form-pendek"><h2>Hapus profil siswa kosong</h2>'
        '<p>Hanya profil tanpa riwayat atau referensi terlindungi yang boleh dihapus. Pemeriksaan diulang saat konfirmasi.</p>'
        '<form method="post" action="/admin/siswa" data-konfirmasi="Hapus login dan profil siswa kosong ini? Tindakan tidak dapat dibatalkan."><input type="hidden" name="aksi" value="student_delete">'
        '<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<label><input type="checkbox" name="konfirmasi" value="1" required> Saya memahami login dan profil siswa kosong dihapus; tindakan ini tidak dapat dibatalkan.</label>'
        '<button class="admin-tombol admin-bahaya" type="submit">Hapus login dan profil siswa kosong</button></form></section>'
        % (_e(csrf), _e(token)))


def render_pendaftaran(status, *, csrf: str, token: str) -> str:
    """Form dan field tidak berubah: pesan tetap pilihan baku ``pesan_kode``."""
    dibuka = bool(status.dibuka)
    pesan = (
        'Pendaftaran sementara ditutup untuk pemeliharaan'
        if status.pesan_kode == 'closed_maintenance' else 'Pendaftaran baru sedang ditutup'
    )
    keadaan = (
        "Saat ini pendaftaran dibuka, jadi pesan ini belum tampil."
        if dibuka else "Saat ini pendaftaran ditutup, jadi pesan ini yang tampil."
    )
    return (
        '<section class="admin-kartu admin-status-baris" aria-labelledby="status-pendaftaran">'
        '<h2 id="status-pendaftaran"><span class="admin-titik-status%s" aria-hidden="true"></span>Pendaftaran %s</h2>'
        '<span class="admin-meta">Perubahan tidak memengaruhi login yang sudah ada.</span></section>'
        '<div class="admin-dua-kolom admin-kolom-2-1"><section class="admin-kartu"><h2>Pengaturan pendaftaran</h2>'
        '<form class="admin-form-bagian" method="post" action="/admin/pendaftaran">'
        '<input type="hidden" name="aksi" value="registration_config_update">'
        '<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
        '<label class="admin-cek"><input type="checkbox" name="dibuka" value="1"%s>'
        '<span><strong>Buka pendaftaran baru</strong>'
        '<span class="admin-meta">Matikan untuk menutup pendaftaran. Keluarga yang sudah punya akun tetap bisa masuk.</span></span></label>'
        '<div class="admin-bagian"><label>Pesan saat ditutup<select name="pesan_kode">'
        '<option value="closed_standard"%s>Pendaftaran baru sedang ditutup</option>'
        '<option value="closed_maintenance"%s>Pendaftaran sementara ditutup untuk pemeliharaan</option>'
        '</select></label></div>'
        '<div class="admin-bagian"><label>Sandi admin saat ini'
        '<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<span class="admin-meta">Diminta untuk setiap perubahan pengaturan.</span>'
        '<div><button class="admin-tombol" type="submit">Simpan pengaturan</button></div></div>'
        '</form></section><aside class="admin-kartu" aria-label="Pratinjau"><h2>Pratinjau saat ditutup</h2>'
        '<p class="admin-meta">Yang dilihat calon pengguna jika pendaftaran ditutup. %s</p>'
        '<div class="admin-pratinjau"><strong>%s</strong></div>'
        '<p class="admin-meta">Pesan tersimpan. Pratinjau diperbarui setelah pengaturan disimpan.</p></aside></div>' % (
            "" if dibuka else " admin-titik-netral", "dibuka" if dibuka else "ditutup",
            _e(csrf), _e(token), ' checked' if dibuka else '',
            ' selected' if status.pesan_kode == 'closed_standard' else '',
            ' selected' if status.pesan_kode == 'closed_maintenance' else '',
            keadaan, _e(pesan),
        )
    )


def render_bulk_awal(csrf: str, token: str) -> str:
    return (
        '<p><a class="admin-tautan" href="/admin/bulk/pilih?peran=guru">Kelola akun orang tua terpilih</a></p>'
        '<details class="admin-kartu"><summary>Buat akun orang tua massal</summary>'
        '<p class="admin-meta">CSV UTF-8 satu kolom <code>pengguna</code>; maksimal 100 akun dan 64 KiB. Tahap ini hanya meninjau alias, bukan membuat akun.</p>'
        '<p><a class="admin-tautan" href="/admin/bulk/templat">Unduh templat CSV kosong</a></p>'
        '<form method="post" action="/admin/bulk/impor" enctype="multipart/form-data">'
        '<input type="hidden" name="aksi" value="bulk_teacher_create">'
        '<input type="hidden" name="csrf" value="%s">'
        '<input type="hidden" name="tinjauan" value="%s">'
        '<label>File CSV<input type="file" name="csv" accept=".csv,text/csv" required></label>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Tinjau batch</button>'
        '</form></details>' % (_e(csrf), _e(token))
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
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="Hasil operasi akun"><table class="admin-tabel"><thead><tr><th scope="col">Akun</th><th scope="col">Hasil</th><th scope="col">Akses</th></tr></thead>'
        '<tbody>%s</tbody></table></div>'
        '<p><a class="admin-tautan" href="/admin/bulk/hasil?id=%s">Lihat status tanpa sandi</a></p>'
        % (_e(aksi), len(batch.item), _e(label.get(batch.status, batch.status)), _e(ringkas), ''.join(baris), _e(batch.batch_id)))
    def form(jalur, token, teks, dampak, tambahan='', utama=True):
        return ('<form method="post" action="/admin/bulk/%s">'
            '<input type="hidden" name="batch_id" value="%s"><input type="hidden" name="csrf" value="%s">'
            '<input type="hidden" name="tinjauan" value="%s">%s'
            '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
            '<label><input type="checkbox" name="konfirmasi" value="1" required> %s</label>'
            '<button class="%s" type="submit">%s</button></form>'
            % (jalur, _e(batch.batch_id), _e(csrf), _e(token), tambahan, _e(dampak),
               'admin-tombol' if utama else 'admin-tombol admin-tombol-sekunder', _e(teks)))
    if not batch.draft_tersedia:
        isi += '<p class="admin-catatan">Draft alias sudah tidak tersedia. Hasil ini berasal dari metadata tersimpan tanpa sandi. Item yang belum pasti tidak dijalankan ulang otomatis.</p>'
    aksi = []
    if batch.boleh_proses:
        tombol = 'Pulihkan kelompok yang sama' if batch.kelompok_aktif_id else 'Proses kelompok berikutnya'
        aksi.append(('proses', tokens['process'], tombol,
            'Saya menyetujui tindakan pada maksimal 10 akun berikutnya dan dampak pencabutan sesi; hasil selesai tidak dibatalkan.'))
    if batch.status in ('ready', 'partial', 'attention'):
        aksi.append(('hentikan', tokens['stop'], 'Hentikan item yang belum mulai',
            'Item yang belum mulai dibatalkan; perubahan yang sudah selesai tetap tercatat.'))
    if belum_diserahkan:
        aksi.append(('serahkan', tokens['handover'], 'Konfirmasi akses telah diserahkan',
            'Saya sudah menyerahkan akses akun berhasil yang belum dikonfirmasi melalui kanal privat.',
            '<input type="hidden" name="item_ids" value="%s">' % _e(','.join(belum_diserahkan))))
    # Satu aksi utama per kartu: aksi pertama yang tersedia solid, sisanya sekunder.
    isi += ''.join(form(*a, utama=i == 0) for i, a in enumerate(aksi))
    if batch.status == 'running':
        isi += '<p role="alert">Kelompok belum memiliki hasil final. Pemulihan hanya menggunakan identitas kelompok yang sama dan memeriksa receipt; jangan membuat batch pengganti.</p>'
    if batch.status == 'attention':
        isi += '<p role="alert">Hasil tak pasti ditahan. Jangan mengulang batch; pemeriksaan receipt oleh operator diperlukan.</p>'
    return isi + '</section>'


def _label_status_batch(status):
    return L.label_status(status)


def _waktu_audit_batch(epoch):
    return L.tanggal(epoch)


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
    return (nav_riwayat("batch") + '<section class="admin-kartu"><h2>Metadata batch %s</h2>'
        '<p>Actor: %s · Aksi: %s · Status: %s · %d target.</p>'
        '<p>Tampilan audit hanya-baca; bukan akses untuk mengambil alih draft sesi lain.</p>'
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="Metadata item batch"><table class="admin-tabel"><thead><tr><th scope="col">Item</th><th scope="col">Operasi</th>'
        '<th scope="col">Target/hasil</th><th scope="col">Status</th><th scope="col">Penyerahan</th></tr></thead><tbody>%s</tbody></table></div>'
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
