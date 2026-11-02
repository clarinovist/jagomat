"""Kontrak transport: body berbatas, header aman default, dan rate-limit sadar proxy.

Semua permintaan memakai server uji HTTP nyata di port acak; tidak ada DB anak
yang disentuh dan tidak ada jaringan keluar.
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sessions  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402


@pytest.fixture()
def server(tmp_path, monkeypatch):
    """Server HTTP nyata di port acak; state hanya di tmp_path."""
    s = ServerUji(tmp_path, monkeypatch)
    try:
        yield s
    finally:
        s.berhenti()


def _kirim_mentah(server, baris: bytes, header: dict[str, str], tubuh: bytes = b"") -> bytes:
    """Kirim satu permintaan HTTP mentah dan kembalikan byte respons awal."""
    alamat = urlsplit(server.alamat)
    isi = b"".join(
        f"{nama}: {nilai}\r\n".encode("ascii") for nama, nilai in header.items()
    )
    with socket.create_connection((alamat.hostname, alamat.port), timeout=5) as soket:
        soket.sendall(baris + b"\r\n" + isi + b"\r\n" + tubuh)
        soket.settimeout(5)
        data = b""
        while b"\r\n\r\n" not in data:
            bagian = soket.recv(4096)
            if not bagian:
                break
            data += bagian
    return data


def _kode(respons: bytes) -> int:
    return int(respons.split(b"\r\n", 1)[0].split()[1])


def _host(server) -> str:
    alamat = urlsplit(server.alamat)
    return f"{alamat.hostname}:{alamat.port}"


@pytest.mark.parametrize(
    "panjang",
    ["-1", "1000000000", "99999999999999999999"],
)
def test_content_length_tidak_sah_ditolak_tanpa_membaca_body(server, panjang):
    """Regresi: `read(-1)`/tanpa batas membuat klien anonim menahan thread."""
    respons = _kirim_mentah(
        server,
        b"POST /masuk HTTP/1.0",
        {
            "Host": _host(server),
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": panjang,
        },
    )
    assert _kode(respons) in (400, 413)


def test_transfer_encoding_ditolak(server):
    respons = _kirim_mentah(
        server,
        b"POST /masuk HTTP/1.0",
        {
            "Host": _host(server),
            "Content-Type": "application/x-www-form-urlencoded",
            "Transfer-Encoding": "chunked",
        },
        b"0\r\n\r\n",
    )
    assert _kode(respons) in (400, 413)


def test_content_length_ganda_ditolak(server):
    alamat = urlsplit(server.alamat)
    with socket.create_connection((alamat.hostname, alamat.port), timeout=5) as soket:
        soket.sendall(
            b"POST /masuk HTTP/1.0\r\n"
            + f"Host: {_host(server)}\r\n".encode()
            + b"Content-Type: application/x-www-form-urlencoded\r\n"
            + b"Content-Length: 4\r\nContent-Length: 4\r\n\r\nabcd"
        )
        respons = soket.recv(4096)
    assert _kode(respons) in (400, 413)


def test_post_lintas_situs_ditolak_di_permukaan_wajib_login(server):
    """Form publik punya pembatas sendiri; permukaan guru/admin wajib same-origin."""
    respons = _kirim_mentah(
        server,
        b"POST /akun HTTP/1.0",
        {
            "Host": _host(server),
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": "0",
            "Sec-Fetch-Site": "cross-site",
        },
    )
    assert _kode(respons) == 403


def test_post_masuk_tanpa_origin_tetap_dilayani(server):
    """Peramban lama tanpa Fetch Metadata tidak boleh terkunci dari login."""
    respons = _kirim_mentah(
        server,
        b"POST /masuk HTTP/1.0",
        {
            "Host": _host(server),
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": "0",
        },
    )
    assert _kode(respons) == 200


def test_head_dijawab_dan_tidak_membocorkan_versi(server):
    respons = _kirim_mentah(server, b"HEAD / HTTP/1.0", {"Host": _host(server)})
    assert _kode(respons) == 405
    teks = respons.decode("latin-1").lower()
    assert "allow: get, post" in teks
    assert "python/" not in teks


def test_header_aman_default_di_respons_publik(server):
    kode, _isi, header = server.minta("/masuk")
    assert kode == 200
    assert header["X-Content-Type-Options"] == "nosniff"
    assert header["X-Frame-Options"] == "DENY"
    assert header["Referrer-Policy"] == "no-referrer"


def test_lampiran_tidak_menyajikan_nama_berkas_keluar_direktori(server, monkeypatch):
    """Nama berkas dari DB wajib basename; pertahanan berlapis bila baris keliru."""
    import attachment_http

    class _Lampiran(dict):
        pass

    monkeypatch.setattr(
        attachment_http.database,
        "ambil_lampiran",
        lambda _kon, _id: _Lampiran(
            sesi_id=1, nama_berkas="../sandi.json", mime="image/png"
        ),
    )
    dipanggil = {}

    class _Penangan:
        def __init__(self):
            self._sudah_menjawab = False

        def _bisa_lihat_sesi(self, _kon, _sesi):
            return True

        def _kirim(self, isi, kode=200):
            dipanggil["kode"] = kode

    attachment_http._kirim_berkas(_Penangan(), object(), 7)
    assert dipanggil.get("kode") == 404


def test_ip_klien_memakai_entri_kanan_di_belakang_proxy_privat():
    class _Header:
        def __init__(self, nilai):
            self._nilai = nilai

        def get_all(self, nama, default=None):
            return [self._nilai] if nama == "X-Forwarded-For" else (default or [])

    # Proxy loopback menambahkan IP asli di kanan; entri kiri kiriman klien diabaikan.
    assert sessions.ip_klien(_Header("1.2.3.4, 203.0.113.9"), ("127.0.0.1", 1)) == "203.0.113.9"
    # Peer publik tidak dipercaya membawa XFF.
    assert sessions.ip_klien(_Header("203.0.113.9"), ("8.8.8.8", 1)) == "8.8.8.8"
    # Nilai tidak sah jatuh ke peer.
    assert sessions.ip_klien(_Header("bukan-ip"), ("127.0.0.1", 1)) == "127.0.0.1"


def test_kunci_rate_limit_tidak_tumbuh_tanpa_batas(monkeypatch):
    monkeypatch.setattr(sessions, "_BATAS_KUNCI", 16)
    sessions._reset_rate_limit()
    for nomor in range(64):
        sessions.catat_gagal(f"nama-{nomor}", "203.0.113.9")
    assert len(sessions._jalur_dari_kunci_ip) <= 16
    sessions._reset_rate_limit()
