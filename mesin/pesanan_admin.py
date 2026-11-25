"""Catatan yatim, refund manual, dan daftar admin pesanan.

Refund hanya CATATAN manual admin (tanpa panggilan provider). Yatim menyimpan
callback `ord_` yang lolos signature tetapi tanpa order: hanya potongan id,
petunjuk status, dan hash payload (tanpa payload mentah/PII).
"""
from __future__ import annotations

import re

import pesanan_dasar as d
import pesanan_refund_aturan as ra
import pesanan_status as st
import pesanan_transfer as tf
import pesanan_transfer_baca as tb
from schema_pesanan import CATATAN_REFUND

BATAS_ID_YATIM = 40
BATAS_PER_HALAMAN = 100
JAM_PENANDA_MENUNGGU = 72  # bukti terakhir menunggu keputusan lebih lama dari ini = ditandai di admin
# Kelompok saringan daftar admin. Sekat penuh: setiap status turunan masuk tepat satu kelompok.
# `dibayar` memuat order yang pernah dibayar (termasuk perlu_diperiksa dan direfund); `ditolak`
# memuat bukti ditolak dan jendela bayar yang habis.
KELOMPOK_STATUS = {
    "menunggu": (d.STATUS_MENUNGGU_VERIFIKASI,),
    "belum_bayar": (d.STATUS_BELUM_BAYAR,),
    "dibayar": (d.STATUS_SUDAH_DIBAYAR, d.STATUS_PERLU_DIPERIKSA, d.STATUS_DIREFUND),
    "ditolak": (d.STATUS_DITOLAK, d.STATUS_KEDALUWARSA),
}
KUNCI_SEMUA = "semua"
_ASING_ID = re.compile(r"[^A-Za-z0-9_-]")
_PANJANG_AKUN_SINGKAT = 13  # 'akun_' + 8 hex


def _id_yatim(teks):
    if type(teks) is not str or not teks:
        raise d.PesananDataTidakSah("order_id_teks tidak sah")
    return _ASING_ID.sub("?", teks[:BATAS_ID_YATIM])


def catat_yatim(kon, order_id_teks, status_hint, hash_payload, sekarang, operasi_id):
    """Catat callback `ord_` tanpa order, durable dan idempoten per `operasi_id`.

    Mengembalikan True bila baris baru, False bila replay identik;
    PesananKonflik bila `operasi_id` sama dengan isi berbeda.
    """
    d.periksa_koneksi(kon)
    d.periksa_operasi_id(operasi_id)
    isi = (_id_yatim(order_id_teks), d.status_aman(status_hint), d.periksa_hash(hash_payload))
    kini = d.waktu_baku(sekarang)
    with d.tulis(kon):
        lama = kon.execute(
            "SELECT order_id_teks,status_hint,hash_payload FROM pesanan_yatim WHERE operasi_id=?",
            (operasi_id,)).fetchone()
        if lama is not None:
            if tuple(lama) != isi:
                raise d.PesananKonflik("operasi yatim sama dengan isi berbeda")
            return False
        kon.execute("INSERT INTO pesanan_yatim(operasi_id,order_id_teks,status_hint,hash_payload,dibuat) "
                    "VALUES(?,?,?,?,?)", (operasi_id,) + isi + (kini,))
        return True


def catat_refund(kon, order_id, operasi_id, dicatat_oleh, catatan_kode, sekarang):
    """Catat refund manual untuk order ber-receipt; idempoten per `operasi_id`.

    Satu catatan refund per order (dicek di `pesanan_refund` DAN `transfer_refund`). Hanya status turunan
    `STATUS_BISA_REFUND`; selain itu (termasuk tanpa receipt) PesananKonflik.
    Status turunan menjadi `direfund`. Mengembalikan {status, baru}.
    """
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    d.periksa_operasi_id(operasi_id)
    d.periksa_pelaku(dicatat_oleh)
    if catatan_kode not in CATATAN_REFUND:
        raise d.PesananDataTidakSah("catatan_kode tidak sah")
    kini = d.waktu_baku(sekarang)
    isi = (order_id, dicatat_oleh, catatan_kode)
    with d.tulis(kon):
        baru = _tulis_refund(kon, operasi_id, isi, kini)
        order = st.dict_order(st.baris_order(kon, order_id))
        return {"status": st.status_dari_db(kon, order, kini), "baru": baru}


