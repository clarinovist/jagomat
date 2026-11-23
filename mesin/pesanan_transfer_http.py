"""Rute POST jalur transfer rekening Paket Coba: pesan (transfer-only), tagihan, ulang, unggah bukti.

Dipanggil dispatcher tepat SETELAH `pesanan_http.tangani_post`, jadi gerbang Midtrans/QRIS
dan perilakunya tidak berubah: bila Midtrans terbuka, `pesan` sudah dilayani di sana. Aturan:

- Gerbang = `pesanan_transfer_gerbang` (sakelar tepat "1" + funnel + runtime produksi +
  rekening terisi). Tertutup: rute transfer tidak ditangani (jatuh ke 404 rute tak dikenal).
- `id_akun` HANYA dari principal sesi server; order diturunkan dari akun itu (tanpa id order,
  nominal, atau nama berkas di form). Peran lain: 404 byte-identik dengan rute tak dikenal.
- Token form HMAC per aksi (`pesan`, `tagihan`, `bukti`); pembatas laju per akun dan IP, unggah
  punya ember ketat sendiri.
- Unggah: urutan penolakan SEBELUM tulis apa pun - laju, body berbatas (`_baca_tubuh`),
  multipart sempit, token, ukuran, magic bytes, kepemilikan order, hambatan jendela/tagihan/batas.
  Berkas ditulis atomik ke folder khusus lalu dicatat; catat gagal/duplikat -> berkas dihapus.
- Ulang (`/pesanan/tagihan/ulang`): jendela bayar baru untuk order kedaluwarsa tanpa bukti, hanya bila gerbang
  Midtrans tertutup (terbuka = tidak ditangani; QRIS punya tombol ulangnya sendiri); batas/kuota/status
  ditegakkan domain (`pesanan_transfer_ulang`), token aksi sendiri `ulang_transfer`.
- Pesan galat tetap; tidak ada jalur berkas, id, atau `str(galat)` di respons.
"""
from __future__ import annotations

import hashlib

import admin_store
import bukti_berkas
import bukti_multipart
import pesanan
import pesanan_alur as alur
import pesanan_http as dasar
import pesanan_pages as halaman
import pesanan_permukaan as permukaan
import pesanan_transfer
import pesanan_transfer_pages as teks
import pesanan_transfer_tampil as tampil
import pesanan_transfer_ulang
from bukti_berkas import mime_dari_isi
from cek_http import _tidak_ada
from kontak_http import _alihkan, _baca_form, _principal_guru
from schema_transfer import BATAS_UKURAN_BUKTI

RUTE_UNGGAH = teks.RUTE_BUKTI
RUTE_TAGIHAN = teks.RUTE_TAGIHAN
RUTE_ULANG = teks.RUTE_ULANG
_RUTE = teks.RUTE_POST | {dasar.RUTE_PESAN}
KUNCI_FORM = frozenset({"token"})
OVERHEAD_MULTIPART = 64 * 1024
BATAS_BODY_UNGGAH = BATAS_UKURAN_BUKTI + OVERHEAD_MULTIPART
EMBER_BUKTI = "bukti"
KODE_BERKAS_KOSONG = 400
KODE_BERKAS_BESAR = 413
KODE_TIPE_TIDAK_DIDUKUNG = 415
KODE_BENTROK = 409
KODE_TIDAK_SIAP = 503
_HAMBATAN = {
    tampil.HAMBATAN_TAGIHAN: teks.COPY_BELUM_ADA_TAGIHAN,
    tampil.HAMBATAN_STATUS: teks.COPY_TIDAK_TERIMA,
    tampil.HAMBATAN_JENDELA: teks.COPY_JENDELA_TUTUP,
    tampil.HAMBATAN_BATAS: teks.COPY_BATAS_TERCAPAI,
}
_GALAT_UNGGAH = dasar._GALAT_ALUR + (bukti_berkas.BuktiBerkasError,)


def _kembali(principal):
    return (permukaan.rute_untuk(principal).status, "Kembali ke pesanan")


def _tolak(penangan, principal, judul: str, pesan: str, kode: int) -> None:
    dasar._info(penangan, principal, judul, pesan, kode, _kembali(principal))


