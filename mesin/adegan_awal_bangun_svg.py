"""Gambar satu bangun datar atau ruang untuk sub-adegan `bentuk` (SVG murni, tanpa transform).

Koordinat dihitung langsung (rotasi segitiga kelipatan 90 derajat ditukar-tanda, bukan
`rotate`), dibulatkan dua desimal, deterministik. Hanya elemen `polygon`, `circle`, `ellipse`,
dan `line`; jenis bangun hanya terbaca dari GEOMETRI (tanpa kelas atau atribut bernama bangun).

Bangun datar = TEPAT SATU elemen (`polygon` 3 atau 4 titik, atau `circle`).
Bangun ruang = beberapa elemen, dengan tanda tangan geometri:
  - kubus : tiga `polygon` 4 titik; sisi depan persegi (tepi sejajar sumbu, lebar = tinggi);
  - balok : tiga `polygon` 4 titik; sisi depan persegi panjang (rasio >= 1,5);
  - bola  : tiga `circle` bersarang (bayangan, sorot, kilap);
  - tabung: dua `ellipse` + satu `polygon` 4 titik (badan) + dua `line` (tepi samping);
  - kerucut: satu `ellipse` (alas) + satu `polygon` 3 titik (badan) + dua `line`.
Oblik standar kubus/balok: sisi depan tegak lurus, kedalaman miring ke kanan-atas setengah
panjang. Garis tepi gelap (`T.TEKS_UTAMA`) tebal, jadi warna bukan satu-satunya pembeda.
"""
from __future__ import annotations

import math

import bentuk_katalog as K
import design_tokens as T

_NADA = {"biru": T.ADEGAN_BANGUN_BIRU, "kuning": T.ADEGAN_BANGUN_KUNING,
         "hijau": T.ADEGAN_BANGUN_HIJAU}
TERANG, SEDANG, GELAP = 0, 1, 2
_TINGGI_SAMASISI = math.sqrt(3) / 4
# Titik segitiga pada kotak satuan berpusat di nol (x ke kanan, y ke bawah).
_SEGITIGA = {
    "samasisi": ((0.0, -_TINGGI_SAMASISI), (-0.5, _TINGGI_SAMASISI), (0.5, _TINGGI_SAMASISI)),
    "siku": ((-0.5, -0.375), (-0.5, 0.375), (0.5, 0.375)),  # sisi 1 : 0,75 : 1,25
    "sembarang": ((-0.5, 0.4), (0.5, 0.4), (0.2, -0.4)),
}
_ISI_DATAR = 0.9  # bagian kotak yang dipakai bangun terbesar
_SISI_PERSEGI = 0.72
_PANJANG_PERSEGI_PANJANG, _LEBAR_PERSEGI_PANJANG = 0.9, 0.5  # rasio 1,8
_RADIUS_LINGKARAN = 0.45
# Balok/kubus: (lebar, tinggi, dalam) relatif; kedalaman digambar setengahnya ke kanan-atas.
_BALOK = {
    "kubus": {"biasa": (1.0, 1.0, 1.0)},
    "balok": {"mendatar": (1.0, 0.55, 0.8), "tegak": (0.55, 1.0, 0.8)},
}
_SKALA_KEDALAMAN = 0.5
_RADIUS_BOLA = 0.45
_TABUNG = {"rx": 0.30, "ry": 0.13, "badan": 0.58}
_KERUCUT = {"rx": 0.33, "ry": 0.14, "tinggi": 0.64}


def _n(nilai: float) -> str:
    return f"{round(nilai, 2) + 0.0:g}"


def _titik(titik) -> str:
    return " ".join(f"{_n(x)},{_n(y)}" for x, y in titik)


def _gaya(isi: str, tepi: bool = True) -> str:
    garis = f'stroke="{T.TEKS_UTAMA}"' if tepi else 'stroke="none"'
    return f'fill="{isi}" {garis} stroke-width="{T.ADEGAN_BANGUN_TEBAL}"'


def _polygon(titik, isi: str, tepi: bool = True) -> str:
    return f'<polygon points="{_titik(titik)}" {_gaya(isi, tepi)}/>'


def _lingkaran(cx: float, cy: float, r: float, isi: str, tepi: bool = True) -> str:
    return f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" {_gaya(isi, tepi)}/>'


def _elips(cx: float, cy: float, rx: float, ry: float, isi: str) -> str:
    return f'<ellipse cx="{_n(cx)}" cy="{_n(cy)}" rx="{_n(rx)}" ry="{_n(ry)}" {_gaya(isi)}/>'


def _garis(x1: float, y1: float, x2: float, y2: float) -> str:
    return (f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
            f'stroke="{T.TEKS_UTAMA}" stroke-width="{T.ADEGAN_BANGUN_TEBAL}"/>')


def _putar_90(titik, kali: int):
    """Putar searah jarum jam `kali` x 90 derajat pada pusat (x, y) -> (-y, x); eksak, tanpa sin/cos."""
    for _ in range(kali % 4):
        titik = tuple((-y, x) for x, y in titik)
    return titik


