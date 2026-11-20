"""Tiga tampilan riwayat admin (tindakan, batch, AI); murni, tanpa I/O dan tanpa JavaScript.

Nama field filter (aksi, mulai, selesai, actor_id, status) dan nilai aksi tidak
berubah; form tetap GET agar tautan filter dan paginasi lama tetap berlaku.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlencode

import admin_labels as L
from admin_daftar_pages import kartu_tabel
from admin_komponen import badge_status, e, opsi, pager, waktu

LABEL_AKSI = {
    "account_password_reset": "Reset sandi",
    "account_session_revoke": "Cabut sesi",
    "account_login_delete": "Hapus login",
    "account_teacher_create": "Buat orang tua",
    "student_login_create": "Buat login murid",
    "student_level_update": "Ubah level soal (akun lama)",
    "student_school_grade_update": "Ubah kelas sekolah", "student_delete": "Hapus siswa kosong",
    "registration_config_update": "Ubah pendaftaran",
}
LABEL_AKSI_AI = {"ai_settings_update": "Ubah pengaturan AI", "ai_synthetic_test": "Tes koneksi AI"}
LABEL_AKSI_BATCH = {
    "account_teacher_create": "Buat orang tua", "account_password_reset": "Reset sandi",
    "account_session_revoke": "Cabut sesi",
}
LABEL_TARGET = {
    "account": "akun", "account_candidate": "akun baru", "student": "siswa",
    "registration_config": "pengaturan pendaftaran",
}
RENTANG_CEPAT = (("Hari ini", 1), ("7 hari", 7), ("30 hari", 30))
STATUS_BATCH = ("ready", "running", "partial", "stopped", "succeeded", "attention")
CATATAN_RIWAYAT = (
    '<p class="admin-meta">Riwayat dimulai saat fitur aktif; bukan semua aktivitas belajar. '
    'Tidak ada kejadian lama yang direka ulang. ID ditampilkan lengkap dan dapat dipilih untuk disalin.</p>'
)


def nav_riwayat(aktif=None) -> str:
    """Tab jenis riwayat; ``aktif`` salah satu 'tindakan', 'batch', 'ai' atau None."""
    tab = (
        ("tindakan", "Tindakan akun dan siswa", "/admin?section=riwayat"),
        ("batch", "Riwayat batch", "/admin?section=riwayat&amp;sumber=batch"),
        ("ai", "Riwayat AI", "/admin?section=riwayat&amp;sumber=ai"),
    )
    return '<div class="admin-tab-baris" role="group" aria-label="Jenis riwayat">%s</div>' % "".join(
        '<a class="admin-tab" href="%s"%s>%s</a>' % (
            href, ' aria-current="page"' if kode == aktif else "", e(nama))
        for kode, nama, href in tab
    )


def _kepala(*nama) -> tuple:
    return tuple('<th scope="col">%s</th>' % e(x) for x in nama)


def _filter_bersih(filter_data, diizinkan):
    return {k: v for k, v in (filter_data or {}).items() if k in diizinkan}


def _rentang_cepat(dasar, filter_data, sekarang=None) -> str:
    """Tautan GET yang mengisi ``mulai``/``selesai`` (tanggal WIB) dan mempertahankan filter lain."""
    hari = (sekarang or datetime.now(L.WIB)).astimezone(L.WIB).date()
    tautan = []
    for label, jumlah in RENTANG_CEPAT:
        mulai = (hari - timedelta(days=jumlah - 1)).isoformat()
        query = list(dasar) + [
            (kunci, nilai) for kunci, nilai in (filter_data or {}).items()
            if nilai and kunci not in ("mulai", "selesai", "section", "sumber", "halaman")
        ] + [("mulai", mulai), ("selesai", hari.isoformat())]
        aktif = (filter_data or {}).get("mulai") == mulai and (filter_data or {}).get("selesai") == hari.isoformat()
        tautan.append('<a class="admin-chip"%s href="/admin?%s">%s</a>' % (
            ' aria-current="true"' if aktif else "", e(urlencode(query)), e(label)))
    return '<nav class="admin-chip-baris admin-rentang-cepat" aria-label="Rentang cepat">%s</nav>' % "".join(tautan)


def _form_filter(tersembunyi, isi, tombol, rentang="") -> str:
    """Satu baris filter GET; penyaring selalu aksi sekunder (aksi utama halaman tetap satu)."""
    return (
        '<form method="get" action="/admin" class="admin-kartu admin-form-cari admin-filter-riwayat" '
        'aria-label="Saring riwayat">%s%s%s<button class="admin-tombol admin-tombol-sekunder">%s</button></form>'
        % (tersembunyi, rentang, isi, e(tombol))
    )


def _huruf_kecil_awal(teks: str) -> str:
    """Huruf pertama dikecilkan hanya bila kata berikutnya bukan singkatan (mis. "AI")."""
    if len(teks) > 1 and teks[1].islower():
        return teks[0].lower() + teks[1:]
    return teks


def _kalimat_entri(item) -> str:
    label = LABEL_AKSI.get(item.aksi, L.label_status(item.aksi))
    target = LABEL_TARGET.get(item.jenis_target, item.jenis_target.replace("_", " "))
    return "Pengelola melakukan <strong>%s</strong> pada %s." % (e(_huruf_kecil_awal(label)), e(target))


def _rincian_entri(item) -> str:
    return (
        '<details class="admin-lipat-kecil"><summary>Rincian</summary><dl class="admin-rincian-daftar">'
        '<dt>Waktu</dt><dd>%s</dd><dt>Pelaku</dt><dd>%s</dd><dt>Aksi</dt><dd>%s</dd><dt>Target</dt><dd>%s</dd>'
        '</dl></details>' % (
            e(L.tanggal(item.dibuat)), L.referensi(item.actor_id), L.referensi(item.aksi), L.referensi(item.target_id))
    )


def _entri_tindakan(item) -> str:
    return (
        '<li class="admin-entri"><div class="admin-entri-baris"><span class="admin-entri-jam">%s</span>'
        '<span class="admin-entri-kalimat">%s</span>%s</div>%s</li>' % (
            e(L.waktu(item.dibuat).strftime("%H.%M") if L.waktu(item.dibuat) else "—"),
            _kalimat_entri(item), badge_status((item.status,)), _rincian_entri(item))
    )


def _kelompok_per_hari(item, sekarang=None) -> str:
    """Kelompokkan berurutan per hari WIB; judul "Hari ini", "Kemarin", atau tanggal."""
    kelompok, judul_kini = [], None
    for entri in item:
        judul = L.judul_hari(entri.dibuat, sekarang)
        if judul != judul_kini:
            kelompok.append((judul, []))
            judul_kini = judul
        kelompok[-1][1].append(_entri_tindakan(entri))
    return "".join(
        '<section class="admin-hari"><h3>%s</h3><ul class="admin-entri-daftar">%s</ul></section>' % (e(judul), "".join(isi))
        for judul, isi in kelompok
    )


def _kartu_kelompok(judul, keterangan, isi, kaki) -> str:
    return (
        '<section class="admin-kartu admin-kartu-tabel"><div class="admin-kartu-kepala">'
        '<h2>%s</h2><span class="admin-meta">%s</span></div>%s'
        '<div class="admin-kartu-kaki">%s</div></section>' % (e(judul), e(keterangan), isi, kaki)
    )


def _hidden(**nilai) -> str:
    return "".join('<input type="hidden" name="%s" value="%s">' % (e(k), e(v)) for k, v in nilai.items())


def _opsi_aksi(label, kini, semua="Semua aksi") -> str:
    return opsi("", semua, kini) + "".join(opsi(k, v, kini) for k, v in label.items())


def render_riwayat(data, *, filter_data=None, sekarang=None) -> str:
    filter_data = _filter_bersih(filter_data, ("actor_id", "aksi", "status", "mulai", "selesai"))
    isi = _kelompok_per_hari(data.item, sekarang) or '<p class="admin-kosong admin-kartu-catatan">Belum ada tindakan admin.</p>'
    form = _form_filter(
        _hidden(section="riwayat"),
        '<label>Aksi<select name="aksi">%s</select></label>'
        '<label>ID pengelola<input name="actor_id" value="%s" maxlength="80"></label>'
        '<label>Mulai (WIB)<input type="date" name="mulai" value="%s"></label>'
        '<label>Sampai (WIB)<input type="date" name="selesai" value="%s"></label>' % (
            _opsi_aksi(LABEL_AKSI, filter_data.get("aksi", "")), e(filter_data.get("actor_id", "")),
            e(filter_data.get("mulai", "")), e(filter_data.get("selesai", ""))),
        "Saring riwayat",
        _rentang_cepat((("section", "riwayat"),), filter_data, sekarang),
    )
    return (
        nav_riwayat("tindakan") + form
        + _kartu_kelompok(
            "Riwayat tindakan", "%d hasil" % data.total, isi,
            pager(section="riwayat", halaman=data.halaman, jumlah_halaman=data.jumlah_halaman,
                  total=data.total, filter_data=filter_data, via_post=False))
        + CATATAN_RIWAYAT
    )


def render_riwayat_ai(data, *, filter_data=None, sekarang=None) -> str:
    filter_data = _filter_bersih(filter_data, ("actor_id", "aksi", "mulai", "selesai"))
    baris = "".join(
        '<tr><td>%s</td><td>%s</td><td><strong>%s</strong></td><td>%s</td><td>%s</td></tr>' % (
            e(L.tanggal(x.dibuat)),
            L.referensi(x.actor_id or "Tidak tercatat (sebelum metadata)"), e(LABEL_AKSI_AI[x.aksi]),
            badge_status((x.status,)),
            L.referensi(x.operasi_id or (
                "Revisi %s (sebelum metadata operasi)" % x.revisi if x.revisi else "Sebelum metadata operasi")),
        ) for x in data.item
    ) or '<tr><td colspan="5" class="admin-kosong">Belum ada riwayat AI.</td></tr>'
    form = _form_filter(
        _hidden(section="riwayat", sumber="ai"),
        '<label>Mulai (WIB)<input type="date" name="mulai" value="%s"></label>'
        '<label>Sampai (WIB)<input type="date" name="selesai" value="%s"></label>'
        '<label>ID pengelola<input name="actor_id" maxlength="80" value="%s"></label>'
        '<label>Aksi<select name="aksi">%s</select></label>' % (
            e(filter_data.get("mulai", "")), e(filter_data.get("selesai", "")),
            e(filter_data.get("actor_id", "")), _opsi_aksi(LABEL_AKSI_AI, filter_data.get("aksi", ""))),
        "Saring riwayat",
        _rentang_cepat((("section", "riwayat"), ("sumber", "ai")), filter_data, sekarang),
    )
    return (
        nav_riwayat("ai") + form
        + kartu_tabel(
            "Riwayat dari penyimpanan AI", _kepala("Waktu", "Pelaku", "Aksi", "Status", "Referensi"), baris,
            pager(section="riwayat", halaman=data.halaman, total=data.total,
                  jumlah_halaman=data.jumlah_halaman, filter_data=dict(filter_data, sumber="ai"), via_post=False),
            catatan='<p class="admin-meta admin-kartu-catatan">Pengaturan dikelompokkan per operasi atau revisi. '
                    'Identitas tes lama yang belum tercatat tidak ditebak.</p>',
            keterangan="%d hasil" % data.total)
        + CATATAN_RIWAYAT
    )


def render_audit_batch(data, *, filter_data=None, sekarang=None) -> str:
    filters = _filter_bersih(filter_data, ("actor_id", "aksi", "status", "mulai", "selesai"))
    baris = "".join(
        '<tr><td><a href="/admin?section=riwayat&amp;sumber=batch&amp;id=%s">%s</a></td>'
        '<td>%s</td><td><strong>%s</strong></td><td data-angka>%d</td><td>%s</td><td>%s</td></tr>' % (
            e(x.batch_id), e(x.batch_id), e(x.actor_id), e(LABEL_AKSI_BATCH.get(x.aksi, x.aksi)),
            x.jumlah_total,
            e(" · ".join("%d %s" % (n, L.label_status(status)) for status, n in x.jumlah_status)),
            e(L.tanggal(x.dibuat))) for x in data.item
    ) or '<tr><td colspan="6" class="admin-kosong">Belum ada batch.</td></tr>'
    form = _form_filter(
        _hidden(section="riwayat", sumber="batch"),
        '<label>ID pengelola<input name="actor_id" maxlength="80" value="%s"></label>'
        '<label>Mulai WIB<input type="date" name="mulai" value="%s"></label>'
        '<label>Sampai WIB<input type="date" name="selesai" value="%s"></label>'
        '<label>Aksi<select name="aksi">%s</select></label>'
        '<label>Status<select name="status">%s</select></label>' % (
            e(filters.get("actor_id", "")), e(filters.get("mulai", "")), e(filters.get("selesai", "")),
            _opsi_aksi(LABEL_AKSI_BATCH, filters.get("aksi", "")),
            opsi("", "Semua status", filters.get("status", "")) + "".join(
                opsi(k, L.label_status(k), filters.get("status", "")) for k in STATUS_BATCH)),
        "Saring batch",
        _rentang_cepat((("section", "riwayat"), ("sumber", "batch")), filters, sekarang),
    )
    return (
        nav_riwayat("batch") + form
        + kartu_tabel(
            "Riwayat batch tersimpan",
            _kepala("Batch", "Pelaku", "Aksi", "Target", "Hasil", "Waktu"), baris,
            pager(section="riwayat", halaman=data.halaman, jumlah_halaman=data.jumlah_halaman,
                  total=data.total, filter_data=dict(filters, sumber="batch"), via_post=False),
            catatan='<p class="admin-meta admin-kartu-catatan">Metadata operasi tanpa alias, sandi, atau isi draft. '
                    'Satu batch dapat memiliki beberapa kelompok dan hasil parsial.</p>',
            keterangan="%d hasil" % data.total)
        + CATATAN_RIWAYAT
    )
