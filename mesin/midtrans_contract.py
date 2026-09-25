"""Kontrak Core API QRIS tanpa implementasi jaringan/SDK/env credential.

Transport WAJIB diinjeksi dan dilarang mengikuti redirect. Modul ini tidak membuka
socket. Callback hanya memberi petunjuk untuk query status; signature tidak
mengautentikasi transaction_status. Tidak ada endpoint callback atau refund nyata.
"""

import base64
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import re
from typing import Optional
from urllib.parse import urlsplit

import subscription as d

BATAS_RESPONS = 128_000
HOST_API = {"sandbox": "api.sandbox.midtrans.com", "production": "api.midtrans.com"}
HOST_QR = {"sandbox": ("api.sandbox.midtrans.com", "api.midtrans.com"),
           "production": ("api.midtrans.com",)}


class KontrakTidakSah(ValueError):
    """Respons/permintaan tidak memenuhi kontrak; jangan mencatat payload."""


@dataclass(frozen=True, repr=False)
class Konfigurasi:
    lingkungan: str
    server_key: str = field(repr=False)
    merchant: str

    def __post_init__(self):
        if (self.lingkungan not in HOST_API or type(self.server_key) is not str
                or not self.server_key or len(self.server_key) > 256
                or any(ord(c) < 33 or ord(c) > 126 or c == ":" for c in self.server_key)):
            raise KontrakTidakSah("konfigurasi provider tidak sah")
        _referensi(self.merchant)

    def __repr__(self):
        return "Konfigurasi(Midtrans, rahasia disembunyikan)"

    @property
    def base_url(self):
        return "https://" + HOST_API[self.lingkungan]

    def authorization(self):
        return "Basic " + base64.b64encode((self.server_key + ":").encode()).decode("ascii")


@dataclass(frozen=True)
class Permintaan:
    metode: str
    url: str = field(repr=False)
    headers: dict = field(repr=False)
    body: Optional[bytes] = field(default=None, repr=False)


@dataclass(frozen=True)
class Hasil:
    status: str = "belum_terverifikasi"
    bukti: Optional[d.Pembayaran] = field(default=None, repr=False)
    qr: Optional[str] = field(default=None, repr=False)


def _referensi(nilai):
    if type(nilai) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", nilai) is None:
        raise KontrakTidakSah("referensi provider tidak sah")
    return nilai


def payload_qris(order_id, rupiah):
    d.identitas(order_id, "invoice")
    d.bilangan(rupiah, 1)
    return {"payment_type": "qris", "transaction_details": {"order_id": order_id, "gross_amount": rupiah}}


def request_create(config, order_id, rupiah, idempotency_key):
    d.identitas(idempotency_key, "operasi")
    return Permintaan("POST", config.base_url + "/v2/charge",
                      {"Authorization": config.authorization(), "Content-Type": "application/json",
                       "Accept": "application/json", "Idempotency-Key": idempotency_key},
                      json.dumps(payload_qris(order_id, rupiah), separators=(",", ":")).encode())


def request_status(config, order_id):
    d.identitas(order_id, "invoice")
    return Permintaan("GET", config.base_url + "/v2/" + order_id + "/status",
                      {"Authorization": config.authorization(), "Accept": "application/json"})


def _json(mentah):
    def objek(pasangan):
        hasil = {}
        for k, v in pasangan:
            if k in hasil:
                raise KontrakTidakSah("field JSON duplikat")
            hasil[k] = v
        return hasil
    def konstanta(_):
        raise KontrakTidakSah("konstanta JSON tidak sah")
    if type(mentah) is not bytes or len(mentah) > BATAS_RESPONS:
        raise KontrakTidakSah("body provider tidak sah")
    try:
        hasil = json.loads(mentah.decode("utf-8"), object_pairs_hook=objek, parse_constant=konstanta)
        if type(hasil) is not dict:
            raise KontrakTidakSah("JSON provider bukan objek")
        return hasil
    except (ValueError, UnicodeError, RecursionError):
        raise KontrakTidakSah("JSON provider tidak sah") from None


