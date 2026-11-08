"""Nilai tempat dan membandingkan bilangan untuk Bilangan Dasar P1/P2 (teks saja).

Malrule adalah HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis
pasti dari satu jawaban. Modul ini hanya berisi template dan enumerator
domain; pendaftaran topik ada di `topic_basic_numbers`.

nilai_tempat memakai skema parameter seragam `{bentuk, bilangan}`: puluhan dan
satuan diturunkan dari bilangan (N = 10 * puluhan + satuan).
"""
from __future__ import annotations

from functools import lru_cache

from templates import Malrule, Soal, saring_malrule

BENTUK_TEMPAT = ("tanya_satuan", "tanya_puluhan", "susun")
# P1: tanya_satuan 11..19, susun 10..20 (tanya_puluhan selalu 1: degeneratif).
# P2: ketiga bentuk untuk 21..99.
RENTANG_TEMPAT = {
    "P1": {"tanya_satuan": range(11, 20), "susun": range(10, 21)},
    "P2": {bentuk: range(21, 100) for bentuk in BENTUK_TEMPAT},
}
# Domain bandingkan P1: bilangan 1..20, selisih paling jauh 6 (pasangan dekat
# yang menguji pemahaman); "=" untuk setiap bilangan -> 20 dari 218 (9,2%).
BATAS_P1 = 20
SELISIH_P1 = 6
# Domain bandingkan P2: bilangan 10..100.
PULUHAN_P2 = range(1, 10)
SELISIH_SATUAN_P2 = 2   # sama puluhan: selisih satuan <= 2
SELISIH_LINTAS_P2 = 4   # beda puluhan berdekatan: selisih <= 4 (satuan melompat)
JARAK_PULUHAN_P2 = 2    # beda puluhan jauh: selisih puluhan >= 2
SATUAN_JAUH_P2 = (9, 1)  # satuan bilangan kecil, satuan bilangan besar
BILANGAN_SERATUS = (99, 98, 91, 90, 80, 50)


# ── nilai_tempat ────────────────────────────────────────────────────────

def _domain_tempat(level):
    return tuple({"bentuk": bentuk, "bilangan": n}
                 for bentuk, rentang in RENTANG_TEMPAT[level].items()
                 for n in rentang)


def _tempat_sah(bentuk, bilangan):
    if type(bilangan) is not int or bentuk not in BENTUK_TEMPAT:
        return False
    return any(bentuk in rentang and bilangan in rentang[bentuk]
               for rentang in RENTANG_TEMPAT.values())


def _pembahasan_tempat(bentuk, n):
    puluhan, satuan = divmod(n, 10)
    kunci = {"tanya_satuan": satuan, "tanya_puluhan": puluhan, "susun": n}[bentuk]
    if bentuk == "susun":
        return (f"{puluhan} puluhan = {10 * puluhan}. Lalu {10 * puluhan} + {satuan} = {n}. "
                f"Jadi bilangannya {kunci}.")
    nama = "satuannya" if bentuk == "tanya_satuan" else "puluhannya"
    return (f"{n} = {puluhan} puluhan dan {satuan} satuan, karena {10 * puluhan} + {satuan} = {n}. "
            f"Jadi {nama} {kunci}.")


def _malrule_tempat(bentuk, n):
    puluhan, satuan = divmod(n, 10)
    if bentuk == "susun":
        return [
            Malrule("nilai_tempat.susun_dibalik", str(10 * satuan + puluhan), "K",
                    "Menulis satuan lebih dulu lalu puluhan, sehingga kedua angkanya terbalik."),
            Malrule("nilai_tempat.susun_dijumlah", str(puluhan + satuan), "K",
                    "Menjumlahkan banyak puluhan dan banyak satuan, bukan menyusunnya menjadi bilangan."),
            Malrule("nilai_tempat.puluhan_meleset", str(n + 10), "H",
                    "Salah menghitung banyak puluhan sehingga bilangan yang disusun lebih sepuluh."),
        ]
    tertukar = satuan if bentuk == "tanya_puluhan" else puluhan
    ditanya = "puluhan" if bentuk == "tanya_puluhan" else "satuan"
    return [
        Malrule("nilai_tempat.puluhan_satuan_tertukar", str(tertukar), "K",
                "Menjawab dengan angka di tempat yang lain, puluhan tertukar dengan satuan."),
        Malrule("nilai_tempat.nilai_bukan_banyak", str(10 * puluhan), "K",
                f"Menulis {10 * puluhan}, yaitu nilai dari {puluhan} puluhan, "
                f"padahal yang ditanya banyak {ditanya}."),
        Malrule("nilai_tempat.bilangan_utuh", str(n), "K",
                "Menulis seluruh bilangan di kotak, padahal yang ditanya hanya satu bagiannya."),
    ]


def nilai_tempat(bentuk: str, bilangan: int) -> Soal:
    """Satu isian angka: banyak satuan, banyak puluhan, atau bilangan yang tersusun."""
    if not _tempat_sah(bentuk, bilangan):
        raise ValueError("parameter nilai tempat di luar domain")
    puluhan, satuan = divmod(bilangan, 10)
    teks, kunci = {
        "tanya_satuan": (f"Bilangan {bilangan} terdiri dari {puluhan} puluhan dan ... satuan.", satuan),
        "tanya_puluhan": (f"Bilangan {bilangan} terdiri dari ... puluhan dan {satuan} satuan.", puluhan),
        "susun": (f"{puluhan} puluhan dan {satuan} satuan membentuk bilangan ...", bilangan),
    }[bentuk]
    return Soal(
        template_id="nilai_tempat", parameter={"bentuk": bentuk, "bilangan": bilangan},
        teks=teks, kunci=str(kunci),
        malrule=saring_malrule(str(kunci), _malrule_tempat(bentuk, bilangan)),
        pembahasan=_pembahasan_tempat(bentuk, bilangan), bagian="D",
    )


