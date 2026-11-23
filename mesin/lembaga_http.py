"""Rute guru `/lembaga` (ringkasan pemilik les), `/lembaga/pindah` dan `/lembaga/pindah-banyak` (POST).

Kewenangan ditegakkan di sini dan diulang di ``lembaga_store.pindahkan``/``pindahkan_banyak``
dalam transaksi yang sama. Selain pemilik lembaga (guru, bukan admin), semua jawaban
memakai 404 yang byte-identik dengan rute tak dikenal, termasuk POST yang
otorisasinya gagal (tanpa tulis apa pun). Penolakan bisnis dialihkan (PRG) ke
`/lembaga?pesan=<kode tetap>`.
"""
from __future__ import annotations

import re
import urllib.parse

import database
import lembaga_pages as halaman
import lembaga_store as toko
from learning_cycle_http import GalatForm, _batasi_laju
from support_pages import halaman_pesan

RUTE = "/lembaga"
RUTE_PINDAH = "/lembaga/pindah"
RUTE_PINDAH_BANYAK = "/lembaga/pindah-banyak"
BATAS_FORM = 4096
# Pindah banyak: satu `ke` + id anak berulang; sedikit di atas batas agar kelebihan
# dijawab pesan ramah (store), bukan 400. Lewat itu = form tidak sah.
_BATAS_FIELD_BANYAK = 2 * toko.BATAS_PINDAH_BANYAK + 2
# Kode pesan hasil pindah banyak (status store -> kode tampil).
_KODE_BANYAK = {
    toko.STATUS_SAMA: "banyak_sama",
    toko.STATUS_SESI_BERJALAN: "banyak_sesi",
    toko.STATUS_BENTROK_NAMA: "banyak_nama",
    toko.STATUS_TERLALU_BANYAK: "banyak_terlalu",
}
_POLA_JUMLAH = re.compile(r"[1-9][0-9]{0,2}")
_POLA_ID = re.compile(r"[1-9][0-9]{0,17}")
_BATAS_NAMA_GURU = 200


def _tidak_ada(penangan) -> None:
    """Jawaban sama persis dengan fallthrough GET rute tak dikenal."""
    penangan._kirim(halaman_pesan("404", "<h1>Halaman tidak ada</h1>"), 404)


def _alihkan(penangan, tujuan: str) -> None:
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def _pemilik_guru(penangan):
    """(pengguna, peran) bila peran guru, selain itu None (admin tidak pernah pemilik)."""
    ident = penangan._identitas()
    return ident if ident and ident[1] == "guru" else None


def _baca_form(penangan):
    """Form urlencoded kecil dengan kunci tunggal; None bila tidak sah."""
    tubuh = penangan._baca_tubuh(BATAS_FORM)
    if tubuh is None or penangan.headers.get_content_type() != "application/x-www-form-urlencoded":
        return None
    try:
        pasangan = urllib.parse.parse_qs(
            tubuh.decode("utf-8", "strict"), keep_blank_values=True,
            strict_parsing=bool(tubuh), max_num_fields=8,
        )
    except (UnicodeDecodeError, ValueError):
        return None
    if any(len(v) != 1 for v in pasangan.values()):
        return None
    return {k: v[0] for k, v in pasangan.items()}


def _isian_pindah(data):
    """(siswa_id, ke) hanya bila tepat dua kolom sah; selain itu None."""
    if data is None or set(data) != {"siswa_id", "ke"}:
        return None
    ke = data["ke"]
    if not _POLA_ID.fullmatch(data["siswa_id"]) or not ke or len(ke) > _BATAS_NAMA_GURU:
        return None
    return int(data["siswa_id"]), ke


def _baca_pasangan(penangan):
    """Pasangan (kunci, nilai) form urlencoded kecil, kunci boleh berulang; None bila tidak sah."""
    tubuh = penangan._baca_tubuh(BATAS_FORM)
    if tubuh is None or penangan.headers.get_content_type() != "application/x-www-form-urlencoded":
        return None
    try:
        return urllib.parse.parse_qsl(
            tubuh.decode("utf-8", "strict"), keep_blank_values=True,
            strict_parsing=bool(tubuh), max_num_fields=_BATAS_FIELD_BANYAK,
        )
    except (UnicodeDecodeError, ValueError):
        return None


def _isian_banyak(pasangan):
    """(tuple id anak, ke) bila bentuk sah: kolom hanya siswa_id (>=1, tanpa duplikat) + satu ke."""
    if pasangan is None or any(k not in ("siswa_id", "ke") for k, _ in pasangan):
        return None
    tujuan = [v for k, v in pasangan if k == "ke"]
    ids = [v for k, v in pasangan if k == "siswa_id"]
    if len(tujuan) != 1 or not tujuan[0] or len(tujuan[0]) > _BATAS_NAMA_GURU:
        return None
    if not ids or not all(_POLA_ID.fullmatch(v) for v in ids):
        return None
    angka = tuple(int(v) for v in ids)
    return (angka, tujuan[0]) if len(set(angka)) == len(angka) else None


