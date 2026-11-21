"""Kontrak soal Latihan Lomba (Grand Final Corexis 2026, Matematika Level 1, kelas 1-2).

Satu `Template` = sampler parameter + pembangun soal + verifikator independen.
Pembangun murni: parameter yang sama selalu menghasilkan soal yang sama, jadi soal,
pilihan, kunci, dan pembahasan dihitung dari parameter yang sama. Verifikator
menghitung ulang kunci dengan cara kedua (mis. cacah brute-force), bukan rumus
yang sama dengan pembangun. Modul ini tidak menyentuh DB, jaringan, atau LLM.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple

TOPIK = ("bilangan", "operasi", "pengukuran", "bangun")
LABEL_TOPIK = {
    "bilangan": "Bilangan",
    "operasi": "Operasi Hitung",
    "pengukuran": "Pengukuran",
    "bangun": "Bangun Datar/Ruang",
}
JENIS_PG = "pg"
JENIS_ISIAN = "isian"
JENIS = (JENIS_PG, JENIS_ISIAN)
TINGKAT = (1, 2, 3)
HURUF = ("A", "B", "C", "D")
JUMLAH_PENGECOH = 3
BATAS_NILAI = 100000
MAKS_PERCOBAAN = 500
MAKS_UKURAN_SVG = 40000
MAKS_TEKS = 600
MAKS_LANGKAH = 8

# Nama sintetis untuk cerita soal; bukan nama anak atau pengguna nyata.
NAMA_ANAK = (
    "Rudi", "Kia", "Doni", "Siti", "Dina", "Budi", "Sari", "Andi", "Tia", "Raka",
    "Nina", "Bima", "Lala", "Putra", "Wati", "Joko", "Ratna", "Eko", "Maya", "Agus",
)

# Awalan id per topik: tiap pekerja punya ruang namanya sendiri, id tidak bisa bertabrakan.
AWALAN_ID = {"bilangan": "bil_", "operasi": "ops_", "pengukuran": "ukur_", "bangun": "bgn_"}

_POLA_ID = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
_POLA_BILANGAN_POSITIF = re.compile(r"^[1-9][0-9]{0,5}$")
_POLA_ISIAN = re.compile(r"^[0-9]{1,6}$")
_POLA_ARIA = re.compile(r'aria-label="([^"]*)"')
_POLA_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
_NAMESPACE_SVG = 'xmlns="http://www.w3.org/2000/svg"'


class ParameterTidakSah(ValueError):
    """Parameter acak tidak memenuhi syarat soal (mis. pengecoh kurang); ulangi sampling."""


class GagalMembuatSoal(RuntimeError):
    """Template tidak menghasilkan soal sah dalam batas percobaan."""


@dataclass(frozen=True)
class Pengecoh:
    """Satu pilihan salah beserta hipotesis kesalahan umum anak (hanya untuk dibaca orang tua)."""

    nilai: str
    kesalahan: str
    svg: str = ""      # gambar pilihan (bila pilihan berupa gambar); semua pilihan atau tidak sama sekali


@dataclass(frozen=True)
class SoalLomba:
    template_id: str
    topik: str
    jenis: str
    tingkat: int
    teks: str
    svg: str
    kunci: str
    pengecoh: Tuple[Pengecoh, ...]
    pembahasan: Tuple[str, ...]
    parameter: str
    nilai: Optional[int] = None
    inggris: bool = False
    kunci_svg: str = ""   # gambar pilihan yang benar; pasangan `Pengecoh.svg`


@dataclass(frozen=True)
class Template:
    id: str
    topik: str
    jenis: str
    tingkat: int
    sampler: Callable[[random.Random], Mapping]
    bangun: Callable[[Mapping], SoalLomba]
    verifikator: Callable[[Mapping], str]


REGISTRY: Dict[str, Template] = {}


def kanonik(parameter: Mapping) -> str:
    """JSON kanonik (kunci terurut, tanpa spasi) agar tanda tangan soal stabil."""
    try:
        return json.dumps(parameter, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as galat:
        raise ValueError(f"parameter tidak bisa diserialkan: {galat}") from galat


def tanda_tangan(soal: SoalLomba) -> str:
    return f"{soal.template_id}|{soal.parameter}"


def _normal(teks: str) -> str:
    return " ".join(str(teks).split()).casefold()


def validasi_svg(svg: str) -> None:
    if not isinstance(svg, str) or not svg.startswith("<svg") or not svg.endswith("</svg>"):
        raise ValueError("svg harus berupa satu elemen <svg>")
    if len(svg) > MAKS_UKURAN_SVG:
        raise ValueError("svg terlalu besar")
    if 'role="img"' not in svg:
        raise ValueError("svg wajib role=\"img\"")
    sisa = svg.replace(_NAMESPACE_SVG, "")
    kecil = sisa.lower()
    for terlarang in ("<script", "<foreignobject", "javascript:", "http", "href=", "<title", "<desc"):
        if terlarang in kecil:
            raise ValueError(f"svg memuat {terlarang!r}")
    if _POLA_HANDLER.search(sisa):
        raise ValueError("svg memuat atribut penangan kejadian")
    aria = _POLA_ARIA.search(svg)
    if aria is None or not aria.group(1).strip():
        raise ValueError("svg wajib aria-label")
    if re.search(r"[0-9]", aria.group(1)):
        raise ValueError("aria-label tidak boleh memuat angka (bisa membocorkan jawaban)")


def _validasi_gambar_pilihan(soal: SoalLomba) -> None:
    gambar = [soal.kunci_svg] + [pengecoh.svg for pengecoh in soal.pengecoh]
    if not any(gambar):
        return
    if not all(gambar):
        raise ValueError("pilihan bergambar: semua pilihan wajib bergambar atau tidak sama sekali")
    if len(set(gambar)) != len(gambar):
        raise ValueError("gambar pilihan harus berbeda semua")
    for svg in gambar:
        validasi_svg(svg)


def _validasi_pengecoh_angka(soal: SoalLomba) -> None:
    """Soal berkunci angka: pengecoh juga wajib bilangan bulat positif dalam batas wajar."""
    for pengecoh in soal.pengecoh:
        if not _POLA_BILANGAN_POSITIF.match(pengecoh.nilai) or int(pengecoh.nilai) > BATAS_NILAI:
            raise ValueError(f"pengecoh angka tidak wajar: {pengecoh.nilai!r}")


def _validasi_pengecoh(soal: SoalLomba) -> None:
    if soal.jenis == JENIS_ISIAN:
        if soal.pengecoh != () or soal.kunci_svg:
            raise ValueError("isian tidak punya pengecoh atau gambar pilihan")
        return
    if len(soal.pengecoh) != JUMLAH_PENGECOH:
        raise ValueError(f"pilihan ganda wajib {JUMLAH_PENGECOH} pengecoh")
    semua = [soal.kunci] + [p.nilai for p in soal.pengecoh]
    if len({_normal(nilai) for nilai in semua}) != len(semua):
        raise ValueError("kunci dan pengecoh harus berbeda semua")
    for pengecoh in soal.pengecoh:
        if not isinstance(pengecoh, Pengecoh) or not pengecoh.nilai.strip() \
                or not pengecoh.kesalahan.strip():
            raise ValueError("pengecoh wajib bernilai dan berlabel kesalahan")
    if soal.nilai is not None:
        _validasi_pengecoh_angka(soal)
    _validasi_gambar_pilihan(soal)


def _validasi_kunci(soal: SoalLomba) -> None:
    if not isinstance(soal.kunci, str) or not soal.kunci.strip() or len(soal.kunci) > 60:
        raise ValueError("kunci wajib teks tidak kosong")
    if soal.jenis == JENIS_ISIAN:
        if not _POLA_BILANGAN_POSITIF.match(soal.kunci):
            raise ValueError("kunci isian wajib bilangan bulat positif")
        if soal.nilai != int(soal.kunci):
            raise ValueError("nilai isian wajib sama dengan kunci")
    elif soal.kunci.isdigit() and soal.nilai is None:
        raise ValueError("kunci angka wajib membawa nilai agar pengecoh ikut diperiksa")
    if soal.nilai is not None and not 1 <= soal.nilai <= BATAS_NILAI:
        raise ValueError("nilai di luar batas wajar")
    if soal.nilai is not None and soal.kunci != str(soal.nilai):
        raise ValueError("nilai wajib sama dengan kunci")


def _validasi_parameter(parameter: str) -> None:
    try:
        data = json.loads(parameter)
    except (TypeError, ValueError) as galat:
        raise ValueError("parameter bukan JSON") from galat
    if not isinstance(data, dict) or kanonik(data) != parameter:
        raise ValueError("parameter harus objek JSON kanonik")


def validasi_soal(soal: SoalLomba) -> None:
    """Gerbang tunggal: soal cacat tidak boleh sampai ke anak."""
    if soal.topik not in TOPIK:
        raise ValueError(f"topik tidak dikenal: {soal.topik!r}")
    if soal.jenis not in JENIS:
        raise ValueError(f"jenis tidak dikenal: {soal.jenis!r}")
    if soal.tingkat not in TINGKAT:
        raise ValueError(f"tingkat tidak dikenal: {soal.tingkat!r}")
    if not isinstance(soal.teks, str) or not soal.teks.strip() or len(soal.teks) > MAKS_TEKS:
        raise ValueError("teks soal kosong atau terlalu panjang")
    if "<" in soal.teks or ">" in soal.teks:
        raise ValueError("teks soal tidak boleh memuat markup")
    langkah = soal.pembahasan
    if not langkah or len(langkah) > MAKS_LANGKAH or any(
            not isinstance(baris, str) or not baris.strip() for baris in langkah):
        raise ValueError("pembahasan wajib 1-8 langkah tidak kosong")
    _validasi_kunci(soal)
    _validasi_pengecoh(soal)
    _validasi_parameter(soal.parameter)
    if soal.svg:
        validasi_svg(soal.svg)


def _validasi_template(template: Template) -> None:
    if not isinstance(template.id, str) or not _POLA_ID.match(template.id):
        raise ValueError(f"id template tidak sah: {template.id!r}")
    if template.topik not in TOPIK:
        raise ValueError(f"topik template tidak dikenal: {template.topik!r}")
    if not template.id.startswith(AWALAN_ID[template.topik]):
        raise ValueError(f"id template topik {template.topik!r} wajib berawalan "
                         f"{AWALAN_ID[template.topik]!r}: {template.id!r}")
    if template.jenis not in JENIS:
        raise ValueError(f"jenis template tidak dikenal: {template.jenis!r}")
    if template.tingkat not in TINGKAT:
        raise ValueError(f"tingkat template tidak dikenal: {template.tingkat!r}")
    for nama in ("sampler", "bangun", "verifikator"):
        if not callable(getattr(template, nama)):
            raise ValueError(f"{nama} template wajib fungsi")


def daftarkan(template: Template) -> Template:
    _validasi_template(template)
    if template.id in REGISTRY:
        raise ValueError(f"template {template.id!r} sudah terdaftar")
    REGISTRY[template.id] = template
    return template


def ambil(template_id: str) -> Template:
    return REGISTRY[template_id]


def semua() -> Tuple[Template, ...]:
    return tuple(REGISTRY[kunci] for kunci in sorted(REGISTRY))


def _cocok_template(template: Template, soal: SoalLomba, parameter: Mapping) -> None:
    if (soal.template_id, soal.topik, soal.jenis, soal.tingkat) != (
            template.id, template.topik, template.jenis, template.tingkat):
        raise ValueError(f"soal tidak cocok dengan metadata template {template.id!r}")
    if soal.parameter != kanonik(parameter):
        raise ValueError(f"parameter soal bukan hasil sampler template {template.id!r}")


def buat_soal(template: Template, rng: random.Random,
              maks_percobaan: int = MAKS_PERCOBAAN) -> SoalLomba:
    """Ulang hanya saat ParameterTidakSah; soal cacat tidak ditutupi oleh pengulangan."""
    for _ in range(maks_percobaan):
        try:
            parameter = template.sampler(rng)
            soal = template.bangun(parameter)
        except ParameterTidakSah:
            continue
        _cocok_template(template, soal, parameter)
        validasi_soal(soal)
        return soal
    raise GagalMembuatSoal(f"template {template.id!r} gagal setelah {maks_percobaan} percobaan")


def susun_pilihan(soal: SoalLomba, posisi_kunci: int, rng: random.Random) -> Tuple[str, ...]:
    """Empat pilihan; kunci di posisi_kunci, pengecoh diacak mengisi sisanya."""
    if soal.jenis != JENIS_PG:
        raise ValueError("hanya pilihan ganda yang punya pilihan")
    if posisi_kunci not in range(len(HURUF)):
        raise ValueError("posisi kunci di luar A-D")
    lain = [pengecoh.nilai for pengecoh in soal.pengecoh]
    rng.shuffle(lain)
    return tuple(lain[:posisi_kunci] + [soal.kunci] + lain[posisi_kunci:])


def ambil_pengecoh(kunci: str, kandidat: Sequence[Pengecoh]) -> Tuple[Pengecoh, ...]:
    """Tiga pengecoh pertama yang sah dari `kandidat` (urut prioritas kesalahan paling khas).

    Membuang kandidat yang sama dengan kunci atau kembar (setelah normalisasi); bila kunci berupa
    angka, kandidat bukan bilangan bulat positif wajar juga dibuang. Kurang dari tiga ->
    ParameterTidakSah, supaya parameter diulang dan pengecoh tidak pernah diisi angka sembarang.
    """
    terpakai = {_normal(kunci)}
    hasil = []
    for pengecoh in kandidat:
        nilai = _normal(pengecoh.nilai)
        if nilai in terpakai:
            continue
        if kunci.isdigit() and not (_POLA_BILANGAN_POSITIF.match(pengecoh.nilai)
                                    and int(pengecoh.nilai) <= BATAS_NILAI):
            continue
        terpakai.add(nilai)
        hasil.append(pengecoh)
        if len(hasil) == JUMLAH_PENGECOH:
            return tuple(hasil)
    raise ParameterTidakSah(f"pengecoh sah kurang dari {JUMLAH_PENGECOH} untuk kunci {kunci!r}")


def gambar_pilihan(soal: SoalLomba, pilihan: Tuple[str, ...]) -> Tuple[str, ...]:
    """SVG tiap pilihan menurut urutan `pilihan` (hasil susun_pilihan); "" bila pilihan teks."""
    peta = {pengecoh.nilai: pengecoh.svg for pengecoh in soal.pengecoh}
    peta[soal.kunci] = soal.kunci_svg
    try:
        return tuple(peta[nilai] for nilai in pilihan)
    except KeyError as galat:
        raise ValueError(f"pilihan bukan milik soal: {galat.args[0]!r}") from galat


def posisi_seimbang(jumlah: int, rng: random.Random) -> Tuple[int, ...]:
    """Posisi kunci untuk `jumlah` soal PG: selisih hitungan A-D paling banyak satu, urutan diacak."""
    posisi = [indeks % len(HURUF) for indeks in range(jumlah)]
    rng.shuffle(posisi)
    return tuple(posisi)


def jawaban_benar(kunci: str, jawaban: str, jenis: str) -> bool:
    if not isinstance(jawaban, str):
        return False
    if jenis == JENIS_ISIAN:
        bersih = jawaban.strip()
        return bool(_POLA_ISIAN.match(bersih)) and _POLA_ISIAN.match(kunci) is not None \
            and int(bersih) == int(kunci)
    return _normal(kunci) == _normal(jawaban)
