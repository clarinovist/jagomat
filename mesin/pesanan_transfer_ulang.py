"""Jendela bayar ulang untuk jalur transfer rekening (domain, tanpa HTTP/env/berkas/jaringan).

Saat jendela 24 jam habis TANPA bukti menunggu dan order belum lunas, guru boleh membuka jendela baru
(maksimal `MAKS_JENDELA`, sama dengan Midtrans). Pembukaan memakai `pesanan_jendela.buka_jendela_ulang`
(sumber kebenaran batas, kuota, receipt, bukti menunggu, lunas) sehingga jalur Midtrans tidak berubah;
tambahan di sini hanya penyempitan khusus transfer:

* hanya status turunan `kedaluwarsa` (jendela lokal benar-benar habis). Sinyal "mati" dari provider pada
  jendela yang masih terbuka tetap hanya membuka jalur Midtrans, bukan jalur transfer;
* tagihan jendela baru TIDAK dibuat otomatis: guru membuat tagihan (kode unik baru) lewat
  `buat_tagihan_transfer`, yang menghindari nominal yang masih dipegang order lain. Nominal jendela lama
  dilepas karena hanya tagihan jendela terbaru yang dipegang.

`operasi_id` dari pemanggil (deterministik per order dan urutan jendela) sehingga ulangan identik
idempoten dan Midtrans/transfer yang membuka jendela yang sama tidak membuka dua jendela.
"""
from __future__ import annotations

import pesanan_dasar as d
import pesanan_jendela as jd
import pesanan_status as st


def _operasi_sudah_dipakai(kon, operasi_id) -> bool:
    return kon.execute("SELECT 1 FROM pesanan_jendela WHERE operasi_id=?", (operasi_id,)).fetchone() is not None


def _wajib_kedaluwarsa(kon, order_id, akun_id, sekarang) -> None:
    order = st.ambil_order(kon, order_id, akun_id)
    if st.status_dari_db(kon, order, d.waktu_baku(sekarang)) != d.STATUS_KEDALUWARSA:
        raise d.PesananKonflik("jendela pembayaran transfer belum dapat dibuka ulang")


def buka_ulang(kon, order_id, akun_id, sekarang, operasi_id) -> dict:
    """Buka jendela bayar baru untuk order MILIK `akun_id` yang kedaluwarsa tanpa bukti menunggu.

    Order bukan milik akun / tak dikenal -> PesananTidakDitemukan identik; status selain `kedaluwarsa`
    (terbuka, menunggu_verifikasi, lunas, ...) -> PesananKonflik; batas jendela -> PesananBatasJendela;
    kuota -> PesananKuotaHabis. Gagal = tanpa tulis. Mengembalikan dict jendela baru dengan `baru`.
    """
    d.periksa_koneksi(kon)
    d.periksa_operasi_id(operasi_id)
    if not _operasi_sudah_dipakai(kon, operasi_id):
        _wajib_kedaluwarsa(kon, order_id, akun_id, sekarang)
    return jd.buka_jendela_ulang(kon, order_id, akun_id, sekarang, operasi_id)
