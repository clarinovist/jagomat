"""Komponen bersama permukaan anak untuk sesi Cek Kemampuan gratis.

Murni presentasi: tanpa akses basis data belajar, tanpa kunci/skor/kategori. Satu-satunya
bacaan luar adalah label awam topik (`topik_awam.nama`, bisa diubah admin di DB kurikulum). Palang
murid berlaku (tidak ada benar/salah di layar anak mana pun): jejak soal hanya
membedakan "sudah dijawab" (bintang) dan "masih kosong", bukan benar atau salah.
Semua nilai visual berasal dari ``design_tokens`` (lihat ``cek_anak_style``).
"""
from __future__ import annotations

import functools
import html
import urllib.parse
from dataclasses import dataclass

import brand
import design_tokens as T
import topik_awam
import topics
from cek_anak_style import GAYA_CEK_ANAK

# Cermin `cek_gratis_skor.semua_topik_cek()`; permukaan anak sengaja tidak
# mengimpor modul skor. test_cek_anak menjaga keduanya tetap sama.
TOPIK_CEK = (
    "berhitung-sekolah", "geometri-datar", "statistika", "pengukuran",
    "aritmetika-dasar", "aritmatika-lanjut", "pola-bilangan", "bilangan-dasar",
)
JEDA_SETELAH = (5, 10)
NILAI_DI_HP_INI = "hp-ini"
TUJUAN_LOGIN_HASIL = "/masuk?lanjut=/cek-kemampuan/hasil"
DASAR_URL = "/mulai/"
# Warna ubin per topik: konstanta. Label teksnya BUKAN konstanta: lihat `nama_topik`.
WARNA_TOPIK = {
    "pola-bilangan": "teal",
    "statistika": "koral",
    "geometri-datar": "amber",
    "bilangan-dasar": "navy",
    "berhitung-sekolah": "koral",
    "pengukuran": "teal",
    "aritmetika-dasar": "amber",
    "aritmatika-lanjut": "navy",
}
_STROKE = 'fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"'
IKON_TOPIK = {
    "pola-bilangan": (
        '<circle cx="5" cy="17" r="2" fill="currentColor"/>'
        '<circle cx="11.5" cy="12.5" r="2.5" fill="currentColor"/>'
        '<circle cx="18.5" cy="7" r="3" fill="currentColor"/>'
    ),
    "statistika": '<path d="M4 20h16"/><path d="M7 20v-7M12 20V5M17 20v-10"/>',
    "geometri-datar": '<path d="M3.5 20l5.5-9.5 5.5 9.5z"/><rect x="13" y="3.5" width="7.5" height="7.5" rx="1"/>',
    "bilangan-dasar": '<path d="M12 5v14M5 12h14"/>',
    "berhitung-sekolah": (
        '<path d="M5 5l6 6M11 5l-6 6"/><path d="M14 17h6"/>'
        '<circle cx="17" cy="14" r=".6" fill="currentColor"/><circle cx="17" cy="20" r=".6" fill="currentColor"/>'
    ),
    "pengukuran": (
        '<rect x="3" y="8" width="18" height="8" rx="1.5"/>'
        '<path d="M7 8v3M11 8v4M15 8v3M19 8v4"/>'
    ),
    "aritmetika-dasar": '<path d="M8 4v4M6 6h4"/><path d="M5 20L19 4"/><path d="M14 17h5"/><path d="M14 20h5"/>',
    "aritmatika-lanjut": '<path d="M5 19L19 5"/><circle cx="7" cy="7" r="2.2"/><circle cx="17" cy="17" r="2.2"/>',
}
IKON_JEDA = (
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
    '<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>'
)
IKON_PENSIL = (
    f'<svg width="16" height="16" viewBox="0 0 24 24" {_STROKE} aria-hidden="true">'
    '<path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19z"/></svg>'
)
DOODLE_SAPAAN = (
    '<span style="left:8%;top:9%">+</span><span style="right:10%;top:14%">×</span>'
    '<span style="left:14%;top:60%">÷</span><span style="right:8%;top:56%">½</span>'
    '<span style="left:46%;top:5%">7</span><span style="right:30%;bottom:6%">=</span>'
    '<span style="left:6%;bottom:10%">3</span>'
)
DOODLE_KEPALA = (
    '<span style="left:40%;top:30%">×</span><span style="right:6%;top:52%">+</span>'
    '<span style="left:4%;top:56%">½</span>'
)
DOODLE_PETA = '<span style="left:60%;top:20%">÷</span><span style="left:8%;top:40%">=</span>'
DOODLE_HORE = (
    '<span style="left:8%;top:10%">★</span><span style="right:10%;top:18%">+</span>'
    '<span style="left:12%;bottom:18%">×</span><span style="right:12%;bottom:12%">★</span>'
)
JUMLAH_KONFETI = 30
WARNA_KONFETI = (
    T.AKSEN_MURID_AMBER, T.AKSEN_MURID_KORAL, T.TEKS_PUTIH,
    T.ANAK_HEADER_AVATAR_LATAR, T.LATAR_GALAT,
)


@dataclass(frozen=True)
class Konteks:
    """Token tautan + penanda "Di HP ini"; hanya mengubah copy, bukan akses."""

    token: str
    di_hp_ini: bool = False


