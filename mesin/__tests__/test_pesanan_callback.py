"""Cabang callback `ord_` (3c-2): petunjuk durable, yatim, dan `inv_` tidak berubah.

Memakai server loopback + konteks sintetis dari tes callback langganan; DB admin
sementara dengan skema pesanan. Tanpa jaringan, secret nyata, atau DB nyata.
"""
import os
import re
import sqlite3

import pytest

import admin_store
import pesanan
import pesanan_callback
import schema_pesanan
from pesanan_kit import AKUN_A, SEKARANG, buat, ord_id, snapshot_langganan
from test_subscription_callback import (  # noqa: F401  (fixture `uji` dipakai ulang)
    INVOICE, JALUR, KUNCI, MERCHANT, hint, kirim, muatan, uji,
)
from test_subscription_store import dump

ORD = ord_id(1)
ORD_ASING = ord_id(404)
NOMINAL = 49000
TRANSAKSI = "trx_sintetis"


@pytest.fixture
def uji_p(uji):
    """`uji` + skema pesanan + satu order sintetis (ORD) milik AKUN_A."""
    schema_pesanan.migrasikan(admin_store.BAWAAN)
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        buat(kon, 1)
    return uji


def _ord(order_id=ORD, **ubah):
    ubah.setdefault("nominal", NOMINAL)
    return muatan(order_id, **ubah)


def _baris(sql, *arg):
    with pesanan.buka(admin_store.BAWAAN) as kon:
        return [tuple(b) for b in kon.execute(sql, arg)]


def _pengamatan():
    return _baris("SELECT operasi_id,order_id,sumber,transaction_status,status_code,"
                  "transaksi_id,gross_amount_teks FROM pesanan_pengamatan ORDER BY rowid")


def _yatim():
    return _baris("SELECT operasi_id,order_id_teks,status_hint,hash_payload "
                  "FROM pesanan_yatim ORDER BY rowid")


def _jumlah(tabel):
    return _baris("SELECT COUNT(*) FROM " + tabel)[0][0]


def _langganan():
    with pesanan.buka(admin_store.BAWAAN) as kon:
        return snapshot_langganan(kon)


def _status():
    with pesanan.buka(admin_store.BAWAAN) as kon:
        return pesanan.status_order(kon, ORD, AKUN_A, SEKARANG)["status"]


def _ledak(*a, **kw):
    raise sqlite3.OperationalError("database is locked (sintetis)")


# --- order dikenal -------------------------------------------------------------------

def test_ord_valid_order_ada_tulis_pengamatan_callback_tanpa_receipt(uji_p):
    status_awal, langganan_awal = _status(), _langganan()
    kode, isi, headers = kirim(uji_p, _ord())
    assert (kode, isi) == (200, "OK")
    assert headers["Cache-Control"] == "no-store"
    assert "Location" not in headers and "Set-Cookie" not in headers
    assert _jumlah("pesanan_receipt") == 0
    assert _status() == status_awal == "belum_bayar"
    baris = _pengamatan()
    assert len(baris) == 1
    operasi, order_id, sumber, status, kode_status, transaksi, nominal = baris[0]
    assert operasi.startswith("cbk_") and len(operasi) == 36
    assert (order_id, sumber, status, kode_status) == (ORD, "callback", "settlement", "200")
    assert transaksi == TRANSAKSI
    assert _jumlah("pesanan_receipt") == 0 and _jumlah("pesanan_yatim") == 0
    assert _status() == status_awal == "belum_bayar"
    assert _langganan() == langganan_awal
    assert hint(admin_store.BAWAAN) == []


def test_ord_callback_settlement_tidak_pernah_membuat_receipt_atau_status_dibayar(uji_p):
    for data in (_ord(), _ord(status="pending", kode="201"), _ord(status="refund"),
                 _ord(status="expire", kode="407")):
        assert kirim(uji_p, data)[0] == 200
    assert _jumlah("pesanan_receipt") == 0
    assert _status() == "belum_bayar"
    assert len(_pengamatan()) == 4


def test_ord_callback_ganda_identik_idempoten_satu_baris(uji_p):
    data = _ord()
    assert [kirim(uji_p, data)[0] for _ in range(3)] == [200, 200, 200]
    assert len(_pengamatan()) == 1
    assert _jumlah("pesanan_yatim") == 0


def test_ord_tuple_beda_operasi_id_sama_dijawab_409_tanpa_baris_baru(uji_p):
    assert kirim(uji_p, _ord())[0] == 200
    sebelum = dump(admin_store.BAWAAN)
    # Nominal beda tetapi field penentu operasi_id sama: tuple pengamatan berbeda.
    kode, isi, _ = kirim(uji_p, _ord(nominal=50000))
    assert (kode, isi) == (409, "petunjuk berbeda")
    assert dump(admin_store.BAWAAN) == sebelum


