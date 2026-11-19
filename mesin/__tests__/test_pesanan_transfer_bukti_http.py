"""Unggah bukti transfer (tahap 2): multipart, magic bytes, kepemilikan, berkas atomik, rollback.

Semua penolakan dibuktikan TANPA efek: tidak ada baris `transfer_bukti` dan tidak ada berkas
di folder bukti. Isi berkas sintetis (bytes generik), rekening sintetis.
"""
from __future__ import annotations

import http.client
import os
import re
import sqlite3
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import bukti_berkas  # noqa: E402
import pesanan_transfer  # noqa: E402
import schema_transfer  # noqa: E402
from bukti_kit import JPEG, PDF, PNG, TEKS_PALSU, bagian, bukti, multipart, sha256, tipe_konten  # noqa: E402
from pesanan_transfer_http_kit import (  # noqa: E402
    AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, BUKTI, STATUS, berkas_tersimpan, hitung, jam, jumlah_respons,
    keluarga, kirim_bukti, respons_mentah,
    kirim_tagihan, ledger, minta_mentah, minta_multipart, pesan, server, siap_order, siap_pesan,
    siap_tagihan, teks_tampak, tertutup, token, transfer,
)

KATA_BOCOR = ("Traceback", "bukti-uji", "/tmp", "/private", "sqlite", ".db", "OSError")


def _tanpa_efek(server):
    assert hitung("transfer_bukti") == 0
    assert berkas_tersimpan(server) == []


def _tidak_bocor(isi):
    for kata in KATA_BOCOR:
        assert kata not in isi, kata


def _baris_bukti():
    with ledger() as kon:
        return [dict(b) for b in kon.execute("SELECT * FROM transfer_bukti ORDER BY id")]


# --- sukses ---------------------------------------------------------------------------

@pytest.mark.parametrize("isi,mime", [(JPEG, "image/jpeg"), (PNG, "image/png"), (PDF, "application/pdf")])
def test_unggah_sah_menyimpan_berkas_dan_metadata_lalu_menunggu_verifikasi(transfer, isi, mime):
    siap_tagihan(transfer)
    kode, _i, tajuk = kirim_bukti(transfer, isi)
    assert (kode, tajuk["Location"]) == (303, STATUS)
    baris = _baris_bukti()
    assert len(baris) == 1
    assert (baris[0]["mime"], baris[0]["ukuran"], baris[0]["sha256"]) == (mime, len(isi), sha256(isi))
    assert re.fullmatch(r"[0-9a-f]{32}", baris[0]["berkas"])
    assert berkas_tersimpan(transfer) == [baris[0]["berkas"]]
    tersimpan = Path(transfer.folder) / baris[0]["berkas"]
    assert tersimpan.read_bytes() == isi
    assert stat.S_IMODE(os.stat(tersimpan).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(transfer.folder).st_mode) == 0o700
    kode, halaman, _t = minta_mentah(transfer, STATUS, AKUN_A)
    assert kode == 200 and "Bukti diterima, menunggu pemeriksaan" in halaman
    assert 'action="/pesanan/bukti"' not in halaman and 'action="/pesanan/tagihan"' not in halaman
    assert transfer.provider.panggilan == []


def test_nama_berkas_klien_tidak_berpengaruh_dan_traversal_tidak_menulis_di_luar(transfer, tmp_path):
    siap_tagihan(transfer)
    kode, _i, _t = kirim_bukti(transfer, JPEG, nama_berkas="../../../../tmp/jahat.png", tipe="text/html")
    assert kode == 303
    baris = _baris_bukti()
    assert baris[0]["mime"] == "image/jpeg" and re.fullmatch(r"[0-9a-f]{32}", baris[0]["berkas"])
    assert berkas_tersimpan(transfer) == [baris[0]["berkas"]]
    assert not any(p.name.startswith("jahat") for p in tmp_path.rglob("*"))


def test_berkas_sama_diunggah_dua_kali_tidak_menggandakan_baris_maupun_berkas(transfer):
    siap_tagihan(transfer)
    assert kirim_bukti(transfer, JPEG)[0] == 303
    assert kirim_bukti(transfer, JPEG)[0] == 303
    assert hitung("transfer_bukti") == 1 and len(berkas_tersimpan(transfer)) == 1


# --- penolakan tanpa efek -----------------------------------------------------------------

