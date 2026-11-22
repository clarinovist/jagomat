"""Font merek same-origin di semua halaman guru (keputusan pemilik 22 Nov 2026).

Invarian: halaman privat memuat `@font-face` lokal `/aset/font-...` dan TIDAK memuat
host pihak ketiga; berkas font terdaftar di `brand.ASET`, ada di disk, dan CSP
halaman privat mengizinkan `'self'` untuk `font-src` tanpa melonggarkan direktif lain.
"""
import re

import pytest

import brand
import database
import design_tokens as T
import font_lokal
import style_stitch
import teacher_shell
from http_test_kit import SANDI_GURU, ServerUji

HOST_PIHAK_KETIGA = ("fonts.googleapis.com", "fonts.gstatic.com")
MAGIC_TTF = (b"\x00\x01\x00\x00", b"true", b"OTTO")
NAMA_FONT_DALAM_CSS = re.findall(
    r'src:url\("/aset/([^"]+)"\) format\("truetype"\)', font_lokal.CSS_FONT_LOKAL
)


def _direktif(csp):
    return {p.split()[0]: p.split()[1:] for p in csp.split(";") if p.strip()}


def test_tiap_font_di_face_terdaftar_dan_berkasnya_ada():
    assert sorted(NAMA_FONT_DALAM_CSS) == sorted(n for _, _, n in font_lokal.BERKAS_FONT)
    assert len(NAMA_FONT_DALAM_CSS) == 7
    for nama in NAMA_FONT_DALAM_CSS:
        assert brand.ASET[nama] == "font/ttf", nama
        isi = (brand.FOLDER_ASET / nama).read_bytes()
        assert isi[:4] in MAGIC_TTF, f"{nama} bukan berkas font"
        assert re.search(r"-v\d+\.ttf$", nama), f"{nama} harus berversi (rute immutable)"


def test_face_swap_lokal_dan_keluarga_sesuai_token():
    css = font_lokal.CSS_FONT_LOKAL
    assert css.count("@font-face") == 7 and css.count("font-display:swap") == 7
    assert "http" not in css
    for keluarga in {k for k, _, _ in font_lokal.BERKAS_FONT}:
        assert f'"{keluarga}"' in T.FONT_HEADLINE + T.FONT_BODY


def test_impor_cdn_cocok_dengan_gaya_stitch_dan_bisa_dibuang():
    assert style_stitch.GAYA_STITCH.count(font_lokal.IMPOR_FONT_CDN) == 1
    bersih = font_lokal.tanpa_impor_font_cdn(style_stitch.GAYA_STITCH)
    assert "@import url(" not in bersih and "fonts.googleapis" not in bersih
    assert font_lokal.IMPOR_FONT_CDN in style_stitch.GAYA_STITCH  # argumen tidak berubah


def _tanpa_pihak_ketiga(h):
    for host in HOST_PIHAK_KETIGA:
        assert host not in h, host
    assert "@import url(" not in h


def _wajib_font_lokal(h):
    for nama in NAMA_FONT_DALAM_CSS:
        assert f'url("/aset/{nama}")' in h, nama


@pytest.mark.parametrize("bingkai", ["stitch_privat", "halaman_stitch_privat"])
def test_shell_privat_memuat_font_lokal_tanpa_pihak_ketiga(bingkai):
    ident = ("guru", "guru")
    if bingkai == "stitch_privat":
        h = teacher_shell._halaman("Uji", "<p>x</p>", ident=ident, stitch=True, privat=True).decode()
    else:
        h = teacher_shell._halaman_stitch("Uji", "<p>x</p>", ident=ident, privat=True).decode()
    _wajib_font_lokal(h)
    _tanpa_pihak_ketiga(h)


