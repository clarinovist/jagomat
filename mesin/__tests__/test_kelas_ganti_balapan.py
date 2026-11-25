"""Unggah bukti dan ganti paket yang berebut (butir QA #3, 25 Nov 2026; data sintetis, HTTP nyata).

Celah lama: unggah membaca tagihan lalu menulis bukti, ganti paket menulis tagihan baru di antaranya, sehingga bukti masuk ke tagihan
LAMA yang sudah digantikan. Sekarang keduanya diserialkan per anak; yang kedua melihat keadaan akhir yang konsisten.
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


def test_ganti_yang_masuk_saat_unggah_berjalan_menunggu_lalu_ditolak_karena_bukti_sudah_ada(kidup, murid, jam, monkeypatch):
    assert buat(kidup, murid, "mini")[0] == 303
    jam.maju_jam(1)
    hasil = {}
    asli = KM._simpan_dan_catat

    def sambil_ganti(*a, **k):
        # Di sini unggah sudah membaca tagihan Mini tetapi belum menulis bukti: ganti paket datang dari tab lain.
        pekerja = threading.Thread(target=lambda: hasil.update(ganti=_ganti(kidup, murid, "private")[0]))
        pekerja.start()
        pekerja.join(timeout=1.0)
        hasil["selesai_sebelum_bukti"] = not pekerja.is_alive()
        hasil["pekerja"] = pekerja
        return asli(*a, **k)

    monkeypatch.setattr(KM, "_simpan_dan_catat", sambil_ganti)
    assert unggah(kidup, murid)[0] == 303
    hasil["pekerja"].join(timeout=10)
    assert hasil["selesai_sebelum_bukti"] is False         # ganti tidak boleh menyelip di antara baca dan tulis
    assert hasil["ganti"] == 409                           # sesudah bukti ada, ganti paket ditolak
    order = _order()
    assert [o["paket"] for o in order] == ["mini"]
    assert [b["order_id"] for b in baca_admin("SELECT order_id FROM kelas_bukti")] == [order[0]["id"]]


def test_ganti_lebih_dulu_membuat_unggah_masuk_ke_tagihan_baru(kidup, murid, jam):
    assert buat(kidup, murid, "mini")[0] == 303
    jam.maju_jam(1)
    assert _ganti(kidup, murid, "private")[0] == 303
    assert unggah(kidup, murid)[0] == 303
    private = [o["id"] for o in _order() if o["paket"] == "private"][0]
    assert [b["order_id"] for b in baca_admin("SELECT order_id FROM kelas_bukti")] == [private]
