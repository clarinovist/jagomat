"""Tagihan, bukti, dan pembacaan Paket Belajar 1 Bulan (Private, Mini Class); tanpa HTTP, jaringan, env, atau berkas.

Pemanggil (HTTP) menyuntik waktu, `akun_id` dan `siswa_id` DARI SESI (tidak pernah dari form; `siswa` ada di DB
belajar jadi store tidak dapat memeriksa keberadaannya) dan metadata bukti (isi berkas disimpan pemanggil lewat
`kelas_berkas`). Semua tulis dalam satu `BEGIN IMMEDIATE` (`pesanan_dasar.tulis`) di admin-control.db dan append-only
(`schema_kelas`). Nominal HANYA dari katalog dan ledger (`kelas_rincian`), kode unik dari server.

Kepemilikan: order selalu disaring `akun_id`; order akun lain berperilaku identik dengan tidak ada (bacaan order
-> PesananTidakDitemukan; bukti -> "tidak punya tagihan"), tanpa efek samping. Anak yang sudah punya order atas
nama akun lain diperlakukan seperti anak tak ada (PesananTidakDitemukan).

Status diturunkan (lihat `kelas_status`); satu anak punya SATU order terbuka per paket. Nominal tagihan =
rincian + kode unik 1..999, unik di antara tagihan yang masih dipegang (terbuka, atau lunas dalam
`HARI_TAHAN_KODE_LUNAS` hari). Rentang tiap nominal tidak beririsan dengan produk lain (dijaga tes katalog).
"""
from __future__ import annotations

from contextlib import contextmanager
import secrets
import sqlite3
from typing import List, Optional

import kelas_dasar as k
import kelas_rincian
import kelas_status as ks
from kelas_keluarga import tautkan_keluarga  # noqa: F401  (antarmuka admin)
import paket_belajar_katalog as katalog
import pesanan_dasar as d
import pesanan_transfer
import pesanan_transfer_baca as tb
import schema_kelas

fakta_order = ks.fakta_order
status_dari = ks.status_dari


@contextmanager
def buka(path, *, tulis_data=False):
    """Koneksi ke admin-control.db dengan ledger pesanan, transfer, DAN kelas yang sah (kelas belum dipasang -> galat)."""
    import admin_store_core
    with pesanan_transfer.buka(path, tulis_data=tulis_data) as kon:
        if not schema_kelas.validasi(kon):
            raise admin_store_core.StoreBelumSiap("kelas belum dipasang")
        yield kon


# --- bacaan -------------------------------------------------------------------------------

def _berakhir_order(kon, order_id: str) -> Optional[str]:
    baris = kon.execute("SELECT berakhir FROM kelas_akses WHERE order_id=?", (order_id,)).fetchone()
    return None if baris is None else baris["berakhir"]


def _tagihan_kelas(kon, order, fakta: ks.Fakta, status: str) -> katalog.TagihanKelas:
    tagihan = ks.baris_tagihan(kon, order["id"])
    aktif = status == k.STATUS_AKTIF
    return katalog.TagihanKelas(
        order["id"], order["paket"], ks.rincian_dari_baris(order["paket"], tagihan), tagihan["kode_unik"],
        tagihan["total_transfer"], status, None if aktif else order["kedaluwarsa"], fakta.jumlah_bukti,
        _berakhir_order(kon, order["id"]) if aktif else None)


def _wajib_anak_milik(kon, akun_id: str, siswa_id: int) -> None:
    if ks.akun_lain_punya_order(kon, akun_id, siswa_id):
        raise d.PesananTidakDitemukan()


