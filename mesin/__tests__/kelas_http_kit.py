"""Pembantu tes HTTP Paket Belajar 1 Bulan (kelas): server loopback, DB admin sintetis, rekening dan jam SINTETIS.

Tabel kelas_* ada di admin-control.db (bukan DB belajar). Server dari `cek_http_kit`; sakelar PAKET_BELAJAR
dinyalakan fixture `kidup`. Murid = akun murid bertaut ke siswa sintetis (Basic auth). Tanpa jaringan/data asli.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import kelas_berkas  # noqa: E402
import pesanan  # noqa: E402
import pesanan_http  # noqa: E402
import schema_kelas  # noqa: E402
import schema_pesanan  # noqa: E402
import schema_purna  # noqa: E402
import schema_transfer  # noqa: E402
from bukti_kit import JPEG, PDF, PNG, bukti, tipe_konten  # noqa: E402,F401
from cek_http_kit import minta_mentah, server  # noqa: E402,F401
from harian_kit import AWAL, SANDI, Jam, Murid, buat_murid, jam, pasang_rekening, token  # noqa: E402,F401
from pesanan_kit import buat as buat_peta, terapkan as terapkan_peta  # noqa: E402,F401
from pesanan_transfer_http_kit import minta_multipart  # noqa: E402,F401

M = "/murid/paket"
BUAT = M + "/buat"
BUKTI = M + "/bukti"
TAGIHAN = M + "/tagihan"
HAPUS = M + "/hapus"
TABEL = ("kelas_order", "kelas_tagihan", "kelas_bukti", "kelas_verifikasi", "kelas_akses", "kelas_keluarga")
KOSONG = {t: 0 for t in TABEL}
ADMIN = "admin_sintetis"


def pasang_skema(path) -> None:
    schema_pesanan.migrasikan(path)
    schema_transfer.migrasikan(path)
    schema_purna.migrasikan(path)
    schema_kelas.migrasikan(path)


@pytest.fixture()
def kmati(server, monkeypatch, tmp_path, jam):
    """Server dengan sakelar PAKET_BELAJAR MATI (bawaan); skema kelas terpasang di DB admin sintetis."""
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.delenv("PAKET_BELAJAR", raising=False)
    monkeypatch.setenv("OSN_DIREKTORI_BUKTI", str(tmp_path / "bukti-uji"))
    monkeypatch.setattr(pesanan_http, "_laju", {})
    server.folder = tmp_path / "bukti-uji"
    pasang_skema(admin_store.BAWAAN)
    return server


@pytest.fixture()
def kidup(kmati, monkeypatch):
    """Sakelar hidup + rekening terisi."""
    monkeypatch.setenv("PAKET_BELAJAR", "1")
    pasang_rekening()
    return kmati


def baca_admin(sql, args=()):
    kon = sqlite3.connect(admin_store.BAWAAN)
    kon.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in kon.execute(sql, args).fetchall()]
    finally:
        kon.close()


def hitung(server=None) -> dict:
    return {t: baca_admin("SELECT COUNT(*) AS n FROM %s" % t)[0]["n"] for t in TABEL}


def berkas_kelas(server):
    folder = Path(server.folder) / kelas_berkas.SUBFOLDER
    return sorted(p.name for p in folder.glob("*")) if folder.exists() else []


def semua_berkas(server):
    return sorted(str(p.relative_to(server.folder)) for p in Path(server.folder).rglob("*") if p.is_file()) \
        if Path(server.folder).exists() else []


def kirim(server, jalur, murid, data):
    return minta_mentah(server, jalur, murid.akun, data)


def buat(server, murid, kode="mini", *, ekstra=None, hapus=(), tok=None, aksi=None):
    data = {"token": token(murid.akun, aksi or "kelas_buat:" + kode) if tok is None else tok, "kode": kode}
    data.update(ekstra or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return kirim(server, BUAT, murid, data)


def hapus_tagihan(server, murid, kode="mini", *, tok=None, ekstra=None):
    data = {"token": token(murid.akun, "kelas_hapus:" + kode) if tok is None else tok, "kode": kode}
    data.update(ekstra or {})
    return kirim(server, HAPUS, murid, data)


def unggah(server, murid, isi=JPEG, *, kode="mini", tok=None, **opsi):
    tok = token(murid.akun, "kelas_bukti:" + kode) if tok is None else tok
    return minta_multipart(server, BUKTI + "?kode=" + kode, murid.akun, bukti(tok, isi, **opsi))


def tagihan_halaman(server, murid, kode="mini"):
    """GET halaman tagihan satu paket: (kode, isi, tajuk)."""
    return minta_mentah(server, TAGIHAN + "?kode=" + kode, murid.akun)


def hapus_halaman(server, murid, kode="mini"):
    """GET halaman konfirmasi hapus satu paket: (kode, isi, tajuk)."""
    return minta_mentah(server, HAPUS + "?kode=" + kode, murid.akun)


def pasang_catatan() -> None:
    """Migrasi tabel catatan tagihan (batal/pulih); tanpa ini tombol hapus tidak tampil dan POST hapus ditolak."""
    import schema_tagihan_catatan as stc
    stc.migrasikan(admin_store.BAWAAN)


def halaman(server, murid):
    kode, isi, _ = minta_mentah(server, M, murid.akun)
    assert kode == 200, kode
    return isi


def order_terakhir() -> dict:
    return baca_admin("SELECT o.*,t.kode_unik,t.total_transfer,t.nominal,t.potongan_deposit,t.potongan_diskon,"
                      "t.deposit_order_id FROM kelas_order o JOIN kelas_tagihan t ON t.order_id=o.id "
                      "ORDER BY o.dibuat DESC,o.id DESC")[0]


def bukti_terakhir(order_id: str) -> int:
    return baca_admin("SELECT MAX(id) AS n FROM kelas_bukti WHERE order_id=?", (order_id,))[0]["n"]


def peta_lunas_untuk(murid: Murid, n: int = 1) -> str:
    """Order Peta lunas atas nama akun murid ini untuk anaknya (deposit Rp49.000 aktif pada AWAL); mengembalikan id."""
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = buat_peta(kon, n, akun=murid.id_akun, siswa=murid.siswa_id)
        terapkan_peta(kon, order, n, transaction_id="trx-sintetis-%04d" % n)
    return order["order_id"]


def buat_dan_unggah(server, murid, kode="mini", isi=JPEG) -> str:
    assert buat(server, murid, kode)[0] == 303
    assert unggah(server, murid, isi, kode=kode)[0] == 303
    return order_terakhir()["id"]
