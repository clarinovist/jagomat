"""Kontak WhatsApp per akun: normalisasi nomor dan simpan/ambil/hapus.

Kunci baris adalah `id_akun` (ID acak dari `sandi.json`), bukan nama login dan
bukan data anak. Nomor hanya milik orang dewasa pembayar; modul ini tidak pernah
mencatat, mencetak, atau memasukkan nomor ke pesan galat.

`simpan` dan `hapus` bekerja di dalam transaksi pemanggil dan tidak commit
sendiri, supaya registrasi dapat menulis kontak bersama baris lain secara atomik.
Waktu disuntik (string ISO) agar tes deterministik.

Retensi: `aktivitas_terakhir` ditulis `sentuh_aktivitas` (maks satu tulis per
hari per akun) dan baris dihapus `sapu_kontak` bila lebih tua dari
`RETENSI_HARI` atau akunnya tidak lagi ada. Sapuan belum dijadwalkan otomatis.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from auth import id_akun_sah

PANJANG_MASUKAN_MAKS = 32
RETENSI_HARI = 365  # 12 bulan sejak aktivitas terakhir akun
_FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
_PANJANG_TANGGAL = 10  # "YYYY-MM-DD"
_SAVEPOINT_SAPU = "sapu_kontak"
_PEMISAH = " -.()"
_POLA_WA = re.compile(r"628[0-9]{8,12}")
_KOLOM = ("id_akun", "wa", "dibuat", "diperbarui", "aktivitas_terakhir")


def normalisasi_wa(teks) -> str | None:
    """Ubah `08…`, `+62…`, atau `62…` menjadi `628…`; selain itu None.

    Spasi, strip, titik, dan kurung dibuang. Fungsi murni.
    """
    if type(teks) is not str or len(teks) > PANJANG_MASUKAN_MAKS:
        return None
    bersih = teks.strip()
    awal_plus = bersih.startswith("+")
    isi = bersih[1:] if awal_plus else bersih
    angka = "".join(c for c in isi if c not in _PEMISAH)
    if not (angka.isascii() and angka.isdigit()):
        return None
    if angka.startswith("0") and not awal_plus:
        angka = "62" + angka[1:]
    elif not angka.startswith("62"):
        return None
    return angka if _POLA_WA.fullmatch(angka) else None


def _periksa_id_akun(id_akun) -> None:
    if not id_akun_sah(id_akun):
        raise ValueError("id_akun tidak sah")


def _periksa_waktu(sekarang) -> None:
    if type(sekarang) is not str:
        raise ValueError("waktu harus string ISO")
    try:
        datetime.fromisoformat(sekarang)
    except ValueError:
        raise ValueError("waktu bukan format ISO") from None


def simpan(kon, id_akun, wa_ternormalisasi, sekarang) -> None:
    """Upsert kontak akun di transaksi pemanggil (tanpa commit).

    `dibuat` tetap pada pemanggilan berikutnya; `diperbarui` dan
    `aktivitas_terakhir` mengikuti `sekarang`.
    """
    _periksa_id_akun(id_akun)
    if type(wa_ternormalisasi) is not str or normalisasi_wa(wa_ternormalisasi) != wa_ternormalisasi:
        raise ValueError("nomor WhatsApp belum ternormalisasi")
    _periksa_waktu(sekarang)
    kon.execute(
        """INSERT INTO kontak_akun(id_akun, wa, dibuat, diperbarui, aktivitas_terakhir)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(id_akun) DO UPDATE SET
               wa = excluded.wa,
               diperbarui = excluded.diperbarui,
               aktivitas_terakhir = excluded.aktivitas_terakhir""",
        (id_akun, wa_ternormalisasi, sekarang, sekarang, sekarang),
    )


def ambil(kon, id_akun) -> dict | None:
    """Baris kontak sebagai dict baru, atau None bila akun belum punya kontak."""
    _periksa_id_akun(id_akun)
    baris = kon.execute(
        "SELECT " + ", ".join(_KOLOM) + " FROM kontak_akun WHERE id_akun = ?",
        (id_akun,),
    ).fetchone()
    return None if baris is None else dict(zip(_KOLOM, tuple(baris)))


def hapus(kon, id_akun) -> bool:
    """Hapus kontak akun di transaksi pemanggil; True bila ada baris terhapus."""
    _periksa_id_akun(id_akun)
    return kon.execute("DELETE FROM kontak_akun WHERE id_akun = ?", (id_akun,)).rowcount > 0


def _waktu_baku(sekarang) -> datetime:
    """Waktu ISO menjadi datetime naif UTC (zona dibuang setelah dikonversi)."""
    _periksa_waktu(sekarang)
    waktu = datetime.fromisoformat(sekarang)
    if waktu.tzinfo is not None:
        waktu = waktu.astimezone(timezone.utc).replace(tzinfo=None)
    return waktu


def sentuh_aktivitas(kon, id_akun, sekarang) -> bool:
    """Majukan `aktivitas_terakhir` bila tanggalnya lebih tua dari hari `sekarang`.

    Throttle: maksimal satu tulis per hari per akun. Tidak pernah membuat baris
    baru (akun tanpa kontak tidak ditulis). Di transaksi pemanggil, tanpa commit.
    True bila ada baris yang ditulis.
    """
    _periksa_id_akun(id_akun)
    waktu = _waktu_baku(sekarang).strftime(_FORMAT_WAKTU)
    return kon.execute(
        """UPDATE kontak_akun SET aktivitas_terakhir = ?
           WHERE id_akun = ?
             AND substr(aktivitas_terakhir, 1, ?) < substr(?, 1, ?)""",
        (waktu, id_akun, _PANJANG_TANGGAL, waktu, _PANJANG_TANGGAL),
    ).rowcount > 0


def _periksa_akun_hidup(id_akun_hidup) -> None:
    """Guard: daftar akun gagal dibaca tidak boleh berubah menjadi 'semua yatim'."""
    if type(id_akun_hidup) not in (set, frozenset) or not id_akun_hidup:
        raise ValueError("daftar akun hidup harus himpunan tidak kosong")
    if not all(id_akun_sah(i) for i in id_akun_hidup):
        raise ValueError("daftar akun hidup memuat id_akun tidak sah")


def _hapus_kedaluwarsa(kon, sekarang: datetime) -> int:
    batas = (sekarang - timedelta(days=RETENSI_HARI)).strftime(_FORMAT_WAKTU)
    return kon.execute(
        "DELETE FROM kontak_akun WHERE aktivitas_terakhir < ?", (batas,)
    ).rowcount


def _hapus_yatim(kon, id_akun_hidup) -> int:
    ada = [r[0] for r in kon.execute("SELECT id_akun FROM kontak_akun")]
    yatim = [(i,) for i in ada if i not in id_akun_hidup]
    kon.executemany("DELETE FROM kontak_akun WHERE id_akun = ?", yatim)
    return len(yatim)


def sapu_kontak(kon, id_akun_hidup, sekarang) -> dict:
    """Hapus kontak kedaluwarsa (> `RETENSI_HARI`) dan yatim (akun tidak hidup).

    `id_akun_hidup` wajib `set`/`frozenset` tidak kosong berisi id_akun sah; selain
    itu ValueError dan tidak ada yang dihapus. Atomik lewat SAVEPOINT: gagal di
    tengah berarti rollback utuh (bila tanpa transaksi pemanggil, RELEASE
    meng-commit hasilnya). Baris yang kedaluwarsa sekaligus yatim dihitung sebagai
    kedaluwarsa. Hasil hanya agregat, tanpa nomor atau id.
    """
    _periksa_akun_hidup(id_akun_hidup)
    waktu = _waktu_baku(sekarang)
    kon.execute("SAVEPOINT " + _SAVEPOINT_SAPU)
    try:
        hasil = {
            "kedaluwarsa": _hapus_kedaluwarsa(kon, waktu),
            "yatim": _hapus_yatim(kon, id_akun_hidup),
        }
    except Exception:
        kon.execute("ROLLBACK TO " + _SAVEPOINT_SAPU)
        kon.execute("RELEASE " + _SAVEPOINT_SAPU)
        raise
    kon.execute("RELEASE " + _SAVEPOINT_SAPU)
    return hasil
