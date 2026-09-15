#!/usr/bin/env python3
"""Bagi file pytest deterministik ke beberapa runner CI yang terisolasi."""

from __future__ import annotations

import argparse
import hashlib
import sys
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
                f"Recovery shard {self.shard}/{self.total}: "
                f"{self.terpilih} test terpilih"
            )
        if self.terpilih == 0:
            raise pytest.UsageError(
                f"Recovery shard {self.shard}/{self.total} kosong"
            )


def parse_argumen(argv: Sequence[str]) -> Tuple[int, int, List[str]]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--total", type=int, required=True)
    parser.add_argument("argumen_pytest", nargs=argparse.REMAINDER)
    hasil = parser.parse_args(argv)
    argumen_pytest = hasil.argumen_pytest
    if argumen_pytest[:1] == ["--"]:
        argumen_pytest = argumen_pytest[1:]
    if not argumen_pytest:
        parser.error("argumen pytest wajib diberikan setelah --")
    if hasil.total < 1 or not 1 <= hasil.shard <= hasil.total:
        parser.error("shard harus 1..total dan total minimal 1")
    return hasil.shard, hasil.total, argumen_pytest


def main(argv: Optional[Sequence[str]] = None) -> int:
    shard, total, argumen_pytest = parse_argumen(
        sys.argv[1:] if argv is None else argv
    )
    return pytest.main(argumen_pytest, plugins=[PemilihShard(shard, total)])


if __name__ == "__main__":
    raise SystemExit(main())
