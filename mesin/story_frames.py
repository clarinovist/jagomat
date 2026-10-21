"""Bank kalimat terkurasi offline untuk snapshot baru melalui opt-in.

Hanya parameter publik yang diterima. Kunci, malrule dan identitas matematis
milik template; modul ini tidak membuat atau mengubahnya. Snapshot lama tidak
boleh dirender ulang memakai bank ini. Isi ditinjau per versi sebelum aktivasi.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
import re
from string import Formatter
from types import MappingProxyType
from typing import Mapping, Optional

VERSI_BANK = "bingkai-2026-10-v1"


@dataclass(frozen=True)
class Bingkai:
    id: str
    pola: str


@dataclass(frozen=True)
class Kalimat:
    """Provenance untuk penulis snapshot; tidak masuk parameter/tanda tangan soal."""
    bank_versi: str
    bingkai_id: str
    teks: str


# Pola harus memiliki setiap parameter tepat sekali; tidak ada field turunan
# kunci. Kalimat tetap menyatakan operasi/asumsi yang mendasari malrule lama.
BANK = MappingProxyType({
    "kpk_dua_bilangan": (
        Bingkai("kpk.pengingat", "Dua pengingat berbunyi berkala, yang pertama setiap {a} menit dan yang kedua setiap {b} menit. Keduanya baru saja berbunyi bersamaan. Berapa menit lagi keduanya pertama kali berbunyi bersamaan?"),
        Bingkai("kpk.lampu", "Dua lampu menyala berkala: lampu merah setiap {a} menit, lampu biru setiap {b} menit. Sekarang keduanya menyala bersamaan. Setelah berapa menit keduanya menyala bersamaan lagi untuk pertama kalinya?"),
        Bingkai("kpk.bel", "Bel di ruang A berbunyi setiap {a} menit dan bel di ruang B setiap {b} menit. Jika keduanya berbunyi bersamaan sekarang, berapa menit waktu tunggu sampai bunyi bersama berikutnya?"),
        Bingkai("kpk.sinyal", "Sinyal A muncul setiap {a} menit dan sinyal B setiap {b} menit. Keduanya muncul bersamaan saat pengamatan dimulai. Pada menit ke berapa setelah itu keduanya pertama kali muncul bersamaan lagi?"),
        Bingkai("kpk.alarm", "Alarm A berbunyi setiap {a} menit, sedangkan alarm B berbunyi setiap {b} menit. Saat ini kedua alarm berbunyi. Berapa menit hingga keduanya berbunyi bersamaan lagi untuk pertama kalinya?"),
        Bingkai("kpk.penanda", "Penanda merah berkedip setiap {a} menit dan penanda hijau setiap {b} menit. Pengamatan dimulai ketika keduanya berkedip bersamaan. Berapa menit kemudian keduanya pertama kali berkedip bersamaan lagi?"),
    ),
    "aturan_kali": (
        Bingkai("kali.kartu", "Tersedia {m} motif kartu dan {n} warna amplop. Sebuah paket memakai satu motif kartu dan satu warna amplop. Setiap motif dapat dipasangkan dengan setiap warna. Berapa banyak paket berbeda yang dapat dipilih?"),
        Bingkai("kali.pita", "Ada {m} warna pita dan {n} bentuk label. Untuk hiasan dipilih satu warna pita dan satu bentuk label; semua pasangan diperbolehkan. Berapa banyak pilihan hiasan berbeda?"),
        Bingkai("kali.stempel", "Sebuah stempel dapat memakai salah satu dari {m} gambar dan salah satu dari {n} warna tinta. Semua gambar dapat dicetak dengan semua warna. Berapa banyak pilihan gambar berwarna yang dapat dibuat?"),
        Bingkai("kali.sampul", "Pilihan sampul terdiri atas {m} pola, sedangkan pilihan penanda buku terdiri atas {n} warna. Pilih satu pola sampul dan satu warna penanda; setiap pasangan boleh dipilih. Ada berapa pilihan pasangan?"),
        Bingkai("kali.lencana", "Untuk membuat lencana tersedia {m} bentuk dan {n} warna tali. Satu lencana memakai satu bentuk dan satu warna tali. Setiap bentuk cocok dengan setiap warna tali. Berapa banyak pilihan lencana?"),
        Bingkai("kali.bingkai", "Ada {m} gambar dan {n} jenis bingkai. Satu pajangan dibuat dengan memilih satu gambar dan satu jenis bingkai. Semua gambar dapat memakai semua bingkai. Berapa banyak pilihan pajangan berbeda?"),
    ),
    "jabat_tangan": (
        Bingkai("jabat.pertemuan", "Sebuah pertemuan dihadiri {n} orang. Setiap pasangan orang berjabat tangan tepat sekali dan tidak ada yang berjabat tangan dengan dirinya sendiri. Berapa jumlah jabat tangan seluruhnya?"),
        Bingkai("jabat.panitia", "Panitia beranggotakan {n} orang. Sebelum rapat, setiap orang berjabat tangan sekali dengan setiap anggota lain. Satu pasangan hanya dihitung sekali. Berapa banyak jabat tangan yang terjadi?"),
        Bingkai("jabat.reuni", "Ada {n} orang di sebuah reuni. Semua orang saling berjabat tangan, tepat sekali untuk setiap pasangan orang berbeda. Berapa jumlah seluruh jabat tangan?"),
        Bingkai("jabat.kenalan", "Dalam acara perkenalan hadir {n} orang. Masing-masing berjabat tangan dengan semua orang lain, tanpa mengulang pasangan yang sama. Berapa jabat tangan yang terjadi?"),
        Bingkai("jabat.diskusi", "Kelompok diskusi terdiri atas {n} orang. Setiap orang berjabat tangan satu kali dengan setiap orang lainnya. Hitung banyaknya jabat tangan, bukan banyaknya tangan yang bergerak."),
        Bingkai("jabat.silaturahmi", "Acara silaturahmi diikuti {n} orang. Setiap pasangan dari orang-orang tersebut saling berjabat tangan tepat sekali. Berapa banyak kejadian jabat tangan selama acara itu?"),
    ),
})
PARAMETER = MappingProxyType({"kpk_dua_bilangan": ("a", "b"), "aturan_kali": ("m", "n"), "jabat_tangan": ("n",)})
LEVEL = MappingProxyType({"kpk_dua_bilangan": ("P5", "P6"), "aturan_kali": ("P5",), "jabat_tangan": ("P5",)})


def validasi_bank(bank: Mapping[str, tuple[Bingkai, ...]]) -> None:
    """Struktur/placeholder diperiksa lokal; makna masih wajib review semantik."""
    if set(bank) != set(PARAMETER):
        raise ValueError("allowlist bingkai berubah tanpa tinjauan")
    ids = set()
    for tid, bingkai in bank.items():
        if not isinstance(bingkai, tuple) or len(bingkai) < 6:
            raise ValueError("bank bingkai belum lengkap")
        for item in bingkai:
            if not isinstance(item, Bingkai) or not re.fullmatch(r"[a-z][a-z0-9_.-]+", item.id) or item.id in ids:
                raise ValueError("identitas bingkai tidak sah atau duplikat")
            ids.add(item.id)
            if not isinstance(item.pola, str) or not item.pola.strip() or len(item.pola) > 500 or re.search(r"[<>\d]", item.pola):
                raise ValueError("pola bingkai memuat angka literal/markup atau panjang tidak sah")
            fields = []
            for _, field, spec, conversion in Formatter().parse(item.pola):
                if field is not None:
                    if field not in PARAMETER[tid] or spec or conversion:
                        raise ValueError("placeholder bingkai tidak diizinkan")
                    fields.append(field)
            if Counter(fields) != Counter(PARAMETER[tid]):
                raise ValueError("placeholder hilang atau berulang")


def aktif() -> bool:
    """Rollout eksplisit; nilai asing bukan aktivasi atau fallback diam-diam."""
    nilai = os.environ.get("OSN_BANK_KALIMAT", "0")
    if nilai not in ("0", "1"):
        raise ValueError("OSN_BANK_KALIMAT hanya menerima 0 atau 1")
    return nilai == "1"


def untuk_snapshot_baru(soal) -> Optional[Kalimat]:
    """Gunakan hanya teks bawaan yang dikenali, bukan cerita kustom/riwayat.

    Snapshot v1 tidak memiliki field ID bank. Hasil seleksi berguna untuk
    manifest offline; hanya teksnya yang dibekukan pada snapshot runtime.
    """
    if not aktif() or soal.template_id not in PARAMETER or soal.level not in LEVEL[soal.template_id]:
        return None
    from templates import REGISTRI

    asli = REGISTRI[soal.template_id](**soal.parameter)
    if soal.teks != asli.teks or soal.penyajian is not None:
        return None
    # Kenali hanya empat bentuk cerita canonical yang sudah ditinjau.
    # Bentuk murni ATAU bentuk baru yang belum ditinjau tidak ditimpa.
    if soal.template_id == "kpk_dua_bilangan":
        p = soal.parameter
        dikenal = {
            f"{pembuka} {p['a']} {satuan} dan {p['b']} {satuan}. Jika tadi keduanya "
            f"{kejadian}, setelah berapa {satuan} keduanya {kejadian} lagi?"
            for pembuka, satuan, kejadian in (
                ("Dua lampu hias berkedip setiap", "detik", "berkedip bersamaan"),
                ("Dua bus berangkat dari terminal setiap", "menit", "berangkat bersamaan"),
                ("Dua lonceng dibunyikan setiap", "detik", "berbunyi bersamaan"),
                ("Dua kapal singgah di pelabuhan setiap", "hari", "singgah bersamaan"),
            )
        }
        if soal.teks not in dikenal:
            return None
    return kalimat_baru(soal.template_id, soal.level, soal.parameter)


def kalimat_baru(template_id: str, level: str, parameter: Mapping[str, int], *, nomor: int = 0) -> Optional[Kalimat]:
    """Pilih untuk snapshot baru saja; None berarti template/level bukan allowlist.

    Nomor bingkai eksplisit dapat dipakai preview offline. Tidak membaca cache,
    database, env provider, atau data anak. Dilarang dipanggil reader histori.
    """
    if template_id not in PARAMETER or level not in LEVEL[template_id]:
        return None
    if type(nomor) is not int or nomor < 0:
        raise ValueError("nomor bingkai wajib bilangan bulat nonnegatif")
    fields = PARAMETER[template_id]
    if set(parameter) != set(fields) or any(type(parameter[k]) is not int or parameter[k] < 1 for k in fields):
        raise ValueError("hanya parameter publik bulat positif yang diterima")
    validasi_bank(BANK)
    data = json.dumps([VERSI_BANK, template_id, level, dict(parameter)], sort_keys=True, separators=(",", ":"))
    indeks = int(hashlib.sha256(data.encode()).hexdigest(), 16)
    item = BANK[template_id][(indeks + nomor) % len(BANK[template_id])]
    return Kalimat(VERSI_BANK, item.id, item.pola.format(**parameter))
