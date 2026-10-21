"""Pembatas parameter soal topik geometri-datar (dipecah 31 Aug 2026).

_parameter memetakan template -> parameter variasi per level; konstanta
hiasan teks NON-jawaban (KONTEKS_KOTAK, WARNA_KERTAS) pindah bersamanya
karena hanya dipakai di sini. Leaf murni — tidak mengimpor modul topik.
"""

from __future__ import annotations

import random
from catalog_versions import parameter_baru

# Hiasan teks NON-jawaban untuk template dasar P3 — melebarkan variasi
# parameter (target >= 200 kombinasi unik) tanpa menyentuh kunci.
KONTEKS_KOTAK = (
    "ubin",
    "keramik",
    "kotak kue",
    "potongan cokelat",
    "stiker",
    "kancing",
)
WARNA_KERTAS = ("merah", "biru", "hijau", "kuning", "oranye", "ungu")
@parameter_baru
def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id == "sudut_pelurus_berpenyiku":
        varian = rng.choice(("pelurus", "penyiku", "balik_pelurus", "balik_penyiku", "tiga_kali"))
        if varian in ("pelurus", "balik_pelurus"):
            # x bebas 15..165. Untuk pelurus: x=90 membuat kunci == x (B
            # bertabrakan); untuk balik_pelurus: x=90 membuat kunci == 0
            # (tidak sah). Keduanya dieksklusi di sini.
            x = rng.randint(15, 165)
            while x == 90:
                x = rng.randint(15, 165)
            return {"varian": varian, "x": x}
        if varian in ("penyiku", "balik_penyiku"):
            return {"varian": varian, "x": rng.randint(15, 85)}
        # tiga_kali: kali di {3,4,5,8,9,11} — 360/(k+1) ≠ k·180/(k+1)
        # untuk k≠2, jadi malrule K dan B tidak bertabrakan.
        return {"varian": varian, "kali": rng.choice((3, 4, 5, 8, 9, 11))}
    if template_id == "jumlah_sudut_segitiga":
        varian = rng.choice(("dua_sudut", "perbandingan"))
        if varian == "dua_sudut":
            # a+b <= 160 supaya sudut ketiga >= 20; b != 90 supaya malrule
            # salah_tanda tidak bertabrakan dengan pakai_360.
            a = rng.randint(20, 100)
            b = rng.randint(20, min(140 - a, 100))
            while b == 90:
                b = rng.randint(20, min(140 - a, 100))
            return {"varian": varian, "a": a, "b": b}
        # perbandingan: total bagian membagi 180 dan <= 12, p < q < r,
        # p sudut terkecil. Kunci selalu bilangan bulat.
        pilihan = (
            (1, 2, 3),
            (1, 2, 6),
            (1, 3, 5),
            (2, 3, 4),
            (1, 2, 7),
            (1, 3, 6),
            (1, 4, 5),
            (2, 3, 5),
            (1, 2, 9),
            (1, 3, 8),
            (1, 4, 7),
            (1, 5, 6),
            (2, 3, 7),
            (2, 4, 6),
            (3, 4, 5),
        )
        p, q, r = rng.choice(pilihan)
        return {"varian": varian, "p": p, "q": q, "r": r}
    if template_id == "sudut_luar_segitiga":
        # a > b supaya selisih positif; a != 90 supaya dikira_dalam (180-a-b)
        # != selisih_a_b (a-b); a+b != 90 supaya dikira_dalam != kunci (a+b).
        a = rng.randint(30, 89)
        b = rng.randint(20, a - 1)
        while a + b == 90:
            a = rng.randint(30, 89)
            b = rng.randint(20, a - 1)
        return {"a": a, "b": b}
    if template_id == "keliling_luas_datar":
        if level == "P3":
            # P3 (SASMO Primary 1-4): hanya keliling maju dengan angka kecil
            # (2..16). balik_luas (dari K cari luas) disisakan P4+.
            # Ambang variasi pasangan level baru butuh >=200 kombinasi —
            # 2..10 cuma 81 pasang, 2..16 memberi 15x15-6 eksklusi = 219.
            # Eksklusi: p*l == 2(p+l) — (3,6), (4,4), (6,3) — menjatuhkan
            # malrule tukar_luas; p*l == 2(p+l)-1 — (3,5), (5,3) — menjatuhkan
            # kurang_satu, satu-satunya jalur H varian ini; (2,2) membuat
            # tukar_luas dan lupa_kali_dua sama-sama 4.
            p, l = rng.randint(2, 16), rng.randint(2, 16)
            while p * l in (2 * (p + l), 2 * (p + l) - 1) or p == l == 2:
                p, l = rng.randint(2, 16), rng.randint(2, 16)
            return {"varian": "keliling", "p": p, "l": l}
        if rng.random() < 0.5:
            # maju: keliling 2(p+l). Hindari p*l == 2(p+l) (3x6, 4x4, 6x3)
            # supaya malrule tukar_luas tidak bertabrakan dengan kunci.
            p, l = rng.randint(3, 40), rng.randint(3, 40)
            while p * l == 2 * (p + l) or p == l == 2:
                p, l = rng.randint(3, 40), rng.randint(3, 40)
            return {"varian": "keliling", "p": p, "l": l}
        # balik arah: dari K cari luas. l = K/2 - p >= 2, jadi K >= 2(p+2).
        p = rng.randint(3, 30)
        l = rng.randint(2, 25)
        K = 2 * (p + l)
        return {"varian": "balik_luas", "p": p, "K": K}
    if template_id == "luas_segitiga_jajargenjang":
        # a genap supaya a*t/2 dan a*s/2 bilangan bulat. s > t (sisi miring
        # lebih panjang dari tinggi) dan s != 2t supaya lupa_setengah (a*t)
        # != pakai_sisi_miring (a*s/2) untuk varian segitiga.
        a = rng.choice([x for x in range(4, 41, 2)])
        t = rng.randint(3, 20)
        s = rng.randint(t + 1, 2 * t - 1)
        return {"varian": rng.choice(("segitiga", "jajargenjang")), "a": a, "t": t, "s": s}
    if template_id == "luas_segiempat_lain":
        varian = rng.choice(("trapesium", "ketupat_layang", "balik_diagonal"))
        if varian == "trapesium":
            # (a+b) genap supaya (a+b)*t/2 bulat; t >= 3 supaya malrule
            # jawab_sisi (a+b) != kunci; a != b supaya sisi sejajar beda.
            a, b = rng.randint(4, 30), rng.randint(4, 30)
            while (a + b) % 2 or a == b:
                a, b = rng.randint(4, 30), rng.randint(4, 30)
            return {"varian": varian, "a": a, "b": b, "t": rng.randint(3, 15)}
        if varian == "ketupat_layang":
            # d1,d2 genap supaya d1*d2/2 bulat; d1 != d2 supaya jumlah_diagonal
            # != lupa_setengah... cek: d1+d2 != d1*d2/2 untuk d1,d2 >= 4.
            d1 = rng.choice([x for x in range(4, 41, 2)])
            d2 = rng.choice([x for x in range(4, 41, 2)])
            while d1 == d2:
                d2 = rng.choice([x for x in range(4, 41, 2)])
            return {"varian": varian, "d1": d1, "d2": d2}
        # balik arah: cari d2 = 2L/d1. L = d1*d2/2 dengan d1,d2 genap; L//d1
        # harus != kunci (kunci = 2L//d1 = d2) dan != d1 (malrule jawab_d1).
        d1 = rng.choice([x for x in range(4, 41, 2)])
        d2 = rng.choice([x for x in range(4, 41, 2)])
        while d1 == d2:
            d2 = rng.choice([x for x in range(4, 41, 2)])
        L = d1 * d2 // 2
        return {"varian": varian, "L": L, "d1": d1}
    if template_id == "lingkaran_keliling_luas":
        # r lebar (5..130) supaya guard variasi >= 200 kombinasi unik
        # terpenuhi dari 500 seed (r ~126 nilai x 2 varian). r kelipatan 7
        # otomatis memilih π=22/7 di template; sisanya π=3,14.
        r = rng.randint(5, 130)
        return {"varian": rng.choice(("keliling", "luas")), "r": r}
    if template_id == "juring":
        # s dari himpunan OSN (7 nilai) x r (5..40) x 2 varian = 504 combo.
        r = rng.randint(5, 40)
        return {"varian": rng.choice(("luas_juring", "keliling_juring")), "s": rng.choice((30, 45, 60, 90, 120, 180, 270)), "r": r}
    if template_id == "luas_arsiran":
        if rng.random() < 0.3:
            # persegi_titik_tengah: r kelipatan 7 supaya 22/7 (kunci bulat)
            r = rng.choice((7, 14, 21, 28, 35))
            return {"varian": "persegi_titik_tengah", "r": r}
        # jalan_pinggir: dalam lebar (10..100) x lebar (2,4,...,20) = 910 combo
        dalam = rng.randint(10, 100)
        luar = dalam + rng.choice((2, 4, 6, 8, 10, 12, 14, 16, 18, 20))
        return {"varian": "jalan_pinggir", "luar": luar, "dalam": dalam}
    if template_id == "perbandingan_ukuran":
        # k kecil (2,3,4,5) x ukuran lebar (1..30) x 3 varian = 360 combo
        k = rng.choice((2, 3, 4, 5))
        return {"varian": rng.choice(("keliling", "luas", "volume")), "k": k, "ukuran": rng.randint(1, 30)}
    if template_id == "luas_kotak_satuan":
        # P3: grid p × l kecil (2..8) supaya kotaknya masih bisa digambar dan
        # dihitung anak. Eksklusi: p*l == 2(p+l) — (3,6), (4,4), (6,3) —
        # menjatuhkan malrule hitung_keliling; p*l == 2(p+l)+1 — (3,7), (7,3)
        # — menjatuhkan kurang_satu (pola yang sama dengan keliling_luas_datar).
        p, l = rng.randint(2, 8), rng.randint(2, 8)
        while p * l in (2 * (p + l), 2 * (p + l) + 1):
            p, l = rng.randint(2, 8), rng.randint(2, 8)
        # satuan & konteks hanya menghias teks (NON-jawaban) dan menjaga
        # variasi >= 200 kombinasi unik: 44 grid x 2 satuan x 6 konteks.
        return {
            "p": p,
            "l": l,
            "satuan": rng.choice(("cm", "m")),
            "konteks": rng.choice(KONTEKS_KOTAK),
        }
    if template_id == "simetri_bangun":
        # Empat bangun dasar; kunci (jumlah sumbu) ditentukan di template.
        # ukuran/satuan/warna (+lebar untuk persegi-panjang) NON-jawaban —
        # 4 bangun x 14 ukuran x 2 satuan x 6 warna melebihi 200 kombinasi.
        bangun = rng.choice(
            ("persegi", "persegi_panjang", "segitiga_sama_sisi", "belah_ketupat")
        )
        ukuran = rng.randint(3, 16)
        param: dict = {
            "bangun": bangun,
            "ukuran": ukuran,
            "satuan": rng.choice(("cm", "m")),
            "warna": rng.choice(WARNA_KERTAS),
        }
        if bangun == "persegi_panjang":
            # lebar < panjang supaya teksnya masuk akal
            param["lebar"] = rng.randint(2, ukuran - 1)
        return param
    raise KeyError(f"template tidak dikenal: {template_id}")
