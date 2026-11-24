"""Domain purna (baca): konstanta, SLA beku, kode voucher, waktu lunas, dan keadaan turunan.

Semua fixture sintetis. Order QRIS lunas pada SEKARANG (18 Nov 10:00); order transfer lunas 18 Nov 12:00.
"""
import dataclasses
import re
from datetime import datetime, timedelta

import pytest

import pesanan_dasar as d
import purna
from purna_kit import (PELAKU, QRIS_BATAS, QRIS_HINGGA, QRIS_JANJI, SEKARANG, TRANSFER_BATAS,  # noqa: F401
                       TRANSFER_HINGGA, TRANSFER_JANJI, WAKTU_SETUJU, db, kon, kon_pesanan_saja,
                       kon_tanpa_purna, operasi, order_belum_lunas, order_qris_lunas,
                       order_transfer_lunas, refund_mentah)

POLA_WAKTU = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
SESUDAH_JANJI = "2026-11-21T00:00:00"          # lewat janji (20 Nov 10:00), belum lewat batas
SESUDAH_BATAS = "2026-11-23T10:00:01"          # satu detik lewat batas pilihan QRIS


def _geser(waktu, detik):
    awal = datetime.strptime(waktu, "%Y-%m-%dT%H:%M:%S")
    return (awal + timedelta(seconds=detik)).strftime("%Y-%m-%dT%H:%M:%S")


def detik_sebelum(waktu):
    return _geser(waktu, -1)


# --- konstanta dan SLA beku ----------------------------------------------------------------

def test_konstanta_dan_entri_sla_awal():
    assert purna.SLA_TERBIT[0] == ("2000-01-01T00:00:00", 48)
    assert purna.JAM_TOLERANSI_TERLAMBAT == 72
    assert purna.HARI_VOUCHER == 90


def test_sla_terbit_berurutan_menaik_dan_berformat_kanonis():
    waktu = [w for w, _ in purna.SLA_TERBIT]
    assert waktu == sorted(waktu) and len(set(waktu)) == len(waktu)
    assert all(POLA_WAKTU.fullmatch(w) for w in waktu)
    assert all(type(jam) is int and jam > 0 for _, jam in purna.SLA_TERBIT)


def test_sla_jam_memakai_entri_awal_untuk_waktu_lunas_sekarang():
    assert purna.sla_jam("2026-11-18T10:00:00") == 48


def test_sla_jam_memilih_entri_terakhir_yang_berlaku_dari_lebih_awal_atau_sama(monkeypatch):
    monkeypatch.setattr(purna, "SLA_TERBIT", (("2000-01-01T00:00:00", 48), ("2026-12-01T00:00:00", 24),
                                              ("2027-03-01T00:00:00", 12)))
    assert purna.sla_jam("2026-11-30T23:59:59") == 48
    assert purna.sla_jam("2026-12-01T00:00:00") == 24      # tepat di batas berlaku
    assert purna.sla_jam("2027-02-28T23:59:59") == 24
    assert purna.sla_jam("2027-03-01T00:00:00") == 12


def test_sla_jam_waktu_lunas_sebelum_entri_pertama_ditolak(monkeypatch):
    monkeypatch.setattr(purna, "SLA_TERBIT", (("2026-12-01T00:00:00", 24),))
    with pytest.raises(d.PesananDataTidakSah):
        purna.sla_jam("2026-11-30T23:59:59")


def test_entri_sla_baru_tidak_menggeser_janji_order_lama(kon, monkeypatch):
    lama = order_qris_lunas(kon, 1)                      # lunas 18 Nov
    sebelum = purna.keadaan(kon, lama, SEKARANG)
    monkeypatch.setattr(purna, "SLA_TERBIT", purna.SLA_TERBIT + (("2026-11-19T00:00:00", 24),))
    sesudah = purna.keadaan(kon, lama, SEKARANG)
    assert sesudah.janji_terbit == sebelum.janji_terbit == QRIS_JANJI
    assert sesudah.batas_pilihan == sebelum.batas_pilihan == QRIS_BATAS


def test_entri_sla_baru_berlaku_untuk_order_yang_lunas_sesudahnya(kon, monkeypatch):
    # order transfer lunas 18 Nov 12:00; entri baru berlaku dari 18 Nov 11:00 (24 jam)
    baru = order_transfer_lunas(kon, 1)
    monkeypatch.setattr(purna, "SLA_TERBIT", purna.SLA_TERBIT + (("2026-11-18T11:00:00", 24),))
    k = purna.keadaan(kon, baru, SEKARANG)
    assert k.janji_terbit == "2026-11-19T12:00:00"
    assert k.batas_pilihan == "2026-11-22T12:00:00"


# --- kode voucher --------------------------------------------------------------------------

