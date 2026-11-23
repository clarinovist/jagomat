"""Halaman Detail order admin (`/admin/pesanan/order`) dan aksi periksa/refund dari halaman itu (Fase C).

Provider PALSU dan data sintetis. Efek (atau ketiadaannya) dibuktikan dari ledger dan hitungan panggilan
provider. Tes negatif sandi/CSRF/refund di sini menjadi sasaran mutation di `test_admin_pesanan_mutation.py`.
"""
from __future__ import annotations

import html
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pesanan_detail_pages as dui  # noqa: E402
import admin_pesanan_http as ap  # noqa: E402
from admin_pesanan_kit import (  # noqa: E402
    HALAMAN, ORDER_ASING, PERIKSA, REFUND, TAK_ADA, alamat_detail, baris_refund, form_order, hasil_dari,
    id_admin, jumlah_panggilan, kirim_dari_detail, login_admin, markup, minta_admin, order_bayar,
    order_lunas, token_langsung,
)
from admin_transfer_kit import SETUJUI, kirim_putusan, order_menunggu  # noqa: E402
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_http_kit import (  # noqa: E402,F401  (bayar/keluarga/jam/server/tertutup = fixture)
    MERCHANT, NAMA_A, WA_SINTETIS, atur_tahap, bayar, jam, keadaan_ledger, keluarga, minta_mentah,
    server, tertutup,
)
from pesanan_transfer_http_kit import transfer  # noqa: E402,F401
from schema_pesanan import CATATAN_REFUND  # noqa: E402

AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)


@pytest.fixture()
def admin(bayar):
    return login_admin(bayar)


def _stempel(server):
    return keadaan_ledger(), jumlah_panggilan(server), baris_refund()


def _detail(server, cookie, order_id, hasil=""):
    kode, isi, _t = minta_admin(server, alamat_detail(order_id, hasil), cookie)
    assert kode == 200
    return isi


def _lunas_transfer(transfer, admin) -> str:
    order_id = order_menunggu(transfer)
    assert kirim_putusan(transfer, admin, SETUJUI, order_id)[0] == 303
    return order_id


# --- akses dan isi ---------------------------------------------------------------------

def test_detail_admin_200_privat_memuat_ringkasan_minimal_tanpa_pii(bayar, admin):
    order, trx = order_bayar(bayar)
    kode, isi, tajuk = minta_admin(bayar, alamat_detail(order["order_id"]), admin)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store"
    assert "Detail order" in isi and order["order_id"] in isi and "Peta Kemampuan" in isi
    assert order["akun_id"][:13] in isi and order["akun_id"] not in isi
    assert "QRIS" in isi and "Menunggu pembayaran" in isi
    assert "18 Nov 2026, 17.00 WIB" in isi      # dibuat 10.00 UTC
    assert "19 Nov 2026, 17.00 WIB" in isi      # batas bayar +24 jam
    for terlarang in (NAMA_A, WA_SINTETIS, MERCHANT, trx, order["idempotency_key"], "49000"):
        assert terlarang not in isi


def test_detail_nav_tetap_di_bagian_pesanan_dan_ada_tautan_kembali(bayar, admin):
    order, _trx = order_bayar(bayar)
    isi = _detail(bayar, admin, order["order_id"])
    assert 'href="/admin/pesanan"' in isi and html.escape(dui.COPY_KEMBALI) in isi


def test_detail_transfer_menunggu_nominal_persis_disorot_dan_tautan_bukti(transfer):
    admin = login_admin(transfer)
    order_id = order_menunggu(transfer)
    isi = _detail(transfer, admin, order_id)
    assert re.search(r'Rp49\.<mark class="admin-digit-unik">\d{3}</mark>', isi)
    assert "Transfer rekening" in isi and "Menunggu verifikasi" in isi
    assert 'href="/admin/pesanan/verifikasi?order=%s"' % order_id in isi and dui.COPY_LIHAT_BUKTI in isi
    assert "Order dibuat" in isi and "Bukti transfer diunggah" in isi
    assert "bukti-transfer" not in isi and ".jpg" not in isi


