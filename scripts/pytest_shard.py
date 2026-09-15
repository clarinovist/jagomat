#!/usr/bin/env python3
"""Bagi nodeid pytest deterministik; manifest bukti eksekusi bersifat opsional."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pytest


_PERSONALISASI = b"osn-ci-v1"


def shard_untuk_nodeid(nodeid: str, total: int) -> int:
    """Petakan nodeid ke shard 1-based, stabil terhadap urutan collection."""
    if total < 1:
        raise ValueError("Total shard minimal 1")
    digest = hashlib.blake2b(
        nodeid.encode("utf-8"), digest_size=8, person=_PERSONALISASI
    ).digest()
    return int.from_bytes(digest, "big") % total + 1


def petakan_nodeid(nodeids: Sequence[str], total: int) -> Dict[str, int]:
    """Petakan seluruh nodeid tanpa bergantung urutan atau state runner lain."""
    return {nodeid: shard_untuk_nodeid(nodeid, total) for nodeid in nodeids}


class PemilihShard:
    def __init__(self, shard: int, total: int) -> None:
        if not 1 <= shard <= total:
            raise ValueError("Nomor shard harus antara 1 dan total shard")
        self.shard = shard
        self.total = total
        self.terpilih = 0

    def pytest_collection_modifyitems(self, config, items) -> None:
        terpilih = []
        dilewati = []
        tujuan = petakan_nodeid([item.nodeid for item in items], self.total)
        for item in items:
            (terpilih if tujuan[item.nodeid] == self.shard else dilewati).append(item)
        if dilewati:
            config.hook.pytest_deselected(items=dilewati)
        items[:] = terpilih
        self.terpilih = len(terpilih)

    def pytest_collection_finish(self, session) -> None:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(
                f"Shard {self.shard}/{self.total}: "
                f"{self.terpilih} test terpilih"
            )
        if self.terpilih == 0:
            raise pytest.UsageError(f"Shard {self.shard}/{self.total} kosong")


class PencatatManifest:
    """Catat bukti mentah tanpa teks kegagalan, durasi, atau data fixture."""

    def __init__(self, shard: int, total: int, revision: str) -> None:
        self.data = {
            "schema_version": 1,
            "revision": revision,
            "shard": shard,
            "total": total,
            "collected": [],
            "selected": [],
            "reports": [],
            "collection_errors": [],
            "exitstatus": None,
        }

    def pytest_itemcollected(self, item) -> None:
        # Dicatat saat ditemukan, sebelum wrapper plugin lain bisa menyaringnya.
        self.data["collected"].append(item.nodeid)

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_collection_modifyitems(self, items):
        self.data["collected"].sort()
        yield
        self.data["selected"] = sorted(item.nodeid for item in items)

    def pytest_collectreport(self, report) -> None:
        if report.outcome != "passed":
            self.data["collection_errors"].append(
                {"nodeid": report.nodeid, "outcome": report.outcome}
            )

    def pytest_runtest_logreport(self, report) -> None:
        # Jangan deduplikasi: pengulangan eksekusi harus ditolak verifier.
        self.data["reports"].append({
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
            "wasxfail": hasattr(report, "wasxfail"),
        })

    def tulis(self, tujuan: Path, exitstatus: int) -> None:
        """Tulis atomik setelah pytest.main mengembalikan status sesi final."""
        self.data["exitstatus"] = int(exitstatus)
        sementara = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=tujuan.parent,
                prefix=".pytest-shard-", suffix=".tmp", delete=False,
            ) as berkas:
                sementara = Path(berkas.name)
                json.dump(self.data, berkas, ensure_ascii=True, indent=2)
                berkas.write("\n")
            os.replace(sementara, tujuan)
        finally:
            if sementara is not None:
                sementara.unlink(missing_ok=True)


def _parse_opsi(argv: Sequence[str]) -> argparse.Namespace:
    """Pisahkan opsi helper dari argumen pytest tanpa environment global."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--total", type=int, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--revision")
    parser.add_argument("argumen_pytest", nargs=argparse.REMAINDER)
    hasil = parser.parse_args(argv)
    if hasil.argumen_pytest[:1] == ["--"]:
        hasil.argumen_pytest = hasil.argumen_pytest[1:]
    if not hasil.argumen_pytest:
        parser.error("argumen pytest wajib diberikan setelah --")
    if hasil.total < 1 or not 1 <= hasil.shard <= hasil.total:
        parser.error("shard harus 1..total dan total minimal 1")
    if hasil.manifest is not None and (
        not hasil.revision or hasil.revision.strip() != hasil.revision
    ):
        parser.error("--manifest memerlukan --revision yang tidak kosong")
    return hasil


def parse_argumen(argv: Sequence[str]) -> Tuple[int, int, List[str]]:
    """Pertahankan kontrak tuple tiga elemen untuk pemanggil recovery lama."""
    hasil = _parse_opsi(argv)
    return hasil.shard, hasil.total, hasil.argumen_pytest


def main(argv: Optional[Sequence[str]] = None) -> int:
    hasil = _parse_opsi(sys.argv[1:] if argv is None else argv)
    plugins: List[object] = [PemilihShard(hasil.shard, hasil.total)]
    pencatat = None
    if hasil.manifest is not None:
        hasil.manifest.parent.mkdir(parents=True, exist_ok=True)
        # Sesi terputus tidak boleh meninggalkan bukti sukses dari run sebelumnya.
        hasil.manifest.unlink(missing_ok=True)
        pencatat = PencatatManifest(hasil.shard, hasil.total, hasil.revision)
        plugins.append(pencatat)
    status = pytest.main(hasil.argumen_pytest, plugins=plugins)
    if pencatat is not None and hasil.manifest is not None:
        pencatat.tulis(hasil.manifest, status)
    return int(status)


if __name__ == "__main__":
    raise SystemExit(main())
