"""Penyimpanan laporan guru -> orang tua dan tautan baca-saja satu anak.

Dua tabel milik modul ini: ``laporan_ortu`` (kepala + snapshot presentasi
JSON) dan ``tautan_laporan`` (capability baca-saja). Aturan yang ditegakkan
di sini, bukan hanya di rute HTTP:

- Laporan **terbit** append-only: catatan tidak bisa diubah dan draf terbit
  tidak bisa dihapus. Koreksi = laporan baru (keputusan pemilik).
- Token mentah hanya dikembalikan sekali; basis data menyimpan SHA-256.
- Terbit = satu UPDATE ``diterbitkan`` + rotasi token. Satu tautan aktif per
  anak: laporan baru mematikan tautan lama, tanpa perpanjangan otomatis.
- Tidak ada kolom kontak. Pengiriman = guru menyalin tautan.

Modul ini hanya menulis dua tabel di atas; bukti/sesi tidak pernah disentuh.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone

# 30 hari (keputusan pemilik): orang tua perlu waktu membaca/mencetak, tanpa
# perpanjangan otomatis dan selalu bisa dicabut.
TTL_DETIK = 30 * 24 * 60 * 60
POLA_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
BATAS_CATATAN = 2000
POLA_PERIODE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

_WIB = timezone(timedelta(hours=7))


def sekarang_detik() -> int:
    """Jam dinding; satu titik agar test bisa membekukan waktu."""
    return int(time.time())


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def tanggal_wib(epoch: int) -> date:
    return datetime.fromtimestamp(int(epoch), _WIB).date()


def _waktu_wib(epoch: int) -> str:
    """Stempel yang sama bentuknya dengan datetime('now', '+7 hours')."""
    return datetime.fromtimestamp(int(epoch), _WIB).strftime("%Y-%m-%d %H:%M:%S")


def _periode_sah(mulai: str, akhir: str) -> bool:
    if not (isinstance(mulai, str) and isinstance(akhir, str)
            and POLA_PERIODE.match(mulai) and POLA_PERIODE.match(akhir)):
        return False
    try:
        return date.fromisoformat(mulai) <= date.fromisoformat(akhir)
    except ValueError:
        return False


def catatan_aman(teks: str) -> str:
    """Teks polos: tanpa NUL/kontrol selain baris baru dan tab."""
    if not isinstance(teks, str):
        raise ValueError("catatan harus teks")
    normal = teks.replace("\r\n", "\n").replace("\r", "\n")
    if any(ord(x) < 32 and x not in "\n\t" for x in normal):
        raise ValueError("catatan memuat karakter yang tidak didukung")
    normal = normal.rstrip()
    if len(normal) > BATAS_CATATAN:
        raise ValueError("catatan terlalu panjang")
    return normal


def daftar(kon: sqlite3.Connection, siswa_id: int) -> list[sqlite3.Row]:
    """Kepala laporan satu anak, terbaru dulu; tanpa kolom JSON berat."""
    return kon.execute(
        """SELECT id, siswa_id, periode_mulai, periode_akhir, catatan, guru,
                  dibuat, diterbitkan, kejadian_terakhir
           FROM laporan_ortu WHERE siswa_id = ? ORDER BY id DESC""",
        (siswa_id,),
    ).fetchall()


def ambil(
    kon: sqlite3.Connection, laporan_id: int, siswa_id: int | None = None
) -> sqlite3.Row | None:
    """Satu laporan; pemanggil wajib mengikatkan siswa_id untuk rute guru."""
    if siswa_id is None:
        return kon.execute(
            "SELECT * FROM laporan_ortu WHERE id = ?", (laporan_id,)
        ).fetchone()
    return kon.execute(
        "SELECT * FROM laporan_ortu WHERE id = ? AND siswa_id = ?",
        (laporan_id, siswa_id),
    ).fetchone()


def buat_draf(
    kon: sqlite3.Connection,
    siswa_id: int,
    periode_mulai: str,
    periode_akhir: str,
    isi: str,
    *,
    catatan: str = "",
    guru: str = "",
) -> int:
    """Simpan draf (belum bisa dibuka lewat tautan)."""
    if not _periode_sah(periode_mulai, periode_akhir):
        raise ValueError("periode tidak sah")
    if not isinstance(isi, str) or not isi:
        raise ValueError("isi laporan kosong")
    cur = kon.execute(
        """INSERT INTO laporan_ortu
               (siswa_id, periode_mulai, periode_akhir, catatan, isi, guru)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (siswa_id, periode_mulai, periode_akhir,
         catatan_aman(catatan), isi, guru),
    )
    return int(cur.lastrowid)


def simpan_catatan(
    kon: sqlite3.Connection, laporan_id: int, siswa_id: int, catatan: str
) -> bool:
    """Hanya draf; laporan terbit menolak (append-only)."""
    aman = catatan_aman(catatan)
    cur = kon.execute(
        """UPDATE laporan_ortu SET catatan = ?
           WHERE id = ? AND siswa_id = ? AND diterbitkan IS NULL""",
        (aman, laporan_id, siswa_id),
    )
    return cur.rowcount == 1


