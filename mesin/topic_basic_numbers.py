"""Bilangan dasar khusus Latihan manual P1/P2, bukan target siklus.

Penjumlahan, pengurangan, dan bilangan yang hilang; teks saja. Malrule adalah
HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari satu
jawaban. Template baru tidak punya konten historis yang perlu marker
katalog/revisi. Jenis baru hanya dibuat saat `OSN_DASAR_LENGKAP=1`
(lihat `basic_numbers_versions`); pembaca selalu mengenal semuanya.
"""
from __future__ import annotations

from functools import lru_cache

from basic_numbers_versions import keterangan_level, pilih_komposisi_writer
from templates import Malrule, Soal, saring_malrule
from topics import Topik, daftarkan


PROFIL_LEVEL = {
    "P1": {"hasil": (2, 10)},
    "P2": {"hasil": (11, 20)},
}


BENTUK_HILANG = ("tambah_akhir", "tambah_awal", "kurang_akhir", "kurang_awal")
JUMLAH_TERKECIL, JUMLAH_TERBESAR = 2, 20  # gabungan P1 dan P2 untuk bilangan_hilang
BATAS_KURANG_P1 = 10
BATAS_KURANG_P2 = (11, 20)
BATAS_PENGURANG_P2 = 10
TANDA_KURANG = "−"


def _domain_tambah(level):
    bawah, atas = PROFIL_LEVEL[level]["hasil"]
    return tuple({"a": a, "b": b}
                 for a in range(1, atas)
                 for b in range(1, atas)
                 if bawah <= a + b <= atas)


def _domain_kurang(level):
    if level == "P1":
        return tuple({"a": a, "b": b}
                     for a in range(1, BATAS_KURANG_P1 + 1)
                     for b in range(1, a + 1))
    bawah, atas = BATAS_KURANG_P2
    return tuple({"a": a, "b": b}
                 for a in range(bawah, atas + 1)
                 for b in range(1, BATAS_PENGURANG_P2 + 1))


def _parameter_hilang(bentuk, x, y):
    """Bentuk a + b = c (x + y = z) -> parameter yang tampak pada soal."""
    if bentuk == "tambah_akhir":
        return {"bentuk": bentuk, "tampak": x, "hasil": x + y}
    if bentuk == "tambah_awal":
        return {"bentuk": bentuk, "tampak": y, "hasil": x + y}
    if bentuk == "kurang_akhir":
        return {"bentuk": bentuk, "tampak": x + y, "hasil": x}
    return {"bentuk": bentuk, "tampak": y, "hasil": x}


def _domain_hilang(level):
    bawah, atas = PROFIL_LEVEL[level]["hasil"]
    return tuple(_parameter_hilang(bentuk, x, z - x)
                 for bentuk in BENTUK_HILANG
                 for z in range(bawah, atas + 1)
                 for x in range(1, z))


_ENUMERATOR = {
    "tambah_dasar": _domain_tambah,
    "kurang_dasar": _domain_kurang,
    "bilangan_hilang": _domain_hilang,
}


@lru_cache(maxsize=None)
def _domain_beku(template_id: str, level: str) -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _ENUMERATOR[template_id](level))


def domain_parameter(template_id: str, level: str) -> tuple[dict, ...]:
    """Seluruh parameter sah satu jenis di satu level; dict baru setiap panggilan.

    Keputusan pengguna 30 Okt 2026: domain kecil tidak diperlebar demi variasi
    semu; cakupan diuji terhadap enumerator ini, bukan nama/benda.
    tambah_dasar: P1 45 pasangan, P2 145 (nol dikecualikan agar operasi tertukar
    tidak sama dengan kunci). kurang_dasar: P1 55 (hasil 0 sah, a - a), P2 100.
    bilangan_hilang: empat bentuk x tripel x + y = z dengan x, y >= 1 (nol
    membuat soal sepele: bilangan yang dicari sama dengan yang tampak); P1
    z 2..10 -> 180, P2 z 11..20 -> 580.
    """
    if template_id not in _ENUMERATOR:
        raise KeyError(template_id)
    if level not in PROFIL_LEVEL:
        raise ValueError("level bilangan dasar harus P1 atau P2")
    return tuple(dict(item) for item in _domain_beku(template_id, level))


