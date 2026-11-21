"""Template topik Operasi Hitung untuk Latihan Lomba (bagian 2 dari 2).

Berisi: ops_jumlah_selisih, ops_umur, ops_cerita_dua_langkah, ops_inggris_dua_langkah,
ops_inggris_jumlah_selisih. Modul ini mandiri (hanya memakai `contest_core`) dan didaftarkan
lewat impor di `contest_templates_arithmetic.py`.
"""
from __future__ import annotations

import contest_core as C

TOPIK = "operasi"
MINUS = "−"

# ---------------------------------------------------------------- jumlah dan selisih (bersama)
PASANGAN_LAMBANG = (
    ("\U0001F34E", "\U0001F34A"), ("\U0001F431", "\U0001F436"), ("\U0001F34C", "\U0001F347"),
    ("⚽", "\U0001F3C0"), ("\U0001F430", "\U0001F43B"),
)
BENDA_JUMLAH = ("kelereng", "stiker", "kue", "permen", "pensil", "buku")
KECIL_MIN, KECIL_MAKS = 3, 20
BEDA_MIN, BEDA_MAKS = 2, 12


def _sampler_jumlah_selisih_dasar(rng):
    """(kecil, selisih, tanya); jumlah = 2 * kecil + selisih, besar = kecil + selisih."""
    kecil = rng.randint(KECIL_MIN, KECIL_MAKS)
    selisih = rng.randint(BEDA_MIN, BEDA_MAKS)
    return kecil, selisih, rng.choice(("besar", "besar", "kecil"))


