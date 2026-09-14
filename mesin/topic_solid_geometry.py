"""Paket topik geometri-ruang — Fase 5 plan 30 Aug 2026.

Tujuh template menutup cakupan geometri ruang OSN SD: unsur bangun ruang
& volume (bagian A), luas permukaan & jaring (B), kubus dicat & perbandingan
volume (C). Level P5/P6 (P3/P4 tidak didukung). Fungsi tanpa versi menjaga
teks warisan; soal baru memakai matematika versi2 dan SVG snapshot opt-in.
"""

from __future__ import annotations

import random

from templates import Malrule, Soal, saring_malrule
from topics import Topik, daftarkan
from solid_geometry_versions import soal_berversi, parameter_baru


# ── Data bangun ruang ───────────────────────────────────────────────────

BANGUN = {
    # nama: (rusuk, sisi, titik)
    "kubus": (12, 6, 8),
    "balok": (12, 6, 8),
    "prisma_segitiga": (9, 5, 6),
    "tabung": (2, 3, 0),
    "limas_segiempat": (8, 5, 5),
    "kerucut": (1, 2, 1),
}

# Untuk tiap bangun, bangun yang paling sering tertukar (sumber malrule K)
TERTUKAR = {
    "kubus": "prisma_segitiga",        # kubus 12/6/8 ≠ prisma 9/5/6
    "balok": "prisma_segitiga",        # balok 12/6/8 ≠ prisma 9/5/6
    "prisma_segitiga": "limas_segiempat",  # prisma 9/5/6 ≠ limas 8/5/5
    "tabung": "kerucut",               # tabung 2/3/0 ≠ kerucut 1/2/1
    "limas_segiempat": "prisma_segitiga",
    "kerucut": "tabung",
}

TANYA = ("rusuk", "sisi", "titik")
TANYA_INDEKS = {"rusuk": 0, "sisi": 1, "titik": 2}

# ── 11 jaring-jaring kubus (koordinat (baris, kolom) dalam grid 3×4) ────
# Setiap jaring adalah tuple koordinat 6 kotak. Baris 0=atas, kolom 0=kiri.
# Sumber: 11 jaring kubus yang berbeda.
JARING_KUBUS: tuple[tuple[tuple[int, int], ...], ...] = (
    # 1. Salib: 4 baris-0, 1 baris-1 kol-1, 1 baris-2 kol-1
    ((0, 0), (0, 1), (0, 2), (0, 3), (1, 1), (2, 1)),
    # 2. T: 3 baris-0, 1 baris-1 kol-0, 1 baris-1 kol-2, 1 baris-2 kol-1
    ((0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 1)),
    # 3. Tangga: 2 baris-0, 2 baris-1 kol-1, 2 baris-2 kol-2
    ((0, 0), (0, 1), (1, 1), (1, 2), (2, 2), (2, 3)),
    # 4. L: 3 baris-0, 1 baris-1 kol-0, 1 baris-2 kol-0, 1 baris-2 kol-1
    ((0, 0), (0, 1), (0, 2), (1, 0), (2, 0), (2, 1)),
    # 5. Zigzag: 3 baris-0, 1 baris-1 kol-0, 1 baris-2 kol-0, 1 baris-2 kol-2
    ((0, 0), (0, 1), (0, 2), (1, 0), (2, 0), (2, 2)),
    # 6. 4-1-1: 4 baris-0, 1 baris-1 kol-0, 1 baris-2 kol-3
    ((0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (2, 3)),
    # 7. 4-1-1 varian: 4 baris-0, 1 baris-1 kol-0, 1 baris-2 kol-0
    ((0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (2, 0)),
    # 8. 3-2-1: 3 baris-0, 2 baris-1 kol-1, 1 baris-2 kol-0
    ((0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 0)),
    # 9. 3-2-1 varian: 3 baris-0, 2 baris-1 kol-0, 1 baris-2 kol-2
    ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 2)),
    # 10. 2-2-2: 2 baris-0, 2 baris-1, 2 baris-2, semua kolom berselang
    ((0, 0), (0, 1), (1, 1), (1, 2), (2, 2), (2, 3)),
    # 11. 2-2-2 lurus: 2 baris-0, 2 baris-1, 2 baris-2, semua kolom sama
    ((0, 1), (0, 2), (1, 1), (1, 2), (2, 1), (2, 2)),
)

