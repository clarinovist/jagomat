"""Penyimpanan sesi Latihan Lomba: timer yang dipegang server, jawaban, dan nilai.

Semua batas waktu memakai epoch detik dari jam server; `sekarang` selalu parameter (handler
memberi `int(time.time())`, tes memberi angka tetap). Jam klien tidak pernah dipercaya.
Sesi yang lewat batas ditutup secara malas (saat dibaca, disimpan, atau dikumpulkan) dengan satu
pernyataan UPDATE bersyarat, dan simpan jawaban satu pernyataan atomik yang menolak diri sendiri
bila sesi bukan milik anak itu, sudah tidak berjalan, atau sudah melewati batas.

Halaman anak hanya boleh memakai `soal_untuk_anak` (kolom aman); kunci dan pembahasan hanya dibaca
`hasil_ringkas` setelah sesi tidak lagi berjalan.
"""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from typing import AbstractSet, FrozenSet, Optional, Sequence, Tuple

import contest_core as C
import contest_session as S
import contest_templates

DURASI_DETIK = 15 * 60
PAKET_ID = "corexis_l1_matematika"
BERJALAN, DIKUMPUL, WAKTU_HABIS = "berjalan", "dikumpul", "waktu_habis"
SEED_BIT = 63
NOMOR_PERTAMA, NOMOR_TERAKHIR = 1, S.JUMLAH_SOAL
_POLA_ISIAN = re.compile(r"^[0-9]{1,6}$")
_SAVEPOINT = "lomba_mulai"
_KOLOM_SESI = "id, siswa_id, status, mulai_epoch, batas_epoch, selesai_epoch"
_SYARAT_BERJALAN = ("EXISTS (SELECT 1 FROM lomba_sesi WHERE id = ? AND siswa_id = ? "
                    "AND status = 'berjalan' AND batas_epoch > ?)")


class SesiTidakDitemukan(LookupError):
    """Sesi atau nomor tidak ada, atau bukan milik anak itu (pemanggil menjawab 404 yang identik)."""


class SesiSelesai(RuntimeError):
    """Sesi sudah dikumpulkan atau waktunya habis; jawaban tidak diterima lagi."""


class SesiBerjalan(RuntimeError):
    """Hasil belum boleh dilihat selama sesi masih berjalan."""


class JawabanTidakSah(ValueError):
    """Bentuk jawaban tidak cocok dengan jenis soal."""


@dataclass(frozen=True)
class SesiRingkas:
    id: int
    siswa_id: int
    status: str
    mulai_epoch: int
    batas_epoch: int
    selesai_epoch: Optional[int]

    def sisa_detik(self, sekarang: int) -> int:
        return max(0, self.batas_epoch - sekarang) if self.status == BERJALAN else 0


@dataclass(frozen=True)
class SoalAnak:
    nomor: int
    jenis: str
    topik: str
    teks: str
    svg: str
    pilihan: Tuple[str, ...]
    gambar_pilihan: Tuple[str, ...]
    jawaban: Optional[str]


@dataclass(frozen=True)
class HasilRingkas:
    nilai: int
    jumlah_soal: int
    waktu_terpakai_detik: int
    status: str


def _ringkas(baris) -> SesiRingkas:
    return SesiRingkas(id=baris["id"], siswa_id=baris["siswa_id"], status=baris["status"],
                       mulai_epoch=baris["mulai_epoch"], batas_epoch=baris["batas_epoch"],
                       selesai_epoch=baris["selesai_epoch"])


def _finalkan_habis(kon, siswa_id: int, sekarang: int) -> None:
    """Tutup sesi berjalan milik anak yang batasnya sudah lewat; selesai = batas, bukan saat dibuka."""
    kon.execute(
        "UPDATE lomba_sesi SET status = 'waktu_habis', selesai_epoch = batas_epoch "
        "WHERE siswa_id = ? AND status = 'berjalan' AND ? >= batas_epoch", (siswa_id, sekarang))


def _berjalan(kon, siswa_id: int) -> Optional[SesiRingkas]:
    baris = kon.execute(f"SELECT {_KOLOM_SESI} FROM lomba_sesi WHERE siswa_id = ? AND status = 'berjalan'",
                        (siswa_id,)).fetchone()
    return _ringkas(baris) if baris else None


