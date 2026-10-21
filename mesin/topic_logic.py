"""Paket topik logika — Fase 7 plan 30 Aug 2026.

Enam template menutup cakupan penalaran & logika OSN SD: penalaran
(bagian A), besaran & umur (B). Level P3/P5/P6. P3 selaras band SASMO
Primary 1–4 (non-routine: logic problems) — tanpa template baru,
cukup filter parameter per level di _parameter; P4 tetap di luar scope.
Soal berbentuk teks; pilihan ganda dirender sebagai daftar A-E.
"""

from __future__ import annotations

import random

from templates import Malrule, Soal, saring_malrule
from topics import Topik, daftarkan
from catalog_versions import parameter_baru, soal_berversi
from catalog_logic import soal_umur as soal_umur_diperbaiki
from catalog_versions import koreksi_soal
from catalog_diagnosis import pengandaian
from catalog_malrules import jumlah_selisih as koreksi_jumlah_selisih


# ── Bagian A — Penalaran ────────────────────────────────────────────────


@koreksi_soal(pengandaian)
def benar_salah_pengandaian(
    varian: str, nama: str, warna: str, barang: str, kelas: int,
    pilihan_benar: int, urutan_tampil: list[int] | tuple[int, ...],
) -> Soal:
    """"Jika semua X memakai Y, dan Z anggota X" — tentukan yang PASTI benar.

    Varian memilih jenis cerita; pilihan dirender A-E, kunci = huruf benar.
    urutan_tampil = posisi pernyataan di layar (dihitung di _parameter
    dengan rng deterministik — JANGAN pakai hash() di sini: hash string
    diacak per-proses dan merusak kontrak determinisme seed→soal).
    """
    opsi = ["A", "B", "C", "D", "E"]
    if varian == "warna":
        fakta = f"{nama} adalah siswa kelas {kelas}. Semua siswa kelas {kelas} memakai sepatu berwarna {warna}."
        pernyataan = [
            f"{nama} memakai sepatu berwarna {warna}.",
            f"{nama} memakai sepatu berwarna lain selain {warna}.",
            f"Semua siswa kelas {kelas} memakai sepatu berwarna lain selain {warna}.",
            f"{nama} bukan siswa kelas {kelas}.",
            "Tidak ada siswa yang memakai sepatu.",
        ]
        pembahasan = (
            f"Langkah: {nama} adalah siswa kelas {kelas}, dan semua "
            f"siswa kelas {kelas} memakai sepatu berwarna {warna}. Jadi "
            f"{nama} pasti memakai sepatu berwarna {warna}. "
            f"Jawabannya {opsi[pilihan_benar]}."
        )
    else:
        fakta = f"Setiap hari {nama} membawa bekal {barang} ke sekolah."
        pernyataan = [
            f"Hari ini {nama} membawa bekal {barang}.",
            f"Hari ini {nama} membawa bekal lain selain {barang}.",
            f"{nama} tidak pernah membawa bekal.",
            f"{nama} membawa {barang} hanya ketika tidak hujan.",
            "Tidak ada siswa yang membawa bekal.",
        ]

    # urutan_tampil: 5 posisi layar; posisi pilihan_benar = pernyataan[0]
    # (benar), sisanya pernyataan 1..4 yang diacak. Selalu panjang 5.
    kunci = opsi[pilihan_benar]
    blok = "\n".join(f"{opsi[i]}. {pernyataan[urutan_tampil[i]]}" for i in range(5))
    teks = f"{fakta}\nManakah pernyataan yang PASTI benar?\n{blok}"
    # Malrule harus mengikuti MAKNA pernyataan setelah pengacakan, bukan
    # urutan huruf salah. Cari posisi layar tiap indeks pernyataan lalu
    # petakan ke hurufnya. Ini menjaga alasan/kode tetap melekat pada
    # kesalahan yang benar meski pilihan_benar pindah A–E.
    huruf_per_pernyataan = {
        indeks: opsi[posisi]
        for posisi, indeks in enumerate(urutan_tampil)
    }
    spesifikasi_malrule = (
        (1, "pengandaian.mungkin_saja", "K",
         "memilih pernyataan yang mungkin tapi tidak pasti benar"),
        (2, "pengandaian.negasi", "K",
         "memilih pernyataan yang bertentangan dengan fakta"),
        (3, "pengandaian.salah_baca", "B",
         "salah membaca fakta — membalik arah implikasi"),
        (4, "pengandaian.ekstrem", "H",
         "memilih pernyataan yang terlalu umum/menyimpang"),
    )
    mal = [
        Malrule(rule_id, huruf_per_pernyataan[indeks], kode, alasan)
        for indeks, rule_id, kode, alasan in spesifikasi_malrule
    ]
    return Soal(
        "benar_salah_pengandaian",
        {"varian": varian, "nama": nama, "warna": warna, "barang": barang,
         "kelas": kelas, "pilihan_benar": pilihan_benar,
         "urutan_tampil": list(urutan_tampil)},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        pembahasan=pembahasan if varian == "warna" else (
            f"Langkah: dari \"setiap A adalah B\", yang PASTI benar hanya "
            f"tidak ada A yang bukan B. Kebalikannya belum tentu benar. "
            f"Jawabannya {kunci}."
        ),
        bagian="A",
    )


