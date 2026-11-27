"""Orang tua memilih kelompok Mini sendiri (butir QA #4): penempatan mandiri, sekali saja, hanya untuk Mini.

Aturan penempatan sama dengan `jadwal_store.tempatkan` (kuota, kelompok ditutup setelah dua pertemuan mulai, pertemuan
tidak boleh melewati masa akses, satu penempatan per anak); modul ini meminjam primitifnya dan menambah syarat orang tua:
anak milik akun, order Mini aktif, dan order itu BELUM punya penempatan. Semua dalam SATU transaksi, jadi penempatan admin
yang masuk bersamaan tidak pernah tertimpa dan dua orang tua tidak bisa merebut kursi terakhir sekaligus. Mengubah atau
melepas penempatan tetap lewat admin. Private tidak ditangani: butuh guru, tanggal, dan jam yang ditentukan admin.
Modul sengaja bukan berkas `*store*` (kontrak recovery tidak bergeser). Pilihan untuk orang tua tanpa guru atau lokasi.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple

import jadwal_dasar as jd
import jadwal_store as js
import kelas_dasar as dasar
import kelas_status as ks
import kelas_store
import pesanan_dasar as d
import schema_jadwal


@dataclass(frozen=True)
class PilihanKelompok:
    kelompok_id: str
    nama: str
    mulai: str          # pertemuan aktif berikutnya, UTC baku
    sisa: int           # kursi yang masih kosong (0 bila penuh)
    penuh: bool = False  # terbuka tetapi kursinya habis: tampil sebagai "penuh", tidak bisa dipilih


PESAN_BUKAN_MILIK_GURU = "kelompok sudah dipindah ke guru lain sejak permintaan diajukan"


class KelompokBukanMilikGuru(jd.JadwalKonflik):
    """`guru_diharapkan` tidak sama dengan guru kelompok di dalam transaksi tempatkan (kelompok dipindah guru)."""


def _penempatan_lain_menghalangi(kon, order_id: str, kini: str) -> bool:
    """Anak masih punya penempatan lama yang belum boleh dipensiunkan (aturan sama dengan `js._pensiunkan_penempatan_lama`)."""
    lama = [b["order_id"] for b in kon.execute(
        "SELECT p.order_id FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id "
        "WHERE p.order_id<>? AND o.siswa_id=(SELECT siswa_id FROM kelas_order WHERE id=?)", (order_id, order_id))]
    if not lama:
        return False
    mulai_baru = kon.execute("SELECT MIN(mulai) FROM kelas_akses WHERE order_id=?", (order_id,)).fetchone()[0]
    return not all(js._akses_lama_berakhir(kon, ada, mulai_baru, kini) for ada in lama)


def _order_mini_tanpa_jadwal(kon, akun_id: str, siswa_id: int, kini: str):
    """Order Mini AKTIF terbaru milik (akun, anak) yang belum ditempatkan, atau None."""
    for order in kon.execute(
            "SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? AND paket=? ORDER BY dibuat DESC,id DESC"
            % ks.KOLOM_ORDER, (akun_id, siswa_id, schema_jadwal.KODE_PAKET_MINI)).fetchall():
        if ks.status_dari(order, ks.fakta_order(kon, order["id"]), kini) != dasar.STATUS_AKTIF:
            continue
        if kon.execute("SELECT 1 FROM jadwal_penempatan WHERE order_id=?", (order["id"],)).fetchone() is not None:
            return None            # sudah ditempatkan (admin atau pilihan sendiri): sekali saja
        return None if _penempatan_lain_menghalangi(kon, order["id"], kini) else order
    return None


def _kelompok_terbuka(kon, kelompok: dict, order_id: str, kini: str) -> Optional[str]:
    """Pertemuan berikutnya kelompok bila order ini boleh melihatnya (belum ditutup, muat dalam akses), selain itu None.

    Kursi TIDAK diperiksa di sini: kelompok penuh tetap tampil (`penuh`), dan `pilih_kelompok` tetap menolaknya.
    """
    kid = kelompok["id"]
    berikut = js._pertemuan_mendatang(kon, kid, kini)
    if berikut is None or js._jumlah_sudah_mulai(kon, kid, kini) >= js.TUTUP_SETELAH_PERTEMUAN_MULAI:
        return None
    batas = js._batas_akses_order(kon, order_id)
    terakhir = js._pertemuan_aktif_terakhir(kon, kid)
    if terakhir is not None and batas is not None and terakhir > batas:
        return None
    return berikut


def _pilihan(kon, kelompok: dict, berikut: str) -> PilihanKelompok:
    isi = js._isi_kelompok(kon, kelompok["id"])
    penuh = isi >= kelompok["kuota"]
    return PilihanKelompok(kelompok["id"], kelompok["nama"], berikut, max(0, kelompok["kuota"] - isi), penuh)


def pilihan_untuk(kon, akun_id, siswa_id, sekarang) -> Tuple[PilihanKelompok, ...]:
    """Kelompok terbuka untuk anak ini sekarang, termasuk yang penuh (`penuh=True`, tidak bisa dipilih).

    Kosong bila tidak ada order Mini aktif yang belum ditempatkan. Kelompok yang sudah ditutup atau tidak muat dalam
    masa akses tidak pernah masuk. Anak milik akun lain -> PesananTidakDitemukan. Hanya baca.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    dasar.periksa_siswa_id(siswa_id)
    kini = dasar.ke_baku(sekarang)
    kelas_store._wajib_anak_milik(kon, akun_id, siswa_id)
    order = _order_mini_tanpa_jadwal(kon, akun_id, siswa_id, kini)
    if order is None:
        return ()
    hasil = []
    for baris in kon.execute("SELECT id,nama,kuota FROM jadwal_kelompok ORDER BY nama,id").fetchall():
        kelompok = dict(baris)
        berikut = _kelompok_terbuka(kon, kelompok, order["id"], kini)
        if berikut is not None:
            hasil.append(_pilihan(kon, kelompok, berikut))
    return tuple(sorted(hasil, key=lambda p: (p.mulai, p.nama, p.kelompok_id)))