def _tulis_refund(kon, operasi_id, isi, kini):
    """Tulis satu catatan refund; replay/konflik dan status layak diperiksa di KEDUA tabel (lihat aturan)."""
    order_id = isi[0]
    if st.baris_order(kon, order_id) is None:
        raise d.PesananTidakDitemukan()
    if st.receipt_order(kon, order_id) is None:
        # Jalur transfer rekening: receipt-nya `transfer_lunas`, refund-nya `transfer_refund`.
        return tf.tulis_refund_transfer(kon, operasi_id, isi, kini)
    if ra.siapkan_refund(kon, operasi_id, isi, kini):
        return False
    kon.execute("INSERT INTO pesanan_refund(operasi_id,order_id,dicatat_oleh,catatan_kode,dibuat) "
                "VALUES(?,?,?,?,?)", (operasi_id,) + isi + (kini,))
    return True


_SQL_DAFTAR = """
SELECT o.order_id, o.akun_id, o.rupiah, o.dibuat, %s AS kedaluwarsa, r.hasil AS receipt_hasil,
       r.alasan_kode,
       EXISTS(SELECT 1 FROM pesanan_refund f WHERE f.order_id=o.order_id) AS direfund,
       EXISTS(SELECT 1 FROM pesanan_pengamatan p WHERE p.order_id=o.order_id
              AND p.sumber='status' AND p.transaction_status IN (%s)) AS refund_teramati,
       %s AS transfer_lunas, %s AS transfer_direfund, %s AS transfer_bukti, %s AS bukti_diunggah
FROM pesanan_order o LEFT JOIN pesanan_receipt r ON r.order_id=o.order_id%s
ORDER BY o.dibuat DESC, o.order_id DESC LIMIT ? OFFSET ?
"""


def _sql_daftar(kon, hanya_menunggu=False):
    fakta = tb.sql_fakta(kon)
    saring = " WHERE " + fakta["menunggu"] if hanya_menunggu else ""
    return _SQL_DAFTAR % (
        st.SQL_KEDALUWARSA_TERBARU, ",".join("'%s'" % s for s in d.STATUS_REFUND_PROVIDER),
        fakta["lunas"], fakta["direfund"], fakta["bukti"], fakta["diunggah"], saring)


def _menunggu_lama(status, diunggah, kini):
    """True bila order menunggu verifikasi dan bukti terakhirnya diunggah lebih dari `JAM_PENANDA_MENUNGGU` jam lalu."""
    if status != d.STATUS_MENUNGGU_VERIFIKASI or diunggah is None:
        return False
    return diunggah <= d.tambah_jam(kini, -JAM_PENANDA_MENUNGGU)


def _lama_di_atas(items):
    """Urutan stabil: order menunggu-lama lebih dulu, sisanya tetap urut semula."""
    return tuple(sorted(items, key=lambda i: not i["menunggu_lama"]))


def _item_admin(baris, kini):
    status = st.turunkan_status(
        kedaluwarsa=baris["kedaluwarsa"], sekarang=kini,
        receipt_hasil=baris["receipt_hasil"], direfund=bool(baris["direfund"]),
        refund_teramati=bool(baris["refund_teramati"]),
        transfer_lunas=bool(baris["transfer_lunas"]),
        transfer_direfund=bool(baris["transfer_direfund"]),
        transfer_bukti=baris["transfer_bukti"])
    return {
        "order_id": baris["order_id"],
        "akun": baris["akun_id"][:_PANJANG_AKUN_SINGKAT],
        "rupiah": baris["rupiah"],
        "dibuat": baris["dibuat"],
        "kedaluwarsa": baris["kedaluwarsa"],
        "alasan_kode": baris["alasan_kode"],
        "status": status,
        "dua_jalur": st.dua_jalur(baris["receipt_hasil"], bool(baris["transfer_lunas"]), baris["transfer_bukti"]),
        "menunggu_lama": _menunggu_lama(status, baris["bukti_diunggah"], kini),
    }


