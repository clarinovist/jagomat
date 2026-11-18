"""Adapter + klien order Midtrans (`pesanan_midtrans`): transport palsu, tanpa jaringan nyata."""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
import socket

import pytest

import admin_subscription
import midtrans_contract as m
import midtrans_produksi as p
import pesanan
import pesanan_midtrans as pm
import subscription as d
from pesanan_kit import (MERCHANT, SEKARANG, TRANSAKSI, buat, hasil_status, operasi, ord_id,
                         siapkan_db, snapshot_langganan)

CFG = m.Konfigurasi("sandbox", "kunci-sintetis-bukan-credential", MERCHANT)
CFGP = m.Konfigurasi("production", "SB-Mid-server-sintetis-0001", MERCHANT)
URL_QR = "https://api.sandbox.midtrans.com/v2/qris/" + TRANSAKSI + "/qr-code"
URL_QR_PROD = "https://api.midtrans.com/v2/qris/" + TRANSAKSI + "/qr-code"
MESIN = Path(__file__).resolve().parent.parent
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (64).to_bytes(4, "big") + (64).to_bytes(4, "big")
       + b"\x08\x02\x00\x00\x00" + b"\x00" * 4)


@pytest.fixture(autouse=True)
def tanpa_jaringan(monkeypatch):
    def dilarang(*a, **kw):
        pytest.fail("socket/network tidak boleh dipanggil")
    for nama in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, nama, dilarang)


@pytest.fixture
def db(tmp_path):
    return siapkan_db(tmp_path)


