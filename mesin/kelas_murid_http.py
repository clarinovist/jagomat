"""Rute murid Paket Belajar 1 Bulan: orang tua memilih Private/Mini Class, membayar transfer, dan mengunggah bukti lewat akun anak.

Titik masuk GET `/murid/paket` (SELALU daftar paket; di atasnya satu kartu per tagihan terbuka), GET `/murid/paket/tagihan?kode=`
(halaman tagihan satu paket), GET `/murid/paket/hapus?kode=` (konfirmasi hapus), POST `/murid/paket/buat` (buat tagihan, atau
memulihkan tagihan yang baru dihapus), POST `/murid/paket/bukti?kode=` (unggah bukti), POST `/murid/paket/hapus` (hapus tagihan
belum bayar) dan `/murid/paket/jadwal` (orang tua memilih kelompok Mini sekali saja; aturan di `jadwal_pilih`) dan GET
`/murid/paket/kalender.ics` (jadwal pertemuan anak sebagai berkas iCalendar; tanpa jadwal = 404 identik). Pola sama dengan
`harian_langganan_murid_http`; beda utama: tabel `kelas_*` ada di admin-control.db (bukan DB belajar), jadi semua baca/tulis lewat
`kelas_store.buka(admin_store.BAWAAN)` dan DB belajar hanya dipakai untuk memetakan akun murid ke siswanya. Aturan yang
ditegakkan di sini, bukan di halaman:

- Hidup HANYA bila sakelar `PAKET_BELAJAR` aktif; mati = `False` (jatuh ke penangan murid biasa: jawaban sama dengan
  jalur `/murid` tak dikenal). Dijawab SEBELUM `_lolos_sandi` seperti permukaan murid lain.
- Pembeli = akun murid sesi (`akun_id` = `principal.id_akun`); anak = siswa tertaut akun itu
  (`students.siswa_dari_akun`), BUKAN dari URL/form/kueri. Anonim, guru, dan admin tidak ditangani (False: GET 303
  /masuk, POST 401 seperti jalur murid lain).
- Tagihan dikenali lewat KODE PAKET (allowlist katalog), bukan id order. Satu tagihan terbuka per (anak, paket) dijamin DB;
  beberapa paket BERBEDA boleh terbuka bersamaan. Kode asing: 400 pada form POST, 404 pada GET dan unggah, sebelum DB.
- Form buat dan hapus persis `{token, kode}`, token terikat aksi + kode. Unggah: kode di kueri `?kode=`, form persis
  `{token, berkas}`, token terikat `kelas_bukti:` + kode. Nominal selalu dari katalog + deposit di server
  (`kelas_store.buat_tagihan`), tidak pernah dari form.
- Memilih lagi paket yang tagihannya baru dihapus memulihkan tagihan itu (`kelas_store.buat_tagihan`); bila deposit Peta
  sudah dipakai tagihan lain, 409 dengan pesan yang menyebut waktu bayar tagihan sebelumnya.
- Hapus tagihan (`kelas_batal`): hanya tagihan belum bayar tanpa bukti, dan hanya bila tabel catatan sudah dipasang (tanpa itu
  tautan tidak tampil dan POST ditolak tanpa tulis). Akun lain, anak lain, dan tanpa tagihan terbuka = 404 identik.
- Rekening belum diisi admin: GET = halaman jujur "belum dibuka", POST, GET tagihan, dan GET hapus = 404 murid, tanpa efek.
- Unggah: laju ketat, body berbatas, multipart sempit, token, ukuran, magic bytes, lalu hambatan status; berkas
  ditulis atomik ke subfolder khusus (`kelas_berkas`) dan dihapus bila catat gagal/duplikat.
- Kartu jadwal pertemuan (halaman pilih, paket aktif) memakai order milik akun + anak sesi saja (`jadwal_terbaru_murid`)
  dan GAGAL-DIAM: jadwal belum dipasang/rusak = tanpa kartu, halaman dan galat tagihan tidak terpengaruh. Hanya
  lokasi dan waktu pertemuan; tidak ada guru atau id.
- Nama anak, kontak, id order, dan jalur berkas tidak pernah dirender; pesan galat tetap, tanpa `str(galat)`.
"""
from __future__ import annotations

