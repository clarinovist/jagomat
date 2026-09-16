"""Pembagian recovery menjaga cakupan penuh tanpa xdist satu runner."""

import importlib.util
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest


SKRIP = Path(__file__).resolve().parents[2] / "scripts/pytest_shard.py"
SPEK = importlib.util.spec_from_file_location("pytest_shard", SKRIP)
assert SPEK is not None
pytest_shard = importlib.util.module_from_spec(SPEK)
assert SPEK.loader is not None
SPEK.loader.exec_module(pytest_shard)

# Anchor koleksi snapshot immutable yang diuji/dibangun CI, bukan jumlah kandidat.
# Recovery baru harus diukur dan direview sebelum dimasukkan; tidak ada fallback.
JUMLAH_RECOVERY = {
    "33e241c18024190f41ebca1986e35af26c0397fd": 9851,
    "0ee93109f7950fb6fd86ae93fb63ffbd69bcb10c": 10635,
    "e38e2e150c514c54db5470820561e69654c699bf": 10851,
}


class ItemPalsu:
    def __init__(self, nodeid):
        self.nodeid = nodeid


class HookPalsu:
    def __init__(self):
        self.dilewati = []

    def pytest_deselected(self, items):
        self.dilewati.extend(items)


class ConfigPalsu:
    def __init__(self):
        self.hook = HookPalsu()


def test_vector_blake2b_tetap_dan_1_based():
    assert pytest_shard.shard_untuk_nodeid(
        "mesin/__tests__/test_a.py::test_x", 4
    ) == 1
    assert pytest_shard.shard_untuk_nodeid(
        "mesin/__tests__/test_generator.py::test_kasus[0]", 4
    ) == 4
    assert pytest_shard.shard_untuk_nodeid(
        "mesin/__tests__/test_generator.py::test_kasus[1]", 4
    ) == 4


def test_pemetaan_stabil_walau_urutan_collection_berubah():
    nodeids = [
        f"mesin/__tests__/test_area_{nomor}.py::test_kasus[{varian}]"
        for nomor in range(80)
        for varian in range(40)
    ]
    awal = pytest_shard.petakan_nodeid(nodeids, 4)
    acak = list(nodeids)
    random.Random(20260915).shuffle(acak)
    assert pytest_shard.petakan_nodeid(acak, 4) == awal
    muatan = [sum(nilai == shard for nilai in awal.values()) for shard in range(1, 5)]
    assert set(awal.values()) == {1, 2, 3, 4}
    assert max(muatan) <= min(muatan) * 1.15


def test_koleksi_recovery_pinned_stabil_dan_seluruh_shard_exact_once(tmp_path):
    """Buktikan helper terhadap nodeid snapshot yang benar-benar dibangun."""
    akar = Path(__file__).resolve().parents[2]
    workflow = (akar / ".github/workflows/deploy.yml").read_text()
    cocok = re.search(r"^  RECOVERY_SHA: ([0-9a-f]{40})$", workflow, re.M)
    assert cocok is not None
    recovery = cocok.group(1)
    assert recovery in JUMLAH_RECOVERY, "Ukur dan tinjau anchor koleksi recovery baru."
    arsip = tmp_path / "recovery.tar"
    with arsip.open("wb") as keluaran:
        subprocess.run(
            ["git", "-C", str(akar), "archive", recovery],
            stdout=keluaran, check=True,
        )
    salinan = tmp_path / "recovery"
    salinan.mkdir()
    subprocess.run(["tar", "-xf", str(arsip), "-C", str(salinan)], check=True)
    lingkungan = os.environ.copy()
    lingkungan.pop("PYTEST_ADDOPTS", None)
    lingkungan.pop("PYTEST_PLUGINS", None)
    lingkungan["TMPDIR"] = str(tmp_path)
    hasil = subprocess.run(
        [sys.executable, "-m", "pytest", "mesin/__tests__/", "--collect-only", "-q",
         "-p", "no:cacheprovider"],
        cwd=salinan, env=lingkungan, capture_output=True, text=True, check=True, timeout=180,
    )
    nodeids = [baris for baris in hasil.stdout.splitlines() if "::" in baris]
    assert len(nodeids) == JUMLAH_RECOVERY[recovery]
    assert len(nodeids) == len(set(nodeids))
    tujuan = pytest_shard.petakan_nodeid(nodeids, 4)
    acak = list(reversed(nodeids))
    assert pytest_shard.petakan_nodeid(acak, 4) == tujuan
    shard = [{nodeid for nodeid, nomor in tujuan.items() if nomor == n} for n in range(1, 5)]
    assert all(shard)
    assert sum(map(len, shard)) == len(nodeids)
    assert set().union(*shard) == set(nodeids)
    assert all(shard[a].isdisjoint(shard[b]) for a in range(4) for b in range(a + 1, 4))


