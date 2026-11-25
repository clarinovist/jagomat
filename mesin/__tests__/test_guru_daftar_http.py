"""Guru mendaftar sendiri lewat /daftar?peran=guru (butir QA #5, 25 Nov 2026; data sintetis di tmp_path).

Pilihan rancangan: jalur yang sama dengan /daftar (query, bukan rute baru), akun guru TANPA profil anak, di balik gerbang env
DAFTAR_GURU (bawaan mati), tidak otomatis masuk lembaga mana pun, dibatasi laju per IP. Pemasukan ke lembaga tetap oleh admin.
"""
import re
import urllib.error
import urllib.parse
import urllib.request

import pytest

import admin_registration as reg
import admin_store
import auth
import database
import laju_masuk
import lembaga_store
from http_test_kit import ServerUji

GURU_PATH = "/daftar?peran=guru"


@pytest.fixture
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    for nama in ("DAFTAR_AKUN_ANAK", "OSN_LEMBAGA_ANTREAN", "FUNNEL_AKTIF", "DAFTAR_GURU"):
        monkeypatch.delenv(nama, raising=False)
    auth.tambah_akun("admin-sintetis", "sandi-admin-sintetis", "admin")
    reg.migrasikan_profil_registrasi(database.BAWAAN)
    laju_masuk._reset()
    yield s
    s.berhenti()
    laju_masuk._reset()


@pytest.fixture
def hidup(server, monkeypatch):
    monkeypatch.setenv("DAFTAR_GURU", "1")
    return server


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post(server, jalur, data):
    req = urllib.request.Request(
        server.alamat + jalur, data=urllib.parse.urlencode(data).encode(), method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as galat:
        return galat.code, galat.read().decode("utf-8", "replace"), dict(galat.headers)


def _form(server, path=GURU_PATH, **tambahan):
    kode, isi, _ = server.minta(path)
    assert kode == 200
    token = re.search(r'name="token_form" value="([^"]+)"', isi).group(1)
    data = dict(nama="bu-ratna", sandi="sandi-guru-sintetis", setuju="1", token_form=token)
    return {**data, **tambahan}


def _tanpa_akun(nama="bu-ratna"):
    assert auth.cari_akun(nama) is None


def _pesan(isi):
    cocok = re.search(r'id="pesan-daftar"[^>]*>(.*?)</div>', isi, re.S)
    return cocok.group(1) if cocok else ""


# --- gerbang ---------------------------------------------------------------

def test_gerbang_mati_get_tidak_menampilkan_form_guru_dan_post_tidak_membuat_akun(server, monkeypatch):
    kode, isi, _ = server.minta(GURU_PATH)
    assert kode == 200 and 'name="sandi"' not in isi and "belum dibuka" in isi.lower()
    monkeypatch.setenv("DAFTAR_GURU", "1")
    data = _form(server)
    monkeypatch.setenv("DAFTAR_GURU", "0")
    kode, isi, _ = _post(server, GURU_PATH, data)
    assert kode in (403, 503) and "belum dibuka" in isi.lower()
    _tanpa_akun()


@pytest.mark.parametrize("nilai", ["", "0", "true", "yes", "1 ", "2", "1"])
def test_hanya_nilai_persis_1_membuka_gerbang(server, monkeypatch, nilai):
    import guru_daftar_gate
    monkeypatch.setenv("DAFTAR_GURU", nilai)
    assert guru_daftar_gate.aktif() is (nilai == "1")


def test_sakelar_admin_menang_atas_env(server, monkeypatch, tmp_path):
    import feature_switch
    import guru_daftar_gate
    import sakelar_registry
    db = tmp_path / "sakelar-guru.db"
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(db))
    monkeypatch.setenv("DAFTAR_GURU", "1")
    feature_switch.bersihkan_cache()
    assert guru_daftar_gate.aktif() is True                      # belum ada baris DB: env jadi fallback
    feature_switch.ubah("DAFTAR_GURU", False, actor_id="admin-sintetis", revisi_diharapkan=1,
                        seed=sakelar_registry.seed_env())
    assert guru_daftar_gate.aktif() is False                     # baris DB menang atas env
    assert server.minta(GURU_PATH)[1].count('name="sandi"') == 0
    feature_switch.ubah("DAFTAR_GURU", True, actor_id="admin-sintetis", revisi_diharapkan=2,
                        seed=sakelar_registry.seed_env())
    monkeypatch.delenv("DAFTAR_GURU")
    assert guru_daftar_gate.aktif() is True                      # DB hidup tanpa env
    assert 'name="sandi"' in server.minta(GURU_PATH)[1]
    feature_switch.bersihkan_cache()


def test_gerbang_hidup_get_menampilkan_form_guru_tanpa_isian_anak(hidup):
    kode, isi, _ = hidup.minta(GURU_PATH)
    assert kode == 200
    assert 'name="nama"' in isi and 'name="sandi"' in isi and 'name="token_form"' in isi
    assert 'name="setuju"' in isi and "peran=guru" in isi
    for terlarang in ('name="nama_anak"', 'name="nama_lengkap"', 'name="wa"', 'name="pin"'):
        assert terlarang not in isi


