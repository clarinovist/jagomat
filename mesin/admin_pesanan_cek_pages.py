"""Renderer murni kartu "Data cek untuk laporan" di Detail order admin (irisan D1): tanpa I/O, tanpa form, tanpa JS.

Data hanya hasil allowlist `cek_ringkasan_admin.ringkasan_untuk_order` (atau None = tidak terbaca): skor, kategori,
ringkasan topik, hitungan benar/total per materi, dan keadaan bahan. Kartu ini baca-saja untuk tim yang menulis
laporan; bukan laporan orang tua. Semua nilai dinamis di-escape.
"""
from __future__ import annotations

from typing import Mapping, Optional

from admin_komponen import e
from cek_gratis_skor import RETENSI_SELESAI_HARI
from cek_ringkasan_admin import BAHAN_ADA, BAHAN_DIHAPUS, STATUS_SELESAI

JUDUL = "Data cek untuk laporan"
COPY_TIDAK_TERBACA = "Data cek tidak terbaca"
COPY_BELUM_SELESAI = "Cek belum selesai"
COPY_BELUM_DINILAI = "Belum dinilai"
COPY_BAHAN_ADA = "Data per materi dihapus otomatis dalam %d hari (retensi %d hari). Buat draf laporan sebelum itu."
COPY_BAHAN_DIHAPUS = "Data per materi sudah dihapus (retensi %d hari)"
_STRIP = "—"
_PANJANG_TANGGAL = 10  # YYYY-MM-DD dari waktu selesai


def _baris(label: str, nilai: str) -> str:
    return "<div><dt>%s</dt><dd>%s</dd></div>" % (e(label), nilai)


def _daftar_nama(nama) -> str:
    return e(", ".join(nama)) if nama else _STRIP


def _hasil(cek: Mapping) -> str:
    if cek["status"] != STATUS_SELESAI:
        return e(COPY_BELUM_SELESAI)
    return e("Skor %s dari 100 · %s" % (cek["skor"], cek["kategori"]))


def _tanggal_selesai(cek: Mapping) -> str:
    return e(cek["selesai_pada"][:_PANJANG_TANGGAL]) if cek["selesai_pada"] else _STRIP


def _rincian(cek: Mapping) -> str:
    return "".join((
        _baris("Kelas", e("Kelas %s" % cek["kelas"]) if cek["kelas"] is not None else _STRIP),
        _baris("Hasil", _hasil(cek)),
        _baris("Jumlah soal", e("%s soal" % cek["jumlah_soal"])),
        _baris("Selesai", _tanggal_selesai(cek)),
        _baris("Topik yang sudah kuat", _daftar_nama(cek["ringkasan_kuat"])),
        _baris("Topik yang perlu diperkuat", _daftar_nama(cek["ringkasan_perlu"]))))


def _tabel(per_materi) -> str:
    if not per_materi:
        return ""
    baris = "".join('<tr><th scope="row">%s</th><td>%d</td><td>%d</td></tr>' % (e(b["materi"]), b["benar"], b["total"])
                    for b in per_materi)
    return ('<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="%s"><table class="admin-tabel">'
            '<thead><tr><th scope="col">Materi</th><th scope="col">Benar</th><th scope="col">Dari</th></tr></thead>'
            '<tbody>%s</tbody></table></div>' % (e("Hitungan per materi"), baris))


def _status_bahan(cek: Mapping) -> str:
    if cek["bahan"] == BAHAN_ADA:
        return COPY_BAHAN_ADA % (cek["hari_tersisa"], RETENSI_SELESAI_HARI)
    if cek["bahan"] == BAHAN_DIHAPUS:
        return COPY_BAHAN_DIHAPUS % RETENSI_SELESAI_HARI
    return COPY_BELUM_DINILAI


def kartu(cek: Optional[Mapping]) -> str:
    """Kartu data cek; `cek` None = tidak terbaca (galat baca atau tiga kunci tidak cocok)."""
    kepala = "<h2>%s</h2>" % e(JUDUL)
    if cek is None:
        return '<section class="admin-kartu">%s<p class="admin-meta">%s</p></section>' % (kepala, e(COPY_TIDAK_TERBACA))
    return ('<section class="admin-kartu">%s<dl class="admin-order-rincian">%s</dl>%s<p class="admin-meta">%s</p></section>'
            % (kepala, _rincian(cek), _tabel(cek["per_materi"]), e(_status_bahan(cek))))
