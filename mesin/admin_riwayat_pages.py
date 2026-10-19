"""Tiga tampilan riwayat admin (tindakan, batch, AI); murni, tanpa I/O dan tanpa JavaScript.

Nama field filter (aksi, mulai, selesai, actor_id, status) dan nilai aksi tidak
berubah; form tetap GET agar tautan filter dan paginasi lama tetap berlaku.
"""
from __future__ import annotations

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
    "student_level_update": "Ubah profil parameter warisan",
    "student_school_grade_update": "Ubah kelas sekolah", "student_delete": "Hapus siswa kosong",
    "registration_config_update": "Ubah pendaftaran",
}
LABEL_AKSI_AI = {"ai_settings_update": "Ubah pengaturan AI", "ai_synthetic_test": "Tes sintetis AI"}
LABEL_AKSI_BATCH = {
    "account_teacher_create": "Buat orang tua", "account_password_reset": "Reset sandi",
    "account_session_revoke": "Cabut sesi",
}
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
        '<a class="admin-tab%s" href="%s"%s>%s</a>' % (
            " admin-tab-aktif" if kode == aktif else "", href,
            ' aria-current="page"' if kode == aktif else "", e(nama))
        for kode, nama, href in tab
    )


def _kepala(*nama) -> tuple:
    return tuple('<th scope="col">%s</th>' % e(x) for x in nama)


def _filter_bersih(filter_data, diizinkan):
    return {k: v for k, v in (filter_data or {}).items() if k in diizinkan}


def _form_filter(tersembunyi, isi, tombol, kelas_tombol) -> str:
    return (
        '<form method="get" action="/admin" class="admin-kartu admin-form-cari admin-filter-riwayat" '
        'aria-label="Saring riwayat">%s%s<button class="%s">%s</button></form>'
        % (tersembunyi, isi, kelas_tombol, e(tombol))
    )


def _hidden(**nilai) -> str:
    return "".join('<input type="hidden" name="%s" value="%s">' % (e(k), e(v)) for k, v in nilai.items())


def _opsi_aksi(label, kini, semua="Semua aksi") -> str:
    return opsi("", semua, kini) + "".join(opsi(k, v, kini) for k, v in label.items())


def render_riwayat(data, *, filter_data=None) -> str:
    filter_data = _filter_bersih(filter_data, ("actor_id", "aksi", "status", "mulai", "selesai"))
    baris = "".join(
        '<tr><td>%s</td><td>%s</td><td><strong>%s</strong></td><td>%s</td><td>%s</td></tr>' % (
            e(L.tanggal(item.dibuat)), L.referensi(item.actor_id),
            e(LABEL_AKSI.get(item.aksi, L.label_status(item.aksi))),
            L.referensi(item.target_id), badge_status((item.status,)),
        ) for item in data.item
    ) or '<tr><td colspan="5" class="admin-kosong">Belum ada tindakan admin.</td></tr>'
    kini_aksi = filter_data.get("aksi", "")
    dasar = [("section", "riwayat")] + [
        (kunci, filter_data[kunci]) for kunci in ("mulai", "selesai", "actor_id") if filter_data.get(kunci)
    ]
    chips = ['<a class="admin-chip"%s href="/admin?%s">Semua aksi</a>' % (
        ' aria-current="true"' if not kini_aksi else "", e(urlencode(dasar)))]
    chips.extend(
        '<a class="admin-chip"%s href="/admin?%s">%s</a>' % (
            ' aria-current="true"' if kini_aksi == kode else "",
            e(urlencode(dasar + [("aksi", kode)])), e(nama))
        for kode, nama in LABEL_AKSI.items()
    )
    cepat = (
        '<details class="admin-kartu admin-cepat-aksi"%s><summary>Filter cepat aksi</summary>'
        '<nav class="admin-chip-baris" aria-label="Filter cepat aksi">%s</nav></details>'
        % (" open" if kini_aksi else "", "".join(chips))
    )
    form = _form_filter(
        _hidden(section="riwayat"),
        '<label>Mulai (WIB)<input type="date" name="mulai" value="%s"></label>'
        '<label>Sampai (WIB)<input type="date" name="selesai" value="%s"></label>'
        '<label>ID pengelola<input name="actor_id" value="%s" maxlength="80"></label>'
        '<label>Aksi<select name="aksi">%s</select></label>' % (
            e(filter_data.get("mulai", "")), e(filter_data.get("selesai", "")),
            e(filter_data.get("actor_id", "")), _opsi_aksi(LABEL_AKSI, kini_aksi)),
        "Saring riwayat", "admin-tombol admin-tombol-sekunder",
    )
    return (
        nav_riwayat("tindakan") + form + cepat
        + kartu_tabel(
            "Riwayat tindakan", _kepala("Waktu", "Pelaku", "Aksi", "Target", "Status"), baris,
            pager(section="riwayat", halaman=data.halaman, jumlah_halaman=data.jumlah_halaman,
                  total=data.total, filter_data=filter_data, via_post=False),
            keterangan="%d hasil" % data.total)
        + CATATAN_RIWAYAT
    )


def render_riwayat_ai(data, *, filter_data=None) -> str:
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
        "Saring riwayat", "admin-tombol",
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


def render_audit_batch(data, *, filter_data=None) -> str:
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
        "Saring batch", "admin-tombol",
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
