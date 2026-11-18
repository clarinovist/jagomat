"""Regresi 3b: request langganan `inv_` byte-identik, allow-list transport `ord_`, langganan menolak `ord_`.

Golden di bawah dihasilkan dari kode SEBELUM perubahan (skrip sementara di luar repo)
dan ditanam sebagai konstanta; bukan dibaca dari berkas. Tanpa jaringan nyata.
"""
from __future__ import annotations

import hashlib
import json
import socket

import pytest

import midtrans_contract as m
import midtrans_produksi as p
import subscription as d
import subscription_store as store
from pesanan_kit import AKUN_A, siapkan_db

INV = "inv_" + "0123456789abcdef" * 2
ORD = "ord_" + "0123456789abcdef" * 2
KUNCI = "op_ab12cd34ef56ab78"
KUNCI_ORDER = "ord-" + "0123456789abcdef" * 2
MERCHANT = "M_SINTETIS"
KUNCI_SERVER = "SB-Mid-server-sintetis-0001"
CFGP = m.Konfigurasi("production", KUNCI_SERVER, MERCHANT)
AUTH = "Basic U0ItTWlkLXNlcnZlci1zaW50ZXRpcy0wMDAxOg=="
HEX = "0123456789abcdef" * 2

BODY_CREATE_INV = (b'{"payment_type":"qris","transaction_details":{"order_id":"inv_'
                   + HEX.encode() + b'","gross_amount":25000}}')
BODY_HEX_CREATE_INV = (
    "7b227061796d656e745f74797065223a2271726973222c227472616e73616374696f6e5f64657461696c73"
    "223a7b226f726465725f6964223a22696e765f30313233343536373839616263646566303132333435363738"
    "39616263646566222c2267726f73735f616d6f756e74223a32353030307d7d")
# SHA-256 atas JSON kanonis (sort_keys, tanpa spasi) dari seluruh request create/status
# sandbox+produksi untuk INV dan hasil `_validasi` transport produksi.
SIDIK_GOLDEN = "eec83c0677f5cdaea0fce46663fa8655652a2a875e479202b803593022c77aaa"


@pytest.fixture(autouse=True)
def tanpa_jaringan(monkeypatch):
    def dilarang(*a, **kw):
        pytest.fail("socket/network tidak boleh dipanggil")
    for nama in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, nama, dilarang)
    monkeypatch.setattr(p.http.client, "HTTPSConnection", dilarang)


def _bentuk(req):
    return {"metode": req.metode, "url": req.url, "headers": dict(sorted(req.headers.items())),
            "body_hex": None if req.body is None else req.body.hex()}


def _bangun_golden():
    hasil = {}
    for lingkungan in ("sandbox", "production"):
        cfg = m.Konfigurasi(lingkungan, KUNCI_SERVER, MERCHANT)
        hasil[lingkungan] = {"create": _bentuk(m.request_create(cfg, INV, 25000, KUNCI)),
                             "status": _bentuk(m.request_status(cfg, INV))}
    transport = p.TransportProduksi(CFGP)
    hasil["validasi_path"] = {
        "create": transport._validasi(m.request_create(CFGP, INV, 25000, KUNCI), 10, False),
        "status": transport._validasi(m.request_status(CFGP, INV), 10, False)}
    return hasil


# --- (a) request langganan inv_ byte-identik ---------------------------------------

def test_request_create_inv_byte_identik_dengan_golden():
    req = m.request_create(CFGP, INV, 25000, KUNCI)
    assert req.metode == "POST" and req.url == "https://api.midtrans.com/v2/charge"
    assert req.body == BODY_CREATE_INV and req.body.hex() == BODY_HEX_CREATE_INV
    assert req.headers == {"Authorization": AUTH, "Content-Type": "application/json",
                           "Accept": "application/json", "Idempotency-Key": KUNCI}
    assert list(req.headers) == ["Authorization", "Content-Type", "Accept", "Idempotency-Key"]


def test_request_status_inv_byte_identik_dengan_golden():
    req = m.request_status(CFGP, INV)
    assert req.metode == "GET" and req.body is None
    assert req.url == "https://api.midtrans.com/v2/" + INV + "/status"
    assert req.headers == {"Authorization": AUTH, "Accept": "application/json"}
    assert list(req.headers) == ["Authorization", "Accept"]


