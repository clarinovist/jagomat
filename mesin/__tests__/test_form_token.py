"""Modul bersama `form_token`: token form HMAC berumur pendek.

Semua data sintetis: akun uji di tmp (sandi uji, bukan sandi asli). Waktu
dibekukan lewat `time.time`, jadi kedaluwarsa dibuktikan tanpa menunggu.
Bagian EKIVALENSI mengunci keluaran `kontak_http` byte-per-byte terhadap rumus
lama yang ditulis ulang di sini sebagai acuan independen.
"""
from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import form_token  # noqa: E402
import kontak_http  # noqa: E402
import sessions  # noqa: E402

DOMAIN_A = b"domain-uji-a:"
DOMAIN_B = b"domain-uji-b:"
DOMAIN_KONTAK = b"kontak-form-v1:"
DOMAIN_PESANAN = b"pesanan-form-v1:"
AKSI = "pertemuan:1"
SESI = "sesi-uji-1"
WAKTU_BEKU = 1_800_000_000.0
UMUR_KONTAK_LAMA = 900
ITERASI_UJI = 1000
AKUN_A = "guru-uji-a"
AKUN_B = "guru-uji-b"
SANDI_A = "sandi-uji-a-panjang"
SANDI_B = "sandi-uji-b-panjang"
ANGKA_ARAB = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


@pytest.fixture(scope="module")
def berkas_akun(tmp_path_factory):
    berkas = tmp_path_factory.mktemp("form-token") / "sandi.json"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(auth, "_ITERASI", ITERASI_UJI)
        auth.tambah_akun(AKUN_A, SANDI_A, "guru", path=berkas)
        auth.tambah_akun(AKUN_B, SANDI_B, "guru", path=berkas)
    return berkas


@pytest.fixture(autouse=True)
def berkas_sandi_uji(berkas_akun, monkeypatch):
    monkeypatch.setattr(auth, "BERKAS_SANDI", berkas_akun)


def _principal(pengguna: str, berkas: Path):
    akun = auth.cari_akun(pengguna, path=berkas)
    return sessions.Principal(
        pengguna=akun["pengguna"],
        peran=akun["peran"],
        id_akun=akun["id_akun"],
        revisi_auth=auth.revisi_auth(akun),
        metode="basic",
    )


@pytest.fixture()
def principal_a(berkas_akun):
    return _principal(AKUN_A, berkas_akun)


@pytest.fixture()
def principal_b(berkas_akun):
    return _principal(AKUN_B, berkas_akun)


def _bekukan_waktu(monkeypatch, detik: float) -> None:
    monkeypatch.setattr(time, "time", lambda: detik)


def _buat(principal, *, sesi=SESI, domain=DOMAIN_A, aksi=AKSI, umur=None) -> str:
    if umur is None:
        return form_token.buat_token(principal, sesi, domain=domain, aksi=aksi)
    return form_token.buat_token(principal, sesi, domain=domain, aksi=aksi, umur=umur)


def _sah(principal, token, *, sesi=SESI, domain=DOMAIN_A, aksi=AKSI) -> bool:
    return form_token.token_sah(principal, sesi, token, domain=domain, aksi=aksi)


def _ubah_satu_hex(tanda: str) -> str:
    ganti = "1" if tanda[-1] != "1" else "0"
    return tanda[:-1] + ganti


# --- roundtrip & pemisahan konteks -----------------------------------------

def test_token_yang_baru_dibuat_sah(monkeypatch, principal_a):
    # Arrange
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a)
    # Act
    hasil = _sah(principal_a, token)
    # Assert
    assert hasil is True


@pytest.mark.parametrize("aksi_lain", ["pertemuan:2", "pertemuan:10", "kontak"])
def test_aksi_berbeda_ditolak(monkeypatch, principal_a, aksi_lain):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a, aksi=AKSI)
    assert _sah(principal_a, token, aksi=AKSI) is True
    assert _sah(principal_a, token, aksi=aksi_lain) is False


def test_domain_berbeda_ditolak_walau_aksi_dan_akun_sama(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a, domain=DOMAIN_A)
    assert _sah(principal_a, token, domain=DOMAIN_A) is True
    assert _sah(principal_a, token, domain=DOMAIN_B) is False


