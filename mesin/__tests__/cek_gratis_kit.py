"""Pembantu bersama tes cek gratis: data sintetis di basis sementara."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis  # noqa: E402
import database  # noqa: E402
import learning_profile  # noqa: E402

ID_A = "akun_" + "a1" * 16
ID_B = "akun_" + "b2" * 16
ID_C = "akun_" + "c3" * 16
SEKARANG = "2026-11-18T10:00:00"
SELESAI_SESI = "2026-11-18 09:00:00"
TABEL_BUKTI_SIKLUS = (
    "putaran_fokus", "anggota_fokus", "bukti_fokus", "konfirmasi_hasil",
    "snapshot_outcome", "kejadian_belajar",
)


def tambah_anak(kon, nama: str, pemilik: str, kelas, tingkat: str = "P3") -> int:
    siswa_id = database.tambah_siswa(kon, nama, tingkat, pemilik=pemilik)
    if kelas is not None:
        learning_profile.simpan_kelas(kon, siswa_id, kelas, revisi=0, pemilik=pemilik)
    return siswa_id


def mulai_cek(kon, id_akun, siswa_id, pemilik, *, seed=7) -> int:
    return cek_gratis.mulai(kon, id_akun, siswa_id, pemilik, True, SEKARANG, seed=seed)["sesi_id"]


def hitung(kon, tabel: str) -> int:
    return kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]


def jawab(kon, sesi_id: int, benar_per_topik=None, *, semua_benar: int = 0) -> None:
    """Isi jawaban PG sintetis: `benar_per_topik` {topik_id: n} atau `semua_benar` n soal pertama.

    Soal yang tidak dibenarkan dijawab kosong (pilihan belum dipilih), bukan dibiarkan
    tanpa baris, supaya jalur "jawaban kosong = salah" ikut teruji.
    """
    peta = cek_gratis._peta_template_ke_topik()
    sisa = dict(benar_per_topik or {})
    for nomor, baris in enumerate(database.isi_sesi(kon, sesi_id)):
        topik_id = peta[baris["template_id"]]
        if benar_per_topik is not None:
            benar = sisa.get(topik_id, 0) > 0
            sisa[topik_id] = sisa.get(topik_id, 0) - 1
        else:
            benar = nomor < semua_benar
        database.simpan_jawaban(kon, baris["sesi_soal_id"], jawaban=baris["kunci"] if benar else "")


def tandai_selesai(kon, sesi_id: int, waktu: str = SELESAI_SESI) -> None:
    kon.execute("UPDATE sesi SET selesai = ? WHERE id = ?", (waktu, sesi_id))
