"""Simulasi Lomba lewat HTTP sungguhan: mulai per mode, 35 nomor, durasi dari Guru, target, hasil, palang 404.

Data sintetis di tmp_path; jam server dipalsukan lewat `contest_http._sekarang` / `contest_guru_http._sekarang`.
"""
import base64
import http.client
import itertools
import json
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import contest_anak  # noqa: E402
import contest_assignment_store as AS  # noqa: E402
import contest_core as C  # noqa: E402
import contest_guru_http  # noqa: E402
import contest_guru_pages as H  # noqa: E402
import contest_http  # noqa: E402
import contest_store  # noqa: E402
import database  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402

T0 = 1_800_000_000
MURID = ("feby", SANDI_MURID)
GURU = ("guru", SANDI_GURU)
GURU_LAIN = ("guru-lain", "sandi-guru-lain-123")
HEADER_PENTING = ("cache-control", "content-security-policy", "content-type", "x-frame-options", "referrer-policy")
FORM_SAH = {"aktif": "1", "target": "paket", "hitung_mundur": "1"}
ANGKA_ARAB = "٣٠"          # "30" dengan digit Arab-Indic: int() menerimanya, palang ASCII harus menolak


class _Jam:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


@pytest.fixture
def s(tmp_path, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    jam = _Jam()
    monkeypatch.setattr(contest_http, "_sekarang", jam)
    monkeypatch.setattr(contest_guru_http, "_sekarang", jam)
    benih = itertools.count(501)
    monkeypatch.setattr(contest_store.secrets, "randbits", lambda _bit: next(benih))
    server = ServerUji(tmp_path, monkeypatch)
    server.jam = jam
    auth.tambah_akun("guru-lain", GURU_LAIN[1], "guru", path=auth.BERKAS_SANDI)
    with server.buka() as kon:
        server.anak = database.tambah_siswa(kon, "feby", pemilik="guru")
        server.asing = database.tambah_siswa(kon, "Anak Guru Lain", pemilik="guru-lain")
        AS.atur(kon, server.anak, aktif=True, target_harian=1, tampil_hitung_mundur=None, durasi_latihan_detik=None,
                durasi_simulasi_detik=None, sekarang=T0, oleh="guru")
    yield server
    server.berhenti()


def raw(s, jalur, data=None, kredensial=MURID):
    kepala = {"Authorization": "Basic " + base64.b64encode(":".join(kredensial).encode()).decode()}
    tubuh = None if data is None else urllib.parse.urlencode(data)
    if tubuh is not None:
        kepala["Content-Type"] = "application/x-www-form-urlencoded"
    k = http.client.HTTPConnection(s.alamat.split("//")[1], timeout=10)
    k.request("POST" if tubuh is not None else "GET", jalur, body=tubuh, headers=kepala)
    r = k.getresponse()
    isi = r.read()
    header = {nama.lower(): nilai for nama, nilai in r.getheaders()}
    k.close()
    return r.status, header, isi


def sidik(hasil):
    kode, header, isi = hasil
    return kode, isi, {k: header[k] for k in HEADER_PENTING if k in header}


def _mulai(s, mode=None):
    kode, header, _ = raw(s, "/murid/lomba/mulai", {} if mode is None else {"mode": mode})
    cocok = re.fullmatch(r"/murid/lomba/sesi/(\d+)\?no=1", header.get("location", ""))
    assert kode == 303 and cocok, (kode, header)
    return int(cocok.group(1))


def _sesi(s, sesi_id):
    with s.buka() as kon:
        return dict(kon.execute("SELECT * FROM lomba_sesi WHERE id = ?", (sesi_id,)).fetchone())


def _soal(s, sesi_id):
    with s.buka() as kon:
        return [dict(b) for b in kon.execute("SELECT * FROM lomba_soal WHERE sesi_id = ? ORDER BY nomor", (sesi_id,))]


def _jawaban_benar(baris):
    if baris["jenis"] == "isian":
        return baris["kunci"]
    return C.HURUF[json.loads(baris["pilihan_json"]).index(baris["kunci"])]


def _jawab_benar(s, sesi_id, banyak):
    for baris in _soal(s, sesi_id)[:banyak]:
        kode, _, _ = raw(s, f"/murid/lomba/sesi/{sesi_id}/jawab", {"no": str(baris["nomor"]), "jawaban": _jawaban_benar(baris)})
        assert kode == 303


def _kumpul(s, sesi_id):
    kode, header, _ = raw(s, f"/murid/lomba/sesi/{sesi_id}/kumpul", {})
    assert kode == 303 and header["location"] == f"/murid/lomba/hasil/{sesi_id}"


def _penugasan(s, siswa_id):
    with s.buka() as kon:
        return AS.ambil(kon, siswa_id)


def _atur_durasi(s, latihan, simulasi):
    with s.buka() as kon:
        AS.atur(kon, s.anak, aktif=True, target_harian=1, tampil_hitung_mundur=None, durasi_latihan_detik=latihan,
                durasi_simulasi_detik=simulasi, sekarang=T0, oleh="guru")


# --- murid: mulai per mode -------------------------------------------------------------------------------

def test_halaman_awal_menawarkan_latihan_dan_simulasi_dengan_menit_anak(s):
    _atur_durasi(s, 20 * 60, 75 * 60)

    kode, _, isi = raw(s, "/murid/lomba")

    teks = isi.decode()
    assert kode == 200
    assert ">Latihan (10 soal · 20 menit)</button>" in teks and ">Simulasi Lomba (35 soal · 75 menit)</button>" in teks


def test_simulasi_35_soal_60_menit_dan_soal_35_bisa_dibuka(s):
    sesi_id = _mulai(s, "simulasi")

    sesi = _sesi(s, sesi_id)
    kode, _, isi = raw(s, f"/murid/lomba/sesi/{sesi_id}?no=35")

    teks = isi.decode()
    assert (sesi["mode"], sesi["batas_epoch"] - sesi["mulai_epoch"]) == ("simulasi", 3600) and len(_soal(s, sesi_id)) == 35
    assert kode == 200 and "Soal 35 dari 35" in teks
    assert len(re.findall(r'<button type="submit" name="pindah" value="\d+" class="nomor ', teks)) == 35
    assert 'value="36"' not in teks


def test_halaman_soal_simulasi_tidak_membocorkan_kunci_atau_pembahasan(s):
    sesi_id = _mulai(s, "simulasi")
    for baris in _soal(s, sesi_id):
        _, _, isi = raw(s, f"/murid/lomba/sesi/{sesi_id}?no={baris['nomor']}")
        teks = isi.decode()
        for langkah in json.loads(baris["pembahasan_json"]):
            assert langkah not in teks
        tanpa_timer = teks.replace("data-sisa=", "").replace("data-hasil=", "")
        assert "data-" not in re.sub(r"<script>.*?</script>", "", tanpa_timer, flags=re.S)


def test_durasi_guru_disalin_ke_sesi_dan_perubahan_tidak_mengubah_sesi_berjalan(s):
    _atur_durasi(s, None, 45 * 60)
    sesi_id = _mulai(s, "simulasi")
    batas = _sesi(s, sesi_id)["batas_epoch"]

    kode, _, _ = raw(s, f"/anak/{s.anak}/lomba/pengaturan", dict(FORM_SAH, durasi_simulasi="90"), kredensial=GURU)

    assert batas == T0 + 45 * 60 and kode == 303
    assert _penugasan(s, s.anak).durasi_simulasi_detik == 90 * 60
    assert _sesi(s, sesi_id)["batas_epoch"] == batas


def test_mode_tidak_dikenal_404_tanpa_membuat_sesi(s):
    kode, _, isi = raw(s, "/murid/lomba/mulai", {"mode": "ujian"})
    tak_dikenal = raw(s, "/murid/tidak-ada")

    assert kode == 404 and isi == tak_dikenal[2]
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM lomba_sesi").fetchone()[0] == 0


def test_latihan_tetap_10_nomor_dan_nomor_11_dijawab_404_tanpa_tulis(s):
    sesi_id = _mulai(s)

    kode_get, _, _ = raw(s, f"/murid/lomba/sesi/{sesi_id}?no=11")
    kode_pindah, _, _ = raw(s, f"/murid/lomba/sesi/{sesi_id}/jawab", {"no": "1", "jawaban": "A", "pindah": "11"})
    _, _, isi = raw(s, f"/murid/lomba/sesi/{sesi_id}?no=10")

    assert kode_get == 404 and kode_pindah == 404
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM lomba_jawaban").fetchone()[0] == 0
    assert "Soal 10 dari 10" in isi.decode() and 'value="11"' not in isi.decode()


def test_auto_pindah_simulasi_ke_soal_kosong_berikutnya_sampai_35(s):
    sesi_id = _mulai(s, "simulasi")
    soal_34 = _soal(s, sesi_id)[33]

    _, header, _ = raw(s, f"/murid/lomba/sesi/{sesi_id}/jawab",
                       {"no": "34", "jawaban": _jawaban_benar(soal_34), "aksi": "simpan"})

    assert header["location"] == f"/murid/lomba/sesi/{sesi_id}?no=35"


def test_auto_pindah_latihan_tidak_melompat_ke_nomor_11(s):
    sesi_id = _mulai(s)
    soal_10 = _soal(s, sesi_id)[9]

    _, header, _ = raw(s, f"/murid/lomba/sesi/{sesi_id}/jawab",
                       {"no": "10", "jawaban": _jawaban_benar(soal_10), "aksi": "simpan"})

    assert header["location"] == f"/murid/lomba/sesi/{sesi_id}?no=1"


def test_sesi_berjalan_dilanjutkan_walau_tombol_mode_lain_ditekan(s):
    latihan = _mulai(s)
    assert _mulai(s, "simulasi") == latihan


# --- target, hasil, riwayat ------------------------------------------------------------------------------

def test_simulasi_sah_dihitung_satu_sesi_target_dan_hasil_dari_35(s):
    sesi_id = _mulai(s, "simulasi")
    _jawab_benar(s, sesi_id, 12)
    s.jam.t = T0 + 11 * 60
    _kumpul(s, sesi_id)

    _, _, hasil = raw(s, f"/murid/lomba/hasil/{sesi_id}")
    with s.buka() as kon:
        ringkas = contest_anak.muat_ringkas(kon, s.anak, s.jam.t)
    _, _, awal = raw(s, "/murid/lomba")

    teks = hasil.decode()
    assert "12/35" in teks and ">Simulasi lagi</button>" in teks and 'name="mode" value="simulasi"' in teks
    assert ringkas.selesai_hari_ini == 1 and ringkas.terbaik_simulasi == 12 and ringkas.nilai_terbaik is None
    assert "Simulasi terbaik" in awal.decode() and '<span class="label-mode">Simulasi</span>' in awal.decode()


def test_simulasi_asal_asalan_tidak_dihitung_target_tetapi_tampil_di_riwayat(s):
    sesi_id = _mulai(s, "simulasi")
    _jawab_benar(s, sesi_id, 4)
    s.jam.t = T0 + 30 * 60
    _kumpul(s, sesi_id)

    with s.buka() as kon:
        ringkas = contest_anak.muat_ringkas(kon, s.anak, s.jam.t)

    assert ringkas.selesai_hari_ini == 0 and ringkas.terbaik_simulasi is None
    assert [r.sesi_id for r in ringkas.riwayat] == [sesi_id] and ringkas.riwayat[0].asal_kumpul


def _selesaikan(s, mode, benar, menit):
    sesi_id = _mulai(s, mode)
    _jawab_benar(s, sesi_id, benar)
    s.jam.t += menit * 60
    _kumpul(s, sesi_id)
    return sesi_id


def test_banding_simulasi_hanya_dengan_simulasi_sebelumnya(s):
    _selesaikan(s, None, 9, 5)
    pertama = _selesaikan(s, "simulasi", 12, 15)
    kedua = _selesaikan(s, "simulasi", 15, 15)

    _, _, hasil_kedua = raw(s, f"/murid/lomba/hasil/{kedua}")
    _, _, hasil_pertama = raw(s, f"/murid/lomba/hasil/{pertama}")

    assert "Naik 3 dari simulasi sebelumnya" in hasil_kedua.decode()
    assert "sebelumnya" not in re.sub(r"<style>.*?</style>", "", hasil_pertama.decode(), flags=re.S)


def test_halaman_guru_memisahkan_terbaik_per_mode_dan_grafik_persen(s):
    _selesaikan(s, None, 9, 5)
    simulasi = _selesaikan(s, "simulasi", 21, 20)

    kode, _, isi = raw(s, f"/anak/{s.anak}/lomba", kredensial=GURU)
    _, _, detail = raw(s, f"/anak/{s.anak}/lomba/{simulasi}", kredensial=GURU)

    teks = isi.decode()
    assert kode == 200 and "9/10" in teks and "21/35" in teks and "Simulasi terbaik" in teks
    assert "Persen benar per sesi" in teks
    assert re.findall(r'<circle [^>]*data-nilai="(\d+)"', teks) == ["90", "60"]
    assert "<td>Simulasi</td>" in teks and "<td>Latihan</td>" in teks
    assert "21/35" in detail.decode() and len(re.findall(r'<h3 class="hl-judul" id="soal-', detail.decode())) == 35


# --- guru: isian durasi ----------------------------------------------------------------------------------

def test_guru_menyimpan_durasi_dan_kartu_menampilkannya(s):
    kode, header, _ = raw(s, f"/anak/{s.anak}/lomba/pengaturan",
                          dict(FORM_SAH, durasi_latihan="20", durasi_simulasi="90"), kredensial=GURU)
    _, _, isi = raw(s, f"/anak/{s.anak}/lomba", kredensial=GURU)

    p = _penugasan(s, s.anak)
    teks = isi.decode()
    assert kode == 303 and header["location"].endswith("?tersimpan=1")
    assert (p.durasi_latihan_detik, p.durasi_simulasi_detik) == (1200, 5400)
    assert 'name="durasi_latihan" min="5" max="180" step="1" inputmode="numeric" value="20"' in teks
    assert 'name="durasi_simulasi" min="5" max="180" step="1" inputmode="numeric" value="90"' in teks
    assert "Latihan (10 soal, 20 menit)" in teks and "Simulasi Lomba (35 soal, 90 menit)" in teks


def test_durasi_kosong_berarti_bawaan_dan_kolom_tak_terkirim_mempertahankan_nilai(s):
    raw(s, f"/anak/{s.anak}/lomba/pengaturan", dict(FORM_SAH, durasi_latihan="20", durasi_simulasi="90"),
        kredensial=GURU)

    raw(s, f"/anak/{s.anak}/lomba/pengaturan", dict(FORM_SAH, target="2"), kredensial=GURU)       # form lama
    tetap = _penugasan(s, s.anak)
    raw(s, f"/anak/{s.anak}/lomba/pengaturan", dict(FORM_SAH, durasi_latihan="", durasi_simulasi=" "),
        kredensial=GURU)
    kosong = _penugasan(s, s.anak)

    assert (tetap.durasi_latihan_detik, tetap.durasi_simulasi_detik, tetap.target_harian) == (1200, 5400, 2)
    assert (kosong.durasi_latihan_detik, kosong.durasi_simulasi_detik) == (None, None)


@pytest.mark.parametrize("nilai", ["4", "181", "0", "abc", "20.5", "-5", "1e2", ANGKA_ARAB, "1000"])
def test_durasi_tidak_sah_pesan_ramah_tanpa_menulis(s, nilai):
    raw(s, f"/anak/{s.anak}/lomba/pengaturan", dict(FORM_SAH, durasi_simulasi="45"), kredensial=GURU)
    sebelum = _penugasan(s, s.anak)

    kode, header, _ = raw(s, f"/anak/{s.anak}/lomba/pengaturan",
                          dict(FORM_SAH, target="3", durasi_latihan=nilai), kredensial=GURU)
    _, _, isi = raw(s, f"/anak/{s.anak}/lomba?galat=durasi", kredensial=GURU)

    assert kode == 303 and header["location"] == f"/anak/{s.anak}/lomba?galat=durasi"
    assert _penugasan(s, s.anak) == sebelum
    assert H.GALAT_DURASI in isi.decode() and 'role="alert"' in isi.decode()


@pytest.mark.parametrize("nilai,detik", [("5", 300), ("180", 10800), ("030", 1800), (" 25 ", 1500)])
def test_durasi_batas_sah_diterima(s, nilai, detik):
    kode, _, _ = raw(s, f"/anak/{s.anak}/lomba/pengaturan", dict(FORM_SAH, durasi_latihan=nilai), kredensial=GURU)
    assert kode == 303 and _penugasan(s, s.anak).durasi_latihan_detik == detik


def test_durasi_untuk_anak_guru_lain_404_identik_tanpa_menulis(s):
    with s.buka() as kon:
        sebelum = [tuple(b) for b in kon.execute("SELECT * FROM lomba_penugasan ORDER BY siswa_id")]

    asing = raw(s, f"/anak/{s.asing}/lomba/pengaturan", dict(FORM_SAH, durasi_latihan="20"), kredensial=GURU)
    asing_galat = raw(s, f"/anak/{s.asing}/lomba/pengaturan", dict(FORM_SAH, durasi_latihan="999"), kredensial=GURU)
    tidak_ada = raw(s, "/anak/987654/lomba", kredensial=GURU)

    assert sidik(asing) == sidik(asing_galat) == sidik(tidak_ada) and asing[0] == 404
    with s.buka() as kon:
        assert [tuple(b) for b in kon.execute("SELECT * FROM lomba_penugasan ORDER BY siswa_id")] == sebelum