def hapus_draf(kon: sqlite3.Connection, laporan_id: int, siswa_id: int) -> bool:
    """Hanya draf; laporan terbit tidak pernah dihapus (hanya tautannya)."""
    cur = kon.execute(
        """DELETE FROM laporan_ortu
           WHERE id = ? AND siswa_id = ? AND diterbitkan IS NULL""",
        (laporan_id, siswa_id),
    )
    return cur.rowcount == 1


def _putar_token(
    kon: sqlite3.Connection, laporan_id: int, siswa_id: int, sekarang: int
) -> str:
    """Satu-satunya penulis token; menimpa baris anak ini (rotasi)."""
    terbit = kon.execute(
        """SELECT 1 FROM laporan_ortu
           WHERE id = ? AND siswa_id = ? AND diterbitkan IS NOT NULL""",
        (laporan_id, siswa_id),
    ).fetchone()
    if terbit is None:
        raise ValueError("laporan belum terbit")
    token = secrets.token_urlsafe(32)
    kon.execute(
        """INSERT INTO tautan_laporan
               (siswa_id, laporan_id, token_hash, dibuat, kedaluarsa, dicabut)
           VALUES (?, ?, ?, ?, ?, NULL)
           ON CONFLICT(siswa_id) DO UPDATE SET
               laporan_id = excluded.laporan_id,
               token_hash = excluded.token_hash,
               dibuat = excluded.dibuat,
               kedaluarsa = excluded.kedaluarsa,
               dicabut = NULL""",
        (siswa_id, laporan_id, _hash(token), sekarang, sekarang + TTL_DETIK),
    )
    return token


def terbitkan(
    kon: sqlite3.Connection,
    laporan_id: int,
    siswa_id: int,
    kejadian_terakhir: int,
    guru: str,
    sekarang: int | None = None,
) -> str | None:
    """Terbitkan draf + rotasi token dalam satu transaksi milik pemanggil.

    ``None`` berarti draf tidak ada, milik anak lain, atau sudah terbit.
    """
    kini = sekarang_detik() if sekarang is None else int(sekarang)
    cur = kon.execute(
        """UPDATE laporan_ortu
           SET diterbitkan = ?, guru = ?, kejadian_terakhir = ?
           WHERE id = ? AND siswa_id = ? AND diterbitkan IS NULL""",
        (_waktu_wib(kini), guru, int(kejadian_terakhir), laporan_id, siswa_id),
    )
    if cur.rowcount != 1:
        return None
    return _putar_token(kon, laporan_id, siswa_id, kini)


def ganti_tautan(
    kon: sqlite3.Connection,
    laporan_id: int,
    siswa_id: int,
    sekarang: int | None = None,
) -> str | None:
    """Token baru untuk laporan yang sudah terbit; token lama langsung mati."""
    kini = sekarang_detik() if sekarang is None else int(sekarang)
    try:
        return _putar_token(kon, laporan_id, siswa_id, kini)
    except ValueError:
        return None


def tautan_aktif(
    kon: sqlite3.Connection, siswa_id: int, sekarang: int | None = None
) -> sqlite3.Row | None:
    """Status tautan anak ini; token/hash tidak pernah ikut dikembalikan."""
    kini = sekarang_detik() if sekarang is None else int(sekarang)
    return kon.execute(
        """SELECT t.laporan_id, t.dibuat, t.kedaluarsa, t.dicabut,
                  (t.dicabut IS NULL AND t.kedaluarsa > ?) AS dapat_dibuka
           FROM tautan_laporan t WHERE t.siswa_id = ?""",
        (kini, siswa_id),
    ).fetchone()


def cabut_tautan(
    kon: sqlite3.Connection, siswa_id: int, sekarang: int | None = None
) -> bool:
    """Cabut tautan aktif; idempoten (panggilan kedua ``False``)."""
    kini = sekarang_detik() if sekarang is None else int(sekarang)
    cur = kon.execute(
        """UPDATE tautan_laporan SET dicabut = ?
           WHERE siswa_id = ? AND dicabut IS NULL""",
        (kini, siswa_id),
    )
    return cur.rowcount > 0


def ambil_tautan(
    kon: sqlite3.Connection, token: str, sekarang: int | None = None
) -> sqlite3.Row | None:
    """Baca-saja: token sah + terbit + belum kedaluwarsa + belum dicabut.

    Satu kueri, tanpa menyentuh soal/kunci/diagnosis. Nama anak ikut karena
    identitas dibaca live (koreksi nama harus terlihat).
    """
    if not isinstance(token, str) or not POLA_TOKEN.fullmatch(token):
        return None
    kini = sekarang_detik() if sekarang is None else int(sekarang)
    return kon.execute(
        """SELECT l.id AS laporan_id, l.siswa_id, l.periode_mulai,
                  l.periode_akhir, l.catatan, l.isi, l.guru, l.diterbitkan,
                  t.kedaluarsa, w.nama AS nama
           FROM tautan_laporan t
           JOIN laporan_ortu l
                ON l.id = t.laporan_id AND l.siswa_id = t.siswa_id
           JOIN siswa w ON w.id = t.siswa_id
           WHERE t.token_hash = ?
             AND t.dicabut IS NULL
             AND t.kedaluarsa > ?
             AND l.diterbitkan IS NOT NULL""",
        (_hash(token), kini),
    ).fetchone()