def _pilih_indeks(n: int, benar: int, utama: int, kedua: int):
    """Pilih indeks malrule yang dijamin saling berbeda: (K1, H, K2|None).

    `saring_malrule` membuang malrule yang nilainya kembar dengan kunci
    atau dengan malrule lain — yang PERTAMA didaftarkan menang (§7.1).
    Sebelum perbaikan ini `h` dan `k2` sering menunjuk orang yang SAMA:
    K menang, lalu k2 ditambal string "orang lain" sehingga jalur K mati
    (anak tak mungkin menulis "orang lain"), dan anak yang salah konsep
    justru divonis H "meleset satu posisi".

    Dengan 3 nama hanya tersedia 2 pengecoh, sedangkan kode butuh 3 —
    secara matematis mustahil. Prioritasnya K1 lalu H (dua kode berbeda
    lebih berharga daripada dua K yang sama), K2 hanya kalau masih ada
    ruang. Nilai yang dipakai selalu nama nyata dari cerita.
    """
    dipakai = {benar}

    def ambil(pilihan: int):
        if 0 <= pilihan < n and pilihan not in dipakai:
            dipakai.add(pilihan)
            return pilihan
        for j in range(n):
            if j not in dipakai:
                dipakai.add(j)
                return j
        return None

    i_k1 = ambil(utama)
    # H = posisi bersebelahan dengan kunci ("meleset satu"), beda dari K1.
    i_h = None
    for kandidat in (benar + 1, benar - 1):
        if 0 <= kandidat < n and kandidat not in dipakai:
            dipakai.add(kandidat)
            i_h = kandidat
            break
    if i_h is None:
        i_h = ambil(benar + 1)
    i_k2 = ambil(kedua)
    # n >= 3 di semua pemanggil, jadi K1 dan H selalu dapat jatah; hanya
    # K2 yang boleh kosong. assert menahan kontrak itu supaya perubahan
    # komposisi di _parameter tidak diam-diam menghasilkan None.
    assert i_k1 is not None and i_h is not None
    return i_k1, i_h, i_k2


