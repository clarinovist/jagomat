"""Renderer HTML murni draf AI cetakan soal (C3): tombol "Buatkan draf cetakan dengan AI" + ringkasan permintaan.

Tanpa JS, tanpa DB, tanpa I/O. Tombol hanya dirender bila pemanggil memberi token (sesi berkuki) DAN sisa kuota
> 0; kunci API dan kuota diputuskan pemanggil (fail-closed). SEMUA nilai dinamis (judul draf, alasan penolakan
dari AI) di-escape: alasan bisa memuat potongan isi kandidat AI, jadi anggap stored-XSS.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple
from urllib.parse import urlencode

import admin_kurikulum_cetakan_pages as ui
import cetakan_ai_store as kuota
import cetakan_store as store
from admin_komponen import e

RUTE_DRAF_AI = ui.RUTE + "/draf-ai"
AKSI_DRAF_AI = "draf_ai_cetakan_soal"
TOMBOL_DRAF_AI = "Buatkan draf cetakan dengan AI"
LABEL_TAUTAN_TABEL = "Buatkan draf cetakan"
COPY_CATATAN_FORM = (
    "AI hanya diberi kelas, judul bab, dan sub-materi, lalu menulis 1 sampai 3 draf cetakan. Mesin memeriksa "
    "tiap draf dan menghitung kuncinya sendiri; yang lolos masuk sebagai draf untuk Anda periksa, belum aktif. "
    "Permintaan memakan satu slot kuota walau AI gagal, dan bisa berjalan sampai setengah menit."
)
COPY_KUOTA_HABIS = "Kuota draf AI hari ini habis. Cetakan tetap bisa ditulis manual, dan kuota kembali besok (WIB)."
COPY_KUOTA_HABIS_POST = "Kuota draf AI hari ini sudah habis. Tidak ada yang diubah. Coba lagi besok."
COPY_AI_TIDAK_AKTIF = "Draf AI belum tersedia di server ini. Tidak ada yang diubah."
COPY_KUOTA_TIDAK_SIAP = (
    "Pencatat kuota draf AI tidak dapat dibaca atau ditulis di server ini, jadi permintaan tidak dikirim. "
    "Tidak ada yang diubah. Operator perlu memeriksa berkas kuota."
)
COPY_KOSONG = "AI tidak menghasilkan draf yang lolos pemeriksaan mesin kali ini."
COPY_BELUM_SELESAI = "Permintaan draf AI ini belum tercatat selesai. Periksa daftar cetakan bab di bawah."

Token = Tuple[str, str]


def url_daftar_hasil(kelas: int, bab: int, id_permintaan: int) -> str:
    """Tujuan PRG: halaman cetakan bab itu dengan ringkasan permintaan."""
    return "%s&%s" % (ui.url_daftar(kelas, bab), urlencode({"permintaan": id_permintaan}))


def teks_kuota(sisa: int) -> str:
    return "Sisa kuota hari ini: %d dari %d." % (sisa, kuota.BATAS_HARIAN)


def bagian_ai(token: Optional[Token], sisa: Optional[int], kunci_ada: bool) -> str:
    """Kartu draf AI di halaman cetakan bab. Kosong bila kunci tak ada, kuota tak terbaca, atau sesi baca-saja.

    Tombol (form POST) hanya bila kunci ada, sisa > 0, dan ada token; kuota habis = catatan tanpa tombol."""
    if not kunci_ada or sisa is None:
        return ""
    if sisa <= 0:
        return '<section class="admin-kartu"><p class="admin-meta">%s</p></section>' % e(COPY_KUOTA_HABIS)
    if token is None:
        return ""
    return '<section class="admin-kartu"><h2>Draf dari AI</h2><p class="admin-meta">%s</p>%s</section>' % (
        e(teks_kuota(sisa)), ui.form_pindah(RUTE_DRAF_AI, token, COPY_CATATAN_FORM, TOMBOL_DRAF_AI))


def _tautan_draf(item: store.ItemCetakan) -> str:
    return '<li><a href="%s">%s</a></li>' % (e(ui.url_periksa(item.id)), e(item.cetakan.judul))


def _daftar_ditolak(alasan: Sequence[str]) -> str:
    if not alasan:
        return ""
    return '<p class="admin-meta">Ditolak mesin:</p><ul>%s</ul>' % "".join("<li>%s</li>" % e(a) for a in alasan)


def ringkasan(p: kuota.Permintaan, items: Sequence[store.ItemCetakan]) -> str:
    """Ringkasan satu permintaan draf AI. `items` = cetakan bab itu; hanya draf yang benar-benar ada ditautkan."""
    if p.status == kuota.STATUS_BERJALAN:
        return '<p class="admin-kartu admin-catatan" role="status">%s</p>' % e(COPY_BELUM_SELESAI)
    if p.status == kuota.STATUS_GAGAL:
        alasan = "; ".join(p.ditolak) or "tidak diketahui"
        return ('<section class="admin-kartu admin-galat" role="alert"><p>AI belum berhasil membuat draf kali ini. '
                'Slot kuota tetap terpakai.</p><p class="admin-meta">Alasan: %s</p></section>' % e(alasan))
    tautan = "".join(_tautan_draf(i) for i in items if i.id in p.draf)
    judul = ("AI membuat %d draf:" % p.jumlah_draf) if p.jumlah_draf else COPY_KOSONG
    daftar = "<ul>%s</ul>" % tautan if tautan else ""
    return ('<section class="admin-kartu admin-catatan" role="status" aria-atomic="true"><p>%s</p>%s%s</section>'
            % (e(judul), daftar, _daftar_ditolak(p.ditolak)))