def _parameter(template_id, rng, level):
    """Satu undian seragam dari domain terbatas; tanpa rejection atau nudge."""
    if template_id not in _ENUMERATOR:
        raise KeyError(template_id)
    if level not in PROFIL_LEVEL:
        raise ValueError("level bilangan dasar harus P1 atau P2")
    return dict(rng.choice(_domain_beku(template_id, level)))


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
        return (f"{a} + {b}: {besar} butuh {ambil} lagi supaya menjadi 10. "
                f"Ambil {ambil} dari {kecil}, tersisa {sisa}. "
                f"Maka 10 + {sisa} = {jumlah}.")
    if besar == 10:
        return (f"{a} + {b}: bilangan terbesarnya 10, jadi tambahkan {kecil} ke 10. "
                f"10 + {kecil} = {jumlah}.")
    satuan = besar - 10
    return (f"{a} + {b}: pecah {besar} menjadi 10 dan {satuan}. "
            f"Jumlahkan satuannya: {satuan} + {kecil} = {satuan + kecil}. "
            f"Lalu 10 + {satuan + kecil} = {jumlah}.")


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


def _kurang_sah(a, b):
    if type(a) is not int or type(b) is not int:
        return False
    if 1 <= b <= a <= BATAS_KURANG_P1:
        return True
    bawah, atas = BATAS_KURANG_P2
    return bawah <= a <= atas and 1 <= b <= BATAS_PENGURANG_P2


def _pembahasan_kurang_p2(a, b):
    kunci = a - b
    if b == BATAS_PENGURANG_P2:
        return (f"{a} {TANDA_KURANG} {b}: kurangi satu puluhan, satuannya tetap. "
                f"Jadi {a} {TANDA_KURANG} {b} = {kunci}.")
    satuan = a - 10
    if satuan >= b:
        sisa = satuan - b
        return (f"{a} {TANDA_KURANG} {b}: pecah {a} menjadi 10 dan {satuan}. "
                f"Kurangi bagian {satuan}: {satuan} {TANDA_KURANG} {b} = {sisa}. "
                f"Lalu 10 + {sisa} = {kunci}.")
    masih = b - satuan
    return (f"{a} {TANDA_KURANG} {b}: kurangi dulu sampai 10, yaitu "
            f"{a} {TANDA_KURANG} {satuan} = 10. "
            f"Masih harus dikurangi {b} {TANDA_KURANG} {satuan} = {masih}. "
            f"Lalu 10 {TANDA_KURANG} {masih} = {kunci}.")


def _pembahasan_kurang(a, b):
    kunci = a - b
    kurang = TANDA_KURANG
    if kunci == 0:
        return (f"{a} {kurang} {b}: bilangan yang dikurangkan sama besar dengan {a}, "
                f"jadi tidak ada yang tersisa. Maka {a} {kurang} {b} = 0.")
    if a > BATAS_KURANG_P1:
        return _pembahasan_kurang_p2(a, b)
    if b <= kunci:
        langkah = ", ".join(str(n) for n in range(a - 1, kunci - 1, -1))
        return (f"Mulai dari {a}, hitung mundur {b} langkah: {langkah}. "
                f"Jadi {a} {kurang} {b} = {kunci}.")
    if kunci == 1:
        return (f"{a} {kurang} {b}: dari {b} ke {a} hanya satu langkah maju. "
                f"Jadi {a} {kurang} {b} = 1.")
    langkah = ", ".join(str(n) for n in range(b + 1, a + 1))
    return (f"Mulai dari {b}, hitung maju sampai {a}: {langkah}. "
            f"Ada {kunci} langkah, jadi {a} {kurang} {b} = {kunci}.")


