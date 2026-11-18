"""Jendela bayar/QR per order pesanan (append-only) dan pembukaan jendela ulang.

`pesanan_order.kedaluwarsa` immutable dan `UNIQUE(siswa_id)`; tanpa jendela, order
yang kedaluwarsa tanpa bayar mengunci anak selamanya. Jendela #1 dibuat bersama
order (kunci idempotensinya = kunci order); jendela berikutnya hanya lewat
:func:`buka_jendela_ulang` dengan order_id TETAP sama. Kuota menghitung order
berdasar jendela terbaru: order tanpa receipt yang jendela terbarunya sudah
kedaluwarsa tidak memakan slot.

Semantik izin meniru `subscription_service.buat_ulang_qr`: tanpa receipt, dan
provider menyatakan expire/cancel/deny (pengamatan sumber `status`) atau
jendela lokal sudah lewat. Callback (sumber `callback`) hanya petunjuk dan tidak
pernah membuka jendela. Modul ini tidak menghubungi provider: pemanggil (3c-3)
membuat transaksi memakai `jendela_terbaru`.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3

import pesanan_dasar as d
import pesanan_status as st

MAKS_JENDELA = 5
KELAS_MATI = ("expire", "cancel", "deny")  # sama dengan midtrans_contract.KELAS_MATI (dijaga tes)
PREFIX_KUNCI_ULANG = "ordj-"
_POLA_KUNCI = re.compile(r"[A-Za-z0-9_-]{8,46}")

jendela_terbaru = st.jendela_terbaru  # fungsi baca untuk 3c-3

_SQL_MATI = (
    "SELECT 1 FROM pesanan_pengamatan WHERE order_id=? AND sumber='status' "
    "AND transaction_status IN (%s) AND dibuat>? LIMIT 1"
    % ",".join("'%s'" % s for s in KELAS_MATI))


class PesananBatasJendela(d.PesananKonflik):
    def __init__(self):
        super().__init__("batas jendela pembayaran tercapai")


def _tidak_dapat_dibuka():
    return d.PesananKonflik("jendela pembayaran tidak dapat dibuka ulang")


def periksa_kunci(nilai):
    if type(nilai) is not str or _POLA_KUNCI.fullmatch(nilai) is None:
        raise d.PesananDataTidakSah("kunci idempotensi tidak sah")
    return nilai


def kunci_ulang(order_id, urutan):
    """Kunci idempotensi deterministik jendela ke-`urutan` (>=2) satu order."""
    bahan = ("%s|%d" % (order_id, urutan)).encode()
    return PREFIX_KUNCI_ULANG + hashlib.sha256(bahan).hexdigest()[:32]


def sisipkan_jendela(kon, *, order_id, urutan, idempotency_key, operasi_id, dibuat):
    """Tulis satu jendela (kedaluwarsa = dibuat + KEDALUWARSA_JAM); hanya dalam transaksi tulis."""
    kedaluwarsa = d.tambah_jam(dibuat, d.KEDALUWARSA_JAM)
    kon.execute(
        "INSERT INTO pesanan_jendela(order_id,urutan,idempotency_key,operasi_id,dibuat,kedaluwarsa) "
        "VALUES(?,?,?,?,?,?)", (order_id, urutan, idempotency_key, operasi_id, dibuat, kedaluwarsa))


def jumlah_aktif(kon, kini, kecuali=None):
    """Order yang memakai slot kuota, tidak menghitung `kecuali` (order yang sedang dibuka ulang).

    Aktif = ber-receipt (lunas/perlu_diperiksa) ATAU jendela terbaru belum kedaluwarsa.
    """
    return kon.execute(
        """SELECT COUNT(*) FROM pesanan_order o
           WHERE o.order_id IS NOT ?
             AND (EXISTS(SELECT 1 FROM pesanan_receipt r WHERE r.order_id=o.order_id)
                  OR %s>?)""" % st.SQL_KEDALUWARSA_TERBARU, (kecuali, kini)).fetchone()[0]


def _hasil(baris, baru):
    return {"order_id": baris["order_id"], "urutan": baris["urutan"],
            "idempotency_key": baris["idempotency_key"], "dibuat": baris["dibuat"],
            "kedaluwarsa": baris["kedaluwarsa"], "baru": baru}


def _replay(kon, order_id, operasi_id, idem_baru):
    """Jendela milik `operasi_id` bila sudah pernah dibuka (identik); None bila operasi baru."""
    lama = kon.execute(
        "SELECT order_id,urutan,idempotency_key,dibuat,kedaluwarsa FROM pesanan_jendela "
        "WHERE operasi_id=?", (operasi_id,)).fetchone()
    if lama is None:
        return None
    if lama["order_id"] != order_id or (idem_baru is not None
                                        and idem_baru != lama["idempotency_key"]):
        raise d.PesananKonflik("operasi jendela sama dengan isi berbeda")
    return _hasil(lama, False)


def _mati_teramati(kon, order_id, terbaru):
    """Provider menyatakan expire/cancel/deny sesudah jendela terbaru dibuat."""
    return kon.execute(_SQL_MATI, (order_id, terbaru["dibuat"])).fetchone() is not None


def _wajib_dapat_dibuka(kon, order_id, terbaru, kini):
    if st.receipt_order(kon, order_id) is not None:
        raise _tidak_dapat_dibuka()
    if kini < terbaru["kedaluwarsa"] and not _mati_teramati(kon, order_id, terbaru):
        raise _tidak_dapat_dibuka()
    if terbaru["urutan"] >= MAKS_JENDELA:
        raise PesananBatasJendela()
    if jumlah_aktif(kon, kini, kecuali=order_id) >= d.KUOTA_ORDER:
        raise d.PesananKuotaHabis()


def _validasi(order_id, akun_id, operasi_id, idem_baru, sekarang):
    try:
        d.periksa_order_id(order_id)
        d.periksa_akun_id(akun_id)
    except d.PesananDataTidakSah:
        raise d.PesananTidakDitemukan() from None
    d.periksa_operasi_id(operasi_id)
    kunci = None if idem_baru is None else periksa_kunci(idem_baru)
    return kunci, d.waktu_baku(sekarang)


def buka_jendela_ulang(kon, order_id, akun_id, sekarang, operasi_id, idem_baru=None):
    """Buka jendela bayar baru untuk order MILIK `akun_id` (atomik, idempoten per `operasi_id`).

    Urutan, semuanya dalam satu `BEGIN IMMEDIATE`: kepemilikan (selain pemilik ->
    PesananTidakDitemukan identik) -> replay `operasi_id` (jendela yang sama,
    `baru=False`) -> tanpa receipt dan (jendela terbaru sudah kedaluwarsa atau
    provider menyatakan expire/cancel/deny sesudahnya) selain itu PesananKonflik
    -> batas jumlah jendela (PesananBatasJendela) -> kuota tanpa menghitung order
    ini (PesananKuotaHabis). Gagal = tanpa tulis. `idem_baru` opsional (validasi
    format); bila None diturunkan deterministik dari (order_id, urutan).
    Mengembalikan dict jendela baru dengan kunci tambahan `baru`.
    """
    d.periksa_koneksi(kon)
    kunci, kini = _validasi(order_id, akun_id, operasi_id, idem_baru, sekarang)
    with d.tulis(kon):
        st.ambil_order(kon, order_id, akun_id)
        ulang = _replay(kon, order_id, operasi_id, kunci)
        if ulang is not None:
            return ulang
        terbaru = st.jendela_terbaru(kon, order_id)
        _wajib_dapat_dibuka(kon, order_id, terbaru, kini)
        urutan = terbaru["urutan"] + 1
        try:
            sisipkan_jendela(kon, order_id=order_id, urutan=urutan, operasi_id=operasi_id,
                             idempotency_key=kunci or kunci_ulang(order_id, urutan), dibuat=kini)
        except sqlite3.IntegrityError:
            raise d.PesananKonflik("jendela bentrok dengan catatan yang ada") from None
        return {**st.jendela_terbaru(kon, order_id), "order_id": order_id, "baru": True}