def _galat_transfer(penangan, principal, galat: Exception, konflik: str) -> None:
    """Peta galat domain transfer ke pesan tetap; sisanya diserahkan ke peta pesanan_http."""
    if isinstance(galat, pesanan_transfer.PesananBatasBukti):
        _tolak(penangan, principal, "Batas bukti tercapai", teks.COPY_BATAS_TERCAPAI, KODE_BENTROK)
    elif isinstance(galat, pesanan_transfer.PesananKodeUnikHabis):
        _tolak(penangan, principal, "Tagihan belum bisa dibuat", teks.COPY_KODE_HABIS, KODE_BENTROK)
    elif isinstance(galat, pesanan.PesananBatasJendela):
        _tolak(penangan, principal, "Tidak bisa dibuka ulang", halaman.COPY_BATAS_ULANG, KODE_BENTROK)
    elif isinstance(galat, pesanan.PesananKonflik):
        _tolak(penangan, principal, "Belum bisa diproses", konflik, KODE_BENTROK)
    else:
        dasar._galat_domain(penangan, principal, galat, post=True)


def _form_token_sah(penangan, principal, aksi: str) -> bool:
    """True bila form `{token}` sah; selain itu respons 400/403 sudah dikirim."""
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM:
        penangan._tolak_isian()
        return False
    if not dasar.token_sah(principal, penangan._ambil_token(), aksi, data["token"]):
        penangan._tolak_isian(403)
        return False
    return True


def _selesai(penangan, principal) -> None:
    if not dasar._masih_sah(penangan, principal):
        dasar._tidak_ada_pembeli(penangan, principal, post=True)
        return
    _alihkan(penangan, permukaan.rute_untuk(principal).status)


# --- pesan (Midtrans tertutup) dan tagihan -----------------------------------------

def _pesan(penangan, principal) -> bool:
    runtime = dasar._runtime(penangan)
    if runtime is None:
        return False
    if not _terima_form(penangan, principal, dasar.AKSI_PESAN):
        return True
    try:
        alur.pesan(admin_store.BAWAAN, principal, None, runtime.config.merchant)
    except dasar._GALAT_ALUR as galat:
        dasar._galat_domain(penangan, principal, galat, post=True)
        return True
    _selesai(penangan, principal)
    return True


def _buat_tagihan(principal) -> None:
    order_id = alur.order_id_akun(admin_store.BAWAAN, principal)
    if order_id is None:
        raise pesanan.PesananTidakDitemukan()  # dijawab 404 identik oleh `_galat_domain`
    with pesanan_transfer.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        pesanan_transfer.buat_tagihan_transfer(kon, order_id, principal.id_akun, alur.waktu_sekarang())


def _tagihan(penangan, principal) -> None:
    if not _terima_form(penangan, principal, teks.AKSI_TAGIHAN):
        return
    try:
        _buat_tagihan(principal)
    except dasar._GALAT_ALUR as galat:
        _galat_transfer(penangan, principal, galat, teks.COPY_TAGIHAN_TIDAK_BISA)
        return
    _selesai(penangan, principal)


def _buka_ulang(principal) -> None:
    order_id = alur.order_id_akun(admin_store.BAWAAN, principal)
    if order_id is None:
        raise pesanan.PesananTidakDitemukan()
    with pesanan_transfer.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        urutan = pesanan.jendela_terbaru(kon, order_id)["urutan"] + 1
        pesanan_transfer_ulang.buka_ulang(
            kon, order_id, principal.id_akun, alur.waktu_sekarang(), alur.operasi_ulang(order_id, urutan))


def _ulang(penangan, principal) -> bool:
    """Jendela bayar baru lewat transfer; hanya bila Midtrans tertutup (satu aksi satu tombol)."""
    if dasar._runtime_bila_terbuka(penangan) is not None:
        return False
    if not _terima_form(penangan, principal, teks.AKSI_ULANG):
        return True
    try:
        _buka_ulang(principal)
    except dasar._GALAT_ALUR as galat:
        _galat_transfer(penangan, principal, galat, teks.COPY_ULANG_TIDAK_BISA)
        return True
    _selesai(penangan, principal)
    return True


def _terima_form(penangan, principal, aksi: str) -> bool:
    """Laju + form `{token}` sah; False (respons sudah dikirim) bila ditolak."""
    if not dasar._izinkan(penangan, principal):
        dasar._tolak_laju(penangan)
        return False
    return _form_token_sah(penangan, principal, aksi)


# --- unggah bukti --------------------------------------------------------------------

def _periksa_isi(isi: bytes):
    """(kode, pesan, mime): kode/pesan terisi bila isi ditolak; mime dari MAGIC BYTES."""
    if not isi:
        return KODE_BERKAS_KOSONG, teks.COPY_BERKAS_KOSONG, None
    if len(isi) > BATAS_UKURAN_BUKTI:
        return KODE_BERKAS_BESAR, teks.COPY_BERKAS_BESAR, None
    mime = mime_dari_isi(isi)
    if mime is None:
        return KODE_TIPE_TIDAK_DIDUKUNG, teks.COPY_TIPE_TIDAK_DIDUKUNG, None
    return None, None, mime


