"""Rute admin Paket Belajar 1 Bulan: antrean `/admin/kelas`, detail `/verifikasi`, pratinjau `/bukti`, aksi `/setujui`
dan `/tolak`.

Dijawab `admin_http` sebelum palang guru, jadi anonim, murid, dan guru menerima 404 yang sama dengan rute admin tak
dikenal SEBELUM DB atau berkas disentuh. Rute admin TIDAK bergantung pada sakelar `PAKET_BELAJAR`: antrean tetap
terbuka walau sakelar mati supaya bukti transfer yang sudah masuk tetap bisa diputuskan (hanya rute murid yang
404 saat sakelar mati). Data ada di admin-control.db (`kelas_store.buka`), bukan DB belajar. Aturan aksi (pola uang
yang sama dengan verifikasi transfer dan Latihan Harian):

- CSRF + tinjauan bertanda tangan terikat aksi dan sesi + sandi admin ulang (`h._token_final`), wajib sesi berkuki.
  `order_id` dan bukti terakhir yang dilihat admin HANYA dari tinjauan (`target_id`, `target_revisi`); `admin_id`
  dari principal sesi. Field lain (admin_id, order_id, nominal, paket) = 400. Keputusan hanya sah atas bukti terbaru
  yang dilihat admin (bukti baru = 409). Setujui tanpa field; Tolak hanya `alasan` (wajib).
- Setujui menulis verifikasi, akses, dan pemakaian deposit dalam satu transaksi (`kelas_putusan`). Deposit yang tidak
  lagi berlaku = pesan jelas khusus (tolak bukti, minta pembeli mendaftar ulang); TIDAK ada yang disetujui.
- Pratinjau memakai pembaca berkas dan header yang sama dengan bukti Paket Coba (tipe dari ledger dan magic bytes,
  `nosniff`, CSP ketat, nama unduhan generik); berkas dari subfolder `kelas`. Id bukti = bilangan ledger.
- Tidak ada `str(galat)` di respons; PRG 303 dengan kode hasil dari enum tetap.
"""
from __future__ import annotations

import sqlite3

import admin_http as h
import admin_pesanan_aksi as aksi
import admin_pesanan_pages as daftar_ui
import admin_security
import admin_store
import admin_verifikasi_http as bukti_umum
import bukti_berkas
import kelas_admin_pages as ui
import kelas_berkas as berkas
import kelas_dasar as dasar
import kelas_peserta
import kelas_putusan as putusan
import kelas_store as store
import jadwal_admin_http as jadwal_http
import jadwal_admin_pages as jadwal_ui
import jadwal_store
import paket_belajar_katalog as katalog
import pesanan
import pesanan_alur as alur
from schema_transfer import BATAS_UKURAN_BUKTI, MIME_BUKTI

HASIL_SETUJU = "kelas_setuju"
HASIL_TOLAK = "kelas_tolak"
PESAN_HASIL = {HASIL_SETUJU: "Bukti disetujui. Paket langsung aktif.",
               HASIL_TOLAK: "Bukti ditolak. Pembeli dapat mengunggah ulang selama waktu pembayaran terbuka."}
COPY_DEPOSIT_TIDAK_AKTIF = ("Deposit pembeli tidak lagi berlaku; tolak bukti ini dan minta pembeli mendaftar ulang "
                            "(nominal baru). Tidak ada yang disetujui.")
RUTE_GET = frozenset({ui.RUTE, ui.RUTE_VERIFIKASI, ui.RUTE_BUKTI})
_AKSI_POST = {ui.RUTE_SETUJUI: ui.AKSI_SETUJUI, ui.RUTE_TOLAK: ui.AKSI_TOLAK}
_GALAT_BACA = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError)


def _buka(*, tulis: bool = False):
    return store.buka(h._path_admin(), tulis_data=tulis)


def _kirim(penangan, principal, isi: str, kode: int = 200) -> None:
    if h._principal_admin(penangan) != principal:
        return h._tidak_ada(penangan)
    h._kirim_privat(penangan, h._halaman_admin(
        principal, ui.SECTION, isi, penangan=penangan, skrip=True, judul=ui.JUDUL, subjudul=ui.SUBJUDUL,
    ), kode, skrip=True)


def _token_form(penangan, principal, kode_aksi: str, isi: dict):
    """(csrf, tinjauan) untuk satu form, hanya untuk sesi berkuki; selain itu None."""
    if principal.metode != "cookie":
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    return h._csrf(akun, sesi), admin_security.buat_tinjauan(akun, sesi, kode_aksi, isi)


# --- antrean dan detail -----------------------------------------------------------------------

