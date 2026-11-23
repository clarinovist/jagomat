"""Pembaca detail order admin (`pesanan_admin_order`) dan daftar tersaring (`pesanan_admin.daftar_tersaring`).

Data sintetis; ledger sementara di tmp_path (tanpa HTTP).
"""
import pytest

import pesanan
import pesanan_admin
import pesanan_admin_order as po
import pesanan_transfer as tf
from pesanan_kit import (AKUN_A, MERCHANT, SEKARANG, SESUDAH_KEDALUWARSA, TRANSAKSI, buat, operasi,
                         ord_id, siapkan_db, terapkan)
from transfer_kit import (ADMIN, SESUDAH_UPLOAD, akun_ke, menunggu, sha, siapkan_db_transfer, tagihan,
                          unggah)

SESUDAH = "2026-11-18T13:00:00"
KUNCI_DETAIL = {"order_id", "akun", "status", "dibuat", "kedaluwarsa", "cara", "nominal", "jumlah_bukti", "langkah",
                "dua_jalur", "bukti_dipakai_ulang"}


@pytest.fixture
def kon(tmp_path):
    with tf.buka(siapkan_db_transfer(tmp_path), tulis_data=True) as sambungan:
        yield sambungan


@pytest.fixture
def kon_qris(tmp_path):
    """DB hanya dengan skema pesanan v1 (tanpa namespace transfer_*)."""
    with pesanan.buka(siapkan_db(tmp_path), tulis_data=True) as sambungan:
        yield sambungan


def _kode(detail):
    return [x["kode"] for x in detail["langkah"]]


# --- detail_order -----------------------------------------------------------------

def test_order_tak_dikenal_none_dan_id_tak_sah_ditolak(kon):
    assert po.detail_order(kon, ord_id(404), SEKARANG) is None
    with pytest.raises(pesanan.PesananDataTidakSah):
        po.detail_order(kon, "bukan-order", SEKARANG)


def test_order_qris_belum_bayar_hanya_langkah_dibuat_dan_kunci_minimal(kon_qris):
    order = buat(kon_qris, 1)
    detail = po.detail_order(kon_qris, order["order_id"], SEKARANG)
    assert set(detail) == KUNCI_DETAIL
    assert (detail["status"], detail["cara"], detail["nominal"], detail["jumlah_bukti"]) == (
        "belum_bayar", "qris", None, 0)
    assert detail["akun"] == AKUN_A[:13] and detail["dibuat"] == SEKARANG
    assert _kode(detail) == ["dibuat"]


def test_detail_tidak_memuat_transaksi_merchant_atau_akun_penuh(kon_qris):
    order = buat(kon_qris, 1)
    terapkan(kon_qris, order, 1)
    teks = repr(po.detail_order(kon_qris, order["order_id"], SEKARANG))
    assert TRANSAKSI not in teks and MERCHANT not in teks and AKUN_A not in teks


def test_order_qris_lunas_lalu_refund_menambah_langkah_berurutan(kon_qris):
    order = buat(kon_qris, 1)
    terapkan(kon_qris, order, 1, sekarang="2026-11-18T10:05:00")
    assert _kode(po.detail_order(kon_qris, order["order_id"], SEKARANG)) == ["dibuat", "lunas"]
    pesanan.catat_refund(kon_qris, order["order_id"], operasi(2), "admin_a", "kebijakan", "2026-11-18T11:00:00")
    detail = po.detail_order(kon_qris, order["order_id"], SEKARANG)
    assert detail["status"] == "direfund" and _kode(detail) == ["dibuat", "lunas", "refund"]


def test_order_kedaluwarsa_menambah_langkah_waktu_bayar_habis(kon_qris):
    order = buat(kon_qris, 1)
    detail = po.detail_order(kon_qris, order["order_id"], SESUDAH_KEDALUWARSA)
    assert detail["status"] == "kedaluwarsa" and _kode(detail) == ["dibuat", "kedaluwarsa"]
    assert detail["langkah"][-1]["waktu"] == detail["kedaluwarsa"]


