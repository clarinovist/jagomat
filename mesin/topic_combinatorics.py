"""Paket topik kombinatorik — Fase 2 plan 30 Aug 2026.

11 template menutup cakupan kombinatorik OSN SD: aturan mencacah (bagian A),
susunan angka (B), permutasi & kombinasi (C), penerapan (D). Level P5/P6
(P3/P4 tidak didukung). Soal berbentuk teks dulu (keputusan pengguna #2);
diagram pohon/petak/Venn adalah penyempurnaan `render_badan` belakangan.
"""

from __future__ import annotations

import math
import random

from templates import Malrule, Soal, putar, saring_malrule
from topics import Topik, daftarkan


# ── Latar cerita berputar (2 Sep 2026) ─────────────────────────────────
#
# Empat template P5 (aturan_tambah, aturan_kali, jabat_tangan,
# inklusi_eksklusi_2) dulu punya SATU cerita yang ditulis mati di dalam
# f-string: roti & selai, buku cerita, pertemuan, matematika & IPA.
# Terukur 2 Sep 2026: 3000 soal kombinatorik P5 hanya melahirkan 14
# bentuk kalimat, dan empat template itu menyumbang 1 bentuk masing-masing.
#
# Latar dipilih dari PARAMETER soal, bukan dari rng: parameter sudah
# deterministik per seed, jadi lembar yang sama tetap melahirkan kalimat
# yang sama (kontrak generator.py) TANPA menambah parameter baru —
# penting karena parameter ikut tanda_tangan, dan menambahnya akan
# membatalkan seluruh bank soal serta snapshot golden.
#
# Helpernya sendiri pindah ke templates.putar (gelombang 2, 2 Sep 2026)
# karena modul topik lain memakainya juga; kontrak lengkapnya ada di
# docstring fungsi itu.

# ── Bagian A — Aturan mencacah ─────────────────────────────────────────


def aturan_tambah(m: int, n: int) -> Soal:
    """Aturan penjumlahan: m + n cara (mutually exclusive)."""
    kunci = m + n
    mal = [
        Malrule(
            "aturan_tambah.dikira_kali",
            str(m * n),
            "K",
            "mengalikan m dan n padahal aturan penjumlahan (pilihan saling lepas)",
        ),
        Malrule(
            "aturan_tambah.hanya_satu",
            str(m),
            "B",
            "hanya menghitung pilihan A, pilihan B tidak dijumlahkan",
        ),
        Malrule(
            "aturan_tambah.kurang_satu",
            str(kunci - 1),
            "H",
            "penjumlahan benar, hasilnya meleset satu",
        ),
    ]
    tempat, jenis1, jenis2, benda, tokoh = putar(
        (
            ("toko buku", "buku cerita", "buku pelajaran", "buku", "Budi"),
            ("kantin sekolah", "roti isi", "kue basah", "jajanan", "Sinta"),
            ("warung sayur", "ikat bayam", "ikat kangkung", "sayur", "Ibu"),
            ("toko olahraga", "bola plastik", "bola karet", "bola", "Rian"),
            ("perpustakaan", "majalah anak", "komik", "bacaan", "Dika"),
        ),
        m,
        n,
    )
    teks = (
        f"Di {tempat}, ada {m} {jenis1} dan {n} {jenis2}. "
        f"{tokoh} ingin membeli satu {benda}. Berapa banyak pilihan {benda} "
        f"yang dimiliki {tokoh}?"
    )
    return Soal(
        "aturan_tambah",
        {"m": m, "n": n},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: memilih SATU dari kelompok ini ATAU itu -> DITAMBAH. "
            f"Hasilnya {kunci}."
        ),
        bagian="A",
    )


