"""Template Pengukuran bagian B: minggu dan hari, uang kembalian, panjang klip, timbangan berantai.

Didaftarkan lewat impor di `contest_templates_measurement`.
"""
from __future__ import annotations

import contest_core as C
import contest_svg_measurement as S

HARI_PER_MINGGU = 7
# --- minggu dan hari
MINGGU_MIN, MINGGU_MAKS = 2, 12
SISA_HARI_MIN, SISA_HARI_MAKS = 1, 6
CERITA_MINGGU = (
    "Nenek tinggal di rumah {nama} selama {n} minggu dan {m} hari. Berapa hari lamanya Nenek tinggal?",
    "{nama} berlibur di rumah kakek selama {n} minggu {m} hari. Berapa hari {nama} berlibur?",
    "Kakak merawat kucing selama {n} minggu {m} hari. Berapa hari Kakak merawat kucing?",
    "Pak Guru sakit selama {n} minggu {m} hari. Berapa hari Pak Guru sakit?",
)
# --- uang
RIBU = 1000
SETENGAH_RIBU = 500
HARGA_MIN, HARGA_MAKS = 1000, 9500
UANG_BAYAR = (10000, 15000, 20000, 20000, 25000, 50000)
KEMBALIAN_MIN = 1000
BENDA_BELI = ("buku tulis", "penggaris", "roti", "susu kotak", "pensil warna", "penghapus",
              "jus jeruk", "balon", "stiker", "mobil mainan")
# --- klip
KLIP_PANJANG_MIN, KLIP_PANJANG_MAKS = 2, 5
KLIP_JUMLAH_MIN, KLIP_JUMLAH_MAKS = 2, 9
# --- timbangan
RASIO_MIN, RASIO_MAKS = 2, 5
JUMLAH_RASIO = 3


# --- ukur_minggu_hari --------------------------------------------------------------------------

def _sampler_minggu_hari(rng):
    return {"nama": rng.choice(C.NAMA_ANAK), "cerita": rng.randrange(len(CERITA_MINGGU)),
            "n": rng.randint(MINGGU_MIN, MINGGU_MAKS), "m": rng.randint(SISA_HARI_MIN, SISA_HARI_MAKS)}


def _bangun_minggu_hari(p):
    n, m = p["n"], p["m"]
    hari_minggu = n * HARI_PER_MINGGU
    kunci = str(hari_minggu + m)
    pengecoh = C.ambil_pengecoh(kunci, [
        C.Pengecoh(str(hari_minggu), "lupa menambah sisa hari"),
        C.Pengecoh(str(n * m), "mengalikan banyak minggu dengan sisa hari"),
        C.Pengecoh(str(n + m), "menjumlahkan banyak minggu dengan sisa hari tanpa mengubah minggu jadi hari"),
        C.Pengecoh(str(hari_minggu - m), "mengurangi sisa hari, bukan menambah"),
        C.Pengecoh(str((n + m) * HARI_PER_MINGGU), "mengalikan 7 dengan jumlah minggu dan sisa hari"),
    ])
    cerita = CERITA_MINGGU[p["cerita"]].format(nama=p["nama"], n=n, m=m)
    return C.SoalLomba(
        template_id="ukur_minggu_hari", topik="pengukuran", jenis=C.JENIS_PG, tingkat=1,
        teks="\U0001F4C5 " + cerita, svg="", kunci=kunci, pengecoh=pengecoh,
        pembahasan=(f"1 minggu ada {HARI_PER_MINGGU} hari.",
                    f"{n} minggu = {n} x {HARI_PER_MINGGU} = {hari_minggu} hari.",
                    f"Ditambah {m} hari: {hari_minggu} + {m} = {kunci}.",
                    f"Jadi jawabannya {kunci} hari."),
        parameter=C.kanonik(p), nilai=int(kunci))


