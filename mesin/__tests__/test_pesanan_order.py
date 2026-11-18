"""Order Paket Coba: nominal tetap, kepemilikan, UNIQUE per anak, kuota, kontak, galat bersih."""
import inspect
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

import pesanan
import pesanan_dasar
from pesanan_kit import (AKUN_A, AKUN_B, MERCHANT, SEKARANG, SESUDAH_KEDALUWARSA, buat,
                         hitung, jumlah_semua_pesanan, ord_id, siapkan_db, terapkan)


@pytest.fixture
def db(tmp_path):
    return siapkan_db(tmp_path)


@pytest.fixture
def kon(db):
    with pesanan.buka(db, tulis_data=True) as k:
        yield k


def test_nominal_selalu_konstanta_server_dan_tidak_ada_parameter_nominal(kon):
    parameter = set(inspect.signature(pesanan.buat_order).parameters)
    assert not {p for p in parameter if "nominal" in p or "rupiah" in p or "harga" in p}
    assert pesanan.RUPIAH_PAKET == 49000
    order = buat(kon, 1)
    assert order["rupiah"] == 49000
    assert kon.execute("SELECT rupiah FROM pesanan_order").fetchone()[0] == 49000
    with pytest.raises(TypeError):
        buat(kon, 2, rupiah=1)
    with pytest.raises(TypeError):
        buat(kon, 3, nominal=1)
    assert hitung(kon, "pesanan_order") == 1


def test_nominal_mengikuti_konstanta_modul_bukan_input(kon, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "RUPIAH_PAKET", 51000)
    assert buat(kon, 1)["rupiah"] == 51000


def test_order_berisi_atribut_tetap_dan_kedaluwarsa_24_jam(kon):
    order = buat(kon, 1)
    assert (order["currency"], order["provider"], order["channel"]) == ("IDR", "midtrans", "qris")
    assert order["merchant"] == MERCHANT
    assert order["dibuat"] == SEKARANG and order["kedaluwarsa"] == "2026-11-19T10:00:00"
    assert order["order_id"].startswith("ord_") and len(order["order_id"]) == 36
    assert order["idempotency_key"] == "ord-" + order["order_id"][4:]
    assert 8 <= len(order["idempotency_key"]) <= 46
    assert order["baru"] is True


def test_id_order_acak_bila_tidak_disuntik(kon):
    satu = buat(kon, 1, order_id=None)
    dua = buat(kon, 2, order_id=None)
    assert satu["order_id"] != dua["order_id"]
    assert pesanan_dasar.periksa_order_id(satu["order_id"])


def test_waktu_berzona_dinormalisasi_ke_utc(kon):
    order = buat(kon, 1, sekarang="2026-11-18T17:00:00+07:00")
    assert order["dibuat"] == "2026-11-18T10:00:00"


@pytest.mark.parametrize("ganti", [
    dict(akun_id="akun_pendek"), dict(siswa_id=0), dict(siswa_id=True), dict(cek_id="1"),
    dict(merchant="bad merchant"), dict(order_id="inv_" + "1" * 32), dict(sekarang="kemarin"),
    dict(sekarang=1700000000),
])
def test_masukan_tidak_sah_ditolak_tanpa_tulis(kon, ganti):
    with pytest.raises(pesanan.PesananDataTidakSah):
        buat(kon, 1, **ganti)
    assert jumlah_semua_pesanan(kon) == dict.fromkeys(jumlah_semua_pesanan(kon), 0)


@pytest.mark.parametrize("selesai", [False, None, 1, "true"])
def test_cek_belum_selesai_ditolak_sebagai_tidak_ditemukan_tanpa_efek(kon, selesai):
    with pytest.raises(pesanan.PesananTidakDitemukan):
        buat(kon, 1, cek_selesai=selesai)
    assert hitung(kon, "pesanan_order") == 0


