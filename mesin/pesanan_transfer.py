"""Logika inti pembayaran transfer rekening (verifikasi manual admin) untuk pesanan.

Tanpa HTTP, jaringan, env, atau berkas: pemanggil menyuntik waktu, id akun/admin, dan
metadata bukti (isi berkas disimpan pemanggil di luar DB). Semua tulis lewat
`pesanan_dasar.tulis` (`BEGIN IMMEDIATE`), append-only (`schema_transfer`), tanpa
menyentuh `pesanan_receipt`/`pesanan_pengamatan` dan jalur Midtrans.

Aturan jendela bayar (24 jam, `pesanan_jendela`):

* Tagihan (kode unik + nominal) dibuat PER JENDELA; jendela yang dibuka ulang lewat
  `buka_jendela_ulang` memerlukan tagihan baru.
* Bukti hanya diterima saat jendela terbaru terbuka (dijaga juga trigger DB).
* Order dengan bukti belum diputuskan berstatus `menunggu_verifikasi` dan TIDAK
  kedaluwarsa; admin tetap dapat setuju/tolak sesudah jendela lewat. Nominalnya tetap
  dipegang selama menunggu.
* `ditolak` berlaku selama jendela terbuka (boleh unggah ulang); sesudahnya menjadi
  `kedaluwarsa` dan order dibuka ulang lewat jendela baru.
* Nominal (49.000 + kode 1..999) unik di antara tagihan jendela-terbaru yang masih
  dipegang: belum lunas dan (jendela terbuka atau menunggu verifikasi).
"""
from __future__ import annotations

from contextlib import contextmanager
import re
import secrets
import sqlite3
import unicodedata

import pesanan_dasar as d
import pesanan_status as st
import pesanan_transfer_baca as tb
from schema_pesanan import CATATAN_REFUND
from schema_transfer import (BATAS_ALASAN, BATAS_UKURAN_BUKTI, KODE_MAKS, KODE_MIN, MAKS_BUKTI,
                             MIME_BUKTI)

HARI_RETENSI_BUKTI = 30
JAM_PER_HARI = 24
KEPUTUSAN_SETUJU = "setuju"
KEPUTUSAN_TOLAK = "tolak"

_POLA_NAMA_BERKAS = re.compile(r"[0-9a-f]{32}")
_POLA_SHA256 = re.compile(r"[0-9a-f]{64}")
_STATUS_TERIMA_BUKTI = (d.STATUS_BELUM_BAYAR, d.STATUS_DITOLAK, d.STATUS_MENUNGGU_VERIFIKASI)
_KOLOM_TAGIHAN = ("order_id", "urutan", "kode_unik", "nominal_transfer", "dibuat")
_KOLOM_BUKTI = ("id", "urutan", "berkas", "mime", "ukuran", "sha256", "diunggah")
_SQL_BUKTI_BARU = ("id>COALESCE((SELECT MAX(bukti_hingga_id) FROM transfer_verifikasi "
                   "WHERE order_id=?),0)")


class PesananKodeUnikHabis(d.PesananKonflik):
    def __init__(self):
        super().__init__("kode unik transfer habis")


class PesananBatasBukti(d.PesananKonflik):
    def __init__(self):
        super().__init__("batas bukti transfer tercapai")


@contextmanager
def buka(path, *, tulis_data=False):
    """Koneksi ke DB admin dengan ledger pesanan DAN namespace transfer yang sah."""
    import admin_store_core
    import schema_transfer
    with d.buka(path, tulis_data=tulis_data) as kon:
        if not schema_transfer.validasi(kon):
            raise admin_store_core.StoreBelumSiap("transfer belum dipasang")
        yield kon


# --- tagihan ----------------------------------------------------------------

def _tagihan(kon, order_id, urutan):
    baris = kon.execute(
        "SELECT %s FROM transfer_tagihan WHERE order_id=? AND urutan=?" % ",".join(_KOLOM_TAGIHAN),
        (order_id, urutan)).fetchone()
    return None if baris is None else {k: baris[k] for k in _KOLOM_TAGIHAN}


