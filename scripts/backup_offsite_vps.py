#!/usr/bin/env python3
"""Off-site backup dari VPS ke Cloudflare R2, dienkripsi hibrida dengan kunci PUBLIK.

Dijalankan root di VPS oleh cron terpisah setelah backup harian, contoh baris
yang DIUSULKAN (belum dipasang):

    0 22 * * * root /usr/bin/python3 /opt/osn/backup-harian/backup_offsite_vps.py \
        >> /opt/osn/log/offsite-vps.log 2>&1

Berkas `backup_offsite_vps.py`, `offsite_kripto.py`, `r2_s3.py`, dan
`backup_harian.py` harus dipasang berdampingan di /opt/osn/backup-harian/.

Alur: pilih bundle terbaru -> tolak bila basi atau tak lolos `validasi` ->
tar.gz -> enkripsi AES-256 dengan sandi sesi acak -> sandi sesi dibungkus
RSA-OAEP memakai kunci publik -> HMAC -> unggah ke `vps/<id>/` -> verifikasi
(List, ukuran sama) -> retensi `vps/` -> tulis penanda -> satu baris JSON. Skrip ini TIDAK
punya kode atau argumen untuk kunci privat, dan tidak pernah menaruh rahasia
di argv/env. Detail format: lihat `offsite_kripto.py`.

Keluar: 0 sukses; 1 gagal; 3 set baru terunggah dan terverifikasi tetapi
retensi gagal. Pada kode non-nol penanda lama tidak diubah.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import tarfile
import tempfile
import time
from typing import Dict, List, Optional

_DIR = str(Path(__file__).resolve().parent)
if _DIR not in sys.path:
    sys.path.append(_DIR)

import backup_harian  # noqa: E402
import offsite_kripto as kripto  # noqa: E402
import r2_s3  # noqa: E402

WIB = dt.timezone(dt.timedelta(hours=7))
UMUR_MAKS_JAM = 26.0
RETENSI_HARI = 30
KUNCI_ENV = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
MODE_LONGGAR = 0o177  # bit selain rw pemilik (maks 0600)
POLA_KUNCI_OBJEK = re.compile(r"^vps/(\d{8}-\d{6})/(data\.enc|kunci\.enc|meta\.json)$")
POLA_AKUN = re.compile(r"^[A-Za-z0-9]{1,64}$")
KODE_RETENSI_GAGAL = 3


class GalatOffsite(Exception):
    """Galat alur off-site; pesan tanpa rahasia."""


class GalatKonfigurasi(GalatOffsite):
    pass


def buat_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bundle-dir", default="/opt/osn/backup-harian")
    p.add_argument("--env", default="/etc/osn/offsite-r2.env")
    p.add_argument("--kunci-publik", default="/etc/osn/offsite-publik.pem")
    p.add_argument("--penanda", default="/opt/osn/log/offsite-vps.last-ok")
    p.add_argument("--umur-maks-jam", type=float, default=UMUR_MAKS_JAM)
    p.add_argument("--retensi-hari", type=int, default=RETENSI_HARI)
    p.add_argument("--endpoint", help="timpa endpoint R2 (untuk tes)")
    p.add_argument("--tmp-dir", help="induk direktori kerja sementara (bawaan: tmp sistem)")
    p.add_argument("--openssl", default="openssl")
    p.add_argument("--uji-lewati-pemilik-env", action="store_true",
                   help="HANYA untuk tes: lewati cek pemilik root (cek mode tetap berlaku)")
    return p


def urai_env(teks: str) -> Dict[str, str]:
    nilai = {}
    for baris in teks.splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        kunci, _, isi = baris.partition("=")
        nilai[kunci.strip()] = isi.strip().strip("'\"")
    return nilai


def muat_env(path, *, lewati_pemilik: bool = False) -> Dict[str, str]:
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as galat:
        raise GalatKonfigurasi("berkas env tidak bisa dibuka (tidak ada atau symlink)") from galat
    with os.fdopen(fd, "r", encoding="utf-8") as berkas:
        info = os.fstat(berkas.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise GalatKonfigurasi("berkas env bukan berkas biasa")
        if not lewati_pemilik and info.st_uid != 0:
            raise GalatKonfigurasi("berkas env harus milik root")
        if info.st_mode & MODE_LONGGAR:
            raise GalatKonfigurasi("mode berkas env terlalu longgar (maksimal 0600)")
        nilai = urai_env(berkas.read())
    kosong = [k for k in KUNCI_ENV if not nilai.get(k)]
    if kosong:
        raise GalatKonfigurasi("kunci env kosong atau tidak ada: " + ", ".join(kosong))
    if not POLA_AKUN.match(nilai["R2_ACCOUNT_ID"]):
        raise GalatKonfigurasi("R2_ACCOUNT_ID tidak sah")
    return {k: nilai[k] for k in KUNCI_ENV}


def periksa_kunci_publik(path) -> None:
    try:
        teks = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as galat:
        raise GalatKonfigurasi("kunci publik tidak terbaca") from galat
    if "PRIVATE KEY" in teks:
        raise GalatKonfigurasi("berkas kunci publik ternyata kunci privat; ditolak")
    if "-----BEGIN PUBLIC KEY-----" not in teks:
        raise GalatKonfigurasi("berkas bukan PEM kunci publik")


def epoch_id(id_bundle: str) -> float:
    waktu = dt.datetime.strptime(id_bundle, "%Y%m%d-%H%M%S").replace(tzinfo=WIB)
    return waktu.timestamp()


def pilih_bundle(akar: Path) -> Path:
    try:
        kandidat = sorted((p for p in akar.iterdir() if p.is_dir() and not p.is_symlink()
                           and kripto.POLA_ID.fullmatch(p.name)), key=lambda p: p.name)
    except OSError as galat:
        raise GalatOffsite("direktori bundle tidak terbaca") from galat
    if not kandidat:
        raise GalatOffsite("tidak ada bundle backup harian")
    return kandidat[-1]


def periksa_umur(id_bundle: str, sekarang: float, umur_maks_jam: float) -> None:
    umur_jam = (sekarang - epoch_id(id_bundle)) / 3600
    if umur_jam > umur_maks_jam:
        raise GalatOffsite(f"bundle {id_bundle} lebih tua dari {umur_maks_jam:g} jam")


def validasi_bundle(bundle: Path) -> None:
    try:
        manifest = backup_harian.validasi(bundle)
    except (OSError, ValueError, KeyError, sqlite3.Error) as galat:
        raise GalatOffsite(f"validasi bundle gagal: {type(galat).__name__}") from galat
    if manifest["id"] != bundle.name:
        raise GalatOffsite("validasi bundle gagal: id manifest berbeda dari nama direktori")


def buat_tar(bundle: Path, tujuan: Path) -> None:
    """Tar.gz hanya berkas/direktori biasa; symlink atau perangkat ditolak."""
    with tarfile.open(str(tujuan), "w:gz") as tar:
        for path in [bundle, *sorted(bundle.rglob("*"))]:
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise GalatOffsite("bundle memuat entri bukan berkas biasa")
            info = tar.gettarinfo(str(path), arcname=f"{bundle.name}/{path.relative_to(bundle)}"
                                  if path != bundle else bundle.name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            if path.is_file():
                with path.open("rb") as isi:
                    tar.addfile(info, isi)
            else:
                tar.addfile(info)


def enkripsi_paket(openssl: str, publik: Path, bundle: Path, kerja: Path) -> Dict[str, Path]:
    tar, data, kunci = kerja / "bundle.tar.gz", kerja / "data.enc", kerja / "kunci.enc"
    buat_tar(bundle, tar)
    sandi = kripto.bangkitkan_sandi()
    berkas_sandi = kripto.tulis_privat(kerja, "sandi.sesi", sandi.encode("ascii"))
    kripto.jalankan_openssl(openssl, [
        "enc", "-aes-256-cbc", "-pbkdf2", "-iter", str(kripto.ITERASI), "-md", "sha256",
        "-salt", "-pass", f"file:{berkas_sandi}", "-in", str(tar), "-out", str(data)])
    tar.unlink()
    kripto.jalankan_openssl(openssl, [
        "pkeyutl", "-encrypt", "-pubin", "-inkey", str(publik),
        "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
        "-pkeyopt", "rsa_mgf1_md:sha256", "-in", str(berkas_sandi), "-out", str(kunci)])
    meta = kripto.bangun_meta(bundle.name, data.stat().st_size, kripto.sha256_berkas(data),
                              kripto.hitung_mac(sandi, bundle.name, data))
    berkas_meta = kripto.tulis_privat(kerja, "meta.json",
                                      (json.dumps(meta, sort_keys=True) + "\n").encode("utf-8"))
    berkas_sandi.unlink()
    return {"data.enc": data, "kunci.enc": kunci, "meta.json": berkas_meta}


def unggah_dan_verifikasi(klien, id_bundle: str, berkas: Dict[str, Path]) -> None:
    for nama in kripto.NAMA_OBJEK:  # meta.json terakhir: penanda set lengkap
        klien.put_objek(f"{kripto.PREFIKS}{id_bundle}/{nama}", berkas[nama])
    ada = {o.kunci: o.ukuran for o in klien.daftar_objek(f"{kripto.PREFIKS}{id_bundle}/")}
    for nama in kripto.NAMA_OBJEK:
        if ada.get(f"{kripto.PREFIKS}{id_bundle}/{nama}") != berkas[nama].stat().st_size:
            raise GalatOffsite(f"verifikasi unggahan gagal: {nama}")


def kunci_kedaluwarsa(objek, batas: float, id_baru: str) -> List[str]:
    """Kunci milik set `vps/<id>/` yang seluruh objeknya lebih tua dari `batas`."""
    kelompok: Dict[str, list] = {}
    for item in objek:
        cocok = POLA_KUNCI_OBJEK.match(item.kunci)
        if cocok and item.kunci.startswith(kripto.PREFIKS):
            kelompok.setdefault(cocok.group(1), []).append(item)
    hapus = []
    for id_set, isi in kelompok.items():
        if id_set != id_baru and max(o.diubah for o in isi) < batas:
            hapus.extend(o.kunci for o in isi)
    return sorted(hapus)


def terapkan_retensi(klien, id_baru: str, sekarang: float, hari: int) -> int:
    objek = klien.daftar_objek(kripto.PREFIKS)
    hapus = kunci_kedaluwarsa(objek, sekarang - hari * 86400, id_baru)
    for kunci in hapus:
        klien.hapus_objek(kunci)
    return len(hapus)


def tulis_penanda(path: Path, id_bundle: str, sekarang: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sementara = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    sementara.write_text(f"{backup_harian._stempel(int(sekarang))} {id_bundle}\n", encoding="utf-8")
    os.replace(sementara, path)


def _buat_klien(a, kredensial) -> r2_s3.KlienR2:
    endpoint = a.endpoint or f"https://{kredensial['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    return r2_s3.KlienR2(endpoint, kredensial["R2_BUCKET"], kredensial["R2_ACCESS_KEY_ID"],
                         kredensial["R2_SECRET_ACCESS_KEY"])


def _proses(a, rahasia: List[str]) -> int:
    if a.retensi_hari < 1:
        raise GalatOffsite("retensi-hari minimal 1")
    kredensial = muat_env(a.env, lewati_pemilik=a.uji_lewati_pemilik_env)
    rahasia.extend(kredensial.values())
    periksa_kunci_publik(a.kunci_publik)
    sekarang = time.time()
    bundle = pilih_bundle(Path(a.bundle_dir))
    periksa_umur(bundle.name, sekarang, a.umur_maks_jam)
    validasi_bundle(bundle)
    klien = _buat_klien(a, kredensial)
    kerja = Path(tempfile.mkdtemp(prefix="offsite-", dir=a.tmp_dir))
    try:
        berkas = enkripsi_paket(a.openssl, Path(a.kunci_publik), bundle, kerja)
        unggah_dan_verifikasi(klien, bundle.name, berkas)
        ukuran = berkas["data.enc"].stat().st_size
    finally:
        shutil.rmtree(kerja, ignore_errors=True)
    try:
        terhapus = terapkan_retensi(klien, bundle.name, sekarang, a.retensi_hari)
    except r2_s3.GalatS3 as galat:
        print("galat: set baru terunggah dan terverifikasi, tetapi retensi gagal "
              "(penanda tidak diubah): " + _samarkan(str(galat), rahasia), file=sys.stderr)
        return KODE_RETENSI_GAGAL
    tulis_penanda(Path(a.penanda), bundle.name, sekarang)
    print(json.dumps({"id": bundle.name, "ukuran": ukuran, "terhapus": terhapus, "ok": True},
                     sort_keys=True))
    return 0


def _samarkan(pesan: str, rahasia: List[str]) -> str:
    for nilai in rahasia:
        pesan = pesan.replace(nilai, "***")
    return pesan


def main(argv: Optional[List[str]] = None) -> int:
    a = buat_parser().parse_args(argv)
    rahasia: List[str] = []
    try:
        return _proses(a, rahasia)
    except (GalatOffsite, kripto.GalatKripto, r2_s3.GalatS3, ValueError, OSError) as galat:
        print("galat: " + _samarkan(str(galat), rahasia), file=sys.stderr)
    except Exception as galat:  # noqa: BLE001 - jangan bocorkan rahasia lewat traceback
        print("galat tak terduga: " + type(galat).__name__ + ": "
              + _samarkan(str(galat), rahasia), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