@pytest.fixture
def order(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        return buat(kon, 1)


class Respons:
    def __init__(self, data, *, kode=200, url=None, headers=None):
        self.data = data if type(data) is bytes else json.dumps(data).encode()
        self.status, self.url = kode, url
        self.headers = headers or {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, batas):
        return self.data[:batas]


class Transport:
    """Transport palsu: `jawab` = Respons, Exception, atau callable(req) -> Respons."""

    def __init__(self, jawab, gambar=None):
        self.jawab, self.panggilan, self.url_gambar = jawab, [], []
        if gambar is not None:
            self._gambar = gambar

    def __call__(self, req, *, timeout, allow_redirects):
        self.panggilan.append(req)
        jawab = self.jawab(req) if callable(self.jawab) else self.jawab
        if isinstance(jawab, Exception):
            raise jawab
        jawab.url = jawab.url or req.url
        return jawab

    def gambar(self, url):
        self.url_gambar.append(url)
        return self._gambar(url)


def create_ok(order, **ganti):
    data = {"order_id": order["order_id"], "gross_amount": "%d.00" % order["rupiah"],
            "currency": "IDR", "payment_type": "qris", "merchant_id": MERCHANT,
            "transaction_id": TRANSAKSI, "transaction_status": "pending", "status_code": "201",
            "actions": [{"name": "generate-qr-code", "method": "GET", "url": URL_QR}]}
    data.update(ganti)
    return {k: v for k, v in data.items() if v is not None}


def status_json(order, **ganti):
    return {**hasil_status(order, **ganti), "status_message": "ok", "signature_key": "x" * 8,
            "actions": [], "customer_details": {"nama": "sintetis"}}


# --- susun_binding ------------------------------------------------------------------

def test_susun_binding_memetakan_kolom_order_ke_bentuk_binding(order):
    binding = pm.susun_binding(order)
    assert binding == {"invoice_id": order["order_id"], "rupiah": 49000, "merchant": MERCHANT,
                       "provider": "midtrans", "channel": "qris", "akun_id": order["akun_id"],
                       "idempotency_key": order["idempotency_key"]}
    assert m._binding(create_ok(order), invoice=binding, merchant=MERCHANT) == TRANSAKSI


@pytest.mark.parametrize("ganti", [
    {"order_id": "inv_" + "a" * 32}, {"order_id": "ORD_" + "a" * 32}, {"order_id": None},
    {"akun_id": "akun_pendek"}, {"rupiah": 0}, {"rupiah": -5}, {"rupiah": True},
    {"rupiah": "49000"}, {"rupiah": 10_000_001}, {"merchant": "x y"}, {"provider": "lain"},
    {"channel": "gopay"}, {"idempotency_key": "pendek"}, {"idempotency_key": "k" * 47},
])
def test_susun_binding_menolak_order_rusak_tanpa_menyentuh_transport(order, ganti):
    rusak = {**order, **ganti}
    transport = Transport(Respons(create_ok(order)))
    with pytest.raises(pesanan.PesananDataTidakSah):
        pm.susun_binding(rusak)
    with pytest.raises(pesanan.PesananDataTidakSah):
        pm.buat_order_pembayaran(transport, rusak, config=CFG)
    with pytest.raises(pesanan.PesananDataTidakSah):
        pm.periksa_status_order(transport, rusak, config=CFG)
    assert transport.panggilan == []


def test_susun_binding_menolak_bukan_dict_atau_kunci_hilang(order):
    for salah in (None, [], "x", (("order_id", order["order_id"]),)):
        with pytest.raises(pesanan.PesananDataTidakSah):
            pm.susun_binding(salah)
    for kunci in ("order_id", "akun_id", "rupiah", "merchant", "provider", "channel",
                  "idempotency_key"):
        with pytest.raises(pesanan.PesananDataTidakSah):
            pm.susun_binding({k: v for k, v in order.items() if k != kunci})


# --- (d) create ---------------------------------------------------------------------

def test_create_sukses_mengembalikan_transaksi_qr_dan_kedaluwarsa(order):
    transport = Transport(Respons(create_ok(order)))
    hasil = pm.buat_order_pembayaran(transport, order, config=CFG)
    assert hasil == pm.HasilBuat(True, transaksi_id=TRANSAKSI, url_qr=URL_QR,
                                 kedaluwarsa=order["kedaluwarsa"], galat_kode=None)
    assert hasil.pesan is None
    (req,) = transport.panggilan
    assert (req.metode, req.url) == ("POST", "https://api.sandbox.midtrans.com/v2/charge")
    assert req.headers["Idempotency-Key"] == order["idempotency_key"]
    assert json.loads(req.body) == {"payment_type": "qris", "transaction_details": {
        "order_id": order["order_id"], "gross_amount": 49000}}


@pytest.mark.parametrize("nama,jawab,kode", [
    ("transport raise", RuntimeError("boom"), pm.GALAT_PROVIDER),
    ("timeout", TimeoutError(), pm.GALAT_PROVIDER),
    ("status 500", Respons({}, kode=500), pm.GALAT_PROVIDER),
    ("status 201", Respons({}, kode=201), pm.GALAT_PROVIDER),
    ("bukan json", Respons(b"<html>", headers={"Content-Type": "application/json"}), pm.GALAT_PROVIDER),
    ("tipe respons", Respons(b"{}", headers={"Content-Type": "text/html"}), pm.GALAT_PROVIDER),
    ("redirect", Respons({}, url="https://evil.test/x"), pm.GALAT_PROVIDER),
    ("json duplikat", Respons(b'{"a":1,"a":2}'), pm.GALAT_PROVIDER),
    ("bukan objek", Respons(b"[1]"), pm.GALAT_PROVIDER),
    ("terlalu besar", Respons(b" " * (m.BATAS_RESPONS + 5)), pm.GALAT_PROVIDER),
])
def test_create_gagal_provider_menghasilkan_hasil_eksplisit(order, nama, jawab, kode):
    hasil = pm.buat_order_pembayaran(Transport(jawab), order, config=CFG)
    assert isinstance(hasil, pm.HasilBuat), nama
    assert hasil.ok is False and hasil.galat_kode == kode
    assert hasil.url_qr is None and hasil.transaksi_id is None and hasil.kedaluwarsa is None
    assert hasil.galat_kode in pm.KODE_GALAT and hasil.pesan == pm.PESAN[kode]


@pytest.mark.parametrize("ganti", [
    {"order_id": ord_id(99)}, {"order_id": None}, {"gross_amount": "1000.00"},
    {"gross_amount": None}, {"currency": "USD"}, {"payment_type": "gopay"},
    {"merchant_id": "M_LAIN"}, {"transaction_id": None}, {"transaction_id": "bad id!"},
])
def test_create_dengan_respons_tidak_cocok_ditolak_sebagai_binding(order, ganti):
    hasil = pm.buat_order_pembayaran(Transport(Respons(create_ok(order, **ganti))), order, config=CFG)
    assert (hasil.ok, hasil.galat_kode, hasil.url_qr) == (False, pm.GALAT_BINDING, None)


@pytest.mark.parametrize("actions", [
    None, [], [{"name": "lain", "method": "GET", "url": URL_QR}],
    [{"name": "generate-qr-code", "method": "POST", "url": URL_QR}],
    [{"name": "generate-qr-code", "method": "GET", "url": "http://api.sandbox.midtrans.com/v2/qris/t/qr-code"}],
    [{"name": "generate-qr-code", "method": "GET", "url": "https://evil.test/v2/qris/t/qr-code"}],
    [{"name": "generate-qr-code", "method": "GET", "url": URL_QR + "?x=1"}],
    ["bukan-dict", 5],
])
def test_create_tanpa_url_qr_sah_gagal_eksplisit_dan_membawa_transaksi(order, actions):
    hasil = pm.buat_order_pembayaran(Transport(Respons(create_ok(order, actions=actions))),
                                     order, config=CFG)
    assert (hasil.ok, hasil.galat_kode, hasil.url_qr) == (False, pm.GALAT_QR, None)
    assert hasil.transaksi_id == TRANSAKSI


def test_create_dengan_merchant_config_beda_gagal_sebelum_menghubungi_provider(order):
    transport = Transport(Respons(create_ok(order)))
    lain = m.Konfigurasi("sandbox", "kunci-sintetis-bukan-credential", "M_LAIN")
    hasil = pm.buat_order_pembayaran(transport, order, config=lain)
    assert (hasil.ok, hasil.galat_kode) == (False, pm.GALAT_BINDING)
    assert transport.panggilan == []


def test_pesan_galat_dan_repr_tidak_membocorkan_id_nominal_atau_secret(order):
    for jawab in (RuntimeError(order["order_id"]), Respons(create_ok(order, merchant_id="M_LAIN"))):
        hasil = pm.buat_order_pembayaran(Transport(jawab), order, config=CFG)
        teks = (hasil.pesan or "") + repr(hasil)
        for rahasia in (order["order_id"], "49000", CFG.server_key, order["akun_id"], TRANSAKSI):
            assert rahasia not in teks
    sukses = pm.buat_order_pembayaran(Transport(Respons(create_ok(order))), order, config=CFG)
    assert URL_QR not in repr(sukses)


def test_create_via_transport_produksi_nyata_menerima_ord_dengan_koneksi_palsu(order, monkeypatch):
    koneksi = _pasang_koneksi(monkeypatch, create_ok(order, actions=[
        {"name": "generate-qr-code", "method": "GET", "url": URL_QR_PROD}]))
    hasil = pm.buat_order_pembayaran(p.TransportProduksi(CFGP), order, config=CFGP)
    assert hasil.ok is True and hasil.url_qr == URL_QR_PROD
    (metode, path, body, headers), = koneksi.panggilan
    assert (metode, path) == ("POST", "/v2/charge")
    assert body == m.request_create(CFGP, order["order_id"], 49000, order["idempotency_key"]).body
    assert headers["Idempotency-Key"] == order["idempotency_key"]


def test_create_via_transport_produksi_gagal_koneksi_menjadi_hasil_gagal(order, monkeypatch):
    koneksi = _pasang_koneksi(monkeypatch, {})
    koneksi.gagal = OSError("down")
    hasil = pm.buat_order_pembayaran(p.TransportProduksi(CFGP), order, config=CFGP)
    assert (hasil.ok, hasil.galat_kode) == (False, pm.GALAT_PROVIDER)


# --- (e)(f) status ------------------------------------------------------------------

def _ke_ledger(db, n, jawab_json, order_id=None):
    """Periksa status lewat adapter lalu terapkan ke ledger sementara."""
    with pesanan.buka(db, tulis_data=True) as kon:
        order = pesanan.ambil_order(kon, order_id or ord_id(1), "akun_" + "a1" * 16)
        hasil = pm.periksa_status_order(Transport(Respons(jawab_json(order))), order, config=CFG)
        assert hasil.ok is True and hasil.galat_kode is None
        return pesanan.terapkan_hasil_provider(
            kon, order["order_id"], hasil.hasil_provider, SEKARANG, operasi(n))


def test_status_menyaring_kunci_dan_siap_ke_ledger(order):
    transport = Transport(Respons(status_json(order)))
    hasil = pm.periksa_status_order(transport, order, config=CFG)
    assert hasil.ok and not hasil.tanpa_transaksi and hasil.galat_kode is None
    assert hasil.hasil_provider == hasil_status(order)
    assert set(hasil.hasil_provider) <= set(pm.KUNCI_HASIL)
    (req,) = transport.panggilan
    assert (req.metode, req.body) == ("GET", None)
    assert req.url == "https://api.sandbox.midtrans.com/v2/%s/status" % order["order_id"]


def test_status_settlement_benar_mengalir_ke_ledger_menjadi_lunas(db, order):
    hasil = _ke_ledger(db, 1, lambda o: status_json(o))
    assert hasil["status"] == pesanan.STATUS_SUDAH_DIBAYAR and hasil["receipt"] == "lunas"


@pytest.mark.parametrize("ganti", [
    {"gross_amount": "1000.00"}, {"gross_amount": "49001"}, {"merchant_id": "M_LAIN"},
    {"currency": "USD"}, {"payment_type": "gopay"},
])
def test_status_nominal_atau_binding_beda_sampai_ledger_menjadi_perlu_diperiksa(db, order, ganti):
    hasil = _ke_ledger(db, 1, lambda o: status_json(o, **ganti))
    assert hasil["status"] == pesanan.STATUS_PERLU_DIPERIKSA and hasil["receipt"] == "perlu_diperiksa"


def test_status_pending_tidak_membuat_receipt_dan_refund_perlu_diperiksa(db, order):
    pending = _ke_ledger(db, 1, lambda o: status_json(
        o, transaction_status="pending", status_code="201"))
    assert (pending["status"], pending["receipt"]) == (pesanan.STATUS_BELUM_BAYAR, None)
    refund = _ke_ledger(db, 2, lambda o: status_json(o, transaction_status="refund"))
    assert (refund["status"], refund["receipt"]) == (pesanan.STATUS_PERLU_DIPERIKSA,
                                                     "perlu_diperiksa")


def test_status_kelas_mati_dan_sentinel_tanpa_transaksi(order):
    for status in m.KELAS_MATI:
        hasil = pm.periksa_status_order(
            Transport(Respons(status_json(order, transaction_status=status, status_code="202"))),
            order, config=CFG)
        assert hasil.ok and hasil.mati is True
    hidup = pm.periksa_status_order(Transport(Respons(status_json(order))), order, config=CFG)
    assert hidup.mati is False
    sentinel = {"id": order["order_id"], "status_code": "404",
                "status_message": "Transaction doesn't exist."}
    hasil = pm.periksa_status_order(Transport(Respons(sentinel)), order, config=CFG)
    assert (hasil.ok, hasil.tanpa_transaksi, hasil.hasil_provider, hasil.mati) == (True, True, None, False)


@pytest.mark.parametrize("nama,jawab", [
    ("transport raise", RuntimeError("boom")), ("status 500", Respons({}, kode=500)),
    ("bukan json", Respons(b"nope")), ("redirect", Respons({}, url="https://evil.test/")),
    ("tipe respons", Respons(b"{}", headers={"Content-Type": "text/plain"})),
])
def test_status_gagal_provider_eksplisit(order, nama, jawab):
    hasil = pm.periksa_status_order(Transport(jawab), order, config=CFG)
    assert isinstance(hasil, pm.HasilStatus), nama
    assert (hasil.ok, hasil.hasil_provider, hasil.galat_kode) == (False, None, pm.GALAT_PROVIDER)
    assert hasil.pesan == pm.PESAN[pm.GALAT_PROVIDER]


@pytest.mark.parametrize("jawab", [
    lambda o: status_json(o, order_id=ord_id(77)),
    lambda o: status_json(o, order_id=None),
    lambda o: status_json(o, order_id=o["order_id"].upper()),
    lambda o: status_json(o, order_id=12345),
    lambda o: {"id": ord_id(77), "status_code": "404", "status_message": "Transaction doesn't exist."},
])
def test_status_order_id_respons_beda_ditolak_tanpa_hasil(order, jawab):
    hasil = pm.periksa_status_order(Transport(Respons(jawab(order))), order, config=CFG)
    assert (hasil.ok, hasil.hasil_provider, hasil.galat_kode) == (False, None, pm.GALAT_ORDER)
    assert hasil.tanpa_transaksi is False


def test_status_order_id_beda_tidak_pernah_menulis_ledger(db, order):
    with pesanan.buka(db, tulis_data=True) as kon:
        sebelum = {t: kon.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
                   for t in ("pesanan_order", "pesanan_receipt", "pesanan_pengamatan")}
        hasil = pm.periksa_status_order(
            Transport(Respons(status_json(order, order_id=ord_id(77)))), order, config=CFG)
        assert hasil.hasil_provider is None
        sesudah = {t: kon.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in sebelum}
    assert sesudah == sebelum


# --- (g) nominal hanya dari order --------------------------------------------------

def test_tanda_tangan_fungsi_tidak_punya_parameter_nominal():
    for fungsi in (pm.buat_order_pembayaran, pm.periksa_status_order, pm.susun_binding,
                   pm.ambil_gambar_qr, pm.KlienOrder.buat, pm.KlienOrder.status):
        nama = set(inspect.signature(fungsi).parameters)
        assert not nama & {"rupiah", "nominal", "amount", "gross_amount", "harga", "jumlah"}, fungsi


def test_nominal_luar_ditolak_dan_hanya_rupiah_order_yang_terkirim(order):
    transport = Transport(Respons(create_ok(order)))
    for kunci in ("rupiah", "nominal", "gross_amount", "harga"):
        with pytest.raises(TypeError):
            pm.buat_order_pembayaran(transport, order, config=CFG, **{kunci: 1})
    licik = {**order, "nominal": 1, "gross_amount": 1, "harga": 1, "amount": 1}
    pm.buat_order_pembayaran(transport, licik, config=CFG)
    assert json.loads(transport.panggilan[0].body)["transaction_details"]["gross_amount"] == 49000
    beda = {**order, "rupiah": 12345}
    pm.buat_order_pembayaran(transport, beda, config=CFG)
    assert json.loads(transport.panggilan[1].body)["transaction_details"]["gross_amount"] == 12345
    assert pm.susun_binding(licik)["rupiah"] == 49000


def test_respons_dengan_nominal_beda_dari_order_tidak_diterima_sebagai_sukses(order):
    hasil = pm.buat_order_pembayaran(
        Transport(Respons(create_ok(order, gross_amount="1000.00"))), order, config=CFG)
    assert hasil.ok is False and hasil.url_qr is None


# --- gambar QR dan runtime ----------------------------------------------------------

def test_ambil_gambar_qr_hanya_untuk_url_qr_produksi_sah():
    transport = Transport(Respons({}), gambar=lambda url: PNG)
    assert pm.ambil_gambar_qr(transport, URL_QR_PROD) == PNG
    assert transport.url_gambar == [URL_QR_PROD]
    for salah in (URL_QR, "http://api.midtrans.com/v2/qris/t/qr-code", "https://evil.test/v2/qris/t/qr-code",
                  URL_QR_PROD + "?x=1", "https://api.midtrans.com/v2/qris/t/other", "", None, 5,
                  "https://api.midtrans.com/v2/qris/%2e%2e/qr-code"):
        with pytest.raises(m.KontrakTidakSah):
            pm.ambil_gambar_qr(transport, salah)
    assert transport.url_gambar == [URL_QR_PROD]
    with pytest.raises(m.KontrakTidakSah):
        pm.ambil_gambar_qr(lambda req, **kw: None, URL_QR_PROD)
    assert pm.ambil_gambar_qr(transport, URL_QR, lingkungan="sandbox") == PNG


def test_ambil_gambar_qr_lewat_transport_produksi_memvalidasi_png(monkeypatch):
    koneksi = _pasang_koneksi(monkeypatch, PNG, tipe="image/png")
    assert pm.ambil_gambar_qr(p.TransportProduksi(CFGP), URL_QR_PROD) == PNG
    assert koneksi.panggilan[0][:2] == ("GET", "/v2/qris/" + TRANSAKSI + "/qr-code")
    _pasang_koneksi(monkeypatch, b"bukan png yang sah sama sekali, hanya teks panjang", tipe="image/png")
    with pytest.raises(m.KontrakTidakSah):
        pm.ambil_gambar_qr(p.TransportProduksi(CFGP), URL_QR_PROD)


def test_dari_runtime_membungkus_config_dan_transport(order):
    transport = Transport(Respons(create_ok(order)))
    runtime = admin_subscription.RuntimePembayaran(CFG, transport, d.SAKELAR, None)
    klien = pm.dari_runtime(runtime)
    assert klien.buat(order).ok is True
    assert "kunci-sintetis" not in repr(klien) and CFG.server_key not in repr(klien)
    for rusak in (None, object(), admin_subscription.RuntimePembayaran(CFG, "bukan-callable", d.SAKELAR)):
        with pytest.raises(pesanan.PesananDataTidakSah):
            pm.dari_runtime(rusak)


# --- (h) tidak menyentuh langganan ---------------------------------------------------

def test_alur_klien_dan_ledger_tidak_mengubah_baris_langganan(tmp_path):
    import sqlite3
    path = siapkan_db(tmp_path)
    with sqlite3.connect(path) as kon:
        kon.execute("INSERT INTO langganan_enrollment VALUES(?,?,?,?,?,NULL,'langganan-v1')",
                    ("akun_" + "a1" * 16, "sumber_0001", "transisi", 0, 0))
    with pesanan.buka(path) as baca:
        sebelum = snapshot_langganan(baca)
    assert sebelum["langganan_enrollment"]
    with pesanan.buka(path, tulis_data=True) as kon:
        order = buat(kon, 1)
        assert pm.buat_order_pembayaran(Transport(Respons(create_ok(order))), order, config=CFG).ok
        hasil = pm.periksa_status_order(Transport(Respons(status_json(order))), order, config=CFG)
        pesanan.terapkan_hasil_provider(kon, order["order_id"], hasil.hasil_provider,
                                        SEKARANG, operasi(1))
        assert snapshot_langganan(kon) == sebelum


def test_sumber_adapter_tidak_mengimpor_modul_langganan_atau_jaringan():
    pohon = ast.parse((MESIN / "pesanan_midtrans.py").read_text())
    impor = set()
    for node in ast.walk(pohon):
        if isinstance(node, ast.Import):
            impor |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            impor.add((node.module or "").split(".")[0])
    assert not impor & {"subscription", "subscription_store", "subscription_callback",
                        "subscription_produksi", "admin_store", "socket", "urllib", "http",
                        "database", "web", "os"}
    teks = (MESIN / "pesanan_midtrans.py").read_text()
    assert "langganan_" not in teks and "os.environ" not in teks


# --- koneksi palsu untuk TransportProduksi -------------------------------------------

class _ResponsKoneksi:
    def __init__(self, data, tipe):
        self.data = data if type(data) is bytes else json.dumps(data).encode()
        self.status = 200
        self.headers = {"Content-Type": tipe}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def getheader(self, nama, default=None):
        return self.headers.get(nama, default)

    def read1(self, batas):
        hasil, self.data = self.data[:batas], self.data[batas:]
        return hasil


class _Koneksi:
    def __init__(self, data, tipe):
        self.respons, self.panggilan, self.sock, self.gagal = _ResponsKoneksi(data, tipe), [], self, None

    def connect(self):
        if self.gagal:
            raise self.gagal

    def settimeout(self, _):
        pass

    def request(self, metode, path, *, body, headers):
        self.panggilan.append((metode, path, body, headers))

    def getresponse(self):
        return self.respons

    def close(self):
        pass


def _pasang_koneksi(monkeypatch, data, tipe="application/json"):
    koneksi = _Koneksi(data, tipe)
    monkeypatch.setattr(p.http.client, "HTTPSConnection", lambda host, *, timeout, context: koneksi)
    return koneksi