def kartu_paket(kon, akun_id, siswa_id, sekarang) -> List[katalog.KartuPaket]:
    """Satu kartu per paket katalog untuk pembeli ini: rincian nominal (deposit/diskon) dan ada tidaknya tagihan terbuka.

    Bila paket itu sudah punya tagihan terbuka, rincian = rincian tersimpan di tagihan itu (yang akan ditagihkan);
    selain itu dihitung dari katalog dan ledger. SELECT saja. Anak yang order-nya milik akun lain -> PesananTidakDitemukan.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    k.periksa_siswa_id(siswa_id)
    kini = k.ke_baku(sekarang)
    _wajib_anak_milik(kon, akun_id, siswa_id)
    kartu = []
    for paket in katalog.DAFTAR_PAKET:
        ada = ks.order_terbuka(kon, akun_id, siswa_id, paket.kode, kini)
        if ada is not None:
            rincian = ks.rincian_dari_baris(paket.kode, ks.baris_tagihan(kon, ada[0]["id"]))
        else:
            rincian = kelas_rincian.rincian_untuk(kon, akun_id, siswa_id, paket.kode, kini)[0]
        kartu.append(katalog.KartuPaket(paket, rincian, ada is not None))
    return kartu


def tagihan_dari(kon, akun_id, order_id, sekarang) -> katalog.TagihanKelas:
    """Tagihan order milik akun ini; id salah, tak ada, dan milik akun lain -> PesananTidakDitemukan identik."""
    d.periksa_koneksi(kon)
    kini = k.ke_baku(sekarang)
    try:
        d.periksa_akun_id(akun_id)
        k.periksa_order_id(order_id)
    except d.PesananDataTidakSah:
        raise d.PesananTidakDitemukan() from None
    order = ks.baris_order_akun(kon, akun_id, order_id)
    if order is None:
        raise d.PesananTidakDitemukan()
    fakta = ks.fakta_order(kon, order_id)
    return _tagihan_kelas(kon, order, fakta, ks.status_dari(order, fakta, kini))


def tagihan_terbuka(kon, akun_id, siswa_id, kode_paket, sekarang) -> Optional[katalog.TagihanKelas]:
    """Tagihan terbuka akun ini untuk (anak, paket) untuk halaman pembeli, atau None (boleh membuat tagihan baru)."""
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    k.periksa_siswa_id(siswa_id)
    k.kode_paket_sah(kode_paket)
    kini = k.ke_baku(sekarang)
    ada = ks.order_terbuka(kon, akun_id, siswa_id, kode_paket, kini)
    return None if ada is None else _tagihan_kelas(kon, *ada)


def berakhir_aktif(kon, akun_id, siswa_id, kode_paket, sekarang) -> Optional[str]:
    """Akhir masa aktif paket (UTC naif baku) bila anak sedang aktif pada `sekarang`, selain itu None.

    Aktif = ada akses dengan mulai <= sekarang < berakhir untuk (anak, paket) atas nama akun ini. Nilainya akhir
    rantai: perpanjangan yang sudah disetujui tetapi belum mulai ikut dihitung.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    k.periksa_siswa_id(siswa_id)
    k.kode_paket_sah(kode_paket)
    kini = k.ke_baku(sekarang)
    dasar = ("FROM kelas_akses a JOIN kelas_order o ON o.id=a.order_id "
             "WHERE o.akun_id=? AND a.siswa_id=? AND o.paket=?")
    baris = kon.execute(
        "SELECT MAX(a.berakhir) " + dasar + " AND a.berakhir>? AND EXISTS(SELECT 1 " + dasar +
        " AND a.mulai<=? AND a.berakhir>?)",
        (akun_id, siswa_id, kode_paket, kini, akun_id, siswa_id, kode_paket, kini, kini)).fetchone()
    return baris[0]


def antrean(kon) -> List[katalog.ItemAntrean]:
    """Order menunggu verifikasi admin; bukti terakhir paling lama menunggu dulu."""
    d.periksa_koneksi(kon)
    baris = kon.execute(
        "SELECT o.id AS order_id,o.siswa_id,o.paket,t.total_transfer AS total,"
        "(SELECT MAX(b.diunggah) FROM kelas_bukti b WHERE b.order_id=o.id) AS bukti_terakhir "
        "FROM kelas_order o JOIN kelas_tagihan t ON t.order_id=o.id "
        "WHERE NOT %s AND %s ORDER BY bukti_terakhir,o.id" % (schema_kelas.SQL_SUDAH_LUNAS, schema_kelas.SQL_BELUM_DIPUTUSKAN))
    return [katalog.ItemAntrean(b["order_id"], b["siswa_id"], b["paket"], b["total"], b["bukti_terakhir"])
            for b in baris]


# --- tagihan ------------------------------------------------------------------------------

def _alokasi_kode(kon, nominal: int, kini: str, pilih) -> int:
    dipegang = ks.nominal_dipegang(kon, kini)
    bebas = [kode for kode in range(k.KODE_MIN, k.KODE_MAKS + 1) if nominal + kode not in dipegang]
    if not bebas:
        raise k.KodeUnikHabis()
    kode = pilih(bebas)
    if type(kode) is not int or kode not in bebas:
        raise d.PesananDataTidakSah("kode unik tidak sah")
    return kode


def _tulis_order(kon, akun_id, siswa_id, kode_paket, rincian, deposit_order, kode, kini) -> str:
    order_id = k.id_order_baru()
    try:
        kon.execute("INSERT INTO kelas_order(id,akun_id,siswa_id,paket,dibuat,kedaluwarsa) VALUES(?,?,?,?,?,?)",
                    (order_id, akun_id, siswa_id, kode_paket, kini, k.tambah_jam(kini, k.KEDALUWARSA_JAM)))
        kon.execute(
            "INSERT INTO kelas_tagihan(order_id,harga_dasar,potongan_deposit,potongan_diskon,deposit_order_id,"
            "nominal,kode_unik,total_transfer,dibuat) VALUES(?,?,?,?,?,?,?,?,?)",
            (order_id, rincian.harga_dasar, rincian.potongan_deposit, rincian.potongan_diskon, deposit_order,
             rincian.nominal, kode, rincian.nominal + kode, kini))
    except sqlite3.IntegrityError:
        raise k.KelasKonflik("tagihan bentrok dengan catatan yang ada") from None
    return order_id