import hashlib
import sqlite3
import urllib.parse

import admin_security
import admin_store
import admin_store_core
import bukti_berkas
import bukti_multipart
import database
import jadwal_anak_baca
import jadwal_dasar
import jadwal_pilih
import jadwal_private_murid_http as jpm
import jadwal_store
import kalender_ics
import kelas_batal
import kelas_berkas as berkas
import kelas_catatan as cat
import kelas_dasar as dasar
import kelas_status as ks
import kelas_pages as halaman
import kelas_private_pages as priv
import kelas_store as store
import paket_belajar_gate
import paket_belajar_katalog as katalog
import pesanan_alur as alur
import tirai_aksi
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
KODE_TIRAI = 403
COPY_BELUM_DIBUKA = "Pendaftaran paket belajar belum dibuka. Coba lagi nanti."
COPY_BELUM_SIAP = "Belum bisa diproses sekarang. Coba lagi nanti."
COPY_KONFLIK_PILIH = ("Paket ini belum bisa dipilih lagi sampai waktu bayar tagihan sebelumnya habis. "
                      "Hubungi tim bila masih perlu bantuan.")
COPY_GAGAL_HAPUS = "Tagihan ini belum bisa dihapus. Bila sudah ada bukti transfer, hubungi tim sebelum mengubah apa pun."
COPY_GAGAL_PILIH_JADWAL = ("Kelompok itu belum bisa dipilih. Mungkin sudah penuh atau ditutup, atau jadwal anak sudah ditentukan. "
                          "Muat ulang halaman, atau hubungi tim bila masih perlu bantuan.")
COPY_TIRAI_TERTUTUP = tirai_aksi.COPY_TERTUTUP
COPY_TIRAI_KABAR = ("Halaman ini terkunci PIN. Minta Ayah/Bunda membuka Halaman Ayah/Bunda dulu sebelum memilih paket, "
                    "jadwal, atau mengunggah bukti.")
COPY_DEPOSIT_TIDAK_SAH = "Tagihan belum bisa dibuat sekarang. Coba lagi nanti atau hubungi tim."
COPY_KODE_HABIS = "Tagihan belum bisa dibuat sekarang. Coba lagi nanti atau hubungi tim."
COPY_TIDAK_TERIMA = "Tidak ada tagihan yang sedang menerima bukti. Daftar paket dulu, atau waktu pembayaran sudah habis."
COPY_BATAS_BUKTI = "Batas bukti untuk tagihan ini sudah tercapai. Hubungi tim bila masih perlu bantuan."
COPY_BERKAS = {"kosong": COPY_BERKAS_KOSONG, "besar": COPY_BERKAS_BESAR, "tipe": COPY_TIPE_TIDAK_DIDUKUNG,
               "terbaca": COPY_BERKAS_TAK_TERBACA}
_GET = frozenset({halaman.RUTE, halaman.RUTE_TAGIHAN, halaman.RUTE_HAPUS, halaman.RUTE_KALENDER})
_POST = frozenset({halaman.RUTE_BUAT, halaman.RUTE_BUKTI, halaman.RUTE_HAPUS, halaman.RUTE_JADWAL,
                   priv.RUTE_AJUKAN, priv.RUTE_BATAL})
KUNCI_FORM_JADWAL = frozenset({"token", "kelompok"})
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


def _tirai_tertutup(penangan, principal, siswa_id: int) -> bool:
    """Tindakan di halaman paket (daftar, jadwal, bukti, hapus) mengikuti tirai PIN orang tua (lihat `tirai_aksi`)."""
    return tirai_aksi.tertutup(penangan, principal, siswa_id)


