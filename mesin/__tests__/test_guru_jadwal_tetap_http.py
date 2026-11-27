"""Usulan jadwal tetap dari guru lewat HTTP (`/guru/jadwal-tetap`, WP2): gerbang, akses, token, formulir, batas, PRG.

Server HTTP sungguhan (`cek_http_kit.server`), data sepenuhnya sintetis di tmp_path. Gerbang dinyalakan lewat monkeypatch
`guru_jadwal_tetap_aturan.GURU_JADWAL_TETAP_AKTIF`; berkas DB dialihkan lewat env `GURU_JADWAL_TETAP_DB` ke tmp_path.
Tanpa jaringan dan tanpa data anak nyata.
"""
from __future__ import annotations

import hashlib
import http.cookies
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import auth
import form_token
import guru_jadwal_tetap_aturan as aturan
import guru_jadwal_tetap_dasar as dasar
import learning_cycle_http
import sessions
from cek_http_kit import AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, id_akun, minta_mentah, server  # noqa: F401
from harian_kit import jam  # noqa: F401

RUTE = "/guru/jadwal-tetap"
TIDAK_ADA = "/guru/tidak-ada"
KINI = "2026-11-23T03:00:00"  # 23 Nov 2026 pukul 10.00 WIB
DOMAIN_TOKEN = b"guru-jadwal-tetap-form-v1:"
DOMAIN_TUGAS = b"guru-tugas-form-v1:"
AKSI_USUL = "usul"
BLOK_SENIN = "1@480-600"  # Senin 08.00-10.00
BLOK_SELASA = "2@480-600"
BLOK_RABU = "3@960-1080"  # Rabu 16.00-18.00
JUDUL_SENIN = "Senin 08.00-10.00 WIB"
JUDUL_RABU = "Rabu 16.00-18.00 WIB"
KABAR_TERSIMPAN = "Usulan jadwal sudah diterima."
KABAR_TIDAK_BISA_BACA = "belum bisa dibaca"
POLA_TOKEN = re.compile(r'name="token" value="([^"]+)"')
POLA_SELECT = re.compile(r'<select id="([^"]+)" name="\1"[^>]*>(.*?)</select>', re.S)
POLA_OPSI = re.compile(r'<option value="([0-9]*)"( selected)?>')
ISIAN_TIDAK_SAH = [
    pytest.param({"h1a_m": "485", "h1a_s": "600"}, id="bukan-kelipatan-30"),
    pytest.param({"h1a_m": "480", "h1a_s": "510"}, id="kurang-dari-60-menit"),
    pytest.param({"h1a_m": "600", "h1a_s": "480"}, id="selesai-sebelum-mulai"),
    pytest.param({"h1a_m": "480", "h1a_s": ""}, id="salah-satu-terisi"),
    pytest.param({"h1a_m": "abc", "h1a_s": "600"}, id="bukan-bilangan"),
    pytest.param({"h1a_m": "480", "h1a_s": "600", "h1b_m": "540", "h1b_s": "660"}, id="beririsan"),
    pytest.param({"h7b_m": "1380", "h7b_s": "1470"}, id="melewati-akhir-hari"),
]


# --- fixture ----------------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def berkas_tetap(tmp_path, monkeypatch):
    """DB jadwal tetap di tmp_path; belum dibuat sampai tulis pertama. Pembatas laju dikosongkan per tes."""
    berkas = tmp_path / "guru-jadwal-tetap.db"
    monkeypatch.setenv(dasar.ENV_DB, str(berkas))
    monkeypatch.setattr(learning_cycle_http, "_riwayat", {})
    return berkas


@pytest.fixture()
def menyala(server, jam, monkeypatch):
    """Gerbang menyala dan jam dipatok ke KINI."""
    jam.nilai = KINI
    monkeypatch.setattr(aturan, "GURU_JADWAL_TETAP_AKTIF", True)
    return server


# --- util -------------------------------------------------------------------------------------

def _principal(akun):
    principal = sessions.principal_basic(*akun)
    assert principal is not None
    return principal


def _hash(berkas):
    """Hash isi berkas, atau None bila belum ada (tanpa membuatnya)."""
    berkas = Path(berkas)
    return hashlib.sha256(berkas.read_bytes()).hexdigest() if berkas.exists() else None


def _baris(berkas) -> list:
    """Baris tetap_usulan (guru, blok, asal, oleh) lewat koneksi ro. Berkas belum ada = daftar kosong."""
    if not Path(berkas).exists():
        return []
    uri = Path(berkas).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as kon:
        return kon.execute("SELECT guru_akun, blok, asal, oleh FROM tetap_usulan ORDER BY id").fetchall()


