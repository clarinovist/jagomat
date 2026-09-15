"""Klien HTTPS OpenAI-compatible khusus chat Pendamping."""

from __future__ import annotations

from dataclasses import dataclass
import json
import socket
import urllib.error
import urllib.parse
import urllib.request

BATAS_WAKTU_DETIK = 25
BATAS_RESPONS_BYTE = 128_000


class GalatProvider(RuntimeError):
    """Kegagalan provider dengan kategori statis, tanpa body atau credential."""

    def __init__(self, pesan: str, *, kategori: str = "network_atau_provider"):
        super().__init__(pesan)
        self.kategori = kategori


@dataclass(frozen=True)
class Konfigurasi:
    base_url: str
    api_key: str
    model: str

    def __post_init__(self) -> None:
        hasil = urllib.parse.urlsplit(self.base_url)
        if hasil.scheme != "https" or not hasil.netloc or hasil.username or hasil.password:
            raise ValueError("Base URL provider wajib HTTPS.")
        if hasil.query or hasil.fragment:
            raise ValueError("Base URL provider tidak boleh memuat query.")
        if not self.api_key.strip() or not self.model.strip():
            raise ValueError("Konfigurasi provider belum lengkap.")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))


class _TanpaRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def kirim(
    config: Konfigurasi, pesan: list[dict[str, str]], *, max_tokens: int = 1200,
    timeout: int = BATAS_WAKTU_DETIK,
) -> dict:
    """Kirim request terbatas; redirect, response besar, dan JSON rusak gagal."""
    if type(max_tokens) is not int or not 1 <= max_tokens <= 8000:
        raise ValueError("Batas token provider tidak sah.")
    if type(timeout) is not int or not 1 <= timeout <= BATAS_WAKTU_DETIK:
        raise ValueError("Batas waktu provider tidak sah.")
    tubuh = json.dumps({
        "model": config.model,
        "messages": pesan,
        "temperature": 0.4,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        config.base_url + "/chat/completions",
        data=tubuh,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
        method="POST",
    )
    try:
        pembuka = urllib.request.build_opener(_TanpaRedirect())
        with pembuka.open(req, timeout=timeout) as respons:
            panjang = respons.headers.get("Content-Length") if respons.headers else None
            if panjang and int(panjang) > BATAS_RESPONS_BYTE:
                raise GalatProvider("respons terlalu besar", kategori="respons_terlalu_besar")
            mentah = respons.read(BATAS_RESPONS_BYTE + 1)
            if len(mentah) > BATAS_RESPONS_BYTE:
                raise GalatProvider("respons terlalu besar", kategori="respons_terlalu_besar")
    except urllib.error.HTTPError as galat:
        # Tutup body HTTP tanpa membaca atau mencatat isinya.
        galat.close()
        if 300 <= galat.code < 400:
            raise GalatProvider("redirect provider ditolak", kategori="provider_redirect") from None
        if galat.code == 429:
            raise GalatProvider("batas provider tercapai", kategori="provider_batas") from None
        kategori = "provider_otorisasi" if galat.code in (401, 403) else "provider_gagal"
        raise GalatProvider("provider tidak tersedia", kategori=kategori) from None
    except GalatProvider:
        raise
    except (socket.timeout, TimeoutError):
        raise GalatProvider("provider terlalu lama merespons", kategori="provider_timeout") from None
    except urllib.error.URLError as galat:
        kategori = "provider_timeout" if isinstance(galat.reason, (socket.timeout, TimeoutError)) else "provider_koneksi"
        raise GalatProvider("provider tidak tersedia", kategori=kategori) from None
    except OSError:
        raise GalatProvider("provider tidak tersedia", kategori="provider_koneksi") from None
    except ValueError:
        raise GalatProvider("respons provider tidak sah", kategori="respons_json") from None
    try:
        data = json.loads(mentah.decode("utf-8"))
        pilihan = data["choices"][0]
        if type(pilihan) is not dict:
            raise ValueError
        if pilihan.get("finish_reason") == "length":
            raise GalatProvider("respons provider terpotong", kategori="respons_terpotong")
        konten = pilihan["message"]["content"]
        if type(konten) is not str:
            raise ValueError
        hasil = json.loads(konten)
        if type(hasil) is not dict:
            raise ValueError
        return hasil
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        raise GalatProvider("respons provider tidak sah", kategori="respons_json") from None
