"""Fase B launch publik: pendaftaran mandiri (pengelola + anak).

Kontrak:
1. GET /daftar tanpa sesi -> 200 form pendaftaran.
2. POST /daftar (nama+sandi+setuju) -> akun guru dibuat, auto-login
   (cookie sesi), 303 ke /.
3. Nama sudah dipakai -> galat jelas, TIDAK ada akun baru, TIDAK login.
4. Checkbox persetujuan tidak dicentang -> galat, tidak ada akun.
5. Sandi terlalu pendek -> galat, tidak ada akun.
6. Rate limit login (/masuk) tidak berubah; /daftar memakai jalur gagal
   yang sama bila ada.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402

SANDI_BARU = "sandi-panjang-ortu-123"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("admin-register", "sandi-admin-register-123", "admin")
    yield s
    s.berhenti()


def test_get_daftar_publik(server):
    kode, isi, _ = s_minta(server, "/daftar")
    assert kode == 200
    assert "daftar" in isi.lower()
    assert 'name="nama"' in isi
    assert 'name="sandi"' in isi
    assert 'name="setuju"' in isi  # checkbox persetujuan


def s_minta(server, jalur, **kw):
    return server.minta(jalur, **kw)


def test_post_daftar_membuat_akun_guru_dan_login(server):
    # PITFALL (dari skill): ServerUji.minta memakai urllib yang MENGIKUTI 303,
    # jadi POST redirect diterima sebagai 200 halaman tujuan. Untuk memeriksa
    # 303 + Set-Cookie, pakai opener tanpa redirect.
    import urllib.error
    import urllib.parse
    import urllib.request

    class TanpaIkut(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(TanpaIkut)
    halaman = server.minta("/daftar")[1]
    import re
    token_form = re.search(r'name="token_form" value="([^"]+)"', halaman).group(1)
    req = urllib.request.Request(
        server.alamat + "/daftar",
        data=urllib.parse.urlencode(
            {"nama": "orangtua-budi", "sandi": SANDI_BARU, "setuju": "1", "token_form": token_form}
        ).encode(),
        method="POST",
    )
    try:
        opener.open(req)
        kode, header = 200, {}
    except urllib.error.HTTPError as e:
        kode, header = e.code, dict(e.headers)
    assert kode == 303
    akun = auth.cari_akun("orangtua-budi")
    assert akun is not None
    assert akun.get("peran") == "guru"
    assert auth.periksa("orangtua-budi", SANDI_BARU)
    # auto-login: cookie sesi diberikan
    assert any("osn_sesi=" in v for k, v in header.items() if k.lower() == "set-cookie")



def test_post_daftar_lama_tanpa_token_ditolak(server):
    kode, isi, header = s_minta(
        server, "/daftar",
        data={"nama": "tanpa-token", "sandi": SANDI_BARU, "setuju": "1"},
    )
    assert kode in (400, 403)
    assert auth.cari_akun("tanpa-token") is None
    assert "Set-Cookie" not in header


def _token_daftar(server):
    import re
    return re.search(r'name="token_form" value="([^"]+)"', server.minta("/daftar")[1]).group(1)


def test_post_daftar_nama_duplikat_ditolak(server):
    token = _token_daftar(server)
    server.minta("/daftar", data={"nama": "budi", "sandi": SANDI_BARU, "setuju": "1", "token_form": token})
    assert auth.cari_akun("budi") is not None
    sebelum = auth.BERKAS_SANDI.read_bytes()
    kode, _, header = server.minta("/daftar", data={
        "nama": "BUDI", "sandi": "sandi-lain-panjang-999", "setuju": "1", "token_form": _token_daftar(server),
    })
    assert kode == 200
    assert auth.BERKAS_SANDI.read_bytes() == sebelum
    assert "Set-Cookie" not in header
    assert not auth.periksa("budi", "sandi-lain-panjang-999")


@pytest.mark.parametrize("ubah,nama", [
    ({"setuju": ""}, "tanpa-setuju"),
    ({"sandi": "pendek"}, "sandipendek"),
    ({"nama": "   "}, ""),
])
def test_post_daftar_validasi_asli_dengan_token_sah(server, ubah, nama):
    sebelum = auth.BERKAS_SANDI.read_bytes()
    kode, _, header = server.minta("/daftar", data={
        "nama": nama, "sandi": SANDI_BARU, "setuju": "1", "token_form": _token_daftar(server), **ubah,
    })
    assert kode == 200 and "Set-Cookie" not in header
    assert auth.BERKAS_SANDI.read_bytes() == sebelum
    assert auth.cari_akun(nama) is None