def _verifikator_minggu_hari(p):
    """Hitung hari satu per satu: tiap minggu 7 hari, lalu sisa hari."""
    total = 0
    for _ in range(p["n"]):
        total += sum(1 for _hari in range(7))
    total += sum(1 for _hari in range(p["m"]))
    return str(total)


C.daftarkan(C.Template(id="ukur_minggu_hari", topik="pengukuran", jenis=C.JENIS_PG, tingkat=1,
                       sampler=_sampler_minggu_hari, bangun=_bangun_minggu_hari,
                       verifikator=_verifikator_minggu_hari))


# --- ukur_uang_kembalian -----------------------------------------------------------------------

def _rupiah(nilai: int) -> str:
    """Rp dengan titik ribuan: 9500 -> Rp9.500; ejaan sama di semua pilihan."""
    return "Rp" + f"{nilai:,}".replace(",", ".")


def _sampler_uang(rng):
    benda = rng.sample(BENDA_BELI, 2)
    harga = [rng.randrange(HARGA_MIN, HARGA_MAKS + 1, SETENGAH_RIBU) for _ in range(2)]
    if all(h % RIBU == 0 for h in harga):
        harga[1] += SETENGAH_RIBU
    layak = [u for u in UANG_BAYAR if u >= sum(harga) + KEMBALIAN_MIN]
    if not layak:
        raise C.ParameterTidakSah("uang bayar tidak cukup untuk kembalian")
    return {"nama": rng.choice(C.NAMA_ANAK), "benda": benda, "harga": harga, "bayar": rng.choice(layak)}


def _pengecoh_uang(bayar: int, harga, kembali: int):
    total = sum(harga)
    kandidat = [
        (bayar - harga[0], "mengurangi uang bayar hanya dengan harga benda pertama"),
        (bayar - harga[1], "mengurangi uang bayar hanya dengan harga benda kedua"),
        (kembali - RIBU, "salah meminjam ribuan saat mengurangi, kurang seribu"),
        (kembali + RIBU, "salah meminjam ribuan saat mengurangi, lebih seribu"),
        (total, "menjawab jumlah harga, bukan kembalian"),
        (kembali + SETENGAH_RIBU, "salah menghitung sisa lima ratus rupiah, lebih"),
        (kembali - SETENGAH_RIBU, "salah menghitung sisa lima ratus rupiah, kurang"),
    ]
    return [C.Pengecoh(_rupiah(nilai), label) for nilai, label in kandidat if nilai > 0]


def _bangun_uang(p):
    harga, bayar = p["harga"], p["bayar"]
    total = harga[0] + harga[1]
    kembali = bayar - total
    if kembali < KEMBALIAN_MIN:
        raise C.ParameterTidakSah("kembalian terlalu kecil")
    kunci = _rupiah(kembali)
    pengecoh = C.ambil_pengecoh(kunci, _pengecoh_uang(bayar, harga, kembali))
    b1, b2 = p["benda"]
    return C.SoalLomba(
        template_id="ukur_uang_kembalian", topik="pengukuran", jenis=C.JENIS_PG, tingkat=2,
        teks=f"{p['nama']} membeli {b1} seharga {_rupiah(harga[0])} dan {b2} seharga "
             f"{_rupiah(harga[1])}. {p['nama']} membayar dengan uang {_rupiah(bayar)}. "
             f"Berapa uang kembalian {p['nama']}?",
        svg="", kunci=kunci, pengecoh=pengecoh,
        pembahasan=(f"Jumlah harga = {_rupiah(harga[0])} + {_rupiah(harga[1])} = {_rupiah(total)}.",
                    f"Kembalian = {_rupiah(bayar)} - {_rupiah(total)} = {kunci}.",
                    f"Jadi uang kembaliannya {kunci}."),
        parameter=C.kanonik(p), nilai=None)


def _verifikator_uang(p):
    """Cari kembalian k (kelipatan 500) yang membuat harga + k tepat sama dengan uang bayar."""
    bayar, harga = p["bayar"], p["harga"]
    k = next(k for k in range(0, bayar + 1, 500) if sum(harga) + k == bayar)
    ribuan, sisa = divmod(k, 1000)
    return f"Rp{ribuan}.{sisa:03d}" if ribuan else f"Rp{sisa}"