def aturan_kali(m: int, n: int) -> Soal:
    """Aturan perkalian: m × n cara (pilihan berurutan)."""
    kunci = m * n
    mal = [
        Malrule(
            "aturan_kali.dikira_tambah",
            str(m + n),
            "K",
            "menjumlahkan m dan n padahal aturan perkalian (pilihan berurutan)",
        ),
        Malrule(
            "aturan_kali.hanya_kedua",
            str(n),
            "B",
            "hanya menghitung pilihan kedua, pilihan pertama tidak diperhitungkan",
        ),
        Malrule(
            "aturan_kali.kurang_satu",
            str(kunci - 1),
            "H",
            "perkalian benar, hasilnya meleset satu",
        ),
    ]
    tempat, jenis1, jenis2, tujuan, hasil, tokoh = putar(
        (
            ("toko", "jenis roti", "jenis selai", "sarapan", "menu", "Budi"),
            ("lemari", "kaus", "celana", "dipakai ke sekolah", "setelan", "Rani"),
            ("kantin", "jenis nasi", "jenis lauk", "makan siang", "porsi", "Aldi"),
            ("toko es", "rasa es krim", "jenis wadah", "dibeli", "pesanan", "Nina"),
            ("rak", "warna sampul", "jenis stiker", "menghias buku", "hiasan", "Tio"),
        ),
        m,
        n,
    )
    teks = (
        f"Di {tempat}, ada {m} {jenis1} dan {n} {jenis2}. "
        f"{tokoh} ingin memilih satu {jenis1} dan satu {jenis2} "
        f"untuk {tujuan}. "
        f"Berapa banyak pilihan {hasil} yang dimiliki {tokoh}?"
    )
    return Soal(
        "aturan_kali",
        {"m": m, "n": n},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: memilih satu ini DAN satu itu -> DIKALI. "
            f"Hasilnya {kunci}."
        ),
        bagian="A",
    )


def _angka_ke_bil(angka: tuple[int, ...]) -> int:
    return int("".join(str(d) for d in angka))


def _nama_objek(rng: random.Random, n: int) -> list[str]:
    """n nama acak dari himpunan {A..V} untuk variasi guard 200."""
    huruf = [chr(ord("A") + i) for i in range(22)]
    return sorted(rng.sample(huruf, n))


# Semua pasangan (b, k) dengan 1 <= b,k <= 24 dan b+k <= 25 → 300 sel.
# Dibangun sekali, dipilih rng.choice uniform supaya tiap sel kesempatan
# sama (randint terpisah bias ke sel dengan baris kecil).
_JALUR_PETAK: list[dict[str, int]] = [
    {"b": b, "k": k}
    for b in range(1, 25)
    for k in range(1, 26 - b)
]


def _enumerasi_bilangan(
    angka: tuple[int, ...], panjang: int, syarat
) -> int:
    """Brute force: banyak bilangan `panjang` digit dari angka berbeda."""
    from itertools import permutations

    hasil = 0
    for urutan in permutations(angka, panjang):
        if urutan[0] == 0:
            continue
        if syarat(urutan):
            hasil += 1
    return hasil


# ── Bagian B — Susunan angka ───────────────────────────────────────────


def susun_bilangan(varian: str, angka: tuple[int, ...]) -> Soal:
    """Susun n angka jadi bilangan n-digit, 0 tidak boleh di depan.

    Varian: "dengan_nol" (0 ada di angka) → (n-1)·(n-1)! cara.
    Varian: "tanpa_nol" (tidak ada 0) → n! cara.
    """
    n = len(angka)
    if varian == "dengan_nol":
        kunci = (n - 1) * math.factorial(n - 1)
        mal = [
            Malrule(
                "susun.nol_boleh_depan",
                str(math.factorial(n)),
                "K",
                "0 ditempatkan di depan — padahal 0 tidak boleh menjadi digit pertama",
            ),
            Malrule(
                "susun.lupa_digit",
                str(math.factorial(n - 1)),
                "K",
                "hanya menyusun n−1 angka, lupa satu digit ikut",
            ),
            Malrule(
                "susun.kurang_satu",
                str(kunci - 1),
                "H",
                "penyusunan benar, perhitungannya meleset satu",
            ),
        ]
        teks = (
            f"Angka {', '.join(str(d) for d in angka[:-1])} "
            f"dan {angka[-1]} akan disusun menjadi bilangan "
            f"{n} digit yang berbeda. 0 tidak boleh menjadi digit "
            f"pertama. Berapa banyak bilangan yang dapat dibuat?"
        )
    else:
        kunci = math.factorial(n)
        mal = [
            Malrule(
                "susun.nol_boleh_depan",
                str(n**n),
                "K",
                "angka boleh diulang padahal harus berbeda setiap digit",
            ),
            Malrule(
                "susun.lupa_digit",
                str(math.factorial(n - 1)),
                "K",
                "hanya menyusun n−1 angka, satu digit dilupakan",
            ),
            Malrule(
                "susun.kurang_satu",
                str(kunci - 1),
                "H",
                "penyusunan benar, perhitungannya meleset satu",
            ),
        ]
        teks = (
            f"Angka {', '.join(str(d) for d in angka[:-1])} "
            f"dan {angka[-1]} akan disusun menjadi bilangan "
            f"{n} digit yang berbeda (angka tidak boleh berulang). "
            f"Berapa banyak bilangan yang dapat dibuat?"
        )
    return Soal(
        "susun_bilangan",
        {"varian": varian, "angka": list(angka)},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: hitung pilihan tiap digit lalu kalikan. Kalau digit "
            f"depan tidak boleh 0, pilihannya berkurang satu. Hasilnya {kunci}."
        ),
        bagian="B",
    )


