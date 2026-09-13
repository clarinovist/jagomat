"""Koordinator journal SQLite dan receipt auth JSON untuk operasi admin.

Lock per operasi stabil dipakai lintas thread/proses. Ia dipegang dari sebelum
reservasi hingga finalisasi sehingga request kedua tidak dapat menyimpulkan
receipt absen selagi eksekutor patuh pertama masih aktif.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import threading
from typing import Optional

import admin_accounts
from admin_contracts import (
    AKSI_PEMBUATAN,
    AKSI_RESET_SANDI,
    HasilLayanan,
    PerintahAkun,
    PerintahHapusSiswa,
    PerintahPembuatanAkun,
    PerintahSiswa,
)
import admin_store


class OperasiTidakDapatDilanjutkan(RuntimeError):
    """Operasi terminal/nonretryable atau outcome masih tak pasti."""


class CrashSebelumFinalisasi(RuntimeError):
    """Failpoint test setelah receipt domain, sebelum audit finalize."""


class CrashSetelahFinalisasi(RuntimeError):
    """Failpoint test setelah commit final, sebelum response diterima."""


class PenyimpananOperasiTidakSah(RuntimeError):
    """Direktori/sidecar operasi tidak aman atau tidak dapat digunakan."""


class _StateLock:
    def __init__(self):
        self.thread = threading.RLock()
        self.local = threading.local()


_REGISTRY_GUARD = threading.Lock()
_REGISTRY = {}
_FD_AKTIF = set()


def _reset_setelah_fork():
    global _REGISTRY_GUARD, _REGISTRY, _FD_AKTIF
    for fd in tuple(_FD_AKTIF):
        try:
            os.close(fd)
        except OSError:
            pass
    _REGISTRY_GUARD = threading.Lock()
    _REGISTRY = {}
    _FD_AKTIF = set()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_setelah_fork)


def _lock_path(path_admin, operasi_id: str) -> Path:
    """Nama sidecar tidak mengekspos operation ID mentah."""
    direktori = Path(path_admin).resolve().parent
    sidik = hashlib.sha256(operasi_id.encode("ascii")).hexdigest()
    return direktori / (".admin-operation-%s.lock" % sidik)


def _state(path: Path):
    kunci = str(path)
    with _REGISTRY_GUARD:
        hasil = _REGISTRY.get(kunci)
        if hasil is None:
            hasil = _StateLock()
            _REGISTRY[kunci] = hasil
    return hasil


def _buka_lock(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lama = path.lstat()
    except FileNotFoundError:
        lama = None
    if lama is not None and not stat.S_ISREG(lama.st_mode):
        raise PenyimpananOperasiTidakSah("lock operasi tidak aman")
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(path), flags, 0o600)
    try:
        kini = os.fstat(fd)
        if not stat.S_ISREG(kini.st_mode) or kini.st_nlink != 1:
            raise PenyimpananOperasiTidakSah("lock operasi tidak aman")
        if lama is not None and (
            lama.st_dev != kini.st_dev or lama.st_ino != kini.st_ino
        ):
            raise PenyimpananOperasiTidakSah("lock operasi berubah")
        os.fchmod(fd, 0o600)
        return fd
    except Exception:
        os.close(fd)
        raise


@contextmanager
def kunci_operasi(path_admin, operasi_id: str):
    path = _lock_path(path_admin, operasi_id)
    state = _state(path)
    with state.thread:
        depth = getattr(state.local, "depth", 0)
        if depth == 0:
            fd = _buka_lock(path)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
            except Exception:
                os.close(fd)
                raise
            state.local.fd = fd
            _FD_AKTIF.add(fd)
        state.local.depth = depth + 1
        try:
            yield
        finally:
            state.local.depth -= 1
            if state.local.depth == 0:
                fd = state.local.fd
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    _FD_AKTIF.discard(fd)
                    os.close(fd)
                    del state.local.fd
                    del state.local.depth


def _layanan(hasil, *, baru: bool, sandi: Optional[str] = None):
    credential = (
        sandi
        if hasil.aksi in (AKSI_RESET_SANDI, *AKSI_PEMBUATAN) and baru
        else None
    )
    return HasilLayanan(hasil, baru, credential)


def _reconcile_terkunci(
    path_admin,
    path_auth,
    perintah: PerintahAkun,
    *,
    sekarang: Optional[int],
    reservation_baru: bool,
):
    """Reconcile saat operation lock sudah dimiliki.

    Jika reservation baru, caller masih berhak melakukan first execution. Jika
    journal lama reserved, executor patuh sebelumnya sudah melepas lock; receipt
    absen definitif berarti tidak commit dan tidak dijalankan ulang otomatis.
    """
    try:
        receipt = admin_accounts.baca_receipt(path_auth, perintah)
    except admin_accounts.KonflikAkun:
        hasil = admin_store.finalisasi_gagal(
            path_admin,
            perintah,
            status="conflict",
            hasil_kode="target_changed",
            sekarang=sekarang,
        )
        return _layanan(hasil, baru=False)
    except Exception:
        hasil = admin_store.finalisasi_gagal(
            path_admin,
            perintah,
            status="uncertain",
            hasil_kode="domain_uncertain",
            sekarang=sekarang,
        )
        return _layanan(hasil, baru=False)
    if receipt is not None:
        hasil = admin_store.finalisasi_sukses(
            path_admin, perintah, receipt, sekarang=sekarang
        )
        return _layanan(hasil, baru=False)
    if reservation_baru:
        return None
    hasil = admin_store.finalisasi_gagal(
        path_admin,
        perintah,
        status="failed_before_commit",
        hasil_kode="domain_not_committed",
        sekarang=sekarang,
    )
    return _layanan(hasil, baru=False)


def jalankan(
    path_admin,
    path_auth,
    perintah: PerintahAkun,
    *,
    sandi_baru: Optional[str] = None,
    sekarang: Optional[int] = None,
    failpoint: Optional[str] = None,
) -> HasilLayanan:
    """Eksekusi pertama; replay hanya metadata dan tidak mengulang credential."""
    admin_accounts.validasi_input(perintah, sandi_baru)
    with kunci_operasi(path_admin, perintah.operasi_id):
        # Validasi actor pada snapshot auth terbaru mendahului admission. Reader
        # ini mengambil lock auth lalu melepasnya sebelum transaksi admin; domain
        # writer tetap mengulang validasi di lock mutasi untuk menutup race.
        try:
            admin_accounts.validasi_actor(path_auth, perintah)
        except admin_accounts.KonflikAkun as galat:
            raise OperasiTidakDapatDilanjutkan(
                "receipt/principal tidak dapat diverifikasi"
            ) from galat
        except admin_accounts.DomainAkunTidakSah:
            # Domain rusak bisa berarti operasi lama sudah commit. Reservasi
            # dahulu agar outcome dapat ditahan sebagai uncertain.
            pass
        reservasi = admin_store.reservasi(
            path_admin, perintah, sekarang=sekarang
        )
        if reservasi.hasil.status == "succeeded":
            try:
                receipt = admin_accounts.baca_receipt(path_auth, perintah)
            except Exception as galat:
                raise OperasiTidakDapatDilanjutkan(
                    "receipt sukses tidak dapat diverifikasi"
                ) from galat
            if receipt is None:
                raise OperasiTidakDapatDilanjutkan(
                    "journal sukses tanpa receipt domain"
                )
            hasil = admin_store.finalisasi_sukses(
                path_admin, perintah, receipt, sekarang=sekarang
            )
            return _layanan(hasil, baru=False)
        if reservasi.hasil.status != "reserved":
            raise OperasiTidakDapatDilanjutkan(
                "operasi berstatus %s" % reservasi.hasil.status
            )
        pulih = _reconcile_terkunci(
            path_admin,
            path_auth,
            perintah,
            sekarang=sekarang,
            reservation_baru=reservasi.dibuat_baru,
        )
        if pulih is not None:
            if pulih.hasil.status == "succeeded":
                return pulih
            raise OperasiTidakDapatDilanjutkan(
                "operasi tidak aman dieksekusi ulang"
            )

        try:
            receipt = admin_accounts.jalankan(
                path_auth,
                perintah,
                sandi_baru=sandi_baru,
                sekarang=sekarang,
                failpoint=failpoint if failpoint in ("sebelum_replace", "setelah_replace") else None,
            )
        except admin_accounts.KonflikAkun:
            hasil = admin_store.finalisasi_gagal(
                path_admin,
                perintah,
                status="conflict",
                hasil_kode="target_changed",
                sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        except admin_accounts.BelumCommit:
            hasil = admin_store.finalisasi_gagal(
                path_admin,
                perintah,
                status="failed_before_commit",
                hasil_kode="domain_not_committed",
                sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        except admin_accounts.CrashSetelahReplace:
            raise CrashSebelumFinalisasi("receipt domain sudah commit")
        except admin_accounts.CommitDomainTakPasti as galat:
            admin_store.finalisasi_gagal(
                path_admin,
                perintah,
                status="uncertain",
                hasil_kode="domain_uncertain",
                sekarang=sekarang,
            )
            raise OperasiTidakDapatDilanjutkan("hasil domain tak pasti") from galat
        except admin_accounts.DomainAkunTidakSah as galat:
            admin_store.finalisasi_gagal(
                path_admin,
                perintah,
                status="uncertain",
                hasil_kode="domain_uncertain",
                sekarang=sekarang,
            )
            raise OperasiTidakDapatDilanjutkan("domain akun tidak sah") from galat
        if failpoint == "sebelum_finalize":
            raise CrashSebelumFinalisasi("failpoint sebelum finalisasi")
        hasil = admin_store.finalisasi_sukses(
            path_admin, perintah, receipt, sekarang=sekarang
        )
        if failpoint == "setelah_finalize":
            raise CrashSetelahFinalisasi("failpoint setelah finalisasi")
        return _layanan(
            hasil,
            baru=True,
            sandi=sandi_baru if perintah.aksi == AKSI_RESET_SANDI else None,
        )


@contextmanager
def _guard_pembuatan(path_admin, path_db, perintah):
    import admin_registration
    import admin_students
    if perintah.aksi == "account_teacher_create":
        # Semua caller yang bisa membuat owner siswa harus mengambil lock
        # registrasi ini; lalu urutan canonical registration -> DB -> auth.
        with admin_registration.kunci_registrasi(path_admin):
            with admin_registration.kunci_database_pemilik(path_db) as kon:
                yield {
                    "owner_lama_ada": admin_registration.alias_pemilik_ada(
                        kon, perintah.alias
                    )
                }
        return
    with admin_students.kunci_guard_login(path_db, perintah) as guard:
        yield guard


def buat_akun(
    path_admin,
    path_auth,
    path_db,
    perintah: PerintahPembuatanAkun,
    *,
    sandi_baru: str,
    sekarang: Optional[int] = None,
    failpoint: Optional[str] = None,
) -> HasilLayanan:
    """Create admin-audited dengan owner/one-to-one guard actual."""
    admin_accounts.validasi_pembuatan_input(perintah, sandi_baru)
    with kunci_operasi(path_admin, perintah.operasi_id):
        try:
            admin_accounts.validasi_actor(path_auth, perintah)
        except Exception as galat:
            raise OperasiTidakDapatDilanjutkan("principal tidak sah") from galat
        reservasi = admin_store.reservasi(path_admin, perintah, sekarang=sekarang)
        if reservasi.hasil.status == "succeeded":
            receipt = admin_accounts.baca_receipt(path_auth, perintah)
            if receipt is None:
                raise OperasiTidakDapatDilanjutkan("journal sukses tanpa receipt")
            hasil = admin_store.finalisasi_sukses(
                path_admin, perintah, receipt, sekarang=sekarang
            )
            return _layanan(hasil, baru=False)
        if reservasi.hasil.status not in ("reserved", "uncertain"):
            raise OperasiTidakDapatDilanjutkan(
                "operasi berstatus %s" % reservasi.hasil.status
            )
        try:
            receipt = admin_accounts.baca_receipt(path_auth, perintah)
        except Exception as galat:
            admin_store.finalisasi_gagal(
                path_admin, perintah, status="uncertain",
                hasil_kode="domain_uncertain", sekarang=sekarang,
            )
            raise OperasiTidakDapatDilanjutkan("receipt create tak pasti") from galat
        if receipt is not None:
            hasil = admin_store.finalisasi_sukses(
                path_admin, perintah, receipt, sekarang=sekarang
            )
            return _layanan(hasil, baru=False)
        if reservasi.hasil.status == "uncertain":
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="failed_before_commit",
                hasil_kode="domain_not_committed", sekarang=sekarang,
            )
            raise OperasiTidakDapatDilanjutkan(hasil.status)
        if not reservasi.dibuat_baru:
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="failed_before_commit",
                hasil_kode="domain_not_committed", sekarang=sekarang,
            )
            raise OperasiTidakDapatDilanjutkan(hasil.status)
        try:
            with _guard_pembuatan(path_admin, path_db, perintah) as guard:
                receipt = admin_accounts.buat_akun(
                    path_auth, perintah, sandi_baru=sandi_baru, guard=guard,
                    sekarang=sekarang,
                    failpoint=failpoint if failpoint in ("sebelum_replace", "setelah_replace") else None,
                )
        except admin_accounts.KonflikAkun:
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="conflict",
                hasil_kode="target_changed", sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        except (admin_accounts.KontrakTidakSah, ValueError):
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="conflict",
                hasil_kode="input_rejected", sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        except admin_accounts.BelumCommit:
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="failed_before_commit",
                hasil_kode="domain_not_committed", sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        except (admin_accounts.CrashSetelahReplace, CrashSebelumFinalisasi):
            raise CrashSebelumFinalisasi("receipt create sudah commit")
        except admin_accounts.CommitDomainTakPasti as galat:
            admin_store.finalisasi_gagal(
                path_admin, perintah, status="uncertain",
                hasil_kode="domain_uncertain", sekarang=sekarang,
            )
            raise OperasiTidakDapatDilanjutkan("hasil create tak pasti") from galat
        if failpoint == "sebelum_finalize":
            raise CrashSebelumFinalisasi("failpoint create sebelum finalize")
        hasil = admin_store.finalisasi_sukses(
            path_admin, perintah, receipt, sekarang=sekarang
        )
        if failpoint == "setelah_finalize":
            raise CrashSetelahFinalisasi("failpoint create setelah finalize")
        return _layanan(hasil, baru=True, sandi=sandi_baru)


def ubah_kelas(
    path_admin,
    path_auth,
    path_db,
    perintah: PerintahSiswa,
    *,
    sekarang: Optional[int] = None,
    failpoint: Optional[str] = None,
) -> HasilLayanan:
    """Ubah level + receipt DB lalu finalisasi audit admin.

    Urutan semua operasi siswa adalah operation -> DB -> auth. Adapter domain
    menahan lock DB lalu actor auth sampai commit DB, selaras create login murid
    dan caller `/akun` existing sehingga tidak ada siklus auth->DB.
    """
    import admin_students
    with kunci_operasi(path_admin, perintah.operasi_id):
        reservasi = admin_store.reservasi(path_admin, perintah, sekarang=sekarang)
        if reservasi.hasil.status == "succeeded":
            receipt = admin_students.baca_receipt(path_db, perintah)
            if receipt is None:
                raise OperasiTidakDapatDilanjutkan("journal sukses tanpa receipt siswa")
            hasil = admin_store.finalisasi_sukses(path_admin, perintah, receipt, sekarang=sekarang)
            return _layanan(hasil, baru=False)
        if reservasi.hasil.status not in ("reserved", "uncertain"):
            raise OperasiTidakDapatDilanjutkan(reservasi.hasil.status)
        try:
            receipt = admin_students.baca_receipt(path_db, perintah)
        except Exception as galat:
            admin_store.finalisasi_gagal(
                path_admin, perintah, status="uncertain",
                hasil_kode="domain_uncertain", sekarang=sekarang,
            )
            raise OperasiTidakDapatDilanjutkan("receipt siswa tak pasti") from galat
        if receipt is not None:
            hasil = admin_store.finalisasi_sukses(path_admin, perintah, receipt, sekarang=sekarang)
            return _layanan(hasil, baru=False)
        if reservasi.hasil.status == "uncertain" or not reservasi.dibuat_baru:
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="failed_before_commit",
                hasil_kode="domain_not_committed", sekarang=sekarang,
            )
            raise OperasiTidakDapatDilanjutkan(hasil.status)
        try:
            admin_students.siapkan_anchor_admin(path_admin, perintah, sekarang=sekarang)
            receipt = admin_students.ubah_kelas_domain(
                path_db, path_auth, perintah, sekarang=sekarang,
                failpoint=(
                    failpoint
                    if failpoint in ("sebelum_commit", "setelah_commit")
                    else None
                ),
            )
        except admin_accounts.KonflikAkun as galat:
            admin_students.hapus_anchor_admin(path_admin, perintah)
            raise OperasiTidakDapatDilanjutkan("principal tidak sah") from galat
        except admin_students.KonflikSiswa:
            admin_students.hapus_anchor_admin(path_admin, perintah)
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="conflict",
                hasil_kode="target_changed", sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        except RuntimeError:
            if failpoint == "setelah_commit":
                raise CrashSebelumFinalisasi("receipt siswa sudah commit")
            admin_students.hapus_anchor_admin(path_admin, perintah)
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="failed_before_commit",
                hasil_kode="domain_not_committed", sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        if failpoint == "sebelum_finalize":
            raise CrashSebelumFinalisasi("failpoint siswa sebelum finalize")
        hasil = admin_store.finalisasi_sukses(
            path_admin, perintah, receipt, sekarang=sekarang
        )
        return _layanan(hasil, baru=True)


def hapus_siswa(
    path_admin,
    path_auth,
    path_db,
    perintah: PerintahHapusSiswa,
    *,
    sekarang: Optional[int] = None,
    failpoint: Optional[str] = None,
) -> HasilLayanan:
    """Jalankan saga login→siswa dengan anchor dan receipt per langkah."""
    import admin_students
    with kunci_operasi(path_admin, perintah.operasi_id):
        reservasi = admin_store.reservasi(path_admin, perintah, sekarang=sekarang)
        if reservasi.hasil.status == "succeeded":
            try:
                receipt = admin_students.baca_receipt_dengan_actor(
                    path_db, path_auth, perintah
                )
            except (admin_students.KonflikSiswa, admin_accounts.KonflikAkun) as galat:
                raise OperasiTidakDapatDilanjutkan(
                    "receipt/principal tidak dapat diverifikasi"
                ) from galat
            if receipt is None:
                raise OperasiTidakDapatDilanjutkan("journal sukses tanpa receipt siswa")
            return _layanan(admin_store.finalisasi_sukses(
                path_admin, perintah, receipt, sekarang=sekarang
            ), baru=False)
        if reservasi.hasil.status not in ("reserved", "uncertain"):
            raise OperasiTidakDapatDilanjutkan(reservasi.hasil.status)
        try:
            receipt = admin_students.baca_receipt_dengan_actor(
                path_db, path_auth, perintah
            )
        except admin_students.DomainSiswaTidakSah as galat:
            admin_store.finalisasi_gagal(
                path_admin, perintah, status="uncertain",
                hasil_kode="domain_uncertain", sekarang=sekarang,
            )
            raise OperasiTidakDapatDilanjutkan("domain siswa tak pasti") from galat
        except (admin_students.KonflikSiswa, admin_accounts.KonflikAkun):
            login_commit = None
            try:
                login_commit = admin_accounts.baca_receipt_login_siswa_saga(
                    path_auth, perintah
                )
            except Exception:
                login_commit = None
            if login_commit is not None and reservasi.hasil.status == "uncertain":
                # Journal sudah ditahan uncertain; jangan coba downgrade ke
                # conflict dan jangan kehilangan provenance login-delete.
                return _layanan(reservasi.hasil, baru=False)
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah,
                status="uncertain" if login_commit is not None else "conflict",
                hasil_kode="domain_uncertain" if login_commit is not None else "target_changed",
                sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        if receipt is not None:
            return _layanan(admin_store.finalisasi_sukses(
                path_admin, perintah, receipt, sekarang=sekarang
            ), baru=False)
        anchor = admin_students.baca_anchor_admin(path_admin, perintah)
        if not reservasi.dibuat_baru and anchor is None:
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="failed_before_commit",
                hasil_kode="domain_not_committed", sekarang=sekarang,
            )
            raise OperasiTidakDapatDilanjutkan(hasil.status)
        if anchor is None:
            admin_students.siapkan_anchor_admin(path_admin, perintah, sekarang=sekarang)
            anchor = admin_students.baca_anchor_admin(path_admin, perintah)
        try:
            receipt = admin_students.hapus_siswa_domain(
                path_db, path_auth, perintah, sekarang=sekarang,
                failpoint=failpoint,
            )
        except admin_accounts.CrashSetelahReplace:
            # Login hilang+receipt; siswa tetap karena transaksi DB rollback.
            admin_store.finalisasi_gagal(
                path_admin, perintah, status="uncertain",
                hasil_kode="domain_uncertain", sekarang=sekarang,
            )
            raise CrashSebelumFinalisasi("login delete sudah commit")
        except admin_students.KonflikSetelahLoginDihapus:
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="uncertain",
                hasil_kode="domain_uncertain", sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        except (admin_students.KonflikSiswa, admin_accounts.KonflikAkun):
            login_commit = None
            try:
                login_commit = admin_accounts.baca_receipt_login_siswa_saga(
                    path_auth, perintah
                )
            except Exception:
                login_commit = None
            if login_commit is not None:
                hasil = admin_store.finalisasi_gagal(
                    path_admin, perintah, status="uncertain",
                    hasil_kode="domain_uncertain", sekarang=sekarang,
                )
                return _layanan(hasil, baru=False)
            admin_students.hapus_anchor_admin(path_admin, perintah)
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="conflict",
                hasil_kode="target_changed", sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        except RuntimeError:
            if failpoint in ("setelah_student_delete_sebelum_commit",):
                admin_store.finalisasi_gagal(
                    path_admin, perintah, status="uncertain",
                    hasil_kode="domain_uncertain", sekarang=sekarang,
                )
                raise CrashSebelumFinalisasi("login mungkin sudah dihapus")
            if failpoint == "setelah_domain_commit":
                raise CrashSebelumFinalisasi("delete siswa sudah commit")
            raise
        hasil = admin_store.finalisasi_sukses(
            path_admin, perintah, receipt, sekarang=sekarang
        )
        return _layanan(hasil, baru=True)


def rekonsiliasi_hapus_siswa(
    path_admin, path_auth, path_db, perintah: PerintahHapusSiswa, *, sekarang=None
):
    """Lanjut hanya langkah siswa setelah receipt login dikonfirmasi."""
    return hapus_siswa(
        path_admin, path_auth, path_db, perintah, sekarang=sekarang
    )


def rekonsiliasi(
    path_admin,
    path_auth,
    perintah: PerintahAkun,
    *,
    sekarang: Optional[int] = None,
) -> HasilLayanan:
    """Ambil fencing lock yang sama dan pulihkan dari receipt tanpa mutasi."""
    with kunci_operasi(path_admin, perintah.operasi_id):
        reservasi = admin_store.reservasi(
            path_admin, perintah, sekarang=sekarang
        )
        if reservasi.hasil.status == "succeeded":
            try:
                receipt = admin_accounts.baca_receipt(path_auth, perintah)
            except Exception as galat:
                raise OperasiTidakDapatDilanjutkan(
                    "receipt sukses tidak dapat diverifikasi"
                ) from galat
            if receipt is None:
                raise OperasiTidakDapatDilanjutkan(
                    "journal sukses tanpa receipt domain"
                )
            hasil = admin_store.finalisasi_sukses(
                path_admin, perintah, receipt, sekarang=sekarang
            )
            return _layanan(hasil, baru=False)
        if reservasi.hasil.status not in ("reserved", "uncertain"):
            return _layanan(reservasi.hasil, baru=False)
        pulih = _reconcile_terkunci(
            path_admin,
            path_auth,
            perintah,
            sekarang=sekarang,
            reservation_baru=False,
        )
        if pulih is None:  # pragma: no cover - false untuk reconcile
            raise AssertionError("reconcile tidak menghasilkan status")
        return pulih


def rekonsiliasi_pembuatan(
    path_admin,
    path_auth,
    perintah: PerintahPembuatanAkun,
    *,
    sekarang: Optional[int] = None,
) -> HasilLayanan:
    """Pulihkan create dari receipt auth tanpa membuat akun baru."""
    with kunci_operasi(path_admin, perintah.operasi_id):
        reservasi = admin_store.reservasi(path_admin, perintah, sekarang=sekarang)
        if reservasi.hasil.status not in ("reserved", "uncertain", "succeeded"):
            return _layanan(reservasi.hasil, baru=False)
        receipt = admin_accounts.baca_receipt(path_auth, perintah)
        if receipt is None:
            if reservasi.hasil.status == "succeeded":
                raise OperasiTidakDapatDilanjutkan("journal sukses tanpa receipt")
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="failed_before_commit",
                hasil_kode="domain_not_committed", sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        hasil = admin_store.finalisasi_sukses(
            path_admin, perintah, receipt, sekarang=sekarang
        )
        return _layanan(hasil, baru=False)


def rekonsiliasi_siswa(
    path_admin,
    path_auth,
    path_db,
    perintah: PerintahSiswa,
    *,
    sekarang: Optional[int] = None,
) -> HasilLayanan:
    """Pulihkan mutasi siswa dari receipt DB tanpa menulis ulang domain."""
    import admin_students
    with kunci_operasi(path_admin, perintah.operasi_id):
        try:
            admin_accounts.validasi_actor(path_auth, perintah)
        except Exception as galat:
            raise OperasiTidakDapatDilanjutkan("principal tidak sah") from galat
        reservasi = admin_store.reservasi(path_admin, perintah, sekarang=sekarang)
        if reservasi.hasil.status not in ("reserved", "uncertain", "succeeded"):
            return _layanan(reservasi.hasil, baru=False)
        anchor = admin_students.baca_anchor_admin(path_admin, perintah)
        receipt = admin_students.baca_receipt(path_db, perintah)
        if receipt is None:
            if reservasi.hasil.status == "succeeded":
                raise OperasiTidakDapatDilanjutkan("journal sukses tanpa receipt siswa")
            if anchor is not None:
                hasil = admin_store.finalisasi_gagal(
                    path_admin, perintah, status="uncertain",
                    hasil_kode="domain_uncertain", sekarang=sekarang,
                )
                return _layanan(hasil, baru=False)
            hasil = admin_store.finalisasi_gagal(
                path_admin, perintah, status="failed_before_commit",
                hasil_kode="domain_not_committed", sekarang=sekarang,
            )
            return _layanan(hasil, baru=False)
        hasil = admin_store.finalisasi_sukses(
            path_admin, perintah, receipt, sekarang=sekarang
        )
        return _layanan(hasil, baru=False)
