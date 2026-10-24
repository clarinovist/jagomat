"""Paket topik statistika — Fase 6 plan 30 Aug 2026.

Delapan template menutup cakupan statistika & pengukuran OSN SD:
rata-rata (bagian A), median & modus, diagram lingkaran dan batang/garis,
tabel turus, piktogram, dan terbesar/terkecil/jangkauan (B).
Level P3-P6; P3 selaras band SASMO Primary 1-4 (statistics) — cukup modus
dan pembacaan data, median & rata-rata menunggu P4+. Soal berbentuk teks;
diagram dirender sebagai deskripsi data (SVG adalah penyempurnaan
render_badan belakangan).

Tiga template terakhir (tabel_turus, piktogram, jangkauan_data) ditambahkan
2 Sep 2026 untuk mengobati monoton di P3. Sebelumnya P3 hanya punya DUA
template (modus + diagram batang), dan terukur: 3000 soal P3 hanya
menghasilkan 6 bentuk kalimat berbeda — anak yang berlatih tiap hari
membaca bunyi soal yang sama terus, cuma angkanya ganti. Menambah
template menaikkan variasi jauh lebih besar daripada membungkus kalimat
lewat LLM, dan tidak menambah biaya per soal sama sekali.
"""

from __future__ import annotations

import random

from templates import Malrule, Soal, saring_malrule
from topics import Topik, daftarkan
from catalog_versions import koreksi_soal, parameter_baru
from catalog_malrules import statistika
from assessment_revision import soal_berrevisi


# ── Bagian A — Rata-rata ────────────────────────────────────────────────


