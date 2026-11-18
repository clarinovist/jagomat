"""Yatim durable, refund manual, daftar admin minimal."""
import sqlite3

import pytest

import pesanan
from pesanan_kit import (AKUN_A, MERCHANT, SEKARANG, buat, hitung, operasi, ord_id, siapkan_db,
                         terapkan)

HEX = "cd" * 32


@pytest.fixture
def db(tmp_path):
    return siapkan_db(tmp_path)


@pytest.fixture
def kon(db):
    with pesanan.buka(db, tulis_data=True) as k:
        yield k


def yatim(kon):
    return [tuple(r) for r in kon.execute(
        "SELECT operasi_id,order_id_teks,status_hint,hash_payload,dibuat FROM pesanan_yatim")]


def test_yatim_ditulis_durable_di_db_dan_selamat_setelah_koneksi_ditutup(db):
    with pesanan.buka(db, tulis_data=True) as k:
        assert pesanan.catat_yatim(k, ord_id(404), "settlement", HEX, SEKARANG, operasi(1)) is True
    with pesanan.buka(db) as baca:
        assert yatim(baca) == [(operasi(1), ord_id(404), "settlement", HEX, SEKARANG)]
        assert hitung(baca, "pesanan_order") == 0


def test_yatim_idempoten_dan_konflik_bila_isi_beda(kon):
    assert pesanan.catat_yatim(kon, ord_id(404), "pending", HEX, SEKARANG, operasi(1)) is True
    assert pesanan.catat_yatim(kon, ord_id(404), "pending", HEX, SEKARANG, operasi(1)) is False
    with pytest.raises(pesanan.PesananKonflik):
        pesanan.catat_yatim(kon, ord_id(404), "settlement", HEX, SEKARANG, operasi(1))
    assert pesanan.catat_yatim(kon, ord_id(404), "pending", HEX, SEKARANG, operasi(2)) is True
    assert hitung(kon, "pesanan_yatim") == 2


def test_yatim_memotong_dan_membersihkan_id_serta_menolak_hash_dan_operasi_buruk(kon):
    pesanan.catat_yatim(kon, "ord_" + "x" * 100 + "<b>", "Settlement!", HEX, SEKARANG, operasi(1))
    pesanan.catat_yatim(kon, "ord_a b<c>", "pending", HEX, SEKARANG, operasi(2))
    baris = yatim(kon)
    assert baris[0][1] == "ord_" + "x" * 36 and baris[0][2] == "tidak_dikenal"
    assert baris[1][1] == "ord_a?b?c?"
    for argumen in [("", "pending", HEX), (None, "pending", HEX), ("ord_x", "pending", "bukan-hash"),
                    ("ord_x", "pending", HEX.upper())]:
        with pytest.raises(pesanan.PesananDataTidakSah):
            pesanan.catat_yatim(kon, *argumen, SEKARANG, operasi(3))
    with pytest.raises(pesanan.PesananDataTidakSah):
        pesanan.catat_yatim(kon, "ord_x", "pending", HEX, SEKARANG, "pendek")
    assert hitung(kon, "pesanan_yatim") == 2


def test_yatim_tidak_membuat_order_receipt_atau_baris_lain(kon):
    pesanan.catat_yatim(kon, ord_id(404), "settlement", HEX, SEKARANG, operasi(1))
    for tabel in ("pesanan_order", "pesanan_pengamatan", "pesanan_receipt", "pesanan_refund"):
        assert hitung(kon, tabel) == 0


def test_refund_hanya_untuk_order_dengan_receipt_dan_status_menjadi_direfund(kon):
    order = buat(kon, 1)
    with pytest.raises(pesanan.PesananKonflik):
        pesanan.catat_refund(kon, order["order_id"], operasi(1), "admin_a", "kebijakan", SEKARANG)
    assert hitung(kon, "pesanan_refund") == 0
    terapkan(kon, order, 2)
    hasil = pesanan.catat_refund(kon, order["order_id"], operasi(3), "admin_a", "permintaan_pembeli",
                                 SEKARANG)
    assert hasil == {"status": "direfund", "baru": True}
    assert pesanan.status_order(kon, order["order_id"], AKUN_A, SEKARANG)["status"] == "direfund"


def test_refund_boleh_untuk_receipt_perlu_diperiksa(kon):
    order = buat(kon, 1)
    terapkan(kon, order, 1, gross_amount="48000")
    assert pesanan.catat_refund(kon, order["order_id"], operasi(2), "admin_a", "kesalahan_sistem",
                                SEKARANG)["status"] == "direfund"


def test_refund_idempoten_per_operasi_konflik_isi_beda_dan_satu_per_order(kon):
    order = buat(kon, 1)
    terapkan(kon, order, 1)
    awal = pesanan.catat_refund(kon, order["order_id"], operasi(2), "admin_a", "kebijakan", SEKARANG)
    ulang = pesanan.catat_refund(kon, order["order_id"], operasi(2), "admin_a", "kebijakan", SEKARANG)
    assert awal["baru"] is True and ulang["baru"] is False and ulang["status"] == "direfund"
    with pytest.raises(pesanan.PesananKonflik):
        pesanan.catat_refund(kon, order["order_id"], operasi(2), "admin_b", "kebijakan", SEKARANG)
    with pytest.raises(pesanan.PesananKonflik):
        pesanan.catat_refund(kon, order["order_id"], operasi(3), "admin_a", "kebijakan", SEKARANG)
    assert hitung(kon, "pesanan_refund") == 1


