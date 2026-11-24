"""Whitelist `purna` pada detail order admin (`pesanan_admin_order.purna_ringkas` dan `detail_order`): daftar kunci persis,
tanpa PII, netral bila skema purna belum dipasang. Data sintetis di tmp_path (tanpa HTTP)."""
import json

import pesanan_admin_order as po
import purna
from purna_kit import (PELAKU, QRIS_BATAS, QRIS_HINGGA, QRIS_JANJI, SEKARANG, db, kon, kon_pesanan_saja,  # noqa: F401
                       kon_tanpa_purna, operasi, order_belum_lunas, order_qris_lunas)

KUNCI_PURNA = {"terpasang", "lunas", "voucher", "kode", "berlaku_hingga", "janji_terbit", "batas_pilihan", "terbit",
               "terlambat", "pilihan", "dipakai", "direfund", "ditahan"}
NETRAL = {"terpasang": False, "lunas": False, "voucher": None, "kode": None, "berlaku_hingga": None,
          "janji_terbit": None, "batas_pilihan": None, "terbit": None, "terlambat": False, "pilihan": None,
          "dipakai": False, "direfund": False, "ditahan": False}
SESUDAH_BATAS = "2026-11-24T00:00:00"


def test_whitelist_purna_daftar_kunci_persis_pada_detail_order(kon):
    oid = order_qris_lunas(kon)
    detail = po.detail_order(kon, oid, SEKARANG)
    assert set(detail["purna"]) == KUNCI_PURNA and len(KUNCI_PURNA) == 13
    assert detail["purna"] == po.purna_ringkas(kon, oid, SEKARANG)


def test_nilai_purna_order_lunas_baru(kon):
    oid = order_qris_lunas(kon)
    assert po.detail_order(kon, oid, SEKARANG)["purna"] == {
        "terpasang": True, "lunas": True, "voucher": "aktif", "kode": purna.kode_voucher(oid),
        "berlaku_hingga": QRIS_HINGGA, "janji_terbit": QRIS_JANJI, "batas_pilihan": QRIS_BATAS, "terbit": None,
        "terlambat": False, "pilihan": None, "dipakai": False, "direfund": False, "ditahan": False}


def test_nilai_purna_belum_lunas(kon):
    ringkas = po.purna_ringkas(kon, order_belum_lunas(kon), SEKARANG)
    assert ringkas["terpasang"] is True and ringkas["lunas"] is False and ringkas["voucher"] == "belum_lunas"
    assert ringkas["janji_terbit"] is None and ringkas["berlaku_hingga"] is None


def test_purna_mengikuti_pemakaian_terbit_dan_keterlambatan(kon):
    oid = order_qris_lunas(kon)
    assert po.purna_ringkas(kon, oid, SESUDAH_BATAS)["terlambat"] is True
    purna.catat_pakai(kon, oid, operasi(1), PELAKU, "kelas", SEKARANG)
    purna.catat_terbit(kon, oid, PELAKU, SEKARANG)
    ringkas = po.purna_ringkas(kon, oid, SESUDAH_BATAS)
    assert (ringkas["dipakai"], ringkas["voucher"], ringkas["terbit"], ringkas["terlambat"]) == (
        True, "dipakai", SEKARANG, False)


def test_purna_netral_tanpa_ledger_purna_walau_order_lunas(kon_tanpa_purna):
    from pesanan_kit import buat, terapkan
    order = buat(kon_tanpa_purna, 1)
    terapkan(kon_tanpa_purna, order, 1, transaction_id="trx-sintetis-0001")
    detail = po.detail_order(kon_tanpa_purna, order["order_id"], SEKARANG)
    assert detail["purna"] == NETRAL


def test_purna_netral_pada_db_pesanan_saja_tanpa_transfer(kon_pesanan_saja):
    from pesanan_kit import buat
    order = buat(kon_pesanan_saja, 1)
    assert po.detail_order(kon_pesanan_saja, order["order_id"], SEKARANG)["purna"] == NETRAL


def test_purna_tidak_memuat_pii_pelaku_operasi_atau_akun_penuh(kon):
    oid = order_qris_lunas(kon)
    purna.catat_pakai(kon, oid, operasi(7), PELAKU, "lainnya", SEKARANG)
    akun_penuh = kon.execute("SELECT akun_id FROM pesanan_order WHERE order_id=?", (oid,)).fetchone()[0]
    teks = json.dumps(po.detail_order(kon, oid, SEKARANG)["purna"])
    for terlarang in (PELAKU, operasi(7), akun_penuh, "lainnya"):
        assert terlarang not in teks


def test_detail_order_tetap_none_untuk_order_tak_dikenal(kon):
    assert po.detail_order(kon, "ord_" + "0" * 32, SEKARANG) is None


def test_ditahan_true_pada_order_lunas_dua_jalur_dan_false_pada_order_normal(kon):
    from pesanan_kit import terapkan
    from purna_kit import order_transfer_lunas
    normal = order_qris_lunas(kon, 1)
    dua_jalur = order_transfer_lunas(kon, 2)
    terapkan(kon, {"order_id": dua_jalur}, 9, sekarang="2026-11-18T13:00:00", transaction_id="trx-sintetis-0009")
    assert po.purna_ringkas(kon, normal, SEKARANG)["ditahan"] is False
    ringkas = po.purna_ringkas(kon, dua_jalur, SEKARANG)
    assert (ringkas["ditahan"], ringkas["voucher"], ringkas["lunas"]) == (True, "ditahan", True)
    assert po.detail_order(kon, dua_jalur, SEKARANG)["status"] == "perlu_diperiksa"


def test_ditahan_netral_false_pada_order_belum_lunas(kon):
    assert po.purna_ringkas(kon, order_belum_lunas(kon), SEKARANG)["ditahan"] is False
