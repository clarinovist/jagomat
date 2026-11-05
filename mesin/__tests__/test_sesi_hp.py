"""HP anak sebagai jalur utama sesi les (keputusan pemilik K6–K8, 6 Nov 2026).

Tombol utama sesi "Salin tautan sesi" diganti "Mulai di HP anak": POST native ke
/sesi/<id>/bagikan yang menampilkan kode QR (server-side, tanpa JS) + tautan teks.
Tautan berlaku 12 jam. Host tautan mengikuti allowlist (uji/produksi), bukan Host
sembarang. Lembar persiapan menyebut HP anak sebagai jalur utama, kertas cadangan.
"""
from __future__ import annotations

import http.client
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth  # noqa: E402
import database  # noqa: E402
import design_tokens as T  # noqa: E402
import qr_code  # noqa: E402
import session_prep  # noqa: E402
import share_links  # noqa: E402
import teacher_session_pages  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji, _basic  # noqa: E402

SANDI_LAIN = "sandi-guru-lain-panjang-789"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "hp.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _sesi(kon, nama="Anak Sintetis HP"):
    anak = database.tambah_siswa(kon, nama, pemilik="guru")
    return anak, database.buat_sesi(kon, anak, seed=7)


def _post(server, jalur, host=None, akun=("guru", SANDI_GURU)):
    u = urllib.parse.urlsplit(server.alamat)
    kon = http.client.HTTPConnection(u.hostname, u.port, timeout=10)
    kepala = {"Authorization": _basic(*akun), "Content-Type": "application/x-www-form-urlencoded",
              "Origin": server.alamat, "Content-Length": "0"}
    if host:
        kepala["Host"] = host
        kepala["Origin"] = f"http://{host}"
    kon.request("POST", jalur, body=b"", headers=kepala)
    r = kon.getresponse()
    hasil = r.status, r.read().decode("utf-8", "replace"), dict(r.getheaders())
    kon.close()
    return hasil


def _tautan(html):
    return re.search(r'id="tautan-sesi"[^>]*value="([^"]+)"', html).group(1)


def test_tombol_utama_sesi_mulai_di_hp_anak_tanpa_cta_ganda(db):
    with database.buka(db) as kon:
        _anak, sesi = _sesi(kon)
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        share_links.buat(kon, sesi)
        html_aktif = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
    assert html.count(f'action="/sesi/{sesi}/bagikan"') == 1
    assert ">Mulai di HP anak<" in html and "Salin tautan sesi" not in html
    # Tombol ini membuka halaman kode QR (POST native), bukan disalin lewat JS.
    assert "data-bagikan-sesi" not in html
    assert html_aktif.count(f'action="/sesi/{sesi}/bagikan"') == 1
    assert "Buat kode baru untuk HP anak" in html_aktif and "Buat dan salin tautan baru" not in html_aktif
    assert "tautan lama berhenti" in html_aktif


def test_bagikan_menampilkan_kode_qr_yang_memuat_tautan_persis(server):
    with server.buka() as kon:
        _anak, sesi = _sesi(kon)
    kode, html, kepala = _post(server, f"/sesi/{sesi}/bagikan")
    assert kode == 200
    tautan = _tautan(html)
    assert re.fullmatch(r"https://jagomat\.id/mulai/[A-Za-z0-9_-]{43}", tautan)
    assert qr_code.svg(tautan, warna_gelap=T.TEKS_UTAMA, warna_terang=T.LATAR_KARTU,
                       label="Kode QR tautan latihan anak") in html
    assert "Anak Sintetis HP" in html and "12 jam" in html
    kartu = html.split('class="kartu-st bagikan-kartu-st"', 1)[1].split("</section>", 1)[0]
    assert "<script" not in kartu and "kode-qr" in kartu  # QR tanpa JS
    assert kepala.get("Cache-Control") == "no-store"
    with server.buka() as kon:
        assert share_links.ambil(kon, tautan.rsplit("/", 1)[1])["sesi_id"] == sesi


@pytest.mark.parametrize("host,awalan", [
    ("uji.jagomat.id", "https://uji.jagomat.id/mulai/"),
    ("jagomat.id", "https://jagomat.id/mulai/"),
    ("penyerang.example", "https://jagomat.id/mulai/"),
    ("uji.jagomat.id.penyerang.example", "https://jagomat.id/mulai/"),
])
def test_host_tautan_mengikuti_allowlist(server, host, awalan):
    with server.buka() as kon:
        _anak, sesi = _sesi(kon)
    kode, html, _ = _post(server, f"/sesi/{sesi}/bagikan", host=host)
    assert kode == 200
    assert _tautan(html).startswith(awalan)


def test_tautan_berlaku_dua_belas_jam(db):
    with database.buka(db) as kon:
        _anak, sesi = _sesi(kon)
        token = share_links.buat(kon, sesi, sekarang=1_000)
        baris = kon.execute("SELECT dibuat, kedaluarsa FROM tautan_sesi WHERE sesi_id=?", (sesi,)).fetchone()
        assert baris["kedaluarsa"] - baris["dibuat"] == 12 * 3600
        assert share_links.ambil(kon, token, sekarang=1_000 + 12 * 3600 - 1)
        assert share_links.ambil(kon, token, sekarang=1_000 + 12 * 3600) is None


def test_guru_asing_404_identik_tanpa_membuat_tautan(server):
    auth.tambah_akun("guru-lain", SANDI_LAIN, "guru", path=auth.BERKAS_SANDI)
    with server.buka() as kon:
        _anak, sesi = _sesi(kon)
        sebelum = tuple(kon.iterdump())
    asing = _post(server, f"/sesi/{sesi}/bagikan", akun=("guru-lain", SANDI_LAIN))
    tidak_ada = _post(server, "/sesi/999999/bagikan", akun=("guru-lain", SANDI_LAIN))
    assert asing[0] == tidak_ada[0] == 404 and asing[1] == tidak_ada[1]
    assert "kode-qr" not in asing[1]
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_lembar_persiapan_hp_anak_utama_kertas_cadangan(db):
    with database.buka(db) as kon:
        anak, _ = _sesi(kon)
        siswa = kon.execute("SELECT * FROM siswa WHERE id=?", (anak,)).fetchone()
        html = session_prep.halaman_persiapan(kon, siswa, peran="guru").decode()
    assert "Mulai di HP anak" in html and "memindai" in html
    assert "cadangan" in html and "Cetak" in html
    assert "tab Perkembangan" not in html
