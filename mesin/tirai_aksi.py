"""Gerbang tirai PIN orang tua untuk tindakan akun murid yang merupakan keputusan orang tua (butir QA 4, 25 Nov 2026).

Daftar/ganti paket, pilih jadwal, bayar, dan unggah bukti dilakukan lewat akun anak. Bila anak punya PIN tirai dan tirai sedang tertutup untuk sesi
itu, tindakan ditolak tanpa efek. Sesi Basic tidak punya token sesi sehingga tidak pernah membuka tirai, dan cookie mati yang menyertai Basic tidak
dihitung (hanya principal bermetode "cookie" yang boleh memakai token). Fail-closed bila PIN tidak terbaca. Tanpa PIN tidak ada perubahan perilaku.
Dipakai `kelas_murid_http`, `harian_langganan_murid_http`, dan `pesanan_murid_http`. PIN tirai bukan batas keamanan data (CLAUDE.md).
"""
from __future__ import annotations

import sqlite3

import database
import pin_orang_tua_store as pin_store
import tirai_orang_tua as tirai

COPY_TERTUTUP = ("Tindakan ini untuk Ayah/Bunda. Minta Ayah/Bunda membuka halaman orang tua dengan PIN dulu, lalu coba lagi. "
                 "Halaman orang tua ada di menu akun anak.")
KODE_TERTUTUP = 403


def tertutup(penangan, principal, siswa_id: int) -> bool:
    """True bila anak punya PIN tirai dan tirai orang tuanya tertutup untuk sesi ini (fail-closed bila PIN tak terbaca)."""
    try:
        with database.buka() as kon:
            if not pin_store.ada_pin(kon, siswa_id):
                return False
    except sqlite3.Error:
        return True
    token = penangan._ambil_token() if principal.metode == "cookie" else None
    return not (token is not None and tirai.terbuka(token, principal.id_akun, siswa_id))