def test_kode_voucher_turunan_tetap_dua_belas_hex_besar_pertama():
    oid = "ord_ab12cd34ef56" + "0" * 20
    assert purna.kode_voucher(oid) == "JGV-AB12CD34EF56"
    assert purna.kode_voucher(oid) == purna.kode_voucher(oid)


def test_kode_voucher_berbeda_untuk_order_berbeda():
    a = purna.kode_voucher("ord_" + "a" * 12 + "0" * 20)
    b = purna.kode_voucher("ord_" + "b" * 12 + "0" * 20)
    assert a != b and a == "JGV-" + "A" * 12


@pytest.mark.parametrize("salah", ["", "ord_123", "akun_" + "a" * 32, "ORD_" + "a" * 32,
                                   "ord_" + "A" * 32, None, 5])
def test_kode_voucher_menolak_order_id_tidak_sah(salah):
    with pytest.raises(d.PesananDataTidakSah):
        purna.kode_voucher(salah)


# --- waktu lunas ---------------------------------------------------------------------------

def test_waktu_lunas_qris_dari_receipt_lunas(kon):
    assert purna.waktu_lunas(kon, order_qris_lunas(kon, 1)) == SEKARANG


def test_waktu_lunas_transfer_dari_transfer_lunas(kon):
    assert purna.waktu_lunas(kon, order_transfer_lunas(kon, 1)) == WAKTU_SETUJU


def test_waktu_lunas_none_bila_belum_lunas_atau_order_tidak_ada(kon):
    assert purna.waktu_lunas(kon, order_belum_lunas(kon, 1)) is None
    assert purna.waktu_lunas(kon, "ord_" + "f" * 32) is None


def test_waktu_lunas_none_untuk_receipt_perlu_diperiksa(kon):
    from pesanan_kit import buat, terapkan
    order = buat(kon, 3)
    terapkan(kon, order, 3, transaction_id="trx-sintetis-0003", gross_amount="1000.00")
    assert purna.waktu_lunas(kon, order["order_id"]) is None


def test_waktu_lunas_aman_tanpa_namespace_transfer(kon_pesanan_saja):
    oid = order_qris_lunas(kon_pesanan_saja, 1)
    assert purna.waktu_lunas(kon_pesanan_saja, oid) == SEKARANG
    assert purna.waktu_lunas(kon_pesanan_saja, order_belum_lunas(kon_pesanan_saja, 2)) is None


def test_waktu_lunas_receipt_didahulukan_bila_dua_jalur_lunas(kon):
    oid = order_transfer_lunas(kon, 1)
    from pesanan_kit import terapkan
    terapkan(kon, {"order_id": oid}, 9, transaction_id="trx-sintetis-0009", sekarang="2026-11-18T13:00:00")
    assert purna.waktu_lunas(kon, oid) == "2026-11-18T13:00:00"      # urutan sama dengan trigger (COALESCE)


@pytest.mark.parametrize("salah", ["x", "", None])
def test_waktu_lunas_menolak_order_id_tidak_sah(kon, salah):
    with pytest.raises(d.PesananDataTidakSah):
        purna.waktu_lunas(kon, salah)


# --- keadaan -------------------------------------------------------------------------------

def test_keadaan_belum_lunas(kon):
    k = purna.keadaan(kon, order_belum_lunas(kon, 1), SEKARANG)
    assert (k.lunas, k.direfund, k.voucher) == (False, False, "belum_lunas")
    assert (k.waktu_lunas, k.berlaku_hingga, k.janji_terbit, k.batas_pilihan) == (None,) * 4
    assert (k.terbit, k.pilihan, k.terlambat, k.bisa_pilih) == (None, None, False, False)


def test_keadaan_qris_aktif_memuat_semua_turunan(kon):
    oid = order_qris_lunas(kon, 1)
    k = purna.keadaan(kon, oid, SEKARANG)
    assert (k.lunas, k.direfund, k.voucher) == (True, False, "aktif")
    assert k.kode == purna.kode_voucher(oid)
    assert (k.waktu_lunas, k.janji_terbit, k.batas_pilihan, k.berlaku_hingga) == (
        SEKARANG, QRIS_JANJI, QRIS_BATAS, QRIS_HINGGA)
    assert (k.terbit, k.pilihan, k.terlambat, k.bisa_pilih, k.dipakai) == (None, None, False, False, False)


def test_keadaan_transfer_aktif(kon):
    oid = order_transfer_lunas(kon, 1)
    k = purna.keadaan(kon, oid, WAKTU_SETUJU)
    assert (k.lunas, k.direfund, k.voucher) == (True, False, "aktif")
    assert (k.waktu_lunas, k.janji_terbit, k.batas_pilihan, k.berlaku_hingga) == (
        WAKTU_SETUJU, TRANSFER_JANJI, TRANSFER_BATAS, TRANSFER_HINGGA)


