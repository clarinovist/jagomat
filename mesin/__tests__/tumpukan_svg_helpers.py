"""Pembantu tes sub-adegan `tumpukan_kubus`: pembaca gambar (solver mandiri) dan geometri SVG.

`baca_gambar` memetakan tiap `kolom-kubus` ke sel (kolom, baris) HANYA dari posisi proyeksi isometrik;
tidak ada atribut, kelas, atau id yang menyebut sel atau jawaban. Caranya (dipakai juga tes jawaban):
  1. Dari kubus pertama diukur tiga vektor proyeksi: `ex` (rusuk datar muka kiri, satu petak ke KANAN),
     `ey` (rusuk datar muka kanan, satu petak ke BELAKANG), `ez` (rusuk tegak). Semua kubus wajib sama.
  2. Tiap `kolom-kubus` diurut dari kubus terendah di layar; titik dasar kubus terbawah (sudut bawah terdekat
     muka kiri) menjadi jangkar. Kubus ke-k wajib berjarak tepat k * ez di atas jangkar (tak melayang
     atau bergeser); banyak kubus = tinggi tumpukan.
  3. Selisih jangkar terhadap kolom pertama dipecahkan sebagai dx * ex + dy * ey (sistem 2 x 2); dx dan dy
     wajib bulat dan sel tidak boleh kembar. Hanya selisih relatif dipakai: baris atau kolom kosong
     tidak mengubah hitungan tampak.
"""
from __future__ import annotations

import re

import adegan_awal_svg
from visual_security_helpers import elemen, kelas, lokal, periksa_xml

ANGKA = re.compile(r"-?\d+(?:\.\d+)?")
TOLERANSI = 0.02


def lajur_dari(tinggi, kolom):
    return [list(tinggi[y * kolom:(y + 1) * kolom]) for y in range(len(tinggi) // kolom)]


def data_adegan(tinggi, kolom):
    return {"adegan": "tumpukan_kubus", "tinggi": lajur_dari(tinggi, kolom)}


def svg_dari_data(data, namespace="uji"):
    return periksa_xml("<div>" + adegan_awal_svg.render_adegan_awal(data, namespace) + "</div>")


def titik_path(d):
    angka = [float(n) for n in ANGKA.findall(d)]
    assert len(angka) % 2 == 0 and len(angka) >= 8, d
    return list(zip(angka[::2], angka[1::2]))


def muka_path(kubus, nama):
    jalur = [e for e in kubus if nama in e.get("class", "").split()]
    assert len(jalur) == 1 and lokal(jalur[0]) == "path", (nama, len(jalur))
    return titik_path(jalur[0].get("d"))


def kubus_kolom(kolom):
    anak = list(kolom)
    assert anak, "kolom-kubus kosong"
    for k in anak:
        assert lokal(k) == "g" and k.get("class") == "kubus-satuan", (lokal(k), k.attrib)
        assert [e.get("class") for e in k] == ["muka-atas", "muka-kiri", "muka-kanan"], [e.get("class") for e in k]
    return anak


def vektor_kubus(kubus):
    kiri, kanan = muka_path(kubus, "muka-kiri"), muka_path(kubus, "muka-kanan")
    ex = (kiri[1][0] - kiri[0][0], kiri[1][1] - kiri[0][1])
    ez = (kiri[3][0] - kiri[0][0], kiri[3][1] - kiri[0][1])
    ey = (kanan[1][0] - kanan[0][0], kanan[1][1] - kanan[0][1])
    return ex, ey, ez


def hampir_sama(a, b):
    return all(abs(x - y) < 0.02 for x, y in zip(a, b))


def jangkar_dan_tinggi(kolom, basis):
    """(jangkar, tinggi) satu kolom; kubus wajib bertumpuk lurus dari jangkar dengan jarak ez."""
    kubus = kubus_kolom(kolom)
    pasangan = sorted(((muka_path(k, "muka-kiri")[2], k) for k in kubus), key=lambda p: -p[0][1])
    jangkar = pasangan[0][0]
    for urut, (dasar, k) in enumerate(pasangan):
        assert all(hampir_sama(v, w) for v, w in zip(vektor_kubus(k), basis)), "ukuran kubus tidak konstan"
        assert abs(dasar[0] - jangkar[0]) < 0.02, ("kubus bergeser ke samping", urut)
        assert abs(dasar[1] - (jangkar[1] - urut * basis[2][1])) < 0.02, ("kubus melayang", urut)
    return jangkar, len(kubus)


def bulatkan(nilai):
    terdekat = round(nilai)
    assert abs(nilai - terdekat) < TOLERANSI, nilai
    return terdekat


def baca_gambar(svg):
    """{(kolom, baris): tinggi} relatif dari posisi kolom-kubus; baris bertambah ke belakang."""
    kolom = kelas(svg, "kolom-kubus")
    assert kolom, "tidak ada kolom-kubus"
    pertama = kubus_kolom(kolom[0])[0]
    ex, ey, ez = vektor_kubus(pertama)
    det = ex[0] * ey[1] - ex[1] * ey[0]
    assert abs(det) > 1 and ez[0] == 0 and ez[1] > 0, (ex, ey, ez)
    jangkar = [jangkar_dan_tinggi(k, (ex, ey, ez)) for k in kolom]
    asal = jangkar[0][0]
    sel = {}
    for (titik, tinggi) in jangkar:
        dx_, dy_ = titik[0] - asal[0], titik[1] - asal[1]
        kol = bulatkan((dx_ * ey[1] - dy_ * ey[0]) / det)
        bar = bulatkan((ex[0] * dy_ - ex[1] * dx_) / det)
        assert (kol, bar) not in sel, ("dua kolom pada sel yang sama", kol, bar)
        sel[(kol, bar)] = tinggi
    return sel


def semua_titik(svg):
    for e in elemen(svg, "path"):
        yield from titik_path(e.get("d"))


def di_dalam(titik, poligon):
    """Titik di dalam poligon cembung (arah sembarang), batas tidak dihitung."""
    tanda = []
    for i, (x1, y1) in enumerate(poligon):
        x2, y2 = poligon[(i + 1) % len(poligon)]
        tanda.append((x2 - x1) * (titik[1] - y1) - (y2 - y1) * (titik[0] - x1))
    return all(t > 1e-6 for t in tanda) or all(t < -1e-6 for t in tanda)


def titik_uji(poligon):
    pusat = (sum(x for x, _ in poligon) / 4, sum(y for _, y in poligon) / 4)
    return [pusat] + [(pusat[0] + 0.7 * (x - pusat[0]), pusat[1] + 0.7 * (y - pusat[1])) for x, y in poligon]


def puncak_tertimpa(svg) -> list:
    """Indeks kolom yang muka atas puncaknya tertimpa muka lain yang digambar sesudahnya."""
    muka = [e for e in svg.iter() if lokal(e) == "path" and "muka" in e.get("class", "")]
    posisi = {id(e): i for i, e in enumerate(muka)}
    tertimpa = []
    for indeks, kolom in enumerate(kelas(svg, "kolom-kubus")):
        kubus_atas = list(kolom)[-1]
        puncak = muka_path(kubus_atas, "muka-atas")
        jalur = next(e for e in kubus_atas if "muka-atas" in e.get("class", ""))
        for lain in muka[posisi[id(jalur)] + 1:]:
            poligon = titik_path(lain.get("d"))
            if any(di_dalam(t, poligon) for t in titik_uji(puncak)):
                tertimpa.append(indeks)
                break
    return tertimpa


def poligon_muka(kubus):
    return [muka_path(kubus, nama) for nama in ("muka-atas", "muka-kiri", "muka-kanan")]


def luas_poligon(poligon):
    n = len(poligon)
    return abs(sum(poligon[i][0] * poligon[(i + 1) % n][1] - poligon[(i + 1) % n][0] * poligon[i][1]
                   for i in range(n))) / 2


def potong_poligon(subjek, pemotong):
    """Sutherland-Hodgman untuk pemotong cembung berlawanan arah jarum jam."""
    def luar_masuk(a, b, p):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-9

    def silang(p, q, a, b):
        den = (p[0] - q[0]) * (a[1] - b[1]) - (p[1] - q[1]) * (a[0] - b[0])
        t = ((p[0] - a[0]) * (a[1] - b[1]) - (p[1] - a[1]) * (a[0] - b[0])) / den
        return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))

    hasil = subjek
    for i in range(len(pemotong)):
        a, b = pemotong[i], pemotong[(i + 1) % len(pemotong)]
        masuk, hasil = hasil, []
        for j, p in enumerate(masuk):
            q = masuk[(j + 1) % len(masuk)]
            if luar_masuk(a, b, p):
                hasil.append(p)
                if not luar_masuk(a, b, q):
                    hasil.append(silang(p, q, a, b))
            elif luar_masuk(a, b, q):
                hasil.append(silang(p, q, a, b))
        if not hasil:
            break
    return hasil