def test_ord_penyimpanan_gagal_dijawab_503_tanpa_ack(uji_p, monkeypatch):
    asli = pesanan.catat_petunjuk
    monkeypatch.setattr(pesanan, "catat_petunjuk", _ledak)
    assert kirim(uji_p, _ord())[0] == 503
    monkeypatch.setattr(pesanan, "catat_petunjuk", asli)
    assert _pengamatan() == [] and _yatim() == []


# --- order tak dikenal -> yatim -----------------------------------------------------

def test_ord_tak_dikenal_signature_sah_tulis_yatim_durable_lalu_200(uji_p):
    langganan_awal = _langganan()
    kode, isi, _ = kirim(uji_p, _ord(ORD_ASING))
    assert (kode, isi) == (200, "OK")
    baris = _yatim()
    assert len(baris) == 1
    operasi, teks, hint_status, sidik = baris[0]
    assert operasi.startswith("cbk_") and teks == ORD_ASING
    assert hint_status == "belum_terverifikasi"
    assert re.fullmatch(r"[0-9a-f]{64}", sidik)
    assert _pengamatan() == [] and _jumlah("pesanan_receipt") == 0
    assert _langganan() == langganan_awal


def test_ord_tak_dikenal_status_refund_menjadi_hint_perlu_diperiksa(uji_p):
    assert kirim(uji_p, _ord(ORD_ASING, status="refund"))[0] == 200
    assert _yatim()[0][2] == "perlu_diperiksa"


def test_ord_yatim_tidak_memuat_payload_nominal_nama_atau_signature(uji_p):
    data = _ord(ORD_ASING, customer_details={"first_name": "Nama Sintetis"}, issuer="bank-lain")
    assert kirim(uji_p, data)[0] == 200
    teks = "\n".join(map(repr, _yatim()))
    for terlarang in (TRANSAKSI, data["signature_key"], "49000", "Nama Sintetis", "bank-lain",
                      KUNCI, MERCHANT):
        assert terlarang not in teks
    assert KUNCI not in "\n".join(dump(admin_store.BAWAAN))


def test_ord_yatim_gagal_tulis_dijawab_503_dan_tidak_ada_200(uji_p, monkeypatch):
    asli = pesanan.catat_yatim
    monkeypatch.setattr(pesanan, "catat_yatim", _ledak)
    kode, isi, _ = kirim(uji_p, _ord(ORD_ASING))
    assert (kode, isi) == (503, "penyimpanan belum siap")
    monkeypatch.setattr(pesanan, "catat_yatim", asli)
    assert _yatim() == [] and _pengamatan() == []
    # Provider mencoba lagi setelah store pulih: kini tercatat dan dijawab 200.
    assert kirim(uji_p, _ord(ORD_ASING))[0] == 200
    assert len(_yatim()) == 1


def test_ord_yatim_ganda_idempoten_dan_isi_beda_operasi_sama_409(uji_p):
    data = _ord(ORD_ASING)
    assert [kirim(uji_p, data)[0] for _ in range(3)] == [200, 200, 200]
    assert len(_yatim()) == 1
    assert kirim(uji_p, _ord(ORD_ASING, nominal=50000))[0] == 409
    assert len(_yatim()) == 1


def test_ord_skema_pesanan_belum_dipasang_dijawab_503(uji):
    # `uji` tanpa migrasi pesanan: tidak ada tempat tulis durable -> tidak boleh 200.
    awal = dump(admin_store.BAWAAN)
    assert kirim(uji, _ord())[0] == 503
    assert dump(admin_store.BAWAAN) == awal


# --- pemeriksaan umum tetap berlaku untuk ord_ ---------------------------------------

def test_ord_signature_salah_ditolak_403_tanpa_efek(uji_p):
    awal = dump(admin_store.BAWAAN)
    rusak = _ord()
    rusak["signature_key"] = "0" * 128
    kasus = [rusak, _ord(kunci="Mid-server-SALAH"), _ord(ORD_ASING, kunci="Mid-server-SALAH"),
             _ord(merchant="M_ASING"), _ord(currency="USD"), _ord(payment_type="bank_transfer"),
             _ord(transaction_id=""), _ord("ord_" + "A" * 32), _ord("ord_" + "a" * 31),
             _ord("ord_" + "a" * 32 + "x"), _ord(status_code="abc")]
    jawab = [kirim(uji_p, data)[:2] for data in kasus]
    assert [kode for kode, _ in jawab] == [403] * len(kasus)
    assert len({isi for _, isi in jawab}) == 1
    assert dump(admin_store.BAWAAN) == awal


def test_ord_signature_diverifikasi_dengan_kunci_dan_algoritma_yang_sama():
    import hashlib
    import json
    import midtrans_contract as m
    from test_subscription_callback import CFGP
    mentah = json.dumps(_ord(ORD_ASING)).encode()
    assert m.signature_cocok(mentah, CFGP) is True
    data = json.loads(mentah)
    data["gross_amount"] = "1.00"
    assert m.signature_cocok(json.dumps(data).encode(), CFGP) is False
    assert hashlib.sha512(
        (ORD_ASING + "200" + "49000.00" + KUNCI).encode()).hexdigest() == _ord(ORD_ASING)["signature_key"]


