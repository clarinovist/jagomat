"""Kode lama yang sudah diganti atau dicabut orang tua tidak bisa diajukan guru: jawabannya identik dengan kode salah.

Lintas dua sisi: kode dibuat lewat `/murid/orang-tua/kode` (akun anak di balik PIN dan tirai), lalu guru mengajukan
kode lama, dan kode salah, ke `POST /guru/kelas/<klp>/tautan`. Status, Content-Type, Content-Length, dan badan harus
sama. Positive control: kode lama SEBELUM diganti/dicabut harus diterima, supaya penolakan berikutnya bermakna.
Data sintetis; DB tautan di tmp_path (`siapkan_db_tautan`).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import pin_orang_tua_store as pin_store
import tirai_orang_tua as tirai
from cek_http_kit import AKUN_A, ambil_token, minta_mentah, server  # noqa: F401  (fixture server)
from guru_tautan_kit import (JALUR_TAUTAN, LOGIN_ANAK, SANDI_ANAK, baris_tabel, siapkan_db_tautan,
                             siapkan_kelompok_dan_order)
from harian_kit import jam  # noqa: F401  (fixture jam: jam sintetis tetap)
from orang_tua_kode_kit import KODE_TAMPIL, RUTE, RUTE_KODE, form_kode, login, req

PIN = "4821"
KODE_SALAH = "2345-6789-ABCD-EFGH"
MASA_PIN = 1_800_000_000


@pytest.fixture
def anak(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("PAKET_BELAJAR", "1")
    tirai._reset()
    kondisi = siapkan_kelompok_dan_order(server)
    with server.buka() as kon:
        pin_store.simpan(kon, kondisi.siswa_id, PIN, MASA_PIN)
    yield kondisi, db
    tirai._reset()


def _buka_tirai(server) -> str:
    cookie = login(server, LOGIN_ANAK, SANDI_ANAK)
    kode_status, _, _ = req(server, RUTE + "/pin", data={"pin": PIN}, cookie=cookie)
    assert kode_status == 303
    return cookie


def _kode_dari_post(server, cookie, tindakan: str, **tambahan) -> str:
    masukan = form_kode(req(server, RUTE, cookie=cookie)[1], tindakan)
    data = {"tindakan": tindakan, "token": masukan["token"], **tambahan}
    if tindakan != "buat":
        data.setdefault("konfirmasi", "1")
    if "kode_id" in masukan:
        data.setdefault("kode_id", masukan["kode_id"])
    kode_status, isi, _ = req(server, RUTE_KODE, data=data, cookie=cookie)
    assert kode_status == 200, (tindakan, kode_status)
    return KODE_TAMPIL.findall(isi)[0]


def _cabut(server, cookie) -> None:
    masukan = form_kode(req(server, RUTE, cookie=cookie)[1], "cabut")
    kode_status, _, _ = req(server, RUTE_KODE,
                            data={"tindakan": "cabut", "kode_id": masukan["kode_id"], "token": masukan["token"], "konfirmasi": "1"},
                            cookie=cookie)
    assert kode_status == 200


def _ajukan_guru(server, kelompok_id: str, kode_mentah: str):
    tok = ambil_token(server, AKUN_A, f"/guru/kelas/{kelompok_id}")
    return minta_mentah(server, JALUR_TAUTAN.format(klp=kelompok_id), AKUN_A,
                        data={"kode": kode_mentah, "token": tok})


def _bentuk_jawaban(jawaban) -> tuple:
    kode_status, isi, header = jawaban
    return kode_status, isi, header.get("Content-Type"), header.get("Content-Length")


@pytest.mark.parametrize("tindakan", ["ganti", "cabut"])
def test_kode_lama_yang_sudah_diganti_atau_dicabut_identik_dengan_kode_salah(anak, server, tindakan):
    kondisi, db = anak
    cookie = _buka_tirai(server)
    kode_lama = _kode_dari_post(server, cookie, "buat")

    positif = _ajukan_guru(server, kondisi.kelompok_id, kode_lama)
    assert positif[0] == 200 and LOGIN_ANAK in positif[1]
    permintaan_sebelum = baris_tabel(db, "permintaan")

    if tindakan == "ganti":
        _kode_dari_post(server, cookie, "ganti")
    else:
        _cabut(server, cookie)
    lama = _ajukan_guru(server, kondisi.kelompok_id, kode_lama)
    salah = _ajukan_guru(server, kondisi.kelompok_id, KODE_SALAH)

    assert _bentuk_jawaban(lama) == _bentuk_jawaban(salah)
    assert lama[0] == 400 and LOGIN_ANAK not in lama[1]
    assert baris_tabel(db, "permintaan") == permintaan_sebelum