def berlawanan_jarum(poligon):
    n = len(poligon)
    area = sum(poligon[i][0] * poligon[(i + 1) % n][1] - poligon[(i + 1) % n][0] * poligon[i][1]
               for i in range(n))
    return poligon if area > 0 else poligon[::-1]


def tumpang_tindih(a, b):
    sisa = potong_poligon(a, berlawanan_jarum(b))
    return len(sisa) >= 3 and luas_poligon(sisa) > 0.5


def kubus_berposisi(svg):
    """[(x, y, z, muka_poligon)] dalam urutan lukis; (x, y) relatif dari baca_gambar, z dari urutan tumpukan."""
    sel = baca_gambar(svg)
    kolom = kelas(svg, "kolom-kubus")
    pertama = kubus_kolom(kolom[0])[0]
    ex, ey, _ = vektor_kubus(pertama)
    det = ex[0] * ey[1] - ex[1] * ey[0]
    jangkar0 = max((muka_path(k, "muka-kiri")[2] for k in kubus_kolom(kolom[0])), key=lambda t: t[1])
    hasil = []
    for k in kolom:
        kubus = kubus_kolom(k)
        dasar = max((muka_path(c, "muka-kiri")[2] for c in kubus), key=lambda t: t[1])
        dx_, dy_ = dasar[0] - jangkar0[0], dasar[1] - jangkar0[1]
        x = bulatkan((dx_ * ey[1] - dy_ * ey[0]) / det)
        y = bulatkan((ex[0] * dy_ - ex[1] * dx_) / det)
        assert (x, y) in sel
        for z, c in enumerate(kubus):
            hasil.append((x, y, z, poligon_muka(c)))
    return hasil
