"""Komponen markup bersama panel admin; murni, tanpa I/O dan tanpa JavaScript."""
from __future__ import annotations

import html
import re
from typing import Mapping, Optional, Sequence, Tuple
from urllib.parse import urlencode

import admin_labels as L


def e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


COPY_AKAN_DIMATIKAN = (
    "Akan dimatikan (keputusan Pemilik 20 Nov 2026). Layanan ini tidak dipakai di alur yang berjalan sekarang. "
    "Langkah pematian ada di rencana; jangan membuat pengaturan baru di sini."
)


def kartu_akan_dimatikan() -> str:
    """Kartu pemberitahuan di atas halaman layanan yang dijadwalkan mati (plan matikan-kpi-dan-ai, Fase 1)."""
    return '<p class="admin-kartu admin-catatan" role="note">%s</p>' % e(COPY_AKAN_DIMATIKAN)


def opsi(nilai: str, label: str, kini: str) -> str:
    return '<option value="%s"%s>%s</option>' % (
        e(nilai), ' selected' if nilai == kini else "", e(label)
    )




def hidden_filter(filter_data: Mapping[str, str]) -> str:
    return "".join(
        '<input type="hidden" name="%s" value="%s">' % (e(kunci), e(nilai))
        for kunci, nilai in filter_data.items()
        if nilai
    )




def pager(
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
                % (e(section), hidden_filter(filter_data), e(csrf), target, e(label))
            )
        else:
            query = {"section": section, "halaman": target}
            query.update({k: v for k, v in filter_data.items() if v})
            kontrol.append(
                '<a class="admin-tautan" href="/admin?%s">%s</a>'
                % (e(urlencode(query)), e(label))
            )
    return (
        '<div class="admin-pager"><span>Halaman %d dari %d · %d hasil</span><div class="admin-aksi-baca">%s</div></div>'
        % (halaman, jumlah_halaman, total, "".join(kontrol))
    )




def badge_status(status: Sequence[str]) -> str:
    if not status:
        return '<span class="admin-badge">Normal</span>'
    return "".join(
        '<span class="admin-badge%s">%s</span>'
        % (' bien' if kode in ('succeeded', 'ok', 'completed', 'selesai') else ' perhatian', e(L.label_status(kode)))
        for kode in status
    )




def badge_aktif(aktif: bool, teks_aktif: str = "Aktif", teks_mati: str = "Mati") -> str:
    """Penanda status besar untuk kartu pengaturan: hijau bila aktif, netral bila mati."""
    return '<span class="admin-badge admin-status-besar%s">%s</span>' % (
        " bien" if aktif else "", e(teks_aktif if aktif else teks_mati))


def lipat_aksi(ringkasan: str, kelas_ringkasan: str, isi: str) -> str:
    """Tindakan terlipat: `isi` (biasanya form sandi) baru tampil setelah <details> dibuka."""
    return ('<details class="admin-aksi-ubah"><summary class="%s">%s</summary>%s</details>'
            % (e(kelas_ringkasan), e(ringkasan), isi))


def waktu(nilai: Optional[str]) -> str:
    return e(L.tanggal(nilai))


TANDA_CARI = re.compile(r"<!--kepala-cari-->(.*?)<!--/kepala-cari-->", re.S)


def kepala_cari(isi: str) -> str:
    """Tandai blok pencarian agar ``halaman_admin`` memindahkannya ke baris judul."""
    return "<!--kepala-cari-->%s<!--/kepala-cari-->" % isi


def pisah_kepala_cari(isi: str) -> Tuple[str, str]:
    """Kembalikan (isi tanpa blok pencarian, blok pencarian atau string kosong)."""
    cocok = TANDA_CARI.search(isi)
    if cocok is None:
        return isi, ""
    return isi[:cocok.start()] + isi[cocok.end():], cocok.group(1)
