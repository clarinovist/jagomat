"""Template topik Bangun Datar/Ruang untuk Latihan Lomba (bagian 1: tingkat 1 dan keliling).

Sembilan template topik ini dibagi dua berkas: berkas ini (id `bgn_titik_sudut` sampai
`bgn_tempel_persegi`) dan `contest_templates_geometry_b.py` (sisanya), yang diimpor di
bagian bawah berkas ini. Pengecoh selalu dari kesalahan khas anak; verifikator memakai
tabel dan cara hitung sendiri (koordinat, enumerasi sisi terbuka), bukan tabel pembangun.
"""
from __future__ import annotations

import random
from typing import Dict, List, Mapping, Sequence, Tuple

import contest_core as C
import contest_svg_geometry as G
import design_tokens as T

TOPIK = "bangun"
SAT_CM = "cm"


def nama_dari(angka: int) -> str:
    """Nama anak sintetis yang ditentukan dari parameter (murni, tanpa keacakan)."""
    return C.NAMA_ANAK[angka % len(C.NAMA_ANAK)]


def teks_cm(nilai: int) -> str:
    return f"{nilai} {SAT_CM}"


def kandidat_cm(nilai: int, kesalahan: str) -> List[C.Pengecoh]:
    """Pengecoh berbentuk "N cm"; nilai bukan bilangan bulat positif dibuang."""
    return [C.Pengecoh(teks_cm(nilai), kesalahan)] if nilai >= 1 else []


# ---------------------------------------------------------------- bgn_titik_sudut
# (banyak titik sudut, keempat sisi sama panjang) menurut pembangun.
SIFAT_BENTUK: Dict[str, Tuple[int, bool]] = {
    "lingkaran": (0, False), "segitiga": (3, False), "persegi": (4, True),
    "persegi panjang": (4, False), "belah ketupat": (4, True), "jajar genjang": (4, False),
    "trapesium": (4, False), "layang-layang": (4, False), "segilima": (5, False),
    "segienam": (6, False),
}
SYARAT_BENTUK = {
    "nol": (lambda n, sama: n == 0, "Bangun yang TIDAK mempunyai titik sudut adalah ..."),
    "tiga": (lambda n, sama: n == 3, "Bangun yang mempunyai 3 titik sudut adalah ..."),
    "lima": (lambda n, sama: n == 5, "Bangun yang mempunyai 5 titik sudut adalah ..."),
    "enam": (lambda n, sama: n == 6, "Bangun yang mempunyai 6 titik sudut adalah ..."),
    "lebih_empat": (lambda n, sama: n > 4, "Bangun yang mempunyai lebih dari 4 titik sudut adalah ..."),
    "empat_sama": (lambda n, sama: n == 4 and sama,
                   "Bangun yang mempunyai 4 titik sudut dan keempat sisinya sama panjang adalah ..."),
    "empat_beda": (lambda n, sama: n == 4 and not sama,
                   "Bangun yang mempunyai 4 titik sudut, tetapi keempat sisinya TIDAK sama panjang, adalah ..."),
}
JUMLAH_PILIHAN_BENTUK = 4


def _cocok_bentuk(syarat: str, nama: str) -> bool:
    return SYARAT_BENTUK[syarat][0](*SIFAT_BENTUK[nama])


def _sampler_titik_sudut(rng: random.Random) -> Mapping:
    syarat = rng.choice(sorted(SYARAT_BENTUK))
    cocok = [n for n in sorted(SIFAT_BENTUK) if _cocok_bentuk(syarat, n)]
    salah = [n for n in sorted(SIFAT_BENTUK) if not _cocok_bentuk(syarat, n)]
    pilihan = [rng.choice(cocok)] + rng.sample(salah, JUMLAH_PILIHAN_BENTUK - 1)
    return {"syarat": syarat, "bentuk": sorted(pilihan)}


def _sifat_teks(nama: str) -> str:
    sudut, sama = SIFAT_BENTUK[nama]
    if sudut == 0:
        return "tidak mempunyai titik sudut"
    if sudut == 4:
        return f"mempunyai 4 titik sudut dan sisinya {'sama panjang' if sama else 'tidak semuanya sama panjang'}"
    return f"mempunyai {sudut} titik sudut"


