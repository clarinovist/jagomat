"""Domain purna (tulis): catat_pakai, catat_terbit, catat_pilihan. Data sintetis QRIS dan transfer."""
import pytest

import pesanan
import pesanan_dasar as d
import purna
from purna_kit import (PELAKU, QRIS_BATAS, QRIS_HINGGA, QRIS_JANJI, SEKARANG, TRANSFER_BATAS,  # noqa: F401
                       WAKTU_SETUJU, baris, db, hitung, kon, kon_pesanan_saja, kon_tanpa_purna, operasi,
                       order_belum_lunas, order_qris_lunas, order_transfer_lunas, refund_mentah)

SESUDAH_BATAS = "2026-11-23T10:00:01"            # QRIS: lewat janji + toleransi
SESUDAH_BATAS_TRANSFER = "2026-11-23T12:00:01"
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


def test_pakai_ditolak_bila_sudah_memilih_uang_kembali(kon):
    oid = order_qris_lunas(kon, 1)
    purna.catat_pilihan(kon, oid, "uang_kembali", SESUDAH_BATAS)
    with pytest.raises(d.PesananKonflik, match="dibatalkan"):
        pakai(kon, oid, sekarang=SESUDAH_BATAS)
    assert baris(kon, "purna_voucher_pakai") == []


def test_pakai_menunggu_belum_membatalkan_voucher(kon):
    oid = order_qris_lunas(kon, 1)
    purna.catat_pilihan(kon, oid, "menunggu", SESUDAH_BATAS)
    assert pakai(kon, oid, sekarang=SESUDAH_BATAS) == {"baru": True}


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


# --- catat_pilihan -------------------------------------------------------------------------

def test_pilihan_menunggu_lalu_uang_kembali_final_untuk_qris(kon):
    oid = order_qris_lunas(kon, 1)
    assert purna.catat_pilihan(kon, oid, "menunggu", SESUDAH_BATAS) == {"baru": True}
    assert purna.catat_pilihan(kon, oid, "uang_kembali", "2026-11-24T10:00:00") == {"baru": True}
    assert baris(kon, "purna_pilihan_terlambat") == [(oid, "menunggu", SESUDAH_BATAS),
                                                    (oid, "uang_kembali", "2026-11-24T10:00:00")]
    k = purna.keadaan(kon, oid, "2026-11-24T10:00:00")
    assert (k.pilihan, k.voucher) == ("uang_kembali", "batal")
    tanpa_transaksi_terbuka(kon)


def test_pilihan_transfer_uang_kembali_langsung_tanpa_menunggu(kon):
    oid = order_transfer_lunas(kon, 1)
    assert purna.catat_pilihan(kon, oid, "uang_kembali", SESUDAH_BATAS_TRANSFER) == {"baru": True}
    assert purna.keadaan(kon, oid, SESUDAH_BATAS_TRANSFER).pilihan == "uang_kembali"


@pytest.mark.parametrize("pilihan", ["menunggu", "uang_kembali"])
def test_pilihan_replay_identik_tanpa_tulis(kon, pilihan):
    oid = order_qris_lunas(kon, 1)
    purna.catat_pilihan(kon, oid, pilihan, SESUDAH_BATAS)
    assert purna.catat_pilihan(kon, oid, pilihan, "2026-11-25T10:00:00") == {"baru": False}
    assert baris(kon, "purna_pilihan_terlambat") == [(oid, pilihan, SESUDAH_BATAS)]


def test_pilihan_menunggu_setelah_uang_kembali_konflik_walau_baris_menunggu_ada(kon):
    oid = order_qris_lunas(kon, 1)
    purna.catat_pilihan(kon, oid, "menunggu", SESUDAH_BATAS)
    purna.catat_pilihan(kon, oid, "uang_kembali", SESUDAH_BATAS)
    sebelum = baris(kon, "purna_pilihan_terlambat")
    with pytest.raises(d.PesananKonflik, match="final"):
        purna.catat_pilihan(kon, oid, "menunggu", "2026-11-25T10:00:00")
    assert baris(kon, "purna_pilihan_terlambat") == sebelum


def test_pilihan_uang_kembali_replay_tetap_dilayani_setelah_refund_dan_terbit(kon):
    oid = order_qris_lunas(kon, 1)
    purna.catat_pilihan(kon, oid, "uang_kembali", SESUDAH_BATAS)
    pesanan.catat_refund(kon, oid, operasi(7), PELAKU, "kebijakan", "2026-11-24T10:00:00")
    assert purna.catat_pilihan(kon, oid, "uang_kembali", "2026-11-25T10:00:00") == {"baru": False}


