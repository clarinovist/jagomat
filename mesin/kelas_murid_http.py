"""Rute murid Paket Belajar 1 Bulan: orang tua memilih Private/Mini Class, membayar transfer, dan mengunggah bukti lewat akun anak.

Titik masuk GET `/murid/paket`; POST `/murid/paket/buat` (buat tagihan) dan `/murid/paket/bukti` (unggah bukti).
Pola sama dengan `harian_langganan_murid_http`; beda utama: tabel `kelas_*` ada di admin-control.db (bukan DB belajar),
jadi semua baca/tulis lewat `kelas_store.buka(admin_store.BAWAAN)` dan DB belajar hanya dipakai untuk memetakan akun
murid ke siswanya. Aturan yang ditegakkan di sini, bukan di halaman:

- Hidup HANYA bila sakelar `PAKET_BELAJAR` aktif; mati = `False` (jatuh ke penangan murid biasa: jawaban sama dengan
  jalur `/murid` tak dikenal). Dijawab SEBELUM `_lolos_sandi` seperti permukaan murid lain.
- Pembeli = akun murid sesi (`akun_id` = `principal.id_akun`); anak = siswa tertaut akun itu
  (`students.siswa_dari_akun`), BUKAN dari URL/form/kueri. Anonim, guru, dan admin tidak ditangani (False: GET 303
  /masuk, POST 401 seperti jalur murid lain).
- Form buat tagihan persis `{token, kode}`; kode hanya salah satu paket katalog dan token terikat ke kode itu.
  Nominal selalu dari katalog + deposit/keluarga di server (`kelas_store.buat_tagihan`), tidak pernah dari form. Status
  anak kedua tidak bisa dipilih pembeli (hanya admin menautkan keluarga).
- Satu tagihan terbuka per anak LINTAS paket: form bukti tidak memuat kode paket, jadi paket yang menerima bukti
  diturunkan dari tagihan terbuka sesi. Membuat tagihan paket lain saat satu masih terbuka = 409, dicek di transaksi
  tulis yang sama dengan pembuatan (`tolak_paket_lain_terbuka`), jadi dua tab tidak bisa melahirkan dua tagihan terbuka.
- Rekening belum diisi admin: GET = halaman jujur "belum dibuka", POST = 404 murid, tanpa efek.
- Unggah: laju ketat, body berbatas, multipart sempit, token, ukuran, magic bytes, lalu hambatan status; berkas
  ditulis atomik ke subfolder khusus (`kelas_berkas`) dan dihapus bila catat gagal/duplikat.
- Nama anak, kontak, id order, dan jalur berkas tidak pernah dirender; pesan galat tetap, tanpa `str(galat)`.
"""
from __future__ import annotations

import hashlib
import sqlite3

import admin_store
import admin_store_core
import bukti_berkas
import bukti_multipart
import database
import kelas_berkas as berkas
import kelas_dasar as dasar
import kelas_pages as halaman
import kelas_store as store
import paket_belajar_gate
import paket_belajar_katalog as katalog
import pesanan_alur as alur
import pesanan_dasar as d
import pesanan_http
import pesanan_rekening
from bukti_berkas import mime_dari_isi
from kontak_http import _alihkan, _baca_form
from pesanan_transfer_pages import COPY_BERKAS_BESAR, COPY_BERKAS_KOSONG, COPY_BERKAS_TAK_TERBACA, COPY_TIPE_TIDAK_DIDUKUNG
from schema_transfer import BATAS_UKURAN_BUKTI