def test_keadaan_beku_tidak_bisa_diubah(kon):
    k = purna.keadaan(kon, order_qris_lunas(kon, 1), SEKARANG)
    assert dataclasses.is_dataclass(k)
    with pytest.raises(dataclasses.FrozenInstanceError):
        k.voucher = "dipakai"


def test_keadaan_order_tidak_ada_atau_id_salah(kon):
    with pytest.raises(d.PesananTidakDitemukan):
        purna.keadaan(kon, "ord_" + "f" * 32, SEKARANG)
    with pytest.raises(d.PesananDataTidakSah):
        purna.keadaan(kon, "bukan-order", SEKARANG)
    with pytest.raises(d.PesananDataTidakSah):
        purna.keadaan(kon, order_qris_lunas(kon, 1), "kemarin")


def test_keadaan_menormalkan_waktu_berzona(kon):
    oid = order_qris_lunas(kon, 1)
    k = purna.keadaan(kon, oid, "2026-11-23T17:00:01+07:00")          # = SESUDAH_BATAS UTC
    assert k.terlambat is True


@pytest.mark.parametrize("buat_order", [order_qris_lunas, order_transfer_lunas])
def test_keadaan_direfund_voucher_batal_di_kedua_ledger(kon, buat_order):
    import pesanan
    from transfer_kit import ADMIN
    oid = buat_order(kon, 1)
    pesanan.catat_refund(kon, oid, operasi(1), ADMIN, "kebijakan", SEKARANG)
    k = purna.keadaan(kon, oid, SEKARANG)
    assert (k.lunas, k.direfund, k.voucher) == (True, True, "batal")


def test_kedaluwarsa_tepat_di_batas_hari_voucher(kon):
    oid = order_qris_lunas(kon, 1)
    assert purna.keadaan(kon, oid, detik_sebelum(QRIS_HINGGA)).voucher == "aktif"
    assert purna.keadaan(kon, oid, QRIS_HINGGA).voucher == "kedaluwarsa"
    assert purna.keadaan(kon, oid, _geser(QRIS_HINGGA, 1)).voucher == "kedaluwarsa"


def test_berlaku_hingga_tepat_hari_voucher_kali_dua_puluh_empat_jam_dari_waktu_lunas(kon):
    k = purna.keadaan(kon, order_qris_lunas(kon, 1), SEKARANG)
    assert k.berlaku_hingga == d.tambah_jam(SEKARANG, purna.HARI_VOUCHER * 24)


def test_terlambat_tepat_di_batas_pilihan_bukan_terlambat_plus_satu_detik_terlambat(kon):
    oid = order_qris_lunas(kon, 1)
    assert purna.keadaan(kon, oid, SESUDAH_JANJI).terlambat is False
    assert purna.keadaan(kon, oid, QRIS_BATAS).terlambat is False
    sesudah = purna.keadaan(kon, oid, SESUDAH_BATAS)
    assert (sesudah.terlambat, sesudah.bisa_pilih, sesudah.voucher) == (True, True, "aktif")


def test_batas_pilihan_tepat_janji_ditambah_toleransi(kon):
    k = purna.keadaan(kon, order_qris_lunas(kon, 1), SEKARANG)
    assert k.batas_pilihan == d.tambah_jam(k.janji_terbit, purna.JAM_TOLERANSI_TERLAMBAT)


def test_terbit_membuat_tidak_terlambat_dan_tidak_bisa_pilih(kon):
    oid = order_qris_lunas(kon, 1)
    kon.execute("INSERT INTO purna_laporan_terbit VALUES(?,?,?,?)", (oid, QRIS_JANJI, PELAKU, QRIS_JANJI))
    kon.commit()
    k = purna.keadaan(kon, oid, SESUDAH_BATAS)
    assert (k.terbit, k.terlambat, k.bisa_pilih) == (QRIS_JANJI, False, False)


def test_pilihan_efektif_dan_voucher_batal_bila_uang_kembali(kon):
    oid = order_qris_lunas(kon, 1)
    assert purna.keadaan(kon, oid, SESUDAH_BATAS).pilihan is None
    kon.execute("INSERT INTO purna_pilihan_terlambat VALUES(?,?,?)", (oid, "menunggu", SESUDAH_BATAS))
    kon.commit()
    menunggu = purna.keadaan(kon, oid, SESUDAH_BATAS)
    assert (menunggu.pilihan, menunggu.voucher) == ("menunggu", "aktif")
    kon.execute("INSERT INTO purna_pilihan_terlambat VALUES(?,?,?)", (oid, "uang_kembali", SESUDAH_BATAS))
    kon.commit()
    final = purna.keadaan(kon, oid, SESUDAH_BATAS)
    assert (final.pilihan, final.voucher) == ("uang_kembali", "batal")