def _halaman(server, akun=AKUN_A) -> str:
    kode, isi, _ = server.minta(RUTE, auth=akun)
    assert kode == 200, kode
    return isi


def _token(isi: str) -> str:
    return POLA_TOKEN.search(isi).group(1)


def _kirim(server, data: dict, akun=AKUN_A):
    return minta_mentah(server, RUTE, akun, data)


def _formulir(token: str, isian: dict | None = None) -> dict:
    """28 field formulir (kosong = tidak ada blok) ditambah token. `isian` menimpa field tertentu."""
    kosong = {nama: "" for nama in aturan.KUNCI_FORM}
    return {"token": token, **kosong, **(isian or {})}


def _isian(hari: int, slot: str, mulai: int, selesai: int) -> dict:
    return {f"h{hari}{slot}_m": str(mulai), f"h{hari}{slot}_s": str(selesai)}


def _nilai_terpilih(isi_select: str) -> str:
    return next((nilai for nilai, terpilih in POLA_OPSI.findall(isi_select) if terpilih), "")


def _terpilih(isi: str) -> dict:
    """Nilai tiap `<select>` seperti yang dikirim peramban: opsi terpilih, atau kosong bila tak ada yang dipilih."""
    return {nama: _nilai_terpilih(isi_select) for nama, isi_select in POLA_SELECT.findall(isi)}


def _kuki_admin(server) -> str:
    kode, _isi, tajuk = minta_mentah(server, "/masuk", None, {"nama": AKUN_ADMIN[0], "sandi": AKUN_ADMIN[1]})
    assert kode == 303
    return http.cookies.SimpleCookie(tajuk["Set-Cookie"])["osn_sesi"].value


def _tetapkan_admin(blok: str) -> None:
    dasar.tetapkan_admin(guru_akun=id_akun(AKUN_A), blok=blok, admin_akun=id_akun(AKUN_ADMIN), dibuat=KINI)


def _usul_guru(blok: str) -> None:
    dasar.usul(guru_akun=id_akun(AKUN_A), blok=blok, dibuat=KINI)


def _isi_batas_harian() -> None:
    """Sepuluh usulan guru A dalam 24 jam sebelum KINI, berselang dua blok berbeda supaya tak ada yang no-op."""
    for nomor in range(aturan.BATAS_USULAN_PER_HARI):
        blok = BLOK_SENIN if nomor % 2 == 0 else BLOK_SELASA
        dasar.usul(guru_akun=id_akun(AKUN_A), blok=blok, dibuat=f"2026-11-23T01:{nomor:02d}:00")


def _acuan_tak_dikenal(server, akun):
    """Acuan 404 identik: GET rute tak dikenal dengan akun yang sama (sama seperti tes gerbang guru_tugas).

    POST ke rute tak dikenal tidak selalu berbadan sama dengan GET (admin Basic), jadi POST dibandingkan dengan GET.
    """
    return minta_mentah(server, TIDAK_ADA, akun)


# --- gerbang dan akses ------------------------------------------------------------------------

def test_gerbang_bawaan_mati():
    assert aturan.guru_jadwal_tetap_aktif() is False


def test_gerbang_mati_get_404_identik_dan_tanpa_berkas(server, berkas_tetap):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)

    kode, isi, _ = server.minta(RUTE, auth=AKUN_A)

    assert (kode, isi) == (acuan[0], acuan[1])
    assert not berkas_tetap.exists()


def test_gerbang_mati_post_404_identik_tanpa_efek_samping(server, berkas_tetap):
    data = _formulir("token-apa-pun", _isian(1, "a", 480, 600))
    acuan = _acuan_tak_dikenal(server, AKUN_A)

    kode, isi, _ = _kirim(server, data)

    assert (kode, isi) == (acuan[0], acuan[1])
    assert not berkas_tetap.exists()


@pytest.mark.parametrize("akun", [AKUN_ADMIN, AKUN_MURID, None], ids=["admin-basic", "murid", "anonim"])
def test_non_guru_get_sama_dengan_rute_tak_dikenal(menyala, akun):
    acuan = menyala.minta(TIDAK_ADA, auth=akun)

    kode, isi, _ = menyala.minta(RUTE, auth=akun)

    assert (kode, isi) == (acuan[0], acuan[1])


@pytest.mark.parametrize("akun", [AKUN_ADMIN, AKUN_MURID, None], ids=["admin-basic", "murid", "anonim"])
def test_non_guru_post_sama_dengan_rute_tak_dikenal_tanpa_tulis(menyala, berkas_tetap, akun):
    data = _formulir("token-apa-pun", _isian(1, "a", 480, 600))
    acuan = _acuan_tak_dikenal(menyala, akun)

    kode, isi, _ = minta_mentah(menyala, RUTE, akun, data)

    assert (kode, isi) == (acuan[0], acuan[1])
    assert not berkas_tetap.exists()


