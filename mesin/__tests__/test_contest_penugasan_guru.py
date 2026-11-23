"""Pengaturan Mode Lomba oleh Guru lewat HTTP sungguhan: kartu, POST, kepemilikan, 404 identik, tanpa efek samping.

Data sintetis di tmp_path. 404 (bukan pemilik, anak tidak ada, id tidak sah, sakelar induk mati) harus byte-identik
dengan 404 GET yang sudah ada dan tidak boleh mengubah baris penugasan sama sekali.
"""
import datetime
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
                tanggal_lomba=datetime.date(2026, 12, 12), nama_lomba=None, sekarang=SEKARANG_UJI, oleh="guru")

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
                tanggal_lomba=datetime.date(2026, 12, 12), nama_lomba=None, sekarang=SEKARANG_UJI, oleh="guru")

    assert "Belum ada sesi latihan yang selesai" in _halaman(s)


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
                tanggal_lomba=datetime.date(2026, 12, 12), nama_lomba=None, sekarang=SEKARANG_UJI, oleh="semula")
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


# --- tanggal dan nama lomba per anak (23 Nov 2026) ---------------------------------------------------------

XSS_NAMA = '<script>alert(1)</script>"&'


def _tabel_lama_dengan(s, **ubah):
    nilai = dict(aktif=True, target_harian=None, tampil_hitung_mundur=None, durasi_latihan_detik=None,
                 durasi_simulasi_detik=None, tanggal_lomba=datetime.date(2026, 12, 20), nama_lomba="Lomba Lama",
                 sekarang=SEKARANG_UJI, oleh="semula")
    nilai.update(ubah)
    with s.buka() as kon:
        AS.atur(kon, s.anak, **nilai)


def test_kartu_memuat_isian_tanggal_dan_nama_kosong_untuk_anak_tanpa_penugasan(s):
    isi = _halaman(s)

    assert '<input type="date" name="tanggal_lomba" value="">' in isi
    assert 'name="nama_lomba" maxlength="60" value=""' in isi and 'type="text"' in isi
    assert "Tampilkan hitung mundur ke hari lomba</label>" in isi


def test_kartu_menampilkan_tanggal_nama_dan_tanggal_di_label_hitung_mundur(s):
    _tabel_lama_dengan(s)

    isi = _halaman(s)

    assert 'name="tanggal_lomba" value="2026-12-20"' in isi and 'value="Lomba Lama"' in isi
    assert "Tampilkan hitung mundur ke hari lomba (20 Des 2026)" in isi


def test_nama_lomba_di_halaman_guru_di_escape(s):
    _tabel_lama_dengan(s, nama_lomba=XSS_NAMA.replace("<", "&lt;")[:60])
    with s.buka() as kon:        # nama sintetis dengan kurung sudut ditulis langsung lewat SQL (lolos validasi atur)
        kon.execute("UPDATE lomba_penugasan SET nama_lomba = ? WHERE siswa_id = ?", (XSS_NAMA, s.anak))

    isi = _halaman(s)

    assert XSS_NAMA not in isi and "<script>alert(1)</script>" not in isi
    assert 'value="&lt;script&gt;alert(1)&lt;/script&gt;&quot;&amp;"' in isi


def test_post_menyimpan_tanggal_dan_nama_milik_anak_itu_saja(s):
    kode, header, _ = _post(s, s.anak, {**FORM_SAH, "tanggal_lomba": "2026-12-20", "nama_lomba": "  Lomba Kota  "})

    assert kode == 303 and header["location"].endswith("?tersimpan=1")
    tersimpan = _pengaturan(s, s.anak)
    assert (tersimpan.tanggal_lomba, tersimpan.nama_lomba) == (datetime.date(2026, 12, 20), "Lomba Kota")
    assert _pengaturan(s, s.lain) is None


def test_dua_anak_menyimpan_tanggal_berbeda_dan_tidak_saling_menimpa(s):
    _post(s, s.anak, {**FORM_SAH, "tanggal_lomba": "2026-12-20", "nama_lomba": ""})
    _post(s, s.lain, {**FORM_SAH, "tanggal_lomba": "2027-01-15", "nama_lomba": ""})

    assert _pengaturan(s, s.anak).tanggal_lomba == datetime.date(2026, 12, 20)
    assert _pengaturan(s, s.lain).tanggal_lomba == datetime.date(2027, 1, 15)


