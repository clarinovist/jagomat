"""Transport palsu saja; socket/DNS selalu dibuat gagal pada setiap test."""

import base64
from dataclasses import replace
import hashlib
import json
import socket

import pytest
import midtrans_contract as m
import subscription as d
from test_subscription import AKUN, INVOICE

CFG = m.Konfigurasi("sandbox", "kunci-sintetis-bukan-credential", "M_SINTETIS")
ON = d.Sakelar(True, True, True, False)
INV = dict(invoice_id=INVOICE, akun_id=AKUN, rupiah=15000, merchant="M_SINTETIS",
           provider="midtrans", channel="qris", idempotency_key="idem_" + "c" * 32)


@pytest.fixture(autouse=True)
def tanpa_jaringan(monkeypatch):
    def dilarang(*a, **kw):
        pytest.fail("socket/network tidak boleh dipanggil")
    for nama in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, nama, dilarang)


class Respons:
    def __init__(self, data, *, kode=200, url=None, headers=None):
        self.data = data if type(data) is bytes else json.dumps(data).encode()
        self.status = kode
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.ditutup = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.ditutup = True

    def read(self, batas):
        assert batas == m.BATAS_RESPONS + 1
        return self.data[:batas]


class Transport:
    def __init__(self, hasil):
        self.hasil = hasil
        self.panggilan = []

    def __call__(self, req, *, timeout, allow_redirects):
        assert timeout == 10 and allow_redirects is False
        self.panggilan.append(req)
        if isinstance(self.hasil, Exception):
            raise self.hasil
        self.hasil.url = self.hasil.url or req.url
        return self.hasil


def status(**kw):
    return dict(order_id=INVOICE, transaction_id="trx_sintetis", gross_amount="15000.00",
                currency="IDR", payment_type="qris", merchant_id="M_SINTETIS",
                status_code="200", transaction_status="settlement", **kw)


def periksa(data=None, **kw):
    transport = Transport(Respons(status() if data is None else data, **kw))
    return m.periksa_status(CFG, INV, akun_id=AKUN, transport=transport, sakelar=ON)


def test_payload_minimum_repr_dan_basic_auth_tidak_bocor(capsys):
    req = m.request_create(CFG, INVOICE, 15000, INV["idempotency_key"])
    assert json.loads(req.body) == {"payment_type": "qris", "transaction_details": {"order_id": INVOICE, "gross_amount": 15000}}
    assert req.headers["Authorization"] == "Basic " + base64.b64encode((CFG.server_key + ":").encode()).decode()
    assert CFG.server_key not in repr(CFG) + repr(req) + req.body.decode()
    assert "Authorization" not in repr(req)
    assert capsys.readouterr().out == ""
    for token in ("customer_details", "email", "phone", "username", "diagnosis", "jawaban", "token", AKUN):
        assert token not in req.body.decode()


@pytest.mark.parametrize("key", ["x"*47, "", None, "spasi tidak sah"])
def test_key_maksimal46(key):
    with pytest.raises(ValueError):
        m.request_create(CFG, INVOICE, 15000, key)


def test_key46_sah():
    assert m.request_create(CFG, INVOICE, 15000, "k"*46).headers["Idempotency-Key"] == "k"*46


@pytest.mark.parametrize("ubah", [{"transaction_status": "pending"}, {"transaction_status": "cancel"},
    {"transaction_status": "capture"}, {"status_code": "202"}, {"status_code": 200},
    {"fraud_status": "challenge"}, {"transaction_status": None}])
def test_http200_saja_bukan_lunas(ubah):
    data = status(); data.update(ubah)
    assert periksa(data).status == "belum_terverifikasi"
    assert periksa(data).bukti is None


@pytest.mark.parametrize("ubah", [{"order_id": "inv_"+"c"*32}, {"gross_amount": "15001.00"},
    {"currency": "USD"}, {"payment_type": "gopay"}, {"merchant_id": "asing"}, {"transaction_id": ""}])
def test_binding_nominal_order_currency_channel_merchant(ubah):
    data = status(); data.update(ubah)
    assert periksa(data).bukti is None


def test_settlement_terverifikasi_dan_owner_sebelum_transport():
    hasil = periksa()
    assert hasil.status == "lunas" and hasil.bukti.status == "settlement"
    tr = Transport(Respons(status()))
    with pytest.raises(LookupError):
        m.periksa_status(CFG, INV, akun_id="akun_"+"f"*32, transport=tr, sakelar=ON)
    assert tr.panggilan == []
    hasil = m.periksa_status(CFG, INV, akun_id=AKUN, transaksi_id="trx_asing", transport=tr, sakelar=ON)
    assert hasil.bukti is None


@pytest.mark.parametrize("kode", [201, 202, 301, 302, 307, 308, 401, 500, 503])
def test_http_non200_tidak_lunas(kode):
    assert periksa(kode=kode).bukti is None


@pytest.mark.parametrize("data", [b'{"status_code":"200","status_code":"200"}', b"[1]", b"not-json", b'{"x":NaN}', b"x"*(m.BATAS_RESPONS+1)])
def test_json_duplikat_malformed_ukuran_tidak_lunas(data):
    assert periksa(data).bukti is None


