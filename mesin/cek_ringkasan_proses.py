"""Pembaca PROSES cek untuk snapshot laporan Peta versi 2 (F3): nomor soal, ada/tidaknya jawaban, benar, dan waktu.

Pembaca MURNI SELECT pada koneksi pemanggil (DB belajar), dipakai jalur otomatis `peta_otomatis`. Kunci baris sama
dengan `cek_ringkasan_admin`: id cek, id siswa, dan id akun dari sisi server; tidak cocok atau sesi hilang -> None.

Keluaran hanya `KUNCI_PROSES`:
- `soal`: urut nomor; `dijawab` = ada baris jawaban; `benar` = diagnosis.benar, None bila belum dinilai.
- `durasi_detik`: sesi.selesai - sesi.mulai; None bila kosong, tak terbaca, atau negatif (tanpa perkiraan).
Tanpa teks soal, penyajian, kunci, jawaban, alasan, kode diagnosis, dan id soal/sesi.
"""
from __future__ import annotations

from typing import Optional

from cek_gratis_skor import periksa_id_akun, waktu_baku

KUNCI_PROSES = ("soal", "durasi_detik")
KUNCI_SOAL = ("nomor", "dijawab", "benar")

# Kunci baris sama dengan `cek_ringkasan_admin._SQL_CEK`; hanya kolom yang dibutuhkan.
_SQL_CEK = """SELECT sesi_id
    FROM cek_gratis
    WHERE id = :cek_id
      AND siswa_id = :siswa_id
      AND id_akun = :id_akun"""
_SQL_WAKTU = "SELECT mulai, selesai FROM sesi WHERE id = :sesi_id"
# Hanya nomor, penanda jawaban, dan nilai benar; urut nomor = urut penyajian.
_SQL_SOAL = """SELECT ss.nomor AS nomor, (j.id IS NOT NULL) AS dijawab, d.benar AS benar
    FROM sesi_soal ss
    LEFT JOIN jawaban j ON j.sesi_soal_id = ss.id
    LEFT JOIN diagnosis d ON d.jawaban_id = j.id
    WHERE ss.sesi_id = :sesi_id
    ORDER BY ss.nomor"""


def _id_sah(nilai) -> bool:
    return type(nilai) is int and nilai >= 1


def _durasi_detik(mulai, selesai) -> Optional[int]:
    """Selisih `selesai - mulai` dalam detik; None bila salah satu kosong, tak terbaca, atau negatif."""
    if mulai is None or selesai is None:
        return None
    try:
        detik = int((waktu_baku(selesai) - waktu_baku(mulai)).total_seconds())
    except ValueError:
        return None
    return detik if detik >= 0 else None


def _soal(kon, sesi_id: int) -> list:
    return [{"nomor": b["nomor"], "dijawab": bool(b["dijawab"]), "benar": b["benar"]}
            for b in kon.execute(_SQL_SOAL, {"sesi_id": sesi_id}).fetchall()]


def proses_untuk_order(kon, siswa_id, cek_id, id_akun) -> Optional[dict]:
    """Proses satu cek untuk snapshot v2, atau None bila tiga kunci tidak cocok, id tak sah, atau sesi hilang.

    `id_akun` tak sah = ValueError. Hanya SELECT; tidak commit dan tidak menulis.
    """
    periksa_id_akun(id_akun)
    if not (_id_sah(siswa_id) and _id_sah(cek_id)):
        return None
    baris = kon.execute(
        _SQL_CEK, {"cek_id": cek_id, "siswa_id": siswa_id, "id_akun": id_akun}).fetchone()
    if baris is None or baris["sesi_id"] is None:
        return None
    waktu = kon.execute(_SQL_WAKTU, {"sesi_id": baris["sesi_id"]}).fetchone()
    if waktu is None:
        return None
    return {"soal": _soal(kon, baris["sesi_id"]),
            "durasi_detik": _durasi_detik(waktu["mulai"], waktu["selesai"])}
