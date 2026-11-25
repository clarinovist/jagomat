"""Unggah bukti dan ganti paket yang berebut (butir QA #3, 25 Nov 2026; data sintetis, HTTP nyata).

Celah lama: unggah memilih tagihan dari kode paket yang dibaca lebih dulu, ganti paket menulis tagihan baru di antaranya, sehingga bukti
masuk ke tagihan LAMA yang sudah digantikan. Sekarang tagihan penerima dipilih di dalam transaksi tulis yang sama (`kelas_unggah`),
jadi urutan antar-proses ditentukan SQLite, bukan kunci proses: bukti selalu masuk ke tagihan terbaru yang terbuka.
"""
from __future__ import annotations

import threading

import pytest

import kelas_murid_http as KM
from kelas_http_kit import (M, baca_admin, buat, buat_murid, jam, kidup, kirim, kmati, server, token, unggah)  # noqa: F401

GANTI = M + "/ganti"


@pytest.fixture()
def murid(kidup, monkeypatch):
    return buat_murid(kidup, "murid-balap", "Anak Sintetis")


def _ganti(server_uji, pembeli, kode):
    return kirim(server_uji, GANTI, pembeli, {"token": token(pembeli.akun, "kelas_ganti:" + kode), "kode": kode})


def _order() -> list:
    return baca_admin("SELECT id,paket FROM kelas_order ORDER BY rowid")


def _bukti() -> list:
    return [b["order_id"] for b in baca_admin("SELECT order_id FROM kelas_bukti")]


def test_ganti_yang_menyelip_di_antara_baca_dan_tulis_tidak_membuat_bukti_jatuh_ke_tagihan_lama(kidup, murid, jam, monkeypatch):
    assert buat(kidup, murid, "mini")[0] == 303
    jam.maju_jam(1)
    hasil = {}
    asli = KM._simpan_dan_catat

    def sambil_ganti(*a, **k):
        # Unggah sudah membaca tagihan Mini (halaman menampilkannya) tetapi belum menulis bukti: ganti datang dari tab lain.
        pekerja = threading.Thread(target=lambda: hasil.update(ganti=_ganti(kidup, murid, "private")[0]))
        pekerja.start()
        pekerja.join(timeout=10)
        return asli(*a, **k)

    monkeypatch.setattr(KM, "_simpan_dan_catat", sambil_ganti)
    assert unggah(kidup, murid)[0] == 303
    assert hasil["ganti"] == 303
    private = [o["id"] for o in _order() if o["paket"] == "private"]
    assert len(private) == 1 and _bukti() == private          # bukti ke tagihan terbaru, tidak ke Mini yang digantikan


def test_ganti_sesudah_bukti_ada_ditolak_dan_bukti_tetap_di_tagihan_asal(kidup, murid, jam):
    assert buat(kidup, murid, "mini")[0] == 303
    jam.maju_jam(1)
    assert unggah(kidup, murid)[0] == 303
    assert _ganti(kidup, murid, "private")[0] == 409
    mini = [o["id"] for o in _order()]
    assert len(mini) == 1 and _bukti() == mini


def test_ganti_lebih_dulu_membuat_unggah_masuk_ke_tagihan_baru(kidup, murid, jam):
    assert buat(kidup, murid, "mini")[0] == 303
    jam.maju_jam(1)
    assert _ganti(kidup, murid, "private")[0] == 303
    assert unggah(kidup, murid)[0] == 303
    private = [o["id"] for o in _order() if o["paket"] == "private"]
    assert _bukti() == private
