"""Adapter jaringan diuji tanpa socket, credential nyata, atau state pengguna."""

from dataclasses import replace
import json
import socket
import ssl

import pytest
import midtrans_contract as m
import midtrans_sandbox as s
import subscription as d
from test_midtrans_contract import CFG, INV, AKUN, INVOICE, ON, status


@pytest.fixture(autouse=True)
def tanpa_socket(monkeypatch):
    def dilarang(*args, **kwargs):
        pytest.fail("jaringan nyata tidak boleh dipanggil")
    for nama in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, nama, dilarang)


class ResponsPalsu:
    def __init__(self):
        self.data = json.dumps(status()).encode()
        self.status = 200
        self.headers = {"Content-Type": "application/json"}
        self.batas = []
        self.ditutup = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.ditutup = True

    def getheader(self, nama, default=None):
        return self.headers.get(nama, default)

    def read1(self, batas):
        self.batas.append(batas)
        hasil, self.data = self.data[:batas], self.data[batas:]
        return hasil


class KoneksiPalsu:
    def __init__(self):
        self.respons = ResponsPalsu()
        self.ditutup = False
        self.panggilan = []
        self.timeout = []
        self.sock = self
        self.gagal = None

    def connect(self):
        if self.gagal:
            raise self.gagal

    def settimeout(self, nilai):
        self.timeout.append(nilai)

    def request(self, metode, path, *, body, headers):
        self.panggilan.append((metode, path, body, headers))

    def getresponse(self):
        return self.respons

    def close(self):
        self.ditutup = True


@pytest.fixture
def jaringan(monkeypatch):
    koneksi = KoneksiPalsu()
    dibuat = []
    def baru(host, *, timeout, context):
        dibuat.append((host, timeout, context))
        return koneksi
    monkeypatch.setattr(s.http.client, "HTTPSConnection", baru)
    return koneksi, dibuat


def test_query_settlement_tls_host_timeout_dan_close(jaringan):
    koneksi, dibuat = jaringan
    hasil = m.periksa_status(CFG, INV, akun_id=AKUN, transport=s.TransportSandbox(CFG), sakelar=ON)
    assert hasil.status == "lunas" and hasil.bukti.invoice_id == INVOICE
    assert len(dibuat) == 1 and dibuat[0][:2] == ("api.sandbox.midtrans.com", 10)
    konteks = dibuat[0][2]
    assert konteks.check_hostname and konteks.verify_mode == ssl.CERT_REQUIRED
    assert len(koneksi.panggilan) == 1
    assert koneksi.panggilan[0] == ("GET", "/v2/" + INVOICE + "/status", None,
                                    m.request_status(CFG, INVOICE).headers)
    assert all(0 < t <= 10 for t in koneksi.timeout)
    assert koneksi.timeout
    assert koneksi.ditutup and koneksi.respons.ditutup


def test_create_minimal_tidak_grant(jaringan):
    koneksi, _ = jaringan
    data = status()
    data.update(status_code="201", transaction_status="pending", actions=[{
        "name": "generate-qr-code", "method": "GET",
        "url": "https://api.sandbox.midtrans.com/v2/qris/trx_sintetis/qr-code"}])
    koneksi.respons.data = json.dumps(data).encode()
    hasil = m.buat_pembayaran(CFG, INV, akun_id=AKUN, transport=s.TransportSandbox(CFG), sakelar=ON)
    assert hasil.qr == data["actions"][0]["url"] and hasil.bukti is None
    metode, path, body, headers = koneksi.panggilan[0]
    assert (metode, path) == ("POST", "/v2/charge")
    assert json.loads(body) == m.payload_qris(INVOICE, 15000)
    assert headers == m.request_create(CFG, INVOICE, 15000, INV["idempotency_key"]).headers


def test_produksi_ditolak_sebelum_socket(jaringan):
    with pytest.raises(m.KontrakTidakSah):
        s.TransportSandbox(replace(CFG, lingkungan="production"))
    assert jaringan[1] == []


