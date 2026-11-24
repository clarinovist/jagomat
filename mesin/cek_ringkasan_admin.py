"""Ringkasan cek kemampuan untuk admin (irisan D1): bahan menulis laporan Peta Kemampuan dalam janji 48 jam.

Pembaca MURNI SELECT (tanpa tulis, tanpa menilai ulang): admin melihat skor, kategori, ringkasan, dan hitungan
benar/total per materi untuk SATU order lunas, plus kapan data per materi hilang oleh retensi. Bukan laporan
orang tua, bukan tampilan Guru, bukan renderer Peta.

Hasil allowlist (`KUNCI_HASIL`): tanpa nama anak, kontak, teks soal, jawaban, kunci, kode diagnosis/malrule/alasan,
atau id sesi/soal. Baris cek dicocokkan lewat TIGA kunci sekaligus (id cek, id siswa, id akun), semuanya dari
baris pesanan di server, bukan input pengguna; tidak cocok -> None.

Per materi dihitung dari (template_id, benar) sesi cek itu saja, dipetakan ke topik lewat
`cek_gratis._peta_template_ke_topik` dan diberi nama awam. Soal tak dijawab atau `benar` NULL dihitung salah,
konsisten dengan `cek_gratis._hitung_dari_sesi`. Jawaban tanpa baris diagnosis berarti BELUM DINILAI: tidak
ditebak dan tidak dinilai di sini (itu pekerjaan `selesaikan_jika_siap`).

Retensi: sapuan menghapus bahan bila `selesai_pada < sekarang - RETENSI_SELESAI_HARI` (perbandingan ketat);
`hari_tersisa` memakai jam dan batas yang sama, dibulatkan ke bawah (tidak pernah melebihkan) dan tidak negatif.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Optional

import topik_awam
from cek_gratis import _peta_template_ke_topik, _urai_ringkasan
from cek_gratis_skor import RETENSI_SELESAI_HARI, periksa_id_akun, waktu_baku

STATUS_BELUM_SELESAI = "belum_selesai"
STATUS_SELESAI = "selesai"
BAHAN_ADA = "ada"
BAHAN_DIHAPUS = "dihapus"
BAHAN_BELUM_DINILAI = "belum_dinilai"
KUNCI_HASIL = (
    "status", "kelas", "skor", "kategori", "jumlah_soal", "selesai_pada", "ringkasan_kuat",
    "ringkasan_perlu", "per_materi", "bahan", "hari_tersisa",
)

_SQL_CEK = """SELECT sesi_id, selesai_pada, skor, kategori, ringkasan, jumlah_soal
    FROM cek_gratis
    WHERE id = :cek_id
      AND siswa_id = :siswa_id
      AND id_akun = :id_akun"""
_SQL_KELAS = "SELECT kelas_sekolah FROM profil_belajar WHERE siswa_id = :siswa_id"
# Hanya template_id, benar, dan penanda "ada jawaban"; tanpa teks soal, jawaban, kunci, atau kode diagnosis.
_SQL_PER_SOAL = """SELECT s.template_id AS template_id, d.benar AS benar, (j.id IS NOT NULL) AS dijawab
    FROM sesi_soal ss
    JOIN soal s ON s.id = ss.soal_id
    LEFT JOIN jawaban j ON j.sesi_soal_id = ss.id
    LEFT JOIN diagnosis d ON d.jawaban_id = j.id
    WHERE ss.sesi_id = :sesi_id
    ORDER BY ss.nomor"""


def _id_sah(nilai) -> bool:
    return type(nilai) is int and nilai >= 1


def _kelas(kon, siswa_id) -> Optional[int]:
    baris = kon.execute(_SQL_KELAS, {"siswa_id": siswa_id}).fetchone()
    return None if baris is None else baris["kelas_sekolah"]


def _hari_tersisa(selesai_pada: str, sekarang: str) -> int:
    """Hari sampai bahan dihapus sapuan; floor dan tidak negatif (bahan yang belum disapu tetap 0)."""
    kedaluwarsa = waktu_baku(selesai_pada) + timedelta(days=RETENSI_SELESAI_HARI)
    return max(0, (kedaluwarsa - waktu_baku(sekarang)).days)


def _per_materi(kon, sesi_id: int):
    """(per_materi, dinilai): hitungan benar/total per topik cek; dinilai False bila ada jawaban tanpa diagnosis."""
    baris = kon.execute(_SQL_PER_SOAL, {"sesi_id": sesi_id}).fetchall()
    if not baris or any(b["dijawab"] and b["benar"] is None for b in baris):
        return [], False
    peta = _peta_template_ke_topik()
    hitung = {}
    for b in baris:
        topik_id = peta.get(b["template_id"])
        if topik_id is None:
            continue
        benar, total = hitung.get(topik_id, (0, 0))
        hitung[topik_id] = (benar + (1 if b["benar"] else 0), total + 1)
    return [{"materi": topik_awam.nama(t), "benar": v[0], "total": v[1]}
            for t, v in sorted(hitung.items())], True


def _hasil(row, kelas, ringkasan, per_materi, bahan, hari) -> dict:
    return {
        "status": STATUS_BELUM_SELESAI if row["skor"] is None else STATUS_SELESAI,
        "kelas": kelas, "skor": row["skor"], "kategori": row["kategori"],
        "jumlah_soal": row["jumlah_soal"], "selesai_pada": row["selesai_pada"],
        "ringkasan_kuat": list(ringkasan["kuat"]), "ringkasan_perlu": list(ringkasan["perlu"]),
        "per_materi": per_materi, "bahan": bahan, "hari_tersisa": hari,
    }


def ringkasan_untuk_order(kon, siswa_id, cek_id, id_akun, sekarang) -> Optional[dict]:
    """Ringkasan allowlist satu cek untuk admin, atau None bila tiga kunci tidak cocok / id tidak sah.

    `id_akun` tak sah atau `sekarang` bukan waktu ISO = ValueError. Hanya SELECT pada koneksi pemanggil.
    """
    periksa_id_akun(id_akun)
    waktu_baku(sekarang)
    if not (_id_sah(siswa_id) and _id_sah(cek_id)):
        return None
    row = kon.execute(_SQL_CEK, {"cek_id": cek_id, "siswa_id": siswa_id, "id_akun": id_akun}).fetchone()
    if row is None:
        return None
    kelas = _kelas(kon, siswa_id)
    if row["skor"] is None:
        return _hasil(row, kelas, {"kuat": [], "perlu": []}, [], BAHAN_BELUM_DINILAI, None)
    ringkasan = _urai_ringkasan(row["ringkasan"])
    if row["sesi_id"] is None:
        return _hasil(row, kelas, ringkasan, [], BAHAN_DIHAPUS, None)
    per_materi, dinilai = _per_materi(kon, row["sesi_id"])
    hari = _hari_tersisa(row["selesai_pada"], sekarang)
    return _hasil(row, kelas, ringkasan, per_materi, BAHAN_ADA if dinilai else BAHAN_BELUM_DINILAI, hari)