def _nominal_dipegang(kon, kini):
    """Nominal tagihan jendela-terbaru yang belum lunas dan (jendela terbuka / menunggu)."""
    fakta = tb.sql_fakta(kon)
    baris = kon.execute(
        """SELECT t.nominal_transfer FROM transfer_tagihan t
           JOIN pesanan_order o ON o.order_id=t.order_id
           WHERE t.urutan=(SELECT MAX(j.urutan) FROM pesanan_jendela j WHERE j.order_id=t.order_id)
             AND NOT %s AND (%s>? OR %s)""" % (fakta["lunas"], st.SQL_KEDALUWARSA_TERBARU,
                                               fakta["menunggu"]), (kini,))
    return {b[0] for b in baris}


def _alokasi_kode(kon, order, kini, pilih):
    dipegang = _nominal_dipegang(kon, kini)
    bebas = [k for k in range(KODE_MIN, KODE_MAKS + 1) if order["rupiah"] + k not in dipegang]
    if not bebas:
        raise PesananKodeUnikHabis()
    kode = pilih(bebas)
    if type(kode) is not int or kode not in bebas:
        raise d.PesananDataTidakSah("kode unik tidak sah")
    return kode


def buat_tagihan_transfer(kon, order_id, akun_id, sekarang, *, acak=None):
    """Tagihan transfer jendela bayar terbaru order MILIK `akun_id` (atomik, idempoten).

    Nominal = `RUPIAH_PAKET` + kode unik 1..999 dari `secrets` (atau `acak(bebas)` yang
    disuntik tes), dipilih dari kode yang belum dipegang tagihan lain; kosong ->
    PesananKodeUnikHabis. Tagihan jendela ini sudah ada -> dikembalikan (`baru=False`).
    Order bukan milik akun / tak dikenal -> PesananTidakDitemukan identik; status selain
    `belum_bayar` (lunas, kedaluwarsa, menunggu, ...) -> PesananKonflik. Mengembalikan dict
    {order_id, urutan, kode_unik, nominal_transfer, dibuat, baru}.
    """
    d.periksa_koneksi(kon)
    kini = d.waktu_baku(sekarang)
    pilih = secrets.choice if acak is None else acak
    with d.tulis(kon):
        order = st.ambil_order(kon, order_id, akun_id)
        urutan = st.jendela_terbaru(kon, order_id)["urutan"]
        ada = _tagihan(kon, order_id, urutan)
        if ada is not None:
            return {**ada, "baru": False}
        if st.status_dari_db(kon, order, kini) != d.STATUS_BELUM_BAYAR:
            raise d.PesananKonflik("pesanan tidak dapat ditagih lewat transfer")
        kode = _alokasi_kode(kon, order, kini, pilih)
        try:
            kon.execute("INSERT INTO transfer_tagihan(order_id,urutan,kode_unik,nominal_transfer,"
                        "dibuat) VALUES(?,?,?,?,?)",
                        (order_id, urutan, kode, order["rupiah"] + kode, kini))
        except sqlite3.IntegrityError:
            raise d.PesananKonflik("tagihan bentrok dengan catatan yang ada") from None
        return {**_tagihan(kon, order_id, urutan), "baru": True}


def ambil_tagihan(kon, order_id, akun_id):
    """Tagihan jendela terbaru order milik akun (dict) atau None bila belum dibuat."""
    d.periksa_koneksi(kon)
    order = st.ambil_order(kon, order_id, akun_id)
    return _tagihan(kon, order["order_id"], st.jendela_terbaru(kon, order_id)["urutan"])


# --- bukti ------------------------------------------------------------------

def _meta_bukti(mime, ukuran, sha256, nama_tersimpan):
    if type(mime) is not str or mime not in MIME_BUKTI:
        raise d.PesananDataTidakSah("mime bukti tidak sah")
    if type(ukuran) is not int or not 1 <= ukuran <= BATAS_UKURAN_BUKTI:
        raise d.PesananDataTidakSah("ukuran bukti tidak sah")
    if type(sha256) is not str or _POLA_SHA256.fullmatch(sha256) is None:
        raise d.PesananDataTidakSah("sha256 bukti tidak sah")
    if type(nama_tersimpan) is not str or _POLA_NAMA_BERKAS.fullmatch(nama_tersimpan) is None:
        raise d.PesananDataTidakSah("nama berkas bukti tidak sah")


def _wajib_terima_bukti(kon, order, jendela, kini):
    status = st.status_dari_db(kon, order, kini)
    if status not in _STATUS_TERIMA_BUKTI or kini >= jendela["kedaluwarsa"]:
        raise d.PesananKonflik("pesanan tidak menerima bukti transfer")
    if _tagihan(kon, order["order_id"], jendela["urutan"]) is None:
        raise d.PesananKonflik("tagihan transfer belum dibuat")
    return status


