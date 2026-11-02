"""Matriks akses rute: batas auth dispatcher `web._rute_get`/`web._rute_post`.

Batas auth di sini sebagian besar adalah URUTAN pemanggilan handler, bukan satu
pemeriksaan terpusat: `/murid` ditangani sebelum palang `_lolos_sandi`, `/admin`
dijawab `admin_http` sebelum palang guru, dan siklus `/sesi/` memegang guard
asalnya sendiri. Menyisipkan modul di posisi yang salah tidak membuat test lama
merah, jadi tabel dokumentasi `web.AKSES_RUTE_GET`/`web.AKSES_RUTE_POST` diuji
terhadap perilaku nyata lewat server sungguhan (`http_test_kit.ServerUji`).

Setiap prefix di tabel wajib punya probe di modul ini: menambah entri tabel
tanpa probe (atau sebaliknya) menggagalkan `test_tabel_akses_punya_probe`.

Data sepenuhnya sintetis: satu anak + satu sesi milik `guru`, akun murid `feby`
dari ServerUji. Tanpa jaringan keluar dan tanpa tidur panjang.
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import web  # noqa: E402
from http_test_kit import (  # noqa: E402
    SANDI_GURU,
    SANDI_MURID,
    ServerUji,
    _basic,
)

NAMA_ANAK = "Anak Sintetis M7"
# Satu-satunya jalur yang menandai halaman landing; beranda guru tidak memuatnya.
PENANDA_LANDING = 'id="judul-landing"'
LINTAS_SITUS = {"Sec-Fetch-Site": "cross-site"}

_TINGKAT = frozenset(("publik", "murid", "guru", "admin"))

# Probe per keluarga rute: jalur yang mewakili prefix di tabel akses.
_PROBE_GET = {
    "/admin": "/admin/tidak-ada",
    "/": "/",
    "/masuk": "/masuk",
    "/daftar": "/daftar",
    "/aset/": "/aset/favicon.svg",
    "/guru": "/guru",
    "/ortu": "/ortu",
    "/murid": "/murid",
    "/sesi/": "/sesi/1",
    "/lampiran/": "/lampiran/1",
    "/lembar/": "/lembar/1",
    "/akun": "/akun",
    "/anak/": "/anak/1",
    "/laporan/": "/laporan/1",
}

_PROBE_POST = {
    "/admin": "/admin/tidak-ada",
    "/masuk": "/masuk",
    "/daftar": "/daftar",
    "/murid/": "/murid/kerjakan/1",
    "/sesi/": "/sesi/1",
    "/akun": "/akun",
}

# Status anonim yang berlaku sekarang untuk tiap tingkat. "publik" POST boleh
# 400: halaman form publik tetap dilayani, isian kosong ditolak validasi.
_HARAPAN_ANONIM_GET = {
    "publik": (200,),
    "murid": (303,),  # pengalihan ke /masuk, bukan 401 polos
    "guru": (401,),
    "admin": (404,),  # keberadaan panel admin tidak diakui
}
_HARAPAN_ANONIM_POST = {
    "publik": (200, 400),
    "murid": (401,),
    "guru": (401,),
    "admin": (404,),
}

# Permukaan guru yang berisi data anak; akun murid tidak boleh menyentuhnya.
RUTE_PERMUKAAN_GURU = ("/guru", "/akun", "/sesi/1", "/lampiran/1", "/lembar/1")


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    """Pertahankan 303 sebagai 303; status asli rute yang sedang diuji."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _minta_mentah(
    uji: ServerUji,
    jalur: str,
    *,
    auth: tuple[str, str] | None = None,
    data: dict | None = None,
    header: dict[str, str] | None = None,
    method: str | None = None,
) -> tuple[int, str, dict]:
    """Satu permintaan tanpa mengikuti pengalihan -> (kode, isi, header)."""
    isi = None
    metode = method
    if data is not None:
        isi = urllib.parse.urlencode(data).encode()
        metode = metode or "POST"
    req = urllib.request.Request(uji.alamat + jalur, data=isi, method=metode)
    if isi is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if auth:
        req.add_header("Authorization", _basic(*auth))
    for nama, nilai in (header or {}).items():
        req.add_header(nama, nilai)
    pembuka = urllib.request.build_opener(_TanpaIkut)
    try:
        with pembuka.open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)


