"""Retensi kontak WhatsApp per akun (K4): throttle aktivitas, sapuan, login fail-open.

Semua data sintetis di tmp_path. Nomor uji adalah nomor rekaan, bukan milik siapa pun.
"""
from __future__ import annotations

import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import kontak_akun  # noqa: E402
import laju_masuk  # noqa: E402
import sessions  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402

FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
SEKARANG = datetime(2026, 11, 17, 10, 0, 0)
ID_A = "akun_" + "a1" * 16
ID_B = "akun_" + "b2" * 16
ID_C = "akun_" + "c3" * 16
ID_D = "akun_" + "d4" * 16
WA = "6281234567890"
WA_LAIN = "6285551234567"


def _waktu(selisih: timedelta = timedelta(0)) -> str:
    return (SEKARANG - selisih).strftime(FORMAT_WAKTU)


def _ada(kon, id_akun) -> bool:
    return kontak_akun.ambil(kon, id_akun) is not None


def _semua_id(kon) -> set:
    return {r[0] for r in kon.execute("SELECT id_akun FROM kontak_akun")}


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "retensi.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


# --- sentuh_aktivitas -----------------------------------------------------

def test_retensi_dua_belas_bulan_adalah_365_hari():
    assert kontak_akun.RETENSI_HARI == 365


def test_sentuh_hari_berikutnya_menulis_aktivitas(kon):
    kontak_akun.simpan(kon, ID_A, WA, "2026-11-16T08:00:00")

    assert kontak_akun.sentuh_aktivitas(kon, ID_A, "2026-11-17T09:00:00") is True

    baris = kontak_akun.ambil(kon, ID_A)
    assert baris["aktivitas_terakhir"] == "2026-11-17T09:00:00"
    assert baris["diperbarui"] == "2026-11-16T08:00:00"
    assert baris["dibuat"] == "2026-11-16T08:00:00"
    assert baris["wa"] == WA


def test_sentuh_dua_kali_di_hari_sama_hanya_satu_tulis(kon):
    kontak_akun.simpan(kon, ID_A, WA, "2026-11-16T08:00:00")

    pertama = kontak_akun.sentuh_aktivitas(kon, ID_A, "2026-11-17T09:00:00")
    kedua = kontak_akun.sentuh_aktivitas(kon, ID_A, "2026-11-17T23:59:00")

    assert (pertama, kedua) == (True, False)
    assert kontak_akun.ambil(kon, ID_A)["aktivitas_terakhir"] == "2026-11-17T09:00:00"


def test_sentuh_pada_hari_yang_sama_dengan_simpan_tidak_menulis(kon):
    kontak_akun.simpan(kon, ID_A, WA, "2026-11-17T01:00:00")

    assert kontak_akun.sentuh_aktivitas(kon, ID_A, "2026-11-17T22:00:00") is False
    assert kontak_akun.ambil(kon, ID_A)["aktivitas_terakhir"] == "2026-11-17T01:00:00"


def test_sentuh_hari_berikutnya_setelah_hari_sama_menulis_lagi(kon):
    kontak_akun.simpan(kon, ID_A, WA, "2026-11-16T08:00:00")
    kontak_akun.sentuh_aktivitas(kon, ID_A, "2026-11-17T09:00:00")

    assert kontak_akun.sentuh_aktivitas(kon, ID_A, "2026-11-18T00:00:01") is True
    assert kontak_akun.ambil(kon, ID_A)["aktivitas_terakhir"] == "2026-11-18T00:00:01"


def test_sentuh_tidak_membuat_baris_baru(kon):
    assert kontak_akun.sentuh_aktivitas(kon, ID_A, _waktu()) is False

    assert _semua_id(kon) == set()


def test_sentuh_hanya_akun_target(kon):
    kontak_akun.simpan(kon, ID_A, WA, "2026-11-16T08:00:00")
    kontak_akun.simpan(kon, ID_B, WA_LAIN, "2026-11-16T08:00:00")

    kontak_akun.sentuh_aktivitas(kon, ID_A, "2026-11-17T09:00:00")

    assert kontak_akun.ambil(kon, ID_B)["aktivitas_terakhir"] == "2026-11-16T08:00:00"


def test_sentuh_tidak_commit_sendiri(tmp_path):
    jalur = tmp_path / "sentuh.db"
    database.siapkan(jalur)
    with database.buka(jalur) as awal:
        kontak_akun.simpan(awal, ID_A, WA, "2026-11-16T08:00:00")
    kon = sqlite3.connect(str(jalur))
    try:
        kon.execute("BEGIN")
        assert kontak_akun.sentuh_aktivitas(kon, ID_A, "2026-11-17T09:00:00") is True
        kon.rollback()
        assert kontak_akun.ambil(kon, ID_A)["aktivitas_terakhir"] == "2026-11-16T08:00:00"
    finally:
        kon.close()


