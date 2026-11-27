"""Orang tua memilih kelompok Mini sendiri lewat HTTP nyata (POST /murid/paket/jadwal; butir QA #4, 25 Nov 2026; data sintetis)."""
from __future__ import annotations

import re

import pytest

import admin_store
import jadwal_store as js
import kelas_putusan
import kelas_store
import schema_jadwal
from bukti_kit import JPEG, PNG
from kelas_http_kit import (ADMIN, AWAL, M, baca_admin, bukti_terakhir, buat, buat_dan_unggah, buat_murid,  # noqa: F401
                            halaman, jam, kidup, kirim, kmati, minta_mentah, server, token)

JADWAL = M + "/jadwal"
GURU = "akun_" + "9" * 32
LOKASI = "https://meet.google.com/rahasia-kelas-xyz"
JUDUL = "Pilih jadwal kelas"


@pytest.fixture()
def siap(kidup):  # noqa: F811
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    kidup.a = buat_murid(kidup, "murid-a", "Anak Alfa")
    kidup.b = buat_murid(kidup, "murid-b", "Anak Beta")
    return kidup


def _aktifkan(server, murid, kode="mini", isi=JPEG):
    order_id = buat_dan_unggah(server, murid, kode, isi)
    with kelas_store.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_putusan.setujui(kon, order_id, ADMIN, AWAL, bukti_dilihat=bukti_terakhir(order_id))
    return order_id


def _kelompok(nama="Mini A", kuota=5, tanggal="2026-11-24"):
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi=LOKASI, guru_id=GURU, kuota=kuota, tanggal=tanggal,
                                jam="09:00", sekarang=AWAL)


def _penempatan():
    return baca_admin("SELECT order_id,kelompok_id,dibuat_oleh FROM jadwal_penempatan")


def pilih(server, murid, kelompok_id, *, tok=None, ekstra=None, hapus=()):
    data = {"token": token(murid.akun, "jadwal_pilih:" + kelompok_id) if tok is None else tok, "kelompok": kelompok_id}
    data.update(ekstra or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return kirim(server, JADWAL, murid, data)


def teks(isi):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", isi.rsplit("</style>", 1)[-1]))


def test_kartu_pilih_jadwal_memuat_nama_waktu_sisa_tanpa_guru_atau_lokasi(siap):
    _aktifkan(siap, siap.a)
    kid = _kelompok()
    isi = halaman(siap, siap.a)
    t = teks(isi)
    assert JUDUL in t and "Mini A" in t and "24 November 2026 pukul 09.00 WIB" in t and "5 kursi" in t
    assert 'action="/murid/paket/jadwal"' in isi and kid in isi
    assert GURU not in isi and LOKASI not in isi


def test_tanpa_kelompok_terbuka_atau_tanpa_paket_aktif_tidak_ada_kartu(siap):
    assert JUDUL not in teks(halaman(siap, siap.a))             # belum punya paket
    _aktifkan(siap, siap.a)
    assert JUDUL not in teks(halaman(siap, siap.a))             # paket aktif tetapi belum ada kelompok


def test_private_tidak_ditawari_pilihan_kelompok(siap):
    _aktifkan(siap, siap.a, "private")
    _kelompok()
    assert JUDUL not in teks(halaman(siap, siap.a))


def test_pilih_berhasil_menempatkan_dan_kartu_berganti_jadwal(siap):
    order_id = _aktifkan(siap, siap.a)
    kid = _kelompok()
    kode, _isi, tajuk = pilih(siap, siap.a, kid)
    assert (kode, tajuk["Location"]) == (303, M)
    assert _penempatan() == [{"order_id": order_id, "kelompok_id": kid, "dibuat_oleh": siap.a.id_akun}]
    t = teks(halaman(siap, siap.a))
    assert JUDUL not in t and "Pertemuan 1 · 24 November 2026 pukul 09.00 WIB" in t


def test_pilih_ditolak_tanpa_efek(siap):
    _aktifkan(siap, siap.a)
    kid = _kelompok()
    assert pilih(siap, siap.a, kid, tok="salah")[0] == 403
    assert pilih(siap, siap.a, kid, tok=token(siap.a.akun, "jadwal_pilih:" + _kelompok("Mini B")))[0] == 403   # token kelompok lain
    assert pilih(siap, siap.a, "bukan-id", tok="x")[0] in (400, 403)
    assert pilih(siap, siap.a, kid, hapus=("kelompok",))[0] == 400
    assert pilih(siap, siap.a, kid, ekstra={"order": "kor_x"})[0] == 400
    assert pilih(siap, siap.a, "klp_" + "0" * 32)[0] == 404                                              # kelompok tak ada
    assert _penempatan() == []


def test_anak_lain_tanpa_paket_ditolak_dan_tidak_menyentuh_penempatan_orang_lain(siap):
    _aktifkan(siap, siap.a)
    kid = _kelompok()
    assert pilih(siap, siap.b, kid)[0] == 409                    # b tidak punya paket Mini aktif
    assert _penempatan() == []


def test_sudah_ditempatkan_admin_tidak_bisa_dipindah_sendiri(siap):
    order_id = _aktifkan(siap, siap.a)
    milik_admin, lain = _kelompok("Admin"), _kelompok("Lain")
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        js.tempatkan(kon, ADMIN, order_id, kelompok_id=milik_admin, sekarang=AWAL)
    assert pilih(siap, siap.a, lain)[0] == 409
    assert [p["kelompok_id"] for p in _penempatan()] == [milik_admin]


def test_kelompok_penuh_ditolak_409(siap, jam):  # noqa: F811
    _aktifkan(siap, siap.a)
    jam.maju_jam(1)
    _aktifkan(siap, siap.b, isi=PNG)          # berkas bukti kembar antar-akun ditolak
    kid = _kelompok(kuota=1)
    assert pilih(siap, siap.a, kid)[0] == 303
    assert pilih(siap, siap.b, kid)[0] == 409
    assert len(_penempatan()) == 1
    isi = halaman(siap, siap.b)                                  # kelompok penuh tampil sebagai "penuh", tanpa tombol
    assert JUDUL in teks(isi) and "Mini A" in teks(isi) and "penuh" in teks(isi)
    assert "Semua kelompok sedang penuh." in teks(isi) and "Pilih kelompok ini" not in teks(isi)
    assert 'action="/murid/paket/jadwal"' not in isi             # tanpa form pilih; hanya tombol daftar tunggu (F2c)
    assert 'action="/murid/paket/tunggu"' in isi


def test_sakelar_mati_rute_jadwal_menjawab_seperti_rute_lain(siap, monkeypatch):
    _aktifkan(siap, siap.a)
    kid = _kelompok()
    monkeypatch.setenv("PAKET_BELAJAR", "0")
    acuan = buat(siap, siap.a, "mini")[0]
    assert acuan != 303 and pilih(siap, siap.a, kid)[0] == acuan
    assert _penempatan() == []
