"""Catat bukti Paket Belajar ke tagihan terbuka TERBARU anak, dipilih di dalam transaksi tulis yang sama (butir QA #3).

`kelas_store.catat_bukti` memilih tagihan dari kode paket yang dibaca pemanggil sebelumnya; ganti paket yang masuk di antaranya
membuat bukti jatuh ke tagihan LAMA yang sudah digantikan. Di sini tagihan penerima diturunkan dari akun, anak, dan keadaan DB di dalam
satu `BEGIN IMMEDIATE` (tanpa kode paket dari luar), sehingga ganti paket dari proses atau tab mana pun terurut dengan unggah: yang
masuk lebih dulu menang, yang kedua melihat keadaan akhir (unggah lebih dulu = ganti ditolak karena bukti ada; ganti lebih dulu = bukti
masuk ke tagihan baru). Aturan lain sama dengan `catat_bukti` (jendela bayar, berkas kembar, batas bukti) dan memakai primitifnya.
Modul sengaja bukan berkas `*store*` (kontrak recovery tidak bergeser).
"""
from __future__ import annotations

import sqlite3

import kelas_dasar as k
import kelas_status as ks
import kelas_store as store
import pesanan_dasar as d


def catat_bukti_terbaru(kon, akun_id, siswa_id, mime, ukuran, sha256, nama_tersimpan, sekarang) -> dict:
    """Catat metadata satu bukti untuk tagihan terbuka terbaru (akun, anak). Mengembalikan {bukti_id, status, baru}.

    Tanpa tagihan terbuka atau jendela lewat -> KelasKonflik; berkas kembar menunggu -> bukti yang ada (`baru=False`); berkas yang sudah
    pernah dipakai -> KelasKonflik; `MAKS_BUKTI` tercapai -> BatasBukti. Tanpa tulis bila galat.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    k.periksa_siswa_id(siswa_id)
    k.periksa_meta_bukti(mime, ukuran, sha256, nama_tersimpan)
    kini = k.ke_baku(sekarang)
    with d.tulis(kon):
        terbaru = next(iter(ks.order_terbuka_siswa(kon, akun_id, siswa_id, kini)), None)
        if terbaru is None or kini >= terbaru[0]["kedaluwarsa"]:
            raise k.KelasKonflik("anak tidak punya tagihan paket yang menerima bukti")
        order, fakta, status = terbaru
        sama = store._bukti_menunggu_sama(kon, order["id"], sha256)
        if sama is not None:
            return {"bukti_id": sama, "status": status, "baru": False}
        if store._sha_sudah_dipakai(kon, sha256):
            raise k.KelasKonflik("berkas bukti sudah pernah dipakai")
        if fakta.jumlah_bukti >= k.MAKS_BUKTI:
            raise k.BatasBukti()
        try:
            kursor = kon.execute(
                "INSERT INTO kelas_bukti(order_id,berkas,mime,ukuran,sha256,diunggah) VALUES(?,?,?,?,?,?)",
                (order["id"], nama_tersimpan, mime, ukuran, sha256, kini))
        except sqlite3.IntegrityError:
            raise k.KelasKonflik("bukti bentrok dengan catatan yang ada") from None
        return {"bukti_id": kursor.lastrowid, "status": k.STATUS_MENUNGGU, "baru": True}
