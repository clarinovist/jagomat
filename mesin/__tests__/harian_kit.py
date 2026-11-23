"""Pembantu tes HTTP langganan Latihan Harian (F5): server loopback, rekening dan jam SINTETIS.

Server dari `cek_http_kit` (guru, guru-b, admin pengelola-cek); sakelar LATIHAN_HARIAN dinyalakan fixture `hidup`.
Murid = akun murid bertaut ke siswa sintetis (Basic auth). Tanpa jaringan, tanpa data asli.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import auth  # noqa: E402
import harian_langganan_berkas  # noqa: E402,F401
import pesanan_alur  # noqa: E402
import pesanan_dasar  # noqa: E402
import pesanan_http  # noqa: E402
import pesanan_rekening  # noqa: E402
import sessions  # noqa: E402
from bukti_kit import JPEG, PDF, PNG, bukti, tipe_konten  # noqa: E402,F401
from cek_http_kit import minta_mentah, server  # noqa: E402,F401
from cek_gratis_kit import tambah_anak  # noqa: E402
from pesanan_transfer_http_kit import ATAS_NAMA, BANK, NOMOR_LABEL, isi_rekening, minta_multipart  # noqa: E402,F401

AWAL = "2026-11-23T03:00:00"
SANDI = "sandi-murid-sintetis-123"
M = "/murid/langganan"
BUAT = M + "/buat"
BUKTI = M + "/bukti"
TABEL = ("harian_order", "harian_tagihan", "harian_bukti", "harian_verifikasi", "harian_akses")


class Jam:
    def __init__(self):
        self.nilai = AWAL

    def __call__(self):
        return self.nilai

    def maju_jam(self, jam):
        self.nilai = pesanan_dasar.tambah_jam(self.nilai, jam)


class Murid:
    def __init__(self, akun, id_akun, siswa_id):
        self.akun, self.id_akun, self.siswa_id = akun, id_akun, siswa_id


@pytest.fixture()
def jam(monkeypatch):
    waktu = Jam()
    monkeypatch.setattr(pesanan_alur, "_sekarang", waktu)
    return waktu


@pytest.fixture()
def mati(server, monkeypatch, tmp_path, jam):
    """Server dengan sakelar LATIHAN_HARIAN MATI (bawaan)."""
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.delenv("LATIHAN_HARIAN", raising=False)
    monkeypatch.setenv("OSN_DIREKTORI_BUKTI", str(tmp_path / "bukti-uji"))
    monkeypatch.setattr(pesanan_http, "_laju", {})
    server.folder = tmp_path / "bukti-uji"
    return server


@pytest.fixture()
def hidup(mati, monkeypatch):
    """Sakelar hidup + rekening terisi."""
    monkeypatch.setenv("LATIHAN_HARIAN", "1")
    pasang_rekening()
    return mati


def pasang_rekening():
    pesanan_rekening.migrasikan(admin_store.BAWAAN, sekarang=10)
    isi_rekening(admin_store.BAWAAN)


def buat_murid(server, nama, nama_anak, *, tertaut=True) -> Murid:
    siswa = None
    if tertaut:
        with server.buka() as kon:
            siswa = tambah_anak(kon, nama_anak, "koordinator-sintetis", 4)
    principal = auth.tambah_akun_dan_principal(nama, SANDI, "murid", siswa_id=siswa)
    return Murid((nama, SANDI), principal.id_akun, siswa)


def token(akun, aksi, sesi=None):
    principal = sessions.principal_basic(*akun)
    assert principal is not None
    return pesanan_http.buat_token(principal, sesi, aksi)


def kirim(server, jalur, murid, data):
    return minta_mentah(server, jalur, murid.akun, data)


def buat(server, murid, paket="bulanan", *, ekstra=None, hapus=(), tok=None, aksi=None):
    data = {"token": token(murid.akun, aksi or "harian_buat:" + paket) if tok is None else tok, "paket": paket}
    data.update(ekstra or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return kirim(server, BUAT, murid, data)


def unggah(server, murid, isi=JPEG, *, tok=None, **opsi):
    tok = token(murid.akun, "harian_bukti") if tok is None else tok
    return minta_multipart(server, BUKTI, murid.akun, bukti(tok, isi, **opsi))


def halaman(server, murid):
    kode, isi, _ = minta_mentah(server, M, murid.akun)
    assert kode == 200, kode
    return isi


def hitung(server) -> dict:
    with server.buka() as kon:
        return {t: kon.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in TABEL}


KOSONG = {t: 0 for t in TABEL}


def berkas_harian(server):
    folder = Path(server.folder) / harian_langganan_berkas.SUBFOLDER
    return sorted(p.name for p in folder.glob("*")) if folder.exists() else []


def semua_berkas(server):
    return sorted(str(p.relative_to(server.folder)) for p in Path(server.folder).rglob("*") if p.is_file()) \
        if Path(server.folder).exists() else []


def satu_order(server) -> dict:
    with server.buka() as kon:
        return dict(kon.execute("SELECT o.*,t.kode_unik,t.nominal_transfer FROM harian_order o "
                                "JOIN harian_tagihan t ON t.order_id=o.id").fetchone())
