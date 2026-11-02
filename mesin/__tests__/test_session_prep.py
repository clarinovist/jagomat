"""Lembar persiapan sesi: isi sama dengan Beranda, cetak tanpa interaksi."""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database  # noqa: E402
import interventions  # noqa: E402
import learning_cycle_ui  # noqa: E402
import session_prep  # noqa: E402
import teacher_pages  # noqa: E402
import teaching_playbook  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402
from learning_cycle import RencanaBelajar  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    jalur = tmp_path / "persiapan.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    with database.buka(jalur) as kon:
        anak = database.tambah_siswa(kon, "Anak <Sintetis>", "P3", pemilik="guru")
        yield kon, anak


def _siswa(kon, anak):
    return kon.execute("SELECT * FROM siswa WHERE id = ?", (anak,)).fetchone()


def _halaman(kon, anak):
    return session_prep.halaman_persiapan(
        kon, _siswa(kon, anak), peran="guru", hari_ini=date(2026, 10, 5)
    ).decode()


def test_isi_kartu_anak_baru_sama_dengan_beranda(db):
    kon, anak = db
    siswa = _siswa(kon, anak)
    beranda = learning_cycle_ui.kartu_rencana(kon, anak, siswa=siswa, peran="guru")
    halaman = _halaman(kon, anak)
    judul = "Mulai dengan latihan awal"
    instruksi = (
        "Biarkan anak mencoba dengan caranya sendiri. Setelah selesai, "
        "periksa hasil dan konfirmasikan."
    )
    assert judul in beranda and judul in halaman
    assert instruksi in beranda and instruksi in halaman
    assert "Caranya" in halaman


def test_isi_kartu_rencana_lain_sama_dengan_beranda(db, monkeypatch):
    kon, anak = db
    sesi = database.buat_sesi(kon, anak, seed=17, jumlah_soal=1)
    database.tandai_selesai(kon, sesi)
    monkeypatch.setattr(
        learning_cycle_ui,
        "rencana_berikutnya",
        lambda bukti, siswa_id, hari_ini=None: RencanaBelajar(
            "konfirmasi_hasil", "uji", sesi_id=sesi
        ),
    )
    siswa = _siswa(kon, anak)
    beranda = learning_cycle_ui.kartu_rencana(kon, anak, siswa=siswa, peran="guru")
    halaman = _halaman(kon, anak)
    judul = "Tinjau hasil latihan Anak &lt;Sintetis&gt;"
    instruksi = (
        "Tanyakan, “Bagaimana kamu mendapat jawaban ini?” "
        "Dengarkan caranya tanpa memberi jawaban."
    )
    assert judul in beranda and judul in halaman
    assert instruksi in beranda and instruksi in halaman


def test_halaman_cetak_tanpa_form_script_dan_berlabel_guru(db):
    kon, anak = db
    halaman = _halaman(kon, anak)
    assert "<form" not in halaman
    assert "<script" not in halaman
    assert "Untuk guru — jangan diberikan ke anak" in halaman
    assert "Catatan sesi (tulis tangan)" in halaman
    assert "5 Okt 2026" in halaman


def test_playbook_draf_terbuka_tanpa_js_dan_peringatan_tetap_terlihat(db, monkeypatch):
    kon, anak = db
    siswa = _siswa(kon, anak)
    monkeypatch.setattr(
        learning_cycle_ui,
        "rencana_berikutnya",
        lambda bukti, siswa_id, hari_ini=None: RencanaBelajar(
            "intervensi", "uji", kandidat=(("deret_aritmetika", "K", None),)
        ),
    )
    materi = interventions.MateriIntervensi(
        "uji", "Materi sintetis.", "Contoh sintetis.", "Strategi sintetis."
    )
    monkeypatch.setattr(
        interventions, "pilihan_untuk_fokus", lambda fokus: (materi,)
    )
    draf = (
        '<details class="playbook-guru" data-playbook-draf>'
        "<summary>Panduan mengajar"
        '<span class="playbook-peringatan">'
        + teaching_playbook.PERINGATAN_DRAF
        + "</span></summary><div class=\"playbook-isi\">Isi sintetis.</div></details>"
    )
    monkeypatch.setattr(teaching_playbook, "render", lambda *a, **k: draf)
    halaman = session_prep.halaman_persiapan(
        kon, siswa, peran="guru", hari_ini=date(2026, 10, 5)
    ).decode()
    assert teaching_playbook.PERINGATAN_DRAF in halaman
    assert '<details open class="playbook-guru"' in halaman