@pytest.mark.parametrize("ubah", [
    {"url": "https://api.midtrans.com/v2/" + INVOICE + "/status"},
    {"url": "https://api.sandbox.midtrans.com.evil.test/v2/" + INVOICE + "/status"},
    {"url": "http://api.sandbox.midtrans.com/v2/" + INVOICE + "/status"},
    {"url": "https://api.sandbox.midtrans.com:443/v2/" + INVOICE + "/status"},
    {"url": "https://api.sandbox.midtrans.com/v2/" + INVOICE + "/status?secret=x"},
    {"url": "https://api.sandbox.midtrans.com/v2/../../status"},
    {"metode": "DELETE"}, {"body": b"{}"},
    {"headers": {"Authorization": "Basic kunci-asing", "Accept": "application/json"}},
])
def test_request_asing_ditolak_sebelum_socket(jaringan, ubah):
    req = replace(m.request_status(CFG, INVOICE), **ubah)
    with pytest.raises(m.KontrakTidakSah):
        m.kirim(req, transport=s.TransportSandbox(CFG))
    assert jaringan[1] == []


@pytest.mark.parametrize("jenis", ["kontak", "duplikat", "metode", "nominal", "header", "key"])
def test_create_tambahan_ditolak_sebelum_socket(jaringan, jenis):
    req = m.request_create(CFG, INVOICE, 15000, INV["idempotency_key"])
    data = json.loads(req.body)
    if jenis == "kontak":
        data["customer_details"] = {"first_name": "Sintetis"}
    elif jenis == "metode":
        data["payment_type"] = "gopay"
    elif jenis == "nominal":
        data["transaction_details"]["gross_amount"] = True
    if jenis in ("kontak", "metode", "nominal"):
        req = replace(req, body=json.dumps(data, separators=(",", ":")).encode())
    elif jenis == "duplikat":
        req = replace(req, body=req.body.replace(b'"payment_type":', b'"payment_type":"qris","payment_type":'))
    elif jenis == "header":
        req = replace(req, headers=dict(req.headers, **{"X-Override-Notification": "https://evil.test"}))
    else:
        req = replace(req, headers=dict(req.headers, **{"Idempotency-Key": "x" * 47}))
    with pytest.raises(m.KontrakTidakSah):
        m.kirim(req, transport=s.TransportSandbox(CFG))
    assert jaringan[1] == []


@pytest.mark.parametrize("timeout,redirect", [(0, False), (16, False), (True, False),
                                               (1.5, False), (10, True), (10, None)])
def test_opsi_tidak_aman_ditolak(jaringan, timeout, redirect):
    with pytest.raises(m.KontrakTidakSah):
        with s.TransportSandbox(CFG)(m.request_status(CFG, INVOICE), timeout=timeout, allow_redirects=redirect):
            pass
    assert jaringan[1] == []


@pytest.mark.parametrize("kode", [201, 202, 301, 302, 307, 308, 401, 500])
def test_error_redirect_tanpa_read_retry_atau_grant(jaringan, kode):
    koneksi, dibuat = jaringan
    koneksi.respons.status = kode
    koneksi.respons.headers["Location"] = "https://evil.test"
    assert m.periksa_status(CFG, INV, akun_id=AKUN, transport=s.TransportSandbox(CFG), sakelar=ON).bukti is None
    assert len(dibuat) == len(koneksi.panggilan) == 1
    assert koneksi.respons.batas == []
    assert koneksi.ditutup and koneksi.respons.ditutup


@pytest.mark.parametrize("header,nilai", [("Content-Type", "text/html"), ("Content-Length", "128001"),
    ("Content-Length", "-1"), ("Content-Length", "1, 1"), ("Content-Length", "bukan angka")])
def test_header_tidak_sah_tanpa_baca(jaringan, header, nilai):
    koneksi, _ = jaringan
    koneksi.respons.headers[header] = nilai
    with pytest.raises(m.KontrakTidakSah):
        m.kirim(m.request_status(CFG, INVOICE), transport=s.TransportSandbox(CFG))
    assert koneksi.respons.batas == [] and koneksi.ditutup


def test_baca_bounded_meski_tanpa_content_length(jaringan):
    koneksi, _ = jaringan
    koneksi.respons.data = b" " * (m.BATAS_RESPONS + 50000)
    with pytest.raises(m.KontrakTidakSah):
        with s.TransportSandbox(CFG)(m.request_status(CFG, INVOICE)):
            pytest.fail("respons terlalu besar harus ditolak adapter")
    assert sum(koneksi.respons.batas) == m.BATAS_RESPONS + 1
    assert max(koneksi.respons.batas) <= 8192 and koneksi.ditutup


