"""Retensi bukti transfer: hapus berkas fisik, tandai di ledger, bersihkan sisa sementara dan berkas yatim.

Tidak dijadwalkan atau dijalankan oleh aplikasi (tanpa worker/startup): hanya dipanggil operator atau cron harian host
lewat CLI

    mesin/.venv/bin/python mesin/pesanan_retensi.py --database <admin-control.db> [--folder <folder-bukti>]
        [--database-belajar <latihan.db>]

Jalur yang sama juga menyapu bukti langganan Latihan Harian (`harian_bukti_retensi`: DB belajar, subfolder `harian/`)
setelah sapuan transfer; DB belajar tidak ada = dilewati, gagalnya membuat exit 1 seperti sapuan transfer.

Aturan keamanan:

- Urutan per bukti: hapus berkas dulu, baru tandai di ledger. Bila proses mati di antaranya, bukti
  tetap terdaftar kedaluwarsa dan sapu berikutnya menyelesaikannya (hapus berkas idempoten, berkas yang
  sudah hilang tidak membuat macet). Menandai dulu akan membuat berkas yatim selamanya.
- Galat satu bukti (izin, nama rusak, DB terkunci) dihitung `gagal` dan tidak menghentikan sisanya;
  bukti itu dicoba lagi pada sapu berikutnya. Ringkasan hanya angka, tanpa nama berkas atau id.
- Sisa sementara `.tmp-*` (tulis yang terputus) dibuang bila berkas biasa (bukan tautan/direktori)
  dan lebih tua dari `UMUR_SEMENTARA_DETIK`. Ambang memakai jam suntikan yang sama dengan retensi.
- Berkas yatim (crash antara simpan berkas dan catat DB): berkas biasa bernama 32 hex di folder bukti yang TIDAK
  dirujuk kolom `berkas` baris `transfer_bukti` mana pun (termasuk yang sudah bertanda hapus) dan lebih tua dari
  `JAM_SAPU_YATIM` jam dibuang. Tautan, direktori, dan nama selain pola bukti tidak pernah disentuh.
- Folder tujuan eksplisit (opsi, env, atau di samping DB): tidak mengubah global/ENV dan tidak dibuat.
  Folder yang tidak ada TIDAK menandai apa pun di ledger (bukti kedaluwarsa dihitung `gagal`); tanpa bukti
  kedaluwarsa hasilnya nol. `berkas_sudah_hilang` yang tinggi = tanda folder salah (jangan abaikan).
"""
from __future__ import annotations

import argparse
from calendar import timegm
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import stat
import sys
from typing import Optional

import bukti_berkas
import pesanan_dasar as d
import pesanan_transfer

UMUR_SEMENTARA_DETIK = 3600
JAM_SAPU_YATIM = 24
DETIK_PER_JAM = 3600
EXIT_SEBAGIAN = 1
_FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
_GALAT_BUKTI = (bukti_berkas.BuktiBerkasError, OSError, d.PesananError, sqlite3.Error)


@dataclass(frozen=True)
class HasilSapu:
    berkas_dihapus: int = 0
    berkas_sudah_hilang: int = 0
    ditandai: int = 0
    gagal: int = 0
    sementara_dibersihkan: int = 0
    yatim_dibuang: int = 0


def _tambah(hasil: HasilSapu, **selisih) -> HasilSapu:
    return HasilSapu(**{k: getattr(hasil, k) + selisih.get(k, 0) for k in HasilSapu.__dataclass_fields__})


def _sapu_satu(kon, folder, bukti, sekarang: str, hari: int, tandai=None) -> dict:
    """Selisih hitungan satu bukti; galat -> `gagal` 1 (dicoba lagi pada sapu berikutnya).

    `tandai` = fungsi penanda (kon, bukti_id, sekarang, hari); bawaannya penanda ledger transfer. Sapuan bukti langganan
    Latihan Harian (`harian_bukti_retensi`) memakai urutan hapus-lalu-tandai yang sama lewat parameter ini.
    """
    try:
        terhapus = bukti_berkas.hapus_berkas(bukti["berkas"], folder)
    except _GALAT_BUKTI:
        return {"gagal": 1}
    hitungan = {"berkas_dihapus": int(terhapus), "berkas_sudah_hilang": int(not terhapus)}
    try:
        (tandai or pesanan_transfer.tandai_dihapus)(kon, bukti["bukti_id"], sekarang, hari)
    except _GALAT_BUKTI:
        return {**hitungan, "gagal": 1}
    return {**hitungan, "ditandai": 1}


