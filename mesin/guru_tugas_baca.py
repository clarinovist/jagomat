"""Pembacaan tugas guru (SELECT saja): anak yang tertaut ke guru, dan skor ringkas sesi tugas.

Tertaut (keputusan Pemilik T3): order `kelas_order` yang statusnya AKTIF menurut `kelas_status` DAN masa aksesnya
TERBUKTI belum berakhir (tanpa baris `kelas_akses` dianggap habis, fail-closed), dengan penempatan di kelompok Mini
milik guru ATAU penempatan Private milik guru (`kelompok_id IS NULL`).
`siswa_id` selalu diturunkan dari order di server, tidak pernah dari form atau URL. Kepemilikan ditegakkan di SQL.

Skor (`skor_ringkas`, `selesai_himpunan`) dibaca dari `latihan.db` lewat koneksi yang dibuka pemanggil. Hanya
`selesai`, `benar`, dan `total` yang keluar; kunci, malrule, kode diagnosis, jawaban, dan pembahasan tidak pernah
diambil. Modul ini tidak menulis dan tidak membuat berkas.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

import kelas_dasar as dasar
import kelas_status as ks

ID_MAKS = 2 ** 63 - 1  # batas INTEGER SQLite
PANJANG_POTONGAN_PASANGAN = 400  # dua parameter per pasangan; di bawah batas variabel SQLite

# Satu baris per penempatan. `jadwal_penempatan.order_id` PRIMARY KEY dan `kelas_akses.order_id` UNIQUE, jadi tidak
# ada duplikasi dan tidak perlu GROUP BY. Kepemilikan: Mini lewat `jadwal_kelompok.guru_id`, Private lewat `p.guru_id`.
_SQL_KANDIDAT = (
    "SELECT o.id AS order_id, o.siswa_id, o.kedaluwarsa, p.kelompok_id, a.berakhir AS berakhir "
    "FROM jadwal_penempatan p "
    "JOIN kelas_order o ON o.id=p.order_id "
    "LEFT JOIN kelas_akses a ON a.order_id=o.id "
    "LEFT JOIN jadwal_kelompok k ON k.id=p.kelompok_id "
    "WHERE ((p.kelompok_id IS NOT NULL AND k.guru_id=?) OR (p.kelompok_id IS NULL AND p.guru_id=?)) "
    "AND o.siswa_id IS NOT NULL"
)
_SQL_SATU_ORDER = " AND o.id=?"

# Sesi dihitung hanya bila pasangan (id, siswa) cocok; sesi dibatalkan dibuang. `{nilai}` diisi "(?, ?)" berulang.
_SQL_SKOR = (
    "WITH pasangan(sesi_id, siswa_id) AS (VALUES {nilai}) "
    "SELECT s.id AS sesi_id, s.selesai IS NOT NULL AS selesai, COUNT(ss.id) AS total, "
    "COALESCE(SUM(d.benar), 0) AS benar "
    "FROM pasangan p JOIN sesi s ON s.id=p.sesi_id AND s.siswa_id=p.siswa_id "
    "LEFT JOIN sesi_soal ss ON ss.sesi_id=s.id "
    "LEFT JOIN jawaban j ON j.sesi_soal_id=ss.id "
    "LEFT JOIN diagnosis d ON d.jawaban_id=j.id "
    "WHERE s.dibatalkan IS NULL GROUP BY s.id"
)


def _teks(nilai) -> bool:
    return isinstance(nilai, str)


def _id_sah(nilai) -> bool:
    return type(nilai) is int and 1 <= nilai <= ID_MAKS


# --- tautan guru -> anak -----------------------------------------------------------------------

def _kandidat(kon, guru_akun: str, order_id: Optional[str] = None) -> list:
    """Penempatan yang bergguru `guru_akun` (Mini atau Private), opsional hanya satu order. Hanya SELECT."""
    sql, parameter = _SQL_KANDIDAT, (guru_akun, guru_akun)
    if order_id is not None:
        sql, parameter = sql + _SQL_SATU_ORDER, parameter + (order_id,)
    return kon.execute(sql, parameter).fetchall()


def _akses_habis(berakhir: Optional[str], waktu: str) -> bool:
    """Habis bila `berakhir <= waktu`, atau bila tidak ada baris akses (`berakhir` None).

    Fail-closed (keputusan sesi utama, T3): akses yang tidak terbukti masih berlaku dianggap habis, sehingga tugas
    tidak diberikan. Ini sengaja lebih ketat daripada tampilan jadwal guru (`guru_jadwal_baca`), yang tidak menandai
    habis pada keadaan itu.
    """
    return berakhir is None or berakhir <= waktu


def _tertaut_aktif(kon, baris, waktu: str) -> bool:
    """Order lunas (AKTIF menurut kelas_status) dan masa aksesnya belum berakhir (T3)."""
    fakta = ks.fakta_order(kon, baris["order_id"])
    aktif = ks.status_dari(baris, fakta, waktu) == dasar.STATUS_AKTIF
    return aktif and not _akses_habis(baris["berakhir"], waktu)


def _ke_tertaut(baris) -> dict:
    return {"order_id": baris["order_id"], "siswa_id": int(baris["siswa_id"]),
            "kelompok_id": baris["kelompok_id"]}


def daftar_tertaut(kon_jadwal, guru_akun: str, kini) -> List[dict]:
    """Anak yang tertaut ke guru: `{order_id, siswa_id, kelompok_id}` (`kelompok_id` None untuk Private), urut order_id.

    `kini` disuntik pemanggil; tidak ada jam sistem di dalam fungsi. `guru_akun` yang bukan teks menghasilkan daftar kosong.
    """
    if not _teks(guru_akun):
        return []
    waktu = dasar.ke_baku(kini)
    tertaut = [_ke_tertaut(b) for b in _kandidat(kon_jadwal, guru_akun)
               if _tertaut_aktif(kon_jadwal, b, waktu)]
    return sorted(tertaut, key=lambda t: t["order_id"])


def anak_tertaut(kon_jadwal, guru_akun: str, order_id, kini) -> Optional[int]:
    """`siswa_id` bila `order_id` termasuk tautan guru itu; selain itu None.

    Order tidak ada, milik guru lain, belum lunas, dibatalkan, kedaluwarsa, akses berakhir, dan penempatan dilepas
    semuanya None, tanpa membedakan alasan (pemanggil memberi 404 yang sama). Filter order dan guru ada di SQL.
    """
    if not (_teks(guru_akun) and _teks(order_id)):
        return None
    waktu = dasar.ke_baku(kini)
    for baris in _kandidat(kon_jadwal, guru_akun, order_id):
        if _tertaut_aktif(kon_jadwal, baris, waktu):
            return int(baris["siswa_id"])
    return None


# --- skor ringkas sesi (DB belajar, hanya selesai/benar/total) ---------------------------------

def _pasangan_sah(pasangan: Iterable[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Salin pasangan (sesi_id, siswa_id) tanpa duplikat; galat eksplisit bila ada id yang bukan bilangan bulat sah."""
    hasil = []
    for sesi_id, siswa_id in pasangan:
        if not (_id_sah(sesi_id) and _id_sah(siswa_id)):
            raise ValueError("Pasangan sesi dan anak tidak sah.")
        hasil.append((sesi_id, siswa_id))
    return sorted(set(hasil))