@pytest.fixture()
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        with uji.buka() as kon:
            anak = database.tambah_siswa(kon, NAMA_ANAK, "P3", pemilik="guru")
            uji.sesi = database.buat_sesi(kon, anak, 7)
        uji.anak = anak
        # `/daftar` menandatangani token form dengan akun pengelola; tanpa akun
        # admin rute publik itu menjawab 503, bukan 200.
        auth.tambah_akun("pengelola-m7", "sandi-pengelola-m7-123", "admin")
        yield uji
    finally:
        uji.berhenti()


def test_tabel_akses_punya_probe():
    """Setiap entri dokumentasi punya probe, dan sebaliknya."""
    get = dict(web.AKSES_RUTE_GET)
    post = dict(web.AKSES_RUTE_POST)
    assert set(get) == set(_PROBE_GET)
    assert set(post) == set(_PROBE_POST)
    assert set(get.values()) <= _TINGKAT
    assert set(post.values()) <= _TINGKAT
    # Urutan entri mengikuti urutan pemeriksaan handler di dispatcher: `/admin`
    # dan `/murid` diperiksa sebelum palang sandi, keluarga guru sesudahnya.
    urutan = [prefix for prefix, _tingkat in web.AKSES_RUTE_GET]
    assert urutan.index("/admin") < urutan.index("/guru")
    assert urutan.index("/murid") < urutan.index("/sesi/")
    assert get["/murid"] == "murid" and get["/admin"] == "admin"


@pytest.mark.parametrize("prefix,tingkat", web.AKSES_RUTE_GET)
def test_anonim_get_sesuai_tingkat(server, prefix, tingkat):
    jalur = _PROBE_GET[prefix]
    kode, isi, _tajuk = _minta_mentah(server, jalur)
    assert kode in _HARAPAN_ANONIM_GET[tingkat], f"GET {jalur} anonim: {kode}"
    if tingkat != "publik":
        assert NAMA_ANAK not in isi, f"GET {jalur} membocorkan nama anak"
    if tingkat == "guru":
        assert "perlu masuk" in isi.lower(), f"GET {jalur} bukan halaman palang"


@pytest.mark.parametrize("prefix,tingkat", web.AKSES_RUTE_POST)
def test_anonim_post_sesuai_tingkat(server, prefix, tingkat):
    jalur = _PROBE_POST[prefix]
    kode, isi, _tajuk = _minta_mentah(server, jalur, data={})
    assert kode in _HARAPAN_ANONIM_POST[tingkat], f"POST {jalur} anonim: {kode}"
    if tingkat != "publik":
        assert NAMA_ANAK not in isi, f"POST {jalur} membocorkan nama anak"


def test_anonim_di_root_mendapat_landing_bukan_beranda_guru(server):
    """`/` adalah landing publik; beranda guru hanya untuk identitas guru/admin."""
    kode, isi, _tajuk = server.minta("/")
    assert kode == 200
    assert PENANDA_LANDING in isi
    assert NAMA_ANAK not in isi


def test_anonim_di_murid_diarahkan_ke_masuk(server):
    """`/murid` ditangani sebelum palang sandi, jadi bentuknya 303, bukan 401/500."""
    kode, isi, tajuk = _minta_mentah(server, "/murid")
    assert kode == 303
    lokasi = urllib.parse.unquote_plus(tajuk.get("Location", ""))
    assert lokasi.startswith("/masuk?")
    assert "galat=" in lokasi
    assert isi == ""


@pytest.mark.parametrize("jalur", RUTE_PERMUKAAN_GURU)
def test_murid_ditolak_di_permukaan_guru(server, jalur):
    kode, isi, _tajuk = server.minta(jalur, auth=("feby", SANDI_MURID))
    assert kode == 401, f"{jalur} terbuka untuk murid"
    assert "perlu masuk" in isi.lower()
    assert NAMA_ANAK not in isi