def test_plugin_memilih_union_disjoint_dan_melaporkan_deselected():
    nodeids = [f"mesin/__tests__/test_{nomor}.py::test_x" for nomor in range(40)]
    semua = set()
    for shard in range(1, 5):
        items = [ItemPalsu(nodeid) for nodeid in nodeids]
        config = ConfigPalsu()
        plugin = pytest_shard.PemilihShard(shard, 4)
        plugin.pytest_collection_modifyitems(config, items)
        dipilih = {item.nodeid for item in items}
        dilewati = {item.nodeid for item in config.hook.dilewati}
        assert dipilih.isdisjoint(semua)
        assert dipilih | dilewati == set(nodeids)
        assert plugin.terpilih == len(dipilih)
        semua.update(dipilih)
    assert semua == set(nodeids)


def test_koleksi_kandidat_nyata_identik_lintas_hashseed(tmp_path):
    """Setiap runner harus mengoleksi himpunan kandidat yang sama."""
    akar = Path(__file__).resolve().parents[2]
    acuan = None
    for seed in ("17", "9281"):
        lingkungan = os.environ.copy()
        lingkungan.pop("PYTEST_ADDOPTS", None)
        lingkungan.pop("PYTEST_PLUGINS", None)
        lingkungan.update(PYTHONHASHSEED=seed, TMPDIR=str(tmp_path))
        hasil = subprocess.run(
            [sys.executable, "-m", "pytest", "mesin/__tests__/", "--collect-only",
             "-q", "-W", "error", "-p", "no:cacheprovider"],
            cwd=akar, env=lingkungan, capture_output=True, text=True, timeout=180,
        )
        assert hasil.returncode == 0, hasil.stdout + hasil.stderr
        nodeids = sorted(baris for baris in hasil.stdout.splitlines() if "::" in baris)
        assert len(nodeids) >= 9910
        assert len(nodeids) == len(set(nodeids))
        if acuan is None:
            acuan = nodeids
        assert nodeids == acuan
        partisi = [
            {nodeid for nodeid in nodeids if pytest_shard.shard_untuk_nodeid(nodeid, 4) == n}
            for n in range(1, 5)
        ]
        assert all(partisi)
        assert sum(map(len, partisi)) == len(nodeids)
        assert set().union(*partisi) == set(nodeids)
        assert all(partisi[a].isdisjoint(partisi[b]) for a in range(4) for b in range(a + 1, 4))


@pytest.mark.parametrize(
    "argv",
    [
        ["--shard", "0", "--total", "4", "--", "tests"],
        ["--shard", "5", "--total", "4", "--", "tests"],
        ["--shard", "1", "--total", "0", "--", "tests"],
        ["--shard", "1", "--total", "4"],
        ["--shard", "1", "--total", "4", "--manifest", "sintetis.json", "--", "tests"],
        ["--shard", "1", "--total", "4", "--manifest", "sintetis.json",
         "--revision", "", "--", "tests"],
        ["--shard", "1", "--total", "4", "--manifest", "sintetis.json",
         "--revision", " ", "--", "tests"],
    ],
)
def test_argumen_tidak_aman_ditolak(argv):
    with pytest.raises(SystemExit):
        pytest_shard.parse_argumen(argv)


@pytest.mark.parametrize("opsi", [[], ["--manifest", "sintetis.json", "--revision", "a" * 40]])
def test_parse_argumen_mempertahankan_tuple_recovery(opsi):
    assert pytest_shard.parse_argumen(
        ["--shard", "2", "--total", "4"] + opsi + ["--", "tests", "-q"]
    ) == (2, 4, ["tests", "-q"])


def test_pemanggilan_recovery_tanpa_manifest_tidak_memasang_pencatat(monkeypatch):
    def jalankan(argumen, plugins):
        assert argumen == ["tests", "-q"]
        assert len(plugins) == 1
        assert type(plugins[0]) is pytest_shard.PemilihShard
        assert plugins[0].shard == 2
        assert plugins[0].total == 4
        return 5

    monkeypatch.setattr(pytest_shard.pytest, "main", jalankan)
    assert pytest_shard.main(["--shard", "2", "--total", "4", "--", "tests", "-q"]) == 5