def kurang_dasar(a: int, b: int) -> Soal:
    """Cari hasil a - b; P1 a <= 10 (hasil 0 sah), P2 a 11..20 dan b 1..10."""
    if not _kurang_sah(a, b):
        raise ValueError("parameter pengurangan di luar domain")
    kunci = a - b
    # Urutan kandidat = prioritas saat dua jawaban sama (saring_malrule
    # mempertahankan yang pertama); a = 20 membuat satuan_dibalik sama dengan
    # operasi_tertukar sehingga yang kedua gugur.
    kandidat = [
        Malrule("kurang_dasar.operasi_tertukar", str(a + b), "K",
                "Menjumlahkan kedua bilangan, padahal tandanya kurang sehingga bilangan awal harus berkurang."),
        Malrule("kurang_dasar.hitung_mundur_dari_awal", str(kunci + 1), "H",
                "Ikut menghitung bilangan awal sebagai langkah pertama saat menghitung mundur, sehingga hasilnya lebih satu."),
    ]
    satuan = a % 10
    if a > BATAS_KURANG_P1 and satuan < b < 10:
        # Satuan kecil dikurangkan dari satuan besar (b - satuan), puluhan tetap.
        hasil = a - satuan + (b - satuan)
        kandidat.append(Malrule(
            "kurang_dasar.satuan_dibalik", str(hasil), "K",
            "Mengurangkan satuan yang kecil dari satuan yang besar tanpa meminjam puluhan, sehingga hasilnya salah."))
    return Soal(
        template_id="kurang_dasar", parameter={"a": a, "b": b},
        teks=f"{a} {TANDA_KURANG} {b} = ...", kunci=str(kunci),
        malrule=saring_malrule(str(kunci), kandidat),
        pembahasan=_pembahasan_kurang(a, b), bagian="B",
    )


def _unsur_hilang(bentuk, tampak, hasil):
    """Bilangan yang dicari dan jumlah x + y = z dari tripel bentuk itu."""
    if bentuk == "tambah_akhir" or bentuk == "tambah_awal":
        return hasil - tampak, hasil
    if bentuk == "kurang_akhir":
        return tampak - hasil, tampak
    if bentuk == "kurang_awal":
        return tampak + hasil, tampak + hasil
    raise ValueError("bentuk bilangan hilang tidak dikenal")


def _hilang_sah(bentuk, tampak, hasil):
    if (type(tampak) is not int or type(hasil) is not int
            or tampak < 1 or hasil < 1 or bentuk not in BENTUK_HILANG):
        return False
    dicari, jumlah = _unsur_hilang(bentuk, tampak, hasil)
    return dicari >= 1 and JUMLAH_TERKECIL <= jumlah <= JUMLAH_TERBESAR


def _teks_hilang(bentuk, tampak, hasil):
    kurang = TANDA_KURANG
    return {
        "tambah_akhir": f"{tampak} + ... = {hasil}",
        "tambah_awal": f"... + {tampak} = {hasil}",
        "kurang_akhir": f"{tampak} {kurang} ... = {hasil}",
        "kurang_awal": f"... {kurang} {tampak} = {hasil}",
    }[bentuk]


def _pembahasan_hilang(bentuk, tampak, hasil, dicari):
    kurang = TANDA_KURANG
    if bentuk == "tambah_akhir":
        return (f"Untuk mencari bilangan yang hilang, kurangkan: {hasil} {kurang} {tampak} = {dicari}. "
                f"Cek: {tampak} + {dicari} = {hasil}.")
    if bentuk == "tambah_awal":
        return (f"Untuk mencari bilangan yang hilang, kurangkan: {hasil} {kurang} {tampak} = {dicari}. "
                f"Cek: {dicari} + {tampak} = {hasil}.")
    if bentuk == "kurang_akhir":
        return (f"Dari {tampak} yang diambil sampai tersisa {hasil}, bilangan yang diambil adalah "
                f"{tampak} {kurang} {hasil} = {dicari}. Cek: {tampak} {kurang} {dicari} = {hasil}.")
    return (f"Setelah dikurangi {tampak}, sisanya {hasil}. Bilangan awalnya dicari dengan menjumlahkan: "
            f"{hasil} + {tampak} = {dicari}. Cek: {dicari} {kurang} {tampak} = {hasil}.")