def test_isi_teks_dinamai_jpg_dengan_content_type_jpeg_ditolak_415(transfer):
    siap_tagihan(transfer)
    kode, isi, _t = kirim_bukti(transfer, TEKS_PALSU, nama_berkas="bukti.jpg", tipe="image/jpeg")
    assert kode == 415 and "JPEG" in isi and "PNG" in isi and "PDF" in isi
    _tanpa_efek(transfer)
    _tidak_bocor(isi)


@pytest.mark.parametrize("isi", [b"\x89PNG", b"%PDF", b"\xff\xd8", b"MZ\x90\x00", b"<?php ?>", b"GIF89a"])
def test_magic_bytes_tidak_lengkap_atau_tipe_lain_ditolak(transfer, isi):
    siap_tagihan(transfer)
    assert kirim_bukti(transfer, isi, nama_berkas="x.png", tipe="image/png")[0] == 415
    _tanpa_efek(transfer)


def test_berkas_kosong_ditolak_400(transfer):
    siap_tagihan(transfer)
    kode, isi, _t = kirim_bukti(transfer, b"")
    assert kode == 400 and "kosong" in isi.lower()
    _tanpa_efek(transfer)


def test_berkas_satu_byte_lebih_dari_batas_ditolak_413_lewat_cek_ukuran(transfer):
    siap_tagihan(transfer)
    isi = JPEG + b"\x00" * (schema_transfer.BATAS_UKURAN_BUKTI + 1 - len(JPEG))
    assert len(isi) == schema_transfer.BATAS_UKURAN_BUKTI + 1
    kode, halaman, _t = kirim_bukti(transfer, isi)
    assert kode == 413 and "5" in halaman and "MB" in halaman
    _tanpa_efek(transfer)


def test_berkas_tepat_di_batas_diterima(transfer):
    siap_tagihan(transfer)
    isi = JPEG + b"\x00" * (schema_transfer.BATAS_UKURAN_BUKTI - len(JPEG))
    assert kirim_bukti(transfer, isi)[0] == 303
    assert _baris_bukti()[0]["ukuran"] == schema_transfer.BATAS_UKURAN_BUKTI


def test_content_length_raksasa_ditolak_sebelum_body_dibaca(transfer):
    siap_tagihan(transfer)
    from http_test_kit import _basic
    host, port = transfer.server.server_address
    sambungan = http.client.HTTPConnection(host, port, timeout=10)
    try:
        sambungan.putrequest("POST", BUKTI)
        sambungan.putheader("Authorization", _basic(*AKUN_A))
        sambungan.putheader("Content-Type", tipe_konten())
        sambungan.putheader("Content-Length", str(10 ** 10))
        sambungan.endheaders()
        jawaban = sambungan.getresponse()
        assert jawaban.status == 413
        jawaban.read()
    finally:
        sambungan.close()
    _tanpa_efek(transfer)


def test_csrf_salah_403_dan_token_aksi_lain_tidak_berlaku(transfer):
    siap_tagihan(transfer)
    for tok in ("", "1.salah", token(AKUN_A, "tagihan"), token(AKUN_A, "pesan"), token(AKUN_B, "bukti")):
        assert kirim_bukti(transfer, JPEG, tok=tok)[0] == 403
    _tanpa_efek(transfer)


def test_tanpa_token_atau_tanpa_berkas_atau_berkas_ganda_400(transfer):
    siap_tagihan(transfer)
    tok = token(AKUN_A, "bukti").encode()
    kasus = [
        multipart([bagian("berkas", JPEG, nama_berkas="a.jpg")]),
        multipart([bagian("token", tok)]),
        multipart([bagian("token", tok), bagian("berkas", JPEG, nama_berkas="a"),
                   bagian("berkas", PNG, nama_berkas="b")]),
        multipart([bagian("token", tok), bagian("berkas", JPEG, nama_berkas="a"),
                   bagian("order_id", b"ord_1")]),
    ]
    for tubuh in kasus:
        assert minta_multipart(transfer, BUKTI, AKUN_A, tubuh)[0] == 400
    _tanpa_efek(transfer)


def test_bukan_multipart_ditolak_400(transfer):
    siap_tagihan(transfer)
    kode, _i, _t = minta_mentah(transfer, BUKTI, AKUN_A, {"token": token(AKUN_A, "bukti")})
    assert kode == 400
    kode, _i, _t = minta_multipart(transfer, BUKTI, AKUN_A, b"x", tipe="multipart/form-data")
    assert kode == 400
    _tanpa_efek(transfer)


