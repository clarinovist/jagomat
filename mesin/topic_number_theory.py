"""Paket topik teori-bilangan — Fase 3 plan 30 Aug 2026.

8 template menutup cakupan bilangan & teori bilangan OSN SD: keterbagian
(bagian A), KPK & FPB (B), sisa & paritas (C), pola bilangan (D).
Level P4/P5/P6 (P3 tidak didukung).
"""

from __future__ import annotations

import math
import random

from templates import Malrule, Soal, putar, saring_malrule
from topics import Topik, daftarkan


# ── Latar cerita: HANYA untuk yang memang bercerita ────────────────────
#
# Gelombang 2 mengukur seluruh 8 template paket ini punya <= 2 bentuk
# kalimat. Godaannya membungkus semuanya dengan cerita, dan itu ditolak:
# "Berapa KPK dari 190 dan 108?" adalah perintah hitung murni, tapi
# "Manakah dari bilangan 84, 85, dan 90 yang habis dibagi 3?" juga —
# membungkusnya jadi cerita mengaburkan konsep yang sedang diuji tanpa
# menambah kemampuan apa pun yang dinilai.
#
# Yang lolos saringan itu cuma KPK: "lampu berkedip tiap N detik, kapan
# berkedip bersamaan" adalah bentuk soal KPK yang SUDAH baku di buku dan
# di naskah OSN — ceritanya bukan bungkus, ia bagian dari konsepnya
# (kejadian berulang yang bertemu).
#
# Konsekuensi yang diterima sadar (keputusan pemilik produk 2 Sep 2026):
# teori-bilangan P4 tetap 4 bentuk kalimat, karena ketiga templatenya
# (keterbagian, sisa_pembagian, paritas) semuanya hitung murni. Lebih
# baik jujur di bawah ambang daripada memberi anak soal yang kabur.
# Perbaikan yang benar untuk P4 adalah menambah JENIS soal, bukan latar —
# dicatat di README sebagai batas yang diketahui.


# ── Bagian A — Keterbagian ─────────────────────────────────────────────

# Trap map: d → divisor yang aturannya sering tertukar.
_TRAP: dict[int, int] = {
    2: 3, 3: 2, 4: 2, 5: 3, 6: 2, 8: 4, 9: 3, 11: 9,
}


def _habis(n: int, d: int) -> bool:
    return n % d == 0


def keterbagian(d: int, a: int, b: int, c: int, jawab: int) -> Soal:
    """Dari tiga bilangan, manakah yang habis dibagi d?

    Tepat satu dari a,b,c habis dibagi d (dijamin _parameter). Kunci =
    bilangan itu. Malrule: jawab bilangan tak habis (B), jawab bilangan
    yang habis dibagi trap divisor (K), kurang-1 (H). Kandidat trap
    dicari eksplisit — posisinya setelah shuffle tidak bisa diasumsikan.
    """
    pilihan = (a, b, c)
    kunci = str(pilihan[jawab])
    trap = _TRAP.get(d, d)
    kandidat_trap = [
        x for x in pilihan
        if x != pilihan[jawab] and _habis(x, trap) and not _habis(x, d)
    ]
    trap_num = kandidat_trap[0] if kandidat_trap else pilihan[(jawab + 1) % 3]
    mal = [
        Malrule(
            "keterbagian.pilih_tak_habis",
            str(pilihan[(jawab + 1) % 3]),
            "B",
            f"memilih bilangan yang tidak habis dibagi {d}",
        ),
        Malrule(
            "keterbagian.trap_divisor",
            str(trap_num),
            "K",
            f"memilih bilangan yang hanya habis dibagi {trap} — "
            f"aturan pembagian {d} tidak dipakai dengan benar",
        ),
        Malrule(
            "keterbagian.kurang_satu",
            str(int(kunci) - 1),
            "H",
            "menentukan bilangan yang benar, lalu menguranginya satu",
        ),
    ]
    teks = (
        f"Manakah dari bilangan {a}, {b}, dan {c} yang habis dibagi {d}?"
    )
    return Soal(
        "keterbagian",
        {"d": d, "a": a, "b": b, "c": c, "jawab": jawab},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: bilangan habis dibagi {d} kalau memenuhi ciri "
            f"pembagi {d}. Yang memenuhi = {kunci}."
        ),
        bagian="A",
    )


