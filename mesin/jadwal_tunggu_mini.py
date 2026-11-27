"""Daftar tunggu Mini Class (F2c, keputusan Pemilik K2): orang tua masuk daftar kelompok yang sudah penuh.

Tabel `tunggu_mini` di DB Private (aditif, `dsr.DDL_TAMBAHAN`); penempatan tetap di admin-control dan dibaca saat tampil.
Satu entri 'menunggu' per order: masuk daftar lain menggantikan yang lama, masuk daftar yang sama tidak mengubah posisi.
Entri TIDAK memegang kursi dan TIDAK menempatkan anak: admin tetap yang menempatkan (`jadwal_store.tempatkan`) dan bisa
menghapus entri (`hapus_admin`).

Kepemilikan dan kelayakan dicek SEBELUM DB private dibuka untuk tulis (404 identik tanpa efek samping): order dari
`jadwal_pilih.order_mini_belum_ditempatkan` (anak milik akun sesi, order Mini aktif, belum ditempatkan) dan kelompok harus
ada di `jadwal_pilih.pilihan_untuk` (terbuka, muat dalam masa akses). Kelompok yang masih ada kursi = 409.
Urutan = posisi menurut `dibuat` (lalu id) di antara 'menunggu' kelompok itu yang ordernya BELUM ditempatkan. Satu-satunya
aturan urutan ada di `antrean`; halaman murid, halaman admin, dan hitungan antrean memakai fungsi yang sama.

Risiko yang sudah diketahui, sengaja TIDAK diselesaikan di sini (tindak lanjut, keputusan Pemilik):
- Masa akses paket mulai saat bukti disetujui (`kelas_putusan.py`, baris 71-93). Anak yang menunggu lama bisa kehilangan
  kelayakan sebelum kursi kosong; entri ini tidak memperpanjang masa akses. Admin yang memutuskan perpanjangan.
- Tanpa notifikasi otomatis saat kursi terbuka (email E2 belum ada). Orang tua melihat kursi di halaman paket.
- Kelayakan di admin-control dan penulisan di DB private tidak satu transaksi (sama dengan pola Private). Akibat terburuk:
  satu entri untuk order yang baru ditempatkan; entri itu tidak dihitung antrean dan tidak tampil untuk orang tua.
- Entri untuk kelompok yang sudah tidak terbuka (ditutup atau lewat masa akses) tidak tampil untuk orang tua; entri tetap
  'menunggu' sampai masuk daftar lain atau dihapus admin.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet, Iterable, Optional, Sequence, Tuple

import jadwal_dasar as jd
import jadwal_pilih as jp
import jadwal_private_baca as jpb
import jadwal_private_dasar as dsr
import kelas_dasar as kd
import kelas_store
import pesanan_dasar as d

TABEL = "tunggu_mini"
STATUS_MENUNGGU = dsr.TUNGGU_STATUS_MENUNGGU
STATUS_DIBATALKAN = dsr.TUNGGU_STATUS_DIBATALKAN
STATUS_DIHAPUS_ADMIN = dsr.TUNGGU_STATUS_DIHAPUS_ADMIN
PESAN_MASIH_ADA_KURSI = "kelompok itu masih ada kursi; pilih kelompok itu langsung"
PESAN_TIDAK_MENUNGGU = "entri daftar tunggu sudah tidak menunggu"
_KOLOM_ENTRI = "id,order_id,kelompok_id,dibuat"


@dataclass(frozen=True)
class TungguSaya:
    """Entri anak di kelompok yang penuh: id kelompok dan posisi antrean (mulai 1)."""

    kelompok_id: str
    urutan: int


@dataclass(frozen=True)
class StatusTunggu:
    """Keadaan daftar tunggu anak untuk kartu pilih kelompok. `saya` None = tidak sedang menunggu di mana pun."""

    saya: Optional[TungguSaya]


@dataclass(frozen=True)
class EntriAdmin:
    """Satu entri untuk halaman admin. `urutan` None = order sudah ditempatkan (tidak antre lagi)."""

    id: int
    order_id: str
    dibuat: str
    urutan: Optional[int]
    sudah_ditempatkan: bool


def antrean(order_menunggu: Sequence[str], ditempatkan: AbstractSet[str]) -> Tuple[str, ...]:
    """Order yang masih antre, menurut urutan masuk (`order_menunggu` sudah terurut dibuat, id). Fungsi murni."""
    return tuple(order for order in order_menunggu if order not in ditempatkan)


def _posisi(antre: Sequence[str], order_id: str) -> Optional[int]:
    """Posisi mulai 1 bila order masih antre, None bila sudah ditempatkan (tidak ada di antrean)."""
    return antre.index(order_id) + 1 if order_id in antre else None


def _ada(kon) -> bool:
    return dsr.ada_tabel(kon, TABEL)


def _ditempatkan(kon_admin, order_ids: Iterable[str]) -> frozenset:
    """Order yang sudah punya penempatan di admin-control (baca saja)."""
    return frozenset(oid for oid in order_ids if kon_admin.execute(
        "SELECT 1 FROM jadwal_penempatan WHERE order_id=?", (oid,)).fetchone() is not None)


def _menunggu_kelompok(kon, kelompok_id: str) -> list:
    return list(kon.execute("SELECT %s FROM %s WHERE kelompok_id=? AND status=? ORDER BY dibuat,id"
                            % (_KOLOM_ENTRI, TABEL), (kelompok_id, STATUS_MENUNGGU)))


def _antrean_kelompok(kon_p, kon_admin, kelompok_id: str) -> Tuple[list, Tuple[str, ...]]:
    baris = _menunggu_kelompok(kon_p, kelompok_id)
    orders = [b["order_id"] for b in baris]
    return baris, antrean(orders, _ditempatkan(kon_admin, orders))


def _saya(kon_p, kon_admin, order_id: str) -> Optional[TungguSaya]:
    if not _ada(kon_p):
        return None
    baris = kon_p.execute("SELECT kelompok_id FROM %s WHERE order_id=? AND status=?" % TABEL,
                          (order_id, STATUS_MENUNGGU)).fetchone()
    if baris is None:
        return None
    _baris, antre = _antrean_kelompok(kon_p, kon_admin, baris["kelompok_id"])
    urutan = _posisi(antre, order_id)
    return None if urutan is None else TungguSaya(baris["kelompok_id"], urutan)


def status_tunggu(kon_admin, akun_id, siswa_id, sekarang, path=None) -> StatusTunggu:
    """Entri anak untuk order Mini yang belum ditempatkan (baca saja). Anak tanpa order seperti itu = `saya` None."""
    kini = kd.ke_baku(sekarang)
    oid = jp.order_mini_belum_ditempatkan(kon_admin, akun_id, siswa_id, kini)
    if oid is None:
        return StatusTunggu(None)
    return dsr.dengan_baca(path, lambda kon_p: StatusTunggu(_saya(kon_p, kon_admin, oid)), StatusTunggu(None))


def _penuh_terbuka(kon_admin, akun_id, siswa_id, kelompok_id: str, kini: str) -> bool:
    """True bila kelompok terbuka untuk anak ini dan penuh. Tidak ada di daftar pilihan = PesananTidakDitemukan (404)."""
    for pilihan in jp.pilihan_untuk(kon_admin, akun_id, siswa_id, kini):
        if pilihan.kelompok_id == kelompok_id:
            return pilihan.penuh
    raise jd.JadwalTidakDitemukan()


def _catat_masuk(kon, order_id: str, kelompok_id: str, kini: str) -> None:
    """Satu entri 'menunggu' per order. Kelompok yang sama = tidak berubah (posisi tetap); kelompok lain = menggantikan."""
    aktif = kon.execute("SELECT id,kelompok_id FROM %s WHERE order_id=? AND status=?" % TABEL,
                        (order_id, STATUS_MENUNGGU)).fetchone()
    if aktif is not None and aktif["kelompok_id"] == kelompok_id:
        return
    if aktif is not None:
        _ubah_status(kon, aktif["id"], STATUS_DIBATALKAN, dsr.PELAKU_SISTEM, kini)
    kon.execute("INSERT INTO %s(order_id,kelompok_id,status,dibuat,diubah,diputuskan_oleh) VALUES(?,?,?,?,?,NULL)"
                % TABEL, (order_id, kelompok_id, STATUS_MENUNGGU, kini, kini))


def masuk(kon_admin, akun_id, siswa_id, kelompok_id, sekarang, path=None) -> None:
    """Orang tua masuk daftar tunggu kelompok yang penuh untuk anak ini. Semua syarat dicek sebelum DB private ditulis."""
    akun = d.periksa_akun_id(akun_id)
    siswa = kd.periksa_siswa_id(siswa_id)
    kid = jd.periksa_kelompok_id(kelompok_id)
    kini = kd.ke_baku(sekarang)
    oid = jp.order_mini_belum_ditempatkan(kon_admin, akun, siswa, kini)
    if oid is None:
        raise jd.JadwalTidakDitemukan()
    if not _penuh_terbuka(kon_admin, akun, siswa, kid, kini):
        raise jd.JadwalKonflik(PESAN_MASIH_ADA_KURSI)
    with dsr.dengan_tulis(path, buat=True) as kon_p:
        _catat_masuk(kon_p, oid, kid, kini)


def _menunggu_milik(kon, milik: AbstractSet[str]):
    for baris in kon.execute("SELECT id,order_id FROM %s WHERE status=?" % TABEL, (STATUS_MENUNGGU,)):
        if baris["order_id"] in milik:
            return baris
    return None


def _ubah_status(kon, entri_id: int, status_baru: str, oleh: str, kini: str) -> None:
    """Transisi tunggal dari 'menunggu' (trigger skema juga menolak transisi lain)."""
    cur = kon.execute("UPDATE %s SET status=?,diubah=?,diputuskan_oleh=? WHERE id=? AND status=?" % TABEL,
                      (status_baru, kini, oleh, entri_id, STATUS_MENUNGGU))
    if cur.rowcount != 1:
        raise jd.JadwalKonflik(PESAN_TIDAK_MENUNGGU)


def keluar(kon_admin, akun_id, siswa_id, sekarang, path=None) -> None:
    """Orang tua keluar dari daftar tunggu anak itu. Anak milik akun lain, atau tanpa entri = 404 identik, tanpa efek."""
    akun = d.periksa_akun_id(akun_id)
    siswa = kd.periksa_siswa_id(siswa_id)
    kini = kd.ke_baku(sekarang)
    kelas_store._wajib_anak_milik(kon_admin, akun, siswa)
    milik = jpb.order_milik_anak(kon_admin, akun, siswa)
    with dsr.dengan_tulis(path) as kon_p:
        baris = _menunggu_milik(kon_p, milik)
        if baris is None:
            raise jd.JadwalTidakDitemukan()
        _ubah_status(kon_p, baris["id"], STATUS_DIBATALKAN, dsr.PELAKU_ORANG_TUA, kini)


def daftar_admin(kon_admin, kelompok_id, path=None) -> Tuple[EntriAdmin, ...]:
    """Semua entri kelompok ini (terlama dulu) untuk halaman admin, dengan urutan atau tanda sudah ditempatkan."""
    kid = jd.periksa_kelompok_id(kelompok_id)
    return dsr.dengan_baca(path, lambda kon_p: _entri_admin(kon_p, kon_admin, kid), ())


def _entri_admin(kon_p, kon_admin, kelompok_id: str) -> Tuple[EntriAdmin, ...]:
    if not _ada(kon_p):
        return ()
    baris, antre = _antrean_kelompok(kon_p, kon_admin, kelompok_id)
    return tuple(EntriAdmin(b["id"], b["order_id"], b["dibuat"], _posisi(antre, b["order_id"]),
                            b["order_id"] not in antre) for b in baris)


def hapus_admin(admin_id, tunggu_id, sekarang, path=None) -> None:
    """Admin menghapus satu entri 'menunggu' dari daftar. Penempatan tidak tersentuh (tetap lewat alur admin)."""
    aktor = d.periksa_pelaku(admin_id)
    tid = dsr.periksa_id(tunggu_id, "daftar tunggu")
    kini = kd.ke_baku(sekarang)
    with dsr.dengan_tulis(path) as kon_p:
        baris = kon_p.execute("SELECT status FROM %s WHERE id=?" % TABEL, (tid,)).fetchone()
        if baris is None:
            raise jd.JadwalTidakDitemukan()
        if baris["status"] != STATUS_MENUNGGU:
            raise jd.JadwalKonflik(PESAN_TIDAK_MENUNGGU)
        _ubah_status(kon_p, tid, STATUS_DIHAPUS_ADMIN, aktor, kini)


def _jumlah_antre(kon_p, kon_admin) -> int:
    if not _ada(kon_p):
        return 0
    orders = [b["order_id"] for b in kon_p.execute(
        "SELECT order_id FROM %s WHERE status=? ORDER BY dibuat,id" % TABEL, (STATUS_MENUNGGU,))]
    return len(antrean(orders, _ditempatkan(kon_admin, orders)))


def jumlah_menunggu_kursi(kon_admin, path=None) -> int:
    """Jumlah anak yang menunggu kursi Mini (entri 'menunggu' dengan order belum ditempatkan). Galat baca ditangani pemanggil."""
    return dsr.dengan_baca(path, lambda kon_p: _jumlah_antre(kon_p, kon_admin), 0)
