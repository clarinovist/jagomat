"""Pembaca PROSES cek untuk snapshot laporan Peta (versi 2 dan 3): nomor soal, jawaban, benar, waktu, dan perilaku.

Pembaca MURNI SELECT pada koneksi pemanggil (DB belajar), dipakai jalur otomatis `peta_otomatis`. Kunci baris sama
dengan `cek_ringkasan_admin`: id cek, id siswa, dan id akun dari sisi server; tidak cocok atau sesi hilang -> None.

Keluaran hanya `KUNCI_PROSES`:
- `soal`: urut nomor; tiap butir berkunci `KUNCI_SOAL`:
  - `dijawab` = ada baris jawaban; `benar` = diagnosis.benar, None bila belum dinilai;
  - `detik` = jawaban.detik, None bila kosong (cek lama) atau dilewati; selain bilangan 0..BATAS, ValueError;
  - `ganti` = jumlah jawaban diganti (tabel aditif `cek_ganti_jawaban`; 0 bila tak ada);
  - `materi` = nama topik awam dari template soal (pemetaan yang sama dengan ringkasan admin); None bila tak terpetakan.
- `durasi_detik`: sesi.selesai - sesi.mulai; None bila kosong, tak terbaca, atau negatif (tanpa perkiraan).
Tanpa teks soal, penyajian, kunci, jawaban, alasan, kode diagnosis, dan id soal/sesi (id sesi soal hanya dipakai
internal untuk mencocokkan `ganti`, tidak pernah keluar).
"""
from __future__ import annotations

from typing import Optional

import cek_gratis
import cek_perilaku
import cek_waktu_soal
import topik_awam
from cek_gratis_skor import periksa_id_akun, waktu_baku

KUNCI_PROSES = ("soal", "durasi_detik")
# Butir versi 2 (tanpa perilaku) dan butir versi 3 (lengkap). Pembangun menerima keduanya.
KUNCI_SOAL_DASAR = ("nomor", "dijawab", "benar")
KUNCI_SOAL = KUNCI_SOAL_DASAR + ("detik", "ganti", "materi")

# Kunci baris sama dengan `cek_ringkasan_admin._SQL_CEK`; hanya kolom yang dibutuhkan.
_SQL_CEK = """SELECT sesi_id
    FROM cek_gratis
    WHERE id = :cek_id
      AND siswa_id = :siswa_id
      AND id_akun = :id_akun"""
_SQL_WAKTU = "SELECT mulai, selesai FROM sesi WHERE id = :sesi_id"
# Nomor, penanda jawaban, nilai benar, detik, dan template (untuk materi). `id` hanya untuk mencocokkan `ganti`.
_SQL_SOAL = """SELECT ss.id AS id, ss.nomor AS nomor, (j.id IS NOT NULL) AS dijawab, d.benar AS benar,
        j.detik AS detik, s.template_id AS template_id
    FROM sesi_soal ss
    LEFT JOIN soal s ON s.id = ss.soal_id
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


def _detik_jawaban(nilai) -> Optional[int]:
    """Detik jawaban: None bila kosong; selain bilangan bulat 0..BATAS_DETIK_SOAL, ValueError (bentuk tak terduga)."""
    if nilai is None:
        return None
    if type(nilai) is not int or not 0 <= nilai <= cek_waktu_soal.BATAS_DETIK_SOAL:
        raise ValueError("detik soal tidak sah")
    return nilai


def _peta_materi() -> dict:
    """template_id -> nama topik awam, pemetaan yang sama dengan `cek_ringkasan_admin`; ValueError bila ambigu."""
    return {template: topik_awam.nama(topik) for template, topik in cek_gratis._peta_template_ke_topik().items()}


def _butir(baris, ganti: dict, materi: dict) -> dict:
    return {
        "nomor": baris["nomor"],
        "dijawab": bool(baris["dijawab"]),
        "benar": baris["benar"],
        "detik": _detik_jawaban(baris["detik"]),
        "ganti": ganti.get(baris["id"], 0),
        "materi": materi.get(baris["template_id"]),
    }


def _soal(kon, sesi_id: int) -> list:
    ganti = cek_perilaku.jumlah_ganti_per_sesi(kon, sesi_id)
    materi = _peta_materi()
    return [_butir(baris, ganti, materi)
            for baris in kon.execute(_SQL_SOAL, {"sesi_id": sesi_id}).fetchall()]


def proses_untuk_order(kon, siswa_id, cek_id, id_akun) -> Optional[dict]:
    """Proses satu cek untuk snapshot, atau None bila tiga kunci tidak cocok, id tak sah, atau sesi hilang.

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
