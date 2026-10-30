"""Bilangan dasar khusus Latihan manual P1/P2, bukan target siklus.

Batch 1 bertahap: hanya penjumlahan, teks saja. Malrule adalah HIPOTESIS
kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari satu jawaban.
Template baru tidak punya konten historis yang perlu marker katalog/revisi.
"""
from __future__ import annotations

from templates import Malrule, Soal, saring_malrule
from topics import Topik, daftarkan


PROFIL_LEVEL = {
    "P1": {"hasil": (2, 10)},
    "P2": {"hasil": (11, 20)},
}


def domain_parameter(template_id: str, level: str) -> tuple[dict, ...]:
    """Seluruh pasangan berurutan sah; dict baru setiap panggilan.

    Keputusan pengguna 30 Okt 2026: cakupan >=90% domain dalam 500 seed,
    bukan >=200 kombinasi. Nol dikecualikan agar operasi tertukar tidak
    sama dengan kunci. P1 45 pasangan; P2 145, termasuk dua digit + satu digit.
    """
    if template_id != "tambah_dasar":
        raise KeyError(template_id)
    if level not in PROFIL_LEVEL:
        raise ValueError("level bilangan dasar harus P1 atau P2")
    bawah, atas = PROFIL_LEVEL[level]["hasil"]
    return tuple({"a": a, "b": b}
                 for a in range(1, atas)
                 for b in range(1, atas)
                 if bawah <= a + b <= atas)


def _parameter(template_id, rng, level):
    """Satu undian seragam dari domain terbatas; tanpa rejection atau nudge."""
    return dict(rng.choice(domain_parameter(template_id, level)))


def _pembahasan(a, b):
    besar, kecil = max(a, b), min(a, b)
    jumlah = a + b
    if jumlah <= 10:
        langkah = ", ".join(str(n) for n in range(besar + 1, jumlah + 1))
        return (f"Mulai dari {besar}, hitung maju {kecil} langkah: {langkah}. "
                f"Jadi {a} + {b} = {jumlah}.")
    if besar < 10:
        ambil = 10 - besar
        sisa = kecil - ambil
        return (f"{a} + {b}: ambil {ambil} dari {kecil} supaya {besar} menjadi 10. "
                f"Sisanya {sisa}. 10 + {sisa} = {jumlah}.")
    if besar == 10:
        return (f"{a} + {b}: mulai dari 10, tambah {kecil}. "
                f"10 + {kecil} = {jumlah}.")
    satuan = besar - 10
    return (f"{a} + {b}: {besar} adalah 10 dan {satuan}. "
            f"{satuan} + {kecil} = {satuan + kecil}. "
            f"10 + {satuan + kecil} = {jumlah}.")


def tambah_dasar(a: int, b: int) -> Soal:
    """Cari hasil a+b pada gabungan domain; level dipasang oleh generator."""
    if type(a) is not int or type(b) is not int or a < 1 or b < 1 or a + b > 20:
        raise ValueError("parameter penjumlahan di luar domain")
    kunci = a + b
    kandidat = [
        Malrule("tambah_dasar.operasi_tertukar", str(abs(a - b)), "K",
                "Mengurangkan bilangan yang lebih kecil dari yang lebih besar, bukan menjumlahkan keduanya."),
        Malrule("tambah_dasar.hitung_maju_dari_awal", str(kunci - 1), "H",
                "Ikut menghitung bilangan awal sebagai langkah pertama, sehingga hasilnya kurang satu."),
    ]
    if kunci >= 10:
        # Definisi yang disetujui: jumlah - 10, bukan modulo 10.
        # Pada hasil 20 kandidatnya 10 (satu puluhan terlupa), bukan 0.
        kandidat.append(Malrule("tambah_dasar.lupa_puluhan", str(kunci - 10), "K",
                                "Melupakan satu puluhan saat menulis hasil penjumlahan, sehingga hasilnya berkurang sepuluh."))
    return Soal(
        template_id="tambah_dasar", parameter={"a": a, "b": b},
        teks=f"{a} + {b} = ...", kunci=str(kunci),
        malrule=saring_malrule(str(kunci), kandidat),
        pembahasan=_pembahasan(a, b), bagian="A",
    )


REGISTRI_TOPIK = {"tambah_dasar": tambah_dasar}


daftarkan(Topik(
    id="bilangan-dasar",
    nama="Bilangan Dasar",
    judul_lembar="Latihan Bilangan Dasar",
    judul_penilaian="Penilaian — Bilangan Dasar",
    templates=REGISTRI_TOPIK,
    komposisi={level: ("tambah_dasar",) * 10 for level in PROFIL_LEVEL},
    profil=PROFIL_LEVEL,
    judul_bagian={"A": "Penjumlahan"},
    parameter_untuk=_parameter,
    unik_per_lembar=True,
    domain_parameter=domain_parameter,
))
