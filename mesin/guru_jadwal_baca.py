"""Pembacaan jadwal untuk guru (SELECT saja): pertemuan mendatang, kelas Mini milik guru, dan detailnya.

Kepemilikan DI SQL: Mini lewat `jadwal_kelompok.guru_id`, Private lewat `jadwal_penempatan.guru_id`. Guru yang
dipakai selalu disuntik pemanggil dari sesi, tidak pernah dari URL atau form. Hanya order berstatus aktif (lewat
`kelas_status`, sama dengan kartu orang tua) yang tampil sebagai anggota atau pertemuan Private. Modul ini tidak
menulis dan tidak membuat berkas; koneksi dibuka pemanggil (`jadwal_store.buka`, mode ro).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Set

import guru_pertemuan_aturan as aturan
import jadwal_dasar as jd
import kelas_dasar as dasar
import kelas_status as ks

_log = logging.getLogger(__name__)

PLACEHOLDER_NAMA = "Anak"
PERTEMUAN_ID_MIN = 1
PERTEMUAN_ID_MAKS = 2 ** 63 - 1  # batas INTEGER SQLite; id di luar rentang langsung None
DURASI_MAKS_MENIT = 180  # sama dengan schema_jadwal.MENIT_MAKS (dijaga tes)
JENDELA_BACA = aturan.JENDELA_KOREKSI + timedelta(minutes=DURASI_MAKS_MENIT)  # batas bawah kueri, lebih longgar
# Penempatan satu kelompok atau satu order Private, dengan masa akses terakhir per order (MAX, LEFT JOIN).
_SQL_ANGGOTA_KELOMPOK = (
    "SELECT p.order_id, o.siswa_id, p.dibuat, MAX(a.berakhir) AS berakhir "
    "FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id "
    "LEFT JOIN kelas_akses a ON a.order_id=p.order_id "
    "WHERE p.kelompok_id=? GROUP BY p.order_id, o.siswa_id, p.dibuat ORDER BY p.order_id"
)
_SQL_ANGGOTA_ORDER = (
    "SELECT p.order_id, o.siswa_id, p.dibuat, MAX(a.berakhir) AS berakhir "
    "FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id "
    "LEFT JOIN kelas_akses a ON a.order_id=p.order_id "
    "WHERE p.order_id=? AND p.kelompok_id IS NULL GROUP BY p.order_id, o.siswa_id, p.dibuat"
)
# Pertemuan yang sudah mulai dalam jendela baca. Parameter berurutan: (guru_id, waktu, batas).
_SQL_BERLANGSUNG_MINI = (
    "SELECT s.id, s.ke, s.mulai, s.menit, s.dibatalkan, k.id AS id_awal, k.nama AS nama_kelompok, "
    "NULL AS siswa_id FROM jadwal_pertemuan s JOIN jadwal_kelompok k ON k.id=s.kelompok_id "
    "WHERE k.guru_id=? AND s.mulai<=? AND s.mulai>=? ORDER BY s.id"
)
_SQL_BERLANGSUNG_PRIVAT = (
    "SELECT DISTINCT s.id, s.ke, s.mulai, s.menit, s.dibatalkan, s.order_id AS id_awal, "
    "NULL AS nama_kelompok, o.siswa_id FROM jadwal_pertemuan s JOIN jadwal_penempatan p ON p.order_id=s.order_id "
    "JOIN kelas_order o ON o.id=s.order_id "
    "WHERE p.guru_id=? AND p.kelompok_id IS NULL AND s.kelompok_id IS NULL AND s.mulai<=? AND s.mulai>=? "
    "ORDER BY s.id"
)


def _id_kelompok_sah(kelompok_id) -> bool:
    try:
        jd.periksa_kelompok_id(kelompok_id)
    except jd.JadwalTidakSah:
        return False
    return True


def _order_aktif_ids(kon, order_ids: Iterable[str], kini: str) -> Set[str]:
    """Himpunan id order yang statusnya aktif pada `kini` (diturunkan dari fakta, tidak disimpan)."""
    aktif = set()
    for order_id in set(order_ids):
        order = ks.baris_order(kon, order_id)
        if order is not None and ks.status_dari(order, ks.fakta_order(kon, order_id), kini) == dasar.STATUS_AKTIF:
            aktif.add(order_id)
    return aktif


def _akses_habis(berakhir: Optional[str], kini: str) -> bool:
    """Masa akses habis bila `berakhir <= kini`: akses berlaku pada [mulai, berakhir), seperti `kelas_store.berakhir_aktif`.

    Tanpa baris kelas_akses (`berakhir` None) TIDAK dianggap habis; keadaan itu tidak ditebak. Kedua nilai memakai
    format waktu baku yang sama, jadi pembandingan teks sah.
    """
    return berakhir is not None and berakhir <= kini


def _anggota_aktif(kon, kelompok_id: str, kini: str) -> List[dict]:
    """Anggota kelompok yang ordernya aktif, urut id order: `siswa_id` dan `akses_habis`. Anggota dengan akses
    lewat tetap ada; hanya ditandai."""
    baris = kon.execute(
        "SELECT p.order_id, o.siswa_id, MAX(a.berakhir) AS berakhir "
        "FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id "
        "LEFT JOIN kelas_akses a ON a.order_id=p.order_id "
        "WHERE p.kelompok_id=? GROUP BY p.order_id, o.siswa_id ORDER BY p.order_id", (kelompok_id,)).fetchall()
    aktif = _order_aktif_ids(kon, (b["order_id"] for b in baris), kini)
    return [{"siswa_id": b["siswa_id"], "akses_habis": _akses_habis(b["berakhir"], kini)}
            for b in baris if b["order_id"] in aktif]


def _pertemuan_berikut(kon, kelompok_id: str, kini: str) -> Optional[str]:
    return kon.execute(
        "SELECT MIN(mulai) FROM jadwal_pertemuan WHERE kelompok_id=? AND dibatalkan=0 AND mulai>=?",
        (kelompok_id, kini)).fetchone()[0]


def _pertemuan_dict(jenis: str, baris, **identitas) -> dict:
    return {"jenis": jenis, **identitas, "ke": int(baris["ke"]), "mulai": baris["mulai"],
            "menit": int(baris["menit"]), "dibatalkan": bool(baris["dibatalkan"])}


def _pertemuan_mini(kon, guru_id: str, kini: str) -> List[dict]:
    baris = kon.execute(
        "SELECT k.id AS kelompok_id, k.nama AS nama_kelompok, s.ke, s.mulai, s.menit, s.dibatalkan "
        "FROM jadwal_pertemuan s JOIN jadwal_kelompok k ON k.id=s.kelompok_id "
        "WHERE k.guru_id=? AND s.mulai>=?", (guru_id, kini)).fetchall()
    return [_pertemuan_dict("kelompok", b, kelompok_id=b["kelompok_id"], nama_kelompok=b["nama_kelompok"],
                            siswa_id=None) for b in baris]


def _pertemuan_privat(kon, guru_id: str, kini: str) -> List[dict]:
    baris = kon.execute(
        "SELECT s.order_id, o.siswa_id, s.ke, s.mulai, s.menit, s.dibatalkan "
        "FROM jadwal_pertemuan s JOIN jadwal_penempatan p ON p.order_id=s.order_id "
        "JOIN kelas_order o ON o.id=s.order_id "
        "WHERE p.guru_id=? AND p.kelompok_id IS NULL AND s.kelompok_id IS NULL AND s.mulai>=?",
        (guru_id, kini)).fetchall()
    aktif = _order_aktif_ids(kon, (b["order_id"] for b in baris), kini)
    return [_pertemuan_dict("privat", b, kelompok_id=None, nama_kelompok=None, siswa_id=b["siswa_id"])
            for b in baris if b["order_id"] in aktif]


def pertemuan_mendatang(kon, guru_id: str, kini) -> List[dict]:
    """Pertemuan Mini dan Private milik guru dengan `mulai >= kini`, urut waktu.

    Tiap item: `jenis` ("kelompok"|"privat"), `kelompok_id`, `nama_kelompok`, `siswa_id` (hanya privat),
    `ke`, `mulai` (UTC baku), `menit`, `dibatalkan`.
    """
    waktu = dasar.ke_baku(kini)
    hasil = _pertemuan_mini(kon, guru_id, waktu) + _pertemuan_privat(kon, guru_id, waktu)
    return sorted(hasil, key=lambda p: (p["mulai"], p["jenis"], p["ke"]))


def _ringkas_kelas(kon, baris, kini: str) -> dict:
    return {"id": baris["id"], "nama": baris["nama"], "kuota": int(baris["kuota"]),
            "terisi": len(_anggota_aktif(kon, baris["id"], kini)),
            "berikut": _pertemuan_berikut(kon, baris["id"], kini)}


def daftar_kelas(kon, guru_id: str, kini) -> List[dict]:
    """Kelompok Mini milik guru: `id`, `nama`, `kuota`, `terisi` (anggota aktif), `berikut` (mulai atau None)."""
    waktu = dasar.ke_baku(kini)
    baris = kon.execute("SELECT id, nama, kuota FROM jadwal_kelompok WHERE guru_id=? ORDER BY nama, id",
                        (guru_id,)).fetchall()
    return [_ringkas_kelas(kon, b, waktu) for b in baris]


def detail_kelas(kon, guru_id: str, kelompok_id, kini) -> Optional[dict]:
    """Detail satu kelompok milik guru, atau None. Id cacat, tak ada, dan milik guru lain sama-sama None.

    `anggota`: list `{"siswa_id", "akses_habis"}` urut id order (lihat `_anggota_aktif`).
    """
    if not _id_kelompok_sah(kelompok_id):
        return None
    waktu = dasar.ke_baku(kini)
    kelompok = kon.execute("SELECT id, nama, lokasi, kuota FROM jadwal_kelompok WHERE id=? AND guru_id=?",
                           (kelompok_id, guru_id)).fetchone()
    if kelompok is None:
        return None
    sesi = kon.execute("SELECT id, ke, mulai, menit, dibatalkan FROM jadwal_pertemuan "
                       "WHERE kelompok_id=? ORDER BY ke, id", (kelompok_id,)).fetchall()
    penempatan = kon.execute(_SQL_ANGGOTA_KELOMPOK, (kelompok_id,)).fetchall()
    return {
        "nama": kelompok["nama"],
        "lokasi": kelompok["lokasi"],
        "kuota": int(kelompok["kuota"]),
        "sesi": [_sesi_detail(kon, s, kelompok_id, penempatan, waktu) for s in sesi],
        "anggota": _anggota_aktif(kon, kelompok_id, waktu),
    }


def _sesi_detail(kon, sesi, kelompok_id: str, penempatan: List, waktu: str) -> dict:
    """Sesi kelompok: `id`, `kunci`, dan `anggota_n` (anggota aktif yang masuk pada sesi itu, R4)."""
    ke = int(sesi["ke"])
    return {"id": int(sesi["id"]), "kunci": aturan.kunci_pertemuan(kelompok_id, ke), "ke": ke,
            "mulai": sesi["mulai"], "menit": int(sesi["menit"]), "dibatalkan": bool(sesi["dibatalkan"]),
            "anggota_n": len(_anggota_pertemuan(kon, penempatan, sesi["mulai"], waktu))}


def nama_siswa(kon, ids) -> Dict[int, str]:
    """Nama anak dari latihan.db untuk id hasil kueri milik guru; id yang tidak ditemukan memakai placeholder."""
    unik = sorted(set(ids))
    if not unik:
        return {}
    tanda = ",".join("?" * len(unik))
    ditemukan = {int(siswa_id): nama for siswa_id, nama in
                 kon.execute("SELECT id, nama FROM siswa WHERE id IN (%s)" % tanda, unik).fetchall()}
    return {siswa_id: ditemukan.get(siswa_id, PLACEHOLDER_NAMA) for siswa_id in unik}


def _anggota_pertemuan(kon, baris: List, mulai: str, waktu: str) -> List[dict]:
    """Anggota pertemuan: order aktif pada `waktu` dan penempatannya sudah ada pada `mulai` (R4)."""
    aktif = _order_aktif_ids(kon, (b["order_id"] for b in baris), waktu)
    return [{"order_id": b["order_id"], "siswa_id": b["siswa_id"], "akses_habis": _akses_habis(b["berakhir"], waktu)}
            for b in baris if b["order_id"] in aktif and aturan.anggota_masuk_form(b["dibuat"], mulai)]


def _dict_pertemuan_milik(jenis: str, baris, id_awal: str, nama_kelompok: Optional[str], anggota: List[dict]) -> dict:
    return {"id": int(baris["id"]), "jenis": jenis, "id_awal": id_awal, "ke": int(baris["ke"]),
            "mulai": baris["mulai"], "menit": int(baris["menit"]), "dibatalkan": bool(baris["dibatalkan"]),
            "nama_kelompok": nama_kelompok, "anggota": anggota}


def _pertemuan_mini_milik(kon, guru_id: str, pertemuan_id: int, waktu: str) -> Optional[dict]:
    baris = kon.execute(
        "SELECT s.id, s.ke, s.mulai, s.menit, s.dibatalkan, k.id AS kelompok_id, k.nama AS nama_kelompok "
        "FROM jadwal_pertemuan s JOIN jadwal_kelompok k ON k.id=s.kelompok_id "
        "WHERE s.id=? AND k.guru_id=?", (pertemuan_id, guru_id)).fetchone()
    if baris is None:
        return None
    penempatan = kon.execute(_SQL_ANGGOTA_KELOMPOK, (baris["kelompok_id"],)).fetchall()
    anggota = _anggota_pertemuan(kon, penempatan, baris["mulai"], waktu)
    return _dict_pertemuan_milik("kelompok", baris, baris["kelompok_id"], baris["nama_kelompok"], anggota)


def _pertemuan_privat_milik(kon, guru_id: str, pertemuan_id: int, waktu: str) -> Optional[dict]:
    baris = kon.execute(
        "SELECT s.id, s.ke, s.mulai, s.menit, s.dibatalkan, s.order_id "
        "FROM jadwal_pertemuan s JOIN jadwal_penempatan p ON p.order_id=s.order_id "
        "WHERE s.id=? AND p.guru_id=? AND p.kelompok_id IS NULL", (pertemuan_id, guru_id)).fetchone()
    if baris is None:
        return None
    penempatan = kon.execute(_SQL_ANGGOTA_ORDER, (baris["order_id"],)).fetchall()
    anggota = _anggota_pertemuan(kon, penempatan, baris["mulai"], waktu)
    return _dict_pertemuan_milik("privat", baris, baris["order_id"], None, anggota)


def pertemuan_milik(kon, guru_id: str, pertemuan_id, kini) -> Optional[dict]:
    """Pertemuan Mini atau Private milik guru, atau None. Id cacat, tak ada, dan milik guru lain sama hasilnya.

    Kepemilikan di SQL: Mini lewat `jadwal_kelompok.guru_id`, Private lewat `jadwal_penempatan.guru_id`. Hanya SELECT.
    `anggota`: list `{"order_id", "siswa_id", "akses_habis"}` urut order_id. order_id dan siswa_id hanya untuk pemakaian
    internal pemanggil dan tidak boleh dirender.
    """
    if type(pertemuan_id) is not int or not PERTEMUAN_ID_MIN <= pertemuan_id <= PERTEMUAN_ID_MAKS:
        return None
    waktu = dasar.ke_baku(kini)
    milik = _pertemuan_mini_milik(kon, guru_id, pertemuan_id, waktu)
    if milik is not None:
        return milik
    return _pertemuan_privat_milik(kon, guru_id, pertemuan_id, waktu)


# --- pertemuan dalam jendela catat (Sudah berlangsung) ------------------------------------------

def _batas_bawah_baca(waktu: str) -> str:
    """Awal kueri: `waktu` dikurangi jendela koreksi dan durasi maksimum. Lebih longgar; saringan akhir di Python."""
    return (datetime.strptime(waktu, aturan.FORMAT_WAKTU) - JENDELA_BACA).strftime(aturan.FORMAT_WAKTU)


def _item_berlangsung(kon, jenis: str, baris, sql_anggota: str, waktu: str) -> Optional[dict]:
    """Item bila boleh dicatat (R1/R2) dan punya >= 1 anggota (R4); None bila tidak. Kunci tak sah dilewati."""
    mulai, menit = baris["mulai"], int(baris["menit"])
    if aturan.boleh_catat(mulai, menit, bool(baris["dibatalkan"]), waktu) is not None:
        return None
    try:
        kunci = aturan.kunci_pertemuan(baris["id_awal"], int(baris["ke"]))
    except ValueError:
        _log.warning("kunci pertemuan tidak sah pada data jadwal; dilewati")
        return None
    penempatan = kon.execute(sql_anggota, (baris["id_awal"],)).fetchall()
    if not _anggota_pertemuan(kon, penempatan, mulai, waktu):
        return None
    return {"id": int(baris["id"]), "jenis": jenis, "nama_kelompok": baris["nama_kelompok"],
            "siswa_id": baris["siswa_id"], "kunci": kunci, "ke": int(baris["ke"]), "mulai": mulai, "menit": menit}


def _berlangsung_dari_kueri(kon, jenis: str, sql_kueri: str, sql_anggota: str, guru_id: str, batas: str,
                            waktu: str) -> List[dict]:
    baris = kon.execute(sql_kueri, (guru_id, waktu, batas)).fetchall()
    hasil = [_item_berlangsung(kon, jenis, b, sql_anggota, waktu) for b in baris]
    return [item for item in hasil if item is not None]


def pertemuan_dalam_jendela(kon, guru_id: str, kini) -> List[dict]:
    """Pertemuan Mini dan Private milik guru yang sudah mulai, masih dalam jendela catat, dan punya >= 1 anggota (R4).

    Tiap item: `id` (jadwal_pertemuan.id), `jenis` ("kelompok"|"privat"), `nama_kelompok` (None untuk privat),
    `siswa_id` (hanya privat; internal, tidak boleh dirender), `kunci` (aturan.kunci_pertemuan), `ke`, `mulai`, `menit`.
    Urut `mulai` menurun, lalu `id` menaik. Kepemilikan di SQL; hanya SELECT.
    """
    waktu = dasar.ke_baku(kini)
    batas = _batas_bawah_baca(waktu)
    mini = _berlangsung_dari_kueri(kon, "kelompok", _SQL_BERLANGSUNG_MINI, _SQL_ANGGOTA_KELOMPOK,
                                   guru_id, batas, waktu)
    privat = _berlangsung_dari_kueri(kon, "privat", _SQL_BERLANGSUNG_PRIVAT, _SQL_ANGGOTA_ORDER,
                                     guru_id, batas, waktu)
    urut_id = sorted(mini + privat, key=lambda p: p["id"])
    return sorted(urut_id, key=lambda p: p["mulai"], reverse=True)
