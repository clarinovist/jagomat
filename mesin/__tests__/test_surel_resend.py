"""Tes pengirim Resend: gagal tertutup, validasi masukan, pemetaan respons, dan tanpa kebocoran rahasia.

Transport selalu palsu; `isolasi_surel` menjamin tes tidak pernah membuka jaringan.
"""
import http.client
import json
import urllib.error
import urllib.request

import pytest

import surel_resend as sr
from surel_kit import ALAMAT_SINTETIS_ADMIN, KUNCI_SINTETIS, LarangJaringan, TransportPalsu, isolasi_surel  # noqa: F401

pytestmark = pytest.mark.usefixtures("isolasi_surel")

PENERIMA = ALAMAT_SINTETIS_ADMIN
SUBJEK = "Ringkasan tes"
TEKS = "Isi sintetis RAHASIA_ISI_TES"
KUNCI_IDEMPOTENSI = "tunggakan-kelas-2026-11-25"
URL_TETAP = "https://api.resend.com/emails"

MASUKAN_TIDAK_SAH = [
    ("penerima", "admin@contoh.test\r\nBcc: orang@contoh.test"),
    ("penerima", "admin@contoh.test\n"),
    ("penerima", "admin@contoh.test, lain@contoh.test"),
    ("penerima", "admin@contoh.test; lain@contoh.test"),
    ("penerima", "<admin@contoh.test>"),
    ("penerima", "admin @contoh.test"),
    ("penerima", "admin.contoh.test"),
    ("penerima", "admin@@contoh.test"),
    ("penerima", "a@b@contoh.test"),
    ("penerima", "admin@contoh"),
    ("penerima", "x" * 250 + "@contoh.test"),
    ("penerima", ""),
    ("penerima", 123),
    ("subjek", "Halo\r\nBcc: orang@contoh.test"),
    ("subjek", "Halo\nBaru"),
    ("subjek", "tab\tdi sini"),
    ("subjek", ""),
    ("subjek", "a" * 201),
    ("subjek", None),
    ("teks", ""),
    ("teks", "a" * 10001),
    ("teks", "nul\x00di sini"),
    ("teks", b"bytes"),
    ("kunci_idempotensi", ""),
    ("kunci_idempotensi", "dengan spasi"),
    ("kunci_idempotensi", "kunci_ü"),
    ("kunci_idempotensi", "k" * 257),
    ("kunci_idempotensi", 5),
    ("pengirim", "Jagomat\r\nBcc: orang@contoh.test <no-reply@jagomat.id>"),
    ("pengirim", "Jagomat\r\n<no-reply@jagomat.id>"),
    ("pengirim", "A <a@contoh.test>, B <b@contoh.test>"),
    ("pengirim", "Jagomat <no-reply@jagomat.id"),
    ("pengirim", "<no-reply@jagomat.id>"),
    ("pengirim", 3),
]


class _ResponPalsu:
    """Respons urllib tiruan (status, read, context manager) untuk transport bawaan tanpa jaringan."""

    def __init__(self, kode, badan):
        self.status = kode
        self._badan = badan

    def read(self):
        return self._badan

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _kirim(transport, **ganti):
    argumen = {"penerima": PENERIMA, "subjek": SUBJEK, "teks": TEKS, "kunci_idempotensi": KUNCI_IDEMPOTENSI,
               "kunci_api": KUNCI_SINTETIS, "pengirim": None, "transport": transport}
    argumen.update(ganti)
    return sr.kirim(**argumen)


# --- gagal tertutup dan kunci -------------------------------------------------------------------

@pytest.mark.parametrize("kunci", ["", "   "])
def test_kunci_kosong_ditahan_tanpa_memanggil_transport(kunci):
    # Arrange
    transport = TransportPalsu()

    # Act
    hasil = _kirim(transport, kunci_api=kunci)

    # Assert
    assert hasil.status == "ditahan"
    assert hasil.kode_http is None
    assert hasil.id_surel is None
    assert transport.panggilan == []


def test_kunci_tidak_ada_di_env_ditahan_tanpa_memanggil_transport():
    transport = TransportPalsu()

    hasil = _kirim(transport, kunci_api=None)

    assert hasil.status == "ditahan"
    assert transport.panggilan == []