def susun_bilangan_syarat(varian: str, angka: tuple[int, ...], N: int | None = None) -> Soal:
    """Susun n digit → bilangan genap atau > N.

    Varian "genap": digit terakhir harus genap (angka dari 1..9, tanpa 0).
    Varian "lebih_dari": bilangan yang terbentuk > N.
    Kedua varian diverifikasi brute force di test (sumber kebenaran).
    """
    n = len(angka)
    kunci = _enumerasi_bilangan(
        angka,
        n,
        (lambda u: u[-1] % 2 == 0) if varian == "genap"
        else (lambda u: _angka_ke_bil(u) > N),
    )
    if varian == "genap":
        ganjil = [d for d in angka if d % 2 == 1]
        mal = [
            Malrule(
                "susun_syarat.abaikan_syarat",
                str(math.factorial(n)),
                "K",
                "menghitung semua kemungkinan tanpa syarat digit terakhir genap",
            ),
            Malrule(
                "susun_syarat.syarat_terbalik",
                str(len(ganjil) * math.factorial(n - 1)),
                "K",
                "memakai digit ganjil di akhir, padahal harus genap",
            ),
            Malrule(
                "susun_syarat.kurang_satu",
                str(kunci - 1),
                "H",
                "perhitungan benar, hasilnya meleset satu",
            ),
        ]
        teks = (
            f"Angka {', '.join(str(d) for d in angka[:-1])} "
            f"dan {angka[-1]} akan disusun menjadi bilangan "
            f"{n} digit yang berbeda dan genap. "
            f"Berapa banyak bilangan yang dapat dibuat?"
        )
    else:
        mal = [
            Malrule(
                "susun_syarat.abaikan_syarat",
                str(math.factorial(n)),
                "K",
                f"menghitung semua kemungkinan tanpa syarat > {N}",
            ),
            Malrule(
                "susun_syarat.syarat_terbalik",
                str(_enumerasi_bilangan(
                    angka, n, lambda u: _angka_ke_bil(u) <= N
                )),
                "K",
                f"menghitung bilangan yang ≤ {N}, bukan yang > {N}",
            ),
            Malrule(
                "susun_syarat.kurang_satu",
                str(kunci - 1),
                "H",
                "perhitungan benar, hasilnya meleset satu",
            ),
        ]
        teks = (
            f"Angka {', '.join(str(d) for d in angka[:-1])} "
            f"dan {angka[-1]} akan disusun menjadi bilangan "
            f"{n} digit yang berbeda dan lebih besar dari {N}. "
            f"Berapa banyak bilangan yang dapat dibuat?"
        )
    return Soal(
        "susun_bilangan_syarat",
        {"varian": varian, "angka": list(angka), "N": N} if varian == "lebih_dari"
        else {"varian": varian, "angka": list(angka)},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: penuhi syaratnya dulu (digit terakhir/awal), "
            f"baru hitung sisa digitnya lalu kalikan. Hasilnya {kunci}."
        ),
        bagian="B",
    )


# ── Bagian C — Permutasi & kombinasi ───────────────────────────────────


