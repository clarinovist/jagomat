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
        kon.execute("PRAGMA foreign_keys=ON")
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


_SKEMA_PROFIL_REGISTRASI = """
CREATE TABLE registrasi_profil_anak (
 operasi_id TEXT PRIMARY KEY, akun_id TEXT NOT NULL, siswa_id INTEGER NOT NULL UNIQUE,
 sidik_perintah TEXT NOT NULL CHECK(length(sidik_perintah)=64),
 profil_sidik TEXT NOT NULL CHECK(length(profil_sidik)=64), dibuat INTEGER NOT NULL CHECK(dibuat>=0)
);
CREATE TRIGGER registrasi_profil_anak_tolak_update BEFORE UPDATE ON registrasi_profil_anak
BEGIN SELECT RAISE(ABORT,'receipt registrasi immutable'); END;
CREATE TRIGGER registrasi_profil_anak_tolak_delete BEFORE DELETE ON registrasi_profil_anak
BEGIN SELECT RAISE(ABORT,'receipt registrasi immutable'); END;
CREATE TRIGGER registrasi_profil_anak_tolak_replace BEFORE INSERT ON registrasi_profil_anak
WHEN EXISTS(SELECT 1 FROM registrasi_profil_anak WHERE operasi_id=NEW.operasi_id)
BEGIN SELECT RAISE(ABORT,'receipt registrasi duplikat'); END;
"""


def validasi_schema_profil(kon):
    """Reader exact, tidak memperbaiki DDL parsial atau bootstrap."""
    import sqlite3
    def struktur(c):
        return tuple(tuple(r) for r in c.execute("SELECT type,name,sql FROM sqlite_master WHERE tbl_name='registrasi_profil_anak' ORDER BY type,name"))
    ref = sqlite3.connect(':memory:')
    try:
        ref.executescript(_SKEMA_PROFIL_REGISTRASI)
        if struktur(ref) != struktur(kon):
            raise admin_store.StoreBelumSiap('receipt profil registrasi belum tersedia')
    finally:
        ref.close()


def migrasikan_profil_registrasi(path_db):
    """Migrasi opt-in receipt; bukan bagian startup, GET, atau POST publik."""
    import database
    with kunci_database_pemilik(path_db) as kon:
        if kon.execute('PRAGMA user_version').fetchone()[0] != 0:
            raise admin_store.StoreBelumSiap('versi database profil tidak dikenal')
        for tabel in ('siswa', 'profil_belajar'):
            if not kon.execute("SELECT 1 FROM sqlite_master WHERE name=? AND type='table'", (tabel,)).fetchone():
                raise admin_store.StoreBelumSiap('database profil belum siap')
        if not kon.execute("SELECT 1 FROM sqlite_master WHERE tbl_name='registrasi_profil_anak'").fetchone():
            database._jalankan_skema(kon, _SKEMA_PROFIL_REGISTRASI)
        validasi_schema_profil(kon)
        kon.commit()


_PROFIL_RECEIPT = {'versi', 'target_id', 'akun_id', 'siswa_id', 'sequence_awal',
                   'sidik_perintah', 'alias_sidik', 'profil_sidik', 'status', 'dibuat', 'kredensial'}