@pytest.mark.parametrize("id_buruk", ["guru", "", None, "akun_xyz"])
def test_sentuh_menolak_id_akun_tidak_sah(kon, id_buruk):
    with pytest.raises(ValueError):
        kontak_akun.sentuh_aktivitas(kon, id_buruk, _waktu())


@pytest.mark.parametrize("waktu_buruk", ["kemarin", "", None, 12345])
def test_sentuh_menolak_waktu_tidak_sah(kon, waktu_buruk):
    kontak_akun.simpan(kon, ID_A, WA, "2026-11-16T08:00:00")
    with pytest.raises(ValueError):
        kontak_akun.sentuh_aktivitas(kon, ID_A, waktu_buruk)


# --- sapu_kontak: kedaluwarsa --------------------------------------------

def _isi(kon, id_akun, selisih: timedelta, wa: str = WA) -> None:
    kontak_akun.simpan(kon, id_akun, wa, _waktu(selisih))


def test_sapu_batas_tepat_365_hari_disimpan_dan_lebih_tua_dihapus(kon):
    _isi(kon, ID_A, timedelta(days=365))
    _isi(kon, ID_B, timedelta(days=365, seconds=1))
    _isi(kon, ID_C, timedelta(days=366))
    _isi(kon, ID_D, timedelta(days=364))

    hasil = kontak_akun.sapu_kontak(kon, {ID_A, ID_B, ID_C, ID_D}, _waktu())

    assert _semua_id(kon) == {ID_A, ID_D}
    assert hasil == {"kedaluwarsa": 2, "yatim": 0}


def test_sapu_tidak_menghapus_kontak_segar_milik_akun_hidup(kon):
    _isi(kon, ID_A, timedelta(days=1))

    hasil = kontak_akun.sapu_kontak(kon, {ID_A}, _waktu())

    assert _semua_id(kon) == {ID_A}
    assert hasil == {"kedaluwarsa": 0, "yatim": 0}


# --- sapu_kontak: yatim ---------------------------------------------------

def test_sapu_menghapus_yatim_dan_menyisakan_akun_hidup(kon):
    _isi(kon, ID_A, timedelta(days=1))
    _isi(kon, ID_B, timedelta(days=1), WA_LAIN)

    hasil = kontak_akun.sapu_kontak(kon, {ID_A}, _waktu())

    assert _semua_id(kon) == {ID_A}
    assert hasil == {"kedaluwarsa": 0, "yatim": 1}


def test_sapu_baris_kedaluwarsa_sekaligus_yatim_dihitung_sekali(kon):
    _isi(kon, ID_A, timedelta(days=1))
    _isi(kon, ID_B, timedelta(days=400), WA_LAIN)

    hasil = kontak_akun.sapu_kontak(kon, {ID_A}, _waktu())

    assert _semua_id(kon) == {ID_A}
    assert hasil["kedaluwarsa"] + hasil["yatim"] == 1


def test_sapu_nama_login_dipakai_ulang_tidak_mewarisi_kontak(kon):
    """Kunci id_akun: akun baru bernama sama punya id berbeda, kontak lama yatim."""
    _isi(kon, ID_A, timedelta(days=1))

    hasil = kontak_akun.sapu_kontak(kon, {ID_B}, _waktu())

    assert _semua_id(kon) == set()
    assert hasil["yatim"] == 1


def test_sapu_menerima_frozenset_dan_tabel_kosong(kon):
    assert kontak_akun.sapu_kontak(kon, frozenset({ID_A}), _waktu()) == {
        "kedaluwarsa": 0, "yatim": 0,
    }


def test_sapu_hasil_hanya_agregat_tanpa_nomor_atau_id(kon):
    _isi(kon, ID_A, timedelta(days=400))
    _isi(kon, ID_B, timedelta(days=1), WA_LAIN)

    hasil = kontak_akun.sapu_kontak(kon, {ID_C}, _waktu())

    assert set(hasil) == {"kedaluwarsa", "yatim"}
    assert all(type(nilai) is int for nilai in hasil.values())
    teks = repr(hasil)
    assert WA not in teks and WA_LAIN not in teks and ID_A not in teks and ID_B not in teks


def test_sapu_tidak_memutasi_himpunan_argumen(kon):
    _isi(kon, ID_A, timedelta(days=1))
    hidup = {ID_A, ID_B}

    kontak_akun.sapu_kontak(kon, hidup, _waktu())

    assert hidup == {ID_A, ID_B}


# --- sapu_kontak: guard himpunan akun hidup ------------------------------