def tutup_yang_habis(kon, siswa_id: int, sekarang: int) -> None:
    """Tutup sesi berjalan milik anak yang batasnya sudah lewat (untuk pembaca riwayat)."""
    _finalkan_habis(kon, siswa_id, sekarang)


def sesi_berjalan(kon, siswa_id: int, sekarang: int) -> Optional[SesiRingkas]:
    _finalkan_habis(kon, siswa_id, sekarang)
    return _berjalan(kon, siswa_id)


def ambil_sesi(kon, siswa_id: int, sesi_id: int, sekarang: int) -> SesiRingkas:
    _finalkan_habis(kon, siswa_id, sekarang)
    baris = kon.execute(f"SELECT {_KOLOM_SESI} FROM lomba_sesi WHERE id = ? AND siswa_id = ?",
                        (sesi_id, siswa_id)).fetchone()
    if baris is None:
        raise SesiTidakDitemukan(sesi_id)
    return _ringkas(baris)


def _pastikan_milik(kon, siswa_id: int, sesi_id: int) -> None:
    ada = kon.execute("SELECT 1 FROM lomba_sesi WHERE id = ? AND siswa_id = ?", (sesi_id, siswa_id)).fetchone()
    if ada is None:
        raise SesiTidakDitemukan(sesi_id)


def _riwayat(kon, siswa_id: int) -> Tuple[FrozenSet[str], FrozenSet[str]]:
    """(tanda tangan soal 5 sesi terakhir, id template 2 sesi terakhir) milik anak ini."""
    ids = [baris[0] for baris in kon.execute(
        "SELECT id FROM lomba_sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT ?", (siswa_id, S.RIWAYAT_SESI))]

    def kolom(nama: str, sesi_ids: Sequence[int]) -> FrozenSet[str]:
        if not sesi_ids:
            return frozenset()
        penampung = ",".join("?" * len(sesi_ids))
        return frozenset(baris[0] for baris in kon.execute(
            f"SELECT {nama} FROM lomba_soal WHERE sesi_id IN ({penampung})", tuple(sesi_ids)))

    return kolom("tanda_tangan", ids), kolom("template_id", ids[:S.ROTASI_SESI])


def _baris_soal(sesi_id: int, butir: S.ButirSesi) -> tuple:
    soal = butir.soal
    pengecoh = [{"nilai": p.nilai, "kesalahan": p.kesalahan, "svg": p.svg} for p in soal.pengecoh]
    return (sesi_id, butir.nomor, soal.template_id, soal.topik, soal.jenis, soal.tingkat,
            C.tanda_tangan(soal), soal.parameter, int(soal.inggris), soal.teks, soal.svg, soal.kunci,
            json.dumps(list(butir.pilihan), ensure_ascii=False),
            json.dumps(list(butir.gambar_pilihan), ensure_ascii=False), butir.posisi_kunci,
            json.dumps(pengecoh, ensure_ascii=False), json.dumps(list(soal.pembahasan), ensure_ascii=False))


