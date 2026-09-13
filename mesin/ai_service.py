"""Koordinator admission dan pencatatan panggilan AI lintas fitur."""

from __future__ import annotations

import os
from pathlib import Path
import secrets
import time

import ai_policy
import ai_store


class AIUnavailable(RuntimeError):
    """Panggilan ditahan tanpa membocorkan konfigurasi internal."""


def path_store():
    return Path(os.environ.get("AI_BERKAS_DB", str(ai_store.BAWAAN)))


def siap() -> bool:
    tujuan = path_store()
    if not tujuan.is_file():
        return False
    try:
        with ai_store.buka(tujuan) as kon:
            ai_store.konfigurasi(kon)
        return True
    except (OSError, RuntimeError):
        return False


def status_fitur(fitur):
    alasan = []
    if not ai_policy.deployment_mengizinkan(fitur):
        alasan.append("diblokir server")
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        alasan.append("key belum tersedia")
    if not siap():
        alasan.append("storage belum siap")
    if siap():
        try:
            with ai_store.buka(path_store()) as kon:
                utama, batas = ai_store.konfigurasi(kon)
                if utama["dihentikan"]:
                    alasan.append("dihentikan")
                if not batas[fitur]["aktif"]:
                    alasan.append("fitur dinonaktifkan")
        except (OSError, RuntimeError):
            alasan.append("storage bermasalah")
    return not alasan, alasan


def panggil(fitur, bucket_akun, pemanggil, *, operasi_id=None):
    """Reservasi sebelum network dan pertahankan debit konservatif saat tak pasti."""
    profil = ai_policy.profil(fitur)
    if not ai_policy.deployment_mengizinkan(fitur):
        raise AIUnavailable("Fitur AI sedang tidak tersedia.")
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        raise AIUnavailable("Fitur AI sedang tidak tersedia.")
    if not siap():
        raise AIUnavailable("Penyimpanan pengendali AI belum siap.")
    oid = operasi_id or ("ai_" + secrets.token_hex(16))
    try:
        reservasi = ai_store.reservasi(
            path_store(), oid, fitur, bucket_akun, profil.model,
            profil.reservasi_micro_usd,
        )
    except (ai_store.Ditolak, OSError) as galat:
        raise AIUnavailable(str(galat)) from galat
    mulai = time.monotonic()
    try:
        hasil = pemanggil()
    except Exception:
        ai_store.selesaikan(
            path_store(), oid, status="tak_pasti",
            durasi_ms=int((time.monotonic() - mulai) * 1000),
            kategori="network_atau_provider",
        )
        raise
    ai_store.selesaikan(
        path_store(), oid, status="selesai", biaya=reservasi.reservation,
        durasi_ms=int((time.monotonic() - mulai) * 1000), kategori="terukur_konservatif",
    )
    if not ai_store.admission_masih_sah(path_store(), oid):
        raise AIUnavailable("Pengaturan AI berubah saat permintaan berjalan; hasil dibuang.")
    return hasil
