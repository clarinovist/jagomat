"""Continuation login: allowlist ketat dan otorisasi ulang lewat HTTP sintetis."""

from __future__ import annotations

import html
import http.client
from html.parser import HTMLParser
from pathlib import Path
import sys
import urllib.parse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_policy  # noqa: E402
import assistant_schema  # noqa: E402
import assistant_service  # noqa: E402
import assistant_store  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import sessions  # noqa: E402
import web  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402


BATAS_ID = 2**63 - 1
TUJUAN_SAH = (
    "/pendamping",
    "/pendamping/konteks/anak/1",
    "/pendamping/konteks/sesi/42",
    "/pendamping/konteks/soal/42:1",
    f"/pendamping/konteks/anak/{BATAS_ID}",
    f"/pendamping/konteks/soal/{BATAS_ID}:{BATAS_ID}",
)
TUJUAN_TIDAK_SAH = (
    "", "https://asing.example/pendamping", "//asing.example/pendamping",
    "javascript:alert(1)", "/\\asing.example", "\\pendamping",
    "/pendamping/", "/pendamping//", "/pendamping?x=1", "/pendamping#x",
    "/pendamping/../admin", "/pendamping/konteks/anak/1/",
    "/pendamping/konteks//anak/1", "/pendamping/konteks/anak/1?x=1",
    "/pendamping/konteks/anak/1#x", "/pendamping/konteks/anak/1\\x",
    "/pendamping/konteks/anak/%31", "%2Fpendamping", "%252Fpendamping",
    "/pendamping%2f%2fasing.example", "/pendamping/konteks/anak/0",
    "/pendamping/konteks/anak/01", "/pendamping/konteks/anak/-1",
    "/pendamping/konteks/anak/+1", "/pendamping/konteks/anak/١",
    "/pendamping/konteks/anak/１", "/pendamping/konteks/anak/1:2",
    "/pendamping/konteks/sesi/1:2", "/pendamping/konteks/soal/1",
    "/pendamping/konteks/soal/1:0", "/pendamping/konteks/soal/01:1",
    "/pendamping/konteks/soal/1:01", "/pendamping/konteks/soal/1:1:1",
    f"/pendamping/konteks/anak/{BATAS_ID + 1}",
    f"/pendamping/konteks/soal/1:{BATAS_ID + 1}",
    "/pendamping/konteks/anak/" + "9" * 1000,
    " /pendamping", "/pendamping ", "/pendamping\n", "/pendamping\r\nX-Test: 1",
    "/pendamping\t", "/pendamping\x00", "/Pendamping", "/pendamping/memori",
    "/pendamping/konteks/pilih", "/pendamping/chat/chat_" + "a" * 32,
    "/guru", "/admin", "/murid", '<script id="redirect-asing">x</script>',
)


class _Isian(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.lanjut = []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "input" and data.get("name") == "lanjut":
            assert data.get("type") == "hidden"
            self.lanjut.append(data.get("value"))


def _minta(server, jalur, *, data=None, cookie=""):
    """Tanpa mengikuti redirect; tak mungkin mengunjungi URL luar dari Location."""
    koneksi = http.client.HTTPConnection(*server.server.server_address, timeout=10)
    tajuk = {}
    if cookie:
        tajuk["Cookie"] = cookie
    isi = None
    if data is not None:
        isi = urllib.parse.urlencode(data).encode("utf-8")
        tajuk["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        koneksi.request("POST" if data is not None else "GET", jalur, isi, tajuk)
        respons = koneksi.getresponse()
        return respons.status, respons.read().decode("utf-8"), dict(respons.getheaders())
    finally:
        koneksi.close()


def _masuk(server, lanjut, *, nama="guru", sandi=SANDI_GURU):
    return _minta(server, "/masuk", data={"nama": nama, "sandi": sandi, "lanjut": lanjut})


def _snapshot(server):
    """Bandingkan isi belajar/privat, bukan token autentikasi yang memang baru."""
    with server.buka() as kon:
        belajar = tuple(kon.iterdump())
    with assistant_schema.buka() as kon:
        privat = tuple(kon.iterdump())
    return belajar, privat


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "kunci-sintetis")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    monkeypatch.setattr(sessions, "_jalur_dari_kunci_ip", {})
    monkeypatch.setattr(assistant_schema, "BAWAAN", tmp_path / "pendamping.db")
    monkeypatch.setattr(web.Penangan, "log_message", lambda *args: None)
    panggilan = []

    def provider_terlarang(*args, **kwargs):
        panggilan.append(True)
        raise AssertionError("Navigasi tidak boleh memanggil provider.")

    monkeypatch.setattr(assistant_service, "panggil_provider_default", provider_terlarang)
    s = ServerUji(tmp_path, monkeypatch)
    try:
        auth.tambah_akun("pengelola", SANDI_GURU, "admin")
        auth.tambah_akun("ortu-b", SANDI_GURU, "guru")
        assistant_schema.siapkan()
        # Consent provider saja; GET sumber tidak boleh otomatis membuat izin konteks.
        with assistant_schema.buka() as kon:
            for nama in ("guru", "ortu-b"):
                assistant_store.beri_persetujuan(
                    kon, auth.cari_akun(nama)["id_akun"],
                    policy_version=assistant_policy.VERSI_KEBIJAKAN,
                    provider_id=assistant_policy.PROVIDER_ID, kategori="chat_umum",
                    sekarang=100,
                )
        with s.buka() as kon:
            anak = database.tambah_siswa(kon, "Anak Navigasi", "P3", pemilik="guru")
            sesi = database.buat_sesi(kon, anak, seed=42)
            asing = database.tambah_siswa(kon, "Anak Asing Navigasi", "P3", pemilik="ortu-b")
            sesi_asing = database.buat_sesi(kon, asing, seed=43)
            database.tandai_selesai(kon, sesi)
        s.ids = (anak, sesi, asing, sesi_asing)
        yield s
        assert not panggilan
    finally:
        s.berhenti()


@pytest.mark.parametrize("tujuan", TUJUAN_SAH)
def test_helper_tujuan_kanonik_dan_tautan(tujuan):
    from assistant_navigation import tautan_masuk, tujuan_lanjut

    assert tujuan_lanjut(tujuan) == tujuan
    tautan = tautan_masuk(tujuan)
    assert tautan == "/masuk?" + urllib.parse.urlencode({"lanjut": tujuan})
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(tautan).query) == {"lanjut": [tujuan]}


