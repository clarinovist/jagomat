"""Token bearer untuk membagikan tepat satu sesi kepada anak.

Token mentah hanya dikembalikan sekali saat dibuat. Basis data menyimpan hash
SHA-256 supaya cadangan basis data tidak langsung berisi tautan yang dapat
dipakai. Tautan kedaluwarsa setelah 12 jam (keputusan pemilik K8, 6 Nov 2026:
tautan yang belum dikirim tidak tertinggal lama di riwayat HP), dapat dicabut,
dan berhenti berlaku ketika sesi selesai atau dibatalkan.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import time


TTL_DETIK = 12 * 60 * 60
LABEL_MASA_BERLAKU = "12 jam"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def buat(kon, sesi_id: int, sekarang: int | None = None) -> str:
    """Buat atau ganti tautan aktif satu sesi dan kembalikan token mentahnya."""
    ada = kon.execute("SELECT 1 FROM sesi WHERE id = ?", (sesi_id,)).fetchone()
    if not ada:
        raise ValueError("sesi tidak ada")
    kini = int(time.time() if sekarang is None else sekarang)
    token = secrets.token_urlsafe(32)
    # Seleksi status dan penulisan satu statement agar caller lain juga tidak
    # dapat membuat token setelah sesi selesai/dibatalkan di koneksi berbeda.
    hasil = kon.execute(
        """INSERT INTO tautan_sesi
               (sesi_id, token_hash, dibuat, kedaluarsa, dicabut)
           SELECT id, ?, ?, ?, NULL FROM sesi
           WHERE id = ? AND selesai IS NULL AND dibatalkan IS NULL
           ON CONFLICT(sesi_id) DO UPDATE SET
               token_hash = excluded.token_hash,
               dibuat = excluded.dibuat,
               kedaluarsa = excluded.kedaluarsa,
               dicabut = NULL""",
        (_hash(token), kini, kini + TTL_DETIK, sesi_id),
    )
    if hasil.rowcount != 1:
        raise ValueError("sesi tidak aktif")
    return token


def ambil(kon, token: str, sekarang: int | None = None) -> dict | None:
    """Kembalikan identitas sesi aktif untuk token sah, selainnya None."""
    if not isinstance(token, str) or not _TOKEN_RE.fullmatch(token):
        return None
    kini = int(time.time() if sekarang is None else sekarang)
    baris = kon.execute(
        """SELECT t.sesi_id, s.siswa_id, t.kedaluarsa
           FROM tautan_sesi t
           JOIN sesi s ON s.id = t.sesi_id
           WHERE t.token_hash = ?
             AND t.dicabut IS NULL
             AND t.kedaluarsa > ?
             AND s.selesai IS NULL
             AND s.dibatalkan IS NULL""",
        (_hash(token), kini),
    ).fetchone()
    return dict(baris) if baris else None


def aktif(kon, sesi_id: int, sekarang: int | None = None) -> bool:
    """Apakah sesi masih mempunyai tautan yang dapat digunakan."""
    kini = int(time.time() if sekarang is None else sekarang)
    return kon.execute(
        """SELECT 1 FROM tautan_sesi t
           JOIN sesi s ON s.id = t.sesi_id
           WHERE t.sesi_id = ? AND t.dicabut IS NULL
             AND t.kedaluarsa > ? AND s.selesai IS NULL
             AND s.dibatalkan IS NULL""",
        (sesi_id, kini),
    ).fetchone() is not None


def cabut(kon, sesi_id: int, sekarang: int | None = None) -> bool:
    """Cabut tautan yang belum dicabut. Aman dipanggil berulang."""
    kini = int(time.time() if sekarang is None else sekarang)
    cur = kon.execute(
        """UPDATE tautan_sesi SET dicabut = ?
           WHERE sesi_id = ? AND dicabut IS NULL""",
        (kini, sesi_id),
    )
    return cur.rowcount > 0