def _faktor_prima(n: int) -> dict[int, int]:
    """Faktorisasi prima n -> {prima: eksponen}."""
    hasil: dict[int, int] = {}
    sisa = n
    p = 2
    while p * p <= sisa:
        while sisa % p == 0:
            hasil[p] = hasil.get(p, 0) + 1
            sisa //= p
        p += 1 if p == 2 else 2
    if sisa > 1:
        hasil[sisa] = hasil.get(sisa, 0) + 1
    return hasil


# ── Bagian B — KPK & FPB ───────────────────────────────────────────────


def prima_faktorisasi(n: int) -> Soal:
    """Banyak faktor positif dari n = ∏(eᵢ+1)."""
    faktor = _faktor_prima(n)
    kunci = 1
    for e in faktor.values():
        kunci *= e + 1
    mal = [
        Malrule(
            "prima.jumlah_eksponen",
            str(sum(faktor.values())),
            "K",
            f"menjumlahkan eksponen {sum(faktor.values())} padahal banyak "
            "faktor = hasil kali (eᵢ+1)",
        ),
        Malrule(
            "prima.banyak_prima_beda",
            str(len(faktor)),
            "K",
            f"menghitung banyak faktor prima berbeda ({len(faktor)}) "
            "padahal yang diminta banyak faktor positif",
        ),
        Malrule(
            "prima.kurang_satu",
            str(kunci - 1),
            "H",
            "perhitungan banyak faktor benar, hasilnya meleset satu",
        ),
    ]
    teks = f"Berapa banyak faktor positif dari bilangan {n}?"
    return Soal(
        "prima_faktorisasi",
        {"n": n},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: pecah {n} jadi perkalian bilangan prima, lalu banyak "
            f"faktor = hasil kali (pangkat + 1) tiap prima = {kunci}."
        ),
        bagian="B",
    )


def kpk_dua_bilangan(a: int, b: int) -> Soal:
    """KPK dari a dan b = a·b / gcd(a,b)."""
    kunci = a * b // math.gcd(a, b)
    mal = [
        Malrule(
            "kpk.dikali",
            str(a * b),
            "K",
            f"mengalikan {a}×{b} — lupa membagi dengan FPB {math.gcd(a, b)}",
        ),
        Malrule(
            "kpk.tertukar_fpb",
            str(math.gcd(a, b)),
            "K",
            f"menjawab FPB {math.gcd(a, b)} padahal yang diminta KPK",
        ),
        Malrule(
            "kpk.kurang_satu",
            str(kunci - 1),
            "H",
            "perhitungan KPK benar, hasilnya meleset satu",
        ),
    ]
    # Latar KPK: kejadian berulang yang bertemu. Bentuk pertama sengaja
    # tetap perintah murni — sebagian anak justru terbantu melihat soal
    # yang sama dalam dua rupa (nama konsepnya dan penerapannya), dan
    # menghilangkan bentuk murni berarti anak tidak pernah lagi diminta
    # menyebut KPK dengan namanya.
    cerita = putar(
        (
            None,
            ("Dua lampu hias berkedip setiap", "detik", "berkedip bersamaan"),
            ("Dua bus berangkat dari terminal setiap", "menit", "berangkat bersamaan"),
            ("Dua lonceng dibunyikan setiap", "detik", "berbunyi bersamaan"),
            ("Dua kapal singgah di pelabuhan setiap", "hari", "singgah bersamaan"),
        ),
        a,
        b,
    )
    if cerita is None:
        teks = f"Berapa KPK dari {a} dan {b}?"
    else:
        pembuka, satuan, kejadian = cerita
        teks = (
            f"{pembuka} {a} {satuan} dan {b} {satuan}. Jika tadi keduanya "
            f"{kejadian}, setelah berapa {satuan} keduanya {kejadian} lagi?"
        )
    return Soal(
        "kpk_dua_bilangan",
        {"a": a, "b": b},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: yang dicari KPK, yaitu kelipatan bersama TERKECIL. "
            f"KPK = (a x b) : FPB. "
            f"({a} x {b}) : {math.gcd(a, b)} = {kunci}."
        ),
        bagian="B",
    )


