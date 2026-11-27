"""Pola Private orang tua (2 hari + 1 jam): ajukan, batalkan, tolak, dan baca. Persetujuan ada di `jadwal_private_pola_setujui`.

Tabel `private_pola_pengajuan` di DB private (aditif, lihat `dsr.DDL_TAMBAHAN`). Kepemilikan: order dicari lewat
`bc.order_boleh_mengajukan` (anak milik akun sesi). Tidak ada / milik akun lain = PesananTidakDitemukan sebelum DB private
dibuka, jadi tanpa efek samping. Pengajuan baru membatalkan pola 'diajukan' order itu dan pengajuan slot lama 'diajukan'
(satu penahan aktif per order lintas dua mekanisme).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

import jadwal_dasar as jd
import jadwal_private_baca as bc
import jadwal_private_dasar as dsr
import jadwal_private_pola_aturan as aturan
import kelas_dasar as kd
import kelas_store
import pesanan_dasar as d
from jadwal_private_pola_aturan import Pola

TABEL = "private_pola_pengajuan"
STATUS_DIAJUKAN = dsr.STATUS_DIAJUKAN
STATUS_DISETUJUI = dsr.STATUS_DISETUJUI
STATUS_DITOLAK = dsr.STATUS_DITOLAK
STATUS_DIBATALKAN = dsr.STATUS_DIBATALKAN
PESAN_MASA_AKSES = "masa akses paket sudah berakhir"
PESAN_TIDAK_ADA_PILIHAN = "tidak ada pilihan yang bisa dibatalkan"
PESAN_SUDAH_DIPUTUSKAN = "pola sudah diputuskan"
_KOLOM = "id,order_id,hari_a,hari_b,jam,status,dibuat"


@dataclass(frozen=True)
class EntriPola:
    """Pola yang masih diajukan beserta tanggal mulai usulan (terdekat, >= 24 jam) untuk layar admin."""

    pola: Pola
    tanggal_usulan: str


def _dari_baris(baris) -> Pola:
    return Pola(int(baris["id"]), baris["order_id"], int(baris["hari_a"]), int(baris["hari_b"]), baris["jam"],
                baris["status"], baris["dibuat"])


def _order_untuk_ajukan(kon_admin, akun: str, siswa: int, kini: str) -> str:
    """Order Private aktif yang boleh mengajukan. Bukan milik akun / tidak ada = PesananTidakDitemukan (404)."""
    oid = bc.order_boleh_mengajukan(kon_admin, akun, siswa, kini)
    if oid is None:
        raise jd.JadwalTidakDitemukan()
    return oid


def _pastikan_masa_akses(kon_admin, order_id: str, kini: str) -> None:
    batas = bc.fakta_order(kon_admin, order_id, kini).batas
    if batas is None or kini >= batas:
        raise jd.JadwalKonflik(PESAN_MASA_AKSES)


def _dari_isian(isian: Mapping[str, str]) -> Tuple[int, int, str]:
    hari, jam = aturan.hari_dan_jam_dari_form(isian)
    return aturan.periksa_pola(hari, jam)


def ajukan(kon_admin, akun_id, siswa_id, isian: Mapping[str, str], sekarang, path=None) -> int:
    """Orang tua memilih dua hari dan satu jam untuk anak. Kepemilikan dicek dulu, isian sesudahnya, lalu DB private."""
    akun = d.periksa_akun_id(akun_id)
    siswa = kd.periksa_siswa_id(siswa_id)
    kini = kd.ke_baku(sekarang)
    oid = _order_untuk_ajukan(kon_admin, akun, siswa, kini)
    _pastikan_masa_akses(kon_admin, oid, kini)
    hari_a, hari_b, jam = _dari_isian(isian)
    with dsr.dengan_tulis(path, buat=True) as kon_p:
        _batalkan_diajukan_order(kon_p, oid, kini)
        cur = kon_p.execute(
            "INSERT INTO private_pola_pengajuan(order_id,hari_a,hari_b,jam,status,dibuat,diubah) VALUES(?,?,?,?,?,?,?)",
            (oid, hari_a, hari_b, jam, STATUS_DIAJUKAN, kini, kini))
        return cur.lastrowid


def _batalkan_diajukan_order(kon, order_id: str, kini: str) -> None:
    """Pola 'diajukan' dan pengajuan slot 'diajukan' milik order ini dibatalkan (pengganti). Keduanya lewat trigger transisi."""
    kon.execute("UPDATE %s SET status=?,diubah=?,diputuskan_oleh=? WHERE order_id=? AND status=?" % TABEL,
                (STATUS_DIBATALKAN, kini, dsr.PELAKU_SISTEM, order_id, STATUS_DIAJUKAN))
    kon.execute("UPDATE private_pengajuan SET status=?,diputuskan=?,diputuskan_oleh=? WHERE order_id=? AND status=?",
                (STATUS_DIBATALKAN, kini, dsr.PELAKU_SISTEM, order_id, STATUS_DIAJUKAN))


def batalkan(kon_admin, akun_id, siswa_id, sekarang, path=None) -> None:
    """Orang tua membatalkan pola 'diajukan' milik anak itu. Pola anak lain tidak tersentuh."""
    akun = d.periksa_akun_id(akun_id)
    siswa = kd.periksa_siswa_id(siswa_id)
    kini = kd.ke_baku(sekarang)
    kelas_store._wajib_anak_milik(kon_admin, akun, siswa)
    milik = bc.order_milik_anak(kon_admin, akun, siswa)
    if not dsr.path_db(path).exists():
        raise jd.JadwalKonflik(PESAN_TIDAK_ADA_PILIHAN)
    with dsr.dengan_tulis(path) as kon_p:
        pid = _diajukan_milik(kon_p, milik)
        if pid is None:
            raise jd.JadwalKonflik(PESAN_TIDAK_ADA_PILIHAN)
        _ubah_status(kon_p, pid, STATUS_DIBATALKAN, dsr.PELAKU_ORANG_TUA, kini)


def _diajukan_milik(kon, milik) -> Optional[int]:
    for baris in kon.execute("SELECT id,order_id FROM %s WHERE status=?" % TABEL, (STATUS_DIAJUKAN,)).fetchall():
        if baris["order_id"] in milik:
            return baris["id"]
    return None


def _ubah_status(kon, pola_id: int, status_baru: str, oleh: str, kini: str) -> None:
    """Transisi tunggal: hanya dari 'diajukan' (trigger skema juga menolak transisi lain)."""
    cur = kon.execute(
        "UPDATE %s SET status=?,diubah=?,diputuskan_oleh=? WHERE id=? AND status=?" % TABEL,
        (status_baru, kini, oleh, pola_id, STATUS_DIAJUKAN))
    if cur.rowcount != 1:
        raise jd.JadwalKonflik(PESAN_SUDAH_DIPUTUSKAN)


def baca_pola(kon, pola_id: int) -> Pola:
    baris = kon.execute("SELECT %s FROM %s WHERE id=?" % (_KOLOM, TABEL), (pola_id,)).fetchone()
    if baris is None:
        raise jd.JadwalTidakDitemukan()
    return _dari_baris(baris)


def tolak(admin_id, pola_id, sekarang, path=None) -> None:
    aktor = d.periksa_pelaku(admin_id)
    pid = dsr.periksa_id(pola_id, "pola")
    kini = kd.ke_baku(sekarang)
    with dsr.dengan_tulis(path) as kon_p:
        baca_pola(kon_p, pid)
        _ubah_status(kon_p, pid, STATUS_DITOLAK, aktor, kini)


def tandai_disetujui(kon, pola_id: int, aktor: str, kini: str) -> None:
    """Dipakai `jadwal_private_pola_setujui` setelah 8 pertemuan ditempatkan (di transaksi DB private yang sama)."""
    _ubah_status(kon, pola_id, STATUS_DISETUJUI, aktor, kini)


def terbaru_order(order_id: str, path=None) -> Optional[Pola]:
    """Pola 'diajukan' order bila ada; kalau tidak, pola terbaru order. None bila belum pernah atau berkas belum ada."""
    return dsr.dengan_baca(path, lambda kon: _terbaru(kon, order_id), None)


def _terbaru(kon, order_id: str) -> Optional[Pola]:
    if not dsr.ada_tabel(kon, TABEL):
        return None
    baris = kon.execute(
        "SELECT %s FROM %s WHERE order_id=? ORDER BY (status=?) DESC, id DESC LIMIT 1" % (_KOLOM, TABEL),
        (order_id, STATUS_DIAJUKAN)).fetchone()
    return None if baris is None else _dari_baris(baris)


def antrean_admin(kini: str, path=None) -> Tuple[EntriPola, ...]:
    """Pola 'diajukan' terlama dulu, dengan tanggal usulan. Berkas belum ada / tabel belum ada = kosong."""
    baris = dsr.dengan_baca(path, _daftar_diajukan, ())
    return tuple(EntriPola(p, aturan.tanggal_mulai_default(kini, p.hari_a, p.hari_b, p.jam)) for p in baris)


def _daftar_diajukan(kon) -> Tuple[Pola, ...]:
    if not dsr.ada_tabel(kon, TABEL):
        return ()
    return tuple(_dari_baris(b) for b in kon.execute(
        "SELECT %s FROM %s WHERE status=? ORDER BY dibuat,id" % (_KOLOM, TABEL), (STATUS_DIAJUKAN,)))


def jumlah_menunggu(path=None) -> int:
    """Jumlah pola 'diajukan' untuk penanda antrean admin. Galat baca ditangani pemanggil."""
    return dsr.dengan_baca(path, lambda kon: len(_daftar_diajukan(kon)), 0)
