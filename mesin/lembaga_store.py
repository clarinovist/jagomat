"""Penyimpanan lembaga les: keanggotaan, ringkasan agregat, dan pindah anak.

Seluruh SQL lembaga ada di sini. Pemilik les tidak memperoleh akses ke halaman
sesi/anak guru anggota (helper kepemilikan di ``student_profile_store`` tidak
disentuh); ia hanya melihat agregat dan boleh memindahkan anak antar guru
lembaganya. ``pindahkan`` dipanggil caller yang sudah membuka ``BEGIN IMMEDIATE``
dan memeriksa ulang SEMUA predikat di dalamnya; penolakan tidak menulis apa pun.
"""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Tuple

STATUS_OK = "ok"
STATUS_TIDAK_BERWENANG = "tidak_berwenang"
STATUS_SAMA = "sama"
STATUS_BENTROK_NAMA = "bentrok_nama"
STATUS_SESI_BERJALAN = "sesi_berjalan"
STATUS_PENOLAKAN_BISNIS = frozenset((STATUS_SAMA, STATUS_BENTROK_NAMA, STATUS_SESI_BERJALAN))

# Operasi baca foto yang belum final; `unknown` ikut ditahan (pilihan restriktif).
_STATUS_FOTO_BELUM_FINAL = ("reserved", "sent", "unknown")
BATAS_NAMA = 80


class PenolakanLembaga(ValueError):
    """Perubahan keanggotaan/pembuatan lembaga melanggar aturan."""


@dataclass(frozen=True)
class HasilPindah:
    status: str
    dari: str = ""

    @property
    def berhasil(self) -> bool:
        return self.status == STATUS_OK


@dataclass(frozen=True)
class AnakRingkas:
    siswa_id: int
    nama: str
    jumlah_sesi: int
    sesi_terakhir: str
    menunggu_konfirmasi: int


@dataclass(frozen=True)
class GuruRingkas:
    guru: str
    anak: Tuple[AnakRingkas, ...]


def lembaga_milik(kon: sqlite3.Connection, pengguna: str):
    """Baris lembaga yang dimiliki ``pengguna``, atau None."""
    if not pengguna:
        return None
    return kon.execute(
        "SELECT id, nama, pemilik FROM lembaga WHERE pemilik = ?", (pengguna,)
    ).fetchone()


def lembaga_dari_anggota(kon: sqlite3.Connection, guru: str):
    """Baris lembaga tempat ``guru`` menjadi anggota, atau None."""
    if not guru:
        return None
    return kon.execute(
        "SELECT l.id, l.nama, l.pemilik FROM anggota_lembaga a "
        "JOIN lembaga l ON l.id = a.lembaga_id WHERE a.guru = ?", (guru,)
    ).fetchone()


def anggota(kon: sqlite3.Connection, lembaga_id: int) -> Tuple[str, ...]:
    """Nama guru anggota (tanpa pemilik), urut abjad."""
    return tuple(r[0] for r in kon.execute(
        "SELECT guru FROM anggota_lembaga WHERE lembaga_id = ? ORDER BY guru",
        (lembaga_id,),
    ))


def _bersih_nama(guru: str) -> str:
    if not isinstance(guru, str) or not guru.strip() or guru != guru.strip():
        raise PenolakanLembaga("nama guru tidak sah")
    return guru


def _sudah_terikat(kon: sqlite3.Connection, guru: str) -> bool:
    return lembaga_milik(kon, guru) is not None or lembaga_dari_anggota(kon, guru) is not None


def buat_lembaga(kon: sqlite3.Connection, *, nama: str, pemilik: str) -> int:
    """Buat lembaga; pemilik belum boleh memiliki/menjadi anggota lembaga mana pun."""
    pemilik = _bersih_nama(pemilik)
    nama = nama.strip() if isinstance(nama, str) else ""
    if not 1 <= len(nama) <= BATAS_NAMA:
        raise PenolakanLembaga("nama lembaga tidak sah")
    if _sudah_terikat(kon, pemilik):
        raise PenolakanLembaga("guru sudah terikat pada lembaga")
    return int(kon.execute(
        "INSERT INTO lembaga (nama, pemilik) VALUES (?, ?)", (nama, pemilik)
    ).lastrowid)


