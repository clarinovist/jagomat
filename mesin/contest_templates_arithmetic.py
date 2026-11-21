"""Template topik Operasi Hitung untuk Latihan Lomba (bagian 1 dari 2).

Berisi: ops_hitung_gambar, ops_kaki_hewan, ops_kotak_kosong, ops_berbagi_sisa, ops_deret_pasangan,
ops_ayam_kambing. Lima template lain (cerita, umur, jumlah-selisih, dua berbahasa Inggris) ada di
`contest_templates_arithmetic_b.py`, diimpor di akhir modul ini supaya ikut terdaftar.

Setiap `_bangun` memakai rumus langsung; setiap verifikator menghitung ulang kunci dengan cara kedua
(simulasi, enumerasi, atau brute-force) tanpa memakai helper `_bangun`.
"""
from __future__ import annotations

import contest_core as C
import contest_svg_arithmetic as G

TOPIK = "operasi"
TANDA = {"+": "+", "-": "−"}

# ---------------------------------------------------------------- ops_hitung_gambar (tingkat 1, pg)
BENDA_HITUNG = (
    ("stroberi", "\U0001F353"), ("apel", "\U0001F34E"), ("jeruk", "\U0001F34A"),
    ("kue", "\U0001F9C1"), ("bola", "⚽"),
)
POLA_OPERATOR = (("+", "-"), ("+", "-"), ("-", "+"), ("+", "+"), ("-", "-"))
KELOMPOK_MIN, KELOMPOK_MAKS = 2, 12
PERCOBAAN_SAMPLER = 50


def _terapkan(kiri: int, tanda: str, kanan: int) -> int:
    return kiri + kanan if tanda == "+" else kiri - kanan


def _balik(tanda: str) -> str:
    return "-" if tanda == "+" else "+"


def _sampler_hitung(rng):
    for _ in range(PERCOBAAN_SAMPLER):
        operator = list(rng.choice(POLA_OPERATOR))
        jumlah = [rng.randint(KELOMPOK_MIN + 2, KELOMPOK_MAKS),
                  rng.randint(KELOMPOK_MIN, KELOMPOK_MAKS - 3),
                  rng.randint(KELOMPOK_MIN, KELOMPOK_MAKS - 3)]
        langkah1 = _terapkan(jumlah[0], operator[0], jumlah[1])
        if langkah1 >= 1 and _terapkan(langkah1, operator[1], jumlah[2]) >= 1:
            return {"benda": rng.randrange(len(BENDA_HITUNG)), "n": jumlah, "op": operator}
    raise C.ParameterTidakSah("kelompok benda tidak menghasilkan hitungan positif")


def _bangun_hitung(p):
    nama, emoji = BENDA_HITUNG[p["benda"]]
    a, b, c = p["n"]
    o1, o2 = p["op"]
    langkah1 = _terapkan(a, o1, b)
    hasil = _terapkan(langkah1, o2, c)
    kunci = str(hasil)
    pengecoh = C.ambil_pengecoh(kunci, [
        C.Pengecoh(str(_terapkan(langkah1, _balik(o2), c)),
                   f"membalik tanda operasi kedua ({langkah1} {TANDA[_balik(o2)]} {c})"),
        C.Pengecoh(str(_terapkan(_terapkan(a, _balik(o1), b), o2, c)),
                   f"membalik tanda operasi pertama ({a} {TANDA[_balik(o1)]} {b} dulu)"),
        C.Pengecoh(str(langkah1), "berhenti setelah langkah pertama, lupa langkah kedua"),
        C.Pengecoh(str(hasil - 1), "salah hitung, kurang satu dari hasil sebenarnya"),
        C.Pengecoh(str(hasil + 1), "salah hitung, lebih satu dari hasil sebenarnya"),
        C.Pengecoh(str(_terapkan(_terapkan(a, _balik(o1), b), _balik(o2), c)),
                   "membalik kedua tanda operasi"),
    ])
    return C.SoalLomba(
        template_id="ops_hitung_gambar", topik=TOPIK, jenis=C.JENIS_PG, tingkat=1,
        teks=f"Berapa hasilnya? Hitung dari kiri ke kanan. Hasilnya = ... {nama}",
        svg=G.gambar_hitung(nama, emoji, p["n"], p["op"]), kunci=kunci, pengecoh=pengecoh,
        pembahasan=(
            f"Hitung gambar dari kiri ke kanan: {a} {TANDA[o1]} {b} {TANDA[o2]} {c}.",
            f"Langkah pertama: {a} {TANDA[o1]} {b} = {langkah1}.",
            f"Langkah kedua: {langkah1} {TANDA[o2]} {c} = {hasil}.",
            f"Jadi hasilnya {kunci} {nama}.",
        ),
        parameter=C.kanonik(p), nilai=hasil)


