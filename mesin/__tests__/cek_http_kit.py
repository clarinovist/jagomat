"""Pembantu bersama tes HTTP cek gratis (Fase 2b): server nyata, data sintetis di tmp_path."""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import cek_http  # noqa: E402
import database  # noqa: E402
import learning_profile  # noqa: E402
import sessions  # noqa: E402
from cek_gratis_kit import jawab, tandai_selesai  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji, _basic  # noqa: E402

MULAI = "/cek-kemampuan/mulai"
HASIL = "/cek-kemampuan/hasil"
TAUTAN = "/cek-kemampuan/tautan"
SANDI_GURU_B = "sandi-guru-b-panjang-123"
SANDI_ADMIN = "sandi-pengelola-cek-123"
AKUN_A = ("guru", SANDI_GURU)
AKUN_B = ("guru-b", SANDI_GURU_B)
AKUN_ADMIN = ("pengelola-cek", SANDI_ADMIN)
AKUN_MURID = ("feby", SANDI_MURID)
NAMA_A = "Anak Sintetis Alfa"
NAMA_B = "Anak Sintetis Beta"
POLA_TOKEN = re.compile(r'name="token" value="([^"]+)"')


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    """Pertahankan 303 sebagai 303; status asli POST sukses."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def minta_mentah(server, jalur, akun=None, data=None, headers=None):
    """Satu permintaan tanpa mengikuti pengalihan -> (kode, isi, header); HTTPError ditutup."""
    isi = None if data is None else urllib.parse.urlencode(data, doseq=True).encode()
    req = urllib.request.Request(server.alamat + jalur, data=isi, method=None if isi is None else "POST")
    if isi is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if akun:
        req.add_header("Authorization", _basic(*akun))
    for nama, nilai in (headers or {}).items():
        req.add_header(nama, nilai)
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
        finally:
            e.close()


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)
    monkeypatch.setattr(cek_http, "_riwayat", {})
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        auth.tambah_akun("guru-b", SANDI_GURU_B, "guru")
        auth.tambah_akun("pengelola-cek", SANDI_ADMIN, "admin")
        yield uji
    finally:
        uji.berhenti()


def tambah_anak(server, nama, pemilik, kelas):
    with server.buka() as kon:
        siswa = database.tambah_siswa(kon, nama, "P3", pemilik=pemilik)
        if kelas is not None:
            learning_profile.simpan_kelas(kon, siswa, kelas, revisi=0, pemilik=pemilik)
    return siswa


@pytest.fixture()
def keluarga(server):
    """Anak sintetis: A kelas 4 (milik guru), B kelas 5 (milik guru-b)."""
    server.anak_a = tambah_anak(server, NAMA_A, "guru", 4)
    server.anak_b = tambah_anak(server, NAMA_B, "guru-b", 5)
    return server


def id_akun(akun) -> str:
    principal = sessions.principal_basic(*akun)
    assert principal is not None
    return principal.id_akun


def jumlah(server, tabel) -> int:
    with server.buka() as kon:
        return kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]


def keadaan(server) -> tuple:
    return tuple(jumlah(server, t) for t in ("cek_gratis", "sesi", "sesi_soal", "tautan_sesi"))


def ambil_token(server, akun, jalur=MULAI) -> str:
    kode, isi, _t = minta_mentah(server, jalur, akun)
    assert kode == 200, (jalur, kode)
    cocok = POLA_TOKEN.search(isi)
    assert cocok, "halaman tidak membawa token"
    return cocok.group(1)


def token_form(akun, aksi) -> str:
    """Token sah langsung dari modul (untuk akun yang halamannya tidak lagi menampilkan form)."""
    principal = sessions.principal_basic(*akun)
    assert principal is not None
    return cek_http.buat_token(principal, None, aksi)


def kirim_mulai(server, akun, *, setuju="1", token=None, ekstra=None):
    data = {"token": token_form(akun, cek_http.AKSI_MULAI) if token is None else token}
    if setuju is not None:
        data["setuju"] = setuju
    data.update(ekstra or {})
    return minta_mentah(server, MULAI, akun, data)


def mulai_cek(server, akun=AKUN_A):
    kode, _i, _t = kirim_mulai(server, akun)
    assert kode == 303
    with server.buka() as kon:
        return kon.execute(
            "SELECT sesi_id FROM cek_gratis WHERE id_akun = ?", (id_akun(akun),)
        ).fetchone()[0]


def selesaikan(server, sesi_id, **jawaban):
    """Jawab PG sintetis lalu tutup sesi lewat jalur database yang ada."""
    with server.buka() as kon:
        jawab(kon, sesi_id, **jawaban)
        tandai_selesai(kon, sesi_id)


def teks_tampak(isi: str) -> str:
    """Teks yang terlihat: badan tanpa <style>/<script> dan tanpa tag (atribut ikut hilang)."""
    badan = isi.split("</style>", 1)[1]
    badan = re.sub(r"<script.*?</script>", " ", badan, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", badan))
