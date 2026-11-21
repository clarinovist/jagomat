"""Metrik runtime dalam memori: persentil, batas memori, label rute (privasi), galat locked.

Data sintetis. Tiap test memakai instance `Metrik` baru, bukan singleton modul, agar tidak
saling mengganggu. Guard privasi: label rute tidak boleh memuat path mentah.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import metrik_runtime as M  # noqa: E402

TOKEN_PANJANG = "Zk3p9QxVbN7mTrLw2YdHcF8sAeJuGo5iXq1WnBvRtUy4"
UUID = "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture()
def metrik():
    return M.Metrik()


# --- persentil (nearest-rank) -----------------------------------------------------------

def test_persentil_nearest_rank_pada_data_kecil():
    data = [0.010, 0.020, 0.030, 0.040, 0.050, 0.060, 0.070, 0.080, 0.090, 0.100]
    assert M.persentil(sorted(data), 50) == 0.050
    assert M.persentil(sorted(data), 95) == 0.100
    assert M.persentil(sorted(data), 99) == 0.100
    assert M.persentil([0.5], 95) == 0.5


def test_persentil_data_kosong_nol():
    assert M.persentil([], 95) == 0.0


def test_ringkasan_p50_p95_p99_maks_dalam_milidetik(metrik):
    for i in range(1, 101):
        metrik.catat_request("GET", "/guru", 200, i / 1000)
    kunci = metrik.ringkasan()["rute"]["GET /guru"]
    assert kunci["n"] == 100
    assert kunci["p50_ms"] == 50.0
    assert kunci["p95_ms"] == 95.0
    assert kunci["p99_ms"] == 99.0
    assert kunci["maks_ms"] == 100.0


# --- batas memori -----------------------------------------------------------------------

def test_ring_buffer_dibatasi_512_durasi_terakhir(metrik):
    for i in range(M.KAPASITAS_RING + 100):
        durasi = 5.0 if i < 100 else 0.001  # 100 durasi lambat paling awal harus terbuang
        metrik.catat_request("GET", "/guru", 200, durasi)
    r = metrik.ringkasan()["rute"]["GET /guru"]
    assert M.KAPASITAS_RING == 512
    assert r["n"] == 612            # jumlah total tetap utuh
    assert r["maks_ms"] == 1.0      # tetapi persentil hanya dari 512 terakhir
    assert r["p99_ms"] == 1.0


def test_kunci_dibatasi_64_sisanya_ke_lainnya(metrik, monkeypatch):
    rute_putih = ["/r%d" % i for i in range(200)]
    monkeypatch.setattr(M, "RUTE_PUTIH", frozenset(rute_putih))
    for rute in rute_putih:
        metrik.catat_request("GET", rute, 200, 0.001)
        metrik.catat_request("POST", rute, 200, 0.001)
    kunci = metrik.ringkasan()["rute"]
    assert M.BATAS_KUNCI == 64
    assert len(kunci) <= 64
    assert "GET lainnya" in kunci and "POST lainnya" in kunci
    assert sum(v["n"] for v in kunci.values()) == 400   # tidak ada request yang hilang


# --- label rute: privasi ----------------------------------------------------------------

@pytest.mark.parametrize("path,harap", [
    ("/", "/"),
    ("", "/"),
    ("/guru", "/guru"),
    ("/guru/", "/guru"),
    ("/guru?section=a&anak=Budi", "/guru"),
    ("/anak/42/sesi", "/anak"),
    ("/sesi/" + UUID, "/sesi"),
    ("/mulai/" + TOKEN_PANJANG, "/mulai"),
    ("/laporan-ortu/" + TOKEN_PANJANG + "?x=1#frag", "/laporan-ortu"),
    ("/admin/metrik", "/admin"),
    ("/cek-kemampuan", "/cek-kemampuan"),
    ("/aset/favicon.svg", "/aset"),
])
def test_label_rute_hanya_segmen_pertama_daftar_putih(path, harap):
    assert M.label_rute(path) == harap


@pytest.mark.parametrize("path", [
    "/rahasia-anak-budi",
    "/" + TOKEN_PANJANG,
    "/" + UUID,
    "/12345",
    "//guru",
    "http://contoh.test/guru",
    "/%67uru",                       # percent-encoding tidak dibongkar
    "/GURU",
    "/../etc/passwd",
    "guru",
    "/ guru",
    "/guru%00",
    "/" + "a" * 5000,
])
def test_label_rute_path_asing_menjadi_lainnya(path):
    assert M.label_rute(path) == "lainnya"


def test_ringkasan_tidak_memuat_potongan_path_atau_token(metrik):
    jalur = [
        "/anak/4242/sesi/9?nama=Budi%20Sintetis",
        "/sesi/" + UUID,
        "/mulai/" + TOKEN_PANJANG,
        "/laporan-ortu/" + TOKEN_PANJANG,
        "/rahasia-" + TOKEN_PANJANG,
        "/guru?token=" + TOKEN_PANJANG + "&q=Budi",
    ]
    for p in jalur:
        metrik.catat_request("GET", M.label_rute(p), 200, 0.01)
        metrik.catat_request("POST", M.label_rute(p), 303, 0.01)
    teks = json.dumps(metrik.ringkasan())
    for terlarang in ("4242", UUID, TOKEN_PANJANG, "Budi", "rahasia", "token=", "nama="):
        assert terlarang not in teks


def test_catat_request_menolak_label_di_luar_daftar_putih(metrik):
    """Pertahanan kedua: penelepon yang keliru memberi path mentah tetap tidak tercatat."""
    metrik.catat_request("GET", "/anak/4242/rahasia-" + TOKEN_PANJANG, 200, 0.01)
    teks = json.dumps(metrik.ringkasan())
    assert TOKEN_PANJANG not in teks and "4242" not in teks
    assert "GET lainnya" in metrik.ringkasan()["rute"]


def test_metode_tidak_dikenal_menjadi_lain(metrik):
    metrik.catat_request("BUDI-" + TOKEN_PANJANG, "/guru", 200, 0.01)
    teks = json.dumps(metrik.ringkasan())
    assert TOKEN_PANJANG not in teks
    assert "LAIN /guru" in metrik.ringkasan()["rute"]


# --- status ----------------------------------------------------------------------------

def test_status_dikelompokkan_2xx_3xx_4xx_5xx(metrik):
    for kode in (200, 204, 303, 404, 401, 403, 500, 503, 503):
        metrik.catat_request("GET", "/guru", kode, 0.001)
    r = metrik.ringkasan()["rute"]["GET /guru"]
    assert r["status"] == {"2xx": 2, "3xx": 1, "4xx": 3, "5xx": 3}
    assert r["n"] == 9


@pytest.mark.parametrize("kode", [0, 99, 600, -1, None, "200"])
def test_status_aneh_tetap_dihitung_n_tanpa_bucket(metrik, kode):
    metrik.catat_request("GET", "/guru", kode, 0.001)
    r = metrik.ringkasan()["rute"]["GET /guru"]
    assert r["n"] == 1 and sum(r["status"].values()) == 0


# --- galat sqlite ----------------------------------------------------------------------

@pytest.mark.parametrize("pesan", [
    "database is locked", "database table is locked", "Database Is Locked",
    "database is busy",
])
def test_galat_locked_menaikkan_penghitung(metrik, pesan):
    metrik.catat_galat_sqlite(sqlite3.OperationalError(pesan))
    assert metrik.ringkasan()["sqlite_locked"] == 1


@pytest.mark.parametrize("exc", [
    sqlite3.OperationalError("no such table: siswa"),
    sqlite3.IntegrityError("database is locked"),   # bukan OperationalError
    ValueError("database is locked"),
    KeyError("locked"),
])
def test_galat_selain_locked_tidak_menaikkan(metrik, exc):
    metrik.catat_galat_sqlite(exc)
    assert metrik.ringkasan()["sqlite_locked"] == 0


def test_teks_galat_tidak_disimpan(metrik):
    metrik.catat_galat_sqlite(sqlite3.OperationalError("database is locked /data/anak-budi.db"))
    teks = json.dumps(metrik.ringkasan())
    assert "anak-budi" not in teks and "/data" not in teks


# --- ringkasan: bentuk, CPU, cgroup ------------------------------------------------------

def test_ringkasan_bisa_di_json_dan_memuat_kunci_wajib(metrik):
    metrik.catat_request("GET", "/", 200, 0.002)
    r = json.loads(json.dumps(metrik.ringkasan()))
    assert {"uptime_detik", "rute", "sqlite_locked", "cpu", "galat_metrik"} <= set(r)
    assert {"proses_detik", "cpu_count", "rasio_cpu_sejak_start", "cgroup"} <= set(r["cpu"])
    assert r["uptime_detik"] >= 0 and r["galat_metrik"] == 0


def test_cgroup_dibaca_dari_cpu_stat(tmp_path, monkeypatch):
    berkas = tmp_path / "cpu.stat"
    berkas.write_text(
        "usage_usec 1234567\nuser_usec 1000\nsystem_usec 200\n"
        "nr_periods 10\nnr_throttled 3\nthrottled_usec 4500\n"
    )
    monkeypatch.setattr(M, "BERKAS_CGROUP_CPU", berkas)
    assert M.baca_cgroup_cpu() == {
        "usage_usec": 1234567, "nr_throttled": 3, "throttled_usec": 4500,
    }


@pytest.mark.parametrize("isi", [None, "", "sampah tanpa angka\n", "usage_usec abc\n"])
def test_cgroup_tak_terbaca_menjadi_none(tmp_path, monkeypatch, isi):
    berkas = tmp_path / "cpu.stat"
    if isi is not None:
        berkas.write_text(isi)
    monkeypatch.setattr(M, "BERKAS_CGROUP_CPU", berkas)
    assert M.baca_cgroup_cpu() is None


# --- thread-safety ----------------------------------------------------------------------

def test_pencatatan_serempak_jumlah_total_cocok(metrik):
    jumlah_ulir, per_ulir = 8, 500

    def kerja():
        for i in range(per_ulir):
            metrik.catat_request("GET", "/guru", 200, 0.001)
            metrik.catat_request("POST", "/akun", 303, 0.002)
            metrik.catat_galat_sqlite(sqlite3.OperationalError("database is locked"))

    ulir = [threading.Thread(target=kerja) for _ in range(jumlah_ulir)]
    for u in ulir:
        u.start()
    for u in ulir:
        u.join()
    r = metrik.ringkasan()
    assert r["rute"]["GET /guru"]["n"] == jumlah_ulir * per_ulir
    assert r["rute"]["POST /akun"]["n"] == jumlah_ulir * per_ulir
    assert r["sqlite_locked"] == jumlah_ulir * per_ulir
    assert r["galat_metrik"] == 0


# --- kode metrik tidak boleh melempar ke jalur request -----------------------------------

def test_selesai_ukur_tidak_melempar_dan_menaikkan_galat_metrik(metrik, monkeypatch):
    def rusak(*a, **k):
        raise RuntimeError("rusak sintetis")
    monkeypatch.setattr(metrik, "catat_request", rusak)
    metrik.selesai_ukur(0.0, "GET", "/guru", 200)   # tidak boleh melempar
    assert metrik.ringkasan()["galat_metrik"] == 1


def test_catat_galat_sqlite_tidak_melempar_bila_internal_rusak(metrik, monkeypatch):
    monkeypatch.setattr(M, "_adalah_locked", lambda exc: 1 / 0)
    metrik.catat_galat_sqlite(sqlite3.OperationalError("database is locked"))
    assert metrik.ringkasan()["galat_metrik"] == 1


# --- baris berkala ---------------------------------------------------------------------

def test_baris_berkala_none_bila_tak_ada_request_baru(metrik):
    assert metrik.baris_berkala() is None
    metrik.catat_request("GET", "/guru", 200, 0.01)
    baris = metrik.baris_berkala()
    assert baris is not None
    assert "\n" not in baris
    isi = json.loads(baris)
    assert "metrik" in isi and isi["metrik"]["total_request"] == 1
    assert metrik.baris_berkala() is None            # tidak ada request baru lagi
    metrik.catat_request("GET", "/guru", 200, 0.01)
    assert metrik.baris_berkala() is not None


def test_baris_berkala_dibatasi_jumlah_kunci(metrik, monkeypatch):
    rute_putih = ["/r%d" % i for i in range(40)]
    monkeypatch.setattr(M, "RUTE_PUTIH", frozenset(rute_putih))
    for rute in rute_putih:
        metrik.catat_request("GET", rute, 200, 0.001)
    isi = json.loads(metrik.baris_berkala())["metrik"]
    assert len(isi["rute"]) <= M.KUNCI_BARIS_MAKS


def test_pencetak_berkala_mencetak_hanya_bila_ada_request(metrik):
    keluar = []
    cetak = threading.Event()

    def tulis(baris):
        keluar.append(baris)
        cetak.set()

    pencetak = M.PencetakBerkala(metrik, interval=0.01, tulis=tulis)
    pencetak.mulai()
    try:
        assert not cetak.wait(0.15)                  # tanpa request: sunyi
        metrik.catat_request("GET", "/guru", 200, 0.01)
        assert cetak.wait(2.0)
    finally:
        pencetak.hentikan()
    assert len(keluar) >= 1
    assert json.loads(keluar[0])["metrik"]["total_request"] == 1


def test_pencetak_berhenti_bersih(metrik):
    pencetak = M.PencetakBerkala(metrik, interval=0.01, tulis=lambda b: None)
    pencetak.mulai()
    pencetak.hentikan()
    assert not pencetak.ulir.is_alive()


# --- ketahanan shutdown dan penulisan log (temuan tinjauan keamanan, LOW/INFO) -------------

def test_hentikan_tidak_menggantung_bila_penulisan_log_macet(metrik, monkeypatch):
    monkeypatch.setattr(M, "JOIN_TIMEOUT_DETIK", 0.2)
    macet = threading.Event()
    mulai_menulis = threading.Event()

    def tulis(_baris):
        mulai_menulis.set()
        macet.wait(timeout=5)  # meniru pipa stdout penuh

    metrik.catat_request("GET", "/guru", 200, 0.01)
    pencetak = M.PencetakBerkala(metrik, interval=0.01, tulis=tulis)
    pencetak.mulai()
    assert mulai_menulis.wait(timeout=2), "pencetak tidak sempat menulis"

    selesai = threading.Event()
    penghenti = threading.Thread(target=lambda: (pencetak.hentikan(), selesai.set()), daemon=True)
    penghenti.start()
    try:
        assert selesai.wait(timeout=2), "hentikan() menggantung saat penulisan macet"
    finally:
        macet.set()


def test_baris_log_ditulis_dalam_satu_operasi_agar_tidak_terselip(monkeypatch):
    potongan = []

    class Perekam:
        def write(self, teks):
            potongan.append(teks)
            return len(teks)

        def flush(self):
            pass

    monkeypatch.setattr(sys, "stdout", Perekam())

    M._tulis_stdout('{"metrik":{}}')

    assert potongan == ['{"metrik":{}}\n']
