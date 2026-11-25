"""Ganti paket lewat HTTP nyata (POST /murid/paket/ganti) dan halaman tagihan (butir QA #3, 25 Nov 2026; data sintetis)."""
from __future__ import annotations

import pytest

from kelas_http_kit import (BUKTI, M, baca_admin, buat, buat_dan_unggah, buat_murid, hitung, jam, kidup,  # noqa: F401
                            kirim, kmati, minta_mentah, server, token, unggah)

GANTI = M + "/ganti"
ANAK = "Anak Sintetis"


@pytest.fixture()
def murid(kidup, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    return buat_murid(kidup, "murid-ganti", ANAK)


def ganti(server_uji, pembeli, kode, *, tok=None, ekstra=None, hapus=()):
    data = {"token": token(pembeli.akun, "kelas_ganti:" + kode) if tok is None else tok, "kode": kode}
    data.update(ekstra or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return kirim(server_uji, GANTI, pembeli, data)


def _jumlah_order() -> int:
    return baca_admin("SELECT COUNT(*) AS n FROM kelas_order")[0]["n"]


def _halaman(server_uji, pembeli) -> str:
    kode, isi, _ = minta_mentah(server_uji, M, pembeli.akun)
    assert kode == 200
    return isi.decode() if isinstance(isi, bytes) else isi


def test_halaman_tagihan_menawarkan_ganti_ke_paket_lain_dengan_peringatan_uang(kidup, murid):
    assert buat(kidup, murid, "mini")[0] == 303
    isi = _halaman(kidup, murid)
    assert 'action="/murid/paket/ganti"' in isi and 'name="kode" value="private"' in isi
    assert 'name="kode" value="mini"' not in isi.split("/murid/paket/ganti", 1)[1]   # hanya paket LAIN
    assert "Salah pilih paket?" in isi and "Jangan transfer ke tagihan yang lama" in isi


def test_ganti_berhasil_halaman_menampilkan_tagihan_baru_dan_bukti_masuk_ke_tagihan_baru(kidup, murid, jam):
    assert buat(kidup, murid, "mini")[0] == 303
    jam.maju_jam(1)
    kode, _isi, tajuk = ganti(kidup, murid, "private")
    assert (kode, tajuk["Location"]) == (303, M)
    assert _jumlah_order() == 2
    isi = _halaman(kidup, murid)
    assert "<h2>Private</h2>" in isi and "<h2>Mini Class</h2>" not in isi
    assert unggah(kidup, murid)[0] == 303
    baru = baca_admin("SELECT id FROM kelas_order WHERE paket='private'")[0]["id"]
    assert [b["order_id"] for b in baca_admin("SELECT order_id FROM kelas_bukti")] == [baru]
    assert "Salah pilih paket?" not in _halaman(kidup, murid)         # sudah ada bukti: tidak bisa ganti lagi


def test_ganti_ditolak_tanpa_efek(kidup, murid, jam):
    assert buat(kidup, murid, "mini")[0] == 303
    sebelum = hitung()
    jam.maju_jam(1)
    assert ganti(kidup, murid, "mini")[0] == 409                               # paket sama
    assert ganti(kidup, murid, "private", tok="salah")[0] == 403               # token salah
    assert ganti(kidup, murid, "paket-asing")[0] in (400, 403)                 # paket asing
    assert ganti(kidup, murid, "private", hapus=("kode",))[0] == 400           # form kurang
    assert ganti(kidup, murid, "private", ekstra={"nominal": "1"})[0] == 400   # field asing
    assert hitung() == sebelum


def test_ganti_setelah_bukti_ditolak_409(kidup, murid, jam):
    buat_dan_unggah(kidup, murid, "mini")
    jam.maju_jam(1)
    assert ganti(kidup, murid, "private")[0] == 409
    assert _jumlah_order() == 1


def test_ganti_dua_kali_beruntun_hanya_pertama_berhasil(kidup, murid, jam):
    assert buat(kidup, murid, "mini")[0] == 303
    jam.maju_jam(1)
    assert ganti(kidup, murid, "private")[0] == 303
    assert ganti(kidup, murid, "mini")[0] == 409
    assert _jumlah_order() == 2


def test_tanpa_tagihan_409_dan_sakelar_mati_404(kidup, murid, monkeypatch):
    assert ganti(kidup, murid, "private")[0] == 409
    monkeypatch.setenv("PAKET_BELAJAR", "0")
    acuan = buat(kidup, murid, "private")[0]            # rute paket lain saat sakelar mati: respons yang sama
    assert acuan != 303 and ganti(kidup, murid, "private")[0] == acuan
    assert _jumlah_order() == 0