def _pakai_mentah(kon, oid, n=1):
    kon.execute("INSERT INTO purna_voucher_pakai VALUES(?,?,?,?,?)", (operasi(n), oid, PELAKU, "kelas", SEKARANG))
    kon.commit()


def test_dipakai_didahulukan_dari_kedaluwarsa(kon):
    oid = order_qris_lunas(kon, 1)
    _pakai_mentah(kon, oid)
    k = purna.keadaan(kon, oid, _geser(QRIS_HINGGA, 1))
    assert (k.voucher, k.dipakai) == ("dipakai", True)


def test_batal_didahulukan_dari_dipakai_dan_kedaluwarsa(kon):
    oid = order_qris_lunas(kon, 1)
    _pakai_mentah(kon, oid)
    refund_mentah(kon, oid)                      # keadaan langka: refund tercatat sesudah pemakaian
    k = purna.keadaan(kon, oid, _geser(QRIS_HINGGA, 1))
    assert (k.voucher, k.direfund, k.dipakai) == ("batal", True, True)


def test_dipakai_menutup_pilihan_meski_voucher_batal_menutupi_status(kon):
    oid = order_qris_lunas(kon, 1)
    _pakai_mentah(kon, oid)
    refund_mentah(kon, oid)
    assert purna.keadaan(kon, oid, SESUDAH_BATAS).bisa_pilih is False


@pytest.mark.parametrize("kasus", ["direfund", "dipakai", "terbit", "belum_terlambat"])
def test_bisa_pilih_mati_bila_salah_satu_syarat_gagal(kon, kasus):
    oid = order_qris_lunas(kon, 1)
    sekarang = SESUDAH_BATAS
    if kasus == "direfund":
        refund_mentah(kon, oid)
    elif kasus == "dipakai":
        _pakai_mentah(kon, oid)
    elif kasus == "terbit":
        kon.execute("INSERT INTO purna_laporan_terbit VALUES(?,?,?,?)", (oid, QRIS_JANJI, PELAKU, QRIS_JANJI))
        kon.commit()
    else:
        sekarang = QRIS_BATAS
    assert purna.keadaan(kon, oid, sekarang).bisa_pilih is False


# --- purna belum terpasang -------------------------------------------------------------------

def test_keadaan_netral_bila_purna_belum_terpasang(kon_tanpa_purna):
    oid = order_qris_lunas(kon_tanpa_purna, 1)
    k = purna.keadaan(kon_tanpa_purna, oid, SESUDAH_BATAS)
    assert (k.lunas, k.voucher, k.terbit, k.pilihan, k.dipakai) == (True, "aktif", None, None, False)
    assert k.bisa_pilih is False                  # tidak ada tabel untuk menulis pilihan


def test_keadaan_aman_di_db_pesanan_saja(kon_pesanan_saja):
    lunas = order_qris_lunas(kon_pesanan_saja, 1)
    belum = order_belum_lunas(kon_pesanan_saja, 2)
    assert purna.keadaan(kon_pesanan_saja, lunas, SEKARANG).voucher == "aktif"
    assert purna.keadaan(kon_pesanan_saja, belum, SEKARANG).voucher == "belum_lunas"
    assert purna.voucher_dipakai(kon_pesanan_saja, lunas) is False


# --- voucher_dipakai -------------------------------------------------------------------------

def test_voucher_dipakai_true_hanya_bila_ada_catatan_pemakaian(kon):
    a, b = order_qris_lunas(kon, 1), order_transfer_lunas(kon, 2)
    assert purna.voucher_dipakai(kon, a) is False
    _pakai_mentah(kon, a)
    assert purna.voucher_dipakai(kon, a) is True
    assert purna.voucher_dipakai(kon, b) is False


def test_voucher_dipakai_false_bila_purna_belum_terpasang(kon_tanpa_purna):
    assert purna.voucher_dipakai(kon_tanpa_purna, order_qris_lunas(kon_tanpa_purna, 1)) is False


@pytest.mark.parametrize("salah", ["x", None, ""])
def test_voucher_dipakai_menolak_order_id_tidak_sah(kon, salah):
    with pytest.raises(d.PesananDataTidakSah):
        purna.voucher_dipakai(kon, salah)


def test_modul_purna_tidak_mengimpor_admin_http_atau_pages():
    from pathlib import Path
    sumber = (Path(purna.__file__)).read_text(encoding="utf-8")
    impor = re.findall(r"^\s*(?:import|from)\s+(\w+)", sumber, flags=re.MULTILINE)
    assert not [m for m in impor if m.startswith(("admin", "http")) or m.endswith(("_http", "_pages"))]