@soal_berrevisi
def rata_rata(varian: str, data: list[int], rata: int = 0) -> Soal:
    """Rata-rata = jumlah/n; dua arah (cari rata atau cari data ke-n)."""
    n = len(data)
    jumlah = sum(data)
    if varian == "cari_rata":
        kunci = str(jumlah // n)
        teks = f"Data: {', '.join(str(x) for x in data)}. Berapa rata-ratanya?"
        k_jumlah = str(jumlah)  # lupa bagi n
        k_salah_n = str(jumlah // (n + 1))  # salah n
        mal = [
            Malrule("rata.jumlah_saja", k_jumlah, "K", "menjumlahkan data tanpa membagi banyak data"),
            Malrule("rata.salah_n", k_salah_n, "K", "membagi dengan banyak data yang salah"),
            Malrule("rata.kurang_satu", str(int(kunci) - 1), "H", "perhitungan benar, hasilnya meleset satu"),
        ]
        pembahasan = f"Langkah: Jumlah data ({' + '.join(str(x) for x in data)}) = {jumlah}. Banyak data = {n}. Rata-rata = {jumlah} ÷ {n} = {kunci}."
        param = {"varian": varian, "data": data}
    else:
        # cari_data_ke_n: data terakhir sudah dihitung di _parameter
        kunci = str(data[-1])
        teks = (
            f"Rata-rata {n} data adalah {rata}. Jika {n-1} data pertama adalah "
            f"{', '.join(str(x) for x in data[:-1])}, berapa data terakhirnya?"
        )
        k_total = str(rata * n)  # lupa kurangi jumlah
        k_salah = str(data[-1] + 1)
        mal = [
            Malrule("rata.total_saja", k_total, "K", "menghitung total semua data tanpa mencari data terakhir"),
            Malrule("rata.kurang_satu_data", k_salah, "K", "melakukan perhitungan yang salah pada data terakhir"),
            Malrule("rata.kurang_satu", str(int(kunci) - 1), "H", "perhitungan benar, hasilnya meleset satu"),
        ]
        sum_n_min_1 = sum(data[:-1])
        pembahasan = f"Langkah: Total seluruh data = {n} × {rata} = {rata * n}. Jumlah {n-1} data pertama = {sum_n_min_1}. Data terakhir = {rata * n} - {sum_n_min_1} = {kunci}."
        param = {"varian": varian, "data": data, "rata": rata}
    return Soal(
        "rata_rata",
        param,
        teks,
        kunci,
        saring_malrule(kunci, mal),
        minta_restatement=True,
        bagian="A",
        pembahasan=pembahasan,
    )


@koreksi_soal(statistika)
def rata_rata_gabungan(n1: int, n2: int, x1: int, x2: int) -> Soal:
    """Rata gabung = (n₁·x̄₁ + n₂·x̄₂)/(n₁+n₂)."""
    total1 = n1 * x1
    total2 = n2 * x2
    kunci = (total1 + total2) // (n1 + n2)
    h = kunci - 1
    k1 = total1 + total2  # lupa bagi total
    k2 = (x1 + x2) // 2  # rata dua rata-rata
    if k1 == kunci or k1 == h:
        k1 = kunci + 1
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = kunci + 2
    mal = [
        Malrule("gabung.total_saja", str(k1), "K", "menjumlahkan total kedua kelompok tanpa membagi"),
        Malrule("gabung.rata_rata_rata", str(k2), "K", "merata-ratakan dua rata-rata tanpa memperhitungkan jumlah data"),
        Malrule("gabung.kurang_satu", str(h), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    teks = (
        f"Kelompok A: {n1} anak dengan rata-rata {x1}. Kelompok B: {n2} anak "
        f"dengan rata-rata {x2}. Berapa rata-rata gabungan keduanya?"
    )
    pembahasan = (
        f"Langkah: Total A = {n1} × {x1} = {total1}. Total B = {n2} × {x2} = {total2}. "
        f"Total gabungan = {total1} + {total2} = {total1 + total2}. "
        f"Rata-rata gabungan = {total1 + total2} ÷ ({n1} + {n2}) = {kunci}."
    )
    return Soal(
        "rata_rata_gabungan",
        {"n1": n1, "n2": n2, "x1": x1, "x2": x2},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        bagian="A",
        pembahasan=pembahasan,
    )


# ── Bagian B — Median & modus, diagram ─────────────────────────────────


@koreksi_soal(statistika)
def median_modus(varian: str, data: list[int]) -> Soal:
    """Median = nilai tengah data urut; modus = nilai paling sering."""
    n = len(data)
    urut = sorted(data)
    if varian == "median":
        def fmt_setengah(dua_kali_nilai: int) -> str:
            """Format bilangan bulat/setengah dengan koma tanpa float."""
            if dua_kali_nilai % 2 == 0:
                return str(dua_kali_nilai // 2)
            return f"{dua_kali_nilai // 2},5"

        if n % 2 == 1:
            kunci_dua = 2 * urut[n // 2]
            tengah_dua = 2 * data[n // 2]  # tengah tanpa urut
            langkah_median = f"Nilai tengah (median) = {fmt_setengah(kunci_dua)}."
        else:
            tengah_kiri, tengah_kanan = urut[n // 2 - 1], urut[n // 2]
            # Simpan dalam satuan setengah agar 15,5 tetap eksak tanpa
            # float. Sebelumnya `// 2` membulatkan 15,5 menjadi 15.
            kunci_dua = tengah_kiri + tengah_kanan
            tengah_dua = data[n // 2 - 1] + data[n // 2]  # tanpa urut
            langkah_median = (
                f"Dua nilai tengahnya {tengah_kiri} dan {tengah_kanan}. "
                f"Median = ({tengah_kiri} + {tengah_kanan}) : 2 = "
                f"{fmt_setengah(kunci_dua)}."
            )
        terkecil_dua = 2 * urut[0]
        h_dua = kunci_dua - 2
        while tengah_dua in (kunci_dua, h_dua):
            tengah_dua += 2
        while terkecil_dua in (kunci_dua, h_dua, tengah_dua):
            terkecil_dua += 2
        while h_dua in (kunci_dua, tengah_dua, terkecil_dua):
            h_dua += 2
        kunci = fmt_setengah(kunci_dua)
        mal = [
            Malrule("median.tanpa_urut", fmt_setengah(tengah_dua), "K", "mengambil nilai tengah tanpa mengurutkan data"),
            Malrule("median.terkecil", fmt_setengah(terkecil_dua), "K", "menjawab data terkecil, bukan median"),
            Malrule("median.kurang_satu", fmt_setengah(h_dua), "H", "perhitungan benar, hasilnya meleset satu"),
        ]
        teks = f"Data: {', '.join(str(x) for x in data)}. Berapa mediannya?"
        pembahasan = (
            f"Langkah: Data diurutkan ({', '.join(str(x) for x in urut)}). "
            f"{langkah_median}"
        )
        param = {"varian": varian, "data": data}
    else:
        # modus: nilai paling sering muncul
        from collections import Counter
        hitung = Counter(data)
        modus = max(hitung.items(), key=lambda kv: kv[1])[0]
        kunci = str(modus)
        # Nilai pertama yang benar bukan miskonsepsi. Biarkan filter
        # membuangnya, bukan mengganti jawabannya sambil memakai label lama.
        mal = [Malrule("modus.pertama", str(data[0]), "K", "menjawab data pertama, bukan yang paling sering muncul")]
        urut_modus = sorted(hitung, key=lambda x: -hitung[x])
        if len(urut_modus) > 1 and hitung[urut_modus[1]] < hitung[modus]:
            mal.append(Malrule("modus.kedua", str(urut_modus[1]), "K", "menjawab nilai yang bukan paling sering muncul"))
        # H hanya boleh meleset satu. Jika kedua tetangga sudah dipakai
        # K, tidak ada H yang dapat dibedakan; jangan mengarang selisih lain.
        terpakai = {m.jawaban for m in mal}
        for h in (modus - 1, modus + 1):
            if str(h) not in terpakai:
                mal.append(Malrule("modus.kurang_satu", str(h), "H", "perhitungan benar, hasilnya meleset satu"))
                break
        teks = f"Data: {', '.join(str(x) for x in data)}. Berapa modusnya (nilai yang paling sering muncul)?"
        pembahasan = f"Langkah: Kemunculan data ({', '.join(f'{k}:{v}x' for k, v in hitung.items())}). Modus (paling sering muncul) = {kunci}."
        param = {"varian": varian, "data": data}
    return Soal(
        "median_modus",
        param,
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        bagian="B",
        pembahasan=pembahasan,
    )


def diagram_lingkaran(varian: str, s: int, total: int, nilai: int = 0) -> Soal:
    """Dari diagram lingkaran (derajat): nilai = s/360×total, atau cari sudut."""
    if varian == "cari_nilai":
        kunci = str(total * s // 360)
        teks = (
            f"Diagram lingkaran menunjukkan data {total} siswa. Bagian yang "
            f"memilih olahraga menempati sudut {s}°. Berapa siswa yang memilih "
            f"olahraga?"
        )
        k_lupa_total = str(s // 360 * total if s >= 360 else s)  # baca sudut saja
        k_dobel = str(total * s // 180)  # s/180 bukan s/360
        mal = [
            Malrule("lingkaran.sudut_saja", k_lupa_total, "K", "menjawab sudut, bukan banyak siswa"),
            Malrule("lingkaran.salah_360", k_dobel, "K", "memakai sudut/180 bukan sudut/360"),
            Malrule("lingkaran.kurang_satu", str(int(kunci) - 1), "H", "perhitungan benar, hasilnya meleset satu"),
        ]
        pembahasan = f"Langkah: Banyak siswa = ({s}° ÷ 360°) × {total} = {kunci} siswa."
        param = {"varian": varian, "s": s, "total": total}
    else:
        # cari_sudut: sudut = nilai/total×360
        kunci = str(nilai * 360 // total)
        teks = (
            f"Diagram lingkaran menunjukkan data {total} siswa. Sebanyak {nilai} "
            f"siswa memilih membaca. Berapa sudut bagian membaca pada diagram "
            f"lingkaran (derajat)?"
        )
        k_nilai_saja = str(nilai)  # baca nilai saja
        k_balik = str((total - nilai) * 360 // total)  # sudut bagian lain
        mal = [
            Malrule("lingkaran.nilai_saja", k_nilai_saja, "K", "menjawab banyak siswa, bukan sudut"),
            Malrule("lingkaran.bagian_lain", k_balik, "K", "menghitung sudut bagian yang lain"),
            Malrule("lingkaran.kurang_satu", str(int(kunci) - 1), "H", "perhitungan benar, hasilnya meleset satu"),
        ]
        pembahasan = f"Langkah: Sudut = ({nilai} ÷ {total}) × 360° = {kunci}°."
        param = {"varian": varian, "s": nilai * 360 // total, "total": total, "nilai": nilai}
    return Soal(
        "diagram_lingkaran",
        param,
        teks,
        kunci,
        saring_malrule(kunci, mal),
        bagian="B",
        pembahasan=pembahasan,
    )


@koreksi_soal(statistika)
def diagram_batang_garis(varian: str, data: list[int], i: int = 0) -> Soal:
    """Dari diagram batang: baca nilai, jumlah, selisih, atau total."""
    n = len(data)
    nama = [f"B{i+1}" for i in range(n)]
    teks_data = ", ".join(f"{nama[k]}: {data[k]}" for k in range(n))
    if varian == "baca":
        kunci = data[i]
        k1 = data[(i + 1) % n]
        k2 = data[(i + 2) % n]
        h = kunci - 1
        if k1 == kunci or k1 == h:
            k1 = kunci + 1
        if k2 == kunci or k2 == h or k2 == k1:
            k2 = kunci + 2
        mal = [
            Malrule("batang.baca_tetangga", str(k1), "K", f"membaca batang yang berdekatan, bukan {nama[i]}"),
            Malrule("batang.baca_lain", str(k2), "K", "membaca batang yang salah"),
            Malrule("batang.kurang_satu", str(h), "H", "membaca benar, nilainya meleset satu"),
        ]
        teks = f"Diagram batang: {teks_data}. Berapa nilai {nama[i]}?"
        pembahasan = f"Langkah: Membaca nilai {nama[i]} langsung pada data = {kunci}."
        param = {"varian": varian, "data": data, "i": i}
    elif varian == "jumlah":
        kunci = sum(data)
        k1 = max(data)  # menjawab batang terbesar
        k2 = sum(data) - data[0]  # lupa menjumlahkan batang pertama
        h = kunci - 1
        if k1 == kunci or k1 == h:
            k1 = kunci + 1
        if k2 == kunci or k2 == h or k2 == k1:
            k2 = kunci + 2
        mal = [
            Malrule("batang.terbesar", str(k1), "K", "menjawab batang terbesar, bukan jumlah"),
            Malrule("batang.lupa_pertama", str(k2), "K", "menjumlahkan dengan melupakan satu batang"),
            Malrule("batang.kurang_satu", str(h), "H", "perhitungan benar, hasilnya meleset satu"),
        ]
        teks = f"Diagram batang: {teks_data}. Berapa jumlah seluruh nilai?"
        pembahasan = f"Langkah: Jumlah seluruh batang = {' + '.join(str(x) for x in data)} = {kunci}."
        param = {"varian": varian, "data": data}
    elif varian == "selisih":
        a, b = data[i], data[(i + 1) % n]
        kunci = abs(a - b)
        k1 = a + b  # menjumlahkan dua batang
        k2 = abs(a - data[(i + 2) % n])  # selisih batang yang berbeda
        h = kunci - 1
        if k1 == kunci or k1 == h:
            k1 = kunci + 1
        if k2 == kunci or k2 == h or k2 == k1:
            k2 = kunci + 2
        mal = [
            Malrule("batang.jumlah_dua", str(k1), "K", "menjumlahkan dua batang padahal yang diminta selisih"),
            Malrule("batang.selisih_lain", str(k2), "K", "menghitung selisih batang yang berbeda"),
            Malrule("batang.kurang_satu", str(h), "H", "perhitungan benar, hasilnya meleset satu"),
        ]
        teks = f"Diagram batang: {teks_data}. Berapa selisih {nama[i]} dan {nama[(i+1)%n]}?"
        pembahasan = f"Langkah: Selisih |{a} - {b}| = {kunci}."
        param = {"varian": varian, "data": data, "i": i}
    return Soal(
        "diagram_batang_garis",
        param,
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        bagian="B",
        pembahasan=pembahasan,
    )


@koreksi_soal(statistika)
def tabel_turus(varian: str, nama: list[str], data: list[int], i: int = 0) -> Soal:
    """Tabel turus (tally): baca frekuensi, cari terbanyak, atau total.

    Bentuk soal yang berbeda dari diagram batang meski datanya sejenis:
    anak membaca coretan turus, bukan tinggi batang. Ditambahkan untuk
    P3 yang sebelumnya hanya punya dua template.
    """
    n = len(data)
    baris = ", ".join(f"{nama[k]} = {data[k]} turus" for k in range(n))
    if varian == "baca":
        kunci = data[i]
        k1 = data[(i + 1) % n]
        k2 = data[(i + 2) % n]
        teks = f"Tabel turus: {baris}. Berapa banyak {nama[i]}?"
        pembahasan = f"Langkah: Baca baris {nama[i]} pada tabel = {kunci}."
        param = {"varian": varian, "nama": nama, "data": data, "i": i}
        alasan1 = f"membaca baris yang berdekatan, bukan {nama[i]}"
        alasan2 = "membaca baris yang salah"
    elif varian == "terbanyak":
        besar = max(data)
        kunci = data.index(besar)
        # kunci berupa NAMA, bukan angka — dikembalikan sebagai teks.
        nama_kunci = nama[kunci]
        urut = sorted(range(n), key=lambda k: -data[k])
        mal = [
            Malrule("turus.terkecil", nama[min(range(n), key=lambda k: data[k])],
                    "K", "menjawab yang paling sedikit, bukan yang terbanyak"),
            Malrule("turus.kedua", nama[urut[1]], "K",
                    "menjawab yang terbanyak kedua"),
            Malrule("turus.jumlahnya", str(besar), "E",
                    "menuliskan banyaknya, padahal yang diminta namanya"),
        ]
        teks = f"Tabel turus: {baris}. Yang paling banyak adalah?"
        pembahasan = (
            f"Langkah: Bandingkan semua baris ({', '.join(str(x) for x in data)}). "
            f"Paling banyak = {besar}, yaitu {nama_kunci}."
        )
        return Soal(
            "tabel_turus",
            {"varian": varian, "nama": nama, "data": data},
            teks,
            nama_kunci,
            saring_malrule(nama_kunci, mal),
            bagian="B",
            pembahasan=pembahasan,
        )
    else:
        kunci = sum(data)
        k1 = max(data)
        k2 = sum(data) - data[0]
        teks = f"Tabel turus: {baris}. Berapa jumlah seluruhnya?"
        pembahasan = (
            f"Langkah: Jumlahkan semua baris = "
            f"{' + '.join(str(x) for x in data)} = {kunci}."
        )
        param = {"varian": varian, "nama": nama, "data": data}
        alasan1 = "menjawab baris terbesar, bukan jumlah"
        alasan2 = "menjumlahkan dengan melupakan satu baris"
    h = kunci - 1
    if k1 == kunci or k1 == h:
        k1 = kunci + 1
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = kunci + 2
    mal = [
        Malrule("turus.salah_baris", str(k1), "K", alasan1),
        Malrule("turus.salah_baris2", str(k2), "K", alasan2),
        Malrule("turus.kurang_satu", str(h), "H",
                "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "tabel_turus",
        param,
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        bagian="B",
        pembahasan=pembahasan,
    )


@koreksi_soal(statistika)
def piktogram(varian: str, satuan: int, gambar: list[int], nama: list[str], i: int = 0) -> Soal:
    """Piktogram: 1 gambar mewakili `satuan` benda.

    Yang diuji bukan aritmetikanya saja tapi SKALA — kesalahan khas anak
    adalah menjawab banyaknya gambar, bukan hasil kali dengan satuan.
    Miskonsepsi itu tidak tersedia di template diagram batang, jadi
    template ini menambah jalur diagnosis baru, bukan sekadar kalimat baru.
    """
    n = len(gambar)
    baris = ", ".join(f"{nama[k]}: {gambar[k]} gambar" for k in range(n))
    awalan = f"Piktogram (1 gambar = {satuan} buah). {baris}."
    if varian == "baca":
        kunci = gambar[i] * satuan
        teks = f"{awalan} Berapa buah {nama[i]}?"
        pembahasan = (
            f"Langkah: {nama[i]} punya {gambar[i]} gambar. "
            f"Tiap gambar = {satuan} buah, jadi {gambar[i]} × {satuan} = {kunci}."
        )
        k1 = gambar[i]  # lupa dikali satuan
        k2 = gambar[i] + satuan  # menambah, bukan mengali
        alasan1 = "menjawab banyaknya gambar, lupa dikali nilai satu gambar"
        alasan2 = "menambahkan nilai satu gambar, bukan mengalikan"
        param = {"varian": varian, "satuan": satuan, "gambar": gambar, "nama": nama, "i": i}
    elif varian == "total":
        kunci = sum(gambar) * satuan
        teks = f"{awalan} Berapa buah seluruhnya?"
        pembahasan = (
            f"Langkah: Jumlah gambar = {' + '.join(str(x) for x in gambar)} "
            f"= {sum(gambar)}. Seluruhnya = {sum(gambar)} × {satuan} = {kunci}."
        )
        k1 = sum(gambar)  # lupa dikali satuan
        k2 = max(gambar) * satuan  # baris terbesar saja
        alasan1 = "menjumlahkan gambar tanpa mengalikan nilai satu gambar"
        alasan2 = "menghitung satu baris saja, bukan seluruhnya"
        param = {"varian": varian, "satuan": satuan, "gambar": gambar, "nama": nama}
    else:
        # selisih dua baris
        a, b = gambar[i], gambar[(i + 1) % n]
        kunci = abs(a - b) * satuan
        teks = f"{awalan} Berapa selisih {nama[i]} dan {nama[(i+1)%n]}?"
        pembahasan = (
            f"Langkah: Selisih gambar = |{a} - {b}| = {abs(a - b)}. "
            f"Selisih buah = {abs(a - b)} × {satuan} = {kunci}."
        )
        k1 = abs(a - b)  # lupa dikali satuan
        k2 = (a + b) * satuan  # menjumlahkan, bukan selisih
        alasan1 = "menjawab selisih gambar, lupa dikali nilai satu gambar"
        alasan2 = "menjumlahkan dua baris padahal yang diminta selisih"
        param = {"varian": varian, "satuan": satuan, "gambar": gambar, "nama": nama, "i": i}
    h = kunci - 1
    if k1 == kunci or k1 == h:
        k1 = kunci + 1
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = kunci + 2
    mal = [
        Malrule("pikto.lupa_skala", str(k1), "K", alasan1),
        Malrule("pikto.salah_operasi", str(k2), "K", alasan2),
        Malrule("pikto.kurang_satu", str(h), "H",
                "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "piktogram",
        param,
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        bagian="B",
        pembahasan=pembahasan,
    )


@koreksi_soal(statistika)
def jangkauan_data(varian: str, data: list[int]) -> Soal:
    """Nilai terbesar, terkecil, atau jangkauan (terbesar − terkecil).

    Konsep paling dasar di statistika dan satu-satunya yang bisa dikerjakan
    anak P3 tanpa membagi — pintu masuk sebelum modus.
    """
    besar, kecil = max(data), min(data)
    teks_data = ", ".join(str(x) for x in data)
    if varian == "terbesar":
        kunci = besar
        k1 = kecil
        k2 = sorted(data)[-2] if len(set(data)) > 1 else besar + 2
        alasan1 = "menjawab nilai terkecil, bukan terbesar"
        alasan2 = "menjawab nilai terbesar kedua"
        tanya = "Berapa nilai terbesarnya?"
        pembahasan = (
            f"Langkah: Bandingkan semua data ({teks_data}). Terbesar = {kunci}."
        )
    elif varian == "terkecil":
        kunci = kecil
        k1 = besar
        k2 = sorted(data)[1] if len(set(data)) > 1 else kecil + 2
        alasan1 = "menjawab nilai terbesar, bukan terkecil"
        alasan2 = "menjawab nilai terkecil kedua"
        tanya = "Berapa nilai terkecilnya?"
        pembahasan = (
            f"Langkah: Bandingkan semua data ({teks_data}). Terkecil = {kunci}."
        )
    else:
        kunci = besar - kecil
        k1 = besar + kecil  # menjumlahkan, bukan mengurangi
        k2 = besar  # menjawab terbesar saja
        alasan1 = "menjumlahkan nilai terbesar dan terkecil, bukan menguranginya"
        alasan2 = "menjawab nilai terbesar, bukan selisihnya"
        tanya = "Berapa jangkauannya (nilai terbesar dikurangi terkecil)?"
        pembahasan = (
            f"Langkah: Terbesar = {besar}, terkecil = {kecil}. "
            f"Jangkauan = {besar} - {kecil} = {kunci}."
        )
    h = kunci - 1
    if k1 == kunci or k1 == h:
        k1 = kunci + 1
    if k2 == kunci or k2 == h or k2 == k1:
        k2 = kunci + 2
    if h == k1 or h == k2:
        h = kunci + 3
    mal = [
        Malrule("jangkau.arah_salah", str(k1), "K", alasan1),
        Malrule("jangkau.hampir", str(k2), "K", alasan2),
        Malrule("jangkau.kurang_satu", str(h), "H",
                "perhitungan benar, hasilnya meleset satu"),
    ]
    teks = f"Data: {teks_data}. {tanya}"
    return Soal(
        "jangkauan_data",
        {"varian": varian, "data": data},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        bagian="B",
        pembahasan=pembahasan,
    )

# ── Registry ─────────────────────────────────────────────────────────────

REGISTRI_TOPIK = {
    "rata_rata": rata_rata,
    "rata_rata_gabungan": rata_rata_gabungan,
    "median_modus": median_modus,
    "diagram_lingkaran": diagram_lingkaran,
    "diagram_batang_garis": diagram_batang_garis,
    "tabel_turus": tabel_turus,
    "piktogram": piktogram,
    "jangkauan_data": jangkauan_data,
}

KOMPOSISI = {
    # P3 (10 soal): lima template berputar. Sebelum 2 Sep 2026 hanya dua
    # (modus + diagram batang) dan itu membuat P3 jadi level paling
    # monoton di seluruh aplikasi — terukur 3000 soal hanya melahirkan
    # 6 bentuk kalimat. Jangkauan/turus/piktogram semuanya sesuai band
    # SASMO Primary 1-4 (membaca & membandingkan data, tanpa membagi);
    # median & rata-rata tetap menunggu P4.
    "P3": (
        "jangkauan_data",
        "median_modus",
        "tabel_turus",
        "diagram_batang_garis",
        "piktogram",
        "median_modus",
        "jangkauan_data",
        "tabel_turus",
        "diagram_batang_garis",
        "piktogram",
    ),
    # P4 (10 soal): rata-rata masuk, piktogram & turus tetap dipakai
    # supaya posisi yang sama tidak selalu bermodel sama antar-seed.
    "P4": (
        "rata_rata",
        "median_modus",
        "diagram_batang_garis",
        "piktogram",
        "rata_rata",
        "tabel_turus",
        "median_modus",
        "diagram_batang_garis",
        "jangkauan_data",
        "rata_rata",
    ),
    # P5 (10 soal): 1, 2, 3, 4, 5, 1, 2, 3, 4, 5
    "P5": (
        "rata_rata",
        "rata_rata_gabungan",
        "median_modus",
        "diagram_lingkaran",
        "diagram_batang_garis",
        "rata_rata",
        "rata_rata_gabungan",
        "median_modus",
        "diagram_lingkaran",
        "diagram_batang_garis",
    ),
    # P6 (10 soal): 1, 2, 3, 4, 5, 2, 3, 4, 5, 1
    "P6": (
        "rata_rata",
        "rata_rata_gabungan",
        "median_modus",
        "diagram_lingkaran",
        "diagram_batang_garis",
        "rata_rata_gabungan",
        "median_modus",
        "diagram_lingkaran",
        "diagram_batang_garis",
        "rata_rata",
    ),
}

JUDUL_BAGIAN = {
    "A": "Bagian A — Rata-rata",
    "B": "Bagian B — Median & modus, diagram",
}

CATATAN_BAGIAN = {
    "A": "Rata-rata = jumlah data ÷ banyak data.",
    "B": "Median = nilai tengah (urutkan dulu). Modus = nilai paling sering muncul.",
}


@parameter_baru
def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id == "rata_rata":
        varian = rng.choice(("cari_rata", "cari_data_ke_n"))
        n = rng.randint(3, 8)
        if varian == "cari_rata":
            # jumlah harus habis dibagi n supaya rata-rata bulat
            data = [rng.randint(1, 100) for _ in range(n)]
            while sum(data) % n != 0:
                data = [rng.randint(1, 100) for _ in range(n)]
            return {"varian": varian, "data": data}
        # cari_data_ke_n: pilih rata bulat, lalu data pertama; data terakhir = rata×n−jumlah
        rata = rng.randint(12, 80)
        data = [rng.randint(1, 100) for _ in range(n - 1)]
        data.append(rata * n - sum(data))
        # jaga data terakhir tetap positif & masuk akal (1..200)
        while data[-1] < 1 or data[-1] > 200:
            data = [rng.randint(1, 100) for _ in range(n - 1)]
            data.append(rata * n - sum(data))
        return {"varian": varian, "data": data, "rata": rata}
    if template_id == "rata_rata_gabungan":
        n1, n2 = rng.randint(2, 12), rng.randint(2, 12)
        x1, x2 = rng.randint(5, 100), rng.randint(5, 100)
        # total gabungan habis dibagi (n1+n2)
        while (n1 * x1 + n2 * x2) % (n1 + n2) != 0:
            x2 = rng.randint(5, 100)
        return {"n1": n1, "n2": n2, "x1": x1, "x2": x2}
    if template_id == "median_modus":
        # P3: median di atas kelas 3 — selalu varian modus; band SASMO
        # Primary 1-4 (statistics) memuat modus, bukan median.
        if level == "P3":
            varian = "modus"
        else:
            varian = rng.choice(("median", "modus"))
        if varian == "median":
            n = rng.randint(3, 9)
            data = [rng.randint(1, 30) for _ in range(n)]
            return {"varian": varian, "data": data}
        # Modus: 3-8 data (P3: 3-5, nilai 1-12), minimal satu nilai muncul ≥2 kali.
        # Modus wajib TUNGGAL: kalau dua nilai seri (mis. 1,1,3,3,10),
        # soalnya tidak punya satu jawaban benar — pola yang sama dengan
        # "terbanyak tunggal" di tabel_turus & jangkauan_data di bawah.
        from collections import Counter

        while True:
            if level == "P3":
                n = rng.randint(3, 5)
                data = [rng.randint(1, 12) for _ in range(n)]
                modus = rng.randint(1, 12)
            else:
                n = rng.randint(3, 8)
                data = [rng.randint(1, 40) for _ in range(n)]
                modus = rng.randint(1, 40)
            data[0] = modus
            if n > 1:
                data[1] = modus
            hitung = Counter(data)
            tertinggi = max(hitung.values())
            # Semua data sama sah secara matematika, tetapi tidak punya
            # kandidat K "nilai lain"; jangan mengarang angka untuk diagnosis.
            if len(hitung) > 1 and sum(1 for v in hitung.values() if v == tertinggi) == 1:
                break
        rng.shuffle(data)
        return {"varian": varian, "data": data}
    if template_id == "diagram_lingkaran":
        varian = rng.choice(("cari_nilai", "cari_sudut"))
        s_pilihan = (30, 45, 60, 90, 120, 180)
        if varian == "cari_nilai":
            s = rng.choice(s_pilihan)
            kunci = rng.randint(2, 50)
            total = kunci * 360 // s
            return {"varian": varian, "s": s, "total": total}
        # cari_sudut: pilih sudut kunci, nilai = kunci_sudut/360×total
        sudut = rng.choice(s_pilihan)
        total = rng.randint(36, 3600)
        while total * sudut // 360 == 0 or total * sudut % 360 != 0:
            total = rng.randint(36, 3600)
        nilai = total * sudut // 360
        return {"varian": varian, "s": sudut, "total": total, "nilai": nilai}
    if template_id == "diagram_batang_garis":
        varian = rng.choice(("baca", "jumlah", "selisih"))
        if level == "P3":
            # P3: empat batang, nilai 1-20 — ketiga varian tetap boleh.
            n, atas = 4, 20
        else:
            n, atas = rng.randint(4, 6), 70
        data = [rng.randint(1, atas) for _ in range(n)]
        i = rng.randint(0, n - 1)
        if varian == "baca":
            return {"varian": varian, "data": data, "i": i}
        if varian == "jumlah":
            return {"varian": varian, "data": data}
        # selisih: pastikan dua batang yang dibandingkan berbeda
        a, b = data[i], data[(i + 1) % n]
        while a == b:
            data[(i + 1) % n] = rng.randint(1, atas)
            b = data[(i + 1) % n]
        return {"varian": varian, "data": data, "i": i}
    if template_id == "tabel_turus":
        varian = rng.choice(("baca", "terbanyak", "jumlah"))
        pilihan = (
            ("Apel", "Jeruk", "Mangga", "Pisang"),
            ("Merah", "Biru", "Hijau", "Kuning"),
            ("Sepeda", "Motor", "Mobil", "Becak"),
            ("Bakso", "Soto", "Mie", "Nasi"),
        )
        nama = list(rng.choice(pilihan))
        atas = 9 if level == "P3" else 25
        data = [rng.randint(1, atas) for _ in range(4)]
        if varian == "terbanyak":
            # Terbanyak harus TUNGGAL, kalau seri soalnya tidak punya
            # satu jawaban benar dan malrule "terbanyak kedua" jadi kunci.
            while data.count(max(data)) > 1:
                data = [rng.randint(1, atas) for _ in range(4)]
            return {"varian": varian, "nama": nama, "data": data}
        if varian == "jumlah":
            return {"varian": varian, "nama": nama, "data": data}
        return {"varian": varian, "nama": nama, "data": data, "i": rng.randint(0, 3)}
    if template_id == "piktogram":
        varian = rng.choice(("baca", "total", "selisih"))
        pilihan = (
            ("Senin", "Selasa", "Rabu"),
            ("Kelas A", "Kelas B", "Kelas C"),
            ("Toko 1", "Toko 2", "Toko 3"),
        )
        nama = list(rng.choice(pilihan))
        # Satuan kecil di P3 (2/5/10 — masih bisa dihitung dengan
        # penjumlahan berulang), lebih besar mulai P4.
        satuan = rng.choice((2, 5, 10)) if level == "P3" else rng.choice((2, 4, 5, 10, 20))
        atas = 6 if level == "P3" else 12
        gambar = [rng.randint(1, atas) for _ in range(3)]
        if varian == "total":
            return {"varian": varian, "satuan": satuan, "gambar": gambar, "nama": nama}
        i = rng.randint(0, 2)
        if varian == "selisih":
            # Dua baris yang dibandingkan wajib berbeda, kalau tidak
            # kuncinya 0 dan malrule selisih jadi tak bermakna.
            while gambar[i] == gambar[(i + 1) % 3]:
                gambar[(i + 1) % 3] = rng.randint(1, atas)
        return {"varian": varian, "satuan": satuan, "gambar": gambar, "nama": nama, "i": i}
    if template_id == "jangkauan_data":
        varian = rng.choice(("terbesar", "terkecil", "jangkauan"))
        n = rng.randint(4, 5) if level == "P3" else rng.randint(4, 7)
        atas = 20 if level == "P3" else 99
        data = [rng.randint(1, atas) for _ in range(n)]
        # Terbesar & terkecil wajib TUNGGAL dan berbeda: kalau seri,
        # "terbesar kedua" bertabrakan dengan kunci dan malrule terbuang.
        while (
            data.count(max(data)) > 1
            or data.count(min(data)) > 1
            or max(data) == min(data)
        ):
            data = [rng.randint(1, atas) for _ in range(n)]
        return {"varian": varian, "data": data}
    raise KeyError(f"template tidak dikenal: {template_id}")


TOPIK = Topik(
    id="statistika",
    nama="Statistika",
    judul_lembar="Latihan Statistika",
    judul_penilaian="Penilaian — Statistika",
    templates=REGISTRI_TOPIK,
    komposisi=KOMPOSISI,
    profil={"P3": {}, "P4": {}, "P5": {}, "P6": {}},
    judul_bagian=JUDUL_BAGIAN,
    catatan_bagian=CATATAN_BAGIAN,
    parameter_untuk=_parameter,
)

daftarkan(TOPIK)