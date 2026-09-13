"""Validator dan rehearsal lokal untuk bundle backup admin-control.

Modul ini sengaja TIDAK mengambil backup produksi dan tidak mengklaim snapshot
lintas-file atomik. Operator harus menghentikan seluruh writer terlebih dahulu,
lalu memakai SQLite backup API/penyalinan auth di bawah lock yang sesuai. Helper
ini hanya membuat manifest dari salinan yang sudah ada, memvalidasinya, dan
menguji migrasi pada turunan sementara.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import stat
import tempfile
from typing import Mapping, Optional, Tuple


VERSI_MANIFEST = 1
NAMA_MANIFEST = "manifest.json"
BERKAS_WAJIB = {
    "belajar": "latihan.db",
    "auth": "sandi.json",
    "admin": "admin-control.db",
    "ai": "ai-control.db",
    "pendamping": "pendamping.db",
}
BERKAS_TERLARANG = frozenset((
    "sesi.json", "admin-drafts.db", "transient.db",
))
VERSI_TARGET = {
    "admin": 4,
    "ai": 2,
    "transient": 2,
}
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ID_BUNDLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class BackupTidakSah(RuntimeError):
    """Bundle tidak aman, tidak lengkap, atau gagal verifikasi."""


@dataclass(frozen=True)
class RingkasanBackup:
    bundle_id: str
    cutoff: int
    berkas: Tuple[str, ...]
    versi_admin: int
    versi_ai: int
    versi_pendamping: int
    revisi_auth_min: int
    revisi_auth_max: int
    operasi_admin_pending: int
    operasi_admin_uncertain: int
    perlu_rekonsiliasi: bool = False


def _sha256(path: Path) -> str:
    sidik = hashlib.sha256()
    with path.open("rb") as sumber:
        for blok in iter(lambda: sumber.read(1024 * 1024), b""):
            sidik.update(blok)
    return sidik.hexdigest()


def _regular_privat(path: Path, *, direktori: bool = False) -> None:
    try:
        info = path.lstat()
    except OSError as galat:
        raise BackupTidakSah("artefak backup tidak tersedia") from galat
    jenis_sah = stat.S_ISDIR(info.st_mode) if direktori else stat.S_ISREG(info.st_mode)
    if not jenis_sah or (not direktori and info.st_nlink != 1):
        raise BackupTidakSah("artefak backup bukan file privat biasa")
    batas = 0o700 if direktori else 0o600
    if stat.S_IMODE(info.st_mode) & ~batas:
        raise BackupTidakSah("izin artefak backup terlalu longgar")


def _baca_json_ketat(path: Path):
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda nilai: (_ for _ in ()).throw(
                ValueError("konstanta JSON tidak sah")
            ),
            object_pairs_hook=_objek_tanpa_duplikat,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as galat:
        raise BackupTidakSah("JSON backup tidak sah") from galat


def _objek_tanpa_duplikat(pasangan):
    hasil = {}
    for kunci, nilai in pasangan:
        if kunci in hasil:
            raise ValueError("key JSON duplikat")
        hasil[kunci] = nilai
    return hasil


def _versi_sqlite(path: Path, *, tabel_wajib) -> int:
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        kon = sqlite3.connect(uri, uri=True, timeout=5.0)
        try:
            if kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise BackupTidakSah("integritas SQLite gagal")
            if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise BackupTidakSah("foreign key SQLite gagal")
            tabel = {
                row[0] for row in kon.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not set(tabel_wajib) <= tabel:
                raise BackupTidakSah("schema SQLite tidak lengkap")
            return int(kon.execute("PRAGMA user_version").fetchone()[0])
        finally:
            kon.close()
    except sqlite3.Error as galat:
        raise BackupTidakSah("SQLite backup tidak dapat dibaca") from galat


def _revisi_auth(path: Path) -> Tuple[int, int]:
    data = _baca_json_ketat(path)
    if not isinstance(data, dict):
        raise BackupTidakSah("auth backup tidak sah")
    akun = data.get("akun")
    if akun is None and isinstance(data.get("pengguna"), str):
        akun = [data]
    if not isinstance(akun, list) or not akun:
        raise BackupTidakSah("auth backup tidak sah")
    # Pakai validator akun kanonis tanpa membuka/menulis storage aplikasi.
    import auth
    import admin_contracts
    try:
        auth._validasi_daftar_akun(akun, bentuk_multi="akun" in data)
        for key, receipt in data.get("operasi_admin", {}).items():
            parsed = admin_contracts.receipt_dari_dict(receipt)
            if parsed.operasi_id != key:
                raise ValueError("receipt tidak cocok")
    except (ValueError, TypeError, AttributeError):
        raise BackupTidakSah("metadata auth/receipt backup tidak sah") from None
    revisi = []
    id_terlihat = set()
    nama_terlihat = set()
    for item in akun:
        if not isinstance(item, dict):
            raise BackupTidakSah("auth backup tidak sah")
        nama = item.get("pengguna")
        identitas = item.get("id_akun")
        nilai = item.get("revisi_auth")
        if (
            type(nama) is not str or not nama.strip()
            or nama.strip().casefold() in nama_terlihat
            or type(identitas) is not str
            or re.fullmatch(r"akun_[0-9a-f]{32}", identitas) is None
            or identitas in id_terlihat
            or type(nilai) is not int or nilai < 0
            or type(item.get("garam")) is not str
            or re.fullmatch(r"[0-9a-f]{32}", item["garam"]) is None
            or type(item.get("kunci")) is not str
            or re.fullmatch(r"[0-9a-f]{64}", item["kunci"]) is None
            or type(item.get("iterasi")) is not int
            or item["iterasi"] < 1
        ):
            raise BackupTidakSah("auth backup tidak sah")
        nama_terlihat.add(nama.strip().casefold())
        id_terlihat.add(identitas)
        revisi.append(nilai)
    return min(revisi), max(revisi)


def _validasi_inventaris(akar: Path, *, dengan_manifest: bool) -> None:
    diizinkan = set(BERKAS_WAJIB.values())
    if dengan_manifest:
        diizinkan.add(NAMA_MANIFEST)
    try:
        aktual = {path.name for path in akar.iterdir()}
    except OSError as galat:
        raise BackupTidakSah("inventaris backup tidak tersedia") from galat
    if aktual != diizinkan:
        raise BackupTidakSah("inventaris backup tidak tepat")


def _validasi_nama_manifest(berkas) -> Mapping[str, Mapping[str, object]]:
    if not isinstance(berkas, dict) or set(berkas) != set(BERKAS_WAJIB):
        raise BackupTidakSah("daftar file backup tidak lengkap")
    for jenis, nama_harus in BERKAS_WAJIB.items():
        info = berkas[jenis]
        if not isinstance(info, dict) or set(info) != {"nama", "sha256", "ukuran"}:
            raise BackupTidakSah("metadata file backup tidak sah")
        nama = info["nama"]
        if (
            nama != nama_harus or Path(nama).name != nama
            or nama in BERKAS_TERLARANG
            or type(info["ukuran"]) is not int or info["ukuran"] <= 0
            or type(info["sha256"]) is not str
            or _HASH.fullmatch(info["sha256"]) is None
        ):
            raise BackupTidakSah("metadata file backup tidak sah")
    return berkas


def buat_manifest(bundle, *, bundle_id: str, cutoff: int) -> Path:
    """Tulis manifest atomik untuk salinan quiescent yang sudah dibuat caller."""
    if type(bundle_id) is not str or _ID_BUNDLE.fullmatch(bundle_id) is None:
        raise BackupTidakSah("bundle_id tidak sah")
    if type(cutoff) is not int or cutoff < 0:
        raise BackupTidakSah("cutoff tidak sah")
    akar = Path(bundle)
    _regular_privat(akar, direktori=True)
    if (akar / NAMA_MANIFEST).exists():
        raise BackupTidakSah("manifest backup sudah ada")
    if any((akar / nama).exists() for nama in BERKAS_TERLARANG):
        raise BackupTidakSah("state transient/sesi tidak boleh masuk backup")
    _validasi_inventaris(akar, dengan_manifest=False)
    isi = {}
    for jenis, nama in BERKAS_WAJIB.items():
        path = akar / nama
        _regular_privat(path)
        isi[jenis] = {
            "nama": nama,
            "sha256": _sha256(path),
            "ukuran": path.stat().st_size,
        }
    manifest = {
        "versi": VERSI_MANIFEST,
        "bundle_id": bundle_id,
        "cutoff": cutoff,
        # Prasyarat yang harus dibuktikan operator; helper tidak memegang writer.
        "coherence": "external_quiesce_required",
        "sessions_included": False,
        "transient_included": False,
        "berkas": isi,
    }
    sementara = akar / (
        ".%s.%s.%s.tmp" % (NAMA_MANIFEST, os.getpid(), secrets.token_hex(8))
    )
    try:
        fd = os.open(
            str(sementara), os.O_WRONLY | os.O_CREAT | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0), 0o600,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as tujuan:
            json.dump(manifest, tujuan, sort_keys=True, separators=(",", ":"))
            tujuan.write("\n")
            tujuan.flush()
            os.fsync(tujuan.fileno())
        os.replace(str(sementara), str(akar / NAMA_MANIFEST))
        os.chmod(str(akar / NAMA_MANIFEST), 0o600)
        fd_direktori = os.open(str(akar), os.O_RDONLY)
        try:
            os.fsync(fd_direktori)
        finally:
            os.close(fd_direktori)
    finally:
        try:
            sementara.unlink()
        except FileNotFoundError:
            pass
    return akar / NAMA_MANIFEST


def validasi_bundle(bundle, *, bundle_id: Optional[str] = None) -> RingkasanBackup:
    """Validasi hash, schema, FK/integrity, auth revision, dan exclusion."""
    akar = Path(bundle)
    _regular_privat(akar, direktori=True)
    if any((akar / nama).exists() for nama in BERKAS_TERLARANG):
        raise BackupTidakSah("state transient/sesi tidak boleh masuk backup")
    _validasi_inventaris(akar, dengan_manifest=True)
    manifest_path = akar / NAMA_MANIFEST
    _regular_privat(manifest_path)
    manifest = _baca_json_ketat(manifest_path)
    wajib = {
        "versi", "bundle_id", "cutoff", "coherence", "sessions_included",
        "transient_included", "berkas",
    }
    if not isinstance(manifest, dict) or set(manifest) != wajib:
        raise BackupTidakSah("manifest backup tidak sah")
    if (
        manifest["versi"] != VERSI_MANIFEST
        or type(manifest["bundle_id"]) is not str
        or _ID_BUNDLE.fullmatch(manifest["bundle_id"]) is None
        or (bundle_id is not None and manifest["bundle_id"] != bundle_id)
        or type(manifest["cutoff"]) is not int or manifest["cutoff"] < 0
        or manifest["coherence"] != "external_quiesce_required"
        or manifest["sessions_included"] is not False
        or manifest["transient_included"] is not False
    ):
        raise BackupTidakSah("manifest backup tidak sah")
    berkas = _validasi_nama_manifest(manifest["berkas"])
    for info in berkas.values():
        path = akar / info["nama"]
        _regular_privat(path)
        if path.stat().st_size != info["ukuran"] or _sha256(path) != info["sha256"]:
            raise BackupTidakSah("hash/ukuran backup tidak cocok")
    versi_admin = _versi_sqlite(
        akar / BERKAS_WAJIB["admin"],
        tabel_wajib=("konfigurasi_pendaftaran", "operasi_admin", "audit_admin"),
    )
    versi_ai = _versi_sqlite(
        akar / BERKAS_WAJIB["ai"],
        tabel_wajib=("konfigurasi", "batas_fitur", "ledger"),
    )
    _versi_sqlite(
        akar / BERKAS_WAJIB["belajar"],
        tabel_wajib=("siswa", "sesi"),
    )
    versi_pendamping = _versi_sqlite(
        akar / BERKAS_WAJIB["pendamping"],
        tabel_wajib=("migrasi_pendamping", "chat", "operasi"),
    )
    if not 1 <= versi_admin <= VERSI_TARGET["admin"]:
        raise BackupTidakSah("versi admin backup tidak didukung")
    if not 1 <= versi_ai <= VERSI_TARGET["ai"]:
        raise BackupTidakSah("versi AI backup tidak didukung")
    if not 1 <= versi_pendamping <= 4:
        raise BackupTidakSah("versi Pendamping backup tidak didukung")
    # Schema-versi harus lengkap, bukan sekadar user_version yang cocok.
    if versi_admin == VERSI_TARGET['admin']:
        import admin_store
        try:
            with admin_store.buka_baca(akar / BERKAS_WAJIB['admin']):
                pass
        except (RuntimeError, ValueError, sqlite3.Error):
            raise BackupTidakSah('schema admin backup tidak lengkap') from None
    minimum, maksimum = _revisi_auth(akar / BERKAS_WAJIB["auth"])
    admin_uri = (akar / BERKAS_WAJIB["admin"]).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(admin_uri, uri=True) as kon:
        pending = int(kon.execute(
            "SELECT COUNT(*) FROM operasi_admin WHERE status='reserved'"
        ).fetchone()[0])
        uncertain = int(kon.execute(
            "SELECT COUNT(*) FROM operasi_admin WHERE status='uncertain'"
        ).fetchone()[0])
    _validasi_link_receipt(akar)
    return RingkasanBackup(
        manifest["bundle_id"], manifest["cutoff"],
        tuple(BERKAS_WAJIB), versi_admin, versi_ai, versi_pendamping,
        minimum, maksimum, pending, uncertain, bool(pending or uncertain),
    )


def _validasi_link_receipt(akar: Path) -> None:
    """Tolak sukses tanpa receipt pasangan; pending tetap wajib direkonsiliasi."""
    auth_data = _baca_json_ketat(akar / BERKAS_WAJIB['auth'])
    receipts = auth_data.get('operasi_admin', {})
    admin = sqlite3.connect((akar / BERKAS_WAJIB['admin']).resolve().as_uri() + '?mode=ro', uri=True)
    belajar = sqlite3.connect((akar / BERKAS_WAJIB['belajar']).resolve().as_uri() + '?mode=ro', uri=True)
    admin.row_factory = sqlite3.Row
    belajar.row_factory = sqlite3.Row
    try:
        tabel = {r[0] for r in belajar.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for row in admin.execute("SELECT * FROM operasi_admin WHERE status='succeeded'"):
            if row['jenis_target'] == 'registration_config':
                continue  # journal/config satu transaksi pada DB yang sama
            if row['jenis_target'] in ('account', 'account_candidate'):
                receipt = receipts.get(row['operasi_id'])
                if (not isinstance(receipt, dict)
                        or receipt.get('sidik_perintah') != row['sidik_perintah']
                        or receipt.get('actor_id') != row['actor_id']):
                    raise BackupTidakSah('pasangan journal/receipt akun tidak cocok')
            else:
                if 'operasi_admin_siswa' not in tabel:
                    raise BackupTidakSah('receipt siswa pasangan tidak tersedia')
                receipt = belajar.execute('SELECT * FROM operasi_admin_siswa WHERE operasi_id=?', (row['operasi_id'],)).fetchone()
                if receipt is None or receipt['sidik_perintah'] != row['sidik_perintah']:
                    raise BackupTidakSah('pasangan journal/receipt siswa tidak cocok')
                if row['aksi'] == 'student_delete' and receipt['login_receipt_id']:
                    login = receipts.get(receipt['login_receipt_id'])
                    if (not isinstance(login, dict) or login.get('aksi') != 'student_login_delete_step'
                            or login.get('actor_id') != row['actor_id']):
                        raise BackupTidakSah('pasangan receipt langkah login siswa tidak cocok')
                    akun = auth_data.get('akun', [auth_data])
                    if any(a.get('id_akun') == login.get('target_id') for a in akun):
                        raise BackupTidakSah('login siswa terhapus masih ada pada pasangan backup')
    except sqlite3.Error:
        raise BackupTidakSah('schema pasangan receipt tidak sah') from None
    finally:
        admin.close()
        belajar.close()


def rehearsal_bundle(bundle, *, migrator_ai=None) -> RingkasanBackup:
    """Migrasikan turunan temp dua kali; backup induk tidak pernah ditulis.

    ``migrator_ai`` wajib diinjeksi coordinator dari candidate AI2. Snapshot F
    ini masih membawa AI1; helper menolak mengklaim kesiapan target tanpa
    migrator yang benar.
    """
    import admin_store
    import admin_students
    import assistant_schema
    import database

    sebelum = validasi_bundle(bundle)
    if migrator_ai is None:
        raise BackupTidakSah("migrator AI2 candidate wajib untuk rehearsal")
    akar = Path(bundle)
    with tempfile.TemporaryDirectory(prefix="jagomat-rehearsal-") as direktori:
        turunan = Path(direktori)
        turunan.chmod(0o700)
        for nama in BERKAS_WAJIB.values():
            shutil.copy2(str(akar / nama), str(turunan / nama))
            (turunan / nama).chmod(0o600)
        for _ in range(2):
            database.siapkan(turunan / BERKAS_WAJIB["belajar"])
            admin_students.siapkan(turunan / BERKAS_WAJIB["belajar"])
            admin_store.siapkan(turunan / BERKAS_WAJIB["admin"])
            migrator_ai(turunan / BERKAS_WAJIB["ai"])
            assistant_schema.siapkan(turunan / BERKAS_WAJIB["pendamping"])
        versi_admin = _versi_sqlite(
            turunan / BERKAS_WAJIB["admin"],
            tabel_wajib=("konfigurasi_pendaftaran", "operasi_admin", "receipt_admin"),
        )
        versi_ai = _versi_sqlite(
            turunan / BERKAS_WAJIB["ai"],
            tabel_wajib=(
                "konfigurasi", "batas_fitur", "ledger", "audit_uji_admin",
                "operasi_pengaturan_admin",
            ),
        )
        _versi_sqlite(
            turunan / BERKAS_WAJIB["belajar"],
            tabel_wajib=("siswa", "sesi", "operasi_admin_siswa"),
        )
        versi_pendamping = _versi_sqlite(
            turunan / BERKAS_WAJIB["pendamping"],
            tabel_wajib=("migrasi_pendamping", "chat", "operasi"),
        )
        if (
            versi_admin != VERSI_TARGET["admin"]
            or versi_ai != VERSI_TARGET["ai"]
            or versi_pendamping != 4
        ):
            raise BackupTidakSah("versi hasil rehearsal tidak sesuai target")
    return RingkasanBackup(
        sebelum.bundle_id, sebelum.cutoff, sebelum.berkas,
        versi_admin, versi_ai, versi_pendamping,
        sebelum.revisi_auth_min, sebelum.revisi_auth_max,
        sebelum.operasi_admin_pending, sebelum.operasi_admin_uncertain,
        sebelum.perlu_rekonsiliasi,
    )
