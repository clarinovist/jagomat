"""Bagian netral format off-site (dipakai sisi VPS dan sisi pemulihan).

TIDAK berisi kode dekripsi atau penanganan kunci privat: VPS hanya boleh
mengenkripsi. Dekripsi ada di `pulihkan_offsite.py` (dijalankan di Mac).

Format v1 (objek di `vps/<id>/`):
- `data.enc`  : tar.gz bundle, `openssl enc -aes-256-cbc -pbkdf2 -iter 200000
  -md sha256 -salt`, kata sandi = sandi sesi.
- `kunci.enc` : sandi sesi dibungkus RSA-OAEP (SHA-256) dengan kunci PUBLIK.
- `meta.json` : id, ukuran dan sha256 ciphertext, mac, sidik jari SHA-256 kunci
  publik (DER), parameter algoritma.

Sandi sesi = `os.urandom(32).hex()` (64 karakter hex, 256 bit entropi). Hex
dipakai karena `openssl -pass file:` hanya membaca satu baris dan berhenti di
NUL/newline, yang bisa memotong 32 byte mentah.

Keaslian: `openssl enc` tidak autentik, jadi ada HMAC-SHA256 atas
`header || ciphertext`. Kunci MAC diturunkan dari sandi sesi dengan
HKDF-Expand (RFC 5869) berlabel: `HMAC(sandi, "jagomat-offsite-v1/mac" || 0x01)`
(sandi sudah acak seragam, jadi tahap Extract tidak diperlukan). Header
mengikat versi, id, sidik jari kunci publik, dan parameter algoritma. Batas:
MAC memberi integritas, bukan bukti asal; pemegang kunci publik yang bisa
menulis ke bucket dapat membuat paket sah. Karena itu skrip VPS mencatat `mac`
dan `sha256` ke sumber tepercaya (log/penanda di VPS) dan pemulihan
membandingkannya lewat `--mac-harapan`/`--sha256-harapan`.
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
# ASCII murni dan selalu dipakai dengan fullmatch: `\d` cocok angka Unicode dan `$`
# menerima newline di akhir.
POLA_ID = re.compile(r"[0-9]{8}-[0-9]{6}")
POLA_HEX = re.compile(r"[0-9a-f]{64}")
POLA_BIT_RSA = re.compile(r"(?:RSA )?Public-Key: \(([0-9]+) bit\)")
BIT_RSA_MINIMAL = 3072
BLOK = 1024 * 1024
KUNCI_META = {"format", "id", "ukuran", "sha256", "mac", "alg", "kunci_publik_sha256"}
BATAS_STDERR = 200


class GalatKripto(Exception):
    """Galat kripto/format; pesan tanpa rahasia."""


class GalatOffsite(Exception):
    """Galat alur off-site VPS; pesan tanpa rahasia (dasar untuk galat retensi/konfigurasi)."""


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


def _header_mac(id_bundle: str, sidik_kunci: str) -> bytes:
    alg = json.dumps(ALGORITMA, sort_keys=True, separators=(",", ":"))
    return f"jagomat-offsite/{FORMAT}\n{id_bundle}\n{sidik_kunci}\n{alg}\n".encode("utf-8")


def hitung_mac(sandi: str, id_bundle: str, path_cipher, sidik_kunci: str) -> str:
    mac = hmac.new(kunci_mac(sandi), _header_mac(id_bundle, sidik_kunci), hashlib.sha256)
    with open(path_cipher, "rb") as sumber:
        for blok in iter(lambda: sumber.read(BLOK), b""):
            mac.update(blok)
    return mac.hexdigest()


def bangun_meta(id_bundle: str, ukuran: int, sha256: str, mac: str, sidik_kunci: str) -> Dict:
    return {"format": FORMAT, "id": id_bundle, "ukuran": ukuran, "sha256": sha256,
            "mac": mac, "kunci_publik_sha256": sidik_kunci, "alg": dict(ALGORITMA)}


def urai_bit_rsa(teks: str) -> int:
    """Ambil jumlah bit dari `openssl pkey -pubin -text`; tolak bila bukan kunci RSA.

    Header berbeda antar versi (`Public-Key:` OpenSSL 3+, `RSA Public-Key:`
    OpenSSL 1.x/LibreSSL); kunci non-RSA tidak punya baris Modulus/Exponent.
    """
    baris = teks.splitlines()
    cocok = POLA_BIT_RSA.fullmatch(baris[0].strip()) if baris else None
    punya_rsa = any(b.startswith("Modulus:") for b in baris) and any(
        b.startswith("Exponent:") for b in baris)
    if not cocok or not punya_rsa:
        raise GalatKripto("kunci publik bukan RSA; hanya RSA yang didukung")
    return int(cocok.group(1))


def validasi_kunci_publik(openssl: str, path) -> str:
    """Pastikan PEM kunci publik RSA >= 3072 bit; kembalikan sidik jari SHA-256 (DER)."""
    teks = jalankan_openssl(openssl, ["pkey", "-pubin", "-in", str(path), "-text", "-noout"],
                            ambil_keluaran=True).decode("utf-8", "replace")
    bit = urai_bit_rsa(teks)
    if bit < BIT_RSA_MINIMAL:
        raise GalatKripto(f"kunci publik RSA {bit} bit terlalu kecil (minimal {BIT_RSA_MINIMAL})")
    der = jalankan_openssl(openssl, ["pkey", "-pubin", "-in", str(path), "-outform", "DER"],
                           ambil_keluaran=True)
    return hashlib.sha256(der).hexdigest()


def _tipe_ketat(nilai, harapan) -> bool:
    """Sama nilai DAN sama tipe persis: menolak `true` untuk 1 dan `200000.0` untuk 200000."""
    return type(nilai) is type(harapan) and nilai == harapan


def _alg_sah(alg) -> bool:
    return (isinstance(alg, dict) and set(alg) == set(ALGORITMA)
            and all(_tipe_ketat(alg[k], v) for k, v in ALGORITMA.items()))


def _hex_sah(nilai) -> bool:
    return isinstance(nilai, str) and POLA_HEX.fullmatch(nilai) is not None


def periksa_meta(meta, id_harapan: str) -> Dict:
    """Validasi ketat meta.json; parameter asing ditolak, tidak pernah diteruskan ke openssl."""
    if not isinstance(meta, dict) or set(meta) != KUNCI_META:
        raise GalatKripto("meta.json tidak sah")
    if not _tipe_ketat(meta["format"], FORMAT) or not _alg_sah(meta["alg"]):
        raise GalatKripto("format/algoritma meta.json tidak didukung")
    if meta["id"] != id_harapan or not POLA_ID.fullmatch(str(meta["id"])):
        raise GalatKripto("id meta.json tidak cocok")
    sah = (type(meta["ukuran"]) is int and meta["ukuran"] > 0
           and all(_hex_sah(meta[k]) for k in ("sha256", "mac", "kunci_publik_sha256")))
    if not sah:
        raise GalatKripto("isi meta.json tidak sah")
    return meta