def test_akun_lain_tidak_bisa_memesan_atau_melihat_status_milik_orang(kon):
    milik_a = buat(kon, 1)
    with pytest.raises(pesanan.PesananTidakDitemukan) as lain_pesan:
        buat(kon, 99, akun=AKUN_B, siswa=1, order_id=ord_id(99))
    with pytest.raises(pesanan.PesananTidakDitemukan) as lain_status:
        pesanan.status_order(kon, milik_a["order_id"], AKUN_B, SEKARANG)
    with pytest.raises(pesanan.PesananTidakDitemukan) as tak_ada:
        pesanan.status_order(kon, ord_id(12345), AKUN_B, SEKARANG)
    with pytest.raises(pesanan.PesananTidakDitemukan) as format_salah:
        pesanan.status_order(kon, "bukan-id", "bukan-akun", SEKARANG)
    with pytest.raises(pesanan.PesananTidakDitemukan) as ambil:
        pesanan.ambil_order(kon, milik_a["order_id"], AKUN_B)
    assert {str(e.value) for e in (lain_pesan, lain_status, tak_ada, format_salah, ambil)} == {
        "pesanan tidak ditemukan"}
    assert hitung(kon, "pesanan_order") == 1
    assert hitung(kon, "pesanan_pengamatan") == 0


def test_pemilik_sah_melihat_status_dan_data_minimal(kon):
    order = buat(kon, 1)
    status = pesanan.status_order(kon, order["order_id"], AKUN_A, SEKARANG)
    assert status == {"order_id": order["order_id"], "rupiah": 49000, "dibuat": SEKARANG,
                      "kedaluwarsa": order["kedaluwarsa"], "status": "belum_bayar"}
    assert pesanan.ambil_order(kon, order["order_id"], AKUN_A)["siswa_id"] == 1


def test_satu_order_per_anak_idempoten_untuk_pemilik_sama(kon):
    pertama = buat(kon, 1)
    ulang = buat(kon, 1, order_id=ord_id(777))
    assert ulang["order_id"] == pertama["order_id"] and ulang["baru"] is False
    assert hitung(kon, "pesanan_order") == 1


def test_order_idempoten_tetap_dikembalikan_walau_kuota_habis_atau_kontak_hilang(kon, monkeypatch):
    pertama = buat(kon, 1)
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 1)
    assert buat(kon, 1, punya_kontak=False)["order_id"] == pertama["order_id"]


def test_tanpa_kontak_tidak_ada_baris_apa_pun(kon):
    with pytest.raises(pesanan.PesananButuhKontak):
        buat(kon, 1, punya_kontak=False)
    for nilai in (None, 0, "ya"):
        with pytest.raises(pesanan.PesananButuhKontak):
            buat(kon, 1, punya_kontak=nilai)
    assert jumlah_semua_pesanan(kon) == dict.fromkeys(jumlah_semua_pesanan(kon), 0)


def test_kuota_dua_puluh_ditegakkan_pada_batas_tanpa_menulis(kon):
    assert pesanan.KUOTA_ORDER == 20
    for n in range(1, 21):
        buat(kon, n)
    with pytest.raises(pesanan.PesananKuotaHabis):
        buat(kon, 21)
    assert hitung(kon, "pesanan_order") == 20


def test_kuota_menghitung_lunas_dan_perlu_diperiksa_tetapi_bukan_kedaluwarsa_tanpa_receipt(kon, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 3)
    lunas, salah, kadaluarsa = buat(kon, 1), buat(kon, 2), buat(kon, 3)
    terapkan(kon, lunas, 1, transaction_id="trx-1")
    terapkan(kon, salah, 2, transaction_id="trx-2", gross_amount="48000")
    with pytest.raises(pesanan.PesananKuotaHabis):
        buat(kon, 4)
    # Order ke-3 kedaluwarsa tanpa receipt: slotnya dibebaskan, yang ber-receipt tetap dihitung.
    buat(kon, 4, sekarang=SESUDAH_KEDALUWARSA)
    with pytest.raises(pesanan.PesananKuotaHabis):
        buat(kon, 5, sekarang=SESUDAH_KEDALUWARSA)
    assert hitung(kon, "pesanan_order") == 4
    assert kadaluarsa["order_id"]


