"""Refund lewat HTTP: status turunan ditegakkan di SERVER walau token (csrf, tinjauan, sandi ulang) sah.

Tombol refund hanya tampil untuk `sudah_dibayar`/`perlu_diperiksa`, tetapi POST dengan token langsung
(tanpa lewat halaman) tidak boleh menembus. Efek (ketiadaannya) dibuktikan dari seluruh ledger.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pesanan_http as ap  # noqa: E402
from admin_pesanan_kit import (  # noqa: E402
    REFUND, baris_refund, hasil_dari, login_admin, minta_admin, order_bayar, order_lunas, token_langsung,
)
from admin_transfer_kit import SETUJUI, TOLAK, kirim_putusan, order_menunggu, tabel  # noqa: E402
from pesanan_http_kit import (  # noqa: E402,F401  (fixture)
    bayar, jam, keadaan_ledger, keluarga, server, tertutup,
)
from pesanan_transfer_http_kit import transfer  # noqa: E402,F401


def _stempel():
    """Seluruh ledger pesanan + catatan refund kedua tabel (transfer_refund kosong bila belum dimigrasikan)."""
    try:
        transfer_refund = tabel("transfer_refund")
    except sqlite3.OperationalError:
        transfer_refund = []
    return keadaan_ledger(), baris_refund(), transfer_refund


def _refund_langsung(server, admin, order_id, catatan="kebijakan"):
    data = {**token_langsung(admin, ap.AKSI_REFUND, order_id), "catatan_kode": catatan}
    return minta_admin(server, REFUND, admin, data)


def _siapkan(nama, peladen, jam):
    """(admin, order_id) untuk satu status non-refundable (token tetap sah)."""
    admin = login_admin(peladen)
    if nama in ("belum_bayar", "kedaluwarsa"):
        order, _ = order_bayar(peladen)
        if nama == "kedaluwarsa":
            jam.maju_jam(25)
        return admin, order["order_id"]
    order_id = order_menunggu(peladen)
    if nama == "ditolak":
        assert kirim_putusan(peladen, admin, TOLAK, order_id)[0] == 303
    return admin, order_id


@pytest.mark.parametrize("nama", ["belum_bayar", "kedaluwarsa", "menunggu_verifikasi", "ditolak"])
def test_refund_status_tak_layak_409_tanpa_efek_walau_token_sah(nama, request, jam):
    peladen = request.getfixturevalue("transfer" if nama in ("menunggu_verifikasi", "ditolak") else "bayar")
    admin, order_id = _siapkan(nama, peladen, jam)
    sebelum = _stempel()
    kode, isi, _t = _refund_langsung(peladen, admin, order_id)
    assert kode == 409 and "Traceback" not in isi
    assert _stempel() == sebelum


def test_refund_order_direfund_isi_beda_409_dan_replay_identik_tanpa_baris_baru(bayar):
    admin = login_admin(bayar)
    order, _ = order_lunas(bayar, admin)
    kode, _i, tajuk = _refund_langsung(bayar, admin, order["order_id"], "kebijakan")
    assert (kode, hasil_dari(tajuk, order["order_id"])) == (303, "refund_dicatat")
    sesudah = _stempel()
    assert _refund_langsung(bayar, admin, order["order_id"], "lainnya")[0] == 409
    kode, _i, tajuk = _refund_langsung(bayar, admin, order["order_id"], "kebijakan")
    assert (kode, hasil_dari(tajuk, order["order_id"])) == (303, "refund_sudah_ada")
    assert _stempel() == sesudah


def test_refund_transfer_lunas_tetap_sukses_dan_replay_idempoten(transfer):
    admin = login_admin(transfer)
    order_id = order_menunggu(transfer)
    assert kirim_putusan(transfer, admin, SETUJUI, order_id)[0] == 303
    assert hasil_dari(_refund_langsung(transfer, admin, order_id)[2], order_id) == "refund_dicatat"
    assert hasil_dari(_refund_langsung(transfer, admin, order_id)[2], order_id) == "refund_sudah_ada"
    assert len(tabel("transfer_refund")) == 1 and baris_refund() == []