def test_kartu_gagal_aman_tanpa_detail_galat(db, monkeypatch):
    kon, anak = db
    siswa = _siswa(kon, anak)

    def gagal(*args, **kwargs):
        raise ValueError("detail internal yang tidak boleh tampil")

    monkeypatch.setattr(learning_cycle_ui, "kartu_rencana", gagal)
    halaman = session_prep.halaman_persiapan(kon, siswa, peran="guru").decode()
    assert session_prep.PESAN_TIDAK_TERBACA in halaman
    assert "detail internal" not in halaman
    assert "Traceback" not in halaman


def test_tautan_cetak_ada_di_beranda_guru_tetapi_tidak_di_halaman_persiapan(db):
    kon, anak = db
    siswa = _siswa(kon, anak)
    beranda = teacher_pages.halaman_anak(
        kon, siswa, peran="guru", pengguna="guru"
    ).decode()
    assert f'href="/anak/{anak}/persiapan"' in beranda
    assert "Cetak catatan persiapan guru" in beranda
    halaman = _halaman(kon, anak)
    assert "Cetak catatan persiapan guru" not in halaman
    assert f'href="/anak/{anak}/persiapan"' not in halaman


def test_tanpa_hex_warna_di_modul():
    sumber = Path(session_prep.__file__).read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", sumber)


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak persiapan", "P3", pemilik="guru")
        asing = database.tambah_siswa(kon, "Anak asing", "P3", pemilik="asing")
    yield s, anak, asing
    s.berhenti()


def test_http_pemilik_200_privat_dan_db_tetap(server):
    s, anak, _ = server
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, header = s.minta(
        f"/anak/{anak}/persiapan", auth=("guru", SANDI_GURU)
    )
    assert kode == 200
    assert header["Cache-Control"] == "no-store"
    assert header["Referrer-Policy"] == "no-referrer"
    assert "Untuk guru" in isi
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_http_asing_404_identik_dengan_id_tidak_ada_tanpa_write(server):
    s, _, asing = server
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())
    asing_hasil = s.minta(
        f"/anak/{asing}/persiapan", auth=("guru", SANDI_GURU)
    )
    tidak_ada = s.minta("/anak/999999/persiapan", auth=("guru", SANDI_GURU))
    assert asing_hasil[0] == tidak_ada[0] == 404
    assert asing_hasil[1] == tidak_ada[1]
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_http_kartu_gagal_tetap_200_dengan_pesan_aman(server, monkeypatch):
    s, anak, _ = server

    def gagal(*args, **kwargs):
        raise ValueError("detail internal yang tidak boleh tampil")

    monkeypatch.setattr(learning_cycle_ui, "kartu_rencana", gagal)
    kode, isi, _ = s.minta(
        f"/anak/{anak}/persiapan", auth=("guru", SANDI_GURU)
    )
    assert kode == 200
    assert session_prep.PESAN_TIDAK_TERBACA in isi
    assert "detail internal" not in isi
    assert "Traceback" not in isi


def test_http_tanpa_login_dan_murid_tidak_bisa_membuka(server):
    s, anak, _ = server
    assert s.minta(f"/anak/{anak}/persiapan")[0] != 200
    assert (
        s.minta(f"/anak/{anak}/persiapan", auth=("feby", SANDI_MURID))[0]
        != 200
    )


def test_jalur_lain_di_bawah_anak_tetap_merender_profil(server):
    s, anak, _ = server
    kode, isi, _ = s.minta(f"/anak/{anak}/apa", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "Yang perlu dilakukan sekarang" in isi
    assert "Untuk guru — jangan diberikan ke anak" not in isi
