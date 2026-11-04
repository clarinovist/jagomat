"""Token bearer baca-saja untuk laporan orang tua (hanya hash disimpan)."""
from __future__ import annotations

import hashlib
import re
import secrets

TTL_DETIK = 30 * 24 * 60 * 60
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def token_baru() -> str:
    return secrets.token_urlsafe(32)


def token_sah(token) -> bool:
    return isinstance(token, str) and _TOKEN_RE.fullmatch(token) is not None
