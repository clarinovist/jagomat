"""Cabang callback Midtrans untuk order Paket Coba (`ord_`): hanya petunjuk durable.

Dipanggil `subscription_callback` SETELAH semua pemeriksaan umum (header peramban,
Content-Type, ukuran, readiness/sakelar, signature, merchant/IDR/QRIS) dan SEBELUM
jalur langganan. Callback BUKAN bukti bayar: modul ini hanya menulis pengamatan
sumber `callback` lewat `pesanan.catat_petunjuk`; receipt/status dibayar tetap hanya
lewat query status server-ke-server. Tidak pernah menyentuh tabel `langganan_*`.

Hasil `(kode_http, isi)`:

* order dikenal -> 200 (pengamatan tertulis, atau replay identik);
* order tak dikenal -> catatan yatim durable lalu 200; gagal tulis -> 503;
* pengamatan/yatim dengan `operasi_id` sama tetapi isi berbeda -> 409;
* penyimpanan belum siap atau galat lain -> 503 (provider mencoba lagi).

Payload mentah, signature, dan kontak tidak pernah disimpan; yatim hanya memuat id
order opak, petunjuk status, dan hash 64 hex dari field terverifikasi.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import sqlite3

import admin_store_core
import pesanan

PREFIX = "ord_"
_FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
_BIDANG_OPERASI = ("order_id", "status_code", "transaction_status", "transaction_id")
_PANJANG_OPERASI = 32
_GALAT_SIMPAN = (admin_store_core.StoreBelumSiap, sqlite3.Error, OSError, LookupError,
                 ValueError, pesanan.PesananError)


def milik_pesanan(order_id):
    """True bila `order_id` berawalan `ord_` (jalur order, bukan langganan)."""
    return type(order_id) is str and order_id.startswith(PREFIX)


def _bidang(data, nama):
    nilai = data.get(nama)
    if type(nilai) is not str:
        raise pesanan.PesananDataTidakSah("field callback tidak sah")
    return nilai


def _bahan(data):
    fraud = data.get("fraud_status") or ""
    if type(fraud) is not str:
        raise pesanan.PesananDataTidakSah("field callback tidak sah")
    return [_bidang(data, nama) for nama in _BIDANG_OPERASI] + [fraud]


def _operasi_id(data):
    """Identitas deterministik dari field terverifikasi (replay -> id sama)."""
    sidik = hashlib.sha256("|".join(_bahan(data)).encode("ascii")).hexdigest()
    return "cbk_" + sidik[:_PANJANG_OPERASI]


def _hash_payload(data):
    """Hash 64 hex dari field terverifikasi (incl. nominal); bukan payload mentah."""
    bahan = _bahan(data) + [_bidang(data, "gross_amount")]
    return hashlib.sha256("|".join(bahan).encode("ascii")).hexdigest()


def _petunjuk(data):
    return {nama: data.get(nama) for nama in
            ("order_id", "transaction_status", "status_code", "transaction_id", "gross_amount")}


def _waktu(sekarang):
    return datetime.fromtimestamp(sekarang, timezone.utc).strftime(_FORMAT_WAKTU)


def _tulis(kon, data, status_hint, sekarang):
    operasi = _operasi_id(data)
    waktu = _waktu(sekarang)
    order_id = data["order_id"]
    try:
        pesanan.catat_petunjuk(kon, order_id, _petunjuk(data), waktu, operasi)
        return
    except pesanan.PesananTidakDitemukan:
        pass
    # Order tak dikenal: wajib durable di yatim sebelum ACK, atau galat (503).
    pesanan.catat_yatim(kon, order_id, status_hint, _hash_payload(data), waktu, operasi)


def proses(path_admin, data, status_hint, sekarang):
    """Catat callback `ord_` yang sudah lolos pemeriksaan umum; (kode, isi)."""
    try:
        with pesanan.buka(path_admin, tulis_data=True) as kon:
            _tulis(kon, data, status_hint, sekarang)
    except pesanan.PesananKonflik:
        return 409, b"petunjuk berbeda"
    except _GALAT_SIMPAN:
        return 503, b"penyimpanan belum siap"
    return 200, b"OK"
