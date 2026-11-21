#!/usr/bin/env python3
"""Pulihkan backup off-site `vps/<id>/` di Mac memakai kunci PRIVAT.

Urutan (gagal di langkah mana pun = berhenti, tidak ada yang didekripsi):
1. tujuan harus belum ada atau direktori kosong;
2. ambil `meta.json` DULU (unduh dari R2, atau `--dari-direktori`) dan validasi
   ketat; lalu `data.enc` (dibatasi sebesar `meta.ukuran`) dan `kunci.enc`; set
   tanpa meta dianggap tidak lengkap dan ditolak;
2b. bandingkan `mac`/`sha256` meta dengan `--mac-harapan`/`--sha256-harapan` (nilai
   dari log/penanda `offsite-vps.last-ok` di VPS, sumber TEPERCAYA; token R2 yang
   bocor bisa menanam set palsu yang sah secara internal). Tanpa keduanya, keaslian
   TIDAK diverifikasi dan peringatan dicetak ke stderr; cek ukuran + sha256;
3. buka sandi sesi dengan kunci privat (`openssl pkeyutl -decrypt`, RSA-OAEP
   SHA-256); kunci privat hanya sebagai PATH, tidak pernah isinya di argv. Bila
   kunci privat berpassphrase, openssl akan menanyakannya di terminal;
4. VERIFIKASI HMAC (`hmac.compare_digest`) SEBELUM dekripsi data;
5. dekripsi, ekstraksi tar aman (batas byte terdekompresi; hanya berkas/direktori
   biasa, tanpa traversal/link/duplikat, tanpa `extractall`) ke staging, validasi
   bundle dengan `backup_harian.validasi`, lalu rename atomik ke tujuan.

Contoh:
    pulihkan_offsite.py --id 20261121-214501 --env ~/.config/jagomat-offsite/r2-baca.env \
        --kunci-privat ~/jagomat-offsite-privat.pem --tujuan ~/pulih-20261121 \
        --mac-harapan <mac dari penanda/log VPS> --sha256-harapan <sha256 dari penanda/log VPS>
"""
from __future__ import annotations

import argparse
import gzip
import hmac
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from typing import List, Optional, Tuple
import zlib

_DIR = str(Path(__file__).resolve().parent)
if _DIR not in sys.path:
    sys.path.append(_DIR)

import backup_harian  # noqa: E402
import backup_offsite_vps as sisi_vps  # noqa: E402  (hanya muat_env/_buat_klien)
import offsite_kerja  # noqa: E402
import offsite_kripto as kripto  # noqa: E402
import r2_s3  # noqa: E402

BATAS_ENTRI = 10_000
BATAS_BYTE = 8 * 1024 * 1024 * 1024
BLOK = 1024 * 1024
PESAN_TANPA_META = "set tidak lengkap: meta.json tidak ada (unggahan terputus atau dihapus)"
BATAS_META = 64 * 1024
BATAS_KUNCI_ENC = 16 * 1024  # RSA-OAEP: sebesar modulus (<= 8192 bit = 1 KiB)
PERINGATAN_KEASLIAN = ("peringatan: keaslian paket TIDAK diverifikasi terhadap sumber tepercaya; "
                       "beri --mac-harapan/--sha256-harapan dari penanda/log VPS "
                       "(offsite-vps.last-ok)")


def _id_sah(nilai: str) -> str:
    if not kripto.POLA_ID.fullmatch(nilai):
        raise argparse.ArgumentTypeError("id harus berformat YYYYMMDD-HHMMSS")
    return nilai


def _hex_sah(nilai: str) -> str:
    if not kripto.POLA_HEX.fullmatch(nilai):
        raise argparse.ArgumentTypeError("harus 64 karakter hex huruf kecil")
    return nilai


def buat_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--id", required=True, type=_id_sah,
                   help="id bundle, format YYYYMMDD-HHMMSS (WIB)")
    p.add_argument("--mac-harapan", type=_hex_sah,
                   help="mac paket dari penanda/log VPS (sumber tepercaya); dicocokkan sebelum dekripsi")
    p.add_argument("--sha256-harapan", type=_hex_sah,
                   help="sha256 data.enc dari penanda/log VPS (sumber tepercaya)")
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