def permutasi_urutan(n: int, r: int, objek: list[str]) -> Soal:
    """P(n,r) = n!/(n−r)!. objek adalah daftar n benda berbeda."""
    kunci = math.perm(n, r)
    mal = [
        Malrule(
            "permutasi.tertukar_kombinasi",
            str(math.comb(n, r)),
            "K",
            f"menghitung kombinasi C({n},{r}) padahal urutan penting (permutasi)",
        ),
        Malrule(
            "permutasi.boleh_ulang",
            str(n**r),
            "K",
            f"benda boleh dipakai berulang — padahal tiap benda hanya sekali",
        ),
        Malrule(
            "permutasi.kurang_satu",
            str(kunci - 1),
            "H",
            "perhitungan permutasi benar, hasilnya meleset satu",
        ),
    ]
    teks = (
        f"Dari {', '.join(objek[:-1])} dan {objek[-1]} "
        f"({n} orang berbeda), akan dipilih {r} orang untuk menempati "
        f"posisi pertama, kedua, dan seterusnya secara berurutan. "
        f"Berapa banyak cara susunan yang mungkin?"
    )
    return Soal(
        "permutasi_urutan",
        {"n": n, "r": r, "objek": objek},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: URUTAN penting, jadi pakai permutasi: "
            f"kalikan pilihan yang tersisa tiap posisi. Hasilnya {kunci}."
        ),
        bagian="C",
    )


def permutasi_blok(n: int, k: int, objek: list[str]) -> Soal:
    """n benda, k harus berdampingan → (n−k+1)!·k!.

    objek adalah daftar n benda berbeda; k benda pertama disebut
    sebagai benda yang harus berdampingan.
    """
    kunci = math.factorial(n - k + 1) * math.factorial(k)
    mal = [
        Malrule(
            "blok.abaikan_isi_blok",
            str(math.factorial(n - k + 1)),
            "K",
            f"{k} benda dalam blok dianggap tidak bisa diubah urutannya",
        ),
        Malrule(
            "blok.hanya_isi_blok",
            str(math.factorial(k)),
            "K",
            "hanya menghitung urutan dalam blok, lupa bloknya ikut disusun",
        ),
        Malrule(
            "blok.kurang_satu",
            str(kunci - 1),
            "H",
            "perhitungan blok benar, hasilnya meleset satu",
        ),
    ]
    teks = (
        f"Ada {n} buku berbeda ({', '.join(objek[:-1])} "
        f"dan {objek[-1]}) akan disusun berjajar di rak. "
        f"{' dan '.join(objek[:k])} harus berdampingan. "
        f"Berapa banyak cara susunan yang mungkin?"
    )
    return Soal(
        "permutasi_blok",
        {"n": n, "k": k, "objek": objek},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: yang harus berdampingan dianggap SATU blok dulu, "
            f"lalu kalikan dengan susunan di dalam blok. Hasilnya {kunci}."
        ),
        bagian="C",
    )


def kombinasi_pilih(n: int, r: int, objek: list[str]) -> Soal:
    """C(n,r) = n!/(r!(n−r)!). objek = n benda berbeda."""
    kunci = math.comb(n, r)
    mal = [
        Malrule(
            "kombinasi.tertukar_permutasi",
            str(math.perm(n, r)),
            "K",
            f"menghitung permutasi P({n},{r}) padahal urutan tidak penting",
        ),
        Malrule(
            "kombinasi.dikira_2_pangkat",
            str(2**n),
            "K",
            f"menghitung 2^{n} (semua himpunan bagian) padahal hanya pilih {r}",
        ),
        Malrule(
            "kombinasi.kurang_satu",
            str(kunci - 1),
            "H",
            "perhitungan kombinasi benar, hasilnya meleset satu",
        ),
    ]
    teks = (
        f"Dari {', '.join(objek[:-1])} dan {objek[-1]} "
        f"({n} orang berbeda), akan dipilih {r} orang untuk menjadi "
        f"anggota tim (urutan tidak penting). "
        f"Berapa banyak cara memilih tim?"
    )
    return Soal(
        "kombinasi_pilih",
        {"n": n, "r": r, "objek": objek},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: urutan TIDAK penting, jadi kombinasi: "
            f"permutasi dibagi banyaknya susunan yang sama. Hasilnya {kunci}."
        ),
        bagian="C",
    )


# ── Bagian D — Penerapan ───────────────────────────────────────────────


