"""Template Pengukuran bagian C: kalender asli 2026/2027.

Tanggal dan nama hari dihitung dari kalender sungguhan (`datetime.date`), bukan tabel buatan sendiri,
jadi panjang bulan dan tahun kabisat ikut benar.
Tanggal hanya dari 1 Januari 2026 sampai 31 Desember 2027 (tahun kabisat tetap benar karena kalender
asli). Didaftarkan lewat impor di `contest_templates_measurement`.
"""
from __future__ import annotations

import datetime as dt

import contest_core as C

NAMA_HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
NAMA_BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
              "September", "Oktober", "November", "Desember")
HARI_PER_MINGGU = 7
HARI_PER_BULAN_ANGGAPAN = 30
AWAL_KALENDER = dt.date(2026, 1, 1)
AKHIR_KALENDER = dt.date(2027, 12, 31)
HARI_RENTANG = (AKHIR_KALENDER - AWAL_KALENDER).days + 1     # 730 hari: kalender 2026 dan 2027
SELANG_MIN, SELANG_MAKS = 3, 40
PELUANG_MUNDUR = 3               # 1 dari 3 soal bertanya tanggal yang lebih awal
N_LAGI_MIN, N_LAGI_MAKS = 8, 60
PERCOBAAN = 40
IKON_KALENDER = "\U0001F4C5 "


def _tgl(tahun: int, bulan: int, hari: int) -> dt.date:
    try:
        return dt.date(tahun, bulan, hari)
    except ValueError as galat:
        raise C.ParameterTidakSah(f"tanggal tidak ada: {tahun}-{bulan}-{hari}") from galat


def _hari_ke(tanggal: dt.date) -> int:
    """Indeks hari (0 = Senin) dari nomor urut hari kalender; nomor 1 jatuh pada hari Senin."""
    return (tanggal.toordinal() - 1) % HARI_PER_MINGGU


def _tulis(tanggal: dt.date) -> str:
    return f"{tanggal.day} {NAMA_BULAN[tanggal.month - 1]} {tanggal.year}"


