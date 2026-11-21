"""Metrik runtime dalam memori: p95 latensi per rute, galat `database is locked`, dan CPU.

Tujuannya satu: memutuskan perlu tidaknya skala (Tahap B) berdasarkan angka, bukan
dugaan. Tanpa dependency, tanpa berkas, tanpa log per request.

Keterbatasan (sengaja, jangan dianggap bug):
- Di memori: hilang saat proses restart/deploy. Cukup untuk membaca beban satu jendela
  kerja; bukan arsip jangka panjang.
- Per proses: tiap container/proses punya hitungan sendiri.
- Hanya request HTTP (`do_GET`/`do_POST`). Galat `locked` di thread pemeliharaan atau
  cron tidak terhitung. Galat yang ditangkap handler sendiri lalu dijawab 503 (mis. rute
  admin yang menangkap `sqlite3.Error`) juga tidak sampai ke pengukur, jadi
  `sqlite_locked` bisa lebih rendah dari kenyataan; baca bersama hitungan `5xx` per rute.
- Persentil dihitung dari 512 durasi terakhir per kunci (`n` tetap total sejak start).
- Daftar putih rute (sekitar 48 segmen x 2 metode) lebih banyak dari batas 64 kunci;
  bila banyak rute berbeda aktif, sisanya digabung ke `lainnya` (tidak ada yang hilang
  dari hitungan `n`).

Privasi: label rute hanya segmen pertama path bila ada di `RUTE_PUTIH` (literal dari
router), `/` untuk root, selain itu `lainnya`. Path mentah, query, id, token tautan,
cookie, dan teks galat tidak pernah disimpan atau dikeluarkan. `catat_request` memeriksa
ulang labelnya sendiri sehingga pemanggil yang keliru tetap tidak bisa membocorkan path.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
import threading
import time
from collections import deque
from pathlib import Path

KAPASITAS_RING = 512
BATAS_KUNCI = 64
KUNCI_BARIS_MAKS = 10
INTERVAL_BARIS_DETIK = 600
JOIN_TIMEOUT_DETIK = 2.0
RUTE_LAINNYA = "lainnya"
RUTE_ROOT = "/"
METODE_LAIN = "LAIN"
METODE_SAH = frozenset({"GET", "POST"})
KELOMPOK_STATUS = ("2xx", "3xx", "4xx", "5xx")
TANDA_LOCKED = ("locked", "busy")
BERKAS_CGROUP_CPU = Path("/sys/fs/cgroup/cpu.stat")
KUNCI_CGROUP = ("usage_usec", "nr_throttled", "throttled_usec")
MS = 1000.0

# Segmen pertama yang dikenali router (web.py `_rute_get`/`_rute_post` dan modul
# `tangani_get`/`tangani_post` yang didelegasikan). Literal tetap: menambah rute baru
# ke router tidak otomatis membuka label baru, dan input pengguna tidak bisa menjadi label.
RUTE_PUTIH = frozenset({
    "/admin", "/akun", "/analitik", "/anak", "/anggota", "/aset", "/bagikan",
    "/batalkan", "/bubarkan", "/cabut-tautan", "/cari", "/cek-kemampuan", "/cerita",
    "/cetak", "/contoh-peta-kemampuan", "/daftar", "/guru", "/hapus",
    "/kebijakan-privasi", "/keluar", "/konfirmasi", "/lampiran", "/langganan",
    "/laporan", "/laporan-ortu", "/latihan-serupa", "/lembaga", "/lembar",
    "/lupa-sandi", "/masuk", "/mulai", "/murid", "/ortu", "/paket-coba", "/pendamping",
    "/pengaturan", "/persetujuan", "/pesanan", "/riset", "/sesi", "/sesi-baru",
    "/sesi-diagnostik", "/sesi-gabungan", "/sesi-remedial", "/siklus",
    "/syarat-penggunaan", "/tinjauan", "/v2",
})


def label_rute(path) -> str:
    """Label aman untuk sebuah path mentah: segmen pertama daftar putih, `/`, atau `lainnya`."""
    if not isinstance(path, str):
        return RUTE_LAINNYA
    bersih = path.split("?", 1)[0].split("#", 1)[0]
    if bersih == "":
        return RUTE_ROOT
    if not bersih.startswith("/"):
        return RUTE_LAINNYA
    if bersih == RUTE_ROOT:
        return RUTE_ROOT
    segmen = "/" + bersih[1:].split("/", 1)[0]
    return segmen if segmen in RUTE_PUTIH else RUTE_LAINNYA


def _label_aman(rute) -> str:
    """Pertahanan kedua: hanya label yang sudah bersih yang boleh masuk penyimpanan."""
    if rute == RUTE_ROOT or rute in RUTE_PUTIH:
        return rute
    return RUTE_LAINNYA


def persentil(terurut, p: float) -> float:
    """Nearest-rank pada daftar yang SUDAH terurut naik; kosong -> 0.0."""
    if not terurut:
        return 0.0
    peringkat = max(1, math.ceil(p / 100.0 * len(terurut)))
    return terurut[min(peringkat, len(terurut)) - 1]


def _kelompok_status(kode):
    if isinstance(kode, bool) or not isinstance(kode, int):
        return None
    if 200 <= kode < 600:
        return "%dxx" % (kode // 100)
    return None


def _adalah_locked(exc) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    teks = str(exc).lower()
    return any(tanda in teks for tanda in TANDA_LOCKED)


def baca_cgroup_cpu():
    """Angka throttling cgroup v2, atau None bila `cpu.stat` tak ada/tak terbaca."""
    try:
        baris = BERKAS_CGROUP_CPU.read_text().splitlines()
    except (OSError, ValueError):
        return None
    nilai = {}
    for entri in baris:
        bagian = entri.split()
        if len(bagian) == 2 and bagian[0] in KUNCI_CGROUP:
            try:
                nilai[bagian[0]] = int(bagian[1])
            except ValueError:
                return None
    if not nilai:
        return None
    return {kunci: nilai.get(kunci) for kunci in KUNCI_CGROUP}


class _Rute:
    """Penampung satu kunci (metode, rute); hanya dipakai di bawah kunci `Metrik`."""

    def __init__(self):
        self.durasi = deque(maxlen=KAPASITAS_RING)
        self.n = 0
        self.status = {kel: 0 for kel in KELOMPOK_STATUS}

    def catat(self, durasi_detik: float, kelompok) -> None:
        self.durasi.append(durasi_detik)
        self.n += 1
        if kelompok is not None:
            self.status[kelompok] += 1

    def ringkas(self) -> dict:
        urut = sorted(self.durasi)
        return {
            "n": self.n,
            "p50_ms": round(persentil(urut, 50) * MS, 2),
            "p95_ms": round(persentil(urut, 95) * MS, 2),
            "p99_ms": round(persentil(urut, 99) * MS, 2),
            "maks_ms": round((urut[-1] if urut else 0.0) * MS, 2),
            "status": dict(self.status),
        }


class Metrik:
    """Penampung metrik thread-safe. Pakai instance baru di test; produksi memakai `METRIK`."""

    def __init__(self):
        self._kunci = threading.Lock()
        self.atur_ulang()

    def atur_ulang(self) -> None:
        with self._kunci:
            self._rute = {}
            self._locked = 0
            self._galat_metrik = 0
            self._total = 0
            self._total_baris_terakhir = 0
            self._mulai = time.monotonic()
            self._cpu_awal = time.process_time()

    def _tambah_galat_metrik(self) -> None:
        with self._kunci:
            self._galat_metrik += 1

    def _kunci_efektif(self, metode: str, rute: str):
        kunci = (metode, rute)
        if kunci in self._rute or rute == RUTE_LAINNYA:
            return kunci
        cadangan = len(METODE_SAH) + 1   # slot tetap untuk `lainnya` tiap metode
        if len(self._rute) < BATAS_KUNCI - cadangan:
            return kunci
        return (metode, RUTE_LAINNYA)

    def catat_request(self, metode, rute, status, durasi_detik) -> None:
        metode = metode if metode in METODE_SAH else METODE_LAIN
        rute = _label_aman(rute)
        kelompok = _kelompok_status(status)
        with self._kunci:
            kunci = self._kunci_efektif(metode, rute)
            penampung = self._rute.get(kunci)
            if penampung is None:
                penampung = self._rute[kunci] = _Rute()
            penampung.catat(float(durasi_detik), kelompok)
            self._total += 1

    def catat_galat_sqlite(self, exc) -> None:
        """Naikkan penghitung hanya untuk `OperationalError` locked/busy; teks galat dibuang."""
        try:
            if _adalah_locked(exc):
                with self._kunci:
                    self._locked += 1
        except Exception:
            self._tambah_galat_metrik()

    def selesai_ukur(self, awal, metode, path, status) -> None:
        """Dipanggil dari `finally` request. TIDAK PERNAH melempar."""
        try:
            durasi = time.perf_counter() - awal
            self.catat_request(metode, label_rute(path), status, durasi)
        except Exception:
            self._tambah_galat_metrik()

    def _cpu(self, uptime: float) -> dict:
        proses = time.process_time()
        terpakai = proses - self._cpu_awal
        return {
            "proses_detik": round(proses, 3),
            "cpu_count": os.cpu_count(),
            # 1.0 = satu inti penuh sejak start (GIL: kira-kira batas atas satu proses).
            "rasio_cpu_sejak_start": round(terpakai / uptime, 4) if uptime > 0 else 0.0,
            "cgroup": baca_cgroup_cpu(),
        }

    def ringkasan(self) -> dict:
        with self._kunci:
            rute = {"%s %s" % kunci: p.ringkas() for kunci, p in sorted(self._rute.items())}
            locked, galat = self._locked, self._galat_metrik
            uptime = time.monotonic() - self._mulai
        return {
            "uptime_detik": round(uptime, 1),
            "rute": rute,
            "sqlite_locked": locked,
            "cpu": self._cpu(uptime),
            "galat_metrik": galat,
        }

    def baris_berkala(self):
        """Satu baris JSON ringkas, atau None bila tak ada request baru sejak baris terakhir."""
        with self._kunci:
            if self._total == self._total_baris_terakhir:
                return None
            self._total_baris_terakhir = self._total
            total = self._total
        penuh = self.ringkasan()
        terlambat = sorted(
            penuh["rute"].items(), key=lambda it: it[1]["p95_ms"], reverse=True,
        )[:KUNCI_BARIS_MAKS]
        isi = {
            "total_request": total,
            "uptime_detik": penuh["uptime_detik"],
            "sqlite_locked": penuh["sqlite_locked"],
            "galat_metrik": penuh["galat_metrik"],
            "cpu": penuh["cpu"],
            "rute": {k: {"n": v["n"], "p95_ms": v["p95_ms"], "status": v["status"]}
                     for k, v in terlambat},
        }
        return json.dumps({"metrik": isi}, separators=(",", ":"))


class PencetakBerkala:
    """Thread daemon: cetak satu baris `{"metrik": ...}` tiap interval bila ada request baru."""

    def __init__(self, metrik, interval=INTERVAL_BARIS_DETIK, tulis=None):
        self.metrik = metrik
        self.interval = interval
        self.tulis = tulis or _tulis_stdout
        self.berhenti = threading.Event()
        self.ulir = None

    def _putaran(self) -> None:
        while not self.berhenti.wait(self.interval):
            try:
                baris = self.metrik.baris_berkala()
                if baris is not None:
                    self.tulis(baris)
            except Exception:
                self.metrik._tambah_galat_metrik()

    def mulai(self) -> None:
        if self.ulir is not None:
            return
        self.ulir = threading.Thread(target=self._putaran, name="metrik-berkala", daemon=True)
        self.ulir.start()

    def hentikan(self) -> None:
        self.berhenti.set()
        if self.ulir is not None:
            # Thread daemon: bila penulisan log macet (pipa penuh), jangan menahan shutdown.
            self.ulir.join(timeout=JOIN_TIMEOUT_DETIK)


def _tulis_stdout(baris: str) -> None:
    # Satu write: print() menulis teks dan newline terpisah sehingga bisa terselip thread lain.
    sys.stdout.write(baris + "\n")
    sys.stdout.flush()


METRIK = Metrik()
_pencetak = None
_kunci_pencetak = threading.Lock()


def mulai_ukur() -> float:
    return time.perf_counter()


def selesai_ukur(awal, metode, path, status) -> None:
    METRIK.selesai_ukur(awal, metode, path, status)


def catat_galat_sqlite(exc) -> None:
    METRIK.catat_galat_sqlite(exc)


def ringkasan() -> dict:
    return METRIK.ringkasan()


def mulai_pencetak(interval=INTERVAL_BARIS_DETIK, tulis=None) -> None:
    """Mulai pencetak berkala untuk `METRIK`; panggilan kedua tidak membuat thread ganda."""
    global _pencetak
    with _kunci_pencetak:
        if _pencetak is None:
            _pencetak = PencetakBerkala(METRIK, interval=interval, tulis=tulis)
            _pencetak.mulai()


def hentikan_pencetak() -> None:
    global _pencetak
    with _kunci_pencetak:
        pencetak, _pencetak = _pencetak, None
    if pencetak is not None:
        pencetak.hentikan()