def _daftar_menunggu(kon, halaman, per_halaman, kini):
    """Tab menunggu verifikasi: kandidat SQL (ada bukti belum diputuskan), lalu status turunan memutuskan.

    Penyaring akhir memakai `turunkan_status` yang sama dengan daftar penuh, jadi tab tidak bisa
    berbeda dari status yang ditampilkan; kandidat kecil (bukti belum diputuskan).
    """
    baris = kon.execute(_sql_daftar(kon, True), (-1, 0)).fetchall()
    items = _lama_di_atas(i for i in (_item_admin(b, kini) for b in baris)
                          if i["status"] == d.STATUS_MENUNGGU_VERIFIKASI)
    awal = (halaman - 1) * per_halaman
    return {"items": items[awal:awal + per_halaman], "total": len(items),
            "halaman": halaman, "per_halaman": per_halaman}


def daftar_admin(kon, *, halaman, per_halaman, sekarang, hanya_menunggu=False):
    """Daftar order terbaru (SELECT saja) berdata minimal untuk admin.

    Tanpa kontak, nama anak, siswa_id, cek_id, merchant, atau payload; akun
    hanya awalan id, `rupiah` = harga order (dipakai kolom Nominal bila bukan jalur transfer).
    `sekarang` dibutuhkan untuk status `kedaluwarsa`.
    `hanya_menunggu` = hanya order berstatus `menunggu_verifikasi` (tab verifikasi transfer).
    """
    d.periksa_koneksi(kon)
    d.periksa_bilangan(halaman, "halaman")
    if type(per_halaman) is not int or not 1 <= per_halaman <= BATAS_PER_HALAMAN:
        raise d.PesananDataTidakSah("per_halaman tidak sah")
    kini = d.waktu_baku(sekarang)
    if hanya_menunggu:
        return _daftar_menunggu(kon, halaman, per_halaman, kini)
    total = kon.execute("SELECT COUNT(*) FROM pesanan_order").fetchone()[0]
    baris = kon.execute(_sql_daftar(kon), (per_halaman, (halaman - 1) * per_halaman)).fetchall()
    return {"items": tuple(_item_admin(b, kini) for b in baris), "total": total,
            "halaman": halaman, "per_halaman": per_halaman}


def daftar_tersaring(kon, *, halaman, per_halaman, sekarang, kelompok=None):
    """Daftar admin per kelompok status (SELECT saja) beserta hitungan semua kelompok.

    Status turunan dihitung dengan `turunkan_status` yang sama dengan daftar penuh lalu disaring di Python
    (satu pemindaian ledger), jadi saringan dan hitungan tidak bisa berbeda dari lencana status yang
    tampil. `kelompok` None = semua order; nilai di luar `KELOMPOK_STATUS` = PesananDataTidakSah.
    Kunci hasil: items, total (sesudah saring), halaman, per_halaman, hitungan {kelompok|semua: n}.
    """
    d.periksa_koneksi(kon)
    d.periksa_bilangan(halaman, "halaman")
    if type(per_halaman) is not int or not 1 <= per_halaman <= BATAS_PER_HALAMAN:
        raise d.PesananDataTidakSah("per_halaman tidak sah")
    if kelompok is not None and kelompok not in KELOMPOK_STATUS:
        raise d.PesananDataTidakSah("kelompok tidak sah")
    kini = d.waktu_baku(sekarang)
    semua = tuple(_item_admin(b, kini) for b in kon.execute(_sql_daftar(kon), (-1, 0)).fetchall())
    hitungan = {k: sum(1 for i in semua if i["status"] in status) for k, status in KELOMPOK_STATUS.items()}
    hitungan[KUNCI_SEMUA] = len(semua)
    pilihan = semua if kelompok is None else tuple(i for i in semua if i["status"] in KELOMPOK_STATUS[kelompok])
    if kelompok == "menunggu":
        pilihan = _lama_di_atas(pilihan)
    awal = (halaman - 1) * per_halaman
    return {"items": pilihan[awal:awal + per_halaman], "total": len(pilihan), "halaman": halaman,
            "per_halaman": per_halaman, "hitungan": hitungan}
