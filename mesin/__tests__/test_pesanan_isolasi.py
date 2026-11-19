"""Isolasi pesanan dari langganan/provider/DB belajar, paritas kontrak, retensi hapus keluarga."""
import ast
import json
from pathlib import Path
import sqlite3

import pytest

import cek_gratis
import family_deletion
import midtrans_contract
import pesanan
import pesanan_provider
import subscription as sub
from pesanan_kit import (AKUN_A, MERCHANT, SEKARANG, buat, hasil_status, jumlah_semua_pesanan,
                         operasi, ord_id, siapkan_db, snapshot_langganan, terapkan)

MESIN = Path(__file__).resolve().parent.parent
BERKAS = ["schema_pesanan.py", "pesanan.py", "pesanan_dasar.py", "pesanan_status.py",
          "pesanan_order.py", "pesanan_provider.py", "pesanan_admin.py", "schema_transfer.py",
          "pesanan_transfer.py", "pesanan_transfer_baca.py", "pesanan_admin_transfer.py",
          "pesanan_transfer_ulang.py", "pesanan_retensi.py", "pesanan_transfer_migrasi.py"]
TERLARANG = {"subscription", "subscription_store", "subscription_schema", "subscription_callback",
             "subscription_package_store", "midtrans_contract", "midtrans_produksi", "midtrans_secret",
             "database", "cek_gratis", "kontak_akun", "auth", "web", "urllib", "http", "socket",
             "requests"}
HEX = "ef" * 32


@pytest.fixture
def db(tmp_path):
    path = siapkan_db(tmp_path)
    with sqlite3.connect(path) as kon:
        kon.execute("INSERT INTO langganan_enrollment VALUES(?,?,?,?,?,NULL,'langganan-v1')",
                    (AKUN_A, "sumber_0001", "transisi", 0, 0))
    return path


def _alur_penuh(kon):
    order = buat(kon, 1)
    pesanan.catat_petunjuk(kon, order["order_id"], {"transaction_status": "pending"}, SEKARANG, operasi(1))
    terapkan(kon, order, 2)
    pesanan.catat_refund(kon, order["order_id"], operasi(3), "admin_a", "kebijakan", SEKARANG)
    pesanan.catat_yatim(kon, ord_id(404), "settlement", HEX, SEKARANG, operasi(4))
    pesanan.status_order(kon, order["order_id"], AKUN_A, SEKARANG)
    pesanan.daftar_admin(kon, halaman=1, per_halaman=5, sekarang=SEKARANG)


def test_alur_penuh_tidak_mengubah_satu_baris_langganan_atau_paket(db):
    with pesanan.buka(db) as baca:
        sebelum = snapshot_langganan(baca)
    assert sebelum["langganan_enrollment"], "fixture harus punya baris langganan"
    with pesanan.buka(db, tulis_data=True) as kon:
        _alur_penuh(kon)
        assert snapshot_langganan(kon) == sebelum
        assert sum(jumlah_semua_pesanan(kon).values()) >= 5


def test_sql_yang_dijalankan_domain_tidak_menyebut_tabel_langganan_atau_invoice(db):
    pernyataan = []
    with pesanan.buka(db, tulis_data=True) as kon:
        kon.set_trace_callback(pernyataan.append)
        _alur_penuh(kon)
        kon.set_trace_callback(None)
    teks = "\n".join(pernyataan).lower()
    assert "insert into pesanan_" in teks
    for terlarang in ("langganan_", "paket_", "invoice", "kuota_pendamping", "penutupan_tagihan"):
        assert terlarang not in teks


def test_sumber_pesanan_tidak_mengimpor_langganan_provider_atau_db_belajar():
    for nama in BERKAS:
        pohon = ast.parse((MESIN / nama).read_text())
        impor = set()
        for node in ast.walk(pohon):
            if isinstance(node, ast.Import):
                impor |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                impor.add((node.module or "").split(".")[0])
        assert not (impor & TERLARANG), (nama, impor & TERLARANG)
        teks = (MESIN / nama).read_text()
        assert "langganan_" not in teks.replace("tabel `langganan_*`", "").replace("`langganan_*`", ""), nama


def test_gerbang_adalah_satu_satunya_tempat_yang_mengimpor_modul_produksi():
    pohon = ast.parse((MESIN / "pesanan.py").read_text())
    impor_fungsi = {n.names[0].name for n in ast.walk(pohon) if isinstance(n, ast.Import)}
    assert impor_fungsi == {"funnel_flag", "subscription_produksi", "admin_launch_service", "admin_store"}


@pytest.mark.parametrize("nilai", [
    "49000", "49000.00", 49000, "0", 0, "0.00", "00", "049000", "49000.5", "49000.000", "-1", -1,
    "1e3", " 49000", "49000 ", "99999999", "100000000", "10000000", "10000001", 10000000, 49000.0, None, True, False, b"49000",
    "", "٤٩٠٠٠", "49,000",
])
def test_parser_nominal_setara_kontrak_midtrans(nilai):
    assert pesanan_provider.BATAS_NOMINAL == sub.BATAS_RUPIAH
    try:
        diharapkan = midtrans_contract.nominal_provider(nilai)
    except ValueError:  # KontrakTidakSah dan batas subscription.bilangan
        diharapkan = None
    assert pesanan_provider.nominal_provider(nilai) == diharapkan