C.daftarkan(C.Template(id="ukur_uang_kembalian", topik="pengukuran", jenis=C.JENIS_PG, tingkat=2,
                       sampler=_sampler_uang, bangun=_bangun_uang, verifikator=_verifikator_uang))


# --- ukur_panjang_klip -------------------------------------------------------------------------

def _sampler_klip(rng):
    a = rng.randint(KLIP_JUMLAH_MIN, KLIP_JUMLAH_MAKS)
    b = rng.choice([n for n in range(KLIP_JUMLAH_MIN, KLIP_JUMLAH_MAKS + 1) if n != a])
    return {"k": rng.randint(KLIP_PANJANG_MIN, KLIP_PANJANG_MAKS), "benda": rng.sample(sorted(S.BENDA_KLIP), 2),
            "klip": [a, b], "tanya": rng.choice(("selisih", "total"))}


def _pengecoh_klip(k: int, a: int, b: int, tanya: str):
    selisih, jumlah = abs(a - b), a + b
    if tanya == "selisih":
        kandidat = [(selisih, "menghitung selisih banyak klip tanpa mengalikan panjang satu klip"),
                    (jumlah * k, "menjumlahkan panjang kedua benda, bukan mencari selisih"),
                    (max(a, b) * k, "menjawab panjang benda yang lebih panjang saja"),
                    (min(a, b) * k, "menjawab panjang benda yang lebih pendek saja"),
                    (jumlah, "menjumlahkan banyak klip tanpa mengalikan panjang satu klip")]
    else:
        kandidat = [(jumlah, "menjumlahkan banyak klip tanpa mengalikan panjang satu klip"),
                    (selisih * k, "mencari selisih panjang, bukan jumlahnya"),
                    (max(a, b) * k, "menjawab panjang benda yang lebih panjang saja"),
                    (min(a, b) * k, "menjawab panjang benda yang lebih pendek saja"),
                    (jumlah * k + k, "menghitung satu klip terlalu banyak")]
    return [C.Pengecoh(f"{nilai} cm", label) for nilai, label in kandidat if nilai > 0]


def _bangun_klip(p):
    k, (a, b) = p["k"], p["klip"]
    nama_a, nama_b = p["benda"]
    kunci_nilai = abs(a - b) * k if p["tanya"] == "selisih" else (a + b) * k
    kunci = f"{kunci_nilai} cm"
    pengecoh = C.ambil_pengecoh(kunci, _pengecoh_klip(k, a, b, p["tanya"]))
    if p["tanya"] == "selisih":
        tanya = f"Berapa cm selisih panjang {nama_a} dan {nama_b}?"
        langkah = f"Selisih klip = {max(a, b)} - {min(a, b)} = {abs(a - b)} klip."
        hitung = f"Selisih panjang = {abs(a - b)} x {k} = {kunci_nilai} cm."
    else:
        tanya = "Kedua benda disambung lurus. Berapa cm panjang seluruhnya?"
        langkah = f"Jumlah klip = {a} + {b} = {a + b} klip."
        hitung = f"Panjang seluruhnya = {a + b} x {k} = {kunci_nilai} cm."
    return C.SoalLomba(
        template_id="ukur_panjang_klip", topik="pengukuran", jenis=C.JENIS_PG, tingkat=2,
        teks=f"Satu klip kertas panjangnya {k} cm. {nama_a.capitalize()} dan {nama_b} diukur memakai "
             f"klip seperti pada gambar. {tanya}",
        svg=S.gambar_klip([nama_a, nama_b], [a, b]), kunci=kunci, pengecoh=pengecoh,
        pembahasan=(f"Banyak klip pada gambar: {nama_a} {a} klip, {nama_b} {b} klip.", langkah, hitung,
                    f"Jadi jawabannya {kunci}."),
        parameter=C.kanonik(p), nilai=None)