KUNCI_FORM_BUAT = frozenset({"token", "kode"})
OVERHEAD_MULTIPART = 64 * 1024
BATAS_BODY_UNGGAH = BATAS_UKURAN_BUKTI + OVERHEAD_MULTIPART
EMBER_BUKTI = "bukti_kelas"
KODE_BENTROK = 409
KODE_BERKAS_KOSONG = 400
KODE_BERKAS_BESAR = 413
KODE_TIPE_TIDAK_DIDUKUNG = 415
KODE_TIDAK_SIAP = 503
COPY_BELUM_DIBUKA = "Pendaftaran paket belajar belum dibuka. Coba lagi nanti."
COPY_BELUM_SIAP = "Belum bisa diproses sekarang. Coba lagi nanti."
COPY_GAGAL_BUAT = "Tagihan belum bisa dibuat. Selesaikan tagihan yang sedang berjalan, atau coba lagi nanti."
COPY_KODE_HABIS = "Tagihan belum bisa dibuat sekarang. Coba lagi nanti atau hubungi tim."
COPY_TIDAK_TERIMA = "Tidak ada tagihan yang sedang menerima bukti. Daftar paket dulu, atau waktu pembayaran sudah habis."
COPY_BATAS_BUKTI = "Batas bukti untuk tagihan ini sudah tercapai. Hubungi tim bila masih perlu bantuan."
COPY_BERKAS = {"kosong": COPY_BERKAS_KOSONG, "besar": COPY_BERKAS_BESAR, "tipe": COPY_TIPE_TIDAK_DIDUKUNG,
               "terbaca": COPY_BERKAS_TAK_TERBACA}
_GET = frozenset({halaman.RUTE})
_POST = frozenset({halaman.RUTE_BUAT, halaman.RUTE_BUKTI})
_GALAT_LAYANAN = (d.PesananError, sqlite3.Error, OSError, bukti_berkas.BuktiBerkasError, ValueError,
                  admin_store_core.StoreBelumSiap)


def _pembeli(penangan):
    """(principal, siswa_id) murid yang siswanya tertaut, atau None (jatuh ke penangan murid biasa)."""
    import students
    principal = pesanan_http.principal_murid(penangan)
    if principal is None:
        return None
    with database.buka() as kon:
        siswa_id = students.siswa_dari_akun(kon, principal.pengguna)
    return None if siswa_id is None else (principal, siswa_id)


def _buka(*, tulis: bool = False):
    return store.buka(admin_store.BAWAAN, tulis_data=tulis)


def _rekening():
    """Teks rekening publik (satu baris per bagian) atau None (fail-closed bila penyimpanan rekening belum siap)."""
    try:
        publik = pesanan_rekening.baca_publik()
    except Exception:
        return None
    if publik is None:
        return None
    return "\n".join(("Bank: " + publik.nama_bank, "Nomor rekening: " + publik.nomor_label,
                      "Atas nama: " + publik.atas_nama))


def _info(penangan, judul: str, teks: str, kode: int) -> None:
    penangan._kirim_privat(halaman.halaman_info(judul, teks), kode)


def _tidak_ada(penangan) -> None:
    from support_pages import halaman_pesan_murid
    penangan._kirim(halaman_pesan_murid("404", "<h1>Halaman tidak ada</h1>"), 404)


def _token_untuk(penangan, principal):
    sesi = penangan._ambil_token()
    return lambda aksi: pesanan_http.buat_token(principal, sesi, aksi)


def _tagihan_berjalan(kon, akun_id: str, siswa_id: int, kini: str):
    """Tagihan terbuka anak ini (paket pertama di katalog yang punya), atau None."""
    for paket in katalog.DAFTAR_PAKET:
        tagihan = store.tagihan_terbuka(kon, akun_id, siswa_id, paket.kode, kini)
        if tagihan is not None:
            return tagihan
    return None


# --- GET ---------------------------------------------------------------------------------

def _kabar_aktif(kon, akun_id: str, siswa_id: int, kini: str) -> str:
    """Kalimat 'aktif sampai' untuk paket yang sedang aktif (satu per baris), atau ''."""
    kalimat = []
    for paket in katalog.DAFTAR_PAKET:
        berakhir = store.berakhir_aktif(kon, akun_id, siswa_id, paket.kode, kini)
        if berakhir is not None:
            kalimat.append(halaman.kalimat_aktif(paket.nama, berakhir))
    return " ".join(kalimat)


