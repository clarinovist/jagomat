"""Kosakata bangun untuk jenis `kenali_bangun_awal` dan sub-adegan `bentuk` (Matematika Awal).

Satu sumber untuk nama bangun, himpunan per level, ragam gambar (orientasi, ukuran, warna),
kalimat ciri, fakta, dan benda sehari-hari. Modul ini hanya berisi data dan fungsi murni
tanpa impor modul mesin, jadi aman diimpor jenis soal, validator descriptor, dan renderer.

Fakta bangun HARUS benar (ulasan Mutia): segitiga 3 sisi 3 sudut; persegi 4 sisi sama
panjang; persegi panjang 4 sisi dengan sisi berhadapan sama panjang tetapi tidak semuanya
sama; lingkaran tanpa sisi lurus dan tanpa sudut; kubus 6 sisi persegi; balok 6 sisi persegi
panjang; bola tanpa sisi datar; tabung 2 sisi datar lingkaran + 1 sisi lengkung; kerucut 1
sisi datar lingkaran + 1 titik puncak.

Semua daftar bersifat APPEND-ONLY menurut indeks bila ikut dalam identitas soal (BENDA);
nama bangun, ragam, dan warna ikut dalam parameter sebagai teks.
"""
from __future__ import annotations

from types import MappingProxyType

DATAR = ("segitiga", "persegi", "persegi panjang", "lingkaran")
RUANG = ("kubus", "balok", "bola", "tabung", "kerucut")
SEMUA_NAMA = DATAR + RUANG

# Himpunan bangun DATAR sama di P1 dan P2 (persegi panjang dikenalkan sejak kelas 1); P2 hanya
# menambah kerucut pada bangun ruang. Nama himpunan tetap "dasar" dan "lengkap" (ikut domain).
HIMPUNAN_LEVEL = MappingProxyType({"P1": "dasar", "P2": "lengkap"})
DATAR_HIMPUNAN = MappingProxyType({
    "dasar": ("segitiga", "persegi", "persegi panjang", "lingkaran"),
    "lengkap": ("segitiga", "persegi", "persegi panjang", "lingkaran"),
})
RUANG_HIMPUNAN = MappingProxyType({
    "dasar": ("kubus", "balok", "bola", "tabung"),
    "lengkap": ("kubus", "balok", "bola", "tabung", "kerucut"),
})

# Ragam gambar per bangun. Segitiga: tiga rupa dan empat putaran kelipatan 90 derajat
# (koordinat dihitung langsung, tanpa transform). Persegi panjang dan balok: mendatar atau
# tegak dengan rasio sisi jelas (>= 1,5). Persegi miring 45 derajat sengaja tidak ada.
RAGAM = MappingProxyType({
    "segitiga": ("samasisi", "siku", "sembarang"),
    "persegi": ("biasa",),
    "persegi panjang": ("mendatar", "tegak"),
    "lingkaran": ("biasa",),
    "kubus": ("biasa",),
    "balok": ("mendatar", "tegak"),
    "bola": ("biasa",),
    "tabung": ("tegak",),
    "kerucut": ("tegak",),
})
PUTAR = MappingProxyType({
    "segitiga": (0, 90, 180, 270),
    **{nama: (0,) for nama in SEMUA_NAMA if nama != "segitiga"},
})
UKURAN = ("kecil", "besar")
WARNA = ("biru", "kuning", "hijau")
JUMLAH_CIRI = len(WARNA)  # kalimat ciri teks dipilih lewat indeks warna: tiap gambar punya satu teks tetap

