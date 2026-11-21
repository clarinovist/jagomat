"""Template topik Pengukuran untuk Latihan Lomba, keluarga jam analog.

Memuat `ukur_jam_analog`, `ukur_lama_kegiatan`, dan `ukur_lama_menit`. Template lain topik ini
ada di `contest_templates_measurement_b` (uang, minggu, klip, timbangan) dan
`contest_templates_measurement_c` (kalender); keduanya diimpor di akhir modul ini.

Aturan jam: teks selalu menyebut pagi/siang/sore/malam; jawaban format 24 jam "08.30". Durasi tidak
pernah menyeberang batas bagian hari, jadi tidak ada soal jam yang ambigu.
"""
from __future__ import annotations

import contest_core as C
import contest_svg_measurement as S

# Jam (format 24 jam) yang termasuk tiap bagian hari.
BAGIAN_JAM = {
    "pagi": range(6, 12),
    "siang": range(12, 15),
    "sore": range(15, 18),
    "malam": range(18, 24),
}
# Pagi dan malam punya lebih banyak jam, jadi diberi bobot lebih agar sebaran jam merata.
BAGIAN_BOBOT = ("pagi", "pagi", "siang", "sore", "malam", "malam")
MENIT_KELIPATAN_5 = tuple(range(0, 60, 5))
MENIT_PER_JAM = 60
HARI_MENIT = 24 * MENIT_PER_JAM
KEGIATAN = ("belajar", "bermain", "menggambar", "membaca", "berlatih", "bernyanyi")
DURASI_MIN_KEGIATAN = 30
DURASI_MAKS_KEGIATAN = 180
DURASI_MIN_MENIT = 35
LANGKAH_MENIT = 5
PERCOBAAN_PINJAM = 40
SETENGAH_JAM = 30


def _jam24(bagian: str, jam12: int) -> int:
    """Jam 24 jam dari angka di muka jam (1-12) dan bagian hari; tidak ada -> parameter diulang."""
    cocok = [jam for jam in BAGIAN_JAM[bagian] if jam % 12 == jam12 % 12]
    if len(cocok) != 1:
        raise C.ParameterTidakSah(f"jam {jam12} tidak ada pada bagian {bagian}")
    return cocok[0]


def _wkt(jam: int, menit: int) -> str:
    return f"{jam:02d}.{menit:02d}"


def _dalam_bagian(bagian: str, jam: int) -> bool:
    return jam in BAGIAN_JAM[bagian]


def _angka_menit(menit: int) -> int:
    """Angka di muka jam yang ditunjuk jarum panjang (menit 0 -> angka 12)."""
    return menit // 5 or 12


def _teks_durasi(total_menit: int) -> str:
    """Durasi dalam menit -> "2 jam 30 menit", "1 jam", "45 menit"; <= 0 tidak berarti."""
    jam, menit = divmod(total_menit, MENIT_PER_JAM)
    bagian = ([f"{jam} jam"] if jam else []) + ([f"{menit} menit"] if menit else [])
    return " ".join(bagian)


# --- ukur_jam_analog ---------------------------------------------------------------------------

def _sampler_jam_analog(rng):
    bagian = rng.choice(BAGIAN_BOBOT)
    jam = rng.choice(list(BAGIAN_JAM[bagian]))
    return {"bagian": bagian, "jam12": jam % 12 or 12, "menit": rng.choice(MENIT_KELIPATAN_5),
            "nama": rng.choice(C.NAMA_ANAK)}