def tambah_anggota(kon: sqlite3.Connection, *, lembaga_id: int, guru: str) -> None:
    """Tambah guru anggota; satu guru hanya satu lembaga dan pemilik bukan anggota."""
    guru = _bersih_nama(guru)
    if kon.execute("SELECT 1 FROM lembaga WHERE id = ?", (lembaga_id,)).fetchone() is None:
        raise PenolakanLembaga("lembaga tidak ada")
    if _sudah_terikat(kon, guru):
        raise PenolakanLembaga("guru sudah terikat pada lembaga")
    kon.execute(
        "INSERT INTO anggota_lembaga (lembaga_id, guru) VALUES (?, ?)", (lembaga_id, guru)
    )


def bubarkan_lembaga(kon: sqlite3.Connection, *, lembaga_id: int) -> None:
    """Hapus lembaga beserta keanggotaannya; anak dan jejak pindah tetap ada.

    ``pindah_siswa.lembaga_id`` bukan FK, jadi jejak lama tidak ikut terhapus.
    """
    kon.execute("DELETE FROM anggota_lembaga WHERE lembaga_id = ?", (lembaga_id,))
    if kon.execute("DELETE FROM lembaga WHERE id = ?", (lembaga_id,)).rowcount != 1:
        raise PenolakanLembaga("lembaga tidak ada")


def nama_lembaga_terikat(kon: sqlite3.Connection, guru: str):
    """Nama lembaga tempat ``guru`` menjadi pemilik/anggota, atau None."""
    baris = lembaga_milik(kon, guru) or lembaga_dari_anggota(kon, guru)
    return baris["nama"] if baris is not None else None


def lepas_anggota(kon: sqlite3.Connection, *, lembaga_id: int, guru: str) -> None:
    """Lepas anggota; anak yang sudah dipindahkan tetap milik gurunya."""
    kur = kon.execute(
        "DELETE FROM anggota_lembaga WHERE lembaga_id = ? AND guru = ?", (lembaga_id, guru)
    )
    if kur.rowcount != 1:
        raise PenolakanLembaga("guru bukan anggota lembaga ini")


def daftar_lembaga(kon: sqlite3.Connection) -> Tuple[Tuple[sqlite3.Row, Tuple[str, ...]], ...]:
    """Semua lembaga beserta anggotanya, untuk halaman admin."""
    return tuple(
        (baris, anggota(kon, int(baris["id"])))
        for baris in kon.execute("SELECT id, nama, pemilik FROM lembaga ORDER BY nama, id")
    )


def guru_terikat(kon: sqlite3.Connection) -> frozenset:
    """Nama guru yang sudah menjadi pemilik atau anggota lembaga mana pun."""
    return frozenset(
        r[0] for r in kon.execute(
            "SELECT pemilik FROM lembaga UNION SELECT guru FROM anggota_lembaga")
    )


def _anak_guru(kon: sqlite3.Connection, guru: str) -> Tuple[AnakRingkas, ...]:
    baris = kon.execute(
        """SELECT w.id, w.nama,
             (SELECT COUNT(*) FROM sesi s
               WHERE s.siswa_id = w.id AND s.dibatalkan IS NULL),
             (SELECT MAX(s.tanggal) FROM sesi s
               WHERE s.siswa_id = w.id AND s.dibatalkan IS NULL),
             (SELECT COUNT(*) FROM sesi s
               WHERE s.siswa_id = w.id AND s.dibatalkan IS NULL
                 AND s.selesai IS NOT NULL AND s.dikonfirmasi_guru IS NULL)
           FROM siswa w WHERE w.pemilik = ? ORDER BY w.nama, w.id""",
        (guru,),
    ).fetchall()
    return tuple(AnakRingkas(int(r[0]), r[1], int(r[2]), r[3] or "", int(r[4])) for r in baris)