def _baca_unggahan(penangan, principal):
    """BuktiForm sah dari body multipart, atau None (respons penolakan sudah dikirim)."""
    tubuh = penangan._baca_tubuh(BATAS_BODY_UNGGAH)
    if tubuh is None:
        penangan.close_connection = True
        penangan._tolak_isian(KODE_BERKAS_BESAR)
        return None
    form = bukti_multipart.parse(tubuh, penangan.headers.get("Content-Type", ""))
    if form is None:
        _tolak(penangan, principal, "Berkas tidak terbaca", teks.COPY_BERKAS_TAK_TERBACA, 400)
        return None
    if not dasar.token_sah(principal, penangan._ambil_token(), teks.AKSI_BUKTI, form.token):
        penangan._tolak_isian(403)
        return None
    return form


def _hambatan(order_id, principal):
    """Pesan ramah bila order PASTI menolak bukti baru sekarang; None bila boleh dicoba."""
    sekarang = alur.waktu_sekarang()
    with pesanan_transfer.buka(admin_store.BAWAAN) as kon:
        potret = tampil.baca(kon, order_id, principal.id_akun, sekarang)
    kode = tampil.hambatan_unggah(potret, sekarang)
    return None if kode is None else _HAMBATAN[kode]


def _simpan_dan_catat(order_id, principal, isi: bytes, mime: str) -> None:
    """Tulis berkas atomik lalu catat; gagal atau duplikat -> berkas dihapus."""
    nama = bukti_berkas.simpan_berkas(isi)
    try:
        with pesanan_transfer.buka(admin_store.BAWAAN, tulis_data=True) as kon:
            hasil = pesanan_transfer.catat_bukti(
                kon, order_id, principal.id_akun, mime, len(isi), _sha256(isi), nama,
                alur.waktu_sekarang())
    except BaseException:
        bukti_berkas.hapus_berkas(nama)
        raise
    if not hasil["baru"]:
        bukti_berkas.hapus_berkas(nama)


def _sha256(isi: bytes) -> str:
    return hashlib.sha256(isi).hexdigest()


def _unggah_sah(penangan, principal, form) -> None:
    kode, pesan, mime = _periksa_isi(form.isi)
    if kode is not None:
        _tolak(penangan, principal, "Berkas belum bisa diterima", pesan, kode)
        return
    order_id = alur.order_id_akun(admin_store.BAWAAN, principal)
    if order_id is None:
        dasar._tidak_ada_pembeli(penangan, principal, post=True)
        return
    hambatan = _hambatan(order_id, principal)
    if hambatan is not None:
        _tolak(penangan, principal, "Bukti belum bisa diterima", hambatan, KODE_BENTROK)
        return
    _simpan_dan_catat(order_id, principal, form.isi, mime)
    _selesai(penangan, principal)


def _unggah(penangan, principal) -> None:
    if not dasar._izinkan(penangan, principal, ketat=True, ember=EMBER_BUKTI):
        penangan.close_connection = True
        dasar._tolak_laju(penangan)
        return
    form = _baca_unggahan(penangan, principal)
    if form is None:
        return
    try:
        _unggah_sah(penangan, principal, form)
    except _GALAT_UNGGAH as galat:
        _galat_transfer(penangan, principal, galat, teks.COPY_TIDAK_TERIMA)


def tangani_post(penangan, jalur: str) -> bool:
    """POST pesan (transfer-only), tagihan, ulang, atau unggah bukti; gerbang tertutup = tidak ditangani."""
    if jalur not in _RUTE:
        return False
    principal = _principal_guru(penangan)
    if principal is None:
        _tidak_ada(penangan, post=True)
        return True
    return layani_post(penangan, jalur, principal)


def layani_post(penangan, jalur: str, principal) -> bool:
    """POST transfer untuk principal pembeli yang SUDAH tervalidasi; `jalur` = alamat kanonik (guru).

    Dipakai penangan guru dan `pesanan_murid_http`. False bila bukan rute transfer atau gerbang
    transfer tertutup (pemanggil memutuskan jawabannya).
    """
    if jalur not in _RUTE:
        return False
    if dasar.rekening_transfer(penangan) is None:
        return False
    if jalur == dasar.RUTE_PESAN:
        return _pesan(penangan, principal)
    if jalur == RUTE_ULANG:
        return _ulang(penangan, principal)
    (_unggah if jalur == RUTE_UNGGAH else _tagihan)(penangan, principal)
    return True
