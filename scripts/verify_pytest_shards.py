#!/usr/bin/env python3
"""Palang agregat manifest pytest: koleksi sama, partisi utuh, semua fase lulus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

from pytest_shard import shard_untuk_nodeid


_KUNCI_MANIFEST = {
    "schema_version", "revision", "shard", "total", "collected", "selected",
    "reports", "collection_errors", "exitstatus",
}
_KUNCI_LAPORAN = {"nodeid", "when", "outcome", "wasxfail"}
_FASE = ["setup", "call", "teardown"]


def _wajib(syarat: bool, pesan: str) -> None:
    if not syarat:
        raise ValueError(pesan)


def _objek_unik(pasangan):
    """JSON dengan kunci ganda tidak memiliki interpretasi yang aman."""
    hasil = {}
    for kunci, nilai in pasangan:
        _wajib(kunci not in hasil, "Kunci JSON ganda")
        hasil[kunci] = nilai
    return hasil


def _konstanta_tidak_sah(nilai):
    raise ValueError("Konstanta JSON tidak sah")


def _nodeids(nilai: Any, nama: str) -> List[str]:
    _wajib(type(nilai) is list and bool(nilai), f"{nama} wajib daftar tidak kosong")
    _wajib(all(type(nodeid) is str and bool(nodeid) for nodeid in nilai),
           f"{nama} berisi nodeid tidak sah")
    _wajib(len(nilai) == len(set(nilai)), f"{nama} berisi nodeid ganda")
    _wajib(nilai == sorted(nilai), f"{nama} harus terurut")
    return nilai


def _periksa_manifest(data: Any, total: int, revision: str) -> Tuple[List[str], List[str]]:
    _wajib(type(data) is dict and set(data) == _KUNCI_MANIFEST,
           "Struktur manifest tidak sah")
    data = cast(Dict[str, Any], data)
    for kunci in ("schema_version", "shard", "total", "exitstatus"):
        _wajib(type(data[kunci]) is int, f"{kunci} harus integer")
    _wajib(data["schema_version"] == 1, "Versi manifest tidak didukung")
    _wajib(type(data["revision"]) is str and data["revision"] == revision,
           "Revision manifest berbeda")
    _wajib(data["total"] == total, "Total shard manifest berbeda")
    _wajib(1 <= data["shard"] <= total, "Nomor shard di luar rentang")
    _wajib(data["exitstatus"] == 0, "Sesi pytest tidak sukses")
    _wajib(type(data["collection_errors"]) is list and not data["collection_errors"],
           "Koleksi gagal atau dilewati")
    koleksi = _nodeids(data["collected"], "collected")
    terpilih = _nodeids(data["selected"], "selected")
    kanonis = [nodeid for nodeid in koleksi
               if shard_untuk_nodeid(nodeid, total) == data["shard"]]
    _wajib(terpilih == kanonis, "Pemilihan tidak sesuai partisi hash kanonis")
    laporan = data["reports"]
    _wajib(type(laporan) is list, "reports harus daftar")
    _wajib(len(laporan) == 3 * len(terpilih), "Jumlah laporan fase tidak lengkap")
    fase = {nodeid: [] for nodeid in terpilih}
    for entri in laporan:
        _wajib(type(entri) is dict and set(entri) == _KUNCI_LAPORAN,
               "Struktur laporan fase tidak sah")
        entri = cast(Dict[str, Any], entri)
        _wajib(type(entri["nodeid"]) is str and entri["nodeid"] in fase,
               "Laporan memuat nodeid di luar pilihan")
        _wajib(type(entri["when"]) is str and entri["when"] in _FASE,
               "Fase laporan tidak sah")
        _wajib(type(entri["outcome"]) is str and entri["outcome"] == "passed",
               "Fase test gagal atau dilewati")
        _wajib(type(entri["wasxfail"]) is bool and not entri["wasxfail"],
               "Test xfail/xpass atau penanda tidak sah")
        fase[entri["nodeid"]].append(entri["when"])
    _wajib(all(urutan == _FASE for urutan in fase.values()),
           "Fase test hilang, ganda, atau tidak berurutan")
    return koleksi, terpilih


def verifikasi_manifest(direktori: Path, total: int, revision: str) -> int:
    """Tolak semua bukti tidak lengkap; kembalikan jumlah test exact-once."""
    _wajib(type(total) is int and total > 0, "Total shard minimal 1")
    _wajib(type(revision) is str and bool(revision) and revision.strip() == revision,
           "Revision wajib tidak kosong")
    _wajib(direktori.is_dir(), "Direktori manifest tidak ditemukan")
    berkas = sorted(direktori.iterdir())
    _wajib(len(berkas) == total, "Jumlah berkas manifest tidak sesuai total shard")
    _wajib(all(path.is_file() and not path.is_symlink() and path.suffix == ".json"
               for path in berkas), "Direktori hanya boleh berisi manifest JSON reguler")
    koleksi_acuan = None
    shard_ditemukan = set()
    semua_terpilih = set()
    for path in berkas:
        try:
            data = json.loads(path.read_text(encoding="utf-8"),
                              object_pairs_hook=_objek_unik,
                              parse_constant=_konstanta_tidak_sah)
            koleksi, terpilih = _periksa_manifest(data, total, revision)
        except (ValueError, OSError, RecursionError) as kesalahan:
            raise ValueError(f"Manifest {path.name} ditolak: {kesalahan}") from kesalahan
        _wajib(data["shard"] not in shard_ditemukan, "Nomor shard ganda")
        shard_ditemukan.add(data["shard"])
        if koleksi_acuan is None:
            koleksi_acuan = koleksi
        _wajib(koleksi == koleksi_acuan, "Koleksi lengkap antar-shard berbeda")
        _wajib(semua_terpilih.isdisjoint(terpilih), "Nodeid dieksekusi lintas shard")
        semua_terpilih.update(terpilih)
    _wajib(shard_ditemukan == set(range(1, total + 1)), "Nomor shard tidak lengkap")
    _wajib(semua_terpilih == set(koleksi_acuan or []), "Union pilihan tidak lengkap")
    return len(semua_terpilih)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--total", type=int, required=True)
    parser.add_argument("--revision", required=True)
    hasil = parser.parse_args(argv)
    try:
        jumlah = verifikasi_manifest(hasil.directory, hasil.total, hasil.revision)
    except (ValueError, OSError, RecursionError) as kesalahan:
        print(f"Verifikasi shard gagal: {kesalahan}", file=sys.stderr)
        return 1
    print(f"Verifikasi shard lulus: {hasil.total} shard, {jumlah} test exact-once.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