def kirim(req, *, transport, timeout=10):
    """Transport memberi context-manager(status,url,headers,read(n)); tanpa fallback.

    Transport wajib mematuhi timeout, read maksimum dan allow_redirects=False.
    Status HTTP DAN final URL diperiksa, termasuk redirect yang diikuti transport
    keliru. Tidak meneruskan exception/header/body/Server Key ke log pemanggil.
    """
    d.bilangan(timeout, 1, 15)
    if not callable(transport):
        raise KontrakTidakSah("transport wajib diinjeksi")
    try:
        with transport(req, timeout=timeout, allow_redirects=False) as respons:
            if respons.status != 200 or respons.url != req.url:
                raise KontrakTidakSah("transport belum terverifikasi")
            if respons.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise KontrakTidakSah("tipe respons tidak sah")
            panjang = respons.headers.get("Content-Length")
            if panjang is not None and (not re.fullmatch(r"[0-9]{1,9}", panjang) or int(panjang) > BATAS_RESPONS):
                raise KontrakTidakSah("respons terlalu besar")
            return _json(respons.read(BATAS_RESPONS + 1))
    except Exception:
        raise KontrakTidakSah("respons provider belum terverifikasi") from None


def nominal_provider(nilai):
    if type(nilai) not in (str, int) or re.fullmatch(r"(?:0|[1-9][0-9]{0,7})(?:\.00)?", str(nilai)) is None:
        raise KontrakTidakSah("nominal provider tidak sah")
    return d.bilangan(int(str(nilai).split(".")[0]))


def _binding(data, *, invoice, merchant):
    if (data.get("order_id") != invoice["invoice_id"]
            or nominal_provider(data.get("gross_amount")) != invoice["rupiah"]
            or data.get("currency") != "IDR" or data.get("payment_type") != "qris"
            or data.get("merchant_id") != merchant
            or invoice["merchant"] != merchant or invoice["provider"] != "midtrans"
            or invoice["channel"] != "qris"):
        raise KontrakTidakSah("binding pembayaran tidak cocok")
    return _referensi(data.get("transaction_id"))


def periksa_status(config, invoice, *, akun_id, transport, transaksi_id=None, sakelar=d.SAKELAR):
    sakelar.wajib("rekonsiliasi")
    if invoice["akun_id"] != akun_id:
        raise LookupError("invoice tidak ditemukan")
    try:
        data = kirim(request_status(config, invoice["invoice_id"]), transport=transport)
        transaksi = _binding(data, invoice=invoice, merchant=config.merchant)
        if transaksi_id is not None and transaksi != transaksi_id:
            raise KontrakTidakSah("identitas transaksi berbeda")
        if (data.get("transaction_status") == "settlement" and data.get("status_code") == "200"
                and data.get("fraud_status") in (None, "accept")):
            return Hasil("lunas", d.Pembayaran("midtrans", transaksi, invoice["invoice_id"], akun_id,
                         invoice["rupiah"], "IDR", "qris", config.merchant, "settlement", True))
        if (data.get("transaction_status") == "pending" and data.get("status_code") == "201"
                and data.get("fraud_status") in (None, "accept")):
            # GET tidak mengembalikan actions; endpoint gambar Core v2 memakai
            # transaction_id terverifikasi, bukan URL/ID dari input browser.
            return Hasil("pending", qr=config.base_url + "/v2/qris/" + transaksi + "/qr-code")
        if data.get("transaction_status") in ("refund", "partial_refund"):
            return Hasil("perlu_diperiksa")
        return Hasil()
    except (ValueError, TypeError, KeyError, AttributeError):
        return Hasil()


def buat_pembayaran(config, invoice, *, akun_id, transport, sakelar=d.SAKELAR):
    sakelar.wajib("buat_pembayaran")
    if invoice["akun_id"] != akun_id:
        raise LookupError("invoice tidak ditemukan")
    try:
        req = request_create(config, invoice["invoice_id"], invoice["rupiah"], invoice["idempotency_key"])
        data = kirim(req, transport=transport)
        _binding(data, invoice=invoice, merchant=config.merchant)
        # Create tidak pernah memberikan grant; wajib query status terautentikasi.
        for aksi in data.get("actions", []):
            if (type(aksi) is dict and aksi.get("name") == "generate-qr-code"
                    and aksi.get("method") == "GET" and url_qr_sah(aksi.get("url"), config.lingkungan)):
                return Hasil(qr=aksi["url"])
    except (ValueError, TypeError, KeyError, AttributeError):
        pass
    return Hasil()