def _pengecoh_jam(bagian: str, jam: int, menit: int):
    """Kandidat urut kesalahan paling khas dalam membaca jam analog (format sama dengan kunci)."""
    kandidat = []
    angka = _angka_menit(menit)
    jam_tukar = [h for h in BAGIAN_JAM[bagian] if h % 12 == angka % 12]
    if jam_tukar:
        kandidat.append(C.Pengecoh(_wkt(jam_tukar[0], (jam % 12) * 5),
                                   "menukar fungsi jarum pendek dan jarum panjang"))
    if _dalam_bagian(bagian, jam + 1):
        kandidat.append(C.Pengecoh(_wkt(jam + 1, menit),
                                   "membaca jam mengikuti angka berikutnya yang akan dilewati jarum pendek"))
    if menit:
        kandidat.append(C.Pengecoh(_wkt(jam, 0), "melupakan menit dan hanya membaca jarum pendek"))
    kandidat.append(C.Pengecoh(_wkt(jam, angka), "membaca angka jarum panjang langsung sebagai menit"))
    if _dalam_bagian(bagian, jam - 1):
        kandidat.append(C.Pengecoh(_wkt(jam - 1, menit),
                                   "membaca jam mengikuti angka sebelumnya yang sudah dilewati"))
    kandidat.append(C.Pengecoh(_wkt(jam, (menit + SETENGAH_JAM) % MENIT_PER_JAM),
                               "membaca jarum panjang di sisi seberang muka jam"))
    return kandidat


def _langkah_jam_analog(p, jam: int, kunci: str):
    menit = p["menit"]
    langkah_menit = (f"Jarum panjang menunjuk angka {_angka_menit(menit)}, jadi menitnya {menit}."
                     if menit else "Jarum panjang tepat di angka 12, jadi menitnya 0.")
    letak_jam = (f"Jarum pendek ada di antara angka {p['jam12']} dan {p['jam12'] % 12 + 1}."
                 if menit else f"Jarum pendek tepat di angka {p['jam12']}.")
    return (langkah_menit, letak_jam + f" Jamnya {p['jam12']}.",
            f"Karena {p['bagian']} hari, jam ditulis dengan format 24 jam: {kunci}.")


def _bangun_jam_analog(p):
    bagian, menit = p["bagian"], p["menit"]
    jam = _jam24(bagian, p["jam12"])
    kunci = _wkt(jam, menit)
    pengecoh = C.ambil_pengecoh(kunci, _pengecoh_jam(bagian, jam, menit))
    return C.SoalLomba(
        template_id="ukur_jam_analog", topik="pengukuran", jenis=C.JENIS_PG, tingkat=1,
        teks=f"{p['nama']} melihat jam dinding {bagian} hari. Jam itu menunjukkan pukul ...",
        svg=S.gambar_jam(jam, menit), kunci=kunci, pengecoh=pengecoh,
        pembahasan=_langkah_jam_analog(p, jam, kunci), parameter=C.kanonik(p), nilai=None)


