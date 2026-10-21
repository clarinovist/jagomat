"""Paket topik aritmetika dasar — Fase B, terbatas untuk P5/P6.

Tiga template awal diambil dari malrule yang sudah diprototipekan di
arsip lokal ~/Documents/osn-resources/referensi/spike/malrule.yaml. Python tetap menghitung parameter, kunci, dan malrule;
ini bukan soal yang ditulis LLM.
"""

from __future__ import annotations

import math
import random
import re
from fractions import Fraction

from templates import Malrule, Soal, saring_malrule
from topics import Topik, daftarkan
from assessment_revision import soal_berrevisi
from catalog_versions import koreksi_soal, parameter_baru
from catalog_malrules import fpb


def _teks_pecahan(nilai: Fraction) -> str:
    return f"{nilai.numerator}/{nilai.denominator}"


def _kandidat_pecahan(penyebut: tuple[int, ...]) -> list[dict[str, int]]:
    """Semua (n,d) yang menghasilkan soal pecahan dengan diagnosis sehat.

    Syarat yang disaring di sini — hasil positif, hasil tidak bilangan
    bulat, dan keempat jawaban (kunci + 3 malrule) saling berbeda —
    menjaga `saring_malrule` tidak membuang satu jalur pun. Kalau sebuah
    kombinasi parameter membuat K atau H bertabrakan dengan kunci, soal
    yang dihasilkan kehilangan jalur diagnosis tanpa terlihat dari kode.

    Konteks plan 30 Aug 2026 (Fase 0 Task 0.2): versi lama memilih dari 2
    kombinasi hardcoded per level sehingga dua anak beda seed bisa dapat
    soal identik. Sekarang rentangnya lebar dan divalidasi otomatis.
    """
    kandidat: list[dict[str, int]] = []
    for d1 in penyebut:
        for d2 in penyebut:
            for d3 in penyebut:
                if d1 + d2 == d3:
                    continue  # penyebut malrule "terpisah" jadi nol
                for n1 in range(1, d1):
                    for n2 in range(1, d2):
                        for n3 in range(1, d3):
                            pertama = Fraction(n1, d1)
                            kedua = Fraction(n2, d2)
                            ketiga = Fraction(n3, d3)
                            hasil = pertama + kedua - ketiga
                            if hasil <= 0 or hasil.denominator == 1:
                                continue  # hasil harus positif dan pecahan
                            terpisah = Fraction(n1 + n2 - n3, d1 + d2 - d3)
                            satu_unit = Fraction(1, math.lcm(d1, d2, d3))
                            salah_hitung = hasil - satu_unit
                            pertama_kedua = pertama + kedua
                            jawaban = {
                                _teks_pecahan(hasil),
                                _teks_pecahan(terpisah),
                                _teks_pecahan(salah_hitung),
                                _teks_pecahan(pertama_kedua),
                            }
                            if len(jawaban) < 4:
                                continue  # tabrakan — saring_malrule akan buang
                            if (
                                terpisah.denominator == 1
                                or salah_hitung.denominator == 1
                            ):
                                continue  # anak menulis bilangan bulat, bukan pecahan
                            kandidat.append(
                                {
                                    "n1": n1,
                                    "d1": d1,
                                    "n2": n2,
                                    "d2": d2,
                                    "n3": n3,
                                    "d3": d3,
                                }
                            )
    return kandidat


# Dibangun sekali saat impor, lalu dipilih rng per soal. List tetap
# deterministik (bukan hasil rng), jadi seed yang sama tetap menghasilkan
# parameter yang sama persis.
_KANDIDAT_PECAHAN_P5 = _kandidat_pecahan((2, 3, 4, 6))
_KANDIDAT_PECAHAN_P6 = _kandidat_pecahan((3, 4, 5, 6, 8))


def _teks_desimal(perseratus: int) -> str:
    """Desimal dua angka di belakang koma, dengan KOMA (bukan titik).

    Repo ini memakai koma desimal di seluruh kunci (mis. π=3,14 di
    geometri) dan normalisasi diagnosa mengubah koma→titik saat
    membandingkan jawaban anak. Menulis titik di sini akan membuat kunci
    template ini tidak seragam dengan yang lain.
    """
    return f"{perseratus // 100},{perseratus % 100:02d}"


def _angka_awal(teks: str) -> int:
    """Angka pertama yang tertulis di sebuah bentuk bilangan.

    Dipakai malrule "membandingkan angka yang tertulis saja": anak yang
    belum menyamakan bentuk membandingkan 3 (dari 3/5), 60 (dari 0,60),
    dan 55 (dari 55%) apa adanya.
    """
    cocok = re.match(r"(\d+)", teks)
    return int(cocok.group(1)) if cocok else 0


