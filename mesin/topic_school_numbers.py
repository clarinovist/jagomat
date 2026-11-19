"""Bilangan Sekolah kelas 3–5 (P3–P5), khusus Latihan manual guru dan lembar cetak.

Tahap A: satu jenis soal, `nilai_tempat_besar` (nilai angka menurut tempatnya,
dan bentuk panjang: menyusun dan membongkar bilangan). Semua soal teks angka,
tanpa gambar. Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan
diagnosis pasti dari satu jawaban.

Palang: topik ini `hanya_manual`, jadi tidak ikut Campuran, siklus terpandu,
mastery, atau Pendamping karena belum punya grup mastery, kartu intervensi, dan
playbook. Pembuatan soal juga di balik `OSN_BILANGAN_SEKOLAH` (lihat
`school_numbers_versions`); pembaca histori selalu mengenal topik dan jenisnya.

Rentang (CP 046/2025, batas tepat ditinjau Guru sebelum sakelar menyala):
P3 100–999, P4 1.000–9.999, P5 10.000–999.999. Angka dalam satu bilangan tidak
berulang supaya "angka 3 pada bilangan ..." tak ambigu dan dua malrule angka
tak kembar. Kunci dan malrule dihitung dari parameter; kunci dicek solver
terpisah yang hanya membaca teks (test_school_numbers_domain).
"""
from __future__ import annotations

import random

from templates import Malrule, Soal, saring_malrule
from topics import Topik, daftarkan

TEMPLATE_ID = "nilai_tempat_besar"
VARIAN = ("nilai_angka", "lengkapi_panjang", "susun_panjang")
BATAS_BAWAH, BATAS_ATAS = 100, 999_999
JUMLAH_ANGKA_PER_LEVEL = {"P3": (3,), "P4": (4,), "P5": (5, 6)}
PROFIL_LEVEL = {level: {} for level in JUMLAH_ANGKA_PER_LEVEL}
JUMLAH_SOAL_LEMBAR = 8
NAMA_TEMPAT = ("satuan", "puluhan", "ratusan", "ribuan", "puluhan ribu", "ratusan ribu")
KALI = "×"

ID_ANGKA_SAJA = TEMPLATE_ID + ".angka_saja"
ID_TEMPAT_TETANGGA = TEMPLATE_ID + ".tempat_tetangga"
ID_NOL_KURANG = TEMPLATE_ID + ".nol_kurang_satu"
ID_ANGKA_DIJUMLAH = TEMPLATE_ID + ".angka_dijumlah"
ID_TERATAS_TERTUKAR = TEMPLATE_ID + ".angka_teratas_tertukar"
ID_SATUAN_TERLEWAT = TEMPLATE_ID + ".satuan_terlewat"


def _ribuan(n: int) -> str:
    """Titik ribuan gaya Indonesia untuk teks; kunci dan malrule tetap angka polos."""
    return f"{n:,}".replace(",", ".")


def _digit(bilangan: int, posisi: int) -> int:
    return bilangan // 10 ** posisi % 10


def _sah(varian, bilangan, posisi) -> bool:
    if varian not in VARIAN:
        return False
    if type(bilangan) is not int or not BATAS_BAWAH <= bilangan <= BATAS_ATAS:
        return False
    teks = str(bilangan)
    if len(set(teks)) != len(teks):
        return False
    if varian == "susun_panjang":
        return posisi is None and "0" not in teks
    atas = len(teks) - 1
    if type(posisi) is not int or not 1 <= posisi <= atas:
        return False
    if _digit(bilangan, posisi) == 0:
        return False
    return varian == "nilai_angka" or "0" not in teks


def _bagian(bilangan: int) -> list:
    """(posisi, angka, nilai) dari tempat tertinggi ke satuan."""
    atas = len(str(bilangan)) - 1
    return [(p, _digit(bilangan, p), _digit(bilangan, p) * 10 ** p)
            for p in range(atas, -1, -1)]


# ── nilai_angka dan lengkapi_panjang: satu angka pada satu tempat ────────