def _kode_kueri(jalur_penuh: str):
    """Kode paket dari kueri `?kode=` bila sah (allowlist katalog); None bila tak ada atau asing. Sebelum DB."""
    nilai = (urllib.parse.parse_qs(urllib.parse.urlsplit(jalur_penuh).query).get("kode") or [""])[0]
    try:
        return dasar.kode_paket_sah(nilai)
    except d.PesananDataTidakSah:
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


def _dibatalkan_per_paket(kon, akun_id: str, siswa_id: int, kini: str) -> dict:
    """{kode paket: batas waktu bayar} untuk tagihan yang baru dihapus dan masih dalam jendela (bisa dipilih lagi)."""
    hasil = {}
    for paket in katalog.DAFTAR_PAKET:
        ada = ks.order_dibatalkan(kon, akun_id, siswa_id, paket.kode, kini)
        if ada is not None:
            hasil[paket.kode] = ada[0]["kedaluwarsa"]
    return hasil


def _bacaan_daftar(kon, akun_id: str, siswa_id: int, kini: str):
    """Bacaan DB halaman daftar: tagihan terbuka, kartu paket, paket yang baru dihapus, tabel catatan terpasang, dan kabar."""
    return (store.tagihan_terbuka_semua(kon, akun_id, siswa_id, kini),
            store.kartu_paket(kon, akun_id, siswa_id, kini),
            _dibatalkan_per_paket(kon, akun_id, siswa_id, kini),
            cat.terpasang(kon),
            _kabar_aktif(kon, akun_id, siswa_id, kini))


def _jadwal_anak(akun_id: str, siswa_id: int, kini: str):
    """Jadwal pertemuan anak ini (order aktif terbaru berpenempatan) atau None.

    Fail-silent HANYA untuk bagian jadwal: belum dipasang, struktur rusak, atau galat baca = tanpa kartu supaya
    fitur tambahan ini tidak pernah merusak halaman tagihan. Dipanggil sesudah pembacaan tagihan selesai.
    """
    try:
        with jadwal_store.buka(admin_store.BAWAAN) as kon:
            return jadwal_store.jadwal_terbaru_murid(kon, akun_id, siswa_id, kini)
    except (admin_store_core.StoreBelumSiap, sqlite3.Error, ValueError):
        return None


def _pilihan_jadwal(akun_id: str, siswa_id: int, kini: str):
    """Kelompok yang boleh dipilih orang tua, atau () (gagal-diam seperti kartu jadwal: tidak pernah merusak halaman)."""
    try:
        with jadwal_store.buka(admin_store.BAWAAN) as kon:
            return jadwal_pilih.pilihan_untuk(kon, akun_id, siswa_id, kini)
    except (admin_store_core.StoreBelumSiap, sqlite3.Error, ValueError, d.PesananError):
        return ()


def _badan_get(penangan, principal, siswa_id: int, rekening: str):
    """Halaman daftar paket: selalu tampil; kartu tagihan terbuka di atasnya dan jadwal/pilihan bila tirai terbuka."""
    kini = alur.waktu_sekarang()
    token_untuk = _token_untuk(penangan, principal)
    with _buka() as kon:
        tagihan, kartu, dibatalkan, bisa_hapus, kabar = _bacaan_daftar(kon, principal.id_akun, siswa_id, kini)
    jadwal = _jadwal_anak(principal.id_akun, siswa_id, kini)
    tertutup = _tirai_tertutup(penangan, principal, siswa_id)
    tampil_hapus = bisa_hapus and not tertutup
    if tertutup:
        kabar = (kabar + " " if kabar else "") + COPY_TIRAI_KABAR
        pilihan, privat = (), ""
    else:
        pilihan = _pilihan_jadwal(principal.id_akun, siswa_id, kini)
        privat = jpm.kartu_untuk(principal.id_akun, siswa_id, kini, token_untuk)
    return halaman.halaman_pilih_paket(kartu, tagihan, token_untuk, kabar=kabar, jadwal=jadwal,
                                       pilihan_jadwal=pilihan, privat=privat, dibatalkan=dibatalkan,
                                       boleh_hapus=tampil_hapus)