def test_sidik_golden_gabungan_request_inv_tidak_berubah():
    kanonis = json.dumps(_bangun_golden(), sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(kanonis).hexdigest() == SIDIK_GOLDEN


def test_request_ord_memakai_bentuk_yang_sama_selain_id():
    ord_req = m.request_create(CFGP, ORD, 49000, KUNCI_ORDER)
    inv_req = m.request_create(CFGP, INV, 49000, KUNCI_ORDER)
    assert ord_req.body == inv_req.body.replace(b"inv_", b"ord_")
    assert (ord_req.url, ord_req.headers) == (inv_req.url, inv_req.headers)
    assert m.request_status(CFGP, ORD).url == "https://api.midtrans.com/v2/" + ORD + "/status"


# --- (b) allow-list transport --------------------------------------------------------

def _masuk(transport, req):
    with transport(req, timeout=10, allow_redirects=False):
        pass


def _ditolak(req):
    with pytest.raises(m.KontrakTidakSah):
        _masuk(p.TransportProduksi(CFGP), req)


def _get(url):
    return m.Permintaan("GET", url, {"Authorization": AUTH, "Accept": "application/json"})


def test_validasi_menerima_ord_dan_inv_untuk_status_dan_create():
    transport = p.TransportProduksi(CFGP)
    assert transport._validasi(m.request_status(CFGP, ORD), 10, False) == "/v2/" + ORD + "/status"
    assert transport._validasi(m.request_status(CFGP, INV), 10, False) == "/v2/" + INV + "/status"
    assert transport._validasi(m.request_create(CFGP, ORD, 49000, KUNCI_ORDER), 10, False) == "/v2/charge"
    assert transport._validasi(m.request_create(CFGP, INV, 25000, KUNCI), 10, False) == "/v2/charge"


@pytest.mark.parametrize("id_salah", [
    "ord_" + "a" * 31, "ord_" + "a" * 33, "ord_" + "A" * 32, "ord_" + "g" * 32, "ord_",
    "ORD_" + "a" * 32, "Ord_" + "a" * 32, "inv" + "a" * 33, "ord-" + "a" * 32, " ord_" + "a" * 32,
    "xyz_" + "a" * 32, "ordd_" + "a" * 32, "ord_" + "a" * 32 + "x", "pay_" + "a" * 32,
    "ord_" + "a" * 32 + "\n", "ord_" + "a" * 32 + "/..", "../ord_" + "a" * 32,
])
def test_status_menolak_varian_id_salah(id_salah):
    _ditolak(_get("https://api.midtrans.com/v2/" + id_salah + "/status"))


@pytest.mark.parametrize("url", [
    "https://api.midtrans.com/v2/" + ORD + "/status?x=1",
    "https://api.midtrans.com/v2/" + ORD + "/status/",
    "https://api.midtrans.com/v2/" + ORD + "/status/extra",
    "https://api.midtrans.com/v2/" + ORD + "/cancel",
    "https://api.midtrans.com/v2/" + ORD + "/refund",
    "https://api.midtrans.com/v2/" + ORD + "/../" + ORD + "/status",
    "https://api.midtrans.com/v2/%6frd_" + "a" * 32 + "/status",
    "https://api.midtrans.com/v2/" + ORD + "%2f..%2fstatus",
    "https://api.midtrans.com/v3/" + ORD + "/status",
    "https://api.midtrans.com/" + ORD + "/status",
    "http://api.midtrans.com/v2/" + ORD + "/status",
    "https://api.sandbox.midtrans.com/v2/" + ORD + "/status",
    "https://api.midtrans.com.evil.test/v2/" + ORD + "/status",
    "https://user@api.midtrans.com/v2/" + ORD + "/status",
    "https://api.midtrans.com:444/v2/" + ORD + "/status",
])
def test_status_menolak_path_host_dan_query_tidak_kanonis(url):
    _ditolak(_get(url))


def test_get_dengan_header_atau_body_tambahan_ditolak():
    asli = m.request_status(CFGP, ORD)
    _ditolak(m.Permintaan("GET", asli.url, {**asli.headers, "X-Extra": "1"}))
    _ditolak(m.Permintaan("GET", asli.url, asli.headers, b"{}"))
    _ditolak(m.Permintaan("GET", asli.url, {"Accept": "application/json"}))


def test_create_menolak_path_bukan_charge_dan_metode_lain():
    asli = m.request_create(CFGP, ORD, 49000, KUNCI_ORDER)
    for url in ("https://api.midtrans.com/v2/charge?x=1", "https://api.midtrans.com/v2/charge/",
                "https://api.midtrans.com/v2/" + ORD + "/cancel",
                "https://api.midtrans.com/v2/" + ORD + "/status",
                "https://api.midtrans.com/v2/../v2/charge", "https://api.midtrans.com/v1/charge"):
        _ditolak(m.Permintaan("POST", url, asli.headers, asli.body))
    for metode in ("PUT", "DELETE", "PATCH", "get", "post"):
        _ditolak(m.Permintaan(metode, asli.url, asli.headers, asli.body))
    _ditolak(m.Permintaan("GET", asli.url, asli.headers))


def _badan_lain(asli):
    data = json.loads(asli.body)
    tambah = dict(data, customer_details={"phone": "08000000000"})
    cacat = dict(data, transaction_details={**data["transaction_details"], "gross_amount": "49000"})
    return [json.dumps(data).encode(),                                    # spasi default
            json.dumps(data, indent=1).encode(),
            json.dumps(tambah, separators=(",", ":")).encode(),            # field kontak
            json.dumps(cacat, separators=(",", ":")).encode(),             # tipe nominal beda
            asli.body + b" ", b" " + asli.body, asli.body + b"\n", asli.body[:-1]]


def test_create_menolak_body_tidak_byte_identik():
    asli = m.request_create(CFGP, ORD, 49000, KUNCI_ORDER)
    for badan in _badan_lain(asli):
        _ditolak(m.Permintaan("POST", asli.url, asli.headers, badan))
    _ditolak(m.Permintaan("POST", asli.url, asli.headers, None))


def test_create_menolak_header_tidak_kanonis_dan_kredensial_lain():
    asli = m.request_create(CFGP, ORD, 49000, KUNCI_ORDER)
    _ditolak(m.Permintaan("POST", asli.url, {**asli.headers, "X-Extra": "1"}, asli.body))
    _ditolak(m.Permintaan("POST", asli.url, {**asli.headers, "Idempotency-Key": "pendek"}, asli.body))
    lain = m.Konfigurasi("production", "SB-Mid-server-lain-0002", MERCHANT)
    _ditolak(m.request_create(lain, ORD, 49000, KUNCI_ORDER))


def test_create_menolak_order_id_prefix_salah_walau_body_konsisten():
    asli = m.request_create(CFGP, ORD, 49000, KUNCI_ORDER)
    for salah in ("ORD_" + HEX, "xyz_" + HEX, "ord_" + HEX[:-1], "ord_" + HEX + "0"):
        badan = asli.body.replace(ORD.encode(), salah.encode())
        _ditolak(m.Permintaan("POST", asli.url, asli.headers, badan))


def test_lapis_transport_berdiri_sendiri_menolak_prefix_lain(monkeypatch):
    """Kontrak dilonggarkan pun, regex transport tetap hanya inv_/ord_ (lapis ganda)."""
    def longgar(config, order_id):
        return m.Permintaan("GET", config.base_url + "/v2/" + order_id + "/status",
                            {"Authorization": config.authorization(), "Accept": "application/json"})
    monkeypatch.setattr(m, "request_status", longgar)
    transport = p.TransportProduksi(CFGP)
    for salah in ("xyz_" + HEX, "ORD_" + HEX, "ord_" + HEX[:-1], "ord_" + HEX + "0", "abc"):
        with pytest.raises(m.KontrakTidakSah):
            _masuk(transport, longgar(CFGP, salah))
    assert transport._validasi(longgar(CFGP, ORD), 10, False).endswith("/status")
    assert transport._validasi(longgar(CFGP, INV), 10, False).endswith("/status")


def test_kontrak_menolak_id_selain_inv_atau_ord():
    for salah in ("xyz_" + HEX, "ORD_" + HEX, "ord_" + HEX[:-1], "ord_" + HEX + "0",
                  "ord_" + HEX.upper(), "ord_" + HEX + "/..", "", None, 7):
        with pytest.raises(ValueError):
            m.request_status(CFGP, salah)
        with pytest.raises(ValueError):
            m.request_create(CFGP, salah, 49000, KUNCI_ORDER)
        with pytest.raises(ValueError):
            m.payload_qris(salah, 49000)


# --- (c) kode langganan menolak ord_ -------------------------------------------------

def test_identitas_langganan_menolak_ord_dan_tetap_menerima_inv():
    assert d.identitas(INV, "invoice") == INV
    with pytest.raises(ValueError):
        d.identitas(ORD, "invoice")
    with pytest.raises(ValueError):
        d.identitas(ORD.upper(), "invoice")


def test_signature_callback_menerima_ord_dan_inv():
    # 3c-2: kontrak berubah sengaja; signature `ord_` kini sah (cabang order callback).
    def mentah(order_id):
        sidik = hashlib.sha512((order_id + "200" + "49000.00" + KUNCI_SERVER).encode()).hexdigest()
        return json.dumps({"order_id": order_id, "status_code": "200",
                           "gross_amount": "49000.00", "signature_key": sidik}).encode()
    assert m.signature_cocok(mentah(INV), CFGP) is True
    assert m.signature_cocok(mentah(ORD), CFGP) is True


def test_store_langganan_menolak_ord_dan_tidak_menulis_baris(tmp_path):
    path = siapkan_db(tmp_path)
    on = d.Sakelar(True, True, True, False)
    with pytest.raises(ValueError):
        store.buat_invoice(path, AKUN_A, invoice_id=ORD, idempotency_key="idem_" + "c" * 32,
                           provider="midtrans", channel="qris", merchant=MERCHANT,
                           sekarang=1_000, kedaluwarsa=2_000, sakelar=on)
    with pytest.raises(ValueError):
        store.catat_pengamatan(path, AKUN_A, ORD, operasi_id="op-sintetis-0001",
                               status="belum_terverifikasi", sekarang=1_000, sakelar=on)
    with pytest.raises(ValueError):
        store.tutup_tagihan(path, AKUN_A, ORD, operasi_id="op-sintetis-0002", actor_id="admin_a",
                            actor_revisi=0, sekarang=1_000, sakelar=on)
    import sqlite3
    with sqlite3.connect(path) as kon:
        for tabel in ("langganan_invoice", "langganan_receipt", "langganan_grant",
                      "langganan_rekonsiliasi"):
            assert kon.execute("SELECT COUNT(*) FROM " + tabel).fetchone()[0] == 0
