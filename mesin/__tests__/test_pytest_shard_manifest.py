"""Bukti shard sintetis harus lengkap sebelum palang kandidat bisa lulus."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR / "scripts"))
import pytest_shard as pembagi
import verify_pytest_shards as pemeriksa

REVISION = "a" * 40
FASE = ["setup", "call", "teardown"]


def _laporan(nodeids):
    return [
        {"nodeid": nodeid, "when": fase, "outcome": "passed", "wasxfail": False}
        for nodeid in nodeids for fase in FASE
    ]


def _manifest_sintetis():
    koleksi = sorted(f"test_sintetis.py::test_kasus[{n}]" for n in range(40))
    hasil = []
    for shard in range(1, 5):
        pilihan = [n for n in koleksi if pembagi.shard_untuk_nodeid(n, 4) == shard]
        hasil.append({
            "schema_version": 1, "revision": REVISION, "shard": shard, "total": 4,
            "collected": list(koleksi), "selected": pilihan,
            "reports": _laporan(pilihan), "collection_errors": [], "exitstatus": 0,
        })
    return hasil


def _tulis(direktori, manifests):
    direktori.mkdir(parents=True, exist_ok=True)
    for nomor, data in enumerate(manifests, 1):
        (direktori / f"kandidat-{nomor}.json").write_text(json.dumps(data), encoding="utf-8")
    return direktori


def _lingkungan(tmpdir=None):
    lingkungan = os.environ.copy()
    lingkungan.pop("PYTEST_ADDOPTS", None)
    lingkungan.pop("PYTEST_PLUGINS", None)
    lingkungan["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if tmpdir is not None:
        lingkungan["TMPDIR"] = str(tmpdir)
    return lingkungan


def _jalankan_shard(akar, manifest, shard=1, total=1, tambahan=()):
    return subprocess.run(
        [sys.executable, str(AKAR / "scripts/pytest_shard.py"),
         "--shard", str(shard), "--total", str(total),
         "--manifest", str(manifest), "--revision", REVISION, "--",
         "test_sintetis.py", "-q", "-W", "error", "-p", "no:cacheprovider",
         *tambahan],
        cwd=akar, env=_lingkungan(akar), capture_output=True, text=True, timeout=60,
    )


def _jalankan_verifier(direktori, total=4):
    return subprocess.run(
        [sys.executable, str(AKAR / "scripts/verify_pytest_shards.py"),
         "--directory", str(direktori), "--total", str(total), "--revision", REVISION],
        env=_lingkungan(), capture_output=True, text=True, timeout=30,
    )


def test_verifier_menerima_partisi_sintetis_utuh(tmp_path):
    assert pemeriksa.verifikasi_manifest(_tulis(tmp_path, _manifest_sintetis()), 4, REVISION) == 40


@pytest.mark.parametrize("kasus", ["hilang", "tambahan", "ganda", "tak_dikenal", "total", "revision"])
def test_verifier_menolak_shard_tidak_lengkap_atau_berbeda(tmp_path, kasus):
    manifests = _manifest_sintetis()
    if kasus == "hilang":
        manifests.pop()
    elif kasus == "tambahan":
        manifests.append(copy.deepcopy(manifests[0]))
    elif kasus == "ganda":
        manifests[1] = copy.deepcopy(manifests[0])
    elif kasus == "tak_dikenal":
        manifests[0]["shard"] = 5
    elif kasus == "total":
        manifests[0]["total"] = 3
    else:
        manifests[0]["revision"] = "b" * 40
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(_tulis(tmp_path, manifests), 4, REVISION)


@pytest.mark.parametrize("kasus", [
    "koleksi_berbeda", "pilihan_hilang", "pilihan_salah", "laporan_hilang",
    "laporan_ganda", "laporan_asing", "koleksi_ganda", "pilihan_ganda",
    "koleksi_tidak_terurut", "pilihan_tidak_terurut", "fase_ganda", "fase_terbalik",
    "fase_tak_dikenal", "koleksi_kosong", "pilihan_kosong", "hanya_koleksi",
])
def test_verifier_menolak_bukti_exact_once_rusak(tmp_path, kasus):
    manifests = _manifest_sintetis()
    data = manifests[0]
    if kasus == "koleksi_berbeda":
        # Ubah nodeid milik shard lain sehingga partisi lokal tetap valid.
        data["collected"].remove(manifests[1]["selected"][0])
    elif kasus == "pilihan_hilang":
        data["selected"].pop()
        data["reports"] = _laporan(data["selected"])
    elif kasus == "pilihan_salah":
        data["selected"] = sorted(data["selected"] + [manifests[1]["selected"][0]])
        data["reports"] = _laporan(data["selected"])
    elif kasus == "laporan_hilang":
        data["reports"].pop()
    elif kasus == "laporan_ganda":
        data["reports"].extend(copy.deepcopy(data["reports"][:3]))
    elif kasus == "laporan_asing":
        data["reports"][0]["nodeid"] = "test_sintetis.py::test_asing"
    elif kasus in ("koleksi_ganda", "pilihan_ganda"):
        kunci = "collected" if kasus == "koleksi_ganda" else "selected"
        data[kunci] = sorted(data[kunci] + data[kunci][:1])
    elif kasus in ("koleksi_tidak_terurut", "pilihan_tidak_terurut"):
        data["collected" if kasus.startswith("koleksi") else "selected"].reverse()
    elif kasus == "fase_ganda":
        data["reports"][1]["when"] = "setup"
    elif kasus == "fase_terbalik":
        data["reports"][0], data["reports"][1] = data["reports"][1], data["reports"][0]
    elif kasus == "fase_tak_dikenal":
        data["reports"][0]["when"] = "unknown"
    elif kasus == "koleksi_kosong":
        data["collected"] = []
    elif kasus == "pilihan_kosong":
        data["selected"] = []
        data["reports"] = []
    else:
        data["reports"] = []
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(_tulis(tmp_path, manifests), 4, REVISION)


@pytest.mark.parametrize("fase", range(3))
@pytest.mark.parametrize("outcome", ["failed", "skipped", "rerun"])
def test_verifier_menolak_fase_tidak_lulus_walau_exit_nol(tmp_path, fase, outcome):
    manifests = _manifest_sintetis()
    manifests[0]["reports"][fase]["outcome"] = outcome
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(_tulis(tmp_path, manifests), 4, REVISION)


@pytest.mark.parametrize("kasus", ["xfail", "koleksi_gagal", "koleksi_skip", "exit_gagal"])
def test_verifier_menolak_status_sesi_atau_xfail(tmp_path, kasus):
    manifests = _manifest_sintetis()
    if kasus == "xfail":
        manifests[0]["reports"][1]["wasxfail"] = True
    elif kasus == "exit_gagal":
        manifests[0]["exitstatus"] = 1
    else:
        manifests[0]["collection_errors"] = [{
            "nodeid": "test_sintetis.py", "outcome": "failed" if kasus == "koleksi_gagal" else "skipped",
        }]
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(_tulis(tmp_path, manifests), 4, REVISION)


@pytest.mark.parametrize("kunci", sorted(_manifest_sintetis()[0]))
@pytest.mark.parametrize("perubahan", ["hilang", "tipe"])
def test_verifier_menolak_field_manifest_hilang_atau_salah_tipe(tmp_path, kunci, perubahan):
    manifests = _manifest_sintetis()
    if perubahan == "hilang":
        del manifests[0][kunci]
    else:
        manifests[0][kunci] = None
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(_tulis(tmp_path, manifests), 4, REVISION)


@pytest.mark.parametrize("kunci", ["nodeid", "when", "outcome", "wasxfail"])
@pytest.mark.parametrize("perubahan", ["hilang", "tipe"])
def test_verifier_menolak_field_laporan_hilang_atau_salah_tipe(tmp_path, kunci, perubahan):
    manifests = _manifest_sintetis()
    if perubahan == "hilang":
        del manifests[0]["reports"][0][kunci]
    else:
        manifests[0]["reports"][0][kunci] = []
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(_tulis(tmp_path, manifests), 4, REVISION)


@pytest.mark.parametrize("kunci,nilai", [
    ("schema_version", True), ("schema_version", 2), ("shard", True),
    ("total", 4.0), ("exitstatus", False), ("reports", [None]),
    ("collected", [0]), ("selected", [""]),
])
def test_verifier_menolak_nilai_tidak_sah(tmp_path, kunci, nilai):
    manifests = _manifest_sintetis()
    manifests[0][kunci] = nilai
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(_tulis(tmp_path, manifests), 4, REVISION)


@pytest.mark.parametrize("isi", ["{", "[]", "null", '{"shard":1,"shard":2}', '{"total":NaN}'])
def test_cli_verifier_menolak_json_rusak(tmp_path, isi):
    _tulis(tmp_path, _manifest_sintetis())
    (tmp_path / "kandidat-1.json").write_text(isi, encoding="utf-8")
    hasil = _jalankan_verifier(tmp_path)
    assert hasil.returncode == 1, hasil.stdout + hasil.stderr
    assert "Verifikasi shard gagal" in hasil.stderr
    assert "Traceback" not in hasil.stderr


def test_cli_verifier_menolak_kunci_ganda_meski_nilai_sama(tmp_path):
    manifests = _manifest_sintetis()
    _tulis(tmp_path, manifests)
    isi = json.dumps(manifests[0])
    (tmp_path / "kandidat-1.json").write_text(
        isi[:-1] + ', "exitstatus": 0}', encoding="utf-8",
    )
    hasil = _jalankan_verifier(tmp_path)
    assert hasil.returncode == 1, hasil.stdout + hasil.stderr
    assert "Kunci JSON ganda" in hasil.stderr


@pytest.mark.parametrize("bagian", ["manifest", "laporan"])
def test_verifier_menolak_field_tambahan(tmp_path, bagian):
    manifests = _manifest_sintetis()
    sasaran = manifests[0] if bagian == "manifest" else manifests[0]["reports"][0]
    sasaran["tak_dikenal"] = True
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(_tulis(tmp_path, manifests), 4, REVISION)


@pytest.mark.parametrize("kasus", ["direktori_hilang", "direktori_bukan_json", "non_json", "symlink"])
def test_verifier_menolak_direktori_tidak_sah(tmp_path, kasus):
    direktori = _tulis(tmp_path / "manifests", _manifest_sintetis())
    path = direktori / "kandidat-1.json"
    if kasus == "direktori_hilang":
        direktori = tmp_path / "tidak_ada"
    elif kasus == "direktori_bukan_json":
        path.unlink()
        path.mkdir()
    elif kasus == "non_json":
        path.rename(path.with_suffix(".txt"))
    else:
        sasaran = tmp_path / "salinan.json"
        path.rename(sasaran)
        path.symlink_to(sasaran)
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(direktori, 4, REVISION)


def test_pytest_nyata_empat_shard_merekam_semua_fase_dan_lulus_agregat(tmp_path):
    (tmp_path / "test_sintetis.py").write_text(
        "import pytest\n@pytest.mark.parametrize('nomor', range(40))\n"
        "def test_kasus(nomor):\n    assert nomor >= 0\n", encoding="utf-8",
    )
    direktori = tmp_path / "manifests"
    for shard in range(1, 5):
        path = direktori / f"kandidat-{shard}.json"
        hasil = _jalankan_shard(tmp_path, path, shard, 4)
        assert hasil.returncode == 0, hasil.stdout + hasil.stderr
        data = json.loads(path.read_text())
        assert data == _manifest_sintetis()[shard - 1] | {"reports": data["reports"]}
        assert len(data["reports"]) == 3 * len(data["selected"])
    hasil = _jalankan_verifier(direktori)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    assert "4 shard, 40 test exact-once" in hasil.stdout


@pytest.mark.parametrize("sumber,status,tambahan", [
    ("def test_kasus():\n    assert False\n", 1, ()),
    ("import pytest\n@pytest.fixture(autouse=True)\ndef awal():\n    assert False\n"
     "def test_kasus():\n    pass\n", 1, ()),
    ("import pytest\n@pytest.fixture(autouse=True)\ndef akhir():\n    yield\n    assert False\n"
     "def test_kasus():\n    pass\n", 1, ()),
    ("import pytest\ndef test_kasus():\n    pytest.skip('sintetis')\n", 0, ()),
    ("import pytest\n@pytest.mark.skip(reason='sintetis')\ndef test_kasus():\n    pass\n", 0, ()),
    ("import pytest\n@pytest.mark.xfail(reason='sintetis')\ndef test_kasus():\n    assert False\n", 0, ()),
    ("import pytest\n@pytest.mark.xfail(reason='sintetis')\ndef test_kasus():\n    pass\n", 0, ()),
    ("def test_kasus():\n    pass\n", 0, ("--collect-only",)),
    ("def test_kasus():\n    pass\ndef test_lain():\n    pass\n", 0, ("-k", "test_kasus")),
    ("import pytest\ndef test_kasus():\n    pytest.exit('sintetis', returncode=0)\n", 0, ()),
], ids=["call_gagal", "setup_gagal", "teardown_gagal", "skip_call", "skip_setup",
        "xfail", "xpass", "collect_only", "filter_k", "keluar_nol_tanpa_hasil"])
def test_pytest_nyata_bukti_tidak_lengkap_tidak_bisa_lulus(tmp_path, sumber, status, tambahan):
    (tmp_path / "test_sintetis.py").write_text(sumber, encoding="utf-8")
    path = tmp_path / "manifests/kandidat-1.json"
    hasil = _jalankan_shard(tmp_path, path, tambahan=tambahan)
    assert hasil.returncode == status, hasil.stdout + hasil.stderr
    data = json.loads(path.read_text())
    assert data["exitstatus"] == status
    assert data["collected"]
    assert data["selected"]
    if tambahan == ("--collect-only",):
        assert data["reports"] == []
    if tambahan == ("-k", "test_kasus"):
        assert len(data["collected"]) == 2 and len(data["selected"]) == 1
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(path.parent, 1, REVISION)


@pytest.mark.parametrize("sumber", [
    "raise RuntimeError('koleksi sintetis gagal')\n",
    "import pytest\npytest.skip('koleksi sintetis skip', allow_module_level=True)\n",
])
def test_pytest_nyata_mencatat_kegagalan_atau_skip_koleksi(tmp_path, sumber):
    (tmp_path / "test_sintetis.py").write_text(sumber, encoding="utf-8")
    path = tmp_path / "manifests/kandidat-1.json"
    hasil = _jalankan_shard(tmp_path, path)
    data = json.loads(path.read_text())
    assert data["exitstatus"] == hasil.returncode
    assert data["collection_errors"]
    with pytest.raises(ValueError):
        pemeriksa.verifikasi_manifest(path.parent, 1, REVISION)


def test_manifest_tidak_diwariskan_ke_pytest_anak(tmp_path):
    (tmp_path / "anak_sintetis.py").write_text("def test_anak():\n    pass\n", encoding="utf-8")
    (tmp_path / "test_sintetis.py").write_text(
        "import subprocess, sys\ndef test_kasus():\n"
        "    subprocess.run([sys.executable, '-m', 'pytest', 'anak_sintetis.py', "
        "'-q', '-p', 'no:cacheprovider'], check=True, timeout=30)\n", encoding="utf-8",
    )
    path = tmp_path / "manifests/kandidat-1.json"
    hasil = _jalankan_shard(tmp_path, path)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    assert pemeriksa.verifikasi_manifest(path.parent, 1, REVISION) == 1
    assert json.loads(path.read_text())["collected"] == ["test_sintetis.py::test_kasus"]


def test_wrapper_plugin_lain_tidak_bisa_memangkas_bukti_koleksi(tmp_path):
    (tmp_path / "conftest.py").write_text(
        "import pytest\n"
        "@pytest.hookimpl(hookwrapper=True, tryfirst=True)\n"
        "def pytest_collection_modifyitems(config, items):\n"
        "    dibuang = items[1:]\n"
        "    items[:] = items[:1]\n"
        "    config.hook.pytest_deselected(items=dibuang)\n"
        "    yield\n", encoding="utf-8",
    )
    (tmp_path / "test_sintetis.py").write_text(
        "def test_satu():\n    pass\ndef test_dua():\n    pass\n", encoding="utf-8",
    )
    path = tmp_path / "manifests/kandidat-1.json"
    hasil = _jalankan_shard(tmp_path, path)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    data = json.loads(path.read_text())
    assert len(data["collected"]) == 2
    assert len(data["selected"]) == 1
    with pytest.raises(ValueError, match="partisi hash"):
        pemeriksa.verifikasi_manifest(path.parent, 1, REVISION)


def test_sesi_terputus_menghapus_manifest_lama(tmp_path, monkeypatch):
    path = tmp_path / "kandidat-1.json"
    path.write_text(json.dumps(_manifest_sintetis()[0]), encoding="utf-8")

    def terputus(*args, **kwargs):
        assert not path.exists()
        raise RuntimeError("sesi sintetis terputus")

    monkeypatch.setattr(pembagi.pytest, "main", terputus)
    with pytest.raises(RuntimeError, match="terputus"):
        pembagi.main(["--shard", "1", "--total", "4", "--manifest", str(path),
                      "--revision", REVISION, "--", "test_sintetis.py"])
    assert not path.exists()