def _badan_tagihan(principal, siswa_id: int, kode: str, rekening: str, token_untuk):
    """Halaman tagihan satu paket bila tagihan terbuka milik akun dan anak ini; selain itu PesananTidakDitemukan."""
    kini = alur.waktu_sekarang()
    with _buka() as kon:
        tagihan = store.tagihan_terbuka(kon, principal.id_akun, siswa_id, kode, kini)
    if tagihan is None:
        raise d.PesananTidakDitemukan()
    return halaman.halaman_tagihan(tagihan, katalog.ambil(kode), rekening, token_untuk)


def _badan_hapus(principal, siswa_id: int, kode: str, token_untuk):
    """Konfirmasi hapus hanya untuk tagihan belum bayar tanpa bukti, dengan tabel catatan terpasang; selain itu tak ada."""
    kini = alur.waktu_sekarang()
    with _buka() as kon:
        tagihan = store.tagihan_terbuka(kon, principal.id_akun, siswa_id, kode, kini)
        bisa_hapus = cat.terpasang(kon)
    if tagihan is None or not bisa_hapus or tagihan.status != dasar.STATUS_BELUM_BAYAR or tagihan.jumlah_bukti:
        raise d.PesananTidakDitemukan()
    return halaman.halaman_konfirmasi_hapus(tagihan, katalog.ambil(kode), token_untuk)


def _kirim_get(penangan, badan) -> None:
    """Kirim isi halaman GET; tanpa tagihan/identitas = 404 murid identik; galat layanan = 503 tanpa rincian."""
    try:
        isi = badan()
    except d.PesananTidakDitemukan:
        _tidak_ada(penangan)
        return
    except _GALAT_LAYANAN:
        _info(penangan, "Belum bisa diproses", COPY_BELUM_SIAP, KODE_TIDAK_SIAP)
        return
    penangan._kirim_privat(isi)


def _get_halaman(penangan, principal, siswa_id: int, jalur_penuh: str = "") -> None:
    rekening = _rekening()
    if rekening is None:
        _info(penangan, "Belum dibuka", COPY_BELUM_DIBUKA, 200)
        return
    _kirim_get(penangan, lambda: _badan_get(penangan, principal, siswa_id, rekening))


def _get_tagihan(penangan, principal, siswa_id: int, jalur_penuh: str = "") -> None:
    kode = _kode_kueri(jalur_penuh)
    if kode is None:
        _tidak_ada(penangan)
        return
    rekening = _rekening()
    if rekening is None:
        _info(penangan, "Belum dibuka", COPY_BELUM_DIBUKA, 200)
        return
    token_untuk = _token_untuk(penangan, principal)
    _kirim_get(penangan, lambda: _badan_tagihan(principal, siswa_id, kode, rekening, token_untuk))


def _get_hapus(penangan, principal, siswa_id: int, jalur_penuh: str = "") -> None:
    kode = _kode_kueri(jalur_penuh)
    if kode is None or _rekening() is None:
        _tidak_ada(penangan)
        return
    token_untuk = _token_untuk(penangan, principal)
    _kirim_get(penangan, lambda: _badan_hapus(principal, siswa_id, kode, token_untuk))


# --- GET kalender ------------------------------------------------------------------------------

def _jadwal_kalender(akun_id: str, siswa_id: int, kini: str):
    """(kunci order, jadwal) penempatan order aktif terbaru anak ini, atau None. Baca-saja; galat baca = None."""
    try:
        with jadwal_store.buka(admin_store.BAWAAN) as kon:
            order_id = jadwal_anak_baca.order_penempatan_murid(kon, akun_id, siswa_id, kini)
            jadwal = None if order_id is None else jadwal_store.jadwal_untuk_murid(kon, order_id)
    except (admin_store_core.StoreBelumSiap, sqlite3.Error, ValueError, d.PesananError):
        return None
    return None if jadwal is None else (order_id, jadwal)


