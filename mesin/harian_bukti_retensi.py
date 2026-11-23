"""Retensi bukti transfer langganan Latihan Harian: hapus berkas 30 hari sesudah keputusan, lalu tandai di ledger.

Mengikuti retensi bukti Paket Coba (`pesanan_retensi`) dan DIPANGGIL dari jalur yang sama (`pesanan_retensi.main`, yang
dijalankan cron harian host): tidak ada cron/worker baru dan aplikasi tidak menjadwalkan apa pun. Bedanya hanya letak
data: `harian_bukti` ada di DB belajar (bukan admin-control.db) dan berkasnya di subfolder `harian/` dari folder bukti.

Aturan keamanan (sama dengan Paket Coba):

- Urutan per bukti: hapus berkas dulu, baru tandai di `harian_bukti_hapus`; proses mati di antaranya diselesaikan sapuan
  berikutnya (hapus idempoten). Galat satu bukti dihitung `gagal` tanpa menghentikan sisanya.
- Hanya bukti yang SUDAH diputuskan (setuju/tolak) dan keputusannya >= 30 hari lalu; bukti menunggu tidak pernah
  dihapus (dijaga query dan trigger skema `harian_bukti_hapus_putusan`).
- Subfolder tujuan tidak ada = `gagal` tanpa menandai apa pun (jangan menandai terhapus padahal berkas utuh di folder lain).
- TIDAK ada sapuan berkas yatim di `harian/`: DB belajar ditemukan lewat opsi/env/samping admin-control.db, dan tebakan
  yang salah akan membuat bukti yang masih menunggu tampak yatim. Hanya sisa `.tmp-*` lama yang dibersihkan.
- DB belajar dicari berurutan: `--database-belajar`, env `OSN_BERKAS_DB`, lalu `latihan.db` di samping admin-control.db.
  Tidak pernah memakai bawaan kode (`database.BAWAAN`), tidak membuat berkas, dan tidak memigrasi: DB belum ada atau
  tabelnya belum lengkap = dilewati (bukan galat).
- Ringkasan hanya angka, tanpa nama berkas atau id.
"""
from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
from typing import Optional

import bukti_berkas
import database
import harian_langganan_berkas as berkas
import harian_langganan_dasar as h
import pesanan_dasar as d
import pesanan_retensi as pr

HARI_RETENSI_BUKTI = 30
NAMA_ENV_DB = "OSN_BERKAS_DB"
NAMA_DB_SAMPING = "latihan.db"
_JAM_PER_HARI = 24
_TABEL_WAJIB = frozenset({"harian_bukti", "harian_verifikasi", "harian_bukti_hapus"})


def _batas_retensi(sekarang, hari: int) -> str:
    if type(hari) is not int or hari < 1:
        raise d.PesananDataTidakSah("hari retensi tidak sah")
    return d.tambah_jam(d.waktu_baku(sekarang), -_JAM_PER_HARI * hari)


def _pilih_kedaluwarsa(kon, batas: str, bukti_id: Optional[int] = None) -> tuple:
    """Bukti yang sudah diputuskan sejak `batas` atau lebih lama dan belum bertanda hapus."""
    baris = kon.execute(
        "SELECT b.id,b.order_id,b.berkas FROM harian_bukti b "
        "WHERE NOT EXISTS(SELECT 1 FROM harian_bukti_hapus x WHERE x.bukti_id=b.id) "
        "AND EXISTS(SELECT 1 FROM harian_verifikasi v WHERE v.order_id=b.order_id "
        "AND v.bukti_hingga_id>=b.id AND v.dibuat<=?) AND (? IS NULL OR b.id=?) ORDER BY b.id",
        (batas, bukti_id, bukti_id))
    return tuple({"bukti_id": b["id"], "order_id": b["order_id"], "berkas": b["berkas"]} for b in baris)


def bukti_kedaluwarsa(kon, sekarang, hari: int = HARI_RETENSI_BUKTI) -> tuple:
    """Bukti yang keputusannya sudah >= `hari` hari lalu dan belum ditandai terhapus: tuple dict {bukti_id, order_id, berkas}.

    Hanya SELECT; pemanggil menghapus berkas fisik lalu memanggil :func:`tandai_dihapus`.
    """
    d.periksa_koneksi(kon)
    return _pilih_kedaluwarsa(kon, _batas_retensi(sekarang, hari))