def test_kuota_tidak_terlampaui_pada_balapan_banyak_koneksi(db, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 3)

    def coba(n):
        with pesanan.buka(db, tulis_data=True) as k:
            try:
                buat(k, n)
                return "ok"
            except pesanan.PesananKuotaHabis:
                return "habis"
            except sqlite3.OperationalError:
                return "terkunci"

    with ThreadPoolExecutor(max_workers=8) as pool:
        hasil = list(pool.map(coba, range(1, 9)))
    with pesanan.buka(db) as k:
        assert hitung(k, "pesanan_order") == hasil.count("ok") <= 3
    assert hasil.count("ok") + hasil.count("habis") + hasil.count("terkunci") == 8
    assert hasil.count("ok") >= 1


def test_koneksi_dalam_transaksi_ditolak_agar_kuota_tetap_atomik(db):
    with pesanan.buka(db, tulis_data=True) as k:
        k.execute("BEGIN IMMEDIATE")
        with pytest.raises(pesanan.PesananDataTidakSah):
            buat(k, 1)
        k.rollback()
        assert hitung(k, "pesanan_order") == 0


def test_koneksi_tanpa_row_factory_ditolak(db):
    with sqlite3.connect(db) as polos:
        with pytest.raises(pesanan.PesananDataTidakSah):
            buat(polos, 1)


def test_galat_tidak_memuat_id_nominal_atau_nama(kon):
    kon.execute("SELECT 1")
    percobaan = [
        lambda: buat(kon, 1, punya_kontak=False),
        lambda: buat(kon, 1, cek_selesai=False),
        lambda: pesanan.status_order(kon, ord_id(5), AKUN_B, SEKARANG),
        lambda: buat(kon, 1, akun_id="akun_pendek"),
    ]
    pesan = []
    for jalankan in percobaan:
        with pytest.raises(pesanan.PesananError) as galat:
            jalankan()
        pesan.append(str(galat.value))
    buat(kon, 2)
    for jalankan in (lambda: buat(kon, 3, siswa=2, akun=AKUN_B),):
        with pytest.raises(pesanan.PesananError) as galat:
            jalankan()
        pesan.append(str(galat.value))
    kuota = pesanan_dasar.KUOTA_ORDER
    for teks in pesan:
        assert AKUN_A not in teks and AKUN_B not in teks and "ord_" not in teks
        assert "49000" not in teks and str(kuota) not in teks and MERCHANT not in teks


def _jejak_sql(kon, jalankan):
    pernyataan = []
    kon.set_trace_callback(pernyataan.append)
    try:
        jalankan()
    finally:
        kon.set_trace_callback(None)
    return [p.strip() for p in pernyataan]


def _urutan_atomik_ok(sql):
    """BEGIN IMMEDIATE lebih dulu dari bacaan pesanan_*, COMMIT sesudah tulisan terakhir."""
    awal = next((i for i, p in enumerate(sql) if p.startswith("BEGIN IMMEDIATE")), None)
    baca = next((i for i, p in enumerate(sql) if "pesanan_" in p and p.startswith("SELECT")), None)
    tulis = [i for i, p in enumerate(sql) if p.startswith("INSERT")]
    akhir = next((i for i, p in enumerate(sql) if p == "COMMIT"), None)
    return (awal is not None and baca is not None and awal < baca
            and tulis and akhir is not None and akhir > max(tulis))


def test_penulisan_domain_memakai_begin_immediate_sebelum_membaca_dan_commit_sesudah_tulis(kon):
    order = None

    def buat_satu():
        nonlocal order
        order = buat(kon, 1)
    assert _urutan_atomik_ok(_jejak_sql(kon, buat_satu))
    assert _urutan_atomik_ok(_jejak_sql(kon, lambda: terapkan(kon, order, 1)))
    assert _urutan_atomik_ok(_jejak_sql(kon, lambda: pesanan.catat_refund(
        kon, order["order_id"], "op-refund-01", "admin_a", "kebijakan", SEKARANG)))
    assert _urutan_atomik_ok(_jejak_sql(kon, lambda: pesanan.catat_yatim(
        kon, ord_id(404), "pending", "ab" * 32, SEKARANG, "op-yatim-01")))
