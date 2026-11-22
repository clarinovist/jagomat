"""Latihan Lomba lewat HTTP sungguhan (ServerUji): gerbang, akses, alur sesi, timer server, kepemilikan.

Waktu memakai angka literal (900 = 15 menit, 600, 300) dan jam server dipalsukan lewat
`contest_http._sekarang`; data sepenuhnya sintetis di tmp_path.
"""
import base64
import hashlib
import html
import itertools
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import contest_http  # noqa: E402
import contest_session  # noqa: E402
import contest_store  # noqa: E402
import database  # noqa: E402
from http_test_kit import SANDI_MURID, ServerUji, _basic  # noqa: E402

T0 = 1_800_000_000
SANDI_DUA = "sandi-budi-12345"
MURID_SATU = ("feby", SANDI_MURID)
MURID_DUA = ("budi-uji", SANDI_DUA)
ASAL_LAIN = {"Origin": "https://contoh.example"}
HEADER_PENTING = ("location", "cache-control", "content-security-policy", "content-type")
RUTE_GET = ("/murid/lomba", "/murid/lomba/sesi/1?no=1", "/murid/lomba/sesi/1/selesai", "/murid/lomba/hasil/1")
RUTE_POST = ("/murid/lomba/mulai", "/murid/lomba/sesi/1/jawab", "/murid/lomba/sesi/1/kumpul")
PESAN_404 = "Halaman tidak ada"
P_GALAT = "Tulis angkanya saja, tanpa huruf atau tanda baca. Contoh: 120"


