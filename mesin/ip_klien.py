"""Resolusi IP klien untuk pembatas laju, sadar proxy.

Dipisah dari ``sessions.py`` karena ``sessions.py`` termasuk berkas kontrak
rilis (`PROBE_KONTRAK` di ``scripts/deploy.py``): menambah helper di sana
mengubah fingerprint kontrak recovery tanpa perubahan format data. Modul ini
murni string/header, tanpa state dan tanpa I/O.
"""
from __future__ import annotations

import ipaddress


def _ip_privat(teks: str) -> bool:
    """Benar bila alamat loopback/jaringan privat (kandidat proxy terdekat)."""
    try:
        alamat = ipaddress.ip_address(teks)
    except ValueError:
        return False
    return bool(alamat.is_loopback or alamat.is_private)


def _ip_sah(teks: str) -> bool:
    try:
        ipaddress.ip_address(teks)
    except ValueError:
        return False
    return True


def ip_klien(headers, client_address) -> str:
    """IP klien untuk pembatas laju.

    Di produksi aplikasi berada di belakang Caddy: `client_address` adalah IP
    proxy sehingga kunci per-IP menyusut menjadi satu. Ambil entri **paling
    kanan** `X-Forwarded-For` (ditambahkan proxy terdekat) hanya bila peer
    langsung loopback/privat; di luar itu pakai peer apa adanya supaya header
    kiriman klien tidak bisa memalsukan kunci.
    """
    peer = client_address[0] if client_address else "unknown"
    if headers is None or not _ip_privat(peer):
        return peer
    nilai = headers.get_all("X-Forwarded-For", [])
    if len(nilai) != 1:
        return peer
    bagian = [item.strip() for item in str(nilai[0]).split(",") if item.strip()]
    if not bagian or not _ip_sah(bagian[-1]):
        return peer
    return bagian[-1]