@pytest.mark.parametrize("nilai", (*TUJUAN_TIDAK_SAH, None, 1, [], {}, b"/pendamping"))
def test_helper_tolak_tujuan_nonkanonik(nilai):
    from assistant_navigation import tautan_masuk, tujuan_lanjut

    assert tujuan_lanjut(nilai) == ""
    assert tautan_masuk(nilai) == "/masuk"


@pytest.mark.parametrize("tujuan", TUJUAN_SAH)
def test_http_get_masuk_menyimpan_satu_lanjut_kanonik(server, tujuan):
    kode, isi, tajuk = _minta(server, "/masuk?" + urllib.parse.urlencode({"lanjut": tujuan}))
    assert kode == 200
    assert _Isian(isi).lanjut == [tujuan]
    assert "Set-Cookie" not in tajuk


@pytest.mark.parametrize("tujuan", TUJUAN_SAH)
def test_http_guru_meneruskan_tujuan_kanonik(server, tujuan):
    kode, isi, tajuk = _masuk(server, tujuan)
    assert kode == 303
    assert tajuk["Location"] == tujuan
    assert isi == ""
    assert "HttpOnly" in tajuk["Set-Cookie"]
    assert "SameSite=Lax" in tajuk["Set-Cookie"]


@pytest.mark.parametrize("jenis_gagal", ("kosong", "salah", "blocked"))
@pytest.mark.parametrize("tujuan", ("/pendamping/konteks/soal/42:1", "//asing.example/rahasia-redirect"))
def test_http_error_login_hanya_simpan_lanjut_aman(server, jenis_gagal, tujuan):
    sandi = "" if jenis_gagal == "kosong" else "salah-sintetis"
    if jenis_gagal == "blocked":
        for _ in range(5):
            sessions.catat_gagal("guru", "127.0.0.1")
        sandi = SANDI_GURU
    kode, isi, tajuk = _masuk(server, tujuan, sandi=sandi)
    assert kode == (429 if jenis_gagal == "blocked" else 200)
    assert 'role="alert"' in isi
    aman = tujuan.startswith("/pendamping/")
    assert _Isian(isi).lanjut == ([tujuan] if aman else [])
    if not aman:
        assert tujuan not in isi
        assert html.escape(tujuan) not in isi
    assert "Set-Cookie" not in tajuk
    assert "Location" not in tajuk
    assert not sessions.BERKAS_SESI.exists()


@pytest.mark.parametrize("tujuan", TUJUAN_TIDAK_SAH)
def test_http_unsafe_get_dan_post_tidak_echo_atau_redirect(server, tujuan):
    kode, isi, tajuk = _minta(server, "/masuk?" + urllib.parse.urlencode({"lanjut": tujuan}))
    assert kode == 200
    assert _Isian(isi).lanjut == []
    if tujuan and tujuan not in ("/guru", "/admin", "/murid"):
        assert html.escape(tujuan) not in isi
    kode, isi, tajuk = _masuk(server, tujuan)
    assert kode == 303
    assert tajuk["Location"] == "/guru"
    assert isi == ""


