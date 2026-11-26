"""Bantuan bersama tes tautan kode anak guru (3b-2). Data sepenuhnya sintetis: akun, anak, dan kode buatan.

Setiap tes memakai `ServerUji` (server nyata di port acak, semua state di tmp_path). DB tautan dialihkan ke tmp_path
lewat env `GURU_TAUTAN_DB`. Akun murid dibuat dengan `siswa_id` supaya lolos cek kepemilikan anak.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import admin_contracts as c
import admin_store
import auth
import database
import family_deletion
import guru_tautan_aturan as aturan
import guru_tautan_dasar as dasar
import guru_tautan_laju as laju
import jadwal_store as js
import schema_jadwal
import schema_tagihan_catatan
from cek_http_kit import AKUN_A, id_akun, tambah_anak
from kelas_http_kit import pasang_skema
import kelas_kit

ADMIN = "admin_sintetis"
LOGIN_ANAK = "anak-alfa"
SANDI_ANAK = "sandi-anak-tautan-123"
AKUN_ANAK = (LOGIN_ANAK, SANDI_ANAK)
LOGIN_KELUARGA_LAIN = "keluarga-lain"
SANDI_KELUARGA_LAIN = "sandi-keluarga-lain-123"
KODE = "ABCD2345EFGH6789"
KODE_LAIN = "2345ABCD6789EFGH"
KODE_TAMPIL = "ABCD-2345-EFGH-6789"
KINI = "2026-11-23T03:00:00"
SESUDAH = "2026-11-23T03:30:00"
NAMA_KELOMPOK = "Mini Alfa"
TANGGAL_KELOMPOK = "2026-11-24"
JAM_KELOMPOK = "09:00"
PSEUDONIM = "Dihapus-sintetis"
LOKASI = "https://meet.google.com/abc-defg-hij"
JALUR_TAUTAN = "/guru/kelas/{klp}/tautan"
TABEL_TAUTAN = ("kode_anak", "kode_cabut", "permintaan", "putusan", "percobaan_gagal")


@dataclass
class KondisiTautan:
    kelompok_id: str
    siswa_id: int
    murid_id: str
    guru_id: str


def pasang_admin_jadwal() -> None:
    pasang_skema(admin_store.BAWAAN)
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    schema_tagihan_catatan.migrasikan(admin_store.BAWAAN)


def siapkan_db_tautan(tmp_path, monkeypatch) -> Path:
    """DB tautan di tmp_path, dan penghitung laju memori dikosongkan. Belum dibuat sampai tulis pertama."""
    berkas = tmp_path / "guru-tautan-uji.db"
    monkeypatch.setenv(dasar.ENV_DB, str(berkas))
    laju._reset()
    return berkas


def tambah_murid(login: str = LOGIN_ANAK, sandi: str = SANDI_ANAK, siswa_id: int | None = None) -> dict:
    """Akun murid sintetis yang terikat ke `siswa_id`. Mengembalikan akun (dict) dari berkas auth."""
    auth.tambah_akun(login, sandi, "murid", siswa_id=siswa_id)
    return auth.cari_akun(login)


def siapkan_kelompok_dan_order(server, *, kuota: int = 5, tanggal: str = TANGGAL_KELOMPOK) -> KondisiTautan:
    """Anak sintetis punya order Mini lunas dan BELUM ditempatkan; kelompok Mini terbuka milik guru A (AKUN_A).

    `kuota` dan `tanggal` diatur pemanggil untuk membuat kelompok penuh atau tertutup.
    """
    pasang_admin_jadwal()
    siswa = tambah_anak(server, "Anak Sintetis Alfa", AKUN_A[0], None)
    murid = tambah_murid(siswa_id=siswa)
    guru_id = id_akun(AKUN_A)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelompok = js.buat_kelompok(kon, ADMIN, nama=NAMA_KELOMPOK, lokasi=LOKASI, guru_id=guru_id,
                                    kuota=kuota, tanggal=tanggal, jam=JAM_KELOMPOK, sekarang=kelas_kit.KINI)
        kelas_kit.lunas(kon, siswa, "mini", n=1, akun=murid["id_akun"], sekarang=kelas_kit.KINI)
        kon.commit()
    return KondisiTautan(kelompok_id=kelompok, siswa_id=siswa, murid_id=murid["id_akun"], guru_id=guru_id)


def buat_kode_anak(kondisi: KondisiTautan, kode: str = KODE, *, pada: str = KINI) -> int:
    """Kode aktif untuk anak itu, dibuat langsung lewat modul penyimpanan (pengganti alur orang tua, belum dibangun)."""
    return dasar.buat_kode(akun_id=kondisi.murid_id, siswa_id=kondisi.siswa_id, kode_hash=aturan.hash_kode(kode),
                           oleh=kondisi.murid_id, peran=aturan.PERAN_ORANG_TUA, pada=pada)


def baris_tabel(path: Path | None, tabel: str) -> int | None:
    """Jumlah baris `tabel` di DB tautan, atau None bila berkas belum ada (berkas tidak dibuat oleh pembacaan)."""
    if path is None or not Path(path).exists():
        return None
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as kon:
        return int(kon.execute("SELECT COUNT(*) FROM " + tabel).fetchone()[0])


def keadaan_tautan(path: Path) -> dict:
    return {tabel: baris_tabel(path, tabel) for tabel in TABEL_TAUTAN}


def hapus_keluarga_sintetis(login_pemilik: str) -> None:
    """Jalur penghapusan keluarga yang menentukan `anak_masih_ada`: `family_deletion._ubah_belajar` (siswa
    dianonimkan) lalu `_ubah_auth` (akun pemilik ditombstone, akun murid dibuang). Bagian lain dilewati dan dicatat
    di laporan tes: `jalankan` memerlukan bundle dan receipt yang tidak relevan untuk uji ini."""
    akun = auth.cari_akun(login_pemilik)
    siswa_ids = family_deletion._ubah_belajar(database.BAWAAN, login_pemilik, akun["id_akun"], PSEUDONIM)
    perintah = c.PerintahHapusKeluarga(
        "operasi_hapus_keluarga_001", "akun_" + "a" * 32, 2, "family_data_delete", akun["id_akun"],
        auth.revisi_auth(akun), "guru", "c" * 64, "backup-recourse-001", True, "T" * 48,
    )
    family_deletion._ubah_auth(auth.BERKAS_SANDI, perintah, PSEUDONIM, siswa_ids)