def _kode_pesan(jalur_penuh: str) -> str:
    kueri = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query)
    nilai = (kueri.get("pesan") or [""])[0]
    return nilai if nilai in halaman.PESAN else ""


def _param_pesan(jalur_penuh: str, ringkas):
    """(jumlah, ke) dari kueri hanya bila sah: bilangan 1..batas dan guru penghuni lembaga ini.

    Nilai tidak sah jadi 0/"" (banner tidak tampil), jadi kueri buatan tidak memantulkan apa pun.
    """
    kueri = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query)
    teks = (kueri.get("jumlah") or [""])[0]
    jumlah = int(teks) if _POLA_JUMLAH.fullmatch(teks) else 0
    ke = (kueri.get("ke") or [""])[0]
    penghuni = {g.guru for g in ringkas}
    return (jumlah if jumlah <= toko.BATAS_PINDAH_BANYAK else 0), (ke if ke in penghuni else "")


def tangani_get(penangan, jalur: str) -> bool:
    """Dipanggil setelah palang sandi guru/admin."""
    if jalur not in (RUTE, RUTE_PINDAH, RUTE_PINDAH_BANYAK):
        return False
    ident = _pemilik_guru(penangan) if jalur == RUTE else None
    if ident is None:
        _tidak_ada(penangan)
        return True
    with database.buka() as kon:
        lembaga = toko.lembaga_milik(kon, ident[0])
        if lembaga is None:
            _tidak_ada(penangan)
            return True
        ringkas = toko.ringkasan(kon, lembaga)
        jumlah, ke = _param_pesan(penangan.path, ringkas)
        isi = halaman.halaman(lembaga, ringkas, _kode_pesan(penangan.path), ident,
                              jumlah=jumlah, ke=ke)
    penangan._kirim_privat(isi)
    return True


def _galat_form(penangan, galat: GalatForm) -> None:
    if galat.status == 429:
        penangan._kirim(halaman_pesan("Terlalu banyak permintaan", "<h1>Terlalu banyak permintaan</h1>"
                                      "<p>Coba lagi sebentar.</p>"), 429)
    else:
        penangan._tolak_isian(galat.status)


def _pindah_satu(penangan, kon, pengguna):
    """Pindah satu anak: lokasi PRG, None bila respons sudah dikirim, "" bila 404."""
    isian = _isian_pindah(_baca_form(penangan))
    if isian is None:
        penangan._tolak_isian()
        return None
    kon.execute("BEGIN IMMEDIATE")
    hasil = toko.pindahkan(kon, oleh=pengguna, siswa_id=isian[0], ke=isian[1])
    if hasil.berhasil:
        kon.commit()
        return _lokasi("pindah_ok")
    kon.rollback()
    return _lokasi(hasil.status) if hasil.status in toko.STATUS_PENOLAKAN_BISNIS else ""


def _pindah_banyak(penangan, kon, pengguna):
    """Pindah banyak anak sekaligus, semua-atau-tidak: lokasi PRG, None bila respons terkirim, "" bila 404."""
    isian = _isian_banyak(_baca_pasangan(penangan))
    if isian is None:
        penangan._tolak_isian()
        return None
    kon.execute("BEGIN IMMEDIATE")
    hasil = toko.pindahkan_banyak(kon, oleh=pengguna, siswa_ids=isian[0], ke=isian[1])
    if hasil.berhasil:
        kon.commit()
        return _lokasi("banyak_ok", jumlah=hasil.jumlah, ke=hasil.ke)
    kon.rollback()
    kode = _KODE_BANYAK.get(hasil.status)
    if kode is None:
        return ""
    if hasil.status in (toko.STATUS_SAMA, toko.STATUS_SESI_BERJALAN):
        return _lokasi(kode, jumlah=hasil.jumlah)  # jumlah anak bermasalah untuk pesan
    return _lokasi(kode)


def _lokasi(kode: str, **param) -> str:
    return "/lembaga?" + urllib.parse.urlencode({"pesan": kode, **param})


def tangani_post(penangan, jalur: str) -> bool:
    """Dipanggil setelah `_asal_sama_post` dan palang sandi guru/admin."""
    if jalur not in (RUTE_PINDAH, RUTE_PINDAH_BANYAK):
        return False
    ident = _pemilik_guru(penangan)
    if ident is None:
        _tidak_ada(penangan)
        return True
    proses = _pindah_satu if jalur == RUTE_PINDAH else _pindah_banyak
    with database.buka() as kon:
        if toko.lembaga_milik(kon, ident[0]) is None:
            _tidak_ada(penangan)
            return True
        try:
            _batasi_laju(penangan, ident[0])
        except GalatForm as galat:
            _galat_form(penangan, galat)
            return True
        tujuan = proses(penangan, kon, ident[0])
    if tujuan is None:
        return True
    if tujuan == "":
        _tidak_ada(penangan)
        return True
    _alihkan(penangan, tujuan)
    return True