def test_order_milik_akun_lain_404_identik_tanpa_efek(transfer):
    siap_tagihan(transfer, AKUN_A)
    siap_pesan(transfer, AKUN_B)                                # B belum punya order
    acuan = minta_mentah(transfer, "/rute-tidak-ada", AKUN_B, {"x": "1"})
    kode, isi, _t = kirim_bukti(transfer, JPEG, AKUN_B)
    assert (kode, isi) == acuan[:2] and kode == 404
    _tanpa_efek(transfer)


def test_admin_404_identik_tanpa_efek(transfer):
    siap_tagihan(transfer)
    acuan = minta_mentah(transfer, "/rute-tidak-ada", AKUN_ADMIN, {"x": "1"})
    kode, isi, _t = minta_multipart(transfer, BUKTI, AKUN_ADMIN, b"x")
    assert (kode, isi) == acuan[:2] and kode == 404
    _tanpa_efek(transfer)


def test_anonim_dan_murid_ditahan_palang_sandi(transfer):
    assert minta_multipart(transfer, BUKTI, None, b"x")[0] == 401
    assert minta_multipart(transfer, BUKTI, AKUN_MURID, b"x")[0] == 401
    _tanpa_efek(transfer)


def test_tanpa_tagihan_ditolak_ramah(transfer):
    siap_order(transfer)
    kode, isi, _t = kirim_bukti(transfer, JPEG)
    assert kode == 409 and "tagihan" in isi.lower()
    _tanpa_efek(transfer)
    _tidak_bocor(isi)


def test_jendela_bayar_tutup_ditolak_ramah(transfer, jam):
    siap_tagihan(transfer)
    jam.maju_jam(25)
    kode, isi, _t = kirim_bukti(transfer, JPEG)
    assert kode == 409 and "waktu" in isi.lower()
    _tanpa_efek(transfer)


def test_bukti_keenam_ditolak_ramah_dan_tidak_meninggalkan_berkas(transfer, jam):
    siap_tagihan(transfer)
    for n in range(5):
        assert kirim_bukti(transfer, JPEG + bytes([n]))[0] == 303
    assert hitung("transfer_bukti") == 5 and len(berkas_tersimpan(transfer)) == 5
    kode, isi, _t = kirim_bukti(transfer, JPEG + b"\x09")
    assert kode == 409 and "5" in isi and "bukti" in isi.lower()
    assert hitung("transfer_bukti") == 5 and len(berkas_tersimpan(transfer)) == 5


def test_catat_bukti_gagal_menghapus_berkas_dan_jawaban_tidak_bocor(transfer, monkeypatch):
    siap_tagihan(transfer)

    def _gagal(*_a, **_k):
        raise sqlite3.OperationalError("database is locked: /rahasia/admin-control.db")
    monkeypatch.setattr(pesanan_transfer, "catat_bukti", _gagal)
    kode, isi, _t = kirim_bukti(transfer, JPEG)
    assert kode == 503
    _tanpa_efek(transfer)
    _tidak_bocor(isi)
    assert "rahasia" not in isi


def test_galat_tak_terduga_saat_catat_juga_menghapus_berkas(transfer, monkeypatch):
    siap_tagihan(transfer)

    def _meledak(*_a, **_k):
        raise RuntimeError("tak terduga")
    monkeypatch.setattr(pesanan_transfer, "catat_bukti", _meledak)
    kode, _i, _t = kirim_bukti(transfer, JPEG)
    assert kode == 500
    assert berkas_tersimpan(transfer) == []


def test_gagal_menulis_berkas_jawaban_ramah_tanpa_baris(transfer, monkeypatch):
    siap_tagihan(transfer)

    def _gagal(isi):
        raise OSError("No space left on device: /data/bukti-transfer")
    monkeypatch.setattr(bukti_berkas, "simpan_berkas", _gagal)
    kode, isi, _t = kirim_bukti(transfer, JPEG)
    assert kode == 503
    assert hitung("transfer_bukti") == 0
    _tidak_bocor(isi)
    assert "/data" not in isi


def test_batas_laju_unggah_429_tanpa_efek_tambahan(transfer):
    siap_tagihan(transfer)
    kode = [kirim_bukti(transfer, TEKS_PALSU)[0] for _ in range(8)]
    assert 429 in kode and kode[:3] == [415, 415, 415]
    assert kode.index(429) <= 7
    _tanpa_efek(transfer)