# Jaring PALSU (pola error umum). Jaring ini TIDAK bisa dilipat jadi kubus
# karena: 1) sisi bentrok (tumpang tindih saat dilipat), 2) lubang (sisi
# kurang), 3) sambungan salah (dua sisi jadi satu saat dilipat).
JARING_PALSU: tuple[tuple[tuple[int, int], ...], ...] = (
    # 1. 4 baris-0, 1 baris-1 kol-2, 1 baris-2 kol-2 (bentrok baris-1/2)
    ((0, 0), (0, 1), (0, 2), (0, 3), (1, 2), (2, 2)),
    # 2. 4 baris-0, 1 baris-1 kol-0, 1 baris-1 kol-3 (bentrok saat dilipat)
    ((0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 3)),
    # 3. 3 baris-0, 2 baris-1 kol-2, 1 baris-2 kol-0 (lubang di tengah)
    ((0, 0), (0, 1), (0, 2), (1, 2), (1, 3), (2, 0)),
    # 4. 3 baris-0, 1 baris-1 kol-0, 1 baris-1 kol-1, 1 baris-2 kol-0 (bentrok)
    ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 0)),
    # 5. 2 baris-0, 2 baris-1, 2 baris-2, semua di kol-0 (hanya 3 baris, lubang)
    ((0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)),
    # 6. 4 baris-0, 1 baris-1 kol-1, 1 baris-2 kol-2 (bentrok diagonal)
    ((0, 0), (0, 1), (0, 2), (0, 3), (1, 1), (2, 2)),
    # 7. 3 baris-0, 1 baris-1 kol-0, 1 baris-1 kol-1, 1 baris-2 kol-2 (lubang)
    ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 2)),
    # 8. 4 baris-0, 1 baris-1 kol-0, 1 baris-1 kol-1 (bentrok — 2 di baris 1)
    ((0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1)),
)


# ── Bagian A — Unsur & volume ────────────────────────────────────────────


def unsur_bangun(bangun: str, tanya: str, n: int = 1) -> Soal:
    """Hitung jumlah rusuk/sisi/titik sudut bangun ruang,
    atau total jika ada n bangun identik (varian *_kali)."""
    tanya_asli = tanya.replace("_kali", "")
    nilai = BANGUN[bangun][TANYA_INDEKS[tanya_asli]]
    if tanya.endswith("_kali"):
        # n bangun identik: total = nilai × n
        kunci = str(nilai * n)
        teks = (f"Setiap bangun {bangun.replace('_', ' ')} memiliki "
                f"{nilai} {tanya_asli}. Berapa total {tanya_asli} "
                f"dari {n} bangun {bangun.replace('_', ' ')}?")
        k_tertukar = str(nilai)  # lupa ×n
        h = str(int(kunci) - 1)
        if k_tertukar == kunci or k_tertukar == h:
            k_tertukar = str(int(kunci) + 1)
        mal = [
            Malrule(f"unsur.kali_lupa_{bangun}", k_tertukar, "K",
                    f"menjawab jumlah {tanya_asli} satu bangun, bukan {n} bangun"),
            Malrule(f"unsur.kali_lebih_{bangun}", str(nilai * (n + 1)), "K",
                    f"menghitung {n+1} bangun, bukan {n}"),
            Malrule(f"unsur.kali_kurang_{bangun}", h, "H",
                    "perhitungan benar, hasilnya meleset satu"),
        ]
        return Soal(
            "unsur_bangun",
            {"bangun": bangun, "tanya": tanya, "n": n},
            teks,
            kunci,
            saring_malrule(kunci, mal),
        pembahasan=(
            f"Langkah: kubus/balok punya 6 sisi, 12 rusuk, 8 titik sudut; "
            f"limas segiempat 5 sisi, 8 rusuk, 5 titik sudut. "
            f"Jawabannya {kunci}."
        ),
            bagian="A",
        )

    # Varian dasar: hitung jumlah rusuk/sisi/titik satu bangun
    kunci = str(nilai)

    # Bangun yang sering tertukar sebagai sumber malrule K
    tertukar = BANGUN[TERTUKAR[bangun]][TANYA_INDEKS[tanya]]
    k_tertukar = str(tertukar)

    # Malrule H: kunci ± 1 (hindari negatif)
    if nilai > 1:
        h = str(nilai - 1)
    else:
        h = str(nilai + 1)

    # Pastikan K dan H tidak bertabrakan
    if k_tertukar == kunci:
        k_tertukar = str(int(kunci) + 2)
    if h == k_tertukar:
        h = str(int(h) + 2)

    # Nama bangun dalam bahasa Indonesia
    nama_bangun = bangun.replace("_", " ")
    mal = [
        Malrule(f"unsur.tertukar_{bangun}", k_tertukar, "K",
                f"menjawab jumlah {tanya} bangun {TERTUKAR[bangun].replace('_', ' ')}"),
        Malrule(f"unsur.kurang_satu_{bangun}", h, "H",
                "perhitungan benar, hasilnya meleset satu"),
        Malrule(f"unsur.anggap_satu", "1", "B",
                "menjawab satu (seolah-olah hanya ada satu)"),
    ]
    teks = f"Bangun ruang {nama_bangun} memiliki berapa jumlah {tanya}?"
    return Soal(
        "unsur_bangun",
        {"bangun": bangun, "tanya": tanya},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        pembahasan=(
            f"Langkah: hitung nilai dasarnya dulu, lalu kalikan sebanyak "
            f"yang diminta soal. Hasilnya {kunci}."
        ),
        bagian="A",
    )


