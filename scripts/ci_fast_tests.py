"""Jalankan smoke test tetap dan test langsung terdampak untuk push kode."""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys


SHA = re.compile(r"[0-9a-f]{40}")
TEST_INTI = (
    "mesin/__tests__/test_auth.py",
    "mesin/__tests__/test_database.py",
    "mesin/__tests__/test_diagnosis.py",
    "mesin/__tests__/test_generator.py",
    "mesin/__tests__/test_learning_cycle.py",
    "mesin/__tests__/test_students.py",
    "mesin/__tests__/test_web_dispatch.py",
)
TEST_KHUSUS = {
    ".github/workflows/deploy.yml": (
        "mesin/__tests__/test_ci_workflow.py",
        "mesin/__tests__/test_deployment_pipeline.py",
        "mesin/__tests__/test_release_metadata.py",
        "mesin/__tests__/test_subscription_recovery.py",
    ),
    "mesin/Dockerfile": (
        "mesin/__tests__/test_image.py",
    ),
    "scripts/check_repo.py": (
        "mesin/__tests__/test_repo_hygiene.py",
    ),
    "scripts/ci_changes.py": (
        "mesin/__tests__/test_ci_changes.py",
        "mesin/__tests__/test_ci_workflow.py",
    ),
    "scripts/ci_fast_tests.py": (
        "mesin/__tests__/test_ci_fast_tests.py",
        "mesin/__tests__/test_ci_workflow.py",
    ),
    "scripts/deploy.py": (
        "mesin/__tests__/test_deployer.py",
        "mesin/__tests__/test_routine_deployment.py",
    ),
    "scripts/pytest_shard.py": (
        "mesin/__tests__/test_pytest_shard.py",
    ),
    "scripts/release_metadata.py": (
        "mesin/__tests__/test_release_metadata.py",
    ),
    "scripts/verify_pytest_shards.py": (
        "mesin/__tests__/test_pytest_shard.py",
    ),
    "scripts/verify_release_image.py": (
        "mesin/__tests__/test_release_image.py",
    ),
}


def _git(akar, *argumen):
    """Baca rentang Git tanpa shell atau mencetak nama berkas."""
    return subprocess.run(
        ["git", "-C", str(akar), *argumen], check=True,
        capture_output=True, timeout=30,
    ).stdout


def _perubahan_push(akar, event, revisi):
    """Ambil seluruh delta push; None berarti metadata tidak dapat dipercaya."""
    if not isinstance(event, dict):
        return None
    sebelum, sesudah = event.get("before"), event.get("after")
    if (event.get("ref") != "refs/heads/main" or event.get("forced") is not False
            or not all(isinstance(x, str) and SHA.fullmatch(x)
                       and x != "0" * 40 for x in (sebelum, sesudah))
            or sesudah != revisi):
        return None
    try:
        if _git(akar, "rev-parse", "HEAD").decode("ascii").strip() != sesudah:
            return None
        _git(akar, "merge-base", "--is-ancestor", sebelum, sesudah)
        mentah = _git(akar, "diff", "--name-only", "--no-renames", "-z",
                      sebelum, sesudah, "--")
        daftar = tuple(x for x in mentah.decode("utf-8").split("\0") if x)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    return daftar or None


def _tambah_jika_ada(akar, terpilih, nama):
    path = akar / nama
    if path.is_file() and not path.is_symlink():
        terpilih.add(nama)


def _tambah_pola_test(akar, terpilih, stem):
    direktori = akar / "mesin/__tests__"
    for path in direktori.glob("test_{}*.py".format(stem)):
        if path.is_file() and not path.is_symlink():
            terpilih.add(path.relative_to(akar).as_posix())


def _impor(path):
    """Ambil nama modul top-level; kompilasi terpisah tetap menangani syntax error."""
    try:
        pohon = ast.parse(path.read_text(encoding="utf-8"), str(path))
    except (OSError, UnicodeError, SyntaxError):
        return frozenset()
    hasil = set()
    for node in ast.walk(pohon):
        if isinstance(node, ast.Import):
            hasil.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            hasil.add(node.module.split(".", 1)[0])
    return frozenset(hasil)


def _test_dependen(akar, modul_awal):
    """Ikuti reverse import modul aplikasi lalu pilih test yang mengimpornya."""
    modul = {
        path.stem: path for path in (akar / "mesin").glob("*.py")
        if path.is_file() and not path.is_symlink()
    }
    impor_modul = {nama: _impor(path) for nama, path in modul.items()}
    # Nama modul yang dihapus tetap dipertahankan agar importirnya dites dan
    # memunculkan kegagalan import, bukan hilang dari analisis karena file lenyap.
    terdampak = set(modul_awal)
    berubah = True
    while berubah:
        sebelum = len(terdampak)
        terdampak.update(
            nama for nama, impor in impor_modul.items() if impor & terdampak
        )
        berubah = len(terdampak) != sebelum
    return tuple(
        path.relative_to(akar).as_posix()
        for path in sorted((akar / "mesin/__tests__").glob("test_*.py"))
        if path.is_file() and not path.is_symlink() and _impor(path) & terdampak
    )


def pilih_test(akar, event, revisi):
    """Pilih suite cepat konservatif tanpa pernah mengembalikan daftar kosong."""
    akar = akar.resolve()
    terpilih = set()
    for nama in TEST_INTI:
        _tambah_jika_ada(akar, terpilih, nama)

    perubahan = _perubahan_push(akar, event, revisi)
    if perubahan is None:
        return tuple(sorted(terpilih)), "fallback"

    modul_berubah = set()
    for nama in perubahan:
        if nama.startswith("mesin/__tests__/test_") and nama.endswith(".py"):
            _tambah_jika_ada(akar, terpilih, nama)
        path = Path(nama)
        if path.parent.as_posix() == "mesin" and path.suffix == ".py":
            modul_berubah.add(path.stem)
            _tambah_pola_test(akar, terpilih, path.stem)
        elif path.parent.as_posix() == "scripts" and path.suffix == ".py":
            _tambah_pola_test(akar, terpilih, path.stem)
        for test in TEST_KHUSUS.get(nama, ()):
            _tambah_jika_ada(akar, terpilih, test)
        if nama.startswith("mesin/aset/"):
            _tambah_jika_ada(akar, terpilih, "mesin/__tests__/test_image.py")
    terpilih.update(_test_dependen(akar, modul_berubah))
    return tuple(sorted(terpilih)), "delta"


def perintah_pytest(test):
    """Bentuk argv tanpa shell agar nama path tidak dapat menjadi opsi/perintah."""
    if not test:
        raise ValueError("Suite cepat tidak boleh kosong.")
    return [
        sys.executable, "-m", "pytest", *test,
        "-q", "-W", "error", "-p", "no:cacheprovider",
    ]


def utama(akar):
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError):
        event = None
    test, mode = pilih_test(akar, event, os.environ.get("GITHUB_SHA", ""))
    print("CI cepat: {} berkas test ({}).".format(len(test), mode))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
            output.write("## Test cepat\n\n{} berkas test dipilih dalam mode `{}`.\n".format(
                len(test), mode,
            ))
    return subprocess.run(perintah_pytest(test), cwd=str(akar)).returncode


if __name__ == "__main__":
    raise SystemExit(utama(Path(__file__).resolve().parents[1]))