def _bulat_ke(x: int, satuan: int) -> int:
    """Pembulatan ke satuan terdekat, aturan "setengah ke atas".

    Dipisah dari template supaya `_parameter` bisa memakai aturan yang
    SAMA saat menyaring kandidat. Kalau keduanya menghitung sendiri-
    sendiri, syarat "hasil pengurangan positif" bisa dijaga dengan aturan
    yang berbeda dari yang dipakai menghitung kunci.
    """
    sisa = x % satuan
    return x - sisa if sisa * 2 < satuan else x - sisa + satuan


def _kandidat_urut(penyebut: tuple[int, ...]) -> list[dict[str, int]]:
    """Trio (pecahan, desimal, persen) yang layak diurutkan.

    Tiga syarat, semuanya karena jalur diagnosis bisa hilang diam-diam
    lewat `saring_malrule`:

    1. **Ketiga nilai berbeda.** Kalau dua bentuk sama besar, urutannya
       punya lebih dari satu jawaban benar dan anak yang benar bisa
       tercatat salah.
    2. **Urutan "angka yang tertulis" berbeda dari urutan sebenarnya.**
       Ini sekaligus syarat KESAHIHAN soal: kalau membandingkan 3, 60,
       dan 55 apa adanya sudah memberi urutan yang benar, soal itu tidak
       menguji konversi sama sekali — anak bisa menjawab benar tanpa
       mengubah satu bentuk pun. Sebagai malrule, nilai itu juga akan
       menebak kunci dan membuang satu-satunya jalur K.
    3. **Urutan itu juga berbeda dari dua malrule lain** (terbalik penuh
       dan dua terbesar tertukar), supaya K, B, dan H tidak saling
       menghapus.

    Disaring saat impor, bukan lewat while-loop di `_parameter`: ruangnya
    kecil dan tertutup, jadi daftar penuh lebih murah sekaligus membuat
    jumlah kombinasi bisa dihitung pasti (guard >= 200).
    """
    hasil: list[dict[str, int]] = []
    for d1 in penyebut:
        for n1 in range(1, d1):
            if math.gcd(n1, d1) != 1:
                continue  # tampilkan pecahan paling sederhana saja
            pecahan = Fraction(n1, d1)
            # Pecahan WAJIB habis dua angka di belakang koma. 1/8 = 0,125
            # dan 1/3 = 0,333… memaksa pembahasan menulis "1/8 = 0,12" —
            # fakta yang SALAH, dan pembahasan itu dibaca anak.
            if (pecahan * 100).denominator != 1:
                continue
            for desimal in range(5, 100, 5):
                for persen in range(5, 100, 5):
                    bentuk = {
                        f"{n1}/{d1}": pecahan,
                        _teks_desimal(desimal): Fraction(desimal, 100),
                        f"{persen}%": Fraction(persen, 100),
                    }
                    if len(set(bentuk.values())) < 3:
                        continue
                    urut = [t for t, _ in sorted(bentuk.items(), key=lambda kv: kv[1])]
                    tertulis = sorted(bentuk, key=_angka_awal)
                    if tertulis == urut:
                        continue  # bisa dijawab benar tanpa mengubah bentuk
                    if tertulis == list(reversed(urut)):
                        continue  # K menabrak B
                    if tertulis == [urut[0], urut[2], urut[1]]:
                        continue  # K menabrak H
                    hasil.append(
                        {"n1": n1, "d1": d1, "desimal": desimal, "persen": persen}
                    )
    return hasil