def _verifikator_hitung(p):
    tumpukan = ["x"] * p["n"][0]
    for tanda, banyak in zip(p["op"], p["n"][1:]):
        if tanda == "+":
            tumpukan.extend(["x"] * banyak)
        else:
            if banyak > len(tumpukan):
                raise ValueError("benda yang diambil lebih banyak dari yang ada")
            del tumpukan[:banyak]
    return str(len(tumpukan))


C.daftarkan(C.Template(id="ops_hitung_gambar", topik=TOPIK, jenis=C.JENIS_PG, tingkat=1,
                       sampler=_sampler_hitung, bangun=_bangun_hitung,
                       verifikator=_verifikator_hitung))

# ---------------------------------------------------------------- ops_kaki_hewan (tingkat 1, pg)
HEWAN_DUA_KAKI = (("ayam", "\U0001F413"), ("bebek", "\U0001F986"))
HEWAN_EMPAT_KAKI = (("sapi", "\U0001F404"), ("kambing", "\U0001F410"), ("kucing", "\U0001F408"))
EMOJI_HEWAN = dict(HEWAN_DUA_KAKI + HEWAN_EMPAT_KAKI)
KAKI_HEWAN = dict([(nama, 2) for nama, _ in HEWAN_DUA_KAKI]
                  + [(nama, 4) for nama, _ in HEWAN_EMPAT_KAKI])
DUA_MAKS, EMPAT_MAKS = 6, 5


def _sampler_kaki(rng):
    dua = [rng.choice(HEWAN_DUA_KAKI)[0], rng.randint(1, DUA_MAKS)]
    empat = [rng.choice(HEWAN_EMPAT_KAKI)[0], rng.randint(1, EMPAT_MAKS)]
    daftar = [dua, empat]
    rng.shuffle(daftar)
    return {"daftar": daftar}


def _bangun_kaki(p):
    daftar = [(nama, banyak) for nama, banyak in p["daftar"]]
    kaki = [banyak * KAKI_HEWAN[nama] for nama, banyak in daftar]
    kepala = sum(banyak for _, banyak in daftar)
    hasil = sum(kaki)
    kunci = str(hasil)
    dua = next(k for (nama, _), k in zip(daftar, kaki) if KAKI_HEWAN[nama] == 2)
    empat = next(k for (nama, _), k in zip(daftar, kaki) if KAKI_HEWAN[nama] == 4)
    pengecoh = C.ambil_pengecoh(kunci, [
        C.Pengecoh(str(kepala), "menghitung banyak hewan, bukan banyak kaki"),
        C.Pengecoh(str(kepala * 4), "mengira semua hewan berkaki 4"),
        C.Pengecoh(str(kepala * 2), "mengira semua hewan berkaki 2"),
        C.Pengecoh(str(empat), "lupa menghitung kaki hewan berkaki 2"),
        C.Pengecoh(str(dua), "lupa menghitung kaki hewan berkaki 4"),
    ])
    langkah = tuple(f"{banyak} {nama} × {KAKI_HEWAN[nama]} kaki = {banyak * KAKI_HEWAN[nama]} kaki."
                    for nama, banyak in daftar)
    return C.SoalLomba(
        template_id="ops_kaki_hewan", topik=TOPIK, jenis=C.JENIS_PG, tingkat=1,
        teks="Berapa banyak kaki semua hewan ini?",
        svg=G.gambar_hewan([(nama, EMOJI_HEWAN[nama], banyak) for nama, banyak in daftar]),
        kunci=kunci, pengecoh=pengecoh,
        pembahasan=langkah + (
            f"Jumlah semua kaki: {kaki[0]} + {kaki[1]} = {hasil}.",
            f"Jadi semua hewan itu punya {kunci} kaki.",
        ),
        parameter=C.kanonik(p), nilai=hasil)


