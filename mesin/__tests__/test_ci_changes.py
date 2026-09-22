"""Seleksi CI hanya melewati suite untuk delta dokumen aman yang terverifikasi."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
SPEK = importlib.util.spec_from_file_location("ci_changes_uji", AKAR / "scripts/ci_changes.py")
ci = importlib.util.module_from_spec(SPEK)
SPEK.loader.exec_module(ci)


def _git(akar, *argumen):
    return subprocess.run(
        ["git", "-C", str(akar), *argumen], check=True, capture_output=True,
        text=True, timeout=10,
    ).stdout.strip()


def _simpan(akar, nama, teks="# Contoh sintetis\n"):
    path = akar / nama
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(teks, encoding="utf-8")


def _commit(akar):
    _git(akar, "add", "-A")
    _git(akar, "-c", "user.name=Uji CI", "-c", "user.email=ci@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "-qm", "test: perubahan sintetis")
    return _git(akar, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    akar = tmp_path / "repo"
    akar.mkdir()
    _git(akar, "init", "-q")
    _simpan(akar, "README.md")
    _simpan(akar, "mesin/contoh.py", "NILAI = 1\n")
    sebelum = _commit(akar)
    return akar, sebelum


def _event(sebelum, sesudah):
    return {"before": sebelum, "after": sesudah,
            "ref": "refs/heads/main", "forced": False}


def _pilih(akar, sebelum):
    sesudah = _git(akar, "rev-parse", "HEAD")
    return ci.pilih_jalur(akar, "push", _event(sebelum, sesudah), sesudah)


@pytest.mark.parametrize("nama", sorted(ci.DOKUMEN_AMAN))
def test_dokumen_allowlist_memakai_jalur_ringan(repo, nama):
    akar, sebelum = repo
    _simpan(akar, nama, "# Dokumentasi sintetis diperbarui\n")
    _commit(akar)
    lengkap, _, daftar = _pilih(akar, sebelum)
    assert lengkap is False
    assert daftar == (nama,)
    ci.periksa_dokumen(akar, daftar)


@pytest.mark.parametrize("nama", [
    "mesin/contoh.py", "mesin/__tests__/test_baru.py", "mesin/Dockerfile",
    "mesin/aset/contoh.svg", "scripts/ci_changes.py", "scripts/check_repo.py",
    "scripts/release-metadata.json", ".github/workflows/deploy.yml",
    ".project-gate.json", "pytest.ini", ".gitignore", "CLAUDE.md",
    "docs/siklus-belajar-terpandu.md", "docs/production-release.md",
    "docs/workflow-reference.md", "docs/baru.md", "mesin/README.md",
    "docs/spasi dan\nbaris.md", "README.md.py",
])
def test_berkas_nonallowlist_dan_campuran_selalu_lengkap(repo, nama):
    akar, sebelum = repo
    _simpan(akar, "README.md", "# Dokumen baru\n")
    _simpan(akar, nama, "contoh baru\n")
    _commit(akar)
    assert _pilih(akar, sebelum)[0] is True


def test_tidak_memakai_wildcard_dokumen():
    assert ci.DOKUMEN_AMAN == {"README.md", "docs/README.md", "docs/ci-selective.md"}


def test_huruf_besar_path_tidak_disamakan(repo):
    akar, sebelum = repo
    # Lepas nama lama dari index dahulu, termasuk pada filesystem Mac case-insensitive.
    _git(akar, "rm", "README.md")
    _simpan(akar, "README.MD", "# Nama berbeda\n")
    _commit(akar)
    assert _pilih(akar, sebelum)[0] is True


def test_seluruh_push_bukan_hanya_commit_terakhir(repo):
    akar, sebelum = repo
    _simpan(akar, "mesin/contoh.py", "NILAI = 2\n")
    _commit(akar)
    _simpan(akar, "README.md", "# Commit terakhir hanya dokumentasi\n")
    _commit(akar)
    assert _pilih(akar, sebelum)[0] is True


def test_diff_tidak_terpotong_pada_300_path(repo):
    akar, sebelum = repo
    for nomor in range(305):
        _simpan(akar, "docs/sintetis-{:03}.md".format(nomor))
    _simpan(akar, "mesin/contoh.py", "NILAI = 2\n")
    _commit(akar)
    assert _pilih(akar, sebelum)[0] is True


@pytest.mark.parametrize("asal,tujuan", [
    ("mesin/contoh.py", "docs/ci-selective.md"),
    ("README.md", "mesin/README.md"),
])
def test_rename_tidak_menyembunyikan_path_nonaman(repo, asal, tujuan):
    akar, sebelum = repo
    (akar / tujuan).parent.mkdir(parents=True, exist_ok=True)
    (akar / asal).rename(akar / tujuan)
    _commit(akar)
    assert _pilih(akar, sebelum)[0] is True


@pytest.mark.parametrize("nama,lengkap", [("README.md", False), ("mesin/contoh.py", True)])
def test_penghapusan_tetap_diperiksa(repo, nama, lengkap):
    akar, sebelum = repo
    (akar / nama).unlink()
    _commit(akar)
    assert _pilih(akar, sebelum)[0] is lengkap


def test_delta_kosong_selalu_lengkap(repo):
    akar, sebelum = repo
    assert _pilih(akar, sebelum)[0] is True


@pytest.mark.parametrize("nama_event", ["workflow_dispatch", "pull_request", "", "schedule"])
def test_manual_dan_event_lain_tidak_bisa_memaksa_skip(repo, nama_event):
    akar, sebelum = repo
    _simpan(akar, "README.md", "# Berubah\n")
    sesudah = _commit(akar)
    event = _event(sebelum, sesudah)
    event["inputs"] = {"lengkap": False, "mode": "dokumen"}
    assert ci.pilih_jalur(akar, nama_event, event, sesudah)[0] is True


@pytest.mark.parametrize("perubahan", [
    {"before": "0" * 40}, {"before": None}, {"before": ""},
    {"before": "a" * 40}, {"before": "HEAD^"}, {"before": "--help"},
    {"before": "$(echo tidak-dijalankan)"}, {"after": "b" * 40},
    {"ref": "refs/heads/lain"}, {"forced": True}, {"forced": None},
])
def test_metadata_tidak_pasti_selalu_lengkap(repo, perubahan):
    akar, sebelum = repo
    _simpan(akar, "README.md", "# Berubah\n")
    sesudah = _commit(akar)
    event = {**_event(sebelum, sesudah), **perubahan}
    assert ci.pilih_jalur(akar, "push", event, sesudah)[0] is True


@pytest.mark.parametrize("event", [None, [], "push", {}])
def test_event_rusak_tidak_dianggap_dokumen(repo, event):
    akar, sebelum = repo
    assert ci.pilih_jalur(akar, "push", event, sebelum)[0] is True


def test_checkout_mismatch_selalu_lengkap(repo):
    akar, sebelum = repo
    _simpan(akar, "README.md", "# Berubah\n")
    sesudah = _commit(akar)
    assert ci.pilih_jalur(akar, "push", _event(sebelum, sebelum), sebelum)[0] is True
    assert sesudah != sebelum


def test_history_nonancestor_selalu_lengkap(repo):
    akar, sebelum = repo
    _simpan(akar, "README.md", "# Berubah\n")
    sesudah = _commit(akar)
    # Commit orphan memakai plumbing, tanpa checkout/reset atau mengganti workspace.
    pohon = _git(akar, "rev-parse", sesudah + "^{tree}")
    asing = _git(akar, "-c", "user.name=Uji CI", "-c", "user.email=ci@example.invalid",
                 "commit-tree", pohon, "-m", "test: orphan sintetis")
    assert ci.pilih_jalur(akar, "push", _event(asing, sesudah), sesudah)[0] is True


def test_git_gagal_tidak_dianggap_dokumen(tmp_path):
    assert ci.pilih_jalur(tmp_path, "push", _event("a" * 40, "b" * 40), "b" * 40)[0] is True


@pytest.mark.parametrize("teks", [
    "<<<<<<< HEAD\nkonflik\n=======\nteks\n>>>>>>> lain\n",
    "# Contoh\0rusak", "[rusak](hilang.md)", "[keluar](../../luar.md)",
])
def test_dokumen_rusak_menahan_pemeriksaan(tmp_path, teks):
    _simpan(tmp_path, "README.md", teks)
    with pytest.raises(ValueError):
        ci.periksa_dokumen(tmp_path, ("README.md",))


def test_dokumen_utf8_rusak_ditolak(tmp_path):
    (tmp_path / "README.md").write_bytes(b"\xff")
    with pytest.raises(ValueError):
        ci.periksa_dokumen(tmp_path, ("README.md",))


def test_dokumen_symlink_ditolak(tmp_path):
    _simpan(tmp_path, "contoh.md")
    (tmp_path / "README.md").symlink_to("contoh.md")
    with pytest.raises(ValueError):
        ci.periksa_dokumen(tmp_path, ("README.md",))


def test_tautan_lokal_valid_dan_eksternal_tidak_diakses(tmp_path):
    _simpan(tmp_path, "docs/README.md")
    _simpan(tmp_path, "README.md", '[lokal](docs/README.md#judul) '
            '[luar](https://example.invalid/tidak-diakses) [anchor](#judul)\n')
    ci.periksa_dokumen(tmp_path, ("README.md",))


def test_dokumen_aman_repo_lulus_pemeriksaan():
    ci.periksa_dokumen(AKAR, ci.DOKUMEN_AMAN)


def _cli(akar, tmp_path, event, revisi, nama_event="push"):
    # Salinan hanya helper, bukan data/venv/worktree pengguna.
    tujuan = akar / "scripts/ci_changes.py"
    tujuan.parent.mkdir(exist_ok=True)
    shutil.copyfile(AKAR / "scripts/ci_changes.py", tujuan)
    event_path = tmp_path / "event.json"
    event_path.write_text(event, encoding="utf-8")
    output = tmp_path / "output"
    ringkasan = tmp_path / "summary"
    hasil = subprocess.run(
        [sys.executable, "-B", str(tujuan)], capture_output=True, text=True, timeout=10,
        env={**os.environ, "GITHUB_EVENT_NAME": nama_event, "GITHUB_SHA": revisi,
             "GITHUB_EVENT_PATH": str(event_path), "GITHUB_OUTPUT": str(output),
             "GITHUB_STEP_SUMMARY": str(ringkasan)},
    )
    return hasil, output, ringkasan


@pytest.mark.parametrize("nama_event,lengkap", [("push", "false"), ("workflow_dispatch", "true")])
def test_cli_output_boolean_dan_ringkasan(repo, tmp_path, nama_event, lengkap):
    akar, sebelum = repo
    _simpan(akar, "README.md", "# Berubah\n")
    sesudah = _commit(akar)
    hasil, output, ringkasan = _cli(
        akar, tmp_path, json.dumps(_event(sebelum, sesudah)), sesudah, nama_event,
    )
    assert hasil.returncode == 0, hasil.stderr
    assert output.read_text() == "lengkap=" + lengkap + "\n"
    assert "Pemilihan pemeriksaan" in ringkasan.read_text()
    assert "README" not in hasil.stdout + hasil.stderr + ringkasan.read_text()


def test_cli_event_invalid_memilih_lengkap(repo, tmp_path):
    akar, sebelum = repo
    hasil, output, _ = _cli(akar, tmp_path, "{invalid", sebelum)
    assert hasil.returncode == 0
    assert output.read_text() == "lengkap=true\n"


def test_cli_dokumen_gagal_tidak_menerbitkan_output_skip(repo, tmp_path):
    akar, sebelum = repo
    _simpan(akar, "README.md", "[rusak](hilang.md)\n")
    sesudah = _commit(akar)
    hasil, output, ringkasan = _cli(akar, tmp_path, json.dumps(_event(sebelum, sesudah)), sesudah)
    assert hasil.returncode == 1
    assert "Pemeriksaan dokumen gagal" in hasil.stdout
    assert not output.exists()
    assert not ringkasan.exists()
    assert "hilang" not in hasil.stdout + hasil.stderr
