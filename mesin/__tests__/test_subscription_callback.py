"""Callback Midtrans lewat socket loopback; akun, ledger, dan secret sintetis.

Tidak ada kredensial nyata dan tidak ada panggilan jaringan keluar: endpoint
callback hanya menulis hint durable, tidak pernah menyentuh provider.
"""

import hashlib
import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import replace
from types import SimpleNamespace

import pytest
import admin_store
import admin_subscription
import subscription as d
import subscription_produksi as prod
import subscription_store as store
from http_test_kit import ServerUji
from test_midtrans_contract import CFG
from test_subscription import AKUN, ts
from test_subscription_store import ON, dump

KUNCI = "Mid-server-SINTETIS-bukan-credential"
MERCHANT = "M_SINTETIS"
CFGP = replace(CFG, lingkungan="production", server_key=KUNCI, merchant=MERCHANT)
T0 = ts(2027, 1, 1)
JALUR = "/midtrans/callback"
INVOICE = "inv_" + "1" * 32


def _ledak(*a, **kw):
    raise OSError("penyimpanan sintetis gagal")


@pytest.fixture
def uji(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    rahasia = tmp_path / "rahasia.conf"
    rahasia.write_text("merchant=%s\nserver_key=%s\n" % (MERCHANT, KUNCI))
    os.chmod(rahasia, 0o600)
    monkeypatch.setattr(prod, "BERKAS_RAHASIA_BAWAAN", rahasia)
    monkeypatch.setattr(prod, "BERKAS_RECOVERY_BAWAAN", tmp_path / "belum-ada.json")
    with admin_store._transaksi(admin_store.BAWAAN) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap='rekonsiliasi'")
    store.buat_kampanye(admin_store.BAWAAN, "promo_v1", mulai=T0, sakelar=ON)
    store.enroll(admin_store.BAWAAN, AKUN, sumber_id="daftar_0001", asal="publik",
                 mulai=T0, peran="guru", sakelar=ON)
    store.atur_cakupan(admin_store.BAWAAN, AKUN, (1,), operasi_id="cakupan_001", revisi=0,
                       sekarang=T0, pemilik_profil=lambda _: AKUN, sakelar=ON)
    store.buat_invoice(admin_store.BAWAAN, AKUN, invoice_id=INVOICE,
                       idempotency_key="idem_" + "2" * 32, provider="midtrans",
                       channel="qris", merchant=MERCHANT, sekarang=T0,
                       kedaluwarsa=T0 + 86400, sakelar=ON)
    store.reservasi_create(admin_store.BAWAAN, AKUN, INVOICE, sekarang=T0, sakelar=ON)
    k = SimpleNamespace(server=server, rahasia=rahasia, tmp=tmp_path)
    try:
        yield k
    finally:
        server.berhenti()


def tanda_tangan(data, kunci=KUNCI):
    bahan = data["order_id"] + data["status_code"] + data["gross_amount"] + kunci
    return hashlib.sha512(bahan.encode()).hexdigest()


def muatan(inv=None, *, status="settlement", fraud="accept", kode="200", nominal=15000,
           merchant=MERCHANT, kunci=KUNCI, **ubah):
    data = {"transaction_id": "trx_sintetis", "order_id": INVOICE if inv is None else inv,
            "gross_amount": str(nominal) + ".00", "currency": "IDR", "payment_type": "qris",
            "merchant_id": merchant, "status_code": kode, "transaction_status": status,
            "fraud_status": fraud}
    data.update(ubah)
    data["signature_key"] = tanda_tangan(data, kunci)
    return data


def kirim(k, data, *, tipe="application/json", jalur=JALUR, headers=None, metode="POST",
          mentah=None):
    isi = json.dumps(data).encode() if mentah is None else mentah
    req = urllib.request.Request(k.server.alamat + jalur, data=isi, method=metode)
    if tipe is not None:
        req.add_header("Content-Type", tipe)
    for nama, nilai in (headers or {}).items():
        req.add_header(nama, nilai)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)


def hint(path):
    with admin_store.buka_baca(path) as kon:
        return [tuple(baris) for baris in kon.execute(
            "SELECT operasi_id, invoice_id, status, rujukan FROM langganan_rekonsiliasi "
            "WHERE operasi_id LIKE 'cbk_%' ORDER BY rowid")]