def _malrule_tempat(d: int, p: int, atas: int) -> list:
    """Dua jalur K (angka saja, tempat sebelah) dan satu H (kurang satu nol).

    Tetangga yang dipakai adalah tempat DI ATAS bila ada. Tetangga bawah pada
    puluhan bernilai d x 1 = angka saja, jadi dipakai hanya di tempat tertinggi
    (di sana bernilai d x 10^(p-1), tidak sama dengan angka saja karena p >= 2).
    """
    if p < atas:
        tetangga = Malrule(
            ID_TEMPAT_TETANGGA, str(d * 10 ** (p + 1)), "K",
            f"Menukar tempat angka {d} dengan tempat di atasnya ({NAMA_TEMPAT[p + 1]}), "
            "sehingga nilainya satu tingkat terlalu besar.")
    else:
        tetangga = Malrule(
            ID_TEMPAT_TETANGGA, str(d * 10 ** (p - 1)), "K",
            f"Menukar tempat angka {d} dengan tempat di bawahnya ({NAMA_TEMPAT[p - 1]}), "
            "sehingga nilainya satu tingkat terlalu kecil.")
    kandidat = [
        Malrule(ID_ANGKA_SAJA, str(d), "K",
                f"Menjawab angkanya saja ({d}), padahal yang ditanya nilainya menurut tempat."),
        tetangga,
    ]
    if p < atas:
        kandidat.append(Malrule(
            ID_NOL_KURANG, str(d * 10 ** (p - 1)), "H",
            "Konsep nilai tempat sudah tepat, tetapi salah menghitung banyak nol sehingga kurang satu nol."))
    return kandidat


def _pembahasan_nilai_angka(bilangan: int, p: int, d: int) -> str:
    nilai = d * 10 ** p
    return (f"Pada {_ribuan(bilangan)}, angka {d} berada di tempat {NAMA_TEMPAT[p]}, "
            f"jadi nilainya {d} {KALI} {_ribuan(10 ** p)} = {_ribuan(nilai)}. "
            f"Jadi nilai angka {d} adalah {_ribuan(nilai)}.")


def _pembahasan_lengkapi(bilangan: int, p: int, d: int) -> str:
    langkah = [f"{a} {KALI} {_ribuan(10 ** q)} = {_ribuan(v)}" for q, a, v in _bagian(bilangan)]
    daftar = ", ".join(langkah[:-1]) + ", dan " + langkah[-1]
    jumlah = " + ".join(_ribuan(v) for _, _, v in _bagian(bilangan))
    return (f"Setiap angka dikalikan nilai tempatnya: {daftar}. "
            f"Bagian yang hilang adalah angka {d} di tempat {NAMA_TEMPAT[p]}, "
            f"yaitu {d} {KALI} {_ribuan(10 ** p)} = {_ribuan(d * 10 ** p)}. "
            f"Cek: {jumlah} = {_ribuan(bilangan)}.")


# ── susun_panjang: bagian-bagian disatukan menjadi satu bilangan ─────────

def _malrule_susun(bilangan: int) -> list:
    angka = str(bilangan)
    tertukar = int(angka[1] + angka[0] + angka[2:])
    return [
        Malrule(ID_ANGKA_DIJUMLAH, str(sum(map(int, angka))), "K",
                "Menjumlahkan angkanya saja, bukan nilai tiap bagian menurut tempatnya."),
        Malrule(ID_TERATAS_TERTUKAR, str(tertukar), "K",
                "Menukar dua angka teratas ketika menuliskan bilangan, sehingga tempatnya terbalik."),
        Malrule(ID_SATUAN_TERLEWAT, str(bilangan - bilangan % 10), "H",
                "Konsep nilai tempat sudah tepat, tetapi bagian satuan terlewat saat menjumlahkan."),
    ]


def _pembahasan_susun(bilangan: int) -> str:
    jumlah = " + ".join(_ribuan(v) for _, _, v in _bagian(bilangan))
    return (f"Jumlahkan semua bagian: {jumlah} = {_ribuan(bilangan)}. "
            f"Jadi bilangan yang terbentuk adalah {_ribuan(bilangan)}.")


