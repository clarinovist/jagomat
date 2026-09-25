#!/usr/bin/env python3
"""Metadata build-only dan kelayakan pasangan image, bukan approval deploy VPS."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re


def _modul(nama):
    spek = importlib.util.spec_from_file_location(nama, Path(__file__).with_name(nama + ".py"))
    modul = importlib.util.module_from_spec(spek)
    spek.loader.exec_module(modul)
    return modul


deploy = _modul("deploy")
verify_release_image = _modul("verify_release_image")
MODE = frozenset(("persiapan", "migrasi", "rutin"))
GATE_RUTIN = "needs.bangun.outputs.siap_pasang == 'true' && vars.OSN_DEPLOY_RUTIN_SIAP == '1' && github.ref == 'refs/heads/main'"


def _hex(nilai, panjang):
    return type(nilai) is str and re.fullmatch(r"[0-9a-f]{" + str(panjang) + "}", nilai) is not None


def _digest(nilai):
    return type(nilai) is str and nilai.startswith("sha256:") and _hex(nilai[7:], 64)


def validasi_config(data):
    """Konfigurasi tertutup; mode tidak dikenal tidak pernah menjadi rutin."""
    if (type(data) is not dict
            or set(data) != {"versi", "mode", "recovery_revision", "recovery_contract"}
            or type(data["versi"]) is not int or data["versi"] != 1
            or type(data["mode"]) is not str or data["mode"] not in MODE
            or not _hex(data["recovery_revision"], 40)
            or not _hex(data["recovery_contract"], 64)):
        raise ValueError("Konfigurasi rilis tidak sah.")
    return dict(data)


def _tanpa_duplikat(pasangan):
    hasil = {}
    for nama, nilai in pasangan:
        if nama in hasil:
            raise ValueError("Field rilis duplikat.")
        hasil[nama] = nilai
    return hasil


def baca_config(path):
    return validasi_config(json.loads(Path(path).read_text(), object_pairs_hook=_tanpa_duplikat))


def buat_manifest(config, kandidat, recovery, *, pasangan_teruji=False):
    """Hitung readiness dari pasangan yang diperiksa, bukan boolean input caller."""
    config = validasi_config(config)
    for item in (kandidat, recovery):
        if (type(item) is not dict or set(item) != {"revision", "digest", "contract"}
                or not _hex(item["revision"], 40) or not _digest(item["digest"])
                or not _hex(item["contract"], 64)):
            raise ValueError("Identitas artefak tidak sah.")
    if (recovery["revision"] != config["recovery_revision"]
            or recovery["contract"] != config["recovery_contract"]
            or kandidat["revision"] == recovery["revision"]
            or kandidat["digest"] == recovery["digest"]):
        raise ValueError("Artefak tidak cocok dengan anchor recovery.")
    kompatibel = kandidat["contract"] == recovery["contract"]
    if type(pasangan_teruji) is not bool or (config["mode"] == "persiapan" and pasangan_teruji):
        raise ValueError("Bukti pasangan tidak cocok dengan mode.")
    if config["mode"] != "persiapan" and (not kompatibel or not pasangan_teruji):
        raise ValueError("Pasangan belum kompatibel/teruji; pemasangan ditahan.")
    return {
        "versi": 1, "mode": config["mode"],
        **{"candidate_" + k: v for k, v in kandidat.items()},
        **{"recovery_" + k: v for k, v in recovery.items()},
        "compatible": kompatibel,
        "pair_verified": pasangan_teruji,
        "siap_pasang": config["mode"] == "rutin" and kompatibel and pasangan_teruji,
        "requires_controlled_migration": config["mode"] == "migrasi",
    }


def validasi_workflow(teks, config):
    """Periksa subset workflow yang dipatok; bukan parser YAML serbaguna."""
    config = validasi_config(config)
    cocok = re.findall(r"^  pasang:\n(.*?)(?=^  [a-z_]+:\n|\Z)", teks, re.M | re.S)
    if len(cocok) != 1:
        raise ValueError("Job pasang harus tunggal.")
    job = cocok[0]
    kondisi = re.findall(r"^    if: (.*)$", job, re.M)
    harapan = GATE_RUTIN if config["mode"] == "rutin" else "false"
    if kondisi != ["${{ " + harapan + " }}"] or re.findall(r"^    needs: (.+)$", job, re.M) != ["bangun"]:
        raise ValueError("Gate pemasangan tidak cocok dengan mode rilis.")
    revision = config["recovery_revision"]
    if (re.findall(r"^  RECOVERY_SHA: ([0-9a-f]{40})$", teks, re.M) != [revision]
            or re.findall(r"^          ref: ([0-9a-f]{40})$", teks, re.M) != [revision, revision]):
        raise ValueError("Checkout recovery tidak cocok dengan konfigurasi.")
    # Secret SSH tetap hanya dalam job yang dipagari; bukan build/test/summary.
    sebelum = teks.split("  pasang:\n", 1)[0]
    if "secrets.VPS_" in sebelum:
        raise ValueError("Credential produksi berada di luar job pasang.")
    return config


def validasi_bukti_pasangan(data, kandidat, recovery, digest_kandidat, digest_recovery):
    """Bukti helper pair terikat revision DAN digest; bukan approval operator."""
    harapan = {"ok": True, "candidate_revision": kandidat, "recovery_revision": recovery,
               "candidate_digest": digest_kandidat, "recovery_digest": digest_recovery,
               "pengiriman_pair_checks": 6, "pilihan_pair_checks": 8, "learning_pair_checks": 8, "subscription_pair_checks": 4, "admin_launch_pair_checks": 4, "provider_calls": 0}
    if (type(data) is not dict or data != harapan
            or any(type(data[k]) is not type(v) for k, v in harapan.items())):
        raise ValueError("Bukti lintas image tidak sah.")
    return True


def probe_artefak(digest, revision):
    """Verifikasi image digest exact, lalu fingerprint source dalam sandbox tanpa data."""
    if not _digest(digest) or not _hex(revision, 40):
        raise ValueError("Identitas image tidak sah.")
    image = verify_release_image.REPOSITORI + "@" + digest
    verify_release_image.verifikasi(image, revision)
    # Docker.kontrak_image menerima imageID, bukan manifest digest. Resolve ID
    # dari inspect immutable reference yang sama; jangan jalankan image lain.
    docker = deploy.Docker()
    identitas = docker._panggil(["image", "inspect", "--format", "{{.Id}}", image])
    if not _digest(identitas):
        raise ValueError("Identitas image hasil inspect tidak sah.")
    kontrak = docker.kontrak_image(identitas)
    if not _hex(kontrak, 64):
        raise ValueError("Fingerprint image tidak sah.")
    return {"revision": revision, "digest": digest, "contract": kontrak}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--config", default=str(Path(__file__).with_name("release-metadata.json")))
    parser.add_argument("--workflow", default=str(Path(__file__).resolve().parents[1] / ".github/workflows/deploy.yml"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--pair-proof")
    for nama in ("candidate-revision", "candidate-digest", "recovery-revision", "recovery-digest"):
        parser.add_argument("--" + nama)
    args = parser.parse_args(argv)
    try:
        config = baca_config(args.config)
        validasi_workflow(Path(args.workflow).read_text(), config)
        if args.check:
            if args.output or args.pair_proof or any((args.candidate_revision, args.candidate_digest, args.recovery_revision, args.recovery_digest)):
                raise ValueError("Argumen pemeriksaan tidak sah.")
            print(json.dumps({"ok": True, "mode": config["mode"], "gate": "tervalidasi"}))
            return 0
        if not args.output or args.recovery_revision != config["recovery_revision"]:
            raise ValueError("Argumen manifest tidak sah.")
        if Path(args.output).exists():
            raise ValueError("Manifest lama tidak boleh dipakai ulang atau ditimpa.")
        pasangan_teruji = False
        if config["mode"] == "persiapan":
            if args.pair_proof:
                raise ValueError("Persiapan tidak mengklaim bukti pasangan.")
        else:
            if not args.pair_proof:
                raise ValueError("Bukti pasangan wajib untuk migrasi/rutin.")
            bukti = json.loads(Path(args.pair_proof).read_text(), object_pairs_hook=_tanpa_duplikat)
            pasangan_teruji = validasi_bukti_pasangan(
                bukti, args.candidate_revision, args.recovery_revision,
                args.candidate_digest, args.recovery_digest)
        kandidat = probe_artefak(args.candidate_digest, args.candidate_revision)
        recovery = probe_artefak(args.recovery_digest, args.recovery_revision)
        hasil = buat_manifest(config, kandidat, recovery, pasangan_teruji=pasangan_teruji)
        with Path(args.output).open("x") as tujuan:
            tujuan.write(json.dumps(hasil, indent=2) + "\n")
        print(json.dumps({"ok": True, "mode": hasil["mode"], "compatible": hasil["compatible"], "siap_pasang": hasil["siap_pasang"]}))
        return 0
    except (Exception, KeyboardInterrupt):
        # Jangan mengeluarkan traceback/hasil Docker, konfigurasi, atau data probe.
        print(json.dumps({"ok": False, "kode": "metadata_rilis_ditolak"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