def test_order_transfer_menunggu_nominal_cara_dan_bukti(kon):
    order, tag = menunggu(kon, 1)
    detail = po.detail_order(kon, order["order_id"], SESUDAH_UPLOAD)
    assert (detail["status"], detail["cara"], detail["jumlah_bukti"]) == ("menunggu_verifikasi", "transfer", 1)
    assert detail["nominal"] == tag["nominal_transfer"]
    assert _kode(detail) == ["dibuat", "bukti"]
    assert detail["langkah"][1]["jumlah"] == 1 and detail["langkah"][1]["waktu"] == SESUDAH_UPLOAD


def test_order_transfer_disetujui_lalu_direfund_langkah_lengkap(kon):
    order, _tag = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, "2026-11-18T12:30:00")
    assert _kode(po.detail_order(kon, order["order_id"], SESUDAH)) == ["dibuat", "bukti", "setuju"]
    pesanan.catat_refund(kon, order["order_id"], operasi(5), "admin_a", "kebijakan", "2026-11-18T12:45:00")
    detail = po.detail_order(kon, order["order_id"], SESUDAH)
    assert detail["status"] == "direfund" and _kode(detail) == ["dibuat", "bukti", "setuju", "refund"]


def test_order_transfer_ditolak_langkah_tolak_dan_bukan_data_alasan(kon):
    order, _tag = menunggu(kon, 1)
    tf.tolak(kon, order["order_id"], ADMIN, "Nominal kurang", "2026-11-18T12:30:00")
    detail = po.detail_order(kon, order["order_id"], SESUDAH)
    assert detail["status"] == "ditolak" and _kode(detail) == ["dibuat", "bukti", "tolak"]
    assert "Nominal kurang" not in repr(detail)


def test_order_qris_pada_db_dengan_transfer_tetap_qris_tanpa_nominal(kon):
    order = buat(kon, 1)
    detail = po.detail_order(kon, order["order_id"], SEKARANG)
    assert (detail["cara"], detail["nominal"], detail["jumlah_bukti"]) == ("qris", None, 0)


def test_langkah_terurut_menurut_waktu(kon):
    order, _tag = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, "2026-11-18T12:30:00")
    waktu = [x["waktu"] for x in po.detail_order(kon, order["order_id"], SESUDAH)["langkah"]]
    assert waktu == sorted(waktu)


# --- penanda dua jalur dan bukti dipakai ulang ----------------------------------------

def test_detail_dua_jalur_bila_receipt_lunas_dan_bukti_menunggu(kon):
    order, _ = menunggu(kon, 1)
    terapkan(kon, order, 1, sekarang=SESUDAH_UPLOAD)
    detail = po.detail_order(kon, order["order_id"], SESUDAH)
    assert detail["status"] == "perlu_diperiksa" and detail["dua_jalur"] is True
    item = pesanan.daftar_admin(kon, halaman=1, per_halaman=5, sekarang=SESUDAH)["items"][0]
    assert item["status"] == "perlu_diperiksa" and item["dua_jalur"] is True


def test_detail_dua_jalur_bila_receipt_lunas_dan_transfer_lunas(kon):
    order, _ = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    # trigger skema hanya menjaga satu arah (lunas transfer tanpa receipt); receipt sesudahnya tetap masuk.
    terapkan(kon, order, 1, sekarang=SESUDAH_UPLOAD)
    detail = po.detail_order(kon, order["order_id"], SESUDAH)
    assert detail["status"] == "perlu_diperiksa" and detail["dua_jalur"] is True


def test_detail_bukan_dua_jalur_untuk_satu_jalur_saja(kon):
    transfer, _ = menunggu(kon, 1)
    qris = buat(kon, 2, akun=akun_ke(2))
    terapkan(kon, qris, 2, transaction_id="trx-qris-2")
    ditolak, _ = menunggu(kon, 3, akun=akun_ke(3))
    tf.tolak(kon, ditolak["order_id"], ADMIN, "buram", SESUDAH_UPLOAD)
    terapkan(kon, ditolak, 3, transaction_id="trx-ditolak-3")
    for order in (transfer, qris, ditolak):
        assert po.detail_order(kon, order["order_id"], SESUDAH)["dua_jalur"] is False
    assert not any(i["dua_jalur"] for i in pesanan.daftar_admin(
        kon, halaman=1, per_halaman=10, sekarang=SESUDAH)["items"])


