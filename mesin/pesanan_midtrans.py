"""Adapter + klien order Midtrans untuk pesanan `ord_` (tanpa jaringan sendiri).

Memakai ulang klien kontrak `midtrans_contract` (request create/status, `kirim`,
`_binding`, validasi URL QR) dan transport yang diinjeksi. Tidak memakai
`periksa_status`/`status_ulang`/`buat_pembayaran` kontrak: itu terikat tabel
langganan (`Pembayaran`, sakelar langganan, `invoice_id`). Gerbang pembayaran
(`pesanan.gerbang_pembayaran`) adalah urusan pemanggil, bukan modul ini.

Nominal HANYA dari baris order (`order["rupiah"]`); tidak ada parameter nominal.
Kegagalan selalu hasil eksplisit (`galat_kode` dari enum kecil), tidak pernah
None/kosong diam-diam. Pesan tidak memuat id, nominal, atau secret.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Optional

import midtrans_contract as m
import pesanan_dasar as d
import pesanan_provider as pp

GALAT_PROVIDER = "provider_gagal"        # transport/status HTTP/JSON/tipe respons tidak sah
GALAT_BINDING = "binding_tidak_cocok"    # respons create tidak cocok dengan order
GALAT_QR = "qr_tidak_tersedia"           # create sah tetapi tanpa URL QR sah
GALAT_ORDER = "order_tidak_cocok"        # order_id di dalam respons status beda
GALAT_GAMBAR = "gambar_tidak_sah"        # PNG/URL QR ditolak
KODE_GALAT = (GALAT_PROVIDER, GALAT_BINDING, GALAT_QR, GALAT_ORDER, GALAT_GAMBAR)
PESAN = {GALAT_PROVIDER: "provider pembayaran belum terverifikasi",
         GALAT_BINDING: "respons pembayaran tidak cocok dengan pesanan",
         GALAT_QR: "QR pembayaran belum tersedia",
         GALAT_ORDER: "respons status tidak terikat ke pesanan",
         GALAT_GAMBAR: "gambar QR tidak sah"}

# Kunci respons status yang diteruskan ke `pesanan.terapkan_hasil_provider`.
KUNCI_HASIL = ("order_id", "transaction_status", "status_code", "transaction_id",
               "gross_amount", "merchant_id", "currency", "payment_type", "fraud_status")
_POLA_KUNCI_OPERASI = re.compile(r"[A-Za-z0-9_-]{8,46}")  # sama dengan pola kontrak


@dataclass(frozen=True)
class HasilBuat:
    ok: bool
    transaksi_id: Optional[str] = None
    url_qr: Optional[str] = field(default=None, repr=False)
    kedaluwarsa: Optional[str] = None
    galat_kode: Optional[str] = None

    @property
    def pesan(self):
        return None if self.galat_kode is None else PESAN[self.galat_kode]


@dataclass(frozen=True)
class HasilStatus:
    ok: bool
    hasil_provider: Optional[dict] = field(default=None, repr=False)
    tanpa_transaksi: bool = False
    galat_kode: Optional[str] = None

    @property
    def mati(self):
        """Provider menyatakan expire/cancel/deny: dasar 'buat ulang' (keputusan di pemanggil)."""
        data = self.hasil_provider or {}
        return data.get("transaction_status") in m.KELAS_MATI

    @property
    def pesan(self):
        return None if self.galat_kode is None else PESAN[self.galat_kode]


def _gagal_buat(kode, transaksi_id=None):
    return HasilBuat(False, transaksi_id=transaksi_id, galat_kode=kode)


def susun_binding(order):
    """Dict `invoice` untuk `_binding` dari baris order; salah satu kunci rusak -> PesananDataTidakSah."""
    if not isinstance(order, dict):
        raise d.PesananDataTidakSah("order tidak sah")
    try:
        rupiah, kunci = order["rupiah"], order["idempotency_key"]
        order_id, akun_id = order["order_id"], order["akun_id"]
        merchant, provider, channel = order["merchant"], order["provider"], order["channel"]
    except KeyError:
        raise d.PesananDataTidakSah("order tidak lengkap") from None
    d.periksa_order_id(order_id)
    d.periksa_akun_id(akun_id)
    d.periksa_referensi(merchant, "merchant")
    d.periksa_bilangan(rupiah, "rupiah")
    if rupiah > pp.BATAS_NOMINAL:
        raise d.PesananDataTidakSah("rupiah tidak sah")
    if (provider != d.PROVIDER or channel != d.CHANNEL or type(kunci) is not str
            or _POLA_KUNCI_OPERASI.fullmatch(kunci) is None):
        raise d.PesananDataTidakSah("order tidak sah")
    return {"invoice_id": order_id, "rupiah": rupiah, "merchant": merchant,
            "provider": provider, "channel": channel, "akun_id": akun_id,
            "idempotency_key": kunci}


def _url_qr(data, lingkungan):
    for aksi in data.get("actions", []):
        if (type(aksi) is dict and aksi.get("name") == "generate-qr-code"
                and aksi.get("method") == "GET" and m.url_qr_sah(aksi.get("url"), lingkungan)):
            return aksi["url"]
    return None


def buat_order_pembayaran(transport, order, *, config):
    """Create QRIS untuk satu order lalu ambil URL QR. Tidak melempar karena provider."""
    binding = susun_binding(order)
    kedaluwarsa = d.waktu_baku(order.get("kedaluwarsa"))
    if binding["merchant"] != config.merchant:
        return _gagal_buat(GALAT_BINDING)
    req = m.request_create(config, binding["invoice_id"], binding["rupiah"],
                           binding["idempotency_key"])
    try:
        data = m.kirim(req, transport=transport)
    except m.KontrakTidakSah:
        return _gagal_buat(GALAT_PROVIDER)
    try:
        transaksi = m._binding(data, invoice=binding, merchant=config.merchant)
        url = _url_qr(data, config.lingkungan)
    except (ValueError, TypeError, AttributeError):
        return _gagal_buat(GALAT_BINDING)
    if url is None:
        return _gagal_buat(GALAT_QR, transaksi)
    return HasilBuat(True, transaksi_id=transaksi, url_qr=url, kedaluwarsa=kedaluwarsa)


def _hasil_provider(data):
    """Salinan baru hanya berisi kunci yang dipakai ledger, bernilai skalar str/int."""
    return {k: data[k] for k in KUNCI_HASIL if type(data.get(k)) in (str, int)}


def periksa_status_order(transport, order, *, config):
    """Status server-ke-server satu order; `hasil_provider` siap ke `terapkan_hasil_provider`.

    Nominal/merchant tidak dibandingkan di sini: ketidakcocokan harus sampai ke
    ledger agar menjadi `perlu_diperiksa`, bukan hilang sebagai galat.
    """
    binding = susun_binding(order)
    try:
        data = m.kirim(m.request_status(config, binding["invoice_id"]), transport=transport)
    except m.KontrakTidakSah:
        return HasilStatus(False, galat_kode=GALAT_PROVIDER)
    if m.tanpa_transaksi_sentinel(data, binding):
        return HasilStatus(True, tanpa_transaksi=True)
    if data.get("order_id") != binding["invoice_id"]:
        return HasilStatus(False, galat_kode=GALAT_ORDER)
    return HasilStatus(True, hasil_provider=_hasil_provider(data))


def ambil_gambar_qr(transport, url, *, lingkungan="production"):
    """PNG QR lewat `transport.gambar`; URL wajib lolos allow-list kontrak. Gagal -> KontrakTidakSah."""
    if not m.url_qr_sah(url, lingkungan) or not url.startswith(
            "https://" + m.HOST_API[lingkungan] + "/v2/qris/"):
        raise m.KontrakTidakSah(PESAN[GALAT_GAMBAR])
    fungsi = getattr(transport, "gambar", None)
    if not callable(fungsi):
        raise m.KontrakTidakSah(PESAN[GALAT_GAMBAR])
    return fungsi(url)


@dataclass(frozen=True, repr=False)
class KlienOrder:
    """Pembungkus tipis config+transport dari runtime pembayaran yang sudah ada."""
    config: object
    transport: object

    def __repr__(self):
        return "KlienOrder(rahasia disembunyikan)"

    def buat(self, order):
        return buat_order_pembayaran(self.transport, order, config=self.config)

    def status(self, order):
        return periksa_status_order(self.transport, order, config=self.config)

    def gambar(self, url):
        return ambil_gambar_qr(self.transport, url, lingkungan=self.config.lingkungan)


def dari_runtime(runtime):
    """KlienOrder dari `RuntimePembayaran` (config + transport); selain itu PesananDataTidakSah."""
    config, transport = getattr(runtime, "config", None), getattr(runtime, "transport", None)
    if type(config) is not m.Konfigurasi or not callable(transport):
        raise d.PesananDataTidakSah("runtime pembayaran tidak sah")
    return KlienOrder(config, transport)
