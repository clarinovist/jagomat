"""SQLite privat untuk konfigurasi, journal, dan audit pusat kendali admin.

Bootstrap hanya melalui :func:`siapkan`. Semua reader/mutator lain membuka file
existing dengan mode URI ``ro``/``rw`` agar GET atau kegagalan konfigurasi tidak
membuat database kosong diam-diam.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import time
from typing import Mapping, Optional, Tuple

from admin_batch_store import (
    BatchDurable, HalamanBatchDurable, ItemBatchDurable, KelompokBatchDurable,
    PenyerahanBatchDurable, RingkasanBatchDurable, SnapshotBatchDurable,
    batalkan_batch_aktif_durable, baca_batch_durable,
    baca_batch_operasional_durable, buat_batch_durable,
    buat_batch_durable_dengan_guard, catat_item_batch_durable,
    daftar_batch_durable, hentikan_batch_durable,
    hentikan_batch_durable_dengan_guard, konfirmasi_penyerahan_durable,
    konfirmasi_penyerahan_durable_dengan_guard, mulai_kelompok_durable,
    mulai_kelompok_durable_dengan_guard, selesaikan_kelompok_durable,
)
from admin_history_store import (
    EntriRiwayat,
    HalamanRiwayat,
    PerubahanRiwayat,
    daftar_riwayat as _daftar_riwayat_impl,
)
from admin_journal_store import (
    DataAuditTidakSah,
    KonflikOperasi,
    KonfigurasiPendaftaran,
    ReservasiOperasi,
    _baris_cocok_perintah,
    _hasil_dari_baris,
    _sidik_config,
    _tulis_audit,
    _validasi_nilai_audit,
    validasi_perubahan_audit,
)
from admin_store_core import (
    DDL as _DDL,
    KOLOM_WAJIB as _KOLOM_WAJIB,
    VERSI_SKEMA,
    StoreBelumSiap,
    jalankan_ddl as _jalankan_ddl,
    koneksi as _koneksi,
    uri as _uri,
    validasi_skema as _validasi_skema,
)

from admin_contracts import HasilOperasi, ReceiptAkun


BAWAAN = Path(os.environ.get("ADMIN_BERKAS_DB", "/data/admin-control.db"))



def _tujuan(path=None) -> Path:
    return Path(path) if path is not None else BAWAAN






@contextmanager
def buka_baca(path=None):
    """Buka readonly tanpa membuat file atau menjalankan migrasi."""
    kon = _koneksi(_tujuan(path), "ro")
    try:
        kon.execute("PRAGMA query_only=ON")
        _validasi_skema(kon)
        yield kon
    finally:
        kon.close()


@contextmanager
def _transaksi(path=None):
    kon = _koneksi(_tujuan(path), "rw")
    try:
        _validasi_skema(kon)
        kon.execute("BEGIN IMMEDIATE")
        yield kon
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()






def _migrasi_registry_aksi(
    kon: sqlite3.Connection, *, sumber_punya_hasil_id: bool, pertahankan_batch: bool = False
) -> None:
    """Rebuild CHECK registry sambil mempertahankan seluruh data lama."""
    ada_anchor = kon.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='receipt_admin'"
    ).fetchone() is not None
    tabel_batch = (
        "penyerahan_admin_item", "penyerahan_admin", "kelompok_admin_item",
        "kelompok_admin", "batch_admin_item", "batch_admin",
    )
    for tabel in (() if pertahankan_batch else tabel_batch):
        if kon.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabel,)
        ).fetchone():
            kon.execute('DROP TABLE "%s"' % tabel)
    _jalankan_ddl(
        kon,
        """
        ALTER TABLE audit_admin_perubahan RENAME TO audit_admin_perubahan_v1;
        ALTER TABLE audit_admin RENAME TO audit_admin_v1;
        ALTER TABLE operasi_admin RENAME TO operasi_admin_v1;
        DROP INDEX IF EXISTS idx_audit_admin_waktu;
        """,
    )
    if ada_anchor:
        kon.execute("ALTER TABLE receipt_admin RENAME TO receipt_admin_v1")
    _jalankan_ddl(kon, _DDL)
    kolom_hasil_id = "hasil_id" if sumber_punya_hasil_id else "NULL"
    kon.execute(
        """INSERT INTO operasi_admin(
               operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
               revisi_target,sidik_perintah,status,hasil_kode,revisi_hasil,
               hasil_id,credential_status,dibuat,diperbarui)
           SELECT operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
               revisi_target,sidik_perintah,status,hasil_kode,revisi_hasil,
               %s,credential_status,dibuat,diperbarui
           FROM operasi_admin_v1""" % kolom_hasil_id
    )
    kon.execute(
        """INSERT INTO audit_admin
           SELECT id,operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
                  status,hasil_kode,dibuat FROM audit_admin_v1"""
    )
    kon.execute(
        """INSERT INTO audit_admin_perubahan
           SELECT audit_id,field_kode,nilai_lama,nilai_baru
           FROM audit_admin_perubahan_v1"""
    )
    if ada_anchor:
        kon.execute(
            """INSERT INTO receipt_admin
               SELECT operasi_id,actor_id,aksi,jenis_target,target_id,
                      sidik_perintah,hasil_kode,dibuat FROM receipt_admin_v1"""
        )
        kon.execute("DROP TABLE receipt_admin_v1")
    kon.execute("DROP TABLE audit_admin_perubahan_v1")
    kon.execute("DROP TABLE audit_admin_v1")
    kon.execute("DROP TABLE operasi_admin_v1")


def siapkan(path=None, *, sekarang: Optional[int] = None, paket_v2: bool = False) -> None:
    """Bootstrap7; paket8 opt-in, kuota9 hanya migrator terpisah eksplisit."""
    import subscription_package_schema as paket_schema
    import assistant_quota_schema as kuota_schema
    if type(paket_v2) is not bool:
        raise ValueError("pilihan migrasi paket tidak sah")
    tujuan = _tujuan(path)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    kon = sqlite3.connect(str(tujuan), timeout=5.0)
    try:
        kon.row_factory = sqlite3.Row
        versi = int(kon.execute("PRAGMA user_version").fetchone()[0])
        if versi > kuota_schema.VERSI_SKEMA:
            raise StoreBelumSiap("skema admin lebih baru dari aplikasi")
        if versi in (0, 1, 2, 3, 4):
            try:
                if versi in (1, 2, 3, 4):
                    # PRAGMA ini harus dijalankan sebelum BEGIN; SQLite
                    # mengabaikan perubahan foreign_keys di dalam transaksi.
                    kon.execute("PRAGMA foreign_keys=OFF")
                else:
                    kon.execute("PRAGMA foreign_keys=ON")
                kon.execute("BEGIN IMMEDIATE")
                # Baca ulang setelah lock; migrator lain mungkin sudah selesai.
                versi = int(kon.execute("PRAGMA user_version").fetchone()[0])
                if versi > kuota_schema.VERSI_SKEMA:
                    raise StoreBelumSiap("skema admin lebih baru dari aplikasi")
                if versi in (1, 2, 3, 4):
                    _migrasi_registry_aksi(
                        kon, sumber_punya_hasil_id=(versi >= 2),
                        pertahankan_batch=(versi == 4),
                    )
                elif versi == 0:
                    _jalankan_ddl(kon, _DDL)
                kon.execute(
                    "INSERT OR IGNORE INTO konfigurasi_pendaftaran VALUES(1,1,1,?,?)",
                    ("closed_standard", int(time.time()) if sekarang is None else int(sekarang)),
                )
                for tabel, wajib in _KOLOM_WAJIB.items():
                    aktual = {
                        str(baris[1])
                        for baris in kon.execute("PRAGMA table_info(%s)" % tabel)
                    }
                    if not wajib <= aktual:
                        raise StoreBelumSiap("struktur store admin bentrok")
                if kon.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    raise StoreBelumSiap('foreign key migrasi admin tidak valid')
                if versi < 5:
                    kon.execute("PRAGMA user_version=5")
                kon.commit()
                kon.execute("PRAGMA foreign_keys=ON")
            except Exception:
                kon.rollback()
                raise
        # Lock sebelum membaca ulang versi: dua migrator tidak menulis DDL ganda.
        kon.execute("PRAGMA foreign_keys=ON")
        kon.execute("BEGIN IMMEDIATE")
        try:
            if kon.execute("PRAGMA user_version").fetchone()[0] == 5:
                import subscription_schema
                _jalankan_ddl(kon, subscription_schema.DDL)
                kon.execute("INSERT INTO langganan_aturan VALUES(?,30,3,10000,5000,25000,10000,'belum_ditetapkan')",
                            ("langganan-v1",))
                kon.execute("PRAGMA user_version=6")
            if kon.execute("PRAGMA user_version").fetchone()[0] == 6:
                import admin_launch_schema
                _jalankan_ddl(kon, admin_launch_schema.DDL)
                kon.execute(
                    "INSERT INTO pembayaran_konfigurasi VALUES(1,'nonaktif',1,?,?)",
                    (int(time.time()) if sekarang is None else int(sekarang), "sistem_migrasi"),
                )
                kon.execute("PRAGMA user_version=7")
            if paket_v2 and kon.execute("PRAGMA user_version").fetchone()[0] == 7:
                _validasi_skema(kon)
                _jalankan_ddl(kon, paket_schema.DDL)
                kon.execute("PRAGMA user_version=8")
            _validasi_skema(kon)
            kon.commit()
        except Exception:
            kon.rollback()
            raise
        if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise StoreBelumSiap("foreign key store admin tidak valid")
    except sqlite3.Error as galat:
        raise StoreBelumSiap("gagal menyiapkan store admin") from galat
    finally:
        kon.close()
    try:
        tujuan.chmod(0o600)
    except OSError:
        pass


def migrasikan_kuota_pendamping(path) -> None:
    """Migrasi aditif8→9 eksplisit pada file existing; bukan startup/GET.

    Operator wajib backup/rehearsal dan binary recovery9 sebelum data nyata.
    Tidak membuat file, paket/enrollment/trial/jendela, atau memperbaiki schema
    parsial secara diam-diam. DDL+versi atomik, replay9 hanya memvalidasi.
    """
    import assistant_quota_schema as kuota_schema
    import assistant_quota_store as kuota_store
    import subscription_store
    kon = _koneksi(_tujuan(path), "rw")
    try:
        kon.execute("BEGIN IMMEDIATE")
        versi = kon.execute("PRAGMA user_version").fetchone()[0]
        if versi not in (8, kuota_schema.VERSI_SKEMA):
            raise StoreBelumSiap("migrasi kuota memerlukan admin8 atau admin9")
        _validasi_skema(kon)
        subscription_store.validasi_ledger(kon)
        if versi == 8:
            _jalankan_ddl(kon, kuota_schema.DDL)
            kon.execute("PRAGMA user_version=9")
        _validasi_skema(kon)
        kuota_store.validasi_sumber(kon)
        if (kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or kon.execute("PRAGMA foreign_key_check").fetchone()):
            raise StoreBelumSiap("integritas migrasi kuota gagal")
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()


def migrasikan_penutupan_tagihan(path) -> None:
    """Migrasi aditif eksplisit tabel penutupan tagihan (tanpa bump versi).

    Tabel penutupan sengaja di luar namespace berversi dan divalidasi
    optional absent-or-exact pada setiap buka; image lama tetap dapat membuka
    DB pascamigrasi, sedangkan tabel parsial ditolak tanpa perbaikan diam-diam.
    Replay hanya memvalidasi. Operator wajib backup/rehearsal sebelum
    menjalankan pada data nyata; bukan startup/GET.
    """
    import subscription_schema
    kon = _koneksi(_tujuan(path), "rw")
    try:
        kon.execute("BEGIN IMMEDIATE")
        _validasi_skema(kon)
        if not subscription_schema.tersedia_penutupan(kon):
            _jalankan_ddl(kon, subscription_schema.DDL_PENUTUPAN)
        subscription_schema.validasi_penutupan(kon)
        if (kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or kon.execute("PRAGMA foreign_key_check").fetchone()):
            raise StoreBelumSiap("integritas migrasi penutupan gagal")
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()




























def _buat_batch_durable_kon(*args, **kwargs):
    from admin_batch_store import _buat_batch_durable_kon_impl
    return _buat_batch_durable_kon_impl(*args, **kwargs)


def baca_operasi(path, operasi_id: str) -> Optional[HasilOperasi]:
    from admin_journal_store import baca_operasi as baca
    return baca(path, operasi_id, buka_baca=buka_baca)


def reservasi(path, perintah, *, sekarang: Optional[int] = None) -> ReservasiOperasi:
    from admin_journal_store import reservasi as simpan
    return simpan(path, perintah, sekarang=sekarang, transaksi=_transaksi)


def finalisasi_sukses(
    path, perintah, receipt: ReceiptAkun, *, sekarang: Optional[int] = None,
    perubahan: Optional[Mapping[str, Tuple[str, str]]] = None,
) -> HasilOperasi:
    from admin_journal_store import finalisasi_sukses as finalisasi
    return finalisasi(path, perintah, receipt, sekarang=sekarang,
                      perubahan=perubahan, transaksi=_transaksi)


def finalisasi_gagal(
    path, perintah, *, status: str, hasil_kode: str,
    sekarang: Optional[int] = None,
) -> HasilOperasi:
    from admin_journal_store import finalisasi_gagal as finalisasi
    return finalisasi(path, perintah, status=status, hasil_kode=hasil_kode,
                      sekarang=sekarang, transaksi=_transaksi)


def baca_konfigurasi(path=None) -> KonfigurasiPendaftaran:
    from admin_journal_store import baca_konfigurasi as baca
    return baca(path, buka_baca=buka_baca)


def ubah_konfigurasi(
    path, *, operasi_id: str, actor_id: str, revisi: int, dibuka: bool,
    pesan_kode: str, token_tinjauan: str, sekarang: Optional[int] = None,
    failpoint: Optional[str] = None,
) -> HasilOperasi:
    from admin_journal_store import ubah_konfigurasi as ubah
    return ubah(
        path, operasi_id=operasi_id, actor_id=actor_id, revisi=revisi,
        dibuka=dibuka, pesan_kode=pesan_kode, token_tinjauan=token_tinjauan,
        sekarang=sekarang, failpoint=failpoint, transaksi=_transaksi,
    )


def purge_audit(
    path=None, *, sekarang: Optional[int] = None, batas_baris: int = 500,
) -> int:
    from admin_journal_store import purge_audit as purge
    return purge(path, sekarang=sekarang, batas_baris=batas_baris,
                 transaksi=_transaksi)


def daftar_riwayat(
    path=None, *, actor_id: str = "", aksi: str = "", status: str = "",
    mulai: Optional[int] = None, selesai: Optional[int] = None,
    halaman: int = 1, per_halaman: int = 25,
) -> HalamanRiwayat:
    return _daftar_riwayat_impl(
        path, actor_id=actor_id, aksi=aksi, status=status, mulai=mulai,
        selesai=selesai, halaman=halaman, per_halaman=per_halaman,
        buka_baca=buka_baca,
    )
