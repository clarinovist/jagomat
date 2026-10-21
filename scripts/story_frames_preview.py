#!/usr/bin/env python3
"""Ekspor contoh bank kalimat sintetis+manifest untuk review offline, tanpa DB/API."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "mesin"))
from story_frames import BANK, VERSI_BANK, kalimat_baru, validasi_bank

CONTOH = {"kpk_dua_bilangan": {"a": 6, "b": 8}, "aturan_kali": {"m": 3, "n": 4}, "jabat_tangan": {"n": 5}}


def ekspor(tujuan: Path):
    validasi_bank(BANK)
    # Snapshot konten, bukan identitas per-row dalam database aplikasi.
    bank = {tid: [asdict(b) for b in rows] for tid, rows in BANK.items()}
    serial = json.dumps(bank, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    contoh = [dict(template_id=tid, **asdict(kalimat_baru(tid, "P5", p, nomor=n)))
              for tid, p in CONTOH.items() for n in range(len(BANK[tid]))]
    sha = subprocess.check_output(["git", "-C", str(AKAR), "rev-parse", "HEAD"], text=True).strip()
    tracked = subprocess.run(["git", "-C", str(AKAR), "ls-files", "--error-unmatch", "mesin/story_frames.py"],
                             capture_output=True, text=True, check=False)
    diff = subprocess.run(["git", "-C", str(AKAR), "diff", "--quiet", "HEAD", "--", "mesin/story_frames.py"], check=False)
    if tracked.returncode not in (0, 1) or diff.returncode not in (0, 1):
        raise RuntimeError("status provenance Git tidak dapat diperiksa")
    manifest = {"bank_versi": VERSI_BANK, "konten_sha256": hashlib.sha256(serial.encode()).hexdigest(),
                "source_sha": sha, "bank_sesuai_commit": tracked.returncode == diff.returncode == 0,
                "status": "menunggu_tinjauan_manusia", "bank": bank, "contoh": contoh}
    tujuan.mkdir(parents=True, exist_ok=False)
    (tujuan / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    isi = "".join('<li><h2>' + html.escape(c['bingkai_id']) + '</h2><p>' + html.escape(c['teks']) + '</p></li>' for c in contoh)
    halaman = ('<!doctype html><html lang="id"><meta charset="utf-8"><title>Tinjauan bank kalimat</title>'
               '<h1>18 contoh bank kalimat — draf tinjauan</h1><p>Bukan lembar anak atau hasil penilaian. '
               'Periksa makna, satuan, asumsi dan bahasa. Kunci/malrule tetap milik template.</p><ol>' + isi + '</ol></html>')
    (tujuan / "tinjauan.html").write_text(halaman)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-committed", action="store_true")
    args = parser.parse_args()
    manifest = ekspor(args.output)
    if args.require_committed and not manifest["bank_sesuai_commit"]:
        raise SystemExit("Bank kalimat tidak cocok dengan commit rilis.")
    print(json.dumps({"output": str(args.output.resolve()), "bank_versi": manifest['bank_versi'],
                      "bank_sesuai_commit": manifest['bank_sesuai_commit'], "jumlah_contoh": len(manifest['contoh'])}))


if __name__ == "__main__":
    main()
