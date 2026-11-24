"""Domain purna (tulis): catat_pakai dan catat_terbit. Data sintetis QRIS dan transfer."""
import pytest

import pesanan
import pesanan_dasar as d
import purna
from purna_kit import (PELAKU, QRIS_BATAS, QRIS_HINGGA, QRIS_JANJI, SEKARANG, TRANSFER_BATAS,  # noqa: F401
                       WAKTU_SETUJU, baris, db, hitung, kon, kon_pesanan_saja, kon_tanpa_purna, operasi,
                       order_belum_lunas, order_qris_lunas, order_transfer_lunas, refund_mentah)

SESUDAH_HINGGA = "2027-02-16T10:00:00"           # QRIS: tepat batas kedaluwarsa
SEBELUM_LUNAS = "2026-11-18T09:59:59"


def pakai(kon, oid, n=1, *, pelaku=PELAKU, catatan="kelas", sekarang=SEKARANG):
    return purna.catat_pakai(kon, oid, operasi(n), pelaku, catatan, sekarang)


def tanpa_transaksi_terbuka(kon):
    assert not kon.in_transaction


# --- catat_pakai ---------------------------------------------------------------------------

@pytest.mark.parametrize("buat_order,sekarang", [(order_qris_lunas, SEKARANG),
                                                 (order_transfer_lunas, WAKTU_SETUJU)])
def test_pakai_voucher_aktif_menulis_satu_baris_untuk_qris_dan_transfer(kon, buat_order, sekarang):
    oid = buat_order(kon, 1)
    assert pakai(kon, oid, catatan="lainnya", sekarang=sekarang) == {"baru": True}
    assert baris(kon, "purna_voucher_pakai") == [(operasi(1), oid, PELAKU, "lainnya", sekarang)]
    assert purna.keadaan(kon, oid, sekarang).voucher == "dipakai"
    tanpa_transaksi_terbuka(kon)


def test_pakai_replay_identik_tidak_menulis_lagi_walau_waktu_berbeda(kon):
    oid = order_qris_lunas(kon, 1)
    pakai(kon, oid)
    assert pakai(kon, oid, sekarang="2026-11-19T10:00:00") == {"baru": False}
    assert len(baris(kon, "purna_voucher_pakai")) == 1


def test_pakai_replay_tetap_dilayani_setelah_kedaluwarsa(kon):
    oid = order_qris_lunas(kon, 1)
    pakai(kon, oid)
    assert pakai(kon, oid, sekarang=SESUDAH_HINGGA) == {"baru": False}


@pytest.mark.parametrize("ganti", [dict(catatan="lainnya"), dict(pelaku="admin_lain")])
def test_pakai_operasi_sama_isi_beda_konflik_tanpa_tulis(kon, ganti):
    oid = order_qris_lunas(kon, 1)
    pakai(kon, oid)
    sebelum = baris(kon, "purna_voucher_pakai")
    with pytest.raises(d.PesananKonflik):
        pakai(kon, oid, **ganti)
    assert baris(kon, "purna_voucher_pakai") == sebelum
    tanpa_transaksi_terbuka(kon)


def test_pakai_order_sudah_punya_pemakaian_dengan_operasi_lain_konflik(kon):
    oid = order_qris_lunas(kon, 1)
    pakai(kon, oid, 1)
    with pytest.raises(d.PesananKonflik):
        pakai(kon, oid, 2)
    assert len(baris(kon, "purna_voucher_pakai")) == 1


def test_pakai_operasi_sama_untuk_order_lain_konflik_dan_order_lain_tidak_tertulis(kon):
    a, b = order_qris_lunas(kon, 1), order_qris_lunas(kon, 2)
    pakai(kon, a, 1)
    with pytest.raises(d.PesananKonflik):
        pakai(kon, b, 1)
    assert [r[1] for r in baris(kon, "purna_voucher_pakai")] == [a]
    assert purna.keadaan(kon, b, SEKARANG).voucher == "aktif"