def _malrule_operasi_tampak(bentuk, tampak, hasil):
    """Kesalahan K utama per bentuk: satu operasi langsung pada dua bilangan tampak.

    Pada `a - ... = c` operasi tertulis (a - c) justru benar, jadi bentuk itu
    memakai dugaan lain: dua bilangan yang tampak dijumlahkan.
    """
    if bentuk == "kurang_akhir":
        return Malrule(
            "bilangan_hilang.menjumlah_tampak", str(tampak + hasil), "K",
            "Menjumlahkan dua bilangan yang tampak karena mengira kotak berisi gabungan keduanya, padahal tandanya kurang.")
    terlihat = abs(hasil - tampak) if bentuk == "kurang_awal" else tampak + hasil
    return Malrule(
        "bilangan_hilang.operasi_terlihat", str(terlihat), "K",
        "Mengerjakan tanda operasi yang tertulis langsung pada dua bilangan yang tampak, tanpa memikirkan bilangan yang hilang.")


def bilangan_hilang(bentuk: str, tampak: int, hasil: int) -> Soal:
    """Isi bilangan yang hilang; `tampak` bilangan di dekat kotak, `hasil` sesudah "="."""
    if not _hilang_sah(bentuk, tampak, hasil):
        raise ValueError("parameter bilangan hilang di luar domain")
    dicari, _ = _unsur_hilang(bentuk, tampak, hasil)
    kandidat = [
        _malrule_operasi_tampak(bentuk, tampak, hasil),
        Malrule("bilangan_hilang.meleset_satu", str(dicari + 1), "H",
                "Ikut menghitung bilangan yang tampak sebagai satu langkah, sehingga bilangan yang dicari lebih satu."),
    ]
    return Soal(
        template_id="bilangan_hilang",
        parameter={"bentuk": bentuk, "tampak": tampak, "hasil": hasil},
        teks=_teks_hilang(bentuk, tampak, hasil), kunci=str(dicari),
        malrule=saring_malrule(str(dicari), kandidat),
        pembahasan=_pembahasan_hilang(bentuk, tampak, hasil, dicari),
        bagian="C",
    )


REGISTRI_TOPIK = {
    "tambah_dasar": tambah_dasar,
    "kurang_dasar": kurang_dasar,
    "bilangan_hilang": bilangan_hilang,
}

# Inventaris pembaca: semua jenis yang dikenal. Writer bawaan (sakelar mati)
# dipilih `pilih_komposisi_writer`; tambah_dasar harus tetap pertama (kartu contoh).
KOMPOSISI_PEMBACA = ("tambah_dasar", "kurang_dasar", "bilangan_hilang") * 3 + ("tambah_dasar",)


daftarkan(Topik(
    id="bilangan-dasar",
    nama="Bilangan Dasar",
    judul_lembar="Latihan Bilangan Dasar",
    judul_penilaian="Penilaian — Bilangan Dasar",
    templates=REGISTRI_TOPIK,
    komposisi={level: KOMPOSISI_PEMBACA for level in PROFIL_LEVEL},
    komposisi_writer=pilih_komposisi_writer(),
    profil=PROFIL_LEVEL,
    judul_bagian={"A": "Penjumlahan", "B": "Pengurangan", "C": "Bilangan yang hilang"},
    parameter_untuk=_parameter,
    unik_per_lembar=True,
    domain_parameter=domain_parameter,
    keterangan_level=keterangan_level(),
))
