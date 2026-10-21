"""Koreksi kunci Batch A; teks warisan tetap tersedia melalui versi parameter."""
from dataclasses import replace
from fractions import Fraction as F

from catalog_exact import format_angka as fmt, PETUNJUK_EKSAK
from templates import Malrule, saring_malrule


def aritmatika(soal):
    p, tid = soal.parameter, soal.template_id
    if tid == "perbandingan_senilai":
        kunci = F(p["q"] * p["n"], p["p"])
        kandidat = (("senilai.terbalik", F(p["p"] * p["n"], p["q"]), "K", "membalik perbandingan menjadi p/q lalu mengalikan nilai yang diketahui"),
                    ("senilai.selisih", abs(p["q"] - p["p"]), "B", "menjawab selisih pembanding, bukan nilai yang dicari"))
        langkah = f"Setiap satu bagian pertama memerlukan {p['q']}/{p['p']} bagian kedua. Maka {p['n']} × {p['q']}/{p['p']} = {fmt(kunci)}."
        prefix = "senilai"
    elif tid == "perbandingan_berbalik":
        kunci = F(p["a1"] * p["b1"], p["a2"])
        kandidat = (("berbalik.terbalik", F(p["a2"] * p["b1"], p["a1"]), "K", "memakai perbandingan senilai padahal ini berbalik nilai"),
                    ("berbalik.jumlah", p["a1"] + p["b1"], "B", "menjumlahkan jumlah pelaku dan waktu, bukan mencari waktu baru"))
        langkah = f"Beban kerja tetap: {p['a1']} × {p['b1']}. Waktu baru = {p['a1']} × {p['b1']} : {p['a2']} = {fmt(kunci)}."
        prefix = "berbalik"
    else:
        kunci = 1 / (F(1, p["a"]) + F(1, p["b"]))
        kandidat = (("kerja.jumlah_waktu", p["a"] + p["b"], "K", "menjumlahkan waktu masing-masing, bukan laju kerja"),
                    ("kerja.kali_waktu", p["a"] * p["b"], "K", "mengalikan waktu tetapi tidak membaginya dengan jumlah waktu"))
        langkah = f"Dalam satu jam selesai 1/{p['a']} + 1/{p['b']} pekerjaan. Waktu bersama = 1 : (1/{p['a']} + 1/{p['b']}) = {fmt(kunci)} jam."
        prefix = "kerja"
    mal = [Malrule(prefix + ".kurang_satu", fmt(kunci - 1), "H", "perhitungan benar, hasilnya meleset satu")]
    mal.extend(Malrule(ident, fmt(v), kode, alasan) for ident, v, kode, alasan in kandidat)
    return replace(soal, kunci=fmt(kunci), malrule=saring_malrule(fmt(kunci), mal),
                   teks=soal.teks + PETUNJUK_EKSAK, pembahasan=langkah)


def lingkaran(soal):
    p = soal.parameter
    r = p["r"]
    pi = F(22, 7) if r % 7 == 0 else F(314, 100)
    pi_teks = "22/7" if r % 7 == 0 else "3,14"
    luas, keliling = pi * r * r, 2 * pi * r
    if soal.template_id == "lingkaran_keliling_luas":
        if p["varian"] == "keliling":
            kunci = keliling
            kandidat = (("lingkaran.tukar_luas", luas, "menghitung luas, bukan keliling"),
                        ("lingkaran.pakai_diameter", 2 * keliling, "memakai diameter sebagai jari-jari pada keliling"))
            langkah = f"Keliling = 2 × {pi_teks} × {r} = {fmt(kunci)} cm."
        else:
            kunci = luas
            kandidat = (("lingkaran.pakai_diameter", 4 * luas, "memakai diameter sebagai jari-jari pada luas"),
                        ("lingkaran.tukar_keliling", keliling, "menghitung keliling, bukan luas"))
            langkah = f"Luas = {pi_teks} × {r} × {r} = {fmt(kunci)} cm²."
        prefix = "lingkaran"
    else:
        bagian = F(p["s"], 360)
        busur = bagian * keliling
        if p["varian"] == "luas_juring":
            kunci = bagian * luas
            kandidat = (("juring.lupa_setengah_busur", luas, "menghitung luas lingkaran penuh, bukan luas juring"),
                        ("juring.pakai_s_180", 2 * kunci, "menggunakan s/180 bukan s/360"))
            langkah = f"Luas juring = {p['s']}/360 × {pi_teks} × {r} × {r} = {fmt(kunci)} cm²."
        else:
            kunci = busur + 2 * r
            kandidat = (("juring.lupa_tambah_2r", busur, "hanya menghitung busur, lupa dua jari-jari"),
                        ("juring.pakai_diameter", 2 * busur, "memakai diameter sebagai jari-jari pada rumus busur dan tidak menambah sisi lurus"))
            langkah = f"Panjang busur = {p['s']}/360 × 2 × {pi_teks} × {r} = {fmt(busur)} cm. Keliling = {fmt(busur)} + {2*r} = {fmt(kunci)} cm."
        prefix = "juring"
    selisih = F(1, 10) if kunci.denominator != 1 else F(1)
    mal = [Malrule(prefix + ".kurang_satu", fmt(kunci - selisih), "H", f"perhitungan benar, hasilnya meleset {fmt(selisih)}")]
    mal.extend(Malrule(ident, fmt(v), "K", alasan) for ident, v, alasan in kandidat)
    return replace(soal, kunci=fmt(kunci), malrule=saring_malrule(fmt(kunci), mal),
                   teks=soal.teks + PETUNJUK_EKSAK, pembahasan=langkah)


def paritas(soal):
    a, n = soal.parameter["a"], soal.parameter["n"]
    jenis = "ganjil" if a % 2 else "genap"
    akhir = a + 2 * (n - 1)
    return replace(soal, teks=soal.teks.replace("bilangan ganjil", "bilangan " + jenis),
        malrule=tuple(replace(m, alasan=m.alasan.replace("bilangan ganjil", "bilangan " + jenis)) for m in soal.malrule),
        pembahasan=f"Ada {n} bilangan {jenis} dengan beda 2. Suku terakhir {a} + 2 × ({n} − 1) = {akhir}. Jumlah = {n} x ({a} + {akhir}) : 2 = {soal.kunci}.")
