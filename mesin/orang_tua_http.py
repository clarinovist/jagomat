"""Rute halaman orang tua di akun murid: `GET /murid/orang-tua` dan tiga POST PIN tirai.

Dijawab di permukaan murid (sebelum `_lolos_sandi`, dipanggil `student_http`). Aturan yang ditegakkan di sini:

- Gerbang: semua rute hanya hidup bila sakelar DAFTAR_AKUN_ANAK aktif. Mati -> fungsi ini mengembalikan False
  dan pemanggil memperlakukan jalur seperti rute murid tak dikenal (tanpa efek, tanpa jejak).
- `siswa_id` HANYA dari sesi (`students.siswa_dari_akun`); query/form tidak pernah dibaca untuk itu.
- Tirai terbuka disimpan di `tirai_orang_tua` (memori, terikat token sesi + akun + anak, 30 menit) dan hanya bisa
  dibuka untuk sesi cookie: Basic tidak punya token sesi sehingga tidak pernah membuka tirai.
- Laju PIN: `laju_masuk` dengan ruang tersendiri per (anak, IP); blokir diperiksa SEBELUM PBKDF2.
- CSRF: pola murid yang ada (cookie SameSite=Lax + `_asal_sama_post` di dispatcher untuk semua `/murid/`).
- Atur/ganti/hapus PIN hanya saat tirai terbuka atau anak belum punya PIN; hapus wajib centang konfirmasi.
- Kontak orang tua tidak pernah dibaca atau dirender.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
import urllib.parse
from typing import Optional

import daftar_anak_gate
import database
import laju_masuk
import orang_tua_data
import orang_tua_pages as halaman
import pin_orang_tua_store as pin_store
import tirai_orang_tua as tirai
from orang_tua_style import RUTE
from support_pages import halaman_pesan_murid

RUTE_POST = (halaman.RUTE_PIN, halaman.RUTE_ATUR, halaman.RUTE_HAPUS)
RUANG_LAJU = "pin-orang-tua"
BATAS_FORM = 1024
BATAS_KOLOM_FORM = 8
KODE_PIN_SALAH = 200
KODE_DIBLOKIR = 429
KODE_PERLU_BUKA = 403
KODE_ISIAN_TIDAK_SAH = 400
KODE_TIDAK_ADA = 404


@dataclass(frozen=True)
class _Konteks:
    id_akun: str
    siswa_id: int
    token: Optional[str]  # token cookie sesi; None untuk Basic (tidak bisa membuka tirai)

    def terbuka(self) -> bool:
        return self.token is not None and tirai.terbuka(self.token, self.id_akun, self.siswa_id)

    def buka(self) -> None:
        if self.token is not None:
            tirai.buka(self.token, self.id_akun, self.siswa_id)

    def tutup(self) -> None:
        if self.token is not None:
            tirai.tutup(self.token, self.id_akun, self.siswa_id)


def tersedia() -> bool:
    """Gerbang tunggal: sakelar DAFTAR_AKUN_ANAK hidup (dipakai juga beranda murid)."""
    return daftar_anak_gate.aktif()


def _konteks(penangan, principal, siswa_id: int) -> _Konteks:
    token = penangan._ambil_token() if principal.metode == "cookie" else None
    return _Konteks(principal.id_akun, siswa_id, token or None)


def _kunci_laju(penangan, siswa_id: int) -> tuple:
    ip = laju_masuk.ip_klien(penangan.headers, penangan.client_address)
    return (f"pin:{siswa_id}", f"{RUANG_LAJU}:{ip}")


def _kirim(penangan, isi: bytes, kode: int = 200) -> None:
    penangan._kirim_privat(isi, kode, skrip_sandi=True)


def _alihkan(penangan, tujuan: str) -> None:
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def _tujuan(kode_kabar: str = "") -> str:
    return RUTE + ("?" + urllib.parse.urlencode({"pesan": kode_kabar}) if kode_kabar else "")


def _kode_kabar(jalur_penuh: str) -> str:
    kueri = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query)
    nilai = (kueri.get("pesan") or [""])[0]
    return nilai if nilai in halaman.KABAR else ""


def _tampilkan(penangan, kon, ctx: _Konteks, *, kabar: str = "", galat: str = "", kode: int = 200) -> None:
    """Form PIN bila anak punya PIN dan tirai tertutup (tanpa membaca isi); selain itu isi halaman."""
    ada_pin = pin_store.ada_pin(kon, ctx.siswa_id)
    if ada_pin and not ctx.terbuka():
        _kirim(penangan, halaman.halaman_pin(), kode)
        return
    data = orang_tua_data.kumpulkan(kon, ctx.id_akun, ctx.siswa_id)
    _kirim(penangan, halaman.halaman_isi(data, ada_pin, kabar=kabar, galat=galat), kode)


def tangani_get(penangan, kon, siswa_id: int) -> bool:
    """GET `/murid/orang-tua` untuk murid yang sudah sah dan terhubung; False bila gerbang mati."""
    if not tersedia():
        return False
    principal = penangan._principal()
    if principal is None:
        return False
    ctx = _konteks(penangan, principal, siswa_id)
    _tampilkan(penangan, kon, ctx, kabar=_kode_kabar(penangan.path))
    return True


def _baca_form(penangan) -> Optional[dict]:
    """Form urlencoded kecil dengan kunci tunggal; None bila tidak sah. Kunci tak dikenal tidak pernah dibaca."""
    from kontak_http import _baca_form as baca
    return baca(penangan)


def _tolak_masuk(penangan) -> None:
    penangan._kirim(halaman_pesan_murid("Perlu masuk", "<h1>Halaman murid</h1>"), 401)


def _siswa_sesi(kon, principal) -> Optional[int]:
    import students
    return students.siswa_dari_akun(kon, principal.pengguna)


def _buka_dengan_pin(penangan, kon, ctx: _Konteks, data: dict) -> None:
    if not pin_store.ada_pin(kon, ctx.siswa_id):
        _alihkan(penangan, _tujuan())
        return
    kunci = _kunci_laju(penangan, ctx.siswa_id)
    if laju_masuk.sedang_diblokir(*kunci):
        _kirim(penangan, halaman.halaman_pin(halaman.COPY_PIN_DIBLOKIR), KODE_DIBLOKIR)
        return
    if not pin_store.periksa_pin(kon, ctx.siswa_id, data.get("pin")):
        laju_masuk.catat_gagal(*kunci)
        _kirim(penangan, halaman.halaman_pin(halaman.COPY_PIN_SALAH), KODE_PIN_SALAH)
        return
    laju_masuk.catat_berhasil(*kunci)
    ctx.buka()
    _alihkan(penangan, _tujuan())


def _boleh_ubah(kon, ctx: _Konteks) -> bool:
    return not pin_store.ada_pin(kon, ctx.siswa_id) or ctx.terbuka()


def _atur_pin(penangan, kon, ctx: _Konteks, data: dict) -> bool:
    """Pasang/ganti PIN; True bila berhasil (respons sudah dikirim bila gagal)."""
    if not _boleh_ubah(kon, ctx):
        _kirim(penangan, halaman.halaman_pin(halaman.COPY_PIN_PERLU_BUKA), KODE_PERLU_BUKA)
        return False
    pin, ulang = data.get("pin"), data.get("pin_ulang")
    if not pin_store.pin_sah(pin) or pin != ulang:
        _tampilkan(penangan, kon, ctx, galat=halaman.COPY_PIN_TIDAK_SAH, kode=KODE_ISIAN_TIDAK_SAH)
        return False
    pin_store.simpan(kon, ctx.siswa_id, pin, int(time.time()))
    return True


def _hapus_pin(penangan, kon, ctx: _Konteks, data: dict) -> bool:
    if not pin_store.ada_pin(kon, ctx.siswa_id):
        _alihkan(penangan, _tujuan())
        return False
    if not ctx.terbuka():
        _kirim(penangan, halaman.halaman_pin(halaman.COPY_PIN_PERLU_BUKA), KODE_PERLU_BUKA)
        return False
    if data.get("konfirmasi") != "1":
        _tampilkan(penangan, kon, ctx, galat=halaman.COPY_KONFIRMASI_WAJIB, kode=KODE_ISIAN_TIDAK_SAH)
        return False
    pin_store.hapus(kon, ctx.siswa_id)
    return True


def _ubah_dalam_transaksi(penangan, ctx: _Konteks, jalur: str, data: dict) -> Optional[str]:
    """Jalankan atur/hapus di satu transaksi tulis; kode kabar bila berhasil, None bila respons sudah dikirim."""
    aksi = _atur_pin if jalur == halaman.RUTE_ATUR else _hapus_pin
    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        if not aksi(penangan, kon, ctx, data):
            return None
    return "pin-dipasang" if jalur == halaman.RUTE_ATUR else "pin-dihapus"


def tangani_post(penangan, jalur: str) -> bool:
    """POST PIN tirai; False bila jalur bukan milik modul atau gerbang mati (jatuh ke perilaku rute tak dikenal)."""
    if jalur not in RUTE_POST or not tersedia():
        return False
    principal = penangan._principal()
    if principal is None or principal.peran != "murid":
        _tolak_masuk(penangan)
        return True
    data = _baca_form(penangan)
    if data is None:
        penangan._tolak_isian()
        return True
    with database.buka() as kon:
        siswa_id = _siswa_sesi(kon, principal)
        if siswa_id is None:
            penangan._kirim(halaman_pesan_murid("404", "<h1>Halaman tidak ada</h1>"), KODE_TIDAK_ADA)
            return True
        ctx = _konteks(penangan, principal, siswa_id)
        if jalur == halaman.RUTE_PIN:
            _buka_dengan_pin(penangan, kon, ctx, data)
            return True
    kabar = _ubah_dalam_transaksi(penangan, ctx, jalur, data)
    if kabar is None:
        return True
    if jalur == halaman.RUTE_ATUR:
        ctx.buka()
    else:
        ctx.tutup()
    _alihkan(penangan, _tujuan(kabar))
    return True