def _get_antrean(penangan, principal) -> None:
    try:
        hasil = h._query(penangan, diizinkan={"hasil"}).get("hasil")
        if hasil is not None and hasil not in PESAN_HASIL:
            raise ValueError("hasil tidak sah")
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        with _buka() as kon:
            daftar = store.antrean(kon)
            peserta = kelas_peserta.daftar_peserta_aktif(kon, alur.waktu_sekarang())
            try:
                kelompok = jadwal_store.daftar_kelompok(kon, alur.waktu_sekarang())
            except (sqlite3.OperationalError, ValueError):
                kelompok = None
        # Token dibuat di dalam try: bentuk_token bisa melempar PermissionError (sesi cookie tanpa token) -> 403.
        token_jadwal = jadwal_http.bentuk_token(penangan, principal, jadwal_http.AKSI_BUAT, {"section": ui.SECTION})
    except PermissionError:
        return h._galat(penangan, 403, daftar_ui.COPY_GALAT_FORM)
    except _GALAT_BACA:
        return _kirim(penangan, principal, daftar_ui.halaman_tidak_siap(), 503)
    isi = ui.halaman_antrean(daftar, PESAN_HASIL.get(hasil, "")) + ui.blok_peserta(peserta)
    if kelompok is not None and token_jadwal is not None:
        try:
            guru = jadwal_http.guru_map()
        except (OSError, ValueError):
            guru = {}
        isi += jadwal_ui.blok_daftar(kelompok, guru, token_jadwal)
    _kirim(penangan, principal, isi)


def _order_query(penangan) -> str:
    query = h._query(penangan, diizinkan={"order"})
    return dasar.periksa_order_id(query.get("order"))


def _forms(penangan, principal, detail):
    """{'setujui': (csrf, tinjauan), 'tolak': ...} hanya untuk order menunggu dan sesi berkuki."""
    if principal.metode != "cookie" or detail["status"] != dasar.STATUS_MENUNGGU:
        return None
    isi = {"target_id": detail["order_id"], "target_revisi": detail["bukti_terakhir_id"]}
    return {nama: _token_form(penangan, principal, kode, isi)
            for nama, kode in (("setujui", ui.AKSI_SETUJUI), ("tolak", ui.AKSI_TOLAK))}


def _tampilan(detail):
    """(ItemAntrean, TagihanKelas, [BuktiView]) dari hasil `putusan.detail` (kamus ledger) untuk renderer murni."""
    bukti = detail["bukti"]
    terakhir = max((b["diunggah"] for b in bukti), default="")
    item = katalog.ItemAntrean(detail["order_id"], detail["siswa_id"], detail["kode_paket"], detail["total"], terakhir)
    tagihan = katalog.TagihanKelas(detail["order_id"], detail["kode_paket"], detail["rincian"], detail["kode_unik"],
                                   detail["total"], detail["status"], None, len(bukti), None)
    return item, tagihan, [ui.BuktiView(str(b["id"]), b["diunggah"], b["ukuran"], b["mime"]) for b in bukti]


def _get_detail(penangan, principal) -> None:
    try:
        order_id = _order_query(penangan)
    except (ValueError, pesanan.PesananDataTidakSah):
        return h._tidak_ada(penangan)
    try:
        with _buka() as kon:
            detail = putusan.detail(kon, order_id, alur.waktu_sekarang())
        forms = None if detail is None else _forms(penangan, principal, detail)
    except PermissionError:
        return h._galat(penangan, 403, daftar_ui.COPY_GALAT_FORM)
    except _GALAT_BACA:
        return _kirim(penangan, principal, daftar_ui.halaman_tidak_siap(), 503)
    if detail is None:
        return h._tidak_ada(penangan)
    isi = ui.halaman_detail(*_tampilan(detail), forms, baca_saja=principal.metode != "cookie")
    if principal.metode == "cookie":
        kelompok, ringkas, tersedia = [], None, False
        try:
            with jadwal_http._buka() as kon_jadwal:
                kelompok = jadwal_store.daftar_kelompok(kon_jadwal, alur.waktu_sekarang())
                ringkas = jadwal_store.ringkas_order(kon_jadwal, order_id)
                tersedia = True
        except (admin_store.StoreBelumSiap, sqlite3.Error, ValueError):
            pass
        if tersedia:
            try:
                guru = jadwal_http.guru_map()
            except (OSError, ValueError):
                guru = {}
            isi_lepas = {"order_id": order_id}
            if ringkas is not None:                   # versi = penempatan yang dilihat admin; form lama ditolak
                isi_lepas = {**isi_lepas, "target_revisi": ringkas["dibuat"]}
            tokens = {nama: jadwal_http.bentuk_token(penangan, principal, kode, isi)
                      for nama, kode, isi in (("tempatkan", jadwal_http.AKSI_TEMPATKAN, {"order_id": order_id}),
                                              ("lepas", jadwal_http.AKSI_LEPAS, isi_lepas),
                                              ("sesi_ubah", jadwal_http.AKSI_SESI_UBAH, {"order_id": order_id}),
                                              ("sesi_batal", jadwal_http.AKSI_SESI_BATAL, {"order_id": order_id}))}
            isi += jadwal_ui.blok_penempatan({"paket": detail["kode_paket"]}, ringkas, kelompok, guru,
                                             detail["status"] == dasar.STATUS_AKTIF, tokens)
    _kirim(penangan, principal, isi)