def nilai_tempat_besar(varian: str, bilangan: int, posisi: int | None = None) -> Soal:
    """Nilai angka menurut tempat, atau bentuk panjang (lengkapi / susun).

    `posisi` = pangkat sepuluh tempat yang ditanya (1 puluhan ... 5 ratusan ribu);
    satuan (0) tidak ditanya karena angka saja sama dengan nilainya. Bentuk
    `susun_panjang` tidak memakai posisi.
    """
    if not _sah(varian, bilangan, posisi):
        raise ValueError("parameter nilai tempat bilangan besar di luar domain")
    atas = len(str(bilangan)) - 1
    parameter = {"varian": varian, "bilangan": bilangan}
    if varian == "susun_panjang":
        bagian = " + ".join(_ribuan(v) for _, _, v in _bagian(bilangan))
        return Soal(
            template_id=TEMPLATE_ID, parameter=parameter,
            teks=f"Tulis sebagai satu bilangan: {bagian} = ...", kunci=str(bilangan),
            malrule=saring_malrule(str(bilangan), _malrule_susun(bilangan)),
            pembahasan=_pembahasan_susun(bilangan), bagian="A")
    parameter["posisi"] = posisi
    d = _digit(bilangan, posisi)
    kunci = str(d * 10 ** posisi)
    if varian == "nilai_angka":
        teks = f"Nilai angka {d} pada bilangan {_ribuan(bilangan)} adalah ..."
        pembahasan = _pembahasan_nilai_angka(bilangan, posisi, d)
    else:
        suku = [("..." if q == posisi else _ribuan(v)) for q, _, v in _bagian(bilangan)]
        teks = f"Lengkapi bentuk panjang: {_ribuan(bilangan)} = {' + '.join(suku)}"
        pembahasan = _pembahasan_lengkapi(bilangan, posisi, d)
    return Soal(
        template_id=TEMPLATE_ID, parameter=parameter, teks=teks, kunci=kunci,
        malrule=saring_malrule(kunci, _malrule_tempat(d, posisi, atas)),
        pembahasan=pembahasan, bagian="A")


# ── sampler ──────────────────────────────────────────────────────────────

def _acak_bilangan(rng: random.Random, panjang: int, boleh_nol: bool) -> int:
    """Angka tak berulang, angka pertama bukan nol; hanya memakai `rng`."""
    awal = rng.randint(1, 9)
    sisa = [a for a in range(0 if boleh_nol else 1, 10) if a != awal]
    return int("".join(str(a) for a in [awal] + rng.sample(sisa, panjang - 1)))


def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id != TEMPLATE_ID:
        raise KeyError(template_id)
    if level not in JUMLAH_ANGKA_PER_LEVEL:
        raise ValueError("level bilangan sekolah harus P3, P4, atau P5")
    panjang = rng.choice(JUMLAH_ANGKA_PER_LEVEL[level])
    varian = rng.choice(VARIAN)
    bilangan = _acak_bilangan(rng, panjang, boleh_nol=(varian == "nilai_angka"))
    if varian == "susun_panjang":
        return {"varian": varian, "bilangan": bilangan}
    layak = [p for p in range(1, panjang) if _digit(bilangan, p) != 0]
    return {"varian": varian, "bilangan": bilangan, "posisi": rng.choice(layak)}


REGISTRI_TOPIK = {TEMPLATE_ID: nilai_tempat_besar}
KOMPOSISI = {level: (TEMPLATE_ID,) * JUMLAH_SOAL_LEMBAR for level in PROFIL_LEVEL}


daftarkan(Topik(
    id="bilangan-sekolah",
    nama="Bilangan Sekolah",
    judul_lembar="Latihan Bilangan Sekolah (Kelas 3–5)",
    judul_penilaian="Penilaian — Bilangan Sekolah",
    templates=REGISTRI_TOPIK,
    komposisi=KOMPOSISI,
    profil=PROFIL_LEVEL,
    judul_bagian={"A": "Bagian A — Nilai tempat bilangan besar"},
    catatan_bagian={"A": "Perhatikan beda antara angka dan nilainya menurut tempat."},
    parameter_untuk=_parameter,
    hanya_manual=True,
))
