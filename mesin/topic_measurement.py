"""Paket topik pengukuran — Fase 8 plan 30 Aug 2026.

Tiga template pertama menutup cakupan pengukuran OSN SD yang belum
tercakup Fase 4/6: skala peta, satuan waktu lama, jam/menit/detik.
Level P4/P5/P6 (P3 tidak).

Gelombang 2 (2 Sep 2026) menambah EMPAT jenis soal — lihat blok catatan
di atas `satuan_kuantitas`.
"""

from __future__ import annotations

import random

from measurement_versions import parameter_baru, soal_berversi
from templates import Malrule, Soal, saring_malrule
from topics import Topik, daftarkan


# ── Bagian A — Skala peta ──────────────────────────────────────────────


@soal_berversi
def skala_peta(varian: str, sebenarnya: int, peta: int, skala: int) -> Soal:
    """Skala = peta:sebenarnya (cm:cm). Dua arah: cari skala, peta, atau sebenarnya."""
    # skala = peta:sebenarnya_cm — sebenarnya dalam km, konversi ke cm ×100.000
    if varian == "cari_skala":
        # skala = peta : sebenarnya_cm → sederhanakan
        kunci = f"1:{skala}"
        teks = (f"Jarak dua kota sebenarnya {sebenarnya} km. Pada peta "
                f"jaraknya {peta} cm. Berapa skala peta tersebut?")
        k_terbalik = f"{skala}:1"
        h = f"1:{skala + 1}"
        mal = [
            Malrule("skala.terbalik", k_terbalik, "K", "membalik skala — peta:sebenarnya bukan sebenarnya:peta"),
            Malrule("skala.lupa_km_ke_cm", f"1:{peta * sebenarnya}", "K", "lupa mengubah km ke cm (×100.000)"),
            Malrule("skala.kurang_satu", h, "H", "skala benar, meleset satu pada penyebut"),
        ]
    elif varian == "cari_peta":
        kunci = str(peta)
        # peta = sebenarnya_cm / skala
        teks = (f"Jarak dua kota sebenarnya {sebenarnya} km. Skala peta "
                f"1:{skala}. Berapa jarak pada peta (cm)?")
        k_terbalik = str(sebenarnya * 100000 // skala * skala)  # salah
        k_lupa = str(sebenarnya)  # lupa km→cm
        mal = [
            Malrule("skala.peta_terbalik", str(sebenarnya * 100000), "K", "menjawab jarak sebenarnya dalam cm, bukan jarak peta"),
            Malrule("skala.peta_lupa_km", k_lupa, "K", "lupa mengubah km ke cm"),
            Malrule("skala.peta_kurang_satu", str(peta - 1), "H", "perhitungan benar, hasilnya meleset satu"),
        ]
    else:  # cari_sebenarnya
        kunci = str(sebenarnya)
        teks = (f"Jarak dua kota pada peta {peta} cm. Skala peta "
                f"1:{skala}. Berapa jarak sebenarnya (km)?")
        k_lupa_bagi = str(peta * skala)  # lupa ÷100.000
        k_terbalik = str(peta // skala)  # bagi dengan skala, bukan kali
        mal = [
            Malrule("skala.sebenarnya_lupa_bagi", k_lupa_bagi, "K", "menghitung peta×skala tanpa mengubah ke km"),
            Malrule("skala.sebenarnya_terbalik", k_terbalik, "K", "membagi dengan skala padahal harus dikali"),
            Malrule("skala.sebenarnya_kurang_satu", str(sebenarnya - 1), "H", "perhitungan benar, hasilnya meleset satu"),
        ]
    return Soal(
        "skala_peta",
        {"varian": varian, "sebenarnya": sebenarnya, "peta": peta, "skala": skala},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: skala 1 : n berarti 1 cm di peta = n cm sebenarnya. "
            f"Jarak peta {peta} cm, skala 1:{skala}, jarak sebenarnya "
            f"{sebenarnya} cm. Yang diminta: {kunci}."
        ),
        bagian="A",
    )


# ── Bagian B — Waktu & konversi ────────────────────────────────────────


def satuan_waktu_lama(varian: str, nilai: int, hasil: int) -> Soal:
    """Konversi satuan waktu lama: abad, windu, lustrum, dasawarsa, tahun."""
    SATUAN = {
        "abad_ke_tahun": ("abad", "tahun", 100),
        "tahun_ke_abad": ("tahun", "abad", 1 / 100),
        "windu_ke_tahun": ("windu", "tahun", 8),
        "tahun_ke_windu": ("tahun", "windu", 1 / 8),
        "lustrum_ke_tahun": ("lustrum", "tahun", 5),
        "tahun_ke_lustrum": ("tahun", "lustrum", 1 / 5),
        "dasawarsa_ke_tahun": ("dasawarsa", "tahun", 10),
        "tahun_ke_dasawarsa": ("tahun", "dasawarsa", 1 / 10),
        "windu_ke_lustrum": ("windu", "lustrum", 8 / 5),
        "abad_ke_dasawarsa": ("abad", "dasawarsa", 10),
    }
    src, dst, faktor = SATUAN[varian]
    if faktor >= 1:
        kunci = str(int(nilai * faktor))
        teks = f"{nilai} {src} = berapa {dst}?"
        k_salah_arah = str(nilai // int(faktor)) if int(faktor) != 0 else "0"
        k_lupa = str(nilai)
    else:
        kunci = str(hasil)
        teks = f"{nilai} {src} = berapa {dst}?"
        k_salah_arah = str(nilai * int(1 / faktor))
        k_lupa = str(nilai)

    if k_salah_arah == kunci:
        k_salah_arah = str(int(kunci) + 1)
    if k_lupa == kunci or k_lupa == k_salah_arah:
        k_lupa = str(int(kunci) + 2)

    mal = [
        Malrule(f"waktu.salah_arah_{varian}", k_salah_arah, "K", "membalik arah konversi (dikali/dibagi yang salah)"),
        Malrule(f"waktu.lupa_{varian}", k_lupa, "K", "lupa mengkonversi — menjawab angka yang sama"),
        Malrule(f"waktu.kurang_satu", str(int(kunci) - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "satuan_waktu_lama",
        {"varian": varian, "nilai": nilai, "hasil": hasil},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        pembahasan=(
            f"Langkah: ingat 1 windu = 8 tahun, 1 dasawarsa = 10 tahun, "
            f"1 abad = 100 tahun. Hasil konversinya {kunci}."
        ),
        bagian="B",
    )


@soal_berversi
def jam_menit_detik(varian: str, jam: int, menit: int, detik: int) -> Soal:
    """Konversi jam↔menit↔detik; varian durasi (jam:menit ke menit total)."""
    if varian == "jam_ke_menit":
        kunci = str(jam * 60)
        teks = f"{jam} jam = berapa menit?"
        k_terbalik = str(jam // 60)
        k_lupa = str(jam)
    elif varian == "menit_ke_jam":
        kunci = str(menit // 60)
        teks = f"{menit} menit = berapa jam?"
        k_terbalik = str(menit * 60)
        k_lupa = str(menit)
    elif varian == "menit_ke_detik":
        kunci = str(menit * 60)
        teks = f"{menit} menit = berapa detik?"
        k_terbalik = str(menit // 60)
        k_lupa = str(menit)
    elif varian == "detik_ke_menit":
        kunci = str(detik // 60)
        teks = f"{detik} detik = berapa menit?"
        k_terbalik = str(detik * 60)
        k_lupa = str(detik)
    elif varian == "jam_ke_detik":
        kunci = str(jam * 3600)
        teks = f"{jam} jam = berapa detik?"
        k_terbalik = str(jam // 3600)
        k_lupa = str(jam)
    elif varian == "detik_ke_jam":
        kunci = str(detik // 3600)
        teks = f"{detik} detik = berapa jam?"
        k_terbalik = str(detik * 3600)
        k_lupa = str(detik)
    elif varian == "durasi_ke_menit":
        kunci = str(jam * 60 + menit)
        teks = f"{jam} jam {menit} menit = berapa menit?"
        k_terbalik = str(jam + menit // 60)
        k_lupa = str(jam)
    else:  # durasi_ke_detik
        kunci = str(jam * 3600 + menit * 60 + detik)
        teks = f"{jam} jam {menit} menit {detik} detik = berapa detik?"
        k_terbalik = str(jam * 60 + menit)
        k_lupa = str(jam * 3600 + menit * 60)

    if k_terbalik == kunci:
        k_terbalik = str(int(kunci) + 1)
    if k_lupa == kunci or k_lupa == k_terbalik:
        k_lupa = str(int(kunci) + 2)

    mal = [
        Malrule(f"jam.terbalik_{varian}", k_terbalik, "K", "membalik arah konversi"),
        Malrule(f"jam.lupa_{varian}", k_lupa, "K", "lupa mengkonversi — menjawab angka yang sama"),
        Malrule(f"jam.kurang_satu", str(int(kunci) - 1), "H", "perhitungan benar, hasilnya meleset satu"),
    ]
    return Soal(
        "jam_menit_detik",
        {"varian": varian, "jam": jam, "menit": menit, "detik": detik},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        pembahasan=(
            f"Langkah: 1 jam = 60 menit, 1 menit = 60 detik, "
            f"1 jam = 3600 detik. Hasilnya {kunci}."
        ),
        bagian="B",
    )


# ── Empat jenis soal baru (gelombang 2, 2 Sep 2026) ────────────────────
#
# Paket ini adalah sisa terakhir gelombang 2: P4 18 bentuk kalimat, P5/P6
# 21 — di bawah ambang 25. Akar masalahnya bukan kalimat mati (ketiga
# template lama sudah punya 3, 10, dan 8 varian) melainkan paket ini cuma
# punya TIGA template, dan dua di antaranya sama-sama konversi waktu.
#
# Karena itu obatnya menambah JENIS soal, bukan latar cerita — sama
# seperti aritmetika-dasar, dan berbeda dari aritmatika-lanjut/geometri.
# Aturan yang dipakai sejak commit 2e8c912: latar diberi kalau ia bagian
# dari konsepnya, ditolak kalau ia cuma bungkus. Konversi satuan adalah
# perintah hitung berbesaran; membungkusnya jadi cerita menambah beban
# baca yang bukan sedang diuji.
#
# Empat jenis dipilih karena masing-masing membawa JALUR DIAGNOSIS yang
# belum ada di paket ini, bukan sekadar menambah kalimat:
#
#   satuan_kuantitas     lusin/kodi/gros/rim — satuan non-desimal, anak
#                        yang hafal "tangga ×10" tidak bisa menebaknya
#   tangga_satuan_campuran  km+hm+m dalam satu soal — miskonsepsi utama:
#                        semua suku dikali faktor yang sama
#   satuan_luas_volume   faktor 100 (luas) dan 1000 (volume) — inilah
#                        miskonsepsi terbesar di topik ini: anak memakai
#                        10 karena itu yang dihafal dari satuan panjang
#   jam_selesai          waktu mulai + durasi melewati batas jam, dan
#                        melewati tengah malam — anak menjumlahkan menit
#                        melewati 60 tanpa menaikkan jamnya
#
# Semuanya ada di silabus SD dan muncul di naskah OSN tingkat sekolah/
# kabupaten. Konversi luas & volume juga menutup sebagian gap "Statistika
# Data & Pengukuran" di riset 1.237 soal (arsip lokal ~/Documents/osn-resources/referensi/docs/riset-soal-osn-10-tahun.md).

# Satuan kuantitas dan isinya. Nilainya fakta, bukan pilihan desain:
# 1 lusin 12, 1 gros 12 lusin = 144, 1 kodi 20, 1 rim 500 lembar.
_KUANTITAS = {
    "lusin": (12, "buah"),
    "kodi": (20, "lembar"),
    "gros": (144, "buah"),
    "rim": (500, "lembar"),
}

# Benda yang WAJAR dihitung per satuan itu. Ini bukan latar cerita
# (soalnya tetap perintah hitung) melainkan bagian dari kesahihan
# satuannya: kodi dipakai untuk kain/sarung, rim untuk kertas, gros untuk
# barang kecil. "3 rim pensil" adalah fakta yang salah, dan soal yang
# faktanya salah mengajari anak hal yang salah.
_BENDA_KUANTITAS = {
    "lusin": ("pensil", "gelas", "sendok", "buku tulis"),
    "kodi": ("kain", "sarung", "handuk", "kaus"),
    "gros": ("kancing", "peniti", "karet gelang", "paku"),
    "rim": ("kertas HVS", "kertas folio", "kertas gambar"),
}


def satuan_kuantitas(satuan: str, benda: str, nilai: int, arah: str) -> Soal:
    """Konversi satuan kuantitas: lusin, kodi, gros, rim.

    Satuan non-desimal, dan itu justru gunanya: anak yang menghafal
    "tangga satuan dikali 10" tidak punya jalan pintas di sini — ia harus
    tahu isi tiap satuan. Malrule K memakai faktor satuan LAIN (mis.
    menghitung kodi sebagai 12), yang adalah kesalahan paling sering
    ketika empat satuan ini diajarkan berbarengan.
    """
    isi, _satuan_benda = _KUANTITAS[satuan]
    # Faktor satuan lain yang paling mudah tertukar — dipilih dari daftar
    # yang SAMA supaya malrule-nya benar-benar kesalahan yang mungkin,
    # bukan angka acak.
    tertukar = {"lusin": 20, "kodi": 12, "gros": 12, "rim": 100}[satuan]
    if arah == "ke_satuan":
        kunci = nilai * isi
        teks = f"{nilai} {satuan} {benda} = berapa {_satuan_benda}?"
        k_tertukar = nilai * tertukar
        langkah = (
            f"Langkah: 1 {satuan} = {isi} {_satuan_benda}. "
            f"{nilai} x {isi} = {kunci}."
        )
    else:  # ke_kuantitas
        kunci = nilai // isi
        teks = f"{nilai} {_satuan_benda} {benda} = berapa {satuan}?"
        k_tertukar = nilai // tertukar
        langkah = (
            f"Langkah: 1 {satuan} = {isi} {_satuan_benda}, jadi dibagi. "
            f"{nilai} : {isi} = {kunci}."
        )
    mal = [
        Malrule(
            f"kuantitas.faktor_tertukar_{satuan}",
            str(k_tertukar),
            "K",
            f"memakai isi satuan yang lain ({tertukar}), bukan isi 1 {satuan} "
            f"yang {isi}",
        ),
        Malrule(
            f"kuantitas.belum_dikonversi_{satuan}",
            str(nilai),
            "K",
            f"menyalin angka soal apa adanya — {satuan} belum diubah ke "
            f"{_satuan_benda} (atau sebaliknya)",
        ),
        Malrule(
            "kuantitas.kurang_satu",
            str(kunci - 1),
            "H",
            "cara sudah benar, hasilnya meleset satu",
        ),
    ]
    return Soal(
        "satuan_kuantitas",
        {"satuan": satuan, "benda": benda, "nilai": nilai, "arah": arah},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        pembahasan=langkah,
        bagian="C",
    )


# Tangga satuan panjang dan berat, dari yang terbesar. Indeks = jumlah
# tangga, jadi faktor = 10 ** selisih indeks.
_TANGGA_PANJANG = ("km", "hm", "dam", "m", "dm", "cm", "mm")
_TANGGA_BERAT = ("kg", "hg", "dag", "g", "dg", "cg", "mg")


def tangga_satuan_campuran(
    besaran: str, i1: int, i2: int, i3: int, a: int, b: int, c: int, tujuan: int
) -> Soal:
    """Jumlahkan tiga besaran bersatuan berbeda ke satu satuan tujuan.

    Beda dari `satuan_konversi` di aritmatika-lanjut, yang mengubah SATU
    nilai antar dua satuan. Di sini tiga suku bersatuan berbeda harus
    diubah masing-masing lebih dulu — dan itulah miskonsepsi yang diuji:
    anak yang mengalikan seluruh soal dengan satu faktor yang sama
    (biasanya faktor suku pertama) mendapat jawaban yang salah tanpa
    merasa salah, karena langkahnya "terlihat" benar.

    Satuan tujuan dijaga TIDAK lebih kecil dari ketiga satuan sumber
    (indeks tujuan >= indeks terkecil), supaya semua konversi menghasilkan
    bilangan bulat. Pecahan satuan bukan yang sedang diuji di sini dan
    membuat kunci punya banyak bentuk penulisan yang sah.
    """
    tangga = _TANGGA_PANJANG if besaran == "panjang" else _TANGGA_BERAT
    u1, u2, u3, ut = tangga[i1], tangga[i2], tangga[i3], tangga[tujuan]
    f1 = 10 ** (tujuan - i1)
    f2 = 10 ** (tujuan - i2)
    f3 = 10 ** (tujuan - i3)
    kunci = a * f1 + b * f2 + c * f3
    # K1: satu faktor untuk semua suku — faktor suku PERTAMA dipakai ke
    # seluruh jumlah (a+b+c) x f1.
    k_satu_faktor = (a + b + c) * f1
    # K2: tiap suku dikali 10 saja, berapa pun jarak tangganya.
    k_sepuluh = (a + b + c) * 10
    mal = [
        Malrule(
            f"tangga.satu_faktor_{besaran}",
            str(k_satu_faktor),
            "K",
            f"menjumlahkan angkanya dulu lalu mengalikan semua dengan {f1} — "
            f"tiap satuan punya jarak tangga sendiri",
        ),
        Malrule(
            f"tangga.selalu_sepuluh_{besaran}",
            str(k_sepuluh),
            "K",
            "mengalikan tiap suku dengan 10 — jaraknya lebih dari satu tangga",
        ),
        Malrule(
            "tangga.abaikan_suku_terakhir",
            str(a * f1 + b * f2),
            "B",
            "menjumlahkan dua suku pertama saja, suku terakhir terlewat",
        ),
        # Jalur H wajib ada (konvensi repo: tiap template minimal satu K
        # dan satu H). Di sini H berarti ketiga konversinya sudah benar
        # dan yang meleset hanya penjumlahan akhirnya — itu kesalahan
        # yang berbeda jenisnya dari dua K di atas, dan guru menanganinya
        # dengan cara yang berbeda pula (latih hitung, bukan latih konsep).
        Malrule(
            "tangga.jumlah_akhir_meleset",
            str(kunci - 1),
            "H",
            "konversi tiap satuan sudah benar, penjumlahan akhirnya "
            "meleset satu",
        ),
    ]
    teks = f"{a} {u1} + {b} {u2} + {c} {u3} = berapa {ut}?"
    return Soal(
        "tangga_satuan_campuran",
        {
            "besaran": besaran,
            "i1": i1, "i2": i2, "i3": i3,
            "a": a, "b": b, "c": c,
            "tujuan": tujuan,
        },
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        minta_restatement=True,
        pembahasan=(
            f"Langkah: ubah SATU PER SATU ke {ut} dulu, baru dijumlahkan. "
            f"{a} {u1} = {a * f1} {ut}, {b} {u2} = {b * f2} {ut}, "
            f"{c} {u3} = {c * f3} {ut}. Jumlahnya {kunci}."
        ),
        bagian="C",
        tantangan=True,
    )


# Satuan luas dan volume, dari yang terbesar. Faktor antar tangga: 100
# untuk luas, 1000 untuk volume — inilah yang sedang diuji.
_TANGGA_LUAS = ("km²", "hm²", "dam²", "m²", "dm²", "cm²")
_TANGGA_VOLUME = ("m³", "dm³", "cm³")
# Nama satuan tanah, dipetakan ke indeks _TANGGA_LUAS yang besarnya sama:
# 1 hektar = 1 hm², 1 are = 1 dam². Namanya berbeda tapi besarnya sama,
# dan justru itu yang sering ditanyakan di OSN tingkat sekolah — anak
# menghafal keduanya terpisah lalu tertukar.
_NAMA_TANAH = {1: "hektar", 2: "are", 3: "m²"}


def satuan_luas_volume(jenis: str, i1: int, i2: int, nilai: int) -> Soal:
    """Konversi satuan luas (×100 per tangga) atau volume (×1000).

    Ini jenis soal yang paling banyak menjaring miskonsepsi di seluruh
    topik pengukuran: anak menghafal "turun satu tangga dikali 10" dari
    satuan panjang dan memakainya di sini juga. Malrule K pertama menebak
    tepat kesalahan itu, jadi jawaban salahnya bisa dibaca sebagai
    diagnosis, bukan cuma "salah".

    Jenis "tanah" memakai nama hektar dan are, yang besarnya sama dengan
    hm² dan dam² — kesetaraan yang dihafal terpisah dan sering tertukar.
    """
    if jenis == "luas":
        tangga, faktor_tangga = _TANGGA_LUAS, 100
    elif jenis == "volume":
        tangga, faktor_tangga = _TANGGA_VOLUME, 1000
    else:  # tanah
        tangga, faktor_tangga = _TANGGA_LUAS, 100
    u1, u2 = tangga[i1], tangga[i2]
    jarak = i2 - i1
    if jenis == "tanah":
        # i1/i2 dibatasi ke indeks hektar (1), are (2), dan m² (3) di
        # _parameter; nama tanahnya yang ditampilkan, bukan hm²/dam².
        u1, u2 = _NAMA_TANAH[i1], _NAMA_TANAH[i2]
    kunci = nilai * (faktor_tangga ** jarak)
    # Faktor jenis yang SATUNYA — luas dan volume diajarkan berdekatan dan
    # angkanya (100 vs 1.000) paling sering tertukar antar keduanya.
    faktor_tertukar = 1000 if faktor_tangga == 100 else 100
    mal = [
        Malrule(
            f"luas_volume.faktor_sepuluh_{jenis}",
            str(nilai * (10 ** jarak)),
            "K",
            f"memakai faktor 10 per tangga seperti satuan panjang — "
            f"satuan {jenis if jenis != 'tanah' else 'luas'} naik "
            f"{faktor_tangga} tiap tangga",
        ),
        Malrule(
            f"luas_volume.faktor_tertukar_{jenis}",
            str(nilai * (faktor_tertukar ** jarak)),
            "K",
            f"memakai faktor {faktor_tertukar} — itu faktor satuan "
            f"{'volume' if faktor_tertukar == 1000 else 'luas'}, bukan "
            f"satuan {'luas' if faktor_tangga == 100 else 'volume'}",
        ),
        # H memakai (nilai-1) kelompok, bukan "satu tangga kurang": pada
        # jarak 1 "satu tangga kurang" justru menghasilkan kunci itu
        # sendiri, sehingga saring_malrule membuangnya dan soal kehilangan
        # SATU-SATUNYA jalur H. Ketahuan dengan membaca keluaran nyata:
        # "93 hektar = berapa are?" cuma menyisakan dua malrule.
        Malrule(
            f"luas_volume.kurang_satu_kelompok_{jenis}",
            str((nilai - 1) * (faktor_tangga ** jarak)),
            "H",
            f"cara dan faktornya sudah benar, tetapi hasil perkaliannya "
            f"meleset {faktor_tangga ** jarak}",
        ),
    ]
    teks = f"{nilai} {u1} = berapa {u2}?"
    return Soal(
        "satuan_luas_volume",
        {"jenis": jenis, "i1": i1, "i2": i2, "nilai": nilai},
        teks,
        str(kunci),
        saring_malrule(str(kunci), mal),
        pembahasan=(
            f"Langkah: satuan {'luas' if jenis != 'volume' else 'volume'} "
            f"turun satu tangga DIKALI {faktor_tangga} "
            f"(bukan 10 seperti satuan panjang). Dari {u1} ke {u2} "
            f"jaraknya {jarak} tangga, jadi {nilai} x "
            f"{faktor_tangga ** jarak} = {kunci}."
        ),
        bagian="D",
    )


def jam_selesai(
    varian: str, jam: int, menit: int, durasi_jam: int, durasi_menit: int
) -> Soal:
    """Waktu selesai / mulai / durasi, melewati batas jam.

    Berbeda dari `jam_menit_detik` yang hanya mengkonversi satu nilai.
    Di sini anak harus menjumlahkan waktu dalam sistem 60, dan parameter
    dijaga supaya penjumlahan menitnya SELALU melewati 60 — kalau tidak,
    soalnya bisa dijawab benar tanpa menaikkan jam sama sekali dan
    malrule "menit lebih dari 60" akan menebak kunci.

    Format 24 jam dengan titik ("14.20") dipakai karena itu format yang
    dipakai jadwal di Indonesia dan di naskah OSN. Titik di sini BUKAN
    desimal; `diagnosis.normalisasi` tidak mengubah titik antar angka
    yang diapit huruf, dan kunci tetap dibandingkan sebagai teks.
    """
    total_mulai = jam * 60 + menit
    total_durasi = durasi_jam * 60 + durasi_menit
    total_selesai = total_mulai + total_durasi

    def jam_teks(total: int) -> str:
        total %= 24 * 60
        return f"{total // 60:02d}.{total % 60:02d}"

    mulai_teks = jam_teks(total_mulai)
    selesai_teks = jam_teks(total_selesai)
    if varian == "cari_selesai":
        kunci = selesai_teks
        teks = (
            f"Sebuah kegiatan mulai pukul {mulai_teks} dan berlangsung "
            f"{durasi_jam} jam {durasi_menit} menit. Pukul berapa selesai?"
        )
        # K: menit dijumlahkan melewati 60 tanpa menaikkan jam —
        # 14.20 + 0.50 ditulis "14.70".
        k_menit_lewat = f"{(jam + durasi_jam) % 24:02d}.{menit + durasi_menit:02d}"
        k_arah = jam_teks(total_mulai - total_durasi)
        langkah = (
            f"Langkah: {mulai_teks} + {durasi_jam} jam = "
            f"{jam_teks(total_mulai + durasi_jam * 60)}, lalu + "
            f"{durasi_menit} menit. Setiap 60 menit menjadi 1 jam, "
            f"jadi selesai pukul {kunci}."
        )
    elif varian == "cari_mulai":
        kunci = mulai_teks
        teks = (
            f"Sebuah kegiatan selesai pukul {selesai_teks} setelah "
            f"berlangsung {durasi_jam} jam {durasi_menit} menit. "
            f"Pukul berapa kegiatan itu mulai?"
        )
        k_menit_lewat = (
            f"{(total_selesai // 60 - durasi_jam) % 24:02d}."
            f"{abs(total_selesai % 60 - durasi_menit):02d}"
        )
        k_arah = jam_teks(total_selesai + total_durasi)
        langkah = (
            f"Langkah: dari {selesai_teks} hitung MUNDUR "
            f"{durasi_jam} jam {durasi_menit} menit. Kalau menitnya tidak "
            f"cukup, pinjam 60 menit dari jamnya. Mulainya pukul {kunci}."
        )
    else:  # cari_durasi
        kunci = f"{total_durasi // 60} jam {total_durasi % 60} menit"
        teks = (
            f"Sebuah kegiatan mulai pukul {mulai_teks} dan selesai pukul "
            f"{selesai_teks}. Berapa lama kegiatan itu berlangsung?"
        )
        # K: kurangkan jam dan menit apa adanya, termasuk menit negatif
        # yang ditulis sebagai selisih positif.
        selisih_jam = (total_selesai // 60) % 24 - jam
        k_menit_lewat = (
            f"{selisih_jam} jam {abs(total_selesai % 60 - menit)} menit"
        )
        # "Pinjam menit tapi lupa menurunkan jamnya" — kesalahan yang
        # BERBEDA dari K1: di sini menitnya sudah benar (39), jamnya yang
        # belum dikurangi setelah meminjam. Versi pertama memakai
        # "60 - menit" yang bukan kesalahan yang dilakukan anak mana pun;
        # ketahuan dengan membaca keluarannya, bukan dari test yang lolos.
        k_arah = f"{selisih_jam} jam {total_durasi % 60} menit"
        langkah = (
            f"Langkah: dari {mulai_teks} ke {selesai_teks}. Hitung selisih "
            f"jamnya dulu, lalu selisih menitnya; kalau menit selesai lebih "
            f"kecil, pinjam 60 menit dari jamnya. Lamanya {kunci}."
        )
    mal = [
        Malrule(
            f"jam_selesai.menit_lewat_enam_puluh_{varian}",
            k_menit_lewat,
            "K",
            "menjumlahkan atau mengurangkan menit apa adanya — setiap 60 "
            "menit harus menjadi 1 jam",
        ),
        Malrule(
            f"jam_selesai.arah_atau_pinjam_{varian}",
            k_arah,
            "K",
            (
                "menit sudah dipinjam dengan benar, tetapi jamnya lupa "
                "diturunkan satu"
                if varian == "cari_durasi"
                else "arah hitungnya terbalik — dikurangi padahal harus "
                "ditambah, atau sebaliknya"
            ),
        ),
        Malrule(
            f"jam_selesai.geser_satu_menit_{varian}",
            (
                jam_teks(total_selesai - 1)
                if varian == "cari_selesai"
                else jam_teks(total_mulai - 1)
                if varian == "cari_mulai"
                else f"{total_durasi // 60} jam {total_durasi % 60 - 1} menit"
            ),
            "H",
            "cara sudah benar, hasilnya meleset satu menit",
        ),
    ]
    return Soal(
        "jam_selesai",
        {
            "varian": varian,
            "jam": jam,
            "menit": menit,
            "durasi_jam": durasi_jam,
            "durasi_menit": durasi_menit,
        },
        teks,
        kunci,
        saring_malrule(kunci, mal),
        minta_restatement=True,
        pembahasan=langkah,
        bagian="B",
    )


# ── Registry ─────────────────────────────────────────────────────────────

REGISTRI_TOPIK = {
    "skala_peta": skala_peta,
    "satuan_waktu_lama": satuan_waktu_lama,
    "jam_menit_detik": jam_menit_detik,
    "satuan_kuantitas": satuan_kuantitas,
    "tangga_satuan_campuran": tangga_satuan_campuran,
    "satuan_luas_volume": satuan_luas_volume,
    "jam_selesai": jam_selesai,
}

# Komposisi 10 soal per lembar. Keempat template baru masuk di SEMUA
# level yang sahih: template yang terdaftar tapi tidak dipakai adalah
# "template tidur", dan gelombang 1 sudah membuktikan menambah template
# tanpa memakainya tidak memperbaiki apa pun.
#
# `skala_peta` tetap P5+ (perbandingan belum diajarkan di P4).
# `satuan_luas_volume` juga P5+ dengan alasan yang sama kuatnya: satuan
# luas dan volume baru masuk kurikulum kelas 5.
KOMPOSISI = {
    "P4": (
        "satuan_waktu_lama", "jam_menit_detik", "satuan_kuantitas",
        "jam_selesai", "tangga_satuan_campuran",
        "satuan_waktu_lama", "jam_menit_detik", "satuan_kuantitas",
        "jam_selesai", "tangga_satuan_campuran",
    ),
    "P5": (
        "skala_peta", "satuan_waktu_lama", "jam_menit_detik",
        "satuan_kuantitas", "tangga_satuan_campuran", "satuan_luas_volume",
        "jam_selesai", "skala_peta", "satuan_luas_volume", "jam_selesai",
    ),
    "P6": (
        "skala_peta", "satuan_waktu_lama", "jam_menit_detik",
        "satuan_kuantitas", "tangga_satuan_campuran", "satuan_luas_volume",
        "jam_selesai", "skala_peta", "satuan_luas_volume",
        "tangga_satuan_campuran",
    ),
}

JUDUL_BAGIAN = {
    "A": "Bagian A — Skala peta",
    "B": "Bagian B — Waktu & konversi",
    "C": "Bagian C — Satuan kuantitas & tangga satuan",
    "D": "Bagian D — Satuan luas & volume",
}

CATATAN_BAGIAN = {
    "A": "Skala = jarak peta : jarak sebenarnya. Ubah km ke cm dulu (×100.000).",
    "B": "1 abad=100 tahun, 1 windu=8 tahun, 1 lustrum=5 tahun, 1 dasawarsa=10 tahun.",
    "C": "1 lusin=12, 1 kodi=20, 1 gros=144, 1 rim=500. Tangga panjang/berat ×10 per tangga.",
    "D": "Satuan luas ×100 tiap tangga, volume ×1000 — bukan ×10. 1 hektar=1 hm², 1 are=1 dam².",
}


def _diagnosis_utuh(soal: Soal, harap: int = 3) -> bool:
    """True kalau ketiga jalur diagnosis soal ini selamat.

    `saring_malrule` membuang malrule yang menebak kunci atau menebak
    jawaban yang sama dengan malrule lain. Itu penyelamat yang benar,
    tapi ia bekerja DIAM-DIAM: soal yang kehilangan jalur K tetap sah
    dan tetap tercetak, hanya saja jawaban salah anak tidak lagi bisa
    dibaca sebagai miskonsepsi tertentu.

    Dua template baru (`tangga_satuan_campuran`, `jam_selesai`) punya
    ruang parameter yang membuat tabrakan itu sering: jarak tangga yang
    kebetulan sama membuat "satu faktor untuk semua" menebak kunci, dan
    durasi yang bulat membuat "menit tidak dibawa" menebak kunci. Karena
    itu kelayakannya disaring di `_parameter`, bukan dipasrahkan.

    Jumlah yang diharapkan diberikan pemanggil karena tidak seragam:
    `tangga_satuan_campuran` punya empat (K, K, B, H), sisanya tiga.
    Yang dijaga adalah "tidak ada yang hilang", bukan angka tertentu.
    """
    return len(soal.malrule) == harap


@parameter_baru
def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id == "skala_peta":
        varian = rng.choice(("cari_skala", "cari_peta", "cari_sebenarnya"))
        # pilih skala dan jarak peta yang menghasilkan jarak sebenarnya bulat
        skala = rng.choice((100000, 250000, 500000, 1000000, 2000000, 5000000))
        peta = rng.randint(1, 50)
        sebenarnya = peta * skala // 100000  # km
        return {"varian": varian, "sebenarnya": sebenarnya, "peta": peta, "skala": skala}
    if template_id == "satuan_waktu_lama":
        varian = rng.choice((
            "abad_ke_tahun", "tahun_ke_abad",
            "windu_ke_tahun", "tahun_ke_windu",
            "lustrum_ke_tahun", "tahun_ke_lustrum",
            "dasawarsa_ke_tahun", "tahun_ke_dasawarsa",
            "windu_ke_lustrum", "abad_ke_dasawarsa",
        ))
        if varian == "windu_ke_lustrum":
            # 1 windu = 8/5 lustrum = 1,6 lustrum
            # pilih n kelipatan 5 → n×8/5 bulat; rentang lebar supaya ≥200 combo
            nilai = rng.randint(1, 50) * 5
            hasil = nilai * 8 // 5
        elif varian == "abad_ke_dasawarsa":
            # 1 abad = 10 dasawarsa (integer)
            nilai = rng.randint(1, 50)
            hasil = nilai * 10
        elif varian in ("abad_ke_tahun", "windu_ke_tahun", "lustrum_ke_tahun", "dasawarsa_ke_tahun"):
            # besar → kecil: ×faktor (integer)
            faktor = {"abad_ke_tahun": 100, "windu_ke_tahun": 8, "lustrum_ke_tahun": 5, "dasawarsa_ke_tahun": 10}[varian]
            nilai = rng.randint(1, 100)
            hasil = nilai * faktor
        else:
            # kecil → besar: ÷faktor (integer). Pilih nilai kelipatan faktor.
            faktor = {"tahun_ke_abad": 100, "tahun_ke_windu": 8, "tahun_ke_lustrum": 5, "tahun_ke_dasawarsa": 10}[varian]
            nilai = rng.randint(1, 50) * faktor
            hasil = nilai // faktor
        return {"varian": varian, "nilai": nilai, "hasil": hasil}
    if template_id == "jam_menit_detik":
        varian = rng.choice((
            "jam_ke_menit", "menit_ke_jam",
            "menit_ke_detik", "detik_ke_menit",
            "jam_ke_detik", "detik_ke_jam",
            "durasi_ke_menit", "durasi_ke_detik",
        ))
        jam = rng.randint(1, 23)
        menit = rng.randint(0, 59)
        detik = rng.randint(0, 59)
        if varian in ("menit_ke_jam", "detik_ke_menit", "detik_ke_jam"):
            menit = rng.randint(60, 600)  # menit/detik besar untuk dibagi
            detik = rng.randint(60, 3600)
            jam = 1
        return {"varian": varian, "jam": jam, "menit": menit, "detik": detik}

    # ── Parameter empat template baru (gelombang 2) ────────────────────
    if template_id == "satuan_kuantitas":
        satuan = rng.choice(("lusin", "kodi", "gros", "rim"))
        benda = rng.choice(_BENDA_KUANTITAS[satuan])
        arah = rng.choice(("ke_satuan", "ke_kuantitas"))
        isi = _KUANTITAS[satuan][0]
        # P4 memakai angka kecil; P5/P6 lebih besar. Rentang cukup lebar
        # supaya guard >= 200 kombinasi di test_parameter_variants lewat
        # (4 satuan x 3-4 benda x 2 arah x rentang ini).
        atas = 24 if level == "P4" else 60
        while True:
            banyak = rng.randint(2, atas)
            # Arah "ke_kuantitas" WAJIB kelipatan isi: kalau tidak, kuncinya
            # dibulatkan diam-diam oleh pembagian bulat dan anak yang
            # menjawab sisa yang benar tercatat salah.
            nilai = banyak if arah == "ke_satuan" else banyak * isi
            param = {
                "satuan": satuan, "benda": benda, "nilai": nilai, "arah": arah,
            }
            # Angka kecil membuat jalur H tertelan: "24 buah = berapa
            # lusin?" berkunci 2, dan K "isi satuan tertukar" (24 : 20 = 1)
            # kebetulan sama dengan H (kunci - 1 = 1), jadi saring_malrule
            # membuang H dan soal kehilangan satu jalur diagnosis.
            # Ketahuan dengan MEMBACA keluaran nyata, bukan dari test hijau.
            if _diagnosis_utuh(satuan_kuantitas(**param)):
                return param

    if template_id == "tangga_satuan_campuran":
        besaran = rng.choice(("panjang", "berat"))
        # Tiga satuan BERBEDA, urut dari yang terbesar — itu cara soal ini
        # ditulis di buku ("2 km + 3 hm + 45 m"). Satuan tujuan tidak boleh
        # lebih besar dari satuan terkecil, kalau tidak hasilnya pecahan
        # dan kunci punya banyak bentuk penulisan yang sama sahihnya.
        lebar = 4 if level == "P4" else 6
        while True:
            i1, i2, i3 = sorted(rng.sample(range(lebar), 3))
            tujuan = rng.choice(range(i3, min(i3 + 2, 7)))
            a = rng.randint(1, 9)
            b = rng.randint(1, 9)
            c = rng.randint(1, 99)
            param = {
                "besaran": besaran,
                "i1": i1, "i2": i2, "i3": i3,
                "a": a, "b": b, "c": c,
                "tujuan": tujuan,
            }
            # Dijaga di sini, bukan dipasrahkan ke saring_malrule: kalau
            # dua jalur bertabrakan, malrule-nya dibuang diam-diam dan
            # soalnya kehilangan K atau B tanpa terlihat dari kode.
            if _diagnosis_utuh(tangga_satuan_campuran(**param), harap=4):
                return param

    if template_id == "satuan_luas_volume":
        jenis = rng.choice(("luas", "volume", "tanah"))
        if jenis == "volume":
            # m3 -> dm3 -> cm3; jarak 2 hanya di P6 (faktornya sejuta).
            i1 = rng.choice((0, 1))
            jarak = 1 if level != "P6" else rng.choice((1, 2))
            i2 = min(i1 + jarak, 2)
        elif jenis == "tanah":
            # Hanya hektar/are/m2 yang punya nama tanah (indeks 1..3).
            i1 = rng.choice((1, 2))
            i2 = rng.choice(range(i1 + 1, 4))
        else:
            i1 = rng.choice(range(0, 4))
            i2 = rng.choice(range(i1 + 1, min(i1 + 3, 6)))
        atas = 40 if level == "P4" else 99
        return {"jenis": jenis, "i1": i1, "i2": i2, "nilai": rng.randint(2, atas)}

    if template_id == "jam_selesai":
        varian = rng.choice(("cari_selesai", "cari_mulai", "cari_durasi"))
        while True:
            jam = rng.randint(5, 21)
            menit = rng.randint(5, 55)
            durasi_jam = rng.randint(1, 4 if level == "P4" else 6)
            durasi_menit = rng.randint(5, 55)
            # Penjumlahan menit WAJIB melewati 60. Kalau tidak, soalnya
            # bisa dijawab benar tanpa menaikkan jam sama sekali — dan
            # malrule "menit tidak dibawa ke jam" akan menebak KUNCI,
            # sehingga anak yang benar tercatat punya miskonsepsi.
            if menit + durasi_menit <= 60:
                continue
            param = {
                "varian": varian,
                "jam": jam,
                "menit": menit,
                "durasi_jam": durasi_jam,
                "durasi_menit": durasi_menit,
            }
            if _diagnosis_utuh(jam_selesai(**param)):
                return param

    raise KeyError(f"template tidak dikenal: {template_id}")


TOPIK = Topik(
    id="pengukuran",
    nama="Pengukuran",
    judul_lembar="Latihan Pengukuran",
    judul_penilaian="Penilaian — Pengukuran",
    templates=REGISTRI_TOPIK,
    komposisi=KOMPOSISI,
    profil={"P4": {}, "P5": {}, "P6": {}},
    judul_bagian=JUDUL_BAGIAN,
    catatan_bagian=CATATAN_BAGIAN,
    parameter_untuk=_parameter,
)

daftarkan(TOPIK)