# --- ditolak lalu unggah ulang ----------------------------------------------------------------

def test_ditolak_menampilkan_alasan_dan_unggah_ulang_kembali_menunggu(transfer):
    siap_tagihan(transfer)
    assert kirim_bukti(transfer, JPEG)[0] == 303
    with pesanan_transfer.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order_id = kon.execute("SELECT order_id FROM pesanan_order").fetchone()[0]
        pesanan_transfer.tolak(kon, order_id, "admin_sintetis_a", "Nominal <b>kurang</b>", "2026-11-18T10:30:00")
    kode, halaman, _t = minta_mentah(transfer, STATUS, AKUN_A)
    assert "Bukti belum sesuai" in halaman and "Nominal &lt;b&gt;kurang&lt;/b&gt;" in halaman
    assert "<b>kurang</b>" not in halaman and "Unggah ulang" in halaman
    assert kirim_bukti(transfer, PDF)[0] == 303
    assert hitung("transfer_bukti") == 2
    kode, halaman, _t = minta_mentah(transfer, STATUS, AKUN_A)
    assert "Bukti diterima, menunggu pemeriksaan" in halaman and "<form" not in teks_tampak(halaman)


def test_lunas_oleh_admin_halaman_pembayaran_diterima_tanpa_form(transfer):
    siap_tagihan(transfer)
    kirim_bukti(transfer, JPEG)
    with pesanan_transfer.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order_id = kon.execute("SELECT order_id FROM pesanan_order").fetchone()[0]
        pesanan_transfer.setujui(kon, order_id, "admin_sintetis_a", "2026-11-18T10:30:00")
    kode, halaman, _t = minta_mentah(transfer, STATUS, AKUN_A)
    assert kode == 200 and "Pembayaran diterima" in halaman
    assert "<form" not in halaman.split("</header>", 1)[1]
    assert kirim_bukti(transfer, PNG)[0] == 409
    assert hitung("transfer_bukti") == 1 and len(berkas_tersimpan(transfer)) == 1


# --- setiap permintaan dijawab TEPAT satu kali ---------------------------------------------------

def _mentah(server, tubuh, akun=AKUN_A, tipe=None):
    return respons_mentah(server, BUKTI, akun, tubuh, tipe_konten() if tipe is None else tipe)


def _satu_respons(mentah, kode):
    assert jumlah_respons(mentah) == 1, mentah[:400]
    assert mentah.startswith(b"HTTP/1.0 %d" % kode) or mentah.startswith(b"HTTP/1.1 %d" % kode), mentah[:60]


def test_unggah_tanpa_order_dijawab_sekali_404(transfer):
    siap_pesan(transfer)
    _satu_respons(_mentah(transfer, bukti(token(AKUN_A, "bukti"), JPEG)), 404)
    _tanpa_efek(transfer)


def test_unggah_sukses_dan_semua_penolakan_dijawab_sekali(transfer):
    siap_tagihan(transfer)
    tok = token(AKUN_A, "bukti")
    _satu_respons(_mentah(transfer, bukti("1.salah", JPEG)), 403)
    _satu_respons(_mentah(transfer, bukti(tok, TEKS_PALSU)), 415)
    _satu_respons(_mentah(transfer, bukti(tok, b"")), 400)
    _satu_respons(_mentah(transfer, b"bukan multipart"), 400)
    _satu_respons(_mentah(transfer, b"x", akun=AKUN_ADMIN), 404)
    _satu_respons(_mentah(transfer, b"x", akun=AKUN_MURID), 401)
    _satu_respons(_mentah(transfer, bukti(tok, JPEG)), 303)
    _satu_respons(_mentah(transfer, bukti(tok, JPEG + b"1")), 303)


def test_unggah_ditolak_hambatan_dan_laju_dijawab_sekali(transfer, jam):
    siap_tagihan(transfer)
    tok = token(AKUN_A, "bukti")
    jam.maju_jam(25)
    _satu_respons(_mentah(transfer, bukti(tok, JPEG)), 409)
    mentah = [_mentah(transfer, bukti(tok, JPEG)) for _ in range(8)]
    assert all(jumlah_respons(m) <= 1 for m in mentah)
    assert any(m.startswith(b"HTTP/1.0 429") or m.startswith(b"HTTP/1.1 429") for m in mentah)