def test_detail_tanpa_bukti_tidak_ada_tautan_bukti(bayar, admin):
    order, _trx = order_bayar(bayar)
    isi = _detail(bayar, admin, order["order_id"])
    assert "/verifikasi?" not in isi and dui.COPY_LIHAT_BUKTI not in isi
    assert "Order dibuat" in isi and "Bukti transfer diunggah" not in isi


def test_detail_banner_hasil_dari_allowlist_detail(bayar, admin):
    order, _trx = order_bayar(bayar)
    isi = _detail(bayar, admin, order["order_id"], "refund_dicatat")
    assert 'role="status"' in isi and "Catatan refund tersimpan" in isi
    assert 'role="status"' not in _detail(bayar, admin, order["order_id"])


@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_detail_nonadmin_404_byte_identik_dan_ledger_tak_dibaca(bayar, admin, akun, monkeypatch):
    order, _trx = order_lunas(bayar, admin)
    dibaca = []

    def gagal(*_a, **_k):
        dibaca.append(1)
        raise sqlite3.OperationalError("tidak boleh dibaca")

    with monkeypatch.context() as ctx:
        ctx.setattr(ap.pesanan, "buka", gagal)
        acuan = minta_mentah(bayar, TAK_ADA, akun)
        assert acuan[0] == 404
        for query in ("?id=" + order["order_id"], "?id=" + ORDER_ASING, "", "?id=sembarang"):
            assert minta_mentah(bayar, HALAMAN + "/order" + query, akun)[:2] == acuan[:2]
    assert dibaca == []


