"""Test sesi: principal mutakhir, TTL, hapus, bersih, dan rate limit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import sessions  # noqa: E402


def _berkas(tmp_path):
    return tmp_path / "sandi.json", tmp_path / "sesi.json"


def _akun(tmp_path, pengguna="guru", peran="guru"):
    sandi, sesi = _berkas(tmp_path)
    auth.tambah_akun(pengguna, "sandi-sintetis-panjang", peran, path=sandi)
    akun = auth.cari_akun(pengguna, sandi)
    return sandi, sesi, akun


def _buat_valid(sesi, akun, *, sekarang=None):
    return sessions.buat(
        akun["pengguna"], akun["peran"], path=sesi, sekarang=sekarang,
        id_akun=akun["id_akun"], revisi_auth=akun["revisi_auth"],
    )


def test_buat_lalu_ambil(tmp_path):
    sandi, sesi, akun = _akun(tmp_path)
    token = _buat_valid(sesi, akun)
    assert sessions.ambil(token, path=sesi, path_akun=sandi) == ("guru", "guru")
    assert sessions.ambil(
        token, path=sesi, path_akun=sandi, sekarang=9_999_999_999
    ) is None
    assert sessions.ambil("salah", path=sesi, path_akun=sandi) is None


def test_buat_mewajibkan_id_dan_revisi_eksplisit(tmp_path):
    _, sesi, akun = _akun(tmp_path)
    for id_akun, revisi in (
        (None, None),
        (akun["id_akun"], None),
        (None, akun["revisi_auth"]),
        (akun["id_akun"], True),
        (akun["id_akun"], -1),
    ):
        try:
            sessions.buat(
                "guru", "guru", path=sesi,
                id_akun=id_akun, revisi_auth=revisi,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("sesi tanpa metadata eksplisit diterima")


def test_token_acak(tmp_path):
    _, sesi, akun = _akun(tmp_path)
    a = _buat_valid(sesi, akun)
    b = _buat_valid(sesi, akun)
    assert a != b


def test_kedaluarsa(tmp_path):
    sandi, sesi, akun = _akun(tmp_path, "feby", "murid")
    token = _buat_valid(sesi, akun, sekarang=1000.0)
    assert sessions.ambil(
        token, path=sesi, path_akun=sandi, sekarang=1000.0
    ) == ("feby", "murid")
    assert sessions.ambil(
        token, path=sesi, path_akun=sandi,
        sekarang=1000.0 + sessions.TTL_DETIK - 1,
    ) is not None
    assert sessions.ambil(
        token, path=sesi, path_akun=sandi,
        sekarang=1000.0 + sessions.TTL_DETIK + 1,
    ) is None


def test_hapus(tmp_path):
    sandi, sesi, akun = _akun(tmp_path)
    token = _buat_valid(sesi, akun)
    assert sessions.hapus(token, path=sesi) is True
    assert sessions.ambil(token, path=sesi, path_akun=sandi) is None
    assert sessions.hapus(token, path=sesi) is False


def test_bersihkan(tmp_path):
    sandi = tmp_path / "sandi.json"
    sesi = tmp_path / "sesi.json"
    akun = []
    for nama, peran in (("a", "murid"), ("b", "murid"), ("c", "guru")):
        auth.tambah_akun(nama, "sandi-sintetis-panjang", peran, path=sandi)
        akun.append(auth.cari_akun(nama, sandi))
    t1 = _buat_valid(sesi, akun[0], sekarang=0.0)
    t2 = _buat_valid(sesi, akun[1], sekarang=0.0)
    t3 = _buat_valid(sesi, akun[2])

    assert sessions.bersihkan(path=sesi) == 2
    assert sessions.ambil(t1, path=sesi, path_akun=sandi) is None
    assert sessions.ambil(t2, path=sesi, path_akun=sandi) is None
    assert sessions.ambil(t3, path=sesi, path_akun=sandi) == ("c", "guru")


def test_cookie_legacy_tanpa_revisi_ditolak(tmp_path):
    sandi, sesi, akun = _akun(tmp_path)
    sesi.write_text(json.dumps({
        "legacy": {
            "pengguna": akun["pengguna"],
            "peran": akun["peran"],
            "id_akun": akun["id_akun"],
            "kedaluarsa": 9_999_999_999,
        }
    }), encoding="utf-8")

    assert sessions.ambil("legacy", path=sesi, path_akun=sandi) is None
    assert not auth.muat_sandi(sandi).get("migrasi_otomatis")


def test_berkas_hilang_aman(tmp_path):
    p = tmp_path / "tidak-ada.json"
    assert sessions.muat(path=p) == {}
    assert sessions.ambil("apa pun", path=p, path_akun=tmp_path / "akun.json") is None
    assert sessions.hapus("apa pun", path=p) is False


def test_rate_limit(tmp_path):
    sessions._reset_rate_limit()
    for i in range(5):
        assert not sessions.sedang_diblokir("feby", "1.2.3.4", sekarang=1000.0 + i)
        sessions.catat_gagal("feby", "1.2.3.4", sekarang=1000.0 + i)
    assert sessions.sedang_diblokir("feby", "1.2.3.4", sekarang=1004.0)
    assert not sessions.sedang_diblokir("guru", "1.2.3.4", sekarang=1004.0)
    assert not sessions.sedang_diblokir("feby", "1.2.3.4", sekarang=2000.0)
    sessions._reset_rate_limit()
