"""Tingkat Latihan Harian: Tingkat 1-6 (bab Kurikulum Merdeka per kelas) dan dua Tantangan OSN.

Data murni, tanpa DB. Tiap tingkat dipetakan ke kumpulan *sumber* (bab, atau grup pengayaan untuk OSN) yang
masing-masing berisi `(topik_id, template_id, level)` yang tersedia di level tingkat itu dan palang rilisnya
terbuka (`kurikulum_kelas_hitung.template_dibuka`, dibaca di luar cache supaya sakelar langsung terlihat).
Kecocokan bab 'ada' dan 'sebagian' sama-sama boleh. Jenis soal yang tak bisa jadi PG 4 opsi sah dikeluarkan
(`harian_pg.audit_template`); `audit_tingkat` melaporkan daftar yang tersisih per tingkat.

Nama tingkat memakai judul materi, bukan "Kelas", supaya anak bebas memilih tanpa malu.
Saran tingkat dari profil kelas anak (`learning_profile`) hanya saran: anak memilih sendiri.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional, Tuple

import harian_pg
import kurikulum_katalog as kat
import kurikulum_kelas as kk
import kurikulum_kelas_hitung as hitung
import learning_profile
import topics

KODE_OSN_PEMULA = "osn-pemula"
KODE_OSN_LANJUT = "osn-lanjut"

# (topik_id, template_id, level)
Ref = Tuple[str, str, str]


@dataclass(frozen=True)
class Tingkat:
    kode: str
    judul: str
    ringkas: str
    kelas: Optional[int]  # kelas buku (1-6) untuk Tingkat 1-6; None untuk Tantangan OSN
    level: Tuple[str, ...]  # level P<k> tempat template dicari
    bawah: Optional[str]  # kode tingkat yang soalnya boleh jadi ulangan (maks 2 per sesi)


DAFTAR_TINGKAT: Tuple[Tingkat, ...] = (
    Tingkat("t1", "Tingkat 1", "Bilangan sampai 20, bentuk, dan diagram", 1, ("P1",), None),
    Tingkat("t2", "Tingkat 2", "Bilangan sampai 100, jam, dan pecahan setengah", 2, ("P2",), "t1"),
    Tingkat("t3", "Tingkat 3", "Ribuan, perkalian, dan bangun datar", 3, ("P3",), "t2"),
    Tingkat("t4", "Tingkat 4", "Pecahan, pola, dan luas", 4, ("P4",), "t3"),
    Tingkat("t5", "Tingkat 5", "KPK, FPB, pecahan, dan sudut", 5, ("P5",), "t4"),
    Tingkat("t6", "Tingkat 6", "Rasio, pecahan desimal, dan kubus", 6, ("P6",), "t5"),
    Tingkat(KODE_OSN_PEMULA, "Tantangan OSN Pemula", "Soal pengayaan tingkat awal", None, ("P3", "P4"), None),
    Tingkat(KODE_OSN_LANJUT, "Tantangan OSN Lanjut", "Soal pengayaan tingkat lanjut", None, ("P5", "P6"),
            KODE_OSN_PEMULA),
)
KODE_SAH = tuple(t.kode for t in DAFTAR_TINGKAT)
_PETA = {t.kode: t for t in DAFTAR_TINGKAT}


@dataclass(frozen=True)
class Sumber:
    label: str
    refs: Tuple[Ref, ...]


def ambil_tingkat(kode) -> Tingkat:
    """Tingkat menurut kode; `KeyError` bila bukan kode sah (pemanggil menjawab 404/tolak)."""
    if not isinstance(kode, str) or kode not in _PETA:
        raise KeyError(kode)
    return _PETA[kode]


def saran_tingkat(kon, siswa_id: int) -> Optional[str]:
    """Kode tingkat yang disarankan dari kelas sekolah di profil anak; None bila belum diisi. Hanya membaca."""
    baris = kon.execute("SELECT pemilik FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
    if baris is None:
        return None
    try:
        kelas = learning_profile.baca(kon, siswa_id, pemilik=baris["pemilik"]).kelas_sekolah
    except learning_profile.ProfilTidakDitemukan:
        return None
    return None if kelas is None else "t%d" % kelas


def _sumber_kelas(tingkat: Tingkat) -> Tuple[Sumber, ...]:
    kelas = next(k for k in kk.KELAS if k.kelas == tingkat.kelas)
    level = hitung.level_kelas(kelas.kelas)
    hasil = []
    for bab in kelas.bab:
        pelatih = tuple(hitung.pelatih_kelas(t, g, c, kelas.kelas) for t, g, c in bab.pelatih)
        refs = tuple((topik, tid, level) for topik, tid in hitung.template_unik(pelatih))
        hasil.append(Sumber("%d. %s" % (bab.nomor, bab.judul), refs))
    return tuple(hasil)


def _sumber_osn(tingkat: Tingkat) -> Tuple[Sumber, ...]:
    terpakai = kk.grup_terpakai()
    hasil = []
    for entri in kat.KATALOG:
        nama_topik = topics.ambil(entri.topik_id).nama
        for kode, nama, pola in entri.grup:
            if (entri.topik_id, kode) in terpakai:
                continue
            refs = tuple((entri.topik_id, tid, level) for level in tingkat.level
                         for tid in hitung._template_di_level(entri.topik_id, tuple(pola), level))
            if refs:  # grup yang tak punya template di level tingkat ini bukan bagian tingkat ini
                hasil.append(Sumber("%s: %s" % (nama_topik, nama), refs))
    return tuple(hasil)


@lru_cache(maxsize=None)
def _sumber_mentah(kode: str) -> Tuple[Sumber, ...]:
    tingkat = ambil_tingkat(kode)
    return _sumber_kelas(tingkat) if tingkat.kelas is not None else _sumber_osn(tingkat)


def sumber_dibuka(kode: str) -> Tuple[Sumber, ...]:
    """Sumber tingkat dengan template yang palang rilisnya terbuka (tanpa audit PG); sumber kosong dibuang."""
    hasil = []
    for s in _sumber_mentah(kode):
        refs = tuple(r for r in s.refs if hitung.template_dibuka(r[1]))
        if refs:
            hasil.append(Sumber(s.label, refs))
    return tuple(hasil)


def sumber_layak(kode: str) -> Tuple[Sumber, ...]:
    """Sumber siap pakai: template terbuka DAN layak PG 4 opsi (audit). Sumber yang jadi kosong dibuang."""
    hasil = []
    for s in sumber_dibuka(kode):
        refs = tuple(r for r in s.refs if harian_pg.audit_template(*r).layak)
        if refs:
            hasil.append(Sumber(s.label, refs))
    return tuple(hasil)


@dataclass(frozen=True)
class Tersisih:
    sumber: str
    topik_id: str
    template_id: str
    level: str
    alasan: str  # "tertutup" (palang rilis) atau alasan dominan dari harian_pg.audit_template


@dataclass(frozen=True)
class LaporanTingkat:
    kode: str
    jumlah_sumber: int
    jumlah_sumber_layak: int
    jumlah_template_layak: int
    sumber_kosong: Tuple[str, ...]  # label sumber yang tidak punya satu pun jenis layak
    tersisih: Tuple[Tersisih, ...]


def _alasan_dominan(topik_id: str, template_id: str, level: str) -> str:
    laporan = harian_pg.audit_template(topik_id, template_id, level)
    if not laporan.alasan:
        return "peluang_lolos_rendah (%d/%d)" % (laporan.lolos, laporan.jumlah)
    utama = max(laporan.alasan, key=lambda p: p[1])[0]
    return "%s (lolos %d/%d)" % (utama, laporan.lolos, laporan.jumlah)


def audit_tingkat(kode: str) -> LaporanTingkat:
    """Daftar jenis soal yang tersisih per tingkat, plus sumber yang jadi kosong. Dipakai laporan audit dan tes."""
    tersisih = []
    for s in _sumber_mentah(kode):
        for topik, tid, level in s.refs:
            if not hitung.template_dibuka(tid):
                tersisih.append(Tersisih(s.label, topik, tid, level, "tertutup"))
            elif not harian_pg.audit_template(topik, tid, level).layak:
                tersisih.append(Tersisih(s.label, topik, tid, level, _alasan_dominan(topik, tid, level)))
    layak = sumber_layak(kode)
    nama_layak = {s.label for s in layak}
    kosong = tuple(s.label for s in _sumber_mentah(kode) if s.label not in nama_layak)
    return LaporanTingkat(kode, len(_sumber_mentah(kode)), len(layak), sum(len(s.refs) for s in layak),
                          kosong, tuple(tersisih))


def laporan_audit() -> str:
    """Teks laporan audit semua tingkat (untuk dicetak manual: `python -c "import harian_tingkat as h; print(h.laporan_audit())"`)."""
    baris = []
    for tingkat in DAFTAR_TINGKAT:
        lap = audit_tingkat(tingkat.kode)
        baris.append("%s: %d/%d sumber layak, %d jenis soal layak, %d tersisih" % (
            tingkat.judul, lap.jumlah_sumber_layak, lap.jumlah_sumber, lap.jumlah_template_layak,
            len(lap.tersisih)))
        for k in lap.sumber_kosong:
            baris.append("  SUMBER KOSONG: %s" % k)
        for t in lap.tersisih:
            baris.append("  - %s | %s/%s @%s | %s" % (t.sumber, t.topik_id, t.template_id, t.level, t.alasan))
    return "\n".join(baris)
