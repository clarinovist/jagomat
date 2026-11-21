"""Gambar SVG topik Bangun Datar/Ruang untuk Latihan Lomba.

Semua bentuk, kisi, kubus, dan balok dibuat sendiri dari poligon, garis, dan kotak.
Tiap elemen yang dihitung anak diberi atribut `data-*` supaya tes bisa menghitung
ulang apa yang benar-benar tergambar. `aria-label` selalu netral dan tanpa angka.
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Sequence, Tuple

import contest_svg_common as S
import design_tokens as T

KOTAK_PILIHAN = 100
SETENGAH_PILIHAN = 38
SEL_KISI = 30
MARGIN = 14
ALT_BENTUK = "Gambar bentuk"
ALT_BENDA = "Gambar benda"
JARAK_BENTUK = 72
TINGGI_BARIS_BENTUK = 90
SETENGAH_BARIS_BENTUK = 30
EMOJI_UKURAN = 62
TITIK_RUANG_JARI = 2.5
KUBUS_JARI = 17
KUBUS_JARAK_X = 36
KUBUS_JARAK_Y = 38
SATUAN_GARIS = 80
TEPI_GARIS = 28
SEL_TEMPEL = 44
TEPI_TEMPEL = 46
UKURAN_LABEL_SISI = 16

_POLA_TAG_BUKA = re.compile(r"^<([A-Za-z]+)")
Titik = Tuple[float, float]


def atribut_data(**data) -> str:
    return "".join(f' data-{nama.replace("_", "-")}="{S.esc(nilai)}"' for nama, nilai in data.items())


def tandai(elemen: str, **data) -> str:
    """Sisipkan atribut `data-*` pada elemen SVG (primitif umum tidak menerimanya)."""
    return _POLA_TAG_BUKA.sub(lambda m: f"<{m.group(1)}{atribut_data(**data)}", elemen, count=1)


def bungkus_data(isi: str, lebar, tinggi, alt: str, **data) -> str:
    return tandai(S.bungkus(isi, lebar, tinggi, alt), **data)


def _beraturan(sisi: int, jari: float = 0.95) -> Tuple[Titik, ...]:
    return tuple((jari * math.cos(math.radians(-90 + 360 * i / sisi)),
                  jari * math.sin(math.radians(-90 + 360 * i / sisi))) for i in range(sisi))


# Titik sudut tiap bentuk pada kotak satuan -1..1; lingkaran digambar terpisah.
TITIK_BENTUK: Dict[str, Tuple[Titik, ...]] = {
    "persegi": ((-0.8, -0.8), (0.8, -0.8), (0.8, 0.8), (-0.8, 0.8)),
    "persegi panjang": ((-1, -0.6), (1, -0.6), (1, 0.6), (-1, 0.6)),
    "segitiga": ((0, -0.9), (0.95, 0.8), (-0.95, 0.8)),
    "belah ketupat": ((0, -1), (0.75, 0), (0, 1), (-0.75, 0)),
    "jajar genjang": ((-0.6, -0.6), (1, -0.6), (0.6, 0.6), (-1, 0.6)),
    "trapesium": ((-0.5, -0.6), (0.5, -0.6), (1, 0.6), (-1, 0.6)),
    "layang-layang": ((0, -1), (0.7, -0.2), (0, 0.9), (-0.7, -0.2)),
    "segilima": _beraturan(5),
    "segienam": _beraturan(6),
}
BENTUK_DATAR = ("lingkaran",) + tuple(TITIK_BENTUK)
WARNA_BENTUK = {
    "persegi": T.GEO_LOMBA_MERAH, "persegi panjang": T.GEO_LOMBA_KUNING,
    "segitiga": T.GEO_LOMBA_MERAH, "belah ketupat": T.GEO_LOMBA_BIRU,
    "jajar genjang": T.GEO_LOMBA_HIJAU, "trapesium": T.GEO_LOMBA_KUNING,
    "layang-layang": T.GEO_LOMBA_HIJAU_MUDA, "segilima": T.GEO_LOMBA_HIJAU,
    "segienam": T.GEO_LOMBA_BIRU_MUDA,
}


def gambar_bentuk(nama: str, cx, cy, setengah) -> str:
    """Satu bentuk datar bertanda `data-bangun`; lingkaran putih, lainnya berwarna."""
    if nama == "lingkaran":
        return tandai(S.lingkaran(cx, cy, setengah * 0.9), bangun=nama)
    titik = [(cx + x * setengah, cy + y * setengah) for x, y in TITIK_BENTUK[nama]]
    return tandai(S.poligon(titik, isi=WARNA_BENTUK[nama]), bangun=nama)


def gambar_pilihan_bentuk(nama: str) -> str:
    """Gambar satu pilihan bentuk; `aria-label` sama untuk semua dan tidak menyebut bentuk."""
    isi = gambar_bentuk(nama, KOTAK_PILIHAN / 2, KOTAK_PILIHAN / 2, SETENGAH_PILIHAN)
    return S.bungkus(isi, KOTAK_PILIHAN, KOTAK_PILIHAN, ALT_BENTUK)


def gambar_pilihan_benda(emoji: str, benda: str, bangun: str) -> str:
    """Satu pilihan benda sehari-hari: satu emoji di tengah kotak."""
    isi = tandai(S.teks(KOTAK_PILIHAN / 2, KOTAK_PILIHAN / 2 + 2, emoji, ukuran=EMOJI_UKURAN),
                 benda=benda, bangun=bangun)
    return S.bungkus(isi, KOTAK_PILIHAN, KOTAK_PILIHAN, ALT_BENDA)


def gambar_barisan_bentuk(daftar: Sequence[str]) -> str:
    """Bentuk-bentuk berjajar dalam satu baris, di tengah kanvas."""
    mulai = (T.GEO_LEBAR - JARAK_BENTUK * len(daftar)) / 2 + JARAK_BENTUK / 2
    isi = "".join(gambar_bentuk(nama, mulai + indeks * JARAK_BENTUK, TINGGI_BARIS_BENTUK / 2,
                                SETENGAH_BARIS_BENTUK) for indeks, nama in enumerate(daftar))
    return S.bungkus(isi, T.GEO_LEBAR, TINGGI_BARIS_BENTUK, "Gambar bangun-bangun")


def sel_kisi(sel: Sequence[Sequence[int]], ukuran, x0, y0, isi: str) -> str:
    """Kotak satuan bertanda `data-sel="baris,kolom"` (baris dari atas, kolom dari kiri)."""
    return "".join(tandai(S.kotak(x0 + kolom * ukuran, y0 + baris * ukuran, ukuran, ukuran, isi=isi),
                          sel=f"{baris},{kolom}") for baris, kolom in sorted(map(tuple, sel)))


def gambar_sel(sel: Sequence[Sequence[int]], isi: str, alt: str, **data) -> str:
    """Gambar himpunan sel satuan lengkap dengan bingkai kanvas."""
    baris = max(r for r, _ in sel) + 1
    kolom = max(c for _, c in sel) + 1
    lebar = kolom * SEL_KISI + 2 * MARGIN
    tinggi = baris * SEL_KISI + 2 * MARGIN
    return bungkus_data(sel_kisi(sel, SEL_KISI, MARGIN, MARGIN, isi), lebar, tinggi, alt, **data)


def kubus_kecil(cx, cy, jari) -> str:
    """Kubus kecil tampak miring: segi enam bertanda `data-kubus` dan tiga garis rusuk depan."""
    titik = [(cx + jari * math.cos(math.radians(-90 + 60 * i)),
              cy + jari * math.sin(math.radians(-90 + 60 * i))) for i in range(6)]
    badan = tandai(S.poligon(titik, isi=T.GEO_LOMBA_BIRU_MUDA), kubus="1")
    rusuk = "".join(S.garis(cx, cy, *titik[i], tebal=T.GEO_GARIS_TIPIS) for i in (1, 3, 5))
    return badan + rusuk


def gambar_lapisan_kubus(baris: int, kolom: int) -> str:
    isi = "".join(kubus_kecil(MARGIN + KUBUS_JARI + c * KUBUS_JARAK_X,
                              MARGIN + KUBUS_JARI + r * KUBUS_JARAK_Y, KUBUS_JARI)
                  for r in range(baris) for c in range(kolom))
    return S.bungkus(isi, kolom * KUBUS_JARAK_X + 2 * MARGIN - (KUBUS_JARAK_X - 2 * KUBUS_JARI),
                     baris * KUBUS_JARAK_Y + 2 * MARGIN - (KUBUS_JARAK_Y - 2 * KUBUS_JARI),
                     "Gambar lapisan kubus kecil")


def diagram_garis(w: int, h: int, garis_dalam: Sequence[Sequence[int]]) -> str:
    """Persegi/persegi panjang w x h satuan dengan garis dalam; tiap garis bertanda `data-garis`."""
    u, t = SATUAN_GARIS, TEPI_GARIS
    sudut = [(0, 0), (w, 0), (w, h), (0, h)]
    isi = S.kotak(t, t, w * u, h * u, isi=T.GEO_LOMBA_KREM, garis_warna=T.GEO_LOMBA_KREM)
    for indeks in range(4):
        (x1, y1), (x2, y2) = sudut[indeks], sudut[(indeks + 1) % 4]
        isi += tandai(S.garis(t + x1 * u, t + y1 * u, t + x2 * u, t + y2 * u), garis="sisi")
    for x1, y1, x2, y2 in garis_dalam:
        isi += tandai(S.garis(t + x1 * u, t + y1 * u, t + x2 * u, t + y2 * u), garis="dalam")
    return S.bungkus(isi, w * u + 2 * t, h * u + 2 * t, "Gambar bangun dengan garis di dalamnya")


def _poligon_ruang(titik: Sequence[Titik], isi: str, nama: str, tersembunyi: bool = False) -> str:
    garis_warna = T.GEO_LOMBA_LATAR if tersembunyi else None
    return tandai(S.poligon(titik, isi=isi, garis_warna=garis_warna), sisi=nama)


def bangun_ruang(nama: str, x0, y0, lebar, tinggi, dx, dy) -> str:
    """Balok/kubus tampak miring: 6 sisi, 12 rusuk (3 putus-putus), 8 titik sudut, semua bertanda."""
    d = [(x0, y0 + tinggi), (x0 + lebar, y0 + tinggi), (x0 + lebar, y0), (x0, y0)]
    b = [(x + dx, y - dy) for x, y in d]
    tersembunyi = ((b, T.GEO_LOMBA_LATAR), ([d[0], d[3], b[3], b[0]], T.GEO_LOMBA_LATAR),
                   ([d[0], d[1], b[1], b[0]], T.GEO_LOMBA_LATAR))
    terlihat = ((d, T.GEO_LOMBA_BIRU_MUDA), ([d[3], d[2], b[2], b[3]], T.GEO_LOMBA_HIJAU_MUDA),
                ([d[1], d[2], b[2], b[1]], T.GEO_LOMBA_KREM))
    isi = "".join(_poligon_ruang(p, w, nama, True) for p, w in tersembunyi)
    isi += "".join(_poligon_ruang(p, w, nama) for p, w in terlihat)
    rusuk: List[Tuple[Titik, Titik, bool]] = []
    for i in range(4):
        j = (i + 1) % 4
        rusuk += [(d[i], d[j], False), (b[i], b[j], i in (0, 3)), (d[i], b[i], i == 0)]
    for (x1, y1), (x2, y2), putus in rusuk:
        extra = {"stroke_dasharray": T.GEO_PUTUS} if putus else {}
        isi += tandai(S.garis(x1, y1, x2, y2, tebal=T.GEO_GARIS_TIPIS, **extra), rusuk=nama)
    isi += "".join(tandai(S.lingkaran(x, y, TITIK_RUANG_JARI, isi=T.GEO_LOMBA_GARIS), titik=nama)
                   for x, y in d + b)
    return isi + tandai(S.teks(x0 + lebar / 2 + dx / 2, y0 + tinggi + 18, nama, ukuran=T.GEO_FONT),
                        label=nama)


def gambar_balok_dan_kubus() -> str:
    isi = bangun_ruang("balok", 40, 60, 90, 56, 40, 28)
    isi += bangun_ruang("kubus", 200, 52, 64, 64, 32, 32)
    return S.bungkus(isi, T.GEO_LEBAR, 160, "Gambar sebuah balok dan sebuah kubus")


def gambar_tempel(sisi: int, banyak: int, arah: str) -> str:
    """Persegi-persegi bersisi `sisi` cm ditempel mendatar/tegak; panjang sisi dilabeli di dua tepi."""
    u, t = SEL_TEMPEL, TEPI_TEMPEL
    sel = [[0, c] for c in range(banyak)] if arah == "mendatar" else [[r, 0] for r in range(banyak)]
    label = f"{sisi} cm"
    isi = sel_kisi(sel, u, t, t, T.GEO_LOMBA_BIRU_MUDA)
    isi += S.teks(t + u / 2, t / 2, label, ukuran=UKURAN_LABEL_SISI)
    isi += S.teks(t - 6, t + u / 2, label, ukuran=UKURAN_LABEL_SISI, jangkar="end")
    lebar = (banyak if arah == "mendatar" else 1) * u + 2 * t
    tinggi = (banyak if arah == "tegak" else 1) * u + 2 * t
    return bungkus_data(isi, lebar, tinggi, "Gambar persegi-persegi yang ditempel", sisi=sisi)