def test_admin_kuki_get_dan_post_sama_dengan_rute_tak_dikenal(menyala, berkas_tetap):
    kuki = {"Cookie": "osn_sesi=" + _kuki_admin(menyala)}
    data = _formulir("token-apa-pun", _isian(1, "a", 480, 600))
    acuan = minta_mentah(menyala, TIDAK_ADA, None, None, kuki)

    kode_get, isi_get, _ = minta_mentah(menyala, RUTE, None, None, kuki)
    kode_post, isi_post, _ = minta_mentah(menyala, RUTE, None, data, kuki)

    assert (kode_get, isi_get) == (acuan[0], acuan[1])
    assert (kode_post, isi_post) == (acuan[0], acuan[1])
    assert not berkas_tetap.exists()


def test_mode_lokal_get_dan_post_sama_dengan_rute_tak_dikenal(menyala, berkas_tetap, monkeypatch):
    monkeypatch.setattr(auth, "wajib_sandi", lambda: False)
    acuan = menyala.minta(TIDAK_ADA)

    kode_get, isi_get, _ = menyala.minta(RUTE)
    kode_post, isi_post, _ = minta_mentah(menyala, RUTE, None, _formulir("token-apa-pun", _isian(1, "a", 480, 600)))

    assert (kode_get, isi_get) == (acuan[0], acuan[1])
    assert (kode_post, isi_post) == (acuan[0], acuan[1])
    assert not berkas_tetap.exists()


# --- GET: isi halaman -------------------------------------------------------------------------

def test_guru_melihat_formulir_kosong_tanpa_jadwal(menyala, berkas_tetap):
    isi = _halaman(menyala)

    assert "Belum ada jadwal tetap" in isi
    assert 'name="token"' in isi
    assert not berkas_tetap.exists()


def test_formulir_memuat_tepat_28_field_dan_opsi_tidak_ada(menyala):
    isi = _halaman(menyala)

    assert set(_terpilih(isi)) == aturan.KUNCI_FORM
    assert len(aturan.KUNCI_FORM) == 28
    assert '<option value="">tidak ada</option>' in isi
    assert '<option value="480">08.00</option>' in isi


def test_tampil_aktif_dan_menunggu_dengan_isian_dari_menunggu(menyala):
    _tetapkan_admin(BLOK_SENIN)
    _usul_guru(BLOK_RABU)

    isi = _halaman(menyala)

    assert JUDUL_SENIN in isi
    assert JUDUL_RABU in isi
    assert "Menunggu penetapan admin" in isi
    terpilih = _terpilih(isi)
    assert terpilih["h3a_m"] == "960" and terpilih["h3a_s"] == "1080"
    assert terpilih["h1a_m"] == ""


def test_usulan_terakhir_ditolak_tampil_pesan(menyala):
    _usul_guru(BLOK_SENIN)
    usulan = dasar.menunggu(id_akun(AKUN_A))["usulan_id"]
    dasar.putus(usulan_id=usulan, putusan=dasar.PUTUSAN_TOLAK, admin_akun=id_akun(AKUN_ADMIN), dibuat=KINI)

    isi = _halaman(menyala)

    assert "Usulan terakhir ditolak admin" in isi
    assert "Menunggu penetapan admin" not in isi


def test_halaman_tanpa_id_mentah_dan_data_anak(menyala):
    _tetapkan_admin(BLOK_SENIN)
    _usul_guru(BLOK_RABU)

    isi = _halaman(menyala)

    for pola in ("akun_", "klp_", "kor_", "usulan_id", id_akun(AKUN_A)):
        assert pola not in isi


def test_pesan_tersimpan_dari_query_tampil_tanpa_gema(menyala):
    kode, isi, _ = menyala.minta(RUTE + "?pesan=tersimpan", auth=AKUN_A)
    assert kode == 200 and KABAR_TERSIMPAN in isi

    kode, isi, _ = menyala.minta(RUTE + "?pesan=%3Cscript%3E", auth=AKUN_A)
    assert kode == 200
    assert KABAR_TERSIMPAN not in isi
    assert "%3Cscript" not in isi and "&lt;script" not in isi


def test_galat_baca_tampil_halaman_aman_tanpa_formulir(menyala, monkeypatch):
    monkeypatch.setattr(dasar, "aktif", _gagal_baca)

    kode, isi, _ = menyala.minta(RUTE, auth=AKUN_A)

    assert kode == 200
    assert KABAR_TIDAK_BISA_BACA in isi
    assert 'name="token"' not in isi and 'name="h1a_m"' not in isi
    assert "galat rahasia" not in isi