class _Jam:
    def __init__(self, awal):
        self.t = awal

    def __call__(self):
        return self.t


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    """Pertahankan 303 sebagai 303 (urlopen biasa akan mengikutinya)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Hasil:
    def __init__(self, kode, isi, header):
        self.kode, self.isi = kode, isi
        self.header = {k.lower(): v for k, v in header.items()}

    @property
    def lokasi(self):
        return self.header.get("location")

    def sidik(self):
        return self.kode, self.isi, {k: self.header[k] for k in HEADER_PENTING if k in self.header}


def _minta(uji, jalur, *, auth_=None, data=None, header=None, isi_mentah=None):
    isi = isi_mentah if isi_mentah is not None else (urllib.parse.urlencode(data).encode() if data is not None else None)
    req = urllib.request.Request(uji.alamat + jalur, data=isi, method="POST" if isi is not None else "GET")
    if isi is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if auth_:
        req.add_header("Authorization", _basic(*auth_))
    for nama, nilai in (header or {}).items():
        req.add_header(nama, nilai)
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return Hasil(r.status, r.read(), dict(r.headers))
    except urllib.error.HTTPError as e:
        return Hasil(e.code, e.read(), dict(e.headers))


@pytest.fixture
def jam(monkeypatch):
    jam_uji = _Jam(T0)
    monkeypatch.setattr(contest_http, "_sekarang", jam_uji)
    return jam_uji


@pytest.fixture
def server(tmp_path, monkeypatch, jam):
    monkeypatch.setenv("OSN_LOMBA", "1")
    benih = itertools.count(101)
    monkeypatch.setattr(contest_store.secrets, "randbits", lambda _bit: next(benih))
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        with uji.buka() as kon:
            uji.anak_satu = database.tambah_siswa(kon, "feby", pemilik="guru")
            uji.anak_dua = database.tambah_siswa(kon, "Budi Sintetis", pemilik="guru")
        auth.tambah_akun("budi-uji", SANDI_DUA, "murid", siswa_id=uji.anak_dua)
        yield uji
    finally:
        uji.berhenti()


def _get(uji, jalur, pengguna=MURID_SATU, **kw):
    return _minta(uji, jalur, auth_=pengguna, **kw)


def _post(uji, jalur, data=None, pengguna=MURID_SATU, **kw):
    return _minta(uji, jalur, auth_=pengguna, data={} if data is None else data, **kw)


def _mulai(uji, pengguna=MURID_SATU):
    hasil = _post(uji, "/murid/lomba/mulai", pengguna=pengguna)
    cocok = re.fullmatch(r"/murid/lomba/sesi/(\d+)\?no=1", hasil.lokasi or "")
    assert hasil.kode == 303 and cocok, (hasil.kode, hasil.lokasi)
    return int(cocok.group(1))


def _tabel(uji, nama, urut):
    with uji.buka() as kon:
        return [tuple(b) for b in kon.execute(f"SELECT * FROM {nama} ORDER BY {urut}")]


def _keadaan(uji):
    return {nama: _tabel(uji, nama, urut) for nama, urut in
            (("lomba_sesi", "id"), ("lomba_soal", "sesi_id, nomor"), ("lomba_jawaban", "sesi_id, nomor"))}


def _jawaban(uji, sesi_id):
    with uji.buka() as kon:
        return {b["nomor"]: b["jawaban"] for b in
                kon.execute("SELECT nomor, jawaban FROM lomba_jawaban WHERE sesi_id=?", (sesi_id,))}


def _status(uji, sesi_id):
    with uji.buka() as kon:
        return tuple(kon.execute("SELECT status, selesai_epoch FROM lomba_sesi WHERE id=?", (sesi_id,)).fetchone())


def _jenis(uji, sesi_id, nomor):
    with uji.buka() as kon:
        return kon.execute("SELECT jenis FROM lomba_soal WHERE sesi_id=? AND nomor=?", (sesi_id, nomor)).fetchone()[0]


def _nomor_berjenis(uji, sesi_id, jenis):
    return next(n for n in range(1, 11) if _jenis(uji, sesi_id, n) == jenis)


def _tidak_ada(uji, pengguna=MURID_SATU):
    return _get(uji, "/murid/tidak-ada", pengguna)


def _sha256_skrip(isi):
    return [base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode() for m in re.finditer(rb"<script>(.*?)</script>", isi, re.S)]


# 1 --- gerbang mati ------------------------------------------------------------------

@pytest.mark.parametrize("jalur", RUTE_GET)
@pytest.mark.parametrize("pengguna", [MURID_SATU, None], ids=["murid", "anonim"])
def test_gerbang_mati_get_identik_dengan_jalur_murid_tak_dikenal(server, monkeypatch, jalur, pengguna):
    monkeypatch.setenv("OSN_LOMBA", "0")

    lomba = _get(server, jalur, pengguna)
    biasa = _get(server, "/murid/tidak-ada", pengguna)

    assert lomba.sidik() == biasa.sidik()
    assert (lomba.kode == 404) if pengguna else (lomba.kode == 303)


@pytest.mark.parametrize("jalur", RUTE_POST)
@pytest.mark.parametrize("pengguna", [MURID_SATU, None], ids=["murid", "anonim"])
def test_gerbang_mati_post_identik_dengan_jalur_murid_tak_dikenal_dan_tanpa_efek(server, monkeypatch, jalur, pengguna):
    monkeypatch.setenv("OSN_LOMBA", "0")
    sebelum = _keadaan(server)

    lomba = _post(server, jalur, {"no": "1", "jawaban": "A"}, pengguna)
    biasa = _post(server, "/murid/tidak-ada", {"no": "1", "jawaban": "A"}, pengguna)

    assert lomba.sidik() == biasa.sidik()
    assert _keadaan(server) == sebelum


# 2 --- gerbang hidup, anonim ---------------------------------------------------------

@pytest.mark.parametrize("jalur", RUTE_GET)
def test_anonim_get_dialihkan_ke_masuk_seperti_halaman_murid_lain(server, jalur):
    lomba = _get(server, jalur, None)
    murid = _get(server, "/murid", None)

    assert lomba.kode == 303 and lomba.lokasi.startswith("/masuk?galat=")
    assert lomba.lokasi == murid.lokasi


@pytest.mark.parametrize("jalur", RUTE_POST)
def test_anonim_post_ditolak_401_seperti_post_murid_lain(server, jalur):
    sebelum = _keadaan(server)

    lomba = _post(server, jalur, {"no": "1"}, None)
    murid = _post(server, "/murid/kerjakan/1", {}, None)

    assert lomba.kode == 401 and lomba.sidik() == murid.sidik()
    assert _keadaan(server) == sebelum


def test_akun_guru_tidak_bisa_membuka_halaman_lomba(server):
    guru = _get(server, "/murid/lomba", ("guru", "sandi-guru-panjang-123"))

    assert guru.kode == 303 and guru.lokasi.startswith("/masuk?")


def test_akun_murid_belum_terhubung_melihat_halaman_belum_terhubung_dan_tidak_bisa_memulai(server):
    auth.tambah_akun("yatim", "sandi-yatim-12345", "murid")
    yatim = ("yatim", "sandi-yatim-12345")

    halaman = _get(server, "/murid/lomba", yatim)
    mulai = _post(server, "/murid/lomba/mulai", pengguna=yatim)

    assert halaman.kode == 200 and b"Belum terhubung" in halaman.isi
    assert mulai.sidik() == _tidak_ada(server).sidik() and _tabel(server, "lomba_sesi", "id") == []


# 3 --- lintas asal -------------------------------------------------------------------

@pytest.mark.parametrize("header", [ASAL_LAIN, {"Sec-Fetch-Site": "cross-site"}], ids=["origin", "fetch-metadata"])
def test_post_lintas_asal_ditolak_dan_tidak_membuat_sesi(server, header):
    hasil = _post(server, "/murid/lomba/mulai", header=header)

    assert hasil.kode == 403
    assert _tabel(server, "lomba_sesi", "id") == []


# 4 --- alur lengkap ------------------------------------------------------------------

def test_mulai_menampilkan_soal_satu_dengan_timer_strip_dan_csp_cocok(server):
    sesi_id = _mulai(server)

    halaman = _get(server, f"/murid/lomba/sesi/{sesi_id}?no=1")
    isi = halaman.isi.decode()

    assert halaman.kode == 200 and 'data-sisa="900"' in isi and "Soal 1 dari 10" in isi
    assert len(re.findall(r'<button type="submit" name="pindah" value="\d+" class="nomor ', isi)) == 10
    assert halaman.header["cache-control"] == "no-store"
    csp = halaman.header["content-security-policy"]
    hash_skrip = _sha256_skrip(halaman.isi)
    assert len(hash_skrip) == 1 and f"script-src 'sha256-{hash_skrip[0]}'" in csp


def test_awal_menawarkan_mulai_lalu_lanjutkan_setelah_sesi_ada(server, jam):
    sebelum = _get(server, "/murid/lomba")
    sesi_id = _mulai(server)
    jam.t = T0 + 300
    sesudah = _get(server, "/murid/lomba")

    assert b'action="/murid/lomba/mulai"' in sebelum.isi and b"Lanjutkan" not in sebelum.isi
    assert f"/murid/lomba/sesi/{sesi_id}?no=1".encode() in sesudah.isi and b"10:00" in sesudah.isi
    assert sesudah.header["cache-control"] == "no-store"


def test_beranda_murid_tanpa_sesi_guru_menampilkan_kartu_lomba_besar_pengganti_pesan_kosong(server):
    isi = _get(server, "/murid").isi.decode()

    assert isi.count('href="/murid/lomba"') == 1 and "Grand Final Corexis" in isi and "Mulai latihan" in isi
    assert "lomba-beranda besar" in isi and "Belum ada latihan dari gurumu." in isi
    assert "Siap untuk latihan pertama?" not in isi and "Latihan Lomba" not in isi


def test_beranda_murid_dengan_sesi_berjalan_menawarkan_lanjutkan_ke_soal_kosong_pertama_dan_sisa_waktu(server, jam):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "pg")
    for n in range(1, nomor):
        _jawab_valid(server, sesi_id, n)
    jam.t = T0 + 125

    isi = _get(server, "/murid").isi.decode()

    assert f'href="/murid/lomba/sesi/{sesi_id}?no={nomor}">Lanjutkan</a>' in isi
    assert "Latihanmu masih berjalan" in isi and "Sisa waktu 12:55" in isi
    assert f"{nomor - 1} dari 10 soal terisi" in isi and "Mulai latihan" not in isi


def test_beranda_murid_tidak_menautkan_ke_lomba_saat_gerbang_mati(server, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "0")

    isi = _get(server, "/murid").isi

    assert b"/murid/lomba" not in isi and b"Latihan Lomba" not in isi


# 5 --- muat ulang tidak mengembalikan timer ------------------------------------------

def test_muat_ulang_di_tengah_sesi_tidak_mengembalikan_timer(server, jam):
    sesi_id = _mulai(server)
    jam.t = T0 + 300

    isi = _get(server, f"/murid/lomba/sesi/{sesi_id}?no=2").isi.decode()

    assert 'data-sisa="600"' in isi and ">10:00<" in isi


# 6 --- setelah batas -----------------------------------------------------------------

def test_setelah_batas_sesi_dialihkan_ke_hasil_waktu_habis_dan_tidak_bisa_kembali(server, jam):
    sesi_id = _mulai(server)
    jam.t = T0 + 900

    soal = _get(server, f"/murid/lomba/sesi/{sesi_id}?no=1")
    hasil = _get(server, f"/murid/lomba/hasil/{sesi_id}")
    lagi = _get(server, f"/murid/lomba/sesi/{sesi_id}?no=3")
    selesai = _get(server, f"/murid/lomba/sesi/{sesi_id}/selesai")

    assert soal.kode == 303 and soal.lokasi == f"/murid/lomba/hasil/{sesi_id}"
    assert hasil.kode == 200 and b"Waktu habis!" in hasil.isi and b"Waktu: 15:00" in hasil.isi
    assert lagi.kode == 303 and selesai.kode == 303
    assert _status(server, sesi_id) == ("waktu_habis", T0 + 900)


def test_satu_detik_sebelum_batas_sesi_masih_berjalan(server, jam):
    sesi_id = _mulai(server)
    jam.t = T0 + 899

    halaman = _get(server, f"/murid/lomba/sesi/{sesi_id}?no=1")

    assert halaman.kode == 200 and b'data-sisa="1"' in halaman.isi and b'class="timer merah"' in halaman.isi


# 7 --- jawab setelah batas -----------------------------------------------------------

def test_jawab_setelah_batas_dialihkan_ke_hasil_tanpa_mengubah_jawaban(server, jam):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "pg")
    _post(server, f"/murid/lomba/sesi/{sesi_id}/jawab", {"no": nomor, "jawaban": "A"})
    jam.t = T0 + 900

    hasil = _post(server, f"/murid/lomba/sesi/{sesi_id}/jawab", {"no": nomor, "jawaban": "C"})

    assert hasil.kode == 303 and hasil.lokasi == f"/murid/lomba/hasil/{sesi_id}"
    assert _jawaban(server, sesi_id) == {nomor: "A"}
    assert _status(server, sesi_id)[0] == "waktu_habis"


@pytest.mark.parametrize("isian", [{"no": "1", "pindah": "2"}, {"no": "1"}, {"no": "1", "pindah": "2", "jawaban": ""}],
                         ids=["hanya-pindah", "hanya-nomor", "kosong-pindah"])
def test_jawab_tanpa_isian_setelah_batas_juga_dialihkan_ke_hasil_bukan_ke_soal(server, jam, isian):
    sesi_id = _mulai(server)
    jam.t = T0 + 900

    hasil = _post(server, f"/murid/lomba/sesi/{sesi_id}/jawab", isian)

    assert hasil.kode == 303 and hasil.lokasi == f"/murid/lomba/hasil/{sesi_id}"


# 8 --- selesai dan kumpul ------------------------------------------------------------

def _jawab_tiga_pertama(uji, sesi_id):
    for nomor in (1, 2, 3):
        jawaban = "A" if _jenis(uji, sesi_id, nomor) == "pg" else "12"
        assert _post(uji, f"/murid/lomba/sesi/{sesi_id}/jawab", {"no": nomor, "jawaban": jawaban}).kode == 303


def test_konfirmasi_selesai_menyebut_jumlah_belum_dijawab_yang_benar(server):
    sesi_id = _mulai(server)
    _jawab_tiga_pertama(server, sesi_id)

    halaman = _get(server, f"/murid/lomba/sesi/{sesi_id}/selesai")

    isi = halaman.isi.decode()
    assert halaman.kode == 200 and "Masih ada 7 soal kosong" in isi and "Kerjakan soal 4" in isi
    assert "Waktumu masih 15 menit" in isi and 'href="/murid/lomba/sesi/%d?no=4"' % sesi_id in isi
    assert halaman.header["cache-control"] == "no-store"


def test_kumpul_menampilkan_sesi_selesai_dan_kumpul_kedua_tidak_mengubah_apa_pun(server, jam):
    sesi_id = _mulai(server)
    jam.t = T0 + 200
    _jawab_tiga_pertama(server, sesi_id)
    jam.t = T0 + 330

    kumpul = _post(server, f"/murid/lomba/sesi/{sesi_id}/kumpul")
    hasil = _get(server, f"/murid/lomba/hasil/{sesi_id}")
    sebelum = _keadaan(server)
    jam.t = T0 + 500
    kumpul_lagi = _post(server, f"/murid/lomba/sesi/{sesi_id}/kumpul")

    assert kumpul.kode == 303 and kumpul.lokasi == f"/murid/lomba/hasil/{sesi_id}"
    assert hasil.kode == 200 and b"Sesi selesai!" in hasil.isi and b"Waktu: 05:30" in hasil.isi
    assert re.search(rb'<span class="sr-saja">Nilai: </span>\d+/10', hasil.isi)
    assert _status(server, sesi_id) == ("dikumpul", T0 + 330)
    assert kumpul_lagi.kode == 303 and _keadaan(server) == sebelum


def test_setelah_kumpul_layar_soal_dan_konfirmasi_tidak_bisa_dibuka_dan_jawab_tidak_berubah(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "pg")
    _post(server, f"/murid/lomba/sesi/{sesi_id}/jawab", {"no": nomor, "jawaban": "B"})
    _post(server, f"/murid/lomba/sesi/{sesi_id}/kumpul")

    soal = _get(server, f"/murid/lomba/sesi/{sesi_id}?no=1")
    selesai = _get(server, f"/murid/lomba/sesi/{sesi_id}/selesai")
    jawab = _post(server, f"/murid/lomba/sesi/{sesi_id}/jawab", {"no": nomor, "jawaban": "D"})

    assert soal.lokasi == selesai.lokasi == jawab.lokasi == f"/murid/lomba/hasil/{sesi_id}"
    assert _jawaban(server, sesi_id) == {nomor: "B"}


def test_latihan_lagi_setelah_selesai_membuat_sesi_baru(server):
    pertama = _mulai(server)
    _post(server, f"/murid/lomba/sesi/{pertama}/kumpul")

    kedua = _mulai(server)

    assert kedua != pertama and _status(server, kedua)[0] == "berjalan"


# 9 --- hasil saat berjalan -----------------------------------------------------------

def test_hasil_saat_berjalan_dialihkan_ke_soal_dengan_tubuh_kosong(server):
    sesi_id = _mulai(server)

    hasil = _get(server, f"/murid/lomba/hasil/{sesi_id}")

    assert hasil.kode == 303 and hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no=1"
    assert hasil.isi == b""


# 9b --- hasil rinci setelah sesi tidak berjalan ---------------------------------------

def _soal_db(uji, sesi_id):
    """Baris soal dengan kunci dibaca langsung dari DB (hanya di sisi uji)."""
    with uji.buka() as kon:
        return [dict(b) for b in kon.execute(
            "SELECT nomor, jenis, kunci, teks, pilihan_json, pengecoh_json, pembahasan_json "
            "FROM lomba_soal WHERE sesi_id=? ORDER BY nomor", (sesi_id,))]


def _huruf_kunci(soal):
    return "ABCD"[json.loads(soal["pilihan_json"]).index(soal["kunci"])]


def _nilai(isi):
    return re.search(r'<span class="sr-saja">Nilai: </span>(\d+/\d+)</p>', isi).group(1)


def _isi_semua(uji, sesi_id, benar):
    """Jawab sepuluh soal: semua benar, atau semua salah (huruf lain / angka 1 yang bukan kunci)."""
    for soal in _soal_db(uji, sesi_id):
        if soal["jenis"] == "pg":
            huruf = _huruf_kunci(soal)
            jawaban = huruf if benar else next(h for h in "ABCD" if h != huruf)
        else:
            jawaban = soal["kunci"] if benar else ("1" if soal["kunci"] != "1" else "2")
        assert _jawab(uji, sesi_id, no=soal["nomor"], jawaban=jawaban).kode == 303


def test_hasil_rinci_memuat_jawaban_anak_kunci_dan_pembahasan_sepuluh_soal(server):
    sesi_id = _mulai(server)
    _isi_semua(server, sesi_id, benar=False)
    _post(server, f"/murid/lomba/sesi/{sesi_id}/kumpul")

    hasil = _get(server, f"/murid/lomba/hasil/{sesi_id}")
    isi = hasil.isi.decode()

    assert hasil.kode == 200 and "Sesi selesai!" in isi and _nilai(isi) == "0/10"
    assert isi.count('class="hl-soal"') == 10 and isi.count("Jawabanmu: <strong>") == 10
    assert isi.count("Jawaban yang benar: <strong>") == 10
    for soal in _soal_db(server, sesi_id):
        kunci = _huruf_kunci(soal) if soal["jenis"] == "pg" else html.escape(soal["kunci"])
        assert f"Jawaban yang benar: <strong>{kunci}" in isi, soal["nomor"]
        assert all(html.escape(baris) in isi for baris in json.loads(soal["pembahasan_json"])), soal["nomor"]
    assert hasil.header["cache-control"] == "no-store" and "<script" not in isi
    assert "script-src 'none'" in hasil.header["content-security-policy"]


def test_hasil_rinci_semua_benar_tidak_menampilkan_jawaban_yang_benar_terpisah(server):
    sesi_id = _mulai(server)
    _isi_semua(server, sesi_id, benar=True)
    _post(server, f"/murid/lomba/sesi/{sesi_id}/kumpul")

    isi = _get(server, f"/murid/lomba/hasil/{sesi_id}").isi.decode()

    assert _nilai(isi) == "10/10" and "Jawaban yang benar" not in isi and isi.count('class="hl-status hl-benar"') == 10


def test_hasil_rinci_tidak_memuat_label_kesalahan_pengecoh_mana_pun(server):
    sesi_id = _mulai(server)
    _isi_semua(server, sesi_id, benar=False)
    _post(server, f"/murid/lomba/sesi/{sesi_id}/kumpul")
    isi = _get(server, f"/murid/lomba/hasil/{sesi_id}").isi.decode()

    label = []
    for soal in _soal_db(server, sesi_id):
        sah = [p["kesalahan"] for p in json.loads(soal["pengecoh_json"]) if p["kesalahan"]]
        dipakai = " ".join(json.loads(soal["pembahasan_json"]) + [soal["teks"]] + json.loads(soal["pilihan_json"]))
        label += [k for k in sah if k not in dipakai]

    assert len(label) >= 5
    for teks in label:
        assert teks not in isi and html.escape(teks) not in isi, teks
    assert "Kemungkinan kesalahan" not in isi


def test_hasil_waktu_habis_menandai_soal_kosong_tidak_dijawab_dan_tetap_menampilkan_pembahasan(server, jam):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "pg")
    soal = next(s for s in _soal_db(server, sesi_id) if s["nomor"] == nomor)
    _jawab(server, sesi_id, no=nomor, jawaban=_huruf_kunci(soal))
    jam.t = T0 + 900

    isi = _get(server, f"/murid/lomba/hasil/{sesi_id}").isi.decode()

    assert "Waktu habis!" in isi and _nilai(isi) == "1/10" and "Waktu: 15:00" in isi
    assert isi.count("tidak dijawab") == 9 and isi.count("Jawabanmu: <strong>belum diisi</strong>") == 9
    assert html.escape(json.loads(soal["pembahasan_json"])[0]) in isi


def test_halaman_awal_tanpa_sesi_selesai_tidak_menampilkan_latihan_terakhir(server):
    assert b"Latihan terakhir" not in _get(server, "/murid/lomba").isi


def test_halaman_awal_menampilkan_latihan_terakhir_maksimal_lima_terbaru_dulu_dengan_tanggal_wib_dan_nilai(server, jam):
    ids = []
    for i in range(6):
        jam.t = T0 + i * 1000
        sesi_id = _mulai(server)
        _isi_semua(server, sesi_id, benar=(i == 5))
        _post(server, f"/murid/lomba/sesi/{sesi_id}/kumpul")
        ids.append(sesi_id)

    isi = _get(server, "/murid/lomba").isi.decode()

    tautan = re.findall(r'<a class="tautan-latihan" href="(/murid/lomba/hasil/\d+)"><span>([^<]+)</span><strong>([^<]+)</strong>', isi)
    assert [t[0] for t in tautan] == [f"/murid/lomba/hasil/{i}" for i in reversed(ids[1:])]
    assert [t[1] for t in tautan] == ["Hari ini, 16.23", "Hari ini, 16.06", "Hari ini, 15.50",
                                       "Hari ini, 15.33", "Hari ini, 15.16"]
    assert [t[2] for t in tautan] == ["10/10", "0/10", "0/10", "0/10", "0/10"]
    assert f"/murid/lomba/hasil/{ids[0]}" not in isi


def test_latihan_terakhir_tidak_menampilkan_sesi_berjalan_atau_milik_anak_lain(server):
    selesai = _mulai(server, MURID_DUA)
    _post(server, f"/murid/lomba/sesi/{selesai}/kumpul", pengguna=MURID_DUA)
    _mulai(server)

    isi = _get(server, "/murid/lomba").isi

    assert b"Latihan terakhir" not in isi and f"/murid/lomba/hasil/{selesai}".encode() not in isi


# 10 --- tanpa kebocoran --------------------------------------------------------------

def _teks_rahasia(uji, sesi_id):
    """Pembahasan dan label pengecoh dari DB (hanya dibaca uji), diabaikan bila kebetulan tampil di teks soal."""
    rahasia = {}
    with uji.buka() as kon:
        for b in kon.execute("SELECT nomor, teks, pembahasan_json, pengecoh_json FROM lomba_soal WHERE sesi_id=?", (sesi_id,)):
            kandidat = [str(x) for x in json.loads(b["pembahasan_json"])]
            kandidat += [str(p["kesalahan"]) for p in json.loads(b["pengecoh_json"]) if p["kesalahan"]]
            rahasia[b["nomor"]] = [t for t in kandidat if t.strip() and t not in b["teks"]]
    return rahasia


def test_sepuluh_halaman_soal_tidak_membocorkan_pembahasan_label_pengecoh_atau_kata_kunci(server):
    sesi_id = _mulai(server)
    rahasia = _teks_rahasia(server, sesi_id)

    assert sum(len(v) for v in rahasia.values()) > 0
    for nomor in range(1, 11):
        isi = _get(server, f"/murid/lomba/sesi/{sesi_id}?no={nomor}").isi.decode()
        for teks in rahasia[nomor]:
            assert teks not in isi and html.escape(teks) not in isi, (nomor, teks)
        assert "kunci" not in isi.lower() and "pembahasan" not in isi.lower()
        if _jenis(server, sesi_id, nomor) == "pg":
            tombol = re.findall(r'<button type="submit" name="jawaban" value="[A-D]" class="pilih" aria-pressed="false">', isi)
            assert len(tombol) == 4 and 'class="pilih dipilih"' not in isi


# 11 --- perilaku POST jawab ----------------------------------------------------------

def _jawab(uji, sesi_id, **isian):
    return _post(uji, f"/murid/lomba/sesi/{sesi_id}/jawab", isian)


def test_isian_tanpa_pindah_seperti_enter_menyimpan_lalu_pindah_ke_soal_kosong_berikutnya(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="12", aksi="simpan")

    assert hasil.kode == 303 and hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no={nomor % 10 + 1}"
    assert _jawaban(server, sesi_id) == {nomor: "12"}


@pytest.mark.parametrize("ketikan", ["594", " 594 ", "5 9 4", "5 94", "5\u00a09\u00a04", "5\t94"])
def test_isian_dengan_spasi_lewat_http_tersimpan_sebagai_angka_tanpa_spasi(server, ketikan):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")

    hasil = _jawab(server, sesi_id, no=nomor, jawaban=ketikan, aksi="simpan")

    assert hasil.kode == 303 and "galat" not in hasil.lokasi
    assert _jawaban(server, sesi_id) == {nomor: "594"}


@pytest.mark.parametrize("ketikan", ["5.94", "5,94", "abc", "1234567"])
def test_isian_berpisah_titik_koma_atau_huruf_tetap_ditolak_lewat_http(server, ketikan):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")

    hasil = _jawab(server, sesi_id, no=nomor, jawaban=ketikan, aksi="simpan")

    assert "galat=angka" in hasil.lokasi and _jawaban(server, sesi_id) == {}


def test_klik_nomor_menyimpan_isian_terketik_lalu_pindah(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="34", pindah="5")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no=5"
    assert _jawaban(server, sesi_id) == {nomor: "34"}


def test_isian_kosong_bersama_pindah_tidak_menghapus(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")
    _jawab(server, sesi_id, no=nomor, jawaban="34")

    _jawab(server, sesi_id, no=nomor, jawaban="", pindah="5")
    _jawab(server, sesi_id, no=nomor, jawaban="   ", pindah="5", aksi="simpan")
    _jawab(server, sesi_id, no=nomor, jawaban="")

    assert _jawaban(server, sesi_id) == {nomor: "34"}


def test_aksi_simpan_dengan_isian_kosong_menghapus_jawaban(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")
    _jawab(server, sesi_id, no=nomor, jawaban="34")

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="", aksi="simpan")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no={nomor}"
    assert _jawaban(server, sesi_id) == {}


def test_isian_bukan_angka_dialihkan_ke_soal_itu_dengan_galat_dan_tidak_tersimpan(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")
    _jawab(server, sesi_id, no=nomor, jawaban="7")

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="abc", aksi="simpan", pindah="9")
    halaman = _get(server, hasil.lokasi)

    assert hasil.kode == 303 and hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no={nomor}&galat=angka&isi=abc"
    assert _jawaban(server, sesi_id) == {nomor: "7"}
    isi = halaman.isi.decode()
    assert halaman.kode == 200 and P_GALAT in isi and 'name="jawaban" value="abc"' in isi


def test_pilihan_ganda_huruf_tidak_sah_tidak_tersimpan_dan_huruf_kecil_dibakukan(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "pg")

    salah = _jawab(server, sesi_id, no=nomor, jawaban="E")
    kosong_state = _jawaban(server, sesi_id)
    _jawab(server, sesi_id, no=nomor, jawaban="b")
    halaman = _get(server, f"/murid/lomba/sesi/{sesi_id}?no={nomor}").isi.decode()

    assert salah.kode == 303 and "galat=angka" in salah.lokasi and kosong_state == {}
    assert _jawaban(server, sesi_id) == {nomor: "B"}
    assert re.search(r'class="pilih dipilih" aria-pressed="true"><span class="huruf">B<', halaman)


def _jawab_valid(uji, sesi_id, nomor):
    jawaban = "A" if _jenis(uji, sesi_id, nomor) == "pg" else "1"
    assert _jawab(uji, sesi_id, no=nomor, jawaban=jawaban, pindah=str(nomor)).kode == 303


def _isi_kecuali(uji, sesi_id, kosong):
    for nomor in range(1, 11):
        if nomor not in kosong:
            _jawab_valid(uji, sesi_id, nomor)


def _nomor_pg(uji, sesi_id):
    return [n for n in range(1, 11) if _jenis(uji, sesi_id, n) == "pg"]


def test_klik_pilihan_tanpa_pindah_langsung_ke_soal_kosong_berikutnya(server):
    sesi_id = _mulai(server)
    nomor = _nomor_pg(server, sesi_id)[0]

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="C")

    assert hasil.kode == 303 and hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no={nomor % 10 + 1}"
    assert _jawaban(server, sesi_id) == {nomor: "C"}


def test_auto_pindah_melewati_soal_yang_sudah_terisi_dan_memutar_ke_awal(server):
    sesi_id = _mulai(server)
    nomor = _nomor_pg(server, sesi_id)[-1]
    _isi_kecuali(server, sesi_id, {nomor, 1})

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="B")

    assert nomor > 1 and hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no=1"


def test_auto_pindah_ke_kosong_di_depan_mendahului_kosong_di_belakang(server):
    sesi_id = _mulai(server)
    nomor = _nomor_pg(server, sesi_id)[2]
    _isi_kecuali(server, sesi_id, {nomor, nomor - 1, 10 if nomor < 9 else 9})
    depan = 10 if nomor < 9 else 9

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="B")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no={depan}"


def test_semua_soal_terisi_setelah_jawaban_ini_tetap_di_soal_itu(server):
    sesi_id = _mulai(server)
    nomor = _nomor_pg(server, sesi_id)[0]
    _isi_kecuali(server, sesi_id, {nomor})

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="D")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no={nomor}" and _jawaban(server, sesi_id)[nomor] == "D"


def test_klik_nomor_atau_berikutnya_tetap_ke_tujuan_pindah_walau_ada_jawaban(server):
    sesi_id = _mulai(server)
    nomor = _nomor_pg(server, sesi_id)[0]

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="C", pindah="9")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no=9" and _jawaban(server, sesi_id) == {nomor: "C"}


def test_selesai_tidak_memicu_auto_pindah(server):
    sesi_id = _mulai(server)
    nomor = _nomor_pg(server, sesi_id)[0]

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="C", aksi="selesai")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}/selesai"


def test_isian_galat_tetap_di_soal_itu_bukan_auto_pindah(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="1.5", aksi="simpan")

    assert hasil.lokasi.startswith(f"/murid/lomba/sesi/{sesi_id}?no={nomor}&galat=angka")


def test_isian_enter_dengan_semua_terisi_tetap_di_soal_itu(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")
    _isi_kecuali(server, sesi_id, {nomor})

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="77", aksi="simpan")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no={nomor}"


@pytest.mark.parametrize("kueri", ["&isi=1234567890123", "&isi=1&isi=2", "&isi=%00", "&isi=%0a1"])
def test_ketikan_galat_tidak_sah_di_url_diabaikan_tanpa_404(server, kueri):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")

    halaman = _get(server, f"/murid/lomba/sesi/{sesi_id}?no={nomor}&galat=angka{kueri}")

    assert halaman.kode == 200 and P_GALAT in halaman.isi.decode()
    assert 'name="jawaban" value=""' in halaman.isi.decode()


def test_ketikan_galat_di_url_dipertahankan_dan_di_escape(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")

    halaman = _get(server, f"/murid/lomba/sesi/{sesi_id}?no={nomor}&galat=angka&isi=%22%3Cb%3E")

    assert 'name="jawaban" value="&quot;&lt;b&gt;"' in halaman.isi.decode()


def test_pindah_tanpa_jawaban_hanya_berpindah_halaman(server):
    sesi_id = _mulai(server)

    hasil = _jawab(server, sesi_id, no="2", pindah="3")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no=3" and _jawaban(server, sesi_id) == {}


# 12 --- strip nomor ------------------------------------------------------------------

def test_strip_membedakan_soal_terjawab_dari_yang_belum(server):
    sesi_id = _mulai(server)
    _jawab_tiga_pertama(server, sesi_id)

    isi = _get(server, f"/murid/lomba/sesi/{sesi_id}?no=4").isi.decode()

    assert isi.count('class="nomor sudah"') == 3 and isi.count("sudah dijawab") == 3
    assert isi.count("belum dijawab") == 7 and 'value="4" class="nomor belum aktif" aria-current="step"' in isi
    assert "\u2713" not in isi.split("<form", 1)[1].split("</nav>", 1)[0]


# 13 --- kepemilikan ------------------------------------------------------------------

def _rute_sesi(sesi_id):
    dasar = f"/murid/lomba/sesi/{sesi_id}"
    return (("GET", f"{dasar}?no=1", None), ("GET", f"{dasar}/selesai", None),
            ("GET", f"/murid/lomba/hasil/{sesi_id}", None),
            ("POST", f"{dasar}/jawab", {"no": "1", "jawaban": "A", "aksi": "simpan"}),
            ("POST", f"{dasar}/jawab", {"no": "1", "jawaban": "", "aksi": "simpan"}),
            ("POST", f"{dasar}/kumpul", {}))


@pytest.mark.parametrize("akhiri", [False, True], ids=["berjalan", "selesai"])
def test_sesi_milik_anak_lain_dijawab_404_identik_tanpa_efek_samping(server, akhiri):
    sesi_id = _mulai(server)
    _jawab_tiga_pertama(server, sesi_id)
    if akhiri:
        _post(server, f"/murid/lomba/sesi/{sesi_id}/kumpul")
    sebelum = _keadaan(server)
    referensi = _tidak_ada(server, MURID_DUA).sidik()

    for metode, jalur, data in _rute_sesi(sesi_id):
        hasil = _get(server, jalur, MURID_DUA) if metode == "GET" else _post(server, jalur, data, MURID_DUA)
        assert hasil.sidik() == referensi, (metode, jalur)
    assert _keadaan(server) == sebelum


def test_sesi_yang_tidak_ada_dijawab_404_identik(server):
    referensi = _tidak_ada(server).sidik()
    sebelum = _keadaan(server)

    for metode, jalur, data in _rute_sesi(987654):
        hasil = _get(server, jalur) if metode == "GET" else _post(server, jalur, data)
        assert hasil.sidik() == referensi, (metode, jalur)
    assert _keadaan(server) == sebelum


def test_halaman_404_lomba_memuat_pesan_yang_sama_dengan_jalur_tak_dikenal(server):
    assert PESAN_404.encode() in _get(server, "/murid/lomba/sesi/987654?no=1").isi


# 14 --- id dan nomor tidak sah -------------------------------------------------------

@pytest.mark.parametrize("jalur", [
    "/murid/lomba/sesi/abc", "/murid/lomba/sesi/abc/selesai", "/murid/lomba/hasil/abc", "/murid/lomba/sesi/1x?no=1",
    "/murid/lomba/sesi/99999999999999999999?no=1", "/murid/lomba/hasil/%D9%A5", "/murid/lomba/sesi/+1?no=1",
])
def test_id_bukan_angka_atau_terlalu_panjang_dijawab_404(server, jalur):
    _mulai(server)

    assert _get(server, jalur).sidik() == _tidak_ada(server).sidik()


@pytest.mark.parametrize("kueri", ["no=0", "no=11", "no=abc", "no=", "no=1&no=2", "no=-1", "no=%D9%A1", "no=100"])
def test_nomor_soal_di_luar_satu_sampai_sepuluh_dijawab_404(server, kueri):
    sesi_id = _mulai(server)

    hasil = _get(server, f"/murid/lomba/sesi/{sesi_id}?{kueri}")

    assert hasil.sidik() == _tidak_ada(server).sidik()


@pytest.mark.parametrize("isian", [
    {"jawaban": "A"}, {"no": "0", "jawaban": "A"}, {"no": "11", "jawaban": "A"}, {"no": "abc", "jawaban": "A"},
    {"no": "1", "pindah": "0"}, {"no": "1", "pindah": "11"}, {"no": "1", "pindah": "x", "jawaban": "A"},
    {"no": "1", "pindah": ""},
])
def test_post_jawab_dengan_nomor_tidak_sah_dijawab_404_tanpa_efek_samping(server, isian):
    sesi_id = _mulai(server)
    sebelum = _keadaan(server)

    hasil = _jawab(server, sesi_id, **isian)

    assert hasil.sidik() == _tidak_ada(server).sidik()
    assert _keadaan(server) == sebelum


# 15 --- dua tab ---------------------------------------------------------------------

def test_mulai_dua_kali_mengembalikan_sesi_yang_sama(server):
    pertama = _mulai(server)
    kedua = _mulai(server)

    assert pertama == kedua and len(_tabel(server, "lomba_sesi", "id")) == 1
    assert len(_tabel(server, "lomba_soal", "sesi_id, nomor")) == 10


# 16 --- gagal merakit ----------------------------------------------------------------

def test_gagal_merakit_sesi_menampilkan_halaman_ramah_503_dan_tidak_membuat_sesi(server, monkeypatch):
    def gagal(*_a, **_k):
        raise contest_session.GagalMerakitSesi("sengaja")

    monkeypatch.setattr(contest_session, "rakit_sesi", gagal)

    hasil = _post(server, "/murid/lomba/mulai")

    assert hasil.kode == 503 and b"Soal belum bisa disiapkan" in hasil.isi and b"sengaja" not in hasil.isi
    assert _keadaan(server) == {"lomba_sesi": [], "lomba_soal": [], "lomba_jawaban": []}


# --- body POST ---------------------------------------------------------------------

def test_body_lebih_dari_2048_byte_ditolak_tanpa_efek(server):
    sesi_id = _mulai(server)
    sebelum = _keadaan(server)

    hasil = _minta(server, f"/murid/lomba/sesi/{sesi_id}/jawab", auth_=MURID_SATU, isi_mentah=b"no=1&jawaban=" + b"1" * 2100)

    assert hasil.kode == 413 and _keadaan(server) == sebelum


def test_kolom_ganda_ditolak_400_tanpa_efek(server):
    sesi_id = _mulai(server)
    sebelum = _keadaan(server)

    hasil = _minta(server, f"/murid/lomba/sesi/{sesi_id}/jawab", auth_=MURID_SATU, isi_mentah=b"no=1&jawaban=A&jawaban=B")

    assert hasil.kode == 400 and _keadaan(server) == sebelum


def test_body_bukan_utf8_ditolak_400(server):
    hasil = _minta(server, "/murid/lomba/mulai", auth_=MURID_SATU, isi_mentah=b"x=\xff\xfe")

    assert hasil.kode == 400 and _tabel(server, "lomba_sesi", "id") == []


def test_rute_tak_dikenal_di_bawah_lomba_tetap_404_biasa(server):
    for jalur in ("/murid/lomba/xyz", "/murid/lomba/sesi", "/murid/lomba/sesi/1/jawab"):
        assert _get(server, jalur).sidik() == _tidak_ada(server).sidik(), jalur


# 11b --- tombol Selesai menyimpan isian terketik lebih dulu --------------------------------

def test_selesai_menyimpan_isian_terketik_lalu_membuka_konfirmasi(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="42", aksi="selesai")

    assert hasil.kode == 303 and hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}/selesai"
    assert _jawaban(server, sesi_id) == {nomor: "42"}


def test_selesai_dengan_isian_kosong_tidak_menghapus_jawaban_lama(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")
    _jawab(server, sesi_id, no=nomor, jawaban="34")

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="", aksi="selesai")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}/selesai"
    assert _jawaban(server, sesi_id) == {nomor: "34"}


def test_selesai_dengan_isian_tidak_sah_kembali_ke_soal_dengan_pesan_galat(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="abc", aksi="selesai")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}?no={nomor}&galat=angka&isi=abc"
    assert _jawaban(server, sesi_id) == {}


def test_selesai_pada_soal_pilihan_ganda_tanpa_jawaban_langsung_membuka_konfirmasi(server):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "pg")

    hasil = _jawab(server, sesi_id, no=nomor, aksi="selesai")

    assert hasil.lokasi == f"/murid/lomba/sesi/{sesi_id}/selesai"
    assert _jawaban(server, sesi_id) == {}


def test_selesai_setelah_batas_dialihkan_ke_hasil_dan_isian_tidak_tersimpan(server, jam):
    sesi_id = _mulai(server)
    nomor = _nomor_berjenis(server, sesi_id, "isian")
    jam.t = T0 + 900

    hasil = _jawab(server, sesi_id, no=nomor, jawaban="42", aksi="selesai")

    assert hasil.lokasi == f"/murid/lomba/hasil/{sesi_id}"
    assert _jawaban(server, sesi_id) == {}


# 14 --- halaman awal: lanjutkan, target, nilai terbaik; hasil: banding --------------------------------------

def _sesi_sah(uji, jam, mulai, benar, lama=300):
    """Satu sesi lengkap dari `mulai`: sepuluh jawaban semua benar/salah, dikumpulkan `lama` detik kemudian."""
    jam.t = mulai
    sesi_id = _mulai(uji)
    _isi_semua(uji, sesi_id, benar=benar)
    jam.t = mulai + lama
    _post(uji, f"/murid/lomba/sesi/{sesi_id}/kumpul")
    return sesi_id


def _hasil_isi(uji, sesi_id):
    return _get(uji, f"/murid/lomba/hasil/{sesi_id}").isi.decode()


def test_awal_menawarkan_lanjutkan_ke_soal_kosong_pertama_bukan_soal_satu(server):
    sesi_id = _mulai(server)
    for nomor in (1, 2, 3):
        _jawab_valid(server, sesi_id, nomor)

    isi = _get(server, "/murid/lomba").isi.decode()

    assert f'href="/murid/lomba/sesi/{sesi_id}?no=4">Lanjutkan</a>' in isi and "3 dari 10 soal terisi" in isi
    assert "Waktu terus berjalan walaupun kamu keluar dari halaman ini" in isi
    assert '<a class="tautan-beranda" href="/murid">' in isi


def test_awal_menampilkan_hitung_mundur_target_nilai_terbaik_dan_riwayat_relatif(server, jam):
    _sesi_sah(server, jam, T0, benar=True)
    jam.t = T0 + 1000

    isi = _get(server, "/murid/lomba").isi.decode()

    assert "Latihan hari ini: 1 dari 2" in isi and 'style="width:50%"' in isi
    assert "Nilai terbaikmu" in isi and "<strong>10/10</strong>" in isi
    assert "Hari ini, 15.00" in isi and "hitung-mundur" not in re.sub(r"<style>.*?</style>", "", isi, flags=re.S)


def test_awal_sebelum_tanggal_lomba_menampilkan_hitung_mundur(server, jam):
    jam.t = 1_795_000_000

    isi = _get(server, "/murid/lomba").isi.decode()

    assert "Grand Final Corexis tinggal 24 hari lagi" in isi and "Latihan hari ini: 0 dari 2" in isi
    assert "Nilai terbaikmu" not in isi


def test_sesi_asal_kumpul_tidak_masuk_nilai_terbaik_target_atau_banding(server, jam):
    sah = _sesi_sah(server, jam, T0, benar=False)
    cepat = _sesi_sah(server, jam, T0 + 1000, benar=True, lama=30)
    jam.t = T0 + 2000

    awal = _get(server, "/murid/lomba").isi.decode()
    hasil_cepat = _hasil_isi(server, cepat)

    assert "Latihan hari ini: 1 dari 2" in awal and "<strong>0/10</strong>" in awal    # terbaik = 0 (sah), bukan 10
    assert "dari latihan sebelumnya" not in hasil_cepat
    assert f"/murid/lomba/hasil/{cepat}" in awal and f"/murid/lomba/hasil/{sah}" in awal  # tetap tampil di riwayat


def test_hasil_pertama_tanpa_pembanding_tidak_menampilkan_kalimat_banding(server, jam):
    sesi_id = _sesi_sah(server, jam, T0, benar=True)

    assert "dari latihan sebelumnya" not in _hasil_isi(server, sesi_id)


@pytest.mark.parametrize("pertama,kedua,kalimat", [
    (False, True, "Naik 10 dari latihan sebelumnya"), (True, False, "Turun 10 dari latihan sebelumnya"),
    (True, True, "Sama dengan latihan sebelumnya"),
])
def test_hasil_membandingkan_dengan_sesi_sah_sebelumnya(server, jam, pertama, kedua, kalimat):
    _sesi_sah(server, jam, T0, benar=pertama)
    sesi_dua = _sesi_sah(server, jam, T0 + 1000, benar=kedua)

    assert f'<p class="hl-banding">{kalimat}</p>' in _hasil_isi(server, sesi_dua)


def test_banding_melewati_sesi_asal_kumpul_di_antaranya(server, jam):
    _sesi_sah(server, jam, T0, benar=False)
    _sesi_sah(server, jam, T0 + 1000, benar=True, lama=30)
    ketiga = _sesi_sah(server, jam, T0 + 2000, benar=True)

    assert '<p class="hl-banding">Naik 10 dari latihan sebelumnya</p>' in _hasil_isi(server, ketiga)


def test_hasil_anak_tidak_membandingkan_dengan_sesi_anak_lain(server, jam):
    jam.t = T0
    lain = _mulai(server, MURID_DUA)
    _post(server, f"/murid/lomba/sesi/{lain}/kumpul", pengguna=MURID_DUA)
    sesi_id = _sesi_sah(server, jam, T0 + 1000, benar=True)

    assert "dari latihan sebelumnya" not in _hasil_isi(server, sesi_id)


def test_hasil_memuat_peta_nomor_beranda_dan_kelompok_soal(server, jam):
    sesi_id = _sesi_sah(server, jam, T0, benar=False)

    isi = _hasil_isi(server, sesi_id)

    assert isi.count('class="peta-nomor hl-salah"') == 10 and "Yang perlu dilihat lagi (10)" in isi
    assert '<a class="tautan-beranda" href="/murid">' in isi and '<a class="tombol sekunder" href="/murid">Beranda</a>' in isi
    assert re.findall(r'<h3 class="hl-judul" id="(soal-\d+)"', isi) == [f"soal-{n}" for n in range(1, 11)]


def _csp(hasil):
    return hasil.header["content-security-policy"]


def test_csp_halaman_awal_dengan_maskot_mengizinkan_gambar_sendiri_dan_gaya_inline_tanpa_hash(server):
    csp = _csp(_get(server, "/murid/lomba"))

    assert "img-src 'self'" in csp and "style-src 'unsafe-inline'" in csp
    assert "style-src" in csp and not re.search(r"style-src[^;]*('sha256-|'nonce-)", csp)


def test_csp_halaman_hasil_dan_soal(server, jam):
    sesi_id = _sesi_sah(server, jam, T0, benar=True)
    hasil = _get(server, f"/murid/lomba/hasil/{sesi_id}")
    jam.t = T0 + 5000
    baru = _mulai(server)
    soal = _get(server, f"/murid/lomba/sesi/{baru}?no=1")

    for halaman in (hasil, soal):
        assert "img-src 'self'" in _csp(halaman) and not re.search(r"style-src[^;]*('sha256-|'nonce-)", _csp(halaman))
    assert "script-src 'none'" in _csp(hasil) and "script-src 'sha256-" in _csp(soal)


@pytest.mark.parametrize("ketikan,bersih", [
    ("594", "594"), (" 594 ", "594"), ("5 9 4", "594"), ("5 94", "594"), ("594\t", "594"),
    ("5\u00a09\u00a04", "594"), ("\u3000594\u3000", "594"), ("   ", ""), ("5,94", "5,94"), ("B", "B"),
])
def test_buang_spasi_di_batas_http_membuang_semua_spasi_putih(ketikan, bersih):
    assert contest_http.buang_spasi(ketikan) == bersih