def tabel_penalaran(urutan: list[str], tanya: str) -> Soal:
    """Urutan dari aturan perbandingan (lebih tinggi/lebih besar).

    urutan = nama dari yang tertinggi ke terendah; kunci = nama sesuai tanya.
    """
    n = len(urutan)
    perbandingan = []
    for i in range(n - 1):
        perbandingan.append(f"{urutan[i]} lebih tinggi dari {urutan[i+1]}")
    kalimat = ", ".join(perbandingan)

    # i_* = INDEKS pengecoh, dipilih lewat _pilih_indeks supaya K dan H
    # dijamin menunjuk orang yang BERBEDA. Sebelumnya h dan k2 sering
    # sama: K menang (didaftarkan duluan), k2 ditambal "orang lain" ->
    # jalur K mati dan anak yang salah konsep divonis H. K2 bisa None
    # kalau namanya cuma 3 (2 pengecoh untuk 3 slot) — H diprioritaskan
    # karena dua KODE berbeda lebih berharga daripada dua K sejenis.
    if tanya == "tertinggi":
        kunci = urutan[0]
        teks = f"{kalimat}. Siapa yang paling tinggi?"
        i_k1, i_h, i_k2 = _pilih_indeks(n, benar=0, utama=n - 1, kedua=1)
        id_k1, alasan_k1 = "tabel.terendah", "menjawab yang paling rendah, bukan paling tinggi"
        id_k2, alasan_k2 = "tabel.kedua", "menjawab urutan kedua, bukan pertama"
    elif tanya == "terendah":
        kunci = urutan[-1]
        teks = f"{kalimat}. Siapa yang paling rendah?"
        i_k1, i_h, i_k2 = _pilih_indeks(n, benar=n - 1, utama=0, kedua=n - 2)
        id_k1, alasan_k1 = "tabel.tertinggi", "menjawab yang paling tinggi, bukan paling rendah"
        id_k2, alasan_k2 = "tabel.kedua_bawah", "menjawab urutan kedua dari bawah, bukan terakhir"
    elif tanya == "posisi_dua":
        kunci = urutan[1]
        teks = f"{kalimat}. Siapa yang berada di urutan kedua dari atas?"
        i_k1, i_h, i_k2 = _pilih_indeks(n, benar=1, utama=0, kedua=2)
        id_k1, alasan_k1 = "tabel.pertama", "menjawab yang paling tinggi, bukan urutan kedua"
        id_k2, alasan_k2 = "tabel.ketiga", "menjawab urutan ketiga, bukan kedua"
    else:  # posisi_tiga (hanya untuk n>=4)
        kunci = urutan[2]
        teks = f"{kalimat}. Siapa yang berada di urutan ketiga dari atas?"
        i_k1, i_h, i_k2 = _pilih_indeks(n, benar=2, utama=1, kedua=3)
        id_k1, alasan_k1 = "tabel.kedua", "menjawab urutan kedua, bukan ketiga"
        id_k2, alasan_k2 = "tabel.keempat", "menjawab urutan keempat, bukan ketiga"

    mal = [Malrule(id_k1, urutan[i_k1], "K", alasan_k1)]
    if i_k2 is not None:
        mal.append(Malrule(id_k2, urutan[i_k2], "K", alasan_k2))
    mal.append(
        Malrule("tabel.kurang_satu", urutan[i_h], "H",
                "urutan benar, meleset satu posisi")
    )
    return Soal(
        "tabel_penalaran",
        {"urutan": urutan, "tanya": tanya},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        pembahasan=(
            f"Langkah: tulis urutannya jadi satu baris dari yang paling "
            f"besar ke paling kecil, baru jawab pertanyaannya: {kunci}."
        ),
        bagian="A",
    )


# ── Bagian B — Besaran & umur ──────────────────────────────────────────


@koreksi_soal(koreksi_jumlah_selisih)
def jumlah_selisih(jumlah: int, selisih: int, tanya: str) -> Soal:
    """Dua bilangan: jumlah & selisih → (j+s)/2 dan (j−s)/2."""
    besar = (jumlah + selisih) // 2
    kecil = (jumlah - selisih) // 2
    if tanya == "besar":
        kunci = besar
        teks = f"Jumlah dua bilangan {jumlah}, selisihnya {selisih}. Berapa bilangan yang lebih besar?"
        k1 = kecil  # kebalikan
        k2 = jumlah - selisih  # lupa bagi 2
    else:
        kunci = kecil
        teks = f"Jumlah dua bilangan {jumlah}, selisihnya {selisih}. Berapa bilangan yang lebih kecil?"
        k1 = besar
        k2 = jumlah - selisih
    h = kunci - 1
    if k1 == kunci or k1 == h:
        k1 = kunci + 1
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = kunci + 2
    if h == k1 or h == k2:
        h = kunci + 1
    mal = [
        Malrule(f"jumlah_selisih.terbalik_{tanya}", str(k1), "K",
                "menjawab bilangan yang lain (terbalik besar/kecil)"),
        Malrule(f"jumlah_selisih.lupa_bagi_{tanya}", str(k2), "K",
                "menghitung jumlah−selisih tanpa membagi dua"),
        Malrule(f"jumlah_selisih.kurang_satu", str(h), "H",
                "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "jumlah_selisih",
        {"jumlah": jumlah, "selisih": selisih, "tanya": tanya},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: bilangan besar = (jumlah + selisih) : 2, "
            f"bilangan kecil = (jumlah - selisih) : 2. Hasilnya {kunci}."
        ),
        bagian="B",
    )