def _gagal_baca(*_args, **_kwargs):
    raise dasar.GalatTetap(dasar.KIND_UMUM, "galat rahasia di /data/guru-jadwal-tetap.db")


def _gagal_umum(**_kwargs):
    raise dasar.GalatTetap(dasar.KIND_UMUM, "galat rahasia di /data/guru-jadwal-tetap.db")


# --- POST: sukses dan no-op -------------------------------------------------------------------

def test_post_sukses_menulis_satu_baris_guru_dan_tampil_menunggu(menyala, berkas_tetap):
    kode, _, tajuk = _kirim(menyala, _formulir(_token(_halaman(menyala)), _isian(1, "a", 480, 600)))

    assert kode == 303
    assert tajuk["Location"] == RUTE + "?pesan=tersimpan"
    guru = id_akun(AKUN_A)
    assert _baris(berkas_tetap) == [(guru, BLOK_SENIN, "guru", guru)]
    isi = _halaman(menyala)
    assert "Menunggu penetapan admin" in isi and JUDUL_SENIN in isi


def test_kirim_ulang_identik_tidak_menambah_baris(menyala, berkas_tetap):
    _kirim(menyala, _formulir(_token(_halaman(menyala)), _isian(1, "a", 480, 600)))

    kode, _, _ = _kirim(menyala, _formulir(_token(_halaman(menyala)), _isian(1, "a", 480, 600)))

    assert kode == 303
    assert len(_baris(berkas_tetap)) == 1


def test_halaman_terisi_lalu_kirim_ulang_tanpa_baris_baru(menyala, berkas_tetap):
    isian = {**_isian(1, "a", 480, 600), **_isian(3, "b", 960, 1080)}
    _kirim(menyala, _formulir(_token(_halaman(menyala)), isian))

    isi = _halaman(menyala)
    terpilih = _terpilih(isi)
    # Blok pertama tiap hari selalu tampil di slot `a` (urutan kanonik), jadi blok `b` tunggal pindah ke `a`.
    assert terpilih["h1a_m"] == "480" and terpilih["h3a_s"] == "1080"
    assert terpilih["h3b_m"] == ""

    kode, _, _ = _kirim(menyala, {"token": _token(isi), **terpilih})

    assert kode == 303
    assert len(_baris(berkas_tetap)) == 1


def test_kirim_aktif_saat_menunggu_berbeda_menjadi_usulan_baru(menyala, berkas_tetap):
    _tetapkan_admin(BLOK_SENIN)
    _usul_guru(BLOK_RABU)

    kode, _, _ = _kirim(menyala, _formulir(_token(_halaman(menyala)), _isian(1, "a", 480, 600)))

    assert kode == 303
    assert len(_baris(berkas_tetap)) == 3
    menunggu = dasar.menunggu(id_akun(AKUN_A))
    assert menunggu["blok"] == BLOK_SENIN


def test_nol_blok_usulan_kosong_menunggu_lalu_disetujui_mengosongkan(menyala):
    _tetapkan_admin(BLOK_SENIN)

    kode, _, _ = _kirim(menyala, _formulir(_token(_halaman(menyala))))

    assert kode == 303
    isi = _halaman(menyala)
    assert "Menunggu penetapan admin" in isi and JUDUL_SENIN in isi
    usulan = dasar.menunggu(id_akun(AKUN_A))["usulan_id"]
    dasar.putus(usulan_id=usulan, putusan=dasar.PUTUSAN_SETUJU, admin_akun=id_akun(AKUN_ADMIN), dibuat=KINI)
    isi = _halaman(menyala)
    assert "Jadwal tetap dikosongkan" in isi
    assert JUDUL_SENIN not in isi and "Belum ada jadwal tetap" not in isi


# --- POST: penolakan tanpa tulis --------------------------------------------------------------

def test_batas_harian_409_tanpa_baris_baru(menyala, berkas_tetap):
    _isi_batas_harian()
    sebelum = _hash(berkas_tetap)

    kode, _, _ = _kirim(menyala, _formulir(_token(_halaman(menyala)), _isian(3, "a", 960, 1080)))

    assert kode == 409
    assert _hash(berkas_tetap) == sebelum


def test_galat_umum_simpan_menjadi_503_tanpa_tulis(menyala, berkas_tetap, monkeypatch):
    monkeypatch.setattr(dasar, "usul", _gagal_umum)

    kode, isi, _ = _kirim(menyala, _formulir(_token(_halaman(menyala)), _isian(1, "a", 480, 600)))

    assert kode == 503
    assert "rahasia" not in isi and "/data" not in isi
    assert not berkas_tetap.exists()