def _segitiga(ragam: str, putar: int, cx: float, cy: float, kotak: float, isi: str) -> str:
    titik = _putar_90(_SEGITIGA[ragam], putar // 90)
    xs, ys = [x for x, _ in titik], [y for _, y in titik]
    skala = _ISI_DATAR * kotak / max(max(xs) - min(xs), max(ys) - min(ys))
    tengah_x, tengah_y = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return _polygon(tuple((cx + (x - tengah_x) * skala, cy + (y - tengah_y) * skala)
                          for x, y in titik), isi)


def _persegi_panjang(lebar: float, tinggi: float, cx: float, cy: float, isi: str) -> str:
    return _polygon(((cx - lebar / 2, cy - tinggi / 2), (cx + lebar / 2, cy - tinggi / 2),
                     (cx + lebar / 2, cy + tinggi / 2), (cx - lebar / 2, cy + tinggi / 2)), isi)


def _datar(nama: str, ragam: str, putar: int, cx: float, cy: float, kotak: float, nada) -> str:
    isi = nada[SEDANG]
    if nama == "segitiga":
        return _segitiga(ragam, putar, cx, cy, kotak, isi)
    if nama == "persegi":
        sisi = _SISI_PERSEGI * kotak
        return _persegi_panjang(sisi, sisi, cx, cy, isi)
    if nama == "persegi panjang":
        panjang, lebar = _PANJANG_PERSEGI_PANJANG * kotak, _LEBAR_PERSEGI_PANJANG * kotak
        sisi = (panjang, lebar) if ragam == "mendatar" else (lebar, panjang)
        return _persegi_panjang(*sisi, cx, cy, isi)
    return _lingkaran(cx, cy, _RADIUS_LINGKARAN * kotak, isi)


def _balok(nama: str, ragam: str, cx: float, cy: float, kotak: float, nada) -> str:
    lebar, tinggi, dalam = _BALOK[nama][ragam]
    mundur = dalam * _SKALA_KEDALAMAN
    f = _ISI_DATAR * kotak / max(lebar + mundur, tinggi + mundur)
    w, h, m = lebar * f, tinggi * f, mundur * f
    kiri, bawah = cx - (w + m) / 2, cy + (h + m) / 2
    atas = bawah - h
    depan = ((kiri, atas), (kiri + w, atas), (kiri + w, bawah), (kiri, bawah))
    puncak = ((kiri, atas), (kiri + m, atas - m), (kiri + w + m, atas - m), (kiri + w, atas))
    samping = ((kiri + w, atas), (kiri + w + m, atas - m), (kiri + w + m, bawah - m),
               (kiri + w, bawah))
    return (_polygon(depan, nada[SEDANG]) + _polygon(puncak, nada[TERANG])
            + _polygon(samping, nada[GELAP]))


def _bola(cx: float, cy: float, kotak: float, nada) -> str:
    r = _RADIUS_BOLA * kotak
    return (_lingkaran(cx, cy, r, nada[GELAP])
            + _lingkaran(cx - 0.12 * r, cy - 0.12 * r, 0.82 * r, nada[SEDANG], tepi=False)
            + _lingkaran(cx - 0.3 * r, cy - 0.3 * r, 0.38 * r, nada[TERANG], tepi=False))


def _tabung(cx: float, cy: float, kotak: float, nada) -> str:
    rx, ry, badan = (_TABUNG[k] * kotak for k in ("rx", "ry", "badan"))
    atas, bawah = cy - badan / 2, cy + badan / 2
    rect = ((cx - rx, atas), (cx + rx, atas), (cx + rx, bawah), (cx - rx, bawah))
    return (_elips(cx, bawah, rx, ry, nada[SEDANG]) + _polygon(rect, nada[SEDANG], tepi=False)
            + _garis(cx - rx, atas, cx - rx, bawah) + _garis(cx + rx, atas, cx + rx, bawah)
            + _elips(cx, atas, rx, ry, nada[TERANG]))


def _kerucut(cx: float, cy: float, kotak: float, nada) -> str:
    rx, ry, tinggi = (_KERUCUT[k] * kotak for k in ("rx", "ry", "tinggi"))
    puncak = cy - (tinggi + ry) / 2
    alas = puncak + tinggi
    badan = ((cx, puncak), (cx - rx, alas), (cx + rx, alas))
    return (_elips(cx, alas, rx, ry, nada[GELAP]) + _polygon(badan, nada[SEDANG], tepi=False)
            + _garis(cx, puncak, cx - rx, alas) + _garis(cx, puncak, cx + rx, alas))


def _ruang(nama: str, ragam: str, cx: float, cy: float, kotak: float, nada) -> str:
    if nama in _BALOK:
        return _balok(nama, ragam, cx, cy, kotak, nada)
    return {"bola": lambda: _bola(cx, cy, kotak, nada),
            "tabung": lambda: _tabung(cx, cy, kotak, nada),
            "kerucut": lambda: _kerucut(cx, cy, kotak, nada)}[nama]()


def gambar_bangun(bangun, cx: float, cy: float, kotak: float) -> str:
    """Markup satu bangun dari item descriptor tervalidasi, berpusat di (cx, cy) dalam `kotak`."""
    nama = bangun["nama"]
    nada = _NADA[bangun["warna"]]
    if nama in K.RUANG:
        return _ruang(nama, bangun["ragam"], cx, cy, kotak, nada)
    return _datar(nama, bangun["ragam"], bangun["putar"], cx, cy, kotak, nada)
