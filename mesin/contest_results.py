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

MIN_SESI_TREN = 4              # tren baru dihitung bila ada sedikitnya empat sesi selesai
BANYAK_SESI_TREN = 3           # bandingkan rata-rata tiga sesi terakhir dengan tiga pertama
BATAS_JENIS_BAWAAN = 5
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


@dataclass(frozen=True)
class Progres:
    sesi: Tuple[RingkasSesi, ...]                 # urut dari yang terlama
    jumlah: int
    terbaik: Optional[int]
    rata_rata: Optional[float]
    terakhir: Optional[int]
    selisih_tren: Optional[float]
    per_topik_total: Tuple[NilaiTopik, ...]


@dataclass(frozen=True)
class JenisSering:
    template_id: str
    label: str
    salah: int
    total: int


def label_jenis(template_id: str) -> str:
    """Label ramah untuk id template: buang awalan topik, garis bawah jadi spasi."""
    return _AWALAN_TOPIK.sub("", template_id).replace("_", " ")


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
    for baris in _ambil_baris(kon, [s["id"] for s in sesi_baris]):
        per_sesi.setdefault(baris["sesi_id"], []).append((baris["topik"], _benar(baris)))
    return tuple(
        RingkasSesi(
            sesi_id=s["id"], mulai_epoch=s["mulai_epoch"], selesai_epoch=s["selesai_epoch"], status=s["status"],
            nilai=sum(1 for _, benar in per_sesi.get(s["id"], []) if benar),
            jumlah_soal=len(per_sesi.get(s["id"], [])),
            waktu_terpakai_detik=s["selesai_epoch"] - s["mulai_epoch"],
            per_topik=_per_topik(per_sesi.get(s["id"], [])))
        for s in sesi_baris)


def _rata(nilai: Sequence[int]) -> float:
    return sum(nilai) / len(nilai)


def progres(kon, siswa_id: int, sekarang: int) -> Progres:
    sesi = riwayat_sesi(kon, siswa_id, sekarang)
    if not sesi:
        return Progres(sesi=(), jumlah=0, terbaik=None, rata_rata=None, terakhir=None,
                       selisih_tren=None, per_topik_total=())
    nilai = [s.nilai for s in sesi]
    tren = None
    if len(sesi) >= MIN_SESI_TREN:
        tren = round(_rata(nilai[-BANYAK_SESI_TREN:]) - _rata(nilai[:BANYAK_SESI_TREN]), 2)
    gabungan: Dict[str, List[int]] = {}
    for s in sesi:
        for n in s.per_topik:
            akun = gabungan.setdefault(n.topik, [0, 0])
            akun[0] += n.benar
            akun[1] += n.total
    total = tuple(NilaiTopik(t, gabungan[t][0], gabungan[t][1]) for t in C.TOPIK if t in gabungan)
    return Progres(sesi=sesi, jumlah=len(sesi), terbaik=max(nilai), rata_rata=round(_rata(nilai), 1),
                   terakhir=nilai[-1], selisih_tren=tren, per_topik_total=total)


def jenis_sering_salah(kon, siswa_id: int, sekarang: int, batas: int = BATAS_JENIS_BAWAAN) -> Tuple[JenisSering, ...]:
    """Jenis soal yang paling sering salah (salah terbanyak, lalu rasio salah); yang selalu benar tidak muncul."""
    K.tutup_yang_habis(kon, siswa_id, sekarang)
    ids = [b["id"] for b in kon.execute(
        "SELECT id FROM lomba_sesi WHERE siswa_id = ? AND status != 'berjalan'", (siswa_id,))]
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
