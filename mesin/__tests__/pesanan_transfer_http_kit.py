"""Pembantu tes HTTP transfer rekening (tahap 2): gerbang transfer terpisah dari Midtrans.

Memakai server/provider PALSU dari `pesanan_http_kit`. Runtime produksi palsu terpasang
(syarat gerbang transfer), tahap pembayaran `nonaktif` (Midtrans tertutup) kecuali fixture
`dua_jalur`. Rekening, berkas bukti, dan nomor semuanya sintetis di tmp_path.
"""
from __future__ import annotations

import re
import socket
import sqlite3
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import admin_store
import pesanan_rekening
import pesanan_transfer
import schema_transfer
from bukti_kit import JPEG, PDF, PNG, bukti, tipe_konten  # noqa: F401
from http_test_kit import _basic
from pesanan_http_kit import (  # noqa: F401
    AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, BUAT, KOSONG, NAMA_A, PERIKSA, PESAN, QR, STATUS,
    ULANG, atur_tahap, bayar, jam, keadaan_ledger, keluarga, kirim, ledger, minta_mentah,
    pasang_runtime, pesan, server, siap_pesan, teks_tampak, tertutup, token,
)

TAGIHAN = "/pesanan/tagihan"
BUKTI = "/pesanan/bukti"
BANK = "Bank Contoh"
NOMOR = "1234567890"
NOMOR_LABEL = "1234 5678 90"
ATAS_NAMA = "PT Contoh Sintetis"
POLA_NOMINAL = re.compile(r"Rp49\.(\d{3})")


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def isi_rekening(path):
    """Isi rekening sintetis langsung ke tabel (jalur admin diuji di tempat lain)."""
    with sqlite3.connect(path) as kon:
        kon.execute("INSERT INTO rekening_konfigurasi(id,nama_bank,nomor_rekening,atas_nama,revisi,"
                    "diperbarui,actor_id) VALUES(1,?,?,?,1,10,'admin_sintetis')",
                    (BANK, NOMOR, ATAS_NAMA))


@pytest.fixture()
def transfer(tertutup, monkeypatch, tmp_path):
    """Hanya transfer terbuka: runtime produksi palsu ada, tahap nonaktif, rekening terisi."""
    monkeypatch.setenv("PESANAN_TRANSFER_AKTIF", "1")
    monkeypatch.setenv("OSN_DIREKTORI_BUKTI", str(tmp_path / "bukti-uji"))
    schema_transfer.migrasikan(admin_store.BAWAAN)
    pesanan_rekening.migrasikan(admin_store.BAWAAN, sekarang=10)
    isi_rekening(admin_store.BAWAAN)
    atur_tahap("nonaktif")
    pasang_runtime(tertutup, tertutup.provider)
    tertutup.folder = tmp_path / "bukti-uji"
    return tertutup


@pytest.fixture()
def dua_jalur(transfer):
    """Midtrans (tahap checkout) DAN transfer terbuka."""
    atur_tahap("checkout")
    return transfer


def minta_multipart(server, jalur, akun, tubuh: bytes, tipe=None):
    req = urllib.request.Request(server.alamat + jalur, data=tubuh, method="POST")
    req.add_header("Content-Type", tipe_konten() if tipe is None else tipe)
    if akun:
        req.add_header("Authorization", _basic(*akun))
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
        finally:
            e.close()


def kirim_bukti(server, isi, akun=AKUN_A, *, tok=None, **opsi):
    """POST multipart dengan token sah (kecuali `tok` diberikan)."""
    tok = token(akun, "bukti") if tok is None else tok
    return minta_multipart(server, BUKTI, akun, bukti(tok, isi, **opsi))


def kirim_tagihan(server, akun=AKUN_A, **kw):
    return kirim(server, TAGIHAN, akun, aksi="tagihan", **kw)


def siap_order(server, akun=AKUN_A):
    """Cek selesai + kontak + order dibuat lewat POST pesan; mengembalikan order_id."""
    siap_pesan(server, akun)
    assert pesan(server, akun)[0] == 303
    with ledger() as kon:
        return kon.execute("SELECT order_id FROM pesanan_order").fetchone()[0]


def siap_tagihan(server, akun=AKUN_A):
    siap_order(server, akun)
    assert kirim_tagihan(server, akun)[0] == 303


def hitung(tabel):
    with pesanan_transfer.buka(admin_store.BAWAAN) as kon:
        return kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]


def berkas_tersimpan(server):
    return sorted(p.name for p in Path(server.folder).glob("*")) if Path(server.folder).exists() else []


def respons_mentah(server, jalur, akun, tubuh: bytes, tipe: str) -> bytes:
    """Kirim POST lewat soket mentah dan baca SAMPAI koneksi ditutup (semua byte yang dikirim server).

    urllib berhenti membaca di Content-Length, jadi respons kedua yang menyusul tidak terlihat;
    helper ini dipakai untuk membuktikan setiap permintaan dijawab TEPAT satu kali.
    """
    host, port = server.server.server_address
    kepala = ["POST %s HTTP/1.0" % jalur, "Host: %s:%d" % (host, port),
              "Content-Type: %s" % tipe, "Content-Length: %d" % len(tubuh)]
    if akun:
        kepala.append("Authorization: %s" % _basic(*akun))
    with socket.create_connection((host, port), timeout=10) as soket:
        soket.sendall("\r\n".join(kepala).encode() + b"\r\n\r\n" + tubuh)
        potongan, hasil = True, b""
        while potongan:
            potongan = soket.recv(65536)
            hasil += potongan
    return hasil


def form_mentah(server, jalur, akun, data: dict) -> bytes:
    return respons_mentah(server, jalur, akun, urllib.parse.urlencode(data).encode(),
                          "application/x-www-form-urlencoded")


def jumlah_respons(mentah: bytes) -> int:
    """Banyaknya baris status HTTP di aliran respons (harus 1)."""
    return len(re.findall(rb"HTTP/1\.[01] \d{3} ", mentah))
