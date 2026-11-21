#!/usr/bin/env python3
"""Pulihkan backup off-site `vps/<id>/` di Mac memakai kunci PRIVAT.

Urutan (gagal di langkah mana pun = berhenti, tidak ada yang didekripsi):
1. tujuan harus belum ada atau direktori kosong;
2. ambil `data.enc`, `kunci.enc`, `meta.json` (unduh dari R2, atau
   `--dari-direktori`); validasi ketat `meta.json`; cek ukuran + sha256;
3. buka sandi sesi dengan kunci privat (`openssl pkeyutl -decrypt`, RSA-OAEP
   SHA-256); kunci privat hanya sebagai PATH, tidak pernah isinya di argv. Bila
   kunci privat berpassphrase, openssl akan menanyakannya di terminal;
4. VERIFIKASI HMAC (`hmac.compare_digest`) SEBELUM dekripsi data;
5. dekripsi, ekstraksi tar aman (hanya berkas/direktori biasa, tanpa
   traversal/link/duplikat, tanpa `extractall`) ke direktori staging, validasi
   bundle dengan `backup_harian.validasi`, lalu rename atomik ke tujuan.

Contoh:
    pulihkan_offsite.py --id 20261121-214501 --env ~/.config/jagomat-offsite/r2-baca.env \
        --kunci-privat ~/jagomat-offsite-privat.pem --tujuan ~/pulih-20261121
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from typing import List, Optional

_DIR = str(Path(__file__).resolve().parent)
if _DIR not in sys.path:
    sys.path.append(_DIR)

import backup_harian  # noqa: E402
import backup_offsite_vps as sisi_vps  # noqa: E402  (hanya muat_env/_buat_klien)
import offsite_kripto as kripto  # noqa: E402
import r2_s3  # noqa: E402

BATAS_ENTRI = 10_000
BATAS_BYTE = 8 * 1024 * 1024 * 1024
BLOK = 1024 * 1024


def buat_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--id", required=True, help="id bundle, format YYYYMMDD-HHMMSS (WIB)")
    p.add_argument("--kunci-privat", required=True, help="path PEM kunci privat (hanya path)")
    p.add_argument("--tujuan", required=True, help="direktori baru/kosong")
    p.add_argument("--dari-direktori", help="direktori berisi tiga objek (tanpa unduh)")
    p.add_argument("--env", help="berkas env R2 (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
                                 "R2_SECRET_ACCESS_KEY, R2_BUCKET) untuk unduh")
    p.add_argument("--endpoint", help="timpa endpoint R2 (untuk tes)")
    p.add_argument("--tmp-dir")
    p.add_argument("--openssl", default="openssl")
    return p


def periksa_tujuan(tujuan: Path) -> None:
    if tujuan.is_symlink():
        raise kripto.GalatKripto("tujuan tidak boleh symlink")
    if tujuan.exists() and (not tujuan.is_dir() or any(tujuan.iterdir())):
        raise kripto.GalatKripto("tujuan harus belum ada atau direktori kosong")


def sediakan_objek(a, kerja: Path) -> Path:
    if a.dari_direktori:
        return Path(a.dari_direktori)
    if not a.env:
        raise kripto.GalatKripto("beri --dari-direktori atau --env untuk mengunduh")
    kredensial = sisi_vps.muat_env(a.env, lewati_pemilik=True)
    klien = sisi_vps._buat_klien(a, kredensial)
    unduhan = kerja / "unduhan"
    unduhan.mkdir(mode=0o700)
    for nama in kripto.NAMA_OBJEK:
        klien.ambil_objek(f"{kripto.PREFIKS}{a.id}/{nama}", unduhan / nama)
    return unduhan


def baca_objek(direktori: Path, id_bundle: str) -> dict:
    for nama in kripto.NAMA_OBJEK:
        if not (direktori / nama).is_file():
            raise kripto.GalatKripto(f"objek tidak ada: {nama}")
    try:
        meta = json.loads((direktori / "meta.json").read_text(encoding="utf-8"))
    except (ValueError, OSError) as galat:
        raise kripto.GalatKripto("meta.json tidak terbaca") from galat
    return kripto.periksa_meta(meta, id_bundle)


def periksa_ciphertext(data: Path, meta: dict) -> None:
    if data.stat().st_size != meta["ukuran"]:
        raise kripto.GalatKripto("ukuran data.enc tidak cocok dengan meta (rusak)")
    if not hmac.compare_digest(kripto.sha256_berkas(data), meta["sha256"]):
        raise kripto.GalatKripto("sha256 data.enc tidak cocok dengan meta (rusak)")


def buka_sandi(openssl: str, kunci_privat: Path, kunci_enc: Path) -> str:
    try:
        keluar = kripto.jalankan_openssl(openssl, [
            "pkeyutl", "-decrypt", "-inkey", str(kunci_privat),
            "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
            "-pkeyopt", "rsa_mgf1_md:sha256", "-in", str(kunci_enc)], ambil_keluaran=True)
    except kripto.GalatKripto as galat:
        raise kripto.GalatKripto(
            "sandi sesi tidak bisa dibuka (kunci privat salah atau kunci.enc rusak)") from galat
    sandi = keluar.decode("ascii", "replace").strip()
    if not kripto.POLA_HEX.fullmatch(sandi):
        raise kripto.GalatKripto("sandi sesi hasil buka tidak berformat sah")
    return sandi


def verifikasi_mac(sandi: str, meta: dict, data: Path) -> None:
    hitung = kripto.hitung_mac(sandi, meta["id"], data)
    if not hmac.compare_digest(hitung, meta["mac"]):
        raise kripto.GalatKripto("MAC tidak cocok: data/kunci dirusak atau dipalsukan; tidak didekripsi")


def dekripsi_data(openssl: str, berkas_sandi: Path, data: Path, keluar: Path) -> None:
    kripto.jalankan_openssl(openssl, [
        "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", str(kripto.ITERASI), "-md", "sha256",
        "-pass", f"file:{berkas_sandi}", "-in", str(data), "-out", str(keluar)])


def _bagian_aman(nama: str, id_bundle: str) -> tuple:
    bagian = tuple(nama.split("/"))
    if (nama.startswith("/") or "\\" in nama or bagian[0] != id_bundle
            or any(b in ("", ".", "..") for b in bagian)):
        raise kripto.GalatKripto("tar tidak aman: nama entri tidak sah")
    return bagian


def periksa_anggota(anggota, id_bundle: str) -> None:
    if len(anggota) > BATAS_ENTRI:
        raise kripto.GalatKripto("tar tidak aman: terlalu banyak entri")
    terlihat, total = set(), 0
    for m in anggota:
        bagian = _bagian_aman(m.name, id_bundle)
        if not (m.isfile() or m.isdir()) or bagian in terlihat:
            raise kripto.GalatKripto("tar tidak aman: jenis entri tidak diizinkan atau duplikat")
        terlihat.add(bagian)
        total += m.size
    if total > BATAS_BYTE:
        raise kripto.GalatKripto("tar tidak aman: ukuran total melebihi batas")


def ekstrak_aman(tar_path: Path, tujuan: Path, id_bundle: str) -> None:
    try:
        with tarfile.open(str(tar_path), "r:gz") as tar:
            anggota = tar.getmembers()
            periksa_anggota(anggota, id_bundle)
            for m in anggota:
                sasaran = tujuan.joinpath(*m.name.split("/"))
                if m.isdir():
                    sasaran.mkdir(parents=True, exist_ok=True)
                    continue
                sasaran.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(m) as sumber, open(sasaran, "xb") as keluar:
                    shutil.copyfileobj(sumber, keluar, BLOK)
                os.chmod(sasaran, 0o600)
    except (tarfile.TarError, EOFError, OSError) as galat:
        raise kripto.GalatKripto(f"tar tidak bisa dibaca/diekstrak: {type(galat).__name__}") from galat


def _validasi_hasil(akar: Path, id_bundle: str) -> None:
    try:
        manifest = backup_harian.validasi(akar / id_bundle)
    except (OSError, ValueError, KeyError, sqlite3.Error) as galat:
        raise kripto.GalatKripto(f"validasi bundle hasil pulih gagal: {type(galat).__name__}") from galat
    if manifest["id"] != id_bundle:
        raise kripto.GalatKripto("validasi bundle hasil pulih gagal: id manifest berbeda")


def pulihkan(a) -> dict:
    tujuan = Path(a.tujuan)
    periksa_tujuan(tujuan)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    kerja = Path(tempfile.mkdtemp(prefix="pulihkan-", dir=a.tmp_dir))
    staging = Path(tempfile.mkdtemp(prefix=".pulihkan-", dir=str(tujuan.parent)))
    try:
        objek = sediakan_objek(a, kerja)
        meta = baca_objek(objek, a.id)
        periksa_ciphertext(objek / "data.enc", meta)
        sandi = buka_sandi(a.openssl, Path(a.kunci_privat), objek / "kunci.enc")
        verifikasi_mac(sandi, meta, objek / "data.enc")
        berkas_sandi = kripto.tulis_privat(kerja, "sandi.sesi", sandi.encode("ascii"))
        tar = kerja / "bundle.tar.gz"
        dekripsi_data(a.openssl, berkas_sandi, objek / "data.enc", tar)
        ekstrak_aman(tar, staging, a.id)
        _validasi_hasil(staging, a.id)
        os.replace(staging, tujuan)
    finally:
        shutil.rmtree(kerja, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)
    jumlah = sum(1 for p in (tujuan / a.id).rglob("*") if p.is_file())
    return {"id": a.id, "tujuan": str(tujuan), "berkas": jumlah, "ok": True}


def main(argv: Optional[List[str]] = None) -> int:
    a = buat_parser().parse_args(argv)
    try:
        print(json.dumps(pulihkan(a), sort_keys=True))
        return 0
    except (kripto.GalatKripto, sisi_vps.GalatOffsite, r2_s3.GalatS3, ValueError, OSError) as galat:
        print(f"galat: {galat}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