@pytest.mark.parametrize("nilai", (
    ("/pendamping", "/pendamping"),
    ("/pendamping", ""),
    ("", "/pendamping"),
    ("/pendamping", "//asing.example"),
    ("//asing.example", "/pendamping"),
    ("/pendamping", "/pendamping/konteks/anak/1"),
))
def test_http_lanjut_ganda_dibuang_pada_get_post_dan_error(server, nilai):
    pasangan = [("lanjut", item) for item in nilai]
    kode, isi, _ = _minta(server, "/masuk?" + urllib.parse.urlencode(pasangan))
    assert kode == 200
    assert _Isian(isi).lanjut == []
    kode, isi, tajuk = _minta(server, "/masuk", data=[("nama", "guru"), ("sandi", "salah"), *pasangan])
    assert kode == 200
    assert _Isian(isi).lanjut == []
    assert "Set-Cookie" not in tajuk
    kode, isi, tajuk = _minta(server, "/masuk", data=[("nama", "guru"), ("sandi", SANDI_GURU), *pasangan])
    assert kode == 303
    assert tajuk["Location"] == "/guru"
    assert isi == ""


def test_http_post_tidak_meminjam_query_lanjut(server):
    kode, _, tajuk = _minta(server, "/masuk?lanjut=%2Fpendamping", data={"nama": "guru", "sandi": SANDI_GURU})
    assert kode == 303
    assert tajuk["Location"] == "/guru"


@pytest.mark.parametrize("nama,sandi,tujuan", (
    ("guru", SANDI_GURU, "/guru"),
    ("feby", SANDI_MURID, "/murid"),
    ("pengelola", SANDI_GURU, "/admin"),
))
def test_http_tanpa_lanjut_mempertahankan_dashboard_peran(server, nama, sandi, tujuan):
    kode, isi, tajuk = _minta(server, "/masuk", data={"nama": nama, "sandi": sandi})
    assert kode == 303
    assert tajuk["Location"] == tujuan
    assert isi == ""


@pytest.mark.parametrize("nama,sandi,dashboard", (
    ("feby", SANDI_MURID, "/murid"),
    ("pengelola", SANDI_GURU, "/admin"),
))
@pytest.mark.parametrize("jenis", ("anak", "sesi", "soal"))
def test_http_murid_admin_abaikan_lanjut_dan_tujuan_tetap_terjaga(server, nama, sandi, dashboard, jenis):
    anak, sesi, _, _ = server.ids
    resource = str(anak) if jenis == "anak" else (f"{sesi}:1" if jenis == "soal" else str(sesi))
    tujuan = f"/pendamping/konteks/{jenis}/{resource}"
    sebelum = _snapshot(server)
    kode, _, tajuk = _masuk(server, tujuan, nama=nama, sandi=sandi)
    assert kode == 303
    assert tajuk["Location"] == dashboard
    cookie = tajuk["Set-Cookie"].split(";", 1)[0]
    kode, isi, _ = _minta(server, tujuan, cookie=cookie)
    assert kode == 401
    assert "Pilih konteks" not in isi
    assert "Anak Navigasi" not in isi
    assert _snapshot(server) == sebelum


@pytest.mark.parametrize("jenis", ("anak", "sesi", "soal"))
def test_http_redirect_foreign_dan_missing_404_identik_tanpa_efek(server, jenis):
    anak, sesi, asing, sesi_asing = server.ids
    pemilik = str(anak) if jenis == "anak" else (f"{sesi}:1" if jenis == "soal" else str(sesi))
    foreign = str(asing) if jenis == "anak" else (f"{sesi_asing}:1" if jenis == "soal" else str(sesi_asing))
    hilang = "999999:1" if jenis == "soal" else "999999"
    sebelum = _snapshot(server)
    respons = []
    for resource in (foreign, hilang):
        tujuan = f"/pendamping/konteks/{jenis}/{resource}"
        kode, _, tajuk = _masuk(server, tujuan)
        assert kode == 303
        assert tajuk["Location"] == tujuan
        cookie = tajuk["Set-Cookie"].split(";", 1)[0]
        respons.append(_minta(server, tajuk["Location"], cookie=cookie))
    assert respons[0][0] == respons[1][0] == 404
    assert respons[0][1] == respons[1][1]
    assert "Anak Asing Navigasi" not in respons[0][1]
    assert respons[0][2]["Cache-Control"] == "no-store"
    assert respons[0][2]["Referrer-Policy"] == "no-referrer"
    assert _snapshot(server) == sebelum

    tujuan = f"/pendamping/konteks/{jenis}/{pemilik}"
    kode, _, tajuk = _masuk(server, tujuan)
    assert kode == 303 and tajuk["Location"] == tujuan
    cookie = tajuk["Set-Cookie"].split(";", 1)[0]
    respons_sah = _minta(server, tajuk["Location"], cookie=cookie)
    assert respons_sah[0] == 303
    tujuan_host = respons_sah[2]["Location"]
    assert tujuan_host.startswith((f"/anak/{anak}?bantuan=", f"/sesi/{sesi}?bantuan="))
    kode_host, isi_host, _ = _minta(server, tujuan_host, cookie=cookie)
    assert kode_host == 200 and 'name="setuju_konteks"' in isi_host