def test_ord_transport_dan_header_peramban_ditolak_seperti_sebelumnya(uji_p):
    awal = dump(admin_store.BAWAAN)
    peramban = {"Origin": uji_p.server.alamat, "Referer": uji_p.server.alamat + "/guru",
                "Authorization": "Basic Z3VydTpzYW5kaS1ndXJ1", "Cookie": "osn_sesi=palsu",
                "Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "cors"}
    for nama, nilai in peramban.items():
        assert kirim(uji_p, _ord(), headers={nama: nilai})[0] == 403, nama
    assert kirim(uji_p, _ord(), tipe="text/plain")[0] == 415
    assert kirim(uji_p, _ord(), tipe=None)[0] == 415
    assert kirim(uji_p, None, mentah=b"x" * 9000)[0] == 413
    assert kirim(uji_p, None, mentah=b"")[0] == 400
    assert kirim(uji_p, _ord(), jalur=JALUR + "?x=1")[0] == 403
    assert kirim(uji_p, None, metode="GET")[0] == 404
    assert dump(admin_store.BAWAAN) == awal


def test_ord_ikut_gerbang_readiness_yang_sudah_berlaku(uji_p):
    """Tidak ada gerbang baru: secret/tahap yang menolak `inv_` menolak `ord_` juga."""
    os.chmod(uji_p.rahasia, 0o644)
    assert kirim(uji_p, _ord())[0] == 503
    os.chmod(uji_p.rahasia, 0o600)
    with admin_store._transaksi(admin_store.BAWAAN) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap='nonaktif'")
    assert kirim(uji_p, _ord())[0] == 503
    assert kirim(uji_p, _ord(ORD_ASING))[0] == 503
    with admin_store._transaksi(admin_store.BAWAAN) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap='rekonsiliasi'")
    assert _pengamatan() == [] and _yatim() == []
    assert kirim(uji_p, _ord())[0] == 200


# --- inv_ tidak berubah --------------------------------------------------------------

def test_inv_tetap_menulis_hint_langganan_dan_tidak_menyentuh_tabel_pesanan(uji_p):
    kode, isi, headers = kirim(uji_p, muatan())
    assert (kode, isi) == (200, "OK")
    assert headers["Cache-Control"] == "no-store"
    baris = hint(admin_store.BAWAAN)
    assert len(baris) == 1
    assert (baris[0][1], baris[0][2], baris[0][3]) == (INVOICE, "belum_terverifikasi", None)
    assert _pengamatan() == [] and _yatim() == []
    assert _jumlah("pesanan_receipt") == 0
    # Replay identik, order asing, dan penolakan: respons sama seperti jalur lama.
    assert kirim(uji_p, muatan())[0] == 200 and len(hint(admin_store.BAWAAN)) == 1
    asing = kirim(uji_p, muatan("inv_" + "9" * 32))
    assert (asing[0], asing[1]) == (200, "OK")
    assert _yatim() == []
    rusak = muatan()
    rusak["signature_key"] = "0" * 128
    assert kirim(uji_p, rusak)[:2] == (403, "ditolak")
    assert kirim(uji_p, muatan("bukan_invoice"))[0] == 403
    assert kirim(uji_p, muatan("INV_" + "1" * 32))[0] == 403
    assert kirim(uji_p, muatan(" ord_" + "1" * 32))[0] == 403
    assert _pengamatan() == [] and _yatim() == []


def test_inv_tanpa_skema_pesanan_tetap_200_seperti_sebelumnya(uji):
    assert kirim(uji, muatan())[:2] == (200, "OK")
    assert len(hint(admin_store.BAWAAN)) == 1


def test_inv_konflik_dan_gagal_simpan_tetap_kode_lama(uji_p, monkeypatch):
    import subscription_store as store
    asli = store.catat_pengamatan
    monkeypatch.setattr(store, "catat_pengamatan", _ledak)
    assert kirim(uji_p, muatan())[:2] == (503, "penyimpanan belum siap")
    monkeypatch.setattr(store, "catat_pengamatan", asli)
    assert hint(admin_store.BAWAAN) == []


# --- unit pesanan_callback -----------------------------------------------------------

def test_operasi_id_deterministik_dan_berbeda_antar_pengamatan():
    a, b = _ord(), _ord()
    assert pesanan_callback._operasi_id(a) == pesanan_callback._operasi_id(b)
    assert pesanan_callback._operasi_id(a) != pesanan_callback._operasi_id(
        _ord(transaction_id="trx_lain"))
    assert pesanan_callback._operasi_id(a) != pesanan_callback._operasi_id(_ord(status="pending"))
    assert pesanan_callback._operasi_id(a) != pesanan_callback._operasi_id(_ord(ORD_ASING))
    assert pesanan_callback.milik_pesanan(ORD) and not pesanan_callback.milik_pesanan(INVOICE)
    assert not pesanan_callback.milik_pesanan(None) and not pesanan_callback.milik_pesanan(7)