def test_isian_kosong_mengosongkan_tanggal_dan_nama(s):
    _tabel_lama_dengan(s)

    kode, _, _ = _post(s, s.anak, {**FORM_SAH, "tanggal_lomba": "", "nama_lomba": ""})

    tersimpan = _pengaturan(s, s.anak)
    assert kode == 303 and (tersimpan.tanggal_lomba, tersimpan.nama_lomba) == (None, None)


def test_kolom_tidak_dikirim_mempertahankan_tanggal_dan_nama_lama(s):
    _tabel_lama_dengan(s)

    kode, _, _ = _post(s, s.anak, FORM_SAH)

    tersimpan = _pengaturan(s, s.anak)
    assert kode == 303 and (tersimpan.tanggal_lomba, tersimpan.nama_lomba) == (datetime.date(2026, 12, 20), "Lomba Lama")


@pytest.mark.parametrize("tanggal", ("2026-13-45", "2026-02-30", "besok", "2026-1-5", "20261220", "2026-12-20x",
                                     "٢٠٢٦-١٢-٢٠", "2026/12/20"))
def test_tanggal_tidak_sah_dialihkan_dengan_galat_tanpa_menulis(s, tanggal):
    _tabel_lama_dengan(s)
    sebelum = _tabel(s)

    kode, header, _ = _post(s, s.anak, {**FORM_SAH, "tanggal_lomba": tanggal, "nama_lomba": "Baru"})

    assert kode == 303 and header["location"] == f"/anak/{s.anak}/lomba?galat=tanggal"
    assert _tabel(s) == sebelum
    assert H.GALAT_TANGGAL in _halaman(s, "?galat=tanggal") and PESAN_TERSIMPAN not in _halaman(s, "?galat=tanggal")


@pytest.mark.parametrize("nama", ("x" * 61, "a\x00b", "baris\nbaru", "tab\tdi sini"))
def test_nama_tidak_sah_dialihkan_dengan_galat_tanpa_menulis(s, nama):
    _tabel_lama_dengan(s)
    sebelum = _tabel(s)

    kode, header, _ = _post(s, s.anak, {**FORM_SAH, "tanggal_lomba": "2026-12-25", "nama_lomba": nama})

    assert kode == 303 and header["location"] == f"/anak/{s.anak}/lomba?galat=nama"
    assert _tabel(s) == sebelum
    assert H.GALAT_NAMA in _halaman(s, "?galat=nama")


def test_galat_durasi_lama_tetap_berfungsi_dan_kode_galat_liar_diabaikan(s):
    assert H.GALAT_DURASI in _halaman(s, "?galat=durasi")
    for kueri in ("?galat=", "?galat=lain", "?galat=tanggal&galat=nama", "?galat=<script>"):
        isi = _halaman(s, kueri)
        assert H.GALAT_DURASI not in isi and H.GALAT_TANGGAL not in isi and H.GALAT_NAMA not in isi, kueri


def test_bukan_pemilik_dengan_tanggal_baru_dijawab_404_identik_tanpa_efek(s):
    _tabel_lama_dengan(s)
    sebelum = _tabel(s)

    hasil = _post(s, s.anak, {**FORM_SAH, "tanggal_lomba": "2026-12-25", "nama_lomba": "Retas"}, auth=GURU_LAIN)
    rusak = _post(s, s.anak, {**FORM_SAH, "tanggal_lomba": "ngawur"}, auth=GURU_LAIN)

    assert sidik(hasil) == _404_get(s) and sidik(rusak) == _404_get(s) and hasil[0] == 404
    assert _tabel(s) == sebelum


def test_sakelar_induk_mati_menolak_tanggal_baru_tanpa_tulis(s, monkeypatch):
    _tabel_lama_dengan(s)
    sebelum = _tabel(s)
    monkeypatch.setenv("OSN_LOMBA", "0")

    hasil = _post(s, s.anak, {**FORM_SAH, "tanggal_lomba": "2026-12-25"})

    assert hasil[0] == 404 and _tabel(s) == sebelum


def test_nama_lomba_tidak_pernah_tampil_di_sisi_anak(s):
    _post(s, s.anak, {**FORM_SAH, "tanggal_lomba": "2099-01-01", "nama_lomba": "NamaRahasiaGuruSintetis"})

    kode, _, isi = raw(s, "/murid/lomba", auth=MURID)

    assert kode == 200 and b"NamaRahasiaGuruSintetis" not in isi and b"Mode Lomba" in isi