def test_pilihan_ditolak_bila_belum_terlambat_tepat_di_batas_boleh_satu_detik_sesudahnya(kon):
    a, b = order_qris_lunas(kon, 1), order_qris_lunas(kon, 2)
    with pytest.raises(d.PesananKonflik, match="belum terlambat"):
        purna.catat_pilihan(kon, a, "menunggu", QRIS_BATAS)
    with pytest.raises(d.PesananKonflik, match="belum terlambat"):
        purna.catat_pilihan(kon, a, "uang_kembali", QRIS_JANJI)
    assert baris(kon, "purna_pilihan_terlambat") == []
    assert purna.catat_pilihan(kon, b, "menunggu", SESUDAH_BATAS) == {"baru": True}


def test_pilihan_ditolak_bila_belum_lunas(kon):
    with pytest.raises(d.PesananKonflik, match="belum lunas"):
        purna.catat_pilihan(kon, order_belum_lunas(kon, 1), "menunggu", SESUDAH_BATAS)
    assert baris(kon, "purna_pilihan_terlambat") == []


@pytest.mark.parametrize("pilihan", ["menunggu", "uang_kembali"])
def test_pilihan_ditolak_bila_laporan_sudah_terbit(kon, pilihan):
    oid = order_qris_lunas(kon, 1)
    purna.catat_terbit(kon, oid, PELAKU, QRIS_JANJI)
    with pytest.raises(d.PesananKonflik, match="terbit"):
        purna.catat_pilihan(kon, oid, pilihan, SESUDAH_BATAS)
    assert baris(kon, "purna_pilihan_terlambat") == []


@pytest.mark.parametrize("pilihan", ["menunggu", "uang_kembali"])
def test_pilihan_ditolak_bila_voucher_sudah_dipakai(kon, pilihan):
    oid = order_qris_lunas(kon, 1)
    pakai(kon, oid)
    with pytest.raises(d.PesananKonflik, match="dipakai"):
        purna.catat_pilihan(kon, oid, pilihan, SESUDAH_BATAS)
    assert baris(kon, "purna_pilihan_terlambat") == []


@pytest.mark.parametrize("pilihan", ["menunggu", "uang_kembali"])
def test_pilihan_ditolak_bila_order_sudah_direfund(kon, pilihan):
    oid = order_qris_lunas(kon, 1)
    pesanan.catat_refund(kon, oid, operasi(7), PELAKU, "kebijakan", SEKARANG)
    with pytest.raises(d.PesananKonflik, match="direfund"):
        purna.catat_pilihan(kon, oid, pilihan, SESUDAH_BATAS)
    assert baris(kon, "purna_pilihan_terlambat") == []


def test_pilihan_ditolak_bila_dipakai_walau_voucher_batal_menutupi_status(kon):
    oid = order_qris_lunas(kon, 1)
    pakai(kon, oid)
    refund_mentah(kon, oid)
    with pytest.raises(d.PesananKonflik):
        purna.catat_pilihan(kon, oid, "uang_kembali", SESUDAH_BATAS)
    assert baris(kon, "purna_pilihan_terlambat") == []


def test_pilihan_validasi_dan_order_tidak_ada(kon):
    oid = order_qris_lunas(kon, 1)
    for argumen in ((oid, "batal", SESUDAH_BATAS), (oid, "", SESUDAH_BATAS), (oid, None, SESUDAH_BATAS),
                    ("x", "menunggu", SESUDAH_BATAS), (oid, "menunggu", "kemarin")):
        with pytest.raises(d.PesananDataTidakSah):
            purna.catat_pilihan(kon, *argumen)
    with pytest.raises(d.PesananTidakDitemukan):
        purna.catat_pilihan(kon, "ord_" + "f" * 32, "menunggu", SESUDAH_BATAS)


def test_pilihan_tanpa_purna_terpasang_ditolak_jelas(kon_tanpa_purna):
    oid = order_qris_lunas(kon_tanpa_purna, 1)
    with pytest.raises(d.PesananKonflik, match="belum dipasang"):
        purna.catat_pilihan(kon_tanpa_purna, oid, "menunggu", SESUDAH_BATAS)
