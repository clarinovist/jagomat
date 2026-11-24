"""Domain purna: voucher (deposit Rp49.000) pemakaian dan janji terbit laporan untuk order Paket Coba lunas.

Domain murni di koneksi DB admin-control (seperti `pesanan_admin`): tanpa HTTP, tanpa env, tanpa jaringan.
Termasuk domain pesanan: hanya boleh mengimpor `pesanan_*` dan `schema_purna` (tidak boleh mengimpor admin,
HTTP, atau halaman). Waktu disuntik pemanggil dan dinormalkan lewat `pesanan_dasar.waktu_baku`.

Voucher, janji terbit, dan kedaluwarsa DITURUNKAN saat dibaca (tidak disimpan); yang disimpan hanya tindakan
manusia di namespace `purna_*` (lihat `schema_purna`). Lunas dan refund dibaca dari KEDUA ledger (QRIS:
`pesanan_receipt`/`pesanan_refund`; transfer: `transfer_lunas`/`transfer_refund`) lewat fungsi turunan yang
sudah ada (`pesanan_status`, `pesanan_transfer_baca`), bukan salinan logikanya.

Bila `purna_*` BELUM dimigrasikan: fungsi baca mengembalikan keadaan netral (tanpa pemakaian dan laporan
terbit) dan fungsi tulis menolak dengan PesananKonflik "belum dipasang".

Kepemilikan order oleh akun pembeli TIDAK ditegakkan di sini: modul ini bekerja pada `order_id`. Pemanggil HTTP
(pembeli) wajib memastikan order milik akun sesi (`pesanan_status.ambil_order`, 404 identik) sebelum membaca
keadaan untuk ditampilkan.

Tidak ada uang kembali otomatis (keputusan Pemilik 24 Nov 2026): uang Rp49.000 menjadi deposit yang memotong
tagihan kelas bersama Guru. `terlambat` hanya informasi untuk admin dan pembeli; keterlambatan tidak membuka
pilihan apa pun.

Voucher 'ditahan' (lunas tetapi status turunan bukan `sudah_dibayar`, praktis `perlu_diperiksa`: dua jalur bayar atau
observasi refund/chargeback penyedia) tidak bisa dipakai atau diterbitkan laporannya; refund tetap boleh dicatat.

Larangan "refund setelah voucher dipakai" ditegakkan di `pesanan_refund_aturan.periksa_layak_refund` lewat
:func:`voucher_dipakai` (skema `purna_*` tidak boleh menyentuh tabel refund milik namespace lain).
Idempotensi = SELECT lalu INSERT dalam satu transaksi tulis; `INSERT OR IGNORE` tidak dipakai.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pesanan_dasar as d
import pesanan_status as st
import pesanan_transfer_baca as tb
import schema_purna as sk

# Janji terbit: (berlaku_dari_waktu_lunas, jam), urut menaik. Order memakai entri terakhir yang
# berlaku_dari <= waktu lunasnya, jadi menambah entri baru tidak menggeser janji order yang sudah lunas.
SLA_TERBIT = (("2000-01-01T00:00:00", 48),)
# Laporan dianggap terlambat segera setelah melewati janji SLA 48 jam (tanpa masa tunggu 72 jam sejak fitur uang kembali otomatis dihapus).
JAM_TOLERANSI_TERLAMBAT = 0
HARI_VOUCHER = 90               # masa berlaku voucher (deposit) sejak waktu lunas
JAM_PER_HARI = 24
AWALAN_KODE = "JGV-"
PANJANG_KODE = 12

VOUCHER_BELUM_LUNAS = "belum_lunas"
VOUCHER_AKTIF = "aktif"
VOUCHER_DIPAKAI = "dipakai"
VOUCHER_KEDALUWARSA = "kedaluwarsa"
VOUCHER_BATAL = "batal"
VOUCHER_DITAHAN = "ditahan"
PESAN_DITAHAN = "pembayaran order perlu diperiksa"

_PESAN_VOUCHER_TIDAK_AKTIF = {
    VOUCHER_BELUM_LUNAS: "order belum lunas",
    VOUCHER_DIPAKAI: "voucher sudah dipakai",
    VOUCHER_KEDALUWARSA: "voucher sudah kedaluwarsa",
    VOUCHER_BATAL: "voucher dibatalkan: order direfund",
    VOUCHER_DITAHAN: PESAN_DITAHAN,
}


@dataclass(frozen=True)
class KeadaanPurna:
    """Keadaan turunan satu order pada waktu `sekarang` (beku; tidak ada yang disimpan)."""
    lunas: bool
    direfund: bool
    waktu_lunas: Optional[str]
    kode: str
    voucher: str
    berlaku_hingga: Optional[str]
    janji_terbit: Optional[str]
    batas_pilihan: Optional[str]    # janji + toleransi; lewat batas ini laporan dianggap terlambat
    terbit: Optional[str]
    terlambat: bool
    dipakai: bool
    ditahan: bool


# --- turunan murni ---------------------------------------------------------------------------

def sla_jam(waktu_lunas):
    """Jam janji terbit untuk order yang lunas pada `waktu_lunas` (entri SLA terakhir yang sudah berlaku)."""
    jam = None
    for berlaku_dari, jam_entri in SLA_TERBIT:
        if berlaku_dari <= waktu_lunas:
            jam = jam_entri
    if jam is None:
        raise d.PesananDataTidakSah("waktu lunas sebelum SLA pertama")
    return jam


def kode_voucher(order_id):
    """Kode tampilan tetap dari order_id: 12 heks pertama (48 bit) sesudah awalan, huruf besar.

    BUKAN bukti kepemilikan dan tidak ada endpoint yang menerimanya sebagai kunci; kunci kanonis tetap order_id.
    Pencocokan oleh petugas lewat akun/order, bukan lewat kode.
    """
    d.periksa_order_id(order_id)
    return AWALAN_KODE + order_id[len(d.PREFIX_ORDER):][:PANJANG_KODE].upper()


def _tenggat(waktu_lunas):
    """(berlaku_hingga, janji_terbit, batas_pilihan) dari waktu lunas; semuanya None bila belum lunas."""
    if waktu_lunas is None:
        return None, None, None
    janji = d.tambah_jam(waktu_lunas, sla_jam(waktu_lunas))
    return (d.tambah_jam(waktu_lunas, HARI_VOUCHER * JAM_PER_HARI), janji,
            d.tambah_jam(janji, JAM_TOLERANSI_TERLAMBAT))


def _ditahan(*, lunas, direfund, status):
    """Lunas, belum direfund, tetapi status turunan bukan `sudah_dibayar` (praktis `perlu_diperiksa`).

    Dua jalur bayar atau observasi refund/chargeback penyedia: uangnya belum pasti, jadi voucher dan laporan ditahan.
    """
    return lunas and not direfund and status != d.STATUS_SUDAH_DIBAYAR


def _status_voucher(*, lunas, direfund, dipakai, ditahan, kini, berlaku_hingga):
    """Urutan: batal (direfund) > dipakai > ditahan > kedaluwarsa > aktif (lunas) / belum_lunas."""
    if direfund:
        return VOUCHER_BATAL
    if dipakai:
        return VOUCHER_DIPAKAI
    if ditahan:
        return VOUCHER_DITAHAN
    if berlaku_hingga is not None and kini >= berlaku_hingga:
        return VOUCHER_KEDALUWARSA
    return VOUCHER_AKTIF if lunas else VOUCHER_BELUM_LUNAS


# --- baca ------------------------------------------------------------------------------------

def _ada_tabel(kon, nama):
    return kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nama,)
                       ).fetchone() is not None


def terpasang(kon):
    """True bila SEMUA tabel `purna_*` sudah dimigrasikan (cek ringan, bukan validasi)."""
    return all(_ada_tabel(kon, tabel) for tabel in sk.TABEL)


def waktu_lunas(kon, order_id):
    """Waktu lunas (receipt Midtrans lunas, selain itu transfer_lunas); None bila belum lunas atau order tak ada.

    Urutan receipt-dulu sama dengan trigger skema (`purna_laporan_terbit_sebelum_lunas`).
    """
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    receipt = kon.execute("SELECT dibuat FROM pesanan_receipt WHERE order_id=? AND hasil='lunas'",
                          (order_id,)).fetchone()
    if receipt is not None:
        return receipt["dibuat"]
    if not tb.fakta(kon, order_id)["lunas"]:
        return None
    return kon.execute("SELECT dibuat FROM transfer_lunas WHERE order_id=?", (order_id,)).fetchone()["dibuat"]


def voucher_dipakai(kon, order_id):
    """True bila order sudah punya catatan pemakaian voucher (False bila `purna_*` belum terpasang)."""
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    if not _ada_tabel(kon, "purna_voucher_pakai"):
        return False
    return kon.execute("SELECT 1 FROM purna_voucher_pakai WHERE order_id=?", (order_id,)).fetchone() is not None


def _waktu_terbit(kon, order_id):
    if not _ada_tabel(kon, "purna_laporan_terbit"):
        return None
    baris = kon.execute("SELECT terbit FROM purna_laporan_terbit WHERE order_id=?", (order_id,)).fetchone()
    return None if baris is None else baris["terbit"]


def _keadaan(kon, order_id, kini):
    """Keadaan turunan; `order_id` dan `kini` sudah divalidasi. Order tak ada -> PesananTidakDitemukan."""
    baris = st.baris_order(kon, order_id)
    if baris is None:
        raise d.PesananTidakDitemukan()
    status = st.status_dari_db(kon, st.dict_order(baris), kini)
    direfund = status == d.STATUS_DIREFUND
    lunas_pada = waktu_lunas(kon, order_id)
    lunas = lunas_pada is not None
    ditahan = _ditahan(lunas=lunas, direfund=direfund, status=status)
    berlaku_hingga, janji, batas = _tenggat(lunas_pada)
    terbit, dipakai = _waktu_terbit(kon, order_id), voucher_dipakai(kon, order_id)
    terlambat = lunas and terbit is None and kini > batas
    return KeadaanPurna(
        lunas=lunas, direfund=direfund, waktu_lunas=lunas_pada, kode=kode_voucher(order_id),
        voucher=_status_voucher(lunas=lunas, direfund=direfund, dipakai=dipakai, ditahan=ditahan,
                                kini=kini, berlaku_hingga=berlaku_hingga),
        berlaku_hingga=berlaku_hingga, janji_terbit=janji, batas_pilihan=batas, terbit=terbit,
        terlambat=terlambat, dipakai=dipakai, ditahan=ditahan)


def keadaan(kon, order_id, sekarang):
    """Keadaan turunan order pada `sekarang` (SELECT saja); order tak ada -> PesananTidakDitemukan."""
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    return _keadaan(kon, order_id, d.waktu_baku(sekarang))


# --- tulis -----------------------------------------------------------------------------------

def _wajib_terpasang(kon):
    if not terpasang(kon):
        raise d.PesananKonflik("voucher purna belum dipasang")


def _pakai_sudah_ada(kon, operasi_id, isi):
    """True = replay identik; False = belum ada; operasi/order sudah punya catatan lain -> PesananKonflik."""
    ada = [tuple(b) for b in kon.execute(
        "SELECT operasi_id,order_id,dicatat_oleh,catatan_kode FROM purna_voucher_pakai "
        "WHERE operasi_id=? OR order_id=?", (operasi_id, isi[0]))]
    if any(b[0] != operasi_id or b[1:] != isi for b in ada):
        raise d.PesananKonflik("operasi atau order sudah punya catatan pemakaian lain")
    return bool(ada)


def catat_pakai(kon, order_id, operasi_id, dicatat_oleh, catatan_kode, sekarang):
    """Catat pemakaian voucher; idempoten per `operasi_id`. Mengembalikan {baru}.

    Hanya bila voucher 'aktif' (lunas, tidak direfund/ditahan, belum dipakai, belum kedaluwarsa); selain itu
    PesananKonflik. Replay identik -> baru False (juga sesudah kedaluwarsa); operasi sama isi beda, atau order
    sudah punya pemakaian lain -> PesananKonflik.
    """
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    d.periksa_operasi_id(operasi_id)
    d.periksa_pelaku(dicatat_oleh)
    if catatan_kode not in sk.CATATAN_PAKAI:
        raise d.PesananDataTidakSah("catatan_kode tidak sah")
    kini = d.waktu_baku(sekarang)
    isi = (order_id, dicatat_oleh, catatan_kode)
    with d.tulis(kon):
        _wajib_terpasang(kon)
        if _pakai_sudah_ada(kon, operasi_id, isi):
            return {"baru": False}
        voucher = _keadaan(kon, order_id, kini).voucher
        if voucher != VOUCHER_AKTIF:
            raise d.PesananKonflik(_PESAN_VOUCHER_TIDAK_AKTIF[voucher])
        kon.execute("INSERT INTO purna_voucher_pakai(operasi_id,order_id,dicatat_oleh,catatan_kode,dibuat) "
                    "VALUES(?,?,?,?,?)", (operasi_id,) + isi + (kini,))
        return {"baru": True}


def catat_terbit(kon, order_id, dicatat_oleh, sekarang):
    """Catat laporan terbit (terbit = `sekarang`) untuk order lunas yang tidak direfund; idempoten per order.

    Replay (sudah ada, siapa pun pencatatnya) -> baru False tanpa tulis. Ditolak (PesananKonflik) bila order belum
    lunas, direfund, atau voucher ditahan (pembayaran perlu diperiksa). Waktu terbit lebih awal dari waktu lunas -> PesananKonflik (trigger
    skema tidak sampai terpicu).
    """
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    d.periksa_pelaku(dicatat_oleh)
    kini = d.waktu_baku(sekarang)
    with d.tulis(kon):
        _wajib_terpasang(kon)
        if _waktu_terbit(kon, order_id) is not None:
            return {"baru": False}
        k = _keadaan(kon, order_id, kini)
        if not k.lunas:
            raise d.PesananKonflik("order belum lunas")
        if k.direfund:
            raise d.PesananKonflik("order sudah direfund")
        if k.ditahan:
            raise d.PesananKonflik(PESAN_DITAHAN)
        if kini < k.waktu_lunas:
            raise d.PesananKonflik("waktu terbit lebih awal dari waktu lunas")
        kon.execute("INSERT INTO purna_laporan_terbit(order_id,terbit,dicatat_oleh,dibuat) VALUES(?,?,?,?)",
                    (order_id, kini, dicatat_oleh, kini))
        return {"baru": True}