def _simpan_soal(kon, sesi_id: int, sesi: S.Sesi) -> None:
    kon.executemany(
        "INSERT INTO lomba_soal(sesi_id, nomor, template_id, topik, jenis, tingkat, tanda_tangan, parameter, "
        "inggris, teks, svg, kunci, pilihan_json, gambar_pilihan_json, posisi_kunci, pengecoh_json, "
        "pembahasan_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [_baris_soal(sesi_id, butir) for butir in sesi.butir])


def _simpan_sesi_baru(kon, siswa_id: int, sekarang: int, seed: int, sesi: S.Sesi) -> SesiRingkas:
    """Sesi dan sepuluh soalnya masuk atau batal bersama; yang kalah balapan melanjutkan pemenang."""
    kon.execute(f"SAVEPOINT {_SAVEPOINT}")
    try:
        kursor = kon.execute(
            "INSERT INTO lomba_sesi(siswa_id, paket_id, seed, mulai_epoch, batas_epoch, status) "
            "VALUES (?, ?, ?, ?, ?, 'berjalan')",
            (siswa_id, PAKET_ID, seed, sekarang, sekarang + DURASI_DETIK))
    except sqlite3.IntegrityError:
        kon.execute(f"ROLLBACK TO {_SAVEPOINT}")
        kon.execute(f"RELEASE {_SAVEPOINT}")
        pemenang = _berjalan(kon, siswa_id)
        if pemenang is None:
            raise
        return pemenang
    try:
        _simpan_soal(kon, kursor.lastrowid, sesi)
    except Exception:
        kon.execute(f"ROLLBACK TO {_SAVEPOINT}")
        kon.execute(f"RELEASE {_SAVEPOINT}")
        raise
    kon.execute(f"RELEASE {_SAVEPOINT}")
    return SesiRingkas(id=kursor.lastrowid, siswa_id=siswa_id, status=BERJALAN, mulai_epoch=sekarang,
                       batas_epoch=sekarang + DURASI_DETIK, selesai_epoch=None)


def mulai_atau_lanjut(kon, siswa_id: int, sekarang: int, *, seed: Optional[int] = None,
                      pool: Optional[Sequence[C.Template]] = None) -> SesiRingkas:
    """Lanjutkan sesi yang masih berjalan, atau rakit sesi baru (soal baru, rotasi jenis, tanpa ulang)."""
    _finalkan_habis(kon, siswa_id, sekarang)
    ada = _berjalan(kon, siswa_id)
    if ada is not None:
        return ada
    seed = secrets.randbits(SEED_BIT) if seed is None else seed
    katalog = contest_templates.katalog() if pool is None else pool
    terlarang, dihindari = _riwayat(kon, siswa_id)
    sesi = S.rakit_sesi(seed, katalog, terlarang, template_dihindari=dihindari)
    return _simpan_sesi_baru(kon, siswa_id, sekarang, seed, sesi)


def soal_untuk_anak(kon, siswa_id: int, sesi_id: int, nomor: int) -> SoalAnak:
    """Soal yang boleh dilihat anak: hanya kolom aman (tanpa kunci, pembahasan, atau label pengecoh)."""
    baris = kon.execute(
        "SELECT s.nomor, s.jenis, s.topik, s.teks, s.svg, s.pilihan_json, s.gambar_pilihan_json, j.jawaban "
        "FROM lomba_soal s JOIN lomba_sesi x ON x.id = s.sesi_id "
        "LEFT JOIN lomba_jawaban j ON j.sesi_id = s.sesi_id AND j.nomor = s.nomor "
        "WHERE s.sesi_id = ? AND s.nomor = ? AND x.siswa_id = ?", (sesi_id, nomor, siswa_id)).fetchone()
    if baris is None:
        raise SesiTidakDitemukan((sesi_id, nomor))
    return SoalAnak(nomor=baris["nomor"], jenis=baris["jenis"], topik=baris["topik"], teks=baris["teks"],
                    svg=baris["svg"], pilihan=tuple(json.loads(baris["pilihan_json"])),
                    gambar_pilihan=tuple(json.loads(baris["gambar_pilihan_json"])),
                    jawaban=baris["jawaban"])


def nomor_terjawab(kon, siswa_id: int, sesi_id: int) -> FrozenSet[int]:
    _pastikan_milik(kon, siswa_id, sesi_id)
    return frozenset(baris[0] for baris in kon.execute(
        "SELECT nomor FROM lomba_jawaban WHERE sesi_id = ?", (sesi_id,)))


def _jenis_soal(kon, siswa_id: int, sesi_id: int, nomor: int) -> str:
    baris = kon.execute(
        "SELECT s.jenis FROM lomba_soal s JOIN lomba_sesi x ON x.id = s.sesi_id "
        "WHERE s.sesi_id = ? AND s.nomor = ? AND x.siswa_id = ?", (sesi_id, nomor, siswa_id)).fetchone()
    if baris is None:
        raise SesiTidakDitemukan((sesi_id, nomor))
    return baris["jenis"]


def _normalkan_jawaban(jenis: str, jawaban: str) -> Optional[str]:
    """Jawaban baku untuk disimpan; None berarti "hapus jawaban"."""
    if not isinstance(jawaban, str):
        raise JawabanTidakSah("jawaban wajib teks")
    bersih = jawaban.strip()
    if not bersih:
        return None
    if jenis == C.JENIS_PG:
        huruf = bersih.upper()
        if huruf in C.HURUF:
            return huruf
    elif _POLA_ISIAN.match(bersih):
        return str(int(bersih))
    raise JawabanTidakSah(f"jawaban tidak sah untuk soal {jenis}")


def simpan_jawaban(kon, siswa_id: int, sesi_id: int, nomor: int, jawaban: str, sekarang: int) -> None:
    """Simpan (atau hapus bila kosong) jawaban; satu pernyataan atomik yang menegakkan batas waktu."""
    jenis = _jenis_soal(kon, siswa_id, sesi_id, nomor)
    nilai = _normalkan_jawaban(jenis, jawaban)
    if nilai is None:
        kursor = kon.execute(
            f"DELETE FROM lomba_jawaban WHERE sesi_id = ? AND nomor = ? AND {_SYARAT_BERJALAN}",
            (sesi_id, nomor, sesi_id, siswa_id, sekarang))
    else:
        kursor = kon.execute(
            "INSERT INTO lomba_jawaban(sesi_id, nomor, jawaban, diubah_epoch) "
            f"SELECT ?, ?, ?, ? WHERE {_SYARAT_BERJALAN} "
            "ON CONFLICT(sesi_id, nomor) DO UPDATE SET jawaban = excluded.jawaban, "
            "diubah_epoch = excluded.diubah_epoch",
            (sesi_id, nomor, nilai, sekarang, sesi_id, siswa_id, sekarang))
    if kursor.rowcount == 0 and ambil_sesi(kon, siswa_id, sesi_id, sekarang).status != BERJALAN:
        raise SesiSelesai(sesi_id)


def kumpulkan(kon, siswa_id: int, sesi_id: int, sekarang: int) -> SesiRingkas:
    """Akhiri sesi lebih awal; idempoten. Kumpul setelah batas dicatat sebagai waktu habis pada batas."""
    _pastikan_milik(kon, siswa_id, sesi_id)
    kon.execute(
        "UPDATE lomba_sesi SET status = CASE WHEN ? >= batas_epoch THEN 'waktu_habis' ELSE 'dikumpul' END, "
        "selesai_epoch = MAX(mulai_epoch, MIN(?, batas_epoch)) "
        "WHERE id = ? AND siswa_id = ? AND status = 'berjalan'", (sekarang, sekarang, sesi_id, siswa_id))
    return ambil_sesi(kon, siswa_id, sesi_id, sekarang)


def benar(jenis: str, kunci: str, pilihan: Sequence[str], jawaban: Optional[str]) -> bool:
    if jawaban is None:
        return False
    if jenis == C.JENIS_ISIAN:
        return C.jawaban_benar(kunci, jawaban, C.JENIS_ISIAN)
    return jawaban in C.HURUF and C.jawaban_benar(kunci, pilihan[C.HURUF.index(jawaban)], C.JENIS_PG)


def hasil_ringkas(kon, siswa_id: int, sesi_id: int, sekarang: int) -> HasilRingkas:
    """Nilai total dan waktu terpakai; hanya setelah sesi tidak lagi berjalan (kunci dibaca di sini)."""
    sesi = ambil_sesi(kon, siswa_id, sesi_id, sekarang)
    if sesi.status == BERJALAN:
        raise SesiBerjalan(sesi_id)
    baris = kon.execute(
        "SELECT s.jenis, s.kunci, s.pilihan_json, j.jawaban FROM lomba_soal s "
        "LEFT JOIN lomba_jawaban j ON j.sesi_id = s.sesi_id AND j.nomor = s.nomor "
        "WHERE s.sesi_id = ? ORDER BY s.nomor", (sesi_id,)).fetchall()
    nilai = sum(1 for r in baris if benar(r["jenis"], r["kunci"], json.loads(r["pilihan_json"]), r["jawaban"]))
    return HasilRingkas(nilai=nilai, jumlah_soal=len(baris),
                        waktu_terpakai_detik=sesi.selesai_epoch - sesi.mulai_epoch, status=sesi.status)
