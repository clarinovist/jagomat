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
PERIKSA = HALAMAN + "/periksa"
REFUND = HALAMAN + "/refund"
RUTE_AKSI = (PERIKSA, REFUND)
TAK_ADA = "/admin/tidak-ada"
ORDER_ASING = "ord_" + "0" * 32
POLA_BARIS = re.compile(r"<tr>.*?</tr>", re.S)
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


def hasil_dari(tajuk) -> str:
    """Kode `hasil` pada Location pengalihan (bukti PRG: tanpa data di URL selain kode)."""
    cocok = re.fullmatch(r"/admin/pesanan\?halaman=\d+&hasil=([a-z_]+)", lokasi(tajuk))
    assert cocok, lokasi(tajuk)
    return cocok.group(1)


def form_halaman(isi: str, order_id: str) -> dict:
    """{action: {nama: nilai}} semua form tersembunyi pada baris tabel milik order ini."""
    baris = [b for b in POLA_BARIS.findall(isi) if order_id in b]
    assert len(baris) == 1, "baris order harus tepat satu"
    return {aksi: {k: html.unescape(v) for k, v in POLA_ISIAN.findall(badan)}
            for aksi, badan in POLA_FORM.findall(baris[0])}


def token_langsung(cookie: str, aksi: str, order_id: str, halaman: int = 1) -> dict:
    """csrf + tinjauan sah untuk order tertentu tanpa lewat halaman (kasus order asing/aksi silang)."""
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie), "reauth": SANDI_ADMIN,
            "tinjauan": admin_security.buat_tinjauan(
                akun, cookie, aksi, {"target_id": order_id, "halaman": halaman})}


def kirim_aksi(server, cookie, jalur, order_id, *, ekstra=None, ganti=None, hapus=()):
    """POST aksi admin dengan token langsung; `ganti`/`hapus` mengubah field."""
    aksi = ap.AKSI_PERIKSA if jalur == PERIKSA else ap.AKSI_REFUND
    data = token_langsung(cookie, aksi, order_id)
    if jalur == REFUND:
        data["catatan_kode"] = "permintaan_pembeli"
    data.update(ekstra or {})
    data.update(ganti or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return minta_admin(server, jalur, cookie, data)


def kirim_dari_halaman(server, cookie, jalur, order_id, *, ekstra=None):
    """POST dengan form persis seperti yang dirender halaman daftar (E2E)."""
    kode, isi, _t = minta_admin(server, HALAMAN, cookie)
    assert kode == 200
    data = dict(form_halaman(isi, order_id)[jalur])
    data["reauth"] = SANDI_ADMIN
    if jalur == REFUND:
        data["catatan_kode"] = "permintaan_pembeli"
    data.update(ekstra or {})
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
    kode, _i, tajuk = kirim_dari_halaman(bayar, cookie, PERIKSA, order["order_id"])
    assert (kode, hasil_dari(tajuk)) == (303, "periksa_ok")
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
