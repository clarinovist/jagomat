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
    "/admin/pesanan": "/admin/pesanan",
    "/admin/pesanan/verifikasi": "/admin/pesanan/verifikasi?order=ord_" + "0" * 32,
    "/admin/pesanan/bukti": "/admin/pesanan/bukti?id=1",
    "/admin/pesanan/order": "/admin/pesanan/order?id=ord_" + "0" * 32,
    "/admin/pesanan/rekening": "/admin/pesanan/rekening",
    "/admin/sakelar": "/admin/sakelar",
    "/admin/harga": "/admin/harga",
    "/admin/langganan": "/admin/langganan",
    "/admin/pembayaran": "/admin/pembayaran",
    "/admin/kelas": "/admin/kelas",
    "/admin/kelas/kelompok": "/admin/kelas/kelompok?id=klp_" + "0" * 32,
    "/admin/kelas/private": "/admin/kelas/private",
    "/admin/kurikulum": "/admin/kurikulum",
    "/admin/kurikulum/cp-detail": "/admin/kurikulum/cp-detail",
    "/admin/kurikulum/buat": "/admin/kurikulum/buat?kelas=3&bab=1",
    "/admin/kurikulum/cp": "/admin/kurikulum/cp?grup=aritmatika-lanjut%2Fkonversi",
    "/admin/kurikulum/label": "/admin/kurikulum/label?topik=pengukuran",
    "/admin/kurikulum/cetakan": "/admin/kurikulum/cetakan?kelas=3&bab=1",
    "/admin/kurikulum/cetakan/baru": "/admin/kurikulum/cetakan/baru?kelas=3&bab=1",
    "/admin/kurikulum/cetakan/periksa": "/admin/kurikulum/cetakan/periksa?id=1",
    "/": "/",
    "/masuk": "/masuk",
    "/daftar": "/daftar",
    "/cek-kemampuan": "/cek-kemampuan",
    "/paket-coba": "/paket-coba",
    "/contoh-peta-kemampuan": "/contoh-peta-kemampuan",
    "/contoh-peta-kemampuan/lembar": "/contoh-peta-kemampuan/lembar",
    "/aset/": "/aset/favicon.svg",
    "/guru": "/guru",
    "/ortu": "/ortu",
    "/murid": "/murid",
    "/murid/orang-tua": "/murid/orang-tua",
    "/murid/pesanan": "/murid/pesanan",
    "/murid/langganan": "/murid/langganan",
    "/murid/latihan-harian": "/murid/latihan-harian",
    "/murid/paket": "/murid/paket",
    "/murid/paket/tagihan": "/murid/paket/tagihan?kode=mini",
    "/murid/paket/hapus": "/murid/paket/hapus?kode=mini",
    "/lembaga": "/lembaga",
    "/guru/jadwal": "/guru/jadwal",
    "/guru/kelas": "/guru/kelas",
    "/guru/kelas/": "/guru/kelas/klp_" + "0" * 32,
    "/sesi/": "/sesi/1",
    "/lampiran/": "/lampiran/1",
    "/lembar/": "/lembar/1",
    "/akun": "/akun",
    "/akun/kontak": "/akun/kontak",
    "/cek-kemampuan/mulai": "/cek-kemampuan/mulai",
    "/cek-kemampuan/hasil": "/cek-kemampuan/hasil",
    "/pesanan": "/pesanan",
    "/pesanan/qr": "/pesanan/qr",
    "/paket-coba/pesan": "/paket-coba/pesan",
    "/anak/": "/anak/1",
    "/laporan/": "/laporan/1",
}

