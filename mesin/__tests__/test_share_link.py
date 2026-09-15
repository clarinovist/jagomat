"""Tautan berbagi: akses satu sesi tanpa login, tetap dipagari ketat."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import share_links  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Tautan", pemilik="guru")
        sesi_id = database.buat_sesi(
            kon, siswa_id, seed=7, jumlah_soal=3,
        )
    yield s, siswa_id, sesi_id
    s.berhenti()


def _buat_tautan(server, sesi_id):
    kode, isi, header = server.minta(
        f"/sesi/{sesi_id}/bagikan",
        auth=("guru", SANDI_GURU),
        data={},
    )
    cocok = re.search(r'id="tautan-sesi"[^>]*value="([^"]+)"', isi)
    assert cocok, isi
    return kode, isi, header, cocok.group(1)


def test_token_mentah_tidak_disimpan_dan_berlaku_tujuh_hari(tmp_path):
    db = tmp_path / "tautan.db"
    database.siapkan(db)
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak", pemilik="guru")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=7, jumlah_soal=1)
        token = share_links.buat(kon, sesi_id, sekarang=1_000)
        baris = kon.execute(
            "SELECT token_hash, kedaluarsa FROM tautan_sesi WHERE sesi_id = ?",
            (sesi_id,),
        ).fetchone()

        assert baris["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
        assert token not in tuple(baris)
        assert baris["kedaluarsa"] == 1_000 + 7 * 24 * 60 * 60
        assert share_links.ambil(kon, token, sekarang=baris["kedaluarsa"] - 1)
        assert share_links.ambil(kon, token, sekarang=baris["kedaluarsa"]) is None


def test_buat_ulang_membatalkan_token_lama_dan_cabut_idempoten(tmp_path):
    db = tmp_path / "tautan.db"
    database.siapkan(db)
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak", pemilik="guru")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=7, jumlah_soal=1)
        lama = share_links.buat(kon, sesi_id, sekarang=1_000)
        baru = share_links.buat(kon, sesi_id, sekarang=2_000)

        assert lama != baru
        assert share_links.ambil(kon, lama, sekarang=2_001) is None
        assert share_links.ambil(kon, baru, sekarang=2_001)
        assert share_links.cabut(kon, sesi_id, sekarang=2_002) is True
        assert share_links.cabut(kon, sesi_id, sekarang=2_003) is False
        assert share_links.ambil(kon, baru, sekarang=2_003) is None


def test_link_tidak_membaca_kolom_rahasia_saat_render(tmp_path):
    db = tmp_path / "palang.db"
    database.siapkan(db)
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Palang", pemilik="guru")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=7, jumlah_soal=1)
        token = share_links.buat(kon, sesi_id)

        terlarang = {"kunci", "kode_usulan", "kode_final", "malrule_id", "alasan"}

        def jaga(aksi, _arg1, arg2, _db, _pemicu):
            if aksi == sqlite3.SQLITE_READ and arg2 in terlarang:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        kon.set_authorizer(jaga)
        akses = share_links.ambil(kon, token)
        assert akses is not None
        import student_pages

        halaman = student_pages.halaman_kerja_baru(
            kon, int(akses["siswa_id"]), int(akses["sesi_id"]),
            jalur_aksi=f"/mulai/{token}", akses_tautan=True,
        )
        assert halaman is not None


def test_tautan_ikut_hilang_saat_sesi_dihapus(tmp_path):
    db = tmp_path / "tautan.db"
    database.siapkan(db)
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak", pemilik="guru")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=7, jumlah_soal=1)
        share_links.buat(kon, sesi_id)
        assert database.hapus_sesi(kon, sesi_id)
        jumlah = kon.execute("SELECT COUNT(*) FROM tautan_sesi").fetchone()[0]
    assert jumlah == 0


def test_guru_membuat_tautan_absolut_untuk_fallback_tanpa_js(server):
    s, _, sesi_id = server
    kode, isi, _, tautan = _buat_tautan(s, sesi_id)

    assert kode == 200
    assert tautan.startswith("https://jagomat.id/mulai/")
    assert 'id="tautan-sesi"' in isi


def test_halaman_anak_menawarkan_bagikan_dan_cabut(server):
    s, siswa_id, sesi_id = server
    _buat_tautan(s, sesi_id)

    kode, isi, _ = s.minta(f"/anak/{siswa_id}", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert f'data-bagikan-url="/sesi/{sesi_id}/bagikan"' in isi
    assert f'action="/sesi/{sesi_id}/cabut-tautan"' in isi
    assert 'aria-label="Cabut tautan sesi"' in isi


def test_link_membuka_hanya_satu_sesi_tanpa_login(server):
    s, _, sesi_id = server
    _, _, _, tautan = _buat_tautan(s, sesi_id)
    jalur = tautan.removeprefix("https://jagomat.id")

    kode, isi, header = s.minta(jalur)

    assert kode == 200
    assert f'action="{jalur}"' in isi
    assert "Anak Tautan" in isi
    with s.buka() as kon:
        assert kon.execute(
            "SELECT mulai FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["mulai"] is None, "preview GET tidak boleh memulai timer"
    badan = isi.split("</style>", 1)[-1]
    assert "Sesi lain" not in badan
    assert 'action="/keluar"' not in badan
    assert 'action="/murid/foto/' not in badan
    assert "kunci" not in badan.lower()
    assert "malrule" not in badan.lower()
    assert header["Cache-Control"] == "no-store"
    assert header["Referrer-Policy"] == "no-referrer"
    assert header["X-Robots-Tag"] == "noindex, nofollow"
    assert "body:'aksi=mulai'" in isi


def test_post_mulai_dari_browser_tautan_mencatat_waktu_tanpa_jawaban(server):
    s, _, sesi_id = server
    _, _, _, tautan = _buat_tautan(s, sesi_id)
    jalur = tautan.removeprefix("https://jagomat.id")

    kode, _, header = s.minta(jalur, data={"aksi": "mulai"})

    assert kode == 200
    assert header["Cache-Control"] == "no-store"
    with s.buka() as kon:
        mulai = kon.execute(
            "SELECT mulai FROM sesi WHERE id = ?", (sesi_id,),
        ).fetchone()["mulai"]
        assert mulai is not None
        assert kon.execute("SELECT COUNT(*) FROM jawaban").fetchone()[0] == 0


def test_post_tanpa_jawaban_tidak_memulai_timer(server):
    s, _, sesi_id = server
    _, _, _, tautan = _buat_tautan(s, sesi_id)
    jalur = tautan.removeprefix("https://jagomat.id")

    kode, _, _ = s.minta(jalur, data={})

    assert kode == 200
    with s.buka() as kon:
        mulai = kon.execute(
            "SELECT mulai FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["mulai"]
        assert mulai is None
        assert kon.execute("SELECT COUNT(*) FROM jawaban").fetchone()[0] == 0


def test_post_menolak_id_soal_dari_sesi_lain(server):
    s, _, sesi_id = server
    with s.buka() as kon:
        siswa_lain = database.tambah_siswa(
            kon, "Anak Lain", pemilik="guru-lain"
        )
        sesi_lain = database.buat_sesi(
            kon, siswa_lain, seed=11, jumlah_soal=1
        )
        ssid_lain = database.isi_sesi(kon, sesi_lain)[0]["sesi_soal_id"]
    _, _, _, tautan = _buat_tautan(s, sesi_id)
    jalur = tautan.removeprefix("https://jagomat.id")

    kode, _, _ = s.minta(jalur, data={f"jwb_{ssid_lain}": "disusupkan"})

    assert kode == 400
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM jawaban").fetchone()[0] == 0


def test_bagikan_sesi_selesai_ditolak_jelas(server):
    s, _, sesi_id = server
    _, _, _, tautan = _buat_tautan(s, sesi_id)
    jalur = tautan.removeprefix("https://jagomat.id")
    with s.buka() as kon:
        soal = database.isi_sesi(kon, sesi_id)
    data = {f"jwb_{b['sesi_soal_id']}": "1" for b in soal}
    data["aksi"] = "selesai"
    s.minta(jalur, data=data)

    kode, isi, header = s.minta(
        f"/sesi/{sesi_id}/bagikan", auth=("guru", SANDI_GURU), data={}
    )

    assert kode == 400
    assert "sudah selesai" in isi
    assert 'id="tautan-sesi"' not in isi
    with s.buka() as kon:
        n_tautan = kon.execute(
            "SELECT COUNT(*) AS n FROM tautan_sesi WHERE sesi_id = ?",
            (sesi_id,),
        ).fetchone()["n"]
    assert n_tautan <= 1  # tautan lama boleh tersisa; tidak ada rotasi baru


def test_post_raksasa_ditolak_413(server):
    import http.client
    from urllib.parse import urlparse

    s, _, sesi_id = server
    _, _, _, tautan = _buat_tautan(s, sesi_id)
    jalur = tautan.removeprefix("https://jagomat.id")
    alamat = urlparse(s.alamat)

    # Kirim header dengan Content-Length raksasa TANPA mengirim body:
    # server wajib menjawab 413 sebelum membaca, bukan menggantung.
    conn = http.client.HTTPConnection(alamat.hostname, alamat.port, timeout=10)
    conn.putrequest("POST", jalur)
    conn.putheader("Content-Type", "application/x-www-form-urlencoded")
    conn.putheader("Content-Length", "1100000")
    conn.endheaders()
    resp = conn.getresponse()
    kode = resp.status
    resp.read()
    conn.close()

    assert kode == 413
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM jawaban").fetchone()[0] == 0


def test_link_bisa_menyimpan_lalu_otomatis_mati_setelah_selesai(server):
    s, _, sesi_id = server
    _, _, _, tautan = _buat_tautan(s, sesi_id)
    jalur = tautan.removeprefix("https://jagomat.id")
    with s.buka() as kon:
        soal = database.isi_sesi(kon, sesi_id)
    data = {f"jwb_{b['sesi_soal_id']}": "1" for b in soal}
    data["aksi"] = "selesai"

    kode, isi, _ = s.minta(jalur, data=data)
    assert kode == 200
    assert "Semua jawabanmu sudah masuk" in isi

    kode, isi, _ = s.minta(jalur)
    assert kode == 404
    with s.buka() as kon:
        jumlah = kon.execute(
            """SELECT COUNT(*) FROM jawaban j JOIN sesi_soal ss
               ON ss.id = j.sesi_soal_id WHERE ss.sesi_id = ?""",
            (sesi_id,),
        ).fetchone()[0]
    assert jumlah == len(soal)


@pytest.mark.parametrize("keadaan", ["salah", "kedaluarsa", "dicabut"])
def test_link_tidak_sah_404_identik_tanpa_menyentuh_jawaban(server, keadaan):
    s, _, sesi_id = server
    _, _, _, tautan = _buat_tautan(s, sesi_id)
    token = tautan.rsplit("/", 1)[1]
    kode_acuan, isi_acuan, _ = s.minta(f"/mulai/{'x' * len(token)}")
    if keadaan == "salah":
        token = "y" * len(token)
    else:
        with s.buka() as kon:
            if keadaan == "kedaluarsa":
                kon.execute(
                    "UPDATE tautan_sesi SET kedaluarsa = 0 WHERE sesi_id = ?",
                    (sesi_id,),
                )
            else:
                share_links.cabut(kon, sesi_id)

    kode, isi, _ = s.minta(f"/mulai/{token}", data={"jwb_1": "disusupkan"})
    assert kode_acuan == kode == 404
    assert isi == isi_acuan
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM jawaban").fetchone()[0] == 0


def test_guru_lain_tidak_bisa_membuat_atau_mencabut_tautan(server):
    s, _, sesi_id = server
    import auth

    auth.tambah_akun("guru-lain", "sandi-guru-lain-123", "guru")
    for aksi in ("bagikan", "cabut-tautan"):
        kode, _, _ = s.minta(
            f"/sesi/{sesi_id}/{aksi}",
            auth=("guru-lain", "sandi-guru-lain-123"),
            data={},
        )
        assert kode == 404
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM tautan_sesi").fetchone()[0] == 0


def test_mencabut_tautan_membuatnya_tidak_bisa_dipakai(server):
    s, _, sesi_id = server
    _, _, _, tautan = _buat_tautan(s, sesi_id)
    kode, isi, _ = s.minta(
        f"/sesi/{sesi_id}/cabut-tautan",
        auth=("guru", SANDI_GURU),
        data={},
    )
    assert kode == 200
    assert "Tautan sesi dicabut" in isi
    assert f"Sesi #{sesi_id}" in isi
    with s.buka() as kon:
        assert share_links.aktif(kon, sesi_id) is False

    jalur = tautan.removeprefix("https://jagomat.id")
    kode, _, _ = s.minta(jalur)
    assert kode == 404