@soal_berversi(soal_umur_diperbaiki)
def soal_umur(a: int, b: int, k: int, n: int, tanya: str) -> Soal:
    """Umur ayah sekarang a, anak b. Dalam n tahun, ayah k× anak. Cari n."""
    # a + n = k(b + n) → a + n = kb + kn → a − kb = n(k−1) → n = (a−kb)/(k−1)
    n_hitung = (a - k * b) // (k - 1)
    if tanya == "n_tahun":
        kunci = n_hitung
        teks = (f"Umur ayah sekarang {a} tahun, umur anak {b} tahun. Dalam "
                f"berapa tahun lagi umur ayah menjadi {k} kali umur anak?")
        k1 = a - k * b  # lupa bagi (k−1)
        k2 = n_hitung + 1  # salah hitung satu tahun
    else:
        kunci = k * b  # umur ayah saat itu = a + n = k·b
        teks = (f"Umur ayah sekarang {a} tahun, umur anak {b} tahun. Dalam "
                f"{n} tahun, umur ayah menjadi berapa kali umur anak?")
        k1 = b + n  # umur anak saat itu, bukan kelipatan
        k2 = a + n  # umur ayah saat itu, bukan kelipatannya
    h = kunci - 1
    if k1 == kunci or k1 == h:
        k1 = kunci + 1
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = kunci + 2
    if h == k1 or h == k2:
        h = kunci + 1
    mal = [
        Malrule(f"umur.salah_rumus_{tanya}", str(k1), "K",
                "memakai rumus yang salah untuk perbandingan umur"),
        Malrule(f"umur.kelipatan_lain_{tanya}", str(k2), "K",
                "menjawab besaran yang berbeda dari yang diminta"),
        Malrule(f"umur.kurang_satu", str(h), "H",
                "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "soal_umur",
        {"a": a, "b": b, "k": k, "n": n, "tanya": tanya},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: selisih umur SELALU tetap. Pakai selisih itu untuk "
            f"mencari kapan syaratnya terpenuhi. Jawabannya {kunci}."
        ),
        bagian="B",
    )


def soal_uang(total: int, k: int, tanya: str) -> Soal:
    """Uang A + uang B = total; A = k×B → B = total/(k+1)."""
    kecil = total // (k + 1)
    besar = k * kecil
    if tanya == "uang_kecil":
        kunci = kecil
        teks = (f"Uang Andi dan uang Budi jumlahnya {total} rupiah. Uang Andi "
                f"{k} kali uang Budi. Berapa uang Budi (rupiah)?")
        k1 = besar
        k2 = total // k  # pola salah
    else:
        kunci = besar
        teks = (f"Uang Andi dan uang Budi jumlahnya {total} rupiah. Uang Andi "
                f"{k} kali uang Budi. Berapa uang Andi (rupiah)?")
        k1 = kecil
        k2 = total // k
    h = kunci - 1
    if k1 == kunci or k1 == h:
        k1 = kunci + 1
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = kunci + 2
    if h == k1 or h == k2:
        h = kunci + 1
    mal = [
        Malrule(f"uang.terbalik_{tanya}", str(k1), "K",
                "menjawab uang yang lain (terbalik besar/kecil)"),
        Malrule(f"uang.salah_bagi_{tanya}", str(k2), "K",
                "membagi total dengan k, bukan k+1"),
        Malrule(f"uang.kurang_satu", str(h), "H",
                "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "soal_uang",
        {"total": total, "k": k, "tanya": tanya},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: nyatakan yang satu sebagai kelipatan yang lain, "
            f"jumlahkan bagiannya, lalu bagi. Hasilnya {kunci}."
        ),
        bagian="B",
    )