def url(k: Konteks, **param) -> str:
    """Alamat halaman anak; parameter ``di`` selalu dibawa bila alur "Di HP ini"."""
    pasangan = [(nama, str(nilai)) for nama, nilai in param.items() if nilai is not None]
    if k.di_hp_ini:
        pasangan.append(("di", NILAI_DI_HP_INI))
    dasar = DASAR_URL + k.token
    return dasar + ("?" + urllib.parse.urlencode(pasangan) if pasangan else "")


def attr(k: Konteks, **param) -> str:
    """``url`` yang aman dipasang di atribut HTML."""
    return html.escape(url(k, **param), quote=True)


def esc(teks) -> str:
    return html.escape(str(teks), quote=True)


@functools.lru_cache(maxsize=1)
def _peta_template() -> dict:
    """template_id -> topik_id untuk topik cek saja; tanpa menyentuh kunci."""
    peta: dict = {}
    for topik_id in TOPIK_CEK:
        for template_id in topics.ambil(topik_id).templates:
            peta.setdefault(template_id, topik_id)
    return peta


def topik_dari_template(template_id: str):
    return _peta_template().get(template_id)


def nama_topik(topik_id: str) -> str:
    """Label awam topik, dibaca saat request (bawaan kode atau hasil ubah admin).

    Satu-satunya teks topik di layar anak. Hanya label; tidak ada kunci, skor, atau diagnosis.
    """
    return topik_awam.nama(topik_id)


def ubin_topik(topik_id: str, ukuran: str = "") -> str:
    """Ubin ikon topik (hiasan; nama topik ada sebagai teks di sebelahnya)."""
    warna = WARNA_TOPIK[topik_id]
    gaya = f' style="--u:{ukuran}"' if ukuran else ""
    return (
        f'<span class="ubin {warna}"{gaya}><svg width="16" height="16" viewBox="0 0 24 24" '
        f'{_STROKE} aria-hidden="true">{IKON_TOPIK[topik_id]}</svg></span>'
    )


def label_topik(template_id: str) -> str:
    topik_id = topik_dari_template(template_id)
    if topik_id is None:
        return ""
    return f'<span class="label-materi">{ubin_topik(topik_id)}{esc(nama_topik(topik_id))}</span>'


def konfeti() -> str:
    """Konfeti CSS; posisi tetap dari rumus (tanpa acak) supaya HTML deterministik."""
    potongan = []
    for i in range(JUMLAH_KONFETI):
        kiri = (i * 37 + 11) % 100
        tunda = ((i * 13) % 8) / 10
        warna = WARNA_KONFETI[i % len(WARNA_KONFETI)]
        potongan.append(
            f'<i style="left:{kiri}%;animation-delay:{tunda:.1f}s;background:{warna}"></i>'
        )
    return f'<div class="konfeti" aria-hidden="true">{"".join(potongan)}</div>'


def stiker(jumlah: int) -> str:
    """Stiker usaha "Pejuang N Soal" (usaha, bukan kemampuan); teks lurus >= 14px."""
    gaya = f'stroke="{T.TEKS_JUDUL}" stroke-linejoin="round"'
    huruf = f'font-family="Plus Jakarta Sans,sans-serif" font-weight="800" fill="{T.TEKS_JUDUL}" text-anchor="middle"'
    return (
        '<svg viewBox="0 0 170 170" aria-hidden="true" focusable="false">'
        '<path d="M85 6l14 17 21-6 4 22 21 7-8 20 13 17-18 12 2 22-22 2-9 20-19-10-19 10-9-20-22-2 '
        f'2-22-18-12 13-17-8-20 21-7 4-22 21 6z" fill="{T.AKSEN_MURID_AMBER}" {gaya} stroke-width="4"/>'
        f'<circle cx="85" cy="85" r="52" fill="{T.LATAR_KARTU}" {gaya} stroke-width="3"/>'
        '<path transform="translate(85 56) scale(.5) translate(-85 -80)" '
        'd="M85 52l9 18 20 3-14.5 14 3.5 20L85 97.5 67 107l3.5-20L56 73l20-3z" '
        f'fill="{T.AKSEN_MURID_KORAL}" {gaya} stroke-width="3"/>'
        f'<text x="85" y="97" font-size="12.5" {huruf}>PEJUANG</text>'
        f'<text x="85" y="116" font-size="14" {huruf}>{int(jumlah)} SOAL</text></svg>'
    )


def kepala_teal(isi_baris: str, doodle: str, *, tambahan: str = "") -> str:
    """Kepala berlatar teal berisi doodle matematika (dekoratif)."""
    return (
        f'<header class="kepala-anak"><div class="doodle" aria-hidden="true">{doodle}</div>'
        f'<div class="baris">{isi_baris}</div>{tambahan}</header>'
    )


def kerangka(judul: str, isi: str, *, skrip: str = "") -> bytes:
    """Dokumen lengkap halaman anak cek; CSS hanya dimuat di sini."""
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@700;800&display=swap" rel="stylesheet">
<style>{GAYA_CEK_ANAK}</style></head>
<body class="cek-anak"><div class="bingkai">
{isi}
</div>{skrip}</body></html>""".encode()