def buat_tagihan(kon, akun_id, siswa_id, kode_paket, sekarang, *, acak=None,
                 tolak_paket_lain_terbuka=False) -> katalog.TagihanKelas:
    """Order + tagihan transfer paket untuk anak `siswa_id` atas nama `akun_id` (atomik, idempoten per paket terbuka).

    Nominal dihitung server: katalog + deposit Peta aktif + status anak kedua (`kelas_rincian`); tidak ada angka dari
    pemanggil. Paket asing -> PesananDataTidakSah. Anak yang sudah punya order atas nama akun lain ->
    PesananTidakDitemukan. Sudah ada tagihan terbuka untuk paket itu: dikembalikan apa adanya. Kode unik dari
    `secrets` (atau `acak(bebas)` suntikan tes); habis -> KodeUnikHabis. `tolak_paket_lain_terbuka` (jalur HTTP): bila
    paket LAIN masih terbuka untuk anak ini, KelasKonflik di transaksi yang sama (tidak ada balapan dua tab).
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    k.periksa_siswa_id(siswa_id)
    paket = k.kode_paket_sah(kode_paket)
    kini = k.ke_baku(sekarang)
    pilih = secrets.choice if acak is None else acak
    with d.tulis(kon):
        _wajib_anak_milik(kon, akun_id, siswa_id)
        ada = ks.order_terbuka(kon, akun_id, siswa_id, paket, kini)
        if ada is not None:
            return _tagihan_kelas(kon, *ada)
        if tolak_paket_lain_terbuka and any(True for _ in ks.order_terbuka_siswa(kon, akun_id, siswa_id, kini)):
            raise k.KelasKonflik("tagihan paket lain masih terbuka")
        rincian, deposit_order = kelas_rincian.rincian_untuk(kon, akun_id, siswa_id, paket, kini)
        kode = _alokasi_kode(kon, rincian.nominal, kini, pilih)
        order_id = _tulis_order(kon, akun_id, siswa_id, paket, rincian, deposit_order, kode, kini)
        order = ks.baris_order(kon, order_id)
        return _tagihan_kelas(kon, order, ks.fakta_order(kon, order_id), k.STATUS_BELUM_BAYAR)


# --- bukti --------------------------------------------------------------------------------

def _bukti_menunggu_sama(kon, order_id: str, sha256: str) -> Optional[int]:
    baris = kon.execute(
        "SELECT id FROM kelas_bukti WHERE order_id=? AND sha256=? AND id>COALESCE("
        "(SELECT MAX(bukti_hingga_id) FROM kelas_verifikasi WHERE order_id=?),0)",
        (order_id, sha256, order_id)).fetchone()
    return None if baris is None else baris["id"]


def _sha_sudah_dipakai(kon, sha256: str) -> bool:
    if kon.execute("SELECT 1 FROM kelas_bukti WHERE sha256=?", (sha256,)).fetchone() is not None:
        return True
    return tb.terpasang(kon) and kon.execute(
        "SELECT 1 FROM transfer_bukti WHERE sha256=?", (sha256,)).fetchone() is not None


def catat_bukti(kon, akun_id, siswa_id, kode_paket, mime, ukuran, sha256, nama_tersimpan, sekarang) -> dict:
    """Catat metadata satu bukti untuk tagihan terbuka akun ini untuk (anak, paket) (atomik).

    Order TIDAK dipilih klien: diturunkan dari akun, anak, dan paket sesi. Metadata diperiksa sebelum DB. Tanpa
    tagihan terbuka milik akun (termasuk milik akun lain) atau jendela sudah lewat -> KelasKonflik tanpa tulis;
    berkas yang sama (sha256) yang masih menunggu -> bukti yang ada (`baru=False`); berkas yang sudah pernah dipakai
    di bukti mana pun (kelas atau Peta) -> KelasKonflik; `MAKS_BUKTI` tercapai -> BatasBukti.
    Mengembalikan {bukti_id, status, baru}.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    k.periksa_siswa_id(siswa_id)
    paket = k.kode_paket_sah(kode_paket)
    k.periksa_meta_bukti(mime, ukuran, sha256, nama_tersimpan)
    kini = k.ke_baku(sekarang)
    with d.tulis(kon):
        ada = ks.order_terbuka(kon, akun_id, siswa_id, paket, kini)
        if ada is None or kini >= ada[0]["kedaluwarsa"]:
            raise k.KelasKonflik("anak tidak punya tagihan paket yang menerima bukti")
        order, fakta, status = ada
        sama = _bukti_menunggu_sama(kon, order["id"], sha256)
        if sama is not None:
            return {"bukti_id": sama, "status": status, "baru": False}
        if _sha_sudah_dipakai(kon, sha256):
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