def dua_besaran_selisih(selisih: int, k: int, tanya: str) -> Soal:
    """Perbandingan a:b = k:1, selisih s → b = s/(k−1), a = k·b."""
    kecil = selisih // (k - 1)
    besar = k * kecil
    if tanya == "besar":
        kunci = besar
        teks = (f"Perbandingan banyak kelereng Andi dan Budi adalah {k} : 1. "
                f"Selisih kelereng mereka {selisih} butir. Berapa kelereng Andi?")
        k1 = kecil
        k2 = selisih * k  # selisih×k
    else:
        kunci = kecil
        teks = (f"Perbandingan banyak kelereng Andi dan Budi adalah {k} : 1. "
                f"Selisih kelereng mereka {selisih} butir. Berapa kelereng Budi?")
        k1 = besar
        k2 = selisih // (k + 1)  # pola salah
    h = kunci - 1
    if k1 == kunci or k1 == h:
        k1 = kunci + 1
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = kunci + 2
    if h == k1 or h == k2:
        h = kunci + 1
    mal = [
        Malrule(f"selisih.terbalik_{tanya}", str(k1), "K",
                "menjawab besaran yang lain (terbalik besar/kecil)"),
        Malrule(f"selisih.salah_rumus_{tanya}", str(k2), "K",
                "memakai rumus yang salah untuk perbandingan dengan selisih"),
        Malrule(f"selisih.kurang_satu", str(h), "H",
                "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "dua_besaran_selisih",
        {"selisih": selisih, "k": k, "tanya": tanya},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: pakai jumlah dan selisihnya untuk memisahkan dua "
            f"besaran itu, lalu jawab yang diminta: {kunci}."
        ),
        bagian="B",
    )


# ── Registry ─────────────────────────────────────────────────────────────

REGISTRI_TOPIK = {
    "benar_salah_pengandaian": benar_salah_pengandaian,
    "tabel_penalaran": tabel_penalaran,
    "jumlah_selisih": jumlah_selisih,
    "soal_umur": soal_umur,
    "soal_uang": soal_uang,
    "dua_besaran_selisih": dua_besaran_selisih,
}

KOMPOSISI = {
    # P3 (10 soal): 1, 2, 1, 2, 5, 4, 1, 2, 5, 4
    # mudah → sulit: pengandaian & tabel (penalaran murni) dulu,
    # lalu uang (bagi), umur (paling abstrak) di akhir.
    "P3": (
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "soal_uang",
        "soal_umur",
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "soal_uang",
        "soal_umur",
    ),
    # P5 (10 soal): 1, 2, 3, 5, 1, 2, 3, 5, 1, 2
    "P5": (
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "jumlah_selisih",
        "soal_uang",
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "jumlah_selisih",
        "soal_uang",
        "benar_salah_pengandaian",
        "tabel_penalaran",
    ),
    # P6 (10 soal): 1, 2, 3, 4, 5, 6, 3, 4, 5, 6
    "P6": (
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "jumlah_selisih",
        "soal_umur",
        "soal_uang",
        "dua_besaran_selisih",
        "jumlah_selisih",
        "soal_umur",
        "soal_uang",
        "dua_besaran_selisih",
    ),
}

JUDUL_BAGIAN = {
    "A": "Bagian A — Penalaran",
    "B": "Bagian B — Besaran & umur",
}

CATATAN_BAGIAN = {
    "A": "Baca fakta dulu. Mana yang PASTI benar, bukan hanya mungkin?",
    "B": "Jumlah & selisih: (jumlah+selisih)/2 dan (jumlah−selisih)/2.",
}