def test_daftar_biasa_dan_peran_lain_tidak_berubah(hidup):
    for jalur in ("/daftar", "/daftar?peran=admin", "/daftar?peran=guru&peran=admin", "/daftar?peran=GURU"):
        kode, isi, _ = hidup.minta(jalur)
        assert kode == 200 and 'name="nama_anak"' in isi, jalur           # form lama utuh, tanpa eskalasi


# --- pendaftaran -----------------------------------------------------------

def test_daftar_membuat_akun_guru_tanpa_profil_anak_dan_sesi_masuk(hidup):
    kode, _, header = _post(hidup, GURU_PATH, _form(hidup))
    assert kode == 303 and header["Location"] in ("/guru", "/persetujuan") and "Set-Cookie" in header
    akun = auth.cari_akun("bu-ratna")
    assert akun["peran"] == "guru"
    with hidup.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM siswa").fetchone()[0] == 0
    kuki = header["Set-Cookie"].split(";")[0]
    kode, _, _ = hidup.minta("/guru", cookie=kuki.split("=", 1)[1])
    assert kode in (200, 303)


def test_guru_baru_tidak_otomatis_masuk_lembaga_mana_pun(hidup):
    with hidup.buka() as kon:
        lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik="admin-sintetis")
    _post(hidup, GURU_PATH, _form(hidup))
    with hidup.buka() as kon:
        assert "bu-ratna" not in lembaga_store.guru_terikat(kon)
        assert all("bu-ratna" not in anggota for _, anggota in lembaga_store.daftar_lembaga(kon))


@pytest.mark.parametrize("ubah,pesan", [
    ({"nama": ""}, "Nama"),
    ({"sandi": "pendek"}, "minimal 8"),
    ({"setuju": "0"}, "persetujuan"),
])
def test_isian_tidak_sah_ditolak_tanpa_akun(hidup, ubah, pesan):
    kode, isi, _ = _post(hidup, GURU_PATH, _form(hidup, **ubah))
    assert kode == 200 and pesan.lower() in _pesan(isi).lower()
    _tanpa_akun()
    assert auth.cari_akun("") is None


@pytest.mark.parametrize("asing", [{"nama_anak": "Anak"}, {"wa": "0812"}, {"jalur": "cek"}, {"peran": "admin"}, {"pin": "1234"}])
def test_field_asing_ditolak_tanpa_akun(hidup, asing):
    kode, _, _ = _post(hidup, GURU_PATH, _form(hidup, **asing))
    assert kode in (200, 400)
    _tanpa_akun()


def test_token_form_salah_atau_hilang_ditolak(hidup):
    kode, _, _ = _post(hidup, GURU_PATH, _form(hidup, token_form="x" * 64))
    assert kode in (400, 403)
    data = _form(hidup)
    data.pop("token_form")
    assert _post(hidup, GURU_PATH, data)[0] in (200, 400)
    _tanpa_akun()


def test_nama_sudah_dipakai_ditolak_tanpa_akun_kedua(hidup):
    assert _post(hidup, GURU_PATH, _form(hidup))[0] == 303
    kode, isi, _ = _post(hidup, GURU_PATH, _form(hidup))
    assert kode == 200 and "sudah dipakai" in _pesan(isi)
    assert len([a for a in auth.muat_sandi(auth.BERKAS_SANDI)["akun"] if a["pengguna"] == "bu-ratna"]) == 1


def test_kirim_ulang_token_yang_sama_idempoten_tanpa_akun_ganda(hidup):
    data = _form(hidup)
    assert _post(hidup, GURU_PATH, data)[0] == 303
    kode, _, _ = _post(hidup, GURU_PATH, data)
    assert kode in (200, 303)
    assert len([a for a in auth.muat_sandi(auth.BERKAS_SANDI)["akun"] if a["pengguna"] == "bu-ratna"]) == 1


def test_pendaftaran_ditutup_admin_ditolak(hidup, monkeypatch):
    data = _form(hidup)
    asli = admin_store.baca_konfigurasi

    def ditutup(path):
        nilai = asli(path)
        return type(nilai)(**{**nilai._asdict(), "dibuka": False}) if hasattr(nilai, "_asdict") else (
            type(nilai)(**{**vars(nilai), "dibuka": False}))

    monkeypatch.setattr(admin_store, "baca_konfigurasi", ditutup)
    kode, isi, _ = _post(hidup, GURU_PATH, data)
    assert kode == 403 and "ditutup" in isi.lower()
    _tanpa_akun()


def test_laju_per_ip_menutup_keran_setelah_lima_akun(hidup):
    for n in range(laju_masuk.BATAS_GAGAL):
        assert _post(hidup, GURU_PATH, _form(hidup, nama="guru-%d" % n))[0] == 303
    kode, _, _ = _post(hidup, GURU_PATH, _form(hidup, nama="guru-baru"))
    assert kode == 429
    _tanpa_akun("guru-baru")
