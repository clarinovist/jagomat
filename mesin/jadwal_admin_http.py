"""Rute admin jadwal Paket Belajar: kelompok Mini Class, penempatan, dan delapan pertemuan.

Dijawab `admin_http` sebelum palang guru; anonim/guru menerima 404 yang sama. Rute ini TIDAK bergantung pada
sakelar `PAKET_BELAJAR` (admin tetap bisa menyiapkan operasional), tetapi hanya tersedia setelah `jadwal_*`
dimigrasikan. Aksi memakai CSRF + tinjauan bertanda tangan (tanpa sandi ulang: penjadwalan bukan aksi uang);
`admin_id` dari principal sesi, `order_id`/`kelompok_id` dari tinjauan, dan `pertemuan_id` diverifikasi milik
induk yang ditandatangani. Semua galat dipetakan ke pesan tetap tanpa data.
"""
from __future__ import annotations

import sqlite3

import admin_http as h
import admin_pesanan_aksi as aksi
import admin_pesanan_pages as daftar_ui
import admin_security
import admin_store
import auth
import jadwal_admin_pages as ui
import jadwal_dasar as jd
import kelas_dasar as dasar
import jadwal_store as js
import pesanan
import pesanan_alur as alur

AKSI_BUAT = "jadwal_kelompok_buat"
AKSI_UBAH = "jadwal_kelompok_ubah"
AKSI_TEMPATKAN = "jadwal_tempatkan"
AKSI_LEPAS = "jadwal_lepas"
AKSI_SESI_UBAH = "jadwal_pertemuan_ubah"
AKSI_SESI_BATAL = "jadwal_pertemuan_batal"
RUTE_KELOMPOK = ui.RUTE_KELOMPOK
RUTE_PENEMPATAN = "/admin/kelas/penempatan"
RUTE_LEPAS = "/admin/kelas/penempatan/lepas"
RUTE_PERTEMUAN = "/admin/kelas/pertemuan"
RUTE_PERTEMUAN_BATAL = "/admin/kelas/pertemuan/batal"
COPY_KONFLIK = ("Jadwal tidak dapat disimpan: kelompok mungkin penuh, sudah selesai, atau kembar (nama dan waktu "
                "mulai sama), anak masih punya penempatan yang aksesnya belum berakhir, pertemuan order ini sudah "
                "pernah dijadwalkan, Private sudah mulai berlangsung (tidak bisa dilepas), atau paket belum aktif. "
                "Lepas penempatan lama / pilih kelompok lain. Tidak ada yang diubah.")
COPY_ISIAN = ("Isian jadwal tidak sah: periksa nama, lokasi, guru, kuota (1-5), tanggal, dan jam; pertemuan "
              "tidak boleh sudah lewat atau melewati masa akses paket (delapan pertemuan memakan 24 hari). "
              "Tidak ada yang diubah.")
COPY_LAYANAN = "Jadwal belum siap di server. Coba lagi beberapa saat; tidak ada yang diubah."
MAKS_FIELD = 12
_GALAT_LAYANAN = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError, ValueError)


def guru_map() -> dict:
    """Akun guru aktif: id -> nama pengguna. Akun nonaktif tidak bisa dipilih."""
    return {a["id_akun"]: a["pengguna"] for a in auth.muat_akun()
            if a.get("peran") == "guru" and not a.get("dinonaktifkan") and a.get("id_akun")}


def bentuk_token(penangan, principal, aksi_nama: str, isi: dict):
    """{csrf, tinjauan} untuk satu form, hanya untuk sesi cookie; selain itu None."""
    if principal.metode != "cookie":
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    return {"csrf": h._csrf(akun, sesi),
            "tinjauan": admin_security.buat_tinjauan(akun, sesi, aksi_nama, isi)}


def _terima(penangan, principal, aksi_nama: str, maks: int = MAKS_FIELD):
    data = admin_security.baca_form(penangan, maksimum_field=maks)
    akun = h._akun_principal(principal)
    if akun is None:
        raise PermissionError("Identitas pengelola berubah.")
    sesi = h._wajib_cookie(penangan, principal)
    h._cek_csrf(akun, sesi, data.pop("csrf", None))
    tinjauan = admin_security.periksa_tinjauan(akun, sesi, data.pop("tinjauan", None))
    if tinjauan["aksi"] != aksi_nama or type(tinjauan["data"]) is not dict:
        raise PermissionError("Tinjauan tidak cocok.")
    return tinjauan, data


