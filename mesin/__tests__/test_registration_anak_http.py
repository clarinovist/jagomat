"""/daftar mode anak (F2a) lewat HTTP nyata: sakelar, fail-closed, validasi form, sesi murid, login ulang.

Data sintetis di tmp_path. Sakelar dinyalakan lewat env (fallback; DB sakelar tidak ada).
"""
import re
import urllib.error
import urllib.parse
import urllib.request

import pytest

import admin_registration as reg
import auth
import cek_gratis_skor
import database
import lembaga_store
import pin_orang_tua_store
from http_test_kit import ServerUji

WA = "0812-3456-7890"
WA_NORMAL = "6281234567890"
KOORDINATOR = "koordinator-jagomat"


@pytest.fixture
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.delenv("DAFTAR_AKUN_ANAK", raising=False)
    monkeypatch.delenv("OSN_LEMBAGA_ANTREAN", raising=False)
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    auth.tambah_akun("admin-sintetis", "sandi-admin-sintetis", "admin")
    auth.tambah_akun(KOORDINATOR, "sandi-koordinator-sintetis", "guru")
    reg.migrasikan_profil_registrasi(database.BAWAAN)
    with s.buka() as kon:
        s.lembaga_id = lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik=KOORDINATOR)
    yield s
    s.berhenti()