def volume_kubus_balok(varian: str, s: int = 0, p: int = 0,
                        l: int = 0, t: int = 0,
                        V: int = 0) -> Soal:
    """V = s³ atau V = p·l·t; dua arah (cari V atau cari sisi)."""
    if varian == "kubus_cari_V":
        kunci = s * s * s
        teks = f"Kubus dengan panjang rusuk {s} cm. Berapa volumenya (cm³)?"
        k_salah = str(s * s)  # s² lupa ×s
        k_lain = str(s * 2)  # s×2/s×6
    elif varian == "kubus_cari_s":
        kunci = s
        teks = f"Volume kubus {V} cm³. Berapa panjang rusuknya (cm)?"
        k_salah = str(V // 2)  # V/2 bukan ∛V
        k_lain = str(V // 3)  # V/3
    elif varian == "balok_cari_V":
        kunci = p * l * t
        teks = f"Balok berukuran {p} cm × {l} cm × {t} cm. Berapa volumenya (cm³)?"
        k_salah = str(p * l)  # lupa ×t
        k_lain = str(p + l + t)  # jumlah rusuk
    else:  # balok_cari_p
        kunci = p
        teks = f"Volume balok {V} cm³, lebar {l} cm, tinggi {t} cm. Berapa panjangnya (cm)?"
        k_salah = str(V // (l + t))  # V/(l+t) bukan V/(l·t)
        k_lain = str(V // (l * t) + 1)

    # Jaga K tidak bertabrakan dengan kunci
    if k_salah == str(kunci):
        k_salah = str(kunci + 1)
    if k_lain == str(kunci) or k_lain == k_salah:
        k_lain = str(kunci + 2)

    mal = [
        Malrule("volume.salah_rumus", k_salah, "K", "memakai rumus yang salah — lupa satu dimensi"),
        Malrule("volume.rumus_lain", k_lain, "K", "menggunakan rumus yang berbeda"),
        Malrule("volume.kurang_satu", str(kunci - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "volume_kubus_balok",
        {"varian": varian, "s": s, "p": p, "l": l, "t": t, "V": V},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: volume kubus = rusuk x rusuk x rusuk; "
            f"volume balok = panjang x lebar x tinggi. Hasilnya {kunci}."
        ),
        bagian="A",
    )


@soal_berversi
def volume_prisma_tabung(varian: str, a: int = 0, t_segitiga: int = 0,
                          t_prisma: int = 0, r: int = 0,
                          t: int = 0, V: int = 0) -> Soal:
    """V = (½·a·t_segitiga) × t_prisma atau V = πr²t."""
    if varian == "prisma_V":
        V = (a * t_segitiga // 2) * t_prisma
        kunci = str(V)
        teks = f"Prisma dengan alas segitiga (alas {a} cm, tinggi {t_segitiga} cm) dan tinggi prisma {t_prisma} cm. Berapa volumenya (cm³)?"
        k1 = str(a * t_segitiga * t_prisma)  # lupa ½
        k2 = str(a * t_prisma)  # lupa a·t/2
        alas = "segitiga"
    elif varian == "tabung_V":
        if r % 7 == 0:
            pi = 22 / 7
            pi_label = "22/7"
        else:
            pi = 3.14
            pi_label = "3,14"
        V = int(pi * r * r * t)
        kunci = str(V)
        teks = f"Tabung dengan jari-jari {r} cm dan tinggi {t} cm (π = {pi_label}). Berapa volumenya (cm³)?"
        k1 = str(int(pi * 2 * r * t))  # 2πrt lupa r²
        k2 = str(int(pi * r * r))  # πr² lupa ×t
        alas = "tabung"
    elif varian == "prisma_balik":
        # balik arah: V = (a·t/2)·t_prisma → t_prisma = V / (a·t/2)
        t_prisma = V // (a * t_segitiga // 2)
        kunci = str(t_prisma)
        teks = f"Volume prisma {V} cm³. Alas segitiga {a}×{t_segitiga} cm. Berapa tinggi prismanya (cm)?"
        k1 = str(V * 2 // (a * t_segitiga))  # V×2/(a·t)
        k2 = str(V // (a + t_segitiga))
        alas = "segitiga"
    else:  # tabung_balik
        if r % 7 == 0:
            pi = 22 / 7
            pi_label = "22/7"
        else:
            pi = 3.14
            pi_label = "3,14"
        t = V // int(pi * r * r)
        kunci = str(t)
        teks = f"Volume tabung {V} cm³, jari-jari {r} cm (π = {pi_label}). Berapa tingginya (cm)?"
        k1 = str(V // int(pi * 2 * r))  # V/(2πr) — lupa r²
        k2 = str(V // r)  # V/r
        alas = "tabung"

    h = str(int(kunci) - 1)
    # Jaga K/H tidak bertabrakan dengan kunci atau satu sama lain
    if k1 == kunci or k1 == h:
        k1 = str(int(kunci) + 1)
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = str(int(kunci) + 2)

    mal = [
        Malrule(f"volprisma.lupa_setengah_{alas}", k1, "K", "lupa membagi dua untuk luas alas segitiga"),
        Malrule(f"volprisma.rumus_lain_{alas}", k2, "K", "memakai rumus yang salah"),
        Malrule(f"volprisma.kurang_satu", h, "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "volume_prisma_tabung",
        {"varian": varian, "a": a, "t_segitiga": t_segitiga, "t_prisma": t_prisma,
         "r": r, "t": t, "V": V},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: volume prisma = luas alas x tinggi; "
            f"volume tabung = pi x r x r x tinggi. Hasilnya {kunci}."
        ),
        bagian="A",
    )


# ── Bagian B — Luas permukaan & jaring ─────────────────────────────────


@soal_berversi
def luas_permukaan(varian: str, s: int = 0,
                   p: int = 0, l: int = 0, t: int = 0,
                   r: int = 0, LP: int = 0) -> Soal:
    """LP = 6s², 2(pl+pt+lt), 2πr²+2πrt; dua arah."""
    if varian == "kubus_LP":
        LP = 6 * s * s
        kunci = str(LP)
        teks = f"Kubus dengan panjang rusuk {s} cm. Berapa luas permukaannya (cm²)?"
        k1 = str(s * s)  # lupa ×6
        k2 = str(6 * s)  # 6s bukan 6s²
        bangun = "kubus"
    elif varian == "kubus_cari_s":
        kunci = str(s)
        teks = f"Luas permukaan kubus {LP} cm². Berapa panjang rusuknya (cm)?"
        k1 = str(LP // 6 // 2)  # LP/6/2
        k2 = str(LP // 12)  # LP/12
        bangun = "kubus"
    elif varian == "balok_LP":
        LP = 2 * (p * l + p * t + l * t)
        kunci = str(LP)
        teks = f"Balok berukuran {p} cm × {l} cm × {t} cm. Berapa luas permukaannya (cm²)?"
        k1 = str(p * l + p * t + l * t)  # lupa ×2
        k2 = str(p * l * t)  # volume
        bangun = "balok"
    elif varian == "balok_cari_p":
        kunci = str(p)
        teks = f"Luas permukaan balok {LP} cm², lebar {l} cm, tinggi {t} cm. Berapa panjangnya (cm)?"
        k1 = str(LP // 2 // (l + t))
        k2 = str(LP // (l * t))
        bangun = "balok"
    elif varian == "tabung_LP":
        if r % 7 == 0:
            pi = 22 / 7
            pi_label = "22/7"
        else:
            pi = 3.14
            pi_label = "3,14"
        LP = int(2 * pi * r * r + 2 * pi * r * t)
        kunci = str(LP)
        teks = f"Tabung dengan jari-jari {r} cm dan tinggi {t} cm (π = {pi_label}). Berapa luas permukaannya (cm²)?"
        k1 = str(int(pi * r * r + 2 * pi * r * t))  # lupa ×2 untuk r²
        k2 = str(int(pi * r * r * t))  # volume
        bangun = "tabung"
    else:  # tabung_cari_t
        # LP = 2πr²+2πrt → t = LP/(2πr) − r
        if r % 7 == 0:
            pi = 22 / 7
            pi_label = "22/7"
        else:
            pi = 3.14
            pi_label = "3,14"
        t = int(LP // int(2 * pi * r) - r)
        kunci = str(t)
        teks = f"Luas permukaan tabung {LP} cm², jari-jari {r} cm (π = {pi_label}). Berapa tingginya (cm)?"
        k1 = str(int(LP // int(2 * pi * r)))  # LP/(2πr) — lupa −r
        k2 = str(int(LP // int(pi * r * r)))  # V = πr²t
        bangun = "tabung"

    h = str(int(kunci) - 1)
    if k1 == kunci or k1 == h:
        k1 = str(int(kunci) + 1)
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = str(int(kunci) + 2)

    mal = [
        Malrule(f"lp.{bangun}.lupa", k1, "K", "lupa faktor pengali pada rumus luas permukaan"),
        Malrule(f"lp.{bangun}.rumus_lain", k2, "K", "memakai rumus yang salah"),
        Malrule("lp.kurang_satu", h, "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "luas_permukaan",
        {"varian": varian, "s": s, "p": p, "l": l, "t": t, "r": r, "LP": LP},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: LP kubus = 6 x rusuk x rusuk; "
            f"LP balok = 2 x (pl + pt + lt); "
            f"LP tabung = 2 x pi x r x (r + tinggi). Hasilnya {kunci}."
        ),
        bagian="B",
    )


def _gambar_jaring(koordinat: tuple[tuple[int, int], ...]) -> str:
    """Render jaring sebagai ASCII art (3 baris × 4 kolom)."""
    grid = [["  " for _ in range(4)] for _ in range(3)]
    for r, c in koordinat:
        if 0 <= r < 3 and 0 <= c < 4:
            grid[r][c] = "■ "
    baris = []
    for r in range(3):
        b = "".join(grid[r]).rstrip()
        if b:
            baris.append(b)
    return "\n".join(baris) if baris else "(kosong)"


@soal_berversi
def jaring_jaring(pilihan_benar: int, urutan: tuple[int, ...]) -> Soal:
    """Dari 5 pilihan, pilih jaring yang bisa dilipat jadi kubus."""
    # Bangun 5 pilihan: 1 benar + 4 palsu (diacak posisinya)
    opsi = ["A", "B", "C", "D", "E"]
    benar = urutan[0]  # urutan[0] = indeks jaring benar di JARING_KUBUS
    palsu = urutan[1:5]  # 4 indeks jaring palsu

    benar_gambar = _gambar_jaring(JARING_KUBUS[benar])
    pilihan_gambar = []
    for i in range(5):
        if i == pilihan_benar:
            pilihan_gambar.append(benar_gambar)
        else:
            idx = palsu[i if i < pilihan_benar else i - 1]
            pilihan_gambar.append(_gambar_jaring(JARING_PALSU[idx % len(JARING_PALSU)]))

    # Teks: tampilkan 5 pilihan dengan ASCII art
    teks = "Manakah dari jaring-jaring berikut yang dapat dilipat menjadi kubus?\n\n"
    for i, (label, gambar) in enumerate(zip(opsi, pilihan_gambar)):
        teks += f"{label}.\n{gambar}\n\n"

    kunci = opsi[pilihan_benar]
    jawaban_palsu = [o for i, o in enumerate(opsi) if i != pilihan_benar]
    # Jawaban berupa huruf A-E: setiap huruf selain kunci sudah pasti salah.
    # Gunakan 4 huruf salah yang BERBEDA untuk B/K/K/H supaya saring_malrule
    # tidak membuang duplikat (satu jawaban salah -> dua kode = diagnosis palsu).
    mal = [
        Malrule("jaring.kebalikan", jawaban_palsu[0], "B",
                f"memilih {jawaban_palsu[0]}, padahal {kunci} yang benar"),
        Malrule("jaring.salah_1", jawaban_palsu[1], "K",
                f"jaring {jawaban_palsu[1]} tidak dapat dilipat tanpa sisi bentrok"),
        Malrule("jaring.salah_2", jawaban_palsu[2], "K",
                f"jaring {jawaban_palsu[2]} memiliki persegi yang tidak terhubung"),
        Malrule("jaring.kurang_satu", jawaban_palsu[3], "H",
                "memilih jaring yang mirip dengan yang benar, tapi sayangnya salah"),
    ]
    return Soal(
        "jaring_jaring",
        {"pilihan_benar": pilihan_benar, "urutan": urutan},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        pembahasan=(
            f"Langkah: jaring-jaring kubus yang sah punya 6 persegi dan "
            f"tidak ada sisi yang bertumpuk saat dilipat. Jawabannya {kunci}."
        ),
        bagian="B",
    )


# ── Bagian C — Kubus dicat & perbandingan volume ────────────────────────


def kubus_dicat(n: int, tanya: str, n_kubus: int = 1) -> Soal:
    """Kubus n×n×n dicat: cari jumlah kubus dengan cat 0/1/2/3 sisi.
    Varian *_kali: n_kubus kubus identik, total = nilai × n_kubus."""
    tiga_sisi = 8
    dua_sisi = 12 * (n - 2)
    satu_sisi = 6 * (n - 2) ** 2
    nol_sisi = (n - 2) ** 3

    if tanya.endswith("_kali"):
        # n_kubus kubus identik, masing-masing dicat
        tanya_asli = tanya.replace("_kali", "")
        if tanya_asli == "tiga_sisi":
            dasar = tiga_sisi
        elif tanya_asli == "dua_sisi":
            dasar = dua_sisi
        elif tanya_asli == "satu_sisi":
            dasar = satu_sisi
        else:
            dasar = nol_sisi
        kunci = str(dasar * n_kubus)
        teks = f"Ada {n_kubus} buah kubus berukuran {n}×{n}×{n}, masing-masing dicat. Berapa total kubus kecil yang memiliki cat pada {tanya_asli.replace('_', ' ')} dari semua kubus?"
        k_salah = str(dasar)  # lupa ×n_kubus
        k_lain = str(dasar * (n_kubus + 1))  # n_kubus+1
        h = str(int(kunci) - 1)
        if k_salah == kunci or k_salah == h:
            k_salah = str(int(kunci) + 1)
        if k_lain == kunci or k_lain == h or k_lain == k_salah:
            k_lain = str(int(kunci) + 2)
        if h == k_salah or h == k_lain:
            h = str(int(kunci) + 1)
        mal = [
            Malrule(f"kubus_dicat.kali_lupa_{tanya_asli}", k_salah, "K",
                    f"menjawab jumlah satu kubus, bukan {n_kubus} kubus"),
            Malrule(f"kubus_dicat.kali_lebih_{tanya_asli}", k_lain, "K",
                    f"menghitung {n_kubus+1} kubus, bukan {n_kubus}"),
            Malrule(f"kubus_dicat.kurang_satu", h, "H",
                    "perhitungan benar, hasilnya meleset satu"),
        ]
        return Soal(
            "kubus_dicat",
            {"n": n, "tanya": tanya, "n_kubus": n_kubus},
            teks,
            kunci,
            saring_malrule(kunci, mal),
        pembahasan=(
            f"Langkah: kubus besar dipotong; yang di POJOK kena cat 3 sisi, "
            f"di RUSUK 2 sisi, di TENGAH sisi 1, di dalam 0. Jawabannya {kunci}."
        ),
            bagian="C",
        )
    else:
        # varian dasar: hitung untuk satu kubus
        if tanya == "tiga_sisi":
            kunci = str(tiga_sisi)
            teks = f"Kubus {n}×{n}×{n} dicat pada semua sisi luar. Jika dipotong menjadi {n}³ kubus kecil, berapa kubus yang memiliki cat pada 3 sisi?"
            k_salah = str(dua_sisi)
            k_lain = str(n)
        elif tanya == "dua_sisi":
            kunci = str(dua_sisi)
            teks = f"Kubus {n}×{n}×{n} dicat pada semua sisi. Berapa kubus kecil yang memiliki cat pada 2 sisi?"
            k_salah = str(12 * n)
            k_lain = str(tiga_sisi)
        elif tanya == "satu_sisi":
            kunci = str(satu_sisi)
            teks = f"Kubus {n}×{n}×{n} dicat. Berapa kubus kecil yang memiliki cat pada 1 sisi?"
            k_salah = str(6 * n ** 2)
            k_lain = str(dua_sisi)
        else:
            kunci = str(nol_sisi)
            teks = f"Kubus {n}×{n}×{n} dicat. Berapa kubus kecil yang TIDAK memiliki cat sama sekali?"
            k_salah = str(n ** 3 - nol_sisi)
            k_lain = str(n ** 3)

    # Jaga K/H tidak bertabrakan
    h = str(int(kunci) - 1)
    if k_salah == kunci or k_salah == h:
        k_salah = str(int(kunci) + 1)
    if k_lain == kunci or k_lain == h or k_lain == k_salah:
        k_lain = str(int(kunci) + 2)
    if h == k_salah or h == k_lain:
        h = str(int(kunci) + 1)

    mal = [
        Malrule(f"kubus_dicat.salah_rumus_{tanya}", k_salah, "K",
                "memakai rumus yang salah untuk posisi kubus yang diminta"),
        Malrule(f"kubus_dicat.rumus_lain_{tanya}", k_lain, "K",
                "menjawab jumlah kubus dengan posisi cat yang berbeda"),
        Malrule(f"kubus_dicat.kurang_satu", h, "H",
                "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "kubus_dicat",
        {"n": n, "tanya": tanya},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        pembahasan=(
            f"Langkah: hitung nilai dasarnya dulu, lalu kalikan sebanyak "
            f"yang diminta soal. Hasilnya {kunci}."
        ),
        bagian="C",
    )


@soal_berversi
def perbandingan_volume(varian: str, k: int, s: int = 0,
                         V: int = 0, V_baru: int = 0) -> Soal:
    """Skala k: V baru = k³ × V lama; dua arah."""
    if varian == "cari_V_baru":
        V_baru = k ** 3 * s
        kunci = str(V_baru)
        teks = f"Kubus dengan panjang rusuk {s} cm. Jika panjang rusuk diperbesar {k} kali, berapa kali lipat volumenya?"
        k_kali = str(k * s)  # lupa pangkat 3
        k_kuadrat = str(k ** 2 * s)  # k² bukan k³
    elif varian == "cari_k":
        kunci = str(k)
        teks = f"Volume kubus diperbesar {V_baru} kali. Berapa kali panjang rusuknya diperbesar?"
        k_kali = str(V_baru // 3)  # V/3
        k_kuadrat = str(int(V_baru ** (1/3)) + 1)  # akar pangkat 3 + 1
    elif varian == "balok_V_baru":
        V_baru = k ** 3 * s
        kunci = str(V_baru)
        teks = f"Balok diperbesar {k} kali pada setiap ukurannya. Volume awal {s} cm³. Berapa volume barunya (cm³)?"
        k_kali = str(k * s)
        k_kuadrat = str(k ** 2 * s)
    else:
        V_baru = k ** 3 * s
        kunci = str(V_baru)
        teks = f"Sebuah bangun ruang diperbesar {k} kali pada setiap dimensinya. Volume awal {s} cm³. Berapa volume barunya (cm³)?"
        k_kali = str(k * s)
        k_kuadrat = str(k ** 2 * s)

    # Jaga malrule tidak bertabrakan
    if k_kuadrat == kunci or k_kuadrat == k_kali:
        k_kuadrat = str(int(kunci) + 1)

    mal = [
        Malrule("perbandingan.kali", k_kali, "K", "hanya mengalikan volume dengan faktor skala — lupa pangkat 3"),
        Malrule("perbandingan.kuadrat", k_kuadrat, "K", "memakai k² bukan k³ — mungkin ingat rumus luas dari geometri datar"),
        Malrule("perbandingan.kurang_satu", str(int(kunci) - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "perbandingan_volume",
        {"varian": varian, "k": k, "s": s, "V": V, "V_baru": V_baru},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: kalau rusuk diperbesar k kali, volumenya jadi "
            f"k x k x k kali. Hasilnya {kunci}."
        ),
        bagian="C",
    )


# ── Registry ─────────────────────────────────────────────────────────────

REGISTRI_TOPIK = {
    "unsur_bangun": unsur_bangun,
    "volume_kubus_balok": volume_kubus_balok,
    "volume_prisma_tabung": volume_prisma_tabung,
    "luas_permukaan": luas_permukaan,
    "jaring_jaring": jaring_jaring,
    "kubus_dicat": kubus_dicat,
    "perbandingan_volume": perbandingan_volume,
}

KOMPOSISI = {
    "P5": (
        "unsur_bangun",
        "volume_kubus_balok",
        "volume_prisma_tabung",
        "luas_permukaan",
        "unsur_bangun",
        "volume_kubus_balok",
        "volume_prisma_tabung",
        "luas_permukaan",
        "unsur_bangun",
        "volume_kubus_balok",
    ),
    "P6": (
        "unsur_bangun",
        "volume_kubus_balok",
        "volume_prisma_tabung",
        "luas_permukaan",
        "jaring_jaring",
        "kubus_dicat",
        "perbandingan_volume",
        "volume_kubus_balok",
        "volume_prisma_tabung",
        "luas_permukaan",
    ),
}

JUDUL_BAGIAN = {
    "A": "Bagian A — Unsur & volume",
    "B": "Bagian B — Luas permukaan & jaring",
    "C": "Bagian C — Kubus dicat & perbandingan volume",
}

CATATAN_BAGIAN = {
    "A": "Volume = luas alas × tinggi. Tabung: πr²t. π = 22/7 untuk r kelipatan 7.",
    "B": "Luas permukaan = jumlah luas semua sisi. Jaring: lipat di kertas.",
    "C": "Kubus n×n×n dicat: 3 sisi=8, 2 sisi=12(n−2), 1 sisi=6(n−2)², 0 sisi=(n−2)³.",
}


@parameter_baru
def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id == "unsur_bangun":
        bangun = rng.choice(("kubus", "balok", "prisma_segitiga", "tabung",
                             "limas_segiempat", "kerucut"))
        if rng.random() < 0.5:
            # varian dasar: 18 combo (6 bangun × 3 tanya)
            tanya = rng.choice(TANYA)
            return {"bangun": bangun, "tanya": tanya}
        # varian *_kali: 18 × rentang n (2..30) → ruang parameter lebar
        tanya = rng.choice(TANYA) + "_kali"
        return {"bangun": bangun, "tanya": tanya, "n": rng.randint(2, 30)}
    if template_id == "volume_kubus_balok":
        varian = rng.choice(("kubus_cari_V", "kubus_cari_s", "balok_cari_V", "balok_cari_p"))
        if varian == "kubus_cari_V":
            s = rng.randint(2, 20)
            return {"varian": varian, "s": s}
        if varian == "kubus_cari_s":
            s = rng.randint(2, 12)
            V = s * s * s
            return {"varian": varian, "s": s, "V": V}
        if varian == "balok_cari_V":
            p, l, t = rng.randint(2, 20), rng.randint(2, 20), rng.randint(2, 20)
            return {"varian": varian, "p": p, "l": l, "t": t}
        # balok_cari_p
        p, l, t = rng.randint(2, 20), rng.randint(2, 20), rng.randint(2, 20)
        V = p * l * t
        return {"varian": varian, "p": p, "l": l, "t": t, "V": V}
    if template_id == "volume_prisma_tabung":
        varian = rng.choice(("prisma_V", "tabung_V", "prisma_balik", "tabung_balik"))
        if varian == "prisma_V":
            a = rng.choice([x for x in range(4, 41, 2)])  # genap supaya ½ bulat
            t_segitiga = rng.randint(2, 20)
            t_prisma = rng.randint(2, 20)
            return {"varian": varian, "a": a, "t_segitiga": t_segitiga, "t_prisma": t_prisma}
        if varian == "tabung_V":
            # r kelipatan 7 → 22/7, selain itu 3.14
            r = rng.choice([x for x in range(2, 29) if x % 7 == 0] + [x for x in range(2, 29) if x % 7 != 0])
            t = rng.randint(2, 20)
            pi = 22 / 7 if r % 7 == 0 else 3.14
            V = int(pi * r * r * t)
            if V == 0:
                V = 1
            return {"varian": varian, "r": r, "t": t, "V": V}
        if varian == "prisma_balik":
            a = rng.choice([x for x in range(4, 41, 2)])
            t_segitiga = rng.randint(2, 20)
            t_prisma = rng.randint(2, 20)
            V = (a * t_segitiga // 2) * t_prisma
            return {"varian": varian, "a": a, "t_segitiga": t_segitiga, "t_prisma": t_prisma, "V": V}
        # tabung_balik
        r = rng.choice([x for x in range(2, 29) if x % 7 == 0] + [x for x in range(2, 29) if x % 7 != 0])
        t = rng.randint(2, 20)
        pi = 22 / 7 if r % 7 == 0 else 3.14
        V = int(pi * r * r * t)
        if V == 0:
            V = 1
        return {"varian": varian, "r": r, "t": t, "V": V}
    if template_id == "luas_permukaan":
        varian = rng.choice(("kubus_LP", "kubus_cari_s", "balok_LP", "balok_cari_p", "tabung_LP", "tabung_cari_t"))
        if varian == "kubus_LP":
            s = rng.randint(2, 20)
            return {"varian": varian, "s": s}
        if varian == "kubus_cari_s":
            s = rng.randint(2, 12)
            LP = 6 * s * s
            return {"varian": varian, "s": s, "LP": LP}
        if varian == "balok_LP":
            p, l, t = rng.randint(2, 20), rng.randint(2, 20), rng.randint(2, 20)
            return {"varian": varian, "p": p, "l": l, "t": t}
        if varian == "balok_cari_p":
            p, l, t = rng.randint(2, 20), rng.randint(2, 20), rng.randint(2, 20)
            LP = 2 * (p * l + p * t + l * t)
            return {"varian": varian, "p": p, "l": l, "t": t, "LP": LP}
        if varian == "tabung_LP":
            r = rng.choice([x for x in range(2, 29) if x % 7 == 0] + [x for x in range(2, 29) if x % 7 != 0])
            t = rng.randint(2, 20)
            return {"varian": varian, "r": r, "t": t}
        # tabung_cari_t
        r = rng.choice([x for x in range(2, 29) if x % 7 == 0])
        t = rng.randint(2, 20)
        pi = 22 / 7
        LP = int(2 * pi * r * r + 2 * pi * r * t)
        return {"varian": varian, "r": r, "t": t, "LP": LP}
    if template_id == "jaring_jaring":
        # Pilih 1 jaring benar + 4 jaring palsu, lalu acak posisinya
        benar = rng.randint(0, len(JARING_KUBUS) - 1)
        pilihan_benar = rng.randint(0, 4)
        # Pilih 4 jaring palsu (tanpa duplikat dengan jaring benar)
        palsu = [i for i in range(len(JARING_PALSU))]
        rng.shuffle(palsu)
        urutan = [benar] + palsu[:4]
        return {"pilihan_benar": pilihan_benar, "urutan": urutan}
    if template_id == "kubus_dicat":
        n = rng.randint(3, 10)
        if rng.random() < 0.5:
            tanya = rng.choice(("tiga_sisi", "dua_sisi", "satu_sisi", "nol_sisi"))
            return {"n": n, "tanya": tanya}
        # varian *_kali: 32 × n_kubus (2..15) → ruang parameter lebar
        tanya = rng.choice(("tiga_sisi", "dua_sisi", "satu_sisi", "nol_sisi")) + "_kali"
        return {"n": n, "tanya": tanya, "n_kubus": rng.randint(2, 15)}
    if template_id == "perbandingan_volume":
        varian = rng.choice(("cari_V_baru", "cari_k", "balok_V_baru"))
        k = rng.choice((2, 3, 4, 5))
        s = rng.randint(1, 30)
        V_baru = k ** 3 * s
        return {"varian": varian, "k": k, "s": s, "V": s, "V_baru": V_baru}
    raise KeyError(f"template tidak dikenal: {template_id}")


TOPIK = Topik(
    id="geometri-ruang",
    nama="Geometri Ruang",
    judul_lembar="Latihan Geometri Ruang",
    judul_penilaian="Penilaian — Geometri Ruang",
    templates=REGISTRI_TOPIK,
    komposisi=KOMPOSISI,
    profil={"P5": {}, "P6": {}},
    judul_bagian=JUDUL_BAGIAN,
    catatan_bagian=CATATAN_BAGIAN,
    parameter_untuk=_parameter,
)

daftarkan(TOPIK)