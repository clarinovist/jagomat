"""Koordinator admission dan pencatatan panggilan AI lintas fitur."""

from __future__ import annotations

import os
from pathlib import Path
import secrets
import time
import sqlite3
from contextlib import closing, contextmanager, nullcontext

import ai_errors
import ai_policy
import ai_store


class AIUnavailable(RuntimeError):
    """Panggilan ditahan tanpa membocorkan konfigurasi internal."""

    def __init__(self, pesan, *, kategori="ai_tertahan"):
        super().__init__(pesan)
        self.kategori = kategori


def path_store():
    return Path(os.environ.get("AI_BERKAS_DB", str(ai_store.BAWAAN)))


def kategori_gagal_pendamping(account_id, request_id):
    """Baca kategori tertutup untuk request pemilik; tidak membuat storage.

    Pemanggil tetap memeriksa chat, resource, dan consent sebelum fungsi ini.
    Metadata hilang/rusak tidak boleh menghalangi halaman belajar.
    """
    tujuan = path_store()
    if not account_id or not request_id:
        return ""
    try:
        if not tujuan.is_file():
            return ""
        with closing(sqlite3.connect(tujuan.resolve().as_uri() + "?mode=ro", uri=True)) as kon:
            kon.execute("PRAGMA query_only=ON")
            baris = kon.execute(
                """SELECT kategori FROM ledger
                   WHERE operasi_id=? AND bucket_akun=? AND fitur='pendamping'
                     AND status IN ('tak_pasti','gagal')""",
                ("pendamping:" + request_id, account_id),
            ).fetchone()
            kategori = baris[0] if baris else None
            return kategori if kategori in ai_errors.KATEGORI else ""
    except (OSError, sqlite3.Error):
        return ""


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
        raise AIUnavailable("Fitur AI sedang tidak tersedia.", kategori="ai_nonaktif")
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        raise AIUnavailable("Fitur AI sedang tidak tersedia.", kategori="ai_konfigurasi")
    if not siap():
        raise AIUnavailable("Penyimpanan pengendali AI belum siap.", kategori="ai_storage")
    oid = operasi_id or ("ai_" + secrets.token_hex(16))
    try:
        with _kunci_actor(actor_id, actor_revisi) if actor_revisi is not None else nullcontext():
            reservasi = ai_store.reservasi(
                path_store(), oid, fitur, bucket_akun, profil.model,
                profil.reservasi_micro_usd, actor_id=actor_id,
            )
    except PermissionError:
        raise
    except ai_store.Ditolak as galat:
        # Pesan store berasal dari konstanta lokal; hanya kategori tertutup diteruskan.
        kategori = {
            "Fitur AI sedang dihentikan.": "ai_nonaktif",
            "Kuota AI harian habis.": "ai_kuota",
            "Kuota AI bulanan habis.": "ai_kuota",
            "Kuota fitur AI habis.": "ai_kuota",
            "Batas request harian akun tercapai.": "ai_kuota",
        }.get(str(galat), "ai_tertahan")
        raise AIUnavailable('Panggilan AI ditahan atau storage tidak tersedia.', kategori=kategori) from galat
    except (OSError, sqlite3.Error) as galat:
        raise AIUnavailable('Panggilan AI ditahan atau storage tidak tersedia.', kategori="ai_storage") from galat
    mulai = time.monotonic()
    try:
        hasil = pemanggil()
    except Exception as galat:
        ai_store.selesaikan(
            path_store(), oid, status="tak_pasti",
            durasi_ms=int((time.monotonic() - mulai) * 1000),
            kategori=ai_errors.kategori_aman(galat) if fitur == "pendamping" else "network_atau_provider",
        )
        raise
    ai_store.selesaikan(
        path_store(), oid, status="selesai", biaya=reservasi.reservation,
        durasi_ms=int((time.monotonic() - mulai) * 1000), kategori="terukur_konservatif",
    )
    if not ai_store.admission_masih_sah(path_store(), oid):
        raise AIUnavailable("Pengaturan AI berubah saat permintaan berjalan; hasil dibuang.", kategori="ai_pengaturan_berubah")
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
