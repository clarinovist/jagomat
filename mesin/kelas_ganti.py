"""Ganti paket saat tagihan belum dibayar (butir QA #3): tagihan baru untuk paket lain, tagihan lama dibiarkan habis sendiri.

Ledger kelas immutable dan status diturunkan, jadi "ganti" tidak mengubah baris: tagihan baru untuk paket lain
ditulis, tagihan lama (belum ada satu pun bukti) dibiarkan terbuka sampai kedaluwarsa. Halaman pembeli selalu memakai
tagihan TERBARU (`kelas_murid_http._tagihan_berjalan`), jadi bukti tidak pernah masuk ke tagihan lama. Semua dalam SATU
transaksi supaya dua tab atau bukti yang masuk bersamaan tidak melahirkan tagihan ketiga. Syarat: anak milik akun, tepat
satu tagihan terbuka, statusnya belum_bayar tanpa bukti, paket tujuan beda. Nominal selalu dari server; deposit Peta yang
dipegang tagihan lama dipindahkan ke tagihan baru (hanya satu yang akan pernah menerima bukti). Modul sengaja bukan
berkas `*store*` (kontrak recovery tidak bergeser); primitif penulisan dipinjam dari `kelas_store`. Kembali ke paket
semula selagi tagihan lamanya terbuka ditolak trigger DB (satu terbuka per anak dan paket) dan muncul sebagai KelasKonflik.
"""
from __future__ import annotations

import secrets

import kelas_dasar as k
import kelas_rincian
import kelas_status as ks
import kelas_store as store
import paket_belajar_katalog as katalog
import pesanan_dasar as d


def ganti_paket(kon, akun_id, siswa_id, kode_paket_baru, sekarang, *, acak=None) -> katalog.TagihanKelas:
    """Tagihan belum_bayar anak diganti ke `kode_paket_baru`; mengembalikan tagihan baru. Selain syarat: KelasKonflik tanpa tulis."""
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    k.periksa_siswa_id(siswa_id)
    paket = k.kode_paket_sah(kode_paket_baru)
    kini = k.ke_baku(sekarang)
    pilih = secrets.choice if acak is None else acak
    with d.tulis(kon):
        store._wajib_anak_milik(kon, akun_id, siswa_id)
        terbuka = list(ks.order_terbuka_siswa(kon, akun_id, siswa_id, kini))
        if len(terbuka) != 1:
            raise k.KelasKonflik("anak tidak punya tepat satu tagihan yang bisa diganti")
        lama, fakta, status = terbuka[0]
        if status != k.STATUS_BELUM_BAYAR or fakta.jumlah_bukti:
            raise k.KelasKonflik("tagihan sudah ada bukti atau bukan belum bayar")
        if lama["paket"] == paket:
            raise k.KelasKonflik("paket tujuan sama dengan tagihan berjalan")
        rincian, deposit_order = kelas_rincian.rincian_untuk(kon, akun_id, siswa_id, paket, kini, lama["id"])
        kode = store._alokasi_kode(kon, rincian.nominal, kini, pilih)
        order_id = store._tulis_order(kon, akun_id, siswa_id, paket, rincian, deposit_order, kode, kini)
        order = ks.baris_order(kon, order_id)
        return store._tagihan_kelas(kon, order, ks.fakta_order(kon, order_id), k.STATUS_BELUM_BAYAR)
