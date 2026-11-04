"""Penyimpanan laporan guru -> orang tua. Hanya menulis dua tabel laporan sendiri.

Bukti belajar (konfirmasi_hasil, snapshot_outcome, kejadian_belajar) tidak pernah
ditulis di sini. Semua fungsi memerlukan `siswa_id` yang cocok dengan baris
laporan, sehingga pemanggil yang sudah memeriksa kepemilikan anak tidak dapat
menyentuh laporan anak lain.
"""
from __future__ import annotations

import json
import time

import parent_report_links as tautan

BATAS_CATATAN = 2000


def _kini(sekarang):
    return int(time.time() if sekarang is None else sekarang)


def buat_draf(kon, siswa_id: int, mulai: str, akhir: str, isi: dict) -> int:
    """Buat draf; snapshot `isi` dihitung server, bukan input pengguna."""
    cur = kon.execute(
        "INSERT INTO laporan_ortu (siswa_id, periode_mulai, periode_akhir, isi) VALUES (?, ?, ?, ?)",
        (siswa_id, mulai, akhir, json.dumps(isi, ensure_ascii=False, sort_keys=True)),
    )
    return cur.lastrowid


def ambil(kon, siswa_id: int, laporan_id: int):
    """Baris laporan milik anak ini, atau None (id asing = tidak ada)."""
    baris = kon.execute(
        "SELECT * FROM laporan_ortu WHERE id = ? AND siswa_id = ?", (laporan_id, siswa_id),
    ).fetchone()
    return dict(baris) if baris else None


def daftar(kon, siswa_id: int):
    return [dict(r) for r in kon.execute(
        "SELECT * FROM laporan_ortu WHERE siswa_id = ? ORDER BY id DESC", (siswa_id,))]


def simpan_catatan(kon, siswa_id: int, laporan_id: int, catatan: str) -> None:
    if not isinstance(catatan, str) or len(catatan) > BATAS_CATATAN:
        raise ValueError("catatan terlalu panjang")
    cur = kon.execute(
        "UPDATE laporan_ortu SET catatan = ? WHERE id = ? AND siswa_id = ? AND diterbitkan IS NULL",
        (catatan, laporan_id, siswa_id),
    )
    if cur.rowcount != 1:
        raise ValueError("laporan bukan draf milik anak ini")


def kejadian_terakhir(kon, siswa_id: int) -> int:
    return kon.execute(
        "SELECT COALESCE(MAX(id), 0) FROM kejadian_belajar WHERE siswa_id = ?", (siswa_id,),
    ).fetchone()[0]


def _pasang_tautan(kon, siswa_id: int, laporan_id: int, kini: int) -> str:
    token = tautan.token_baru()
    kon.execute(
        """INSERT INTO tautan_laporan (siswa_id, laporan_id, token_hash, dibuat, kedaluarsa, dicabut)
           VALUES (?, ?, ?, ?, ?, NULL)
           ON CONFLICT(siswa_id) DO UPDATE SET
               laporan_id = excluded.laporan_id, token_hash = excluded.token_hash,
               dibuat = excluded.dibuat, kedaluarsa = excluded.kedaluarsa, dicabut = NULL""",
        (siswa_id, laporan_id, tautan.hash_token(token), kini, kini + tautan.TTL_DETIK),
    )
    return token


def terbitkan(kon, siswa_id: int, laporan_id: int, guru: str, *, sekarang=None) -> str:
    """Terbit dan rotasi token dalam satu transaksi; token mentah dikembalikan sekali."""
    kini = _kini(sekarang)
    kejadian = kejadian_terakhir(kon, siswa_id)
    kon.execute("SAVEPOINT terbit_laporan")
    try:
        cur = kon.execute(
            """UPDATE laporan_ortu SET diterbitkan = datetime(?, 'unixepoch', '+7 hours'),
                      guru = ?, kejadian_terakhir = ?
               WHERE id = ? AND siswa_id = ? AND diterbitkan IS NULL""",
            (kini, guru, kejadian, laporan_id, siswa_id),
        )
        if cur.rowcount != 1:
            raise ValueError("laporan bukan draf milik anak ini")
        token = _pasang_tautan(kon, siswa_id, laporan_id, kini)
    except Exception:
        kon.execute("ROLLBACK TO terbit_laporan")
        kon.execute("RELEASE terbit_laporan")
        raise
    kon.execute("RELEASE terbit_laporan")
    return token