def _verifikator_kaki(p):
    hewan = [nama for nama, banyak in p["daftar"] for _ in range(banyak)]
    berkaki_empat = sum(1 for nama in hewan if nama in ("sapi", "kambing", "kucing"))
    return str(2 * len(hewan) + 2 * berkaki_empat)


C.daftarkan(C.Template(id="ops_kaki_hewan", topik=TOPIK, jenis=C.JENIS_PG, tingkat=1,
                       sampler=_sampler_kaki, bangun=_bangun_kaki, verifikator=_verifikator_kaki))

# ---------------------------------------------------------------- ops_kotak_kosong (tingkat 2, pg)
LAMBANG = ("\U0001F381", "\U0001F34E", "⚽", "\U0001F36A", "\U0001F9F8")
NILAI_MIN, NILAI_MAKS = 2, 15
KALI_MIN, KALI_MAKS = 2, 9
GESER_MIN, GESER_MAKS = 3, 25


def _sampler_kotak(rng):
    nilai = rng.randint(NILAI_MIN, NILAI_MAKS)
    kali = rng.randint(KALI_MIN, KALI_MAKS)
    geser = rng.randint(GESER_MIN, GESER_MAKS)
    bentuk = rng.choice(("kurang", "tambah"))
    if bentuk == "kurang" and nilai * kali <= geser:
        raise C.ParameterTidakSah("hasil pengurangan harus positif")
    hasil = nilai * kali - geser if bentuk == "kurang" else nilai * kali + geser
    return {"lambang": rng.randrange(len(LAMBANG)), "a": kali, "b": geser, "c": hasil,
            "bentuk": bentuk, "balik": rng.randrange(2)}