def fpb_kpk_hubungan(a: int, b: int) -> Soal:
    """FPB × KPK dari a dan b = a × b (identitas)."""
    kunci = a * b
    kpk = a * b // math.gcd(a, b)
    mal = [
        Malrule(
            "hubungan.hanya_fpb",
            str(math.gcd(a, b)),
            "K",
            f"menjawab FPB {math.gcd(a, b)} — hasil kali FPB×KPK tidak dihitung",
        ),
        Malrule(
            "hubungan.hanya_kpk",
            str(kpk),
            "K",
            f"menjawab KPK {kpk} — hasil kali FPB×KPK tidak dihitung",
        ),
        Malrule(
            "hubungan.kurang_satu",
            str(kunci - 1),
            "H",
            "perhitungan a×b benar, hasilnya meleset satu",
        ),
    ]
    teks = (
        f"Berapa hasil kali FPB dan KPK dari {a} dan {b}?"
    )
    return Soal(
        "fpb_kpk_hubungan",
        {"a": a, "b": b},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: FPB x KPK = hasil kali kedua bilangan. "
            f"{a} x {b} = {kunci}."
        ),
        bagian="B",
    )


# ── Bagian C — Sisa & paritas ──────────────────────────────────────────


def sisa_pembagian(N: int, d: int) -> Soal:
    """N dibagi d bersisa N % d (sisa >= 1, d > sisa)."""
    kunci = N % d
    # Urutan penting: H dulu. kurang_satu (kunci−1) kadang = complement
    # (d−kunci) saat d = 2·kunci−1; kalau H muncul belakangan, saring
    # membuangnya dan soal kehilangan jalur H.
    mal = [
        Malrule(
            "sisa.kurang_satu",
            str(kunci - 1),
            "H",
            "pembagian benar, sisanya meleset satu",
        ),
        Malrule(
            "sisa.quotient",
            str(N // d),
            "K",
            f"menjawab hasil bagi {N // d} padahal yang diminta sisa",
        ),
        Malrule(
            "sisa.complement",
            str(d - kunci),
            "K",
            f"menjawab {d}−{kunci} — menghitung kekurangan menuju kelipatan berikutnya",
        ),
    ]
    teks = f"Jika {N} dibagi {d}, berapa sisanya?"
    return Soal(
        "sisa_pembagian",
        {"N": N, "d": d},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: {N} : {d} = {N // d} sisa {kunci}. "
            f"Yang diminta SISAnya, yaitu {kunci}."
        ),
        bagian="C",
    )


def paritas(a: int, n: int) -> Soal:
    """Jumlah n bilangan ganjil berurutan mulai a = n·(a+n−1).

    a=1 → n² (bentuk klasik). Parameter a memeperluas ruang variasi
    (guard >= 200) tanpa mengubah konsep paritas.
    """
    kunci = n * (a + n - 1)
    # H dulu: kurang_satu tidak pernah sama dengan kunci.
    mal = [
        Malrule(
            "paritas.kurang_satu",
            str(kunci - 1),
            "H",
            "rumus jumlah benar, hasilnya meleset satu",
        ),
        Malrule(
            "paritas.jumlah_natural",
            str(n * (n + 1) // 2),
            "K",
            "memakai rumus 1+2+...+n padahal yang dijumlahkan bilangan ganjil mulai a",
        ),
        Malrule(
            "paritas.hanya_suku_pertama",
            str(n * a),
            "K",
            "mengalikan banyak suku dengan suku pertama, lupa beda 2",
        ),
    ]
    if a == 1:
        teks = f"Berapa jumlah {n} bilangan ganjil pertama (1 + 3 + 5 + …)?"
    else:
        teks = (
            f"Berapa jumlah {n} bilangan ganjil berurutan yang dimulai "
            f"dari {a} ({a} + {a+2} + …)?"
        )
    return Soal(
        "paritas",
        {"a": a, "n": n},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: {n} bilangan berurutan mulai {a}. "
            f"Jumlah = {n} x ({a} + {a + n - 1}) : 2 = {kunci}."
        ),
        bagian="C",
    )


# ── Bagian D — Pola bilangan ───────────────────────────────────────────


def angka_satuan_pangkat(a: int, b: int) -> Soal:
    """Digit satuan a^b lewat siklus (a, a², a³, ... berulang)."""
    satuan = 1
    for _ in range(b):
        satuan = (satuan * a) % 10
    kunci = satuan
    # siklus_meleset: anak menghitung b+1 (atau lupa b=1 kasus awal)
    siklus_meleset = 1
    for _ in range(b + 1):
        siklus_meleset = (siklus_meleset * a) % 10
    mal = [
        Malrule(
            "satuan.jawab_a",
            str(a % 10),
            "K",
            f"menjawab digit satuan {a} (pangkatnya tidak dihitung)",
        ),
        Malrule(
            "satuan.siklus_meleset",
            str(siklus_meleset),
            "K",
            "menghitung satu pangkat terlalu banyak/berikutnya",
        ),
        Malrule(
            "satuan.kurang_satu",
            str((kunci - 1) % 10),
            "H",
            "siklus benar, hasil akhirnya meleset satu",
        ),
    ]
    teks = f"Berapa digit satuan dari {a} pangkat {b} ({a}^{b})?"
    return Soal(
        "angka_satuan_pangkat",
        {"a": a, "b": b},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: digit satuan {a} pangkat berulang dalam siklus. "
            f"Cari sisa {b} dibagi panjang siklusnya, hasilnya {kunci}."
        ),
        bagian="D",
    )