def _bukti_menunggu_sama(kon, order_id, sha256):
    baris = kon.execute("SELECT id FROM transfer_bukti WHERE order_id=? AND sha256=? AND "
                        + _SQL_BUKTI_BARU, (order_id, sha256, order_id)).fetchone()
    return None if baris is None else baris["id"]


def catat_bukti(kon, order_id, akun_id, mime, ukuran, sha256, nama_tersimpan, sekarang):
    """Catat metadata satu bukti transfer milik `akun_id` (atomik).

    `nama_tersimpan` = nama berkas acak (32 hex) yang dibuat pemanggil, bukan nama asli.
    Input diperiksa sebelum DB; order bukan milik akun -> PesananTidakDitemukan tanpa tulis.
    Prasyarat: tagihan jendela terbaru ada, jendela masih terbuka, status belum_bayar/
    ditolak/menunggu_verifikasi, kurang dari `MAKS_BUKTI` bukti (PesananBatasBukti).
    Berkas sama (sha256) yang masih menunggu -> bukti yang ada (`baru=False`).
    Mengembalikan {bukti_id, status, baru}.
    """
    d.periksa_koneksi(kon)
    _meta_bukti(mime, ukuran, sha256, nama_tersimpan)
    kini = d.waktu_baku(sekarang)
    with d.tulis(kon):
        order = st.ambil_order(kon, order_id, akun_id)
        jendela = st.jendela_terbaru(kon, order_id)
        status = _wajib_terima_bukti(kon, order, jendela, kini)
        ada = _bukti_menunggu_sama(kon, order_id, sha256)
        if ada is not None:
            return {"bukti_id": ada, "status": status, "baru": False}
        jumlah = kon.execute("SELECT COUNT(*) FROM transfer_bukti WHERE order_id=?",
                             (order_id,)).fetchone()[0]
        if jumlah >= MAKS_BUKTI:
            raise PesananBatasBukti()
        try:
            kursor = kon.execute(
                "INSERT INTO transfer_bukti(order_id,urutan,berkas,mime,ukuran,sha256,"
                "diunggah_oleh,diunggah) VALUES(?,?,?,?,?,?,?,?)",
                (order_id, jendela["urutan"], nama_tersimpan, mime, ukuran, sha256, akun_id, kini))
        except sqlite3.IntegrityError:
            raise d.PesananKonflik("bukti bentrok dengan catatan yang ada") from None
        return {"bukti_id": kursor.lastrowid, "status": st.status_dari_db(kon, order, kini),
                "baru": True}


def bukti_menunggu(kon, order_id):
    """Bukti yang belum diputuskan admin (tuple dict baru, urut id) untuk tampilan admin."""
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    baris = kon.execute("SELECT %s FROM transfer_bukti WHERE order_id=? AND %s ORDER BY id"
                        % (",".join(_KOLOM_BUKTI), _SQL_BUKTI_BARU), (order_id, order_id))
    return tuple({k: b[k] for k in _KOLOM_BUKTI} for b in baris)


# --- keputusan admin ----------------------------------------------------------

def _alasan_sah(alasan):
    if type(alasan) is not str:
        raise d.PesananDataTidakSah("alasan penolakan wajib diisi")
    bersih = alasan.strip()
    if not 1 <= len(bersih) <= BATAS_ALASAN:
        raise d.PesananDataTidakSah("alasan penolakan tidak sah")
    if any(unicodedata.category(c).startswith("C") for c in bersih):
        raise d.PesananDataTidakSah("alasan penolakan tidak sah")
    return bersih