def _kandidat_kali_bagi(penyebut: tuple[int, ...]) -> list[dict]:
    """Pasangan pecahan untuk kali/bagi dengan diagnosis yang sehat.

    Yang disaring, semuanya karena jalur diagnosis bisa hilang diam-diam
    lewat `saring_malrule`:

    - hasil harus tetap PECAHAN (bukan bilangan bulat) — anak menuliskan
      bentuk yang berbeda dari kunci dan tercatat salah padahal benar;
    - hasil, ketiga malrule, dan kunci harus saling berbeda;
    - malrule "hasil terbalik" tidak boleh sama dengan kunci (terjadi
      saat pembilang == penyebut).
    """
    hasil: list[dict] = []
    for d1 in penyebut:
        for d2 in penyebut:
            for n1 in range(1, d1):
                for n2 in range(1, d2):
                    if math.gcd(n1, d1) != 1 or math.gcd(n2, d2) != 1:
                        continue
                    a, b = Fraction(n1, d1), Fraction(n2, d2)
                    for op in ("kali", "bagi"):
                        nilai = a * b if op == "kali" else a / b
                        if nilai.denominator == 1:
                            continue  # hasil bulat, bukan latihan pecahan
                        k1 = (
                            Fraction(n1 * n2, math.lcm(d1, d2))
                            if op == "kali"
                            else a * b
                        )
                        k2 = Fraction(n1 + n2, d1 + d2)
                        h = Fraction(nilai.denominator, nilai.numerator)
                        teks = {
                            f"{x.numerator}/{x.denominator}"
                            for x in (nilai, k1, k2, h)
                        }
                        if len(teks) < 4:
                            continue  # tabrakan — saring_malrule akan buang
                        hasil.append(
                            {
                                "n1": n1,
                                "d1": d1,
                                "n2": n2,
                                "d2": d2,
                                "op": op,
                            }
                        )
    return hasil


_KANDIDAT_URUT_P5 = _kandidat_urut((2, 4, 5, 10))
# P6 sengaja TIDAK memakai penyebut 3, 6, 8, 9: 1/8 = 0,125 dan 1/3 =
# 0,333… tidak habis dua angka di belakang koma, sehingga pembahasan
# terpaksa menulis "1/8 = 0,12" — fakta yang SALAH, dan pembahasan itu
# dibaca anak. Ketahuan hanya dengan membaca keluaran nyatanya. Variasi
# tetap dijaga lewat penyebut 20 dan 25 (39 pecahan sederhana).
_KANDIDAT_URUT_P6 = _kandidat_urut((2, 4, 5, 10, 20, 25))
# Penyebut P5 sampai 8 (bukan 6): dengan 2..6 ruangnya hanya 142
# kombinasi, di bawah guard 200 di test_parameter_variants — dua anak
# beda seed bisa dapat soal pecahan yang sama. 2..8 memberi 526.
_KANDIDAT_KALI_BAGI_P5 = _kandidat_kali_bagi((2, 3, 4, 5, 6, 7, 8))
_KANDIDAT_KALI_BAGI_P6 = _kandidat_kali_bagi((3, 4, 5, 6, 7, 8, 9, 10))