def unduh_objek(a, kerja: Path) -> Tuple[Path, dict]:
    """Unduh meta.json DULU; data.enc dibatasi sebesar meta.ukuran (server tak dipercaya)."""
    kredensial = sisi_vps.muat_env(a.env, lewati_pemilik=True)
    klien = sisi_vps._buat_klien(a, kredensial)
    unduhan = kerja / "unduhan"
    unduhan.mkdir(mode=0o700)
    awalan = f"{kripto.PREFIKS}{a.id}/"
    try:
        klien.ambil_objek(awalan + "meta.json", unduhan / "meta.json", maks_byte=BATAS_META)
    except r2_s3.GalatS3 as galat:
        if galat.status == 404:
            raise kripto.GalatKripto(PESAN_TANPA_META) from galat
        raise
    meta = baca_meta(unduhan / "meta.json", a.id)
    klien.ambil_objek(awalan + "data.enc", unduhan / "data.enc", maks_byte=meta["ukuran"])
    klien.ambil_objek(awalan + "kunci.enc", unduhan / "kunci.enc", maks_byte=BATAS_KUNCI_ENC)
    return unduhan, meta


def sediakan_objek(a, kerja: Path) -> Tuple[Path, dict]:
    if a.dari_direktori:
        return Path(a.dari_direktori), baca_objek(Path(a.dari_direktori), a.id)
    if not a.env:
        raise kripto.GalatKripto("beri --dari-direktori atau --env untuk mengunduh")
    return unduh_objek(a, kerja)


def baca_meta(path: Path, id_bundle: str) -> dict:
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as galat:
        raise kripto.GalatKripto("meta.json tidak terbaca") from galat
    return kripto.periksa_meta(meta, id_bundle)


def baca_objek(direktori: Path, id_bundle: str) -> dict:
    if not (direktori / "meta.json").is_file():
        raise kripto.GalatKripto(PESAN_TANPA_META)
    meta = baca_meta(direktori / "meta.json", id_bundle)
    for nama in ("data.enc", "kunci.enc"):
        if not (direktori / nama).is_file():
            raise kripto.GalatKripto(f"objek tidak ada: {nama}")
    return meta


def periksa_harapan(meta: dict, mac_harapan: Optional[str], sha256_harapan: Optional[str]) -> bool:
    """Cocokkan mac/sha256 dengan sumber tepercaya SEBELUM dekripsi; True bila ada yang diperiksa."""
    for nama, harapan in (("mac", mac_harapan), ("sha256", sha256_harapan)):
        if harapan is not None and not hmac.compare_digest(meta[nama], harapan):
            raise kripto.GalatKripto(
                f"{nama} paket tidak cocok dengan sumber tepercaya (--{nama}-harapan): "
                "paket mungkin palsu atau bukan set yang dicatat VPS; tidak didekripsi")
    return mac_harapan is not None or sha256_harapan is not None


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
    hitung = kripto.hitung_mac(sandi, meta["id"], data, meta["kunci_publik_sha256"])
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


def periksa_ukuran_terdekompresi(tar_path: Path, batas: Optional[int] = None) -> None:
    """Hitung byte hasil dekompresi (tanpa menyimpan) dan hentikan di `batas`: anti gzip-bomb."""
    batas = BATAS_BYTE if batas is None else batas
    total = 0
    try:
        with gzip.open(str(tar_path), "rb") as sumber:
            for blok in iter(lambda: sumber.read(BLOK), b""):
                total += len(blok)
                if total > batas:
                    raise kripto.GalatKripto("tar tidak aman: ukuran terdekompresi melebihi batas")
    except (OSError, EOFError, zlib.error) as galat:
        raise kripto.GalatKripto(f"tar tidak bisa dibaca: {type(galat).__name__}") from galat


def ekstrak_aman(tar_path: Path, tujuan: Path, id_bundle: str) -> None:
    periksa_ukuran_terdekompresi(tar_path)
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
        objek, meta = sediakan_objek(a, kerja)
        terverifikasi = periksa_harapan(meta, a.mac_harapan, a.sha256_harapan)
        if not terverifikasi:
            print(PERINGATAN_KEASLIAN, file=sys.stderr)
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
        offsite_kerja.hapus_kerja(kerja)  # kegagalan dicatat ke stderr, tidak ditelan
        offsite_kerja.hapus_kerja(staging)
    jumlah = sum(1 for p in (tujuan / a.id).rglob("*") if p.is_file())
    return {"id": a.id, "tujuan": str(tujuan), "berkas": jumlah, "ok": True,
            "kunci_publik_sha256": meta["kunci_publik_sha256"],
            "keaslian_terverifikasi": terverifikasi}


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
