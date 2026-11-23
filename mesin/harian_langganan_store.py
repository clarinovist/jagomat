"""Logika inti tagihan dan bukti transfer langganan Latihan Harian (tanpa HTTP, jaringan, env, atau berkas).

Pemanggil menyuntik waktu dan metadata bukti (isi berkas disimpan pemanggil di folder khusus). Semua tulis dalam
satu `BEGIN IMMEDIATE` (`pesanan_dasar.tulis`) dan append-only (`schema_harian_langganan`). `siswa_id` selalu
argumen server (dari sesi), tidak pernah dari form. Status diturunkan:

* `belum_bayar`  jendela bayar (24 jam) terbuka, belum ada bukti yang menunggu;
* `menunggu_verifikasi`  ada bukti belum diputuskan; TIDAK kedaluwarsa, admin tetap dapat memutuskan;
* `ditolak`  keputusan terakhir menolak dan jendela masih terbuka (boleh unggah ulang);
* `kedaluwarsa`  jendela lewat tanpa bukti menunggu; anak boleh membuat tagihan baru;
* `aktif`  ada keputusan setuju (akses ada di `harian_akses`).

Satu anak hanya punya SATU order terbuka (belum_bayar, menunggu_verifikasi, atau ditolak) pada satu waktu; DB
juga menegakkannya. Nominal = harga paket + kode unik 1..999, unik di antara tagihan yang masih dipegang
(terbuka, atau lunas dalam `HARI_TAHAN_KODE_LUNAS` hari). Rentang tiap paket tidak beririsan dengan Paket Coba.
"""
from __future__ import annotations

from dataclasses import dataclass
import secrets
import sqlite3
from typing import Optional

import harian_langganan_dasar as h
import pesanan_dasar as d
import schema_harian_langganan as sk

_KOLOM_ORDER = "id,siswa_id,paket,rupiah,dibuat,kedaluwarsa"


@dataclass(frozen=True)
class Fakta:
    lunas: bool
    putusan_terakhir: Optional[str]
    alasan: Optional[str]
    bukti_terakhir_id: Optional[int]
    jumlah_bukti: int
    menunggu: bool


@dataclass(frozen=True)
class Tampilan:
    order_id: str
    paket: h.Paket
    kode_unik: int
    nominal: int
    kedaluwarsa: str
    status: str
    alasan_tolak: Optional[str]
    jumlah_bukti: int
    boleh_unggah: bool