def _dua_order_bukti_sama(kon, n_lain=1):
    pertama, _ = menunggu(kon, 1, akun=akun_ke(1))
    lain = []
    for n in range(2, 2 + n_lain):
        order, _ = tagihan(kon, n, akun=akun_ke(n))
        unggah(kon, order, n, akun=akun_ke(n), sha256=sha(1))
        lain.append(order)
    return pertama, lain


def test_detail_menghitung_order_lain_dengan_sha256_bukti_sama(kon):
    pertama, lain = _dua_order_bukti_sama(kon, n_lain=2)
    sendiri, _ = menunggu(kon, 9, akun=akun_ke(9))
    assert po.detail_order(kon, pertama["order_id"], SESUDAH)["bukti_dipakai_ulang"] == 2
    assert po.detail_order(kon, lain[0]["order_id"], SESUDAH)["bukti_dipakai_ulang"] == 2
    assert po.detail_order(kon, sendiri["order_id"], SESUDAH)["bukti_dipakai_ulang"] == 0


def test_detail_bukti_dipakai_ulang_hanya_hitungan_tanpa_id_order_atau_sha(kon):
    pertama, lain = _dua_order_bukti_sama(kon)
    teks = repr(po.detail_order(kon, pertama["order_id"], SESUDAH))
    assert lain[0]["order_id"] not in teks and sha(1) not in teks and akun_ke(2)[:13] not in teks


def test_unggah_ulang_berkas_sama_pada_order_sendiri_bukan_pemakaian_ulang(kon):
    order, _ = menunggu(kon, 1)
    unggah(kon, order, 2, sha256=sha(1))                   # idempoten: tidak ada baris baru
    assert po.detail_order(kon, order["order_id"], SESUDAH)["bukti_dipakai_ulang"] == 0


def test_detail_pada_db_tanpa_transfer_bukti_dipakai_ulang_nol(kon_qris):
    order = buat(kon_qris, 1)
    detail = po.detail_order(kon_qris, order["order_id"], SEKARANG)
    assert detail["bukti_dipakai_ulang"] == 0 and detail["dua_jalur"] is False


# --- menunggu > 72 jam ------------------------------------------------------------

KINI = "2026-11-18T12:00:00"


def _menunggu_diunggah(kon, n, dibuat, diunggah):
    order, _ = tagihan(kon, n, akun=akun_ke(n), sekarang=dibuat)
    unggah(kon, order, n, akun=akun_ke(n), sekarang=diunggah)
    return order["order_id"]


def _empat_menunggu(kon):
    """lama (4 hari), batas (tepat 72 jam), hampir (72 jam kurang 1 detik), baru (0 jam)."""
    return {
        "lama": _menunggu_diunggah(kon, 1, "2026-11-14T10:00:00", "2026-11-14T11:00:00"),
        "batas": _menunggu_diunggah(kon, 2, "2026-11-15T09:00:00", "2026-11-15T12:00:00"),
        "hampir": _menunggu_diunggah(kon, 3, "2026-11-15T10:00:00", "2026-11-15T12:00:01"),
        "baru": _menunggu_diunggah(kon, 4, "2026-11-18T10:00:00", "2026-11-18T11:00:00"),
    }


def _tab_menunggu(kon):
    return pesanan_admin.daftar_tersaring(kon, halaman=1, per_halaman=25, sekarang=KINI, kelompok="menunggu")


def test_menunggu_lama_ditandai_mulai_72_jam_sejak_bukti_terakhir(kon):
    o = _empat_menunggu(kon)
    tanda = {i["order_id"]: i["menunggu_lama"] for i in _tab_menunggu(kon)["items"]}
    assert tanda == {o["lama"]: True, o["batas"]: True, o["hampir"]: False, o["baru"]: False}