def test_http_akun_saat_login_bukan_pemilik_sumber_dari_form(server):
    tujuan = f"/pendamping/konteks/anak/{server.ids[0]}"
    kode, isi, _ = _minta(server, "/masuk?" + urllib.parse.urlencode({"lanjut": tujuan}))
    assert kode == 200
    kode, _, tajuk = _masuk(server, _Isian(isi).lanjut[0], nama="ortu-b")
    assert kode == 303
    assert tajuk["Location"] == tujuan
    cookie = tajuk["Set-Cookie"].split(";", 1)[0]
    sebelum = _snapshot(server)
    kode, isi, _ = _minta(server, tajuk["Location"], cookie=cookie)
    kode_hilang, isi_hilang, _ = _minta(server, "/pendamping/konteks/anak/999999", cookie=cookie)
    assert kode == kode_hilang == 404
    assert isi == isi_hilang
    assert _snapshot(server) == sebelum


def test_http_kepemilikan_diubah_setelah_login_dicek_ulang(server):
    tujuan = f"/pendamping/konteks/anak/{server.ids[0]}"
    kode, _, tajuk = _masuk(server, tujuan)
    assert kode == 303
    assert tajuk["Location"] == tujuan
    cookie = tajuk["Set-Cookie"].split(";", 1)[0]
    with server.buka() as kon:
        kon.execute("UPDATE siswa SET pemilik = 'ortu-b' WHERE id = ?", (server.ids[0],))
    sebelum = _snapshot(server)
    kode, isi, _ = _minta(server, tajuk["Location"], cookie=cookie)
    kode_hilang, isi_hilang, _ = _minta(server, "/pendamping/konteks/anak/999999", cookie=cookie)
    assert kode == kode_hilang == 404
    assert isi == isi_hilang
    assert _snapshot(server) == sebelum


def test_http_guru_form_ke_pendamping_dengan_principal_baru(server):
    kode, isi, _ = _minta(server, "/masuk?lanjut=%2Fpendamping")
    assert kode == 200
    sebelum = _snapshot(server)
    kode, _, tajuk = _masuk(server, _Isian(isi).lanjut[0])
    assert kode == 303
    assert tajuk["Location"] == "/pendamping"
    cookie = tajuk["Set-Cookie"].split(";", 1)[0]
    kode, isi, tajuk = _minta(server, tajuk["Location"], cookie=cookie)
    assert kode == 303
    assert tajuk["Location"] == "/guru"
    kode, isi, _ = _minta(server, "/guru", cookie=cookie)
    assert kode == 200 and 'action="/pendamping/chat-baru"' not in isi
    assert _snapshot(server) == sebelum


def test_http_akun_tidak_dikenal_tetap_gagal_tanpa_echo(server):
    kode, isi, tajuk = _masuk(server, "//asing.example/redirect-rahasia", nama="bukan-akun")
    assert kode == 200
    assert 'role="alert"' in isi
    assert _Isian(isi).lanjut == []
    assert "redirect-rahasia" not in isi
    assert "Set-Cookie" not in tajuk
    assert "Location" not in tajuk
    assert not sessions.BERKAS_SESI.exists()


def test_http_batas_id_sqlite_tidak_menyebabkan_overflow_tujuan(server):
    tujuan = f"/pendamping/konteks/soal/{BATAS_ID}:{BATAS_ID}"
    kode, _, tajuk = _masuk(server, tujuan)
    assert kode == 303
    assert tajuk["Location"] == tujuan
    cookie = tajuk["Set-Cookie"].split(";", 1)[0]
    sebelum = _snapshot(server)
    kode, _, _ = _minta(server, tajuk["Location"], cookie=cookie)
    assert kode == 404
    assert _snapshot(server) == sebelum


def test_renderer_memvalidasi_lanjut_tanpa_percaya_pemanggil():
    sah = "/pendamping/konteks/soal/42:1"
    assert _Isian(web.Penangan._halaman_masuk_stitch(None, lanjut=sah).decode()).lanjut == [sah]
    for nilai in TUJUAN_TIDAK_SAH:
        isi = web.Penangan._halaman_masuk_stitch(None, lanjut=nilai).decode()
        assert _Isian(isi).lanjut == []
    assert _Isian(web.Penangan._halaman_masuk_stitch(None).decode()).lanjut == []
