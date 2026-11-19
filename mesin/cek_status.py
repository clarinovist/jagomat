"""Status cek gratis untuk halaman "siap mulai" orang tua (funnel Fase 3).

Satu pembaca: anak milik akun sesi, status cek, dan jumlah soal yang sudah
dijawab di sesi cek. Orang tua boleh melihat jumlah jawaban terisi (tanpa
benar/salah), jadi hanya hitungan, tidak pernah isi jawaban atau kunci.

"Terjawab" = soal sesi cek yang punya baris jawaban dengan isian `jawaban`
tidak kosong. Soal yang dilewati tanpa memilih tidak dihitung.
Semua kunci dari principal sesi server (`id_akun`, `pengguna`), bukan dari klien.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cek_gratis

STATUS_BELUM_MULAI = "belum_mulai"
STATUS_BERJALAN = "belum_selesai"
STATUS_SELESAI = "selesai"


@dataclass(frozen=True)
class StatusCek:
    """Gambaran satu cek untuk orang tua; tidak memuat skor, kunci, atau jawaban."""
    nama_anak: str
    kelas: Optional[int]
    status: str
    terjawab: int
    jumlah_soal: int


def kelas_anak(kon, siswa_id: int):
    """Kelas sekolah (int 1-6) anak ini dari profil belajar, atau None bila belum diisi."""
    baris = kon.execute(
        "SELECT kelas_sekolah FROM profil_belajar WHERE siswa_id = ?", (siswa_id,)
    ).fetchone()
    return None if baris is None else baris["kelas_sekolah"]


def _terjawab(kon, sesi_id) -> int:
    if sesi_id is None:
        return 0
    return kon.execute(
        """SELECT COUNT(*) FROM sesi_soal ss
           JOIN jawaban j ON j.sesi_soal_id = ss.id
           WHERE ss.sesi_id = ? AND TRIM(IFNULL(j.jawaban, '')) <> ''""",
        (sesi_id,),
    ).fetchone()[0]


def _sesi_dikumpulkan(kon, sesi_id) -> bool:
    if sesi_id is None:
        return False
    baris = kon.execute("SELECT selesai FROM sesi WHERE id = ?", (sesi_id,)).fetchone()
    return baris is not None and baris["selesai"] is not None


def _cek_terbaru(kon, id_akun: str):
    return kon.execute(
        """SELECT c.siswa_id, c.sesi_id, c.jumlah_soal, w.nama FROM cek_gratis c
           JOIN siswa w ON w.id = c.siswa_id
           WHERE c.id_akun = ? ORDER BY c.id DESC LIMIT 1""",
        (id_akun,),
    ).fetchone()


def _anak_pertama(kon, pengguna: str):
    return kon.execute(
        "SELECT id, nama FROM siswa WHERE pemilik = ? ORDER BY id LIMIT 1", (pengguna,)
    ).fetchone()


def baca_status(kon, id_akun: str, pengguna: str) -> Optional[StatusCek]:
    """Status cek akun ini, atau None bila akun belum punya anak. Hanya membaca.

    Cek yang sesinya sudah dikumpulkan anak tetapi belum dinilai dianggap
    `selesai` (halaman hasil yang menilai), supaya tidak tampil sebagai
    "berjalan 15 dari 15" dan GET halaman siap mulai tidak menulis DB.
    """
    hasil = cek_gratis.baca_hasil(kon, id_akun)
    baris = _cek_terbaru(kon, id_akun)
    if baris is not None:
        terjawab = _terjawab(kon, baris["sesi_id"])
        status = hasil["status"]
        if status == STATUS_BERJALAN and _sesi_dikumpulkan(kon, baris["sesi_id"]):
            status = STATUS_SELESAI
        return StatusCek(baris["nama"], kelas_anak(kon, baris["siswa_id"]), status,
                         terjawab, baris["jumlah_soal"])
    anak = _anak_pertama(kon, pengguna)
    if anak is None:
        return None
    return StatusCek(anak["nama"], kelas_anak(kon, anak["id"]), STATUS_BELUM_MULAI, 0,
                     hasil["jumlah_soal"])
