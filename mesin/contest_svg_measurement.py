"""Gambar soal topik Pengukuran untuk Latihan Lomba: jam analog, klip, dan timbangan berantai.

Semua gambar buatan sendiri lewat primitif `contest_svg_common`. Jam tidak pernah memuat label waktu
digital (bocor jawaban); teks alternatif tanpa angka. Elemen yang dihitung anak diberi atribut `data-*`
agar tes bisa membaca ulang apa yang BENAR-BENAR tergambar.
"""
from __future__ import annotations

from typing import Sequence

import design_tokens as T
from contest_svg_common import bungkus, jam_analog, kotak, teks

# Jam tunggal
JAM_TUNGGAL_LEBAR = 200
JAM_TUNGGAL_RADIUS = 80
# Dua jam (mulai dan selesai)
DUA_JAM_LEBAR = 360
DUA_JAM_TINGGI = 160
DUA_JAM_RADIUS = 66
DUA_JAM_X = (76, 284)
DUA_JAM_Y = 80
DUA_JAM_TENGAH_X = 180
DUA_JAM_UKURAN_SAMPAI = 24
PANAH = "\u2192"
# Klip (baris benda = n klip)
KLIP_LEBAR_VIEW = 360
KLIP_TINGGI_BARIS = 52
KLIP_Y_AWAL = 14
KLIP_X_AWAL = 96
KLIP_JARAK = 26
KLIP_LEBAR = 14
KLIP_TINGGI = 30
KLIP_RADIUS = 7
KLIP_DALAM_LEBAR = 6
KLIP_DALAM_TINGGI = 18
EMOJI_UKURAN = 28
EMOJI_X = 34
TANDA_SAMA_X = 66
TANDA_UKURAN = 22
# Timbangan berantai
RANTAI_LEBAR_VIEW = 360
RANTAI_TINGGI_BARIS = 44
RANTAI_Y_AWAL = 28
RANTAI_X_KIRI = 40
RANTAI_X_SAMA = 82
RANTAI_X_KANAN = 122
RANTAI_JARAK = 34

BUAH = {
    "semangka": "\U0001F349", "melon": "\U0001F348", "apel": "\U0001F34E", "jeruk": "\U0001F34A",
    "pisang": "\U0001F34C", "anggur": "\U0001F347", "stroberi": "\U0001F353", "pir": "\U0001F350",
    "nanas": "\U0001F34D", "mangga": "\U0001F96D",
}
BENDA_KLIP = {
    "pensil": "✏️", "krayon": "\U0001F58D️", "pulpen": "\U0001F58A️",
    "kuas": "\U0001F58C️", "sendok": "\U0001F944", "garpu": "\U0001F374",
    "gunting": "\u2702\uFE0F",
}


def _tandai(elemen: str, **atribut) -> str:
    """Sisipkan atribut data-* pada elemen SVG tunggal (underscore -> tanda hubung)."""
    nama_tag = elemen[1:elemen.index(" ")]
    tambahan = "".join(f' {nama.replace("_", "-")}="{nilai}"' for nama, nilai in atribut.items())
    return elemen.replace(f"<{nama_tag} ", f"<{nama_tag}{tambahan} ", 1)


def gambar_jam(jam: int, menit: int) -> str:
    """Satu jam analog (jam 24 jam; muka jam tetap 12 angka)."""
    pusat = JAM_TUNGGAL_LEBAR / 2
    isi = f'<g data-jam="tunggal">{jam_analog(pusat, pusat, JAM_TUNGGAL_RADIUS, jam, menit)}</g>'
    return bungkus(isi, JAM_TUNGGAL_LEBAR, JAM_TUNGGAL_LEBAR, "Jam analog")