def tandai_dihapus(kon, bukti_id, sekarang, hari: int = HARI_RETENSI_BUKTI) -> dict:
    """Tandai satu bukti terhapus (INSERT `harian_bukti_hapus`; metadata bukti tetap). Idempoten (`baru=False`).

    Bukti belum diputuskan atau belum berumur `hari` hari sejak keputusan -> LanggananKonflik; id tak dikenal ->
    PesananTidakDitemukan. Mengembalikan {bukti_id, berkas, baru}.
    """
    d.periksa_koneksi(kon)
    d.periksa_bilangan(bukti_id, "bukti_id")
    batas = _batas_retensi(sekarang, hari)
    kini = d.waktu_baku(sekarang)
    with d.tulis(kon):
        bukti = kon.execute("SELECT berkas FROM harian_bukti WHERE id=?", (bukti_id,)).fetchone()
        if bukti is None:
            raise d.PesananTidakDitemukan()
        hasil = {"bukti_id": bukti_id, "berkas": bukti["berkas"]}
        if kon.execute("SELECT 1 FROM harian_bukti_hapus WHERE bukti_id=?", (bukti_id,)).fetchone():
            return {**hasil, "baru": False}
        if not _pilih_kedaluwarsa(kon, batas, bukti_id):
            raise h.LanggananKonflik("bukti belum kedaluwarsa")
        kon.execute("INSERT INTO harian_bukti_hapus(bukti_id,dihapus) VALUES(?,?)", (bukti_id, kini))
        return {**hasil, "baru": True}


def sapu(kon, folder, sekarang, *, hari: int = HARI_RETENSI_BUKTI) -> pr.HasilSapu:
    """Satu sapuan retensi bukti langganan: bukti kedaluwarsa (berkas -> tanda) + sisa sementara di `harian/`.

    `kon` koneksi `database.buka` ke DB belajar; `folder` = folder bukti INDUK (subfolder `harian/` dihitung di sini);
    `sekarang` waktu ledger (UTC naif). Idempoten: sapu ulang tanpa perubahan menghasilkan nol.
    """
    sub = Path(folder) / berkas.SUBFOLDER
    kedaluwarsa = bukti_kedaluwarsa(kon, sekarang, hari)
    if not sub.is_dir():
        # Subfolder salah/hilang: "berkas sudah hilang" akan menandai bukti terhapus padahal berkas aslinya utuh
        # di tempat lain. Jangan sentuh ledger; laporkan sebagai gagal.
        return pr.HasilSapu(gagal=len(kedaluwarsa))
    hasil = pr.HasilSapu()
    for bukti in kedaluwarsa:
        hasil = pr._tambah(hasil, **pr._sapu_satu(kon, sub, bukti, sekarang, hari, tandai=tandai_dihapus))
    return pr._tambah(hasil, sementara_dibersihkan=pr._bersihkan_sementara(sub, sekarang))


# --- jalur CLI (dipanggil pesanan_retensi.main) ------------------------------------------------------------

def jalur_belajar(opsi: Optional[str], path_admin: Path) -> Path:
    """DB belajar: opsi, lalu env, lalu `latihan.db` di samping admin-control.db (tidak pernah bawaan kode)."""
    if opsi:
        return Path(opsi)
    lingkungan = os.environ.get(NAMA_ENV_DB, "").strip()
    return Path(lingkungan) if lingkungan else Path(path_admin).resolve().parent / NAMA_DB_SAMPING


def _siap(path: Path) -> bool:
    """True bila berkas ada dan ketiga tabel yang dibutuhkan sudah ada. Hanya baca (`mode=ro`), tidak membuat apa pun."""
    if not path.is_file():
        return False
    with closing(sqlite3.connect("%s?mode=ro" % path.resolve().as_uri(), uri=True)) as baca:
        ada = {b[0] for b in baca.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return _TABEL_WAJIB <= ada


def sapu_dari_jalur(opsi_belajar: Optional[str], path_admin: Path, folder, sekarang: str) -> Optional[pr.HasilSapu]:
    """Sapu bukti langganan untuk CLI; None bila DB belajar tidak ada atau belum punya tabelnya (dilewati).

    DB terkunci/rusak = `gagal` 1 (dicoba lagi pada sapuan berikutnya), bukan melewatkan diam-diam.
    """
    path = jalur_belajar(opsi_belajar, path_admin)
    try:
        if not _siap(path):
            return None
        with database.buka(path) as kon:
            return sapu(kon, folder, sekarang)
    except (sqlite3.Error, OSError, d.PesananError, bukti_berkas.BuktiBerkasError):
        return pr.HasilSapu(gagal=1)


def ringkasan(hasil: pr.HasilSapu) -> str:
    return ("Sapu retensi langganan Latihan Harian selesai: %d bukti ditandai, %d berkas dihapus, "
            "%d berkas sudah hilang, %d gagal (dicoba lagi pada sapu berikutnya), %d sisa sementara dibuang."
            % (hasil.ditandai, hasil.berkas_dihapus, hasil.berkas_sudah_hilang, hasil.gagal,
               hasil.sementara_dibersihkan))