def _bangun_titik_sudut(p: Mapping) -> C.SoalLomba:
    syarat, bentuk = p["syarat"], list(p["bentuk"])
    cocok = [n for n in bentuk if _cocok_bentuk(syarat, n)]
    if len(cocok) != 1:
        raise ValueError(f"pilihan harus punya tepat satu jawaban benar: {bentuk}")
    kunci = cocok[0]
    kandidat = [C.Pengecoh(n, f"memilih {n}, padahal {n} {_sifat_teks(n)}", G.gambar_pilihan_bentuk(n))
                for n in bentuk if n != kunci]
    pengecoh = C.ambil_pengecoh(kunci, kandidat)
    daftar = ", ".join(f"{n} {_sifat_teks(n)}" for n in bentuk)
    return C.SoalLomba(
        template_id="bgn_titik_sudut", topik=TOPIK, jenis=C.JENIS_PG, tingkat=1,
        teks=SYARAT_BENTUK[syarat][1], svg="", kunci=kunci, pengecoh=pengecoh,
        pembahasan=("Titik sudut adalah pojok, tempat dua sisi bertemu.",
                    f"Periksa tiap bentuk: {daftar}.", f"Jadi jawabannya {kunci}."),
        parameter=C.kanonik(p), nilai=None, kunci_svg=G.gambar_pilihan_bentuk(kunci))


# Verifikator: titik sudut tiap bentuk pada koordinat bulat; sifat dihitung dari koordinat.
KOORDINAT_VERIF = {
    "persegi": [(0, 0), (1, 0), (1, 1), (0, 1)],
    "persegi panjang": [(0, 0), (2, 0), (2, 1), (0, 1)],
    "segitiga": [(0, 0), (2, 0), (1, 2)],
    "belah ketupat": [(0, 1), (1, 0), (2, 1), (1, 2)],
    "jajar genjang": [(0, 0), (3, 0), (4, 1), (1, 1)],
    "trapesium": [(0, 0), (4, 0), (3, 1), (1, 1)],
    "layang-layang": [(0, 0), (1, 1), (0, 3), (-1, 1)],
    "segilima": [(0, 0), (2, 0), (3, 1), (1, 3), (-1, 1)],
    "segienam": [(1, 0), (2, 0), (3, 1), (2, 2), (1, 2), (0, 1)],
    "lingkaran": [],
}
# (sudut minimal, sudut maksimal, keempat sisi harus sama: True/False/None)
BATAS_VERIF = {
    "nol": (0, 0, None), "tiga": (3, 3, None), "lima": (5, 5, None), "enam": (6, 6, None),
    "lebih_empat": (5, 99, None), "empat_sama": (4, 4, True), "empat_beda": (4, 4, False),
}