def test_refund_order_tak_ada_masukan_buruk_dan_tanpa_panggilan_provider(kon):
    with pytest.raises(pesanan.PesananTidakDitemukan):
        pesanan.catat_refund(kon, ord_id(9), operasi(1), "admin_a", "kebijakan", SEKARANG)
    order = buat(kon, 1)
    terapkan(kon, order, 1)
    for argumen in [(operasi(2), "admin a", "kebijakan"), (operasi(2), "admin_a", "bebas"),
                    ("pendek", "admin_a", "kebijakan"), (operasi(2), "", "kebijakan")]:
        with pytest.raises(pesanan.PesananDataTidakSah):
            pesanan.catat_refund(kon, order["order_id"], *argumen, SEKARANG)
    assert hitung(kon, "pesanan_refund") == 0


def test_refund_tidak_mengubah_receipt_yang_ada(kon):
    order = buat(kon, 1)
    terapkan(kon, order, 1)
    sebelum = tuple(kon.execute("SELECT * FROM pesanan_receipt").fetchone())
    pesanan.catat_refund(kon, order["order_id"], operasi(2), "admin_a", "kebijakan", SEKARANG)
    assert tuple(kon.execute("SELECT * FROM pesanan_receipt").fetchone()) == sebelum


def test_daftar_admin_terbaru_dulu_berhalaman_dan_status_turunan(kon):
    ordo = [buat(kon, n, sekarang="2026-11-18T10:0%d:00" % n) for n in range(1, 6)]
    terapkan(kon, ordo[0], 1)
    terapkan(kon, ordo[1], 2, transaction_id="trx-2", gross_amount="48000")
    terapkan(kon, ordo[2], 3, transaction_id="trx-3")
    pesanan.catat_refund(kon, ordo[2]["order_id"], operasi(9), "admin_a", "kebijakan", SEKARANG)
    halaman = pesanan.daftar_admin(kon, halaman=1, per_halaman=3, sekarang=SEKARANG)
    assert halaman["total"] == 5 and halaman["halaman"] == 1 and halaman["per_halaman"] == 3
    assert [i["order_id"] for i in halaman["items"]] == [ordo[4]["order_id"], ordo[3]["order_id"],
                                                          ordo[2]["order_id"]]
    assert [i["status"] for i in halaman["items"]] == ["belum_bayar", "belum_bayar", "direfund"]
    kedua = pesanan.daftar_admin(kon, halaman=2, per_halaman=3, sekarang=SEKARANG)
    assert [i["status"] for i in kedua["items"]] == ["perlu_diperiksa", "sudah_dibayar"]
    assert kedua["items"][0]["alasan_kode"] == "nominal"
    akhir = pesanan.daftar_admin(kon, halaman=1, per_halaman=10, sekarang="2026-11-20T00:00:00")
    assert "kedaluwarsa" in {i["status"] for i in akhir["items"]}
    assert pesanan.daftar_admin(kon, halaman=9, per_halaman=3, sekarang=SEKARANG)["items"] == ()


def test_daftar_admin_data_minimal_tanpa_kontak_anak_atau_payload(kon):
    order = buat(kon, 1, cek_id=77)
    terapkan(kon, order, 1)
    item = pesanan.daftar_admin(kon, halaman=1, per_halaman=5, sekarang=SEKARANG)["items"][0]
    assert set(item) == {"order_id", "akun", "dibuat", "kedaluwarsa", "alasan_kode", "status"}
    assert item["akun"] == AKUN_A[:13] and AKUN_A not in item.values()
    teks = " ".join(str(v) for v in item.values())
    assert MERCHANT not in teks and "trx-" not in teks


def test_daftar_admin_hanya_membaca(db):
    with pesanan.buka(db, tulis_data=True) as k:
        buat(k, 1)
    with pesanan.buka(db) as baca:
        assert pesanan.daftar_admin(baca, halaman=1, per_halaman=5, sekarang=SEKARANG)["total"] == 1
        with pytest.raises(sqlite3.OperationalError):
            baca.execute("DELETE FROM pesanan_order")


@pytest.mark.parametrize("argumen", [dict(halaman=0, per_halaman=5), dict(halaman=1, per_halaman=0),
                                     dict(halaman=1, per_halaman=101), dict(halaman="1", per_halaman=5),
                                     dict(halaman=1, per_halaman=True)])
def test_daftar_admin_menolak_paginasi_tak_sah(kon, argumen):
    with pytest.raises(pesanan.PesananDataTidakSah):
        pesanan.daftar_admin(kon, sekarang=SEKARANG, **argumen)