def _buka(*, tulis: bool = False):
    return js.buka(h._path_admin(), tulis_data=tulis)


def _kirim(penangan, principal, isi: str, kode: int = 200) -> None:
    if h._principal_admin(penangan) != principal:
        return h._tidak_ada(penangan)
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "kelas_belajar", isi, penangan=penangan, skrip=True, judul="Paket Belajar 1 Bulan",
        subjudul="Kelompok, guru, lokasi, dan jadwal pertemuan."), kode, skrip=True)


def _jalankan(penangan, fungsi) -> None:
    aksi.jalankan_aman(penangan, fungsi, copy_konflik=COPY_KONFLIK, copy_isian=COPY_ISIAN,
                       copy_layanan=COPY_LAYANAN)


def _angka(nilai, *, minimum=1, maksimum=5):
    if type(nilai) is not str or not nilai.isascii() or not nilai.isdigit():
        raise ValueError("angka tidak sah")
    angka = int(nilai)
    if not minimum <= angka <= maksimum:
        raise ValueError("angka tidak sah")
    return angka


def _guru_sah(guru: dict, nilai) -> str:
    kode = jd.periksa_guru_id(nilai)
    if kode not in guru:
        raise ValueError("guru tidak sah")
    return kode


# --- GET ------------------------------------------------------------------------------------

def _get_kelompok(penangan, principal) -> None:
    if principal.metode != "cookie":
        return h._galat(penangan, 403, daftar_ui.COPY_GALAT_FORM)
    try:
        kid = jd.periksa_kelompok_id(h._query(penangan, diizinkan={"id"}).get("id"))
    except (ValueError, pesanan.PesananDataTidakSah):
        return h._tidak_ada(penangan)
    try:
        guru = guru_map()
        with _buka() as kon:
            detail = js.detail_kelompok(kon, kid)
        tokens = {
            "ubah": bentuk_token(penangan, principal, AKSI_UBAH, {"kelompok_id": kid}),
            "sesi_ubah": bentuk_token(penangan, principal, AKSI_SESI_UBAH, {"kelompok_id": kid}),
            "sesi_batal": bentuk_token(penangan, principal, AKSI_SESI_BATAL, {"kelompok_id": kid}),
        }
    except jd.JadwalTidakDitemukan:
        return h._tidak_ada(penangan)
    except PermissionError:
        return h._galat(penangan, 403, daftar_ui.COPY_GALAT_FORM)
    except _GALAT_LAYANAN:
        return _kirim(penangan, principal, daftar_ui.halaman_tidak_siap(), 503)
    _kirim(penangan, principal, ui.halaman_kelompok(detail, guru, tokens))


def tangani_get(penangan, jalur) -> bool:
    if jalur != RUTE_KELOMPOK:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    _get_kelompok(penangan, principal)
    return True


# --- POST -----------------------------------------------------------------------------------

def _buat(penangan, principal) -> None:
    _tinjauan, data = _terima(penangan, principal, AKSI_BUAT)
    aksi.wajib_field(data, frozenset({"nama", "lokasi", "guru_id", "kuota", "tanggal", "jam"}))
    guru = guru_map()
    with _buka(tulis=True) as kon:
        kid = js.buat_kelompok(
            kon, principal.id_akun, nama=data["nama"], lokasi=data["lokasi"],
            guru_id=_guru_sah(guru, data["guru_id"]), kuota=_angka(data["kuota"]),
            tanggal=data["tanggal"], jam=data["jam"], sekarang=alur.waktu_sekarang())
    h._redirect(penangan, "%s?id=%s" % (RUTE_KELOMPOK, kid))


def _ubah(penangan, principal) -> None:
    tinjauan, data = _terima(penangan, principal, AKSI_UBAH)
    aksi.wajib_field(data, frozenset({"nama", "lokasi", "guru_id", "kuota"}))
    kid = jd.periksa_kelompok_id(tinjauan["data"].get("kelompok_id"))
    guru = guru_map()
    with _buka(tulis=True) as kon:
        js.ubah_kelompok(kon, principal.id_akun, kid, nama=data["nama"], lokasi=data["lokasi"],
                         guru_id=_guru_sah(guru, data["guru_id"]), kuota=_angka(data["kuota"]),
                         sekarang=alur.waktu_sekarang())
    h._redirect(penangan, "%s?id=%s" % (RUTE_KELOMPOK, kid))