def test_kunci_api_dibaca_dari_env_bila_parameter_none(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", KUNCI_SINTETIS)
    transport = TransportPalsu()

    hasil = _kirim(transport, kunci_api=None)

    assert hasil.status == "terkirim"
    assert transport.panggilan[0]["headers"]["Authorization"] == "Bearer " + KUNCI_SINTETIS


def test_kunci_dipangkas_sebelum_dipakai_di_header():
    transport = TransportPalsu()

    _kirim(transport, kunci_api=KUNCI_SINTETIS + "\n")

    assert transport.panggilan[0]["headers"]["Authorization"] == "Bearer " + KUNCI_SINTETIS


@pytest.mark.parametrize("kunci", ["re_x\r\nBcc: orang@contoh.test", "re_dengan spasi", 12345])
def test_kunci_api_tidak_sah_gagal_tanpa_memanggil_transport(kunci):
    transport = TransportPalsu()

    hasil = _kirim(transport, kunci_api=kunci)

    assert hasil.status == "gagal"
    assert hasil.alasan == "masukan tidak sah"
    assert transport.panggilan == []


# --- validasi masukan ---------------------------------------------------------------------------

@pytest.mark.parametrize("kolom,nilai", MASUKAN_TIDAK_SAH)
def test_masukan_tidak_sah_gagal_tanpa_memanggil_transport(kolom, nilai):
    transport = TransportPalsu()

    hasil = _kirim(transport, **{kolom: nilai})

    assert hasil.status == "gagal"
    assert hasil.alasan == "masukan tidak sah"
    assert transport.panggilan == []


@pytest.mark.parametrize("alamat", ["admin@contoh.test", "a.b+c@sub.contoh.test", "no-reply@jagomat.id"])
def test_alamat_sah_menerima_alamat_wajar(alamat):
    assert sr.alamat_sah(alamat) is True


@pytest.mark.parametrize("alamat", [
    "", "admin", "admin@contoh", "a@b@contoh.test", "a b@contoh.test", "<a@contoh.test>",
    "a@contoh.test, b@contoh.test", "a@contoh.test\n", None,
])
def test_alamat_sah_menolak_alamat_tidak_wajar(alamat):
    assert sr.alamat_sah(alamat) is False


# --- permintaan dan respons ---------------------------------------------------------------------

def test_permintaan_memakai_header_dan_badan_sesuai_kontrak():
    transport = TransportPalsu()

    _kirim(transport, pengirim="Tes <tes@contoh.test>")

    (panggilan,) = transport.panggilan
    assert panggilan["url"] == URL_TETAP
    assert panggilan["timeout"] == 15
    assert panggilan["headers"] == {
        "Authorization": "Bearer " + KUNCI_SINTETIS,
        "Content-Type": "application/json",
        "User-Agent": "jagomat-surel/1.0",
        "Idempotency-Key": KUNCI_IDEMPOTENSI,
    }
    assert json.loads(panggilan["badan"]) == {
        "from": "Tes <tes@contoh.test>", "to": [PENERIMA], "subject": SUBJEK, "text": TEKS,
    }


def test_pengirim_bawaan_konstanta_sesuai_kontrak():
    assert sr.PENGIRIM_BAWAAN == "Jagomat <no-reply@jagomat.id>"


@pytest.mark.parametrize("nilai_env,harapan", [
    (None, "Jagomat <no-reply@jagomat.id>"),
    ("Tes <tes@contoh.test>", "Tes <tes@contoh.test>"),
])
def test_pengirim_dari_env_lalu_konstanta_bawaan(monkeypatch, nilai_env, harapan):
    if nilai_env is not None:
        monkeypatch.setenv("SUREL_PENGIRIM", nilai_env)
    transport = TransportPalsu()

    _kirim(transport)

    assert json.loads(transport.panggilan[0]["badan"])["from"] == harapan


def test_pengirim_alamat_saja_tanpa_nama_diterima():
    transport = TransportPalsu()

    hasil = _kirim(transport, pengirim="no-reply@jagomat.id")

    assert hasil.status == "terkirim"
    assert json.loads(transport.panggilan[0]["badan"])["from"] == "no-reply@jagomat.id"


@pytest.mark.parametrize("kode", [200, 201])
def test_respons_sukses_dengan_id_menjadi_terkirim(kode):
    transport = TransportPalsu(kode=kode, badan=b'{"id":"email_tes_9"}')

    hasil = _kirim(transport)

    assert hasil.status == "terkirim"
    assert hasil.kode_http == kode
    assert hasil.id_surel == "email_tes_9"


@pytest.mark.parametrize("kode,alasan", [
    (401, "ditolak layanan"),
    (422, "ditolak layanan"),
    (500, "layanan galat"),
    (503, "layanan galat"),
    (429, "terlalu banyak permintaan"),
    (302, "respons layanan tidak sah"),
])
def test_kode_galat_layanan_menjadi_gagal_dengan_alasan_generik(kode, alasan):
    transport = TransportPalsu(kode=kode, badan=b"{}")

    hasil = _kirim(transport)

    assert (hasil.status, hasil.kode_http, hasil.alasan) == ("gagal", kode, alasan)
    assert hasil.id_surel is None


def test_badan_respons_galat_tidak_dicerminkan_ke_alasan():
    badan = ('{"pesan":"kunci %s salah untuk %s isi RAHASIA_ISI_TES"}' % (KUNCI_SINTETIS, PENERIMA)).encode()
    transport = TransportPalsu(kode=401, badan=badan)

    hasil = _kirim(transport)

    assert hasil.alasan == "ditolak layanan"
    for rahasia in (KUNCI_SINTETIS, PENERIMA, "RAHASIA_ISI_TES"):
        assert rahasia not in hasil.alasan
        assert rahasia not in repr(hasil)


@pytest.mark.parametrize("badan", [b"", b"bukan json", b'{"id":""}', b"[]", b'{"nama":"x"}', b'{"id":5}'])
def test_respons_sukses_tanpa_id_string_tidak_dianggap_terkirim(badan):
    hasil = _kirim(TransportPalsu(kode=200, badan=badan))

    assert hasil.status == "gagal"
    assert hasil.alasan == "respons layanan tidak sah"
    assert hasil.kode_http == 200


@pytest.mark.parametrize("galat", [
    TimeoutError("timeout ke " + KUNCI_SINTETIS),
    OSError("soket putus " + PENERIMA),
    urllib.error.URLError("alamat " + KUNCI_SINTETIS),
    http.client.BadStatusLine("garis rusak " + KUNCI_SINTETIS),
])
def test_galat_transport_ditangkap_tanpa_melempar(galat):
    hasil = _kirim(TransportPalsu(galat=galat))

    assert hasil.status == "gagal"
    assert hasil.kode_http is None
    assert hasil.alasan == "gagal menghubungi layanan surel"
    assert KUNCI_SINTETIS not in repr(hasil)
    assert PENERIMA not in repr(hasil)


def test_rahasia_tidak_muncul_di_hasil_atau_keluaran(capsys):
    hasil_sukses = _kirim(TransportPalsu())
    hasil_galat = _kirim(TransportPalsu(kode=500, badan=KUNCI_SINTETIS.encode()))
    hasil_jaringan = _kirim(TransportPalsu(galat=OSError(KUNCI_SINTETIS + PENERIMA + TEKS)))

    keluaran = capsys.readouterr()
    for hasil in (hasil_sukses, hasil_galat, hasil_jaringan):
        for teks in (repr(hasil), hasil.alasan):
            assert KUNCI_SINTETIS not in teks
            assert PENERIMA not in teks
            assert "RAHASIA_ISI_TES" not in teks
    assert keluaran.out == ""
    assert keluaran.err == ""


# --- transport bawaan (tanpa jaringan: OpenerDirector.open diganti tiruan) ----------------------

def test_transport_bawaan_mengirim_ke_url_tetap_dengan_header_dan_metode_post(monkeypatch):
    tangkapan = []

    def palsu(self, permintaan, data=None, timeout=None):
        tangkapan.append(permintaan)
        return _ResponPalsu(200, b'{"id":"email_tes_2"}')

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", palsu)

    hasil = _kirim(None)

    (permintaan,) = tangkapan
    headers = {nama.lower(): nilai for nama, nilai in permintaan.header_items()}
    assert (hasil.status, hasil.id_surel) == ("terkirim", "email_tes_2")
    assert permintaan.full_url == URL_TETAP
    assert permintaan.get_method() == "POST"
    assert headers["authorization"] == "Bearer " + KUNCI_SINTETIS
    assert headers["idempotency-key"] == KUNCI_IDEMPOTENSI
    assert headers["user-agent"] == "jagomat-surel/1.0"
    assert headers["content-type"] == "application/json"
    assert json.loads(permintaan.data)["to"] == [PENERIMA]


@pytest.mark.parametrize("pabrik_galat,kode,alasan", [
    (lambda: urllib.error.HTTPError(URL_TETAP, 401, "Unauthorized", None, None), 401, "ditolak layanan"),
    (lambda: urllib.error.URLError("gagal " + KUNCI_SINTETIS), None, "gagal menghubungi layanan surel"),
])
def test_transport_bawaan_memetakan_galat_ke_hasil_gagal(monkeypatch, pabrik_galat, kode, alasan):
    def palsu(self, permintaan, data=None, timeout=None):
        raise pabrik_galat()

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", palsu)

    hasil = _kirim(None)

    assert (hasil.status, hasil.kode_http, hasil.alasan) == ("gagal", kode, alasan)


def test_transport_bawaan_tidak_mengikuti_alihan():
    penolak = sr._PenolakAlihan()
    permintaan = urllib.request.Request(URL_TETAP, data=b"{}", method="POST")

    hasil = penolak.redirect_request(permintaan, None, 307, "Temporary Redirect", {}, "https://lain.contoh.test/")

    assert hasil is None


def test_isolasi_surel_membuat_jaringan_melempar_galat():
    with pytest.raises(LarangJaringan):
        urllib.request.urlopen(URL_TETAP)
