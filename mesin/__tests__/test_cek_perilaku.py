"""Hitungan ganti jawaban per soal (F1b): tabel aditif, aturan naik, jalur cek anak, dan cascade.

Data sintetis. Tabel hanya memuat nomor soal dan jumlah; isi jawaban dan kunci tidak pernah masuk.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_perilaku  # noqa: E402
import database  # noqa: E402
from cek_anak_kit import Cek, server  # noqa: E402,F401  (fixture server)

TABEL = "cek_ganti_jawaban"


@pytest.fixture()
def cek(server):
    return Cek(server)


def _ada_tabel(kon) -> bool:
    return kon.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABEL,)
    ).fetchone() is not None


def _jumlah(cek, nomor):
    with cek.server.buka() as kon:
        if not _ada_tabel(kon):
            return None
        baris = kon.execute(
            f"""SELECT g.jumlah FROM {TABEL} g JOIN sesi_soal ss ON ss.id = g.sesi_soal_id
                WHERE ss.sesi_id = ? AND ss.nomor = ?""",
            (cek.sesi_id, nomor),
        ).fetchone()
    return baris[0] if baris else None


# --- pasang dan pembaca -------------------------------------------------------------

def test_pasang_idempoten_dan_membuat_tabel_tanpa_kolom_isi_jawaban(server):
    with server.buka() as kon:
        cek_perilaku.pasang(kon)
        cek_perilaku.pasang(kon)
        assert _ada_tabel(kon)
        kolom = {r[1] for r in kon.execute(f"PRAGMA table_info({TABEL})")}
    assert kolom == {"sesi_soal_id", "jumlah"}


def test_pembaca_tidak_membuat_tabel_saat_belum_pernah_dicatat(cek):
    with cek.server.buka() as kon:
        assert cek_perilaku.jumlah_ganti_per_sesi(kon, cek.sesi_id) == {}
        assert not _ada_tabel(kon)


# --- aturan naik -----------------------------------------------------------------------

def test_catat_ganti_jawaban_pertama_tidak_menaikkan(cek):
    with cek.server.buka() as kon:
        ssid = cek.id_butir(1)
        assert cek_perilaku.catat_ganti(kon, ssid, None, "A") is False
        assert cek_perilaku.catat_ganti(kon, ssid, "", "A") is False
        assert cek_perilaku.jumlah_ganti_per_sesi(kon, cek.sesi_id) == {}


def test_catat_ganti_naik_hanya_saat_nilai_berubah_dan_sebelumnya_ada(cek):
    with cek.server.buka() as kon:
        ssid = cek.id_butir(1)
        assert cek_perilaku.catat_ganti(kon, ssid, "A", "A") is False
        assert cek_perilaku.catat_ganti(kon, ssid, "A", "B") is True
        assert cek_perilaku.catat_ganti(kon, ssid, "B", "C") is True
        assert cek_perilaku.jumlah_ganti_per_sesi(kon, cek.sesi_id) == {ssid: 2}


def test_jawaban_lama_kosong_tidak_dihitung_tetapi_mengosongkan_jawaban_dihitung(cek):
    with cek.server.buka() as kon:
        ssid = cek.id_butir(1)
        assert cek_perilaku.catat_ganti(kon, ssid, "", "B") is False
        assert cek_perilaku.catat_ganti(kon, ssid, "A", None) is True


def test_jalur_cek_anak_menghitung_ganti_hanya_saat_pilihan_berubah(cek):
    cek.simpan(1, opsi="opsi_1")
    assert _jumlah(cek, 1) is None
    cek.simpan(1, opsi="opsi_1")
    assert _jumlah(cek, 1) is None
    cek.simpan(1, opsi="opsi_2")
    assert _jumlah(cek, 1) == 1
    cek.simpan(1, opsi="opsi_3")
    assert _jumlah(cek, 1) == 2


def test_kiriman_tanpa_pilihan_tidak_menghitung_ganti(cek):
    cek.simpan(1, opsi="opsi_1")
    cek.simpan(1, opsi=None)
    assert _jumlah(cek, 1) is None


def test_ganti_terbaca_per_sesi_dan_hanya_untuk_sesi_itu(cek):
    cek.simpan(1, opsi="opsi_1")
    cek.simpan(1, opsi="opsi_2")
    with cek.server.buka() as kon:
        ssid = cek.id_butir(1)
        assert cek_perilaku.jumlah_ganti_per_sesi(kon, cek.sesi_id) == {ssid: 1}
        assert cek_perilaku.jumlah_ganti_per_sesi(kon, cek.sesi_id + 999) == {}


# --- cascade -----------------------------------------------------------------------------

def test_hapus_sesi_ikut_menghapus_hitungan_ganti(cek):
    cek.simpan(1, opsi="opsi_1")
    cek.simpan(1, opsi="opsi_2")
    assert _jumlah(cek, 1) == 1
    with cek.server.buka() as kon:
        database.hapus_sesi(kon, cek.sesi_id)
        sisa = kon.execute(f"SELECT COUNT(*) FROM {TABEL}").fetchone()[0]
    assert sisa == 0
