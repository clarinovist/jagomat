"""Sisi admin langganan Latihan Harian: antrean bukti menunggu, detail, keputusan setuju/tolak, masa aktif.

Tanpa HTTP/berkas. Keputusan = satu `BEGIN IMMEDIATE`: tulis `harian_verifikasi` (hanya atas bukti terbaru yang
DILIHAT admin; bukti baru sejak itu = konflik tanpa tulis) lalu, bila setuju, `harian_akses` di transaksi yang sama.
Masa aktif: mulai = max(sekarang, akhir akses terakhir anak) supaya perpanjangan menyambung. berakhir dihitung dari
JANGKAR rantai akses yang tersambung (mulai akses pertama dalam rantai): jangkar + bulan paket seluruh rantai (termasuk
paket baru) dalam bulan kalender WIB (`harian_langganan_dasar.tambah_bulan_wib`), sehingga hari jangkar tidak bergeser
oleh jepit akhir bulan (31 Jan -> 28 Feb -> 31 Mar). Akses terakhir sudah berakhir = rantai baru, jangkar = sekarang.
Tanpa nama anak atau kontak.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

import harian_langganan_dasar as h
import harian_langganan_store as store
import pesanan_dasar as d
import schema_harian_langganan as sk

_KOLOM_BUKTI = ("id", "diunggah", "mime", "ukuran")


def antrean(kon, sekarang) -> tuple:
    """Order menunggu verifikasi, bukti terakhir paling lama menunggu dulu: tuple dict {order_id, paket, nominal, diunggah}."""
    d.periksa_koneksi(kon)
    h.ke_baku(sekarang)
    baris = kon.execute(
        "SELECT o.id AS order_id,o.paket,t.nominal_transfer AS nominal,"
        "(SELECT MAX(b.diunggah) FROM harian_bukti b WHERE b.order_id=o.id) AS diunggah "
        "FROM harian_order o JOIN harian_tagihan t ON t.order_id=o.id "
        "WHERE NOT %s AND %s ORDER BY diunggah,o.id" % (sk.SQL_SUDAH_LUNAS, sk.SQL_BELUM_DIPUTUSKAN))
    return tuple({k: b[k] for k in ("order_id", "paket", "nominal", "diunggah")} for b in baris)


def _order(kon, order_id: str):
    return kon.execute("SELECT id,siswa_id,paket,rupiah,dibuat,kedaluwarsa FROM harian_order WHERE id=?",
                       (order_id,)).fetchone()


def _keadaan_bukti(baris, hingga: int) -> str:
    if baris["dihapus"] is not None:
        return "dihapus"
    return "diputuskan" if baris["id"] <= hingga else "menunggu"


def _bukti(kon, order_id: str, hingga: int) -> tuple:
    """Bukti satu order dengan keadaan: `dihapus` (ada tanda di harian_bukti_hapus), `diputuskan`, atau `menunggu`."""
    baris = kon.execute(
        "SELECT %s,x.dihapus AS dihapus FROM harian_bukti b LEFT JOIN harian_bukti_hapus x ON x.bukti_id=b.id "
        "WHERE b.order_id=? ORDER BY b.id" % ",".join("b." + k for k in _KOLOM_BUKTI), (order_id,))
    return tuple({**{k: b[k] for k in _KOLOM_BUKTI}, "keadaan": _keadaan_bukti(b, hingga)} for b in baris)


def detail(kon, order_id: str, sekarang) -> Optional[dict]:
    """Detail satu order untuk admin, atau None bila tak ada. `bukti_terakhir_id` dipakai sebagai target tinjauan."""
    d.periksa_koneksi(kon)
    h.periksa_order_id(order_id)
    kini = h.ke_baku(sekarang)
    order = _order(kon, order_id)
    if order is None:
        return None
    fakta = store.fakta_order(kon, order_id)
    hingga = kon.execute("SELECT COALESCE(MAX(bukti_hingga_id),0) FROM harian_verifikasi WHERE order_id=?",
                         (order_id,)).fetchone()[0]
    nominal = kon.execute("SELECT nominal_transfer FROM harian_tagihan WHERE order_id=?", (order_id,)).fetchone()[0]
    keputusan = tuple({"keputusan": k["keputusan"], "alasan": k["alasan"], "dibuat": k["dibuat"]} for k in kon.execute(
        "SELECT keputusan,alasan,dibuat FROM harian_verifikasi WHERE order_id=? ORDER BY id", (order_id,)))
    return {"order_id": order_id, "paket": h.PAKET[order["paket"]].nama, "nominal": nominal,
            "status": store.status_dari(order, fakta, kini), "bukti": _bukti(kon, order_id, hingga),
            "keputusan": keputusan, "bukti_terakhir_id": fakta.bukti_terakhir_id}


def bukti_meta(kon, bukti_id) -> Optional[dict]:
    """{berkas, mime, ukuran} satu bukti untuk pratinjau admin, atau None bila id tak dikenal."""
    d.periksa_koneksi(kon)
    d.periksa_bilangan(bukti_id, "bukti_id")
    baris = kon.execute("SELECT berkas,mime,ukuran FROM harian_bukti WHERE id=?", (bukti_id,)).fetchone()
    return None if baris is None else {k: baris[k] for k in ("berkas", "mime", "ukuran")}


def _rantai_akses(kon, siswa_id: int, kini: str) -> tuple:
    """(mulai_baru, jangkar, bulan_terpakai) untuk akses berikutnya milik anak.

    Rantai = akses terakhir bila belum berakhir (berakhir >= kini) ditambah akses sebelumnya yang tersambung
    (mulai baris == berakhir baris sebelumnya), mundur sampai putus. Jangkar = mulai akses pertama rantai;
    bulan_terpakai = jumlah bulan paket seluruh rantai. Tanpa akses, atau akses terakhir sudah berakhir:
    rantai baru (mulai = jangkar = kini, bulan_terpakai = 0). Hanya SELECT; dipanggil di dalam transaksi tulis.
    """
    baris = kon.execute(
        "SELECT a.mulai,a.berakhir,o.paket FROM harian_akses a JOIN harian_order o ON o.id=a.order_id "
        "WHERE a.siswa_id=? ORDER BY a.id DESC", (siswa_id,)).fetchall()
    if not baris or baris[0]["berakhir"] < kini:
        return kini, kini, 0
    rantai = [baris[0]]
    for sebelumnya in baris[1:]:
        if sebelumnya["berakhir"] != rantai[-1]["mulai"]:
            break
        rantai.append(sebelumnya)
    return baris[0]["berakhir"], rantai[-1]["mulai"], sum(h.PAKET[b["paket"]].bulan for b in rantai)


def _tulis_akses(kon, order, verifikasi_id: int, kini: str) -> None:
    mulai, jangkar, bulan_terpakai = _rantai_akses(kon, order["siswa_id"], kini)
    berakhir = h.tambah_bulan_wib(jangkar, bulan_terpakai + h.PAKET[order["paket"]].bulan)
    kon.execute("INSERT INTO harian_akses(order_id,siswa_id,verifikasi_id,mulai,berakhir,dibuat) VALUES(?,?,?,?,?,?)",
                (order["id"], order["siswa_id"], verifikasi_id, mulai, berakhir, kini))


def _tulis_putusan(kon, order, fakta, admin_id, keputusan, alasan, kini, bukti_dilihat) -> int:
    if bukti_dilihat != fakta.bukti_terakhir_id:
        raise h.LanggananKonflik("bukti berubah sejak dilihat admin")
    try:
        kursor = kon.execute(
            "INSERT INTO harian_verifikasi(order_id,keputusan,admin_id,alasan,bukti_hingga_id,dibuat) "
            "VALUES(?,?,?,?,?,?)", (order["id"], keputusan, admin_id, alasan, fakta.bukti_terakhir_id, kini))
        if keputusan == h.KEPUTUSAN_SETUJU:
            _tulis_akses(kon, order, kursor.lastrowid, kini)
    except sqlite3.IntegrityError:
        raise h.LanggananKonflik("keputusan bentrok dengan catatan yang ada") from None
    return kursor.lastrowid


def _putuskan(kon, order_id, admin_id, keputusan, alasan, sekarang, bukti_dilihat) -> dict:
    d.periksa_koneksi(kon)
    h.periksa_order_id(order_id)
    d.periksa_pelaku(admin_id)
    d.periksa_bilangan(bukti_dilihat, "bukti_dilihat")
    kini = h.ke_baku(sekarang)
    with d.tulis(kon):
        order = _order(kon, order_id)
        if order is None:
            raise d.PesananTidakDitemukan()
        fakta = store.fakta_order(kon, order_id)
        if store.status_dari(order, fakta, kini) != h.STATUS_MENUNGGU:
            raise h.LanggananKonflik("order tidak menunggu verifikasi")
        putusan_id = _tulis_putusan(kon, order, fakta, admin_id, keputusan, alasan, kini, bukti_dilihat)
        return {"status": store.status_dari(order, store.fakta_order(kon, order_id), kini),
                "verifikasi_id": putusan_id}


def setujui(kon, order_id, admin_id, sekarang, *, bukti_dilihat) -> dict:
    """Setujui bukti: verifikasi 'setuju' + akses langganan dalam SATU transaksi.

    `bukti_dilihat` (wajib) = id bukti terbaru yang dilihat admin; ada bukti lebih baru -> LanggananKonflik tanpa
    tulis. Bukan status menunggu (termasuk sudah disetujui) -> LanggananKonflik; order tak dikenal ->
    PesananTidakDitemukan. Mengembalikan {status, verifikasi_id}.
    """
    return _putuskan(kon, order_id, admin_id, h.KEPUTUSAN_SETUJU, None, sekarang, bukti_dilihat)


def tolak(kon, order_id, admin_id, alasan, sekarang, *, bukti_dilihat) -> dict:
    """Tolak bukti dengan `alasan` wajib; status jadi `ditolak` (unggah ulang boleh selama jendela terbuka)."""
    return _putuskan(kon, order_id, admin_id, h.KEPUTUSAN_TOLAK, h.alasan_sah(alasan), sekarang, bukti_dilihat)
