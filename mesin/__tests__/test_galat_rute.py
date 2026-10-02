"""Jaring pengaman rute — exception tak terduga jangan jadi 502 kosong.

Insiden 3 Sep 2026: `buat_sesi_remedial` melempar KeyError di dalam
do_POST. BaseHTTPRequestHandler tidak menulis apa pun ke socket saat
handler melempar, koneksi diputus, dan Caddy di depannya menerjemahkan itu
menjadi **502 Bad Gateway** — halaman kosong tanpa penjelasan, tanpa jejak
di UI, dan tanpa cara pengguna tahu harus berbuat apa.

Kontrak yang dikunci di sini:

  1. Exception di handler menghasilkan respons HTTP 500 yang UTUH, bukan
     koneksi putus. Beda 500 vs 502 bukan kosmetik: 500 berarti aplikasi
     hidup dan menjawab, 502 berarti aplikasi mati dari sudut pandang
     reverse proxy — dua investigasi yang sangat berbeda.
  2. Halamannya berbahasa manusia, tanpa traceback. Detail teknis tetap
     tercetak ke log server (satu-satunya tempat yang aman untuk itu).
  3. Rute yang sudah menjawab (sudah mengirim header) tidak boleh ditimpa
     respons kedua — itu merusak respons yang sebenarnya valid.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import web  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _bikin_meledak(monkeypatch, nama_fungsi="buat_sesi_remedial"):
    """Paksa satu fungsi yang dipanggil handler melempar exception."""

    def peledak(*a, **k):
        raise KeyError("template_hantu")

    monkeypatch.setattr(database, nama_fungsi, peledak)


def test_post_yang_meledak_menjawab_500_bukan_koneksi_putus(server, monkeypatch):
    """Inilah bentuk persis insiden 502: KeyError di dalam do_POST."""
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakLedak", pemilik="guru")
    _bikin_meledak(monkeypatch)

    kode, isi, _ = server.minta(
        f"/sesi-remedial/{sid}", auth=("guru", SANDI_GURU), data={}
    )
    assert kode == 500, (
        "handler yang meledak memutus koneksi (Caddy -> 502); "
        "seharusnya menjawab 500 utuh"
    )
    assert isi, "respons 500 kosong — pengguna tidak diberi tahu apa pun"


def test_halaman_500_tidak_membocorkan_traceback(server, monkeypatch):
    """Detail teknis milik log, bukan milik layar pengguna."""
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakLedak2", pemilik="guru")
    _bikin_meledak(monkeypatch)

    _, isi, _ = server.minta(
        f"/sesi-remedial/{sid}", auth=("guru", SANDI_GURU), data={}
    )
    # Catatan: jangan meng-assert substring terlalu umum seperti "line " —
    # layout halaman memuat JS toggle mata sandi yang mengandung kata itu
    # ("inline"), jadi assertion-nya false positive, bukan kebocoran.
    for bocor in ("Traceback", "KeyError", "template_hantu",
                  "web.py", "database.py", "File \""):
        assert bocor not in isi, f"halaman galat membocorkan {bocor!r}"


def test_halaman_500_menjelaskan_dalam_bahasa_manusia(server, monkeypatch):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakLedak3", pemilik="guru")
    _bikin_meledak(monkeypatch)

    _, isi, _ = server.minta(
        f"/sesi-remedial/{sid}", auth=("guru", SANDI_GURU), data={}
    )
    assert "Ada yang bermasalah" in isi
    assert "coba lagi" in isi.lower()


def test_get_yang_meledak_juga_500(server, monkeypatch):
    """Bukan cuma POST — GET berdata punya lubang yang sama."""
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakLedak4", pemilik="guru")

    def peledak(*a, **k):
        raise RuntimeError("gagal baca")

    monkeypatch.setattr(database, "isi_sesi", peledak)
    monkeypatch.setattr(database, "sasaran_remedial_anak", peledak)

    kode, _, _ = server.minta(
        f"/anak/{sid}?section=latihan", auth=("guru", SANDI_GURU)
    )
    assert kode == 500, "GET yang meledak memutus koneksi, bukan menjawab 500"


def test_respons_normal_tidak_terpengaruh_jaring_pengaman(server):
    """Jaring pengaman tidak boleh mengubah jalur yang sehat."""
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakSehat", pemilik="guru")
    kode, isi, _ = server.minta(f"/anak/{sid}", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "AnakSehat" in isi


def test_galat_setelah_header_terkirim_tidak_ditimpa(server, monkeypatch):
    """Rute yang sudah menjawab tidak boleh dapat respons status KEDUA.

    Dua status line dalam satu koneksi merusak respons yang valid (dan
    membingungkan keep-alive di sisi Caddy). Penanganan galat harus
    menyerah kalau header sudah keluar.

    Assertion-nya menghitung status line yang benar-benar ditulis ke
    socket, BUKAN kode yang diterima klien: mutation test membuktikan
    versi yang hanya meng-assert `kode == 200` tetap lolos walau penjaganya
    dilepas — klien membaca respons pertama saja dan tidak pernah melihat
    respons kedua yang tertinggal di socket.

    Penting: respons kedua ditulis di THREAD server, setelah klien sudah
    menerima yang pertama. Tanpa menunggu handler benar-benar selesai,
    assertion balapan dengan thread itu dan mutasi lolos — ini pun
    ketahuan lewat mutation test, bukan lewat membaca kode.
    """
    import threading

    tercatat = []
    selesai = threading.Event()
    asli_status = web.Penangan.send_response

    def catat(self, kode, *a, **k):
        tercatat.append(kode)
        return asli_status(self, kode, *a, **k)

    def rute_kirim_lalu_meledak(self):
        self._kirim(b"<html>sudah dijawab</html>", 200)
        raise RuntimeError("meledak SESUDAH respons terkirim")

    def do_get_bertanda(self):
        try:
            asli_do_get(self)
        finally:
            selesai.set()

    asli_do_get = web.Penangan.do_GET
    monkeypatch.setattr(web.Penangan, "send_response", catat)
    monkeypatch.setattr(web.Penangan, "_rute_get", rute_kirim_lalu_meledak)
    monkeypatch.setattr(web.Penangan, "do_GET", do_get_bertanda)

    kode, isi, _ = server.minta("/apa-saja")
    assert kode == 200
    assert selesai.wait(5), "handler tidak selesai"
    assert tercatat == [200], (
        f"respons status ditulis lebih dari sekali: {tercatat} — "
        "penanganan galat menimpa respons yang sudah valid"
    )
