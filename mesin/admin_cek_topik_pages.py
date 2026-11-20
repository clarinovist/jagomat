"""Renderer HTML murni halaman admin "Topik Cek Kemampuan" (tanpa JS, tanpa DB).

Semua isi diturunkan dari `cek_gratis_skor` (topik per kelas, jumlah soal) dan
registri `topics`; tidak ada topik atau angka yang ditulis tangan di sini.
"""
from __future__ import annotations

from typing import Callable, Optional

import cek_gratis_skor as skor
import topics
from admin_komponen import e
from admin_kurikulum_tab import TAB_CEK_TOPIK, tab_kurikulum

KELAS_CEK = (1, 2, 3, 4, 5, 6)
KELAS_DASAR = (1, 2)
MAKS_CONTOH_PER_TOPIK = 4
STATUS_AKTIF = "aktif"
STATUS_MATI = "mati: cek kelas 1–2 belum tersedia"


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


def _sel_topik(topik_id: str, kelas: int) -> str:
    try:
        nama = topics.ambil(topik_id).nama
        contoh = contoh_template(topik_id, kelas)
    except KeyError:
        return '<li><strong>%s</strong> <span class="admin-meta">(tidak terdaftar)</span></li>' % e(topik_id)
    jenis = ", ".join("<code>%s</code>" % e(t) for t in contoh) or "—"
    return (
        '<li><strong>%s</strong> <span class="admin-meta"><code>%s</code></span>'
        '<br><span class="admin-meta">Contoh jenis soal: %s</span></li>'
    ) % (e(nama), e(topik_id), jenis)


def _status_kelas(kelas: int, dasar_aktif: bool) -> str:
    if kelas not in KELAS_DASAR:
        return ""
    teks = STATUS_AKTIF if dasar_aktif else STATUS_MATI
    return '<p class="admin-meta">Materi dasar: %s</p>' % e(teks)


def _baris(kelas: int, dasar_aktif: bool) -> str:
    # Status ada di sel topik, bukan di <th> (th admin `nowrap` membuat kolom Kelas melebar).
    daftar = "".join(_sel_topik(t, kelas) for t in topik_kelas(kelas))
    return (
        '<tr><th scope="row">Kelas %d</th><td><ul>%s</ul>%s</td><td>%s</td></tr>'
    ) % (kelas, daftar, _status_kelas(kelas, dasar_aktif), e(soal_per_topik(kelas)))


def halaman(dasar_aktif: bool, *, kelas: Optional[tuple] = None) -> str:
    kepala = "".join(
        '<th scope="col">%s</th>' % e(label)
        for label in ("Kelas", "Topik dan contoh jenis soal", "Soal per topik")
    )
    isi = "".join(_baris(k, dasar_aktif) for k in (kelas or KELAS_CEK))
    return tab_kurikulum(TAB_CEK_TOPIK) + (
        '<section class="admin-kartu admin-kartu-tabel"><div class="admin-kartu-kepala">'
        '<h2>Topik per kelas</h2><span class="admin-meta">%d soal per cek, pilihan ganda</span></div>'
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="Topik cek per kelas">'
        '<table class="admin-tabel"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div></section>'
        '<section class="admin-kartu admin-catatan"><p class="admin-meta">%s</p></section>'
    ) % (skor.JUMLAH_SOAL, kepala, isi, e(
        "Contoh jenis soal diambil dari susunan lembar topik di level kelas itu "
        "(maksimal %d per topik); cek sungguhan memilih soal dari topik tersebut. "
        "Nama jenis soal ditampilkan sebagai id template." % MAKS_CONTOH_PER_TOPIK
    ))