@pytest.fixture
def mode_anak(server, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", str(server.lembaga_id))


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


def _form(server, jalur="/daftar", **tambahan):
    kode, isi, _ = server.minta(jalur)
    assert kode == 200
    token = re.search(r'name="token_form" value="([^"]+)"', isi).group(1)
    data = dict(nama="raka-login", sandi="sandi-anak-sintetis", nama_lengkap="Raka Pratama Sintetis",
                kelas_sekolah="4", wa=WA, setuju="1", pin="4821", pin_ulang="4821", token_form=token)
    return {**data, **tambahan}


def _keadaan(server):
    with server.buka() as kon:
        siswa = [tuple(b) for b in kon.execute("SELECT nama, pemilik FROM siswa")]
        tabel = {t: kon.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in (
            "kontak_akun", "persetujuan_daftar_anak", "pin_orang_tua", "registrasi_profil_anak")}
    return siswa, tabel


def _tanpa_efek(server, nama="raka-login"):
    siswa, tabel = _keadaan(server)
    assert siswa == [] and set(tabel.values()) == {0}
    assert auth.cari_akun(nama) is None
    assert auth.muat_sandi(auth.BERKAS_SANDI).get("registrasi_profil", {}) == {}


def _pesan(isi):
    cocok = re.search(r'id="pesan-daftar"[^>]*>(.*?)</div>', isi, re.S)
    return cocok.group(1) if cocok else ""


def _kuki(header):
    return header["Set-Cookie"].split(";")[0]


# --- (a) sakelar mati = alur lama ------------------------------------------

def test_sakelar_mati_get_dan_post_tetap_alur_akun_guru(server, monkeypatch):
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", str(server.lembaga_id))  # lembaga siap tidak mengubah apa pun
    kode, isi, _ = server.minta("/daftar")
    assert kode == 200 and 'name="nama_anak"' in isi and 'name="nama_lengkap"' not in isi
    token = re.search(r'name="token_form" value="([^"]+)"', isi).group(1)
    kode, _, header = _post(server, "/daftar", dict(
        nama="ortu-lama", sandi="sandi-ortu-sintetis", setuju="1", token_form=token, nama_anak="Panggilan",
        kelas_sekolah="4"))
    assert kode == 303 and header["Location"].startswith("/anak/")
    assert auth.cari_akun("ortu-lama")["peran"] == "guru"
    siswa, tabel = _keadaan(server)
    assert siswa == [("Panggilan", "ortu-lama")] and tabel["persetujuan_daftar_anak"] == 0


def test_mode_anak_menolak_field_form_lama_nama_anak(server, mode_anak):
    data = _form(server, nama_anak="Panggilan")
    kode, _, header = _post(server, "/daftar", data)
    assert kode == 400 and "Set-Cookie" not in header
    _tanpa_efek(server)


# --- form -------------------------------------------------------------------

def test_get_mode_anak_menampilkan_field_form_baru(server, mode_anak):
    kode, isi, _ = server.minta("/daftar")
    assert kode == 200
    for nama in ("nama", "sandi", "nama_lengkap", "kelas_sekolah", "wa", "setuju", "pin", "pin_ulang", "token_form"):
        assert 'name="%s"' % nama in isi, nama
    assert "Nama login anak" in isi and "Nama lengkap anak" in isi and 'name="nama_anak"' not in isi
    assert re.search(r'<input[^>]*name="sandi"[^>]*type="password"|<input type="password"[^>]*name="sandi"', isi)
    assert re.search(r'<input[^>]*name="nama_lengkap"[^>]*maxlength="80"', isi) is not None


def test_get_jalur_cek_mode_anak_memakai_form_yang_sama(server, mode_anak, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    _, isi, _ = server.minta("/daftar?jalur=cek")
    assert 'name="nama_lengkap"' in isi and 'name="wa"' in isi


# --- (c) fail-closed ---------------------------------------------------------

@pytest.mark.parametrize("env", [None, "", "0", "abc", "9999", "01"])
def test_sakelar_hidup_tanpa_lembaga_antrean_ditolak_jujur_tanpa_menulis(server, monkeypatch, env):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    if env is not None:
        monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", env)
    kode, isi, _ = server.minta("/daftar")
    assert kode == 503 and "Pendaftaran sementara belum dibuka." in isi and "<form" not in isi
    kode, isi, header = _post(server, "/daftar", dict(
        nama="raka-login", sandi="sandi-anak-sintetis", nama_lengkap="Raka", kelas_sekolah="4", wa=WA, setuju="1",
        token_form="x" * 64))
    assert kode == 503 and "Pendaftaran sementara belum dibuka." in isi and "Set-Cookie" not in header
    _tanpa_efek(server)


def test_tanpa_lembaga_tidak_jatuh_ke_alur_guru_meski_form_lama_dikirim(server, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    kode, _, header = _post(server, "/daftar", dict(
        nama="ortu-lama", sandi="sandi-ortu-sintetis", setuju="1", token_form="x" * 64, nama_anak="P"))
    assert kode == 503 and "Set-Cookie" not in header
    assert auth.cari_akun("ortu-lama") is None


def test_koordinator_tanpa_akun_guru_ditolak_503_tanpa_menulis(server, mode_anak):
    data = _form(server)
    mentah = auth.muat_sandi(auth.BERKAS_SANDI)
    akun = [a for a in mentah["akun"] if a["pengguna"] != KOORDINATOR]
    auth.BERKAS_SANDI.write_text(__import__("json").dumps({**mentah, "akun": akun}))
    kode, isi, header = _post(server, "/daftar", data)
    assert kode == 503 and "Pendaftaran sementara belum dibuka." in isi and "Set-Cookie" not in header
    _tanpa_efek(server)


# --- (f) validasi tanpa tulis -------------------------------------------------

@pytest.mark.parametrize("ubah,potongan", [
    (dict(pin="4821", pin_ulang="4822"), "PIN dan ulangannya belum sama"),
    (dict(pin="48", pin_ulang="48"), "PIN harus 4 angka"),
    (dict(pin="abcd", pin_ulang="abcd"), "PIN harus 4 angka"),
    (dict(pin="", pin_ulang="4821"), "PIN harus 4 angka"),
    (dict(nama_lengkap=""), "Nama lengkap anak wajib diisi"),
    (dict(nama_lengkap="   "), "Nama lengkap anak wajib diisi"),
    (dict(nama_lengkap="A" * 81), "maksimal 80 karakter"),
    (dict(nama_lengkap="Raka\x07Uji"), "Nama lengkap anak tidak sah"),
    (dict(wa="12345"), "nomor WhatsApp"),
    (dict(wa=""), "nomor WhatsApp"),
    (dict(kelas_sekolah=""), "Pilih kelas anak"),
    (dict(kelas_sekolah="7"), None),
    (dict(setuju="0"), "persetujuan"),
    (dict(nama=""), "Nama login anak wajib"),
    (dict(sandi="pendek"), "minimal 8 karakter"),
    (dict(nama="ab"), "Nama login hanya boleh"),
    (dict(nama="nama spasi"), "Nama login hanya boleh"),
])
def test_validasi_form_ditolak_tanpa_menulis(server, mode_anak, ubah, potongan):
    data = _form(server, **ubah)
    kode, isi, header = _post(server, "/daftar", data)
    assert kode in (200, 400) and "Set-Cookie" not in header
    if potongan:
        assert potongan in _pesan(isi)
    assert "4821" not in isi and "sandi-anak-sintetis" not in isi
    _tanpa_efek(server)


def test_wa_diecho_dengan_escape_dan_tidak_di_pesan(server, mode_anak):
    data = _form(server, wa='"><b>x</b>')
    _, isi, _ = _post(server, "/daftar", data)
    assert '"><b>x</b>' not in isi and "&quot;&gt;&lt;b&gt;x&lt;/b&gt;" in isi
    assert "&lt;b&gt;" not in _pesan(isi)
    _tanpa_efek(server)


def test_field_tak_dikenal_atau_jalur_selain_cek_ditolak(server, mode_anak):
    for tambahan in (dict(admin="1"), dict(jalur="lain"), dict(analitik="1")):
        kode, _, header = _post(server, "/daftar", {**_form(server), **tambahan})
        assert kode == 400 and "Set-Cookie" not in header
    _tanpa_efek(server)


# --- (b)(g) sukses, sesi murid, login ulang -----------------------------------

def test_sukses_membuat_akun_murid_siswa_koordinator_sesi_dan_redirect_murid(server, mode_anak):
    kode, _, header = _post(server, "/daftar", _form(server))
    assert kode == 303 and header["Location"] == "/murid" and "osn_sesi=" in header["Set-Cookie"]
    entri = auth.cari_akun("raka-login")
    assert entri["peran"] == "murid"
    with server.buka() as kon:
        siswa = kon.execute("SELECT id, nama, pemilik FROM siswa").fetchall()
        assert [(s["nama"], s["pemilik"]) for s in siswa] == [("Raka Pratama Sintetis", KOORDINATOR)]
        assert entri["siswa_id"] == siswa[0]["id"]
        assert [tuple(r) for r in kon.execute("SELECT id_akun, wa FROM kontak_akun")] == [
            (entri["id_akun"], WA_NORMAL)]
        assert [tuple(r) for r in kon.execute("SELECT versi_notice FROM persetujuan_daftar_anak")] == [
            (cek_gratis_skor.VERSI_NOTICE,)]
        assert pin_orang_tua_store.periksa_pin(kon, siswa[0]["id"], "4821")
    kode_murid, isi, _ = server.minta("/murid", cookie=_kuki(header))
    assert kode_murid == 200


def test_pendaftaran_ditutup_admin_menolak_mode_anak_tanpa_menulis(server, mode_anak, monkeypatch):
    data = _form(server)
    monkeypatch.setattr(reg, "status", lambda _p: reg.StatusPendaftaran(True, False, "", 1))
    kode, isi, header = _post(server, "/daftar", data)
    assert kode == 403 and "Set-Cookie" not in header and "ditutup" in isi
    _tanpa_efek(server)


def test_sukses_tanpa_pin_tidak_menulis_baris_pin(server, mode_anak):
    kode, _, _ = _post(server, "/daftar", _form(server, pin="", pin_ulang=""))
    assert kode == 303
    assert _keadaan(server)[1]["pin_orang_tua"] == 0 and _keadaan(server)[1]["persetujuan_daftar_anak"] == 1


def test_sukses_tidak_membocorkan_pin_sandi_atau_wa_ke_respons_dan_berkas_auth(server, mode_anak):
    kode, isi, header = _post(server, "/daftar", _form(server))
    assert kode == 303
    jejak = auth.BERKAS_SANDI.read_text() + header["Location"] + header["Set-Cookie"] + isi
    for rahasia in ("sandi-anak-sintetis", WA_NORMAL, WA, "Pratama"):
        assert rahasia not in jejak


def test_akun_hasil_daftar_bisa_login_di_masuk_dan_membuka_murid(server, mode_anak):
    assert _post(server, "/daftar", _form(server))[0] == 303
    kode, _, header = _post(server, "/masuk", dict(nama="raka-login", sandi="sandi-anak-sintetis"))
    assert kode == 303 and header["Location"] == "/murid"
    kode, isi, _ = server.minta("/murid", cookie=_kuki(header))
    assert kode == 200
    kode, _, _ = _post(server, "/masuk", dict(nama="raka-login", sandi="salah-salah-salah"))
    assert kode == 200


def test_murid_hasil_daftar_tidak_bisa_membuka_permukaan_guru(server, mode_anak):
    _, _, header = _post(server, "/daftar", _form(server))
    siswa_id = auth.cari_akun("raka-login")["siswa_id"]
    kode, _, _ = server.minta("/anak/%d" % siswa_id, cookie=_kuki(header))
    assert kode in (303, 401, 403, 404)
    kode, isi, _ = server.minta("/guru", cookie=_kuki(header))
    assert kode != 200 or "Raka Pratama" not in isi


def test_replay_form_sama_idempoten_tanpa_dobel(server, mode_anak):
    data = _form(server)
    assert _post(server, "/daftar", data)[0] == 303
    awal = auth.BERKAS_SANDI.read_bytes()
    kode, _, header = _post(server, "/daftar", data)
    assert kode == 303 and header["Location"] == "/murid"
    assert auth.BERKAS_SANDI.read_bytes() == awal
    assert len(_keadaan(server)[0]) == 1


def test_nama_login_terpakai_ditolak_ramah_tanpa_siswa_kedua(server, mode_anak):
    assert _post(server, "/daftar", _form(server))[0] == 303
    kode, isi, header = _post(server, "/daftar", _form(server, nama_lengkap="Anak Lain"))
    assert kode == 200 and "Nama login sudah dipakai" in _pesan(isi) and "Set-Cookie" not in header
    assert len(_keadaan(server)[0]) == 1


def test_dua_keluarga_nama_lengkap_sama_dua_siswa_berbeda(server, mode_anak):
    assert _post(server, "/daftar", _form(server))[0] == 303
    kode, _, _ = _post(server, "/daftar", _form(server, nama="raka-dua", wa="0855-5123-4567"))
    assert kode == 303
    siswa, _ = _keadaan(server)
    assert sorted(siswa) == [("Raka Pratama Sintetis", KOORDINATOR), ("Raka Pratama Sintetis (2)", KOORDINATOR)]
    assert auth.cari_akun("raka-login")["siswa_id"] != auth.cari_akun("raka-dua")["siswa_id"]