# ── bandingkan_bilangan ─────────────────────────────────────────────────

def _simbol(a, b):
    return "<" if a < b else (">" if a > b else "=")


def _pasangan_p1():
    unik = {(a, b) for a in range(1, BATAS_P1 + 1) for b in range(1, BATAS_P1 + 1)
            if abs(a - b) <= SELISIH_P1}
    return unik


def _pasangan_p2():
    """Tak berurut (x < y), lalu dua arah; "=" untuk 10..100."""
    tak_berurut = set()
    for t in PULUHAN_P2:
        dasar = 10 * t
        for i in range(10):
            for j in range(i + 1, min(10, i + SELISIH_SATUAN_P2 + 1)):
                tak_berurut.add((dasar + i, dasar + j))
    for x in range(10, 100):
        for y in range(x + 1, x + SELISIH_LINTAS_P2 + 1):
            if y < 100 and x // 10 != y // 10:
                tak_berurut.add((x, y))
    for p in range(1, 10):          # angka dibalik: 12 dan 21, 35 dan 53
        for s in range(p + 1, 10):
            tak_berurut.add((10 * p + s, 10 * s + p))
    bawah, atas = SATUAN_JAUH_P2
    for t in PULUHAN_P2:            # beda puluhan jauh
        for u in range(t + JARAK_PULUHAN_P2, 10):
            tak_berurut.add((10 * t + bawah, 10 * u + atas))
    for n in BILANGAN_SERATUS:
        tak_berurut.add((n, 100))
    dua_arah = {(x, y) for x, y in tak_berurut} | {(y, x) for x, y in tak_berurut}
    return dua_arah | {(n, n) for n in range(10, 101)}


@lru_cache(maxsize=None)
def _domain_banding(level):
    pasangan = _pasangan_p1() if level == "P1" else _pasangan_p2()
    return tuple(sorted(pasangan))


def _domain_bandingkan(level):
    return tuple({"a": a, "b": b} for a, b in _domain_banding(level))


@lru_cache(maxsize=None)
def _semua_pasangan():
    return frozenset(_domain_banding("P1")) | frozenset(_domain_banding("P2"))


def _kata_banding(a, b):
    return "lebih kecil dari" if a < b else "lebih besar dari"


def _pembahasan_banding(a, b):
    simbol = _simbol(a, b)
    if a == b:
        return f"{a} dan {b} sama besar, jadi {a} = {b}."
    akhir = f"{a} {_kata_banding(a, b)} {b}, jadi {a} {simbol} {b}."
    if min(a, b) < 10:
        if max(a, b) < 10:
            kecil, besar = min(a, b), max(a, b)
            return (f"Saat membilang 1, 2, 3, dan seterusnya, {kecil} disebut lebih dulu "
                    f"daripada {besar}. {akhir}")
        return (f"{min(a, b)} belum sampai 10, sedangkan {max(a, b)} sudah 10 atau lebih. {akhir}")
    pa, pb = a // 10, b // 10
    if pa != pb:
        return (f"Bandingkan puluhannya dulu: {pa} puluhan dan {pb} puluhan. "
                f"Karena {pa} {_kata_banding(pa, pb)} {pb}, maka {akhir}")
    return (f"Puluhannya sama, yaitu {pa}. Bandingkan satuannya: {a % 10} dan {b % 10}. "
            f"Karena {a % 10} {_kata_banding(a % 10, b % 10)} {b % 10}, maka {akhir}")


def _malrule_banding(a, b, kunci):
    if kunci == "=":
        return [
            Malrule("bandingkan_bilangan.sama_dikira_kurang", "<", "K",
                    "Mengira dua bilangan yang sama besar pasti berbeda, sehingga memilih tanda lebih kecil."),
            Malrule("bandingkan_bilangan.sama_dikira_lebih", ">", "K",
                    "Mengira dua bilangan yang sama besar pasti berbeda, sehingga memilih tanda lebih besar."),
        ]
    kandidat = []
    # Prioritas: dugaan yang spesifik (banding satuan) mengalahkan arah terbalik
    # bila jawabannya sama, mis. 35 dan 53.
    if min(a, b) >= 10 and a // 10 != b // 10:
        kandidat.append(Malrule(
            "bandingkan_bilangan.banding_satuan", _simbol(a % 10, b % 10), "K",
            "Membandingkan angka satuannya saja, bukan puluhannya, sehingga tandanya salah."))
    kandidat.append(Malrule(
        "bandingkan_bilangan.arah_terbalik", ">" if kunci == "<" else "<", "K",
        "Tertukar arah tanda: mulut tanda menghadap bilangan yang lebih kecil, bukan yang lebih besar."))
    return kandidat


def bandingkan_bilangan(a: int, b: int) -> Soal:
    """Isi tanda <, >, atau = di antara dua bilangan pada domain eksplisit."""
    if type(a) is not int or type(b) is not int or (a, b) not in _semua_pasangan():
        raise ValueError("parameter membandingkan di luar domain")
    kunci = _simbol(a, b)
    return Soal(
        template_id="bandingkan_bilangan", parameter={"a": a, "b": b},
        teks=f"Isi dengan <, >, atau =: {a} ... {b}", kunci=kunci,
        malrule=saring_malrule(kunci, _malrule_banding(a, b, kunci)),
        pembahasan=_pembahasan_banding(a, b), bagian="E",
    )