def test_murid_tetap_di_beranda_publik_dan_beranda_murid(server):
    """Palang guru tidak boleh ikut menutup jalur publik maupun jalur murid."""
    kode, isi, _tajuk = server.minta("/", auth=("feby", SANDI_MURID))
    assert kode == 200 and PENANDA_LANDING in isi
    assert server.minta("/murid", auth=("feby", SANDI_MURID))[0] == 200


def test_admin_tidak_diaku_untuk_non_pengelola(server):
    """`/admin/...` asing dijawab 404 yang sama untuk anonim, murid, dan guru.

    401 akan mengakui panel itu ada; body yang berbeda antar peran juga menjadi
    oracle. Karena itu ketiganya dibandingkan, bukan hanya dicek kodenya.
    """
    hasil = {
        "anonim": _minta_mentah(server, "/admin/tidak-ada"),
        "murid": _minta_mentah(
            server, "/admin/tidak-ada", auth=("feby", SANDI_MURID)
        ),
        "guru": _minta_mentah(
            server, "/admin/tidak-ada", auth=("guru", SANDI_GURU)
        ),
    }
    for nama, (kode, isi, _tajuk) in hasil.items():
        assert kode == 404, f"{nama}: {kode}"
        assert "perlu masuk" not in isi.lower()
        assert NAMA_ANAK not in isi
    badan = {isi for _kode, isi, _tajuk in hasil.values()}
    assert len(badan) == 1, "body 404 berbeda antar peran: oracle panel admin"


@pytest.mark.parametrize("jalur", ["/admin", "/admin/tidak-ada"])
def test_guru_ditolak_di_panel_admin(server, jalur):
    kode, isi, _tajuk = server.minta(jalur, auth=("guru", SANDI_GURU))
    assert kode == 404, f"GET {jalur} terbuka untuk guru"
    assert NAMA_ANAK not in isi
    kode_post, isi_post, _tajuk = server.minta(
        jalur, auth=("guru", SANDI_GURU), data={}
    )
    assert kode_post == 404, f"POST {jalur} terbuka untuk guru"
    assert NAMA_ANAK not in isi_post


def test_post_lintas_situs_ditolak_sebelum_palang_sandi(server):
    """Palang asal `_rute_post` menjawab 403, bukan 401 halaman masuk."""
    kode, isi, _tajuk = server.minta("/akun", data={}, headers=LINTAS_SITUS)
    assert kode == 403
    assert "Permintaan ditolak" in isi
    assert "perlu masuk" not in isi.lower()


def test_post_lintas_situs_ke_form_masuk_tetap_dilayani(server):
    """`/masuk` dikecualikan dari palang asal karena form publik."""
    kode, isi, _tajuk = server.minta("/masuk", data={}, headers=LINTAS_SITUS)
    assert kode == 200
    assert "Nama dan sandi wajib diisi." in isi


def test_post_lintas_situs_ke_sesi_tanpa_sesi_ditolak_palang_sandi(server):
    """Prefix `/sesi/` melewati palang asal dispatcher (lihat komentar di
    `_rute_post`); untuk anonim yang menolak adalah palang sandi: 401, bukan 403.
    Guard asal siklus hidup di `learning_cycle_http` dan diuji di bawah."""
    kode, isi, _tajuk = server.minta("/sesi/1", data={}, headers=LINTAS_SITUS)
    assert kode == 401
    assert "perlu masuk" in isi.lower()
    assert NAMA_ANAK not in isi


def test_post_lintas_situs_ditolak_guard_asal_siklus(server):
    """Aksi siklus milik guru tetap menolak asal lintas situs dengan 403."""
    jalur = f"/sesi/{server.sesi}/konfirmasi"
    kode, isi, _tajuk = server.minta(
        jalur, auth=("guru", SANDI_GURU), data={}, headers=LINTAS_SITUS
    )
    assert kode == 403
    assert "berasal dari situs ini" in isi


def test_head_ditolak_eksplisit(server):
    kode, isi, tajuk = server.minta("/", method="HEAD")
    assert kode == 405
    assert tajuk.get("Allow") == "GET, POST"
    assert isi == ""