def _bukti_terakhir(kon, order_id):
    baris = kon.execute("SELECT id,urutan FROM transfer_bukti WHERE order_id=? "
                        "ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    if baris is None:
        raise d.PesananKonflik("pesanan tidak menunggu verifikasi")
    return baris["id"], baris["urutan"]


def _tulis_putusan(kon, order, admin_id, keputusan, alasan, kini, bukti_terakhir_id):
    order_id = order["order_id"]
    hingga, urutan = _bukti_terakhir(kon, order_id)
    if bukti_terakhir_id is not None and bukti_terakhir_id != hingga:
        raise d.PesananKonflik("bukti berubah sejak dilihat admin")
    try:
        kursor = kon.execute(
            "INSERT INTO transfer_verifikasi(order_id,urutan,keputusan,admin_id,alasan,"
            "bukti_hingga_id,dibuat) VALUES(?,?,?,?,?,?,?)",
            (order_id, urutan, keputusan, admin_id, alasan, hingga, kini))
        if keputusan == KEPUTUSAN_SETUJU:
            kon.execute("INSERT INTO transfer_lunas(order_id,verifikasi_id,rupiah,dibuat) "
                        "VALUES(?,?,?,?)", (order_id, kursor.lastrowid, order["rupiah"], kini))
    except sqlite3.IntegrityError:
        raise d.PesananKonflik("keputusan bentrok dengan catatan yang ada") from None
    return kursor.lastrowid


def _putuskan(kon, order_id, admin_id, keputusan, alasan, sekarang, bukti_terakhir_id=None):
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    d.periksa_pelaku(admin_id)
    kini = d.waktu_baku(sekarang)
    with d.tulis(kon):
        baris = st.baris_order(kon, order_id)
        if baris is None:
            raise d.PesananTidakDitemukan()
        order = st.dict_order(baris)
        if st.status_dari_db(kon, order, kini) != d.STATUS_MENUNGGU_VERIFIKASI:
            raise d.PesananKonflik("pesanan tidak menunggu verifikasi")
        putusan_id = _tulis_putusan(kon, order, admin_id, keputusan, alasan, kini, bukti_terakhir_id)
        return {"status": st.status_dari_db(kon, order, kini), "verifikasi_id": putusan_id}


def setujui(kon, order_id, admin_id, sekarang, *, bukti_terakhir_id=None):
    """Admin menyetujui bukti: tulis verifikasi 'setuju' + `transfer_lunas` (satu transaksi).

    `bukti_terakhir_id` opsional = id bukti terbaru yang DILIHAT admin; bila ada bukti yang lebih
    baru masuk sesudahnya -> PesananKonflik tanpa tulis (admin tidak menyetujui bukti yang belum ia lihat).

    Hanya untuk status `menunggu_verifikasi` (ada bukti belum diputuskan; sah walau
    jendela bayar sudah lewat). Setuju dua kali, tanpa bukti, atau order sudah lunas
    lewat jalur lain -> PesananKonflik; order tak dikenal -> PesananTidakDitemukan.
    Mengembalikan {status, verifikasi_id}.
    """
    return _putuskan(kon, order_id, admin_id, KEPUTUSAN_SETUJU, None, sekarang, bukti_terakhir_id)


def tolak(kon, order_id, admin_id, alasan, sekarang, *, bukti_terakhir_id=None):
    """Admin menolak bukti dengan `alasan` wajib (1..BATAS_ALASAN, tanpa karakter kontrol).

    Status menjadi `ditolak` (boleh unggah ulang selama jendela terbuka). Syarat status
    sama dengan :func:`setujui` (termasuk `bukti_terakhir_id`). Mengembalikan {status, verifikasi_id}.
    """
    return _putuskan(kon, order_id, admin_id, KEPUTUSAN_TOLAK, _alasan_sah(alasan), sekarang,
                     bukti_terakhir_id)


# --- refund -------------------------------------------------------------------

def tulis_refund_transfer(kon, operasi_id, isi, kini):
    """Tulis refund untuk order lunas-transfer di dalam transaksi pemanggil.

    `isi` = (order_id, dicatat_oleh, catatan_kode). Idempoten per `operasi_id`
    (replay identik False, isi beda PesananKonflik); satu refund per order.
    Mengembalikan True bila baris baru.
    """
    if not tb.terpasang(kon):
        raise d.PesananKonflik("order belum punya receipt")
    lama = kon.execute("SELECT order_id,dicatat_oleh,catatan_kode FROM transfer_refund "
                       "WHERE operasi_id=?", (operasi_id,)).fetchone()
    if lama is not None:
        if tuple(lama) != isi:
            raise d.PesananKonflik("operasi refund sama dengan isi berbeda")
        return False
    order_id = isi[0]
    if kon.execute("SELECT 1 FROM transfer_lunas WHERE order_id=?", (order_id,)).fetchone() is None:
        raise d.PesananKonflik("order belum punya receipt")
    if kon.execute("SELECT 1 FROM transfer_refund WHERE order_id=?", (order_id,)).fetchone():
        raise d.PesananKonflik("order sudah punya catatan refund")
    kon.execute("INSERT INTO transfer_refund(operasi_id,order_id,dicatat_oleh,catatan_kode,dibuat) "
                "VALUES(?,?,?,?,?)", (operasi_id,) + isi + (kini,))
    return True


def catat_refund_transfer(kon, order_id, operasi_id, dicatat_oleh, catatan_kode, sekarang):
    """Refund manual order lunas-transfer (transaksi sendiri); {status, baru}."""
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    d.periksa_operasi_id(operasi_id)
    d.periksa_pelaku(dicatat_oleh)
    if catatan_kode not in CATATAN_REFUND:
        raise d.PesananDataTidakSah("catatan_kode tidak sah")
    kini = d.waktu_baku(sekarang)
    with d.tulis(kon):
        baris = st.baris_order(kon, order_id)
        if baris is None:
            raise d.PesananTidakDitemukan()
        baru = tulis_refund_transfer(kon, operasi_id, (order_id, dicatat_oleh, catatan_kode), kini)
        return {"status": st.status_dari_db(kon, st.dict_order(baris), kini), "baru": baru}


# --- retensi bukti ------------------------------------------------------------

def _batas_retensi(sekarang, hari):
    if type(hari) is not int or hari < 1:
        raise d.PesananDataTidakSah("hari retensi tidak sah")
    return d.tambah_jam(d.waktu_baku(sekarang), -JAM_PER_HARI * hari)


def _pilih_kedaluwarsa(kon, batas, bukti_id=None):
    """Bukti yang sudah diputuskan sejak `batas` atau lebih lama dan belum bertanda hapus."""
    filter_id = "" if bukti_id is None else " AND b.id=%d" % bukti_id
    baris = kon.execute(
        """SELECT b.id,b.order_id,b.berkas FROM transfer_bukti b
           WHERE NOT EXISTS(SELECT 1 FROM transfer_bukti_hapus h WHERE h.bukti_id=b.id)
             AND EXISTS(SELECT 1 FROM transfer_verifikasi v WHERE v.order_id=b.order_id
                        AND v.bukti_hingga_id>=b.id AND v.dibuat<=?)%s ORDER BY b.id""" % filter_id,
        (batas,))
    return tuple({"bukti_id": b["id"], "order_id": b["order_id"], "berkas": b["berkas"]}
                 for b in baris)


def bukti_kedaluwarsa(kon, sekarang, hari=HARI_RETENSI_BUKTI):
    """Bukti yang keputusannya sudah >= `hari` hari lalu dan belum ditandai terhapus.

    Tuple dict {bukti_id, order_id, berkas}. Bukti yang belum diputuskan tidak pernah
    kedaluwarsa. Hanya SELECT: pemanggil menghapus berkas fisik lalu memanggil
    :func:`tandai_dihapus`.
    """
    d.periksa_koneksi(kon)
    return _pilih_kedaluwarsa(kon, _batas_retensi(sekarang, hari))


def tandai_dihapus(kon, bukti_id, sekarang, hari=HARI_RETENSI_BUKTI):
    """Tandai satu bukti terhapus (INSERT `transfer_bukti_hapus`; metadata bukti tetap).

    Idempoten (`baru=False` bila sudah ditandai). Bukti yang belum diputuskan atau belum
    berumur `hari` hari sejak keputusan -> PesananKonflik; id tak dikenal ->
    PesananTidakDitemukan. Mengembalikan {bukti_id, berkas, baru}.
    """
    d.periksa_koneksi(kon)
    d.periksa_bilangan(bukti_id, "bukti_id")
    batas = _batas_retensi(sekarang, hari)
    kini = d.waktu_baku(sekarang)
    with d.tulis(kon):
        bukti = kon.execute("SELECT berkas FROM transfer_bukti WHERE id=?", (bukti_id,)).fetchone()
        if bukti is None:
            raise d.PesananTidakDitemukan()
        hasil = {"bukti_id": bukti_id, "berkas": bukti["berkas"]}
        if kon.execute("SELECT 1 FROM transfer_bukti_hapus WHERE bukti_id=?",
                       (bukti_id,)).fetchone():
            return {**hasil, "baru": False}
        if not _pilih_kedaluwarsa(kon, batas, bukti_id):
            raise d.PesananKonflik("bukti belum kedaluwarsa")
        kon.execute("INSERT INTO transfer_bukti_hapus(bukti_id,dihapus) VALUES(?,?)",
                    (bukti_id, kini))
        return {**hasil, "baru": True}