_PROBE_POST = {
    "/admin": "/admin/tidak-ada",
    "/admin/pesanan/periksa": "/admin/pesanan/periksa",
    "/admin/pesanan/refund": "/admin/pesanan/refund",
    "/admin/pesanan/voucher": "/admin/pesanan/voucher",
    "/admin/pesanan/setujui": "/admin/pesanan/setujui",
    "/admin/pesanan/tolak": "/admin/pesanan/tolak",
    "/admin/pesanan/rekening": "/admin/pesanan/rekening",
    "/admin/sakelar": "/admin/sakelar",
    "/admin/harga": "/admin/harga",
    "/admin/langganan": "/admin/langganan/setujui",
    "/admin/kelas": "/admin/kelas/setujui",
    "/admin/kelas/kelompok": "/admin/kelas/kelompok",
    "/admin/kelas/kelompok/ubah": "/admin/kelas/kelompok/ubah",
    "/admin/kelas/penempatan": "/admin/kelas/penempatan",
    "/admin/kelas/penempatan/lepas": "/admin/kelas/penempatan/lepas",
    "/admin/kelas/pertemuan": "/admin/kelas/pertemuan",
    "/admin/kelas/pertemuan/batal": "/admin/kelas/pertemuan/batal",
    "/admin/kelas/private/slot": "/admin/kelas/private/slot",
    "/admin/kelas/private/slot/batal": "/admin/kelas/private/slot/batal",
    "/admin/kelas/private/setujui": "/admin/kelas/private/setujui",
    "/admin/kelas/private/tolak": "/admin/kelas/private/tolak",
    "/admin/kurikulum/cp": "/admin/kurikulum/cp",
    "/admin/kurikulum/cp/kembalikan": "/admin/kurikulum/cp/kembalikan",
    "/admin/kurikulum/label": "/admin/kurikulum/label",
    "/admin/kurikulum/label/kembalikan": "/admin/kurikulum/label/kembalikan",
    "/admin/kurikulum/cetakan/baru": "/admin/kurikulum/cetakan/baru",
    "/admin/kurikulum/cetakan/ubah": "/admin/kurikulum/cetakan/ubah",
    "/admin/kurikulum/cetakan/setujui": "/admin/kurikulum/cetakan/setujui",
    "/admin/kurikulum/cetakan/nonaktifkan": "/admin/kurikulum/cetakan/nonaktifkan",
    "/admin/kurikulum/cetakan/aktifkan": "/admin/kurikulum/cetakan/aktifkan",
    "/admin/kurikulum/cetakan/draf-ai": "/admin/kurikulum/cetakan/draf-ai",
    "/masuk": "/masuk",
    "/daftar": "/daftar",
    "/murid/": "/murid/kerjakan/1",
    "/murid/orang-tua/pin": "/murid/orang-tua/pin",
    "/murid/orang-tua/pin/atur": "/murid/orang-tua/pin/atur",
    "/murid/orang-tua/pin/hapus": "/murid/orang-tua/pin/hapus",
    "/murid/cek/mulai": "/murid/cek/mulai",
    "/murid/pesanan": "/murid/pesanan/pesan",
    "/murid/langganan": "/murid/langganan/buat",
    "/murid/latihan-harian": "/murid/latihan-harian/mulai",
    "/murid/paket": "/murid/paket/buat",
    "/murid/paket/hapus": "/murid/paket/hapus",
    "/murid/paket/jadwal-private/ajukan": "/murid/paket/jadwal-private/ajukan",
    "/murid/paket/jadwal-private/batal": "/murid/paket/jadwal-private/batal",
    "/lembaga": "/lembaga/pindah",
    "/sesi/": "/sesi/1",
    "/akun": "/akun",
    "/akun/kontak": "/akun/kontak",
    "/cek-kemampuan/mulai": "/cek-kemampuan/mulai",
    "/cek-kemampuan/tautan": "/cek-kemampuan/tautan",
    "/paket-coba/pesan": "/paket-coba/pesan",
    "/pesanan/periksa": "/pesanan/periksa",
    "/pesanan/ulang": "/pesanan/ulang",
    "/pesanan/buat": "/pesanan/buat",
    "/pesanan/tagihan": "/pesanan/tagihan",
    "/pesanan/bukti": "/pesanan/bukti",
    "/pesanan/tagihan/ulang": "/pesanan/tagihan/ulang",
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
RUTE_PERMUKAAN_GURU = (
    "/guru", "/akun", "/akun/kontak", "/lembaga", "/sesi/1", "/lampiran/1", "/lembar/1",
    "/cek-kemampuan/mulai", "/cek-kemampuan/hasil", "/pesanan", "/pesanan/qr", "/paket-coba/pesan",
    "/guru/jadwal", "/guru/kelas", "/guru/kelas/klp_" + "0" * 32,
)


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
    # F3 halaman orang tua: exact, murid, tepat sesudah /murid (sebelum palang sandi guru `/sesi/`).
    assert get["/murid/orang-tua"] == "murid" and urutan.index("/murid/orang-tua") == urutan.index("/murid") + 1
    for rute in ("/murid/orang-tua/pin", "/murid/orang-tua/pin/atur", "/murid/orang-tua/pin/hapus"):
        assert post[rute] == "murid" and rute not in get
    # F2c: pesanan dari akun anak; tepat setelah /murid (sebelum palang sandi), POST di bawah prefix /murid/.
    assert get["/murid/pesanan"] == post["/murid/pesanan"] == "murid"
    assert urutan.index("/murid/pesanan") == urutan.index("/murid/orang-tua") + 1
    # Rute pilihan terlambat (uang kembali) sudah dihapus: tidak ada entri tabel tersendiri.
    assert "/murid/pesanan/pilih" not in get and "/murid/pesanan/pilih" not in post
    # F5: langganan Latihan Harian dari akun anak; tepat setelah /murid/pesanan, GET exact dan POST di bawahnya.
    assert get["/murid/langganan"] == post["/murid/langganan"] == "murid"
    assert urutan.index("/murid/langganan") == urutan.index("/murid/pesanan") + 1
    # F4: Latihan Harian (prefix murid), tepat setelah /murid/pesanan; sakelar mati = rute murid tak dikenal.
    assert get["/murid/latihan-harian"] == post["/murid/latihan-harian"] == "murid"
    assert urutan.index("/murid/latihan-harian") == urutan.index("/murid/langganan") + 1
    # Paket Belajar 1 Bulan (sakelar PAKET_BELAJAR): exact murid, tepat setelah Latihan Harian; GET dan POST di bawahnya.
    assert get["/murid/paket"] == post["/murid/paket"] == "murid"
    assert urutan.index("/murid/paket") == urutan.index("/murid/latihan-harian") + 1
    # Daftar paket selalu tampil; halaman tagihan per kode dan konfirmasi hapus murid di bawah /murid/paket (GET), hapus juga POST.
    assert get["/murid/paket/tagihan"] == get["/murid/paket/hapus"] == "murid" and post["/murid/paket/hapus"] == "murid"
    assert urutan.index("/murid/paket/tagihan") == urutan.index("/murid/paket") + 1
    # Jadwal Private (orang tua): exact murid, tanpa entri GET; sakelar PAKET_BELAJAR mati = jalur murid asing.
    for rute in ("/murid/paket/jadwal-private/ajukan", "/murid/paket/jadwal-private/batal"):
        assert post[rute] == "murid" and rute not in get
    # `/cek-kemampuan` exact tetap publik; rute akun di bawahnya exact dan guru.
    assert get["/cek-kemampuan"] == "publik"
    assert get["/cek-kemampuan/mulai"] == get["/cek-kemampuan/hasil"] == "guru"
    assert post["/cek-kemampuan/mulai"] == post["/cek-kemampuan/tautan"] == "guru"
    assert "/cek-kemampuan/tautan" not in get
    assert urutan.index("/cek-kemampuan") < urutan.index("/guru") < urutan.index("/cek-kemampuan/mulai")
    # Pesanan Paket Coba (Fase 3c-3): exact, guru. `/paket-coba` publik hanya GET exact dan
    # tidak menelurkan prefix: `/paket-coba/pesan` adalah rute guru (GET: status/PRG; POST: pesan).
    assert get["/pesanan"] == get["/pesanan/qr"] == get["/paket-coba/pesan"] == "guru"
    for rute in ("/paket-coba/pesan", "/pesanan/periksa", "/pesanan/ulang", "/pesanan/buat"):
        assert post[rute] == "guru"
    for rute in ("/pesanan/periksa", "/pesanan/ulang", "/pesanan/buat", "/pesanan/tagihan", "/pesanan/bukti"):
        assert rute not in get
    assert post["/pesanan/tagihan"] == post["/pesanan/bukti"] == post["/pesanan/tagihan/ulang"] == "guru"
    assert "/pesanan/tagihan/ulang" not in get
    for rute in ("/admin/pesanan/verifikasi", "/admin/pesanan/bukti", "/admin/pesanan/order"):
        assert get[rute] == "admin" and rute not in post
    for rute in ("/admin/pesanan/setujui", "/admin/pesanan/tolak", "/admin/pesanan/voucher"):
        assert post[rute] == "admin" and rute not in get
    assert "/admin/pesanan/terbit" not in post and "/admin/pesanan/terbit" not in get  # aksi admin dihapus (D1-2)
    assert get["/admin/pesanan/rekening"] == post["/admin/pesanan/rekening"] == "admin"
    assert get["/admin/sakelar"] == post["/admin/sakelar"] == "admin"
    assert get["/admin/langganan"] == post["/admin/langganan"] == "admin"
    assert get["/admin/kelas"] == post["/admin/kelas"] == "admin"
    assert get["/admin/kurikulum/cp"] == post["/admin/kurikulum/cp"] == "admin"
    assert get["/admin/kurikulum"] == get["/admin/kurikulum/cp-detail"] == get["/admin/kurikulum/buat"] == "admin"
    assert not {"/admin/kurikulum", "/admin/kurikulum/cp-detail", "/admin/kurikulum/buat"} & set(post)
    assert post["/admin/kurikulum/cp/kembalikan"] == "admin" and "/admin/kurikulum/cp/kembalikan" not in get
    assert get["/admin/kurikulum/label"] == post["/admin/kurikulum/label"] == "admin"
    assert post["/admin/kurikulum/label/kembalikan"] == "admin" and "/admin/kurikulum/label/kembalikan" not in get
    for rute in ("/admin/kurikulum/cetakan", "/admin/kurikulum/cetakan/baru", "/admin/kurikulum/cetakan/periksa"):
        assert get[rute] == "admin"
    assert "/admin/kurikulum/cetakan" not in post and "/admin/kurikulum/cetakan/periksa" not in post
    for rute in ("/admin/kurikulum/cetakan/baru", "/admin/kurikulum/cetakan/ubah", "/admin/kurikulum/cetakan/setujui",
                 "/admin/kurikulum/cetakan/nonaktifkan", "/admin/kurikulum/cetakan/aktifkan"):
        assert post[rute] == "admin"
    for rute in ("/admin/kurikulum/cetakan/ubah", "/admin/kurikulum/cetakan/setujui",
                 "/admin/kurikulum/cetakan/nonaktifkan", "/admin/kurikulum/cetakan/aktifkan"):
        assert rute not in get
    assert post["/admin/kurikulum/cetakan/draf-ai"] == "admin" and "/admin/kurikulum/cetakan/draf-ai" not in get
    assert get["/paket-coba"] == "publik" and "/paket-coba" not in post
    assert get["/contoh-peta-kemampuan"] == "publik" and "/contoh-peta-kemampuan" not in post
    assert get["/contoh-peta-kemampuan/lembar"] == "publik" and "/contoh-peta-kemampuan/lembar" not in post
    assert urutan.index("/contoh-peta-kemampuan/lembar") < urutan.index("/guru")
    assert urutan.index("/pesanan") > urutan.index("/guru")


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


def test_anonim_post_rute_pilih_yang_dihapus_sama_dengan_rute_murid_tak_dikenal(server):
    """`/murid/pesanan/pilih` tidak ada lagi: anonim 401 persis seperti rute tak dikenal di bawah `/murid/pesanan`."""
    kode_pilih, isi_pilih, _ = _minta_mentah(server, "/murid/pesanan/pilih", data={})
    kode_asing, isi_asing, _ = _minta_mentah(server, "/murid/pesanan/tidak-ada-rute", data={})
    assert kode_pilih == kode_asing == 401
    assert isi_pilih == isi_asing


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
    # Anonim tanpa kuki: /masuk polos tanpa pesan "sesi habis" (audit area anak #15).
    assert lokasi == "/masuk"
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


def test_post_lintas_situs_ke_lembaga_ditolak_palang_asal(server):
    """`/lembaga/pindah` tidak dikecualikan dari palang asal dispatcher."""
    kode, isi, _tajuk = server.minta(
        "/lembaga/pindah", auth=("guru", SANDI_GURU), data={}, headers=LINTAS_SITUS
    )
    assert kode == 403 and "Permintaan ditolak" in isi


def test_guru_biasa_di_lembaga_mendapat_404_identik_rute_tak_dikenal(server):
    """Guru yang bukan pemilik les: 404 yang sama untuk GET dan POST."""
    acuan = server.minta("/rute-tidak-ada", auth=("guru", SANDI_GURU))
    assert acuan[0] == 404
    for jalur in ("/lembaga", "/lembaga/pindah"):
        kode, isi, _tajuk = server.minta(jalur, auth=("guru", SANDI_GURU))
        assert (kode, isi) == (acuan[0], acuan[1]), jalur
    kode, isi, _tajuk = server.minta(
        "/lembaga/pindah", auth=("guru", SANDI_GURU), data={}
    )
    assert (kode, isi) == (acuan[0], acuan[1])


def test_head_ditolak_eksplisit(server):
    kode, isi, tajuk = server.minta("/", method="HEAD")
    assert kode == 405
    assert tajuk.get("Allow") == "GET, POST"
    assert isi == ""
