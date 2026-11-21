"""Bagian netral format off-site (dipakai sisi VPS dan sisi pemulihan).

TIDAK berisi kode dekripsi atau penanganan kunci privat: VPS hanya boleh
mengenkripsi. Dekripsi ada di `pulihkan_offsite.py` (dijalankan di Mac).

Format v1 (objek di `vps/<id>/`):
- `data.enc`  : tar.gz bundle, `openssl enc -aes-256-cbc -pbkdf2 -iter 200000
  -md sha256 -salt`, kata sandi = sandi sesi.
- `kunci.enc` : sandi sesi dibungkus RSA-OAEP (SHA-256) dengan kunci PUBLIK.
- `meta.json` : id, ukuran dan sha256 ciphertext, mac, parameter algoritma.

Sandi sesi = `os.urandom(32).hex()` (64 karakter hex, 256 bit entropi). Hex
dipakai karena `openssl -pass file:` hanya membaca satu baris dan berhenti di
NUL/newline, yang bisa memotong 32 byte mentah.

Keaslian: `openssl enc` tidak autentik, jadi ada HMAC-SHA256 atas
`header || ciphertext`. Kunci MAC diturunkan dari sandi sesi dengan
HKDF-Expand (RFC 5869) berlabel: `HMAC(sandi, "jagomat-offsite-v1/mac" || 0x01)`
(sandi sudah acak seragam, jadi tahap Extract tidak diperlukan). Header
mengikat versi, id, dan parameter algoritma. Batas: MAC memberi integritas,
bukan bukti asal; pemegang kunci publik yang bisa menulis ke bucket dapat
membuat paket sah.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Dict

FORMAT = 1
ITERASI = 200_000
PREFIKS = "vps/"
NAMA_OBJEK = ("data.enc", "kunci.enc", "meta.json")
ALGORITMA = {"cipher": "aes-256-cbc", "kdf": "pbkdf2", "iter": ITERASI, "md": "sha256",
             "wrap": "rsa-oaep-sha256", "mac": "hmac-sha256"}
LABEL_MAC = b"jagomat-offsite-v1/mac"
POLA_ID = re.compile(r"^\d{8}-\d{6}$")
POLA_HEX = re.compile(r"^[0-9a-f]{64}$")
BLOK = 1024 * 1024
KUNCI_META = {"format", "id", "ukuran", "sha256", "mac", "alg"}
BATAS_STDERR = 200


class GalatKripto(Exception):
    """Galat kripto/format; pesan tanpa rahasia."""


def bangkitkan_sandi() -> str:
    return os.urandom(32).hex()


def jalankan_openssl(openssl: str, argumen, *, ambil_keluaran: bool = False) -> bytes:
    """Jalankan openssl dengan lingkungan minimal; rahasia hanya lewat berkas, bukan argv."""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    hasil = subprocess.run([openssl, *argumen], capture_output=True, env=env, check=False)
    if hasil.returncode != 0:
        akhir = hasil.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
        raise GalatKripto(f"openssl {argumen[0]} gagal (kode {hasil.returncode}): "
                          f"{akhir[0][:BATAS_STDERR]}")
    return hasil.stdout if ambil_keluaran else b""


def tulis_privat(direktori: Path, nama: str, isi: bytes) -> Path:
    path = direktori / nama
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as keluar:
        keluar.write(isi)
    return path


def sha256_berkas(path) -> str:
    sidik = hashlib.sha256()
    with open(path, "rb") as sumber:
        for blok in iter(lambda: sumber.read(BLOK), b""):
            sidik.update(blok)
    return sidik.hexdigest()


def kunci_mac(sandi: str) -> bytes:
    return hmac.new(sandi.encode("ascii"), LABEL_MAC + b"\x01", hashlib.sha256).digest()


def _header_mac(id_bundle: str) -> bytes:
    alg = json.dumps(ALGORITMA, sort_keys=True, separators=(",", ":"))
    return f"jagomat-offsite/{FORMAT}\n{id_bundle}\n{alg}\n".encode("utf-8")


def hitung_mac(sandi: str, id_bundle: str, path_cipher) -> str:
    mac = hmac.new(kunci_mac(sandi), _header_mac(id_bundle), hashlib.sha256)
    with open(path_cipher, "rb") as sumber:
        for blok in iter(lambda: sumber.read(BLOK), b""):
            mac.update(blok)
    return mac.hexdigest()


def bangun_meta(id_bundle: str, ukuran: int, sha256: str, mac: str) -> Dict:
    return {"format": FORMAT, "id": id_bundle, "ukuran": ukuran, "sha256": sha256,
            "mac": mac, "alg": dict(ALGORITMA)}


def periksa_meta(meta, id_harapan: str) -> Dict:
    """Validasi ketat meta.json; parameter asing ditolak, tidak pernah diteruskan ke openssl."""
    if not isinstance(meta, dict) or set(meta) != KUNCI_META:
        raise GalatKripto("meta.json tidak sah")
    if meta["format"] != FORMAT or meta["alg"] != ALGORITMA:
        raise GalatKripto("format/algoritma meta.json tidak didukung")
    if meta["id"] != id_harapan or not POLA_ID.fullmatch(str(meta["id"])):
        raise GalatKripto("id meta.json tidak cocok")
    sah = (isinstance(meta["ukuran"], int) and not isinstance(meta["ukuran"], bool)
           and meta["ukuran"] > 0 and POLA_HEX.fullmatch(str(meta["sha256"]))
           and POLA_HEX.fullmatch(str(meta["mac"])))
    if not sah:
        raise GalatKripto("isi meta.json tidak sah")
    return meta