def _header_kalender(panjang: int) -> dict:
    return {**admin_security.header_privat(), "Content-Type": "text/calendar; charset=utf-8",
            "Content-Length": str(panjang), "Vary": "Cookie", "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'attachment; filename="%s"' % kalender_ics.NAMA_BERKAS}


def _kirim_kalender(penangan, isi: bytes) -> None:
    penangan.send_response(200)
    for nama, nilai in _header_kalender(len(isi)).items():
        penangan.send_header(nama, nilai)
    penangan.end_headers()
    penangan.wfile.write(isi)


def _get_kalender(penangan, principal, siswa_id: int, jalur_penuh: str = "") -> None:
    """Jadwal pertemuan anak sebagai berkas .ics. Tanpa jadwal = 404 identik rute tak dikenal; data rusak = 503 tanpa rincian."""
    kini = dasar.ke_baku(alur.waktu_sekarang())
    ada = _jadwal_kalender(principal.id_akun, siswa_id, kini)
    if ada is None:
        _tidak_ada(penangan)
        return
    try:
        isi = kalender_ics.bangun(ada[0], ada[1], kini)
    except (ValueError, KeyError):
        _info(penangan, "Belum bisa diproses", COPY_BELUM_SIAP, KODE_TIDAK_SIAP)
        return
    _kirim_kalender(penangan, isi)


_GET_HALAMAN = {halaman.RUTE: _get_halaman, halaman.RUTE_TAGIHAN: _get_tagihan, halaman.RUTE_HAPUS: _get_hapus,
                halaman.RUTE_KALENDER: _get_kalender}


def tangani_get(penangan, jalur: str, jalur_penuh: str = "") -> bool:
    """GET `/murid/paket`, `/tagihan`, dan `/hapus`; False bila bukan milik modul, sakelar mati, atau bukan murid tertaut."""
    if jalur not in _GET or not paket_belajar_gate.aktif():
        return False
    pembeli = _pembeli(penangan)
    if pembeli is None:
        return False
    _GET_HALAMAN[jalur](penangan, *pembeli, jalur_penuh)
    return True


# --- POST: buat tagihan ----------------------------------------------------------------------

def _form_buat(penangan, principal, aksi: str = halaman.AKSI_BUAT):
    """Kode paket sah dari form `{token, kode}` bertoken (`aksi` + kode), atau None (respons penolakan sudah dikirim).

    Dipakai juga untuk hapus tagihan (`halaman.AKSI_HAPUS`): bentuk form dan pengikatan token sama.
    """
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM_BUAT:
        penangan._tolak_isian()
        return None
    try:
        kode = dasar.kode_paket_sah(data["kode"])
    except d.PesananDataTidakSah:
        penangan._tolak_isian()
        return None
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), aksi + kode, data["token"]):
        penangan._tolak_isian(403)
        return None
    return kode


def _galat_buat(penangan, galat: Exception) -> None:
    if isinstance(galat, dasar.KodeUnikHabis):
        _info(penangan, "Tagihan belum bisa dibuat", COPY_KODE_HABIS, KODE_BENTROK)
    elif isinstance(galat, dasar.DepositTidakSah):  # sebelum cabang PesananKonflik: bukan soal "menunggu pembayaran"
        _info(penangan, "Tagihan belum bisa dibuat", COPY_DEPOSIT_TIDAK_SAH, KODE_TIDAK_SIAP)
    elif isinstance(galat, d.PesananTidakDitemukan):
        _tidak_ada(penangan)
    elif isinstance(galat, d.PesananKonflik):
        _info(penangan, "Paket belum bisa dipilih", COPY_KONFLIK_PILIH, KODE_BENTROK)
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
            store.buat_tagihan(kon, principal.id_akun, siswa_id, kode, alur.waktu_sekarang())
    except _GALAT_LAYANAN as galat:
        _galat_buat(penangan, galat)
        return
    _alihkan(penangan, halaman.RUTE)