def test_content_length_terpotong_tidak_dianggap_utuh(jaringan):
    koneksi, _ = jaringan
    koneksi.respons.headers["Content-Length"] = str(len(koneksi.respons.data) + 1)
    with pytest.raises(m.KontrakTidakSah):
        with s.TransportSandbox(CFG)(m.request_status(CFG, INVOICE)):
            pytest.fail("respons terpotong harus ditolak adapter")
    assert koneksi.ditutup


def test_deadline_memutus_stream_lambat(jaringan, monkeypatch):
    koneksi, _ = jaringan
    koneksi.respons.data = b" " * 20000
    waktu = iter([0, 1, 2, 5, 11])
    monkeypatch.setattr(s.time, "monotonic", lambda: next(waktu))
    with pytest.raises(m.KontrakTidakSah):
        with s.TransportSandbox(CFG)(m.request_status(CFG, INVOICE)):
            pytest.fail("deadline harus memutus stream")
    assert koneksi.respons.batas == [8192] and koneksi.ditutup


@pytest.mark.parametrize("tahap", ["connect", "request", "read", "close"])
def test_exception_tidak_bocor_dan_tidak_retry(jaringan, monkeypatch, capsys, tahap):
    koneksi, dibuat = jaringan
    def gagal(*args, **kwargs):
        raise OSError(CFG.server_key)
    if tahap == "read":
        monkeypatch.setattr(koneksi.respons, "read1", gagal)
    elif tahap == "connect":
        koneksi.gagal = OSError(CFG.server_key)
    else:
        monkeypatch.setattr(koneksi, tahap, gagal)
    with pytest.raises(m.KontrakTidakSah) as exc:
        with s.TransportSandbox(CFG)(m.request_status(CFG, INVOICE)):
            pass
    assert CFG.server_key not in str(exc.value) + repr(exc.value)
    assert len(dibuat) == 1
    if tahap != "close":
        assert koneksi.ditutup
    assert capsys.readouterr().out == ""


def test_gambar_hanya_png_sandbox_bounded(jaringan):
    koneksi, dibuat = jaringan
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (280).to_bytes(4, "big") * 2 + b"\x08\x02\x00\x00\x00" + b"isi-data"
    koneksi.respons.data = png
    koneksi.respons.headers = {"Content-Type": "image/png", "Content-Length": str(len(png))}
    url = "https://api.sandbox.midtrans.com/v2/qris/trx_sintetis/qr-code"
    assert s.TransportSandbox(CFG).gambar(url) == png
    assert dibuat[0][0] == "api.sandbox.midtrans.com"
    assert koneksi.panggilan[0][:3] == ("GET", "/v2/qris/trx_sintetis/qr-code", None)
    for asing in ("https://api.midtrans.com/v2/qris/trx_sintetis/qr-code",
                  "https://evil.test/v2/qris/trx_sintetis/qr-code",
                  "https://api.sandbox.midtrans.com/v4/qris/trx_sintetis/qr-code"):
        with pytest.raises(m.KontrakTidakSah):
            s.TransportSandbox(CFG).gambar(asing)
    assert len(dibuat) == 1


def test_gambar_invalid_ditolak(jaringan):
    koneksi, _ = jaringan
    url = "https://api.sandbox.midtrans.com/v2/qris/trx_sintetis/qr-code"
    for data in (b"bukan png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (0).to_bytes(4, "big") * 2 + b"\x08\x02\x00\x00\x00isi",
                 b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (4096).to_bytes(4, "big") * 2 + b"\x08\x02\x00\x00\x00isi",
                 b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (280).to_bytes(4, "big") * 2 + b"\x08\x02\x01\x00\x00isi"):
        koneksi.respons.data = data
        koneksi.respons.headers = {"Content-Type": "image/png", "Content-Length": str(len(data))}
        with pytest.raises(m.KontrakTidakSah):
            s.TransportSandbox(CFG).gambar(url)


def test_sakelar_off_dan_owner_sebelum_jaringan(jaringan):
    tr = s.TransportSandbox(CFG)
    for fungsi in (m.buat_pembayaran, m.periksa_status):
        with pytest.raises(d.FiturNonaktif, match="fitur langganan nonaktif"):
            fungsi(CFG, INV, akun_id=AKUN, transport=tr)
        with pytest.raises(LookupError):
            fungsi(CFG, INV, akun_id="akun_" + "f" * 32, transport=tr, sakelar=ON)
    assert jaringan[1] == []