def _badan_get(penangan, principal, siswa_id: int, rekening: str):
    kini = alur.waktu_sekarang()
    token_untuk = _token_untuk(penangan, principal)
    with _buka() as kon:
        tagihan = _tagihan_berjalan(kon, principal.id_akun, siswa_id, kini)
        if tagihan is not None:
            return halaman.halaman_tagihan(tagihan, katalog.ambil(tagihan.kode_paket), rekening, token_untuk)
        kartu = store.kartu_paket(kon, principal.id_akun, siswa_id, kini)
        kabar = _kabar_aktif(kon, principal.id_akun, siswa_id, kini)
    return halaman.halaman_pilih_paket(kartu, None, token_untuk, kabar=kabar)


def _get_halaman(penangan, principal, siswa_id: int) -> None:
    rekening = _rekening()
    if rekening is None:
        _info(penangan, "Belum dibuka", COPY_BELUM_DIBUKA, 200)
        return
    try:
        isi = _badan_get(penangan, principal, siswa_id, rekening)
    except d.PesananTidakDitemukan:
        _tidak_ada(penangan)
        return
    except _GALAT_LAYANAN:
        _info(penangan, "Belum bisa diproses", COPY_BELUM_SIAP, KODE_TIDAK_SIAP)
        return
    penangan._kirim_privat(isi)


def tangani_get(penangan, jalur: str, jalur_penuh: str = "") -> bool:
    """GET `/murid/paket`; False bila bukan milik modul, sakelar mati, atau bukan murid tertaut."""
    if jalur not in _GET or not paket_belajar_gate.aktif():
        return False
    pembeli = _pembeli(penangan)
    if pembeli is None:
        return False
    _get_halaman(penangan, *pembeli)
    return True


# --- POST: buat tagihan ----------------------------------------------------------------------

def _form_buat(penangan, principal):
    """Kode paket sah dari form `{token, kode}` bertoken, atau None (respons penolakan sudah dikirim)."""
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM_BUAT:
        penangan._tolak_isian()
        return None
    try:
        kode = dasar.kode_paket_sah(data["kode"])
    except d.PesananDataTidakSah:
        penangan._tolak_isian()
        return None
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), halaman.AKSI_BUAT + kode, data["token"]):
        penangan._tolak_isian(403)
        return None
    return kode


def _buat(kon, akun_id: str, siswa_id: int, kode: str, kini: str) -> None:
    """Tagihan baru; paket LAIN yang masih terbuka = konflik, dicek di transaksi yang sama (atomik)."""
    store.buat_tagihan(kon, akun_id, siswa_id, kode, kini, tolak_paket_lain_terbuka=True)


def _galat_buat(penangan, galat: Exception) -> None:
    if isinstance(galat, dasar.KodeUnikHabis):
        _info(penangan, "Tagihan belum bisa dibuat", COPY_KODE_HABIS, KODE_BENTROK)
    elif isinstance(galat, d.PesananTidakDitemukan):
        _tidak_ada(penangan)
    elif isinstance(galat, d.PesananKonflik):
        _info(penangan, "Tagihan belum bisa dibuat", COPY_GAGAL_BUAT, KODE_BENTROK)
    else:
        _info(penangan, "Belum bisa diproses", COPY_BELUM_SIAP, KODE_TIDAK_SIAP)


def _post_buat(penangan, principal, siswa_id: int) -> None:
    if not pesanan_http._izinkan(penangan, principal):
        pesanan_http._tolak_laju(penangan)
        return
    kode = _form_buat(penangan, principal)
    if kode is None:
        return
    try:
        with _buka(tulis=True) as kon:
            _buat(kon, principal.id_akun, siswa_id, kode, alur.waktu_sekarang())
    except _GALAT_LAYANAN as galat:
        _galat_buat(penangan, galat)
        return
    _alihkan(penangan, halaman.RUTE)


# --- POST: unggah bukti ----------------------------------------------------------------------

