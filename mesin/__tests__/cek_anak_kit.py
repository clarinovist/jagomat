"""Pembantu bersama tes permukaan anak cek gratis: server nyata, data sintetis di tmp_path.

Sengaja tidak mengimpor ``cek_http_kit`` (yang bergantung pada sisi orang tua);
hanya modul anak, ``cek_gratis`` (membuat sesi cek) dan ``share_links`` (token).
"""
from __future__ import annotations

import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import share_links  # noqa: E402
import student_submissions as kiriman  # noqa: E402
from cek_gratis_kit import ID_A, mulai_cek, tambah_anak  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402

JUMLAH = 15
KELUARGA_VISUAL = "statistika,geometri-datar,pola-bilangan"
KOLOM_TERLARANG = {"kunci", "kode_final", "kode_usulan", "malrule_id", "alasan"}


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    """Pertahankan 303 sebagai 303."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def minta(server, jalur, data=None):
    """Satu permintaan tanpa mengikuti pengalihan -> (kode, isi, header)."""
    if data is None or isinstance(data, bytes):
        isi = data
    else:
        isi = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(server.alamat + jalur, data=isi, method=None if isi is None else "POST")
    if isi is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
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
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", KELUARGA_VISUAL)
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        yield uji
    finally:
        uji.berhenti()


class Cek:
    """Satu anak sintetis dengan sesi cek 15 soal dan token tautan aktif."""

    def __init__(self, server, nama="Anak Sintetis", kelas=4, akun=ID_A):
        self.server = server
        with server.buka() as kon:
            self.siswa_id = tambah_anak(kon, nama, "guru", kelas)
            self.sesi_id = mulai_cek(kon, akun, self.siswa_id, "guru", seed=11)
            self.token = share_links.buat(kon, self.sesi_id)

    def jalur(self, **param):
        return "/mulai/" + self.token + ("?" + urllib.parse.urlencode(param) if param else "")

    def get(self, **param):
        return minta(self.server, self.jalur(**param))

    def post(self, data, di=False):
        return minta(self.server, self.jalur(di="hp-ini") if di else self.jalur(), data)

    def revisi(self):
        with self.server.buka() as kon:
            return kiriman.revisi(kon, self.sesi_id)

    def simpan(self, nomor, opsi="opsi_1", di=False, **extra):
        data = {"aksi": "simpan", "soal": str(nomor), "revisi_pekerjaan": str(self.revisi())}
        if opsi is not None:
            data[f"opsi_{self.id_butir(nomor)}"] = opsi
        data.update(extra)
        return self.post(data, di=di)

    def kumpul(self, di=False, **extra):
        data = {"aksi": "kumpul", "revisi_pekerjaan": str(self.revisi())}
        data.update(extra)
        return self.post(data, di=di)

    def id_butir(self, nomor):
        with self.server.buka() as kon:
            return kon.execute(
                "SELECT id FROM sesi_soal WHERE sesi_id = ? AND nomor = ?", (self.sesi_id, nomor)
            ).fetchone()[0]

    def jawaban(self):
        """Isi tabel jawaban terurut; dipakai membuktikan tidak ada efek samping."""
        with self.server.buka() as kon:
            return [tuple(b) for b in kon.execute(
                """SELECT ss.nomor, j.jawaban, j.cara, j.restatement, j.belum_pernah
                   FROM jawaban j JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
                   WHERE ss.sesi_id = ? ORDER BY ss.nomor""", (self.sesi_id,))]

    def terjawab(self):
        return sum(1 for b in self.jawaban() if b[1])

    def status_sesi(self):
        with self.server.buka() as kon:
            return tuple(kon.execute(
                "SELECT mulai, selesai FROM sesi WHERE id = ?", (self.sesi_id,)).fetchone())


def lokasi(tajuk) -> str:
    return tajuk.get("Location", "")


class PenanganPalsu:
    """Penangan minimal untuk memanggil rute anak langsung di koneksi bergerbang."""

    def __init__(self, path):
        self.path = path
        self.kode = None
        self.isi = b""
        self.tajuk = {}

    def _kirim_tautan(self, isi, kode=200, csp=None):
        self.kode, self.isi = kode, isi

    def send_response(self, kode):
        self.kode = kode

    def send_header(self, nama, nilai):
        self.tajuk[nama] = nilai

    def end_headers(self):
        pass


def pasang_gerbang_kunci(kon) -> None:
    """Tolak semua pembacaan kolom kunci/diagnosis (cara `db_terjaga` lain)."""
    def jaga(aksi, tabel, kolom, _db, _pemicu):
        if aksi == sqlite3.SQLITE_READ and kolom in KOLOM_TERLARANG:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    kon.set_authorizer(jaga)


def lepas_gerbang(kon) -> None:
    kon.set_authorizer(lambda *args: sqlite3.SQLITE_OK)


def buang_soal_dan_gaya(html_isi: str) -> str:
    """HTML tanpa <style>, kartu soal, dan opsi (teks soal dari generator boleh memuat kata apa pun)."""
    sisa = re.sub(r"<style>.*?</style>", "", html_isi, flags=re.S)
    sisa = re.sub(r'<div class="kertas">.*?</div>\s*(?=<fieldset|<div class="alat-kecil")', "", sisa, flags=re.S)
    return re.sub(r"<fieldset class=\"opsi.*?</fieldset>", "", sisa, flags=re.S)


def daftar_sesi_biasa(server):
    """Sesi non-cek (3 soal PG) dengan token, untuk membuktikan jalur lama tak berubah."""
    with server.buka() as kon:
        siswa = database.tambah_siswa(kon, "Anak Biasa", pemilik="guru")
        sesi = database.buat_sesi(kon, siswa, seed=7, jumlah_soal=3)
        token = share_links.buat(kon, sesi)
    return siswa, sesi, token


POLA_REVISI = re.compile(r'name="revisi_pekerjaan" value="([0-9]+)"')