def jabat_tangan(n: int) -> Soal:
    """n orang jabat tangan → n(n−1)/2."""
    kunci = n * (n - 1) // 2
    mal = [
        Malrule(
            "jabat.lupa_bagi_2",
            str(n * (n - 1)),
            "K",
            f"{n} x {n - 1} tanpa dibagi dua — lupa tiap jabat tangan dihitung dua orang",
        ),
        Malrule(
            "jabat.jabat_diri",
            str(n),
            "K",
            "menjawab n (setiap orang jabat tangannya sendiri)",
        ),
        Malrule(
            "jabat.kurang_satu",
            str(kunci - 1),
            "H",
            "perhitungan benar, hasilnya meleset satu",
        ),
    ]
    acara = putar(
        (
            "sebuah pertemuan",
            "acara arisan",
            "rapat panitia lomba",
            "reuni keluarga",
            "pembukaan kelas baru",
        ),
        n,
    )
    teks = (
        f"Dalam {acara}, ada {n} orang. Setiap orang berjabat "
        f"tangan satu kali dengan setiap orang lainnya. "
        f"Berapa banyak jabat tangan yang terjadi?"
    )
    return Soal(
        "jabat_tangan",
        {"n": n},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: tiap dua orang berjabat sekali = n x (n-1) : 2. "
            f"Hasilnya {kunci}."
        ),
        bagian="D",
    )


def jalur_petak(b: int, k: int) -> Soal:
    """Petak b×k → C(b+k, b) jalur terpendek (kanan/bawah)."""
    kunci = math.comb(b + k, b)
    mal = [
        Malrule(
            "jalur.dua_arah",
            str(2 * math.comb(b + k, b)),
            "K",
            "mengalikan dua — arah yang benar hanya kanan dan bawah, bukan kiri/atas",
        ),
        Malrule(
            "jalur.jumlah_step",
            str(b + k),
            "K",
            "menjumlahkan langkah kanan dan bawah, bukan menghitung kombinasinya",
        ),
        Malrule(
            "jalur.kurang_satu",
            str(kunci - 1),
            "H",
            "perhitungan kombinasi benar, hasilnya meleset satu",
        ),
    ]
    teks = (
        f"Kota A ke Kota B melewati petak {b}×{k} di mana hanya bisa "
        f"ke kanan atau ke bawah. Berapa banyak jalur terpendek yang "
        f"mungkin?"
    )
    return Soal(
        "jalur_petak",
        {"b": b, "k": k},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: tulis angka di tiap titik = jumlah angka dari kiri "
            f"dan dari atas; angka di pojok tujuan = {kunci}."
        ),
        bagian="D",
    )


def sarang_merpati(n: int, m: int) -> Soal:
    """n benda ke m laci → minimal ceil(n/m) sama."""
    kunci = (n + m - 1) // m
    # Urutan penting: H dulu. n−m (K) kadang menyamai kunci+1 (H); kalau H
    # muncul belakangan, saring_malrule membuangnya dan soal kehilangan
    # jalur H. Dengan H dulu, yang terbuang hanya K n−m — floor (K) tetap.
    mal = [
        Malrule(
            "merpati.kelebihan_satu",
            str(kunci + 1),
            "H",
            "pembulatan benar, hasilnya kelebihan satu",
        ),
        Malrule(
            "merpati.dibulatkan_bawah",
            str(n // m),
            "K",
            f"{n} benda ke {m} laci — dibulatkan ke bawah, padahal harus ke atas",
        ),
        Malrule(
            "merpati.dikira_selisih",
            str(n - m),
            "K",
            f"menghitung selisih {n}−{m}, padahal yang diminta pembagian",
        ),
    ]
    teks = (
        f"Ada {n} merpati dan {m} sangkar. Berapa jumlah merpati "
        f"terbanyak yang pasti ada di satu sangkar yang sama?"
    )
    return Soal(
        "sarang_merpati",
        {"n": n, "m": m},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: bagi rata dulu, sisanya dibagikan satu-satu. "
            f"Yang terbanyak pasti = {kunci}."
        ),
        bagian="D",
    )


