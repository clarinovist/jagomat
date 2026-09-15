"""Paket topik aritmatika-lanjut — Fase 4 plan 30 Aug 2026.

11 template menutup cakupan aritmatika terapan OSN SD: konversi satuan
& kecepatan (bagian A), perbandingan (B), kerja sama (C), persen (D).
Level P5/P6 (P3/P4 tidak didukung).
"""

from __future__ import annotations

import random

from templates import Malrule, Soal, putar, saring_malrule
from topics import Topik, daftarkan


# ── Latar cerita berputar (gelombang 2, 2 Sep 2026) ────────────────────
#
# Delapan dari sebelas template paket ini dulu punya SATU cerita yang
# ditulis mati di f-string: kota A–B, Alif & Budi, sepatu, baju, "sebuah
# barang", pekerja. Terukur: aritmatika-lanjut P5 hanya 18 bentuk kalimat
# dan P6 22 — di bawah ambang 25 yang dipakai menyebut satu topik×level
# tidak lagi monoton.
#
# Yang TIDAK diberi latar, dan alasannya: `satuan_konversi`,
# `kecepatan_jarak_waktu`, dan `debit`. Ketiganya sudah punya banyak
# varian (8, 3, 3) sehingga kalimatnya tidak mati, dan dua yang terakhir
# adalah perintah hitung berbesaran — membungkusnya dalam cerita menambah
# beban baca yang bukan sedang diuji.
#
# Latar dipilih dari PARAMETER lewat templates.putar, bukan rng: lihat
# docstring fungsi itu untuk tiga kontraknya beserta kerusakan yang
# dicegah masing-masing.

# Kota untuk soal perjalanan. Sengaja nama FIKTIF, bukan kota nyata:
# generator menghasilkan jarak 40–480 km dari parameter, jadi pasangan
# kota nyata akan sering memuat jarak yang salah ("Bogor–Sukabumi 480
# km"). Soal yang faktanya keliru mengajari anak hal keliru dan membuat
# guru ragu pada seluruh lembar — nama fiktif menghindari klaim itu
# tanpa mengurangi satu pun bentuk kalimat.
_RUTE = (
    ("Kota Melati", "Kota Cendana"),
    ("Kota Anggrek", "Kota Kenanga"),
    ("Desa Sukamaju", "Kota Mawar"),
    ("Kota Bahari", "Kota Rimba"),
    ("Kota Delima", "Kota Seroja"),
)


# ── Bagian A — Konversi & kecepatan ────────────────────────────────────


