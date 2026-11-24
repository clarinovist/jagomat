"""Kelompok, penempatan, dan jadwal Paket Belajar (tanpa HTTP, jaringan, env, atau berkas).

Mini Class dijadwalkan sebagai kelompok (satu lokasi/guru, 8 pertemuan mingguan, kuota 5); Private per anak
(guru per anak, lokasi "Online"). Semua tulis dalam satu `BEGIN IMMEDIATE` (`pesanan_dasar.tulis`) di
admin-control.db. Nominal tidak disentuh di sini; jadwal hanya membaca order/akses kelas.

Kuota dan kecocokan paket dijaga dua lapis: store (pesan jelas) dan trigger skema (fail-closed). Penempatan
hanya untuk order yang statusnya `aktif`; satu penempatan per order dan per anak (lepas dulu sebelum pindah).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import List, Optional

import jadwal_dasar as jd
import kelas_dasar as dasar
import kelas_status as ks
import kelas_store
import paket_belajar_katalog as katalog
import pesanan_dasar as d
import schema_jadwal
import schema_kelas


@contextmanager
def buka(path, *, tulis_data=False):
    """Koneksi admin dengan kelas DAN jadwal yang sah (salah satunya belum dipasang -> StoreBelumSiap)."""
    import admin_store_core
    with kelas_store.buka(path, tulis_data=tulis_data) as kon:
        if not schema_jadwal.validasi(kon):
            raise admin_store_core.StoreBelumSiap("jadwal belum dipasang")
        yield kon


def _group(kon, kelompok_id):
    baris = kon.execute(
        "SELECT id,paket,nama,lokasi,guru_id,kuota,dibuat,diubah FROM jadwal_kelompok WHERE id=?",
        (kelompok_id,)).fetchone()
    return None if baris is None else dict(baris)


def _isi_kelompok(kon, kelompok_id) -> int:
    return kon.execute("SELECT COUNT(*) FROM jadwal_penempatan WHERE kelompok_id=?",
                       (kelompok_id,)).fetchone()[0]


def _tulis_sesi(kon, *, kelompok_id=None, order_id=None, mulai, menit, aktor, kini):
    for ke, waktu in enumerate(jd.delapan_pertemuan(mulai), start=1):
        kon.execute(
            "INSERT INTO jadwal_pertemuan(kelompok_id,order_id,ke,mulai,menit,dibatalkan,diubah,diubah_oleh) "
            "VALUES(?,?,?,?,?,0,?,?)",
            (kelompok_id, order_id, ke, waktu, menit, kini, aktor))


# --- kelompok -------------------------------------------------------------------------------

def buat_kelompok(kon, admin_id, *, nama, lokasi, guru_id, kuota, tanggal, jam, sekarang) -> str:
    """Buat kelompok Mini + delapan pertemuan mingguan; mengembalikan id kelompok (atomik)."""
    d.periksa_koneksi(kon)
    aktor = d.periksa_pelaku(admin_id)
    nama = jd.periksa_teks(nama, "nama kelompok", 80)
    lokasi = jd.periksa_teks(lokasi, "lokasi", 200)
    guru = jd.periksa_guru_id(guru_id)
    kuota = jd.periksa_kuota(kuota)
    mulai = jd.pertemuan_pertama(tanggal, jam, sekarang)
    kid, kini = jd.id_kelompok_baru(), dasar.ke_baku(sekarang)
    menit = katalog.ambil(schema_jadwal.KODE_PAKET_MINI).menit
    with d.tulis(kon):
        kon.execute(
            "INSERT INTO jadwal_kelompok(id,paket,nama,lokasi,guru_id,kuota,dibuat,diubah,"
            "dibuat_oleh,diubah_oleh) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (kid, schema_jadwal.KODE_PAKET_MINI, nama, lokasi, guru, kuota, kini, kini, aktor, aktor))
        _tulis_sesi(kon, kelompok_id=kid, mulai=mulai, menit=menit, aktor=aktor, kini=kini)
    return kid


def ubah_kelompok(kon, admin_id, kelompok_id, *, nama, lokasi, guru_id, kuota, sekarang) -> None:
    """Ubah nama/lokasi/guru/kuota kelompok; kuota tidak boleh di bawah jumlah anggota."""
    d.periksa_koneksi(kon)
    aktor = d.periksa_pelaku(admin_id)
    kid = jd.periksa_kelompok_id(kelompok_id)
    nama = jd.periksa_teks(nama, "nama kelompok", 80)
    lokasi = jd.periksa_teks(lokasi, "lokasi", 200)
    guru = jd.periksa_guru_id(guru_id)
    kuota = jd.periksa_kuota(kuota)
    kini = dasar.ke_baku(sekarang)
    with d.tulis(kon):
        if _group(kon, kid) is None:
            raise jd.JadwalTidakDitemukan()
        try:
            kon.execute(
                "UPDATE jadwal_kelompok SET nama=?,lokasi=?,guru_id=?,kuota=?,diubah=?,diubah_oleh=? "
                "WHERE id=?", (nama, lokasi, guru, kuota, kini, aktor, kid))
        except sqlite3.IntegrityError:
            raise jd.JadwalKonflik("kuota lebih kecil dari jumlah anggota") from None


def daftar_kelompok(kon) -> List[dict]:
    """Semua kelompok + terisi/kuota + pertemuan berikutnya (tanpa nama anak)."""
    d.periksa_koneksi(kon)
    baris = kon.execute(
        """SELECT k.id,k.nama,k.lokasi,k.guru_id,k.kuota,
                  (SELECT COUNT(*) FROM jadwal_penempatan p WHERE p.kelompok_id=k.id) AS terisi,
                  (SELECT MIN(s.mulai) FROM jadwal_pertemuan s
                    WHERE s.kelompok_id=k.id AND s.dibatalkan=0) AS berikut
             FROM jadwal_kelompok k ORDER BY k.nama,k.id""")
    return [dict(b) for b in baris]


def detail_kelompok(kon, kelompok_id) -> dict:
    """Kelompok + anggota (order/anak/akhir akses) + delapan pertemuan."""
    d.periksa_koneksi(kon)
    kid = jd.periksa_kelompok_id(kelompok_id)
    kelompok = _group(kon, kid)
    if kelompok is None:
        raise jd.JadwalTidakDitemukan()
    anggota = [dict(b) for b in kon.execute(
        """SELECT p.order_id,o.siswa_id,o.paket,MAX(a.berakhir) AS berakhir
             FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id
             LEFT JOIN kelas_akses a ON a.order_id=p.order_id
            WHERE p.kelompok_id=? GROUP BY p.order_id,o.siswa_id,o.paket
            ORDER BY p.order_id""", (kid,))]
    sesi = [dict(b) for b in kon.execute(
        """SELECT id,ke,mulai,menit,dibatalkan FROM jadwal_pertemuan
            WHERE kelompok_id=? ORDER BY ke,id""", (kid,))]
    return {"kelompok": kelompok, "anggota": anggota, "sesi": sesi, "terisi": _isi_kelompok(kon, kid)}


# --- penempatan -----------------------------------------------------------------------------

def _order_aktif(kon, order_id, kini):
    order = ks.baris_order(kon, order_id)
    if order is None:
        raise jd.JadwalTidakDitemukan()
    if ks.status_dari(order, ks.fakta_order(kon, order_id), kini) != dasar.STATUS_AKTIF:
        raise jd.JadwalKonflik("paket belum aktif; setujui bukti dulu")
    return order


def tempatkan(kon, admin_id, order_id, *, kelompok_id=None, guru_id=None, tanggal=None, jam=None,
              sekarang) -> dict:
    """Tempatkan order aktif: Mini ke kelompok (kuota dijaga), Private per anak + 8 pertemuan.

    Mengembalikan `{"jenis": "kelompok"|"privat", "kelompok_id", "guru_id", "sesi"}`.
    """
    d.periksa_koneksi(kon)
    aktor = d.periksa_pelaku(admin_id)
    order_id = dasar.periksa_order_id(order_id)
    kini = dasar.ke_baku(sekarang)
    with d.tulis(kon):
        order = _order_aktif(kon, order_id, kini)
        if order["paket"] == schema_jadwal.KODE_PAKET_MINI:
            if kelompok_id is None or guru_id is not None or tanggal is not None or jam is not None:
                raise jd.JadwalTidakSah("penempatan Mini harus memilih kelompok")
            kid = jd.periksa_kelompok_id(kelompok_id)
            kelompok = _group(kon, kid)
            if kelompok is None:
                raise jd.JadwalTidakDitemukan()
            if _isi_kelompok(kon, kid) >= kelompok["kuota"]:
                raise jd.JadwalPenuh()
            try:
                kon.execute(
                    "INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                    "dibuat_oleh,diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)",
                    (order_id, kid, kini, kini, aktor, aktor))
            except sqlite3.IntegrityError as galat:
                raise _peta_integritas(galat) from None
            return {"jenis": "kelompok", "kelompok_id": kid, "guru_id": None, "sesi": []}
        if order["paket"] != schema_jadwal.KODE_PAKET_PRIVATE:
            raise jd.JadwalTidakSah("paket tidak didukung jadwal")
        if kelompok_id is not None or guru_id is None or tanggal is None or jam is None:
            raise jd.JadwalTidakSah("penempatan Private butuh guru, tanggal, dan jam")
        guru = jd.periksa_guru_id(guru_id)
        mulai = jd.pertemuan_pertama(tanggal, jam, sekarang)
        try:
            kon.execute(
                "INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                "dibuat_oleh,diubah_oleh) VALUES(?,NULL,?,?,?,?,?,?)",
                (order_id, guru, schema_jadwal.LOKASI_PRIVATE, kini, kini, aktor, aktor))
        except sqlite3.IntegrityError as galat:
            raise _peta_integritas(galat) from None
        _tulis_sesi(kon, order_id=order_id, mulai=mulai,
                    menit=katalog.ambil(schema_jadwal.KODE_PAKET_PRIVATE).menit, aktor=aktor, kini=kini)
        return {"jenis": "privat", "kelompok_id": None, "guru_id": guru, "sesi": []}


def _peta_integritas(galat):
    pesan = str(galat).lower()
    if "kelompok penuh" in pesan:
        return jd.JadwalPenuh()
    if "sudah punya penempatan" in pesan:
        return jd.JadwalKonflik("anak sudah punya penempatan; lepas dulu sebelum pindah")
    if "paket dan jenis" in pesan:
        return jd.JadwalTidakSah("paket dan jenis penempatan tidak cocok")
    if "unique" in pesan or "primary key" in pesan:
        return jd.JadwalKonflik("order sudah punya penempatan; lepas dulu untuk mengubah")
    return jd.JadwalTidakSah("penempatan bentrok dengan catatan yang ada")


def lepas_penempatan(kon, admin_id, order_id, *, sekarang) -> None:
    """Lepas penempatan; sesi Private ikut dihapus, sesi kelompok tetap milik kelompok."""
    d.periksa_koneksi(kon)
    d.periksa_pelaku(admin_id)
    order_id = dasar.periksa_order_id(order_id)
    with d.tulis(kon):
        ada = kon.execute("SELECT kelompok_id FROM jadwal_penempatan WHERE order_id=?",
                          (order_id,)).fetchone()
        if ada is None:
            raise jd.JadwalTidakDitemukan()
        if ada["kelompok_id"] is None:
            kon.execute("DELETE FROM jadwal_pertemuan WHERE order_id=?", (order_id,))
        kon.execute("DELETE FROM jadwal_penempatan WHERE order_id=?", (order_id,))


def ringkas_order(kon, order_id) -> Optional[dict]:
    """Penempatan satu order + kelompok + sesi (Private) untuk halaman detail admin."""
    d.periksa_koneksi(kon)
    order_id = dasar.periksa_order_id(order_id)
    baris = kon.execute(
        """SELECT p.order_id,p.kelompok_id,p.guru_id,p.lokasi,p.dibuat,
                  k.nama AS kelompok_nama,k.lokasi AS kelompok_lokasi,k.guru_id AS kelompok_guru,
                  o.siswa_id,o.paket
             FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id
             LEFT JOIN jadwal_kelompok k ON k.id=p.kelompok_id
            WHERE p.order_id=?""", (order_id,)).fetchone()
    if baris is None:
        return None
    hasil = dict(baris)
    hasil["sesi"] = [dict(b) for b in kon.execute(
        """SELECT id,ke,mulai,menit,dibatalkan FROM jadwal_pertemuan
            WHERE kelompok_id=? OR order_id=? ORDER BY ke,id""",
        (baris["kelompok_id"], order_id))]
    return hasil


# --- pertemuan ------------------------------------------------------------------------------

def pertemuan_dari(kon, pertemuan_id) -> Optional[dict]:
    d.periksa_koneksi(kon)
    pid = jd.periksa_pertemuan_id(pertemuan_id)
    baris = kon.execute(
        "SELECT id,kelompok_id,order_id,ke,mulai,menit,dibatalkan FROM jadwal_pertemuan WHERE id=?",
        (pid,)).fetchone()
    return None if baris is None else dict(baris)


def ubah_pertemuan(kon, admin_id, pertemuan_id, *, tanggal, jam, sekarang) -> None:
    """Geser satu pertemuan; identitas (kelompok/order/ke) tidak berubah."""
    d.periksa_koneksi(kon)
    aktor = d.periksa_pelaku(admin_id)
    pid = jd.periksa_pertemuan_id(pertemuan_id)
    mulai = jd.pertemuan_pertama(tanggal, jam, sekarang)
    kini = dasar.ke_baku(sekarang)
    with d.tulis(kon):
        if pertemuan_dari(kon, pid) is None:
            raise jd.JadwalTidakDitemukan()
        kon.execute("UPDATE jadwal_pertemuan SET mulai=?,diubah=?,diubah_oleh=? WHERE id=?",
                    (mulai, kini, aktor, pid))


def batalkan_pertemuan(kon, admin_id, pertemuan_id, *, batal, sekarang) -> None:
    """Batalkan/pulihkan satu pertemuan tanpa menghapus baris (jejak tetap)."""
    d.periksa_koneksi(kon)
    aktor = d.periksa_pelaku(admin_id)
    pid = jd.periksa_pertemuan_id(pertemuan_id)
    if type(batal) is not bool:
        raise d.PesananDataTidakSah("status batal tidak sah")
    kini = dasar.ke_baku(sekarang)
    with d.tulis(kon):
        if pertemuan_dari(kon, pid) is None:
            raise jd.JadwalTidakDitemukan()
        kon.execute("UPDATE jadwal_pertemuan SET dibatalkan=?,diubah=?,diubah_oleh=? WHERE id=?",
                    (1 if batal else 0, kini, aktor, pid))
