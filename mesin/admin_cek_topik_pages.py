"""Renderer HTML murni halaman admin "Topik Cek Kemampuan" (tanpa JS, tanpa DB).

Semua isi diturunkan dari `cek_gratis_skor` (topik per kelas, jumlah soal),
`topik_awam` (nama ramah yang sama dengan layar anak) dan registri `topics`
(nama resmi, id template); tidak ada topik, nama, atau angka yang ditulis
tangan di sini. Id dan nama resmi ada di "Rincian teknis" per kelas.
"""
from __future__ import annotations

from typing import Callable, Optional

import cek_gratis_skor as skor
import topics
import topik_awam
from admin_komponen import e
from admin_kurikulum_tab import TAB_CEK_TOPIK, tab_kurikulum

KELAS_CEK = (1, 2, 3, 4, 5, 6)
KELAS_DASAR = (1, 2)
MAKS_CONTOH_PER_TOPIK = 4
LABEL_AKTIF = "Aktif"
LABEL_BELUM_TERSEDIA = "Belum tersedia"
CATATAN_RILIS = "Topik diubah lewat rilis, bukan dari sini."


def topik_kelas(kelas: int) -> tuple:
    """Id topik cek untuk satu kelas; kelas 1–2 memakai satu topik dasar."""
    if kelas in KELAS_DASAR:
        return (skor.TOPIK_DASAR,)
    return skor.topik_untuk_kelas(kelas)


def soal_per_topik(kelas: int) -> str:
    """Soal per topik: JUMLAH_SOAL dibagi jumlah topik ('5', atau rentang 'a–b' bila tak habis)."""
    jumlah_topik = len(topik_kelas(kelas))
    bagi, sisa = divmod(skor.JUMLAH_SOAL, jumlah_topik)
    return str(bagi) if sisa == 0 else "%d–%d" % (bagi, bagi + 1)


def contoh_template(topik_id: str, kelas: int) -> tuple:
    """Template unik (urutan komposisi) milik topik di level `P{kelas}`; kosong bila level tak ada."""
    level = "P%d" % kelas
    paket = topics.ambil(topik_id)
    sumber = paket.komposisi if paket.komposisi_writer is None else paket.komposisi_writer
    if level not in sumber:
        return ()
    unik = tuple(dict.fromkeys(sumber[level]))
    return unik[:MAKS_CONTOH_PER_TOPIK]


def nama_ramah(topik_id: str) -> str:
    """Nama untuk pembaca awam dari `topik_awam`; bila tak ada, nama resmi registri, lalu id."""
    try:
        return topik_awam.nama(topik_id)
    except KeyError:
        pass
    try:
        return topics.ambil(topik_id).nama
    except KeyError:
        return topik_id


def status_kelas(kelas: int, dasar_aktif: bool) -> tuple:
    """(label, kelas CSS pil); hanya kelas 1–2 (materi dasar) yang bergantung pada sakelar."""
    if kelas in KELAS_DASAR and not dasar_aktif:
        return LABEL_BELUM_TERSEDIA, "perhatian"
    return LABEL_AKTIF, "bien"


def _pil_status(kelas: int, dasar_aktif: bool) -> str:
    label, gaya = status_kelas(kelas, dasar_aktif)
    return '<span class="admin-badge %s">%s</span>' % (gaya, e(label))


def _ringkasan_kelas(kelas: int, dasar_aktif: bool) -> str:
    return (
        '<li class="admin-topik-ringkas"><strong>Kelas %d</strong>'
        '<span class="admin-meta">%d topik</span>%s</li>'
        % (kelas, len(topik_kelas(kelas)), _pil_status(kelas, dasar_aktif))
    )


def _item_topik(topik_id: str, kelas: int) -> str:
    return (
        '<li class="admin-topik-item"><span>%s</span><span class="admin-badge">%s soal</span></li>'
        % (e(nama_ramah(topik_id)), e(soal_per_topik(kelas)))
    )


def _rincian_topik(topik_id: str, kelas: int) -> str:
    try:
        resmi = topics.ambil(topik_id).nama
        contoh = contoh_template(topik_id, kelas)
    except KeyError:
        return '<li><strong>%s</strong> <span class="admin-meta">(tidak terdaftar)</span></li>' % e(topik_id)
    jenis = ", ".join("<code>%s</code>" % e(t) for t in contoh) or "—"
    return (
        '<li><strong>%s</strong> <span class="admin-meta"><code>%s</code></span>'
        '<br><span class="admin-meta">Contoh jenis soal: %s</span></li>'
    ) % (e(resmi), e(topik_id), jenis)


def _kartu_kelas(kelas: int, dasar_aktif: bool) -> str:
    topik = topik_kelas(kelas)
    return (
        '<section class="admin-kartu admin-topik-kelas"><div class="admin-topik-kepala">'
        '<h3>Kelas %d</h3>%s</div><ul class="admin-topik-daftar">%s</ul>'
        '<details class="admin-lipat-kecil"><summary>Rincian teknis</summary><ul>%s</ul>'
        '<p class="admin-meta">%s</p></details></section>'
    ) % (
        kelas, _pil_status(kelas, dasar_aktif),
        "".join(_item_topik(t, kelas) for t in topik),
        "".join(_rincian_topik(t, kelas) for t in topik),
        e(CATATAN_TEKNIS),
    )


CATATAN_TEKNIS = (
    "Contoh jenis soal diambil dari susunan lembar topik di level kelas itu "
    "(maksimal %d per topik); cek sungguhan memilih soal dari topik tersebut. "
    "Nama jenis soal ditampilkan sebagai id template. Nama resmi paket topik dan id topik "
    "dipakai di lembar soal dan penilaian guru." % MAKS_CONTOH_PER_TOPIK
)


def halaman(dasar_aktif: bool, *, kelas: Optional[tuple] = None) -> str:
    daftar_kelas = kelas or KELAS_CEK
    return tab_kurikulum(TAB_CEK_TOPIK) + (
        '<section class="admin-kartu"><h2>Ringkasan per kelas</h2>'
        '<p class="admin-meta">%d soal per cek, pilihan ganda.</p>'
        '<ul class="admin-topik-ringkasan" aria-label="Ringkasan topik per kelas">%s</ul></section>'
        '<h2 class="admin-topik-judul">Topik per kelas</h2>%s'
        '<section class="admin-kartu admin-catatan"><p class="admin-meta">%s</p></section>'
    ) % (
        skor.JUMLAH_SOAL,
        "".join(_ringkasan_kelas(k, dasar_aktif) for k in daftar_kelas),
        "".join(_kartu_kelas(k, dasar_aktif) for k in daftar_kelas),
        e(CATATAN_RILIS),
    )
