"""Pengaturan Mode Lomba oleh Guru lewat HTTP sungguhan: kartu, POST, kepemilikan, 404 identik, tanpa efek samping.

Data sintetis di tmp_path. 404 (bukan pemilik, anak tidak ada, id tidak sah, sakelar induk mati) harus byte-identik
dengan 404 GET yang sudah ada dan tidak boleh mengubah baris penugasan sama sekali.
"""
import base64
import http.client
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import contest_assignment_store as AS  # noqa: E402
import contest_guru_http  # noqa: E402
import contest_guru_pages as H  # noqa: E402
import database  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402

SEKARANG_UJI = 1_800_000_000
GURU = ("guru", SANDI_GURU)
GURU_LAIN = ("guru-lain", "sandi-guru-lain-123")
ADMIN = ("admin-uji", "sandi-admin-uji-123")
MURID = ("feby", SANDI_MURID)
NAMA_ANAK = "Anak <b>Sintetis</b> & Co"
HEADER_PENTING = ("cache-control", "content-security-policy", "content-type", "x-frame-options", "referrer-policy")
PESAN_TERSIMPAN = "Pengaturan Mode Lomba tersimpan."
FORM_SAH = {"aktif": "1", "target": "paket", "hitung_mundur": "1"}


@pytest.fixture()
def s(tmp_path, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    monkeypatch.setattr(contest_guru_http, "_sekarang", lambda: SEKARANG_UJI)
    server = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("guru-lain", GURU_LAIN[1], "guru", path=auth.BERKAS_SANDI)
    auth.tambah_akun("admin-uji", ADMIN[1], "admin", path=auth.BERKAS_SANDI)
    with server.buka() as kon:
        server.anak = database.tambah_siswa(kon, NAMA_ANAK, pemilik="guru")
        server.lain = database.tambah_siswa(kon, "Anak Kedua", pemilik="guru")
        server.asing = database.tambah_siswa(kon, "Anak Guru Lain", pemilik="guru-lain")
    yield server
    server.berhenti()


def raw(s, jalur, data=None, auth=GURU, tubuh=None, header=None):
    """Satu permintaan tanpa mengikuti redirect: (status, header huruf kecil, isi bytes)."""
    kepala = dict(header or {})
    if auth:
        kepala["Authorization"] = "Basic " + base64.b64encode(":".join(auth).encode()).decode()
    if tubuh is None and data is not None:
        tubuh = urllib.parse.urlencode(data)
    if tubuh is not None:
        kepala["Content-Type"] = "application/x-www-form-urlencoded"
    k = http.client.HTTPConnection(s.alamat.split("//")[1], timeout=10)
    k.request("POST" if tubuh is not None else "GET", jalur, body=tubuh, headers=kepala)
    r = k.getresponse()
    isi = r.read()
    kepala_balasan = {nama.lower(): nilai for nama, nilai in r.getheaders()}
    k.close()
    return r.status, kepala_balasan, isi


def sidik(hasil):
    kode, header, isi = hasil
    return kode, isi, {k: header[k] for k in HEADER_PENTING if k in header}


def _pengaturan(s, siswa_id):
    with s.buka() as kon:
        return AS.ambil(kon, siswa_id)


def _tabel(s):
    with s.buka() as kon:
        return [tuple(b) for b in kon.execute("SELECT * FROM lomba_penugasan ORDER BY siswa_id")]


def _post(s, siswa_id, data, **kw):
    return raw(s, f"/anak/{siswa_id}/lomba/pengaturan", data=data, **kw)


def _404_get(s):
    """404 GET yang sudah ada: anak yang tidak ada di rute riwayat."""
    return sidik(raw(s, "/anak/987654/lomba"))


# --- kartu Mode Lomba di halaman /anak/<id>/lomba --------------------------------------------------

def _halaman(s, jalur="", auth=GURU):
    kode, _, isi = raw(s, f"/anak/{s.anak}/lomba{jalur}", auth=auth)
    assert kode == 200
    return isi.decode()


def test_kartu_belum_aktif_tampil_di_atas_dengan_form_dan_pilihan_target(s):
    isi = _halaman(s)

    assert "<h2 id=\"judul-mode-lomba\">Mode Lomba</h2>" in isi and "Belum aktif" in isi
    assert f'action="/anak/{s.anak}/lomba/pengaturan"' in isi and 'method="post"' in isi
    assert 'name="aktif" value="0" checked' in isi and 'name="aktif" value="1" checked' not in isi
    assert re.findall(r'<option value="([^"]+)"', isi) == ["paket", "0", "1", "2", "3"]
    assert "Ikut paket (2)" in isi and "Tanpa target" in isi
    assert 'name="hitung_mundur" value="1" checked' in isi and "Tampilkan hitung mundur ke hari lomba" in isi
    assert isi.index('id="judul-mode-lomba"') < isi.index("Belum ada sesi latihan yang selesai")
    assert PESAN_TERSIMPAN not in isi and "Aktif untuk" not in isi


def test_kartu_menampilkan_status_aktif_dengan_nama_anak_di_escape(s):
    with s.buka() as kon:
        AS.atur(kon, s.anak, aktif=True, target_harian=3, tampil_hitung_mundur=False, durasi_latihan_detik=None, durasi_simulasi_detik=None,
                sekarang=SEKARANG_UJI, oleh="guru")

    isi = _halaman(s)

    assert "Aktif untuk Anak &lt;b&gt;Sintetis&lt;/b&gt; &amp; Co" in isi and "<b>Sintetis</b>" not in isi
    assert 'name="aktif" value="1" checked' in isi
    assert '<option value="3" selected>' in isi and '<option value="paket" selected>' not in isi
    assert 'name="hitung_mundur" value="1" checked' not in isi


def test_pesan_tersimpan_hanya_muncul_dengan_tersimpan_satu(s):
    assert PESAN_TERSIMPAN in _halaman(s, "?tersimpan=1")
    for kueri in ("", "?tersimpan=0", "?tersimpan=1&tersimpan=1", "?tersimpan=ya"):
        assert PESAN_TERSIMPAN not in _halaman(s, kueri), kueri


def test_riwayat_guru_tetap_terbuka_walau_penugasan_mati(s):
    with s.buka() as kon:
        AS.atur(kon, s.anak, aktif=False, target_harian=None, tampil_hitung_mundur=None, durasi_latihan_detik=None, durasi_simulasi_detik=None,
                sekarang=SEKARANG_UJI, oleh="guru")

    assert "Belum ada sesi latihan yang selesai" in _halaman(s)


def test_kartu_di_halaman_anak_menyebut_status_dan_tautan_pengaturan(s):
    def tab():
        kode, _, isi = raw(s, f"/anak/{s.anak}?section=perkembangan")
        assert kode == 200
        return isi.decode()

    belum = tab()
    with s.buka() as kon:
        AS.atur(kon, s.anak, aktif=True, target_harian=None, tampil_hitung_mundur=None, durasi_latihan_detik=None, durasi_simulasi_detik=None,
                sekarang=SEKARANG_UJI, oleh="guru")
    aktif = tab()

    assert "Belum aktif — aktifkan untuk anak ini" in belum and "Atur Mode Lomba" in belum
    assert 'class="lomba-masuk-status">Aktif<' in aktif and f'href="/anak/{s.anak}/lomba"' in aktif
    assert belum.replace(H.kartu_masuk(s.anak, False), "") == aktif.replace(H.kartu_masuk(s.anak, True), "")


# --- POST sukses -------------------------------------------------------------------------------------

def test_post_sukses_menyimpan_dan_mengalihkan_303_dengan_pesan(s):
    kode, header, isi = _post(s, s.anak, {"aktif": "1", "target": "3"})

    assert (kode, isi) == (303, b"") and header["location"] == f"/anak/{s.anak}/lomba?tersimpan=1"
    tersimpan = _pengaturan(s, s.anak)
    assert (tersimpan.aktif, tersimpan.target_harian) == (True, 3)
    assert tersimpan.tampil_hitung_mundur is False          # kotak tidak dicentang, paket menampilkan -> eksplisit False
    assert (tersimpan.diubah_epoch, tersimpan.diubah_oleh) == (SEKARANG_UJI, "guru")
    halaman = raw(s, header["location"])[2].decode()
    assert PESAN_TERSIMPAN in halaman and "Aktif untuk" in halaman


def test_hitung_mundur_sama_dengan_paket_disimpan_sebagai_ikut_paket_dan_target_paket_sebagai_null(s):
    _post(s, s.anak, FORM_SAH)

    tersimpan = _pengaturan(s, s.anak)

    assert tersimpan.aktif is True and tersimpan.target_harian is None and tersimpan.tampil_hitung_mundur is None


@pytest.mark.parametrize("nilai,hasil", (("paket", None), ("0", 0), ("1", 1), ("2", 2), ("3", 3)))
def test_pilihan_target_tersimpan_sesuai(s, nilai, hasil):
    _post(s, s.anak, {"aktif": "1", "target": nilai, "hitung_mundur": "1"})

    assert _pengaturan(s, s.anak).target_harian == hasil


def test_menyimpan_ulang_mengubah_baris_yang_sama_dan_bisa_mematikan(s):
    _post(s, s.anak, FORM_SAH)
    _post(s, s.anak, {"aktif": "0", "target": "0"})

    tersimpan = _pengaturan(s, s.anak)

    assert (tersimpan.aktif, tersimpan.target_harian, tersimpan.tampil_hitung_mundur) == (False, 0, False)
    assert len(_tabel(s)) == 1


def test_menyimpan_satu_anak_tidak_mengubah_anak_lain(s):
    _post(s, s.lain, FORM_SAH)
    sebelum = _pengaturan(s, s.lain)

    _post(s, s.anak, {"aktif": "1", "target": "3"})

    assert _pengaturan(s, s.lain) == sebelum


def test_admin_boleh_mengatur_anak_semua_keluarga_dan_tercatat_sebagai_pengubah(s):
    kode, header, _ = _post(s, s.asing, FORM_SAH, auth=ADMIN)

    assert kode == 303 and header["location"] == f"/anak/{s.asing}/lomba?tersimpan=1"
    assert _pengaturan(s, s.asing).diubah_oleh == "admin-uji"


def test_guru_pemilik_anak_keluarga_sendiri_lain_dapat_mengatur(s):
    kode, _, _ = _post(s, s.asing, FORM_SAH, auth=GURU_LAIN)

    assert kode == 303 and _pengaturan(s, s.asing).diubah_oleh == "guru-lain"


# --- kepemilikan dan 404 identik ---------------------------------------------------------------------

def test_bukan_pemilik_dijawab_404_identik_dan_baris_tidak_berubah(s):
    with s.buka() as kon:
        AS.atur(kon, s.anak, aktif=False, target_harian=1, tampil_hitung_mundur=None, durasi_latihan_detik=None, durasi_simulasi_detik=None,
                sekarang=SEKARANG_UJI, oleh="semula")
    sebelum = _tabel(s)

    hasil = _post(s, s.anak, {"aktif": "1", "target": "3"}, auth=GURU_LAIN)

    assert sidik(hasil) == _404_get(s) and hasil[0] == 404
    assert _tabel(s) == sebelum


def test_bukan_pemilik_tanpa_baris_awal_tidak_membuat_baris(s):
    _post(s, s.anak, FORM_SAH, auth=GURU_LAIN)
    _post(s, s.asing, FORM_SAH, auth=GURU)

    assert _tabel(s) == []


def test_bukan_pemilik_dengan_isian_rusak_tetap_404_bukan_400(s):
    hasil = _post(s, s.anak, {"aktif": "ngawur"}, auth=GURU_LAIN)

    assert sidik(hasil) == _404_get(s)


@pytest.mark.parametrize("jalur", (
    "/anak/987654/lomba/pengaturan", "/anak/abc/lomba/pengaturan", "/anak/1234567890123/lomba/pengaturan",
    "/anak/-1/lomba/pengaturan", "/anak/%D9%A1/lomba/pengaturan", "/anak/١/lomba/pengaturan",
))
def test_anak_tidak_ada_atau_id_tidak_sah_dijawab_404_identik_tanpa_tulis(s, jalur):
    hasil = raw(s, urllib.parse.quote(jalur, safe="/%"), data=FORM_SAH)

    assert hasil[0] == 404 and sidik(hasil) == _404_get(s)
    assert _tabel(s) == []


def test_sakelar_induk_mati_dijawab_404_identik_tanpa_tulis(s, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "0")

    hasil = _post(s, s.anak, FORM_SAH)

    assert hasil[0] == 404 and sidik(hasil) == _404_get(s) and _tabel(s) == []


def test_murid_ditolak_seperti_rute_guru_lain_tanpa_tulis(s):
    hasil = _post(s, s.anak, FORM_SAH, auth=MURID)
    rute_guru_lain = raw(s, f"/anak/{s.anak}/laporan-ortu", data={"periode": "30hari"}, auth=MURID)

    assert hasil[0] == 401 and sidik(hasil) == sidik(rute_guru_lain)
    assert _tabel(s) == []


def test_anonim_ditolak_tanpa_tulis(s):
    hasil = _post(s, s.anak, FORM_SAH, auth=None)

    assert hasil[0] == 401 and _tabel(s) == []


def test_post_lintas_situs_ditolak_403_tanpa_tulis(s):
    kode, _, _ = _post(s, s.anak, FORM_SAH, header={"Origin": "https://contoh.example", "Sec-Fetch-Site": "cross-site"})

    assert kode == 403 and _tabel(s) == []


# --- validasi isian: 400 generik tanpa tulis ---------------------------------------------------------

@pytest.mark.parametrize("tubuh", (
    "target=paket",                                  # aktif hilang
    "aktif=2&target=paket",
    "aktif=&target=paket",
    "aktif=1",                                       # target hilang
    "aktif=1&target=9",
    "aktif=1&target=4",                              # di luar pilihan Guru (DB mengizinkan s.d. 5)
    "aktif=1&target=-1",
    "aktif=1&target=",
    "aktif=1&target=2.0",
    "aktif=1&target=%EF%BC%92",                      # angka lebar penuh
    "aktif=1&target=paket&hitung_mundur=ya",
    "aktif=1&target=paket&hitung_mundur=0",
    "aktif=1&aktif=0&target=paket",                  # kunci ganda
    "aktif=1&target=paket&target=3",
    "aktif=1&target=paket&hitung_mundur=1&hitung_mundur=1",
    "aktif=1&target=paket&paket_id=lain",            # kolom tak dikenal
    "aktif=1&target=paket&diubah_oleh=siapa",
    "aktif=1&target=%FF",                            # bukan UTF-8
    "",
))
def test_isian_tidak_sah_dijawab_400_generik_tanpa_tulis(s, tubuh):
    kode, _, isi = raw(s, f"/anak/{s.anak}/lomba/pengaturan", tubuh=tubuh)

    assert kode == 400 and b"Form tidak sah" in isi and b"ngawur" not in isi
    assert _tabel(s) == []


def test_isian_tidak_sah_pada_update_tidak_mengubah_baris_lama(s):
    _post(s, s.anak, {"aktif": "1", "target": "2", "hitung_mundur": "1"})
    sebelum = _tabel(s)

    kode, _, _ = _post(s, s.anak, {"aktif": "0", "target": "9"})

    assert kode == 400 and _tabel(s) == sebelum


def test_isian_terlalu_besar_ditolak_tanpa_tulis(s):
    kode, _, _ = raw(s, f"/anak/{s.anak}/lomba/pengaturan", tubuh="aktif=1&target=paket&x=" + "a" * 5000)

    assert kode == 400 and _tabel(s) == []


def test_nama_akun_pengubah_dipotong_enam_puluh_empat_karakter(s, monkeypatch):
    class _Penangan:
        def __init__(self, nama):
            self.nama = nama

    panjang = "g" * 80
    monkeypatch.setattr(contest_guru_http, "_pastikan_boleh", lambda *a: None)
    monkeypatch.setattr(contest_guru_http, "_baca_pengaturan",
                        lambda p: contest_guru_http._Pengaturan(True, None, None))
    penangan = _Penangan(panjang)
    penangan._identitas = lambda: (penangan.nama, "guru")
    with s.buka() as kon:
        assert contest_guru_http._simpan(penangan, kon, s.anak) == "tersimpan"
        assert len(AS.ambil(kon, s.anak).diubah_oleh) == AS.MAKS_PANJANG_OLEH