def test_pakai_ditolak_bila_belum_lunas(kon):
    oid = order_belum_lunas(kon, 1)
    with pytest.raises(d.PesananKonflik, match="belum lunas"):
        pakai(kon, oid)
    assert baris(kon, "purna_voucher_pakai") == []


@pytest.mark.parametrize("buat_order,tabel", [(order_qris_lunas, "pesanan_refund"),
                                              (order_transfer_lunas, "transfer_refund")])
def test_pakai_ditolak_bila_order_sudah_direfund_di_kedua_ledger(kon, buat_order, tabel):
    oid = buat_order(kon, 1)
    pesanan.catat_refund(kon, oid, operasi(7), PELAKU, "kebijakan", SEKARANG)
    assert hitung(kon, tabel) == 1
    with pytest.raises(d.PesananKonflik, match="dibatalkan"):
        pakai(kon, oid)
    assert baris(kon, "purna_voucher_pakai") == []


def test_pakai_kedaluwarsa_tepat_di_batas_ditolak_satu_detik_sebelumnya_boleh(kon):
    a, b = order_qris_lunas(kon, 1), order_qris_lunas(kon, 2)
    assert pakai(kon, a, 1, sekarang="2027-02-16T09:59:59") == {"baru": True}
    with pytest.raises(d.PesananKonflik, match="kedaluwarsa"):
        pakai(kon, b, 2, sekarang=SESUDAH_HINGGA)
    assert [r[1] for r in baris(kon, "purna_voucher_pakai")] == [a]


def test_pakai_order_tidak_ada_not_found_tanpa_tulis(kon):
    with pytest.raises(d.PesananTidakDitemukan):
        pakai(kon, "ord_" + "f" * 32)
    tanpa_transaksi_terbuka(kon)


@pytest.mark.parametrize("ganti", [
    dict(catatan="refund"), dict(catatan=""), dict(pelaku=""), dict(pelaku="admin sintetis"),
])
def test_pakai_validasi_masukan(kon, ganti):
    oid = order_qris_lunas(kon, 1)
    with pytest.raises(d.PesananDataTidakSah):
        pakai(kon, oid, **ganti)
    assert baris(kon, "purna_voucher_pakai") == []


def test_pakai_validasi_id_waktu_dan_koneksi(kon, db):
    oid = order_qris_lunas(kon, 1)
    for argumen in (("bukan-order", operasi(1), PELAKU, "kelas", SEKARANG),
                    (oid, "pendek", PELAKU, "kelas", SEKARANG),
                    (oid, operasi(1), PELAKU, "kelas", "kemarin")):
        with pytest.raises(d.PesananDataTidakSah):
            purna.catat_pakai(kon, *argumen)
    import sqlite3
    with sqlite3.connect(db) as mentah:
        with pytest.raises(d.PesananDataTidakSah):
            purna.catat_pakai(mentah, oid, operasi(1), PELAKU, "kelas", SEKARANG)


def test_pakai_menolak_koneksi_yang_sudah_dalam_transaksi(kon):
    oid = order_qris_lunas(kon, 1)
    kon.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(d.PesananDataTidakSah):
            pakai(kon, oid)
    finally:
        kon.rollback()


def test_pakai_tanpa_purna_terpasang_ditolak_jelas_tanpa_tulis(kon_tanpa_purna, kon_pesanan_saja):
    for koneksi in (kon_tanpa_purna, kon_pesanan_saja):
        oid = order_qris_lunas(koneksi, 1)
        with pytest.raises(d.PesananKonflik, match="belum dipasang"):
            pakai(koneksi, oid)
        tanpa_transaksi_terbuka(koneksi)