def _verifikator_klip(p):
    """Susun klip satu per satu sebagai senti: tiap klip menambah k cm pada benda masing-masing."""
    panjang = [0, 0]
    for indeks, jumlah in enumerate(p["klip"]):
        for _ in range(jumlah):
            panjang[indeks] += p["k"]
    hasil = abs(panjang[0] - panjang[1]) if p["tanya"] == "selisih" else panjang[0] + panjang[1]
    return f"{hasil} cm"


C.daftarkan(C.Template(id="ukur_panjang_klip", topik="pengukuran", jenis=C.JENIS_PG, tingkat=2,
                       sampler=_sampler_klip, bangun=_bangun_klip, verifikator=_verifikator_klip))


# --- ukur_timbangan_berantai -------------------------------------------------------------------

def _sampler_rantai(rng):
    urutan = list(range(JUMLAH_RASIO))
    rng.shuffle(urutan)
    return {"objek": rng.sample(sorted(S.BUAH), JUMLAH_RASIO + 1),
            "rasio": [rng.randint(RASIO_MIN, RASIO_MAKS) for _ in range(JUMLAH_RASIO)],
            "urutan": urutan}


def _langkah_rantai(objek, rasio, kunci: str):
    baris = [f"1 {objek[i]} = {rasio[i]} {objek[i + 1]}." for i in range(JUMLAH_RASIO)]
    bagian = [f"{rasio[i]}" for i in range(JUMLAH_RASIO)]
    kali = " x ".join(bagian)
    return (baris[0] + " " + baris[1] + " " + baris[2],
            f"1 {objek[0]} diganti terus sampai {objek[-1]}: banyaknya dikali di setiap langkah.",
            f"{kali} = {kunci}.", f"Jadi 1 {objek[0]} sama dengan {kunci} {objek[-1]}.")


def _bangun_rantai(p):
    objek, (r1, r2, r3) = p["objek"], p["rasio"]
    hasil = r1
    for rasio in (r2, r3):
        hasil *= rasio
    kunci = str(hasil)
    pengecoh = C.ambil_pengecoh(kunci, [
        C.Pengecoh(str(r1 + r2 + r3), "menjumlahkan semua banyaknya, bukan mengalikan"),
        C.Pengecoh(str(r1 * r2), "mengalikan sebagian saja, berhenti setelah dua baris pertama"),
        C.Pengecoh(str(r2 * r3), "mengalikan sebagian saja, melupakan baris pertama"),
        C.Pengecoh(str(r1), "memakai satu baris saja"),
        C.Pengecoh(str(r1 * r3), "melewati baris tengah saat mengalikan"),
    ])
    return C.SoalLomba(
        template_id="ukur_timbangan_berantai", topik="pengukuran", jenis=C.JENIS_PG, tingkat=3,
        teks=f"Semua timbangan pada gambar seimbang. Berapa banyak {objek[-1]} yang beratnya sama "
             f"dengan 1 {objek[0]}?",
        svg=S.gambar_rantai(objek, p["rasio"], p["urutan"]), kunci=kunci, pengecoh=pengecoh,
        pembahasan=_langkah_rantai(objek, p["rasio"], kunci), parameter=C.kanonik(p), nilai=hasil)


def _verifikator_rantai(p):
    """Beri berat 1 pada benda terkecil, lalu cari berat tiap benda di atasnya dengan mencoba bilangan."""
    r1, r2, r3 = p["rasio"]
    berat_a = next(wa for wc in range(1, 200) if wc == r3 * 1
                   for wb in range(1, 400) if wb == r2 * wc
                   for wa in range(1, 800) if wa == r1 * wb)
    return str(berat_a)


C.daftarkan(C.Template(id="ukur_timbangan_berantai", topik="pengukuran", jenis=C.JENIS_PG, tingkat=3,
                       sampler=_sampler_rantai, bangun=_bangun_rantai, verifikator=_verifikator_rantai))
