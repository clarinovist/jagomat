"""Render halaman admin baca-saja jurnal pertemuan (`/admin/jadwal/jurnal`). Murni render: tanpa I/O.

Tanpa nama atau id anak dan tanpa order_id. Nama guru dari peta guru aktif; akun yang tidak ada di peta = "Guru tidak
aktif". Semua teks dinamis di-escape. Tidak ada form atau tautan tindakan: halaman ini hanya untuk dibaca.
"""
from __future__ import annotations

import html
from typing import List, Mapping

from pesanan_transfer_pages import waktu_wib

RUTE = "/admin/jadwal/jurnal"
JUDUL = "Jurnal pertemuan"
SUBJUDUL = "Pertemuan yang sudah lewat dan belum dicatat guru. Baca saja; tidak ada tindakan di halaman ini."
JUDUL_PERLU = "Perlu diisi"
JUDUL_RIWAYAT = "Riwayat tidak diisi"
BANNER_BELUM = ("Peringatan jurnal belum aktif. Pertemuan belum dihitung sampai tanggal mulai peringatan diisi "
                "saat rilis.")
BANNER_AKTIF = "Peringatan aktif untuk pertemuan mulai %s."
COPY_CATATAN_TIDAK_TERBACA = "Catatan pertemuan tidak terbaca; daftar mungkin tidak lengkap."
COPY_KOSONG_PERLU = "Tidak ada pertemuan yang perlu diisi saat ini."
COPY_KOSONG_RIWAYAT = "Tidak ada riwayat pertemuan yang belum diisi."
COPY_RIWAYAT_TERPOTONG = "Pembacaan riwayat dibatasi; jumlah riwayat bisa lebih besar dari yang tampak."
COPY_TERPOTONG = "Menampilkan %d terbaru dari %d"
COPY_TIDAK_SIAP = "Jurnal pertemuan belum bisa dibaca di server. Coba lagi beberapa saat."
GURU_TIDAK_AKTIF = "Guru tidak aktif"
KOLOM = ("Kelas", "Pertemuan ke-", "Waktu", "Guru")


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _kotak(teks: str) -> str:
    return '<section class="admin-kartu"><p>%s</p></section>' % _e(teks)


def _banner(daftar: Mapping) -> str:
    if not daftar["aktif"]:
        return _kotak(BANNER_BELUM)
    pesan = [_kotak(BANNER_AKTIF % waktu_wib(daftar["sejak"]))]
    if not daftar["catatan_terbaca"]:
        pesan.append(_kotak(COPY_CATATAN_TIDAK_TERBACA))
    return "".join(pesan)


def _baris(item: Mapping, guru: Mapping[str, str]) -> str:
    return "<tr><td>%s</td><td>%d</td><td>%s</td><td>%s</td></tr>" % (
        _e(item["nama"]), int(item["ke"]), _e(waktu_wib(item["mulai"])),
        _e(guru.get(item["guru_id"], GURU_TIDAK_AKTIF)))


def _tabel(items: List[Mapping], guru: Mapping[str, str]) -> str:
    kepala = "".join("<th>%s</th>" % _e(kolom) for kolom in KOLOM)
    isi = "".join(_baris(item, guru) for item in items)
    return ('<div class="admin-tabel-wrap"><table class="admin-tabel"><thead><tr>%s</tr></thead>'
            "<tbody>%s</tbody></table></div>" % (kepala, isi))


def _seksi(judul: str, total: int, items: List[Mapping], kosong: str, guru: Mapping[str, str],
           catatan: str = "") -> str:
    tambahan = []
    if total > len(items):
        tambahan.append('<p class="admin-ket">%s.</p>' % _e(COPY_TERPOTONG % (len(items), total)))
    if catatan:
        tambahan.append('<p class="admin-ket">%s</p>' % _e(catatan))
    badan = _tabel(items, guru) if items else '<p class="admin-kosong">%s</p>' % _e(kosong)
    return ('<section class="admin-kartu"><h2>%s (%d)</h2>%s%s</section>'
            % (_e(judul), total, "".join(tambahan), badan))


def halaman(daftar: Mapping, guru: Mapping[str, str]) -> str:
    """Isi halaman (tanpa shell admin): banner status, bagian perlu diisi, dan riwayat tidak diisi."""
    catatan_riwayat = COPY_RIWAYAT_TERPOTONG if daftar["riwayat_terpotong"] else ""
    return "".join([
        _banner(daftar),
        _seksi(JUDUL_PERLU, daftar["total_perlu_diisi"], daftar["perlu_diisi"], COPY_KOSONG_PERLU, guru),
        _seksi(JUDUL_RIWAYAT, daftar["total_riwayat"], daftar["riwayat"], COPY_KOSONG_RIWAYAT, guru,
               catatan=catatan_riwayat),
    ])


def halaman_tidak_siap() -> str:
    return '<section class="admin-kartu"><h2>%s</h2><p>%s</p></section>' % (
        _e(JUDUL), _e(COPY_TIDAK_SIAP))