def _periksa_isi(isi: bytes):
    """(kode, pesan, mime): kode/pesan terisi bila isi ditolak; mime dari MAGIC BYTES."""
    if not isi:
        return KODE_BERKAS_KOSONG, COPY_BERKAS["kosong"], None
    if len(isi) > BATAS_UKURAN_BUKTI:
        return KODE_BERKAS_BESAR, COPY_BERKAS["besar"], None
    mime = mime_dari_isi(isi)
    if mime is None:
        return KODE_TIPE_TIDAK_DIDUKUNG, COPY_BERKAS["tipe"], None
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
        _info(penangan, "Berkas tidak terbaca", COPY_BERKAS["terbaca"], 400)
        return None
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), halaman.AKSI_BUKTI, form.token):
        penangan._tolak_isian(403)
        return None
    return form


def _simpan_dan_catat(kon, akun_id: str, siswa_id: int, kode_paket: str, isi: bytes, mime: str, kini: str) -> None:
    """Tulis berkas atomik lalu catat; gagal atau duplikat -> berkas dihapus."""
    nama = berkas.simpan(isi)
    try:
        hasil = store.catat_bukti(kon, akun_id, siswa_id, kode_paket, mime, len(isi),
                                  hashlib.sha256(isi).hexdigest(), nama, kini)
    except BaseException:
        berkas.hapus(nama)
        raise
    if not hasil["baru"]:
        berkas.hapus(nama)


def _hambatan(tagihan):
    """Pesan ramah bila PASTI tidak ada tagihan yang menerima bukti sekarang; None bila boleh dicoba."""
    if tagihan is None:
        return COPY_TIDAK_TERIMA
    return COPY_BATAS_BUKTI if tagihan.jumlah_bukti >= dasar.MAKS_BUKTI else None


def _unggah_sah(penangan, akun_id: str, siswa_id: int, form) -> None:
    kode, pesan, mime = _periksa_isi(form.isi)
    if kode is not None:
        _info(penangan, "Berkas belum bisa diterima", pesan, kode)
        return
    kini = alur.waktu_sekarang()
    with _buka(tulis=True) as kon:
        tagihan = _tagihan_berjalan(kon, akun_id, siswa_id, kini)
        hambatan = _hambatan(tagihan)
        if hambatan is not None:
            _info(penangan, "Bukti belum bisa diterima", hambatan, KODE_BENTROK)
            return
        _simpan_dan_catat(kon, akun_id, siswa_id, tagihan.kode_paket, form.isi, mime, kini)
    _alihkan(penangan, halaman.RUTE)


def _post_bukti(penangan, principal, siswa_id: int) -> None:
    if not pesanan_http._izinkan(penangan, principal, ketat=True, ember=EMBER_BUKTI):
        penangan.close_connection = True
        pesanan_http._tolak_laju(penangan)
        return
    form = _baca_unggahan(penangan, principal)
    if form is None:
        return
    try:
        _unggah_sah(penangan, principal.id_akun, siswa_id, form)
    except dasar.BatasBukti:
        _info(penangan, "Batas bukti tercapai", COPY_BATAS_BUKTI, KODE_BENTROK)
    except d.PesananTidakDitemukan:
        _tidak_ada(penangan)
    except dasar.KelasKonflik:
        _info(penangan, "Bukti belum bisa diterima", COPY_TIDAK_TERIMA, KODE_BENTROK)
    except _GALAT_LAYANAN:
        _info(penangan, "Belum bisa diproses", COPY_BELUM_SIAP, KODE_TIDAK_SIAP)


def tangani_post(penangan, jalur: str) -> bool:
    """POST buat tagihan / unggah bukti; False bila bukan milik modul, sakelar mati, atau bukan murid tertaut."""
    if jalur not in _POST or not paket_belajar_gate.aktif():
        return False
    pembeli = _pembeli(penangan)
    if pembeli is None:
        return False
    if _rekening() is None:  # gerbang pembayaran tertutup: 404 murid, tanpa efek
        _tidak_ada(penangan)
        return True
    (_post_buat if jalur == halaman.RUTE_BUAT else _post_bukti)(penangan, *pembeli)
    return True