def pilih_kelompok(kon, akun_id, siswa_id, kelompok_id, sekarang, *, guru_diharapkan=None) -> None:
    """Tempatkan order Mini aktif anak ke `kelompok_id`. Syarat tidak terpenuhi: galat domain tanpa tulis apa pun.

    `guru_diharapkan` (None = tidak diperiksa, perilaku lama) memastikan kelompok masih milik guru itu DI DALAM transaksi;
    guru lain (termasuk None) = `KelompokBukanMilikGuru`.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    dasar.periksa_siswa_id(siswa_id)
    kid = jd.periksa_kelompok_id(kelompok_id)
    kini = dasar.ke_baku(sekarang)
    with d.tulis(kon):
        kelas_store._wajib_anak_milik(kon, akun_id, siswa_id)
        order = _order_mini_tanpa_jadwal(kon, akun_id, siswa_id, kini)
        if order is None:
            raise dasar.KelasKonflik("tidak ada paket Mini aktif yang belum ditempatkan")
        kelompok = js._group(kon, kid)
        if kelompok is None:
            raise jd.JadwalTidakDitemukan()
        if guru_diharapkan is not None and kelompok["guru_id"] != guru_diharapkan:
            raise KelompokBukanMilikGuru(PESAN_BUKAN_MILIK_GURU)
        if js._pertemuan_mendatang(kon, kid, kini) is None:
            raise jd.JadwalKonflik("kelompok sudah selesai")
        if js._jumlah_sudah_mulai(kon, kid, kini) >= js.TUTUP_SETELAH_PERTEMUAN_MULAI:
            raise jd.JadwalKonflik(js.PESAN_DITUTUP)
        js._pastikan_dalam_akses(js._pertemuan_aktif_terakhir(kon, kid), js._batas_akses_order(kon, order["id"]))
        js._pensiunkan_penempatan_lama(kon, order["id"], kini)
        if js._isi_kelompok(kon, kid) >= kelompok["kuota"]:
            raise jd.JadwalPenuh()
        try:
            kon.execute(
                "INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                "dibuat_oleh,diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)",
                (order["id"], kid, kini, kini, akun_id, akun_id))
        except sqlite3.IntegrityError as galat:
            raise js._peta_integritas(galat) from None
