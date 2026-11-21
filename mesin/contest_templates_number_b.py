"""Template topik Bilangan untuk Latihan Lomba, bagian pola dan syarat jumlah angka (`bil_`).

Diimpor dari `contest_templates_number`; jangan diimpor sendiri. Verifikator tiap template
menghitung ulang dengan enumerasi (manik satu per satu, semua bilangan 10..99 atau 100..999,
penambahan pola langkah demi langkah), bukan dengan rumus yang dipakai `bangun`.
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Sequence

import contest_core as C
import contest_svg_number as G

TOPIK = "bilangan"
POLA_TAMPIL = 4
POLA_KE_MIN, POLA_KE_MAKS = 5, 7
SEGITIGA_KELIPATAN = (1, 2)
TAMBAH_AWAL = (1, 2, 3, 4)
TAMBAH_SELISIH = (2, 3, 4)
MANIK_PANJANG_POLA = (3, 4, 5)
MANIK_N_MIN, MANIK_N_MAKS = 20, 50
MANIK_TAMPIL_MAKS = 10
WARNA = ("merah", "biru", "kuning", "hijau")


def soal_bilangan(template_id: str, jenis: str, tingkat: int, teks: str, svg: str, kunci: str,
          pengecoh, pembahasan: Sequence[str], p: Mapping) -> C.SoalLomba:
    return C.SoalLomba(template_id=template_id, topik=TOPIK, jenis=jenis, tingkat=tingkat,
                       teks=teks, svg=svg, kunci=kunci, pengecoh=pengecoh,
                       pembahasan=tuple(pembahasan), parameter=C.kanonik(p), nilai=int(kunci))


# --- 4. bil_pola_bertambah ---------------------------------------------------------------

def _sampler_pola_bertambah(rng) -> Dict:
    n = rng.randint(POLA_KE_MIN, POLA_KE_MAKS)
    if rng.random() < 0.4:
        return {"jenis": "segitiga", "m": rng.choice(SEGITIGA_KELIPATAN), "n": n}
    return {"jenis": "tambah", "a": rng.choice(TAMBAH_AWAL), "d": rng.choice(TAMBAH_SELISIH), "n": n}


def _banyak_pola(p: Mapping, pola_ke: int) -> int:
    if p["jenis"] == "segitiga":
        return p["m"] * pola_ke * (pola_ke + 1) // 2
    return p["a"] + (pola_ke - 1) * p["d"]


def _titik_pola(p: Mapping) -> List[list]:
    if p["jenis"] == "segitiga":
        return [G.titik_segitiga(k, p["m"]) for k in range(1, POLA_TAMPIL + 1)]
    return [G.titik_kisi(_banyak_pola(p, k)) for k in range(1, POLA_TAMPIL + 1)]


def _kandidat_pola(p: Mapping, kunci: int) -> List[C.Pengecoh]:
    n = p["n"]
    terakhir = _banyak_pola(p, POLA_TAMPIL)
    selisih_akhir = terakhir - _banyak_pola(p, POLA_TAMPIL - 1)
    if p["jenis"] == "segitiga":
        m = p["m"]
        return [
            C.Pengecoh(str(terakhir + selisih_akhir * (n - POLA_TAMPIL)),
                       "mengira tiap pola menambah jumlah yang sama dengan pola terakhir yang tampak"),
            C.Pengecoh(str(m * n * (n + 1)), "lupa membagi dua pada jumlah permen satu pola"),
            C.Pengecoh(str(m * n * n), "mengira banyak permen pola ke-n adalah n kali n"),
            C.Pengecoh(str(terakhir), "menjawab banyak permen pola terakhir yang tampak"),
            C.Pengecoh(str(kunci + 1), "salah hitung lebih satu"),
        ]
    a, d = p["a"], p["d"]
    return [
        C.Pengecoh(str(kunci - d), "berhenti satu pola terlalu cepat"),
        C.Pengecoh(str(kunci + d), "menambah satu pola terlalu banyak"),
        C.Pengecoh(str(d * n), "mengalikan penambahan dengan nomor pola, lupa banyak permen awal"),
        C.Pengecoh(str(terakhir + (n - POLA_TAMPIL)), "menambah satu permen saja tiap pola"),
        C.Pengecoh(str(n * n), "mengira banyak permen pola ke-n adalah n kali n"),
        C.Pengecoh(str(a * n), "mengalikan banyak permen pola pertama dengan nomor pola"),
    ]


def _langkah_pola(p: Mapping) -> List[str]:
    n = p["n"]
    awal = [_banyak_pola(p, k) for k in range(1, POLA_TAMPIL + 1)]
    langkah = [f"Banyak permen pola 1 sampai {POLA_TAMPIL}: {', '.join(map(str, awal))}."]
    if p["jenis"] == "segitiga":
        langkah.append("Setiap pola menambah satu baris di bawahnya, jadi tambahannya makin besar.")
    else:
        langkah.append(f"Setiap pola menambah {p['d']} permen.")
    banyak = awal[-1]
    for k in range(POLA_TAMPIL + 1, n + 1):
        tambah = p["m"] * k if p["jenis"] == "segitiga" else p["d"]
        langkah.append(f"Pola {k}: {banyak} + {tambah} = {banyak + tambah}.")
        banyak += tambah
    langkah.append(f"Jadi pola ke-{n} berisi {banyak} permen.")
    return langkah


def _bangun_pola_bertambah(p: Mapping) -> C.SoalLomba:
    kunci_nilai = _banyak_pola(p, p["n"])
    kunci = str(kunci_nilai)
    pengecoh = C.ambil_pengecoh(kunci, _kandidat_pola(p, kunci_nilai))
    teks = f"Perhatikan pola permen berikut. Banyak permen pada pola ke-{p['n']} adalah ..."
    return soal_bilangan("bil_pola_bertambah", C.JENIS_PG, 2, teks, G.svg_pola_permen(_titik_pola(p)),
                 kunci, pengecoh, _langkah_pola(p), p)


def _verifikator_pola_bertambah(p: Mapping) -> str:
    if p["jenis"] == "segitiga":
        banyak = 0
        for pola_ke in range(1, p["n"] + 1):
            banyak = sum(p["m"] * baris for baris in range(1, pola_ke + 1))
        return str(banyak)
    banyak = p["a"]
    for _ in range(p["n"] - 1):
        banyak += p["d"]
    return str(banyak)


# --- 5. bil_pola_berulang ----------------------------------------------------------------

def _periode_terkecil(pola: Sequence[str]) -> int:
    panjang = len(pola)
    for periode in range(1, panjang + 1):
        if panjang % periode == 0 and list(pola) == list(pola[:periode]) * (panjang // periode):
            return periode
    return panjang


def _sampler_pola_berulang(rng) -> Dict:
    panjang = rng.choice(MANIK_PANJANG_POLA)
    warna = rng.sample(WARNA, rng.choice((2, 3)))
    pola = [rng.choice(warna) for _ in range(panjang)]
    n = rng.randint(MANIK_N_MIN, MANIK_N_MAKS)
    if len(set(pola)) < 2 or _periode_terkecil(pola) != panjang or n % panjang == 0:
        raise C.ParameterTidakSah("pola tidak jelas atau n kelipatan panjang pola")
    return {"pola": pola, "n": n, "warna": rng.choice(sorted(set(pola)))}


def _hitung_manik(pola: Sequence[str], n: int, warna: str) -> int:
    penuh, sisa = divmod(n, len(pola))
    return penuh * pola.count(warna) + list(pola[:sisa]).count(warna)


def _langkah_manik(pola: Sequence[str], n: int, warna: str) -> List[str]:
    penuh, sisa = divmod(n, len(pola))
    per_pola = pola.count(warna)
    dalam_sisa = list(pola[:sisa]).count(warna)
    kunci = penuh * per_pola + dalam_sisa
    langkah = [
        f"Pola berulang setiap {len(pola)} manik: {', '.join(pola)}.",
        f"Dalam satu pola ada {per_pola} manik {warna}.",
        f"{n} : {len(pola)} = {penuh} sisa {sisa}, jadi pola penuh ada {penuh} kali.",
        f"{penuh} x {per_pola} = {penuh * per_pola} manik {warna}.",
    ]
    if dalam_sisa:
        langkah.append(f"Sisa {sisa} manik adalah {', '.join(pola[:sisa])}, memuat "
                       f"{dalam_sisa} manik {warna}.")
    else:
        langkah.append(f"Sisa {sisa} manik adalah {', '.join(pola[:sisa])}, tidak memuat manik {warna}.")
    langkah.append(f"{penuh * per_pola} + {dalam_sisa} = {kunci}. Jadi ada {kunci} manik {warna}.")
    return langkah


def _bangun_pola_berulang(p: Mapping) -> C.SoalLomba:
    pola, n, warna = list(p["pola"]), p["n"], p["warna"]
    panjang = len(pola)
    penuh = n // panjang
    per_pola = pola.count(warna)
    kunci_nilai = _hitung_manik(pola, n, warna)
    kunci = str(kunci_nilai)
    tampil = panjang * (3 if panjang == 3 else 2)
    tergambar = [pola[i % panjang] for i in range(tampil)]
    kandidat = [
        C.Pengecoh(str(penuh * per_pola), "lupa menghitung manik pada sisa pola"),
        C.Pengecoh(str((penuh + 1) * per_pola), "membulatkan banyak pola ke atas"),
        C.Pengecoh(str(penuh * len(set(pola))),
                   "mengalikan banyak pola penuh dengan banyak warna, tanpa sisa"),
        C.Pengecoh(str(n // len(set(pola))), "mengira semua warna sama banyak"),
        C.Pengecoh(str(tergambar.count(warna)), "menghitung manik yang tergambar saja"),
        C.Pengecoh(str(kunci_nilai + 1), "salah hitung lebih satu"),
    ]
    pengecoh = C.ambil_pengecoh(kunci, kandidat)
    teks = (f"Manik-manik dirangkai berulang dengan pola yang sama. Di antara {n} manik pertama, "
            f"ada berapa manik {warna}?")
    return soal_bilangan("bil_pola_berulang", C.JENIS_PG, 3, teks, G.svg_rangkaian_manik(tergambar),
                 kunci, pengecoh, _langkah_manik(pola, n, warna), p)


def _verifikator_pola_berulang(p: Mapping) -> str:
    hitung = 0
    for urutan in range(1, p["n"] + 1):
        if p["pola"][(urutan - 1) % len(p["pola"])] == p["warna"]:
            hitung += 1
    return str(hitung)


# --- 6. bil_syarat_jumlah_angka ----------------------------------------------------------

def _sampler_syarat_jumlah_angka(rng) -> Dict:
    return {"urutan": rng.choice(("terkecil", "terbesar")), "k": rng.randint(3, 24)}


def _bilangan_tiga_angka(k: int) -> "tuple[List[int], List[int]]":
    """(angka berbeda semua, ada angka kembar) -- tiga angka berjumlah k, diurutkan naik."""
    beda, kembar = [], []
    for a in range(1, 10):
        for b in range(10):
            for c in range(10):
                if a + b + c != k:
                    continue
                (beda if len({a, b, c}) == 3 else kembar).append(100 * a + 10 * b + c)
    return sorted(beda), sorted(kembar)


def _tukar_puluhan_satuan(n: int) -> int:
    ratusan, sisa = divmod(n, 100)
    return ratusan * 100 + (sisa % 10) * 10 + sisa // 10


def _bangun_syarat_jumlah_angka(p: Mapping) -> C.SoalLomba:
    urutan, k = p["urutan"], p["k"]
    beda, kembar = _bilangan_tiga_angka(k)
    if len(beda) < 2:
        raise C.ParameterTidakSah("bilangan sah kurang dari dua")
    terkecil = urutan == "terkecil"
    kunci_nilai = beda[0] if terkecil else beda[-1]
    kunci = str(kunci_nilai)
    kandidat = []
    if kembar:
        kandidat.append(C.Pengecoh(str(kembar[0] if terkecil else kembar[-1]),
                                   "memilih bilangan yang angkanya kembar (melanggar syarat berbeda semua)"))
    kandidat.append(C.Pengecoh(str(beda[1] if terkecil else beda[-2]),
                               f"memilih bilangan sah berikutnya, bukan yang {urutan}"))
    kandidat.append(C.Pengecoh(str(_tukar_puluhan_satuan(kunci_nilai)),
                               "menukar urutan angka puluhan dan satuan"))
    kandidat.append(C.Pengecoh(str(beda[-1] if terkecil else beda[0]),
                               "memilih yang terbesar padahal diminta terkecil" if terkecil
                               else "memilih yang terkecil padahal diminta terbesar"))
    pengecoh = C.ambil_pengecoh(kunci, kandidat)
    urut = beda if terkecil else beda[::-1]
    langkah = [
        f"Angkanya harus berbeda semua dan jumlahnya {k}.",
        f"Bilangan yang memenuhi, dari yang {urutan}: {', '.join(map(str, urut[:4]))}, dan seterusnya.",
    ]
    if kembar:
        contoh = kembar[0] if terkecil else kembar[-1]
        langkah.append(f"Bilangan seperti {contoh} tidak boleh karena ada angka yang kembar.")
    langkah.append(f"Jadi bilangan tiga angka {urutan} yang memenuhi adalah {kunci}.")
    teks = (f"Bilangan tiga angka {urutan} yang angkanya berbeda semua dan jumlah angkanya {k} "
            f"adalah ...")
    return soal_bilangan("bil_syarat_jumlah_angka", C.JENIS_PG, 3, teks, "", kunci, pengecoh, langkah, p)


def _verifikator_syarat_jumlah_angka(p: Mapping) -> str:
    cocok = [n for n in range(100, 1000)
             if len(set(str(n))) == 3 and sum(map(int, str(n))) == p["k"]]
    return str(min(cocok) if p["urutan"] == "terkecil" else max(cocok))


C.daftarkan(C.Template(id="bil_pola_bertambah", topik=TOPIK, jenis=C.JENIS_PG, tingkat=2,
                       sampler=_sampler_pola_bertambah, bangun=_bangun_pola_bertambah,
                       verifikator=_verifikator_pola_bertambah))
C.daftarkan(C.Template(id="bil_pola_berulang", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
                       sampler=_sampler_pola_berulang, bangun=_bangun_pola_berulang,
                       verifikator=_verifikator_pola_berulang))
C.daftarkan(C.Template(id="bil_syarat_jumlah_angka", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
                       sampler=_sampler_syarat_jumlah_angka, bangun=_bangun_syarat_jumlah_angka,
                       verifikator=_verifikator_syarat_jumlah_angka))
