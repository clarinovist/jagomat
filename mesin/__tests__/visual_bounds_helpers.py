"""Oracle koordinat SVG aktual, bukan mesin layout/font browser.

Anchor text/tspan, points, ujung line, serta batas circle/ellipse/rect diuji
setelah translate/scale. Tidak menghitung font bbox, stroke, atau kurva path.
Defs/pattern/clipPath bukan geometri layar. Clipping elemen terlihat tidak
menjadi alasan untuk melewatkan pemeriksaan; renderer kini tidak memerlukannya.
"""
import math
import re

IDENTITAS = (1.0, 1.0, 0.0, 0.0)
TOLERANSI = 1e-6  # Renderer membulatkan koordinat ke enam tempat desimal.
DEFINISI = frozenset(("defs", "pattern", "clipPath", "mask", "symbol", "marker"))


def _angka(teks):
    try:
        nilai = tuple(float(n) for n in teks.replace(",", " ").split())
    except ValueError as galat:
        raise AssertionError(f"Koordinat bukan angka polos: {teks!r}") from galat
    assert nilai and all(math.isfinite(n) for n in nilai), teks
    return nilai


def _nilai(elemen, nama, bawaan="0"):
    nilai = _angka(elemen.get(nama, bawaan))
    assert len(nilai) == 1, (nama, nilai)
    return nilai[0]


def _gabung(induk, anak):
    """Komposisi induk × anak; translasi anak juga terkena skala induk."""
    sx, sy, dx, dy = induk
    ax, ay, bx, by = anak
    return sx * ax, sy * ay, sx * bx + dx, sy * by + dy


def _transform(teks):
    hasil = IDENTITAS
    sisa = teks.strip()
    while sisa:
        cocok = re.match(r"(translate|scale)\s*\(([^()]*)\)", sisa)
        assert cocok is not None, f"Transform belum didukung oracle: {teks!r}"
        nama, isi = cocok.groups()
        nilai = _angka(isi)
        assert len(nilai) in (1, 2), (nama, nilai)
        a = nilai[0]
        b = nilai[1] if len(nilai) == 2 else (0 if nama == "translate" else a)
        langkah = (1, 1, a, b) if nama == "translate" else (a, b, 0, 0)
        hasil = _gabung(hasil, langkah)
        sisa = sisa[cocok.end():].lstrip(" ,\t\r\n")
    return hasil


def _titik_lokal(elemen, tag):
    if tag in ("text", "tspan"):
        if not (elemen.text or "").strip():
            return ()  # Pembungkus tspan tidak memiliki glyph sendiri.
        assert not any(k in elemen.attrib for k in ("dx", "dy")), "Offset teks belum didukung"
        if tag == "tspan":
            assert "x" in elemen.attrib and "y" in elemen.attrib, "tspan wajib anchor eksplisit"
        return ((_nilai(elemen, "x"), _nilai(elemen, "y")),)
    if tag == "line":
        return tuple((_nilai(elemen, "x" + n), _nilai(elemen, "y" + n)) for n in ("1", "2"))
    if tag in ("polygon", "polyline"):
        nilai = _angka(elemen.get("points", ""))
        assert len(nilai) >= 4 and len(nilai) % 2 == 0, (tag, nilai)
        return tuple(zip(nilai[::2], nilai[1::2]))
    if tag in ("circle", "ellipse"):
        cx, cy = _nilai(elemen, "cx"), _nilai(elemen, "cy")
        rx = _nilai(elemen, "r" if tag == "circle" else "rx")
        ry = rx if tag == "circle" else _nilai(elemen, "ry")
        assert rx >= 0 and ry >= 0, (tag, rx, ry)
        return ((cx-rx, cy-ry), (cx+rx, cy+ry))
    if tag in ("rect", "image"):
        x, y = _nilai(elemen, "x"), _nilai(elemen, "y")
        w, h = _nilai(elemen, "width"), _nilai(elemen, "height")
        assert w >= 0 and h >= 0, (tag, w, h)
        return ((x, y), (x+w, y+h))
    assert tag in ("g", "title", "desc", "path"), f"Elemen belum didukung oracle: {tag}"
    return ()  # Path hanya diperiksa finite oleh gate pemanggil, bukan bbox.


def _tanpa_putar_ikon(elemen, teks):
    """Buang `rotate(<kelipatan 90> cx cy)` dari <image> persegi yang berputar di pusatnya sendiri.

    Hanya kasus itu yang kotaknya tidak berubah, jadi aman tanpa matriks rotasi umum; putaran
    lain (sudut lain, pusat lain, bukan persegi, atau elemen selain <image>) tetap gagal.
    """
    cocok = re.fullmatch(r"\s*rotate\(\s*(-?\d+)\s+([-\d.]+)\s+([-\d.]+)\s*\)\s*", teks)
    assert cocok is not None, f"Transform belum didukung oracle: {teks!r}"
    sudut, cx, cy = int(cocok[1]), float(cocok[2]), float(cocok[3])
    x, y = _nilai(elemen, "x"), _nilai(elemen, "y")
    lebar, tinggi = _nilai(elemen, "width"), _nilai(elemen, "height")
    persegi_di_pusat = (lebar == tinggi and abs(cx - (x + lebar / 2)) <= TOLERANSI
                        and abs(cy - (y + tinggi / 2)) <= TOLERANSI)
    assert sudut % 90 == 0 and persegi_di_pusat, f"Putaran ikon tak didukung oracle: {teks!r}"
    return ""


def _transform_elemen(elemen, tag):
    teks = elemen.get("transform", "")
    if tag == "image" and "rotate" in teks:
        teks = _tanpa_putar_ikon(elemen, teks)
    return _transform(teks)


def _periksa_elemen(elemen, induk, kotak):
    tag = elemen.tag.rsplit("}", 1)[-1]
    if tag in DEFINISI:
        return
    transform = _gabung(induk, _transform_elemen(elemen, tag))
    sx, sy, dx, dy = transform
    kiri, atas, lebar, tinggi = kotak
    for x, y in _titik_lokal(elemen, tag):
        px, py = sx*x+dx, sy*y+dy
        assert (math.isfinite(px) and math.isfinite(py)
                and kiri-TOLERANSI <= px <= kiri+lebar+TOLERANSI
                and atas-TOLERANSI <= py <= atas+tinggi+TOLERANSI), (
                    f"{tag} di luar viewBox", elemen.attrib, (px, py), kotak)
    for anak in elemen:
        _periksa_elemen(anak, transform, kotak)


def periksa_batas_koordinat(akar):
    """Pastikan anchor/primitif berada dalam viewBox setelah transform SVG."""
    kotak = _angka(akar.attrib["viewBox"])
    assert len(kotak) == 4 and kotak[2] > 0 and kotak[3] > 0, kotak
    transform = _transform(akar.get("transform", ""))
    for anak in akar:
        _periksa_elemen(anak, transform, kotak)