def test_callback_valid_menyimpan_hint_dan_ack_bersih(uji):
    k = uji
    awal = dump(admin_store.BAWAAN)
    kode, isi, headers = kirim(k, muatan())
    assert kode == 200 and isi == "OK"
    assert "Location" not in headers and "Set-Cookie" not in headers
    assert headers["Cache-Control"] == "no-store"
    assert KUNCI not in isi and "trx_sintetis" not in isi
    assert dump(admin_store.BAWAAN) != awal
    baris = hint(admin_store.BAWAAN)
    assert len(baris) == 1
    assert baris[0][0].startswith("cbk_") and len(baris[0][0]) <= 46
    assert (baris[0][1], baris[0][2], baris[0][3]) == (INVOICE, "belum_terverifikasi", None)
    assert "trx_sintetis" not in "\n".join(dump(admin_store.BAWAAN))
    with admin_store.buka_baca(admin_store.BAWAAN) as kon:
        assert kon.execute("SELECT COUNT(*) FROM langganan_receipt").fetchone()[0] == 0
        assert kon.execute("SELECT COUNT(*) FROM langganan_grant").fetchone()[0] == 0


def test_callback_duplikat_idempoten_dan_out_of_order_append_only(uji):
    k = uji
    data = muatan()
    assert kirim(k, data)[0] == 200
    setelah_satu = hint(admin_store.BAWAAN)
    assert kirim(k, data)[0] == 200 and kirim(k, data)[0] == 200
    assert hint(admin_store.BAWAAN) == setelah_satu
    assert kirim(k, muatan(status="pending", kode="201"))[0] == 200
    assert kirim(k, muatan(status="settlement"))[0] == 200
    assert kirim(k, muatan(status="refund"))[0] == 200
    assert kirim(k, muatan(status="partial_refund"))[0] == 200
    akhir = hint(admin_store.BAWAAN)
    assert [b[2] for b in akhir] == ["belum_terverifikasi", "belum_terverifikasi",
                                     "perlu_diperiksa", "perlu_diperiksa"]
    with admin_store.buka_baca(admin_store.BAWAAN) as kon:
        assert kon.execute("SELECT COUNT(*) FROM langganan_receipt").fetchone()[0] == 0


def test_callback_asing_tanpa_dokumen_atau_grant_baru(uji):
    k = uji
    awal = dump(admin_store.BAWAAN)
    kode, isi, _ = kirim(k, muatan("inv_" + "9" * 32))
    assert kode == 200 and isi == "OK"
    assert dump(admin_store.BAWAAN) == awal
    with admin_store.buka_baca(admin_store.BAWAAN) as kon:
        for tabel, jumlah in (("langganan_invoice", 1), ("langganan_receipt", 0),
                              ("langganan_grant", 0), ("langganan_rekonsiliasi", 1),
                              ("langganan_cakupan", 1), ("langganan_enrollment", 1)):
            assert kon.execute("SELECT COUNT(*) FROM " + tabel).fetchone()[0] == jumlah, tabel


def test_callback_penolakan_seragam_tanpa_efek(uji):
    k = uji
    awal = dump(admin_store.BAWAAN)
    rusak = muatan()
    rusak["signature_key"] = "0" * 128
    kasus = [rusak, muatan(kunci="Mid-server-SALAH"), muatan(merchant="M_ASING"),
             muatan(currency="USD"), muatan(payment_type="bank_transfer"),
             muatan(transaction_id=""), muatan(order_id="bukan_invoice"),
             muatan(status_code="abc")]
    jawab = [kirim(k, data)[:2] for data in kasus]
    assert [kode for kode, _ in jawab] == [403] * len(kasus)
    assert len({isi for _, isi in jawab}) == 1
    assert dump(admin_store.BAWAAN) == awal
    for mentah in (b"{", b'{"order_id":"a","order_id":"b"}', b"[]", b"x" * 40,
                   '{"order_id": "inv"}'.encode("utf-16")):
        assert kirim(k, None, mentah=mentah)[0] == 403
    assert dump(admin_store.BAWAAN) == awal


def test_callback_field_tambahan_provider_tidak_disimpan(uji):
    k = uji
    kode, _, _ = kirim(k, muatan(va_numbers=[{"bank": "bca"}], issuer="bank-lain",
                                 settlement_time="2026-01-01 00:00:00"))
    assert kode == 200
    isi = "\n".join(dump(admin_store.BAWAAN))
    assert "bca" not in isi and "bank-lain" not in isi and "settlement_time" not in isi


