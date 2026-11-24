"""Pembantu tes HTTP aksi admin purna (voucher dipakai, laporan terbit): fixture DB, order lunas, potret efek.

Data sintetis; server, provider, dan jam palsu dari `pesanan_http_kit`. Fixture `bayar_purna` (QRIS) dan
`transfer_purna` (transfer rekening) memigrasikan `transfer_*` dan `purna_*` pada DB admin sintetis; `bayar` polos
tidak punya keduanya (skema purna belum dipasang).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import purna  # noqa: E402
import schema_purna  # noqa: E402
import schema_transfer  # noqa: E402
from admin_pesanan_kit import login_admin, order_lunas  # noqa: E402
from admin_transfer_kit import SETUJUI, kirim_putusan, order_menunggu  # noqa: E402
from pesanan_http_kit import bayar, jam, keluarga, ledger, server, tertutup  # noqa: E402,F401
from pesanan_transfer_http_kit import transfer  # noqa: E402,F401

TABEL_EFEK = schema_purna.TABEL + ("pesanan_refund", "transfer_refund")


@pytest.fixture()
def bayar_purna(bayar):
    """Gerbang QRIS terbuka; skema transfer + purna terpasang (transfer sendiri tidak dibuka)."""
    schema_transfer.migrasikan(admin_store.BAWAAN)
    schema_purna.migrasikan(admin_store.BAWAAN)
    return bayar


@pytest.fixture()
def transfer_purna(transfer):
    schema_purna.migrasikan(admin_store.BAWAAN)
    return transfer


def lunas_transfer(server, admin) -> str:
    order_id = order_menunggu(server)
    assert kirim_putusan(server, admin, SETUJUI, order_id)[0] == 303
    return order_id


@pytest.fixture(params=["qris", "transfer"])
def lunas(request):
    """(server, cookie admin, order_id) untuk order lunas di jalur QRIS lalu transfer rekening."""
    if request.param == "qris":
        server = request.getfixturevalue("bayar_purna")
        admin = login_admin(server)
        order, _trx = order_lunas(server, admin)
        return server, admin, order["order_id"]
    server = request.getfixturevalue("transfer_purna")
    admin = login_admin(server)
    return server, admin, lunas_transfer(server, admin)


def potret_efek() -> dict:
    """Seluruh baris tabel purna + kedua tabel refund (efek tulis apa pun terlihat di sini)."""
    with ledger() as kon:
        return {t: [tuple(r) for r in kon.execute("SELECT * FROM %s ORDER BY rowid" % t)] for t in TABEL_EFEK}


def kosong(potret: dict) -> bool:
    return not any(potret.values())


def pilih_uang_kembali(order_id: str, sekarang: str) -> None:
    """Pembeli memilih uang kembali (lewat domain; HTTP pembeli = V4): menyiapkan keadaan untuk tes admin."""
    with ledger() as kon:
        purna.catat_pilihan(kon, order_id, purna.PILIHAN_UANG_KEMBALI, sekarang)
