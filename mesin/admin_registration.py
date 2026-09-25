"""Guard pendaftaran publik dan pembuatan akun yang linearizable."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import threading
from typing import Optional

import admin_accounts
import admin_store
import auth
from admin_contracts import validasi_id
from json_storage import transaksi_json


@dataclass(frozen=True)
class StatusPendaftaran:
    tersedia: bool
    dibuka: bool
    pesan_kode: str
    revisi: Optional[int]


@dataclass(frozen=True)
class AkunBaru:
    id_akun: str
    pengguna: str
    peran: str
    revisi_auth: int
    siswa_id: Optional[int]
    baru: bool = False


_TOKEN_FORM = re.compile(r"^[A-Za-z0-9._-]{32,4096}$")
_RECEIPT_PUBLIC_FIELDS = {
    "versi", "operasi_id", "target_id", "hasil_id", "hasil_kode",
    "revisi_hasil", "dibuat", "sidik_perintah",
}


class _State:
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


def _path_lock(path_admin) -> Path:
    tujuan = Path(path_admin).resolve()
    return tujuan.parent / ".admin-registration.lock"


def _state(path: Path):
    kunci = str(path)
    with _REGISTRY_GUARD:
        hasil = _REGISTRY.get(kunci)
        if hasil is None:
            hasil = _State()
            _REGISTRY[kunci] = hasil
    return hasil


@contextmanager
def kunci_registrasi(path_admin):
    path = _path_lock(path_admin)
    path.parent.mkdir(parents=True, exist_ok=True)
    keadaan = _state(path)
    with keadaan.thread:
        depth = getattr(keadaan.local, "depth", 0)
        if depth == 0:
            try:
                info_path = path.lstat()
            except FileNotFoundError:
                info_path = None
            if info_path is not None and not stat.S_ISREG(info_path.st_mode):
                raise admin_store.StoreBelumSiap("lock pendaftaran tidak aman")
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(str(path), flags, 0o600)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise admin_store.StoreBelumSiap("lock pendaftaran tidak aman")
                if info_path is not None and (
                    info.st_dev != info_path.st_dev or info.st_ino != info_path.st_ino
                ):
                    raise admin_store.StoreBelumSiap("lock pendaftaran berubah")
                os.fchmod(fd, 0o600)
                fcntl.flock(fd, fcntl.LOCK_EX)
            except Exception:
                os.close(fd)
                raise
            keadaan.local.fd = fd
            _FD_AKTIF.add(fd)
        keadaan.local.depth = depth + 1
        try:
            yield
        finally:
            keadaan.local.depth -= 1
            if keadaan.local.depth == 0:
                fd = keadaan.local.fd
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    _FD_AKTIF.discard(fd)
                    os.close(fd)
                    del keadaan.local.fd
                    del keadaan.local.depth


def status(path_admin) -> StatusPendaftaran:
    """Status readonly; missing/corrupt melempar StoreBelumSiap."""
    nilai = admin_store.baca_konfigurasi(path_admin)
    return StatusPendaftaran(True, nilai.dibuka, nilai.pesan_kode, nilai.revisi)


def ubah(
    path_admin,
    *,
    operasi_id: str,
    actor_id: str,
    actor_revisi: int,
    path_auth,
    revisi: int,
    dibuka: bool,
    pesan_kode: str,
    token_tinjauan: str,
    sekarang: Optional[int] = None,
):
    """Tahan actor mutakhir sampai commit; close/open serial dengan registrasi."""
    if type(actor_revisi) is not int or actor_revisi < 0 or not auth.id_akun_sah(actor_id):
        raise PermissionError("Identitas pengelola berubah.")
    with kunci_registrasi(path_admin):
        with transaksi_json(path_auth) as tujuan:
            try:
                _mentah, akun, _multi = auth._baca_akun_untuk_tulis(tujuan)
            except (ValueError, OSError):
                raise PermissionError("Identitas pengelola tidak tersedia.") from None
            actor = next((a for a in akun if a.get("id_akun") == actor_id), None)
            if (actor is None or actor.get("peran") != "admin"
                    or auth.revisi_auth(actor) != actor_revisi):
                raise PermissionError("Identitas pengelola berubah.")
            return admin_store.ubah_konfigurasi(
                path_admin,
                operasi_id=operasi_id,
                actor_id=actor_id,
                revisi=revisi,
                dibuka=dibuka,
                pesan_kode=pesan_kode,
                token_tinjauan=token_tinjauan,
                sekarang=sekarang,
            )


@contextmanager
def kunci_database_pemilik(path_db):
    """Tahan write lock DB agar owner baru tak menyusul guard sebelum auth."""
    uri = Path(path_db).resolve().as_uri() + "?mode=rw"
    try:
        import sqlite3
        kon = sqlite3.connect(uri, uri=True, timeout=5.0)
    except sqlite3.Error as galat:
        raise admin_store.StoreBelumSiap("database siswa tidak tersedia") from galat
    try:
        kon.execute("PRAGMA busy_timeout=5000")
        kon.execute("BEGIN IMMEDIATE")
        yield kon
        # Context ini hanya fencing/read guard; jangan punya commit pasca-auth.
        kon.rollback()
    except sqlite3.Error as galat:
        kon.rollback()
        raise admin_store.StoreBelumSiap("guard pemilik tidak tersedia") from galat
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()


def alias_pemilik_ada(kon, alias: str) -> bool:
    return kon.execute(
        "SELECT 1 FROM siswa WHERE lower(pemilik)=lower(?) LIMIT 1", (alias,)
    ).fetchone() is not None


def _id_publik(operasi_id: str, alias: str, token_form: str) -> str:
    bahan = (operasi_id + "\x00" + alias.casefold() + "\x00" + token_form).encode()
    return "candidate_" + hashlib.sha256(bahan).hexdigest()[:32]


def daftar_publik(
    path_admin,
    path_auth,
    path_db,
    *,
    operasi_id: str,
    alias: str,
    sandi: str,
    token_form: str,
    sekarang: Optional[int] = None,
) -> AkunBaru:
    """Create guru publik tanpa journal admin, namun di bawah guard config.

    Operation ID/token form berasal antiforgery/rate-limit HTTP. Public create
    tidak masuk audit tindakan admin dan tidak memakai actor admin palsu.
    """
    validasi_id(operasi_id, "operasi_id")
    alias = admin_accounts.validasi_alias(alias)
    if type(sandi) is not str or len(sandi) < 8:
        raise ValueError("sandi publik minimal 8 karakter")
    if type(token_form) is not str or _TOKEN_FORM.fullmatch(token_form) is None:
        raise ValueError("token form tidak sah")
    target_id = _id_publik(operasi_id, alias, token_form)
    with kunci_registrasi(path_admin):
        config = admin_store.baca_konfigurasi(path_admin)
        if not config.dibuka:
            raise PermissionError("pendaftaran ditutup")
        with kunci_database_pemilik(path_db) as kon:
            owner_ada = alias_pemilik_ada(kon, alias)
            # Public actor tidak ada. Gunakan create primitive khusus di bawah
            # lock auth dan receipt public terpisah agar tidak menyamar admin.
            return _buat_publik_auth(
                path_auth,
                operasi_id=operasi_id,
                target_id=target_id,
                alias=alias,
                sandi=sandi,
                token_form=token_form,
                owner_ada=owner_ada,
                sekarang=sekarang,
            )


def _buat_publik_auth(
    path_auth,
    *,
    operasi_id: str,
    target_id: str,
    alias: str,
    sandi: str,
    token_form: str,
    owner_ada: bool,
    sekarang: Optional[int],
) -> AkunBaru:
    """Writer public minimal; receipt tidak memakai registry audit admin."""
    import auth
    import time

    if owner_ada:
        raise ValueError("alias tidak tersedia")
    hash_baru = auth.buat_hash(sandi)
    sidik = hashlib.sha256((
        operasi_id + "\x00" + target_id + "\x00" + alias.casefold()
        + "\x00" + token_form
    ).encode()).hexdigest()
    path = Path(path_auth)
    with transaksi_json(path) as tujuan:
        ada_file = tujuan.exists()
        try:
            mentah, akun, _multi = auth._baca_akun_untuk_tulis(tujuan)
        except (ValueError, OSError) as galat:
            raise admin_accounts.DomainAkunTidakSah("berkas akun tidak sah") from galat
        if mentah is None:
            if ada_file:
                raise admin_accounts.DomainAkunTidakSah("berkas akun null tidak sah")
            mentah = {}
        receipts = mentah.get("operasi_registrasi", {})
        if not isinstance(receipts, dict):
            raise admin_accounts.DomainAkunTidakSah("receipt registrasi tidak sah")
        for key, nilai in receipts.items():
            if (
                type(key) is not str
                or not isinstance(nilai, dict)
                or set(nilai) != _RECEIPT_PUBLIC_FIELDS
                or nilai.get("versi") != 1
                or nilai.get("operasi_id") != key
                or nilai.get("hasil_kode") != "teacher_created"
                or nilai.get("revisi_hasil") != 1
                or not auth.id_akun_sah(nilai.get("hasil_id"))
                or type(nilai.get("dibuat")) is not int
                or type(nilai.get("sidik_perintah")) is not str
                or len(nilai["sidik_perintah"]) != 64
            ):
                raise admin_accounts.DomainAkunTidakSah(
                    "receipt registrasi tidak sah"
                )
        lama = receipts.get(operasi_id)
        if lama is not None:
            if (
                not isinstance(lama, dict)
                or set(lama) != _RECEIPT_PUBLIC_FIELDS
                or lama.get("versi") != 1
                or lama.get("operasi_id") != operasi_id
                or lama.get("target_id") != target_id
                or lama.get("hasil_kode") != "teacher_created"
                or lama.get("revisi_hasil") != 1
                or lama.get("sidik_perintah") != sidik
                or type(lama.get("dibuat")) is not int
            ):
                raise admin_accounts.DomainAkunTidakSah(
                    "receipt registrasi tidak sah"
                )
            hasil_id = lama.get("hasil_id")
            if not auth.id_akun_sah(hasil_id):
                raise admin_accounts.DomainAkunTidakSah(
                    "receipt registrasi tidak sah"
                )
            akun_lama = next((a for a in akun if a.get("id_akun") == hasil_id), None)
            if akun_lama is None or akun_lama.get("peran") != "guru":
                raise admin_accounts.DomainAkunTidakSah("receipt registrasi yatim")
            return AkunBaru(
                hasil_id, akun_lama["pengguna"], "guru",
                int(lama["revisi_hasil"]), None,
            )
        if any(a["pengguna"].strip().casefold() == alias.casefold() for a in akun):
            raise ValueError("alias tidak tersedia")
        id_baru = auth._buat_id_akun()
        while any(a.get("id_akun") == id_baru for a in akun):
            id_baru = auth._buat_id_akun()
        baru = {
            "pengguna": alias,
            "peran": "guru",
            "id_akun": id_baru,
            "revisi_auth": 1,
            **hash_baru,
        }
        akun.append(baru)
        receipts = dict(receipts)
        receipts[operasi_id] = {
            "versi": 1,
            "operasi_id": operasi_id,
            "target_id": target_id,
            "hasil_id": id_baru,
            "hasil_kode": "teacher_created",
            "revisi_hasil": 1,
            "dibuat": int(time.time()) if sekarang is None else int(sekarang),
            "sidik_perintah": sidik,
        }
        hasil = auth._bungkus_akun(mentah, akun)
        hasil["operasi_registrasi"] = receipts
        auth._tulis_akun_atomik(hasil, tujuan)
        return AkunBaru(id_baru, alias, "guru", 1, None, baru=True)
