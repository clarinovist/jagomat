"""Beranda pendamping: rute peran, isolasi keluarga, dan status yang jujur."""

import http.client
import re
import urllib.parse
import sys
from pathlib import Path
from html.parser import HTMLParser

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth
import design_tokens as T
import database
import sessions
import teacher_pages
import style_stitch
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID


@pytest.fixture()
def server(tmp_path, monkeypatch):
    # Sesi HTTP tidak boleh memakai berkas default bersama worker xdist lain.
    monkeypatch.setattr(sessions, 'BERKAS_SESI', tmp_path / 'sesi.json')
    s = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("pendamping-lain", "sandi-sintetis-123", "guru")
    auth.tambah_akun("pengelola", "sandi-sintetis-123", "admin")
    with s.buka() as kon:
        sendiri = database.tambah_siswa(kon, "Anak Milik Sendiri", pemilik="guru")
        asing = database.tambah_siswa(kon, "Anak Keluarga Lain", pemilik="pendamping-lain")
        database.buat_sesi(kon, sendiri, seed=7)
        database.buat_sesi(kon, asing, seed=8)
    yield s
    s.berhenti()


def _token(nama, peran):
    akun = auth.cari_akun(nama)
    return sessions.buat(
        akun["pengguna"], peran, id_akun=akun["id_akun"],
        revisi_auth=akun["revisi_auth"],
    )


def _minta(s, jalur, data=None, token=None):
    """Jangan ikuti redirect agar Location dan kuki benar-benar diperiksa."""
    alamat = urllib.parse.urlsplit(s.alamat)
    kon = http.client.HTTPConnection(alamat.hostname, alamat.port, timeout=10)
    tajuk = {"Content-Type": "application/x-www-form-urlencoded"}
    if token:
        tajuk["Cookie"] = "osn_sesi=" + token
    try:
        kon.request("POST" if data is not None else "GET", jalur,
                    urllib.parse.urlencode(data) if data is not None else None, tajuk)
        r = kon.getresponse()
        return r.status, r.read().decode(), dict(r.getheaders())
    finally:
        kon.close()


