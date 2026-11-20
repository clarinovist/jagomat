"""Rute admin Pengaturan layanan: GET/POST `/admin/sakelar` (empat sakelar, DB sakelar terpisah).

GET menampilkan halaman Pengaturan layanan lengkap (sakelar fitur, tahap pembayaran, rekening, kesiapan,
dukungan, baris AI); bagian sakelar dirender di sini, bagian lain oleh pemiliknya masing-masing. POST di
rute ini tetap hanya mengubah sakelar fitur dan tidak berubah.

Dijawab `admin_http` sebelum palang guru: anonim/murid/guru = 404 identik rute admin tak dikenal sebelum DB
sakelar dibaca. Aturan:

- Aksi = pola uang admin (`h._token_final`: CSRF + tinjauan terikat aksi dan sesi + sandi ulang, sesi berkuki),
  same-origin, tanpa field isian selain itu. Nama sakelar, target, dan revisi HANYA dari tinjauan bertanda
  tangan; `feature_switch.ubah` menegakkan optimistic concurrency (konflik = 409 ramah, bukan menimpa), sehingga
  kirim ulang form yang sama setelah sukses berakhir konflik, bukan ubah ulang.
- Mematikan selalu boleh. Menyalakan PESANAN_TRANSFER_AKTIF ditolak bila funnel efektif mati atau rekening belum
  terisi/tak terbaca; diperiksa ulang di server saat POST, bukan hanya saat render.
- DB sakelar rusak = halaman/aksi 503 jujur tanpa path dan tanpa efek.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, Optional, Tuple

import admin_http as h
import admin_launch_http as launch
import admin_pesanan_aksi as aksi
import admin_sakelar_pages as ui
import admin_rekening_http
import admin_security
import admin_store
import feature_switch
import funnel_flag
import pesanan_rekening
import sakelar_registry

TRANSFER = "PESANAN_TRANSFER_AKTIF"
HASIL_TERSIMPAN = "tersimpan"
BATAS_ACTOR = 100
REVISI_SEED = 1  # baris yang belum ada di DB dibuat feature_switch.ubah dengan revisi 1
COPY_BELUM_FUNNEL = "Funnel Cek Kemampuan harus aktif lebih dulu."
COPY_BELUM_REKENING = "Rekening transfer harus terisi (atau belum bisa diperiksa); isi di halaman rekening."
_GALAT_REKENING = (admin_store.StoreBelumSiap, sqlite3.Error, OSError, ValueError)
_GALAT_BACA = (feature_switch.GalatSakelar, OSError)


class _PrasyaratBelumTerpenuhi(Exception):
    """Menyalakan sakelar ditolak karena prasyarat; daftar teks aman ditampilkan ke admin."""

    def __init__(self, belum: Tuple[str, ...]):
        super().__init__("prasyarat belum terpenuhi")
        self.belum = belum


def _rekening_terisi() -> bool:
    try:
        return pesanan_rekening.baca(h._path_admin()) is not None
    except _GALAT_REKENING:
        return False


def _prasyarat_belum(nama: str) -> Tuple[str, ...]:
    """Teks prasyarat menyalakan `nama` yang belum terpenuhi (kosong = boleh); dibaca segar tiap panggilan."""
    if nama != TRANSFER:
        return ()
    feature_switch.bersihkan_cache()  # status funnel segar, bukan hasil cache proses lain
    belum = []
    if not funnel_flag.funnel_aktif():
        belum.append(COPY_BELUM_FUNNEL)
    if not _rekening_terisi():
        belum.append(COPY_BELUM_REKENING)
    return tuple(belum)


def _revisi_harapan(sakelar: feature_switch.Sakelar) -> int:
    return sakelar.revisi if sakelar.sumber == "db" else REVISI_SEED


def _tinjauan(akun, sesi, sakelar: feature_switch.Sakelar) -> str:
    return admin_security.buat_tinjauan(akun, sesi, ui.AKSI_UBAH, {
        "target_id": sakelar.nama, "aktif": int(not sakelar.aktif), "target_revisi": _revisi_harapan(sakelar)})


def _tokens(penangan, principal, daftar, prasyarat) -> Dict[str, Tuple[str, str]]:
    """{nama: (csrf, tinjauan)} untuk baris yang boleh diubah (mematikan, atau menyalakan tanpa prasyarat belum)."""
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    csrf = h._csrf(akun, sesi)
    return {s.nama: (csrf, _tinjauan(akun, sesi, s)) for s in daftar if s.aktif or not prasyarat.get(s.nama)}


KUNCI_QUERY = frozenset({"hasil", "dukungan"})
KODE_DUKUNGAN = frozenset(launch.FEEDBACK_DUKUNGAN)


def _query_halaman(penangan) -> Tuple[Optional[str], str]:
    """(kode hasil sakelar, kode hasil dukungan) dari query; kunci/nilai di luar daftar = ValueError (404)."""
    query = h._query(penangan, diizinkan=KUNCI_QUERY)
    hasil, dukungan = query.get("hasil"), query.get("dukungan")
    if "hasil" in query and hasil not in ui.KODE_HASIL:
        raise ValueError("hasil tidak sah")
    if "dukungan" in query and dukungan not in KODE_DUKUNGAN:
        raise ValueError("dukungan tidak sah")
    return hasil, dukungan or ""


def bagian_sakelar(penangan, principal, hasil: Optional[str]) -> Tuple[str, int]:
    """(HTML bagian sakelar, kode HTTP). DB sakelar tak terbaca = kartu galat + 503, tanpa membuang bagian
    halaman lain; PermissionError (sesi berkuki tak sah) diteruskan ke pemanggil."""
    try:
        daftar = feature_switch.daftar(seed=sakelar_registry.seed_env())
        prasyarat = {s.nama: _prasyarat_belum(s.nama) for s in daftar if not s.aktif}
        tokens = _tokens(penangan, principal, daftar, prasyarat) if principal.metode == "cookie" else None
    except _GALAT_BACA:
        return ui.halaman_galat(), 503
    return ui.halaman(daftar, tokens, prasyarat=prasyarat, hasil=hasil), 200


def _get(penangan, principal) -> None:
    try:
        hasil, dukungan = _query_halaman(penangan)
        sakelar, kode = bagian_sakelar(penangan, principal, hasil)
        isi = launch.halaman_pengaturan(
            penangan, principal, kode_dukungan=dukungan, sakelar=sakelar,
            rekening=admin_rekening_http.bagian_pengaturan())
    except PermissionError:
        return h._galat(penangan, 403, ui.COPY_TANPA_SESI)
    except (admin_store.StoreBelumSiap, sqlite3.Error, OSError):
        return h._galat(penangan, 503, "Layanan admin belum siap.")
    except (ValueError, LookupError):
        return h._tidak_ada(penangan)
    launch._kirim(penangan, principal, "operasional", isi, kode)


def tangani_get(penangan, jalur) -> bool:
    if jalur != ui.RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    _get(penangan, principal)
    return True


def _perintah(tinjauan) -> Tuple[str, bool, int]:
    """(nama, target, revisi) dari tinjauan bertanda tangan; bentuk tak sah = ValueError."""
    meta = tinjauan["data"]
    nama, nilai, revisi = meta.get("target_id"), meta.get("aktif"), meta.get("target_revisi")
    if nama not in feature_switch.NAMA_SAKELAR or type(nilai) is not int or nilai not in (0, 1):
        raise ValueError("perintah sakelar tidak sah")
    if type(revisi) is not int or revisi < 0:
        raise ValueError("revisi sakelar tidak sah")
    return nama, bool(nilai), revisi


def _actor(principal) -> str:
    actor = principal.id_akun
    if type(actor) is not str or not actor.strip() or len(actor) > BATAS_ACTOR:
        raise ValueError("identitas pelaku tidak sah")
    return actor


def _ubah(principal, nama: str, nyala: bool, revisi: int) -> None:
    """Terapkan perubahan; galat feature_switch dipetakan ke galat umum jalankan_aman (tanpa isi galat)."""
    if nyala:
        belum = _prasyarat_belum(nama)
        if belum:
            raise _PrasyaratBelumTerpenuhi(belum)
    try:
        feature_switch.ubah(nama, nyala, actor_id=_actor(principal), revisi_diharapkan=revisi,
                            seed=sakelar_registry.seed_env())
    except feature_switch.KonflikRevisi:
        raise admin_store.KonflikOperasi("revisi sakelar berubah") from None
    except feature_switch.GalatSakelar:
        raise admin_store.StoreBelumSiap("db sakelar tidak siap") from None


def _simpan(penangan, principal) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_UBAH)
    aksi.wajib_field(data, frozenset())
    nama, nyala, revisi = _perintah(tinjauan)
    try:
        _ubah(principal, nama, nyala, revisi)
    except _PrasyaratBelumTerpenuhi as galat:
        return h._galat(penangan, 409, " ".join((ui.COPY_PRASYARAT,) + galat.belum))
    h._redirect(penangan, "%s?hasil=%s" % (ui.RUTE, HASIL_TERSIMPAN))


def tangani_post(penangan, jalur) -> bool:
    if jalur != ui.RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    aksi.jalankan_aman(penangan, lambda: _simpan(penangan, principal), copy_konflik=ui.COPY_GALAT_KONFLIK,
                       copy_isian=ui.COPY_GALAT_ISIAN, copy_layanan=ui.COPY_TIDAK_SIAP)
    return True