def test_token_kontak_tidak_sah_di_domain_pesanan(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = kontak_http.buat_token(principal_a, SESI)
    assert _sah(principal_a, token, domain=DOMAIN_KONTAK, aksi="kontak") is True
    assert _sah(principal_a, token, domain=DOMAIN_PESANAN, aksi="kontak") is False


def test_akun_berbeda_ditolak(monkeypatch, principal_a, principal_b):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token_b = _buat(principal_b)
    assert _sah(principal_b, token_b) is True
    assert _sah(principal_a, token_b) is False


def test_sesi_berbeda_ditolak(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a, sesi=SESI)
    assert _sah(principal_a, token, sesi="sesi-uji-2") is False


def test_revisi_auth_berbeda_ditolak(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a)
    principal_baru = dataclasses.replace(principal_a, revisi_auth=principal_a.revisi_auth + 1)
    assert _sah(principal_baru, token) is False


def test_id_akun_berbeda_ditolak_walau_pengguna_sama(monkeypatch, principal_a, principal_b):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a)
    principal_palsu = dataclasses.replace(principal_a, id_akun=principal_b.id_akun)
    assert _sah(principal_palsu, token) is False


def test_akun_tidak_ditemukan_ditolak(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a)
    tidak_ada = dataclasses.replace(principal_a, pengguna="tidak-ada-di-berkas")
    assert _sah(tidak_ada, token) is False


def test_akun_hilang_menghasilkan_token_yang_tidak_sah(monkeypatch, principal_a):
    # Perilaku lama dipertahankan: akun tak ditemukan menghasilkan "<exp>.None"
    # (lihat laporan). Token itu tidak pernah lolos verifikasi.
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    tidak_ada = dataclasses.replace(principal_a, pengguna="tidak-ada-di-berkas")
    token = _buat(tidak_ada)
    assert token == f"{int(WAKTU_BEKU) + form_token.UMUR_BAWAAN_DETIK}.None"
    assert _sah(tidak_ada, token) is False


# --- kedaluwarsa -----------------------------------------------------------

def test_umur_bawaan_900_detik(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a)
    assert form_token.UMUR_BAWAAN_DETIK == 900
    assert token.partition(".")[0] == str(int(WAKTU_BEKU) + 900)


def test_umur_eksplisit_dihormati(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a, umur=60)
    assert token.partition(".")[0] == str(int(WAKTU_BEKU) + 60)
    _bekukan_waktu(monkeypatch, WAKTU_BEKU + 59)
    assert _sah(principal_a, token) is True
    _bekukan_waktu(monkeypatch, WAKTU_BEKU + 60)
    assert _sah(principal_a, token) is False


def test_satu_detik_sebelum_kedaluwarsa_masih_sah(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a)
    _bekukan_waktu(monkeypatch, WAKTU_BEKU + form_token.UMUR_BAWAAN_DETIK - 1)
    assert _sah(principal_a, token) is True


def test_tepat_di_detik_kedaluwarsa_ditolak(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a)
    _bekukan_waktu(monkeypatch, WAKTU_BEKU + form_token.UMUR_BAWAAN_DETIK)
    assert _sah(principal_a, token) is False