def fakta_order(kon, order_id: str) -> Fakta:
    lunas = kon.execute("SELECT 1 FROM harian_verifikasi WHERE order_id=? AND keputusan='setuju'",
                        (order_id,)).fetchone() is not None
    putusan = kon.execute("SELECT keputusan,alasan,bukti_hingga_id FROM harian_verifikasi WHERE order_id=? "
                          "ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    bukti = kon.execute("SELECT MAX(id),COUNT(*) FROM harian_bukti WHERE order_id=?", (order_id,)).fetchone()
    terakhir, jumlah = bukti[0], bukti[1]
    menunggu = terakhir is not None and (putusan is None or terakhir > putusan["bukti_hingga_id"])
    return Fakta(lunas, None if putusan is None else putusan["keputusan"],
                 None if putusan is None else putusan["alasan"], terakhir, jumlah, menunggu)


def status_dari(order, fakta: Fakta, kini: str) -> str:
    if fakta.lunas:
        return h.STATUS_AKTIF
    if fakta.menunggu:
        return h.STATUS_MENUNGGU
    if kini >= order["kedaluwarsa"]:
        return h.STATUS_KEDALUWARSA
    return h.STATUS_DITOLAK if fakta.putusan_terakhir == h.KEPUTUSAN_TOLAK else h.STATUS_BELUM_BAYAR


def _order_terbuka(kon, siswa_id: int, kini: str):
    """(baris order, fakta, status) milik anak yang masih terbuka, atau None."""
    for order in kon.execute("SELECT %s FROM harian_order WHERE siswa_id=? ORDER BY dibuat DESC,id DESC"
                             % _KOLOM_ORDER, (siswa_id,)).fetchall():
        fakta = fakta_order(kon, order["id"])
        status = status_dari(order, fakta, kini)
        if status in h.STATUS_TERBUKA:
            return order, fakta, status
    return None


def _tagihan(kon, order_id: str):
    return kon.execute("SELECT kode_unik,nominal_transfer FROM harian_tagihan WHERE order_id=?",
                       (order_id,)).fetchone()


def _tampilan(kon, order, fakta: Fakta, status: str, kini: str) -> Tampilan:
    tagihan = _tagihan(kon, order["id"])
    terbuka = status in h.STATUS_TERBUKA and kini < order["kedaluwarsa"] and fakta.jumlah_bukti < h.MAKS_BUKTI
    return Tampilan(order["id"], h.PAKET[order["paket"]], tagihan["kode_unik"], tagihan["nominal_transfer"],
                    order["kedaluwarsa"], status,
                    fakta.alasan if status == h.STATUS_DITOLAK else None, fakta.jumlah_bukti, terbuka)


def tampilan_terbuka(kon, siswa_id: int, sekarang) -> Optional[Tampilan]:
    """Tagihan terbuka anak ini untuk halaman murid, atau None (boleh membuat tagihan baru)."""
    d.periksa_koneksi(kon)
    h.periksa_siswa_id(siswa_id)
    kini = h.ke_baku(sekarang)
    ada = _order_terbuka(kon, siswa_id, kini)
    return None if ada is None else _tampilan(kon, ada[0], ada[1], ada[2], kini)


# --- tagihan ----------------------------------------------------------------

def _nominal_dipegang(kon, kini: str) -> set:
    """Nominal tagihan yang masih dipegang: terbuka, atau lunas dalam `HARI_TAHAN_KODE_LUNAS` hari."""
    baris = kon.execute(
        "SELECT t.nominal_transfer FROM harian_tagihan t JOIN harian_order o ON o.id=t.order_id "
        "WHERE (NOT %s AND (o.kedaluwarsa>? OR %s)) OR EXISTS(SELECT 1 FROM harian_verifikasi v "
        "WHERE v.order_id=o.id AND v.keputusan='setuju' AND v.dibuat>?)"
        % (sk.SQL_SUDAH_LUNAS, sk.SQL_BELUM_DIPUTUSKAN),
        (kini, h.batas_hari_lalu(kini, h.HARI_TAHAN_KODE_LUNAS)))
    return {b[0] for b in baris}


def _alokasi_kode(kon, paket: h.Paket, kini: str, pilih) -> int:
    dipegang = _nominal_dipegang(kon, kini)
    bebas = [k for k in range(h.KODE_MIN, h.KODE_MAKS + 1) if paket.rupiah + k not in dipegang]
    if not bebas:
        raise h.KodeUnikHabis()
    kode = pilih(bebas)
    if type(kode) is not int or kode not in bebas:
        raise d.PesananDataTidakSah("kode unik tidak sah")
    return kode


def _wajib_anak_ada(kon, siswa_id: int) -> None:
    if kon.execute("SELECT 1 FROM siswa WHERE id=?", (siswa_id,)).fetchone() is None:
        raise d.PesananTidakDitemukan()


def buat_tagihan(kon, siswa_id: int, paket, sekarang, *, acak=None) -> dict:
    """Order + tagihan transfer untuk anak `siswa_id` (atomik, idempoten per paket).

    Nominal dari konstanta paket + kode unik server (`secrets` atau `acak(bebas)` suntikan tes). Paket asing ->
    PesananDataTidakSah. Anak tak ada -> PesananTidakDitemukan. Anak sudah punya order terbuka: paket sama
    dikembalikan (`baru=False`), paket lain -> LanggananKonflik tanpa tulis. Kode unik habis -> KodeUnikHabis.
    Mengembalikan {order_id, paket, kode_unik, nominal_transfer, dibuat, kedaluwarsa, baru}.
    """
    d.periksa_koneksi(kon)
    h.periksa_siswa_id(siswa_id)
    pilih_paket = h.paket_sah(paket)
    kini = h.ke_baku(sekarang)
    pilih = secrets.choice if acak is None else acak
    with d.tulis(kon):
        _wajib_anak_ada(kon, siswa_id)
        ada = _order_terbuka(kon, siswa_id, kini)
        if ada is not None:
            if ada[0]["paket"] != pilih_paket.kode:
                raise h.LanggananKonflik("anak sudah punya tagihan langganan lain yang berjalan")
            return {**_hasil(kon, ada[0]), "baru": False}
        kode = _alokasi_kode(kon, pilih_paket, kini, pilih)
        order_id = h.id_order_baru()
        kedaluwarsa = h.tambah_jam(kini, h.KEDALUWARSA_JAM)
        try:
            kon.execute("INSERT INTO harian_order(id,siswa_id,paket,rupiah,dibuat,kedaluwarsa) VALUES(?,?,?,?,?,?)",
                        (order_id, siswa_id, pilih_paket.kode, pilih_paket.rupiah, kini, kedaluwarsa))
            kon.execute("INSERT INTO harian_tagihan(order_id,kode_unik,nominal_transfer,dibuat) VALUES(?,?,?,?)",
                        (order_id, kode, pilih_paket.rupiah + kode, kini))
        except sqlite3.IntegrityError:
            raise h.LanggananKonflik("tagihan bentrok dengan catatan yang ada") from None
        order = kon.execute("SELECT %s FROM harian_order WHERE id=?" % _KOLOM_ORDER, (order_id,)).fetchone()
        return {**_hasil(kon, order), "baru": True}


def _hasil(kon, order) -> dict:
    tagihan = _tagihan(kon, order["id"])
    return {"order_id": order["id"], "paket": order["paket"], "kode_unik": tagihan["kode_unik"],
            "nominal_transfer": tagihan["nominal_transfer"], "dibuat": order["dibuat"],
            "kedaluwarsa": order["kedaluwarsa"]}


# --- bukti ------------------------------------------------------------------

def _bukti_menunggu_sama(kon, order_id: str, sha256: str) -> Optional[int]:
    baris = kon.execute(
        "SELECT id FROM harian_bukti WHERE order_id=? AND sha256=? AND id>COALESCE("
        "(SELECT MAX(bukti_hingga_id) FROM harian_verifikasi WHERE order_id=?),0)",
        (order_id, sha256, order_id)).fetchone()
    return None if baris is None else baris["id"]


def catat_bukti(kon, siswa_id: int, mime, ukuran, sha256, nama_tersimpan, sekarang) -> dict:
    """Catat metadata satu bukti untuk order terbuka milik anak `siswa_id` (atomik).

    Order TIDAK dipilih klien: diturunkan dari anak sesi. Metadata diperiksa sebelum DB. Tanpa order terbuka
    atau jendela sudah lewat -> LanggananKonflik; `MAKS_BUKTI` tercapai -> BatasBukti; berkas sama (sha256)
    yang masih menunggu -> bukti yang ada (`baru=False`). Mengembalikan {bukti_id, status, baru}.
    """
    d.periksa_koneksi(kon)
    h.periksa_siswa_id(siswa_id)
    h.periksa_meta_bukti(mime, ukuran, sha256, nama_tersimpan)
    kini = h.ke_baku(sekarang)
    with d.tulis(kon):
        ada = _order_terbuka(kon, siswa_id, kini)
        if ada is None or kini >= ada[0]["kedaluwarsa"]:
            raise h.LanggananKonflik("anak tidak punya tagihan langganan yang menerima bukti")
        order, fakta, status = ada
        sama = _bukti_menunggu_sama(kon, order["id"], sha256)
        if sama is not None:
            return {"bukti_id": sama, "status": status, "baru": False}
        if fakta.jumlah_bukti >= h.MAKS_BUKTI:
            raise h.BatasBukti()
        try:
            kursor = kon.execute(
                "INSERT INTO harian_bukti(order_id,berkas,mime,ukuran,sha256,diunggah) VALUES(?,?,?,?,?,?)",
                (order["id"], nama_tersimpan, mime, ukuran, sha256, kini))
        except sqlite3.IntegrityError:
            raise h.LanggananKonflik("bukti bentrok dengan catatan yang ada") from None
        return {"bukti_id": kursor.lastrowid, "status": h.STATUS_MENUNGGU, "baru": True}