# --- pratinjau bukti --------------------------------------------------------------------------

def _muat_bukti(bukti_id: int):
    """(mime, isi) atau None bila bukti tak ada atau berkas hilang; berkas rusak = BuktiBerkasError."""
    with _buka() as kon:
        meta = putusan.bukti_meta(kon, bukti_id)
    if meta is None:
        return None
    try:
        with berkas.buka(meta["berkas"]) as f:
            isi = f.read(BATAS_UKURAN_BUKTI + 1)
    except FileNotFoundError:
        return None
    except OSError:
        raise bukti_berkas.BuktiBerkasError("berkas bukti tidak bisa dibuka") from None
    if (meta["mime"] not in MIME_BUKTI or len(isi) > BATAS_UKURAN_BUKTI
            or bukti_berkas.mime_dari_isi(isi) != meta["mime"]):
        raise bukti_berkas.BuktiBerkasError("berkas bukti tidak cocok dengan catatan")
    return meta["mime"], isi


def _get_bukti(penangan, principal) -> None:
    try:
        bukti_id, unduh = bukti_umum._query_bukti(penangan)
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        muat = _muat_bukti(bukti_id)
    except bukti_berkas.BuktiBerkasError:
        return _kirim(penangan, principal, bukti_umum.ui.halaman_bukti_rusak(), 503)
    except _GALAT_BACA:
        return _kirim(penangan, principal, daftar_ui.halaman_tidak_siap(), 503)
    if muat is None:
        return _kirim(penangan, principal, bukti_umum.ui.halaman_bukti_tidak_tersedia(), 404)
    if h._principal_admin(penangan) != principal:
        return h._tidak_ada(penangan)
    bukti_umum._kirim_bukti(penangan, muat[0], muat[1], unduh)


def tangani_get(penangan, jalur) -> bool:
    if jalur not in RUTE_GET:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    {ui.RUTE: _get_antrean, ui.RUTE_VERIFIKASI: _get_detail, ui.RUTE_BUKTI: _get_bukti}[jalur](penangan, principal)
    return True


# --- keputusan --------------------------------------------------------------------------------

def _bukti_dilihat(tinjauan) -> int:
    nilai = tinjauan["data"].get("target_revisi")
    if type(nilai) is not int or nilai < 1:
        raise ValueError("bukti tidak sah")
    return nilai


def _order_dari_tinjauan(tinjauan) -> str:
    """`order_id` hanya dari tinjauan bertanda tangan (`target_id`), tidak pernah dari field form."""
    return dasar.periksa_order_id(tinjauan["data"].get("target_id"))


def _putuskan(penangan, principal, jalur: str) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, _AKSI_POST[jalur])
    setuju = jalur == ui.RUTE_SETUJUI
    aksi.wajib_field(data, frozenset() if setuju else frozenset({"alasan"}))
    order_id, dilihat = _order_dari_tinjauan(tinjauan), _bukti_dilihat(tinjauan)
    with _buka(tulis=True) as kon:
        if setuju:
            putusan.setujui(kon, order_id, principal.id_akun, alur.waktu_sekarang(), bukti_dilihat=dilihat)
        else:
            putusan.tolak(kon, order_id, principal.id_akun, data["alasan"], alur.waktu_sekarang(),
                          bukti_dilihat=dilihat)
    h._redirect(penangan, "%s?hasil=%s" % (ui.RUTE, HASIL_SETUJU if setuju else HASIL_TOLAK))


def _putuskan_dengan_deposit(penangan, principal, jalur: str) -> None:
    """Deposit yang tidak lagi berlaku mendapat pesan jelas (bukan konflik generik); tidak ada yang tertulis."""
    try:
        _putuskan(penangan, principal, jalur)
    except dasar.DepositTidakAktif:
        h._galat(penangan, 409, COPY_DEPOSIT_TIDAK_AKTIF)


def tangani_post(penangan, jalur) -> bool:
    if jalur not in _AKSI_POST:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    aksi.jalankan_aman(
        penangan, lambda: _putuskan_dengan_deposit(penangan, principal, jalur),
        copy_konflik=ui.COPY_GALAT_KONFLIK,
        copy_isian=ui.COPY_GALAT_ALASAN if jalur == ui.RUTE_TOLAK else daftar_ui.COPY_GALAT_ISIAN)
    return True
