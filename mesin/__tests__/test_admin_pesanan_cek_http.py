"""Kartu "Data cek untuk laporan" di Detail order admin lewat HTTP (D1): hanya order lunas, baca-saja, tanpa 500.

Order lunas di jalur QRIS DAN transfer rekening (fixture `lunas`); data sintetis, server dan jam palsu. Tes di sini
menjadi sasaran mutation di `test_admin_pesanan_cek_mutation.py`.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pesanan_http as ap  # noqa: E402
import admin_store  # noqa: E402
import cek_gratis_sapu  # noqa: E402
import topik_awam  # noqa: E402
from admin_pesanan_kit import TAK_ADA, alamat_detail, login_admin, minta_admin, order_bayar  # noqa: E402
from cek_http_kit import AKUN_A, AKUN_B, NAMA_A, id_akun, minta_mentah  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_http_kit import WA_SINTETIS, bayar, jam, keluarga, ledger, server, tertutup  # noqa: E402,F401
from pesanan_transfer_http_kit import transfer  # noqa: E402,F401
from purna_http_kit import bayar_purna, jadikan_ditahan, lunas, transfer_purna  # noqa: E402,F401
from admin_transfer_kit import order_menunggu  # noqa: E402

JUDUL = "Data cek untuk laporan"
AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)
TERLARANG = ("kunci", "malrule", "diagnos", "kode_final", "pembahasan", "jawaban benar", "tel:", "wa.me",
             NAMA_A.lower(), WA_SINTETIS, "<form", "<button", "<script", "<input")
SAPUAN_LEWAT_RETENSI = "2026-12-20T00:00:00"


def _isi(server, admin, order_id, kode=200):
    hasil = minta_admin(server, alamat_detail(order_id), admin)
    assert hasil[0] == kode
    return hasil[1]


def _kartu(isi: str) -> str:
    bagian = [b for b in isi.split("<section") if "<h2>%s</h2>" % JUDUL in b]
    assert len(bagian) == 1, "kartu data cek harus tepat satu"
    return bagian[0].split("</section>")[0]


def _teks(kartu: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", kartu))


def _potret_belajar(server):
    """Seluruh isi DB belajar + jumlah perubahan koneksi: tulis apa pun terlihat di sini."""
    with server.buka() as kon:
        nama = [r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        isi = [(t, [tuple(r) for r in kon.execute('SELECT * FROM "%s" ORDER BY rowid' % t)]) for t in nama
               if t != "sqlite_sequence"]
    return hashlib.sha256(repr(isi).encode()).hexdigest()


def _baris_order(order_id):
    with ledger() as kon:
        return dict(kon.execute("SELECT * FROM pesanan_order WHERE order_id=?", (order_id,)).fetchone())


# --- tampil hanya untuk order lunas ----------------------------------------------------------

def test_kartu_tampil_untuk_order_lunas_dengan_data_cek_sintetis(lunas):
    server, admin, oid = lunas
    kartu = _kartu(_isi(server, admin, oid))
    teks = _teks(kartu)
    assert "Kelas 4" in teks and "Skor 67 dari 100" in teks and "Cukup baik" in teks and "15 soal" in teks
    baris = re.findall(r'<th scope="row">(.*?)</th>\s*<td>(\d+)</td>\s*<td>(\d+)</td>', kartu)
    assert len(baris) == 3
    assert sum(int(b) for _n, b, _t in baris) == 10 and sum(int(t) for _n, _b, t in baris) == 15
    assert {n for n, _b, _t in baris} == {topik_awam.nama(t) for t in (
        "berhitung-sekolah", "pengukuran", "geometri-datar")}
    # jam sintetis = 1 jam sesudah sesi selesai (09:00 -> 10:00): 30 hari dikurangi 1 jam, dibulatkan ke bawah.
    assert "Data per materi dihapus otomatis dalam 29 hari (retensi 30 hari). Buat draf laporan sebelum itu." in teks


def test_kartu_di_bawah_voucher_dan_laporan_dan_tanpa_form_atau_tombol_sendiri(lunas):
    server, admin, oid = lunas
    isi = _isi(server, admin, oid)
    assert isi.index("Voucher dan laporan") < isi.index(JUDUL) < isi.index("Perjalanan order")
    kartu = _kartu(isi).lower()
    assert [k for k in TERLARANG if k in kartu] == []


@pytest.mark.parametrize("cara", ["qris", "transfer"])
def test_order_belum_lunas_tanpa_kartu_dan_tanpa_baca_data_cek(cara, request, monkeypatch):
    if cara == "qris":
        server = request.getfixturevalue("bayar_purna")
        order_id = order_bayar(server)[0]["order_id"]
    else:
        server = request.getfixturevalue("transfer_purna")
        order_id = order_menunggu(server)
    dibaca = []
    monkeypatch.setattr(ap.cek_ringkasan_admin, "ringkasan_untuk_order",
                        lambda *a, **k: dibaca.append(a) or None)
    admin = login_admin(server)
    isi = _isi(server, admin, order_id)
    assert JUDUL not in isi and dibaca == []


def test_order_perlu_diperiksa_tanpa_kartu_walau_lunas_di_ledger(lunas, jam, monkeypatch):
    server, admin, oid = lunas
    jadikan_ditahan(server, oid, jam)
    dibaca = []
    monkeypatch.setattr(ap.cek_ringkasan_admin, "ringkasan_untuk_order",
                        lambda *a, **k: dibaca.append(a) or None)
    isi = _isi(server, admin, oid)
    assert JUDUL not in isi and dibaca == []


# --- akses --------------------------------------------------------------------------------

@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_nonadmin_404_byte_identik_rute_tak_dikenal_tanpa_baca_data_cek(lunas, akun, monkeypatch):
    server, _admin, oid = lunas
    dibaca = []
    monkeypatch.setattr(ap.cek_ringkasan_admin, "ringkasan_untuk_order",
                        lambda *a, **k: dibaca.append(a) or None)
    acuan = minta_mentah(server, TAK_ADA, akun)
    assert acuan[0] == 404
    hasil = minta_mentah(server, alamat_detail(oid), akun)
    assert hasil[:2] == acuan[:2] and JUDUL not in hasil[1] and dibaca == []


def test_kunci_cek_dari_ledger_urutan_siswa_cek_akun_dan_none_bila_order_tak_ada(tmp_path):
    import pesanan
    import pesanan_admin_order as po
    from pesanan_kit import AKUN_A as AKUN_LEDGER, buat, ord_id, siapkan_db
    with pesanan.buka(siapkan_db(tmp_path), tulis_data=True) as kon:
        order = buat(kon, 3, siswa=7)  # siswa_id 7 beda dari cek_id 3: urutan tertukar terlihat
        assert po.kunci_cek(kon, order["order_id"]) == (7, 3, AKUN_LEDGER)
        assert po.kunci_cek(kon, ord_id(404)) is None


# --- kunci dari ledger, baca-saja ----------------------------------------------------------

def test_pembaca_dipanggil_dengan_tiga_kunci_dari_ledger_dan_koneksi_query_only(lunas, monkeypatch):
    server, admin, oid = lunas
    panggilan = []
    asli = ap.cek_ringkasan_admin.ringkasan_untuk_order

    def mata_mata(kon, siswa_id, cek_id, id_akun_order, sekarang):
        panggilan.append((siswa_id, cek_id, id_akun_order, kon.execute("PRAGMA query_only").fetchone()[0]))
        return asli(kon, siswa_id, cek_id, id_akun_order, sekarang)

    monkeypatch.setattr(ap.cek_ringkasan_admin, "ringkasan_untuk_order", mata_mata)
    _isi(server, admin, oid)
    baris = _baris_order(oid)
    assert panggilan == [(baris["siswa_id"], baris["cek_id"], baris["akun_id"], 1)]


def test_membuka_detail_tidak_menulis_db_belajar_walau_bahan_belum_dinilai(lunas):
    server, admin, oid = lunas
    sebelum = _potret_belajar(server)
    _isi(server, admin, oid)
    assert _potret_belajar(server) == sebelum
    with server.buka() as kon:
        kon.execute("DELETE FROM diagnosis")
    sebelum = _potret_belajar(server)
    isi = _isi(server, admin, oid)
    assert "Belum dinilai" in _teks(_kartu(isi))
    assert _potret_belajar(server) == sebelum
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM diagnosis").fetchone()[0] == 0


def test_cek_milik_akun_lain_tidak_terbaca(lunas):
    server, admin, oid = lunas
    with server.buka() as kon:
        kon.execute("UPDATE cek_gratis SET id_akun = ?", (id_akun(AKUN_B),))
    teks = _teks(_kartu(_isi(server, admin, oid)))
    assert "Data cek tidak terbaca" in teks and "Skor" not in teks


# --- retensi -----------------------------------------------------------------------------

def test_bahan_sudah_dihapus_retensi_menampilkan_pesan_dan_skor_tetap(lunas):
    server, admin, oid = lunas
    with server.buka() as kon:
        assert cek_gratis_sapu.sapu_cek_gratis(kon, SAPUAN_LEWAT_RETENSI, frozenset({id_akun(AKUN_A)}))[
            "bahan_dihapus"] == 1
    kartu = _kartu(_isi(server, admin, oid))
    teks = _teks(kartu)
    assert "Data per materi sudah dihapus (retensi 30 hari)" in teks and "Skor 67 dari 100" in teks
    assert "<table" not in kartu


# --- galat baca: tanpa 500, tanpa traceback, halaman lain tetap utuh ----------------------------

@pytest.mark.parametrize("galat", [sqlite3.OperationalError("rahasia-sintetis-xyz"), OSError("rahasia-sintetis-xyz"),
                                   admin_store.StoreBelumSiap("rahasia-sintetis-xyz"),
                                   ValueError("rahasia-sintetis-xyz")])
def test_db_belajar_tak_terbaca_pesan_tanpa_500_traceback_atau_isi_galat(lunas, monkeypatch, caplog, galat):
    server, admin, oid = lunas

    def gagal(*_a, **_k):
        raise galat

    monkeypatch.setattr(ap.cek_ringkasan_admin, "ringkasan_untuk_order", gagal)
    with caplog.at_level("DEBUG"):
        isi = _isi(server, admin, oid)
    assert "Data cek tidak terbaca" in _kartu(isi)
    assert "Voucher dan laporan" in isi and "Perjalanan order" in isi
    assert "Traceback" not in isi and "rahasia-sintetis-xyz" not in isi
    assert type(galat).__name__ in caplog.text and "rahasia-sintetis-xyz" not in caplog.text
    assert "Traceback" not in caplog.text


def test_tabel_cek_hilang_di_db_belajar_nyata_pesan_tanpa_500(lunas):
    server, admin, oid = lunas
    with server.buka() as kon:
        kon.execute("DROP TABLE cek_gratis")
    isi = _isi(server, admin, oid)
    assert "Data cek tidak terbaca" in _kartu(isi) and "Traceback" not in isi