def _tempatkan(penangan, principal) -> None:
    tinjauan, data = _terima(penangan, principal, AKSI_TEMPATKAN)
    order_id = dasar.periksa_order_id(tinjauan["data"].get("order_id"))
    if set(data) == {"kelompok_id"}:
        kelompok_id, guru_id, tanggal, jam = jd.periksa_kelompok_id(data["kelompok_id"]), None, None, None
    elif set(data) == {"guru_id", "tanggal", "jam"}:
        kelompok_id = None
        guru_id = _guru_sah(guru_map(), data["guru_id"])
        tanggal, jam = data["tanggal"], data["jam"]
    else:
        raise ValueError("isian penempatan tidak sah")
    with _buka(tulis=True) as kon:
        js.tempatkan(kon, principal.id_akun, order_id, kelompok_id=kelompok_id, guru_id=guru_id,
                     tanggal=tanggal, jam=jam, sekarang=alur.waktu_sekarang())
    h._redirect(penangan, "/admin/kelas/verifikasi?order=%s" % order_id)


def _lepas(penangan, principal) -> None:
    tinjauan, data = _terima(penangan, principal, AKSI_LEPAS)
    aksi.wajib_field(data, frozenset())
    order_id = dasar.periksa_order_id(tinjauan["data"].get("order_id"))
    with _buka(tulis=True) as kon:
        js.lepas_penempatan(kon, principal.id_akun, order_id, sekarang=alur.waktu_sekarang())
    h._redirect(penangan, "/admin/kelas/verifikasi?order=%s" % order_id)


def _induk(tinjauan) -> tuple:
    isi = tinjauan["data"]
    if set(isi) == {"kelompok_id"}:
        return "kelompok_id", jd.periksa_kelompok_id(isi["kelompok_id"])
    if set(isi) == {"order_id"}:
        return "order_id", dasar.periksa_order_id(isi["order_id"])
    raise PermissionError("Tinjauan tidak sah.")


def _sesi_sah(kon, data, induk) -> dict:
    sesi = js.pertemuan_dari(kon, data.get("pertemuan_id"))
    if sesi is None or sesi[induk[0]] != induk[1]:
        raise jd.JadwalTidakDitemukan()
    return sesi


def _kembali_sesi(induk) -> str:
    if induk[0] == "kelompok_id":
        return "%s?id=%s" % (RUTE_KELOMPOK, induk[1])
    return "/admin/kelas/verifikasi?order=%s" % induk[1]


def _ubah_sesi(penangan, principal) -> None:
    tinjauan, data = _terima(penangan, principal, AKSI_SESI_UBAH)
    aksi.wajib_field(data, frozenset({"pertemuan_id", "tanggal", "jam"}))
    induk = _induk(tinjauan)
    with _buka(tulis=True) as kon:
        _sesi_sah(kon, data, induk)
        js.ubah_pertemuan(kon, principal.id_akun, data["pertemuan_id"], tanggal=data["tanggal"],
                          jam=data["jam"], sekarang=alur.waktu_sekarang())
    h._redirect(penangan, _kembali_sesi(induk))


def _batal_sesi(penangan, principal) -> None:
    tinjauan, data = _terima(penangan, principal, AKSI_SESI_BATAL)
    aksi.wajib_field(data, frozenset({"pertemuan_id", "batal"}))
    if data["batal"] not in ("0", "1"):
        raise ValueError("status batal tidak sah")
    induk = _induk(tinjauan)
    with _buka(tulis=True) as kon:
        _sesi_sah(kon, data, induk)
        js.batalkan_pertemuan(kon, principal.id_akun, data["pertemuan_id"], batal=data["batal"] == "1",
                              sekarang=alur.waktu_sekarang())
    h._redirect(penangan, _kembali_sesi(induk))


def tangani_post(penangan, jalur) -> bool:
    fungsi = {RUTE_KELOMPOK: _buat, RUTE_KELOMPOK + "/ubah": _ubah,
              RUTE_PENEMPATAN: _tempatkan, RUTE_LEPAS: _lepas,
              RUTE_PERTEMUAN: _ubah_sesi, RUTE_PERTEMUAN_BATAL: _batal_sesi}.get(jalur)
    if fungsi is None:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    _jalankan(penangan, lambda: fungsi(penangan, principal))
    return True