def gauss_deret(n: int) -> Soal:
    """1+2+...+n = n(n+1)/2 (jumlah deret aritmetika)."""
    kunci = n * (n + 1) // 2
    mal = [
        Malrule(
            "gauss.dikira_ganjil",
            str(n * n),
            "K",
            f"memakai n² (jumlah n ganjil) padahal yang dijumlahkan 1..{n}",
        ),
        Malrule(
            "gauss.lupa_bagi_2",
            str(n * (n + 1)),
            "K",
            "menghitung n×(n+1) tanpa membagi dua",
        ),
        Malrule(
            "gauss.kurang_satu",
            str(kunci - 1),
            "H",
            "rumus benar, hasilnya meleset satu",
        ),
    ]
    teks = f"Berapa jumlah 1 + 2 + 3 + … + {n}?"
    return Soal(
        "gauss_deret",
        {"n": n},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: 1 + 2 + ... + n = n x (n+1) : 2. "
            f"{n} x {n + 1} : 2 = {kunci}."
        ),
        bagian="D",
    )


REGISTRI_TOPIK = {
    "keterbagian": keterbagian,
    "prima_faktorisasi": prima_faktorisasi,
    "kpk_dua_bilangan": kpk_dua_bilangan,
    "fpb_kpk_hubungan": fpb_kpk_hubungan,
    "sisa_pembagian": sisa_pembagian,
    "paritas": paritas,
    "angka_satuan_pangkat": angka_satuan_pangkat,
    "gauss_deret": gauss_deret,
}

KOMPOSISI = {
    # P4 (10): 1,5,6 x3 + 1
    "P4": (
        "keterbagian", "sisa_pembagian", "paritas",
        "keterbagian", "sisa_pembagian", "paritas",
        "keterbagian", "sisa_pembagian", "paritas",
        "keterbagian",
    ),
    # P5 (10): 1,2,3,5,6,8,1,2,3,8
    "P5": (
        "keterbagian", "prima_faktorisasi", "kpk_dua_bilangan",
        "sisa_pembagian", "paritas", "gauss_deret",
        "keterbagian", "prima_faktorisasi", "kpk_dua_bilangan",
        "gauss_deret",
    ),
    # P6 (10): 1,2,3,4,5,7,8,1,4,7
    "P6": (
        "keterbagian", "prima_faktorisasi", "kpk_dua_bilangan",
        "fpb_kpk_hubungan", "sisa_pembagian", "angka_satuan_pangkat",
        "gauss_deret", "keterbagian", "fpb_kpk_hubungan",
        "angka_satuan_pangkat",
    ),
}

JUDUL_BAGIAN = {
    "A": "Bagian A — Keterbagian",
    "B": "Bagian B — KPK & FPB",
    "C": "Bagian C — Sisa & paritas",
    "D": "Bagian D — Pola bilangan",
}

CATATAN_BAGIAN = {
    "A": "Pelajari aturan habis dibagi 2, 3, 4, 5, 6, 8, 9, dan 11.",
    "B": "Faktorisasi prima adalah kunci KPK dan FPB.",
    "D": "Jumlah deret punya jalan pintas (rumus Gauss).",
}


