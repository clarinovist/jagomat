"""Akses rute admin transfer baru (anonim/guru/murid 404 identik tanpa membaca ledger) dan tanpa penanda DRAF.

Data sintetis; fixture `transfer` dari kit. Tidak satu pun rute admin baru boleh dijawab untuk non-admin
selain 404 yang sama dengan rute admin tak dikenal, sebelum DB disentuh.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pesanan_http as ap  # noqa: E402
import admin_rekening_http  # noqa: E402
import bukti_berkas  # noqa: E402
import pesanan_transfer  # noqa: E402
from admin_transfer_kit import (  # noqa: E402
    AKSI_REKENING, AKSI_SETUJUI, AKSI_TOLAK, BUKTI, HALAMAN, REKENING, SETUJUI, TAK_ADA, TOLAK, VERIFIKASI,
    id_bukti_terakhir, kirim_putusan, login_admin, minta_admin, minta_biner, order_menunggu, token_putusan,
    token_rekening, isian_rekening, stempel_putusan,
)
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_transfer_http_kit import (  # noqa: E402
    AKUN_A, STATUS, bayar, jam, keluarga, kirim_bukti, minta_mentah, server, tertutup, transfer,
)

AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)
RUTE_GET = (HALAMAN + "?status=menunggu", VERIFIKASI + "?order=ord_" + "0" * 32, BUKTI + "?id=1", REKENING)
RUTE_POST = (SETUJUI, TOLAK, REKENING)


@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_nonadmin_404_identik_rute_tak_dikenal_tanpa_membaca_ledger_atau_berkas(transfer, akun, monkeypatch):
    admin = login_admin(transfer)
    order_id = order_menunggu(transfer)
    bukti_id = id_bukti_terakhir(order_id)
    sebelum = stempel_putusan()
    dibaca = []

    def gagal(*_a, **_k):
        dibaca.append(1)
        raise sqlite3.OperationalError("tidak boleh dibaca")

    with monkeypatch.context() as ctx:
        ctx.setattr(ap.pesanan, "buka", gagal)
        ctx.setattr(pesanan_transfer, "buka", gagal)
        ctx.setattr(admin_rekening_http.pesanan_rekening, "baca", gagal)
        ctx.setattr(bukti_berkas, "buka_berkas", gagal)
        acuan_get = minta_mentah(transfer, TAK_ADA, akun)
        acuan_post = minta_mentah(transfer, TAK_ADA, akun, {"x": "1"})
        assert acuan_get[0] == acuan_post[0] == 404
        for jalur in (HALAMAN + "?status=menunggu", "%s?order=%s" % (VERIFIKASI, order_id),
                      "%s?id=%d" % (BUKTI, bukti_id), REKENING):
            assert minta_mentah(transfer, jalur, akun)[:2] == acuan_get[:2]
        data = {**token_putusan(admin, AKSI_SETUJUI, order_id, bukti_id), "alasan": "x"}
        for jalur in (SETUJUI, TOLAK):
            assert minta_mentah(transfer, jalur, akun, data)[:2] == acuan_post[:2]
            assert minta_mentah(transfer, jalur, akun, {})[:2] == acuan_post[:2]
        form = {**token_rekening(admin, 1, "a" * 64), **isian_rekening()}
        assert minta_mentah(transfer, REKENING, akun, form)[:2] == acuan_post[:2]
    assert dibaca == []
    assert stempel_putusan() == sebelum


def test_rute_admin_baru_tidak_bergantung_pada_gerbang_transfer(transfer, monkeypatch):
    """Rekening, verifikasi, dan pratinjau tetap bisa diakses admin walau sakelar transfer mati."""
    admin = login_admin(transfer)
    order_id = order_menunggu(transfer)
    monkeypatch.delenv("PESANAN_TRANSFER_AKTIF")
    assert minta_admin(transfer, REKENING, admin)[0] == 200
    assert minta_admin(transfer, "%s?order=%s" % (VERIFIKASI, order_id), admin)[0] == 200
    assert minta_biner(transfer, "%s?id=%d" % (BUKTI, id_bukti_terakhir(order_id)), admin)[0] == 200
    assert kirim_putusan(transfer, admin, SETUJUI, order_id)[0] == 303


# --- tanpa penanda DRAF di HTML yang tampil -------------------------------------------------------

def _tanpa_draf(isi: str, konteks: str) -> None:
    assert "draf" not in isi.lower(), konteks


def test_halaman_guru_jalur_transfer_tanpa_penanda_draf_di_semua_status(transfer, jam):
    from admin_transfer_kit import TOLAK as _T
    from pesanan_transfer_http_kit import kirim_tagihan, siap_order
    siap_order(transfer)
    _tanpa_draf(minta_mentah(transfer, STATUS, AKUN_A)[1], "belum ada tagihan")
    assert kirim_tagihan(transfer)[0] == 303
    _tanpa_draf(minta_mentah(transfer, STATUS, AKUN_A)[1], "tagihan")
    assert kirim_bukti(transfer, b"\xff\xd8\xff\xe0" + b"\x00" * 32)[0] == 303
    _tanpa_draf(minta_mentah(transfer, STATUS, AKUN_A)[1], "menunggu")
    admin = login_admin(transfer)
    order_id = order_menunggu_sudah_ada()
    assert kirim_putusan(transfer, admin, _T, order_id, ganti={"alasan": "Nominal kurang"})[0] == 303
    _tanpa_draf(minta_mentah(transfer, STATUS, AKUN_A)[1], "ditolak")
    jam.maju_jam(25)
    _tanpa_draf(minta_mentah(transfer, STATUS, AKUN_A)[1], "kedaluwarsa + ulang")


def order_menunggu_sudah_ada() -> str:
    from pesanan_transfer_http_kit import ledger
    with ledger() as kon:
        return kon.execute("SELECT order_id FROM pesanan_order").fetchone()[0]


def test_halaman_info_dan_galat_guru_tanpa_penanda_draf(transfer):
    from pesanan_transfer_http_kit import TAGIHAN, siap_order
    siap_order(transfer)
    for isi in (minta_mentah(transfer, STATUS, AKUN_A)[1],
                minta_mentah(transfer, TAGIHAN, AKUN_A, {"token": "rusak"})[1],
                minta_mentah(transfer, "/pesanan/bukti", AKUN_A, {"token": "rusak"})[1]):
        _tanpa_draf(isi, "halaman guru/galat")


def test_halaman_admin_baru_tanpa_penanda_draf(transfer):
    admin = login_admin(transfer)
    order_id = order_menunggu(transfer)
    bukti_id = id_bukti_terakhir(order_id)
    for jalur in (HALAMAN, HALAMAN + "?status=menunggu", HALAMAN + "?hasil=verifikasi_setuju",
                  "%s?order=%s" % (VERIFIKASI, order_id), REKENING, REKENING + "?hasil=tersimpan",
                  "%s?id=999" % BUKTI):
        _tanpa_draf(minta_admin(transfer, jalur, admin)[1], jalur)
    for ganti in ({"alasan": ""},):
        _tanpa_draf(kirim_putusan(transfer, admin, TOLAK, order_id, ganti=ganti)[1], "galat tolak")
    _tanpa_draf(kirim_putusan(transfer, admin, SETUJUI, order_id, bukti_id=bukti_id + 99)[1], "galat setujui")
    assert kirim_putusan(transfer, admin, SETUJUI, order_id)[0] == 303
    _tanpa_draf(kirim_putusan(transfer, admin, SETUJUI, order_id)[1], "galat setujui dua kali")


def test_sumber_jalur_transfer_tidak_memuat_penanda_draf_komentar():
    mesin = Path(__file__).resolve().parent.parent
    for nama in ("pesanan_transfer_pages.py", "pesanan_transfer_tampil.py", "pesanan_pages.py",
                 "admin_pesanan_pages.py", "admin_verifikasi_pages.py", "admin_rekening_pages.py",
                 "pesanan_transfer_http.py", "admin_verifikasi_http.py", "admin_rekening_http.py"):
        assert not re.search(r"\bDRAF\b|menunggu persetujuan Pemilik", (mesin / nama).read_text("utf-8")), nama
