"""Berkas iCalendar (RFC 5545) untuk jadwal pertemuan anak. Murni: tanpa DB, HTTP, env, atau berkas.

Satu VEVENT per pertemuan. UID dihash dari (kunci order, nomor pertemuan): stabil saat unduhan diulang dan tidak memuat
id mentah. Waktu memakai UTC (akhiran `Z`), jadi tanpa VTIMEZONE. SUMMARY hanya "Kelas Jagomat" dan nomor pertemuan;
tanpa nama anak, guru, kontak, atau lokasi.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import List

import jadwal_dasar as jd

CRLF = "\r\n"
BATAS_OKTET = 75
UID_PANJANG = 32
DOMAIN_UID = "jagomat.id"
PRODUK = "-//Jagomat//Kelas Jagomat//ID"
RINGKASAN = "Kelas Jagomat"
FORMAT_ICS = "%Y%m%dT%H%M%SZ"
NAMA_BERKAS = "jadwal-kelas-jagomat.ics"


def escape_teks(nilai: str) -> str:
    """Escape nilai TEXT iCalendar: backslash lebih dulu, lalu `;`, `,`, dan baris baru."""
    return (nilai.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n"))


def lipat(baris: str) -> List[str]:
    """Lipat satu baris menjadi potongan <= 75 oktet UTF-8; potongan lanjutan diawali satu spasi, karakter tidak terpotong."""
    potongan: List[str] = []
    kini, oktet, batas = "", 0, BATAS_OKTET
    for karakter in baris:
        panjang = len(karakter.encode("utf-8"))
        if oktet + panjang > batas:
            potongan.append(kini)
            kini, oktet, batas = "", 0, BATAS_OKTET - 1
        kini += karakter
        oktet += panjang
    potongan.append(kini)
    return [potongan[0]] + [" " + lanjutan for lanjutan in potongan[1:]]


def uid_pertemuan(kunci: str, ke: int) -> str:
    """UID stabil per (order, nomor pertemuan). `kunci` = order_id, tidak pernah ditampilkan mentah."""
    cincang = hashlib.sha256(f"{kunci}|{ke}".encode("utf-8")).hexdigest()[:UID_PANJANG]
    return f"{cincang}@{DOMAIN_UID}"


def _properti(nama: str, nilai: str) -> List[str]:
    return lipat(f"{nama}:{nilai}")


def _vevent(kunci: str, sesi: dict, sekarang: str) -> List[str]:
    mulai = datetime.strptime(sesi["mulai"], jd.FORMAT_BAKU)
    selesai = mulai + timedelta(minutes=sesi["menit"])
    status = "CANCELLED" if sesi["dibatalkan"] else "CONFIRMED"
    isi = ["BEGIN:VEVENT"]
    isi += _properti("UID", uid_pertemuan(kunci, sesi["ke"]))
    isi += _properti("DTSTAMP", datetime.strptime(sekarang, jd.FORMAT_BAKU).strftime(FORMAT_ICS))
    isi += _properti("DTSTART", mulai.strftime(FORMAT_ICS))
    isi += _properti("DTEND", selesai.strftime(FORMAT_ICS))
    isi += _properti("SUMMARY", escape_teks(f"{RINGKASAN} - pertemuan {sesi['ke']}"))
    isi += _properti("STATUS", status)
    isi.append("END:VEVENT")
    return isi


def bangun(kunci: str, jadwal: dict, sekarang: str) -> bytes:
    """Berkas .ics (UTF-8, CRLF) untuk semua pertemuan `jadwal` (bentuk `jadwal_store.jadwal_untuk_murid`).

    `sekarang` = waktu UTC baku untuk DTSTAMP. Data tak sah (format waktu rusak, kunci hilang) menaikkan galat
    (ValueError/KeyError) dan tidak pernah menghasilkan berkas setengah jadi.
    """
    isi = ["BEGIN:VCALENDAR"]
    isi += _properti("VERSION", "2.0")
    isi += _properti("PRODID", PRODUK)
    isi += _properti("CALSCALE", "GREGORIAN")
    isi += _properti("METHOD", "PUBLISH")
    for sesi in jadwal["sesi"]:
        isi += _vevent(kunci, sesi, sekarang)
    isi.append("END:VCALENDAR")
    return (CRLF.join(isi) + CRLF).encode("utf-8")