def _panjang_bulan(tahun: int, bulan: int) -> int:
    awal_depan = dt.date(tahun + bulan // 12, bulan % 12 + 1, 1)
    return (awal_depan - dt.date(tahun, bulan, 1)).days


def _komponen(tanggal: dt.date):
    return {"tahun": tanggal.year, "bulan": tanggal.month, "hari": tanggal.day}


def _acak_tanggal(rng, selisih_hari: int) -> dt.date:
    """Tanggal acak yang masih berada di 2026-2027 setelah ditambah `selisih_hari`."""
    return AWAL_KALENDER + dt.timedelta(days=rng.randrange(HARI_RENTANG - selisih_hari))


def _dalam_kalender(*tanggal: dt.date) -> None:
    if any(not AWAL_KALENDER <= t <= AKHIR_KALENDER for t in tanggal):
        raise C.ParameterTidakSah("tanggal di luar kalender 2026-2027")


# --- ukur_kalender_hari ------------------------------------------------------------------------

def _sampler_kalender_hari(rng):
    selang = rng.randint(SELANG_MIN, SELANG_MAKS)
    pertama = _acak_tanggal(rng, selang)
    kedua = pertama + dt.timedelta(days=selang)
    if rng.randrange(PELUANG_MUNDUR) == 0:
        pertama, kedua = kedua, pertama
    return {"t1": [pertama.year, pertama.month, pertama.day],
            "t2": [kedua.year, kedua.month, kedua.day]}


def _hari_anggapan_30(tanggal: dt.date) -> int:
    """Nomor urut hari bila setiap bulan dianggap 30 hari (kesalahan anak)."""
    return (tanggal.year * 12 + tanggal.month) * HARI_PER_BULAN_ANGGAPAN + tanggal.day


def _pengecoh_kalender_hari(t1: dt.date, t2: dt.date):
    awal = _hari_ke(t1)
    selisih = t2.toordinal() - t1.toordinal()
    benar = (awal + selisih) % HARI_PER_MINGGU
    salah_30 = (awal + _hari_anggapan_30(t2) - _hari_anggapan_30(t1)) % HARI_PER_MINGGU
    kandidat = [
        (salah_30, "menganggap setiap bulan 30 hari"),
        (benar + 1, "salah satu hari karena ikut menghitung hari pertama"),
        (benar - 1, "salah satu hari karena lupa menghitung hari batas"),
        (awal, "menjawab hari yang sama dengan tanggal pertama"),
        (awal - selisih, "menghitung hari ke arah yang terbalik"),
        (benar + 2, "salah dua hari saat menghitung sisa bagi tujuh"),
        (benar - 2, "salah dua hari saat menghitung sisa bagi tujuh, ke arah sebaliknya"),
    ]
    return [C.Pengecoh(NAMA_HARI[nilai % HARI_PER_MINGGU], label) for nilai, label in kandidat]


def _langkah_kalender_hari(t1: dt.date, t2: dt.date, kunci: str):
    selisih = t2.toordinal() - t1.toordinal()
    jarak = abs(selisih)
    arah = "maju" if selisih > 0 else "mundur"
    minggu, sisa = divmod(jarak, HARI_PER_MINGGU)
    langkah = [f"Dari {_tulis(t1)} ke {_tulis(t2)} selisihnya {jarak} hari."]
    if (t1.year, t1.month) != (t2.year, t2.month):
        langkah.append(f"Lintas bulan: bulan {NAMA_BULAN[t1.month - 1]} {t1.year} punya "
                       f"{_panjang_bulan(t1.year, t1.month)} hari.")
    langkah.append(f"{jarak} hari = {minggu} minggu lebih {sisa} hari; tiap minggu harinya kembali sama.")
    hari1 = NAMA_HARI[_hari_ke(t1)]
    langkah.append(f"{hari1} {arah} {sisa} hari menjadi {kunci}." if sisa else f"Sisa 0 hari, tetap {kunci}.")
    langkah.append(f"Jadi {_tulis(t2)} jatuh pada hari {kunci}.")
    return tuple(langkah)


def _bangun_kalender_hari(p):
    t1, t2 = _tgl(*p["t1"]), _tgl(*p["t2"])
    if t1 == t2:
        raise C.ParameterTidakSah("dua tanggal sama")
    _dalam_kalender(t1, t2)
    kunci = NAMA_HARI[_hari_ke(t2)]
    pengecoh = C.ambil_pengecoh(kunci, _pengecoh_kalender_hari(t1, t2))
    return C.SoalLomba(
        template_id="ukur_kalender_hari", topik="pengukuran", jenis=C.JENIS_PG, tingkat=2,
        teks=f"{IKON_KALENDER}Tanggal {_tulis(t1)} hari {NAMA_HARI[_hari_ke(t1)]}. "
             f"Tanggal {_tulis(t2)} hari apa?",
        svg="", kunci=kunci, pengecoh=pengecoh,
        pembahasan=_langkah_kalender_hari(t1, t2, kunci), parameter=C.kanonik(p), nilai=None)


def _verifikator_kalender_hari(p):
    return NAMA_HARI[dt.date(*p["t2"]).weekday()]


C.daftarkan(C.Template(id="ukur_kalender_hari", topik="pengukuran", jenis=C.JENIS_PG, tingkat=2,
                       sampler=_sampler_kalender_hari, bangun=_bangun_kalender_hari,
                       verifikator=_verifikator_kalender_hari))


# --- ukur_kalender_n_hari_lagi -----------------------------------------------------------------

def _sampler_n_hari_lagi(rng):
    tanya = rng.choice(("hari", "tanggal"))
    for _ in range(PERCOBAAN):
        n = rng.randint(N_LAGI_MIN, N_LAGI_MAKS)
        awal = _acak_tanggal(rng, n)
        akhir = awal + dt.timedelta(days=n)
        if tanya == "hari" or (awal.year, awal.month) != (akhir.year, akhir.month):
            return {**_komponen(awal), "n": n, "tanya": tanya}
    raise C.ParameterTidakSah("tidak ada tanggal yang melintas bulan")


def _tanggal_anggapan_30(awal: dt.date, n: int) -> str:
    """Tanggal tujuan bila setiap bulan dianggap 30 hari, ditulis seperti kunci."""
    urut = (awal.year * 12 + awal.month - 1) * HARI_PER_BULAN_ANGGAPAN + awal.day - 1 + n
    bulan_ke, hari = divmod(urut, HARI_PER_BULAN_ANGGAPAN)
    tahun, bulan = divmod(bulan_ke, 12)
    return f"{hari + 1} {NAMA_BULAN[bulan]} {tahun}"


def _tanggal_geser(akhir: dt.date, geser: int) -> str:
    return _tulis(dt.date.fromordinal(akhir.toordinal() + geser))


def _pengecoh_n_tanggal(awal: dt.date, n: int, akhir: dt.date):
    kandidat = [
        (_tanggal_anggapan_30(awal, n), "menganggap setiap bulan 30 hari saat melintas bulan"),
        (_tanggal_geser(akhir, 1), "salah satu hari karena ikut menghitung hari ini"),
        (_tanggal_geser(akhir, -1), "salah satu hari karena lupa menghitung hari terakhir"),
        (_tanggal_geser(akhir, HARI_PER_MINGGU), "salah menghitung satu minggu terlalu banyak"),
        (_tanggal_geser(akhir, -HARI_PER_MINGGU), "salah menghitung satu minggu terlalu sedikit"),
        (_tanggal_geser(akhir, 2), "salah dua hari saat melintas bulan"),
    ]
    return [C.Pengecoh(nilai, label) for nilai, label in kandidat]


def _pengecoh_n_hari(awal: dt.date, n: int):
    dasar = _hari_ke(awal)
    benar = (dasar + n) % HARI_PER_MINGGU
    kandidat = [
        (benar + 1, "salah satu hari karena ikut menghitung hari ini"),
        (benar - 1, "salah satu hari karena lupa menghitung hari terakhir"),
        (dasar, "mengira hari yang sama dengan hari ini"),
        (dasar + n // HARI_PER_MINGGU, "mengira tiap minggu menggeser satu hari"),
        (dasar - n % HARI_PER_MINGGU, "menghitung mundur padahal harus maju"),
        (benar + 2, "salah dua hari saat menghitung sisa bagi tujuh"),
    ]
    return [C.Pengecoh(NAMA_HARI[nilai % HARI_PER_MINGGU], label) for nilai, label in kandidat]


def _langkah_lintas_bulan(awal: dt.date, n: int):
    """Satu baris per bulan yang dilewati, lalu tanggal tujuan."""
    sisa, kini, langkah = n, awal, []
    while True:
        panjang = _panjang_bulan(kini.year, kini.month)
        sampai_akhir = panjang - kini.day
        if sisa <= sampai_akhir:
            tujuan = dt.date.fromordinal(kini.toordinal() + sisa)
            langkah.append(f"Maju {sisa} hari dari {_tulis(kini)} sampai {_tulis(tujuan)}." if sisa
                           else f"Sisanya 0 hari, jadi tepat jatuh pada {_tulis(kini)}.")
            return langkah
        langkah.append(f"Bulan {NAMA_BULAN[kini.month - 1]} {kini.year} punya {panjang} hari; "
                       f"dari tanggal {kini.day} ada {sampai_akhir} hari sampai akhir bulan.")
        sisa -= sampai_akhir + 1
        kini = dt.date.fromordinal(kini.toordinal() + sampai_akhir + 1)
        langkah.append(f"Sekarang tanggal 1 {NAMA_BULAN[kini.month - 1]} {kini.year}; sisa {sisa} hari lagi.")


def _langkah_n_hari(awal: dt.date, n: int, kunci: str):
    minggu, sisa = divmod(n, HARI_PER_MINGGU)
    hari0 = NAMA_HARI[_hari_ke(awal)]
    langkah = [f"{n} hari = {minggu} minggu lebih {sisa} hari.",
               f"Setelah {minggu} minggu, harinya kembali {hari0}."]
    langkah.append(f"{hari0} maju {sisa} hari menjadi {kunci}." if sisa else f"Sisa 0 hari, tetap {kunci}.")
    langkah.append(f"Jadi {n} hari lagi adalah hari {kunci}.")
    return tuple(langkah)


def _bangun_n_hari_lagi(p):
    awal = _tgl(p["tahun"], p["bulan"], p["hari"])
    n = p["n"]
    akhir = dt.date.fromordinal(awal.toordinal() + n)
    _dalam_kalender(awal, akhir)
    if p["tanya"] == "hari":
        kunci = NAMA_HARI[_hari_ke(akhir)]
        pengecoh = C.ambil_pengecoh(kunci, _pengecoh_n_hari(awal, n))
        tanya, langkah = "hari apa", _langkah_n_hari(awal, n, kunci)
    else:
        kunci = _tulis(akhir)
        pengecoh = C.ambil_pengecoh(kunci, _pengecoh_n_tanggal(awal, n, akhir))
        tanya = "tanggal berapa"
        langkah = tuple(_langkah_lintas_bulan(awal, n)) + (f"Jadi {n} hari lagi adalah {kunci}.",)
    return C.SoalLomba(
        template_id="ukur_kalender_n_hari_lagi", topik="pengukuran", jenis=C.JENIS_PG, tingkat=3,
        teks=f"{IKON_KALENDER}Hari ini hari {NAMA_HARI[_hari_ke(awal)]}, {_tulis(awal)}. "
             f"{n} hari lagi adalah {tanya}?",
        svg="", kunci=kunci, pengecoh=pengecoh, pembahasan=langkah,
        parameter=C.kanonik(p), nilai=None)


def _verifikator_n_hari_lagi(p):
    tujuan = dt.date(p["tahun"], p["bulan"], p["hari"]) + dt.timedelta(days=p["n"])
    if p["tanya"] == "hari":
        return NAMA_HARI[tujuan.weekday()]
    return f"{tujuan.day} {NAMA_BULAN[tujuan.month - 1]} {tujuan.year}"


C.daftarkan(C.Template(id="ukur_kalender_n_hari_lagi", topik="pengukuran", jenis=C.JENIS_PG, tingkat=3,
                       sampler=_sampler_n_hari_lagi, bangun=_bangun_n_hari_lagi,
                       verifikator=_verifikator_n_hari_lagi))
