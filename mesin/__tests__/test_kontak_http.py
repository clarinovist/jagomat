"""Halaman `/akun/kontak` (K3): guru melengkapi nomor WhatsApp akunnya sendiri.

Server HTTP sungguhan (`ServerUji`), semua data sintetis di tmp_path. Nomor uji
adalah nomor rekaan, bukan milik siapa pun. Yang dibuktikan: `id_akun` hanya dari
sesi server, field tak dikenal ditolak tanpa efek, murid/anonim/admin tidak
masuk, dan nomor tidak bocor ke URL, log, stdout/stderr, maupun akun lain.
"""
from __future__ import annotations

import logging
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import kontak_akun  # noqa: E402
import kontak_http  # noqa: E402
import registration_contact  # noqa: E402
import sessions  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji, _basic  # noqa: E402

RUTE = "/akun/kontak"
WA_A = "6281234567890"
WA_B = "6285551234567"
WA_B_MENTAH = "0855-5123-4567"
SANDI_GURU_B = "sandi-guru-b-panjang-123"
SANDI_ADMIN = "sandi-pengelola-k3-123"
POLA_TOKEN = re.compile(r'name="token" value="([^"]+)"')
AKUN_A = ("guru", SANDI_GURU)
AKUN_B = ("guru-b", SANDI_GURU_B)
AKUN_ADMIN = ("pengelola-k3", SANDI_ADMIN)
AKUN_MURID = ("feby", SANDI_MURID)


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    """Pertahankan 303 sebagai 303; status asli POST sukses."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _minta_tanpa_ikut(server, jalur, akun, data):
    isi = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(server.alamat + jalur, data=isi, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Authorization", _basic(*akun))
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
        finally:
            e.close()


@pytest.fixture()
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        auth.tambah_akun("guru-b", SANDI_GURU_B, "guru")
        auth.tambah_akun("pengelola-k3", SANDI_ADMIN, "admin")
        yield uji
    finally:
        uji.berhenti()


def _id_akun(akun) -> str:
    principal = sessions.principal_basic(*akun)
    assert principal is not None
    return principal.id_akun


def _kontak(server, akun):
    with server.buka() as kon:
        return kontak_akun.ambil(kon, _id_akun(akun))


def _jumlah_baris(server) -> int:
    with server.buka() as kon:
        return kon.execute("SELECT COUNT(*) FROM kontak_akun").fetchone()[0]


def _token(server, akun) -> str:
    kode, isi, _t = server.minta(RUTE, auth=akun)
    assert kode == 200
    cocok = POLA_TOKEN.search(isi)
    assert cocok, "form tidak membawa token"
    return cocok.group(1)


def _kirim(server, akun, wa, *, token=None, ekstra=None):
    data = {"token": _token(server, akun) if token is None else token, "wa": wa}
    data.update(ekstra or {})
    return _minta_tanpa_ikut(server, RUTE, akun, data)


# --- GET -------------------------------------------------------------------

def test_guru_melihat_form_kosong_dengan_copy_dan_token(server):
    kode, isi, tajuk = server.minta(RUTE, auth=AKUN_A)
    assert kode == 200
    assert 'action="/akun/kontak"' in isi
    assert 'name="wa"' in isi
    assert registration_contact.COPY_FUNNEL_WA in isi
    assert POLA_TOKEN.search(isi)
    assert "no-store" in tajuk.get("Cache-Control", "")
    assert re.search(r'name="wa"[^>]*value="[^"]', isi) is None


def test_halaman_tanpa_javascript(server):
    _kode, isi, _t = server.minta(RUTE, auth=AKUN_A)
    badan = isi.split("<body", 1)[1]
    assert "<script" not in badan
    assert "onclick" not in badan.lower()


def test_get_menampilkan_nomor_milik_sendiri_saja(server):
    assert _kirim(server, AKUN_A, WA_A)[0] == 303
    _k, isi_a, _t = server.minta(RUTE, auth=AKUN_A)
    assert f'value="{WA_A}"' in isi_a
    _k, isi_b, _t = server.minta(RUTE, auth=AKUN_B)
    assert WA_A not in isi_b


def test_pesan_sukses_hanya_dari_kode_tetap(server):
    sukses = "Nomor WhatsApp sudah disimpan."
    _k, polos, _t = server.minta(RUTE, auth=AKUN_A)
    assert sukses not in polos
    _k, isi, _t = server.minta(RUTE + "?pesan=tersimpan", auth=AKUN_A)
    assert sukses in isi
    _k, asing, _t = server.minta(RUTE + "?pesan=<b>x</b>", auth=AKUN_A)
    assert "<b>x</b>" not in asing


def test_trailing_slash_sama_dengan_rute(server):
    kode, isi, _t = server.minta(RUTE + "/", auth=AKUN_A)
    assert kode == 200 and 'name="wa"' in isi


# --- POST sah --------------------------------------------------------------

def test_post_sah_menyimpan_di_akun_sesi_dan_redirect_tanpa_nomor(server):
    kode, isi, tajuk = _kirim(server, AKUN_A, "0812 3456 7890")
    assert kode == 303
    lokasi = tajuk.get("Location", "")
    assert lokasi == "/akun/kontak?pesan=tersimpan"
    assert WA_A not in lokasi and "812" not in lokasi
    assert isi == ""
    baris = _kontak(server, AKUN_A)
    assert baris is not None and baris["wa"] == WA_A
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", baris["diperbarui"])
    assert _jumlah_baris(server) == 1


def test_post_sah_kedua_menimpa_nomor_akun_sendiri(server):
    _kirim(server, AKUN_A, WA_A)
    _kirim(server, AKUN_A, WA_B)
    assert _kontak(server, AKUN_A)["wa"] == WA_B
    assert _jumlah_baris(server) == 1


def test_rute_tidak_bergantung_sakelar_funnel(server, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "0")
    assert _kirim(server, AKUN_A, WA_A)[0] == 303
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    assert _kirim(server, AKUN_A, WA_B)[0] == 303
    assert _kontak(server, AKUN_A)["wa"] == WA_B


# --- kepemilikan -----------------------------------------------------------

def test_guru_a_tidak_bisa_mengubah_kontak_guru_b(server):
    _kirim(server, AKUN_B, WA_B)
    antes = _kontak(server, AKUN_B)
    _kirim(server, AKUN_A, WA_A)
    assert _kontak(server, AKUN_B) == antes
    assert _kontak(server, AKUN_A)["wa"] == WA_A
    assert _jumlah_baris(server) == 2


@pytest.mark.parametrize("nama_field", ["id_akun", "pemilik", "pengguna", "siswa_id"])
def test_field_tak_dikenal_ditolak_tanpa_efek(server, nama_field):
    id_b = _id_akun(AKUN_B)
    kode, isi, _t = _kirim(server, AKUN_A, WA_A, ekstra={nama_field: id_b})
    assert kode == 400
    assert WA_A not in isi
    assert _jumlah_baris(server) == 0


def test_id_akun_form_tidak_mengalihkan_tulis_ke_akun_lain(server):
    _kirim(server, AKUN_B, WA_B)
    antes = _kontak(server, AKUN_B)
    kode, _i, _t = _kirim(server, AKUN_A, WA_A, ekstra={"id_akun": _id_akun(AKUN_B)})
    assert kode == 400
    assert _kontak(server, AKUN_B) == antes
    assert _kontak(server, AKUN_A) is None


def test_field_wa_hilang_ditolak(server):
    kode, _i, _t = server.minta(
        RUTE, auth=AKUN_A, data={"token": _token(server, AKUN_A)}
    )
    assert kode == 400 and _jumlah_baris(server) == 0


def test_field_ganda_ditolak(server):
    token = _token(server, AKUN_A)
    isi = f"token={token}&wa={WA_A}&wa={WA_B}".encode()
    req = urllib.request.Request(server.alamat + RUTE, data=isi, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Authorization", _basic(*AKUN_A))
    with pytest.raises(urllib.error.HTTPError) as galat:
        urllib.request.urlopen(req, timeout=10)
    galat.value.close()
    assert galat.value.code == 400
    assert _jumlah_baris(server) == 0


# --- validasi --------------------------------------------------------------

@pytest.mark.parametrize(
    "wa", ["", "abc", "12345", "08123", "0212345678", "+1 555 123 4567", "628" + "1" * 13]
)
def test_wa_tidak_valid_ditolak_dan_tidak_tersimpan(server, wa):
    kode, isi, _t = _kirim(server, AKUN_A, wa)
    assert kode == 400
    assert registration_contact.PESAN_WA_WAJIB in isi
    assert _jumlah_baris(server) == 0


def test_wa_tidak_valid_tidak_menimpa_nomor_lama(server):
    _kirim(server, AKUN_A, WA_A)
    antes = _kontak(server, AKUN_A)
    kode, _i, _t = _kirim(server, AKUN_A, "0812")
    assert kode == 400
    assert _kontak(server, AKUN_A) == antes


def test_echo_ke_input_di_escape_dan_tidak_ke_galat(server):
    payload = '"><img src=x onerror=1>'
    kode, isi, _t = _kirim(server, AKUN_A, payload)
    assert kode == 400
    assert payload not in isi
    assert "&quot;&gt;&lt;img" in isi
    galat = re.search(r'role="alert">(.*?)</div>', isi, re.S).group(1)
    assert "img" not in galat


def test_halaman_galat_membawa_token_segar_yang_bisa_dipakai(server):
    _k, isi, _t = _kirim(server, AKUN_A, "0812")
    token = POLA_TOKEN.search(isi).group(1)
    assert _kirim(server, AKUN_A, WA_A, token=token)[0] == 303


# --- token form ------------------------------------------------------------

def test_token_salah_ditolak_tanpa_efek(server):
    kode, _i, _t = _kirim(server, AKUN_A, WA_A, token="1.deadbeef")
    assert kode == 403 and _jumlah_baris(server) == 0


def test_token_kosong_ditolak(server):
    kode, _i, _t = _kirim(server, AKUN_A, WA_A, token="")
    assert kode == 403 and _jumlah_baris(server) == 0


def test_token_guru_lain_tidak_berlaku(server):
    token_b = _token(server, AKUN_B)
    kode, _i, _t = _kirim(server, AKUN_A, WA_A, token=token_b)
    assert kode == 403
    assert _kontak(server, AKUN_A) is None


def test_token_kedaluwarsa_ditolak(server, monkeypatch):
    token = _token(server, AKUN_A)
    asli = time.time
    monkeypatch.setattr(kontak_http.time, "time", lambda: asli() + kontak_http.UMUR_TOKEN_DETIK + 5)
    kode, _i, _t = _kirim(server, AKUN_A, WA_A, token=token)
    assert kode == 403 and _jumlah_baris(server) == 0


def test_post_lintas_situs_ditolak_dispatcher(server):
    kode, _i, _t = server.minta(
        RUTE, auth=AKUN_A,
        data={"token": _token(server, AKUN_A), "wa": WA_A},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert kode == 403 and _jumlah_baris(server) == 0


# --- peran ------------------------------------------------------------------

def test_anonim_ditolak_get_dan_post(server):
    assert server.minta(RUTE)[0] == 401
    kode, isi, _t = server.minta(RUTE, data={"token": "x", "wa": WA_A})
    assert kode == 401 and "perlu masuk" in isi.lower()
    assert _jumlah_baris(server) == 0


def test_murid_ditolak_get_dan_post_tanpa_efek(server):
    _kirim(server, AKUN_A, WA_A)
    kode, isi, _t = server.minta(RUTE, auth=AKUN_MURID)
    assert kode == 401 and WA_A not in isi and "perlu masuk" in isi.lower()
    kode, isi, _t = server.minta(
        RUTE, auth=AKUN_MURID, data={"token": _token(server, AKUN_A), "wa": WA_B}
    )
    assert kode == 401 and WA_B not in isi
    assert _jumlah_baris(server) == 1


def test_admin_ditolak_dengan_404_identik_rute_tak_dikenal(server):
    """Admin tidak punya kontak pembayar: halaman ini tidak diakui, tanpa efek."""
    acuan = server.minta("/rute-tidak-ada", auth=AKUN_ADMIN)
    assert acuan[0] == 404
    get = server.minta(RUTE, auth=AKUN_ADMIN)
    assert (get[0], get[1]) == (acuan[0], acuan[1])
    post = server.minta(RUTE, auth=AKUN_ADMIN, data={"token": "x", "wa": WA_A})
    assert (post[0], post[1]) == (acuan[0], acuan[1])
    assert _jumlah_baris(server) == 0


def test_admin_tidak_bisa_memakai_token_guru(server):
    token = _token(server, AKUN_A)
    kode, _i, _t = server.minta(
        RUTE, auth=AKUN_ADMIN, data={"token": token, "wa": WA_A}
    )
    assert kode == 404 and _jumlah_baris(server) == 0


# --- nomor tidak bocor ------------------------------------------------------

def test_nomor_tidak_ada_di_log_stdout_stderr_dan_location(server, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    kode, _i, tajuk = _kirim(server, AKUN_A, WA_B_MENTAH)
    assert kode == 303
    kode, _i, tajuk_gagal = _kirim(server, AKUN_A, "0855-5123")
    assert kode == 400
    semua = capsys.readouterr()
    gabung = semua.out + semua.err + caplog.text + str(tajuk) + str(tajuk_gagal)
    for bentuk in (WA_B, WA_B_MENTAH, "5551234567", "0855-5123"):
        assert bentuk not in gabung


def test_nomor_tidak_tampil_di_halaman_akun_atau_peran_lain(server):
    _kirim(server, AKUN_A, WA_A)
    for jalur, akun in (("/akun", AKUN_A), ("/guru", AKUN_A), ("/akun", AKUN_ADMIN)):
        _k, isi, _t = server.minta(jalur, auth=akun)
        assert WA_A not in isi, jalur
    _k, isi, _t = server.minta("/murid", auth=AKUN_MURID)
    assert WA_A not in isi