def _verifikator_jam_analog(p):
    """Cacah brute-force: menit ke-t dalam sehari yang cocok dengan angka jam, menit, dan bagian hari."""
    hasil = [t for t in range(HARI_MENIT)
             if (t // MENIT_PER_JAM) % 12 == p["jam12"] % 12 and t % MENIT_PER_JAM == p["menit"]
             and (t // MENIT_PER_JAM) in BAGIAN_JAM[p["bagian"]]]
    (t,) = hasil
    return f"{t // MENIT_PER_JAM:02d}.{t % MENIT_PER_JAM:02d}"


C.daftarkan(C.Template(id="ukur_jam_analog", topik="pengukuran", jenis=C.JENIS_PG, tingkat=1,
                       sampler=_sampler_jam_analog, bangun=_bangun_jam_analog,
                       verifikator=_verifikator_jam_analog))


# --- dua jam: mulai dan selesai ----------------------------------------------------------------

def _batas_menit(bagian: str):
    jam = BAGIAN_JAM[bagian]
    return jam[0] * MENIT_PER_JAM, (jam[-1] + 1) * MENIT_PER_JAM


def _ambil_selang(rng, bagian: str, durasi_min: int, durasi_maks: int, perlu_pinjam: bool):
    """(menit mulai, menit selesai) dalam bagian hari; selesai paling lambat 5 menit sebelum batas."""
    awal, akhir = _batas_menit(bagian)
    for _ in range(PERCOBAAN_PINJAM):
        mulai = rng.randrange(awal, akhir - durasi_min + 1 - LANGKAH_MENIT, LANGKAH_MENIT)
        maks = min(durasi_maks, akhir - LANGKAH_MENIT - mulai)
        durasi = LANGKAH_MENIT * rng.randint(durasi_min // LANGKAH_MENIT, maks // LANGKAH_MENIT)
        selesai = mulai + durasi
        if not perlu_pinjam or selesai % MENIT_PER_JAM < mulai % MENIT_PER_JAM:
            return mulai, selesai
    raise C.ParameterTidakSah("tidak ada selang yang memenuhi syarat")


def _param_selang(rng, bagian: str, durasi_min: int, durasi_maks: int, perlu_pinjam: bool):
    mulai, selesai = _ambil_selang(rng, bagian, durasi_min, durasi_maks, perlu_pinjam)
    return {"bagian": bagian, "j1": mulai // MENIT_PER_JAM, "m1": mulai % MENIT_PER_JAM,
            "j2": selesai // MENIT_PER_JAM, "m2": selesai % MENIT_PER_JAM,
            "nama": rng.choice(C.NAMA_ANAK)}


def _selang(p):
    """Validasi selang dari parameter; kembalikan (menit mulai, menit selesai)."""
    mulai = p["j1"] * MENIT_PER_JAM + p["m1"]
    selesai = p["j2"] * MENIT_PER_JAM + p["m2"]
    if not (_dalam_bagian(p["bagian"], p["j1"]) and _dalam_bagian(p["bagian"], p["j2"])
            and selesai > mulai):
        raise C.ParameterTidakSah("selang waktu tidak sah")
    return mulai, selesai


def _hitung_langkah(mulai: int, selesai: int) -> int:
    """Banyak menit dari mulai sampai selesai dengan menghitung satu per satu (bukan pengurangan)."""
    return sum(1 for _ in range(mulai, selesai))


# --- ukur_lama_kegiatan ------------------------------------------------------------------------

def _sampler_lama_kegiatan(rng):
    bagian = rng.choice(("pagi", "siang", "sore"))
    hasil = _param_selang(rng, bagian, DURASI_MIN_KEGIATAN, DURASI_MAKS_KEGIATAN, False)
    return {**hasil, "kegiatan": rng.choice(KEGIATAN)}


def _pengecoh_lama(p, durasi: int):
    jam, menit = durasi // MENIT_PER_JAM, durasi % MENIT_PER_JAM
    selisih_jam = p["j2"] - p["j1"]
    kandidat = []
    if selisih_jam:
        kandidat.append((selisih_jam * MENIT_PER_JAM, "menghitung selisih jam saja dan mengabaikan menit"))
    if p["m2"] < p["m1"]:
        kandidat.append((selisih_jam * MENIT_PER_JAM + (p["m1"] - p["m2"]),
                         "mengurangi menit yang besar dengan yang kecil tanpa meminjam satu jam"))
    kandidat.append(((jam + 1) * MENIT_PER_JAM + menit, "menambah satu jam karena ikut menghitung jam pertama"))
    if menit:
        kandidat.append(((jam + 1) * MENIT_PER_JAM, "membulatkan ke jam penuh berikutnya"))
        if jam:
            kandidat.append((menit, "hanya menghitung menitnya dan melupakan jam"))
    kandidat.append((durasi + SETENGAH_JAM, "salah menghitung setengah jam terlalu banyak"))
    kandidat.append((durasi - SETENGAH_JAM, "salah menghitung setengah jam terlalu sedikit"))
    return [(nilai, label) for nilai, label in kandidat if nilai > 0]


def _bangun_lama_kegiatan(p):
    mulai, selesai = _selang(p)
    durasi = selesai - mulai
    kunci = _teks_durasi(durasi)
    pengecoh = C.ambil_pengecoh(kunci, [C.Pengecoh(_teks_durasi(n), label)
                                        for n, label in _pengecoh_lama(p, durasi)])
    nama, kegiatan = p["nama"], p["kegiatan"]
    return C.SoalLomba(
        template_id="ukur_lama_kegiatan", topik="pengukuran", jenis=C.JENIS_PG, tingkat=2,
        teks=f"{nama} mulai {kegiatan} pada {p['bagian']} hari. Jam kiri menunjukkan waktu mulai, "
             f"jam kanan waktu selesai. Berapa lama {nama} {kegiatan}?",
        svg=S.gambar_dua_jam(p["j1"], p["m1"], p["j2"], p["m2"]), kunci=kunci, pengecoh=pengecoh,
        pembahasan=(
            f"Jam pertama menunjukkan pukul {_wkt(p['j1'], p['m1'])}.",
            f"Jam kedua menunjukkan pukul {_wkt(p['j2'], p['m2'])}.",
            f"Dari {_wkt(p['j1'], p['m1'])} sampai {_wkt(p['j2'], p['m2'])} ada {durasi} menit.",
            f"{durasi} menit sama dengan {kunci}.",
        ), parameter=C.kanonik(p), nilai=None)


def _verifikator_lama_kegiatan(p):
    jam, menit = divmod(_hitung_langkah(p["j1"] * 60 + p["m1"], p["j2"] * 60 + p["m2"]), 60)
    return " ".join(([f"{jam} jam"] if jam else []) + ([f"{menit} menit"] if menit else []))


C.daftarkan(C.Template(id="ukur_lama_kegiatan", topik="pengukuran", jenis=C.JENIS_PG, tingkat=2,
                       sampler=_sampler_lama_kegiatan, bangun=_bangun_lama_kegiatan,
                       verifikator=_verifikator_lama_kegiatan))


# --- ukur_lama_menit (isian) -------------------------------------------------------------------

def _sampler_lama_menit(rng):
    bagian = rng.choice(("siang", "sore"))
    hasil = _param_selang(rng, bagian, DURASI_MIN_MENIT, DURASI_MAKS_KEGIATAN, True)
    return {**hasil, "kegiatan": rng.choice(KEGIATAN)}


def _bangun_lama_menit(p):
    mulai, selesai = _selang(p)
    durasi = selesai - mulai
    nama, kegiatan = p["nama"], p["kegiatan"]
    jam, menit = divmod(durasi, MENIT_PER_JAM)
    lama = _teks_durasi(durasi)
    return C.SoalLomba(
        template_id="ukur_lama_menit", topik="pengukuran", jenis=C.JENIS_ISIAN, tingkat=3,
        teks=f"{nama} mulai {kegiatan} pada {p['bagian']} hari. Jam kiri menunjukkan waktu mulai, "
             f"jam kanan waktu selesai. Berapa menit lamanya {nama} {kegiatan}?",
        svg=S.gambar_dua_jam(p["j1"], p["m1"], p["j2"], p["m2"]), kunci=str(durasi), pengecoh=(),
        pembahasan=(
            f"Jam pertama menunjukkan pukul {_wkt(p['j1'], p['m1'])}.",
            f"Jam kedua menunjukkan pukul {_wkt(p['j2'], p['m2'])}.",
            f"Dari {_wkt(p['j1'], p['m1'])} sampai {_wkt(p['j2'], p['m2'])} lamanya {lama}.",
            (f"{jam} jam sama dengan {jam * MENIT_PER_JAM} menit, ditambah {menit} menit "
             f"jadi {durasi} menit." if jam else f"Jadi lamanya {durasi} menit."),
        ), parameter=C.kanonik(p), nilai=durasi)


def _verifikator_lama_menit(p):
    return str(_hitung_langkah(p["j1"] * 60 + p["m1"], p["j2"] * 60 + p["m2"]))


C.daftarkan(C.Template(id="ukur_lama_menit", topik="pengukuran", jenis=C.JENIS_ISIAN, tingkat=3,
                       sampler=_sampler_lama_menit, bangun=_bangun_lama_menit,
                       verifikator=_verifikator_lama_menit))

import contest_templates_measurement_b  # noqa: E402,F401
import contest_templates_measurement_c  # noqa: E402,F401