@pytest.mark.parametrize(
    "hidup",
    [
        set(),
        frozenset(),
        None,
        [ID_A],
        (ID_A,),
        {ID_A: 1},
        "akun",
        {ID_A, "bukan-id-akun"},
        {ID_A, None},
        {ID_A, 123},
    ],
    ids=["set-kosong", "frozenset-kosong", "none", "list", "tuple", "dict", "str",
         "id-tidak-sah", "elemen-none", "elemen-int"],
)
def test_sapu_menolak_himpunan_tidak_sah_dan_tidak_menghapus_apa_pun(kon, hidup):
    _isi(kon, ID_A, timedelta(days=1))
    _isi(kon, ID_B, timedelta(days=500), WA_LAIN)
    kon.commit()

    with pytest.raises(ValueError):
        kontak_akun.sapu_kontak(kon, hidup, _waktu())

    assert _semua_id(kon) == {ID_A, ID_B}


@pytest.mark.parametrize("waktu_buruk", ["kemarin", "", None, 12345])
def test_sapu_menolak_waktu_tidak_sah_tanpa_menghapus(kon, waktu_buruk):
    _isi(kon, ID_A, timedelta(days=500))
    kon.commit()

    with pytest.raises(ValueError):
        kontak_akun.sapu_kontak(kon, {ID_B}, waktu_buruk)

    assert _semua_id(kon) == {ID_A}


# --- sapu_kontak: atomik --------------------------------------------------

def _pasang_gagal_hapus(kon, id_akun: str) -> None:
    kon.execute(
        "CREATE TRIGGER gagal_hapus BEFORE DELETE ON kontak_akun "
        "WHEN OLD.id_akun = '%s' BEGIN SELECT RAISE(ABORT, 'gagal sengaja'); END" % id_akun
    )
    kon.commit()


def test_sapu_gagal_pada_penghapusan_yatim_membatalkan_penghapusan_kedaluwarsa(kon):
    _isi(kon, ID_A, timedelta(days=1))                 # hidup, segar: aman
    _isi(kon, ID_B, timedelta(days=500), WA_LAIN)      # kedaluwarsa
    _isi(kon, ID_C, timedelta(days=1))                 # yatim, memicu kegagalan
    kon.commit()
    _pasang_gagal_hapus(kon, ID_C)

    with pytest.raises(sqlite3.Error):
        kontak_akun.sapu_kontak(kon, {ID_A, ID_B}, _waktu())

    assert _semua_id(kon) == {ID_A, ID_B, ID_C}


def test_sapu_gagal_pada_penghapusan_kedaluwarsa_membatalkan_penghapusan_yatim(kon):
    _isi(kon, ID_A, timedelta(days=1))                 # hidup, segar: aman
    _isi(kon, ID_B, timedelta(days=500), WA_LAIN)      # kedaluwarsa, memicu kegagalan
    _isi(kon, ID_C, timedelta(days=1))                 # yatim
    kon.commit()
    _pasang_gagal_hapus(kon, ID_B)

    with pytest.raises(sqlite3.Error):
        kontak_akun.sapu_kontak(kon, {ID_A, ID_B}, _waktu())

    assert _semua_id(kon) == {ID_A, ID_B, ID_C}


def test_sapu_berhasil_bisa_dibatalkan_pemanggil_dalam_transaksinya(tmp_path):
    jalur = tmp_path / "sapu.db"
    database.siapkan(jalur)
    with database.buka(jalur) as awal:
        _isi(awal, ID_A, timedelta(days=1))
    kon = sqlite3.connect(str(jalur))
    try:
        kon.execute("BEGIN")
        kontak_akun.sapu_kontak(kon, {ID_B}, _waktu())
        kon.rollback()
        assert _semua_id(kon) == {ID_A}
    finally:
        kon.close()


# --- login: tulis aktivitas, fail-open ------------------------------------

LAMA = "2026-01-01T00:00:00"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    laju_masuk._reset()
    s = ServerUji(tmp_path, monkeypatch)
    try:
        yield s
    finally:
        s.berhenti()


def _id_guru() -> str:
    return auth.cari_akun("guru", path=auth.BERKAS_SANDI)["id_akun"]


def _aktivitas(server, id_akun):
    with server.buka() as kon:
        baris = kontak_akun.ambil(kon, id_akun)
    return None if baris is None else baris["aktivitas_terakhir"]


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _login(server, nama="guru", sandi=SANDI_GURU):
    """POST /masuk tanpa mengikuti redirect -> (kode, header)."""
    req = urllib.request.Request(
        server.alamat + "/masuk",
        data=urllib.parse.urlencode({"nama": nama, "sandi": sandi}).encode(),
        method="POST",
    )
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)


def _beri_kontak(server, id_akun, waktu=LAMA) -> None:
    with server.buka() as kon:
        kontak_akun.simpan(kon, id_akun, WA, waktu)