def urutan_operasi_1(a: int, b: int, c: int, d: int, e: int) -> Soal:
    """Penjumlahan dan pengurangan dengan kali/bagi di tengah."""
    jawab = a + b // c * d - e
    kiri_ke_kanan = ((a + b) // c) * d - e
    kali_dulu = a + b // (c * d) - e
    mal = [
        Malrule(
            "urutan_operasi.kiri_ke_kanan_tanpa_prioritas",
            str(kiri_ke_kanan),
            "K",
            "mengerjakan lurus dari kiri ke kanan, tidak mendahulukan kali dan bagi",
        ),
        Malrule(
            "urutan_operasi.kali_sebelum_bagi_tanpa_kiri_ke_kanan",
            str(kali_dulu),
            "K",
            "mendahulukan kali atas bagi, padahal kali dan bagi dikerjakan dari kiri ke kanan",
        ),
        Malrule(
            "urutan_operasi.hasil_akhir_kurang_satu",
            str(jawab - 1),
            "H",
            "urutan caranya benar, tetapi pengurangan akhir kurang satu",
        ),
    ]
    return Soal(
        "urutan_operasi_1",
        {"a": a, "b": b, "c": c, "d": d, "e": e},
        f"Hitung: {a} + {b} ÷ {c} × {d} − {e}",
        str(jawab),
        saring_malrule(str(jawab), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: kerjakan kali/bagi DULU, baru tambah/kurang. "
            f"{b} : {c} = {b // c}, lalu x {d} = {b // c * d}. "
            f"{a} + {b // c * d} - {e} = {jawab}."
        ),
        bagian="A",
    )


@koreksi_soal(fpb)
def fpb_dua_bilangan(a: int, b: int) -> Soal:
    """FPB dua bilangan dengan pembeda eksplisit terhadap KPK."""
    jawab = math.gcd(a, b)
    kpk = math.lcm(a, b)
    mal = [
        Malrule(
            "fpb.tertukar_dengan_kpk",
            str(kpk),
            "B",
            "menjawab KPK padahal yang diminta FPB",
        ),
        Malrule(
            "fpb.faktor_terbesar_kurang_satu",
            str(jawab - 1),
            "H",
            "faktor bersama sudah dicari, tetapi memilih satu angka terlalu kecil",
        ),
        Malrule(
            "fpb.salah_pilih_faktor_bersama",
            str(max(1, jawab // 2)),
            "K",
            "berhenti pada faktor bersama kecil, belum mencari faktor persekutuan terbesar",
        ),
    ]
    return Soal(
        "fpb_dua_bilangan",
        {"a": a, "b": b},
        f"Tentukan FPB dari {a} dan {b}.",
        str(jawab),
        saring_malrule(str(jawab), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: FPB = bilangan TERBESAR yang membagi habis {a} dan {b}, "
            f"yaitu {jawab}. (KPK-nya {kpk} — jangan tertukar.)"
        ),
        bagian="B",
    )


@soal_berrevisi
def pecahan_operasi_campuran(
    n1: int, d1: int, n2: int, d2: int, n3: int, d3: int
) -> Soal:
    """Penjumlahan dan pengurangan tiga pecahan berbeda penyebut."""
    pertama = Fraction(n1, d1)
    kedua = Fraction(n2, d2)
    ketiga = Fraction(n3, d3)
    hasil = pertama + kedua - ketiga
    terpisah = Fraction(n1 + n2 - n3, d1 + d2 - d3)
    satu_unit = Fraction(1, math.lcm(d1, d2, d3))
    salah_hitung = hasil - satu_unit
    mal = [
        Malrule(
            "pecahan.operasi_pembilang_penyebut_terpisah",
            _teks_pecahan(terpisah),
            "K",
            "menjumlahkan pembilang dan penyebut secara terpisah",
        ),
        Malrule(
            "pecahan.pengurangan_pembilang_meleset",
            _teks_pecahan(salah_hitung),
            "H",
            "penyebut sudah disamakan, tetapi pengurangan pembilang kurang satu",
        ),
        Malrule(
            "pecahan.mengabaikan_pengurangan_terakhir",
            _teks_pecahan(pertama + kedua),
            "B",
            "menjawab penjumlahan dua pecahan pertama dan tidak mengurangi pecahan terakhir",
        ),
    ]
    return Soal(
        "pecahan_operasi_campuran",
        {"n1": n1, "d1": d1, "n2": n2, "d2": d2, "n3": n3, "d3": d3},
        f"Hitung: {n1}/{d1} + {n2}/{d2} − {n3}/{d3}",
        _teks_pecahan(hasil),
        saring_malrule(_teks_pecahan(hasil), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: samakan penyebut dulu (KPK dari {d1}, {d2}, {d3}), "
            f"baru jumlah/kurangkan pembilangnya. Hasilnya "
            + _teks_pecahan(hasil) + "."
        ),
        bagian="C",
        tantangan=True,
    )


# ── Empat jenis soal baru (gelombang 2, 2 Sep 2026) ────────────────────
#
# Paket ini adalah kasus TERPARAH di seluruh aplikasi: 3000 soal P5 hanya
# melahirkan 3 bentuk kalimat, dan itu terjadi di P5/P6 — level yang
# paling butuh variasi.
#
# Obatnya SENGAJA bukan latar cerita (beda dari aritmatika-lanjut). Soal
# di paket ini 100% perintah hitung murni, dan itu memang bentuk yang
# benar untuk melatih urutan operasi; membungkusnya jadi cerita menambah
# beban baca yang bukan sedang diuji. Akar masalahnya paket ini cuma
# punya TIGA template. Jenis soalnya dikonfirmasi pemilik produk —
# pemilihan jenis soal adalah keputusan kurikulum, bukan teknis.


def urut_pecahan_desimal_persen(
    n1: int, d1: int, desimal: int, persen: int
) -> Soal:
    """Urutkan pecahan, desimal, dan persen dari yang TERKECIL.

    Gap riset 28 soal OSN asli: anak bisa menghitung pecahan tapi tidak
    bisa membandingkannya dengan desimal dan persen, karena ketiganya
    diajarkan sebagai tiga dunia terpisah.

    Kunci adalah URUTAN LENGKAP ketiganya, bukan "yang terkecil" saja.
    Versi pertama meminta satu bentuk saja dan itu SALAH desain: ruang
    jawabannya cuma tiga nilai, sehingga kunci + tiga malrule tidak muat
    dan `saring_malrule` membuang jalur K di seluruh 59 seed yang diuji —
    template tanpa jalur K tidak bisa mendiagnosis miskonsepsi apa pun.
    Dengan urutan lengkap, ruang jawabannya 6 permutasi dan ketiga jalur
    diagnosis punya tempat masing-masing.

    Tiap bentuk ditulis dalam BENTUK ASLINYA (mis. "3/5", bukan "0,6"):
    yang dinilai adalah kemampuan mengurutkan, bukan menyalin hasil
    konversi.
    """
    pecahan = Fraction(n1, d1)
    bentuk = {
        f"{n1}/{d1}": pecahan,
        _teks_desimal(desimal): Fraction(desimal, 100),
        f"{persen}%": Fraction(persen, 100),
    }
    urut = [t for t, _ in sorted(bentuk.items(), key=lambda kv: kv[1])]
    kunci = ", ".join(urut)
    # K: membandingkan angka yang TERTULIS tanpa menyamakan bentuk dulu —
    # 3 (dari 3/5), 60 (dari 0,60), 55 (dari 55%) dibandingkan apa adanya.
    tertulis = ", ".join(sorted(bentuk, key=_angka_awal))
    mal = [
        Malrule(
            "urut_bentuk.angka_tertulis",
            tertulis,
            "K",
            "membandingkan angka yang tertulis saja, tanpa menyamakan "
            "bentuk pecahan, desimal, dan persen lebih dulu",
        ),
        Malrule(
            "urut_bentuk.terbalik",
            ", ".join(reversed(urut)),
            "B",
            "mengurutkan dari yang TERBESAR padahal yang diminta terkecil",
        ),
        Malrule(
            "urut_bentuk.dua_terakhir_tertukar",
            ", ".join([urut[0], urut[2], urut[1]]),
            "H",
            "dua bentuk terbesar tertukar tempatnya",
        ),
    ]
    teks = (
        f"Urutkan dari yang TERKECIL: {n1}/{d1}, {_teks_desimal(desimal)}, "
        f"dan {persen}%."
    )
    return Soal(
        "urut_pecahan_desimal_persen",
        {"n1": n1, "d1": d1, "desimal": desimal, "persen": persen},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: ubah ketiganya ke bentuk yang SAMA dulu. "
            f"{n1}/{d1} = {_teks_desimal(round(pecahan * 100))}, "
            f"{persen}% = {_teks_desimal(persen)}, dan "
            f"{_teks_desimal(desimal)} tetap. "
            f"Setelah disamakan, urutannya {kunci}."
        ),
        bagian="D",
    )


@soal_berrevisi
def pecahan_kali_bagi(n1: int, d1: int, n2: int, d2: int, op: str) -> Soal:
    """Kali atau bagi dua pecahan.

    Template lama (`pecahan_operasi_campuran`) hanya melatih + dan −,
    yang justru butuh menyamakan penyebut. Kali dan bagi punya aturan
    yang BERBEDA — dan miskonsepsi terkenalnya adalah menyamakan penyebut
    di sini juga, atau membagi tanpa membalik pecahan kedua.
    """
    a = Fraction(n1, d1)
    b = Fraction(n2, d2)
    hasil = a * b if op == "kali" else a / b
    if op == "kali":
        lambang = "×"
        # Miskonsepsi khas kali: penyebut disamakan dulu (padahal tidak
        # perlu), lalu pembilang dikali dan penyebut dibiarkan satu.
        k1 = Fraction(n1 * n2, math.lcm(d1, d2))
        alasan_k1 = (
            "menyamakan penyebut lebih dulu — aturan itu untuk tambah/kurang, "
            "bukan untuk kali"
        )
    else:
        lambang = "÷"
        # Miskonsepsi khas bagi: langsung dikali tanpa membalik yang kedua.
        k1 = a * b
        alasan_k1 = (
            "langsung mengalikan kedua pecahan — pembagian harus MEMBALIK "
            "pecahan kedua lebih dulu"
        )
    # Salah hitung: pembilang dan penyebut tertukar di hasil akhir.
    h = Fraction(hasil.denominator, hasil.numerator)
    mal = [
        Malrule(
            f"pecahan_{op}.aturan_tertukar" if op == "kali" else "pecahan_bagi.lupa_balik",
            f"{k1.numerator}/{k1.denominator}",
            "K",
            alasan_k1,
        ),
        Malrule(
            f"pecahan_{op}.jumlah_pembilang",
            f"{n1 + n2}/{d1 + d2}",
            "K",
            "menjumlahkan pembilang dan penyebut secara terpisah",
        ),
        Malrule(
            f"pecahan_{op}.hasil_terbalik",
            f"{h.numerator}/{h.denominator}",
            "H",
            "caranya benar, tetapi pembilang dan penyebut hasilnya tertukar",
        ),
    ]
    kunci = f"{hasil.numerator}/{hasil.denominator}"
    if op == "kali":
        langkah = (
            f"Langkah: kali pecahan TIDAK perlu menyamakan penyebut. "
            f"Pembilang x pembilang, penyebut x penyebut: "
            f"({n1} x {n2})/({d1} x {d2}) = {kunci}."
        )
    else:
        langkah = (
            f"Langkah: bagi pecahan = kali dengan KEBALIKANNYA. "
            f"{n1}/{d1} x {d2}/{n2} = {kunci}."
        )
    return Soal(
        "pecahan_kali_bagi",
        {"n1": n1, "d1": d1, "n2": n2, "d2": d2, "op": op},
        f"Hitung: {n1}/{d1} {lambang} {n2}/{d2}",
        kunci,
        saring_malrule(kunci, mal),
        minta_restatement=True,
        pembahasan=langkah,
        bagian="C",
    )


def pembulatan_taksiran(a: int, b: int, satuan: int, op: str) -> Soal:
    """Bulatkan dua bilangan ke satuan terdekat, lalu taksir hasilnya.

    Dua langkah dalam satu soal, dan itu memang intinya: anak yang bisa
    membulatkan tapi menaksir dari angka aslinya belum paham gunanya
    membulatkan.

    Parameter dijaga TIDAK PERNAH tepat di titik tengah (mis. 250 ke
    ratusan): di titik itu ada dua aturan yang sama-sama diajarkan di
    sekolah ("bulatkan ke atas" vs "ke bilangan genap"), jadi soalnya
    tidak bisa dinilai adil.
    """
    def bulat(x: int) -> int:
        sisa = x % satuan
        return x - sisa if sisa * 2 < satuan else x - sisa + satuan

    a_bulat, b_bulat = bulat(a), bulat(b)
    kunci = a_bulat + b_bulat if op == "tambah" else a_bulat - b_bulat
    tepat = a + b if op == "tambah" else a - b
    lambang = "+" if op == "tambah" else "−"
    nama_satuan = {10: "puluhan", 100: "ratusan", 1000: "ribuan"}[satuan]
    mal = [
        Malrule(
            "taksiran.hasil_tepat",
            str(tepat),
            "K",
            f"menghitung {a} {lambang} {b} apa adanya — angkanya belum dibulatkan",
        ),
        Malrule(
            "taksiran.bulatkan_hasil",
            str(bulat(tepat)),
            "K",
            "membulatkan HASILNYA, padahal yang diminta membulatkan dulu "
            "lalu menghitung",
        ),
        Malrule(
            "taksiran.satu_satuan",
            str(kunci - satuan),
            "H",
            f"cara sudah benar, hasilnya meleset satu {nama_satuan}",
        ),
    ]
    kata_op = "jumlahnya" if op == "tambah" else "selisihnya"
    teks = (
        f"Bulatkan {a} dan {b} ke {nama_satuan} terdekat, "
        f"lalu taksir {kata_op}."
    )
    return Soal(
        "pembulatan_taksiran",
        {"a": a, "b": b, "satuan": satuan, "op": op},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: bulatkan DULU, baru hitung. "
            f"{a} jadi {a_bulat}, {b} jadi {b_bulat}. "
            f"{a_bulat} {lambang} {b_bulat} = {kunci}."
        ),
        bagian="A",
    )


def operasi_berkurung(a: int, b: int, c: int, d: int, e: int) -> Soal:
    """(a + b) × c − d ÷ e — kurung mendahului kali dan bagi.

    Konsep yang BERBEDA dari `urutan_operasi_1`: di sana anak belajar
    kali/bagi mendahului tambah/kurang; di sini ia belajar kurung
    mendahului keduanya. Parameter dijaga supaya hasil dengan kurung
    SELALU berbeda dari hasil tanpa kurung — kalau sama, soalnya tidak
    menguji apa pun dan malrule "mengabaikan kurung" akan menebak kunci.
    """
    jawab = (a + b) * c - d // e
    abaikan_kurung = a + b * c - d // e
    kiri_ke_kanan = ((a + b) * c - d) // e
    mal = [
        Malrule(
            "berkurung.abaikan_kurung",
            str(abaikan_kurung),
            "K",
            "mengerjakan kali lebih dulu — kurung harus dikerjakan paling awal",
        ),
        Malrule(
            "berkurung.bagi_seluruh",
            str(kiri_ke_kanan),
            "K",
            f"membagi seluruh hasil dengan {e}, padahal {e} hanya membagi {d}",
        ),
        Malrule(
            "berkurung.kurang_satu",
            str(jawab - 1),
            "H",
            "urutannya benar, hasil akhirnya meleset satu",
        ),
    ]
    return Soal(
        "operasi_berkurung",
        {"a": a, "b": b, "c": c, "d": d, "e": e},
        f"Hitung: ({a} + {b}) × {c} − {d} ÷ {e}",
        str(jawab),
        saring_malrule(str(jawab), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: KURUNG dulu, lalu kali/bagi, baru tambah/kurang. "
            f"({a} + {b}) = {a + b}, x {c} = {(a + b) * c}. "
            f"{d} : {e} = {d // e}. "
            f"{(a + b) * c} - {d // e} = {jawab}."
        ),
        bagian="A",
    )


REGISTRI_TOPIK = {
    "urutan_operasi_1": urutan_operasi_1,
    "fpb_dua_bilangan": fpb_dua_bilangan,
    "pecahan_operasi_campuran": pecahan_operasi_campuran,
    "urut_pecahan_desimal_persen": urut_pecahan_desimal_persen,
    "pecahan_kali_bagi": pecahan_kali_bagi,
    "pembulatan_taksiran": pembulatan_taksiran,
    "operasi_berkurung": operasi_berkurung,
}

# Komposisi 10 soal per lembar (dari 6). Empat template baru masuk semua:
# template yang terdaftar tapi tidak dipakai adalah "template tidur", dan
# gelombang 1 sudah membuktikan bahwa menambah template tanpa memakainya
# tidak memperbaiki apa pun.
KOMPOSISI = {
    "P5": (
        "urutan_operasi_1", "operasi_berkurung", "fpb_dua_bilangan",
        "pecahan_operasi_campuran", "pecahan_kali_bagi",
        "urut_pecahan_desimal_persen", "pembulatan_taksiran",
        "urutan_operasi_1", "pecahan_kali_bagi", "operasi_berkurung",
    ),
    "P6": (
        "urutan_operasi_1", "operasi_berkurung", "fpb_dua_bilangan",
        "pecahan_operasi_campuran", "pecahan_kali_bagi",
        "urut_pecahan_desimal_persen", "pembulatan_taksiran",
        "operasi_berkurung", "pecahan_kali_bagi", "pembulatan_taksiran",
    ),
}


@parameter_baru
def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id == "urutan_operasi_1":
        c, d = rng.choice(((3, 2), (4, 3), (5, 2)))
        pengali = (6, 14) if level == "P5" else (12, 22)
        batas_a = (4, 12) if level == "P5" else (8, 18)
        batas_e = (5, 18) if level == "P5" else (15, 32)
        kandidat = [
            (a_unit, b_unit)
            for a_unit in range(batas_a[0], batas_a[1] + 1)
            for b_unit in range(pengali[0], pengali[1] + 1)
            if (a_unit * d + b_unit * d * d)
            != (a_unit * d + b_unit)
            and (a_unit * d + b_unit * d * d)
            != (a_unit * c + b_unit)
            and (a_unit * d + b_unit * d)
            != (a_unit * c + b_unit)
        ]
        a_unit, b_unit = rng.choice(kandidat)
        return {
            "a": c * a_unit,
            "b": c * d * b_unit,
            "c": c,
            "d": d,
            "e": rng.randint(*batas_e),
        }
    if template_id == "fpb_dua_bilangan":
        faktor = rng.choice(
            (4, 6, 8, 9, 12, 15, 18) if level == "P5" else (12, 15, 18, 20, 24, 30, 36)
        )
        x, y = rng.sample(range(2, 12), 2)
        return {"a": faktor * x, "b": faktor * y}
    if template_id == "pecahan_operasi_campuran":
        kandidat = _KANDIDAT_PECAHAN_P5 if level == "P5" else _KANDIDAT_PECAHAN_P6
        return dict(rng.choice(kandidat))
    if template_id == "urut_pecahan_desimal_persen":
        # Ketiga nilai WAJIB berbeda: kalau dua di antaranya seri sebagai
        # yang terkecil, malrule "ambil yang terbesar" bisa menebak kunci
        # dan anak yang salah tercatat benar.
        kandidat = _KANDIDAT_URUT_P5 if level == "P5" else _KANDIDAT_URUT_P6
        return dict(rng.choice(kandidat))
    if template_id == "pecahan_kali_bagi":
        kandidat = (
            _KANDIDAT_KALI_BAGI_P5 if level == "P5" else _KANDIDAT_KALI_BAGI_P6
        )
        return dict(rng.choice(kandidat))
    if template_id == "pembulatan_taksiran":
        # Satuan pembulatan naik di P6. Tiga syarat, semuanya karena
        # jalur diagnosis bisa hilang diam-diam lewat saring_malrule:
        #
        # 1. Titik tengah (sisa × 2 == satuan) ditolak: di sana ada dua
        #    aturan yang sama-sama diajarkan di sekolah, jadi soalnya
        #    tidak bisa dinilai adil.
        # 2. Hasil TEPAT harus beda dari kunci — kalau a dan b kebetulan
        #    sudah bulat, "menghitung apa adanya" (K) menebak kunci dan
        #    anak yang belum membulatkan tercatat benar.
        # 3. Membulatkan HASILNYA (K kedua) juga harus beda dari kunci
        #    dan dari K pertama, dan H (kurang satu satuan) beda dari
        #    keduanya. Kalau tidak, soal kehilangan K atau H.
        satuan = rng.choice((10, 100)) if level == "P5" else rng.choice((100, 1000))
        batas = (satuan, satuan * 40) if level == "P5" else (satuan, satuan * 80)
        op = rng.choice(("tambah", "kurang"))
        while True:
            a = rng.randint(*batas)
            b = rng.randint(*batas)
            if (a % satuan) * 2 == satuan or (b % satuan) * 2 == satuan:
                continue
            a_bulat, b_bulat = _bulat_ke(a, satuan), _bulat_ke(b, satuan)
            if op == "tambah":
                kunci, tepat = a_bulat + b_bulat, a + b
            else:
                kunci, tepat = a_bulat - b_bulat, a - b
                # Hasil harus positif dan cukup besar: anak SD belum
                # mengerjakan bilangan negatif di paket ini, dan malrule
                # "kurang satu satuan" ikut negatif kalau kunci nol.
                if kunci <= satuan:
                    continue
            jawaban = {kunci, tepat, _bulat_ke(tepat, satuan), kunci - satuan}
            if len(jawaban) < 4:
                continue  # tabrakan — saring_malrule akan membuang K atau H
            return {"a": a, "b": b, "satuan": satuan, "op": op}
    if template_id == "operasi_berkurung":
        # d harus habis dibagi e (hasil bulat) DAN kurung harus mengubah
        # hasil — kalau tidak, soalnya tidak menguji kurung sama sekali
        # dan malrule "abaikan kurung" menebak kunci.
        batas_ab = (2, 12) if level == "P5" else (4, 20)
        batas_c = (2, 8) if level == "P5" else (3, 12)
        while True:
            a = rng.randint(*batas_ab)
            b = rng.randint(*batas_ab)
            c = rng.randint(*batas_c)
            e = rng.randint(2, 9)
            d = e * rng.randint(2, 15 if level == "P5" else 25)
            if a == b * c - a:  # (a+b)*c == a + b*c  →  kurung tak berarti
                continue
            dengan = (a + b) * c - d // e
            tanpa = a + b * c - d // e
            if dengan == tanpa or dengan <= 1:
                continue
            # malrule "bagi seluruh" tidak boleh menebak kunci atau H
            seluruh = ((a + b) * c - d) // e
            if seluruh in (dengan, dengan - 1, tanpa):
                continue
            return {"a": a, "b": b, "c": c, "d": d, "e": e}
    raise KeyError(f"template tidak dikenal: {template_id}")


TOPIK = Topik(
    id="aritmetika-dasar",
    nama="Aritmetika Dasar",
    judul_lembar="Latihan Aritmetika Dasar",
    judul_penilaian="Penilaian — Aritmetika Dasar",
    templates=REGISTRI_TOPIK,
    komposisi=KOMPOSISI,
    profil={"P5": {}, "P6": {}},
    judul_bagian={
        "A": "Bagian A — Urutan operasi & taksiran",
        "B": "Bagian B — Faktor persekutuan",
        "C": "Bagian C — Operasi pecahan",
        "D": "Bagian D — Membandingkan bentuk bilangan",
    },
    catatan_bagian={
        "A": "Kerjakan kurung dulu, lalu kali dan bagi. Kalau sama tingkatnya, baca dari kiri ke kanan.",
        "C": "Tambah/kurang: samakan penyebut. Kali: langsung. Bagi: balik pecahan kedua.",
        "D": "Ubah ke bentuk yang sama dulu sebelum membandingkan.",
    },
    parameter_untuk=_parameter,
)

daftarkan(TOPIK)
