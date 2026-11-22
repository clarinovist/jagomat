"""Hasil rinci, riwayat, dan progress Latihan Lomba.

Berbeda dari `contest_store` (halaman anak saat sesi berjalan), modul ini MEMBACA KUNCI dan pembahasan,
jadi semua fungsinya hanya bekerja pada sesi yang sudah tidak berjalan (selesai, dikumpulkan, atau
waktu habis) dan selalu dibatasi ke satu `siswa_id`. Tidak menulis apa pun ke DB selain menutup sesi
yang batas waktunya sudah lewat (lewat `contest_store.tutup_yang_habis`).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import contest_core as C
import contest_store as K
from contest_label_jenis import LABEL_JENIS

MIN_SESI_TREN = 4              # tren baru dihitung bila ada sedikitnya empat sesi selesai
BANYAK_SESI_TREN = 3           # bandingkan rata-rata tiga sesi terakhir dengan tiga pertama
BATAS_JENIS_BAWAAN = 5
BATAS_DETIK_ASAL_KUMPUL = 120  # sesi selesai lebih cepat dari ini dianggap dikumpulkan asal
BATAS_TERISI_ASAL_KUMPUL = 3   # atau soal terjawab kurang dari ini
_AWALAN_TOPIK = re.compile(r"^(?:bil|ops|ukur|bgn)_")


@dataclass(frozen=True)
class NilaiTopik:
    topik: str
    benar: int
    total: int


@dataclass(frozen=True)
class ButirRinci:
    nomor: int
    topik: str
    jenis: str
    tingkat: int
    template_id: str
    teks: str
    svg: str
    pilihan: Tuple[str, ...]
    gambar_pilihan: Tuple[str, ...]
    jawaban: Optional[str]            # huruf (PG) atau angka (isian) milik anak; None bila kosong
    jawaban_teks: Optional[str]       # teks pilihan yang dipilih (PG) atau angka (isian)
    kunci: str
    kunci_huruf: Optional[str]        # huruf pilihan benar untuk PG; None untuk isian
    benar: bool
    kesalahan: Optional[str]          # hipotesis kesalahan pengecoh yang dipilih; hanya PG yang salah
    pembahasan: Tuple[str, ...]
    inggris: bool


@dataclass(frozen=True)
class HasilRinci:
    sesi: K.SesiRingkas
    nilai: int
    jumlah_soal: int
    waktu_terpakai_detik: int
    per_topik: Tuple[NilaiTopik, ...]
    butir: Tuple[ButirRinci, ...]


@dataclass(frozen=True)
class RingkasSesi:
    sesi_id: int
    mulai_epoch: int
    selesai_epoch: int
    status: str
    nilai: int
    jumlah_soal: int
    waktu_terpakai_detik: int
    per_topik: Tuple[NilaiTopik, ...]
    terisi: int = 0                  # banyak soal yang dijawab anak
    asal_kumpul: bool = False        # selesai < 120 detik ATAU terisi < 3: tak dihitung di agregat


@dataclass(frozen=True)
class Progres:
    sesi: Tuple[RingkasSesi, ...]                 # semua sesi selesai, urut dari yang terlama
    jumlah: int                                   # semua sesi selesai, termasuk asal kumpul
    terbaik: Optional[int]                        # agregat hanya dari sesi sah (bukan asal kumpul)
    rata_rata: Optional[float]
    terakhir: Optional[int]                       # nilai sesi terakhir (semua sesi)
    selisih_tren: Optional[float]
    per_topik_total: Tuple[NilaiTopik, ...]
    jumlah_asal_kumpul: int = 0
    rata_awal: Optional[float] = None             # rata-rata 3 sesi sah pertama
    rata_akhir: Optional[float] = None            # rata-rata 3 sesi sah terakhir


@dataclass(frozen=True)
class JenisSering:
    template_id: str
    label: str
    salah: int
    total: int


def label_jenis(template_id: str) -> str:
    """Label jenis soal untuk Guru (`LABEL_JENIS`); id tak dikenal: buang awalan topik, garis bawah jadi spasi."""
    return LABEL_JENIS.get(template_id) or _AWALAN_TOPIK.sub("", template_id).replace("_", " ")


def _asal_kumpul(waktu_terpakai_detik: int, terisi: int) -> bool:
    """Sesi dikumpulkan asal: waktu terpakai kurang dari 120 detik ATAU soal terjawab kurang dari 3."""
    return waktu_terpakai_detik < BATAS_DETIK_ASAL_KUMPUL or terisi < BATAS_TERISI_ASAL_KUMPUL


def _per_topik(pasangan: Sequence[Tuple[str, bool]]) -> Tuple[NilaiTopik, ...]:
    hitung: Dict[str, List[int]] = {}
    for topik, benar in pasangan:
        akun = hitung.setdefault(topik, [0, 0])
        akun[0] += int(benar)
        akun[1] += 1
    return tuple(NilaiTopik(t, hitung[t][0], hitung[t][1]) for t in C.TOPIK if t in hitung)


def _ambil_baris(kon, sesi_ids: Sequence[int]):
    penampung = ",".join("?" * len(sesi_ids))
    return kon.execute(
        "SELECT s.sesi_id, s.nomor, s.topik, s.jenis, s.tingkat, s.template_id, s.teks, s.svg, s.kunci, "
        "s.pilihan_json, s.gambar_pilihan_json, s.pengecoh_json, s.pembahasan_json, s.inggris, j.jawaban "
        "FROM lomba_soal s LEFT JOIN lomba_jawaban j ON j.sesi_id = s.sesi_id AND j.nomor = s.nomor "
        f"WHERE s.sesi_id IN ({penampung}) ORDER BY s.sesi_id, s.nomor", tuple(sesi_ids)).fetchall()


def _benar(baris) -> bool:
    return K.benar(baris["jenis"], baris["kunci"], json.loads(baris["pilihan_json"]), baris["jawaban"])


def _butir(baris) -> ButirRinci:
    pilihan = tuple(json.loads(baris["pilihan_json"]))
    jawaban = baris["jawaban"]
    pg = baris["jenis"] == C.JENIS_PG
    jawaban_teks = (pilihan[C.HURUF.index(jawaban)] if pg and jawaban in C.HURUF else jawaban)
    benar = _benar(baris)
    kesalahan = None
    if pg and jawaban is not None and not benar:
        label = {p["nilai"]: p["kesalahan"] for p in json.loads(baris["pengecoh_json"])}
        kesalahan = label.get(jawaban_teks)
    return ButirRinci(
        nomor=baris["nomor"], topik=baris["topik"], jenis=baris["jenis"], tingkat=baris["tingkat"],
        template_id=baris["template_id"], teks=baris["teks"], svg=baris["svg"], pilihan=pilihan,
        gambar_pilihan=tuple(json.loads(baris["gambar_pilihan_json"])), jawaban=jawaban,
        jawaban_teks=jawaban_teks, kunci=baris["kunci"],
        kunci_huruf=C.HURUF[pilihan.index(baris["kunci"])] if pg else None, benar=benar,
        kesalahan=kesalahan, pembahasan=tuple(json.loads(baris["pembahasan_json"])),
        inggris=bool(baris["inggris"]))


def hasil_rinci(kon, siswa_id: int, sesi_id: int, sekarang: int) -> HasilRinci:
    """Semua soal sesi dengan jawaban anak, kunci, dan pembahasan; hanya setelah sesi tidak berjalan."""
    sesi = K.ambil_sesi(kon, siswa_id, sesi_id, sekarang)
    if sesi.status == K.BERJALAN:
        raise K.SesiBerjalan(sesi_id)
    butir = tuple(_butir(baris) for baris in _ambil_baris(kon, [sesi_id]))
    return HasilRinci(
        sesi=sesi, nilai=sum(1 for b in butir if b.benar), jumlah_soal=len(butir),
        waktu_terpakai_detik=sesi.selesai_epoch - sesi.mulai_epoch,
        per_topik=_per_topik([(b.topik, b.benar) for b in butir]), butir=butir)


def riwayat_sesi(kon, siswa_id: int, sekarang: int) -> Tuple[RingkasSesi, ...]:
    """Sesi selesai milik anak, dari yang terlama (cocok untuk grafik); sesi berjalan tidak ikut."""
    K.tutup_yang_habis(kon, siswa_id, sekarang)
    sesi_baris = kon.execute(
        "SELECT id, status, mulai_epoch, selesai_epoch FROM lomba_sesi "
        "WHERE siswa_id = ? AND status != 'berjalan' ORDER BY id", (siswa_id,)).fetchall()
    if not sesi_baris:
        return ()
    per_sesi: Dict[int, List[Tuple[str, bool]]] = {}
    terisi: Dict[int, int] = {}
    for baris in _ambil_baris(kon, [s["id"] for s in sesi_baris]):
        per_sesi.setdefault(baris["sesi_id"], []).append((baris["topik"], _benar(baris)))
        terisi[baris["sesi_id"]] = terisi.get(baris["sesi_id"], 0) + int(baris["jawaban"] is not None)
    return tuple(_ringkas(s, per_sesi.get(s["id"], []), terisi.get(s["id"], 0)) for s in sesi_baris)


def _ringkas(sesi, pasangan: Sequence[Tuple[str, bool]], terisi: int) -> RingkasSesi:
    waktu = sesi["selesai_epoch"] - sesi["mulai_epoch"]
    return RingkasSesi(
        sesi_id=sesi["id"], mulai_epoch=sesi["mulai_epoch"], selesai_epoch=sesi["selesai_epoch"],
        status=sesi["status"], nilai=sum(1 for _, benar in pasangan if benar), jumlah_soal=len(pasangan),
        waktu_terpakai_detik=waktu, per_topik=_per_topik(pasangan), terisi=terisi,
        asal_kumpul=_asal_kumpul(waktu, terisi))


def _rata(nilai: Sequence[int]) -> float:
    return sum(nilai) / len(nilai)


def _gabung_topik(sesi: Sequence[RingkasSesi]) -> Tuple[NilaiTopik, ...]:
    gabungan: Dict[str, List[int]] = {}
    for s in sesi:
        for n in s.per_topik:
            akun = gabungan.setdefault(n.topik, [0, 0])
            akun[0] += n.benar
            akun[1] += n.total
    return tuple(NilaiTopik(t, gabungan[t][0], gabungan[t][1]) for t in C.TOPIK if t in gabungan)


def _tren(nilai: Sequence[int]) -> Tuple[Optional[float], Optional[float]]:
    """(rata 3 sesi sah pertama, rata 3 sesi sah terakhir); None bila sesi sah belum cukup."""
    if len(nilai) < MIN_SESI_TREN:
        return None, None
    return round(_rata(nilai[:BANYAK_SESI_TREN]), 2), round(_rata(nilai[-BANYAK_SESI_TREN:]), 2)


def progres(kon, siswa_id: int, sekarang: int) -> Progres:
    """Ringkasan anak. Terbaik, rata-rata, tren, dan per topik hanya dari sesi sah (bukan asal kumpul)."""
    sesi = riwayat_sesi(kon, siswa_id, sekarang)
    if not sesi:
        return Progres(sesi=(), jumlah=0, terbaik=None, rata_rata=None, terakhir=None,
                       selisih_tren=None, per_topik_total=())
    sah = [s for s in sesi if not s.asal_kumpul]
    nilai = [s.nilai for s in sah]
    awal, akhir = _tren(nilai)
    selisih = None if awal is None else round(_rata(nilai[-BANYAK_SESI_TREN:]) - _rata(nilai[:BANYAK_SESI_TREN]), 2)
    return Progres(
        sesi=sesi, jumlah=len(sesi), terbaik=max(nilai) if nilai else None,
        rata_rata=round(_rata(nilai), 1) if nilai else None, terakhir=sesi[-1].nilai,
        selisih_tren=selisih, per_topik_total=_gabung_topik(sah),
        jumlah_asal_kumpul=len(sesi) - len(sah), rata_awal=awal, rata_akhir=akhir)


def jenis_sering_salah(kon, siswa_id: int, sekarang: int, batas: int = BATAS_JENIS_BAWAAN) -> Tuple[JenisSering, ...]:
    """Jenis soal yang paling sering salah (salah terbanyak, lalu rasio salah); sesi asal kumpul dan jenis yang selalu benar tidak ikut."""
    K.tutup_yang_habis(kon, siswa_id, sekarang)
    ids = [s.sesi_id for s in riwayat_sesi(kon, siswa_id, sekarang) if not s.asal_kumpul]
    if not ids:
        return ()
    hitung: Dict[str, List[int]] = {}
    for baris in _ambil_baris(kon, ids):
        akun = hitung.setdefault(baris["template_id"], [0, 0])
        akun[0] += int(not _benar(baris))
        akun[1] += 1
    kandidat = [JenisSering(t, label_jenis(t), salah, total) for t, (salah, total) in hitung.items() if salah]
    kandidat.sort(key=lambda j: (-j.salah, -(j.salah / j.total), j.template_id))
    return tuple(kandidat[:batas])
