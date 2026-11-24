"""Pembantu tes panel admin pesanan (Fase 3c-4): login admin berkuki, form halaman, token langsung.

Data sintetis; provider palsu dan ledger dari `pesanan_http_kit`. Aksi admin wajib sesi berkuki
(Basic ditolak 403 oleh `_token_final`), jadi login lewat POST /masuk.
"""
from __future__ import annotations

import html
import http.cookies
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_http  # noqa: E402
import admin_pesanan_http as ap  # noqa: E402
import admin_security  # noqa: E402
import auth  # noqa: E402
import sessions  # noqa: E402
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN, id_akun, minta_mentah  # noqa: E402
from pesanan_http_kit import (  # noqa: E402
    AKUN_A, ledger, pesan, satu_order, settlement, siap_pesan,
)

HALAMAN = "/admin/pesanan"
DETAIL = HALAMAN + "/order"
PERIKSA = HALAMAN + "/periksa"
REFUND = HALAMAN + "/refund"
VOUCHER = HALAMAN + "/voucher"
TERBIT_LAMA = HALAMAN + "/terbit"  # aksi admin dihapus (D1-2): kini rute tak dikenal
RUTE_AKSI = (PERIKSA, REFUND)  # aksi lama; aksi purna (voucher) ada di RUTE_PURNA dan diuji terpisah
RUTE_PURNA = (VOUCHER,)
AKSI_RUTE = {PERIKSA: ap.AKSI_PERIKSA, REFUND: ap.AKSI_REFUND, VOUCHER: ap.AKSI_VOUCHER}
ISIAN_BAWAAN = {REFUND: {"catatan_kode": "permintaan_pembeli"}, VOUCHER: {"catatan_kode": "kelas"}}
TAK_ADA = "/admin/tidak-ada"
ORDER_ASING = "ord_" + "0" * 32
POLA_FORM = re.compile(r'<form method="post" action="([^"]+)"[^>]*>(.*?)</form>', re.S)
POLA_ISIAN = re.compile(r'<input type="hidden" name="(\w+)" value="([^"]*)"')


def login_admin(server) -> str:
    """Nilai kuki sesi admin sintetis (POST /masuk)."""
    kode, _isi, tajuk = minta_mentah(server, "/masuk", None, {"nama": AKUN_ADMIN[0], "sandi": SANDI_ADMIN})
    assert kode == 303
    return http.cookies.SimpleCookie(tajuk["Set-Cookie"])["osn_sesi"].value


def minta_admin(server, jalur, cookie, data=None):
    return minta_mentah(server, jalur, None, data, {"Cookie": "osn_sesi=" + cookie})


def lokasi(tajuk) -> str:
    return tajuk["Location"]


def alamat_detail(order_id: str, hasil: str = "") -> str:
    """URL Detail order; `hasil` opsional (kode hasil aksi untuk banner)."""
    return "%s?id=%s%s" % (DETAIL, order_id, "&hasil=" + hasil if hasil else "")


def hasil_dari(tajuk, order_id: str = "") -> str:
    """Kode `hasil` pada Location pengalihan ke Detail order (PRG: tanpa data di URL selain id order dan kode).

    Bila `order_id` diberikan, pengalihan harus menuju order itu.
    """
    cocok = re.fullmatch(r"/admin/pesanan/order\?id=(ord_[0-9a-f]{32})&hasil=([a-z_]+)", lokasi(tajuk))
    assert cocok, lokasi(tajuk)
    assert not order_id or cocok.group(1) == order_id, lokasi(tajuk)
    return cocok.group(2)


POLA_GAYA_SKRIP = re.compile(r"<(style|script)\b.*?</\1>", re.S)


def markup(isi: str) -> str:
    """Isi halaman tanpa blok <style>/<script> bingkai admin (yang menyebut `reauth`/`password` sebagai teks)."""
    return POLA_GAYA_SKRIP.sub("", isi)


def form_order(isi: str) -> dict:
    """{action: {nama: nilai}} form tindakan pesanan pada halaman (form bingkai admin seperti tema/keluar diabaikan)."""
    return {aksi: {k: html.unescape(v) for k, v in POLA_ISIAN.findall(badan)}
            for aksi, badan in POLA_FORM.findall(isi) if aksi.startswith(HALAMAN + "/")}


def token_langsung(cookie: str, aksi: str, order_id: str) -> dict:
    """csrf + tinjauan sah untuk order tertentu tanpa lewat halaman (kasus order asing/aksi silang)."""
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie), "reauth": SANDI_ADMIN,
            "tinjauan": admin_security.buat_tinjauan(
                akun, cookie, aksi, {"target_id": order_id})}


def kirim_aksi(server, cookie, jalur, order_id, *, ekstra=None, ganti=None, hapus=()):
    """POST aksi admin dengan token langsung; `ganti`/`hapus` mengubah field."""
    data = token_langsung(cookie, AKSI_RUTE[jalur], order_id)
    data.update(ISIAN_BAWAAN.get(jalur, {}))
    data.update(ekstra or {})
    data.update(ganti or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return minta_admin(server, jalur, cookie, data)


def kirim_dari_detail(server, cookie, jalur, order_id, *, ekstra=None, ganti=None, hapus=()):
    """POST dengan form persis seperti yang dirender halaman Detail order (E2E); `ganti`/`hapus` mengubah field."""
    kode, isi, _t = minta_admin(server, alamat_detail(order_id), cookie)
    assert kode == 200
    data = dict(form_order(isi)[jalur])
    data["reauth"] = SANDI_ADMIN
    data.update(ISIAN_BAWAAN.get(jalur, {}))
    data.update(ekstra or {})
    data.update(ganti or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return minta_admin(server, jalur, cookie, data)


def order_bayar(bayar):
    """Satu order milik AKUN_A, create ke provider palsu sudah terjadi (belum lunas)."""
    siap_pesan(bayar)
    assert pesan(bayar)[0] == 303
    order = satu_order()
    return order, bayar.provider.transaksi[order["order_id"]]


def order_lunas(bayar, cookie):
    """Order lunas lewat jalur nyata: provider melaporkan settlement, admin memeriksa."""
    order, trx = order_bayar(bayar)
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    kode, _i, tajuk = kirim_dari_detail(bayar, cookie, PERIKSA, order["order_id"])
    assert (kode, hasil_dari(tajuk, order["order_id"])) == (303, "periksa_ok")
    return order, trx


def baris_refund():
    with ledger() as kon:
        return [dict(r) for r in kon.execute("SELECT * FROM pesanan_refund")]


def jumlah_panggilan(server) -> int:
    return len(server.provider.panggilan)


def id_admin() -> str:
    principal = sessions.principal_basic(*AKUN_ADMIN)
    assert principal is not None
    return principal.id_akun