def test_login_berhasil_menulis_aktivitas_bila_ada_baris_kontak(server):
    id_guru = _id_guru()
    _beri_kontak(server, id_guru)

    kode, header = _login(server)

    assert kode == 303
    assert "osn_sesi=" in header.get("Set-Cookie", "")
    baru = _aktivitas(server, id_guru)
    assert baru is not None and baru > LAMA
    assert datetime.fromisoformat(baru).year >= 2026


def test_login_berhasil_tidak_membuat_baris_bila_tidak_ada_kontak(server):
    id_guru = _id_guru()

    _login(server)

    assert _aktivitas(server, id_guru) is None
    with server.buka() as kon:
        assert _semua_id(kon) == set()


def test_login_hanya_menulis_baris_milik_akun_yang_masuk(server):
    id_guru = _id_guru()
    id_murid = auth.cari_akun("feby", path=auth.BERKAS_SANDI)["id_akun"]
    _beri_kontak(server, id_murid)
    _beri_kontak(server, id_guru)

    _login(server)

    assert _aktivitas(server, id_murid) == LAMA
    assert _aktivitas(server, id_guru) > LAMA


def test_login_gagal_tidak_menulis_aktivitas(server):
    id_guru = _id_guru()
    _beri_kontak(server, id_guru)

    _login(server, sandi="sandi-salah-sama-sekali")

    assert _aktivitas(server, id_guru) == LAMA


def test_login_dua_kali_sehari_hanya_satu_tulis(server):
    id_guru = _id_guru()
    _beri_kontak(server, id_guru)

    _login(server)
    pertama = _aktivitas(server, id_guru)
    time.sleep(1.1)
    _login(server)

    assert _aktivitas(server, id_guru) == pertama


def test_login_tetap_berhasil_saat_penulisan_raise(server, monkeypatch):
    id_guru = _id_guru()
    _beri_kontak(server, id_guru)

    def meledak(*_args, **_kwargs):
        raise RuntimeError("gagal sengaja")

    monkeypatch.setattr(kontak_akun, "sentuh_aktivitas", meledak)

    _kode, header = _login(server)

    assert "osn_sesi=" in header.get("Set-Cookie", "")
    assert header.get("Location") == "/guru"
    assert _aktivitas(server, id_guru) == LAMA


def test_login_tetap_berhasil_saat_database_error(server, monkeypatch):
    id_guru = _id_guru()
    _beri_kontak(server, id_guru)

    def error_db(*_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(kontak_akun, "sentuh_aktivitas", error_db)

    _kode, header = _login(server)

    assert "osn_sesi=" in header.get("Set-Cookie", "")
    assert _aktivitas(server, id_guru) == LAMA


def test_login_tetap_berhasil_dan_cepat_saat_database_terkunci(server):
    id_guru = _id_guru()
    _beri_kontak(server, id_guru)
    pengunci = sqlite3.connect(str(server.db), isolation_level=None)
    try:
        pengunci.execute("BEGIN EXCLUSIVE")
        mulai = time.monotonic()
        _kode, header = _login(server)
        lama = time.monotonic() - mulai
    finally:
        pengunci.execute("ROLLBACK")
        pengunci.close()

    assert "osn_sesi=" in header.get("Set-Cookie", "")
    assert header.get("Location") == "/guru"
    assert lama < 3.0
    assert _aktivitas(server, id_guru) == LAMA


def test_login_tetap_berhasil_saat_berkas_database_tidak_ada(server, tmp_path, monkeypatch):
    monkeypatch.setattr(database, "BAWAAN", tmp_path / "tidak-ada.db")

    _kode, header = _login(server)

    assert "osn_sesi=" in header.get("Set-Cookie", "")
    assert not (tmp_path / "tidak-ada.db").exists()


def test_login_murid_juga_tidak_gagal_tanpa_kontak(server):
    _kode, header = _login(server, nama="feby", sandi=SANDI_MURID)

    assert header.get("Location") == "/murid"


def test_autentikasi_tetap_tanpa_tulis(server):
    id_guru = _id_guru()
    _beri_kontak(server, id_guru)

    principal = auth.autentikasi("guru", SANDI_GURU, auth.BERKAS_SANDI)

    assert principal is not None
    assert _aktivitas(server, id_guru) == LAMA


def test_log_kegagalan_tidak_memuat_nomor_atau_id_akun_lengkap(server, monkeypatch, caplog):
    id_guru = _id_guru()
    _beri_kontak(server, id_guru)

    def meledak(*_args, **_kwargs):
        raise sqlite3.OperationalError("gagal untuk %s dan %s" % (WA, id_guru))

    monkeypatch.setattr(kontak_akun, "sentuh_aktivitas", meledak)

    with caplog.at_level("DEBUG"):
        _login(server)

    log = caplog.text
    assert WA not in log and id_guru not in log
