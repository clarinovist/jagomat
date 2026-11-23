"""Pembantu bersama tes cek di sesi anak (F2b): server nyata, anak hasil /daftar mode anak, data sintetis."""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_registration as reg  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import lembaga_store  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402

KOORDINATOR = "koordinator-jagomat"
WA = "0812-3456-7890"
SANDI_ANAK = "sandi-anak-sintetis"
KELUARGA_VISUAL = "statistika,geometri-datar,pola-bilangan"
JUMLAH_SOAL = 15
KATA_TERLARANG_KARTU = ("kunci", "malrule", "diagnos", "skor", "kategori", "benar", "salah", "persentil", "peringkat")
POLA_REVISI = re.compile(r'name="revisi_pekerjaan" value="([0-9]+)"')


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def kirim(server, jalur, data=None, cookie=None, metode=None):
    """Satu permintaan tanpa mengikuti pengalihan -> (kode, isi, header). `data` dict = POST form."""
    isi = None if data is None else urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(server.alamat + jalur, data=isi, method=metode or (None if isi is None else "POST"))
    if isi is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as galat:
        try:
            return galat.code, galat.read().decode("utf-8", "replace"), dict(galat.headers)
        finally:
            galat.close()


def kuki(header) -> str:
    return header["Set-Cookie"].split(";")[0]


@pytest.fixture()
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", KELUARGA_VISUAL)
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)
    monkeypatch.delenv("DAFTAR_AKUN_ANAK", raising=False)
    monkeypatch.delenv("OSN_LEMBAGA_ANTREAN", raising=False)
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    auth.tambah_akun("admin-sintetis", "sandi-admin-sintetis", "admin")
    auth.tambah_akun(KOORDINATOR, "sandi-koordinator-sintetis", "guru")
    reg.migrasikan_profil_registrasi(database.BAWAAN)
    with uji.buka() as kon:
        uji.lembaga_id = lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik=KOORDINATOR)
    try:
        yield uji
    finally:
        uji.berhenti()


@pytest.fixture()
def gerbang_hidup(server, monkeypatch):
    """Sakelar anak + funnel hidup, lembaga antrean siap (syarat kartu dan rute F2b)."""
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", str(server.lembaga_id))
    monkeypatch.setenv("FUNNEL_AKTIF", "1")


class Anak:
    """Anak hasil pendaftaran mode anak (akun murid + siswa milik koordinator + persetujuan) yang sedang masuk."""

    def __init__(self, server, nama_login: str, kelas: str = "4"):
        self.server = server
        self.nama_login = nama_login
        _, isi, _ = server.minta("/daftar")
        token = re.search(r'name="token_form" value="([^"]+)"', isi).group(1)
        kode, _, header = kirim(server, "/daftar", dict(
            nama=nama_login, sandi=SANDI_ANAK, nama_lengkap="Anak Sintetis " + nama_login, kelas_sekolah=kelas,
            wa=WA, setuju="1", pin="", pin_ulang="", token_form=token))
        assert kode == 303, isi
        self.cookie = kuki(header)
        entri = auth.cari_akun(nama_login)
        self.id_akun, self.siswa_id = entri["id_akun"], entri["siswa_id"]

    def get(self, jalur):
        return kirim(self.server, jalur, cookie=self.cookie)

    def post(self, jalur="/murid/cek/mulai", data=None):
        return kirim(self.server, jalur, {} if data is None else data, cookie=self.cookie)

    def baris_cek(self):
        with self.server.buka() as kon:
            return kon.execute("SELECT * FROM cek_gratis WHERE siswa_id = ?", (self.siswa_id,)).fetchone()

    def token_dari(self, lokasi: str) -> str:
        return lokasi.split("?")[0].rsplit("/", 1)[1]


def jumlah_baris(server, *tabel) -> dict:
    with server.buka() as kon:
        return {t: kon.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in tabel}


TABEL_CEK = ("cek_gratis", "sesi", "sesi_soal", "tautan_sesi")


def murid_guru(server, nama_login: str, kelas: int = 4):
    """Akun murid buatan guru (tanpa persetujuan_daftar_anak): anak milik 'guru', cookie sesi."""
    from cek_gratis_kit import tambah_anak
    with server.buka() as kon:
        siswa_id = tambah_anak(kon, "Anak Guru " + nama_login, "guru", kelas)
    auth.tambah_akun(nama_login, SANDI_ANAK, "murid", siswa_id=siswa_id)
    _, _, header = kirim(server, "/masuk", dict(nama=nama_login, sandi=SANDI_ANAK))
    return kuki(header), siswa_id, auth.cari_akun(nama_login)["id_akun"]