def test_menunggu_lama_diurutkan_paling_atas_di_tab_menunggu(kon):
    o = _empat_menunggu(kon)
    urutan = [i["order_id"] for i in _tab_menunggu(kon)["items"]]
    assert urutan == [o["batas"], o["lama"], o["baru"], o["hampir"]]     # lama dulu; sisanya urut semula


def test_menunggu_lama_diurutkan_juga_di_daftar_hanya_menunggu(kon):
    o = _empat_menunggu(kon)
    daftar = pesanan.daftar_admin(kon, halaman=1, per_halaman=25, sekarang=KINI, hanya_menunggu=True)
    assert [i["order_id"] for i in daftar["items"]] == [o["batas"], o["lama"], o["baru"], o["hampir"]]
    assert daftar["items"] == _tab_menunggu(kon)["items"]


def test_menunggu_lama_tidak_mengubah_urutan_kelompok_lain(kon):
    o = _empat_menunggu(kon)
    semua = pesanan_admin.daftar_tersaring(kon, halaman=1, per_halaman=25, sekarang=KINI)
    assert [i["order_id"] for i in semua["items"]] == [o["baru"], o["hampir"], o["batas"], o["lama"]]
    assert sum(1 for i in semua["items"] if i["menunggu_lama"]) == 2


def test_penanda_menunggu_lama_hanya_untuk_status_menunggu_verifikasi(kon):
    order = _menunggu_diunggah(kon, 1, "2026-11-14T10:00:00", "2026-11-14T11:00:00")
    tf.tolak(kon, order, ADMIN, "buram", "2026-11-14T12:00:00")
    item = pesanan_admin.daftar_tersaring(kon, halaman=1, per_halaman=5, sekarang=KINI)["items"][0]
    assert item["status"] != "menunggu_verifikasi" and item["menunggu_lama"] is False


def test_penanda_memakai_bukti_terakhir_bukan_bukti_pertama(kon):
    order = _menunggu_diunggah(kon, 1, "2026-11-14T10:00:00", "2026-11-14T11:00:00")
    unggah(kon, {"order_id": order}, 7, akun=akun_ke(1), sekarang="2026-11-14T12:00:00")
    assert _tab_menunggu(kon)["items"][0]["menunggu_lama"] is True
    kini_awal = pesanan_admin.daftar_tersaring(kon, halaman=1, per_halaman=5, sekarang="2026-11-15T11:00:00",
                                               kelompok="menunggu")
    assert kini_awal["items"][0]["menunggu_lama"] is False             # bukti terakhir baru 23 jam


# --- daftar_tersaring ----------------------------------------------------------------

def _isi_status_beragam(kon):
    """Satu order per kelompok: belum bayar, menunggu, dibayar (transfer), direfund, ditolak, kedaluwarsa."""
    belum, _ = tagihan(kon, 1, akun=akun_ke(1), sekarang="2026-11-18T09:00:00")
    tunggu, _ = menunggu(kon, 2, akun=akun_ke(2))
    lunas, _ = menunggu(kon, 3, akun=akun_ke(3))
    tf.setujui(kon, lunas["order_id"], ADMIN, SESUDAH_UPLOAD)
    refund, _ = menunggu(kon, 4, akun=akun_ke(4))
    tf.setujui(kon, refund["order_id"], ADMIN, SESUDAH_UPLOAD)
    pesanan.catat_refund(kon, refund["order_id"], operasi(9), "admin_a", "kebijakan", SESUDAH_UPLOAD)
    tolak, _ = menunggu(kon, 5, akun=akun_ke(5))
    tf.tolak(kon, tolak["order_id"], ADMIN, "Tidak jelas", SESUDAH_UPLOAD)
    lama = buat(kon, 6, akun=akun_ke(6), sekarang="2026-11-10T09:00:00")
    return {"belum": belum, "tunggu": tunggu, "lunas": lunas, "refund": refund, "tolak": tolak, "lama": lama}


def _ids(daftar):
    return {i["order_id"] for i in daftar["items"]}


