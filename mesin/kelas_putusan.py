"""Sisi admin paket kelas: detail order, keputusan setuju/tolak, masa aktif, dan pemakaian deposit saat lunas.

Tanpa HTTP/berkas. Keputusan = SATU `BEGIN IMMEDIATE` (`pesanan_dasar.tulis`):

* hanya atas bukti terbaru yang DILIHAT admin (`bukti_dilihat` wajib; bukti baru sejak itu = konflik tanpa tulis);
* setuju: hitungan tagihan diperiksa ulang (total = nominal + kode unik); bila tagihan memotong deposit Peta, deposit
  diperiksa ULANG di dalam transaksi (order Peta harus milik akun dan anak order, dan masih aktif) dan dicatat dipakai
  lewat `purna.catat_pakai_dalam_transaksi` di transaksi yang SAMA dengan verifikasi dan akses. Deposit kedaluwarsa,
  ditahan, direfund, atau sudah dipakai -> DepositTidakAktif, TIDAK ada verifikasi/akses/pemakaian tertulis (admin
  menolak lalu pembeli membuat tagihan baru dengan nominal yang benar);
* setuju dua kali tidak menggandakan akses atau deposit (balasan `baru=False`).

Masa aktif per (anak, paket): mulai = max(sekarang, akhir akses terakhir paket itu) supaya perpanjangan menyambung;
berakhir dihitung dari JANGKAR rantai yang tersambung dalam bulan kalender WIB (`kelas_dasar.tambah_bulan_wib`),
sehingga hari jangkar tidak bergeser oleh jepit akhir bulan (31 Jan -> 28 Feb -> 31 Mar). Akses terakhir sudah
berakhir = rantai baru. Tanpa nama anak atau kontak.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

import kelas_dasar as k
import kelas_status as ks
import pesanan_dasar as d
import purna

_KOLOM_BUKTI = ("id", "diunggah", "mime", "ukuran")


# --- bacaan admin -----------------------------------------------------------------------------

def detail(kon, order_id, sekarang) -> Optional[dict]:
    """Detail satu order untuk admin, atau None bila tak ada. `bukti_terakhir_id` = target `bukti_dilihat`."""
    d.periksa_koneksi(kon)
    k.periksa_order_id(order_id)
    kini = k.ke_baku(sekarang)
    order = ks.baris_order(kon, order_id)
    if order is None:
        return None
    fakta = ks.fakta_order(kon, order_id)
    tagihan = ks.baris_tagihan(kon, order_id)
    hingga = kon.execute("SELECT COALESCE(MAX(bukti_hingga_id),0) FROM kelas_verifikasi WHERE order_id=?",
                         (order_id,)).fetchone()[0]
    bukti = tuple({**{n: b[n] for n in _KOLOM_BUKTI}, "keadaan": "diputuskan" if b["id"] <= hingga else "menunggu"}
                  for b in kon.execute("SELECT %s FROM kelas_bukti WHERE order_id=? ORDER BY id"
                                       % ",".join(_KOLOM_BUKTI), (order_id,)))
    keputusan = tuple({"keputusan": v["keputusan"], "alasan": v["alasan"], "dibuat": v["dibuat"]}
                      for v in kon.execute("SELECT keputusan,alasan,dibuat FROM kelas_verifikasi "
                                           "WHERE order_id=? ORDER BY id", (order_id,)))
    return {"order_id": order_id, "siswa_id": order["siswa_id"], "kode_paket": order["paket"],
            "rincian": ks.rincian_dari_baris(order["paket"], tagihan), "kode_unik": tagihan["kode_unik"],
            "total": tagihan["total_transfer"], "deposit_order_id": tagihan["deposit_order_id"],
            "status": ks.status_dari(order, fakta, kini), "bukti": bukti, "keputusan": keputusan,
            "bukti_terakhir_id": fakta.bukti_terakhir_id}


def bukti_meta(kon, bukti_id) -> Optional[dict]:
    """{berkas, mime, ukuran} satu bukti untuk pratinjau admin, atau None bila id tak dikenal."""
    d.periksa_koneksi(kon)
    d.periksa_bilangan(bukti_id, "bukti_id")
    baris = kon.execute("SELECT berkas,mime,ukuran FROM kelas_bukti WHERE id=?", (bukti_id,)).fetchone()
    return None if baris is None else {n: baris[n] for n in ("berkas", "mime", "ukuran")}


# --- masa aktif ---------------------------------------------------------------------------------

def _rantai_akses(kon, siswa_id: int, kode_paket: str, kini: str) -> tuple:
    """(mulai_baru, jangkar, bulan_terpakai) untuk akses berikutnya milik (anak, paket).

    Rantai = akses terakhir paket itu bila belum berakhir (berakhir >= kini) ditambah akses sebelumnya yang tersambung
    (mulai baris == berakhir baris sesudahnya), mundur sampai putus. Jangkar = mulai akses pertama rantai. Tanpa akses,
    atau akses terakhir sudah berakhir: rantai baru (mulai = jangkar = kini, bulan_terpakai = 0).
    """
    baris = kon.execute(
        "SELECT a.mulai,a.berakhir FROM kelas_akses a JOIN kelas_order o ON o.id=a.order_id "
        "WHERE a.siswa_id=? AND o.paket=? ORDER BY a.id DESC", (siswa_id, kode_paket)).fetchall()
    if not baris or baris[0]["berakhir"] < kini:
        return kini, kini, 0
    rantai = [baris[0]]
    for sebelumnya in baris[1:]:
        if sebelumnya["berakhir"] != rantai[-1]["mulai"]:
            break
        rantai.append(sebelumnya)
    return baris[0]["berakhir"], rantai[-1]["mulai"], len(rantai) * k.BULAN_PER_PAKET


def _tulis_akses(kon, order, verifikasi_id: int, kini: str) -> None:
    mulai, jangkar, terpakai = _rantai_akses(kon, order["siswa_id"], order["paket"], kini)
    berakhir = k.tambah_bulan_wib(jangkar, terpakai + k.BULAN_PER_PAKET)
    kon.execute("INSERT INTO kelas_akses(order_id,siswa_id,verifikasi_id,mulai,berakhir,dibuat) VALUES(?,?,?,?,?,?)",
                (order["id"], order["siswa_id"], verifikasi_id, mulai, berakhir, kini))


# --- keputusan ----------------------------------------------------------------------------------

def _periksa_hitungan(tagihan) -> None:
    """Hitungan tersimpan harus konsisten (DB sudah menjaganya lewat CHECK; ini lapis kedua di domain)."""
    nominal = tagihan["harga_dasar"] - tagihan["potongan_deposit"] - tagihan["potongan_diskon"]
    if nominal <= 0 or tagihan["nominal"] != nominal or tagihan["total_transfer"] != nominal + tagihan["kode_unik"]:
        raise k.TagihanTidakSah("hitungan tagihan tidak konsisten")


def _periksa_deposit_milik(kon, order, tagihan) -> None:
    """Order Peta yang dipotongkan harus milik akun dan anak order kelas ini (bukan sekadar order Peta mana pun)."""
    peta = kon.execute("SELECT akun_id,siswa_id FROM pesanan_order WHERE order_id=?",
                       (tagihan["deposit_order_id"],)).fetchone()
    if peta is None or peta["akun_id"] != order["akun_id"] or peta["siswa_id"] != order["siswa_id"]:
        raise k.DepositTidakAktif("deposit bukan milik akun pembeli")


def _pakai_deposit(kon, order, tagihan, admin_id: str, kini: str) -> None:
    """Cek ulang di dalam transaksi lalu catat deposit dipakai (tepat sekali; galat membatalkan semuanya)."""
    _periksa_deposit_milik(kon, order, tagihan)
    try:
        purna.catat_pakai_dalam_transaksi(kon, tagihan["deposit_order_id"], k.operasi_deposit(order["id"]),
                                          admin_id, k.CATATAN_PAKAI_DEPOSIT, kini)
    except d.PesananKonflik as galat:
        raise k.DepositTidakAktif(str(galat)) from None


def _tulis_verifikasi(kon, order, fakta, admin_id, keputusan, alasan, kini) -> int:
    try:
        return kon.execute(
            "INSERT INTO kelas_verifikasi(order_id,keputusan,admin_id,alasan,bukti_hingga_id,dibuat) "
            "VALUES(?,?,?,?,?,?)", (order["id"], keputusan, admin_id, alasan, fakta.bukti_terakhir_id, kini)
        ).lastrowid
    except sqlite3.IntegrityError:
        raise k.KelasKonflik("keputusan bentrok dengan catatan yang ada") from None


def _masuk_keputusan(kon, order_id, bukti_dilihat, kini: str):
    """(order, fakta) order yang menunggu keputusan; selain itu galat tanpa tulis."""
    order = ks.baris_order(kon, order_id)
    if order is None:
        raise d.PesananTidakDitemukan()
    fakta = ks.fakta_order(kon, order_id)
    if ks.status_dari(order, fakta, kini) != k.STATUS_MENUNGGU:
        raise k.KelasKonflik("order tidak menunggu verifikasi")
    if bukti_dilihat != fakta.bukti_terakhir_id:
        raise k.KelasKonflik("bukti berubah sejak dilihat admin")
    return order, fakta


def _validasi_keputusan(kon, order_id, admin_id, bukti_dilihat) -> None:
    d.periksa_koneksi(kon)
    k.periksa_order_id(order_id)
    d.periksa_pelaku(admin_id)
    d.periksa_bilangan(bukti_dilihat, "bukti_dilihat")


def _sudah_disetujui(kon, order_id: str) -> Optional[dict]:
    baris = kon.execute("SELECT id FROM kelas_verifikasi WHERE order_id=? AND keputusan='setuju'",
                        (order_id,)).fetchone()
    return None if baris is None else {"status": k.STATUS_AKTIF, "verifikasi_id": baris["id"], "baru": False}


def setujui(kon, order_id, admin_id, sekarang, *, bukti_dilihat) -> dict:
    """Setujui bukti: verifikasi 'setuju' + akses + pemakaian deposit (bila dipotongkan) dalam SATU transaksi.

    `bukti_dilihat` (wajib) = id bukti terbaru yang dilihat admin; ada bukti lebih baru -> KelasKonflik tanpa tulis.
    Sudah disetujui -> {status aktif, verifikasi_id, baru False} tanpa tulis. Bukan status menunggu -> KelasKonflik;
    order tak dikenal -> PesananTidakDitemukan; hitungan tak konsisten -> TagihanTidakSah; deposit tak lagi sah
    -> DepositTidakAktif (tidak ada yang tertulis). Mengembalikan {status, verifikasi_id, baru}.
    """
    _validasi_keputusan(kon, order_id, admin_id, bukti_dilihat)
    kini = k.ke_baku(sekarang)
    with d.tulis(kon):
        ulang = _sudah_disetujui(kon, order_id)
        if ulang is not None:
            return ulang
        order, fakta = _masuk_keputusan(kon, order_id, bukti_dilihat, kini)
        tagihan = ks.baris_tagihan(kon, order_id)
        _periksa_hitungan(tagihan)
        if tagihan["potongan_deposit"] > 0:
            _pakai_deposit(kon, order, tagihan, admin_id, kini)
        verifikasi_id = _tulis_verifikasi(kon, order, fakta, admin_id, k.KEPUTUSAN_SETUJU, None, kini)
        try:
            _tulis_akses(kon, order, verifikasi_id, kini)
        except sqlite3.IntegrityError:
            raise k.KelasKonflik("akses bentrok dengan catatan yang ada") from None
        return {"status": k.STATUS_AKTIF, "verifikasi_id": verifikasi_id, "baru": True}


def tolak(kon, order_id, admin_id, alasan, sekarang, *, bukti_dilihat) -> dict:
    """Tolak bukti dengan `alasan` wajib; status jadi `ditolak` (unggah ulang boleh selama jendela terbuka).

    Deposit TIDAK disentuh (belum dipakai); tagihan yang ditolak dan kedaluwarsa melepas deposit untuk tagihan baru.
    """
    _validasi_keputusan(kon, order_id, admin_id, bukti_dilihat)
    bersih = k.alasan_sah(alasan)
    kini = k.ke_baku(sekarang)
    with d.tulis(kon):
        order, fakta = _masuk_keputusan(kon, order_id, bukti_dilihat, kini)
        verifikasi_id = _tulis_verifikasi(kon, order, fakta, admin_id, k.KEPUTUSAN_TOLAK, bersih, kini)
        status = ks.status_dari(order, ks.fakta_order(kon, order_id), kini)
        return {"status": status, "verifikasi_id": verifikasi_id, "baru": True}