def gambar_dua_jam(jam1: int, menit1: int, jam2: int, menit2: int) -> str:
    """Dua jam analog berdampingan: yang kiri jam mulai, yang kanan jam selesai."""
    kiri = jam_analog(DUA_JAM_X[0], DUA_JAM_Y, DUA_JAM_RADIUS, jam1, menit1)
    kanan = jam_analog(DUA_JAM_X[1], DUA_JAM_Y, DUA_JAM_RADIUS, jam2, menit2)
    isi = (f'<g data-jam="mulai">{kiri}</g>'
           + teks(DUA_JAM_TENGAH_X, DUA_JAM_Y, PANAH, ukuran=DUA_JAM_UKURAN_SAMPAI)
           + f'<g data-jam="selesai">{kanan}</g>')
    return bungkus(isi, DUA_JAM_LEBAR, DUA_JAM_TINGGI, "Dua jam analog")


def _satu_klip(x: float, y: float, baris: str) -> str:
    luar = kotak(x, y, KLIP_LEBAR, KLIP_TINGGI, radius=KLIP_RADIUS, garis_warna=T.GEO_LOMBA_BIRU)
    dalam = kotak(x + (KLIP_LEBAR - KLIP_DALAM_LEBAR) / 2, y + (KLIP_TINGGI - KLIP_DALAM_TINGGI) / 2,
                  KLIP_DALAM_LEBAR, KLIP_DALAM_TINGGI, radius=KLIP_DALAM_LEBAR / 2,
                  garis_warna=T.GEO_LOMBA_BIRU)
    return _tandai(luar, data_klip="1", data_baris=baris) + dalam


def gambar_klip(benda: Sequence[str], jumlah_klip: Sequence[int]) -> str:
    """Dua baris `benda = beberapa klip`; tiap klip bertanda `data-klip`, baris bertanda `data-baris`."""
    bagian = []
    for indeks, (nama, jumlah) in enumerate(zip(benda, jumlah_klip)):
        y = KLIP_Y_AWAL + indeks * KLIP_TINGGI_BARIS
        tengah = y + KLIP_TINGGI / 2
        bagian.append(_tandai(teks(EMOJI_X, tengah, BENDA_KLIP[nama], ukuran=EMOJI_UKURAN),
                              data_objek=nama, data_baris=nama))
        bagian.append(teks(TANDA_SAMA_X, tengah, "=", ukuran=TANDA_UKURAN, tebal=True))
        bagian.extend(_satu_klip(KLIP_X_AWAL + n * KLIP_JARAK, y, nama) for n in range(jumlah))
    tinggi = KLIP_Y_AWAL * 2 + KLIP_TINGGI_BARIS * (len(benda) - 1) + KLIP_TINGGI
    return bungkus("".join(bagian), KLIP_LEBAR_VIEW, tinggi, "Gambar benda dan klip pengukurnya")


def gambar_rantai(objek: Sequence[str], rasio: Sequence[int], urutan: Sequence[int]) -> str:
    """Tiap baris `1 objek[i] = rasio[i] objek[i+1]`, ditampilkan menurut `urutan` (nomor baris 1..n)."""
    bagian = []
    for nomor, indeks in enumerate(urutan, start=1):
        y = RANTAI_Y_AWAL + (nomor - 1) * RANTAI_TINGGI_BARIS
        kiri = BUAH[objek[indeks]]
        bagian.append(_tandai(teks(RANTAI_X_KIRI, y, kiri, ukuran=EMOJI_UKURAN),
                              data_objek=objek[indeks], data_rantai=nomor, data_sisi="kiri"))
        bagian.append(teks(RANTAI_X_SAMA, y, "=", ukuran=TANDA_UKURAN, tebal=True))
        for n in range(rasio[indeks]):
            kanan = teks(RANTAI_X_KANAN + n * RANTAI_JARAK, y, BUAH[objek[indeks + 1]],
                         ukuran=EMOJI_UKURAN)
            bagian.append(_tandai(kanan, data_objek=objek[indeks + 1], data_rantai=nomor,
                                  data_sisi="kanan"))
    tinggi = RANTAI_Y_AWAL * 2 + RANTAI_TINGGI_BARIS * (len(urutan) - 1) - RANTAI_Y_AWAL // 2
    return bungkus("".join(bagian), RANTAI_LEBAR_VIEW, tinggi, "Gambar kesetaraan berat buah")
