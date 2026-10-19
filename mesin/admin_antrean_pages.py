"""DTO dan renderer antrean "Perlu ditangani" panel pengelola; murni, tanpa I/O."""
from __future__ import annotations

from dataclasses import dataclass
import html
from typing import Optional, Tuple

BATAS_BARIS = 50
LABEL_TINGKAT = {"mendesak": "Mendesak", "penting": "Penting", "tinjau": "Tinjau"}


@dataclass(frozen=True)
class ItemAntrean:
    """Satu baris antrean. ``umur_hari`` None berarti waktu awal tidak tercatat."""

    tingkat: str
    judul: str
    deskripsi: str
    jalur: str
    cta: str
    ref_awalan: str = ""
    ref: str = ""
    umur_hari: Optional[int] = None


@dataclass(frozen=True)
class AntreanAdmin:
    item: Tuple[ItemAntrean, ...] = ()
    total: int = 0
    mendesak: int = 0
    layanan_tersedia: bool = True
    bukti_backup: str = "Belum terverifikasi"
    backup_terverifikasi: bool = False


@dataclass(frozen=True)
class SinyalNav:
    """Penanda sidebar; dihitung dari antrean yang sama dengan Ringkasan."""

    total: int = 0
    mendesak: int = 0
    operasional_perhatian: bool = False


def sinyal_dari(antrean: AntreanAdmin) -> SinyalNav:
    return SinyalNav(
        antrean.total, antrean.mendesak,
        antrean.mendesak > 0 or not antrean.backup_terverifikasi,
    )


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _umur(item: ItemAntrean) -> str:
    if item.umur_hari is None:
        return ('<span class="admin-umur"><span aria-hidden="true">—</span>'
                '<span class="admin-sr">Umur tidak tersedia</span></span>')
    teks = "Hari ini" if item.umur_hari == 0 else "%d hari" % item.umur_hari
    kelas = " admin-umur-mendesak" if item.tingkat == "mendesak" else ""
    return '<span class="admin-umur%s">%s</span>' % (kelas, _e(teks))


def _baris(item: ItemAntrean, *, solid: bool) -> str:
    tingkat = item.tingkat if item.tingkat in LABEL_TINGKAT else "tinjau"
    ref = ('%s <code class="admin-ref">%s</code> ' % (_e(item.ref_awalan), _e(item.ref))
           if item.ref else "")
    return (
        '<li class="admin-antrean-item">'
        '<span class="admin-urgensi admin-urgensi-%s"><span class="admin-titik" aria-hidden="true"></span>%s</span>'
        '<div class="admin-antrean-isi"><h3>%s</h3><p>%s%s</p></div>%s'
        '<a class="%s" href="%s">%s</a></li>'
        % (tingkat, LABEL_TINGKAT[tingkat], _e(item.judul), ref, _e(item.deskripsi), _umur(item),
           "admin-tombol" if solid else "admin-antrean-cta", _e(item.jalur), _e(item.cta))
    )


def render_antrean(antrean: AntreanAdmin) -> str:
    sisa = antrean.total - len(antrean.item)
    if antrean.item:
        baris = "".join(_baris(item, solid=indeks == 0) for indeks, item in enumerate(antrean.item))
        if sisa > 0:
            baris += '<li class="admin-antrean-sisa">dan %d lainnya</li>' % sisa
        isi = '<ol class="admin-antrean">%s</ol>' % baris
    else:
        isi = ('<p class="admin-antrean-kosong">Tidak ada kondisi administratif yang perlu '
               'perhatian pada sumber yang tersedia.</p>')
    catatan = (
        "Satu baris per item. Satu keluarga atau siswa dapat muncul di lebih dari satu baris bila "
        "punya lebih dari satu masalah. Umur hanya tampil untuk item yang waktu awal masalahnya tercatat."
        + ("" if antrean.layanan_tersedia else " Jumlah antrean layanan belum tersedia.")
    )
    return (
        '<section class="admin-kartu admin-prioritas" aria-labelledby="judul-antrean">'
        '<header class="admin-prioritas-kepala"><h2 id="judul-antrean">Perlu ditangani</h2>'
        '<p class="admin-prioritas-ket">Diurutkan dari yang paling berisiko · tiap item dihitung sekali</p></header>'
        '%s<p class="admin-antrean-catatan">%s</p></section>' % (isi, _e(catatan))
    )