# --- POST: hapus tagihan ---------------------------------------------------------------------

def _galat_hapus(penangan, galat: Exception) -> None:
    if isinstance(galat, d.PesananTidakDitemukan):
        _tidak_ada(penangan)
    elif isinstance(galat, d.PesananKonflik):
        _info(penangan, "Tagihan belum bisa dihapus", COPY_GAGAL_HAPUS, KODE_BENTROK)
    else:
        _info(penangan, "Belum bisa diproses", COPY_BELUM_SIAP, KODE_TIDAK_SIAP)


def _post_hapus(penangan, principal, siswa_id: int) -> None:
    """Hapus tagihan belum bayar tanpa bukti; kepemilikan, keadaan, dan tabel catatan dicek di transaksi yang sama."""
    if not pesanan_http._izinkan(penangan, principal):
        pesanan_http._tolak_laju(penangan)
        return
    kode = _form_buat(penangan, principal, halaman.AKSI_HAPUS)
    if kode is None:
        return
    try:
        with _buka(tulis=True) as kon:
            kelas_batal.batalkan_tagihan(kon, principal.id_akun, siswa_id, kode, alur.waktu_sekarang())
    except _GALAT_LAYANAN as galat:
        _galat_hapus(penangan, galat)
        return
    _alihkan(penangan, halaman.RUTE)


# --- POST: pilih jadwal kelompok -----------------------------------------------------------

def _form_jadwal(penangan, principal):
    """Id kelompok sah dari form `{token, kelompok}` bertoken (`AKSI_JADWAL` + kelompok), atau None (respons sudah dikirim)."""
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM_JADWAL:
        penangan._tolak_isian()
        return None
    try:
        kelompok = jadwal_dasar.periksa_kelompok_id(data["kelompok"])
    except d.PesananDataTidakSah:
        penangan._tolak_isian()
        return None
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), halaman.AKSI_JADWAL + kelompok, data["token"]):
        penangan._tolak_isian(403)
        return None
    return kelompok


def _post_jadwal(penangan, principal, siswa_id: int) -> None:
    """Orang tua memilih kelompok Mini sekali saja; semua syarat dicek di transaksi penempatan."""
    if not pesanan_http._izinkan(penangan, principal):
        pesanan_http._tolak_laju(penangan)
        return
    kelompok = _form_jadwal(penangan, principal)
    if kelompok is None:
        return
    try:
        with jadwal_store.buka(admin_store.BAWAAN, tulis_data=True) as kon:
            jadwal_pilih.pilih_kelompok(kon, principal.id_akun, siswa_id, kelompok, alur.waktu_sekarang())
    except d.PesananTidakDitemukan:
        _tidak_ada(penangan)
        return
    except d.PesananKonflik:
        _info(penangan, "Kelompok belum bisa dipilih", COPY_GAGAL_PILIH_JADWAL, KODE_BENTROK)
        return
    except _GALAT_LAYANAN:
        _info(penangan, "Belum bisa diproses", COPY_BELUM_SIAP, KODE_TIDAK_SIAP)
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


def _baca_unggahan(penangan, principal, kode: str):
    """BuktiForm sah dari body multipart, atau None (respons penolakan sudah dikirim). Token terikat `kelas_bukti:` + kode."""
    tubuh = penangan._baca_tubuh(BATAS_BODY_UNGGAH)
    if tubuh is None:
        penangan.close_connection = True
        penangan._tolak_isian(KODE_BERKAS_BESAR)
        return None
    form = bukti_multipart.parse(tubuh, penangan.headers.get("Content-Type", ""))
    if form is None:
        _info(penangan, "Berkas tidak terbaca", COPY_BERKAS["terbaca"], 400)
        return None
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), halaman.AKSI_BUKTI + kode, form.token):
        penangan._tolak_isian(403)
        return None
    return form