def signature_cocok(mentah, config):
    """Hanya autentikasi petunjuk order, bukan bukti lunas/refund."""
    try:
        data = _json(mentah)
        for k in ("order_id", "status_code", "gross_amount"):
            if type(data.get(k)) is not str:
                return False
        d.identitas(data["order_id"], "invoice")
        nominal_provider(data["gross_amount"])
        aktual = data.get("signature_key")
        if type(aktual) is not str or re.fullmatch(r"[0-9a-fA-F]{128}", aktual) is None:
            return False
        teks = data["order_id"] + data["status_code"] + data["gross_amount"] + config.server_key
        return hmac.compare_digest(aktual.lower(), hashlib.sha512(teks.encode()).hexdigest())
    except (ValueError, TypeError):
        return False


def url_qr_sah(url, lingkungan):
    if type(url) is not str or lingkungan not in HOST_QR or re.search(r"[\s\\%]", url):
        return False
    try:
        hasil = urlsplit(url)
        return (hasil.scheme == "https" and hasil.hostname in HOST_QR[lingkungan]
                and hasil.username is None and hasil.password is None and not hasil.fragment
                and not hasil.query and hasil.port in (None, 443)
                and re.fullmatch(r"/v[24]/qris/[A-Za-z0-9_-]+/qr-code", hasil.path) is not None)
    except ValueError:
        return False


@dataclass(frozen=True)
class Refund:
    kunci: str
    identitas: str
    rupiah: int
    bank_terkonfirmasi: bool


def ringkas_refund(data, *, rupiah):
    """Snapshot kumulatif, bukan perintah refund atau penetapan kebijakan D8."""
    d.bilangan(rupiah, 1)
    kumulatif = nominal_provider(data.get("refund_amount", 0))
    daftar = data.get("refunds", [])
    if type(daftar) is not list or not 0 <= kumulatif <= rupiah:
        raise KontrakTidakSah("refund tidak sah")
    hasil, kunci, identitas = [], set(), set()
    for item in daftar:
        if type(item) is not dict:
            raise KontrakTidakSah("refund tidak sah")
        key = _referensi(item.get("refund_key"))
        rid = item.get("refund_chargeback_id")
        if type(rid) not in (str, int):
            raise KontrakTidakSah("identitas refund tidak sah")
        rid = _referensi(str(rid))
        if key in kunci or rid in identitas:
            raise KontrakTidakSah("identitas refund duplikat")
        kunci.add(key)
        identitas.add(rid)
        amount = nominal_provider(item.get("refund_amount"))
        if amount <= 0:
            raise KontrakTidakSah("nominal refund tidak sah")
        confirmed = item.get("bank_confirmed_at")
        if confirmed is not None and (type(confirmed) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", confirmed) is None):
            raise KontrakTidakSah("waktu refund tidak sah")
        hasil.append(Refund(key, rid, amount, confirmed is not None))
    if sum(r.rupiah for r in hasil) != kumulatif:
        raise KontrakTidakSah("refund kumulatif tidak cocok")
    return tuple(hasil)


def delta_refund(terbaru, sebelumnya=()):
    """Deduplikasi snapshot ulang; perubahan identitas/nominal ditahan untuk review."""
    for daftar in (terbaru, sebelumnya):
        if (type(daftar) is not tuple or any(type(r) is not Refund for r in daftar)
                or len({r.kunci for r in daftar}) != len(daftar)
                or len({r.identitas for r in daftar}) != len(daftar)):
            raise KontrakTidakSah("snapshot refund duplikat")
        for r in daftar:
            _referensi(r.kunci)
            _referensi(r.identitas)
            d.bilangan(r.rupiah, 1)
            if type(r.bank_terkonfirmasi) is not bool:
                raise KontrakTidakSah("konfirmasi refund tidak sah")
    lama = {r.kunci: r for r in sebelumnya}
    baru = {r.kunci: r for r in terbaru}
    if not lama.keys() <= baru.keys():
        raise KontrakTidakSah("snapshot refund mundur")
    for key, r in lama.items():
        b = baru[key]
        if r.identitas != b.identitas or r.rupiah != b.rupiah or (r.bank_terkonfirmasi and not b.bank_terkonfirmasi):
            raise KontrakTidakSah("snapshot refund berubah")
    return sum(r.rupiah for r in terbaru if r.bank_terkonfirmasi) - sum(r.rupiah for r in sebelumnya if r.bank_terkonfirmasi)