def test_token_kedaluwarsa_jauh_setelah_umur_ditolak(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = _buat(principal_a)
    _bekukan_waktu(monkeypatch, WAKTU_BEKU + form_token.UMUR_BAWAAN_DETIK + 5)
    assert _sah(principal_a, token) is False


# --- token dirusak ---------------------------------------------------------

def test_mac_dirusak_satu_hex_ditolak(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    awal, _, tanda = _buat(principal_a).partition(".")
    assert _sah(principal_a, f"{awal}.{_ubah_satu_hex(tanda)}") is False


def test_awal_kedaluwarsa_diubah_dengan_mac_lama_ditolak(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    awal, _, tanda = _buat(principal_a).partition(".")
    assert _sah(principal_a, f"{int(awal) + 1}.{tanda}") is False


TOKEN_MALFORMED = [
    pytest.param(None, id="none"),
    pytest.param(b"1800000900.abc", id="bytes"),
    pytest.param(12345, id="int"),
    pytest.param("", id="kosong"),
    pytest.param("1800000900." + "a" * 256, id="terlalu-panjang"),
    pytest.param("abc.deadbeef", id="awal-bukan-digit"),
    pytest.param(".deadbeef", id="awal-kosong"),
    pytest.param("1800000900", id="tanpa-titik"),
    pytest.param("٣.deadbeef", id="awal-digit-unicode-pendek"),
]


@pytest.mark.parametrize("token", TOKEN_MALFORMED)
def test_token_bentuk_tidak_sah_ditolak(monkeypatch, principal_a, token):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    assert _sah(principal_a, token) is False


@pytest.mark.parametrize("tanda", ["é", "a" * 63 + "é", "٣" * 64, "ÿ" * 8])
def test_tanda_non_ascii_ditolak_bukan_galat(monkeypatch, principal_a, tanda):
    """hmac.compare_digest melempar TypeError untuk str non-ASCII; token rusak harus ditolak, bukan menjatuhkan request."""
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    awal = _buat(principal_a).partition(".")[0]
    assert _sah(principal_a, f"{awal}.{tanda}") is False


def test_awal_digit_unicode_dengan_mac_sah_ditolak(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    awal, _, tanda = _buat(principal_a).partition(".")
    awal_arab = awal.translate(ANGKA_ARAB)
    assert int(awal_arab) == int(awal)
    assert _sah(principal_a, f"{awal_arab}.{tanda}") is False


# --- argumen ---------------------------------------------------------------

@pytest.mark.parametrize(
    "domain", [b"", "string-bukan-bytes", None, bytearray(b"domain-uji:")],
)
def test_domain_tidak_sah_ditolak_dengan_valueerror(principal_a, domain):
    with pytest.raises(ValueError):
        _buat(principal_a, domain=domain)
    with pytest.raises(ValueError):
        _sah(principal_a, "1800000900.abc", domain=domain)


@pytest.mark.parametrize("aksi", ["", None, 123])
def test_aksi_tidak_sah_ditolak_dengan_valueerror(principal_a, aksi):
    with pytest.raises(ValueError):
        _buat(principal_a, aksi=aksi)
    with pytest.raises(ValueError):
        _sah(principal_a, "1800000900.abc", aksi=aksi)


# --- ekivalensi dengan rumus kontak_http lama ------------------------------

def _rumus_lama_kontak(principal, sesi, kedaluwarsa: int) -> str:
    """Salinan rumus `kontak_http._mac` sebelum refactor (acuan independen)."""
    akun = auth.cari_akun(principal.pengguna)
    badan = json.dumps(
        [
            principal.id_akun,
            principal.revisi_auth,
            hashlib.sha256((sesi or "").encode()).hexdigest(),
            "kontak",
            kedaluwarsa,
        ],
        separators=(",", ":"),
    ).encode()
    mac = hmac.new(
        bytes.fromhex(akun["kunci"]), DOMAIN_KONTAK + badan, hashlib.sha256
    ).hexdigest()
    return f"{kedaluwarsa}.{mac}"


@pytest.mark.parametrize("sesi", [SESI, None, ""])
def test_kontak_http_buat_token_identik_dengan_rumus_lama(monkeypatch, principal_a, sesi):
    # Waktu pecahan: int() memotong, sama dengan rumus lama.
    _bekukan_waktu(monkeypatch, WAKTU_BEKU + 0.7)
    acuan = _rumus_lama_kontak(principal_a, sesi, int(WAKTU_BEKU) + UMUR_KONTAK_LAMA)
    assert kontak_http.buat_token(principal_a, sesi) == acuan


def test_kontak_http_token_sah_menerima_token_rumus_lama(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    acuan = _rumus_lama_kontak(principal_a, SESI, int(WAKTU_BEKU) + UMUR_KONTAK_LAMA)
    assert kontak_http.token_sah(principal_a, SESI, acuan) is True


def test_form_token_domain_kontak_sama_dengan_kontak_http(monkeypatch, principal_a):
    _bekukan_waktu(monkeypatch, WAKTU_BEKU)
    token = form_token.buat_token(
        principal_a, SESI, domain=DOMAIN_KONTAK, aksi="kontak",
        umur=kontak_http.UMUR_TOKEN_DETIK,
    )
    assert token == kontak_http.buat_token(principal_a, SESI)