def _simpan_dan_catat(kon, akun_id: str, siswa_id: int, kode: str, isi: bytes, mime: str, kini: str) -> None:
    """Tulis berkas atomik lalu catat ke tagihan paket `kode`; gagal atau duplikat -> berkas dihapus."""
    nama = berkas.simpan(isi)
    try:
        hasil = store.catat_bukti(kon, akun_id, siswa_id, kode, mime, len(isi),
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


def _unggah_sah(penangan, akun_id: str, siswa_id: int, kode: str, form) -> None:
    kode_galat, pesan, mime = _periksa_isi(form.isi)
    if kode_galat is not None:
        _info(penangan, "Berkas belum bisa diterima", pesan, kode_galat)
        return
    kini = alur.waktu_sekarang()
    with _buka(tulis=True) as kon:
        hambatan = _hambatan(store.tagihan_terbuka(kon, akun_id, siswa_id, kode, kini))
        if hambatan is not None:
            _info(penangan, "Bukti belum bisa diterima", hambatan, KODE_BENTROK)
            return
        _simpan_dan_catat(kon, akun_id, siswa_id, kode, form.isi, mime, kini)
    _alihkan(penangan, halaman.RUTE)


def _post_bukti(penangan, principal, siswa_id: int) -> None:
    kode = _kode_kueri(penangan.path)
    if kode is None:
        penangan.close_connection = True  # body belum dibaca: tutup koneksi agar tidak tersisa di soket
        _tidak_ada(penangan)
        return
    if not pesanan_http._izinkan(penangan, principal, ketat=True, ember=EMBER_BUKTI):
        penangan.close_connection = True
        pesanan_http._tolak_laju(penangan)
        return
    form = _baca_unggahan(penangan, principal, kode)
    if form is None:
        return
    try:
        _unggah_sah(penangan, principal.id_akun, siswa_id, kode, form)
    except dasar.BatasBukti:
        _info(penangan, "Batas bukti tercapai", COPY_BATAS_BUKTI, KODE_BENTROK)
    except d.PesananTidakDitemukan:
        _tidak_ada(penangan)
    except dasar.KelasKonflik:
        _info(penangan, "Bukti belum bisa diterima", COPY_TIDAK_TERIMA, KODE_BENTROK)
    except _GALAT_LAYANAN:
        _info(penangan, "Belum bisa diproses", COPY_BELUM_SIAP, KODE_TIDAK_SIAP)


_POST_HALAMAN = {halaman.RUTE_BUAT: _post_buat, halaman.RUTE_BUKTI: _post_bukti, halaman.RUTE_HAPUS: _post_hapus,
                 halaman.RUTE_JADWAL: _post_jadwal, priv.RUTE_AJUKAN: jpm.post_ajukan, priv.RUTE_BATAL: jpm.post_batal}


def tangani_post(penangan, jalur: str) -> bool:
    """POST buat tagihan, unggah bukti, hapus tagihan, dan jadwal; False bila bukan milik modul, sakelar mati, atau bukan murid tertaut."""
    if jalur not in _POST or not paket_belajar_gate.aktif():
        return False
    pembeli = _pembeli(penangan)
    if pembeli is None:
        return False
    if _rekening() is None:  # gerbang pembayaran tertutup: 404 murid, tanpa efek
        _tidak_ada(penangan)
        return True
    if _tirai_tertutup(penangan, *pembeli):  # PIN terpasang dan tirai tertutup: tanpa efek
        _info(penangan, "Untuk Ayah/Bunda", COPY_TIRAI_TERTUTUP, KODE_TIRAI)
        return True
    _POST_HALAMAN[jalur](penangan, *pembeli)
    return True