def test_token_rusak_403_tanpa_tulis(menyala, berkas_tetap):
    kode, _, _ = _kirim(menyala, _formulir("token-rusak", _isian(1, "a", 480, 600)))

    assert kode == 403
    assert not berkas_tetap.exists()


def test_token_tanpa_field_403_tanpa_tulis(menyala, berkas_tetap):
    data = {nama: nilai for nama, nilai in _formulir(_token(_halaman(menyala))).items() if nama != "token"}

    kode, _, _ = _kirim(menyala, data)

    assert kode == 403
    assert not berkas_tetap.exists()


@pytest.mark.parametrize("domain,aksi", [
    pytest.param(DOMAIN_TUGAS, AKSI_USUL, id="domain-guru-tugas"),
    pytest.param(DOMAIN_TOKEN, "tetapkan:x", id="aksi-tetapkan"),
    pytest.param(DOMAIN_TOKEN, "putus:1:setuju", id="aksi-putus"),
])
def test_token_domain_atau_aksi_lain_403_tanpa_tulis(menyala, berkas_tetap, domain, aksi):
    token = form_token.buat_token(_principal(AKUN_A), None, domain=domain, aksi=aksi)

    kode, _, _ = _kirim(menyala, _formulir(token, _isian(1, "a", 480, 600)))

    assert kode == 403
    assert not berkas_tetap.exists()


def test_token_guru_lain_403_tanpa_tulis(menyala, berkas_tetap):
    token_b = _token(_halaman(menyala, AKUN_B))

    kode, _, _ = _kirim(menyala, _formulir(token_b, _isian(1, "a", 480, 600)), akun=AKUN_A)

    assert kode == 403
    assert not berkas_tetap.exists()


def test_field_berlebih_400_tanpa_tulis(menyala, berkas_tetap):
    data = {**_formulir(_token(_halaman(menyala))), "tambahan": "1"}

    kode, _, _ = _kirim(menyala, data)

    assert kode == 400
    assert not berkas_tetap.exists()


def test_field_kurang_400_tanpa_tulis(menyala, berkas_tetap):
    data = {nama: nilai for nama, nilai in _formulir(_token(_halaman(menyala))).items() if nama != "h7b_s"}

    kode, _, _ = _kirim(menyala, data)

    assert kode == 400
    assert not berkas_tetap.exists()


@pytest.mark.parametrize("isian", ISIAN_TIDAK_SAH)
def test_isian_tidak_sah_400_tanpa_tulis_dan_tanpa_gema(menyala, berkas_tetap, isian):
    kode, isi, _ = _kirim(menyala, _formulir(_token(_halaman(menyala)), isian))

    assert kode == 400
    assert "abc" not in isi
    assert not berkas_tetap.exists()


def test_hash_berkas_sama_pada_semua_penolakan(menyala, berkas_tetap):
    _usul_guru(BLOK_SENIN)
    sebelum = _hash(berkas_tetap)
    token = _token(_halaman(menyala))

    _kirim(menyala, _formulir("token-rusak", _isian(1, "a", 480, 600)))
    _kirim(menyala, _formulir(token, _isian(1, "a", 485, 600)))
    _kirim(menyala, {"token": token, "tambahan": "1"})

    assert _hash(berkas_tetap) == sebelum


def test_blok_disimpan_dalam_bentuk_kanonik_terurut_per_hari(menyala, berkas_tetap):
    isian = {**_isian(3, "a", 960, 1080), **_isian(1, "b", 600, 660), **_isian(1, "a", 480, 540)}

    kode, _, _ = _kirim(menyala, _formulir(_token(_halaman(menyala)), isian))

    assert kode == 303
    assert _baris(berkas_tetap)[-1][1] == "1@480-540;1@600-660;3@960-1080"


def test_laju_429_tanpa_tulis_setelah_batas_per_menit(menyala, berkas_tetap, monkeypatch):
    monkeypatch.setattr(learning_cycle_http, "_BATAS_PER_MENIT", 2)
    data = _formulir(_token(_halaman(menyala)), _isian(1, "a", 480, 600))
    _kirim(menyala, data)
    _kirim(menyala, data)
    sebelum = _hash(berkas_tetap)

    kode, isi, _ = _kirim(menyala, _formulir(_token(_halaman(menyala)), _isian(2, "a", 480, 600)))

    assert kode == 429
    assert "Coba lagi sebentar" in isi
    assert _hash(berkas_tetap) == sebelum
