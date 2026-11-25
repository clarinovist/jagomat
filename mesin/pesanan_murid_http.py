"""Rute murid pesanan Peta Kemampuan Rp49.000 (F2c): orang tua memesan dan membayar lewat akun anak.

Mesin pesanan/transfer/ledger SAMA dengan sisi guru (`pesanan_http.layani_*`,
`pesanan_transfer_http.layani_post`); modul ini hanya penentu pembeli + alamat. Titik masuk GET:
`/murid/pesanan` (status/tagihan; bila belum ada pesanan menampilkan kartu "Pesan"). Rute lain:
`/murid/pesanan/{qr,pesan,periksa,ulang,buat,tagihan,bukti,tagihan/ulang}`.

Aturan yang ditegakkan di sini, bukan di halaman:

- Hidup HANYA bila sakelar `DAFTAR_AKUN_ANAK` aktif; mati = `False` (jatuh ke penangan murid biasa:
  jawaban sama dengan jalur `/murid` tak dikenal). Dijawab SEBELUM `_lolos_sandi` seperti permukaan murid.
- Pembeli = principal peran murid dari sesi server (`id_akun` akun murid). Anak = siswa yang
  tertaut ke akun itu (`students.siswa_dari_akun` di `pesanan_alur`), BUKAN dari URL/form/kueri; kueri
  diabaikan dan form hanya `{token}` (field lain -> 400). Kontak = `kontak_akun(id_akun murid)`.
- Anonim, guru, dan admin tidak ditangani (`False`): GET -> 303 /masuk, POST -> 401 seperti jalur murid lain.
- Sakelar hidup tetapi gerbang pembayaran tertutup: GET = halaman "belum dibuka", POST = 404 murid, tanpa efek.
- Nomor WhatsApp tidak pernah dirender; tidak ada rute kontak untuk murid (ubah lewat admin).
"""
from __future__ import annotations

import daftar_anak_gate
import database
import pesanan_http
import pesanan_permukaan as permukaan
import pesanan_transfer_http
import tirai_aksi

_RUTE = permukaan.RUTE_MURID
_GET = frozenset({_RUTE.status, _RUTE.qr, _RUTE.pesan})
_POST = frozenset({_RUTE.pesan, _RUTE.periksa, _RUTE.ulang, _RUTE.buat, _RUTE.tagihan,
                   _RUTE.bukti, _RUTE.ulang_transfer})


def _pembeli(penangan):
    """Principal murid yang siswanya tertaut, atau None (jatuh ke penangan murid biasa)."""
    import students
    principal = pesanan_http.principal_murid(penangan)
    if principal is None:
        return None
    with database.buka() as kon:
        siswa_id = students.siswa_dari_akun(kon, principal.pengguna)
    return None if siswa_id is None else principal


def _tirai_tertutup(penangan, principal) -> bool:
    """Tirai PIN anak yang tertaut ke akun murid ini tertutup (lihat `tirai_aksi`); anak dari akun sesi, bukan input."""
    import students
    with database.buka() as kon:
        siswa_id = students.siswa_dari_akun(kon, principal.pengguna)
    return siswa_id is None or tirai_aksi.tertutup(penangan, principal, siswa_id)


def _tolak_tirai(penangan) -> None:
    from support_pages import halaman_pesan_murid
    import html
    penangan._kirim(halaman_pesan_murid(str(tirai_aksi.KODE_TERTUTUP), "<h1>Untuk Ayah/Bunda</h1><p>%s</p>"
                                        % html.escape(tirai_aksi.COPY_TERTUTUP)), tirai_aksi.KODE_TERTUTUP)


def tangani_get(penangan, jalur: str, jalur_penuh: str = "") -> bool:
    """GET rute murid pesanan; False bila bukan milik modul, sakelar mati, atau bukan murid tertaut."""
    if jalur not in _GET:
        return False
    if not daftar_anak_gate.aktif():
        return False
    principal = _pembeli(penangan)
    if principal is None:
        return False
    return pesanan_http.layani_get(penangan, permukaan.MURID_KE_KANONIK[jalur], principal)


def tangani_post(penangan, jalur: str) -> bool:
    """POST rute murid pesanan; mesin Midtrans dulu, lalu transfer (urutan sama dengan sisi guru)."""
    if jalur not in _POST:
        return False
    if not daftar_anak_gate.aktif():
        return False
    principal = _pembeli(penangan)
    if principal is None:
        return False
    kanonik = permukaan.MURID_KE_KANONIK[jalur]
    if _tirai_tertutup(penangan, principal):  # PIN terpasang dan tirai tertutup: tanpa efek
        _tolak_tirai(penangan)
        return True
    if pesanan_http.layani_post(penangan, kanonik, principal):
        return True
    if pesanan_transfer_http.layani_post(penangan, kanonik, principal):
        return True
    pesanan_http._tidak_ada_pembeli(penangan, principal, post=True)  # gerbang tertutup: tanpa efek
    return True
