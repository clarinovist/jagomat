"""Pembuatan order Paket Coba: semua prasyarat diperiksa server-side, atomik.

Tidak ada parameter nominal: harga selalu `RUPIAH_PAKET`. Domain admin DB tidak
membaca DB belajar; pemanggil menyuntik fakta cek (`cek_selesai`) dan kontak
(`punya_kontak`). Tidak menyentuh tabel `langganan_*`.
"""
from __future__ import annotations

import secrets
import sqlite3

import pesanan_dasar as d
import pesanan_jendela as jd
import pesanan_status as st


def periksa_prasyarat_cek(hasil_baca) -> bool:
    """Murni: True hanya bila hasil `cek_gratis.baca_hasil` berstatus selesai + bernilai skor.

    Catatan: `baca_hasil` mengembalikan cek TERBARU akun, tanpa id anak/cek.
    Pemanggil (3c) wajib memastikan cek yang dibaca milik anak yang dipesan.
    """
    return (type(hasil_baca) is dict and hasil_baca.get("status") == "selesai"
            and type(hasil_baca.get("skor")) is int)


def _kunci_idempotensi(order_id):
    # 'ord-' + 32 hex = 36 char: dalam rentang 8..46 dan cocok pola identitas operasi.
    return "ord-" + order_id[len(d.PREFIX_ORDER):]


def _validasi_masukan(akun_id, siswa_id, cek_id, merchant, order_id, sekarang):
    d.periksa_akun_id(akun_id)
    d.periksa_bilangan(siswa_id, "siswa_id")
    d.periksa_bilangan(cek_id, "cek_id")
    d.periksa_referensi(merchant, "merchant")
    if order_id is not None:
        d.periksa_order_id(order_id)
    return d.waktu_baku(sekarang)


def _sisipkan(kon, *, order_id, akun_id, siswa_id, cek_id, merchant, kini):
    kedaluwarsa = d.tambah_jam(kini, d.KEDALUWARSA_JAM)
    kunci = _kunci_idempotensi(order_id)
    kon.execute(
        """INSERT INTO pesanan_order(order_id,akun_id,siswa_id,cek_id,rupiah,currency,
               provider,channel,merchant,idempotency_key,dibuat,kedaluwarsa)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (order_id, akun_id, siswa_id, cek_id, d.RUPIAH_PAKET, d.MATA_UANG, d.PROVIDER,
         d.CHANNEL, merchant, kunci, kini, kedaluwarsa))
    # Jendela #1 satu transaksi dengan order; kuncinya = kunci order.
    jd.sisipkan_jendela(kon, order_id=order_id, urutan=1, idempotency_key=kunci,
                        operasi_id=None, dibuat=kini)


def buat_order(kon, *, akun_id, siswa_id, cek_id, cek_selesai, punya_kontak,
               sekarang, merchant, order_id=None):
    """Buat (atau kembalikan) order Paket Coba milik `akun_id` untuk satu anak.

    Urutan, semuanya dalam satu `BEGIN IMMEDIATE`: cek selesai (bukan True ->
    PesananTidakDitemukan, tanpa menyentuh DB) -> order yang sudah ada untuk anak
    ini (idempoten bila milik akun yang sama, selain itu PesananTidakDitemukan)
    -> kontak (PesananButuhKontak) -> kuota (PesananKuotaHabis) -> tulis order
    beserta jendela bayar #1 (`pesanan_jendela`).
    Mengembalikan dict order baru dengan kunci tambahan `baru`.
    """
    kini = _validasi_masukan(akun_id, siswa_id, cek_id, merchant, order_id, sekarang)
    d.periksa_koneksi(kon)
    if cek_selesai is not True:
        raise d.PesananTidakDitemukan()
    ident = order_id if order_id is not None else d.PREFIX_ORDER + secrets.token_hex(16)
    with d.tulis(kon):
        ada = kon.execute("SELECT order_id,akun_id FROM pesanan_order WHERE siswa_id=?",
                          (siswa_id,)).fetchone()
        if ada is not None:
            if ada["akun_id"] != akun_id:
                raise d.PesananTidakDitemukan()
            return {**st.dict_order(st.baris_order(kon, ada["order_id"])), "baru": False}
        if punya_kontak is not True:
            raise d.PesananButuhKontak()
        if jd.jumlah_aktif(kon, kini) >= d.KUOTA_ORDER:
            raise d.PesananKuotaHabis()
        try:
            _sisipkan(kon, order_id=ident, akun_id=akun_id, siswa_id=siswa_id,
                      cek_id=cek_id, merchant=merchant, kini=kini)
        except sqlite3.IntegrityError:
            raise d.PesananKonflik("order bentrok dengan catatan yang ada") from None
        return {**st.dict_order(st.baris_order(kon, ident)), "baru": True}
