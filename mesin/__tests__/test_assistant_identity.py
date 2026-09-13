"""Identitas akun/revisi stabil dan principal cookie terverifikasi."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import sessions  # noqa: E402


@pytest.fixture()
def berkas(tmp_path):
    return tmp_path / "sandi.json", tmp_path / "sesi.json"


def _buat_cookie(sesi, akun, *, pengguna=None, peran=None, id_akun=None, revisi=None):
    return sessions.buat(
        pengguna if pengguna is not None else akun["pengguna"],
        peran if peran is not None else akun["peran"],
        id_akun=id_akun if id_akun is not None else akun["id_akun"],
        revisi_auth=revisi if revisi is not None else akun["revisi_auth"],
        path=sesi,
    )


def test_akun_baru_revisi_satu_reset_naik_dan_id_stabil(berkas):
    sandi, _ = berkas
    auth.tambah_akun("Ortu", "sandi-awal-123", "guru", sandi)
    pertama = auth.cari_akun("ortu", sandi)

    assert pertama["revisi_auth"] == 1
    assert auth.setel_sandi_guru("ORTU", "sandi-baru-456", sandi)
    kedua = auth.cari_akun("ortu", sandi)

    assert auth.id_akun_sah(pertama["id_akun"])
    assert kedua["id_akun"] == pertama["id_akun"]
    assert kedua["revisi_auth"] == 2


def test_hapus_lalu_buat_username_sama_mendapat_id_baru(berkas):
    sandi, _ = berkas
    auth.tambah_akun("ortu", "sandi-awal-123", "guru", sandi)
    lama = auth.cari_akun("ortu", sandi)["id_akun"]
    assert auth.hapus_akun_guru("ortu", sandi)
    auth.tambah_akun("ORTU", "sandi-baru-456", "guru", sandi)
    assert auth.cari_akun("ortu", sandi)["id_akun"] != lama


def test_migrasi_lama_idempoten_mempertahankan_hash_dan_memberi_revisi_nol(berkas):
    sandi, _ = berkas
    sebelum = {"pengguna": "guru", **auth.buat_hash("rahasia-123")}
    sandi.write_text(json.dumps(sebelum), encoding="utf-8")

    assert auth.pastikan_metadata_auth(sandi) is True
    pertama = json.loads(sandi.read_text())
    assert auth.pastikan_metadata_auth(sandi) is False
    kedua = json.loads(sandi.read_text())

    assert pertama == kedua
    assert auth.id_akun_sah(pertama["id_akun"])
    assert pertama["revisi_auth"] == 0
    for kunci in ("pengguna", "garam", "kunci", "iterasi"):
        assert pertama[kunci] == sebelum[kunci]
    assert oct(sandi.stat().st_mode)[-3:] == "600"


def test_reader_multiakun_missing_peran_ditolak_sampai_migrasi(berkas):
    sandi, _ = berkas
    sandi.write_text(json.dumps({"akun": [{
        "pengguna": "legacy", **auth.buat_hash("sandi-legacy")
    }]}), encoding="utf-8")
    assert auth.muat_sandi(sandi) is None
    with pytest.raises(ValueError, match="peran akun tidak sah"):
        auth.pastikan_metadata_auth(sandi)


def test_bungkus_legacy_memindahkan_operasi_admin_ke_envelope(berkas):
    sandi, _ = berkas
    legacy = {
        "pengguna": "guru",
        "operasi_admin": {"op_sintetis": {"hasil_kode": "ok"}},
        **auth.buat_hash("sandi-guru"),
    }
    akun = [{**legacy, "peran": "guru"}]

    hasil = auth._bungkus_akun(legacy, akun)

    assert hasil["operasi_admin"] == legacy["operasi_admin"]
    assert "operasi_admin" not in hasil["akun"][0]


def test_migrasi_multiakun_menjaga_envelope_operasi_admin_dan_field(berkas):
    sandi, _ = berkas
    mentah = {
        "versi": 7,
        "operasi_admin": {"op_sintetis": {"hasil_kode": "ok"}},
        "akun": [
            {
                "pengguna": "ortu", "peran": "guru",
                "catatan": "tetap", **auth.buat_hash("sandi-ortu"),
            },
            {
                "pengguna": "anak", "peran": "murid", "siswa_id": 9,
                **auth.buat_hash("sandi-anak"),
            },
        ],
    }
    sandi.write_text(json.dumps(mentah), encoding="utf-8")

    assert auth.pastikan_metadata_auth(sandi)
    hasil = json.loads(sandi.read_text())

    assert hasil["versi"] == 7
    assert hasil["operasi_admin"] == mentah["operasi_admin"]
    assert hasil["akun"][0]["catatan"] == "tetap"
    assert hasil["akun"][1]["siswa_id"] == 9
    assert {akun["revisi_auth"] for akun in hasil["akun"]} == {0}
    assert len({akun["id_akun"] for akun in hasil["akun"]}) == 2


def test_migrasi_auth_tidak_berjalan_saat_read_principal(berkas):
    sandi, sesi = berkas
    data = {"pengguna": "guru", **auth.buat_hash("sandi-guru")}
    sandi.write_text(json.dumps(data), encoding="utf-8")
    sebelum = sandi.read_bytes()

    assert auth.autentikasi("guru", "sandi-guru", sandi) is None
    assert sessions.ambil_principal(
        "tidak-ada", path=sesi, path_akun=sandi
    ) is None
    assert sandi.read_bytes() == sebelum


def test_migrasi_null_rusak_dan_id_duplikat_tidak_mengubah_berkas(berkas):
    sandi, _ = berkas
    kasus = (
        b"null",
        b'{"akun": [rusak]}',
        json.dumps({"akun": [
            {"pengguna": "a", "peran": "guru", "id_akun": "akun_" + "a" * 32},
            {"pengguna": "b", "peran": "guru", "id_akun": "akun_" + "a" * 32},
        ]}).encode(),
    )
    for isi in kasus:
        sandi.write_bytes(isi)
        with pytest.raises(ValueError):
            auth.pastikan_metadata_auth(sandi)
        assert sandi.read_bytes() == isi


@pytest.mark.parametrize("nilai", ["zz", ""])
def test_hash_malformed_fail_closed_pada_auth_api(berkas, nilai):
    sandi, _ = berkas
    auth.tambah_akun("ortu", "sandi-awal-123", "guru", sandi)
    data = json.loads(sandi.read_text())
    data["akun"][0]["kunci"] = nilai
    sandi.write_text(json.dumps(data), encoding="utf-8")
    assert not auth.periksa(
        "ortu", "sandi-awal-123", data=data["akun"][0]
    )
    assert auth.autentikasi("ortu", "sandi-awal-123", sandi) is None


def test_sesi_baru_membawa_revisi_dan_principal_tervalidasi(berkas):
    sandi, sesi = berkas
    auth.tambah_akun("ortu", "sandi-awal-123", "guru", sandi)
    akun = auth.cari_akun("ortu", sandi)
    token = _buat_cookie(sesi, akun)

    principal = sessions.ambil_principal_pendamping(
        token, path=sesi, path_akun=sandi
    )
    assert principal is not None
    assert (principal.pengguna, principal.peran, principal.id_akun) == (
        "ortu", "guru", akun["id_akun"],
    )
    umum = sessions.ambil_principal(token, path=sesi, path_akun=sandi)
    assert umum is not None and umum.revisi_auth == 1


@pytest.mark.parametrize("field,nilai", [
    ("peran", "bos"),
    ("id_akun", "bukan-id"),
    ("revisi_auth", True),
    ("revisi_auth", -1),
    ("revisi_auth", "1"),
])
def test_reader_menolak_metadata_akun_malformed(berkas, field, nilai):
    sandi, _ = berkas
    auth.tambah_akun("ortu", "sandi-awal-123", "guru", sandi)
    data = json.loads(sandi.read_text())
    data["akun"][0][field] = nilai
    sandi.write_text(json.dumps(data), encoding="utf-8")
    assert auth.muat_sandi(sandi) is None
    assert auth.cari_akun("ortu", sandi) is None
    assert auth.autentikasi("ortu", "sandi-awal-123", sandi) is None


def test_reader_menolak_duplikasi_nama_casefold(berkas):
    sandi, _ = berkas
    hash_akun = auth.buat_hash("sandi-awal-123")
    sandi.write_text(json.dumps({"akun": [
        {
            "pengguna": "Ortu", "peran": "guru",
            "id_akun": "akun_" + "a" * 32, "revisi_auth": 1, **hash_akun,
        },
        {
            "pengguna": "ortu", "peran": "guru",
            "id_akun": "akun_" + "b" * 32, "revisi_auth": 1, **hash_akun,
        },
    ]}), encoding="utf-8")
    assert auth.muat_sandi(sandi) is None
    assert auth.autentikasi("ortu", "sandi-awal-123", sandi) is None


def test_cookie_lama_tanpa_id_atau_revisi_ditolak_semua_reader(berkas):
    sandi, sesi = berkas
    auth.tambah_akun("ortu", "sandi-awal-123", "guru", sandi)
    akun = auth.cari_akun("ortu", sandi)
    sesi.write_text(json.dumps({
        "tanpa-id": {"pengguna": "ortu", "peran": "guru", "kedaluarsa": 9_999_999_999},
        "tanpa-revisi": {
            "pengguna": "ortu", "peran": "guru", "id_akun": akun["id_akun"],
            "kedaluarsa": 9_999_999_999,
        },
    }), encoding="utf-8")

    for token in ("tanpa-id", "tanpa-revisi"):
        assert sessions.ambil(token, path=sesi, path_akun=sandi) is None
        assert sessions.ambil_principal_pendamping(
            token, path=sesi, path_akun=sandi
        ) is None


def test_cookie_malformed_revisi_ditolak(berkas):
    sandi, sesi = berkas
    auth.tambah_akun("ortu", "sandi-awal-123", "guru", sandi)
    akun = auth.cari_akun("ortu", sandi)
    sesi.write_text(json.dumps({"rusak": {
        "pengguna": akun["pengguna"], "peran": akun["peran"],
        "id_akun": akun["id_akun"], "revisi_auth": True,
        "kedaluarsa": 9_999_999_999,
    }}), encoding="utf-8")
    assert sessions.muat(sesi) == {}
    assert sessions.ambil_principal("rusak", path=sesi, path_akun=sandi) is None


def test_cookie_ditolak_setelah_reset_delete_dan_recreate(berkas):
    sandi, sesi = berkas
    auth.tambah_akun("ortu", "sandi-awal-123", "guru", sandi)
    akun = auth.cari_akun("ortu", sandi)
    token_reset = _buat_cookie(sesi, akun)
    assert auth.setel_sandi_guru("ortu", "sandi-baru-456", sandi)
    assert sessions.ambil(token_reset, path=sesi, path_akun=sandi) is None

    akun = auth.cari_akun("ortu", sandi)
    token_delete = _buat_cookie(sesi, akun)
    assert auth.hapus_akun_guru("ortu", sandi)
    assert sessions.ambil(token_delete, path=sesi, path_akun=sandi) is None

    auth.tambah_akun("ortu", "sandi-lagi-789", "guru", sandi)
    assert sessions.ambil(token_delete, path=sesi, path_akun=sandi) is None


def test_buat_dari_principal_menolak_snapshot_stale(berkas):
    sandi, sesi = berkas
    auth.tambah_akun("ortu", "sandi-awal-123", "guru", sandi)
    principal = auth.autentikasi("ortu", "sandi-awal-123", sandi)
    assert principal is not None
    assert auth.setel_sandi_guru("ortu", "sandi-baru-456", sandi)

    assert sessions.buat_dari_principal(
        principal, path=sesi, path_akun=sandi
    ) is None
    assert not sesi.exists()


def test_cookie_ditolak_setelah_pastikan_admin_mengubah_peran(berkas):
    sandi, sesi = berkas
    auth.tambah_akun("ortu", "sandi-awal-123", "guru", sandi)
    akun = auth.cari_akun("ortu", sandi)
    token = _buat_cookie(sesi, akun)

    assert auth.pastikan_admin(sandi) == "ortu"
    sesudah = auth.cari_akun("ortu", sandi)
    assert sesudah["id_akun"] == akun["id_akun"]
    assert sesudah["revisi_auth"] == akun["revisi_auth"] + 1
    assert sessions.ambil(token, path=sesi, path_akun=sandi) is None


def test_principal_menolak_id_peran_revisi_dan_case_tidak_cocok(berkas):
    sandi, sesi = berkas
    auth.tambah_akun("Ortu", "sandi-awal-123", "guru", sandi)
    akun = auth.cari_akun("ortu", sandi)
    token = (
        _buat_cookie(sesi, akun, id_akun="akun_" + "f" * 32),
        _buat_cookie(sesi, akun, peran="admin"),
        _buat_cookie(sesi, akun, revisi=akun["revisi_auth"] + 1),
        _buat_cookie(sesi, akun, pengguna="ortu"),
    )
    assert all(
        sessions.ambil_principal(item, path=sesi, path_akun=sandi) is None
        for item in token
    )


def test_pendamping_hanya_guru(berkas):
    sandi, sesi = berkas
    for nama, peran in (("anak", "murid"), ("pengelola", "admin")):
        auth.tambah_akun(nama, "sandi-awal-123", peran, sandi)
        token = _buat_cookie(sesi, auth.cari_akun(nama, sandi))
        assert sessions.ambil_principal_pendamping(
            token, path=sesi, path_akun=sandi
        ) is None


def test_cabut_akun_naikkan_revisi_dan_id_tetap(berkas):
    sandi, sesi = berkas
    auth.tambah_akun("ortu", "sandi-awal-123", "guru", sandi)
    akun = auth.cari_akun("ortu", sandi)
    token = _buat_cookie(sesi, akun)

    assert sessions.cabut_akun(akun["id_akun"], sandi) == 2
    sesudah = auth.cari_akun("ortu", sandi)
    assert sesudah["id_akun"] == akun["id_akun"]
    assert sesudah["revisi_auth"] == 2
    assert sessions.ambil(token, path=sesi, path_akun=sandi) is None


def test_basic_casefold_mengembalikan_username_kanonik(berkas):
    sandi, _ = berkas
    auth.tambah_akun("Ortu", "sandi-awal-123", "guru", sandi)
    principal = sessions.principal_basic("ortu", "sandi-awal-123", sandi)
    assert principal is not None
    assert principal.pengguna == "Ortu"
    assert principal.metode == "basic"


def test_case_username_tidak_membuat_id_kedua(berkas):
    sandi, _ = berkas
    auth.tambah_akun("Ortu", "sandi-awal-123", "guru", sandi)
    pertama = auth.cari_akun("ortu", sandi)["id_akun"]
    with pytest.raises(ValueError, match="sudah dipakai"):
        auth.tambah_akun("ORTU", "sandi-baru-456", "guru", sandi)
    assert auth.cari_akun("OrTu", sandi)["id_akun"] == pertama