def sisi_sama_verif(titik: Sequence[Tuple[int, int]]) -> bool:
    panjang2 = {(a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 for a, b in zip(titik, list(titik[1:]) + titik[:1])}
    return len(panjang2) == 1


def _verifikator_titik_sudut(p: Mapping) -> str:
    kecil, besar, harus_sama = BATAS_VERIF[p["syarat"]]
    cocok = []
    for nama in p["bentuk"]:
        titik = KOORDINAT_VERIF[nama]
        sama_ok = harus_sama is None or sisi_sama_verif(titik) == harus_sama
        if kecil <= len(titik) <= besar and sama_ok:
            cocok.append(nama)
    if len(cocok) != 1:
        raise ValueError(f"pilihan tidak punya tepat satu jawaban: {cocok}")
    return cocok[0]


# ---------------------------------------------------------------- bgn_benda_ruang
BENDA_RUANG = {
    "tabung": (("\U0001F96B", "kaleng"), ("\U0001F6E2️", "drum minyak"), ("\U0001F56F️", "lilin")),
    "kubus": (("\U0001F3B2", "dadu"), ("\U0001F9CA", "es batu")),
    "bola": (("⚽", "bola sepak"), ("\U0001F3C0", "bola basket"), ("\U0001F3BE", "bola tenis")),
    "balok": (("\U0001F9F1", "batu bata"), ("\U0001F9C3", "kotak jus")),
}


def _sampler_benda_ruang(rng: random.Random) -> Mapping:
    tanya = rng.choice(sorted(BENDA_RUANG))
    pilihan = [rng.choice(BENDA_RUANG[bangun])[1] for bangun in sorted(BENDA_RUANG)]
    return {"tanya": tanya, "benda": sorted(pilihan)}


def _cari_benda(nama: str) -> Tuple[str, str, str]:
    for bangun, daftar in BENDA_RUANG.items():
        for emoji, benda in daftar:
            if benda == nama:
                return emoji, benda, bangun
    raise ValueError(f"benda tidak dikenal: {nama!r}")


def _bangun_benda_ruang(p: Mapping) -> C.SoalLomba:
    tanya = p["tanya"]
    isi = [_cari_benda(nama) for nama in p["benda"]]
    cocok = [item for item in isi if item[2] == tanya]
    if len(cocok) != 1:
        raise ValueError(f"pilihan harus punya tepat satu {tanya}: {p['benda']}")
    kunci = cocok[0][1]
    kandidat = [C.Pengecoh(benda, f"memilih {benda}, padahal {benda} berbentuk {bangun}",
                           G.gambar_pilihan_benda(emoji, benda, bangun))
                for emoji, benda, bangun in isi if benda != kunci]
    daftar = ", ".join(f"{benda} berbentuk {bangun}" for _, benda, bangun in isi)
    return C.SoalLomba(
        template_id="bgn_benda_ruang", topik=TOPIK, jenis=C.JENIS_PG, tingkat=1,
        teks=f"Benda yang berbentuk {tanya} adalah ...", svg="", kunci=kunci,
        pengecoh=C.ambil_pengecoh(kunci, kandidat),
        pembahasan=(f"Kenali bentuk tiap benda: {daftar}.", f"Jadi jawabannya {kunci}, karena berbentuk {tanya}."),
        parameter=C.kanonik(p), nilai=None,
        kunci_svg=G.gambar_pilihan_benda(cocok[0][0], kunci, tanya))


BANGUN_BENDA_VERIF = {
    "kaleng": "tabung", "drum minyak": "tabung", "lilin": "tabung", "dadu": "kubus",
    "es batu": "kubus", "bola sepak": "bola", "bola basket": "bola", "bola tenis": "bola",
    "batu bata": "balok", "kotak jus": "balok",
}


def _verifikator_benda_ruang(p: Mapping) -> str:
    cocok = [nama for nama in p["benda"] if BANGUN_BENDA_VERIF[nama] == p["tanya"]]
    if len(cocok) != 1:
        raise ValueError(f"pilihan tidak punya tepat satu jawaban: {cocok}")
    return cocok[0]


# ---------------------------------------------------------------- bgn_jumlah_sisi
SISI_BENTUK = {"segitiga": 3, "persegi": 4, "persegi panjang": 4, "belah ketupat": 4,
               "jajar genjang": 4, "trapesium": 4, "layang-layang": 4, "segilima": 5, "segienam": 6}
BANYAK_BENTUK_MIN, BANYAK_BENTUK_MAKS = 3, 5


def _sampler_jumlah_sisi(rng: random.Random) -> Mapping:
    banyak = rng.randint(BANYAK_BENTUK_MIN, BANYAK_BENTUK_MAKS)
    daftar = [rng.choice(sorted(SISI_BENTUK)) for _ in range(banyak)]
    if len(set(daftar)) < 2:
        raise C.ParameterTidakSah("bangun-bangun harus ada yang berbeda jenis")
    return {"bangun": daftar}


def _bangun_jumlah_sisi(p: Mapping) -> C.SoalLomba:
    daftar = list(p["bangun"])
    sisi = [SISI_BENTUK[n] for n in daftar]
    total = sum(sisi)
    jenis_beda = sum(SISI_BENTUK[n] for n in sorted(set(daftar)))
    kunci = str(total)
    pengecoh = C.ambil_pengecoh(kunci, [
        C.Pengecoh(str(total - sisi[0]), "melewatkan bangun pertama saat menjumlahkan"),
        C.Pengecoh(str(4 * len(daftar)), "mengira setiap bangun mempunyai 4 sisi"),
        C.Pengecoh(str(len(daftar)), "menghitung banyak bangun, bukan banyak sisi"),
        C.Pengecoh(str(total - sisi[-1]), "melewatkan bangun terakhir saat menjumlahkan"),
        C.Pengecoh(str(jenis_beda), "tidak menghitung bangun yang kembar"),
    ])
    rincian = " + ".join(str(s) for s in sisi)
    nama_isi = ", ".join(f"{n} {SISI_BENTUK[n]}" for n in daftar)
    return C.SoalLomba(
        template_id="bgn_jumlah_sisi", topik=TOPIK, jenis=C.JENIS_PG, tingkat=1,
        teks=f"{nama_dari(total + len(daftar))} menggambar bangun-bangun di bawah. "
             f"Berapa jumlah semua sisi bangun-bangun ini?",
        svg=G.gambar_barisan_bentuk(daftar), kunci=kunci, pengecoh=pengecoh,
        pembahasan=("Sisi adalah garis lurus di tepi bangun. Hitung sisi tiap bangun satu per satu.",
                    f"Banyak sisi: {nama_isi}.", f"{rincian} = {total}", f"Jadi jumlah semua sisinya {kunci}."),
        parameter=C.kanonik(p), nilai=total)


def _verifikator_jumlah_sisi(p: Mapping) -> str:
    return str(sum(len(KOORDINAT_VERIF[nama]) for nama in p["bangun"]))


# ---------------------------------------------------------------- bgn_keliling_susun
def sel_persegi_panjang(kolom: int, baris: int) -> List[List[int]]:
    return [[r, c] for r in range(baris) for c in range(kolom)]


def sel_tangga(tinggi_kolom: Sequence[int]) -> List[List[int]]:
    puncak = max(tinggi_kolom)
    return [[puncak - t + r, c] for c, t in enumerate(tinggi_kolom) for r in range(t)]


def sel_huruf_l(kolom: int, baris: int, potong_k: int, potong_b: int) -> List[List[int]]:
    return [[r, c] for r in range(baris) for c in range(kolom)
            if not (r < potong_b and c >= kolom - potong_k)]


def sel_huruf_u(kolom: int, baris: int, awal: int, lebar: int, dalam: int) -> List[List[int]]:
    return [[r, c] for r in range(baris) for c in range(kolom)
            if not (r < dalam and awal <= c < awal + lebar)]


def _sampler_sel(rng: random.Random) -> List[List[int]]:
    jenis = rng.choice(("persegi panjang", "tangga", "huruf L", "huruf U"))
    if jenis == "persegi panjang":
        return sel_persegi_panjang(rng.randint(2, 6), rng.randint(1, 4))
    if jenis == "tangga":
        tinggi = sorted((rng.randint(1, 4) for _ in range(rng.randint(2, 5))), reverse=True)
        if tinggi[0] == tinggi[-1]:
            raise C.ParameterTidakSah("tangga harus punya anak tangga")
        return sel_tangga(tinggi)
    if jenis == "huruf L":
        kolom, baris = rng.randint(3, 5), rng.randint(3, 4)
        return sel_huruf_l(kolom, baris, rng.randint(1, kolom - 1), rng.randint(1, baris - 1))
    kolom, baris = rng.randint(3, 5), rng.randint(2, 3)
    lebar = rng.randint(1, kolom - 2)
    return sel_huruf_u(kolom, baris, rng.randint(1, kolom - 1 - lebar), lebar, rng.randint(1, baris - 1))


def _sampler_keliling_susun(rng: random.Random) -> Mapping:
    return {"sel": sorted(_sampler_sel(rng))}


def _bangun_keliling_susun(p: Mapping) -> C.SoalLomba:
    sel = {(r, c) for r, c in p["sel"]}
    sisi_dalam = sum(1 for r, c in sel for tetangga in ((r + 1, c), (r, c + 1)) if tetangga in sel)
    banyak = len(sel)
    tepi = {arah: sum(1 for r, c in sel if (r + dr, c + dc) not in sel)
            for arah, (dr, dc) in (("atas", (-1, 0)), ("bawah", (1, 0)), ("kiri", (0, -1)), ("kanan", (0, 1)))}
    keliling = sum(tepi.values())
    bingkai = 2 * (max(r for r, _ in sel) + 1 + max(c for _, c in sel) + 1)
    kunci = teks_cm(keliling)
    kandidat = (kandidat_cm(banyak, "menghitung banyak kotak, bukan panjang tepi luar")
                + kandidat_cm(keliling // 2, "menjumlahkan panjang dan lebar saja (setengah keliling)")
                + kandidat_cm(4 * banyak - sisi_dalam, "ikut menghitung garis-garis di dalam bangun")
                + kandidat_cm(bingkai, "menghitung keliling persegi panjang yang membungkus bangun")
                + kandidat_cm(4 * banyak, "menghitung semua sisi kotak (4 untuk tiap kotak)"))
    return C.SoalLomba(
        template_id="bgn_keliling_susun", topik=TOPIK, jenis=C.JENIS_PG, tingkat=2,
        teks="Setiap kotak berisi 1 cm. Kotak-kotak disusun rapat membentuk bangun seperti gambar. "
             "Keliling bangun ini adalah ...",
        svg=G.gambar_sel(p["sel"], T.GEO_LOMBA_HIJAU_MUDA, "Gambar kotak-kotak yang disusun rapat"),
        kunci=kunci, pengecoh=C.ambil_pengecoh(kunci, kandidat),
        pembahasan=("Keliling adalah panjang garis di sepanjang tepi luar bangun.",
                    f"Sisi kotak di tepi luar: atas {tepi['atas']}, kanan {tepi['kanan']}, "
                    f"bawah {tepi['bawah']}, kiri {tepi['kiri']}, jumlahnya {keliling} sisi.",
                    f"Tiap sisi 1 cm, jadi kelilingnya {kunci}."),
        parameter=C.kanonik(p), nilai=None)


def _verifikator_keliling_susun(p: Mapping) -> str:
    sel = {tuple(s) for s in p["sel"]}
    terbuka = 0
    for r, c in sel:
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            terbuka += (r + dr, c + dc) not in sel
    return f"{terbuka} cm"


# ---------------------------------------------------------------- bgn_tempel_persegi
SISI_TEMPEL_MIN, SISI_TEMPEL_MAKS = 2, 15
KATA_BANYAK = {2: "Dua", 3: "Tiga"}


def _sampler_tempel_persegi(rng: random.Random) -> Mapping:
    return {"sisi": rng.randint(SISI_TEMPEL_MIN, SISI_TEMPEL_MAKS), "banyak": rng.choice((2, 3)),
            "arah": rng.choice(("mendatar", "tegak"))}


def _bangun_tempel_persegi(p: Mapping) -> C.SoalLomba:
    s, k = p["sisi"], p["banyak"]
    keliling = 2 * s * (k + 1)
    kunci = teks_cm(keliling)
    luas = kandidat_cm(k * s * s, "menghitung luas, bukan keliling")
    kurang_satu = kandidat_cm(4 * s * k - s * (k - 1), "hanya mengurangi satu sisi tempel di tiap sambungan")
    kandidat = (kandidat_cm(4 * s * k, "menjumlahkan keliling semua persegi tanpa mengurangi sisi yang ditempel")
                + kandidat_cm(4 * s, "menghitung keliling satu persegi saja")
                + (luas + kurang_satu if s % 2 else kurang_satu + luas)   # pengecoh ketiga bergantian
                + kandidat_cm(s * (k + 1), "menjumlahkan panjang dan lebar saja"))
    return C.SoalLomba(
        template_id="bgn_tempel_persegi", topik=TOPIK, jenis=C.JENIS_PG, tingkat=2,
        teks=f"{KATA_BANYAK[k]} persegi bersisi {s} cm ditempel rapat menjadi satu persegi panjang. "
             f"Keliling persegi panjang itu adalah ...",
        svg=G.gambar_tempel(s, k, p["arah"]), kunci=kunci, pengecoh=C.ambil_pengecoh(kunci, kandidat),
        pembahasan=(f"Persegi panjang itu panjangnya {k} x {s} = {k * s} cm dan lebarnya {s} cm.",
                    f"Keliling = 2 x ({k * s} + {s}) = 2 x {(k + 1) * s} = {keliling} cm.",
                    f"Jadi kelilingnya {kunci}."),
        parameter=C.kanonik(p), nilai=None)


def _verifikator_tempel_persegi(p: Mapping) -> str:
    sel = {(0, c) for c in range(p["banyak"])} if p["arah"] == "mendatar" \
        else {(r, 0) for r in range(p["banyak"])}
    terbuka = sum(1 for r, c in sel for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
                  if (r + dr, c + dc) not in sel)
    return f"{terbuka * p['sisi']} cm"


for _id, _jenis, _tingkat, _sampler, _bangun, _verif in (
        ("bgn_titik_sudut", C.JENIS_PG, 1, _sampler_titik_sudut, _bangun_titik_sudut, _verifikator_titik_sudut),
        ("bgn_benda_ruang", C.JENIS_PG, 1, _sampler_benda_ruang, _bangun_benda_ruang, _verifikator_benda_ruang),
        ("bgn_jumlah_sisi", C.JENIS_PG, 1, _sampler_jumlah_sisi, _bangun_jumlah_sisi, _verifikator_jumlah_sisi),
        ("bgn_keliling_susun", C.JENIS_PG, 2, _sampler_keliling_susun, _bangun_keliling_susun,
         _verifikator_keliling_susun),
        ("bgn_tempel_persegi", C.JENIS_PG, 2, _sampler_tempel_persegi, _bangun_tempel_persegi,
         _verifikator_tempel_persegi)):
    C.daftarkan(C.Template(id=_id, topik=TOPIK, jenis=_jenis, tingkat=_tingkat,
                           sampler=_sampler, bangun=_bangun, verifikator=_verif))

import contest_templates_geometry_b  # noqa: E402,F401  (template bgn_rusuk_titik_sisi dan seterusnya)
