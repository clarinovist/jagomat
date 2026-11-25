"""Nonaktifkan/aktifkan guru (modul inti): penguncian lewat sinyal lama, revisi naik, tombstone tak bisa dibuka (25 Nov 2026; sintetis)."""
import pytest

import auth
import guru_status as S

SANDI = "sandi-sintetis-123"
KINI = 1_800_000_000


@pytest.fixture
def berkas(tmp_path):
    p = tmp_path / "sandi.json"
    for nama, peran in (("Admin-S", "admin"), ("Guru-S", "guru"), ("Guru-T", "guru"), ("Murid-S", "murid")):
        auth.tambah_akun(nama, SANDI, peran, p)
    return p


def _akun(p, nama):
    return auth.cari_akun(nama, p)


def _id(p, nama):
    return _akun(p, nama)["id_akun"]


def _nonaktifkan(p, nama="Guru-S"):
    a = _akun(p, nama)
    return S.nonaktifkan(a["id_akun"], auth.revisi_auth(a), _id(p, "Admin-S"), KINI, p)


def test_nonaktifkan_mengunci_login_dan_menaikkan_revisi(berkas):
    awal = auth.revisi_auth(_akun(berkas, "Guru-S"))
    assert auth.autentikasi("Guru-S", SANDI, berkas) is not None
    baru = _nonaktifkan(berkas)
    akun = _akun(berkas, "Guru-S")
    assert baru == awal + 1 == auth.revisi_auth(akun)
    assert akun["dinonaktifkan"] is True
    assert akun["nonaktif_admin"] == {"oleh": _id(berkas, "Admin-S"), "pada": KINI}
    assert auth.autentikasi("Guru-S", SANDI, berkas) is None
    assert auth.periksa_peran("Guru-S", SANDI, "guru", berkas) is False


def test_nonaktifkan_tidak_menyentuh_akun_lain_atau_kredensial(berkas):
    sebelum = {n: dict(_akun(berkas, n)) for n in ("Admin-S", "Guru-T", "Murid-S")}
    hash_guru = {k: v for k, v in _akun(berkas, "Guru-S").items() if k in ("hash", "garam", "iterasi", "algoritma")}
    _nonaktifkan(berkas)
    for nama, lama in sebelum.items():
        assert _akun(berkas, nama) == lama
    for k, v in hash_guru.items():
        assert _akun(berkas, "Guru-S")[k] == v
    assert auth.autentikasi("Guru-T", SANDI, berkas) is not None


def test_aktifkan_kembali_membuka_login_dengan_revisi_baru(berkas):
    awal = auth.revisi_auth(_akun(berkas, "Guru-S"))
    _nonaktifkan(berkas)
    a = _akun(berkas, "Guru-S")
    baru = S.aktifkan(a["id_akun"], auth.revisi_auth(a), berkas)
    akun = _akun(berkas, "Guru-S")
    assert baru == awal + 2 and "dinonaktifkan" not in akun and "nonaktif_admin" not in akun
    assert auth.autentikasi("Guru-S", SANDI, berkas) is not None


@pytest.mark.parametrize("nama", ["Admin-S", "Murid-S"])
def test_admin_dan_murid_ditolak_tanpa_efek(berkas, nama):
    sebelum = berkas.read_bytes()
    a = _akun(berkas, nama)
    with pytest.raises(S.StatusDitolak):
        S.nonaktifkan(a["id_akun"], auth.revisi_auth(a), _id(berkas, "Admin-S"), KINI, berkas)
    assert berkas.read_bytes() == sebelum


def test_id_tak_dikenal_atau_tak_sah_ditolak(berkas):
    sebelum = berkas.read_bytes()
    for id_akun in ("akun_" + "0" * 32, "bukan-id", ""):
        with pytest.raises(S.StatusDitolak):
            S.nonaktifkan(id_akun, 0, _id(berkas, "Admin-S"), KINI, berkas)
    assert berkas.read_bytes() == sebelum


def test_revisi_basi_menjadi_konflik_tanpa_efek(berkas):
    a = _akun(berkas, "Guru-S")
    sebelum = berkas.read_bytes()
    with pytest.raises(S.StatusBerubah):
        S.nonaktifkan(a["id_akun"], auth.revisi_auth(a) + 1, _id(berkas, "Admin-S"), KINI, berkas)
    assert berkas.read_bytes() == sebelum


def test_nonaktifkan_dua_kali_ditolak(berkas):
    _nonaktifkan(berkas)
    a = _akun(berkas, "Guru-S")
    sebelum = berkas.read_bytes()
    with pytest.raises(S.StatusDitolak):
        S.nonaktifkan(a["id_akun"], auth.revisi_auth(a), _id(berkas, "Admin-S"), KINI, berkas)
    assert berkas.read_bytes() == sebelum


def test_tombstone_tidak_bisa_diaktifkan_dan_tidak_dinilai_nonaktif_admin(berkas):
    from json_storage import transaksi_json
    with transaksi_json(berkas) as tujuan:
        mentah, akun, _ = auth._baca_akun_untuk_tulis(tujuan)
        target = next(a for a in akun if a["pengguna"] == "Guru-T")
        target["dinonaktifkan"] = True  # bentuk tombstone family_deletion: tanpa marka
        auth._tulis_akun_atomik(auth._bungkus_akun(mentah, akun), tujuan)
    a = _akun(berkas, "Guru-T")
    assert S.nonaktif_admin(a) is False
    sebelum = berkas.read_bytes()
    with pytest.raises(S.StatusDitolak):
        S.aktifkan(a["id_akun"], auth.revisi_auth(a), berkas)
    with pytest.raises(S.StatusDitolak):
        S.nonaktifkan(a["id_akun"], auth.revisi_auth(a), _id(berkas, "Admin-S"), KINI, berkas)
    assert berkas.read_bytes() == sebelum


def test_tombstone_bermarka_nonaktif_admin_tetap_tidak_bisa_diaktifkan():
    akun = {"pengguna": "keluarga_dihapus_" + "a" * 24, "peran": "guru", "dinonaktifkan": True,
            "nonaktif_admin": {"oleh": "admin", "pada": 1}}
    assert S.nonaktif_admin(akun) is False


def test_aktifkan_guru_aktif_ditolak(berkas):
    a = _akun(berkas, "Guru-S")
    with pytest.raises(S.StatusDitolak):
        S.aktifkan(a["id_akun"], auth.revisi_auth(a), berkas)


def test_marka_tidak_sah_tidak_dihitung_nonaktif_admin():
    dasar = {"pengguna": "x", "peran": "guru", "dinonaktifkan": True}
    assert S.nonaktif_admin({**dasar, "nonaktif_admin": {"oleh": "a", "pada": 1}}) is True
    for marka in (None, {}, {"oleh": "a"}, {"oleh": 1, "pada": 1}, {"oleh": "a", "pada": "1"}, "ya"):
        assert S.nonaktif_admin({**dasar, "nonaktif_admin": marka}) is False
    assert S.nonaktif_admin({"pengguna": "x", "peran": "guru", "nonaktif_admin": {"oleh": "a", "pada": 1}}) is False
    assert S.nonaktif_admin({**dasar, "peran": "admin", "nonaktif_admin": {"oleh": "a", "pada": 1}}) is False
