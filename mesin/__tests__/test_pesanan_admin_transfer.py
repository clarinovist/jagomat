"""Pembaca admin transfer: ringkasan daftar, detail verifikasi, tab menunggu, keputusan atas bukti yang dilihat.

Data sintetis; ledger sementara di tmp_path (tanpa HTTP).
"""
import pytest

import pesanan
import pesanan_admin_transfer as pat
import pesanan_transfer as tf
from pesanan_kit import (AKUN_A, AKUN_B, SEKARANG, SESUDAH_KEDALUWARSA, buat, ord_id,
                         siapkan_db)
from transfer_kit import (ADMIN, SESUDAH_UPLOAD, berkas, menunggu, siapkan_db_transfer, tagihan,
                          unggah)


@pytest.fixture
def kon(tmp_path):
    with tf.buka(siapkan_db_transfer(tmp_path), tulis_data=True) as sambungan:
        yield sambungan


# --- ringkasan -----------------------------------------------------------------

def test_ringkasan_memuat_nominal_persis_jumlah_dan_waktu_unggah_terakhir(kon):
    order, tag = tagihan(kon, 1)
    unggah(kon, order, 1, sekarang="2026-11-18T11:00:00")
    unggah(kon, order, 2, sekarang="2026-11-18T12:00:00")
    hasil = pat.ringkasan(kon, [order["order_id"]])
    assert hasil[order["order_id"]] == {
        "nominal": tag["nominal_transfer"], "jumlah_bukti": 2, "diunggah": "2026-11-18T12:00:00"}


def test_ringkasan_order_tanpa_tagihan_atau_bukti_bernilai_kosong(kon):
    order = buat(kon, 1)
    assert pat.ringkasan(kon, [order["order_id"]])[order["order_id"]] == {
        "nominal": None, "jumlah_bukti": 0, "diunggah": None}


def test_ringkasan_tanpa_id_kosong_dan_pada_db_tanpa_transfer(tmp_path):
    with pesanan.buka(siapkan_db(tmp_path), tulis_data=True) as kon:
        order = buat(kon, 1)
        assert pat.ringkasan(kon, []) == {}
        assert pat.ringkasan(kon, [order["order_id"]]) == {}


def test_ringkasan_hanya_untuk_id_yang_diminta(kon):
    satu, _ = menunggu(kon, 1)
    dua, _ = menunggu(kon, 2, akun=AKUN_B)
    assert set(pat.ringkasan(kon, [satu["order_id"]])) == {satu["order_id"]}
    assert dua["order_id"] not in pat.ringkasan(kon, [satu["order_id"]])


# --- detail --------------------------------------------------------------------

def test_detail_order_menunggu_memuat_bukti_nominal_dan_bukti_terakhir(kon):
    order, tag = tagihan(kon, 1)
    unggah(kon, order, 1)
    unggah(kon, order, 2, sekarang="2026-11-18T12:30:00")
    d = pat.detail(kon, order["order_id"], SESUDAH_UPLOAD)
    assert d["status"] == "menunggu_verifikasi"
    assert d["nominal"] == tag["nominal_transfer"]
    assert [b["keadaan"] for b in d["bukti"]] == ["menunggu", "menunggu"]
    assert d["bukti_terakhir_id"] == d["bukti"][-1]["id"]
    assert set(d["bukti"][0]) == {"id", "urutan", "mime", "ukuran", "diunggah", "keadaan"}
    assert "berkas" not in d["bukti"][0] and "sha256" not in d["bukti"][0]
    assert d["keputusan"] == ()