def test_callback_tanpa_secret_atau_tier_rendah_fail_closed(uji, monkeypatch):
    k = uji
    awal = dump(admin_store.BAWAAN)
    os.chmod(k.rahasia, 0o644)
    assert kirim(k, muatan())[0] == 503
    os.chmod(k.rahasia, 0o600)
    with admin_store._transaksi(admin_store.BAWAAN) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap='nonaktif'")
    assert kirim(k, muatan())[0] == 503
    with admin_store._transaksi(admin_store.BAWAAN) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap='rekonsiliasi'")
    asli = store.catat_pengamatan
    monkeypatch.setattr(store, "catat_pengamatan", _ledak)
    assert kirim(k, muatan())[0] == 503
    monkeypatch.setattr(store, "catat_pengamatan", asli)
    assert hint(admin_store.BAWAAN) == []
    assert dump(admin_store.BAWAAN) == awal


def test_callback_tanpa_login_dan_header_peramban(uji):
    k = uji
    awal = dump(admin_store.BAWAAN)
    peramban = {"Origin": k.server.alamat, "Referer": k.server.alamat + "/guru",
                "Authorization": "Basic Z3VydTpzYW5kaS1ndXJ1", "Cookie": "osn_sesi=palsu",
                "Sec-Fetch-Site": "cross-site"}
    hasil = {nama: kirim(k, muatan(), headers={nama: nilai})[0] for nama, nilai in peramban.items()}
    assert hasil == {nama: 403 for nama in peramban}, hasil
    assert dump(admin_store.BAWAAN) == awal
    # Header peramban/proxy tidak dipercaya untuk apa pun: tidak mengubah kontrak.
    assert kirim(k, muatan(), headers={"X-Forwarded-Proto": "https"})[0] == 200
    assert kirim(k, muatan(), headers={"X-Forwarded-For": "10.0.0.1"})[0] == 200
    assert len(hint(admin_store.BAWAAN)) == 1
    assert kirim(k, muatan(), jalur=JALUR + "?x=1")[0] == 403
    assert kirim(k, None, metode="GET")[0] == 404
    assert kirim(k, None, metode="PUT")[0] in (404, 405, 501)
    assert len(hint(admin_store.BAWAAN)) == 1


def test_callback_memakai_runtime_terpasang_atau_config_server(uji):
    """Runtime terpasang dipakai bila sah; runtime asing/sandbox diabaikan, tanpa fallback."""
    k = uji
    k.server.server.pembayaran_runtime = SimpleNamespace(config=CFGP, transport=lambda *a, **kw: None)
    assert kirim(k, muatan())[0] == 200

    os.chmod(k.rahasia, 0o644)
    k.server.server.pembayaran_runtime = admin_subscription.RuntimePembayaran(
        CFGP, lambda *a, **kw: None, d.SAKELAR, dict(prod.kesiapan_produksi()))
    assert kirim(k, muatan())[0] == 200

    k.server.server.pembayaran_runtime = admin_subscription.RuntimePembayaran(
        replace(CFGP, lingkungan="sandbox"), lambda *a, **kw: None, d.SAKELAR, {})
    assert kirim(k, muatan())[0] == 503
    os.chmod(k.rahasia, 0o600)


def test_callback_kontrak_transport_ditolak_awal(uji):
    k = uji
    awal = dump(admin_store.BAWAAN)
    assert kirim(k, muatan(), tipe="text/plain")[0] == 415
    assert kirim(k, muatan(), tipe=None)[0] == 415
    assert kirim(k, None, mentah=b"x" * 9000)[0] == 413
    assert kirim(k, None, mentah=b"")[0] == 400
    assert dump(admin_store.BAWAAN) == awal
    mentah = ("POST %s HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n"
              "Connection: close\r\n\r\n" % JALUR).encode()
    with socket.create_connection((k.server.server.server_address[0],
                                   k.server.server.server_address[1]), timeout=10) as s:
        s.sendall(mentah)
        jawab = s.recv(4096).decode("utf-8", "replace")
    assert " 411 " in jawab.split("\r\n")[0] or jawab.split("\r\n")[0].endswith("411")
    assert dump(admin_store.BAWAAN) == awal