def inklusi_eksklusi_2(a: int, b: int, c: int) -> Soal:
    """|A∪B| = a + b − c."""
    kunci = a + b - c
    mal = [
        Malrule(
            "inklusi.lupa_irisan",
            str(a + b),
            "K",
            f"menjumlah |A|={a} dan |B|={b} tanpa mengurangi irisan",
        ),
        Malrule(
            "inklusi.dikali",
            str(a * b),
            "K",
            f"mengalikan |A|×|B|={a}×{b} padahal aturan jumlah−irisan",
        ),
        Malrule(
            "inklusi.kurang_satu",
            str(kunci - 1),
            "H",
            "perhitungan jumlah−irisan benar, hasilnya meleset satu",
        ),
    ]
    kelompok, hal1, hal2 = putar(
        (
            ("siswa", "matematika", "IPA"),
            ("anak", "sepak bola", "renang"),
            ("warga", "membaca koran", "mendengar radio"),
            ("murid", "paduan suara", "pramuka"),
            ("peserta", "lomba gambar", "lomba puisi"),
        ),
        a,
        b,
        c,
    )
    teks = (
        f"Ada {a} {kelompok} yang suka {hal1} dan {b} {kelompok} yang suka "
        f"{hal2}, serta {c} {kelompok} suka keduanya. Berapa banyak "
        f"{kelompok} yang suka {hal1} atau {hal2} (atau keduanya)?"
    )
    return Soal(
        "inklusi_eksklusi_2",
        {"a": a, "b": b, "c": c},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: yang suka setidaknya satu = A + B - keduanya. "
            f"Hasilnya {kunci}."
        ),
        bagian="D",
    )


REGISTRI_TOPIK = {
    "aturan_tambah": aturan_tambah,
    "aturan_kali": aturan_kali,
    "susun_bilangan": susun_bilangan,
    "susun_bilangan_syarat": susun_bilangan_syarat,
    "permutasi_urutan": permutasi_urutan,
    "permutasi_blok": permutasi_blok,
    "kombinasi_pilih": kombinasi_pilih,
    "jabat_tangan": jabat_tangan,
    "jalur_petak": jalur_petak,
    "sarang_merpati": sarang_merpati,
    "inklusi_eksklusi_2": inklusi_eksklusi_2,
}

KOMPOSISI = {
    # P5 (10 soal): 1, 2, 3, 4, 8, 11, 2, 3, 8, 11
    "P5": (
        "aturan_tambah",
        "aturan_kali",
        "susun_bilangan",
        "susun_bilangan_syarat",
        "jabat_tangan",
        "inklusi_eksklusi_2",
        "aturan_kali",
        "susun_bilangan",
        "jabat_tangan",
        "inklusi_eksklusi_2",
    ),
    # P6 (10 soal): 5, 6, 7, 9, 10, 4, 11, 5, 7, 9
    "P6": (
        "permutasi_urutan",
        "permutasi_blok",
        "kombinasi_pilih",
        "jalur_petak",
        "sarang_merpati",
        "susun_bilangan_syarat",
        "inklusi_eksklusi_2",
        "permutasi_urutan",
        "kombinasi_pilih",
        "jalur_petak",
    ),
}

JUDUL_BAGIAN = {
    "A": "Bagian A — Aturan mencacah",
    "B": "Bagian B — Susunan angka",
    "C": "Bagian C — Permutasi & kombinasi",
    "D": "Bagian D — Penerapan",
}

CATATAN_BAGIAN = {
    "A": "Baca dulu: pilihan saling lepas (tambah) atau berurutan (kali)?",
    "B": "0 tidak boleh di depan, kecuali di susunan khusus.",
    "C": "Urutan penting (permutasi) atau tidak (kombinasi)?",
    "D": "Rumusnya sering beda dari yang kelihatan.",
}


