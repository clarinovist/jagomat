"""Struktur data satu laporan Peta Kemampuan dan pemeriksa konsistensinya.

Kontrak antara pembuat data (contoh sintetis sekarang, laporan nyata kelak) dan
renderer (`peta_laporan`, `peta_lembar`). Semua struktur beku (frozen); angka
turunan (skor, kategori, jumlah salah) dihitung dari field, bukan disimpan dua kali.

`periksa_konsisten` menjaga angka satu laporan saling cocok:
jumlah soal per materi = total soal, benar per materi = total benar, jumlah pola
kesalahan = total salah (juga per materi), dan rujukan antarbagian ada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple, Union

from cek_gratis_skor import hitung_skor, kategori_dari_skor


@dataclass(frozen=True)
class Langkah:
    """Satu langkah pekerjaan anak; `salah` menandai langkah tempat salahnya muncul."""

    teks: str
    salah: bool = False
    tanda: str = ""


@dataclass(frozen=True)
class Susun:
    """Perkalian bersusun satu pengali: `atas` x `bawah`, simpanan, dan hasil anak."""

    atas: int
    bawah: int
    simpanan: int
    hasil_anak: int


@dataclass(frozen=True)
class Bagian:
    """Gambar pecahan: `terisi` dari `total` bagian diarsir."""

    terisi: int
    total: int


@dataclass(frozen=True)
class ContohSoal:
    """Contoh soal yang salah, dengan langkah anak (langkah salah ditandai)."""

    soal: str
    jawaban_anak: str
    jawaban_benar: str
    langkah: Tuple[Langkah, ...]
    visual: Optional[Union[Susun, Bagian]] = None


@dataclass(frozen=True)
class Materi:
    """Penguasaan satu materi. `kunci` menentukan ikon dan warna di renderer."""

    kunci: str
    nama: str
    soal: int
    benar: int
    ringkas: str
    yang_dilatih: str
    latihan: str
    contoh: Optional[ContohSoal] = None

    @property
    def salah(self) -> int:
        return self.soal - self.benar


@dataclass(frozen=True)
class Pola:
    """Pola kesalahan: jumlah jawaban salah (bukan persen), tersebar per materi."""

    kunci: str
    nama: str
    sebaran: Tuple[Tuple[str, int], ...]
    asal: str
    contoh: str
    penjelasan: str
    simbol: str
    materi_tujuan: str

    @property
    def jumlah(self) -> int:
        return sum(jumlah for _materi, jumlah in self.sebaran)


@dataclass(frozen=True)
class Temuan:
    """Temuan Guru di lembar 1 halaman: satu pola dengan kalimat Guru."""

    pola_kunci: str
    judul: str


@dataclass(frozen=True)
class Misi:
    """Misi berikutnya; `pola_kunci` (opsional) mengambil jumlah salah dari pola."""

    materi_kunci: str
    judul: str
    catatan: str
    langkah: Tuple[str, ...]
    minggu: str
    pola_kunci: str = ""


@dataclass(frozen=True)
class Guru:
    nama: str
    latar: str
    lama_mengajar: str


@dataclass(frozen=True)
class Resep:
    judul: str
    teks: str


@dataclass(frozen=True)
class Lencana:
    nama: str
    keterangan: str
    ikon: str
    didapat: bool


@dataclass(frozen=True)
class Pilihan:
    kunci: str
    label: str


@dataclass(frozen=True)
class Tantangan:
    soal: str
    petunjuk: str
    pilihan: Tuple[Pilihan, ...]
    benar: str
    umpan_benar: str
    umpan_salah: str
    kata_maskot: str


@dataclass(frozen=True)
class LaporanPeta:
    """Satu laporan Peta Kemampuan lengkap."""

    nama_anak: str
    kelas: int
    tanggal_cek: date
    tanggal_terbit: date
    jumlah_soal: int
    jumlah_benar: int
    materi: Tuple[Materi, ...]
    pola: Tuple[Pola, ...]
    temuan: Tuple[Temuan, ...]
    misi: Tuple[Misi, ...]
    guru: Guru
    catatan_guru: str
    resep: Resep
    lencana: Tuple[Lencana, ...]
    tantangan: Tantangan
    skor_pembanding: Tuple[int, ...]
    # Tanpa nilai bawaan: pembuat laporan nyata harus menyatakan sendiri bahwa Guru sudah meninjau.
    ditinjau: bool

    @property
    def jumlah_salah(self) -> int:
        return self.jumlah_soal - self.jumlah_benar

    @property
    def skor(self) -> int:
        return hitung_skor(self.jumlah_benar, self.jumlah_soal)

    @property
    def kategori(self) -> str:
        return kategori_dari_skor(self.skor)


def _periksa_materi(data: LaporanPeta) -> dict:
    if not data.materi:
        raise ValueError("laporan butuh minimal satu materi")
    per_kunci = {}
    for materi in data.materi:
        if materi.kunci in per_kunci:
            raise ValueError("kunci materi ganda: %s" % materi.kunci)
        if materi.soal < 1 or not 0 <= materi.benar <= materi.soal:
            raise ValueError("soal/benar materi %s tidak sah" % materi.kunci)
        per_kunci[materi.kunci] = materi
    if sum(m.soal for m in data.materi) != data.jumlah_soal:
        raise ValueError("jumlah soal materi tidak sama dengan total soal")
    if sum(m.benar for m in data.materi) != data.jumlah_benar:
        raise ValueError("jumlah benar materi tidak sama dengan total benar")
    return per_kunci


def _periksa_pola(data: LaporanPeta, per_materi: dict) -> dict:
    per_kunci = {}
    salah_per_materi = {kunci: 0 for kunci in per_materi}
    for pola in data.pola:
        if pola.kunci in per_kunci:
            raise ValueError("kunci pola ganda: %s" % pola.kunci)
        per_kunci[pola.kunci] = pola
        if pola.materi_tujuan not in per_materi:
            raise ValueError("materi tujuan pola %s tidak dikenal" % pola.kunci)
        for kunci_materi, jumlah in pola.sebaran:
            if kunci_materi not in per_materi or type(jumlah) is not int or jumlah < 1:
                raise ValueError("sebaran pola %s tidak sah" % pola.kunci)
            salah_per_materi[kunci_materi] += jumlah
    if sum(p.jumlah for p in data.pola) != data.jumlah_salah:
        raise ValueError("jumlah pola kesalahan tidak sama dengan total salah")
    for kunci, materi in per_materi.items():
        if salah_per_materi[kunci] != materi.salah:
            raise ValueError("salah materi %s tidak sama dengan jumlah pola" % kunci)
    return per_kunci


def _periksa_rujukan(data: LaporanPeta, per_materi: dict, per_pola: dict) -> None:
    for temuan in data.temuan:
        if temuan.pola_kunci not in per_pola:
            raise ValueError("temuan merujuk pola tak dikenal")
    for misi in data.misi:
        if misi.materi_kunci not in per_materi:
            raise ValueError("misi merujuk materi tak dikenal")
        if misi.pola_kunci and misi.pola_kunci not in per_pola:
            raise ValueError("misi merujuk pola tak dikenal")
    kunci_pilihan = {p.kunci for p in data.tantangan.pilihan}
    if data.tantangan.benar not in kunci_pilihan:
        raise ValueError("jawaban benar tantangan bukan salah satu pilihan")


def periksa_konsisten(data: LaporanPeta) -> None:
    """ValueError bila angka atau rujukan di `data` tidak saling cocok; None bila sah."""
    if not 0 <= data.jumlah_benar <= data.jumlah_soal or data.jumlah_soal < 1:
        raise ValueError("jumlah soal/benar tidak sah")
    if not data.ditinjau and data.catatan_guru.strip():
        raise ValueError("catatan Guru tanpa tinjauan Guru")
    per_materi = _periksa_materi(data)
    per_pola = _periksa_pola(data, per_materi)
    _periksa_rujukan(data, per_materi, per_pola)