def test_idempotensi_tidak_memakai_insert_or_ignore():
    import ast
    from pathlib import Path
    pohon = ast.parse(Path(purna.__file__).read_text(encoding="utf-8"))
    sql = [n.value.upper() for n in ast.walk(pohon)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)
           and n.value.lstrip().upper().startswith("INSERT")]
    assert sql and not [s for s in sql if "OR IGNORE" in s or "OR REPLACE" in s]


# --- catat_terbit --------------------------------------------------------------------------

@pytest.mark.parametrize("buat_order,lunas", [(order_qris_lunas, SEKARANG), (order_transfer_lunas, WAKTU_SETUJU)])
def test_terbit_menulis_waktu_sekarang_untuk_order_lunas(kon, buat_order, lunas):
    oid = buat_order(kon, 1)
    assert purna.catat_terbit(kon, oid, PELAKU, QRIS_JANJI) == {"baru": True}
    assert baris(kon, "purna_laporan_terbit") == [(oid, QRIS_JANJI, PELAKU, QRIS_JANJI)]
    assert purna.keadaan(kon, oid, QRIS_JANJI).terbit == QRIS_JANJI
    tanpa_transaksi_terbuka(kon)


def test_terbit_replay_tanpa_tulis_walau_pelaku_dan_waktu_beda(kon):
    oid = order_qris_lunas(kon, 1)
    purna.catat_terbit(kon, oid, PELAKU, QRIS_JANJI)
    assert purna.catat_terbit(kon, oid, "admin_lain", QRIS_BATAS) == {"baru": False}
    assert baris(kon, "purna_laporan_terbit") == [(oid, QRIS_JANJI, PELAKU, QRIS_JANJI)]


def test_terbit_ditolak_bila_belum_lunas(kon):
    with pytest.raises(d.PesananKonflik, match="belum lunas"):
        purna.catat_terbit(kon, order_belum_lunas(kon, 1), PELAKU, QRIS_JANJI)
    assert baris(kon, "purna_laporan_terbit") == []


@pytest.mark.parametrize("buat_order", [order_qris_lunas, order_transfer_lunas])
def test_terbit_ditolak_bila_sudah_direfund(kon, buat_order):
    oid = buat_order(kon, 1)
    pesanan.catat_refund(kon, oid, operasi(7), PELAKU, "kebijakan", SEKARANG)
    with pytest.raises(d.PesananKonflik, match="direfund"):
        purna.catat_terbit(kon, oid, PELAKU, QRIS_JANJI)
    assert baris(kon, "purna_laporan_terbit") == []


def test_terbit_lebih_awal_dari_waktu_lunas_ditolak_tepat_waktu_lunas_boleh(kon):
    a, b = order_qris_lunas(kon, 1), order_qris_lunas(kon, 2)
    with pytest.raises(d.PesananKonflik, match="lebih awal"):
        purna.catat_terbit(kon, a, PELAKU, SEBELUM_LUNAS)
    assert baris(kon, "purna_laporan_terbit") == []
    assert purna.catat_terbit(kon, b, PELAKU, SEKARANG) == {"baru": True}


def test_terbit_order_tidak_ada_dan_masukan_salah(kon):
    with pytest.raises(d.PesananTidakDitemukan):
        purna.catat_terbit(kon, "ord_" + "f" * 32, PELAKU, SEKARANG)
    oid = order_qris_lunas(kon, 1)
    for argumen in (("x", PELAKU, SEKARANG), (oid, "", SEKARANG), (oid, "a b", SEKARANG),
                    (oid, PELAKU, "kemarin")):
        with pytest.raises(d.PesananDataTidakSah):
            purna.catat_terbit(kon, *argumen)


def test_terbit_tanpa_purna_terpasang_ditolak_jelas(kon_tanpa_purna):
    oid = order_qris_lunas(kon_tanpa_purna, 1)
    with pytest.raises(d.PesananKonflik, match="belum dipasang"):
        purna.catat_terbit(kon_tanpa_purna, oid, PELAKU, QRIS_JANJI)
