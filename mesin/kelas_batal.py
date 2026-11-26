"""Batal dan pulih tagihan Paket Belajar (domain): tagihan tanpa bukti boleh dibatalkan selama jendela bayar belum lewat.

Tanpa HTTP. Tagihan dipilih lewat KODE PAKET (allowlist katalog), bukan id order: satu tagihan terbuka per (anak, paket)
dijamin DB/domain, dan akun/anak diambil dari sesi, jadi (sesi, kode paket) menunjuk persis satu tagihan. `batalkan_tagihan`
memiliki transaksinya sendiri (`d.tulis`) dan mencari tagihan DI DALAM transaksi itu. `pulihkan_bila_ada` TIDAK: ia dipanggil
dari dalam transaksi tulis `kelas_store.buat_tagihan`, dan `d.tulis` tidak reentrant. Modul ini tidak mengimpor `kelas_store`
(sebaliknya, `kelas_store` yang memanggil modul ini).

Kepemilikan: pencarian tagihan terbuka selalu menyaring `akun_id` DAN `siswa_id` (`ks.order_terbuka`). Tanpa tagihan terbuka
untuk paket itu (termasuk milik akun atau anak lain, dan yang sudah lunas, dibatalkan, atau kedaluwarsa) hasilnya
`PesananTidakDitemukan` yang identik, tanpa tulis dan tanpa efek samping.
"""
from __future__ import annotations

from typing import Optional

import kelas_catatan as cat
import kelas_dasar as k
import kelas_rincian
import kelas_status as ks
import pesanan_dasar as d


def batalkan_tagihan(kon, akun_id: str, siswa_id: int, kode_paket: str, sekarang) -> dict:
    """Batalkan tagihan belum bayar tanpa bukti untuk (anak, paket) milik akun ini; mengembalikan {order_id, status}.

    Atomik: galat apa pun terjadi sebelum catatan ditulis, sehingga tidak ada baris yang berubah. Kode paket asing ->
    PesananDataTidakSah sebelum DB. Tanpa tagihan terbuka untuk paket itu -> PesananTidakDitemukan. Tabel catatan belum
    dipasang, status bukan belum bayar, atau sudah ada bukti -> KelasKonflik tanpa tulis.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    k.periksa_siswa_id(siswa_id)
    paket = k.kode_paket_sah(kode_paket)
    kini = k.ke_baku(sekarang)
    with d.tulis(kon):
        ada = ks.order_terbuka(kon, akun_id, siswa_id, paket, kini)
        if ada is None:
            raise d.PesananTidakDitemukan()
        order, fakta, status = ada
        if not cat.terpasang(kon):
            raise k.KelasKonflik("pembatalan tagihan belum tersedia")
        if status != k.STATUS_BELUM_BAYAR or fakta.jumlah_bukti:
            raise k.KelasKonflik("tagihan ini tidak bisa dibatalkan")
        cat.catat(kon, order["id"], cat.AKSI_BATAL, kini)
        return {"order_id": order["id"], "status": k.STATUS_DIBATALKAN}


def pulihkan_bila_ada(kon, akun_id: str, siswa_id: int, kode_paket: str, kini: str) -> Optional[object]:
    """Pulihkan tagihan batal paket ini (jendela belum lewat) dan kembalikan baris ordernya; None bila tidak ada.

    Dipanggil di dalam transaksi tulis pemanggil. Tagihan berdeposit hanya dipulihkan bila deposit-nya masih tersedia
    (`kelas_rincian.deposit_masih_tersedia`); selain itu KelasKonflik tanpa tulis, karena deposit itu sudah milik tagihan lain.
    """
    ada = ks.order_dibatalkan(kon, akun_id, siswa_id, kode_paket, kini)
    if ada is None:
        return None
    order = ada[0]
    deposit = ks.baris_tagihan(kon, order["id"])["deposit_order_id"]
    if deposit is not None and not kelas_rincian.deposit_masih_tersedia(kon, akun_id, siswa_id, kode_paket,
                                                                         deposit, kini):
        raise k.KelasKonflik("deposit tagihan yang dibatalkan sudah dipakai tagihan lain")
    cat.catat(kon, order["id"], cat.AKSI_PULIH, kini)
    return order
