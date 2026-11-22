"""Mode Lomba di /akun?section=siswa: tombol Aktifkan/Matikan per anak, kepemilikan, tanpa efek samping.

Data sintetis di tmp_path. Aksi hanya mengubah `aktif`; target harian dan hitung mundur dari halaman Lomba tetap.
"""
import base64
import http.client
import sys
import time
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import contest_account  # noqa: E402
import contest_assignment_store as AS  # noqa: E402
import database  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402

GURU = ("guru", SANDI_GURU)
GURU_LAIN = ("guru-lain", "sandi-guru-lain-123")
ADMIN = ("admin-uji", "sandi-admin-uji-123")


@pytest.fixture()
def s(tmp_path, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    server = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("guru-lain", GURU_LAIN[1], "guru", path=auth.BERKAS_SANDI)
    auth.tambah_akun("admin-uji", ADMIN[1], "admin", path=auth.BERKAS_SANDI)
    with server.buka() as kon:
        server.anak = database.tambah_siswa(kon, "Anak <b>Sintetis</b>", pemilik="guru")
        server.asing = database.tambah_siswa(kon, "Anak Guru Lain", pemilik="guru-lain")
    yield server
    server.berhenti()


def _minta(s, jalur, data=None, kredensial=GURU):
    kepala = {"Authorization": "Basic " + base64.b64encode(":".join(kredensial).encode()).decode()}
    tubuh = None
    if data is not None:
        tubuh = urllib.parse.urlencode(data)
        kepala["Content-Type"] = "application/x-www-form-urlencoded"
        kepala["Origin"] = s.alamat
    k = http.client.HTTPConnection(s.alamat.split("//")[1], timeout=10)
    k.request("POST" if tubuh is not None else "GET", jalur, body=tubuh, headers=kepala)
    r = k.getresponse()
    isi = r.read().decode("utf-8", "replace")
    k.close()
    return r.status, isi


def _aksi(siswa_id, aktif="1", **tambahan):
    return {"aksi": "mode_lomba", "siswa_id": str(siswa_id), "aktif": aktif, "section": "siswa", **tambahan}


def _penugasan(s, siswa_id):
    with s.buka() as kon:
        return AS.ambil(kon, siswa_id)


def _tunggu_penugasan(s, siswa_id, aktif, batas_detik=3.0):
    """`account_http` mengirim halaman sebelum commit di akhir `with`; tunggu commit selesai (bukan sleep buta)."""
    akhir = time.monotonic() + batas_detik
    while True:
        p = _penugasan(s, siswa_id)
        if (p is not None and p.aktif is aktif) or time.monotonic() > akhir:
            return p
        time.sleep(0.02)


def test_kartu_anak_menampilkan_status_dan_tombol_aktifkan(s):
    kode, isi = _minta(s, "/akun?section=siswa")

    assert kode == 200
    assert "Mode Lomba: Belum aktif" in isi and ">Aktifkan</button>" in isi
    assert f'href="/anak/{s.anak}/lomba"' in isi and "Anak &lt;b&gt;Sintetis&lt;/b&gt;" in isi


def test_kartu_kosong_saat_sakelar_induk_mati(s, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "0")

    kode, isi = _minta(s, "/akun?section=siswa")

    assert kode == 200 and "Mode Lomba" not in isi and 'value="mode_lomba"' not in isi


def test_guru_mengaktifkan_lalu_mematikan_anaknya_dan_target_dipertahankan(s):
    with s.buka() as kon:
        AS.atur(kon, s.anak, aktif=False, target_harian=1, tampil_hitung_mundur=False, sekarang=1, oleh="guru")

    kode, isi = _minta(s, "/akun", _aksi(s.anak, "1"))
    aktif = _tunggu_penugasan(s, s.anak, True)

    assert kode == 200 and "Mode Lomba untuk Anak &lt;b&gt;Sintetis&lt;/b&gt; diaktifkan." in isi
    assert aktif.aktif is True and aktif.target_harian == 1 and aktif.tampil_hitung_mundur is False
    assert aktif.diubah_oleh == "guru" and "Mode Lomba: Aktif" in isi and ">Matikan</button>" in isi

    _minta(s, "/akun", _aksi(s.anak, "0"))
    mati = _tunggu_penugasan(s, s.anak, False)

    assert mati.aktif is False and mati.target_harian == 1 and mati.tampil_hitung_mundur is False


def test_anak_tanpa_pengaturan_lama_memakai_nilai_paket(s):
    _minta(s, "/akun", _aksi(s.anak, "1"))

    p = _tunggu_penugasan(s, s.anak, True)

    assert p.aktif is True and p.target_harian is None and p.tampil_hitung_mundur is None


@pytest.mark.parametrize("siswa", ["asing", "tidak_ada", "bukan_angka"])
def test_bukan_milik_atau_tidak_ada_ditolak_tanpa_tulis(s, siswa):
    siswa_id = {"asing": s.asing, "tidak_ada": 999999, "bukan_angka": "abc"}[siswa]

    kode, isi = _minta(s, "/akun", _aksi(siswa_id, "1"))

    assert kode == 200 and "Siswa tidak dikenal." in isi
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM lomba_penugasan").fetchone()[0] == 0


def test_admin_boleh_mengatur_anak_keluarga_mana_pun(s):
    with s.buka() as kon:
        assert contest_account.proses(kon, _aksi(s.asing, "1"), "admin-uji", "admin")[1] == ""
        assert AS.ambil(kon, s.asing).aktif is True


@pytest.mark.parametrize("data", [
    {"aktif": "2"}, {"aktif": ""}, {"aktif": "1", "target": "3"},
])
def test_isian_tidak_sah_ditolak_tanpa_tulis(s, data):
    form = {"aksi": "mode_lomba", "siswa_id": str(s.anak), "section": "siswa", **data}

    kode, isi = _minta(s, "/akun", form)

    assert kode == 200 and "Form Mode Lomba tidak sah." in isi
    assert _penugasan(s, s.anak) is None


def test_sakelar_induk_mati_menolak_tanpa_tulis(s, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "0")

    kode, isi = _minta(s, "/akun", _aksi(s.anak, "1"))

    assert kode == 200 and "Mode Lomba sedang dimatikan admin." in isi
    assert _penugasan(s, s.anak) is None