@pytest.mark.parametrize("nama,sandi,tujuan", [
    ("guru", SANDI_GURU, "/guru"),
    ("feby", SANDI_MURID, "/murid"),
    ("pengelola", "sandi-sintetis-123", "/admin"),
])
def test_login_ke_beranda_peran_dengan_kuki_sah(server, nama, sandi, tujuan):
    kode, _, tajuk = _minta(server, "/masuk", {"nama": nama, "sandi": sandi})
    assert kode == 303
    assert tajuk["Location"] == tujuan
    token = tajuk["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
    assert sessions.ambil(token)[0] == nama
    if tujuan == "/guru":
        assert 'id="judul-guru"' in _minta(server, tujuan, token=token)[1]


def test_fixture_sesi_beranda_terisolasi(server, tmp_path):
    assert sessions.BERKAS_SESI == tmp_path / 'sesi.json'
    assert sessions.BERKAS_SESI.parent == server.db.parent


def test_daftar_langsung_ke_beranda_guru(server):
    halaman = _minta(server, "/daftar")[1]
    token_form = re.search(r'name="token_form" value="([^"]+)"', halaman).group(1)
    kode, _, tajuk = _minta(server, "/daftar", {
        "nama": "pendamping-baru", "sandi": "sandi-sintetis-123",
        "setuju": "1", "token_form": token_form,
    })
    assert kode == 303
    assert tajuk["Location"] == "/guru"
    assert "HttpOnly" in tajuk["Set-Cookie"]


def test_gagal_login_tidak_menerbitkan_kuki(server):
    kode, isi, tajuk = _minta(server, "/masuk", {"nama": "guru", "sandi": "salah"})
    assert kode == 200
    assert "belum cocok" in isi
    assert "Set-Cookie" not in tajuk


@pytest.mark.parametrize("jalur", ["/", "/ortu", "/ortu/"])
def test_alias_guru_mempertahankan_pesan_tanpa_redirect_bebas(server, jalur):
    token = _token("guru", "guru")
    kode, _, tajuk = _minta(server, jalur + "?pesan=Halo&sorot=7&next=https://contoh.invalid", token=token)
    assert kode == 303
    assert tajuk["Location"] == "/guru?pesan=Halo&sorot=7"


@pytest.mark.parametrize("jalur", ["/guru", "/guru/", "/ortu", "/ortu/"])
@pytest.mark.parametrize("ident", [None, ("feby", "murid"), ("tidak-sah", None)])
def test_palang_beranda_tidak_membuka_db(server, monkeypatch, jalur, ident):
    token = _token(*ident) if ident and ident[1] else (ident[0] if ident else None)

    def dilarang(*args, **kwargs):
        raise AssertionError("Palang beranda membuka DB sebelum menolak pengunjung")

    monkeypatch.setattr(database, "buka", dilarang)
    kode, isi, _ = _minta(server, jalur, token=token)
    assert kode == 401
    assert "Anak Milik Sendiri" not in isi and "Anak Keluarga Lain" not in isi


@pytest.mark.parametrize("jalur", ["/", "/guru", "/ortu"])
def test_pengelola_tetap_menuju_panel_sendiri(server, jalur):
    kode, _, tajuk = _minta(server, jalur, token=_token("pengelola", "admin"))
    assert kode == 303
    assert tajuk["Location"] == "/admin"


@pytest.mark.parametrize("jalur", ["/guru", "/guru/", "/ortu", "/"])
def test_beranda_hanya_anak_sendiri_dan_get_tidak_menulis(server, jalur):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta(jalur, auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "Anak Milik Sendiri" in isi
    assert "Anak Keluarga Lain" not in isi
    assert 'id="judul-guru"' in isi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


class Markup(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.tag = []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        self.tag.append((tag, dict(attrs)))


def _isi(server, pesan=""):
    with server.buka() as kon:
        return teacher_pages.halaman_utama_stitch(kon, pemilik="guru", pesan=pesan).decode()


def test_semantik_satu_kartu_dan_satu_tambah_anak(server):
    isi = _isi(server, '<img src=x onerror="x">')
    tag = Markup(isi).tag
    assert ("main", {"aria-labelledby": "judul-guru"}) in tag
    assert sum(nama == "h1" for nama, _ in tag) == 1
    tautan = [a["href"] for t, a in tag if t == "a"]
    assert sum(t.startswith("/anak/") for t in tautan) == 1
    assert tautan.count("/akun?section=siswa") == 1
    assert "/guru" in tautan
    assert 'role="status"' in isi
    assert '&lt;img src=x onerror=&quot;x&quot;&gt;' in isi
    assert '<img src=x' not in isi
    assert "Orang Tua / Guru" in isi


def test_keadaan_kosong_bukan_klaim_selesai(server):
    with server.buka() as kon:
        isi = teacher_pages.halaman_utama_stitch(kon, pemilik="belum-punya-anak").decode()
    assert "Tambahkan anak pertama" in isi
    assert "semua direview" not in isi
    assert isi.count('href="/akun?section=siswa"') == 1
    assert 'action="/sesi-baru/' not in isi


@pytest.mark.parametrize("keadaan,teks", [
    ("baru", "1 belum dikirim"),
    ("selesai", "1 menunggu diperiksa"),
    ("direview", "semua direview"),
    ("warisan", "1 belum dikirim"),
    ("tanpa-sesi", "Belum ada sesi"),
])
def test_status_sesi_tidak_mengarang_review(server, keadaan, teks):
    with server.buka() as kon:
        if keadaan == "tanpa-sesi":
            database.tambah_siswa(kon, "Tanpa Sesi", pemilik="kosong")
        else:
            kon.execute("UPDATE sesi SET selesai=?, direview=? WHERE siswa_id IN (SELECT id FROM siswa WHERE pemilik='guru')", (
                "2026-09-09 12:00:00" if keadaan in ("selesai", "direview") else None,
                "2026-09-09 12:01:00" if keadaan in ("direview", "warisan") else None,
            ))
        isi = teacher_pages.halaman_utama_stitch(kon, pemilik="kosong" if keadaan == "tanpa-sesi" else "guru").decode()
    badan = isi.split("<body", 1)[1]
    assert teks in badan
    if keadaan != "selesai":
        assert "menunggu diperiksa" not in badan
    if keadaan in ("baru", "warisan", "tanpa-sesi"):
        assert "semua direview" not in badan


def test_status_campuran_tetap_memisahkan_sesi_belum_dikirim(server):
    with server.buka() as kon:
        sid = kon.execute("SELECT id FROM siswa WHERE pemilik='guru'").fetchone()[0]
        sesi = database.buat_sesi(kon, sid, seed=9)
        kon.execute("UPDATE sesi SET selesai='2026-09-09 12:00:00' WHERE id=?", (sesi,))
    isi = _isi(server)
    assert "1 menunggu diperiksa" in isi
    assert "1 belum dikirim" in isi
    assert "2 latihan tercatat" in isi


@pytest.mark.parametrize("keadaan_batal", ["baru", "selesai", "direview", "warisan"])
@pytest.mark.parametrize("keadaan_lain", [None, "baru", "selesai", "direview", "warisan"])
def test_sesi_dibatalkan_dipisah_dari_antrean(server, keadaan_batal, keadaan_lain):
    def atur(kon, sesi, keadaan):
        kon.execute("UPDATE sesi SET selesai=?, direview=? WHERE id=?", (
            "2026-09-09 12:00:00" if keadaan in ("selesai", "direview") else None,
            "2026-09-09 12:01:00" if keadaan in ("direview", "warisan") else None,
            sesi,
        ))

    with server.buka() as kon:
        siswa = kon.execute("SELECT id FROM siswa WHERE pemilik='guru'").fetchone()[0]
        batal = kon.execute("SELECT id FROM sesi WHERE siswa_id=?", (siswa,)).fetchone()[0]
        atur(kon, batal, keadaan_batal)
        database.batalkan_sesi(kon, batal, "Pembatalan sintetis")
        if keadaan_lain:
            lain = database.buat_sesi(kon, siswa, seed=9)
            atur(kon, lain, keadaan_lain)
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta("/guru", auth=("guru", SANDI_GURU))
    assert kode == 200
    kartu = re.search(r'<a class="st-kartu kartu-anak"[^>]*>.*?</a>', isi, re.S).group()
    # Assertion status ditempatkan sebelum label total: merah harus menangkap
    # bug antrean, bukan hanya pergantian kata "sesi" menjadi "latihan".
    assert ("belum dikirim" in kartu) == (keadaan_lain in ("baru", "warisan"))
    assert ("menunggu diperiksa" in kartu) == (keadaan_lain == "selesai")
    assert ("semua direview" in kartu) == (keadaan_lain == "direview")
    if keadaan_lain in ("baru", "warisan"):
        assert ">1 belum dikirim</span>" in kartu
    if keadaan_lain == "selesai":
        assert ">1 menunggu diperiksa</span>" in kartu
    assert ("Tidak ada latihan yang perlu dikerjakan." in kartu) == (keadaan_lain is None)
    assert ">1 dibatalkan</span>" in kartu
    assert f'>{2 if keadaan_lain else 1} latihan tercatat</span>' in kartu
    assert "Belum ada sesi" not in kartu
    assert "Anak Keluarga Lain" not in isi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_rekap_pembatalan_tidak_tercampur_antar_anak(server):
    with server.buka() as kon:
        pertama = kon.execute("SELECT id FROM siswa WHERE pemilik='guru'").fetchone()[0]
        kedua = database.tambah_siswa(kon, "Anak Demo Kedua", pemilik="guru")
        kosong = database.tambah_siswa(kon, "Anak Demo Tanpa Sesi", pemilik="guru")
        for seed, keadaan in ((21, "batal"), (22, "selesai"), (23, "direview")):
            sesi = database.buat_sesi(kon, pertama, seed=seed)
            if keadaan == "batal":
                database.batalkan_sesi(kon, sesi)
            else:
                kon.execute("UPDATE sesi SET selesai=?, direview=? WHERE id=?", (
                    "2026-09-09 12:00:00",
                    "2026-09-09 12:01:00" if keadaan == "direview" else None, sesi,
                ))
        database.batalkan_sesi(kon, database.buat_sesi(kon, kedua, seed=24))
        database.batalkan_sesi(kon, database.buat_sesi(kon, kedua, seed=25))
    isi = _isi(server)
    kartu = dict(re.findall(
        r'<a class="st-kartu kartu-anak" href="/anak/(\d+)">(.*?)</a>', isi, re.S,
    ))
    assert set(kartu) == {str(pertama), str(kedua), str(kosong)}
    assert ">4 latihan tercatat</span>" in kartu[str(pertama)]
    for teks in ("1 dibatalkan", "1 belum dikirim", "1 menunggu diperiksa"):
        assert f">{teks}</span>" in kartu[str(pertama)]
    assert "semua direview" not in kartu[str(pertama)]
    assert ">2 latihan tercatat</span>" in kartu[str(kedua)]
    assert ">2 dibatalkan</span>" in kartu[str(kedua)]
    assert "Tidak ada latihan yang perlu dikerjakan." in kartu[str(kedua)]
    assert ">0 latihan tercatat</span>" in kartu[str(kosong)]
    assert "Belum ada sesi" in kartu[str(kosong)]
    assert "dibatalkan" not in kartu[str(kosong)]


def test_nama_dan_pesan_http_tetap_di_escape(server):
    with server.buka() as kon:
        kon.execute("UPDATE siswa SET nama=? WHERE pemilik='guru'", ('<b>Nama & Uji</b>',))
    query = urllib.parse.urlencode({"pesan": '<script>alert(1)</script>', "sorot": "bukan-angka"})
    kode, isi, _ = server.minta('/guru?' + query, auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "&lt;b&gt;Nama &amp; Uji&lt;/b&gt;" in isi
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in isi
    assert '<script>alert(1)</script>' not in isi


def test_gagal_renderer_tidak_menyamar_sebagai_landing(server, monkeypatch):
    import web

    def rusak(*args, **kwargs):
        raise RuntimeError("galat-sintetis-internal")

    monkeypatch.setattr(web, "halaman_utama_stitch", rusak)
    kode, isi, _ = server.minta("/guru", auth=("guru", SANDI_GURU))
    assert kode == 500
    assert "Ada yang bermasalah" in isi
    assert "galat-sintetis-internal" not in isi
    assert 'class="landing-bungkus-st"' not in isi


@pytest.mark.parametrize("teks,latar", [
    (T.TEKS_VARIAN, T.LATAR_MURID),
    (T.TEKS_VARIAN, T.LATAR_KARTU),
    (T.TEKS_PUTIH, T.AKSEN_KORAL_TUA),
    (T.AKSEN_TEAL_TUA, T.LATAR_KARTU),
    (T.BADGE_ADMIN_TEKS, T.BADGE_ADMIN_BG),
])
def test_kontras_teks_kecil_memadai(teks, latar):
    def luminansi(warna):
        nilai = warna.lstrip("#")
        if len(nilai) == 3:
            nilai = "".join(c * 2 for c in nilai)
        rgb = [int(nilai[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
        return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))

    a, b = sorted((luminansi(teks), luminansi(latar)))
    assert (b + .05) / (a + .05) >= 4.5


def test_css_terisolasi_fokus_dan_nama_panjang():
    css = style_stitch.GAYA_STITCH
    assert ".guru-beranda-st" in css
    assert ".guru-beranda-st :is(a, button, summary):focus-visible" in css
    assert ".guru-nama-st" in css
    sumber = style_stitch.__file__
    with open(sumber) as f:
        blok = f.read().split("/* Beranda pendamping editorial", 1)[1].split("/* Akhir beranda pendamping */", 1)[0]
    assert "overflow-wrap: anywhere" in blok
    assert "@media" in blok
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", blok)
