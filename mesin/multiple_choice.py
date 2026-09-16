"""Pembentukan opsi di sisi guru, terpisah dari reader publik dan generator isian.

Pemanggil memilih kebijakan serta jenis jawaban menurut template/varian yang
sudah direview. Kekurangan kandidat selalu ditolak, bukan ditambal angka acak
atau diam-diam diturunkan menjadi tiga opsi.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import random
import re
import unicodedata

from choice_contract import JUMLAH_OPSI, OpsiJawaban, PilihanButir

JENIS_JAWABAN = frozenset({"angka", "daftar_bulat", "urutan_bilangan",
                           "kategori", "jam", "durasi", "rasio"})


def _angka(teks: str) -> Fraction:
    if not re.fullmatch(r"[+-]?[0-9]+(?:[.,][0-9]+|/[0-9]+)?%?", teks):
        raise ValueError("Format angka pilihan tidak dikenal.")
    try:
        hasil = Fraction(teks.rstrip("%").replace(",", "."))
    except (ValueError, ZeroDivisionError) as galat:
        raise ValueError("Angka pilihan tidak sah.") from galat
    return hasil / 100 if teks.endswith("%") else hasil


def nilai_semantis(teks: str, jenis: str):
    """Kesetaraan bertipe; koma daftar tidak ditebak dari tampilan skalar."""
    if jenis not in JENIS_JAWABAN or not isinstance(teks, str) or not teks.strip():
        raise ValueError("Jenis atau nilai jawaban tidak sah.")
    t = unicodedata.normalize("NFKC", teks).strip().replace("−", "-")
    if jenis == "angka":
        return _angka(t)
    if jenis == "kategori":
        if not re.fullmatch(r"[^\W\d_]+(?:[ -][^\W\d_]+)*", t, re.UNICODE):
            raise ValueError("Kategori pilihan tidak sah.")
        return t.casefold()
    if jenis == "daftar_bulat":
        if not re.fullmatch(r"[+-]?[0-9]+(?:\s*,\s*[+-]?[0-9]+)+", t):
            raise ValueError("Daftar bilangan pilihan tidak sah.")
        return tuple(int(x.strip()) for x in t.split(","))
    if jenis == "urutan_bilangan":
        bagian = t.split(", ")
        if len(bagian) < 2:
            raise ValueError("Urutan bilangan pilihan tidak sah.")
        return tuple(_angka(x) for x in bagian)
    if jenis == "rasio":
        cocok = re.fullmatch(r"([0-9]+):([0-9]+)", t)
        if cocok is None or any(int(x) == 0 for x in cocok.groups()):
            raise ValueError("Rasio pilihan tidak sah.")
        return Fraction(*map(int, cocok.groups()))
    if jenis == "jam":
        cocok = re.fullmatch(r"([0-9]{2})\.([0-9]{2})", t)
        if cocok is None:
            raise ValueError("Format jam pilihan tidak sah.")
        jam, menit = map(int, cocok.groups())
        if jam >= 24 or menit >= 60:
            raise ValueError("Nilai jam pilihan tidak sah.")
        return 60 * jam + menit
    cocok = re.fullmatch(r"([0-9]+) jam ([0-9]+) menit", t)
    if cocok is None:
        raise ValueError("Format durasi pilihan tidak sah.")
    jam, menit = map(int, cocok.groups())
    if menit >= 60:
        raise ValueError("Nilai durasi pilihan tidak sah.")
    return 60 * jam + menit


def validasi_kebenaran(pilihan: PilihanButir, kunci: str, jenis: str) -> None:
    """Tepat satu nilai cocok kunci dan semua opsi berbeda secara semantik."""
    benar = nilai_semantis(kunci, jenis)
    nilai = tuple(nilai_semantis(o.nilai, jenis) for o in pilihan.opsi)
    if isinstance(benar, tuple) and any(len(x) != len(benar) for x in nilai):
        raise ValueError("Jumlah bagian jawaban pilihan tidak sama.")
    if len(set(nilai)) != len(nilai):
        raise ValueError("Opsi setara secara matematis.")
    if sum(x == benar for x in nilai) != 1:
        raise ValueError("Pilihan wajib memiliki tepat satu jawaban benar.")


def buat_pilihan(*, sesi_soal_id: int, fingerprint_pertanyaan: str,
                 kebijakan: str, jenis: str, kunci: str,
                 pengecoh: tuple[str, ...], seed: int, identitas: str) -> PilihanButir:
    """Acak kandidat terkurasi tanpa mengonsumsi RNG generator soal isian."""
    if kebijakan not in {"tiga-v1", "empat-v1"}:
        raise ValueError("Kebijakan pembentukan pilihan tidak dikenal.")
    if type(seed) is not int or not isinstance(identitas, str) or not identitas:
        raise ValueError("Seed atau identitas pengacakan tidak sah.")
    if type(pengecoh) is not tuple or len(pengecoh) != JUMLAH_OPSI[kebijakan] - 1:
        raise ValueError("Jumlah pengecoh terkurasi tidak sesuai kebijakan.")
    nilai = [kunci, *pengecoh]
    bahan = json.dumps([1, kebijakan, seed, identitas], ensure_ascii=False, separators=(",", ":"))
    rng = random.Random(int.from_bytes(hashlib.sha256(bahan.encode("utf-8")).digest(), "big"))
    rng.shuffle(nilai)
    opsi = tuple(OpsiJawaban(f"opsi_{i + 1}", "ABCDE"[i], x, x)
                 for i, x in enumerate(nilai))
    pilihan = PilihanButir(sesi_soal_id, fingerprint_pertanyaan, kebijakan, opsi)
    validasi_kebenaran(pilihan, kunci, jenis)
    return pilihan


def pilihan_tertanam(*, sesi_soal_id: int, fingerprint_pertanyaan: str,
                     teks_opsi: tuple[str, ...], kunci: str) -> PilihanButir:
    """Pertahankan A–E dari penyajian asal; jangan membuat lapisan label kedua.

    Teks opsi adalah proyeksi aman server dari soal yang sudah direview, bukan
    parameter rahasia atau HTML. Adapter visual tinggal di lapisan penyajian.
    """
    if type(teks_opsi) is not tuple or len(teks_opsi) != 5 or kunci not in tuple("ABCDE"):
        raise ValueError("Lima pilihan asal atau kunci tidak sah.")
    pilihan = PilihanButir(
        sesi_soal_id, fingerprint_pertanyaan, "tertanam-lima-v1",
        tuple(OpsiJawaban(f"opsi_{i + 1}", h, h, teks_opsi[i])
              for i, h in enumerate("ABCDE")),
    )
    validasi_kebenaran(pilihan, kunci, "kategori")
    return pilihan