def satuan_konversi(varian: str, nilai: int) -> Soal:
    """Konversi satuan: km↔m, jam↔menit, kg↔g, liter↔ml.

    Varian: "km_ke_m", "m_ke_km", "jam_ke_menit", "menit_ke_jam",
    "kg_ke_g", "g_ke_kg", "liter_ke_ml", "ml_ke_liter".
    """
    tabel = {
        "km_ke_m": ("km", "m", "×", 1000),
        "m_ke_km": ("m", "km", "÷", 1000),
        "jam_ke_menit": ("jam", "menit", "×", 60),
        "menit_ke_jam": ("menit", "jam", "÷", 60),
        "kg_ke_g": ("kg", "g", "×", 1000),
        "g_ke_kg": ("g", "kg", "÷", 1000),
        "liter_ke_ml": ("liter", "ml", "×", 1000),
        "ml_ke_liter": ("ml", "liter", "÷", 1000),
    }
    src, dst, op, factor = tabel[varian]
    if op == "×":
        kunci = nilai * factor
        mal = [
            Malrule("konversi.salah_arah", str(nilai // factor), "K", f"membagi {nilai} dengan {factor} padahal {src}→{dst} dikali"),
            Malrule("konversi.lupa_faktor", str(nilai), "K", "tidak mengubah nilai — lupa faktor konversi"),
            Malrule("konversi.kurang_satu", str(kunci - 1), "H", "konversi benar, hasilnya meleset satu"),
        ]
    else:
        if nilai % factor != 0:
            kunci = nilai // factor  # integer division
        else:
            kunci = nilai // factor
        mal = [
            Malrule("konversi.salah_arah", str(nilai * factor), "K", f"mengali {nilai} dengan {factor} padahal {src}→{dst} dibagi"),
            Malrule("konversi.lupa_faktor", str(nilai), "K", "tidak mengubah nilai — lupa faktor konversi"),
            Malrule("konversi.kurang_satu", str(kunci - 1), "H", "konversi benar, hasilnya meleset satu"),
        ]
    teks = f"Konversikan {nilai} {src} ke {dst}."
    return Soal(
        "satuan_konversi",
        {"varian": varian, "nilai": nilai},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: turun satu tangga satuan DIKALI 10, naik DIBAGI 10. "
            f"Hasilnya {kunci}."
        ),
        bagian="A",
    )


def kecepatan_jarak_waktu(varian: str, s: int, t: int, v: int) -> Soal:
    """v = s/t; dua arah: cari v, s, atau t. Semua bilangan bulat."""
    if varian == "cari_v":
        kunci = s // t
        teks = f"Jarak {s} km ditempuh dalam {t} jam. Berapa kecepatan rata-rata (km/jam)?"
        terbalik = t // s if s > 0 else t  # t/s salah arah
        salah_rumus = s * t
    elif varian == "cari_s":
        kunci = v * t
        teks = f"Kecepatan {v} km/jam selama {t} jam. Berapa jarak yang ditempuh (km)?"
        terbalik = v // t if t > 0 else v  # v/t salah arah
        salah_rumus = v + t
    else:
        kunci = s // v
        teks = f"Jarak {s} km ditempuh dengan kecepatan {v} km/jam. Berapa waktu tempuh (jam)?"
        terbalik = v // s if s > 0 else v  # v/s salah arah
        salah_rumus = s * v
    # jaga supaya malrule tidak menebak kunci
    if terbalik == kunci:
        terbalik = kunci + 1
    if salah_rumus == kunci:
        salah_rumus = kunci + 1
    mal = [
        Malrule("kec.t_terbalik", str(terbalik), "K", "rumus terbalik — membagi yang seharusnya dikali/dikali yang seharusnya dibagi"),
        Malrule("kec.salah_rumus", str(salah_rumus), "K", "memakai rumus yang salah untuk besaran yang diminta"),
        Malrule("kec.kurang_satu", str(kunci - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "kecepatan_jarak_waktu",
        {"varian": varian, "s": s, "t": t, "v": v},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: jarak = kecepatan x waktu; kecepatan = jarak : waktu; "
            f"waktu = jarak : kecepatan. Hasilnya {kunci}."
        ),
        bagian="A",
    )


def berpapasan(jarak: int, v1: int, v2: int) -> Soal:
    """Waktu bertemu dua kendaraan saling berhadapan = jarak/(v1+v2)."""
    kunci = jarak // (v1 + v2)
    mal = [
        Malrule("berpapasan.jumlah_kecepatan", str(v1 + v2), "K", "menjawab jumlah kecepatan, bukan waktu bertemu"),
        Malrule("berpapasan.dikali_kecepatan", str(jarak // (v1 * v2)) if jarak % (v1 * v2) == 0 else str(v1 * v2), "K", "mengalikan dua kecepatan padahal waktu = jarak/(v1+v2)"),
        Malrule("berpapasan.kurang_satu", str(kunci - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    asal, tujuan = putar(_RUTE, jarak, v1)
    kendaraan1, kendaraan2 = putar(
        (
            ("Mobil", "bus"),
            ("Bus", "truk"),
            ("Sepeda motor", "mobil"),
            ("Truk", "mobil"),
            ("Mobil", "sepeda motor"),
        ),
        v1,
        v2,
    )
    teks = (
        f"Jarak {asal} dan {tujuan} {jarak} km. {kendaraan1} dari "
        f"{asal} melaju {v1} km/jam dan {kendaraan2} dari {tujuan} melaju "
        f"{v2} km/jam, saling berhadapan. Berapa jam mereka akan berpapasan?"
    )
    return Soal(
        "berpapasan",
        {"jarak": jarak, "v1": v1, "v2": v2},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: berlawanan arah, kecepatan DIJUMLAH. "
            f"Waktu = jarak : jumlah kecepatan = {kunci}."
        ),
        bagian="A",
    )


def menyusul(jarak: int, v1: int, v2: int) -> Soal:
    """Waktu menyusul = jarak_awal/(v2−v1), v2 > v1."""
    kunci = jarak // (v2 - v1)
    k1 = v2 - v1
    k2 = jarak // (v1 + v2)
    h = kunci - 1
    # jaga supaya K tidak menabrak kunci atau H (setelah saring)
    if k1 == kunci or k1 == h:
        k1 = kunci + 1
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = kunci + 2
    mal = [
        Malrule("menyusul.kurang_satu", str(h), "H", "perhitungan benar, hasilnya meleset satu"),
        Malrule("menyusul.selisih_kecepatan", str(k1), "K", "menjawab selisih kecepatan, bukan waktu menyusul"),
        Malrule("menyusul.dikira_berpapasan", str(k2), "K", "memakai rumus berpapasan (v1+v2) padahal yang satu mengejar"),
    ]
    # Semua pilihan harus sahih untuk v ∈ 40..80 km/jam (lihat
    # _parameter). Pelari/pesepeda sempat dicoba dan DIBUANG: "pelari
    # melaju 78 km/jam" adalah fakta yang salah, dan soal yang faktanya
    # keliru mengajari anak hal keliru.
    pengejar, dikejar = putar(
        (
            ("Sepeda motor", "mobil"),
            ("Mobil", "truk"),
            ("Bus", "truk"),
            ("Mobil balap", "bus"),
            ("Ambulans", "mobil box"),
        ),
        v1,
        v2,
    )
    asal, _ = putar(_RUTE, jarak, v2)
    teks = (
        f"{pengejar} dari {asal} melaju {v2} km/jam mengejar "
        f"{dikejar} yang sudah berjalan {v1} km/jam dan unggul {jarak} km. "
        f"Berapa jam waktu yang dibutuhkan untuk menyusul?"
    )
    return Soal(
        "menyusul",
        {"jarak": jarak, "v1": v1, "v2": v2},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: searah, kecepatan DIKURANG. "
            f"Waktu = selisih jarak : selisih kecepatan = {kunci}."
        ),
        bagian="A",
    )


def debit(
    varian: str, volume: int, waktu: int, d: int | None = None,
    *, debit: int | None = None,
) -> Soal:
    """Debit = volume/waktu; alias tersimpan dibaca tanpa mengubah parameter lama."""
    if debit is not None:
        if type(debit) is not int or debit <= 0 or (d is not None and d != debit):
            raise ValueError("parameter debit tidak sah atau berkonflik")
        d = debit
    if type(d) is not int or d <= 0:
        raise ValueError("parameter debit harus bilangan bulat positif")
    if varian == "cari_debit":
        kunci = volume // waktu
        teks = f"Volume {volume} liter mengalir dalam {waktu} menit. Berapa debitnya (liter/menit)?"
        salah = volume * waktu
    elif varian == "cari_volume":
        kunci = d * waktu
        teks = f"Debit {d} liter/menit selama {waktu} menit. Berapa volume yang mengalir (liter)?"
        salah = d + waktu
    else:
        kunci = volume // d
        teks = f"Volume {volume} liter dengan debit {d} liter/menit. Berapa waktu (menit)?"
        salah = volume * d
    if salah == kunci:
        salah = kunci + 1
    mal = [
        Malrule("debit.salah_rumus", str(salah), "K", "memakai rumus yang salah untuk besaran yang diminta"),
        Malrule("debit.lupa_bagi", str(volume // d if varian == "cari_volume" else d * waktu if varian == "cari_waktu" else volume), "K", "lupa membagi/mengalikan dengan waktu"),
        Malrule("debit.kurang_satu", str(kunci - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "debit",
        {"varian": varian, "volume": volume, "waktu": waktu, "debit": d},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: debit = volume : waktu, jadi volume = debit x waktu "
            f"dan waktu = volume : debit. Hasilnya {kunci}."
        ),
        bagian="A",
    )


def perbandingan_senilai(p: int, q: int, n: int) -> Soal:
    """p:q = n:x → x = q·n/p. Senilai (searah)."""
    kunci = (q * n + p - 1) // p
    h = kunci - 1
    k = (p * n + q - 1) // q
    if k == kunci or k == h:
        k = kunci + 1
    mal = [
        Malrule("senilai.kurang_satu", str(h), "H", "perhitungan benar, hasilnya meleset satu"),
        Malrule("senilai.terbalik", str(k), "K", "perbandingan dibalik — senilai searah, bukan kebalikan"),
        Malrule("senilai.selisih", str(abs(q - p)), "B", "menjawab selisih pembanding, bukan nilai yang dicari"),
    ]
    benda, satuan1, satuan2 = putar(
        (
            ("adonan kue", "gelas tepung", "gelas gula"),
            ("cat tembok", "kaleng putih", "kaleng biru"),
            ("sirop", "sendok gula", "gelas air"),
            ("pupuk", "kilogram urea", "kilogram kompos"),
            ("beton", "ember semen", "ember pasir"),
        ),
        p,
        q,
    )
    teks = (
        f"Untuk membuat {benda}, perbandingan {satuan1} dan {satuan2} "
        f"adalah {p} : {q}. Jika {satuan1} yang dipakai {n}, berapa "
        f"{satuan2} yang diperlukan?"
    )
    return Soal(
        "perbandingan_senilai",
        {"p": p, "q": q, "n": n},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: perbandingan SENILAI - kalau satu naik, yang lain "
            f"ikut naik. Kalikan silang lalu bagi. Hasilnya {kunci}."
        ),
        bagian="B",
    )


def perbandingan_berbalik(a1: int, b1: int, a2: int) -> Soal:
    """a1·b1 = a2·b2 → b2 = a1·b1/a2. Berbalik (kebalikan)."""
    kunci = (a1 * b1 + a2 - 1) // a2
    h = kunci - 1
    k = (a2 * b1 + a1 - 1) // a1
    if k == kunci or k == h:
        k = kunci + 1
    mal = [
        Malrule("berbalik.kurang_satu", str(h), "H", "perhitungan benar, hasilnya meleset satu"),
        Malrule("berbalik.terbalik", str(k), "K", "memakai perbandingan senilai padahal ini berbalik nilai"),
        Malrule("berbalik.jumlah", str(a1 + b1), "B", "menjumlahkan dua besaran, padahal yang dicari hasil kali dibagi"),
    ]
    pelaku, pekerjaan, satuan = putar(
        (
            ("pekerja", "menyelesaikan sebuah bangunan", "hari"),
            ("mesin jahit", "menyelesaikan pesanan seragam", "hari"),
            ("traktor", "membajak seluruh sawah", "hari"),
            ("tukang cat", "mengecat sebuah gedung", "hari"),
            ("kran", "mengisi sebuah kolam", "jam"),
        ),
        a1,
        b1,
    )
    teks = (
        f"Jika {a1} {pelaku} dapat {pekerjaan} dalam {b1} {satuan}, "
        f"berapa {satuan} waktu yang dibutuhkan {a2} {pelaku} "
        f"(semakin banyak semakin cepat)?"
    )
    return Soal(
        "perbandingan_berbalik",
        {"a1": a1, "b1": b1, "a2": a2},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: perbandingan BERBALIK nilai - kalau satu naik, yang "
            f"lain turun. Kalikan lurus lalu bagi. Hasilnya {kunci}."
        ),
        bagian="B",
    )


def kerja_bersama(a: int, b: int) -> Soal:
    """Waktu bersama = a·b/(a+b)."""
    kunci = (a * b + a + b - 1) // (a + b)
    mal = [
        Malrule("kerja.jumlah_waktu", str(a + b), "K", "menjumlahkan dua waktu, padahal waktu bersama = a·b/(a+b)"),
        Malrule("kerja.kali_waktu", str(a * b), "K", "mengalikan dua waktu, padahal harus dibagi jumlahnya"),
        Malrule("kerja.kurang_satu", str(kunci - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    orang1, orang2, pekerjaan = putar(
        (
            ("Alif", "Budi", "menyelesaikan sebuah pekerjaan"),
            ("Rani", "Sinta", "menyelesaikan jahitan seragam"),
            ("Pak Tono", "Pak Dedi", "mengecat pagar sekolah"),
            ("Dika", "Tio", "membersihkan halaman"),
            ("Mesin A", "Mesin B", "mencetak seluruh buku"),
        ),
        a,
        b,
    )
    teks = (
        f"{orang1} dapat {pekerjaan} dalam {a} jam, {orang2} dalam {b} "
        f"jam. Jika bekerja bersama, berapa jam waktu yang dibutuhkan?"
    )
    return Soal(
        "kerja_bersama",
        {"a": a, "b": b},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: ubah ke bagian per jam (1/a + 1/b), lalu waktu "
            f"bersama = 1 dibagi hasilnya = {kunci}."
        ),
        bagian="C",
    )


def persen_diskon(harga: int, d: int) -> Soal:
    """Harga setelah diskon d% = harga·(100−d)/100."""
    kunci = harga * (100 - d) // 100
    diskon = harga * d // 100
    mal = [
        Malrule("diskon.jumlah_diskon", str(diskon), "K", f"menjawab besar diskon {diskon}, bukan harga setelah diskon"),
        Malrule("diskon.lupa_persen", str(harga * (100 - d)), "K", "lupa membagi 100 — menghitung (100−d)% dari harga"),
        Malrule("diskon.kurang_satu", str(kunci - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    barang, toko = putar(
        (
            ("sepatu", "toko olahraga"),
            ("tas sekolah", "toko peralatan sekolah"),
            ("sepeda", "toko sepeda"),
            ("jam tangan", "toko jam"),
            ("kipas angin", "toko elektronik"),
        ),
        harga,
        d,
    )
    teks = (
        f"Di {toko}, harga {barang} {harga} rupiah mendapat diskon {d}%. "
        f"Berapa harga setelah diskon?"
    )
    return Soal(
        "persen_diskon",
        {"harga": harga, "d": d},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: setelah diskon x%, harga tinggal (100 - x)% dari "
            f"harga awal. Hasilnya {kunci}."
        ),
        bagian="D",
    )


def persen_untung_rugi(jenis: str, modal: int, persen: int) -> Soal:
    """Harga jual = modal·(100±persen)/100 (untung/rugi)."""
    pedagang, barang = putar(
        (
            ("Pak Hasan", "sekarung beras"),
            ("Bu Ratna", "sepeda bekas"),
            ("Pak Yusuf", "seekor kambing"),
            ("Bu Lastri", "satu peti mangga"),
            ("Koperasi sekolah", "sekotak buku tulis"),
        ),
        modal,
        persen,
    )
    if jenis == "untung":
        kunci = modal * (100 + persen) // 100
        teks = (
            f"{pedagang} membeli {barang} seharga {modal} rupiah, lalu "
            f"menjualnya dengan untung {persen}%. Berapa harga jualnya?"
        )
    else:
        kunci = modal * (100 - persen) // 100
        teks = (
            f"{pedagang} membeli {barang} seharga {modal} rupiah, lalu "
            f"menjualnya dengan rugi {persen}%. Berapa harga jualnya?"
        )
    laba = modal * persen // 100
    mal = [
        Malrule("untung.laba_saja", str(laba), "K", f"menjawab besar untung/rugi {laba}, bukan harga jual"),
        Malrule("untung.lupa_persen", str(modal * (100 + persen) if jenis == "untung" else modal * (100 - persen)), "K", "lupa membagi 100"),
        Malrule("untung.kurang_satu", str(kunci - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "persen_untung_rugi",
        {"jenis": jenis, "modal": modal, "persen": persen},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: untung/rugi dihitung dari harga BELI. "
            f"Harga jual = harga beli +/- (persen x harga beli) = {kunci}."
        ),
        bagian="D",
    )


def persen_bertingkat(harga: int, d1: int, d2: int) -> Soal:
    """Diskon ganda: harga·(1−d1/100)·(1−d2/100)."""
    kunci = harga * (100 - d1) * (100 - d2) // 10000
    mal = [
        Malrule("bertingkat.jumlah_diskon", str(harga * (100 - d1 - d2) // 100), "K", "menjumlahkan dua diskon — diskon ganda tidak bisa dijumlah begitu saja"),
        Malrule("bertingkat.diskon_pertama", str(harga * (100 - d1) // 100), "K", "hanya menghitung diskon pertama, diskon kedua dilupakan"),
        Malrule("bertingkat.kurang_satu", str(kunci - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    barang, acara = putar(
        (
            ("baju", "obral akhir tahun"),
            ("jaket", "cuci gudang"),
            ("sepatu sekolah", "promo awal tahun ajaran"),
            ("tas", "bazar sekolah"),
            ("payung", "diskon musim hujan"),
        ),
        harga,
        d1,
        d2,
    )
    teks = (
        f"Saat {acara}, harga {barang} {harga} rupiah didiskon {d1}%, "
        f"lalu didiskon lagi {d2}%. Berapa harga akhirnya?"
    )
    return Soal(
        "persen_bertingkat",
        {"harga": harga, "d1": d1, "d2": d2},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: diskon bertingkat dihitung BERURUTAN, bukan dijumlah. "
            f"Diskon kedua dikenakan pada harga setelah diskon pertama = {kunci}."
        ),
        bagian="D",
    )


REGISTRI_TOPIK = {
    "satuan_konversi": satuan_konversi,
    "kecepatan_jarak_waktu": kecepatan_jarak_waktu,
    "berpapasan": berpapasan,
    "menyusul": menyusul,
    "debit": debit,
    "perbandingan_senilai": perbandingan_senilai,
    "perbandingan_berbalik": perbandingan_berbalik,
    "kerja_bersama": kerja_bersama,
    "persen_diskon": persen_diskon,
    "persen_untung_rugi": persen_untung_rugi,
    "persen_bertingkat": persen_bertingkat,
}

KOMPOSISI = {
    "P5": (
        "satuan_konversi", "kecepatan_jarak_waktu",
        "debit", "perbandingan_senilai", "perbandingan_berbalik",
        "kerja_bersama", "persen_diskon",
        "satuan_konversi", "kecepatan_jarak_waktu", "persen_diskon",
    ),
    "P6": (
        "berpapasan", "menyusul",
        "perbandingan_senilai", "perbandingan_berbalik",
        "kerja_bersama", "persen_untung_rugi", "persen_bertingkat",
        "satuan_konversi", "kecepatan_jarak_waktu", "debit",
    ),
}

JUDUL_BAGIAN = {
    "A": "Bagian A — Konversi & kecepatan",
    "B": "Bagian B — Perbandingan",
    "C": "Bagian C — Kerja sama",
    "D": "Bagian D — Persen",
}

CATATAN_BAGIAN = {
    "A": "Baca dulu: km→m ×1000, jam→menit ×60, dst.",
    "B": "Senilai = searah, berbalik = kebalikan.",
    "C": "Waktu bersama = hasil kali dibagi jumlah: a×b/(a+b).",
    "D": "Diskon: harga×(100−d)%. Untung/rugi: dari modal.",
}


def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id == "satuan_konversi":
        varian = rng.choice((
            "km_ke_m", "m_ke_km", "jam_ke_menit", "menit_ke_jam",
            "kg_ke_g", "g_ke_kg", "liter_ke_ml", "ml_ke_liter",
        ))
        if varian in ("m_ke_km", "menit_ke_jam", "g_ke_kg", "ml_ke_liter"):
            # konversi bagi: pilih nilai kelipatan faktor
            faktor = {"m_ke_km": 1000, "menit_ke_jam": 60, "g_ke_kg": 1000, "ml_ke_liter": 1000}[varian]
            nilai = faktor * rng.randint(1, 500)
        else:
            nilai = rng.randint(1, 500)
        return {"varian": varian, "nilai": nilai}
    if template_id == "kecepatan_jarak_waktu":
        varian = rng.choice(("cari_v", "cari_s", "cari_t"))
        if varian == "cari_v":
            s = rng.randint(10, 500)
            t = rng.randint(1, 10)
            while s % t != 0:
                s = rng.randint(10, 500)
            return {"varian": varian, "s": s, "t": t, "v": s // t}
        if varian == "cari_s":
            v = rng.randint(2, 60)
            t = rng.randint(1, 10)
            return {"varian": varian, "s": v * t, "t": t, "v": v}
        # cari_t
        s = rng.randint(10, 500)
        v = rng.randint(2, 60)
        while s % v != 0:
            s = rng.randint(10, 500)
        return {"varian": varian, "s": s, "t": s // v, "v": v}
    if template_id == "berpapasan":
        # jarak kelipatan (v1+v2) supaya kunci bulat
        v1, v2 = rng.randint(20, 60), rng.randint(20, 60)
        jarak = (v1 + v2) * rng.randint(1, 4)
        return {"jarak": jarak, "v1": v1, "v2": v2}
    if template_id == "menyusul":
        # v2 > v1; jarak kelipatan selisih supaya kunci bulat
        v1, v2 = rng.randint(20, 50), rng.randint(40, 80)
        while v2 <= v1:
            v2 = rng.randint(40, 80)
        jarak = (v2 - v1) * rng.randint(1, 5)
        return {"jarak": jarak, "v1": v1, "v2": v2}
    if template_id == "debit":
        varian = rng.choice(("cari_debit", "cari_volume", "cari_waktu"))
        if varian == "cari_debit":
            volume = rng.randint(10, 500)
            waktu = rng.randint(1, 30)
            while volume % waktu != 0:
                volume = rng.randint(10, 500)
            return {"varian": varian, "volume": volume, "waktu": waktu, "d": volume // waktu}
        if varian == "cari_volume":
            d, waktu = rng.randint(2, 30), rng.randint(1, 30)
            return {"varian": varian, "volume": d * waktu, "waktu": waktu, "d": d}
        # cari_waktu
        volume = rng.randint(10, 500)
        d = rng.randint(2, 30)
        while volume % d != 0:
            volume = rng.randint(10, 500)
        return {"varian": varian, "volume": volume, "waktu": volume // d, "d": d}
    if template_id == "perbandingan_senilai":
        p, q = rng.randint(1, 10), rng.randint(1, 10)
        while p == q:
            q = rng.randint(1, 10)
        n = rng.randint(1, 20)
        return {"p": p, "q": q, "n": n}
    if template_id == "perbandingan_berbalik":
        a1, b1, a2 = rng.randint(2, 10), rng.randint(2, 10), rng.randint(2, 10)
        while a2 == a1:
            a2 = rng.randint(2, 10)
        return {"a1": a1, "b1": b1, "a2": a2}
    if template_id == "kerja_bersama":
        a, b = rng.randint(2, 24), rng.randint(2, 24)
        while a == b:
            b = rng.randint(2, 24)
        return {"a": a, "b": b}
    if template_id == "persen_diskon":
        # harga kelipatan 100 supaya hasil bulat
        harga = 100 * rng.randint(2, 5000)
        d = rng.randint(5, 50)
        return {"harga": harga, "d": d}
    if template_id == "persen_untung_rugi":
        jenis = rng.choice(("untung", "rugi"))
        modal = 100 * rng.randint(2, 5000)
        persen = rng.randint(5, 40)
        return {"jenis": jenis, "modal": modal, "persen": persen}
    if template_id == "persen_bertingkat":
        harga = 10000 * rng.randint(1, 500)
        d1, d2 = rng.randint(5, 40), rng.randint(5, 40)
        return {"harga": harga, "d1": d1, "d2": d2}
    raise KeyError(f"template tidak dikenal: {template_id}")


TOPIK = Topik(
    id="aritmatika-lanjut",
    nama="Aritmatika Lanjut",
    judul_lembar="Latihan Aritmatika Lanjut",
    judul_penilaian="Penilaian — Aritmatika Lanjut",
    templates=REGISTRI_TOPIK,
    komposisi=KOMPOSISI,
    profil={"P5": {}, "P6": {}},
    judul_bagian=JUDUL_BAGIAN,
    catatan_bagian=CATATAN_BAGIAN,
    parameter_untuk=_parameter,
)

daftarkan(TOPIK)