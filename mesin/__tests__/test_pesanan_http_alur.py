"""Alur uang pesanan (Fase 3c-3) lewat HTTP: pesan, create, QR, status, periksa, ulang.

Provider PALSU (tanpa jaringan). Ledger dibaca langsung dari DB admin sementara untuk
membuktikan efek (atau ketiadaannya). Guard gerbang/peran/token ada di test_pesanan_http.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis_kit  # noqa: E402
import funnel_pages  # noqa: E402
import pesanan  # noqa: E402
import pesanan_alur  # noqa: E402
import pesanan_kit  # noqa: E402
import pesanan_pages  # noqa: E402
from cek_http_kit import id_akun  # noqa: E402
from pesanan_http_kit import (  # noqa: E402
    AKUN_A, BUAT, HASIL, KOSONG, MERCHANT, NAMA_A, PERIKSA, QR, STATUS, ULANG, WAKTU_AWAL,
    ProviderPalsu, Respons, atur_tahap, bayar, cek_selesai, data_status, jam,
    keadaan_ledger, keluarga, kirim, ledger, mulai_cek, minta_mentah, pasang_runtime, pesan,
    satu_order, selesaikan, server, settlement, siap_pesan, simpan_kontak, tabel_langganan,
    tambah_anak, teks_tampak, tertutup, url_qr,
)

PNG_SINTETIS = b"\x89PNG"


def _siapkan_order(bayar):
    siap_pesan(bayar)
    assert pesan(bayar)[0] == 303
    order = satu_order()
    return order, bayar.provider.transaksi[order["order_id"]]


def _halaman(bayar, jalur=STATUS):
    kode, isi, _t = minta_mentah(bayar, jalur, AKUN_A)
    assert kode == 200
    return isi


def _observasi():
    with ledger() as kon:
        return [dict(r) for r in kon.execute("SELECT * FROM pesanan_pengamatan ORDER BY dibuat, operasi_id")]


def _receipt():
    with ledger() as kon:
        baris = kon.execute("SELECT * FROM pesanan_receipt").fetchall()
        return [dict(r) for r in baris]


# --- pesan: sukses, nominal, idempoten -------------------------------------------

def test_pesan_sukses_satu_order_nominal_konstanta_create_sekali_dan_prg(bayar):
    siap_pesan(bayar)
    kode, isi, tajuk = pesan(bayar)
    assert (kode, isi, tajuk["Location"]) == (303, "", STATUS)
    order = satu_order()
    assert order["rupiah"] == pesanan.RUPIAH_PAKET == 49000
    assert order["merchant"] == MERCHANT and order["akun_id"] == id_akun(AKUN_A)
    assert bayar.provider.jumlah_create == 1
    permintaan = bayar.provider.panggilan[0]
    assert json.loads(permintaan.body)["transaction_details"] == {
        "order_id": order["order_id"], "gross_amount": 49000}
    assert permintaan.headers["Idempotency-Key"] == order["idempotency_key"]
    assert order["order_id"] not in str(tajuk) and NAMA_A not in str(tajuk)


def test_create_dicatat_sebagai_pengamatan_tanpa_karangan_dan_tanpa_receipt(bayar):
    order, trx = _siapkan_order(bayar)
    (obs,) = _observasi()
    assert obs["operasi_id"].startswith("buat_") and obs["transaksi_id"] == trx
    assert (obs["transaction_status"], obs["status_code"]) == ("tidak_dikenal", "")
    assert _receipt() == []
    assert keadaan_ledger()["pesanan_jendela"] == 1


def test_halaman_status_belum_bayar_qr_same_origin_tanpa_data_sensitif(bayar):
    order, trx = _siapkan_order(bayar)
    isi = _halaman(bayar)
    assert f'<img src="{QR}"' in isi and "Menunggu pembayaran" in isi
    assert NAMA_A in isi
    for rahasia in (order["order_id"], trx, "api.midtrans.com", "qr-code", order["idempotency_key"]):
        assert rahasia not in isi
    assert "saya sudah bayar" not in isi.lower() and "sudah membayar" not in isi.lower()


def test_copy_harga_refund_netral_tanpa_kata_terlarang_dan_satu_nominal(bayar):
    _siapkan_order(bayar)
    isi = _halaman(bayar)
    rp = pesanan_pages.COPY_REFUND
    assert funnel_pages.COPY_HARGA in isi and "Rp49.000" in funnel_pages.COPY_HARGA
    assert "Rp" + format(pesanan.RUPIAH_PAKET, ",").replace(",", ".") in funnel_pages.COPY_HARGA
    assert rp in isi
    assert funnel_pages.COPY_PEMBATALAN not in isi and "dikembalikan penuh" not in isi
    tampak = teks_tampak(isi).lower()
    for terlarang in ("diagnosis lengkap", "pasti akurat", "nilai pasti naik", "harga kelas"):
        assert terlarang not in tampak
    assert set(re.findall(r"Rp\s?[\d.]+", teks_tampak(isi))) == {"Rp49.000"}


def test_post_ganda_tidak_membuat_order_atau_transaksi_kedua(bayar):
    siap_pesan(bayar)
    assert pesan(bayar)[0] == 303
    awal = keadaan_ledger()
    assert pesan(bayar)[0] == 303
    assert keadaan_ledger() == awal and awal["pesanan_order"] == 1
    assert bayar.provider.jumlah_create == 1


def test_nominal_dan_harga_dari_form_ditolak_dan_tidak_dipakai(bayar):
    siap_pesan(bayar)
    for field in ("rupiah", "nominal", "harga", "gross_amount"):
        assert pesan(bayar, ekstra={field: "1000"})[0] == 400
    assert keadaan_ledger() == KOSONG and bayar.provider.panggilan == []


# --- prasyarat server -----------------------------------------------------------

def test_tanpa_whatsapp_tidak_ada_order_dan_tautan_kontak(bayar):
    cek_selesai(bayar)
    kode, isi, _t = pesan(bayar)
    assert kode == 409 and pesanan_pages.COPY_BUTUH_KONTAK in isi
    assert 'href="/akun/kontak"' in isi
    assert keadaan_ledger() == KOSONG and bayar.provider.panggilan == []


def test_cek_belum_selesai_tidak_bisa_memesan(bayar):
    mulai_cek(bayar, AKUN_A)
    simpan_kontak(bayar)
    kode, isi, _t = pesan(bayar)
    assert kode == 409 and pesanan_pages.COPY_CEK_BELUM_SELESAI in isi
    assert keadaan_ledger() == KOSONG and bayar.provider.panggilan == []


def test_tanpa_cek_sama_sekali_tidak_bisa_memesan(bayar):
    simpan_kontak(bayar)
    assert pesan(bayar)[0] == 409
    assert keadaan_ledger() == KOSONG


def test_cek_milik_anak_lain_akun_yang_sama_tidak_dipakai(bayar):
    """Anak id terkecil belum selesai; anak lain selesai: cek terbaru akun != cek anak ini."""
    sesi_a = mulai_cek(bayar, AKUN_A)
    anak_c = tambah_anak(bayar, "Anak Sintetis Gamma", "guru", 5)
    with bayar.buka() as kon:
        sesi_c = cek_gratis_kit.mulai_cek(kon, id_akun(AKUN_A), anak_c, "guru", seed=11)
    selesaikan(bayar, sesi_c, semua_benar=10)
    assert minta_mentah(bayar, HASIL, AKUN_A)[0] == 200
    simpan_kontak(bayar)
    with bayar.buka() as kon:
        import cek_gratis
        assert cek_gratis.baca_hasil(kon, id_akun(AKUN_A))["status"] == "selesai"  # jebakan
        assert cek_gratis.hasil_siswa(kon, id_akun(AKUN_A), bayar.anak_a)["status"] == "belum_selesai"
    assert sesi_a != sesi_c
    kode, isi, _t = pesan(bayar)
    assert kode == 409 and pesanan_pages.COPY_CEK_BELUM_SELESAI in isi
    assert keadaan_ledger() == KOSONG and bayar.provider.panggilan == []


def test_kuota_20_habis_teks_jujur_tanpa_order_dan_tanpa_provider(bayar):
    siap_pesan(bayar)
    with ledger() as kon:
        for n in range(1, 21):
            pesanan_kit.buat(kon, n, akun=pesanan_kit.AKUN_B, siswa=1000 + n)
    kode, isi, _t = pesan(bayar)
    assert kode == 409 and pesanan_pages.COPY_KUOTA_HABIS in isi
    assert keadaan_ledger()["pesanan_order"] == 20 and bayar.provider.panggilan == []


def test_kuota_19_masih_bisa_memesan_yang_ke_20(bayar):
    siap_pesan(bayar)
    with ledger() as kon:
        for n in range(1, 20):
            pesanan_kit.buat(kon, n, akun=pesanan_kit.AKUN_B, siswa=1000 + n)
    assert pesan(bayar)[0] == 303
    assert keadaan_ledger()["pesanan_order"] == 20


# --- create gagal dan coba lagi -------------------------------------------------

def test_create_gagal_order_belum_bayar_tanpa_qr_lalu_coba_lagi_kunci_sama(bayar):
    siap_pesan(bayar)
    bayar.provider.mode_create = "gagal"
    assert pesan(bayar)[0] == 303
    order = satu_order()
    assert keadaan_ledger()["pesanan_order"] == 1 and _observasi() == []
    isi = _halaman(bayar)
    assert "Menunggu pembayaran" in isi and f'src="{QR}"' not in isi
    assert f'action="{BUAT}"' in isi and pesanan_pages.COPY_TOMBOL["buat"] in isi
    assert minta_mentah(bayar, QR, AKUN_A)[0] == 404
    bayar.provider.mode_create = "ok"
    assert kirim(bayar, BUAT)[0] == 303
    assert keadaan_ledger()["pesanan_order"] == 1 and len(_observasi()) == 1
    assert bayar.provider.kunci_create == [order["idempotency_key"]] * 2
    assert f'src="{QR}"' in _halaman(bayar)


def test_buat_tanpa_order_tidak_menghubungi_provider(bayar):
    siap_pesan(bayar)
    assert kirim(bayar, BUAT)[0] == 303
    assert bayar.provider.panggilan == [] and keadaan_ledger() == KOSONG


def test_buat_tidak_mengulang_create_bila_jendela_sudah_punya_transaksi(bayar):
    _siapkan_order(bayar)
    assert kirim(bayar, BUAT)[0] == 303
    assert bayar.provider.jumlah_create == 1


def test_create_tanpa_url_qr_transaksi_tetap_dicatat_dan_qr_dari_status(bayar):
    siap_pesan(bayar)
    bayar.provider.mode_create = "tanpa_qr"
    assert pesan(bayar)[0] == 303
    assert len(_observasi()) == 1
    assert f'src="{QR}"' in _halaman(bayar)


# --- QR -------------------------------------------------------------------------

def test_qr_png_same_origin_no_store_nosniff_url_dari_status_tervalidasi(bayar):
    order, trx = _siapkan_order(bayar)
    kode, isi, tajuk = minta_mentah(bayar, QR, AKUN_A)
    assert kode == 200 and tajuk["Content-Type"] == "image/png"
    assert tajuk["X-Content-Type-Options"] == "nosniff" and "no-store" in tajuk["Cache-Control"]
    assert "default-src 'none'" in tajuk["Content-Security-Policy"]
    assert isi and bayar.provider.url_gambar == [url_qr(trx)]


def _qr_404(bayar):
    acuan = minta_mentah(bayar, "/rute-tidak-ada", AKUN_A)
    assert minta_mentah(bayar, QR, AKUN_A)[:2] == acuan[:2]


def test_qr_404_identik_tanpa_order(bayar):
    siap_pesan(bayar)
    _qr_404(bayar)


def test_qr_404_tanpa_transaksi(bayar):
    siap_pesan(bayar)
    bayar.provider.mode_create = "gagal"
    pesan(bayar)
    _qr_404(bayar)
    assert bayar.provider.url_gambar == []


def test_qr_404_setelah_lunas(bayar):
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    assert minta_mentah(bayar, STATUS, AKUN_A)[0] == 200
    _qr_404(bayar)
    assert bayar.provider.url_gambar == []


def test_qr_404_setelah_kedaluwarsa_lokal(bayar, jam):
    _siapkan_order(bayar)
    jam.maju_jam(25)
    _qr_404(bayar)
    assert bayar.provider.url_gambar == []


@pytest.mark.parametrize("ganti", [
    {"transaction_id": "trx-lain-sekali"}, {"gross_amount": "1000.00"}, {"merchant_id": "M_LAIN"},
    {"currency": "USD"}, {"payment_type": "gopay"}, {"fraud_status": "deny"},
    {"status_code": "200"}, {"transaction_status": "expire", "status_code": "407"},
])
def test_qr_404_bila_status_provider_tidak_cocok_order(bayar, ganti):
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: data_status(oid, trx, **ganti)
    _qr_404(bayar)
    assert bayar.provider.url_gambar == []


def test_qr_milik_akun_lain_404_dan_tidak_menyentuh_gambar(bayar):
    _siapkan_order(bayar)
    from pesanan_http_kit import AKUN_B
    siap_pesan(bayar, AKUN_B)
    assert minta_mentah(bayar, QR, AKUN_B)[0] == 404
    assert bayar.provider.url_gambar == []


def test_qr_bukan_png_dari_transport_ditolak_503(bayar):
    _siapkan_order(bayar)
    bayar.provider.gambar = lambda url: b"<html>bukan png</html>"
    kode, isi, _t = minta_mentah(bayar, QR, AKUN_A)
    assert kode == 503 and "bukan png" not in isi


# --- status: lunas hanya dari provider ------------------------------------------

def test_settlement_cocok_dari_status_provider_menjadi_sudah_dibayar(bayar):
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    isi = _halaman(bayar)
    assert "Pembayaran diterima. Akses laporan lengkap menyusul" in teks_tampak(isi)
    assert f'src="{QR}"' not in isi and "<form" not in isi.split("</header>", 1)[1]
    (receipt,) = _receipt()
    assert (receipt["hasil"], receipt["alasan_kode"], receipt["rupiah"]) == ("lunas", "ok", 49000)
    assert receipt["transaksi_id"] == trx and receipt["order_id"] == order["order_id"]


def test_pembayaran_yang_diperiksa_tidak_menjanjikan_akses_atau_unduhan(bayar):
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    isi = _halaman(bayar)
    tampak = teks_tampak(isi).lower()
    for kata in ("unduh", "download", "buka laporan", "mulai latihan", "akses sekarang"):
        assert kata not in tampak
    assert 'href="/laporan' not in isi and 'href="/anak' not in isi
    langganan = tabel_langganan()
    assert langganan["langganan_grant"] == () and langganan["langganan_receipt"] == ()


def test_nominal_berbeda_perlu_diperiksa_tanpa_status_lunas(bayar):
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx, gross_amount="1000.00")
    isi = _halaman(bayar)
    assert pesanan_pages.COPY_STATUS["perlu_diperiksa"][1] in isi
    assert "Pembayaran diterima" not in isi and f'src="{QR}"' not in isi
    (receipt,) = _receipt()
    assert (receipt["hasil"], receipt["alasan_kode"]) == ("perlu_diperiksa", "nominal")


def test_callback_hint_tidak_membuat_lunas(bayar):
    order, trx = _siapkan_order(bayar)
    with ledger() as kon:
        pesanan.catat_petunjuk(kon, order["order_id"], settlement(order["order_id"], trx),
                               WAKTU_AWAL, "cbk_" + "a" * 32)
    isi = _halaman(bayar)  # provider tetap menjawab pending
    assert "Menunggu pembayaran" in isi and "Pembayaran diterima" not in isi
    assert _receipt() == []


def test_parameter_url_dan_form_tidak_bisa_menyatakan_lunas(bayar):
    order, trx = _siapkan_order(bayar)
    jalur = STATUS + "?status=settlement&transaction_status=settlement&order_id=" + order["order_id"]
    kode, isi, _t = minta_mentah(bayar, jalur, AKUN_A)
    assert kode == 200 and "Menunggu pembayaran" in isi and _receipt() == []
    assert kirim(bayar, PERIKSA, AKUN_A, ekstra={"status": "settlement"})[0] == 400
    assert _receipt() == []


def test_status_tidak_mundur_setelah_lunas_dan_provider_tidak_ditanya_lagi(bayar):
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    _halaman(bayar)
    panggilan = len(bayar.provider.panggilan)
    bayar.provider.status_data = lambda oid: data_status(
        oid, trx, transaction_status="expire", status_code="407")
    assert "Pembayaran diterima" in _halaman(bayar)
    assert kirim(bayar, PERIKSA, AKUN_A)[0] == 303
    assert len(bayar.provider.panggilan) == panggilan
    assert [r["hasil"] for r in _receipt()] == ["lunas"]


def test_status_ganda_tepat_satu_receipt(bayar):
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    _halaman(bayar)
    with ledger() as kon:
        pesanan.terapkan_hasil_provider(kon, order["order_id"], settlement(order["order_id"], trx),
                                        WAKTU_AWAL, "op-ulang-0001")
    assert len(_receipt()) == 1


def test_direfund_tercatat_menjadi_status_dikembalikan(bayar):
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    _halaman(bayar)
    with ledger() as kon:
        pesanan.catat_refund(kon, order["order_id"], "op-refund-0001", "admin.sintetis",
                             "permintaan_pembeli", WAKTU_AWAL)
    assert pesanan_pages.COPY_STATUS["direfund"][1] in _halaman(bayar)


def test_galat_provider_status_jujur_belum_terperiksa_ledger_tidak_berubah(bayar):
    order, trx = _siapkan_order(bayar)
    awal = keadaan_ledger()
    bayar.provider.status_data = lambda oid: Respons({}, kode=500)
    isi = _halaman(bayar)
    assert pesanan_pages.COPY_BELUM_TERPERIKSA in isi and "Menunggu pembayaran" in isi
    assert f'src="{QR}"' not in isi and keadaan_ledger() == awal
    bayar.provider.status_data = lambda oid: RuntimeError("rahasia-transport")
    isi = _halaman(bayar)
    assert "rahasia-transport" not in isi and keadaan_ledger() == awal


def test_periksa_manual_menerapkan_hasil_provider(bayar):
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    assert kirim(bayar, PERIKSA, AKUN_A)[0] == 303
    assert [r["hasil"] for r in _receipt()] == ["lunas"]


def test_periksa_tanpa_transaksi_tidak_menghubungi_provider(bayar):
    siap_pesan(bayar)
    bayar.provider.mode_create = "gagal"
    pesan(bayar)
    calls = len(bayar.provider.panggilan)
    assert kirim(bayar, PERIKSA, AKUN_A)[0] == 303
    assert len(bayar.provider.panggilan) == calls


def test_get_status_tanpa_order_dialihkan_ke_hasil_cek(bayar):
    siap_pesan(bayar)
    kode, isi, tajuk = minta_mentah(bayar, STATUS, AKUN_A)
    assert (kode, isi, tajuk["Location"]) == (303, "", HASIL)


# --- buat ulang --------------------------------------------------------------------

def _jendela():
    with ledger() as kon:
        return [dict(r) for r in kon.execute("SELECT * FROM pesanan_jendela ORDER BY urutan")]


def test_ulang_saat_belum_diizinkan_tanpa_efek(bayar):
    _siapkan_order(bayar)
    awal = keadaan_ledger()
    assert kirim(bayar, ULANG, AKUN_A)[0] == 303
    assert keadaan_ledger() == awal and bayar.provider.jumlah_create == 1
    assert f'action="{ULANG}"' not in _halaman(bayar)


def test_ulang_setelah_kedaluwarsa_order_sama_kunci_baru_dan_qr_baru(bayar, jam):
    order, trx1 = _siapkan_order(bayar)
    jam.maju_jam(25)
    isi = _halaman(bayar)
    assert "Waktu pembayaran habis" in isi and f'action="{ULANG}"' in isi
    assert f'src="{QR}"' not in isi
    assert kirim(bayar, ULANG, AKUN_A)[0] == 303
    assert keadaan_ledger()["pesanan_order"] == 1 and satu_order()["order_id"] == order["order_id"]
    jendela = _jendela()
    assert [j["urutan"] for j in jendela] == [1, 2]
    assert bayar.provider.kunci_create[1] == jendela[1]["idempotency_key"] != jendela[0]["idempotency_key"]
    trx2 = bayar.provider.transaksi[order["order_id"]]
    assert trx2 != trx1 and f'src="{QR}"' in _halaman(bayar)
    assert minta_mentah(bayar, QR, AKUN_A)[0] == 200
    assert bayar.provider.url_gambar[-1] == url_qr(trx2)


def test_ulang_ganda_tidak_membuat_jendela_ketiga(bayar, jam):
    _siapkan_order(bayar)
    jam.maju_jam(25)
    assert kirim(bayar, ULANG, AKUN_A)[0] == 303
    assert kirim(bayar, ULANG, AKUN_A)[0] == 303
    assert len(_jendela()) == 2 and bayar.provider.jumlah_create == 2


def test_ulang_setelah_provider_menyatakan_mati_untuk_transaksi_jendela_ini(bayar, jam):
    order, trx1 = _siapkan_order(bayar)
    jam.maju_jam(1)  # pengamatan harus lebih baru dari saat jendela dibuka (semantik domain)
    bayar.provider.status_data = lambda oid: data_status(
        oid, trx1, transaction_status="expire", status_code="407")
    isi = _halaman(bayar)  # status expire tercatat; jendela lokal masih aktif
    assert f'action="{ULANG}"' in isi and f'src="{QR}"' not in isi
    bayar.provider.status_data = None
    assert kirim(bayar, ULANG, AKUN_A)[0] == 303
    assert len(_jendela()) == 2 and bayar.provider.jumlah_create == 2
    assert bayar.provider.transaksi[order["order_id"]] != trx1
    assert f'src="{QR}"' in _halaman(bayar)


def test_ulang_dengan_receipt_ditolak_tanpa_efek(bayar, jam):
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    _halaman(bayar)
    jam.maju_jam(25)
    awal = keadaan_ledger()
    assert kirim(bayar, ULANG, AKUN_A)[0] == 303
    assert keadaan_ledger() == awal


def test_sinyal_mati_transaksi_lama_tidak_membuka_jendela_baru(bayar, jam):
    """Jendela 2 tanpa transaksi (create gagal); provider masih melaporkan transaksi LAMA mati."""
    order, trx1 = _siapkan_order(bayar)
    jam.maju_jam(25)
    bayar.provider.mode_create = "gagal"
    assert kirim(bayar, ULANG, AKUN_A)[0] == 303
    assert len(_jendela()) == 2
    bayar.provider.status_data = lambda oid: data_status(
        oid, trx1, transaction_status="expire", status_code="407")
    jam.maju_jam(1)
    isi = _halaman(bayar)  # status transaksi lama diterapkan ke ledger tetapi bukan sinyal jendela 2
    assert f'action="{ULANG}"' not in isi and f'action="{BUAT}"' in isi
    jumlah_create = bayar.provider.jumlah_create
    assert kirim(bayar, ULANG, AKUN_A)[0] == 303
    assert len(_jendela()) == 2 and bayar.provider.jumlah_create == jumlah_create
    assert any(o["transaksi_id"] == trx1 and o["transaction_status"] == "expire" for o in _observasi())


def test_pembayaran_terlambat_transaksi_lama_tetap_dicatat_lunas(bayar, jam):
    """Uang nyata di transaksi jendela lama tidak boleh disaring."""
    order, trx1 = _siapkan_order(bayar)
    jam.maju_jam(25)
    bayar.provider.mode_create = "gagal"
    kirim(bayar, ULANG, AKUN_A)
    bayar.provider.status_data = lambda oid: settlement(oid, trx1)
    assert "Pembayaran diterima" in _halaman(bayar)
    assert [r["transaksi_id"] for r in _receipt()] == [trx1]


# --- isolasi, galat, log ------------------------------------------------------------

def test_jalur_pesanan_tidak_menulis_baris_langganan(bayar, jam):
    awal = tabel_langganan()
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    _halaman(bayar)
    assert tabel_langganan() == awal
    assert all(not baris for nama, baris in tabel_langganan().items()
               if nama in ("langganan_grant", "langganan_receipt", "langganan_invoice"))


def test_galat_domain_tidak_membocorkan_pesan_internal(bayar, monkeypatch):
    siap_pesan(bayar)

    def meledak(*a, **kw):
        raise pesanan.PesananDataTidakSah("RAHASIA-nominal-49000-ord_" + "a" * 32)
    monkeypatch.setattr(pesanan_alur, "pastikan_transaksi", meledak)
    kode, isi, _t = pesan(bayar)
    assert kode == 503 and pesanan_pages.COPY_BELUM_SIAP in isi
    assert "RAHASIA" not in isi and "ord_" not in isi


def test_tidak_ada_data_sensitif_di_log(bayar, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    order, trx = _siapkan_order(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    _halaman(bayar)
    teks = caplog.text
    for rahasia in (order["order_id"], trx, NAMA_A, "49000", "SB-Mid-server"):
        assert rahasia not in teks


def test_ledger_belum_dimigrasikan_halaman_jujur_503_tanpa_efek(keluarga, monkeypatch, jam):
    import pesanan_http
    monkeypatch.setattr(pesanan_http, "_laju", {})
    atur_tahap("checkout")
    keluarga.provider = ProviderPalsu()
    pasang_runtime(keluarga, keluarga.provider)
    siap_pesan(keluarga)
    kode, isi, _t = pesan(keluarga)
    assert kode == 503 and pesanan_pages.COPY_BELUM_SIAP in isi
    kode, isi, _t = minta_mentah(keluarga, STATUS, AKUN_A)
    assert kode == 503 and pesanan_pages.COPY_BELUM_SIAP in isi
    assert keluarga.provider.panggilan == []


def test_copy_refund_selaras_keputusan_18_tanpa_refund_kecuali_terlambat():
    rp = pesanan_pages.COPY_REFUND
    assert "tidak dapat dikembalikan" in rp and "voucher" in rp
    assert "3×24 jam" in rp and "menunggu" in rp and "uang kembali" in rp
    assert "sebelum guru mulai meninjau" not in rp