def ganti_tautan(kon, siswa_id: int, laporan_id: int, *, sekarang=None) -> str:
    """Token baru untuk laporan yang sudah terbit; token lama mati."""
    laporan = ambil(kon, siswa_id, laporan_id)
    if laporan is None or laporan["diterbitkan"] is None:
        raise ValueError("laporan belum terbit")
    return _pasang_tautan(kon, siswa_id, laporan_id, _kini(sekarang))


def cabut_tautan(kon, siswa_id: int, *, sekarang=None) -> bool:
    cur = kon.execute(
        "UPDATE tautan_laporan SET dicabut = ? WHERE siswa_id = ? AND dicabut IS NULL",
        (_kini(sekarang), siswa_id),
    )
    return cur.rowcount > 0


def hapus_draf(kon, siswa_id: int, laporan_id: int) -> bool:
    laporan = ambil(kon, siswa_id, laporan_id)
    if laporan is None:
        return False
    if laporan["diterbitkan"] is not None:
        raise ValueError("laporan terbit tidak dihapus")
    return kon.execute(
        "DELETE FROM laporan_ortu WHERE id = ? AND siswa_id = ? AND diterbitkan IS NULL",
        (laporan_id, siswa_id),
    ).rowcount == 1


def tautan_aktif(kon, siswa_id: int, *, sekarang=None):
    """Keadaan tautan untuk halaman guru (tanpa token): laporan_id + kedaluarsa, atau None."""
    baris = kon.execute(
        "SELECT laporan_id, kedaluarsa FROM tautan_laporan WHERE siswa_id = ? AND dicabut IS NULL AND kedaluarsa > ?",
        (siswa_id, _kini(sekarang)),
    ).fetchone()
    return dict(baris) if baris else None


def bukti_berubah(kon, siswa_id: int, laporan_id: int) -> int:
    """Jumlah kejadian belajar baru sejak laporan terbit (0 bila tidak berubah)."""
    laporan = ambil(kon, siswa_id, laporan_id)
    if laporan is None or laporan["diterbitkan"] is None:
        return 0
    return kon.execute(
        "SELECT COUNT(*) FROM kejadian_belajar WHERE siswa_id = ? AND id > ?",
        (siswa_id, laporan["kejadian_terakhir"]),
    ).fetchone()[0]


def ambil_dengan_token(kon, token, sekarang=None):
    """Isi laporan untuk token sah; selainnya None. Nama anak dibaca live."""
    if not tautan.token_sah(token):
        return None
    baris = kon.execute(
        """SELECT s.nama, l.isi, l.catatan, l.guru, l.periode_mulai, l.periode_akhir,
                  l.diterbitkan, t.kedaluarsa
           FROM tautan_laporan t
           JOIN laporan_ortu l ON l.id = t.laporan_id AND l.siswa_id = t.siswa_id
           JOIN siswa s ON s.id = t.siswa_id
           WHERE t.token_hash = ? AND t.dicabut IS NULL AND t.kedaluarsa > ?
             AND l.diterbitkan IS NOT NULL""",
        (tautan.hash_token(token), _kini(sekarang)),
    ).fetchone()
    if baris is None:
        return None
    return {"nama": baris["nama"], "isi": json.loads(baris["isi"]), "catatan": baris["catatan"],
            "guru": baris["guru"], "periode": (baris["periode_mulai"], baris["periode_akhir"]),
            "diterbitkan": baris["diterbitkan"], "kedaluarsa": baris["kedaluarsa"]}
