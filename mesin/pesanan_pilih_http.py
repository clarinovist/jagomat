"""POST pilihan pembeli saat laporan terlambat (V4a): `/murid/pesanan/pilih`, aksi token `pilih`.

Mengikuti kerangka aksi `periksa` murid (`pesanan_http.layani_post`): pembeli dan anak dari sesi server (dipastikan
`pesanan_murid_http`), pembatas laju per akun dan IP dengan ember ketat yang sama dengan periksa, form harus persis
`{token, pilihan}` (menunggu) atau `{token, pilihan, yakin}` (uang kembali; `yakin` == "1", kotak centang konfirmasi
yang ditegakkan SERVER seperti "hapus PIN": uang kembali bersifat final dan membatalkan voucher), token HMAC terikat
aksi `pilih`, kepemilikan lewat `pesanan_status.ambil_order` (404 murid identik
dengan rute tak dikenal), PRG 303 ke status, galat dipetakan tanpa `str(galat)`.

GERBANG: sengaja TIDAK memakai gerbang pembayaran (Midtrans maupun transfer). Memilih menunggu atau uang kembali
adalah hak pembeli SESUDAH membayar dan tidak menyentuh provider pembayaran mana pun; pembeli transfer harus bisa
memilih, dan menutup penjualan (FUNNEL_AKTIF, tahap, rekening) tidak boleh mengunci pembeli yang sudah lunas.
Penjaganya: sakelar `DAFTAR_AKUN_ANAK` dan murid tertaut (`pesanan_murid_http`), laju, form, token, whitelist,
kepemilikan, dan syarat domain (`purna.catat_pilihan`: lunas, terlambat, belum terbit, voucher belum dipakai,
tidak direfund, skema purna terpasang, monoton). Pelanggaran syarat domain = PesananKonflik = respons konflik yang
sama dengan galat domain pembeli lain, tanpa menyebut alasan internal dan tanpa efek tulis.
"""
from __future__ import annotations

import admin_store
import pesanan
import pesanan_alur as alur
import pesanan_http as dasar
import pesanan_permukaan as permukaan
import pesanan_status
import purna
import schema_purna
import pesanan_voucher_pages as halaman_voucher
from kontak_http import _alihkan, _baca_form

AKSI_PILIH = dasar.AKSI_PILIH
KUNCI_DASAR = frozenset({"token", "pilihan"})
KUNCI_FORM = (KUNCI_DASAR, KUNCI_DASAR | {"yakin"})   # himpunan kunci sah: menunggu, atau uang kembali + yakin
NILAI_YAKIN = "1"
KODE_YAKIN_WAJIB = 400


def _catat(principal, pilihan: str) -> None:
    """Catat pilihan untuk order milik akun sesi; order tak ada atau bukan milik akun = PesananTidakDitemukan."""
    order_id = alur.order_id_akun(admin_store.BAWAAN, principal)
    if order_id is None:
        raise pesanan.PesananTidakDitemukan()
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = pesanan_status.ambil_order(kon, order_id, principal.id_akun)
        purna.catat_pilihan(kon, order["order_id"], pilihan, alur.waktu_sekarang())


def _yakin_sah(penangan, principal, data) -> bool:
    """Konfirmasi: uang kembali WAJIB yakin == "1"; menunggu tidak boleh membawa yakin. Respons galat sudah dikirim."""
    if data["pilihan"] != purna.PILIHAN_UANG_KEMBALI:
        if "yakin" in data:
            penangan._tolak_isian()
            return False
        return True
    if "yakin" not in data:
        dasar._info(penangan, principal, "Konfirmasi dulu", halaman_voucher.COPY_YAKIN_WAJIB, KODE_YAKIN_WAJIB,
                    (permukaan.rute_untuk(principal).status, halaman_voucher.COPY_KEMBALI_STATUS))
        return False
    if data["yakin"] != NILAI_YAKIN:
        penangan._tolak_isian()
        return False
    return True


def _form_sah(penangan, principal):
    """Pilihan dari form sah, atau None (respons 400/403 sudah dikirim)."""
    data = _baca_form(penangan)
    if data is None or frozenset(data) not in KUNCI_FORM:
        penangan._tolak_isian()
        return None
    if not dasar.token_sah(principal, penangan._ambil_token(), AKSI_PILIH, data["token"]):
        penangan._tolak_isian(403)
        return None
    if data["pilihan"] not in schema_purna.PILIHAN_TERLAMBAT:
        penangan._tolak_isian()
        return None
    return data["pilihan"] if _yakin_sah(penangan, principal, data) else None


def layani_post(penangan, principal) -> None:
    """POST pilihan untuk principal murid yang SUDAH tervalidasi; selalu menjawab (tidak ada jatuh ke penangan lain)."""
    if not dasar._izinkan(penangan, principal, ketat=True):
        dasar._tolak_laju(penangan)
        return
    pilihan = _form_sah(penangan, principal)
    if pilihan is None:
        return
    try:
        _catat(principal, pilihan)
    except dasar._GALAT_ALUR as galat:
        dasar._galat_domain(penangan, principal, galat, post=True)
        return
    if not dasar._masih_sah(penangan, principal):
        dasar._tidak_ada_pembeli(penangan, principal, post=True)
        return
    _alihkan(penangan, permukaan.rute_untuk(principal).status)