def _bangun_kotak(p):
    lambang, a, b, c = LAMBANG[p["lambang"]], p["a"], p["b"], p["c"]
    kurang = p["bentuk"] == "kurang"
    sebelum_bagi = c + b if kurang else c - b
    nilai = sebelum_bagi // a
    kunci = str(nilai)
    salah_balik = (c - b) if kurang else (c + b)
    kandidat = [
        C.Pengecoh(str(salah_balik // a) if salah_balik % a == 0 else "0",
                   "membalik operasi dengan tanda yang salah, lalu membagi"),
        C.Pengecoh(str(sebelum_bagi), f"berhenti sebelum membagi dengan {a}"),
        C.Pengecoh(str(c // a) if c % a == 0 else "0", f"mengabaikan {b}, hanya membagi {c} dengan {a}"),
        C.Pengecoh(str(salah_balik), "salah membalik operasi dan lupa membagi"),
        C.Pengecoh(str(nilai - 1), "hasil bagi meleset kurang satu"),
        C.Pengecoh(str(nilai + 1), "hasil bagi meleset lebih satu"),
    ]
    pengecoh = C.ambil_pengecoh(kunci, kandidat)
    tanda = "−" if kurang else "+"
    kali_teks = f"{lambang} × {a}" if p["balik"] == 0 else f"{a} × {lambang}"
    balik_tanda = "+" if kurang else "−"
    return C.SoalLomba(
        template_id="ops_kotak_kosong", topik=TOPIK, jenis=C.JENIS_PG, tingkat=2,
        teks=f"{kali_teks} {tanda} {b} = {c}. Nilai {lambang} adalah ...", svg="",
        kunci=kunci, pengecoh=pengecoh,
        pembahasan=(
            f"Persamaannya: {kali_teks} {tanda} {b} = {c}.",
            f"Balik langkah terakhir: {c} {balik_tanda} {b} = {sebelum_bagi}, jadi {kali_teks} = {sebelum_bagi}.",
            f"Balik perkalian: {sebelum_bagi} ÷ {a} = {nilai}.",
            f"Cek: {nilai} × {a} {tanda} {b} = {c}. Jadi nilai {lambang} adalah {kunci}.",
        ),
        parameter=C.kanonik(p), nilai=nilai)


def _verifikator_kotak(p):
    for coba in range(1, 201):
        kiri = coba * p["a"] - p["b"] if p["bentuk"] == "kurang" else coba * p["a"] + p["b"]
        if kiri == p["c"]:
            return str(coba)
    raise ValueError("tidak ada nilai 1..200 yang cocok")


C.daftarkan(C.Template(id="ops_kotak_kosong", topik=TOPIK, jenis=C.JENIS_PG, tingkat=2,
                       sampler=_sampler_kotak, bangun=_bangun_kotak, verifikator=_verifikator_kotak))

# ---------------------------------------------------------------- ops_berbagi_sisa (tingkat 2, isian)
BENDA_BAGI = (
    ("kue", "\U0001F9C1"), ("permen", "\U0001F36C"), ("apel", "\U0001F34E"),
    ("jeruk", "\U0001F34A"), ("cokelat", "\U0001F36B"), ("biskuit", "\U0001F36A"),
)
ANAK_MIN, ANAK_MAKS = 2, 6
PER_ANAK_MIN, PER_ANAK_MAKS = 2, 9
AMBIL_MIN, AMBIL_MAKS = 1, 5
AWAL_MAKS = 40


def _sampler_bagi(rng):
    anak = rng.randint(ANAK_MIN, ANAK_MAKS)
    per_anak = rng.randint(PER_ANAK_MIN, PER_ANAK_MAKS)
    ambil = rng.randint(AMBIL_MIN, AMBIL_MAKS)
    awal = per_anak * anak + ambil
    if awal > AWAL_MAKS:
        raise C.ParameterTidakSah("benda terlalu banyak untuk digambar")
    return {"benda": rng.randrange(len(BENDA_BAGI)), "awal": awal, "ambil": ambil, "anak": anak}


def _bangun_bagi(p):
    nama, emoji = BENDA_BAGI[p["benda"]]
    awal, ambil, anak = p["awal"], p["ambil"], p["anak"]
    sisa = awal - ambil
    if sisa % anak != 0:
        raise C.ParameterTidakSah("sisa tidak habis dibagi")
    tiap = sisa // anak
    kunci = str(tiap)
    return C.SoalLomba(
        template_id="ops_berbagi_sisa", topik=TOPIK, jenis=C.JENIS_ISIAN, tingkat=2,
        teks=(f"Ibu mengambil {ambil} {nama}. Sisanya dibagi sama rata untuk {anak} anak. "
              f"Setiap anak mendapat berapa {nama}? Tulis jawabanmu dengan angka."),
        svg=G.gambar_bagi(nama, emoji, awal, anak), kunci=kunci, pengecoh=(),
        pembahasan=(
            f"Semua {nama} ada {awal} (hitung gambarnya).",
            f"Ibu mengambil {ambil}, sisanya {awal} − {ambil} = {sisa}.",
            f"Sisa dibagi sama rata untuk {anak} anak: {sisa} ÷ {anak} = {tiap}.",
            f"Jadi setiap anak mendapat {kunci} {nama}.",
        ),
        parameter=C.kanonik(p), nilai=tiap)


def _verifikator_bagi(p):
    terima = [0] * p["anak"]
    for urutan in range(p["awal"] - p["ambil"]):
        terima[urutan % p["anak"]] += 1
    if len(set(terima)) != 1:
        raise ValueError("pembagian tidak sama rata")
    return str(terima[0])


C.daftarkan(C.Template(id="ops_berbagi_sisa", topik=TOPIK, jenis=C.JENIS_ISIAN, tingkat=2,
                       sampler=_sampler_bagi, bangun=_bangun_bagi, verifikator=_verifikator_bagi))

# ---------------------------------------------------------------- ops_deret_pasangan (tingkat 3, pg)
BEDA_DERET = (1, 2, 3, 4, 5, 10)
SUKU_DERET = (6, 8, 10, 12)       # genap, supaya tiap suku punya pasangan


def _sampler_deret(rng):
    beda = rng.choice(BEDA_DERET)
    awal = rng.choice((beda, beda, 1, rng.randint(1, 2 * beda)))
    return {"awal": awal, "beda": beda, "suku": rng.choice(SUKU_DERET)}


def _bangun_deret(p):
    awal, beda, suku = p["awal"], p["beda"], p["suku"]
    akhir = awal + (suku - 1) * beda
    ujung = awal + akhir
    pasang = suku // 2
    total = ujung * pasang
    kunci = str(total)
    pengecoh = C.ambil_pengecoh(kunci, [
        C.Pengecoh(str(ujung * suku), "mengalikan jumlah ujung dengan banyak suku, bukan banyak pasangan"),
        C.Pengecoh(str(ujung * (pasang - 1)), "lupa satu pasangan"),
        C.Pengecoh(str(ujung * (pasang + 1)), "menghitung satu pasangan terlalu banyak"),
        C.Pengecoh(str(total - akhir), "suku terakhir tertinggal saat menjumlah"),
        C.Pengecoh(str(total + beda), "salah menjumlah satu suku"),
        C.Pengecoh(str(ujung), "hanya menjumlah satu pasangan"),
    ])
    deret = " + ".join(str(awal + indeks * beda) for indeks in range(suku))
    return C.SoalLomba(
        template_id="ops_deret_pasangan", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
        teks=f"{deret} = ...", svg="", kunci=kunci, pengecoh=pengecoh,
        pembahasan=(
            f"Pasangkan suku paling depan dengan paling belakang: {awal} + {akhir} = {ujung}.",
            f"Pasangan berikutnya sama jumlahnya: {awal + beda} + {akhir - beda} = {ujung}.",
            f"Ada {suku} suku, jadi ada {suku} ÷ 2 = {pasang} pasangan.",
            f"Jumlah semuanya: {pasang} × {ujung} = {total}.",
            f"Jadi hasilnya {kunci}.",
        ),
        parameter=C.kanonik(p), nilai=total)


def _verifikator_deret(p):
    total, suku_ini = 0, p["awal"]
    for _ in range(p["suku"]):
        total += suku_ini
        suku_ini += p["beda"]
    return str(total)


C.daftarkan(C.Template(id="ops_deret_pasangan", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
                       sampler=_sampler_deret, bangun=_bangun_deret, verifikator=_verifikator_deret))

# ---------------------------------------------------------------- ops_ayam_kambing (tingkat 3, isian)
KEPALA_MIN, KEPALA_MAKS = 8, 20


def _sampler_ayam_kambing(rng):
    dua = rng.choice(HEWAN_DUA_KAKI)[0]
    empat = rng.choice(HEWAN_EMPAT_KAKI)[0]
    kepala = rng.randint(KEPALA_MIN, KEPALA_MAKS)
    jumlah_empat = rng.randint(2, kepala - 2)
    return {"dua": dua, "empat": empat, "kepala": kepala,
            "kaki": 2 * (kepala - jumlah_empat) + 4 * jumlah_empat}


def _bangun_ayam_kambing(p):
    dua, empat, kepala, kaki = p["dua"], p["empat"], p["kepala"], p["kaki"]
    kurang = kaki - 2 * kepala
    if kurang < 2 or kurang % 2 != 0:
        raise C.ParameterTidakSah("kaki tidak cocok dengan kepala")
    jumlah_empat = kurang // 2
    kunci = str(jumlah_empat)
    return C.SoalLomba(
        template_id="ops_ayam_kambing", topik=TOPIK, jenis=C.JENIS_ISIAN, tingkat=3,
        teks=(f"Di kandang ada {dua} {EMOJI_HEWAN[dua]} dan {empat} {EMOJI_HEWAN[empat]}. "
              f"Ada {kepala} kepala dan {kaki} kaki. Berapa ekor {empat}? Tulis jawabanmu dengan angka."),
        svg="", kunci=kunci, pengecoh=(),
        pembahasan=(
            f"Andaikan semua {kepala} hewan itu {dua} (2 kaki): {kepala} × 2 = {2 * kepala} kaki.",
            f"Kaki sebenarnya {kaki}, jadi kurang {kaki} − {2 * kepala} = {kurang} kaki.",
            f"Tiap {empat} punya 2 kaki lebih banyak dari {dua} (4 − 2 = 2).",
            f"Banyak {empat} = {kurang} ÷ 2 = {jumlah_empat}.",
            f"Jadi ada {kunci} ekor {empat}.",
        ),
        parameter=C.kanonik(p), nilai=jumlah_empat)


def _verifikator_ayam_kambing(p):
    cocok = [empat for empat in range(0, p["kepala"] + 1)
             if 2 * (p["kepala"] - empat) + 4 * empat == p["kaki"]]
    if len(cocok) != 1:
        raise ValueError(f"pembagian hewan tidak tunggal: {cocok}")
    return str(cocok[0])


C.daftarkan(C.Template(id="ops_ayam_kambing", topik=TOPIK, jenis=C.JENIS_ISIAN, tingkat=3,
                       sampler=_sampler_ayam_kambing, bangun=_bangun_ayam_kambing,
                       verifikator=_verifikator_ayam_kambing))

import contest_templates_arithmetic_b  # noqa: E402,F401  (mendaftarkan lima template sisanya)
