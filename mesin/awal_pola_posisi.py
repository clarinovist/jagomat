"""Matematika Awal, jenis `pola_posisi`: pola berulang dan posisi benda (P2), teks saja.

Empat bentuk soal (`varian`):
  - `pola`: barisan kata berulang, "Perhatikan pola warna berikut: merah, biru,
    merah, biru, merah, ... Warna berikutnya apa?" (jawaban: kata);
  - `urutan`: barisan empat anak dari depan ke belakang; siapa tepat di belakang
    atau di depan seorang anak, atau siapa di urutan ke-n (jawaban: nama);
  - `kiri_kanan`: dua kalimat letak ("Bola ada di sebelah kiri kotak. ...") yang
    bersama-sama menentukan SATU urutan tiga benda; benda paling kiri, paling
    kanan, atau di tengah (jawaban: benda);
  - `atas_bawah`: sama, tetapi tumpukan ("Topi ada di atas kotak. ...").

Jaminan tak ambigu (diuji solver terpisah di tes jenis ini):
  - barisan `pola` selalu menampilkan paling sedikit DUA putaran penuh (AB: 5-8
    suku, ABC/AAB: 6-8 suku), jadi periode terkecilnya satu-satunya yang masuk akal;
  - `urutan` hanya menanyakan anak yang punya tetangga di depan dan di belakang
    (dua anak tengah), sehingga jawaban "tertukar arah" selalu ada;
  - dua kalimat `kiri_kanan`/`atas_bawah` selalu memuat benda tengah sebagai
    penghubung, jadi tepat satu urutan tiga benda yang cocok.

Kunci berupa teks huruf kecil satu kata. Jawaban isian dibandingkan lewat
`diagnosis.normalisasi` (huruf besar-kecil dan spasi berlebih dimaafkan).

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti
dari satu jawaban. Semuanya K (salah paham posisi/urutan): mengulang benda
terakhir, melompat atau mundur satu suku (pola), tetangga yang salah arah atau
dihitung dari belakang (urutan), ujung yang tertukar atau benda tengah (letak).
Jalur K selalu ada; yang kebetulan sama dengan kunci dibuang `saring_malrule`.
Pilihan ganda: lihat `pengecoh_tambahan` (benda yang memang ada di soal atau
himpunan benda soal), karena pola periode 2 hanya punya satu malrule.

Domain kecil dan eksplisit (`domain_parameter`): sampler hanya mengundi dari domain
itu memakai `rng` (tanpa `hash()`), jadi seed yang sama selalu menghasilkan soal
yang sama lintas proses. Semua parameter skalar (teks atau bilangan bulat): indeks
ke daftar ISI_POLA/ANTREAN/HIMPUNAN_LETAK, yang bersifat APPEND-ONLY karena indeks
ikut dalam identitas soal di bank.
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "pola_posisi"
LEVEL = ("P2",)
VARIAN = ("pola", "urutan", "kiri_kanan", "atas_bawah")
PESAN_LUAR_DOMAIN = "parameter pola posisi di luar domain"

# ── data soal (append-only menurut indeks) ───────────────────────────────

# Himpunan tiga kata per kategori; A/B/C pada RAGAM menunjuk urutan kata itu.
ISI_POLA = {
    "warna": (("merah", "biru", "kuning"), ("hijau", "putih", "ungu")),
    "buah": (("apel", "jeruk", "pisang"), ("mangga", "jambu", "semangka")),
}
KATA_KATEGORI = {"warna": "Warna", "buah": "Buah"}
# Putaran pola sebagai indeks ke himpunan kata, dan jumlah suku yang boleh tampil
# (selalu >= dua putaran penuh dan 5..8 suku).
RAGAM = {"AB": (0, 1), "ABC": (0, 1, 2), "AAB": (0, 0, 1)}
TAMPIL = {"AB": (5, 6, 7, 8), "ABC": (6, 7, 8), "AAB": (6, 7, 8)}

# Empat anak per barisan, urut dari depan ke belakang. Nama sintetis umum.
ANTREAN = (
    ("Rina", "Budi", "Dita", "Eko"),
    ("Sari", "Tono", "Wati", "Andi"),
    ("Maya", "Joko", "Lina", "Rafi"),
)
TANYA_URUTAN = ("belakang", "depan", "ke_n")
ORANG_TENGAH = (1, 2)  # indeks anak yang punya tetangga di depan dan belakang

# Tiga benda per himpunan, urut dari ujung awal (kiri/atas) ke ujung akhir (kanan/bawah).
HIMPUNAN_LETAK = {
    "kiri_kanan": (("bola", "kotak", "buku"), ("pensil", "penghapus", "penggaris"),
                   ("apel", "jeruk", "pisang")),
    "atas_bawah": (("topi", "kotak", "meja"), ("apel", "piring", "nampan")),
}
# awal/akhir: kata ujungnya; frasa: bagian kalimat "X ada di <frasa> Y".
SUMBU = {
    "kiri_kanan": {"awal": "kiri", "akhir": "kanan", "frasa": "sebelah {}"},
    "atas_bawah": {"awal": "atas", "akhir": "bawah", "frasa": "{}"},
}
BENTUK_LETAK = (0, 1, 2, 3)

# Kunci parameter wajib per cabang; kunci lebih atau kurang = di luar domain.
KUNCI_POLA = frozenset({"varian", "kategori", "isi", "ragam", "tampil"})
KUNCI_ORANG = frozenset({"varian", "antrean", "tanya", "orang"})
KUNCI_KE_N = frozenset({"varian", "antrean", "tanya", "n"})
KUNCI_LETAK = frozenset({"varian", "himpunan", "bentuk", "tanya"})


def _int_sah(nilai, bawah: int, atas: int) -> bool:
    """Bilangan bulat murni (bukan bool, bukan float) dalam bawah..atas termasuk."""
    return type(nilai) is int and bawah <= nilai <= atas


def _teks_sah(nilai, pilihan) -> bool:
    return type(nilai) is str and nilai in pilihan


# ── varian pola ──────────────────────────────────────────────────────────

def _sah_pola(p: dict) -> bool:
    if set(p) != KUNCI_POLA or not _teks_sah(p["kategori"], ISI_POLA):
        return False
    if not _int_sah(p["isi"], 0, len(ISI_POLA[p["kategori"]]) - 1):
        return False
    return _teks_sah(p["ragam"], RAGAM) and type(p["tampil"]) is int and p["tampil"] in TAMPIL[p["ragam"]]


def _suku(p: dict, indeks: int) -> str:
    """Suku ke-`indeks` (mulai 0) barisan pola; sama dengan suku satu putaran sebelumnya."""
    putaran = RAGAM[p["ragam"]]
    return ISI_POLA[p["kategori"]][p["isi"]][putaran[indeks % len(putaran)]]


def _soal_pola(p: dict) -> Soal:
    kategori, n = p["kategori"], p["tampil"]
    tampak = [_suku(p, i) for i in range(n)]
    kunci = _suku(p, n)
    teks = (f"Perhatikan pola {kategori} berikut: {', '.join(tampak)}, ... "
            f"{KATA_KATEGORI[kategori]} berikutnya apa?")
    putaran = ", ".join(_suku(p, i) for i in range(len(RAGAM[p["ragam"]])))
    pembahasan = (f"Cari bagian yang terus berulang: {putaran}. Yang tampak ada {n} {kategori}, "
                  f"jadi tinggal melanjutkan bagian itu ke urutan ke-{n + 1}. "
                  f"Urutan ke-{n + 1} adalah {kunci}. Jadi {kategori} berikutnya adalah {kunci}.")
    kandidat = [
        Malrule(f"{TEMPLATE_ID}.pola_ulang_terakhir", tampak[-1], "K",
                "Mengulang benda terakhir yang tampak, bukan melanjutkan bagian yang berulang."),
        Malrule(f"{TEMPLATE_ID}.pola_lompat_satu", _suku(p, n + 1), "K",
                "Melompati satu benda sehingga menyebut benda sesudah yang seharusnya."),
        Malrule(f"{TEMPLATE_ID}.pola_mundur_satu", _suku(p, n - 2), "K",
                "Menyebut benda sebelum yang terakhir tampak, seperti menghitung mundur satu suku."),
    ]
    return _bangun(p, teks, kunci, kandidat, pembahasan)


# ── varian urutan ────────────────────────────────────────────────────────

def _sah_urutan(p: dict) -> bool:
    if p.get("tanya") == "ke_n":
        return (set(p) == KUNCI_KE_N and _int_sah(p["antrean"], 0, len(ANTREAN) - 1)
                and _int_sah(p["n"], 1, 4))
    if p.get("tanya") in ("belakang", "depan"):
        return (set(p) == KUNCI_ORANG and _int_sah(p["antrean"], 0, len(ANTREAN) - 1)
                and type(p["orang"]) is int and p["orang"] in ORANG_TENGAH)
    return False


def _tulis_barisan(anak: tuple) -> str:
    return ("Empat anak berbaris dalam satu barisan, dari depan ke belakang: "
            + ", ".join(anak) + ".")


def _soal_urutan(p: dict) -> Soal:
    anak = ANTREAN[p["antrean"]]
    daftar = ", ".join(anak)
    if p["tanya"] == "ke_n":
        n = p["n"]
        tanya, idx = f"Siapa yang berdiri di urutan ke-{n} dari depan?", n - 1
        pembahasan = (f"Hitung dari depan: {daftar}. Anak di urutan ke-{n} adalah {anak[idx]}. "
                      f"Jadi jawabannya {anak[idx]}.")
        kandidat = _malrule_ke_n(anak, n)
    else:
        arah = 1 if p["tanya"] == "belakang" else -1
        sasaran = p["orang"]
        idx = sasaran + arah
        letak = "belakang" if arah == 1 else "depan"
        tanya = f"Siapa yang berdiri tepat di {letak} {anak[sasaran]}?"
        pembahasan = (f"Barisannya dari depan ke belakang: {daftar}. {anak[sasaran]} ada di urutan "
                      f"ke-{sasaran + 1}, jadi yang tepat di {letak}nya ada di urutan ke-{idx + 1}, "
                      f"yaitu {anak[idx]}. Jadi jawabannya {anak[idx]}.")
        kandidat = _malrule_tetangga(anak, sasaran, arah)
    return _bangun(p, f"{_tulis_barisan(anak)} {tanya}", anak[idx].lower(), kandidat, pembahasan)


def _malrule_tetangga(anak: tuple, sasaran: int, arah: int) -> list:
    letak = "depan" if arah == 1 else "belakang"
    kandidat = [Malrule(
        f"{TEMPLATE_ID}.urutan_arah_tertukar", anak[sasaran - arah].lower(), "K",
        f"Menyebut anak tepat di {letak}, kemungkinan tertukar antara depan dan belakang.")]
    lompat = sasaran + 2 * arah
    if 0 <= lompat < len(anak):
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.urutan_lompat_satu", anak[lompat].lower(), "K",
            "Melewati satu anak sehingga menyebut anak dua tempat dari sasaran."))
    return kandidat


def _malrule_ke_n(anak: tuple, n: int) -> list:
    kandidat = [Malrule(
        f"{TEMPLATE_ID}.urutan_dari_belakang", anak[len(anak) - n].lower(), "K",
        f"Menghitung dari belakang, jadi menyebut anak urutan ke-{n} dari belakang.")]
    if n < len(anak):
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.urutan_lebih_satu", anak[n].lower(), "H",
            "Sudah mengerti cara menghitungnya, tetapi menghitung satu anak terlalu jauh."))
    if n > 1:
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.urutan_kurang_satu", anak[n - 2].lower(), "H",
            "Sudah mengerti cara menghitungnya, tetapi berhenti satu anak lebih awal."))
    return kandidat


# ── varian kiri_kanan dan atas_bawah ─────────────────────────────────────

def _sah_letak(p: dict) -> bool:
    if set(p) != KUNCI_LETAK or not _teks_sah(p["varian"], SUMBU):
        return False
    sumbu = SUMBU[p["varian"]]
    tanya = ("paling_" + sumbu["awal"], "paling_" + sumbu["akhir"], "tengah")
    return (_int_sah(p["himpunan"], 0, len(HIMPUNAN_LETAK[p["varian"]]) - 1)
            and _int_sah(p["bentuk"], 0, len(BENTUK_LETAK) - 1) and _teks_sah(p["tanya"], tanya))


def _kalimat_letak(varian: str, bentuk: int, benda: tuple) -> str:
    """Dua kalimat yang selalu menghubungkan benda tengah dengan kedua ujungnya."""
    sumbu = SUMBU[varian]

    def kalimat(x: str, kata: str, y: str) -> str:
        return f"{x.capitalize()} ada di {sumbu['frasa'].format(kata)} {y}."

    awal, tengah, akhir = benda
    k_awal, k_akhir = sumbu["awal"], sumbu["akhir"]
    if bentuk == 0:
        return f"{kalimat(awal, k_awal, tengah)} {kalimat(tengah, k_awal, akhir)}"
    if bentuk == 1:
        return f"{kalimat(tengah, k_awal, akhir)} {kalimat(awal, k_awal, tengah)}"
    if bentuk == 2:
        return f"{kalimat(awal, k_awal, tengah)} {kalimat(akhir, k_akhir, tengah)}"
    return f"{kalimat(tengah, k_akhir, awal)} {kalimat(akhir, k_akhir, tengah)}"


def _soal_letak(p: dict) -> Soal:
    varian, tanya = p["varian"], p["tanya"]
    benda = HIMPUNAN_LETAK[varian][p["himpunan"]]
    sumbu = SUMBU[varian]
    awal, tengah, akhir = benda
    urut = ", ".join(benda)
    if tanya == "tengah":
        pertanyaan, kunci = "Benda apa yang ada di tengah?", tengah
        kalimat_kunci = f"Yang ada di tengah adalah {tengah}."
    else:
        ujung = tanya[len("paling_"):]
        pertanyaan = f"Benda apa yang paling {ujung}?"
        kunci = awal if ujung == sumbu["awal"] else akhir
        kalimat_kunci = f"Yang paling {ujung} adalah {kunci}."
    teks = f"{_kalimat_letak(varian, p['bentuk'], benda)} {pertanyaan}"
    pembahasan = (f"Susun bendanya dari {sumbu['awal']} ke {sumbu['akhir']}: {urut}. "
                  f"{kalimat_kunci} Jadi jawabannya {kunci}.")
    return _bangun(p, teks, kunci, _malrule_letak(varian, tanya, benda), pembahasan)


def _malrule_letak(varian: str, tanya: str, benda: tuple) -> list:
    sumbu = SUMBU[varian]
    awal, tengah, akhir = benda
    nama = f"{sumbu['awal']}_{sumbu['akhir']}"
    if tanya == "tengah":
        return [
            Malrule(f"{TEMPLATE_ID}.letak_ujung_{sumbu['awal']}", awal, "K",
                    f"Menyebut benda paling {sumbu['awal']}, bukan benda yang di tengah."),
            Malrule(f"{TEMPLATE_ID}.letak_ujung_{sumbu['akhir']}", akhir, "K",
                    f"Menyebut benda paling {sumbu['akhir']}, bukan benda yang di tengah."),
        ]
    lawan = akhir if tanya == "paling_" + sumbu["awal"] else awal
    kata_lawan = sumbu["akhir"] if lawan == akhir else sumbu["awal"]
    return [
        Malrule(f"{TEMPLATE_ID}.letak_tertukar_{nama}", lawan, "K",
                f"Menyebut benda paling {kata_lawan}, kemungkinan tertukar antara "
                f"{sumbu['awal']} dan {sumbu['akhir']}."),
        Malrule(f"{TEMPLATE_ID}.letak_benda_tengah", tengah, "K",
                "Menyebut benda yang di tengah, kemungkinan belum menyusun urutan ketiga benda."),
    ]


# ── fungsi soal ──────────────────────────────────────────────────────────

def _bangun(p: dict, teks: str, kunci: str, kandidat: list, pembahasan: str) -> Soal:
    return Soal(template_id=TEMPLATE_ID, parameter=dict(p), teks=teks, kunci=kunci,
                malrule=saring_malrule(kunci, kandidat), pembahasan=pembahasan, bagian="A")


def _sah(p: dict) -> bool:
    varian = p.get("varian")
    if varian == "pola":
        return _sah_pola(p)
    if varian == "urutan":
        return _sah_urutan(p)
    if varian in ("kiri_kanan", "atas_bawah"):
        return _sah_letak(p)
    return False


def pola_posisi(varian: str, **parameter) -> Soal:
    """Pola berulang atau posisi benda; kunci dihitung dari parameter."""
    lengkap = {"varian": varian, **parameter}
    if not _sah(lengkap):
        raise ValueError(PESAN_LUAR_DOMAIN)
    if varian == "pola":
        return _soal_pola(lengkap)
    if varian == "urutan":
        return _soal_urutan(lengkap)
    return _soal_letak(lengkap)


def pengecoh_tambahan(parameter: dict) -> tuple:
    """Kata lain yang masuk akal sebagai pengecoh pilihan ganda (bukan malrule).

    pola: ketiga kata himpunan soal (periode 2 hanya memakai dua di soal);
    urutan: keempat nama di barisan; letak: ketiga benda yang disebut.
    Pemanggil membuang kunci dan duplikat.
    """
    varian = parameter["varian"]
    if varian == "pola":
        return tuple(ISI_POLA[parameter["kategori"]][parameter["isi"]])
    if varian == "urutan":
        return tuple(x.lower() for x in ANTREAN[parameter["antrean"]])
    return tuple(HIMPUNAN_LETAK[varian][parameter["himpunan"]])


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi_pola() -> list:
    return [{"varian": "pola", "kategori": kategori, "isi": isi, "ragam": ragam, "tampil": n}
            for kategori in ISI_POLA for isi in range(len(ISI_POLA[kategori]))
            for ragam in RAGAM for n in TAMPIL[ragam]]


def _enumerasi_urutan() -> list:
    hasil = []
    for antrean in range(len(ANTREAN)):
        for tanya in ("belakang", "depan"):
            hasil += [{"varian": "urutan", "antrean": antrean, "tanya": tanya, "orang": o}
                      for o in ORANG_TENGAH]
        hasil += [{"varian": "urutan", "antrean": antrean, "tanya": "ke_n", "n": n}
                  for n in range(1, 5)]
    return hasil


def _enumerasi_letak(varian: str) -> list:
    sumbu = SUMBU[varian]
    tanya = ("paling_" + sumbu["awal"], "paling_" + sumbu["akhir"], "tengah")
    return [{"varian": varian, "himpunan": h, "bentuk": b, "tanya": t}
            for h in range(len(HIMPUNAN_LETAK[varian])) for b in BENTUK_LETAK for t in tanya]


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    semua = (_enumerasi_pola() + _enumerasi_urutan() + _enumerasi_letak("kiri_kanan")
             + _enumerasi_letak("atas_bawah"))
    return tuple(tuple(p.items()) for p in semua)


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level pola posisi harus P2")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for item in _domain_beku())


def parameter(rng: random.Random, level: str) -> dict:
    """Satu undian seragam dari domain terbatas; tanpa rejection atau nudge."""
    _pastikan_level(level)
    return dict(rng.choice(_domain_beku()))