# Kalimat ciri per bangun (tepat tiga, satu per warna); tiap ciri menunjuk TEPAT SATU bangun
# pada himpunan dasar maupun lengkap, diuji solver terpisah di tes domain.
CIRI = MappingProxyType({
    "segitiga": ("punya 3 sisi lurus dan 3 sudut", "punya 3 sudut dan 3 sisi lurus",
                 "punya 3 sisi lurus"),
    "persegi": ("punya 4 sisi lurus yang semuanya sama panjang",
                "punya 4 sisi sama panjang dan 4 sudut sama besar",
                "punya 4 sudut sama besar dan 4 sisi sama panjang"),
    "persegi panjang": ("punya 4 sisi lurus; sisi yang berhadapan sama panjang, "
                        "tetapi tidak semuanya sama panjang",
                        "punya 4 sisi lurus, yaitu 2 sisi panjang dan 2 sisi pendek",
                        "punya 4 sudut dan sisi yang berhadapan sama panjang, "
                        "tetapi tidak semua sisinya sama panjang"),
    "lingkaran": ("tidak punya sisi lurus dan tidak punya sudut",
                  "bulat dan tidak punya sudut",
                  "tidak punya sudut sama sekali"),
    "kubus": ("punya 6 sisi yang semuanya berbentuk persegi",
              "punya 6 sisi persegi yang sama besar",
              "punya 6 sisi, dan semua sisinya persegi yang sama besar"),
    "balok": ("punya 6 sisi yang berbentuk persegi panjang",
              "punya 6 sisi berbentuk persegi panjang, dan sisi yang berhadapan sama besar",
              "punya 6 sisi, bentuknya persegi panjang semua"),
    "bola": ("bulat dan tidak punya sisi datar",
             "bisa menggelinding ke segala arah dan tidak punya sisi datar",
             "tidak punya sudut dan tidak punya sisi datar sama sekali"),
    "tabung": ("punya 2 sisi datar yang berbentuk lingkaran dan 1 sisi lengkung",
               "punya alas dan tutup berbentuk lingkaran serta 1 sisi lengkung",
               "bisa menggelinding dan punya 2 sisi datar yang bulat"),
    "kerucut": ("punya 1 sisi datar berbentuk lingkaran dan 1 titik puncak",
                "punya alas berbentuk lingkaran dan ujungnya runcing",
                "punya 1 sisi datar yang bulat dan 1 sisi lengkung yang meruncing ke atas"),
})
# Satu kalimat ciri tanpa nama bangun untuk ringkasan non-HTML (sah di himpunan dasar dan lengkap).
CIRI_RINGKAS = MappingProxyType({nama: CIRI[nama][0] for nama in SEMUA_NAMA})

FAKTA = MappingProxyType({
    "segitiga": "Segitiga punya 3 sisi lurus dan 3 sudut.",
    "persegi": "Persegi punya 4 sisi lurus yang semuanya sama panjang dan 4 sudut.",
    "persegi panjang": ("Persegi panjang punya 4 sisi lurus: 2 sisi panjang dan 2 sisi pendek, "
                        "dan sisi yang berhadapan sama panjang."),
    "lingkaran": "Lingkaran itu bulat. Ia tidak punya sisi lurus dan tidak punya sudut.",
    "kubus": "Kubus punya 6 sisi, dan semuanya persegi yang sama besar.",
    "balok": "Balok punya 6 sisi yang berbentuk persegi panjang; sisi yang berhadapan sama besar.",
    "bola": "Bola itu bulat dan tidak punya sisi datar. Ia bisa menggelinding ke segala arah.",
    "tabung": ("Tabung punya 2 sisi datar berbentuk lingkaran (alas dan tutup) dan 1 sisi "
               "lengkung. Ia bisa menggelinding."),
    "kerucut": ("Kerucut punya 1 sisi datar berbentuk lingkaran (alas) dan 1 titik puncak "
                "yang runcing."),
})

# Benda sehari-hari -> TEPAT SATU bangun ruang (tanpa benda yang bisa dua bentuk, mis. "kotak").
# APPEND-ONLY menurut indeks: indeks ikut dalam identitas soal di bank.
BENDA = MappingProxyType({
    "kubus": ("dadu", "rubik", "kotak kado yang semua sisinya persegi"),
    "balok": ("kardus mi instan", "kotak sepatu", "batu bata"),
    "bola": ("bola sepak", "kelereng", "bola basket"),
    "tabung": ("kaleng susu", "kaleng cat", "lilin batang yang bulat"),
    "kerucut": ("topi ulang tahun", "cone es krim", "tumpeng nasi"),
})

# Bangun datar yang sering disebut untuk bangun ruang (hipotesis K): hanya satu sisinya yang dilihat.
DATAR_KELIRU = MappingProxyType({
    "dasar": MappingProxyType({"kubus": "persegi", "balok": "persegi panjang",
                               "bola": "lingkaran", "tabung": "lingkaran"}),
    "lengkap": MappingProxyType({"kubus": "persegi", "balok": "persegi panjang",
                                 "bola": "lingkaran", "tabung": "lingkaran",
                                 "kerucut": "segitiga"}),
})

JENIS_DATAR = "datar"
JENIS_RUANG = "ruang"


def jenis_bangun(nama: str) -> str:
    """`datar` atau `ruang` menurut daftar nama; nama asing ditolak keras."""
    if nama in DATAR:
        return JENIS_DATAR
    if nama in RUANG:
        return JENIS_RUANG
    raise ValueError(f"nama bangun tidak dikenal: {nama!r}")
