"""Pembantu tes sisi admin transfer rekening: order menunggu, token putusan/rekening, pratinjau biner.

Memakai server/provider PALSU dan fixture `transfer` dari `pesanan_transfer_http_kit`. Semua data sintetis
(nomor rekening contoh fiktif, berkas bukti = header generik + pengisi).
"""
from __future__ import annotations

import html
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_http  # noqa: E402
import admin_security  # noqa: E402
import auth  # noqa: E402
from admin_pesanan_kit import (  # noqa: E402,F401
    HALAMAN, POLA_FORM, POLA_ISIAN, TAK_ADA, id_admin, login_admin, minta_admin,
)
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN  # noqa: E402
from pesanan_transfer_http_kit import (  # noqa: E402,F401
    AKUN_A, JPEG, kirim_bukti, ledger, minta_mentah, siap_tagihan,
)

VERIFIKASI = HALAMAN + "/verifikasi"
BUKTI = HALAMAN + "/bukti"
SETUJUI = HALAMAN + "/setujui"
TOLAK = HALAMAN + "/tolak"
REKENING = HALAMAN + "/rekening"
AKSI_SETUJUI = "setujui_transfer"
AKSI_TOLAK = "tolak_transfer"
AKSI_REKENING = "ubah_rekening"
NAMA_KLIEN = "rahasia-nama-asli-klien.jpg"
LINTAS_SITUS = {"Sec-Fetch-Site": "cross-site"}


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def order_menunggu(server, isi=JPEG, akun=AKUN_A) -> str:
    """Order + tagihan + satu bukti diunggah guru lewat HTTP; mengembalikan order_id."""
    siap_tagihan(server, akun)
    assert kirim_bukti(server, isi, akun, nama_berkas=NAMA_KLIEN)[0] == 303
    with ledger() as kon:
        return kon.execute("SELECT order_id FROM pesanan_order").fetchone()[0]


def id_bukti_terakhir(order_id: str) -> int:
    with ledger() as kon:
        return kon.execute("SELECT MAX(id) FROM transfer_bukti WHERE order_id=?", (order_id,)).fetchone()[0]


def tabel(nama: str):
    with ledger() as kon:
        return [dict(r) for r in kon.execute("SELECT * FROM %s ORDER BY 1" % nama)]


def stempel_putusan():
    return tabel("transfer_verifikasi"), tabel("transfer_lunas"), tabel("transfer_refund")


def token_putusan(cookie: str, aksi: str, order_id: str, bukti_id, *, csrf_cookie=None) -> dict:
    """csrf + tinjauan + reauth sah untuk keputusan atas bukti terakhir `bukti_id` (tanpa lewat halaman)."""
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, csrf_cookie or cookie), "reauth": SANDI_ADMIN,
            "tinjauan": admin_security.buat_tinjauan(
                akun, cookie, aksi, {"target_id": order_id, "target_revisi": bukti_id, "halaman": 1})}


def kirim_putusan(server, cookie, jalur, order_id, *, bukti_id=None, ekstra=None, ganti=None, hapus=(),
                  headers=None):
    """POST setujui/tolak dengan token langsung; `ganti`/`hapus` mengubah field."""
    aksi = AKSI_SETUJUI if jalur == SETUJUI else AKSI_TOLAK
    data = token_putusan(cookie, aksi, order_id,
                         id_bukti_terakhir(order_id) if bukti_id is None else bukti_id)
    if jalur == TOLAK:
        data["alasan"] = "Nominal tidak sesuai"
    data.update(ekstra or {})
    data.update(ganti or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return minta_mentah(server, jalur, None, data, {"Cookie": "osn_sesi=" + cookie, **(headers or {})})


def form_detail(isi: str) -> dict:
    """{action: {nama: nilai}} form keputusan pada halaman detail verifikasi (bukan form bingkai admin)."""
    return {aksi: {k: html.unescape(v) for k, v in POLA_ISIAN.findall(badan)}
            for aksi, badan in POLA_FORM.findall(isi) if aksi.startswith(HALAMAN + "/")}


def minta_biner(server, jalur, cookie=None, akun=None):
    """GET tanpa mengikuti pengalihan -> (kode, bytes, HTTPMessage) agar header ganda dan isi biner terlihat."""
    from http_test_kit import _basic
    req = urllib.request.Request(server.alamat + jalur)
    if cookie:
        req.add_header("Cookie", "osn_sesi=" + cookie)
    if akun:
        req.add_header("Authorization", _basic(*akun))
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(), e.headers
        finally:
            e.close()


def token_rekening(cookie: str, revisi: int, sidik: str) -> dict:
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie), "reauth": SANDI_ADMIN,
            "tinjauan": admin_security.buat_tinjauan(
                akun, cookie, AKSI_REKENING, {"revisi": revisi, "sidik": sidik})}


def isian_rekening(**ganti) -> dict:
    dasar = {"nama_bank": "Bank Contoh Baru", "nomor_rekening": "9876543210", "atas_nama": "PT Contoh Dua"}
    dasar.update(ganti)
    return dasar


def kirim_rekening(server, cookie, revisi, sidik, *, ganti=None, hapus=(), ekstra=None, headers=None):
    data = {**token_rekening(cookie, revisi, sidik), **isian_rekening(**(ganti or {})), **(ekstra or {})}
    for kunci in hapus:
        data.pop(kunci, None)
    return minta_mentah(server, REKENING, None, data, {"Cookie": "osn_sesi=" + cookie, **(headers or {})})


def teks_halaman(isi: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", isi))
