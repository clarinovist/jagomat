"""Koordinator admission dan pencatatan panggilan AI lintas fitur."""

from __future__ import annotations

import os
from pathlib import Path
import secrets
import time
import sqlite3
from contextlib import contextmanager, nullcontext

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
    except (OSError, RuntimeError, sqlite3.Error):
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
        except (OSError, RuntimeError, sqlite3.Error):
            alasan.append("storage bermasalah")
    return not alasan, alasan


def panggil(fitur, bucket_akun, pemanggil, *, operasi_id=None, actor_id=None, actor_revisi=None):
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
        with _kunci_actor(actor_id, actor_revisi) if actor_revisi is not None else nullcontext():
            reservasi = ai_store.reservasi(
                path_store(), oid, fitur, bucket_akun, profil.model,
                profil.reservasi_micro_usd, actor_id=actor_id,
            )
    except PermissionError:
        raise
    except (ai_store.Ditolak, OSError, sqlite3.Error) as galat:
        raise AIUnavailable('Panggilan AI ditahan atau storage tidak tersedia.') from galat
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
    if actor_revisi is not None:
        with _kunci_actor(actor_id, actor_revisi):
            pass
    return hasil


@contextmanager
def _kunci_actor(actor_id, actor_revisi):
    """Revalidasi admin pada auth lock; caller tidak menahan lock saat jaringan."""
    import auth
    from json_storage import transaksi_json

    if type(actor_revisi) is not int or actor_revisi < 0:
        raise PermissionError('Identitas pengelola berubah.')
    with transaksi_json(auth.BERKAS_SANDI) as path:
        _mentah, akun, _multi = auth._baca_akun_untuk_tulis(path)
        actor = next((a for a in akun if a.get('id_akun') == actor_id), None)
        if (actor is None or actor.get('peran') != 'admin'
                or auth.revisi_auth(actor) != actor_revisi):
            raise PermissionError('Identitas pengelola berubah.')
        yield


def ubah_pengaturan_admin(nilai, *, actor_id, actor_revisi, operasi_id, revisi):
    """Konfigurasi+audit+receipt satu transaksi, dengan principal masih sah."""
    if not siap():
        raise AIUnavailable('Penyimpanan pengendali AI belum siap.')
    with _kunci_actor(actor_id, actor_revisi):
        return ai_store.ubah(path_store(), nilai, actor_id, revisi=revisi,
                             operasi_id=operasi_id)


def panggil_uji_admin(pemanggil, *, actor_id, actor_revisi, operasi_id):
    """Admission tes sintetis atomik terhadap revisi actor; replay tidak outbound."""
    return panggil('uji_sintetis', None, pemanggil, operasi_id=operasi_id,
                   actor_id=actor_id, actor_revisi=actor_revisi)


def riwayat_admin(**filter_data):
    import ai_admin_operations
    return ai_admin_operations.riwayat_operasi(path_store(), **filter_data)