def test_redirect_ditolak_meski_transport_salah_mengikuti():
    assert periksa(url="https://evil.test/v2/status").bukti is None
    assert periksa(headers={"Content-Length": str(m.BATAS_RESPONS+1)}).bukti is None
    assert periksa(headers={"Content-Type": "text/html"}).bukti is None


def test_timeout_exception_tidak_mengekspos_key(capsys):
    tr = Transport(TimeoutError(CFG.server_key))
    hasil = m.periksa_status(CFG, INV, akun_id=AKUN, transport=tr, sakelar=ON)
    assert hasil == m.Hasil()
    assert CFG.server_key not in repr(hasil) + capsys.readouterr().out
    with pytest.raises(m.KontrakTidakSah) as e:
        m.kirim(m.request_status(CFG, INVOICE), transport=tr)
    assert CFG.server_key not in str(e.value)


def test_default_off_tidak_memanggil_transport():
    tr = Transport(Respons(status()))
    for fungsi in (m.buat_pembayaran, m.periksa_status):
        with pytest.raises(d.FiturNonaktif):
            fungsi(CFG, INV, akun_id=AKUN, transport=tr)
    assert tr.panggilan == []
    with pytest.raises(TypeError):
        m.kirim(m.request_status(CFG, INVOICE))


def test_create_tidak_memberi_bukti_meski_response_settlement():
    tr = Transport(Respons(status()))
    assert m.buat_pembayaran(CFG, INV, akun_id=AKUN, transport=tr, sakelar=ON).bukti is None
    assert tr.hasil.ditutup


def test_signature_constant_time_unsigned_status_bukan_bukti(monkeypatch):
    data = status()
    data["signature_key"] = hashlib.sha512((INVOICE + "200" + "15000.00" + CFG.server_key).encode()).hexdigest()
    asli = m.hmac.compare_digest
    panggilan = []
    def compare(a,b):
        panggilan.append(True)
        return asli(a,b)
    monkeypatch.setattr(m.hmac, "compare_digest", compare)
    assert m.signature_cocok(json.dumps(data).encode(), CFG)
    data["transaction_status"] = "pending"
    assert m.signature_cocok(json.dumps(data).encode(), CFG)
    assert periksa(data).bukti is None
    data["signature_key"] = "f"*128
    assert not m.signature_cocok(json.dumps(data).encode(), CFG)
    assert len(panggilan) == 3


@pytest.mark.parametrize("url", [
    "https://api.midtrans.com/v4/qris/trx/qr-code",
    "https://api.sandbox.midtrans.com/v2/qris/trx/qr-code",
])
def test_qr_allowlist(url):
    assert m.url_qr_sah(url, "sandbox")


@pytest.mark.parametrize("url", [
    "http://api.midtrans.com/v2/qris/trx/qr-code", "https://api.midtrans.com.evil.test/v2/qris/trx/qr-code",
    "https://user@api.midtrans.com/v2/qris/trx/qr-code", "https://api.midtrans.com:444/v2/qris/trx/qr-code",
    "https://api.midtrans.com:bad/v2/qris/trx/qr-code", "https://api.midtrans.com/v2/qris/../qr-code",
    "https://api.midtrans.com/v2/qris/trx/qr-code?token=secret", "https://api.midtrans.com/v2/qris/a%2fb/qr-code",
    "https://api.midtrans.com/v2/qris/trx/qr-code#fragment", "https://api.midtrans.com/\nv2/qris/trx/qr-code",
])
def test_qr_url_berbahaya_ditolak(url):
    assert not m.url_qr_sah(url, "sandbox")


def refund():
    return {"refund_amount": "12000.00", "refunds": [
        {"refund_key": "r1", "refund_chargeback_id": 1, "refund_amount": "5000.00", "bank_confirmed_at": "2027-01-02 10:00:00"},
        {"refund_key": "r2", "refund_chargeback_id": 2, "refund_amount": "7000.00", "bank_confirmed_at": None}]}


def test_refund_kumulatif_dedup_bukan_delta_ulang():
    awal = m.ringkas_refund(refund(), rupiah=15000)
    assert m.delta_refund(awal) == 5000
    assert m.delta_refund(awal, awal) == 0
    akhir = (awal[0], replace(awal[1], bank_terkonfirmasi=True))
    assert m.delta_refund(akhir, awal) == 7000
    assert m.delta_refund(akhir, akhir) == 0
    with pytest.raises(m.KontrakTidakSah):
        m.delta_refund(awal, akhir)


@pytest.mark.parametrize("jenis", ["key", "id", "nominal", "lebih"])
def test_refund_identitas_dan_total_ketat(jenis):
    data = refund()
    if jenis == "key": data["refunds"][1]["refund_key"] = "r1"
    if jenis == "id": data["refunds"][1]["refund_chargeback_id"] = 1
    if jenis == "nominal": data["refund_amount"] = "13000.00"
    if jenis == "lebih": data["refund_amount"] = "16000.00"
    with pytest.raises(m.KontrakTidakSah):
        m.ringkas_refund(data, rupiah=15000)
