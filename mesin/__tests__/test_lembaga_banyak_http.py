"""Pindah banyak anak lewat HTTP (`/lembaga/pindah-banyak`): satu transaksi, 404 identik,
penolakan tanpa efek, validasi form di server, dan pesan hasil tanpa memantulkan isian.

Data sepenuhnya sintetis. Fixture dan helper dipakai bersama `test_lembaga_http`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import lembaga_store as L  # noqa: E402
from test_lembaga_http import (  # noqa: E402,F401
    GURU_A, GURU_B, LINTAS_SITUS, LUAR, PEMILIK, TIDAK_ADA, _pemilik, _post, _sebagai, _snapshot,
    server,
)

RUTE = "/lembaga/pindah-banyak"


def _banyak(server, nama, ids, ke, **kw):
    pasangan = [("siswa_id", str(i)) for i in ids] + [("ke", ke)]
    return _post(server, RUTE, nama, pasangan, **kw)


def _tambah(server, nama, pemilik):
    with server.buka() as kon:
        return database.tambah_siswa(kon, nama, "P3", pemilik=pemilik)


def _sesi_berjalan(server, siswa_id):
    with server.buka() as kon:
        sesi = database.buat_sesi(kon, siswa_id, seed=9, jumlah_soal=1)
        kon.execute("UPDATE sesi SET mulai='2026-11-01 08:00:00' WHERE id=?", (sesi,))


# --- berhasil -------------------------------------------------------------------

def test_banyak_sukses_alihkan_dengan_jumlah_dan_tujuan_lalu_pesan_ramah(server):
    a, o = server.anak["a"], server.anak["o"]
    kode, _, tajuk = _banyak(server, PEMILIK, [a, o], GURU_B)
    assert kode == 303
    assert tajuk["Location"] == "/lembaga?pesan=banyak_ok&jumlah=2&ke=" + GURU_B
    assert _pemilik(server, a) == _pemilik(server, o) == GURU_B
    with server.buka() as kon:
        jejak = kon.execute("SELECT siswa_id,dari,ke,oleh FROM pindah_siswa ORDER BY siswa_id").fetchall()
    assert [tuple(r) for r in jejak] == [(a, GURU_A, GURU_B, PEMILIK), (o, PEMILIK, GURU_B, PEMILIK)]
    _, halaman, _ = server.minta(tajuk["Location"], auth=_sebagai(PEMILIK))
    assert "2 anak dipindahkan ke " + GURU_B in halaman and 'role="status"' in halaman


def test_banyak_nama_kembar_antar_anak_dan_dengan_tujuan_diberi_pembeda(server):
    k1 = _tambah(server, "Kembar", GURU_A)
    k2 = _tambah(server, "Kembar", PEMILIK)
    _tambah(server, "Kembar", GURU_B)
    assert _banyak(server, PEMILIK, [k1, k2], GURU_B)[0] == 303
    with server.buka() as kon:
        nama = {r["id"]: r["nama"] for r in kon.execute(
            "SELECT id, nama FROM siswa WHERE id IN (?,?)", (k1, k2))}
    assert nama == {k1: "Kembar (2)", k2: "Kembar (3)"}


def test_pindah_satu_anak_form_lama_tetap_berfungsi(server):
    kode, _, tajuk = _post(server, "/lembaga/pindah", PEMILIK,
                           {"siswa_id": str(server.anak["a"]), "ke": GURU_B})
    assert kode == 303 and tajuk["Location"] == "/lembaga?pesan=pindah_ok"
    assert _pemilik(server, server.anak["a"]) == GURU_B


# --- kewenangan: 404 identik, tanpa efek ----------------------------------------

@pytest.mark.parametrize("aktor", [GURU_A, LUAR, "pengelola-l"])
def test_banyak_non_pemilik_404_identik_tanpa_tulis(server, aktor):
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    sebelum = _snapshot(server)
    kode, isi, _ = _banyak(server, aktor, [server.anak["a"], server.anak["b"]], GURU_B)
    assert (kode, isi) == (acuan[0], acuan[1])
    sampah = _post(server, RUTE, aktor, {"x": "y"})
    assert (sampah[0], sampah[1]) == (acuan[0], acuan[1])  # sampah dari non-pemilik tetap 404, bukan 400
    assert _snapshot(server) == sebelum


def test_banyak_sebagian_anak_bukan_milik_lembaga_404_identik_tanpa_efek(server):
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    sebelum = _snapshot(server)
    for ids in ([server.anak["a"], server.anak["o"], server.anak["luar"]], [server.anak["a"], 99999]):
        kode, isi, _ = _banyak(server, PEMILIK, ids, GURU_B)
        assert (kode, isi) == (acuan[0], acuan[1])
        assert _snapshot(server) == sebelum


@pytest.mark.parametrize("tujuan", [LUAR, "pengelola-l", "tidak-ada"])
def test_banyak_tujuan_di_luar_lembaga_404_identik_tanpa_efek(server, tujuan):
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    sebelum = _snapshot(server)
    kode, isi, _ = _banyak(server, PEMILIK, [server.anak["a"], server.anak["o"]], tujuan)
    assert (kode, isi) == (acuan[0], acuan[1])
    assert _snapshot(server) == sebelum


# --- penolakan bisnis: tolak semua, tanpa efek ----------------------------------

def test_banyak_sesi_berjalan_menolak_seluruh_permintaan_dengan_jumlah(server):
    _sesi_berjalan(server, server.anak["o"])
    sebelum = _snapshot(server)
    kode, _, tajuk = _banyak(server, PEMILIK, [server.anak["a"], server.anak["o"]], GURU_B)
    assert kode == 303
    assert tajuk["Location"] == "/lembaga?pesan=banyak_sesi&jumlah=1"
    assert _snapshot(server) == sebelum
    _, halaman, _ = server.minta(tajuk["Location"], auth=_sebagai(PEMILIK))
    assert "1 anak yang Anda pilih masih punya sesi" in halaman


def test_banyak_anak_sudah_di_tujuan_menolak_seluruh_permintaan(server):
    sebelum = _snapshot(server)
    kode, _, tajuk = _banyak(
        server, PEMILIK, [server.anak["a"], server.anak["o"], server.anak["b"]], GURU_B)
    assert kode == 303 and tajuk["Location"] == "/lembaga?pesan=banyak_sama&jumlah=1"
    assert _snapshot(server) == sebelum


def test_banyak_pembeda_nama_habis_menolak_seluruh_permintaan(server):
    with server.buka() as kon:
        database.tambah_siswa(kon, "Anak Omega", "P3", pemilik=GURU_B)
        for urut in range(2, L.BATAS_PEMBEDA + 1):
            database.tambah_siswa(kon, "Anak Omega (%d)" % urut, "P3", pemilik=GURU_B)
    sebelum = _snapshot(server)
    kode, _, tajuk = _banyak(server, PEMILIK, [server.anak["a"], server.anak["o"]], GURU_B)
    assert kode == 303 and tajuk["Location"] == "/lembaga?pesan=banyak_nama"
    assert _snapshot(server) == sebelum


# --- batas jumlah -----------------------------------------------------------------

def test_banyak_tepat_di_batas_diterima_dan_satu_lebih_ditolak(server):
    ids = [_tambah(server, "Murid %03d" % i, GURU_A) for i in range(L.BATAS_PINDAH_BANYAK + 1)]
    sebelum = _snapshot(server)
    kode, _, tajuk = _banyak(server, PEMILIK, ids, GURU_B)
    assert kode == 303 and tajuk["Location"] == "/lembaga?pesan=banyak_terlalu"
    assert _snapshot(server) == sebelum
    kode, _, tajuk = _banyak(server, PEMILIK, ids[:L.BATAS_PINDAH_BANYAK], GURU_B)
    assert kode == 303 and "banyak_ok&jumlah=%d" % L.BATAS_PINDAH_BANYAK in tajuk["Location"]
    assert {_pemilik(server, i) for i in ids[:L.BATAS_PINDAH_BANYAK]} == {GURU_B}
    assert _pemilik(server, ids[-1]) == GURU_A


def test_banyak_id_jauh_melebihi_batas_form_400(server):
    sebelum = _snapshot(server)
    ids = list(range(1, 2 * L.BATAS_PINDAH_BANYAK + 3))
    assert _banyak(server, PEMILIK, ids, GURU_B)[0] == 400
    assert _snapshot(server) == sebelum


# --- validasi form di server -------------------------------------------------------

@pytest.mark.parametrize("pasangan", [
    [("ke", GURU_B)],                                             # tanpa id
    [("siswa_id", "1")],                                           # tanpa ke
    [("siswa_id", "1"), ("ke", "")],                               # ke kosong
    [("siswa_id", "1"), ("ke", GURU_B), ("ke", GURU_A)],           # ke ganda
    [("siswa_id", "abc"), ("ke", GURU_B)],
    [("siswa_id", ""), ("ke", GURU_B)],
    [("siswa_id", "-1"), ("ke", GURU_B)],
    [("siswa_id", "1.5"), ("ke", GURU_B)],
    [("siswa_id", "0"), ("ke", GURU_B)],
    [("siswa_id", "1"), ("siswa_id", "1"), ("ke", GURU_B)],        # id ganda
    [("siswa_id", "1"), ("ke", GURU_B), ("tambahan", "x")],        # kolom asing
    [("siswa_id", "1"), ("ke", "x" * 201)],
])
def test_banyak_isian_salah_bentuk_dari_pemilik_400_tanpa_tulis(server, pasangan):
    sebelum = _snapshot(server)
    kode, _, _ = _post(server, RUTE, PEMILIK, pasangan)
    assert kode == 400
    assert _snapshot(server) == sebelum


# --- asal, sandi, laju, GET ----------------------------------------------------------

def test_banyak_lintas_situs_403_tanpa_tulis(server):
    sebelum = _snapshot(server)
    kode, isi, _ = _banyak(server, PEMILIK, [server.anak["a"]], GURU_B, headers=LINTAS_SITUS)
    assert kode == 403 and "Permintaan ditolak" in isi
    assert _banyak(server, PEMILIK, [server.anak["a"]], GURU_B,
                   headers={"Origin": "http://situs-lain.invalid"})[0] == 403
    assert _snapshot(server) == sebelum


def test_banyak_anonim_dan_murid_ditolak_palang_sandi_tanpa_tulis(server):
    sebelum = _snapshot(server)
    data = {"siswa_id": str(server.anak["a"]), "ke": GURU_B}
    assert server.minta(RUTE, data=data)[0] == 401
    assert server.minta(RUTE, auth=("feby", "sandi-feby-12345"), data=data)[0] == 401
    assert _snapshot(server) == sebelum


def test_get_pada_rute_banyak_404(server):
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    kode, isi, _ = server.minta(RUTE, auth=_sebagai(PEMILIK))
    assert (kode, isi) == (acuan[0], acuan[1])


def test_banyak_memakai_batas_laju(server, monkeypatch):
    import learning_cycle_http as siklus
    monkeypatch.setattr(siklus, "_BATAS_PER_MENIT", 2)
    monkeypatch.setattr(siklus, "_riwayat", {})
    hasil = [_banyak(server, PEMILIK, [server.anak["a"]], GURU_A)[0] for _ in range(4)]
    assert hasil[:2] == [303, 303]
    assert 429 in hasil[2:]


# --- halaman -----------------------------------------------------------------------

def test_halaman_menawarkan_form_banyak_di_luar_tabel_dengan_kotak_centang_native(server):
    _, isi, _ = server.minta("/lembaga", auth=_sebagai(PEMILIK))
    form = re.search(r'<form[^>]*id="form-pindah-banyak"[^>]*action="/lembaga/pindah-banyak"[^>]*>'
                     r'(.*?)</form>', isi, re.S)
    assert form, "form pindah banyak tidak ditemukan"
    pilihan = re.findall(r'<option value="([^"]*)"', form.group(1))
    assert pilihan == [PEMILIK, GURU_A, GURU_B]
    kotak = re.findall(r'<input type="checkbox" name="siswa_id" value="(\d+)" form="form-pindah-banyak"', isi)
    assert sorted(map(int, kotak)) == sorted(server.anak[k] for k in ("a", "b", "o"))
    assert "<script" not in isi.split("<main", 1)[1].split("</main>")[0]
    assert isi.count('action="/lembaga/pindah"') == 3  # form satu-anak tetap ada
    assert "csrf" not in form.group(1).lower()


def test_halaman_tanpa_guru_lain_tidak_menawarkan_pindah_banyak(server):
    with server.buka() as kon:
        for g in (GURU_A, GURU_B):
            L.lepas_anggota(kon, lembaga_id=server.lid, guru=g, oleh="pengelola-l")
    _, isi, _ = server.minta("/lembaga", auth=_sebagai(PEMILIK))
    assert "form-pindah-banyak" not in isi and 'type="checkbox"' not in isi


@pytest.mark.parametrize("kueri", [
    "pesan=banyak_ok&jumlah=9999&ke=" + GURU_B,           # jumlah di atas batas
    "pesan=banyak_ok&jumlah=0&ke=" + GURU_B,
    "pesan=banyak_ok&jumlah=abc&ke=" + GURU_B,
    "pesan=banyak_ok&jumlah=3&ke=%3Cb%3Ejahil%3C/b%3E",     # tujuan bukan penghuni
    "pesan=banyak_ok&jumlah=3&ke=" + LUAR,                  # guru di luar lembaga
    "pesan=banyak_ok&jumlah=3",                             # tanpa tujuan
    "pesan=banyak_sesi",                                    # tanpa jumlah
])
def test_pesan_banyak_tanpa_parameter_sah_tidak_tampil_dan_tidak_memantulkan(server, kueri):
    _, isi, _ = server.minta("/lembaga?" + kueri, auth=_sebagai(PEMILIK))
    assert 'role="status"' not in isi
    assert "jahil" not in isi and "9999" not in isi and LUAR not in isi


def test_pesan_banyak_menampilkan_tujuan_penghuni_dengan_escape(server):
    _, isi, _ = server.minta(f"/lembaga?pesan=banyak_ok&jumlah=7&ke={GURU_A}", auth=_sebagai(PEMILIK))
    assert "7 anak dipindahkan ke " + GURU_A in isi
