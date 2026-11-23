"""Data halaman orang tua di akun murid (baca-saja): hasil cek, laporan Guru terbit terbaru, status pesanan.

Semua kunci datang dari sesi server (`id_akun`, `siswa_id`), tidak pernah dari URL/form. Modul ini tidak
membaca kunci jawaban, malrule, kode diagnosis, atau kontak. Status pesanan dibaca dari ledger pesanan lewat
koneksi read-only (tanpa transaksi tulis, tanpa menghubungi penyedia pembayaran).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import sqlite3
from typing import Optional

import admin_store
import admin_store_core
import akses_harian
import cek_gratis
import harian_langganan_ringkas
import parent_report_store
import pesanan_dasar
import pesanan_status

_FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataOrangTua:
    nama_anak: str
    hasil_cek: dict
    laporan: Optional[dict]
    status_pesanan: Optional[str]
    langganan: Optional[harian_langganan_ringkas.Ringkasan] = None
    harian: Optional[object] = None  # RingkasanHarian (Latihan Harian) atau None bila sakelar mati


def _sekarang_baku() -> str:
    return datetime.now(timezone.utc).strftime(_FORMAT_WAKTU)


def _nama_anak(kon, siswa_id: int) -> str:
    baris = kon.execute("SELECT nama FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
    return "" if baris is None else baris["nama"]


def status_pesanan(id_akun: str, siswa_id: int, sekarang: Optional[str] = None) -> Optional[str]:
    """Status turunan order milik akun ini untuk anak ini, atau None (tanpa order / penyimpanan belum siap).

    Penyimpanan pesanan yang belum dipasang atau tak terbaca menyembunyikan kartu (dicatat tanpa data),
    bukan membuat halaman gagal: kartu ini hanya informasi tambahan.
    """
    try:
        with pesanan_dasar.buka(admin_store.BAWAAN) as kon:
            baris = kon.execute(
                "SELECT order_id FROM pesanan_order WHERE akun_id = ? AND siswa_id = ?", (id_akun, siswa_id)
            ).fetchone()
            if baris is None:
                return None
            kini = _sekarang_baku() if sekarang is None else sekarang
            return pesanan_status.status_order(kon, baris["order_id"], id_akun, kini)["status"]
    except (admin_store_core.StoreBelumSiap, pesanan_dasar.PesananError, sqlite3.Error) as galat:
        _LOG.warning("status pesanan halaman orang tua tidak terbaca: %s", type(galat).__name__)
        return None


def langganan(kon, siswa_id: int, sekarang: str) -> Optional[harian_langganan_ringkas.Ringkasan]:
    """Ringkasan langganan Latihan Harian anak ini; None bila sakelar LATIHAN_HARIAN mati (tanpa kartu dan banner)."""
    if not akses_harian.aktif():
        return None
    return harian_langganan_ringkas.ringkasan(kon, siswa_id, sekarang)


def kumpulkan(kon, id_akun: str, siswa_id: int, sekarang: Optional[str] = None) -> DataOrangTua:
    """Isi halaman untuk anak sesi ini; `kon` ber-row_factory Row (database.buka)."""
    import harian_http  # F4: ringkasan Latihan Harian; None bila sakelar LATIHAN_HARIAN mati
    return DataOrangTua(
        nama_anak=_nama_anak(kon, siswa_id),
        hasil_cek=cek_gratis.hasil_siswa(kon, id_akun, siswa_id),
        laporan=parent_report_store.terbit_terbaru(kon, siswa_id),
        status_pesanan=status_pesanan(id_akun, siswa_id, sekarang),
        langganan=langganan(kon, siswa_id, _sekarang_baku() if sekarang is None else sekarang),
        harian=harian_http.ringkasan_untuk_orang_tua(kon, siswa_id),
    )
