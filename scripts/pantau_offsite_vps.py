#!/usr/bin/env python3
"""Monitor off-site VPS: jalan di Mac (Hermes), alert Telegram bila cadangan VPS->R2 tidak sehat.

Tanpa monitor ini, kegagalan cron off-site VPS hanya jadi satu baris di log VPS. Skrip membaca
penanda `last-ok` dan `retention-ok` lewat SATU panggilan SSH (tanpa sudo; penanda 0644) dan
memeriksa, terhadap JAM VPS sendiri (bukan jam Mac):

1. stempel `last-ok` tidak lebih tua dari batas;
2. **id bundle** di `last-ok` tidak lebih tua dari batas (run ulang `sudah_ada` menyegarkan
   stempel meski bundle-nya kemarin; hanya umur id yang membuktikan backup harian jalan);
3. sidik jari kunci publik di `last-ok` sama dengan kunci publik lokal (kunci tertukar);
4. `retention-ok` ada, segar, dan beridentitas sama dengan `last-ok` (retensi tertinggal).

JADWAL DAN AMBANG SALING BERGANTUNG. Cron VPS jalan 22:00 dan hasilnya ~22:00; ambang 26 jam.
Monitor dijadwalkan PAGI (mis. 08:30): normal ~10,5 jam (tenang); satu malam gagal ~34,5 jam
(alert). Jadwal 22:30 dengan ambang 26 jam akan buta: run yang gagal malam itu menyisakan data
berumur ~24,5 jam, di bawah ambang. Ubah jadwal hanya bersama ambang.

Semua jalur non-OK mengirim alert sendiri (jalur "tidak bisa memeriksa" juga, termasuk VPS
tak terjangkau) lalu keluar non-nol. Alert tidak memuat mac/sha256. Batasan: monitor hanya
jalan saat Mac menyala; bila Mac mati pagi itu, pengecekan menyusul pada jadwal berikutnya.

Kode keluar: 0 sehat; 1 ada masalah pada cadangan; 2 pemeriksaan sendiri gagal.
Env: OSN_PANTAU_HOST (biznet-sekolahdesain), OSN_PANTAU_SSH (ssh), OSN_ALERT
(~/.hermes/scripts/notify-telegram.py), OSN_PANTAU_KUNCI_PUBLIK
(~/.config/jagomat-backup/offsite-rsa-public.pem), OSN_PANTAU_UMUR_MAKS_JAM (26).
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

UMUR_MAKS_JAM = 26.0
FORMAT_STEMPEL = "%Y%m%d-%H%M%S"
TOLERANSI_MASA_DEPAN_DETIK = 3600
BATAS_WAKTU_SSH_DETIK = 45
BATAS_WAKTU_ALERT_DETIK = 60
HOST_BAWAAN = "biznet-sekolahdesain"
PENANDA_LAST_OK = "/opt/osn/log/offsite-vps.last-ok"
PENANDA_RETENSI = "/opt/osn/log/offsite-vps.retention-ok"
PENANDA_BAGIAN = ("@@last-ok", "@@retention-ok", "@@end")
PERINTAH_VPS = (
    "TZ=Asia/Jakarta date +%Y%m%d-%H%M%S; "
    f"echo {PENANDA_BAGIAN[0]}; cat {PENANDA_LAST_OK} 2>/dev/null; "
    f"echo {PENANDA_BAGIAN[1]}; cat {PENANDA_RETENSI} 2>/dev/null; "
    f"echo {PENANDA_BAGIAN[2]}"
)
POLA_STEMPEL = re.compile(r"^\d{8}-\d{6}$")
JAM_PER_DETIK = 3600.0


class GalatPantau(Exception):
    """Pemeriksaan sendiri tidak bisa diselesaikan (bukan: cadangan bermasalah)."""


def _waktu(teks: str) -> Optional[dt.datetime]:
    if not POLA_STEMPEL.match(teks):
        return None
    try:
        return dt.datetime.strptime(teks, FORMAT_STEMPEL)
    except ValueError:
        return None


def _urai_penanda(teks: str) -> Optional[Tuple[dt.datetime, str, dt.datetime, Dict[str, str]]]:
    """(stempel, id, waktu_id, bidang) dari baris pertama; None bila kosong/rusak."""
    for baris in teks.splitlines():
        if not baris.strip():
            continue
        token = baris.split()
        if len(token) < 2:
            return None
        stempel, id_bundle = _waktu(token[0]), _waktu(token[1])
        if stempel is None or id_bundle is None:
            return None
        bidang = {}
        for sisa in token[2:]:
            kunci, pemisah, isi = sisa.partition("=")
            if pemisah:
                bidang[kunci] = isi
        return stempel, token[1], id_bundle, bidang
    return None


def _umur_jam(sekarang: dt.datetime, waktu: dt.datetime) -> float:
    return (sekarang - waktu).total_seconds() / JAM_PER_DETIK


def _periksa_umur(label: str, umur: float, umur_maks: float) -> Optional[str]:
    if umur < -TOLERANSI_MASA_DEPAN_DETIK / JAM_PER_DETIK:
        return f"{label} di masa depan menurut jam VPS ({-umur:.1f} jam): jam VPS tak wajar"
    if umur > umur_maks:
        return f"{label} basi: {umur:.1f} jam, batas {umur_maks:g} jam"
    return None


def nilai(lastok: str, retensi: str, sekarang_vps: str, kunci_harapan: str,
          umur_maks_jam: float) -> List[str]:
    """Daftar masalah (kosong = sehat). Murni: tanpa jaringan atau berkas."""
    sekarang = _waktu(sekarang_vps)
    if sekarang is None:
        raise GalatPantau("jam VPS tak terbaca")
    masalah: List[str] = []

    utama = _urai_penanda(lastok)
    if utama is None:
        masalah.append("last-ok kosong, hilang, atau rusak")
    else:
        stempel, id_utama, waktu_id, bidang = utama
        for pesan in (
            _periksa_umur("last-ok: stempel", _umur_jam(sekarang, stempel), umur_maks_jam),
            _periksa_umur(f"bundle terunggah ({id_utama})", _umur_jam(sekarang, waktu_id),
                          umur_maks_jam),
        ):
            if pesan:
                masalah.append(pesan + (" (backup harian mungkin tidak jalan)"
                                        if pesan.startswith("bundle") else ""))
        if bidang.get("kunci") != kunci_harapan:
            masalah.append("last-ok: sidik jari kunci publik tidak cocok atau tidak tercatat")

    sisa = _urai_penanda(retensi)
    if sisa is None:
        masalah.append("retensi: penanda kosong, hilang, atau rusak")
        return masalah
    pesan = _periksa_umur("retensi: stempel", _umur_jam(sekarang, sisa[0]), umur_maks_jam)
    if pesan:
        masalah.append(pesan)
    if utama is not None and sisa[1] != utama[1]:
        masalah.append(f"retensi tertinggal: berhenti di bundle {sisa[1]}, unggahan terakhir {utama[1]}")
    return masalah


def urai_keluaran(teks: str) -> Tuple[str, str, str]:
    """Pecah keluaran SSH menjadi (jam_vps, isi_last_ok, isi_retensi); galat bila terpotong."""
    baris = teks.splitlines(keepends=True)
    if not baris or not POLA_STEMPEL.match(baris[0].strip()):
        raise GalatPantau("keluaran ssh tak dikenali (jam VPS tidak ada)")
    jam = baris[0].strip()
    bagian: Dict[str, List[str]] = {}
    aktif: Optional[str] = None
    selesai = False
    for isi in baris[1:]:
        penanda = isi.strip()
        if penanda in PENANDA_BAGIAN:
            if penanda == PENANDA_BAGIAN[2]:
                selesai = True
                break
            aktif = penanda
            bagian[aktif] = []
        elif aktif is not None:
            bagian[aktif].append(isi)
    if not selesai or PENANDA_BAGIAN[0] not in bagian or PENANDA_BAGIAN[1] not in bagian:
        raise GalatPantau("keluaran ssh terpotong atau tidak lengkap")
    return jam, "".join(bagian[PENANDA_BAGIAN[0]]), "".join(bagian[PENANDA_BAGIAN[1]])


def sidik_jari_pem(path: Path) -> str:
    """SHA-256 dari DER kunci publik (isi PEM `PUBLIC KEY` didekode base64)."""
    try:
        teks = Path(path).read_text(encoding="utf-8")
    except OSError as galat:
        raise GalatPantau(f"kunci publik lokal tak terbaca ({type(galat).__name__})")
    cocok = re.search(r"-----BEGIN PUBLIC KEY-----(.*?)-----END PUBLIC KEY-----", teks, re.S)
    if not cocok or "PRIVATE" in teks:
        raise GalatPantau("berkas kunci bukan kunci publik PEM")
    try:
        der = base64.b64decode("".join(cocok.group(1).split()), validate=True)
    except ValueError:
        raise GalatPantau("kunci publik PEM rusak")
    return hashlib.sha256(der).hexdigest()


def ambil_dari_vps(ssh: str, host: str) -> Tuple[str, str, str]:
    try:
        hasil = subprocess.run(
            [ssh, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host, PERINTAH_VPS],
            capture_output=True, text=True, timeout=BATAS_WAKTU_SSH_DETIK)
    except subprocess.TimeoutExpired:
        raise GalatPantau("ssh ke VPS melewati batas waktu")
    except OSError as galat:
        raise GalatPantau(f"ssh tak bisa dijalankan ({type(galat).__name__})")
    if hasil.returncode != 0:
        print(hasil.stderr.strip()[-300:], file=sys.stderr)
        raise GalatPantau(f"ssh ke VPS gagal (kode {hasil.returncode})")
    return urai_keluaran(hasil.stdout)


def kirim_alert(alert: str, teks: str) -> None:
    try:
        subprocess.run([alert, teks], timeout=BATAS_WAKTU_ALERT_DETIK, check=True,
                       capture_output=True)
    except (OSError, subprocess.SubprocessError) as galat:
        print(f"alert tak terkirim ({type(galat).__name__}): {teks}", file=sys.stderr)


def _umur_maks_dari_env() -> float:
    mentah = os.environ.get("OSN_PANTAU_UMUR_MAKS_JAM", "")
    if not mentah:
        return UMUR_MAKS_JAM
    try:
        angka = float(mentah)
    except ValueError:
        raise GalatPantau("OSN_PANTAU_UMUR_MAKS_JAM bukan angka")
    if angka <= 0:
        raise GalatPantau("OSN_PANTAU_UMUR_MAKS_JAM harus positif")
    return angka


def main() -> int:
    rumah = Path.home()
    alert = os.environ.get("OSN_ALERT", str(rumah / ".hermes/scripts/notify-telegram.py"))
    try:
        umur_maks = _umur_maks_dari_env()
        kunci = sidik_jari_pem(Path(os.environ.get(
            "OSN_PANTAU_KUNCI_PUBLIK", str(rumah / ".config/jagomat-backup/offsite-rsa-public.pem"))))
        jam, lastok, retensi = ambil_dari_vps(
            os.environ.get("OSN_PANTAU_SSH", "ssh"), os.environ.get("OSN_PANTAU_HOST", HOST_BAWAAN))
        masalah = nilai(lastok, retensi, jam, kunci, umur_maks)
    except GalatPantau as galat:
        kirim_alert(alert, f"Jagomat: monitor off-site VPS GAGAL memeriksa: {galat}. "
                           "Cek SSH ke VPS dan berkas penanda; jalankan "
                           "scripts/pantau_offsite_vps.py manual.")
        print(f"gagal memeriksa: {galat}", file=sys.stderr)
        return 2
    if masalah:
        kirim_alert(alert, "Jagomat: off-site VPS->R2 BERMASALAH. " + "; ".join(masalah)
                    + ". Cek /opt/osn/log/offsite-vps.log di VPS.")
        print("bermasalah: " + "; ".join(masalah), file=sys.stderr)
        return 1
    utama = _urai_penanda(lastok)
    print(f"ok: last-ok {utama[0]:{FORMAT_STEMPEL}} bundle {utama[1]} (jam VPS {jam})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