class _Respons:
    status = 200

    def __init__(self, url, badan):
        self.url, self._badan = url, badan
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _n):
        return json.dumps(self._badan).encode()


def _kelas_kontrak(badan, inv_id):
    """Klasifikasi kontrak midtrans_contract.status_ulang atas badan status sintetis."""
    config = midtrans_contract.Konfigurasi("sandbox", "kunci-sintetis", MERCHANT)
    invoice = {"invoice_id": inv_id, "akun_id": AKUN_A, "rupiah": 49000, "merchant": MERCHANT,
               "provider": "midtrans", "channel": "qris"}
    transport = lambda req, timeout, allow_redirects: _Respons(req.url, dict(badan, order_id=inv_id))
    kelas, _, _ = midtrans_contract.status_ulang(
        config, invoice, akun_id=AKUN_A, transport=transport,
        sakelar=sub.Sakelar(True, True, True, False))
    return kelas


KASUS_PARITAS = [
    {}, {"fraud_status": None}, {"fraud_status": "challenge"}, {"status_code": "201"},
    {"transaction_status": "pending", "status_code": "201"}, {"transaction_status": "capture"},
    {"transaction_status": "refund"}, {"transaction_status": "partial_refund"},
    {"transaction_status": "expire", "status_code": "407"}, {"transaction_status": "deny"},
    {"gross_amount": "48000"}, {"gross_amount": "49000.50"}, {"merchant_id": "M_LAIN"},
    {"currency": "USD"}, {"payment_type": "gopay"},
]


@pytest.mark.parametrize("ganti", KASUS_PARITAS)
def test_lunas_dan_refund_setara_klasifikasi_kontrak_midtrans(ganti, tmp_path):
    inv = "inv_" + "5" * 32
    dasar = hasil_status({"order_id": inv}, **{k: v for k, v in ganti.items() if v is not None})
    dasar.update({k: v for k, v in ganti.items() if v is None})
    dasar = {k: v for k, v in dasar.items() if v is not None}
    kontrak = _kelas_kontrak({k: v for k, v in dasar.items() if k != "order_id"}, inv)
    with pesanan.buka(siapkan_db(tmp_path), tulis_data=True) as kon:
        order = buat(kon, 1)
        data = dict(dasar, order_id=order["order_id"])
        hasil = pesanan.terapkan_hasil_provider(kon, order["order_id"], data, SEKARANG, operasi(1))
    assert (hasil["receipt"] == "lunas") == (kontrak == "lunas")
    if kontrak == "perlu_diperiksa":
        assert hasil["receipt"] == "perlu_diperiksa"
    if kontrak == "pending":
        assert hasil["receipt"] is None


@pytest.mark.parametrize("hasil,harapan", [
    ({"status": "selesai", "skor": 12, "kategori": "x", "ringkasan": {}, "jumlah_soal": 20}, True),
    ({"status": "selesai", "skor": 0}, True),
    ({"status": "selesai", "skor": None}, False),
    ({"status": "selesai", "skor": True}, False),
    ({"status": "selesai", "skor": "12"}, False),
    ({"status": "belum_selesai"}, False),
    ({"status": "belum_mulai"}, False),
    ({}, False), (None, False), ("selesai", False), ([], False),
])
def test_periksa_prasyarat_cek_hanya_status_selesai_bernilai_skor(hasil, harapan):
    assert pesanan.periksa_prasyarat_cek(hasil) is harapan


def test_periksa_prasyarat_cek_dengan_bentuk_nyata_baca_hasil():
    for status in ("belum_mulai", "belum_selesai"):
        bentuk = cek_gratis._hasil_tanpa_skor(status, 20)
        assert bentuk["status"] == status and pesanan.periksa_prasyarat_cek(bentuk) is False


def test_hapus_keluarga_tidak_menyentuh_ledger_pesanan_perlakuan_pertahankan(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        _alur_penuh(kon)
        sebelum = {t: tuple(tuple(r) for r in kon.execute("SELECT * FROM %s" % t))
                   for t in ("pesanan_order", "pesanan_pengamatan", "pesanan_receipt",
                             "pesanan_refund", "pesanan_yatim")}
    family_deletion._ubah_admin(db, AKUN_A)
    with pesanan.buka(db) as baca:
        for tabel, isi in sebelum.items():
            assert tuple(tuple(r) for r in baca.execute("SELECT * FROM %s" % tabel)) == isi
    assert ("receipt/journal operasi dan ledger layanan/finansial immutable", "pertahankan") \
        in family_deletion.MATRIS_RETENSI