def _sekarang_utc() -> str:
    return datetime.now(timezone.utc).strftime(_FORMAT_WAKTU)


def _epoch(sekarang: str) -> float:
    waktu = datetime.strptime(d.waktu_baku(sekarang), _FORMAT_WAKTU)
    return float(timegm(waktu.replace(tzinfo=timezone.utc).timetuple()))


def _sementara_usang(entri, batas: float) -> bool:
    if not entri.name.startswith(bukti_berkas.AWALAN_SEMENTARA):
        return False
    info = os.lstat(entri.path)
    return stat.S_ISREG(info.st_mode) and info.st_mtime <= batas


def _bersihkan_sementara(folder: Path, sekarang: str) -> int:
    """Hapus sisa `.tmp-*` biasa yang berumur >= ambang; folder tidak ada = 0."""
    if not folder.is_dir():
        return 0
    batas = _epoch(sekarang) - UMUR_SEMENTARA_DETIK
    jumlah = 0
    with os.scandir(folder) as isi:
        for entri in isi:
            try:
                if _sementara_usang(entri, batas):
                    os.unlink(entri.path)
                    jumlah += 1
            except OSError:
                continue
    return jumlah


def _yatim_usang(entri, batas: float, dirujuk) -> bool:
    """Berkas biasa bernama bukti, tak dirujuk ledger, dan mtime <= batas (lstat: tautan/direktori tidak lolos)."""
    if bukti_berkas.POLA_NAMA.fullmatch(entri.name) is None or entri.name in dirujuk:
        return False
    info = os.lstat(entri.path)
    return stat.S_ISREG(info.st_mode) and info.st_mtime <= batas


def _berkas_dirujuk(kon) -> frozenset:
    """Semua nama berkas di `transfer_bukti` (baris mana pun, termasuk yang bertanda hapus)."""
    return frozenset(baris[0] for baris in kon.execute("SELECT berkas FROM transfer_bukti"))


def _buang_yatim(kon, folder: Path, sekarang: str) -> int:
    """Hapus berkas yatim berumur > `JAM_SAPU_YATIM`; folder tidak ada = 0. Galat satu berkas dilewati."""
    if not folder.is_dir():
        return 0
    batas = _epoch(sekarang) - JAM_SAPU_YATIM * DETIK_PER_JAM
    with os.scandir(folder) as isi:
        entri_folder = list(isi)
    dirujuk = _berkas_dirujuk(kon)
    jumlah = 0
    for entri in entri_folder:
        try:
            if _yatim_usang(entri, batas, dirujuk):
                os.unlink(entri.path)
                jumlah += 1
        except OSError:
            continue
    return jumlah


def sapu(kon, folder, sekarang: str, *, hari: int = pesanan_transfer.HARI_RETENSI_BUKTI) -> HasilSapu:
    """Satu sapu retensi: bukti kedaluwarsa (berkas -> tanda) + sisa sementara + berkas yatim; kembalikan ringkasan.

    `kon` koneksi tulis `pesanan_transfer.buka(..., tulis_data=True)`; `folder` folder bukti;
    `sekarang` waktu ledger (UTC naif). Idempoten: sapu ulang tanpa perubahan menghasilkan nol.
    """
    folder = Path(folder)
    kedaluwarsa = pesanan_transfer.bukti_kedaluwarsa(kon, sekarang, hari)
    if not folder.is_dir():
        # Folder salah/hilang: "berkas sudah hilang" akan menandai bukti terhapus padahal berkas aslinya
        # utuh di folder lain (yatim selamanya). Jangan sentuh ledger; laporkan sebagai gagal.
        return HasilSapu(gagal=len(kedaluwarsa))
    hasil = HasilSapu()
    for bukti in kedaluwarsa:
        hasil = _tambah(hasil, **_sapu_satu(kon, folder, bukti, sekarang, hari))
    return _tambah(hasil, sementara_dibersihkan=_bersihkan_sementara(folder, sekarang),
                   yatim_dibuang=_buang_yatim(kon, folder, sekarang))