def ringkasan(kon: sqlite3.Connection, lembaga) -> Tuple[GuruRingkas, ...]:
    """Agregat per guru (pemilik dulu, anggota urut abjad); tanpa isi belajar."""
    guru = (lembaga["pemilik"], *anggota(kon, int(lembaga["id"])))
    return tuple(GuruRingkas(g, _anak_guru(kon, g)) for g in guru)


def _sesi_berjalan(kon: sqlite3.Connection, siswa_id: int) -> bool:
    if kon.execute(
        """SELECT 1 FROM sesi WHERE siswa_id = ? AND dibatalkan IS NULL
             AND dikonfirmasi_guru IS NULL
             AND (mulai IS NOT NULL OR selesai IS NOT NULL) LIMIT 1""",
        (siswa_id,),
    ).fetchone():
        return True
    # Tabel receipt foto bersifat opt-in; periksa hanya bila ada.
    if kon.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='operasi_foto_baca'"
    ).fetchone() is None:
        return False
    tanda = ",".join("?" for _ in _STATUS_FOTO_BELUM_FINAL)
    return kon.execute(
        "SELECT 1 FROM operasi_foto_baca o JOIN sesi s ON s.id = o.sesi_id "
        "WHERE s.siswa_id = ? AND o.status IN (%s) LIMIT 1" % tanda,
        (siswa_id, *_STATUS_FOTO_BELUM_FINAL),
    ).fetchone() is not None


def _penghuni(kon: sqlite3.Connection, lembaga) -> frozenset:
    return frozenset((lembaga["pemilik"], *anggota(kon, int(lembaga["id"]))))


def pindahkan(kon: sqlite3.Connection, *, oleh: str, siswa_id: int, ke: str) -> HasilPindah:
    """Pindahkan anak ke guru lain di lembaga yang sama (di dalam BEGIN IMMEDIATE).

    Urutan: kewenangan dulu (status ``tidak_berwenang`` tanpa membedakan sebab),
    lalu penolakan bisnis. Penulisan hanya di akhir: satu UPDATE kepemilikan
    yang dijaga pemilik lama, lalu satu baris jejak.
    """
    lembaga = lembaga_milik(kon, oleh)
    if lembaga is None or not isinstance(siswa_id, int) or not isinstance(ke, str):
        return HasilPindah(STATUS_TIDAK_BERWENANG)
    penghuni = _penghuni(kon, lembaga)
    anak = kon.execute("SELECT nama, pemilik FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
    if anak is None or anak["pemilik"] not in penghuni or ke not in penghuni:
        return HasilPindah(STATUS_TIDAK_BERWENANG)
    dari = anak["pemilik"]
    if ke == dari:
        return HasilPindah(STATUS_SAMA, dari)
    if kon.execute(
        "SELECT 1 FROM siswa WHERE nama = ? AND pemilik = ?", (anak["nama"], ke)
    ).fetchone():
        return HasilPindah(STATUS_BENTROK_NAMA, dari)
    if _sesi_berjalan(kon, siswa_id):
        return HasilPindah(STATUS_SESI_BERJALAN, dari)
    kur = kon.execute(
        "UPDATE siswa SET pemilik = ? WHERE id = ? AND pemilik = ?", (ke, siswa_id, dari)
    )
    if kur.rowcount != 1:
        raise RuntimeError("kepemilikan anak berubah saat dipindahkan")
    kon.execute(
        "INSERT INTO pindah_siswa (siswa_id, lembaga_id, dari, ke, oleh) VALUES (?,?,?,?,?)",
        (siswa_id, int(lembaga["id"]), dari, ke, oleh),
    )
    return HasilPindah(STATUS_OK, dari)