@pytest.mark.parametrize("query", [
    "", "?id=", "?id=sembarang", "?id=ord_123", "?id=ord_" + "0" * 31, "?id=ord_" + "0" * 33,
    "?id=ord_" + "A" * 32, "?id=ord_" + "g" * 32, "?id=ORD_" + "0" * 32, "?order=ord_" + "0" * 32,
    "?id=ord_" + "0" * 32 + "&x=1", "?id=ord_" + "0" * 32 + "&id=ord_" + "1" * 32,
    "?id=ord_" + "0" * 32 + "&hasil=sembarang", "?id=ord_" + "0" * 32 + "&hasil=verifikasi_setuju",
    "?id=ord_" + "0" * 32 + "%00", "?id=%27%20OR%201=1--",
])
def test_detail_query_tak_sah_404_identik_rute_tak_dikenal(bayar, admin, query):
    order_bayar(bayar)
    acuan = minta_admin(bayar, TAK_ADA, admin)
    kode, isi, _t = minta_admin(bayar, HALAMAN + "/order" + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404


def test_detail_order_tak_ada_404_identik_dan_tanpa_efek(bayar, admin):
    order_bayar(bayar)
    sebelum = _stempel(bayar)
    acuan = minta_admin(bayar, TAK_ADA, admin)
    kode, isi, _t = minta_admin(bayar, alamat_detail(ORDER_ASING), admin)
    assert (kode, isi) == acuan[:2] and kode == 404
    assert _stempel(bayar) == sebelum


def test_detail_skema_pesanan_belum_dipasang_kartu_jujur_503_tanpa_aksi(keluarga):
    kode, isi, _t = minta_admin(keluarga, alamat_detail("ord_" + "a" * 32), login_admin(keluarga))
    assert kode == 503 and "belum siap" in isi.lower() and form_order(isi) == {}
    assert "Traceback" not in isi and "sqlite" not in isi.lower()


def test_detail_sesi_basic_baca_saja_tanpa_form_dan_tanpa_sandi(bayar, admin):
    belum, _trx = order_bayar(bayar)
    for order_id in (belum["order_id"],):
        kode, isi, _t = minta_mentah(bayar, alamat_detail(order_id), AKUN_ADMIN)
        assert kode == 200 and "Tampilan baca-saja" in isi
        assert form_order(isi) == {} and 'type="password"' not in markup(isi) and 'name="reauth"' not in markup(isi)


def test_detail_sesi_basic_lunas_baca_saja_tanpa_form_refund(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    kode, isi, _t = minta_mentah(bayar, alamat_detail(order["order_id"]), AKUN_ADMIN)
    assert kode == 200 and "Tampilan baca-saja" in isi and dui.COPY_RINGKAS_REFUND in isi
    assert dui.COPY_KEBIJAKAN_REFUND in isi
    assert form_order(isi) == {} and 'type="password"' not in markup(isi)


# --- C4: periksa status ---------------------------------------------------------------

def test_periksa_form_ada_di_details_bila_gerbang_terbuka_dan_belum_bayar(bayar, admin):
    order, _trx = order_bayar(bayar)
    isi = _detail(bayar, admin, order["order_id"])
    assert "<details" in isi and dui.COPY_RINGKAS_PERIKSA in isi
    form = form_order(isi)
    assert set(form) == {PERIKSA} and set(form[PERIKSA]) == {"csrf", "tinjauan"}
    assert 'action="/admin/pesanan/periksa"' in isi and 'name="reauth"' in markup(isi)
    assert REFUND not in form


def test_periksa_gerbang_tertutup_penjelasan_tanpa_form(bayar, admin):
    order, _trx = order_bayar(bayar)
    atur_tahap("rekonsiliasi")
    isi = _detail(bayar, admin, order["order_id"])
    assert dui.COPY_PERIKSA_GERBANG in isi and form_order(isi) == {}
    assert 'type="password"' not in markup(isi)


def test_periksa_order_lunas_penjelasan_tidak_perlu_dan_tanpa_form_periksa(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    isi = _detail(bayar, admin, order["order_id"])
    assert dui.COPY_PERIKSA_TIDAK_PERLU in isi and PERIKSA not in form_order(isi)


def test_periksa_dari_detail_303_ke_detail_dengan_hasil_dan_banner(bayar, admin):
    from pesanan_http_kit import settlement
    order, trx = order_bayar(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    kode, isi, tajuk = kirim_dari_detail(bayar, admin, PERIKSA, order["order_id"])
    assert (kode, isi) == (303, "")
    assert tajuk["Location"] == "/admin/pesanan/order?id=%s&hasil=periksa_ok" % order["order_id"]
    sesudah = minta_admin(bayar, tajuk["Location"], admin)[1]
    assert "Pemeriksaan selesai" in sesudah and "Dibayar" in sesudah and "Pembayaran dikonfirmasi penyedia" in sesudah


@pytest.mark.parametrize("ganti,hapus", [
    ({"reauth": "sandi-salah"}, ()),
    ({"reauth": ""}, ()),
    (None, ("reauth",)),
    ({"csrf": "rusak"}, ()),
    (None, ("csrf",)),
    (None, ("tinjauan",)),
    ({"tinjauan": "bukan.token"}, ()),
])
def test_periksa_dari_detail_tanpa_syarat_guard_403_tanpa_efek(bayar, admin, ganti, hapus):
    order, _trx = order_bayar(bayar)
    sebelum = _stempel(bayar)
    kode, isi, _t = kirim_dari_detail(bayar, admin, PERIKSA, order["order_id"], ganti=ganti, hapus=hapus)
    assert kode == 403 and "Traceback" not in isi
    assert _stempel(bayar) == sebelum


# --- C5: catat uang kembali -----------------------------------------------------------

def test_refund_ada_dalam_details_tertutup_dengan_copy_keputusan_18_dan_konfirmasi(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    isi = _detail(bayar, admin, order["order_id"])
    bagian = isi.split(dui.COPY_RINGKAS_REFUND)[0].rsplit("<details", 1)[1]
    assert "open" not in bagian                                  # tertutup
    assert dui.COPY_KEBIJAKAN_REFUND in isi
    assert "Peta Kemampuan tidak ada uang kembali" in isi and "dana dikembalikan manual lewat rekening" in isi
    form = re.search(r'<form method="post" action="/admin/pesanan/refund" data-konfirmasi="([^"]+)">', isi)
    assert form and "tidak dapat dibatalkan" in form.group(1)
    assert 'class="admin-tombol admin-bahaya-garis"' in isi and dui.COPY_TOMBOL_REFUND in isi
    assert 'name="reauth"' in markup(isi) and set(form_order(isi)) == {REFUND}


def test_refund_select_default_laporan_terlambat_dan_enum_server_utuh(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    isi = _detail(bayar, admin, order["order_id"])
    opsi = re.findall(r'<option value="([^"]+)">([^<]+)</option>', re.search(r"<select.*?</select>", isi, re.S).group(0))
    assert [v for v, _l in opsi] == list(dui.URUTAN_ALASAN_REFUND)
    assert set(v for v, _l in opsi) == set(CATATAN_REFUND)
    assert opsi[0] == ("kebijakan", "Laporan terlambat (pengecualian kebijakan)")
    assert "selected" not in isi.split("<select")[1].split("</select>")[0]  # bawaan = opsi pertama


def test_refund_dari_form_detail_default_dicatat_sebagai_kebijakan_lalu_redirect_ke_detail(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    panggilan = jumlah_panggilan(bayar)
    kode, isi, tajuk = kirim_dari_detail(bayar, admin, REFUND, order["order_id"], ganti={"catatan_kode": "kebijakan"})
    assert (kode, isi) == (303, "") and hasil_dari(tajuk, order["order_id"]) == "refund_dicatat"
    (baris,) = baris_refund()
    assert (baris["order_id"], baris["dicatat_oleh"], baris["catatan_kode"]) == (
        order["order_id"], id_admin(), "kebijakan")
    assert jumlah_panggilan(bayar) == panggilan
    sesudah = minta_admin(bayar, tajuk["Location"], admin)[1]
    assert "Catatan refund tersimpan" in sesudah and "Direfund" in sesudah and "Uang kembali dicatat" in sesudah
    assert REFUND not in form_order(sesudah)                    # sudah direfund: tidak ada form lagi


@pytest.mark.parametrize("kode_alasan", CATATAN_REFUND)
def test_refund_dari_detail_menerima_setiap_enum_server(bayar, admin, kode_alasan):
    order, _trx = order_lunas(bayar, admin)
    assert kirim_dari_detail(bayar, admin, REFUND, order["order_id"], ganti={"catatan_kode": kode_alasan})[0] == 303
    assert baris_refund()[0]["catatan_kode"] == kode_alasan


def test_refund_tetap_ada_di_detail_saat_gerbang_tertutup(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    atur_tahap("nonaktif")
    isi = _detail(bayar, admin, order["order_id"])
    assert REFUND in form_order(isi) and dui.COPY_PERIKSA_TIDAK_PERLU in isi


def test_refund_tidak_ditawarkan_untuk_order_belum_bayar(bayar, admin):
    order, _trx = order_bayar(bayar)
    isi = _detail(bayar, admin, order["order_id"])
    assert dui.COPY_RINGKAS_REFUND not in isi and REFUND not in form_order(isi)


@pytest.mark.parametrize("ganti,hapus", [
    ({"reauth": "sandi-salah"}, ()),
    ({"reauth": ""}, ()),
    (None, ("reauth",)),
    ({"csrf": "rusak"}, ()),
    (None, ("csrf",)),
    (None, ("tinjauan",)),
])
def test_refund_dari_detail_tanpa_syarat_guard_403_tanpa_catatan(bayar, admin, ganti, hapus):
    order, _trx = order_lunas(bayar, admin)
    sebelum = _stempel(bayar)
    kode, isi, _t = kirim_dari_detail(bayar, admin, REFUND, order["order_id"], ganti=ganti, hapus=hapus)
    assert kode == 403 and "Traceback" not in isi
    assert _stempel(bayar) == sebelum and baris_refund() == []


def test_refund_ganda_beda_isi_409_catatan_pertama_tetap(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    form = form_order(_detail(bayar, admin, order["order_id"]))[REFUND]      # halaman dibuka sekali, dikirim dua kali
    kirim = lambda kode_alasan: minta_admin(bayar, REFUND, admin, {  # noqa: E731
        **form, "reauth": SANDI_ADMIN, "catatan_kode": kode_alasan})
    assert kirim("kebijakan")[0] == 303
    kode, isi, _t = kirim("lainnya")
    assert kode == 409 and "Traceback" not in isi
    (baris,) = baris_refund()
    assert baris["catatan_kode"] == "kebijakan"


def test_refund_ulang_isi_sama_idempoten_303_sudah_ada(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    data = {**token_langsung(admin, ap.AKSI_REFUND, order["order_id"]), "catatan_kode": "kebijakan"}
    assert hasil_dari(minta_admin(bayar, REFUND, admin, data)[2], order["order_id"]) == "refund_dicatat"
    kode, _i, tajuk = minta_admin(bayar, REFUND, admin, data)
    assert (kode, hasil_dari(tajuk, order["order_id"])) == (303, "refund_sudah_ada")
    assert len(baris_refund()) == 1


def test_refund_status_tak_layak_belum_bayar_409_tanpa_catatan(bayar, admin):
    order, _trx = order_bayar(bayar)
    sebelum = _stempel(bayar)
    data = {**token_langsung(admin, ap.AKSI_REFUND, order["order_id"]), "catatan_kode": "kebijakan"}
    kode, isi, _t = minta_admin(bayar, REFUND, admin, data)
    assert kode == 409 and "receipt" not in isi.lower()
    assert _stempel(bayar) == sebelum


def test_refund_order_tak_ada_404_identik(bayar, admin):
    order_lunas(bayar, admin)
    acuan = minta_admin(bayar, TAK_ADA, admin, {"x": "1"})
    data = {**token_langsung(admin, ap.AKSI_REFUND, ORDER_ASING), "catatan_kode": "kebijakan"}
    kode, isi, _t = minta_admin(bayar, REFUND, admin, data)
    assert (kode, isi) == acuan[:2] and kode == 404


def test_refund_transfer_lunas_dari_detail_dicatat_ke_transfer_refund(transfer):
    admin = login_admin(transfer)
    order_id = _lunas_transfer(transfer, admin)
    isi = _detail(transfer, admin, order_id)
    assert REFUND in form_order(isi) and "Transfer disetujui" in isi
    kode, _i, tajuk = kirim_dari_detail(transfer, admin, REFUND, order_id, ganti={"catatan_kode": "kebijakan"})
    assert (kode, hasil_dari(tajuk, order_id)) == (303, "refund_dicatat")
    sesudah = minta_admin(transfer, tajuk["Location"], admin)[1]
    assert "Direfund" in sesudah and "Uang kembali dicatat" in sesudah


# --- tinjauan: terikat aksi, sesi, dan order ---------------------------------------------

def test_tinjauan_dari_detail_tidak_berlaku_untuk_order_lain_karena_target_ada_di_tanda_tangan(bayar, admin):
    satu, _ = order_lunas(bayar, admin)
    isi = _detail(bayar, admin, satu["order_id"])
    data = {**form_order(isi)[REFUND], "reauth": SANDI_ADMIN, "catatan_kode": "kebijakan", "order_id": ORDER_ASING}
    assert minta_admin(bayar, REFUND, admin, data)[0] == 400          # field order_id asing ditolak
    assert baris_refund() == []
    data.pop("order_id")
    kode, _i, tajuk = minta_admin(bayar, REFUND, admin, data)
    assert (kode, hasil_dari(tajuk, satu["order_id"])) == (303, "refund_dicatat")


def test_tinjauan_periksa_dari_detail_ditolak_di_rute_refund(bayar, admin):
    order, _trx = order_bayar(bayar)
    form = form_order(_detail(bayar, admin, order["order_id"]))[PERIKSA]
    data = {**form, "reauth": SANDI_ADMIN, "catatan_kode": "kebijakan"}
    assert minta_admin(bayar, REFUND, admin, data)[0] == 403
    assert baris_refund() == []


# --- daftar: saringan, rekening, tanpa form -------------------------------------------------

def test_daftar_tanpa_type_password_dan_tanpa_form_tindakan(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    isi = minta_admin(bayar, HALAMAN, admin)[1]
    assert order["order_id"] in isi
    assert 'type="password"' not in markup(isi) and 'name="reauth"' not in markup(isi)
    assert form_order(isi) == {} and 'action="/admin/pesanan/' not in isi
    assert "Detail" in isi and 'href="/admin/pesanan/order?id=%s"' % order["order_id"] in isi


@pytest.mark.parametrize("status", ["menunggu", "belum_bayar", "dibayar", "ditolak"])
def test_daftar_saringan_baru_200_dan_chip_aktif(bayar, admin, status):
    order_bayar(bayar)
    kode, isi, _t = minta_admin(bayar, "%s?status=%s" % (HALAMAN, status), admin)
    assert kode == 200
    assert re.search(r'<a class="admin-chip" aria-current="true" href="/admin/pesanan\?status=%s">' % status, isi)


@pytest.mark.parametrize("query", ["?status=sembarang", "?status=semua", "?status=MENUNGGU", "?status=dibayar%20",
                                   "?status=dibayar&status=ditolak", "?status=lunas", "?status=%27--"])
def test_daftar_saringan_asing_404_identik(bayar, admin, query):
    acuan = minta_admin(bayar, TAK_ADA, admin)
    kode, isi, _t = minta_admin(bayar, HALAMAN + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404


def test_daftar_saringan_memilah_order_menurut_status(bayar, admin):
    order, _trx = order_bayar(bayar)
    belum = minta_admin(bayar, HALAMAN + "?status=belum_bayar", admin)[1]
    assert order["order_id"] in belum
    for status in ("menunggu", "dibayar", "ditolak"):
        assert order["order_id"] not in minta_admin(bayar, "%s?status=%s" % (HALAMAN, status), admin)[1]
    assert order["order_id"] in minta_admin(bayar, HALAMAN, admin)[1]


def test_daftar_hitungan_chip_dari_data_yang_sama(bayar, admin):
    order_bayar(bayar)
    isi = minta_admin(bayar, HALAMAN, admin)[1]
    angka = dict((m[0], int(m[1])) for m in re.findall(
        r'href="/admin/pesanan(?:\?status=([a-z_]+))?">[^<]+<span class="admin-cnt">(\d+)</span>', isi))
    assert angka == {"menunggu": 0, "belum_bayar": 1, "dibayar": 0, "ditolak": 0, "": 1}


def test_daftar_strip_rekening_dan_gerbang_satu_baris_dengan_tautan_pengaturan(transfer):
    admin = login_admin(transfer)
    isi = minta_admin(transfer, HALAMAN, admin)[1]
    assert "Rekening transfer terisi" in isi and "Pembayaran ditutup" in isi
    assert 'href="/admin/sakelar#rekening"' in isi


def test_daftar_strip_rekening_kosong_jujur(bayar, admin):
    isi = minta_admin(bayar, HALAMAN, admin)[1]
    assert "Rekening transfer belum diisi" in isi and "1234567890" not in isi


def test_daftar_tanpa_kotak_cari(bayar, admin):
    isi = minta_admin(bayar, HALAMAN, admin)[1]
    assert 'type="search"' not in isi and 'name="cari"' not in isi and 'name="q"' not in isi


def test_dua_jalur_detail_dan_daftar_menandai_cek_refund_dan_status_perlu_diperiksa(transfer, admin):
    import pesanan
    import pesanan_alur
    from pesanan_http_kit import ledger, settlement
    order_id = order_menunggu(transfer)
    assert dui.COPY_DUA_JALUR not in _detail(transfer, admin, order_id)       # satu jalur: tanpa penanda
    with ledger() as kon:
        pesanan.terapkan_hasil_provider(kon, order_id, settlement(order_id, "trx-dua-jalur-0001"),
                                        pesanan_alur._sekarang(), "op-dua-jalur-0001")
    isi = _detail(transfer, admin, order_id)
    assert dui.COPY_DUA_JALUR in isi and "Perlu diperiksa" in isi
    kode, daftar, _t = minta_admin(transfer, HALAMAN, admin)
    assert kode == 200 and dui.ui.COPY_DUA_JALUR in daftar and "Perlu diperiksa" in daftar
