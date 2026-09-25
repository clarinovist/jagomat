"""Endpoint callback Midtrans: publik, sempit, dan hanya petunjuk durable.

Tidak memerlukan login dan tidak menyentuh auth/sesi. Signature SHA512 diperiksa
constant-time terhadap Server Key dari konfigurasi server tepercaya; payload mentah,
signature, kontak, atau data anak tidak pernah disimpan. Callback BUKAN bukti
settlement/refund: efek finansial tetap lewat GET status server-to-server (pekerja
rekonsiliasi atau panel admin) dengan binding penuh. ACK 2xx hanya diberikan
setelah hint minimum tersimpan durable; tanpa konfigurasi/sakelar yang siap,
respons retryable diberikan dan tidak ada yang ditulis.
"""

import hashlib
import re
import sqlite3
import time

import admin_store
import admin_subscription
import midtrans_contract as midtrans
import subscription as d
import subscription_produksi as prod
import subscription_store as store

JALUR = "/midtrans/callback"
BATAS_BODY = 8192
_TIPE = "application/json"
_POLA_WAJIB = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
_POLA_KODE = re.compile(r"[0-9]{3}\Z")
_PERIKSA = ("refund", "partial_refund", "chargeback", "cancel", "deny", "expire")


def _kirim(penangan, kode, isi):
    penangan.send_response(kode)
    penangan.send_header("Content-Type", "text/plain; charset=utf-8")
    penangan.send_header("Cache-Control", "no-store")
    penangan.send_header("X-Content-Type-Options", "nosniff")
    penangan.send_header("Content-Length", str(len(isi)))
    penangan.end_headers()
    penangan.wfile.write(isi)


def tangani_post(penangan, jalur):
    """True bila jalur ini milik endpoint callback (termasuk penolakan)."""
    if jalur != JALUR or getattr(penangan, "command", "POST") != "POST":
        return False
    try:
        kode, isi = _proses(penangan)
    except (Exception, KeyboardInterrupt):
        # Satu respons saja, generik, tanpa detail internal atau payload.
        kode, isi = 503, b"belum aman"
    _kirim(penangan, kode, isi)
    return True


def tangani_get(penangan, jalur):
    """GET di jalur callback bukan kontrak provider: 404 identik, tanpa efek."""
    if jalur != JALUR:
        return False
    _kirim(penangan, 404, b"tidak ada")
    return True


def _proses(penangan):
    if any(_header_asing(penangan, nama) is not None for nama in
           ("Origin", "Referer", "Sec-Fetch-Site", "Sec-Fetch-Mode", "Cookie", "Authorization")):
        return 403, b"ditolak"
    if getattr(penangan, "path", JALUR) != JALUR:
        return 403, b"ditolak"
    tipe = (penangan.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if tipe != _TIPE:
        return 415, b"tipe tidak didukung"
    panjang = penangan.headers.get("Content-Length")
    if panjang is None:
        return 411, b"panjang wajib"
    if type(panjang) is not str or not panjang.isdigit():
        return 400, b"panjang tidak sah"
    jumlah = int(panjang)
    if jumlah == 0:
        return 400, b"body kosong"
    if jumlah > BATAS_BODY:
        return 413, b"terlalu besar"
    mentah = bytes(penangan.rfile.read(jumlah))
    if len(mentah) != jumlah:
        return 400, b"body tidak utuh"
    try:
        config, kesiapan = _konteks(penangan)
        sakelar = prod.sakelar_efektif(admin_store.BAWAAN, kesiapan)
    except (Exception, KeyboardInterrupt):
        return 503, b"belum siap"
    if not midtrans.signature_cocok(mentah, config):
        return 403, b"ditolak"
    try:
        data = midtrans._json(mentah)
        invoice_id = data["order_id"]
        d.identitas(invoice_id, "invoice")
        if not _binding_cocok(data, config):
            return 403, b"ditolak"
        status = _status_hint(data)
        sidik = _sidik(data)
    except (ValueError, TypeError, KeyError):
        return 403, b"ditolak"
    if not sakelar.rekonsiliasi:
        return 503, b"belum siap"
    try:
        _simpan(admin_store.BAWAAN, invoice_id, status, sidik, int(time.time()), sakelar)
    except d.FiturNonaktif:
        return 503, b"belum siap"
    except store.KonflikLangganan:
        return 409, b"petunjuk berbeda"
    except (admin_store.StoreBelumSiap, sqlite3.Error, OSError, LookupError):
        return 503, b"penyimpanan belum siap"
    return 200, b"OK"


def _header_asing(penangan, nama):
    """Header yang tidak pernah dikirim Midtrans: peramban, sesi, atau proxy auth."""
    try:
        return penangan.headers.get(nama)
    except (AttributeError, TypeError):
        return "tidak sah"


def _konteks(penangan):
    """Konfigurasi + readiness dari runtime terpasang, atau config server tepercaya."""
    runtime = getattr(penangan.server, "pembayaran_runtime", None)
    if (isinstance(runtime, admin_subscription.RuntimePembayaran)
            and getattr(runtime.config, "lingkungan", None) == "production"):
        return runtime.config, admin_subscription.kesiapan_penangan(penangan)
    return prod.konfigurasi_tepercaya(), prod.kesiapan_produksi()


def _binding_cocok(data, config):
    """Merchant/IDR/QRIS terikat konfigurasi server; field lain tidak dipercaya."""
    return (data.get("merchant_id") == config.merchant and data.get("currency") == "IDR"
            and data.get("payment_type") == "qris")


def _status_hint(data):
    status = data.get("transaction_status")
    if type(status) is not str:
        raise ValueError("status callback tidak sah")
    return "perlu_diperiksa" if status in _PERIKSA else "belum_terverifikasi"


def _sidik(data):
    """Identitas deterministik dari field terverifikasi; payload mentah tidak disimpan."""
    wajib = [data.get("order_id"), data.get("status_code"), data.get("transaction_status"),
             data.get("transaction_id")]
    if any(type(nilai) is not str or _POLA_WAJIB.fullmatch(nilai) is None for nilai in wajib):
        raise ValueError("field callback tidak sah")
    if _POLA_KODE.fullmatch(data["status_code"]) is None:
        raise ValueError("status code callback tidak sah")
    fraud = data.get("fraud_status") or ""
    if type(fraud) is not str or fraud not in ("", "accept", "challenge", "deny"):
        raise ValueError("fraud status callback tidak sah")
    return hashlib.sha256("|".join(wajib + [fraud]).encode("ascii")).hexdigest()[:32]


def _simpan(path_admin, invoice_id, status, sidik, sekarang, sakelar):
    """Hint untuk invoice existing; order asing tidak membuat apa pun."""
    with admin_store.buka_baca(path_admin) as kon:
        baris = kon.execute("SELECT akun_id FROM langganan_invoice WHERE invoice_id=?",
                            (invoice_id,)).fetchone()
    if baris is None:
        return False
    store.catat_pengamatan(path_admin, baris[0], invoice_id, operasi_id="cbk_" + sidik,
                           status=status, sekarang=sekarang, sakelar=sakelar)
    return True