def _sidik_registrasi(nilai):
    import json
    return hashlib.sha256(json.dumps(nilai, ensure_ascii=True, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def _validasi_receipt_publik(receipts):
    if type(receipts) is not dict:
        raise ValueError('receipt registrasi tidak sah')
    for op, r in receipts.items():
        validasi_id(op, 'operasi_id')
        if (type(r) is not dict or set(r) != _RECEIPT_PUBLIC_FIELDS
                or r['operasi_id'] != op or r['hasil_kode'] != 'teacher_created'
                or type(r['versi']) is not int or r['versi'] != 1
                or type(r['revisi_hasil']) is not int or r['revisi_hasil'] != 1
                or type(r['dibuat']) is not int or r['dibuat'] < 0
                or not auth.id_akun_sah(r['hasil_id'])
                or type(r['target_id']) is not str or not re.fullmatch(r'candidate_[0-9a-f]{32}', r['target_id'])
                or type(r['sidik_perintah']) is not str or not re.fullmatch(r'[0-9a-f]{64}', r['sidik_perintah'])):
            raise ValueError('receipt registrasi tidak sah')


def _intent_profil(mentah):
    """Metadata saja; nama/sandi tidak disalin ke receipt saga."""
    daftar = mentah.get('registrasi_profil', {})
    if type(daftar) is not dict:
        raise ValueError('receipt profil registrasi tidak sah')
    for op, r in daftar.items():
        validasi_id(op, 'operasi_id')
        if (type(r) is not dict or set(r) != _PROFIL_RECEIPT
                or type(r['versi']) is not int or r['versi'] != 1
                or r['status'] not in ('pending', 'selesai')
                or not auth.id_akun_sah(r['akun_id'])
                or type(r['target_id']) is not str or not re.fullmatch(r'candidate_[0-9a-f]{32}', r['target_id'])
                or any(type(r[k]) is not int or r[k] < 0 for k in ('siswa_id', 'sequence_awal', 'dibuat'))
                or r['siswa_id'] <= r['sequence_awal']
                or any(type(r[k]) is not str or not re.fullmatch(r'[0-9a-f]{64}', r[k])
                       for k in ('sidik_perintah', 'alias_sidik', 'profil_sidik'))):
            raise ValueError('receipt profil registrasi tidak sah')
        if type(r['kredensial']) is not dict or set(r['kredensial']) != {'garam', 'kunci', 'iterasi'}:
            raise ValueError('kredensial registrasi tidak sah')
        auth._validasi_hash_akun(r['kredensial'])
    return daftar


def _sidik_profil_registrasi(kon, siswa_id, token_form):
    row = kon.execute('''SELECT s.nama,s.pemilik,s.tingkat,p.kelas_sekolah,COALESCE(p.revisi,0)
                        FROM siswa s LEFT JOIN profil_belajar p ON p.siswa_id=s.id
                        WHERE s.id=?''', (siswa_id,)).fetchone()
    return _sidik_registrasi((token_form, tuple(row))) if row else None


def _gagal_registrasi(failpoint, titik):
    if failpoint == titik:
        raise RegistrasiBelumSelesai('registrasi perlu dilanjutkan dengan form yang sama')


def daftar_dengan_profil(path_admin, path_auth, path_db, *, operasi_id, alias,
                        sandi, token_form, nama_anak, kelas_sekolah,
                        profil_parameter, sekarang=None, failpoint=None):
    """Saga DB→auth: intent, profil commit, lalu publish akun+receipt atomik.

    Intent tidak menerbitkan akun/login. Crash sesudah DB commit dapat dipulihkan
    request exact; profil hilang dengan receipt committed tidak diciptakan ulang.
    Receipt publik v1 tetap kompatibel; field saga terpisah tidak memuat anak.
    """
    import sqlite3
    import time
    import learning_profile
    from templates import level_valid
    validasi_id(operasi_id, 'operasi_id')
    alias = admin_accounts.validasi_alias(alias)
    if type(nama_anak) is not str or not nama_anak.strip() or len(nama_anak.strip()) > 40:
        raise ValueError('Nama panggilan anak wajib diisi, maksimal 40 karakter.')
    nama_anak = nama_anak.strip()
    if any(ord(c) < 32 for c in nama_anak):
        raise ValueError('Nama panggilan anak tidak sah.')
    if kelas_sekolah is not None and (type(kelas_sekolah) is not int or not 1 <= kelas_sekolah <= 6):
        raise ValueError('Pilih kelas sekolah 1–6 atau Kelas belum diisi.')
    if type(profil_parameter) is not str or not level_valid(profil_parameter):
        raise ValueError('Pilih variasi soal untuk latihan awal.')
    if type(sandi) is not str or not 8 <= len(sandi) <= 4096:
        raise ValueError('Kata sandi minimal 8 karakter.')
    if type(token_form) is not str or _TOKEN_FORM.fullmatch(token_form) is None:
        raise ValueError('token form tidak sah')
    kini = int(time.time()) if sekarang is None else sekarang
    if type(kini) is not int or kini < 0:
        raise ValueError('waktu registrasi tidak sah')
    target_id = _id_publik(operasi_id, alias, token_form)
    sidik = _sidik_registrasi((operasi_id, target_id, token_form, alias,
                             nama_anak, kelas_sekolah, profil_parameter))
    alias_sidik = _sidik_registrasi(alias.casefold())
    hash_baru = auth.buat_hash(sandi)
    with kunci_registrasi(path_admin):
        if not admin_store.baca_konfigurasi(path_admin).dibuka:
            raise PermissionError('pendaftaran ditutup')
        with kunci_database_pemilik(path_db) as kon:
            kon.row_factory = sqlite3.Row
            validasi_schema_profil(kon)
            with transaksi_json(path_auth) as tujuan:
                mentah, akun, _ = auth._baca_akun_untuk_tulis(tujuan)
                mentah = mentah or {'akun': []}
                intent = dict(_intent_profil(mentah))
                receipts = mentah.get('operasi_registrasi', {})
                _validasi_receipt_publik(receipts)
                lama = intent.get(operasi_id)
                if lama:
                    if lama['sidik_perintah'] != sidik or lama['target_id'] != target_id:
                        raise ValueError('binding registrasi berbeda')
                    if not auth.periksa(alias, sandi, {'pengguna': alias, **lama['kredensial']}):
                        raise ValueError('kredensial registrasi berbeda')
                    siswa_id = lama['siswa_id']
                    pemilik = kon.execute('SELECT pemilik FROM siswa WHERE id=?', (siswa_id,)).fetchone()
                    receipt_db = kon.execute('SELECT * FROM registrasi_profil_anak WHERE operasi_id=?', (operasi_id,)).fetchone()
                    if receipt_db is not None and tuple(receipt_db) != (
                            operasi_id, lama['akun_id'], siswa_id, sidik, lama['profil_sidik'], lama['dibuat']):
                        raise ValueError('receipt profil berbeda')
                    if receipt_db is None:
                        if lama['status'] != 'pending' or alias_pemilik_ada(kon, alias):
                            raise ValueError('profil tanpa receipt registrasi')
                        # INSERT awal mungkin rollback dan ID dipakai keluarga lain.
                        # Jangan adopsi row itu: receipt absent membuktikan profil
                        # operasi belum committed; alokasikan ID baru di lock DB.
                        seq = kon.execute("SELECT seq FROM sqlite_sequence WHERE name='siswa'").fetchone()
                        cur = kon.execute('INSERT INTO siswa(nama,tingkat,pemilik) VALUES(?,?,?)',
                                          (nama_anak, profil_parameter, alias))
                        siswa_id = cur.lastrowid
                        learning_profile.simpan_kelas(kon, siswa_id, kelas_sekolah, revisi=0, pemilik=alias)
                        lama = {**lama, 'siswa_id': siswa_id, 'sequence_awal': seq[0] if seq else 0}
                        intent[operasi_id] = lama
                        hasil = auth._bungkus_akun(mentah, akun)
                        hasil['registrasi_profil'] = intent
                        auth._tulis_akun_atomik(hasil, tujuan)
                        mentah = hasil
                    elif pemilik is None or pemilik[0] != alias:
                        raise ValueError('pemilik profil registrasi hilang atau berubah')
                    if _sidik_profil_registrasi(kon, siswa_id, token_form) != lama['profil_sidik']:
                        raise ValueError('profil registrasi berubah')
                    cocok = next((a for a in akun if a.get('id_akun') == lama['akun_id']), None)
                    if lama['status'] == 'selesai':
                        receipt = receipts.get(operasi_id)
                        if (cocok is None or cocok['pengguna'] != alias or cocok.get('peran') != 'guru'
                                or type(receipt) is not dict or set(receipt) != _RECEIPT_PUBLIC_FIELDS
                                or receipt['hasil_id'] != lama['akun_id'] or receipt['target_id'] != target_id
                                or receipt['sidik_perintah'] != sidik or receipt['hasil_kode'] != 'teacher_created'
                                or receipt['revisi_hasil'] != 1 or receipt['versi'] != 1
                                or receipt['operasi_id'] != operasi_id or receipt['dibuat'] != lama['dibuat']):
                            raise ValueError('receipt registrasi tidak cocok')
                        return AkunBaru(lama['akun_id'], alias, 'guru', 1, siswa_id)
                    if cocok or operasi_id in receipts:
                        raise ValueError('akun pending registrasi berubah')
                else:
                    if operasi_id in receipts or alias_pemilik_ada(kon, alias):
                        raise ValueError('alias tidak tersedia')
                    if any(r['alias_sidik'] == alias_sidik for r in intent.values()):
                        raise ValueError('alias tidak tersedia')
                    if any(a['pengguna'].strip().casefold() == alias.casefold() for a in akun):
                        raise ValueError('alias tidak tersedia')
                    seq = kon.execute("SELECT seq FROM sqlite_sequence WHERE name='siswa'").fetchone()
                    sequence_awal = seq[0] if seq else 0
                    cur = kon.execute('INSERT INTO siswa(nama,tingkat,pemilik) VALUES(?,?,?)',
                                      (nama_anak, profil_parameter, alias))
                    siswa_id = cur.lastrowid
                    learning_profile.simpan_kelas(kon, siswa_id, kelas_sekolah, revisi=0, pemilik=alias)
                    lama = dict(versi=1, target_id=target_id, akun_id=auth._buat_id_akun(),
                                siswa_id=siswa_id, sequence_awal=sequence_awal,
                                sidik_perintah=sidik, alias_sidik=alias_sidik,
                                profil_sidik=_sidik_profil_registrasi(kon, siswa_id, token_form),
                                status='pending', dibuat=kini, kredensial=hash_baru)
                    intent[operasi_id] = lama
                    _gagal_registrasi(failpoint, 'sebelum_intent')
                    hasil = auth._bungkus_akun(mentah, akun)
                    hasil['registrasi_profil'] = intent
                    auth._tulis_akun_atomik(hasil, tujuan)
                    mentah = hasil
                    _gagal_registrasi(failpoint, 'setelah_intent')
                if any(a['pengguna'].strip().casefold() == alias.casefold()
                       or a.get('id_akun') == lama['akun_id'] for a in akun):
                    raise ValueError('alias tidak tersedia')
                # Receipt DB dan profil commit bersama; tidak cukup hash row saja.
                if not kon.execute('SELECT 1 FROM registrasi_profil_anak WHERE operasi_id=?', (operasi_id,)).fetchone():
                    kon.execute('INSERT INTO registrasi_profil_anak VALUES(?,?,?,?,?,?)',
                                (operasi_id, lama['akun_id'], siswa_id, sidik, lama['profil_sidik'], lama['dibuat']))
                # DB commit di dalam authlock; tidak menerbitkan akun sebelum ini.
                kon.commit()
        # Fase kedua melepas KEDUA lock dahulu, lalu mengambil DB→auth lagi.
        # Tidak pernah menunggu DB saat sudah memegang auth.
        _gagal_registrasi(failpoint, 'setelah_db')
        return _publikasikan_profil(path_db, path_auth, operasi_id, alias, token_form,
                                    lama, failpoint)


def _publikasikan_profil(path_db, path_auth, operasi_id, alias, token_form, harapan, failpoint):
    with kunci_database_pemilik(path_db) as kon:
        validasi_schema_profil(kon)
        with transaksi_json(path_auth) as tujuan:
            mentah, akun, _ = auth._baca_akun_untuk_tulis(tujuan)
            if mentah is None:
                raise ValueError('intent registrasi hilang')
            intent = dict(_intent_profil(mentah))
            lama = intent.get(operasi_id)
            if lama != harapan or lama['status'] != 'pending':
                raise ValueError('intent registrasi berubah')
            siswa_id = lama['siswa_id']
            row = kon.execute('SELECT * FROM registrasi_profil_anak WHERE operasi_id=?', (operasi_id,)).fetchone()
            if row is None or tuple(row) != (operasi_id, lama['akun_id'], siswa_id,
                                             lama['sidik_perintah'], lama['profil_sidik'], lama['dibuat']):
                raise ValueError('receipt profil berbeda')
            if _sidik_profil_registrasi(kon, siswa_id, token_form) != lama['profil_sidik']:
                raise ValueError('profil registrasi berubah sebelum akun diterbitkan')
            if kon.execute('SELECT 1 FROM siswa WHERE lower(pemilik)=lower(?) AND id!=? LIMIT 1',
                           (alias, siswa_id)).fetchone():
                raise ValueError('alias memiliki profil yang tidak terkait registrasi')
            if any(a['pengguna'].strip().casefold() == alias.casefold()
                   or a.get('id_akun') == lama['akun_id'] for a in akun):
                raise ValueError('alias tidak tersedia')
            receipts = mentah.get('operasi_registrasi', {})
            _validasi_receipt_publik(receipts)
            if operasi_id in receipts:
                raise ValueError('receipt registrasi berubah')
            akun.append(dict(pengguna=alias, peran='guru', id_akun=lama['akun_id'],
                             revisi_auth=1, **lama['kredensial']))
            intent[operasi_id] = {**lama, 'status': 'selesai'}
            receipts = dict(receipts)
            receipts[operasi_id] = dict(versi=1, operasi_id=operasi_id, target_id=lama['target_id'],
                hasil_id=lama['akun_id'], hasil_kode='teacher_created', revisi_hasil=1,
                dibuat=lama['dibuat'], sidik_perintah=lama['sidik_perintah'])
            hasil = auth._bungkus_akun(mentah, akun)
            hasil['registrasi_profil'] = intent
            hasil['operasi_registrasi'] = receipts
            auth._tulis_akun_atomik(hasil, tujuan)
            _gagal_registrasi(failpoint, 'setelah_auth')
            return AkunBaru(lama['akun_id'], alias, 'guru', 1, siswa_id, baru=True)


class RegistrasiBelumSelesai(RuntimeError):
    """Pasangan registrasi belum selesai; ulangi token dan input yang sama."""


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
        if any(r['alias_sidik'] == _sidik_registrasi(alias.casefold()) for r in _intent_profil(mentah).values()):
            raise ValueError("alias tidak tersedia")
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
