"""Validator tautan pertemuan Mini Class: hanya tautan Zoom atau Google Meet yang boleh masuk kolom `lokasi`.

Keputusan Pemilik 25 Nov 2026: Mini Class tanpa lokasi fisik; pertemuan lewat Zoom atau Google Meet, tautannya
dikirim setelah daftar. Kolom DB `lokasi` tetap dipakai (tanpa migrasi), semantiknya kini tautan. Tanpa DB/jaringan;
URL tidak ditulis ulang dan isian tidak digemakan di pesan galat.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import jadwal_dasar as jd

MAKS_TAUTAN = 200
SKEMA_TAUTAN = "https"
HOST_MEET = "meet.google.com"
KODE_TAMPAK_AWAL = 33                       # '!' ; spasi dan kontrol di bawahnya ditolak
KODE_TAMPAK_AKHIR = 126                     # '~' ; non-ASCII di atasnya ditolak
KARAKTER_DILARANG = frozenset('<>"\'`\\')
POLA_HOST_ZOOM = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)*zoom\.us")
GALAT_TAUTAN = "tautan meeting tidak sah"


def periksa_tautan_meeting(nilai) -> str:
    """Tautan sah dikembalikan setelah strip; selain itu `JadwalTidakSah` tanpa gema isian."""
    teks = _rapikan_teks(nilai)
    if not _host_dan_path_sah(teks):
        raise jd.JadwalTidakSah(GALAT_TAUTAN)
    return teks


def tautan_meeting_sah(nilai) -> bool:
    try:
        periksa_tautan_meeting(nilai)
    except jd.JadwalTidakSah:
        return False
    return True


def _rapikan_teks(nilai) -> str:
    """Tipe str, di-strip, 1..200 karakter, hanya ASCII tampak tanpa spasi dan tanpa karakter berbahaya."""
    if type(nilai) is not str:
        raise jd.JadwalTidakSah(GALAT_TAUTAN)
    teks = nilai.strip()
    if not 1 <= len(teks) <= MAKS_TAUTAN or any(_karakter_terlarang(ch) for ch in teks):
        raise jd.JadwalTidakSah(GALAT_TAUTAN)
    return teks


def _karakter_terlarang(ch: str) -> bool:
    return not KODE_TAMPAK_AWAL <= ord(ch) <= KODE_TAMPAK_AKHIR or ch in KARAKTER_DILARANG


def _host_dan_path_sah(teks: str) -> bool:
    """Skema https; netloc sama persis dengan host (tanpa userinfo, port, atau titik dua); host dari daftar izin.

    `urlsplit` sudah menurunkan skema dan host ke huruf kecil. Netloc yang sama dengan host menolak userinfo dan
    port apa pun, termasuk `zoom.us:` kosong. Meet wajib punya kode di path; Zoom menerima path apa pun.
    """
    try:
        bagian = urlsplit(teks)
        host = bagian.hostname
    except ValueError:
        return False
    if bagian.scheme != SKEMA_TAUTAN or host is None or bagian.netloc.lower() != host:
        return False
    if host == HOST_MEET:
        return bool(bagian.path.strip("/"))
    return POLA_HOST_ZOOM.fullmatch(host) is not None