def test_detail_menandai_bukti_diputuskan_dan_riwayat_keputusan(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    tf.tolak(kon, order["order_id"], ADMIN, "Nominal kurang", SESUDAH_UPLOAD)
    unggah(kon, order, 2, sekarang="2026-11-18T12:30:00")
    d = pat.detail(kon, order["order_id"], "2026-11-18T13:00:00")
    assert [b["keadaan"] for b in d["bukti"]] == ["diputuskan", "menunggu"]
    assert [(k["keputusan"], k["alasan"]) for k in d["keputusan"]] == [("tolak", "Nominal kurang")]


def test_detail_menandai_bukti_dihapus(kon):
    order, _ = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    tf.tandai_dihapus(kon, pat.detail(kon, order["order_id"], SESUDAH_UPLOAD)["bukti"][0]["id"],
                      "2026-12-30T00:00:00")
    assert pat.detail(kon, order["order_id"], "2026-12-30T00:00:00")["bukti"][0]["keadaan"] == "dihapus"


def test_detail_order_tak_dikenal_none(kon):
    assert pat.detail(kon, ord_id(404), SEKARANG) is None


def test_detail_tidak_memuat_data_sensitif(kon):
    order, _ = menunggu(kon, 1)
    d = pat.detail(kon, order["order_id"], SESUDAH_UPLOAD)
    assert d["akun"] == AKUN_A[:13] and AKUN_A not in repr(d)


# --- ambil_bukti ---------------------------------------------------------------

def test_ambil_bukti_memuat_nama_berkas_mime_dan_status_hapus(kon):
    order, _ = menunggu(kon, 1)
    bukti_id = pat.detail(kon, order["order_id"], SESUDAH_UPLOAD)["bukti"][0]["id"]
    bukti = pat.ambil_bukti(kon, bukti_id)
    assert bukti == {"id": bukti_id, "order_id": order["order_id"], "berkas": berkas(1),
                     "mime": "image/jpeg", "dihapus": False}


def test_ambil_bukti_menandai_dihapus(kon):
    order, _ = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    bukti_id = pat.detail(kon, order["order_id"], SESUDAH_UPLOAD)["bukti"][0]["id"]
    tf.tandai_dihapus(kon, bukti_id, "2026-12-30T00:00:00")
    assert pat.ambil_bukti(kon, bukti_id)["dihapus"] is True


@pytest.mark.parametrize("nilai", [0, -1, 999, "1", None, True, 1.5])
def test_ambil_bukti_id_tak_sah_atau_tak_ada_none(kon, nilai):
    menunggu(kon, 1)
    assert pat.ambil_bukti(kon, nilai) is None


# --- tab menunggu verifikasi ---------------------------------------------------

def test_daftar_hanya_menunggu_hanya_status_menunggu_verifikasi(kon):
    menunggu(kon, 1)
    buat(kon, 2, akun=AKUN_B)                   # belum bayar
    lunas, _ = menunggu(kon, 3, akun=AKUN_B)
    tf.setujui(kon, lunas["order_id"], ADMIN, SESUDAH_UPLOAD)
    ditolak, _ = menunggu(kon, 4, akun=AKUN_B)
    tf.tolak(kon, ditolak["order_id"], ADMIN, "Tidak jelas", SESUDAH_UPLOAD)
    hasil = pesanan.daftar_admin(kon, halaman=1, per_halaman=25, sekarang=SESUDAH_UPLOAD,
                                 hanya_menunggu=True)
    assert [i["order_id"] for i in hasil["items"]] == [ord_id(1)]
    assert hasil["total"] == 1 and all(i["status"] == "menunggu_verifikasi" for i in hasil["items"])


def test_daftar_hanya_menunggu_tetap_muncul_sesudah_jendela_lewat(kon):
    menunggu(kon, 1)
    hasil = pesanan.daftar_admin(kon, halaman=1, per_halaman=25, sekarang=SESUDAH_KEDALUWARSA,
                                 hanya_menunggu=True)
    assert hasil["total"] == 1


def test_daftar_hanya_menunggu_paginasi_menurut_hasil_terfilter(kon):
    for n in range(1, 4):
        menunggu(kon, n, akun=AKUN_A if n == 1 else "akun_" + "%02x" % (0x10 + n) * 16)
    hal1 = pesanan.daftar_admin(kon, halaman=1, per_halaman=2, sekarang=SESUDAH_UPLOAD, hanya_menunggu=True)
    hal2 = pesanan.daftar_admin(kon, halaman=2, per_halaman=2, sekarang=SESUDAH_UPLOAD, hanya_menunggu=True)
    assert (hal1["total"], len(hal1["items"]), len(hal2["items"])) == (3, 2, 1)
    assert {i["order_id"] for i in hal1["items"] + hal2["items"]} == {ord_id(1), ord_id(2), ord_id(3)}


def test_daftar_hanya_menunggu_kosong_pada_db_tanpa_transfer(tmp_path):
    with pesanan.buka(siapkan_db(tmp_path), tulis_data=True) as kon:
        buat(kon, 1)
        hasil = pesanan.daftar_admin(kon, halaman=1, per_halaman=25, sekarang=SEKARANG, hanya_menunggu=True)
        assert hasil["items"] == () and hasil["total"] == 0


def test_daftar_tanpa_filter_tetap_memuat_semua_dan_bentuk_item_tidak_berubah(kon):
    menunggu(kon, 1)
    buat(kon, 2, akun=AKUN_B)
    hasil = pesanan.daftar_admin(kon, halaman=1, per_halaman=25, sekarang=SESUDAH_UPLOAD)
    assert hasil["total"] == 2
    assert set(hasil["items"][0]) == {"order_id", "akun", "dibuat", "kedaluwarsa", "alasan_kode", "status", "dua_jalur", "menunggu_lama"}


# --- keputusan atas bukti yang dilihat -----------------------------------------

def test_setujui_dengan_bukti_terakhir_cocok_sah(kon):
    order, _ = menunggu(kon, 1)
    terakhir = pat.detail(kon, order["order_id"], SESUDAH_UPLOAD)["bukti_terakhir_id"]
    hasil = tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD, bukti_terakhir_id=terakhir)
    assert hasil["status"] == "sudah_dibayar"


def test_setujui_bukti_baru_masuk_sesudah_dilihat_ditolak_tanpa_tulis(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    dilihat = pat.detail(kon, order["order_id"], SESUDAH_UPLOAD)["bukti_terakhir_id"]
    unggah(kon, order, 2, sekarang="2026-11-18T12:30:00")
    with pytest.raises(pesanan.PesananKonflik):
        tf.setujui(kon, order["order_id"], ADMIN, "2026-11-18T13:00:00", bukti_terakhir_id=dilihat)
    assert kon.execute("SELECT COUNT(*) FROM transfer_verifikasi").fetchone()[0] == 0
    assert kon.execute("SELECT COUNT(*) FROM transfer_lunas").fetchone()[0] == 0


def test_tolak_bukti_baru_masuk_sesudah_dilihat_ditolak_tanpa_tulis(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    dilihat = pat.detail(kon, order["order_id"], SESUDAH_UPLOAD)["bukti_terakhir_id"]
    unggah(kon, order, 2, sekarang="2026-11-18T12:30:00")
    with pytest.raises(pesanan.PesananKonflik):
        tf.tolak(kon, order["order_id"], ADMIN, "Kurang jelas", "2026-11-18T13:00:00",
                 bukti_terakhir_id=dilihat)
    assert kon.execute("SELECT COUNT(*) FROM transfer_verifikasi").fetchone()[0] == 0


def test_setujui_tanpa_bukti_terakhir_perilaku_lama_tetap(kon):
    order, _ = menunggu(kon, 1)
    assert tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)["status"] == "sudah_dibayar"