def _tersaring(kon, kelompok=None, halaman=1, per_halaman=25):
    return pesanan_admin.daftar_tersaring(
        kon, halaman=halaman, per_halaman=per_halaman, sekarang=SESUDAH_UPLOAD, kelompok=kelompok)


def test_kelompok_status_menyekat_semua_status_turunan_tepat_satu_kali():
    semua = [s for status in pesanan_admin.KELOMPOK_STATUS.values() for s in status]
    assert sorted(semua) == sorted(pesanan.STATUS_TURUNAN) and len(semua) == len(set(semua))


def test_tersaring_per_kelompok_hanya_status_anggota_dan_total_sesudah_saring(kon):
    o = _isi_status_beragam(kon)
    harap = {
        "menunggu": {o["tunggu"]["order_id"]},
        "belum_bayar": {o["belum"]["order_id"]},
        "dibayar": {o["lunas"]["order_id"], o["refund"]["order_id"]},
        "ditolak": {o["tolak"]["order_id"], o["lama"]["order_id"]},
    }
    for kelompok, ids in harap.items():
        daftar = _tersaring(kon, kelompok)
        assert _ids(daftar) == ids and daftar["total"] == len(ids)
        assert all(i["status"] in pesanan_admin.KELOMPOK_STATUS[kelompok] for i in daftar["items"])


def test_tersaring_hitungan_semua_kelompok_konsisten_dengan_status_yang_tampil(kon):
    _isi_status_beragam(kon)
    semua = _tersaring(kon)
    assert semua["total"] == 6 and semua["hitungan"] == {
        "menunggu": 1, "belum_bayar": 1, "dibayar": 2, "ditolak": 2, "semua": 6}
    assert _tersaring(kon, "dibayar")["hitungan"] == semua["hitungan"]
    assert semua["hitungan"]["semua"] == sum(v for k, v in semua["hitungan"].items() if k != "semua")


def test_tersaring_semua_sama_dengan_daftar_admin_lama(kon):
    _isi_status_beragam(kon)
    lama = pesanan.daftar_admin(kon, halaman=1, per_halaman=25, sekarang=SESUDAH_UPLOAD)
    baru = _tersaring(kon)
    assert baru["items"] == lama["items"] and baru["total"] == lama["total"]


def test_tersaring_menunggu_sama_dengan_hanya_menunggu_lama(kon):
    _isi_status_beragam(kon)
    lama = pesanan.daftar_admin(kon, halaman=1, per_halaman=25, sekarang=SESUDAH_UPLOAD, hanya_menunggu=True)
    assert _tersaring(kon, "menunggu")["items"] == lama["items"]


def test_tersaring_paginasi_memotong_setelah_saring(kon):
    for n in range(1, 8):
        menunggu(kon, n, akun=akun_ke(n))
    h1 = _tersaring(kon, "menunggu", 1, 3)
    h3 = _tersaring(kon, "menunggu", 3, 3)
    assert (len(h1["items"]), len(h3["items"]), h1["total"]) == (3, 1, 7)
    assert _tersaring(kon, "menunggu", 4, 3)["items"] == ()


@pytest.mark.parametrize("kelompok", ["sembarang", "", "MENUNGGU", "semua", 1])
def test_tersaring_kelompok_asing_ditolak(kon, kelompok):
    with pytest.raises(pesanan.PesananDataTidakSah):
        _tersaring(kon, kelompok)


def test_tersaring_per_halaman_tak_sah_ditolak(kon):
    for nilai in (0, 101, "25", True):
        with pytest.raises(pesanan.PesananDataTidakSah):
            _tersaring(kon, None, 1, nilai)


def test_tersaring_pada_db_tanpa_transfer_tetap_jalan(kon_qris):
    order = buat(kon_qris, 1)
    daftar = pesanan_admin.daftar_tersaring(kon_qris, halaman=1, per_halaman=25, sekarang=SEKARANG,
                                            kelompok="belum_bayar")
    assert _ids(daftar) == {order["order_id"]} and daftar["hitungan"]["belum_bayar"] == 1
