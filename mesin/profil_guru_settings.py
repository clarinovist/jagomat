"""Profil guru peninjau yang dikelola admin: migrasi opt-in, reader fail-closed, audit append-only.

Tabel aditif di admin-control.db tanpa bump ``user_version``. Hanya admin menulis;
halaman publik membaca proyeksi ``tampil=1`` lewat ``baca_publik`` (read-only,
fail-closed ke ``()``). Tidak ada kolom kontak/foto dan tidak ada data anak.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Optional, Tuple
import unicodedata

import admin_store

BATAS_NAMA = 80
BATAS_LATAR = 160
BATAS_LAMA = 60
BATAS_BARIS = 6
URUTAN_MIN = 1
URUTAN_MAKS = 99
PESAN_SIDIK_TIDAK_SAH = "snapshot profil guru tidak sah"
KATEGORI_DIIZINKAN = frozenset("LMNP")
# Karakter "kosong" yang tampak seperti spasi/isian tetapi lolos kategori huruf (Lo).
KARAKTER_KOSONG_TAMPAK = frozenset("\u3164\u115f\u1160\u2800\uffa0")
_GALAT_BACA = (OSError, RuntimeError, ValueError, TypeError, KeyError, sqlite3.Error)
_POLA_SIDIK = re.compile(r"[0-9a-f]{64}")

DDL = """
CREATE TABLE profil_guru (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL CHECK(length(nama) BETWEEN 1 AND 80),
    latar TEXT NOT NULL CHECK(length(latar) BETWEEN 1 AND 160),
    lama_mengajar TEXT NOT NULL CHECK(length(lama_mengajar) BETWEEN 1 AND 60),
    urutan INTEGER NOT NULL CHECK(urutan BETWEEN 1 AND 99),
    tampil INTEGER NOT NULL DEFAULT 0 CHECK(tampil IN (0,1)),
    revisi INTEGER NOT NULL CHECK(revisi>=1),
    dibuat_pada INTEGER NOT NULL CHECK(dibuat_pada>=0),
    diubah_pada INTEGER NOT NULL CHECK(diubah_pada>=0)
);
CREATE TABLE profil_guru_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operasi_id TEXT NOT NULL UNIQUE,
    principal_id TEXT NOT NULL,
    principal_revisi INTEGER NOT NULL CHECK(principal_revisi>=0),
    aksi TEXT NOT NULL CHECK(aksi IN ('tambah','ubah','hapus')),
    profil_id INTEGER NOT NULL,
    sidik_masukan TEXT NOT NULL CHECK(length(sidik_masukan)=64),
    ringkasan TEXT NOT NULL,
    dibuat_pada INTEGER NOT NULL CHECK(dibuat_pada>=0)
);
CREATE TRIGGER profil_guru_batas_baris BEFORE INSERT ON profil_guru
WHEN (SELECT COUNT(*) FROM profil_guru)>=6
BEGIN SELECT RAISE(ABORT,'profil guru maksimal 6 baris'); END;
CREATE TRIGGER profil_guru_audit_tolak_update BEFORE UPDATE ON profil_guru_audit
BEGIN SELECT RAISE(ABORT,'audit profil guru immutable'); END;
CREATE TRIGGER profil_guru_audit_tolak_delete BEFORE DELETE ON profil_guru_audit
BEGIN SELECT RAISE(ABORT,'audit profil guru immutable'); END;
CREATE TRIGGER profil_guru_audit_tolak_duplikat BEFORE INSERT ON profil_guru_audit
WHEN EXISTS(SELECT 1 FROM profil_guru_audit WHERE operasi_id=NEW.operasi_id)
BEGIN SELECT RAISE(ABORT,'audit profil guru duplikat'); END;
"""


class ProfilTidakSah(ValueError):
    """Isian profil tidak lolos validasi; pesannya aman ditampilkan (tanpa memantulkan isian)."""


@dataclass(frozen=True)
class ProfilGuru:
    id: int
    nama: str
    latar: str
    lama_mengajar: str
    urutan: int
    tampil: bool
    revisi: int
    dibuat_pada: int
    diubah_pada: int


@dataclass(frozen=True)
class _Isian:
    nama: str
    latar: str
    lama_mengajar: str
    urutan: int
    tampil: bool


# --- validasi -----------------------------------------------------------------

def _karakter_sah(ch: str) -> bool:
    """Allow-list: huruf, tanda gabung, angka, tanda baca, dan spasi ASCII U+0020 saja."""
    if ch in KARAKTER_KOSONG_TAMPAK:
        return False
    return ch == " " or unicodedata.category(ch)[0] in KATEGORI_DIIZINKAN


def _teks(nilai, label: str, batas: int) -> str:
    if type(nilai) is not str:
        raise ProfilTidakSah("%s harus berupa teks." % label)
    bersih = unicodedata.normalize("NFC", nilai).strip()
    if not bersih:
        raise ProfilTidakSah("%s wajib diisi." % label)
    if len(bersih) > batas:
        raise ProfilTidakSah("%s maksimal %d karakter." % (label, batas))
    if "<" in bersih or ">" in bersih:
        raise ProfilTidakSah("%s tidak boleh memuat tanda < atau >." % label)
    if not all(_karakter_sah(ch) for ch in bersih):
        raise ProfilTidakSah(
            "%s hanya boleh berisi huruf, angka, tanda baca, dan spasi biasa." % label)
    return bersih


def _urutan(nilai) -> int:
    if type(nilai) is not int or not URUTAN_MIN <= nilai <= URUTAN_MAKS:
        raise ProfilTidakSah("Urutan harus bilangan bulat %d sampai %d." % (URUTAN_MIN, URUTAN_MAKS))
    return nilai


def _isian(nama, latar, lama_mengajar, urutan, tampil) -> _Isian:
    if type(tampil) is not bool:
        raise ProfilTidakSah("Pilihan tampil tidak sah.")
    return _Isian(
        _teks(nama, "Nama", BATAS_NAMA), _teks(latar, "Latar pendidikan", BATAS_LATAR),
        _teks(lama_mengajar, "Lama mengajar", BATAS_LAMA), _urutan(urutan), tampil,
    )


def _waktu(nilai) -> int:
    if type(nilai) is not int or nilai < 0:
        raise ValueError("waktu profil guru tidak sah")
    return nilai


def _operasi(nilai) -> str:
    # Format sama dengan `subscription.identitas(..., "operasi")`; sengaja tidak
    # mengimpor modul billing agar modul pengaturan admin tetap di luar allow-list hook.
    if type(nilai) is not str or re.fullmatch(r"[A-Za-z0-9_-]{8,46}", nilai) is None:
        raise ValueError("operasi profil guru tidak sah")
    return nilai


def _id_profil(nilai) -> int:
    if type(nilai) is not int or nilai < 1:
        raise ValueError("id profil guru tidak sah")
    return nilai


def _revisi(nilai) -> int:
    if type(nilai) is not int or nilai < 1:
        raise ValueError("revisi profil guru tidak sah")
    return nilai


def _sidik_awal(nilai) -> str:
    if type(nilai) is not str or _POLA_SIDIK.fullmatch(nilai) is None:
        raise ValueError(PESAN_SIDIK_TIDAK_SAH)
    return nilai


def _hash(isi) -> str:
    # Diketahui/diterima: sidik audit = hash data yang pada dasarnya publik bila tampil=1;
    # audit tidak menyimpan nilai teks, hanya hash masukan dan nama kolom yang berubah.
    return hashlib.sha256(json.dumps(isi, separators=(",", ":")).encode()).hexdigest()


def sidik_profil(profil: ProfilGuru) -> str:
    """Sidik snapshot yang dibaca admin; dipakai sebagai kunci optimistic lock."""
    return _hash([profil.id, profil.nama, profil.latar, profil.lama_mengajar,
                  profil.urutan, profil.tampil, profil.revisi])


# --- schema ---------------------------------------------------------------------

def _struktur(kon):
    return tuple(tuple(row) for row in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE "
        "tbl_name GLOB 'profil_guru*' ORDER BY type,name"
    ))


def validasi_schema(kon) -> bool:
    """Absent sah (False) untuk binary sebelum migrasi; parsial/berbeda selalu ValueError."""
    aktual = _struktur(kon)
    if not aktual:
        return False
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(DDL)
        if aktual != _struktur(acuan):
            raise ValueError("struktur profil guru tidak lengkap")
    finally:
        acuan.close()
    return True


def _jalankan_ddl(kon, skrip):
    bagian = ""
    for baris in skrip.splitlines(keepends=True):
        bagian += baris
        if sqlite3.complete_statement(bagian):
            kon.execute(bagian)
            bagian = ""
    if bagian.strip():
        raise RuntimeError("DDL profil guru tidak lengkap")


def migrasikan(path, *, sekarang: int) -> None:
    """Pasang schema profil guru pada admin7/8/9 tanpa mengubah user_version; idempoten."""
    _waktu(sekarang)
    tujuan = Path(path)
    if not tujuan.exists():
        raise admin_store.StoreBelumSiap("store admin tidak tersedia")
    with admin_store._transaksi(tujuan) as kon:
        if not _struktur(kon):
            _jalankan_ddl(kon, DDL)
        validasi_schema(kon)
        # Diketahui/diterima: integrity_check penuh berjalan hanya di migrator operator
        # (sekali per rilis), tidak pernah per request.
        if (kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or kon.execute("PRAGMA foreign_key_check").fetchone()):
            raise admin_store.StoreBelumSiap("integritas migrasi profil guru gagal")


# --- pembaca ---------------------------------------------------------------------

def _dari_row(row) -> ProfilGuru:
    if row["tampil"] not in (0, 1):
        raise ValueError("nilai tampil rusak")
    isi = _isian(row["nama"], row["latar"], row["lama_mengajar"], row["urutan"], row["tampil"] == 1)
    return ProfilGuru(
        row["id"], isi.nama, isi.latar, isi.lama_mengajar, isi.urutan, isi.tampil,
        _revisi(row["revisi"]), _waktu(row["dibuat_pada"]), _waktu(row["diubah_pada"]),
    )


def baca(path=None) -> Optional[Tuple[ProfilGuru, ...]]:
    """Semua baris untuk admin (urut tampilan). None bila penyimpanan belum siap/rusak."""
    # Diketahui/diterima: satu baris rusak membuat seluruh baca() None, sehingga UI admin
    # menampilkan "belum siap" (fail-closed); pemulihannya lewat operator, bukan UI.
    try:
        with admin_store.buka_baca(path) as kon:
            if not validasi_schema(kon):
                return None
            return tuple(_dari_row(r) for r in kon.execute(
                "SELECT * FROM profil_guru ORDER BY urutan,id"))
    except _GALAT_BACA:
        return None


def baca_publik(path=None) -> tuple:
    """Proyeksi publik read-only: hanya ``tampil=1``; ``()`` bila absen/parsial/error."""
    # Diketahui/diterima: galat ditelan tanpa log demi halaman publik tetap tampil (fail-closed).
    try:
        with admin_store.buka_baca(path) as kon:
            if not validasi_schema(kon):
                return ()
            return tuple(
                {"nama": p.nama, "latar": p.latar, "lama_mengajar": p.lama_mengajar}
                for p in (_dari_row(r) for r in kon.execute(
                    "SELECT * FROM profil_guru WHERE tampil=1 ORDER BY urutan,id"))
            )
    except _GALAT_BACA:
        return ()


# --- penulis ---------------------------------------------------------------------

@contextmanager
def _sesi_tulis(path, path_auth, principal):
    """Kunci principal admin hidup, lalu transaksi atomik pada store yang skemanya siap."""
    import admin_launch_service
    with admin_launch_service.kunci_principal(path_auth, principal):
        with admin_store._transaksi(path) as kon:
            if not validasi_schema(kon):
                raise admin_store.StoreBelumSiap("schema profil guru belum dipasang")
            yield kon


def _baris(kon, profil_id: int):
    row = kon.execute("SELECT * FROM profil_guru WHERE id=?", (profil_id,)).fetchone()
    return None if row is None else _dari_row(row)


def _ulang(kon, principal, operasi: str, aksi: str, sidik_masukan: str):
    """Replay operasi sama: (True, hasil) bila identik, KonflikOperasi bila berbeda, (False, None) bila baru."""
    audit = kon.execute("SELECT * FROM profil_guru_audit WHERE operasi_id=?", (operasi,)).fetchone()
    if audit is None:
        return False, None
    cocok = (audit["principal_id"] == principal.id_akun
             and audit["principal_revisi"] == principal.revisi_auth
             and audit["aksi"] == aksi and audit["sidik_masukan"] == sidik_masukan)
    if not cocok:
        raise admin_store.KonflikOperasi("operasi profil guru berbeda")
    return True, _baris(kon, audit["profil_id"])


def _catat(kon, principal, operasi, aksi, profil_id, sidik_masukan, ringkasan, sekarang):
    kon.execute(
        "INSERT INTO profil_guru_audit(operasi_id,principal_id,principal_revisi,aksi,profil_id,"
        "sidik_masukan,ringkasan,dibuat_pada) VALUES(?,?,?,?,?,?,?,?)",
        (operasi, principal.id_akun, principal.revisi_auth, aksi, profil_id,
         sidik_masukan, ringkasan, sekarang),
    )


def _failpoint(failpoint):
    if failpoint == "setelah_tulis":
        raise RuntimeError("failpoint setelah tulis")


def _ringkasan_ubah(lama: ProfilGuru, baru: _Isian) -> str:
    berubah = [n for n in ("nama", "latar", "lama_mengajar")
               if getattr(lama, n) != getattr(baru, n)]
    if lama.urutan != baru.urutan:
        berubah.append("urutan %d->%d" % (lama.urutan, baru.urutan))
    if lama.tampil != baru.tampil:
        berubah.append("tampil %d->%d" % (lama.tampil, baru.tampil))
    return "ubah: " + (", ".join(berubah) or "tanpa perubahan nilai")


def tambah(path, path_auth, principal, *, operasi, nama, latar, lama_mengajar, urutan, tampil,
           sekarang, failpoint=None) -> ProfilGuru:
    """Tambah satu baris (bawaan tersembunyi) + audit atomik; replay operasi sama aman."""
    _operasi(operasi)
    _waktu(sekarang)
    isi = _isian(nama, latar, lama_mengajar, urutan, tampil)
    masukan = _hash(["tambah", isi.nama, isi.latar, isi.lama_mengajar, isi.urutan, isi.tampil])
    with _sesi_tulis(path, path_auth, principal) as kon:
        ulang, hasil = _ulang(kon, principal, operasi, "tambah", masukan)
        if ulang:
            return hasil
        if kon.execute("SELECT COUNT(*) FROM profil_guru").fetchone()[0] >= BATAS_BARIS:
            raise ProfilTidakSah("Daftar penuh: maksimal %d profil guru." % BATAS_BARIS)
        profil_id = kon.execute(
            "INSERT INTO profil_guru(nama,latar,lama_mengajar,urutan,tampil,revisi,dibuat_pada,diubah_pada)"
            " VALUES(?,?,?,?,?,1,?,?)",
            (isi.nama, isi.latar, isi.lama_mengajar, isi.urutan, int(isi.tampil), sekarang, sekarang),
        ).lastrowid
        _failpoint(failpoint)
        _catat(kon, principal, operasi, "tambah", profil_id, masukan,
               "tambah: urutan=%d, tampil=%d" % (isi.urutan, isi.tampil), sekarang)
        return _baris(kon, profil_id)


def _kunci_optimistik(kon, profil_id: int, revisi: int, sidik_awal: str) -> ProfilGuru:
    lama = _baris(kon, profil_id)
    if lama is None:
        raise admin_store.KonflikOperasi("profil guru tidak ditemukan")
    if lama.revisi != revisi or sidik_profil(lama) != sidik_awal:
        raise admin_store.KonflikOperasi("profil guru berubah")
    return lama


def ubah(path, path_auth, principal, *, operasi, profil_id, revisi, sidik_awal, nama, latar,
         lama_mengajar, urutan, tampil, sekarang, failpoint=None) -> ProfilGuru:
    """Ubah satu baris dengan revisi/sidik optimistic lock + audit atomik."""
    _operasi(operasi)
    _waktu(sekarang)
    _id_profil(profil_id)
    _revisi(revisi)
    _sidik_awal(sidik_awal)
    isi = _isian(nama, latar, lama_mengajar, urutan, tampil)
    masukan = _hash(["ubah", profil_id, revisi, sidik_awal, isi.nama, isi.latar,
                     isi.lama_mengajar, isi.urutan, isi.tampil])
    with _sesi_tulis(path, path_auth, principal) as kon:
        ulang, hasil = _ulang(kon, principal, operasi, "ubah", masukan)
        if ulang:
            return hasil
        lama = _kunci_optimistik(kon, profil_id, revisi, sidik_awal)
        kursor = kon.execute(
            "UPDATE profil_guru SET nama=?,latar=?,lama_mengajar=?,urutan=?,tampil=?,"
            "revisi=?,diubah_pada=? WHERE id=? AND revisi=?",
            (isi.nama, isi.latar, isi.lama_mengajar, isi.urutan, int(isi.tampil),
             revisi + 1, sekarang, profil_id, revisi),
        )
        if kursor.rowcount != 1:
            raise admin_store.KonflikOperasi("profil guru berubah")
        _failpoint(failpoint)
        _catat(kon, principal, operasi, "ubah", profil_id, masukan, _ringkasan_ubah(lama, isi), sekarang)
        return _baris(kon, profil_id)


def hapus(path, path_auth, principal, *, operasi, profil_id, revisi, sidik_awal, sekarang,
          failpoint=None) -> None:
    """Hapus satu baris + audit atomik; jejak audit tetap tersimpan."""
    _operasi(operasi)
    _waktu(sekarang)
    _id_profil(profil_id)
    _revisi(revisi)
    _sidik_awal(sidik_awal)
    masukan = _hash(["hapus", profil_id, revisi, sidik_awal])
    with _sesi_tulis(path, path_auth, principal) as kon:
        ulang, _hasil = _ulang(kon, principal, operasi, "hapus", masukan)
        if ulang:
            return None
        lama = _kunci_optimistik(kon, profil_id, revisi, sidik_awal)
        if kon.execute("DELETE FROM profil_guru WHERE id=? AND revisi=?", (profil_id, revisi)).rowcount != 1:
            raise admin_store.KonflikOperasi("profil guru berubah")
        _failpoint(failpoint)
        _catat(kon, principal, operasi, "hapus", profil_id, masukan,
               "hapus: urutan=%d, tampil=%d" % (lama.urutan, lama.tampil), sekarang)
        return None


def main(argv=None) -> int:
    """Migrator operator eksplisit; tidak pernah dipanggil startup atau GET."""
    import argparse
    import time
    parser = argparse.ArgumentParser(description="Pasang schema profil guru peninjau")
    parser.add_argument("--database", required=True, help="Path admin-control.db yang sudah diverifikasi")
    args = parser.parse_args(argv)
    migrasikan(Path(args.database), sekarang=int(time.time()))
    print("Migrasi profil guru selesai dan tervalidasi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