def _pengecoh_jumlah_selisih(kunci: int, jumlah: int, selisih: int, tanya: str):
    besar, kecil = (jumlah + selisih) // 2, (jumlah - selisih) // 2
    separuh = [C.Pengecoh(str(jumlah // 2), "membagi jumlah dua tanpa memakai selisih")] \
        if jumlah % 2 == 0 else []
    if tanya == "besar":
        kandidat = [
            C.Pengecoh(str(jumlah - selisih), "mengurangkan selisih dari jumlah tanpa membagi dua"),
            *separuh,
            C.Pengecoh(str(kecil), "menjawab bilangan yang lebih kecil"),
            C.Pengecoh(str(jumlah + selisih), "menjumlahkan jumlah dan selisih tanpa membagi dua"),
            C.Pengecoh(str(selisih), "menjawab selisihnya saja"),
        ]
    else:
        kandidat = [
            C.Pengecoh(str(jumlah - selisih), "mengurangkan selisih dari jumlah tanpa membagi dua"),
            C.Pengecoh(str(besar), "menjawab bilangan yang lebih besar"),
            *separuh,
            C.Pengecoh(str(selisih), "menjawab selisihnya saja"),
            C.Pengecoh(str(kunci + 1), "salah hitung, lebih satu dari yang sebenarnya"),
        ]
    return C.ambil_pengecoh(str(kunci), kandidat)


def _pembahasan_jumlah_selisih(jumlah, selisih, tanya, awal_kalimat_akhir):
    besar, kecil = (jumlah + selisih) // 2, (jumlah - selisih) // 2
    if tanya == "besar":
        return (
            f"Jumlah ditambah selisih sama dengan dua kali yang besar: {jumlah} + {selisih} = {jumlah + selisih}.",
            f"Yang besar = {jumlah + selisih} ÷ 2 = {besar}.",
            f"Cek: yang kecil = {jumlah} − {besar} = {kecil}, dan {besar} − {kecil} = {selisih}.",
            f"{awal_kalimat_akhir} {besar}.",
        )
    return (
        f"Jumlah dikurangi selisih sama dengan dua kali yang kecil: {jumlah} − {selisih} = {jumlah - selisih}.",
        f"Yang kecil = {jumlah - selisih} ÷ 2 = {kecil}.",
        f"Cek: yang besar = {jumlah} − {kecil} = {besar}, dan {besar} − {kecil} = {selisih}.",
        f"{awal_kalimat_akhir} {kecil}.",
    )


def _verifikator_pasangan(p, tanya: str) -> str:
    """Enumerasi semua pasangan (a, b) bilangan asli yang berjumlah `jumlah`."""
    for a in range(1, p["jumlah"]):
        b = p["jumlah"] - a
        if a - b == p["selisih"]:
            return str(a if tanya == "besar" else b)
    raise ValueError("tidak ada pasangan yang cocok")


# ---------------------------------------------------------------- ops_jumlah_selisih (tingkat 3, pg)
def _sampler_jumlah_selisih(rng):
    kecil, selisih, tanya = _sampler_jumlah_selisih_dasar(rng)
    if rng.randrange(2) == 0:
        return {"mode": "lambang", "tanya": tanya, "jumlah": 2 * kecil + selisih, "selisih": selisih,
                "idx": rng.randrange(len(PASANGAN_LAMBANG)), "n1": "", "n2": ""}
    n1, n2 = rng.sample(C.NAMA_ANAK, 2)
    return {"mode": "cerita", "tanya": tanya, "jumlah": 2 * kecil + selisih, "selisih": selisih,
            "idx": rng.randrange(len(BENDA_JUMLAH)), "n1": n1, "n2": n2}


def _teks_jumlah_selisih(p):
    """(teks soal, awal kalimat penutup pembahasan)."""
    jumlah, selisih, tanya = p["jumlah"], p["selisih"], p["tanya"]
    if p["mode"] == "lambang":
        a, b = PASANGAN_LAMBANG[p["idx"]]
        dicari = a if tanya == "besar" else b
        return (f"{a} + {b} = {jumlah}. {a} {MINUS} {b} = {selisih}. Nilai {dicari} adalah ...",
                f"Jadi nilai {dicari} adalah")
    benda = BENDA_JUMLAH[p["idx"]]
    n1, n2 = p["n1"], p["n2"]
    pemilik = n1 if tanya == "besar" else n2
    return (f"{n1} dan {n2} punya {jumlah} {benda} bersama. {benda.capitalize()} {n1} lebih banyak "
            f"{selisih} daripada {benda} {n2}. Berapa {benda} {pemilik}?"), f"Jadi {benda} {pemilik} ada"


def _bangun_jumlah_selisih(p):
    jumlah, selisih, tanya = p["jumlah"], p["selisih"], p["tanya"]
    if (jumlah + selisih) % 2 != 0 or jumlah <= selisih:
        raise C.ParameterTidakSah("jumlah dan selisih tidak cocok")
    nilai = (jumlah + selisih) // 2 if tanya == "besar" else (jumlah - selisih) // 2
    teks, kalimat_akhir = _teks_jumlah_selisih(p)
    return C.SoalLomba(
        template_id="ops_jumlah_selisih", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
        teks=teks, svg="", kunci=str(nilai),
        pengecoh=_pengecoh_jumlah_selisih(nilai, jumlah, selisih, tanya),
        pembahasan=_pembahasan_jumlah_selisih(jumlah, selisih, tanya, kalimat_akhir),
        parameter=C.kanonik(p), nilai=nilai)


C.daftarkan(C.Template(
    id="ops_jumlah_selisih", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
    sampler=_sampler_jumlah_selisih, bangun=_bangun_jumlah_selisih,
    verifikator=lambda p: _verifikator_pasangan(p, p["tanya"])))

# ---------------------------------------------------------------- ops_inggris_jumlah_selisih (tingkat 3, pg)


def _sampler_inggris_js(rng):
    kecil, selisih, tanya = _sampler_jumlah_selisih_dasar(rng)
    return {"tanya": tanya, "jumlah": 2 * kecil + selisih, "selisih": selisih,
            "idx": rng.randrange(len(PASANGAN_LAMBANG))}


def _bangun_inggris_js(p):
    jumlah, selisih, tanya = p["jumlah"], p["selisih"], p["tanya"]
    if (jumlah + selisih) % 2 != 0 or jumlah <= selisih:
        raise C.ParameterTidakSah("jumlah dan selisih tidak cocok")
    a, b = PASANGAN_LAMBANG[p["idx"]]
    dicari = a if tanya == "besar" else b
    nilai = (jumlah + selisih) // 2 if tanya == "besar" else (jumlah - selisih) // 2
    return C.SoalLomba(
        template_id="ops_inggris_jumlah_selisih", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
        teks=f"If {a} + {b} = {jumlah} and {a} {MINUS} {b} = {selisih}, then {dicari} = ...",
        svg="", kunci=str(nilai),
        pengecoh=_pengecoh_jumlah_selisih(nilai, jumlah, selisih, tanya),
        pembahasan=_pembahasan_jumlah_selisih(jumlah, selisih, tanya, f"Jadi nilai {dicari} adalah"),
        parameter=C.kanonik(p), nilai=nilai, inggris=True)


C.daftarkan(C.Template(
    id="ops_inggris_jumlah_selisih", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
    sampler=_sampler_inggris_js, bangun=_bangun_inggris_js,
    verifikator=lambda p: _verifikator_pasangan(p, p["tanya"])))

# ---------------------------------------------------------------- ops_umur (tingkat 3, pg)
UMUR_A_MIN, UMUR_A_MAKS = 5, 14
UMUR_B_MIN, UMUR_B_MAKS = 2, 9
TAHUN_MIN, TAHUN_MAKS = 2, 12


def _sampler_umur(rng):
    n1, n2 = rng.sample(C.NAMA_ANAK, 2)
    umur1, umur2 = rng.randint(UMUR_A_MIN, UMUR_A_MAKS), rng.randint(UMUR_B_MIN, UMUR_B_MAKS)
    tahun = rng.randint(TAHUN_MIN, TAHUN_MAKS)
    return {"n1": n1, "n2": n2, "a": umur1, "b": umur2, "jumlah": umur1 + umur2 + 2 * tahun}


def _bangun_umur(p):
    a, b, jumlah = p["a"], p["b"], p["jumlah"]
    sekarang = a + b
    kurang = jumlah - sekarang
    if kurang < 4 or kurang % 2 != 0:
        raise C.ParameterTidakSah("jumlah umur tidak cocok")
    tahun = kurang // 2
    kunci = str(tahun)
    pengecoh = C.ambil_pengecoh(kunci, [
        C.Pengecoh(str(kurang), "selisih jumlah dan umur sekarang tanpa membagi dua"),
        C.Pengecoh(str(kurang // 4) if kurang % 4 == 0 else "0", "membagi selisih dengan 4, bukan 2"),
        C.Pengecoh(str(tahun - 1), "salah hitung, kurang satu tahun"),
        C.Pengecoh(str(tahun + 1), "salah hitung, lebih satu tahun"),
        C.Pengecoh(str(tahun - 2), "salah hitung, kurang dua tahun"),
    ])
    return C.SoalLomba(
        template_id="ops_umur", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
        teks=(f"{p['n1']} berumur {a} tahun. {p['n2']} berumur {b} tahun. "
              f"Berapa tahun lagi jumlah umur mereka {jumlah} tahun?"),
        svg="", kunci=kunci, pengecoh=pengecoh,
        pembahasan=(
            f"Jumlah umur sekarang: {a} + {b} = {sekarang}.",
            f"Jumlah umur harus bertambah {jumlah} − {sekarang} = {kurang}.",
            "Tiap tahun umur keduanya bertambah, jadi jumlahnya naik 2 per tahun.",
            f"Banyak tahun = {kurang} ÷ 2 = {tahun}.",
            f"Cek: ({a} + {tahun}) + ({b} + {tahun}) = {jumlah}. Jadi {kunci} tahun lagi.",
        ),
        parameter=C.kanonik(p), nilai=tahun)


def _verifikator_umur(p):
    for tahun in range(1, 200):
        if (p["a"] + tahun) + (p["b"] + tahun) == p["jumlah"]:
            return str(tahun)
    raise ValueError("tidak ada tahun yang cocok")


C.daftarkan(C.Template(id="ops_umur", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
                       sampler=_sampler_umur, bangun=_bangun_umur, verifikator=_verifikator_umur))

# ---------------------------------------------------------------- cerita dua langkah (bersama)
POLA_KURANG_TAMBAH, POLA_TAMBAH_KURANG = "kt", "tk"
AWAL_MIN, AWAL_MAKS = 20, 60
LANGKAH_MIN, LANGKAH_MAKS = 5, 25


def _sampler_langkah(rng, jumlah_aksi: int):
    """(a, b, c, pola, aksi) untuk pola a - b + c (kt) atau a + b - c (tk); tiap hasil positif."""
    pola = rng.choice((POLA_KURANG_TAMBAH, POLA_TAMBAH_KURANG))
    a = rng.randint(AWAL_MIN, AWAL_MAKS)
    b, c = rng.randint(LANGKAH_MIN, LANGKAH_MAKS), rng.randint(LANGKAH_MIN, LANGKAH_MAKS)
    if pola == POLA_KURANG_TAMBAH and a <= b:
        raise C.ParameterTidakSah("harus punya cukup untuk dikurangi")
    if pola == POLA_TAMBAH_KURANG and a + b <= c:
        raise C.ParameterTidakSah("harus punya cukup untuk dikurangi")
    return a, b, c, pola, rng.randrange(jumlah_aksi)


def _hasil_dua_langkah(a, b, c, pola):
    return a - b + c if pola == POLA_KURANG_TAMBAH else a + b - c


def _kandidat_dua_langkah(a, b, c, pola):
    """Pasangan (nilai, label kesalahan) menurut urutan kesalahan paling khas."""
    if pola == POLA_KURANG_TAMBAH:
        return [(a - b, "berhenti setelah langkah pertama, lupa langkah kedua"),
                (a - b - c, "salah tanda: mengurangi juga pada langkah kedua"),
                (a + b - c, "membalik kedua tanda"),
                (a + b + c, "menambahkan semua bilangan"),
                (a + c, "lupa langkah pertama")]
    return [(a + b, "berhenti setelah langkah pertama, lupa langkah kedua"),
            (a + b + c, "salah tanda: menambah juga pada langkah kedua"),
            (a - b + c, "membalik kedua tanda"),
            (a - b - c, "salah tanda pada langkah pertama"),
            (a - c, "lupa langkah pertama")]


def _pembahasan_dua_langkah(a, b, c, pola, kalimat_akhir):
    """Dua langkah hitung dari parameter yang sama, ditutup `kalimat_akhir` (memuat kunci)."""
    langkah1 = a - b if pola == POLA_KURANG_TAMBAH else a + b
    tanda1, tanda2 = (MINUS, "+") if pola == POLA_KURANG_TAMBAH else ("+", MINUS)
    return (
        f"Langkah pertama: {a} {tanda1} {b} = {langkah1}.",
        f"Langkah kedua: {langkah1} {tanda2} {c} = {_hasil_dua_langkah(a, b, c, pola)}.",
        kalimat_akhir,
    )


# ---------------------------------------------------------------- ops_cerita_dua_langkah (tingkat 2, pg)
SATUAN_BENDA = {"kelereng": "butir", "stiker": "lembar", "jeruk": "buah", "pensil": "batang",
                "buku": "buah", "permen": "butir"}
BENDA_CERITA = ("kelereng", "stiker", "jeruk", "pensil", "buku", "permen", "uang")
AKSI_BENDA = {
    "kt": ("{n} memberikan {b} kepada adiknya, lalu membeli {c} lagi.",
           "{n} kehilangan {b}, lalu diberi Ibu {c}.",
           "{n} menjual {b}, lalu mendapat {c} dari kakak."),
    "tk": ("{n} membeli {b} lagi, lalu memberikan {c} kepada teman.",
           "{n} diberi Nenek {b}, lalu kehilangan {c}.",
           "{n} mendapat {b} dari kakak, lalu menjual {c}."),
}
AKSI_UANG = {
    "kt": ("{n} membeli mainan seharga {b}, lalu diberi Ibu {c}.",
           "{n} jajan {b}, lalu mendapat uang saku {c} lagi.",
           "{n} membayar uang kas {b}, lalu mendapat hadiah {c}."),
    "tk": ("{n} diberi Ayah {b}, lalu membeli buku seharga {c}.",
           "{n} menabung {b} lagi, lalu jajan {c}.",
           "{n} mendapat {b} dari Nenek, lalu membeli es krim seharga {c}."),
}
RIBU = 1000


def _rupiah(ribuan: int) -> str:
    return "Rp" + f"{ribuan * RIBU:,}".replace(",", ".")


def _sampler_cerita(rng):
    a, b, c, pola, aksi = _sampler_langkah(rng, 3)
    return {"nama": rng.choice(C.NAMA_ANAK), "benda": rng.choice(BENDA_CERITA),
            "pola": pola, "aksi": aksi, "a": a, "b": b, "c": c}


def _bangun_cerita(p):
    a, b, c, pola, benda = p["a"], p["b"], p["c"], p["pola"], p["benda"]
    uang = benda == "uang"
    tampil = _rupiah if uang else (lambda n: f"{n} {SATUAN_BENDA[benda]} {benda}")
    hasil = _hasil_dua_langkah(a, b, c, pola)
    kunci = _rupiah(hasil) if uang else str(hasil)
    kandidat = [C.Pengecoh(_rupiah(n) if uang else str(n), label)
                for n, label in _kandidat_dua_langkah(a, b, c, pola) if n >= 1]
    kalimat = (AKSI_UANG if uang else AKSI_BENDA)[pola][p["aksi"]].format(
        n=p["nama"], b=tampil(b), c=tampil(c))
    awal = f"{p['nama']} punya uang {_rupiah(a)}." if uang else f"{p['nama']} punya {tampil(a)}."
    tanya = f"Berapa uang {p['nama']} sekarang?" if uang else f"Berapa {benda} {p['nama']} sekarang?"
    return C.SoalLomba(
        template_id="ops_cerita_dua_langkah", topik=TOPIK, jenis=C.JENIS_PG, tingkat=2,
        teks=f"{awal} {kalimat} {tanya}", svg="", kunci=kunci,
        pengecoh=C.ambil_pengecoh(kunci, kandidat),
        pembahasan=_pembahasan_dua_langkah(
            a, b, c, pola,
            f"Jadi uang {p['nama']} sekarang {kunci}." if uang
            else f"Jadi {benda} {p['nama']} sekarang {kunci} {SATUAN_BENDA[benda]}."),
        parameter=C.kanonik(p), nilai=None if uang else hasil)


def _verifikator_cerita(p):
    a, b, c = p["a"], p["b"], p["c"]
    for r in range(1, 1000):
        cocok = (r - c == a - b) if p["pola"] == POLA_KURANG_TAMBAH else (r + c == a + b)
        if cocok:
            return "Rp" + format(r * 1000, ",").replace(",", ".") if p["benda"] == "uang" else str(r)
    raise ValueError("tidak ada hasil yang cocok")


C.daftarkan(C.Template(id="ops_cerita_dua_langkah", topik=TOPIK, jenis=C.JENIS_PG, tingkat=2,
                       sampler=_sampler_cerita, bangun=_bangun_cerita,
                       verifikator=_verifikator_cerita))

# ---------------------------------------------------------------- ops_inggris_dua_langkah (tingkat 2, pg)
BENDA_INGGRIS = ("marbles", "stickers", "apples", "pencils", "cookies", "books")
AKSI_INGGRIS = {
    "kt": ("{n} gives away {b}, then buys {c}.",
           "{n} loses {b}, then finds {c}.",
           "{n} sells {b}, then gets {c} more."),
    "tk": ("{n} buys {b} more, then gives away {c}.",
           "{n} finds {b} more, then loses {c}.",
           "{n} gets {b} more, then sells {c}."),
}


def _sampler_inggris(rng):
    a, b, c, pola, aksi = _sampler_langkah(rng, 3)
    return {"nama": rng.choice(C.NAMA_ANAK), "benda": rng.randrange(len(BENDA_INGGRIS)),
            "pola": pola, "aksi": aksi, "a": a, "b": b, "c": c}


def _bangun_inggris(p):
    a, b, c, pola = p["a"], p["b"], p["c"], p["pola"]
    benda = BENDA_INGGRIS[p["benda"]]
    hasil = _hasil_dua_langkah(a, b, c, pola)
    kunci = str(hasil)
    kandidat = [C.Pengecoh(str(n), label)
                for n, label in _kandidat_dua_langkah(a, b, c, pola) if n >= 1]
    kalimat = AKSI_INGGRIS[pola][p["aksi"]].format(n=p["nama"], b=b, c=c)
    return C.SoalLomba(
        template_id="ops_inggris_dua_langkah", topik=TOPIK, jenis=C.JENIS_PG, tingkat=2,
        teks=f"{p['nama']} has {a} {benda}. {kalimat} How many {benda} does {p['nama']} have now?",
        svg="", kunci=kunci, pengecoh=C.ambil_pengecoh(kunci, kandidat),
        pembahasan=_pembahasan_dua_langkah(
            a, b, c, pola, f"Jadi {p['nama']} sekarang punya {kunci} {benda}."),
        parameter=C.kanonik(p), nilai=hasil, inggris=True)


def _verifikator_inggris(p):
    a, b, c = p["a"], p["b"], p["c"]
    for r in range(1, 1000):
        if (r - c == a - b) if p["pola"] == POLA_KURANG_TAMBAH else (r + c == a + b):
            return str(r)
    raise ValueError("tidak ada hasil yang cocok")


C.daftarkan(C.Template(id="ops_inggris_dua_langkah", topik=TOPIK, jenis=C.JENIS_PG, tingkat=2,
                       sampler=_sampler_inggris, bangun=_bangun_inggris,
                       verifikator=_verifikator_inggris))