def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id == "aturan_tambah":
        m, n = rng.randint(2, 30), rng.randint(2, 30)
        while m == n:
            n = rng.randint(2, 30)
        return {"m": m, "n": n}
    if template_id == "aturan_kali":
        m, n = rng.randint(2, 20), rng.randint(2, 20)
        while m == n:
            n = rng.randint(2, 20)
        return {"m": m, "n": n}
    if template_id == "susun_bilangan":
        # Pilih n digit acak dari 0..9, pastikan 0 ikut (dengan_nol) atau
        # tidak (tanpa_nol). Parameter terdefinisi oleh digit set — unik.
        n = rng.choice((3, 4, 5))
        if rng.random() < 0.5:
            # dengan_nol: 0 harus ada, sisanya dari 1..9
            lainnya = rng.sample(range(1, 10), n - 1)
            angka = tuple(sorted(lainnya + [0]))
            return {"varian": "dengan_nol", "angka": list(angka)}
        # tanpa_nol: semua dari 1..9
        angka = tuple(sorted(rng.sample(range(1, 10), n)))
        return {"varian": "tanpa_nol", "angka": list(angka)}
    if template_id == "susun_bilangan_syarat":
        # Digit dari 1..9 (tanpa 0, menghindari leading-zero kerumitan)
        # Pastikan ada genap untuk varian genap.
        n = rng.choice((3, 4))
        if rng.random() < 0.5:
            # genap: pastikan minimal 1 digit genap
            genap_pool = (2, 4, 6, 8)
            ganjil_pool = (1, 3, 5, 7, 9)
            n_genap = rng.randint(1, min(n - 1, len(genap_pool)))
            n_ganjil = n - n_genap
            genap = rng.sample(genap_pool, n_genap)
            ganjil = rng.sample(ganjil_pool, n_ganjil)
            angka = tuple(sorted(genap + ganjil))
            return {"varian": "genap", "angka": list(angka)}
        # lebih_dari: digit acak, N = 10^(n-1) * X (pembulatan)
        # Pastikan ada digit > X dan ada digit ≤ X.
        digit = rng.sample(range(1, 10), n)
        # Ambil digit pertama (paling signifikan) sebagai threshold
        # N = d * 10^(n-1). Pastikan ada digit > d dan ≤ d.
        for _ in range(10):
            d = rng.choice(digit)
            if any(x > d for x in digit) and any(x <= d for x in digit):
                break
        N = d * 10 ** (n - 1)
        return {"varian": "lebih_dari", "angka": list(digit), "N": N}
    if template_id == "permutasi_urutan":
        # n orang dengan nama acak (variasi ruang untuk guard 200),
        # r dipilih supaya P(n,r) beda dari C dan 2^n.
        n = rng.randint(4, 10)
        r = rng.randint(2, min(5, n - 1))
        nama = _nama_objek(rng, n)
        return {"n": n, "r": r, "objek": nama}
    if template_id == "permutasi_blok":
        # n buku, k (2..3) harus berdampingan; nama acak untuk variasi.
        n = rng.randint(4, 8)
        k = rng.randint(2, min(3, n - 1))
        nama = _nama_objek(rng, n)
        return {"n": n, "k": k, "objek": nama}
    if template_id == "kombinasi_pilih":
        n = rng.randint(4, 12)
        r = rng.randint(2, min(5, n - 1))
        nama = _nama_objek(rng, n)
        return {"n": n, "r": r, "objek": nama}
    if template_id == "jabat_tangan":
        return {"n": rng.randint(4, 250)}
    if template_id == "jalur_petak":
        # Grid 1..24, baris+kolom <= 25 → 300 sel, sampling UNIFORM
        # (bukan randint terpisah yang bias ke sel kecil). Maksimum
        # C(24,12)=2.704.156 — angka besar tapi terbayang di P6, dan
        # plan menuntut >= 200 kombinasi (kendala hasil kecil tidak
        # kompatibel dengan guard, lihat catatan Task 2.4).
        return dict(rng.choice(_JALUR_PETAK))
    if template_id == "sarang_merpati":
        # n > m, n % m != 0 (supaya ceil != floor)
        m = rng.randint(2, 10)
        n = rng.randint(m + 1, 100)
        while n % m == 0:
            n = rng.randint(m + 1, 100)
        return {"n": n, "m": m}
    if template_id == "inklusi_eksklusi_2":
        a, b = rng.randint(3, 40), rng.randint(3, 40)
        while a == b:
            b = rng.randint(3, 40)
        c = rng.randint(1, min(a, b) - 1)
        return {"a": a, "b": b, "c": c}
    raise KeyError(f"template tidak dikenal: {template_id}")


TOPIK = Topik(
    id="kombinatorik",
    nama="Kombinatorik",
    judul_lembar="Latihan Kombinatorik",
    judul_penilaian="Penilaian — Kombinatorik",
    templates=REGISTRI_TOPIK,
    komposisi=KOMPOSISI,
    profil={"P5": {}, "P6": {}},
    judul_bagian=JUDUL_BAGIAN,
    catatan_bagian=CATATAN_BAGIAN,
    parameter_untuk=_parameter,
)

daftarkan(TOPIK)