@pytest.mark.parametrize("bingkai", ["stitch", "halaman_stitch", "legacy"])
def test_shell_nonprivat_font_lokal_dan_cdn_hanya_ikon(bingkai):
    ident = ("guru", "guru")
    if bingkai == "stitch":
        h = teacher_shell._halaman("Uji", "<p>x</p>", ident=ident, stitch=True).decode()
    elif bingkai == "halaman_stitch":
        h = teacher_shell._halaman_stitch("Uji", "<p>x</p>", ident=ident).decode()
    else:
        h = teacher_shell._halaman("Uji", "<p>x</p>", ident=ident).decode()
    _wajib_font_lokal(h)
    assert "@import url(" not in h and "Be+Vietnam" not in h and "Plus+Jakarta" not in h
    if bingkai != "legacy":
        assert "family=Material+Symbols+Outlined" in h


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        with uji.buka() as kon:
            uji.anak = database.tambah_siswa(kon, "Anak Sintetis", "P3", pemilik="guru")
            uji.sesi = database.buat_sesi(kon, uji.anak, 401, jumlah_soal=1)
        yield uji
    finally:
        uji.berhenti()


# Halaman guru yang dikirim lewat `_kirim_tautan` memakai `csp_tautan`; host Google hanya
# diizinkan bila isi halaman memuatnya, jadi halaman privat ini juga tanpa host luar.
RUTE_CSP_TAUTAN = ("/anak/{anak}/laporan-ortu", "/anak/{anak}/lomba")


@pytest.mark.parametrize("jalur", [
    "/akun", "/akun?section=siswa", "/anak/{anak}", "/anak/{anak}?section=perkembangan", "/sesi/{sesi}",
    *RUTE_CSP_TAUTAN,
])
def test_halaman_privat_guru_font_lokal_dan_csp_tanpa_host_luar(server, jalur):
    kode, isi, tajuk = server.minta(
        jalur.format(anak=server.anak, sesi=server.sesi), auth=("guru", SANDI_GURU)
    )
    assert kode == 200
    _wajib_font_lokal(isi)
    _tanpa_pihak_ketiga(isi)
    csp = tajuk.get("Content-Security-Policy")
    if csp is None:
        return  # tanpa CSP tidak ada pembatasan font; invarian isi sudah ditegakkan di atas
    direktif = _direktif(csp)
    assert "'self'" in direktif.get("font-src", []), csp
    assert not any("//" in v for d in ("font-src", "style-src") for v in direktif.get(d, [])), csp
    assert direktif["default-src"] == ["'none'"] and direktif["frame-ancestors"] == ["'none'"]


def test_csp_akun_font_self_saja_dan_berkas_font_terlayani(server):
    kode, _isi, tajuk = server.minta("/akun", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert _direktif(tajuk["Content-Security-Policy"])["font-src"] == ["'self'"]
    nama = font_lokal.BERKAS_FONT[0][2]
    kode, isi, hdr = server.minta(f"/aset/{nama}", biner=True)
    assert kode == 200 and hdr["Content-Type"].startswith("font/ttf") and isi[:4] in MAGIC_TTF


def test_csp_beranda_guru_font_self_plus_gstatic_untuk_ikon(server):
    _, _, tajuk = server.minta("/guru", auth=("guru", SANDI_GURU))
    assert _direktif(tajuk["Content-Security-Policy"])["font-src"] == [
        "'self'", "https://fonts.gstatic.com"
    ]


def test_csp_masuk_font_self_tanpa_host_google(server):
    kode, isi, tajuk = server.minta("/masuk")
    assert kode == 200 and "fonts.googleapis.com" not in isi
    direktif = _direktif(tajuk["Content-Security-Policy"])
    assert direktif["font-src"] == ["'self'"] and direktif["style-src"] == ["'unsafe-inline'"]


@pytest.mark.parametrize("jalur", ["/", "/daftar", "/kebijakan", "/lupa-sandi"])
def test_halaman_publik_font_lokal_tanpa_host_google(server, jalur):
    _kode, isi, tajuk = server.minta(jalur)
    _wajib_font_lokal(isi)
    _tanpa_pihak_ketiga(isi)
    csp = tajuk.get("Content-Security-Policy")
    if csp is not None:
        assert "fonts.googleapis.com" not in csp and "fonts.gstatic.com" not in csp


def test_kerangka_cek_anak_dan_lembar_peta_font_lokal():
    import cek_anak_komponen
    isi = cek_anak_komponen.kerangka("Cek", "<p>x</p>").decode()
    _wajib_font_lokal(isi)
    _tanpa_pihak_ketiga(isi)