def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id == "keterbagian":
        # d pool per level; pilih tiga bilangan, tepat satu habis dibagi d.
        if level == "P4":
            pool = (2, 3, 4, 5, 6)
        elif level == "P5":
            pool = (2, 3, 4, 5, 6, 8, 9)
        else:
            pool = (2, 3, 4, 5, 6, 8, 9, 11)
        d = rng.choice(pool)
        trap = _TRAP[d]
        # bilangan benar: kelipatan d (2 digit)
        benar = d * rng.randint(4, 50)
        # bilangan trap: kelipatan trap, tidak habis dibagi d
        trap_num = trap * rng.randint(5, 60)
        while _habis(trap_num, d) or trap_num == benar:
            trap_num = trap * rng.randint(5, 60)
        # bilangan salah: tak habis dibagi d maupun trap (supaya malrule
        # pilih_tak_habis dan trap_divisor tidak menebak bilangan sama)
        salah = benar + 1
        while _habis(salah, d) or _habis(salah, trap) or salah == benar:
            salah += 1
        # Rotasi menjaga salah tetap setelah kunci untuk malrule B,
        # tanpa membocorkan posisi benar atau mengubah renderer lama.
        pilihan = [benar, salah, trap_num]
        geser = rng.randrange(3)
        pilihan = pilihan[geser:] + pilihan[:geser]
        return {"d": d, "a": pilihan[0], "b": pilihan[1], "c": pilihan[2],
                "jawab": (-geser) % 3}
    if template_id == "prima_faktorisasi":
        # n acak rentang lebar: berapa pun n, faktorisasinya dihitung di
        # template (banyak faktor positif = ∏(eᵢ+1)). P5 lebih kecil.
        if level == "P5":
            return {"n": rng.randint(12, 2000)}
        return {"n": rng.randint(12, 5000)}
    if template_id in ("kpk_dua_bilangan", "fpb_kpk_hubungan"):
        # a,b dengan gcd >= 2 supaya KPK beda dari a×b; a!=b.
        a, b = rng.randint(6, 200), rng.randint(6, 200)
        while a == b or math.gcd(a, b) < 2:
            a, b = rng.randint(6, 200), rng.randint(6, 200)
        return {"a": a, "b": b}
    if template_id == "sisa_pembagian":
        # Hindari: kunci 0 (H negatif), quotient == kunci (N//d == N%d),
        # complement == kunci (d == 2·sisa), dan K == H (quotient == kunci−1
        # atau complement == kunci−1) — semua membuat jalur K atau H hilang
        # setelah saring_malrule.
        N = rng.randint(10, 500)
        d = rng.randint(3, 20)
        kunci = N % d
        while (
            kunci == 0
            or N // d == kunci
            or d - kunci == kunci
            or N // d == kunci - 1
            or d - kunci == kunci - 1
        ):
            N = rng.randint(10, 500)
            d = rng.randint(3, 20)
            kunci = N % d
        return {"N": N, "d": d}
    if template_id == "paritas":
        # a mulai (boleh 1..15), n banyak suku (2..20); a,n lebar supaya
        # ruang variasi >= 200. a=1 bentuk klasik n².
        a = rng.randint(1, 15)
        n = rng.randint(2, 20)
        return {"a": a, "n": n}
    if template_id == "angka_satuan_pangkat":
        # a dari {2,3,4,7,8,9}: siklus satuan >= 2 (a=5/6 selalu sama,
        # membuat malrule jawab_a menyamai kunci). Hindari b yang membuat
        # a^b berdigit satuan = a%10 — nanti jawab_a (K) menebak kunci.
        # b lebar 2..100 supaya 500 seed tetap >= 200 (filter reject ~1/3).
        a = rng.choice((2, 3, 4, 7, 8, 9))
        b = rng.randint(2, 100)
        satuan = pow(a, b, 10)
        while satuan == a % 10:
            b = rng.randint(2, 100)
            satuan = pow(a, b, 10)
        return {"a": a, "b": b}
    if template_id == "gauss_deret":
        # n lebar 3..300 supaya ruang variasi >= 200 (hasil <= 45150).
        return {"n": rng.randint(3, 300)}
    raise KeyError(f"template tidak dikenal: {template_id}")


TOPIK = Topik(
    id="teori-bilangan",
    nama="Teori Bilangan",
    judul_lembar="Latihan Teori Bilangan",
    judul_penilaian="Penilaian — Teori Bilangan",
    templates=REGISTRI_TOPIK,
    komposisi=KOMPOSISI,
    profil={"P4": {}, "P5": {}, "P6": {}},
    judul_bagian=JUDUL_BAGIAN,
    catatan_bagian=CATATAN_BAGIAN,
    parameter_untuk=_parameter,
)

daftarkan(TOPIK)