# --- CLI operator --------------------------------------------------------------

def _folder_tujuan(opsi: Optional[str], path_db: Path) -> Path:
    if opsi:
        return Path(opsi)
    ling = os.environ.get(bukti_berkas.NAMA_ENV, "").strip()
    return Path(ling) if ling else path_db.resolve().parent / bukti_berkas.NAMA_FOLDER


def _ringkasan(hasil: HasilSapu) -> str:
    return ("Sapu retensi selesai: %d bukti ditandai, %d berkas dihapus, %d berkas sudah hilang, "
            "%d gagal (dicoba lagi pada sapu berikutnya), %d sisa sementara dibuang, %d berkas yatim dibuang."
            % (hasil.ditandai, hasil.berkas_dihapus, hasil.berkas_sudah_hilang, hasil.gagal,
               hasil.sementara_dibersihkan, hasil.yatim_dibuang))


COPY_PERIKSA_FOLDER = ("Ada yang gagal: periksa izin dan pastikan --folder sama dengan folder bukti aplikasi "
                       "(OSN_DIREKTORI_BUKTI di container). Berkas sudah hilang yang banyak juga tanda folder salah.")


def _sapu_langganan(opsi_belajar: Optional[str], path_db: Path, folder: Path, sekarang: str) -> int:
    """Sapuan bukti langganan Latihan Harian (DB belajar); mengembalikan jumlah gagal, dan mencetak ringkasannya.

    Impor malas: domain pesanan tidak mengimpor DB belajar di tingkat atas (dijaga `test_pesanan_isolasi`).
    """
    import harian_bukti_retensi
    hasil = harian_bukti_retensi.sapu_dari_jalur(opsi_belajar, path_db, folder, sekarang)
    if hasil is None:
        print("Sapu retensi langganan Latihan Harian dilewati: DB belajar tidak ditemukan atau belum punya tabelnya.")
        return 0
    print(harian_bukti_retensi.ringkasan(hasil))
    return hasil.gagal


def main(argv=None, *, sekarang: Optional[str] = None) -> int:
    """Operator eksplisit; tidak pernah dipanggil startup atau GET. `sekarang` hanya untuk uji."""
    parser = argparse.ArgumentParser(description="Sapu retensi bukti transfer (30 hari sesudah keputusan; yatim > 24 jam)")
    parser.add_argument("--database", required=True, help="Path admin-control.db yang sudah diverifikasi")
    parser.add_argument("--folder", help="Folder bukti (bawaan: OSN_DIREKTORI_BUKTI atau di samping DB)")
    parser.add_argument("--database-belajar", help="DB belajar untuk bukti langganan Latihan Harian "
                        "(bawaan: OSN_BERKAS_DB, lalu latihan.db di samping admin-control.db; tidak ada = dilewati)")
    args = parser.parse_args(argv)
    path_db = Path(args.database)
    if not path_db.exists():
        print("Database tidak ditemukan; tidak ada yang diubah.", file=sys.stderr)
        return 2
    import admin_store_core
    folder, kini = _folder_tujuan(args.folder, path_db), sekarang or _sekarang_utc()
    try:
        with pesanan_transfer.buka(path_db, tulis_data=True) as kon:
            hasil = sapu(kon, folder, kini)
    except (admin_store_core.StoreBelumSiap, sqlite3.Error, OSError, ValueError):
        print("Ledger transfer belum siap atau tidak bisa dibuka; tidak ada yang diubah.", file=sys.stderr)
        return 2
    print(_ringkasan(hasil))
    gagal_langganan = _sapu_langganan(args.database_belajar, path_db, folder, kini)
    if hasil.gagal or gagal_langganan:
        print(COPY_PERIKSA_FOLDER, file=sys.stderr)
        return EXIT_SEBAGIAN
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
