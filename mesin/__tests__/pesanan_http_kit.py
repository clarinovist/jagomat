"""Pembantu bersama tes HTTP pesanan (Fase 3c-3): server loopback, runtime + provider PALSU.

Tanpa jaringan nyata dan tanpa rahasia nyata: runtime pembayaran disuntik ke server uji,
transport hanya objek Python. `server._pembayaran_dicoba = True` mencegah dispatcher
mencoba memasang runtime dari berkas rahasia sungguhan. Soket tidak dilarang karena
server uji memakai loopback.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import admin_subscription  # noqa: E402
import kontak_akun  # noqa: E402
import midtrans_contract as m  # noqa: E402
import pesanan  # noqa: E402
import pesanan_alur  # noqa: E402
import pesanan_dasar  # noqa: E402
import pesanan_http  # noqa: E402
import schema_pesanan  # noqa: E402
import sessions  # noqa: E402
import subscription as d  # noqa: E402
from cek_http_kit import (  # noqa: E402,F401
    AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, HASIL, MULAI, NAMA_A, NAMA_B, POLA_TOKEN,
    id_akun, jumlah, keluarga, mulai_cek, minta_mentah, selesaikan, server, tambah_anak,
)

MERCHANT = "M_SINTETIS"
CFGP = m.Konfigurasi("production", "SB-Mid-server-sintetis-0001", MERCHANT)
SIAP = {"provider_produksi": True, "callback": True, "recovery": True, "kebijakan": True}
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (64).to_bytes(4, "big") + (64).to_bytes(4, "big")
       + b"\x08\x02\x00\x00\x00" + b"\x00" * 4)
WA_SINTETIS = "6281234567890"
WAKTU_AWAL = "2026-11-18T10:00:00"
PESAN = "/paket-coba/pesan"
STATUS = "/pesanan"
QR = "/pesanan/qr"
PERIKSA = "/pesanan/periksa"
ULANG = "/pesanan/ulang"
BUAT = "/pesanan/buat"
TABEL_PESANAN = schema_pesanan.TABEL


class Respons:
    def __init__(self, data, *, kode=200):
        self.data = json.dumps(data).encode()
        self.status, self.url = kode, None
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, batas):
        return self.data[:batas]


class Jam:
    """Jam sintetis untuk `pesanan_alur._sekarang` (naik dengan `maju_jam`)."""

    def __init__(self):
        self.nilai = WAKTU_AWAL

    def __call__(self):
        return self.nilai

    def maju_jam(self, jam):
        self.nilai = pesanan_dasar.tambah_jam(self.nilai, jam)


class ProviderPalsu:
    """Transport palsu: create/status/gambar dikendalikan tes; semua panggilan dicatat."""

    def __init__(self):
        self.panggilan = []
        self.mode_create = "ok"        # ok | gagal | tanpa_qr
        self.transaksi = {}            # order_id -> transaksi_id terbaru yang dibuat
        self.kunci_create = []         # header Idempotency-Key tiap create
        self.status_data = None        # None -> pending jendela terbaru; callable(order_id) -> dict|Exception
        self.url_gambar = []

    @property
    def jumlah_create(self):
        return sum(1 for r in self.panggilan if r.metode == "POST")

    @property
    def jumlah_status(self):
        return sum(1 for r in self.panggilan if r.metode == "GET")

    def __call__(self, req, *, timeout, allow_redirects):
        self.panggilan.append(req)
        hasil = self._create(req) if req.metode == "POST" else self._status(req)
        if isinstance(hasil, Exception):
            raise hasil
        hasil.url = req.url
        return hasil

    def _create(self, req):
        isi = json.loads(req.body)["transaction_details"]
        kunci = req.headers["Idempotency-Key"]
        self.kunci_create.append(kunci)
        if self.mode_create == "gagal":
            return Respons({}, kode=500)
        transaksi = "trx-" + hashlib.sha1(kunci.encode()).hexdigest()[:12]
        self.transaksi[isi["order_id"]] = transaksi
        data = data_status(isi["order_id"], transaksi)
        if self.mode_create == "ok":
            data["actions"] = [{"name": "generate-qr-code", "method": "GET",
                                "url": url_qr(transaksi)}]
        return Respons(data)

    def _status(self, req):
        order_id = req.url.split("/")[-2]
        if self.status_data is not None:
            data = self.status_data(order_id)
            return data if isinstance(data, (Exception, Respons)) else Respons(data)
        transaksi = self.transaksi.get(order_id)
        if transaksi is None:
            return Respons({"id": order_id, "status_code": "404",
                            "status_message": "Transaction doesn't exist."})
        return Respons(data_status(order_id, transaksi))

    def gambar(self, url):
        self.url_gambar.append(url)
        return PNG


def url_qr(transaksi):
    return "https://api.midtrans.com/v2/qris/%s/qr-code" % transaksi


def data_status(order_id, transaksi, **ganti):
    """Respons status Midtrans sintetis (default: pending QRIS Rp49.000 untuk order ini)."""
    data = {"order_id": order_id, "transaction_id": transaksi, "gross_amount": "49000.00",
            "currency": "IDR", "payment_type": "qris", "merchant_id": MERCHANT,
            "status_code": "201", "transaction_status": "pending", "status_message": "ok"}
    data.update(ganti)
    return {k: v for k, v in data.items() if v is not None}


def settlement(order_id, transaksi, **ganti):
    return data_status(order_id, transaksi, status_code="200", transaction_status="settlement",
                       fraud_status="accept", **ganti)


def atur_tahap(tahap):
    with admin_store._transaksi(admin_store.BAWAAN) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap=?", (tahap,))


def pasang_runtime(server, provider, *, kesiapan=None):
    server.server._pembayaran_dicoba = True
    server.server.pembayaran_runtime = admin_subscription.RuntimePembayaran(
        CFGP, provider, d.Sakelar(True, True, True, False), dict(SIAP if kesiapan is None else kesiapan))


@pytest.fixture()
def jam(monkeypatch):
    waktu = Jam()
    monkeypatch.setattr(pesanan_alur, "_sekarang", waktu)
    return waktu


@pytest.fixture()
def tertutup(keluarga, monkeypatch, jam):
    """Server dengan FUNNEL_AKTIF=1 tetapi TANPA runtime pembayaran (gerbang tertutup)."""
    monkeypatch.setattr(pesanan_http, "_laju", {})
    schema_pesanan.migrasikan(admin_store.BAWAAN)
    keluarga.server._pembayaran_dicoba = True
    keluarga.provider = ProviderPalsu()
    return keluarga


@pytest.fixture()
def bayar(tertutup):
    """Gerbang pembayaran terbuka: FUNNEL_AKTIF=1 + runtime siap + tahap checkout."""
    atur_tahap("checkout")
    pasang_runtime(tertutup, tertutup.provider)
    return tertutup


def principal_basic_untuk(akun):
    principal = sessions.principal_basic(*akun)
    assert principal is not None
    return principal


def token(akun, aksi, sesi=None):
    return pesanan_http.buat_token(principal_basic_untuk(akun), sesi, aksi)


def kirim(server, jalur, akun=AKUN_A, *, aksi=None, tok=None, ekstra=None, hapus=()):
    """POST form dengan token sah (kecuali `tok` diberikan); `hapus` membuang field."""
    data = {"token": token(akun, aksi or pesanan_http.AKSI_RUTE[jalur]) if tok is None else tok}
    data.update(ekstra or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return minta_mentah(server, jalur, akun, data)


def simpan_kontak(server, akun=AKUN_A):
    with server.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        kontak_akun.simpan(kon, id_akun(akun), WA_SINTETIS, "2026-11-18T09:00:00")
        kon.commit()


def cek_selesai(server, akun=AKUN_A):
    """Mulai cek lewat HTTP, jawab 10 dari 15, tutup sesi, lalu skor tersimpan lewat halaman hasil."""
    sesi_id = mulai_cek(server, akun)
    selesaikan(server, sesi_id, semua_benar=10)
    assert minta_mentah(server, HASIL, akun)[0] == 200


def siap_pesan(server, akun=AKUN_A):
    """Cek selesai + kontak WA: akun siap memesan."""
    cek_selesai(server, akun)
    simpan_kontak(server, akun)


def pesan(server, akun=AKUN_A, **kw):
    return kirim(server, PESAN, akun, **kw)


def ledger():
    return pesanan.buka(admin_store.BAWAAN, tulis_data=True)


def hitung_ledger(tabel):
    with ledger() as kon:
        return kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]


def keadaan_ledger():
    with ledger() as kon:
        return {t: kon.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in TABEL_PESANAN}


KOSONG = {t: 0 for t in TABEL_PESANAN}


def satu_order():
    with ledger() as kon:
        return dict(kon.execute("SELECT * FROM pesanan_order").fetchone())


def tabel_langganan():
    with ledger() as kon:
        nama = [r[0] for r in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "(name GLOB 'langganan_*' OR name GLOB 'paket_*') ORDER BY name")]
        return {n: tuple(tuple(r) for r in kon.execute('SELECT * FROM "%s"' % n)) for n in nama}


def teks_tampak(isi: str) -> str:
    import re
    badan = isi.rsplit("</style>", 1)[1] if "</style>" in isi else isi
    badan = re.sub(r"<script.*?</script>", " ", badan, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", badan))