def _potong(daftar: list, ukuran: int) -> List[list]:
    return [daftar[i:i + ukuran] for i in range(0, len(daftar), ukuran)]


def _kueri_skor(kon, potongan: list) -> list:
    nilai = ", ".join(["(?, ?)"] * len(potongan))
    parameter = [isi for pasangan in potongan for isi in pasangan]
    return kon.execute(_SQL_SKOR.format(nilai=nilai), parameter).fetchall()


def _ke_skor(baris) -> dict:
    selesai = bool(baris["selesai"])
    return {"selesai": selesai, "benar": int(baris["benar"]) if selesai else None, "total": int(baris["total"])}


def skor_ringkas(kon_belajar, pasangan: Iterable[Tuple[int, int]]) -> Dict[int, dict]:
    """`{sesi_id: {"selesai", "benar", "total"}}` untuk pasangan (sesi_id, siswa_id) yang cocok di latihan.db.

    `total` = jumlah soal sesi. `benar` hanya terisi bila sesi selesai (dikirim). Sesi dibatalkan dan pasangan
    dengan siswa_id yang tidak cocok TIDAK muncul. Hanya SELECT, dibagi per potongan agar tidak melewati batas parameter.
    """
    potongan_daftar = _potong(_pasangan_sah(pasangan), PANJANG_POTONGAN_PASANGAN)
    baris_semua = [b for potongan in potongan_daftar for b in _kueri_skor(kon_belajar, potongan)]
    return {int(b["sesi_id"]): _ke_skor(b) for b in baris_semua}


def selesai_himpunan(kon_belajar, pasangan: Iterable[Tuple[int, int]]) -> Set[int]:
    """Id sesi yang sudah dikirim (selesai) dari pasangan yang cocok. Tanpa skor: untuk sisi anak."""
    return {sid for sid, nilai in skor_ringkas(kon_belajar, pasangan).items() if nilai["selesai"]}
