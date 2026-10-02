"""Seleksi test cepat push tetap konservatif, deterministik, dan fail-safe."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


AKAR = Path(__file__).resolve().parents[2]
SPEK = importlib.util.spec_from_file_location(
    "ci_fast_tests_uji", AKAR / "scripts/ci_fast_tests.py",
)
ci = importlib.util.module_from_spec(SPEK)
SPEK.loader.exec_module(ci)


def _git(akar, *argumen):
    return subprocess.run(
        ["git", "-C", str(akar), *argumen], check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()


def _simpan(akar, nama, teks):
    path = akar / nama
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(teks, encoding="utf-8")


def _commit(akar):
    _git(akar, "add", "-A")
    _git(akar, "-c", "user.name=Uji CI", "-c", "user.email=ci@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "-qm", "test: delta sintetis")
    return _git(akar, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    akar = tmp_path / "repo"
    akar.mkdir()
    _git(akar, "init", "-q")
    for nama in ci.TEST_INTI:
        _simpan(akar, nama, "def test_inti():\n    assert True\n")
    _simpan(akar, "mesin/auth.py", "NILAI = 1\n")
    _simpan(akar, "mesin/auth_http.py", "import auth\n")
    _simpan(akar, "mesin/teacher_http.py", "import auth_http\n")
    _simpan(akar, "mesin/__tests__/test_auth_http.py", "import auth_http\ndef test_auth_http():\n    assert True\n")
    _simpan(akar, "mesin/__tests__/test_teacher_journey.py", "import teacher_http\ndef test_guru():\n    assert True\n")
    _simpan(akar, "mesin/__tests__/test_tidak_terkait.py", "import math\ndef test_math():\n    assert True\n")
    _simpan(akar, "scripts/ci_fast_tests.py", "# helper\n")
    _simpan(akar, "mesin/__tests__/test_ci_fast_tests.py", "def test_helper():\n    assert True\n")
    _simpan(akar, "mesin/__tests__/test_ci_workflow.py", "def test_workflow():\n    assert True\n")
    sebelum = _commit(akar)
    return akar, sebelum


def _event(sebelum, sesudah):
    return {
        "before": sebelum, "after": sesudah,
        "ref": "refs/heads/main", "forced": False,
    }


def test_delta_modul_memilih_smoke_dan_semua_test_dengan_prefix_sama(repo):
    akar, sebelum = repo
    _simpan(akar, "mesin/auth.py", "NILAI = 2\n")
    sesudah = _commit(akar)
    test, mode = ci.pilih_test(akar, _event(sebelum, sesudah), sesudah)
    assert mode == "delta"
    assert set(ci.TEST_INTI) <= set(test)
    assert "mesin/__tests__/test_auth_http.py" in test
    assert "mesin/__tests__/test_teacher_journey.py" in test
    assert "mesin/__tests__/test_tidak_terkait.py" not in test
    assert test == tuple(sorted(set(test)))


def test_modul_yang_dihapus_tetap_memilih_test_pengimpor(repo):
    akar, sebelum = repo
    (akar / "mesin/auth_http.py").unlink()
    sesudah = _commit(akar)
    test, mode = ci.pilih_test(akar, _event(sebelum, sesudah), sesudah)
    assert mode == "delta"
    assert "mesin/__tests__/test_auth_http.py" in test
    assert "mesin/__tests__/test_teacher_journey.py" in test


def test_aset_runtime_memilih_guard_image(repo):
    akar, sebelum = repo
    _simpan(akar, "mesin/__tests__/test_image.py", "def test_image():\n    assert True\n")
    _simpan(akar, "mesin/aset/contoh.svg", "<svg/>\n")
    sesudah = _commit(akar)
    test, _ = ci.pilih_test(akar, _event(sebelum, sesudah), sesudah)
    assert "mesin/__tests__/test_image.py" in test


def test_delta_test_baru_selalu_dijalankan(repo):
    akar, sebelum = repo
    nama = "mesin/__tests__/test_regresi_baru.py"
    _simpan(akar, nama, "def test_baru():\n    assert True\n")
    sesudah = _commit(akar)
    test, mode = ci.pilih_test(akar, _event(sebelum, sesudah), sesudah)
    assert mode == "delta"
    assert nama in test


def test_workflow_memilih_seluruh_kontrak_rilis(tmp_path):
    akar = tmp_path / "repo"
    akar.mkdir()
    for nama in ci.TEST_INTI + ci.TEST_KHUSUS[".github/workflows/deploy.yml"]:
        _simpan(akar, nama, "def test_kontrak():\n    assert True\n")
    _simpan(akar, ".github/workflows/deploy.yml", "name: awal\n")
    _git(akar, "init", "-q")
    sebelum = _commit(akar)
    _simpan(akar, ".github/workflows/deploy.yml", "name: berubah\n")
    sesudah = _commit(akar)
    test, _ = ci.pilih_test(akar, _event(sebelum, sesudah), sesudah)
    assert set(ci.TEST_KHUSUS[".github/workflows/deploy.yml"]) <= set(test)


def test_helper_ci_memilih_test_helper_dan_kontrak_workflow(repo):
    akar, sebelum = repo
    _simpan(akar, "scripts/ci_fast_tests.py", "# helper berubah\n")
    sesudah = _commit(akar)
    test, _ = ci.pilih_test(akar, _event(sebelum, sesudah), sesudah)
    assert "mesin/__tests__/test_ci_fast_tests.py" in test
    assert "mesin/__tests__/test_ci_workflow.py" in test


@pytest.mark.parametrize("event", [None, {}, {"forced": True}, {"ref": "refs/heads/lain"}])
def test_metadata_meragukan_memakai_smoke_fallback(repo, event):
    akar, _ = repo
    revisi = _git(akar, "rev-parse", "HEAD")
    test, mode = ci.pilih_test(akar, event, revisi)
    assert mode == "fallback"
    assert test == tuple(sorted(ci.TEST_INTI))


def test_seluruh_push_bukan_hanya_commit_terakhir(repo):
    akar, sebelum = repo
    _simpan(akar, "mesin/auth.py", "NILAI = 2\n")
    _commit(akar)
    nama = "mesin/__tests__/test_regresi_baru.py"
    _simpan(akar, nama, "def test_baru():\n    assert True\n")
    sesudah = _commit(akar)
    test, _ = ci.pilih_test(akar, _event(sebelum, sesudah), sesudah)
    assert "mesin/__tests__/test_auth_http.py" in test
    assert nama in test


def test_argv_pytest_tidak_memakai_shell_dan_menjaga_warning_error():
    argv = ci.perintah_pytest(("mesin/__tests__/test_auth.py",))
    assert argv == [
        sys.executable, "-m", "pytest", "mesin/__tests__/test_auth.py",
        "-q", "-W", "error", "-p", "no:cacheprovider",
    ]
    with pytest.raises(ValueError):
        ci.perintah_pytest(())


def test_cli_menjalankan_argv_yang_dipilih_tanpa_mencetak_path(tmp_path, monkeypatch):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({}), encoding="utf-8")
    ringkasan = tmp_path / "summary"
    terlihat = {}

    def palsu(argv, cwd):
        terlihat["argv"] = argv
        terlihat["cwd"] = cwd
        return type("Hasil", (), {"returncode": 7})()

    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(ringkasan))
    monkeypatch.setenv("GITHUB_SHA", "")
    monkeypatch.setattr(ci.subprocess, "run", palsu)
    assert ci.utama(AKAR) == 7
    assert terlihat["argv"] == ci.perintah_pytest(tuple(sorted(ci.TEST_INTI)))
    assert terlihat["cwd"] == str(AKAR)
    isi = ringkasan.read_text()
    assert "7 berkas test" in isi and "test_auth.py" not in isi