@parameter_baru
def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id == "benar_salah_pengandaian":
        varian = rng.choice(("warna", "bekal"))
        nama = rng.choice(("Andi", "Budi", "Citra", "Dewi", "Eko"))
        warna = rng.choice(("merah", "biru", "hijau", "kuning", "hitam"))
        barang = rng.choice(("roti", "nasi", "buah", "telur", "sandwich"))
        # P3: kelas 3 (cerita sesuai usia); P5/P6 tetap 4-6
        kelas = 3 if level == "P3" else rng.choice((4, 5, 6))
        pilihan_benar = rng.randint(0, 4)
        # urutan tampilan: posisi pilihan_benar = pernyataan benar (0),
        # sisanya pernyataan 1..4 diacak — pakai rng deterministik, bukan hash()
        sisa = [1, 2, 3, 4]
        rng.shuffle(sisa)
        urutan_tampil: list[int] = []
        j = 0
        for i in range(5):
            if i == pilihan_benar:
                urutan_tampil.append(0)
            else:
                urutan_tampil.append(sisa[j])
                j += 1
        return {"varian": varian, "nama": nama, "warna": warna,
                "barang": barang, "kelas": kelas, "pilihan_benar": pilihan_benar,
                "urutan_tampil": urutan_tampil}
    if template_id == "tabel_penalaran":
        # 3 nama dari 5 (atau 4 nama untuk posisi_tiga)
        pool = ("Andi", "Budi", "Citra", "Dewi", "Eko")
        if level == "P3":
            # Selalu 3 nama, tanya tanpa posisi_tiga (urutan ketiga dari
            # atas butuh minimal 4 nama). Pool diperlebar ke 7 nama:
            # pool 5 hanya 60 urutan × 3 tanya = 180 kombinasi unik,
            # di bawah target variasi ≥ 200 per template.
            urutan = list(rng.sample(
                ("Andi", "Budi", "Citra", "Dewi", "Eko", "Fajar", "Gita"), 3))
            tanya = rng.choice(("tertinggi", "terendah", "posisi_dua"))
        else:
            urutan = list(rng.sample(pool, 4 if rng.random() < 0.5 else 3))
            if len(urutan) == 4:
                tanya = rng.choice(("tertinggi", "terendah", "posisi_dua", "posisi_tiga"))
            else:
                tanya = rng.choice(("tertinggi", "terendah", "posisi_dua"))
        return {"urutan": urutan, "tanya": tanya}
    if template_id == "jumlah_selisih":
        # jumlah & selisih paritas sama supaya (j±s)/2 bulat
        jumlah = rng.randint(4, 100)
        selisih = rng.randint(2, min(jumlah - 2, 30))
        while (jumlah + selisih) % 2 != 0:
            selisih = rng.randint(2, min(jumlah - 2, 30))
        tanya = rng.choice(("besar", "kecil"))
        return {"jumlah": jumlah, "selisih": selisih, "tanya": tanya}
    if template_id == "soal_umur":
        # a = k·b + (k−1)·n → n = (a−kb)/(k−1) bulat & positif
        if level == "P3":
            # P3: k kecil, umur anak & jarak tahun ringan. Batas awal
            # (b 2..6, n 1..5) hanya 5×2×5×2 = 100 kombinasi unik; dipasa
            # jadi b 2..8, n 1..8 (7×2×8×2 = 224) demi target ≥ 200.
            b = rng.randint(2, 8)
            k = rng.choice((2, 3))
            n = rng.randint(1, 8)
        else:
            b = rng.randint(2, 10)
            k = rng.choice((2, 3, 4, 5))
            n = rng.randint(1, 8)
        a = k * b + (k - 1) * n
        tanya = rng.choice(("n_tahun", "kali_umur"))
        return {"a": a, "b": b, "k": k, "n": n, "tanya": tanya}
    if template_id == "soal_uang":
        if level == "P3":
            # P3: k kecil; kecil dinaikkan ke 10..40 karena 10..20 hanya
            # 11×4×2 = 88 kombinasi unik, di bawah target ≥ 200.
            kecil = rng.randint(10, 40)
            k = rng.choice((2, 3, 4, 5))
        else:
            kecil = rng.randint(10, 50)
            k = rng.choice((2, 3, 4, 5, 6, 7, 8, 9))
        total = (k + 1) * kecil
        tanya = rng.choice(("uang_kecil", "uang_besar"))
        return {"total": total, "k": k, "tanya": tanya}
    if template_id == "dua_besaran_selisih":
        kecil = rng.randint(4, 40)
        k = rng.choice((3, 4, 5, 6, 7, 8, 9, 10))
        selisih = (k - 1) * kecil
        tanya = rng.choice(("besar", "kecil"))
        return {"selisih": selisih, "k": k, "tanya": tanya}
    raise KeyError(f"template tidak dikenal: {template_id}")


TOPIK = Topik(
    id="logika",
    nama="Logika & Penalaran",
    judul_lembar="Latihan Logika & Penalaran",
    judul_penilaian="Penilaian — Logika & Penalaran",
    templates=REGISTRI_TOPIK,
    komposisi=KOMPOSISI,
    profil={"P3": {}, "P5": {}, "P6": {}},
    judul_bagian=JUDUL_BAGIAN,
    catatan_bagian=CATATAN_BAGIAN,
    parameter_untuk=_parameter,
)

daftarkan(TOPIK)