"""Rute baca-saja `/laporan-ortu/<token>` untuk orang tua (tanpa login).

Seluruh keadaan tidak sah (token salah/kedaluwarsa/dicabut, laporan masih draf,
anak dihapus) menghasilkan satu halaman 404 identik. Query string diabaikan dan
rute ini tidak menulis apa pun ke basis data.
"""
from __future__ import annotations

import re
import urllib.parse
from datetime import date, timedelta

import brand
import database
import parent_report_guru_pages as guru_pages
import parent_report_page as halaman
import parent_report_snapshot as snapshot
import parent_report_store as toko

AWALAN = "/laporan-ortu/"
POLOS = "/laporan-ortu"  # dispatcher dapat membuang garis miring akhir
CSP = ("default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
       "form-action 'none'; base-uri 'none'; frame-ancestors 'none'")


def _kirim_tidak_ada(penangan) -> None:
    penangan._kirim_tautan(halaman.render_tidak_dapat_dibuka(), 404, csp=CSP)


def tangani_get(penangan, jalur: str) -> bool:
    if jalur != POLOS and not jalur.startswith(AWALAN):
        return False
    token = jalur[len(AWALAN):]
    with database.buka() as kon:
        data = toko.ambil_dengan_token(kon, token)
    if data is None:
        _kirim_tidak_ada(penangan)
        return True
    penangan._kirim_tautan(halaman.render_laporan(**data), 200, csp=CSP)
    return True


def tangani_post(penangan, jalur: str) -> bool:
    """Halaman ini tidak punya formulir; POST apa pun tidak berefek."""
    if jalur != POLOS and not jalur.startswith(AWALAN):
        return False
    _kirim_tidak_ada(penangan)
    return True


# ── Sisi guru: setelah palang login, sebelum penangan profil `/anak/<id>/...` ──
_POLA_GURU = re.compile(
    r"/anak/(\d{1,18})/laporan-ortu(?:/(\d{1,18})(?:/(catatan|terbitkan|tautan/cabut|tautan|hapus))?)?"
)
BATAS_FORM = 20_000
BATAS_RENTANG_HARI = 366


def _tidak_ada(penangan) -> None:
    from support_pages import halaman_pesan

    penangan._kirim(halaman_pesan("404", "<h1>Halaman tidak ada</h1>"), 404)


def _alihkan(penangan, tujuan: str) -> None:
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def periode_dari_form(data: dict, hari_ini: date):
    """(mulai, akhir) ISO dari pilihan periode, atau None bila tidak sah."""
    pilihan = data.get("periode", "")
    if pilihan == "30hari":
        return (hari_ini - timedelta(days=29)).isoformat(), hari_ini.isoformat()
    if pilihan == "bulan":
        return hari_ini.replace(day=1).isoformat(), hari_ini.isoformat()
    if pilihan != "rentang":
        return None
    try:
        mulai, akhir = date.fromisoformat(data.get("dari", "")), date.fromisoformat(data.get("sampai", ""))
    except ValueError:
        return None
    if mulai > akhir or akhir > hari_ini or (akhir - mulai).days > BATAS_RENTANG_HARI:
        return None
    return mulai.isoformat(), akhir.isoformat()


def _baca_form(penangan):
    """Form urlencoded kecil; None bila terlalu besar, salah bentuk, atau berisi kunci ganda."""
    tubuh = penangan._baca_tubuh(BATAS_FORM)
    if tubuh is None:
        return None
    try:
        pasangan = urllib.parse.parse_qs(tubuh.decode("utf-8", "strict"), keep_blank_values=True, max_num_fields=16)
    except (UnicodeDecodeError, ValueError):
        return None
    if any(len(v) != 1 for v in pasangan.values()):
        return None
    return {k: v[0] for k, v in pasangan.items()}


def _kirim_galat(penangan, isi: bytes, kode: int) -> None:
    penangan._kirim_tautan(isi, kode)


def tangani_guru_get(penangan, jalur: str) -> bool:
    cocok = _POLA_GURU.fullmatch(jalur)
    if cocok is None:
        return False
    anak_id, lid, aksi = int(cocok.group(1)), cocok.group(2), cocok.group(3)
    ident = penangan._identitas()
    with database.buka() as kon:
        siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (anak_id,)).fetchone()
        if siswa is None or aksi or not penangan._bisa_lihat_siswa(kon, anak_id):
            _tidak_ada(penangan)
            return True
        hanya_lihat = not ident or ident[1] != "guru"
        if lid is None:
            isi = guru_pages.halaman_daftar(
                siswa, toko.daftar(kon, anak_id), toko.tautan_aktif(kon, anak_id), ident, hanya_lihat=hanya_lihat)
        else:
            lap = toko.ambil(kon, anak_id, int(lid))
            if lap is None:
                _tidak_ada(penangan)
                return True
            isi = guru_pages.halaman_detail(
                siswa, lap, ident, tautan=toko.tautan_aktif(kon, anak_id),
                berubah=toko.bukti_berubah(kon, anak_id, lap["id"]), hanya_lihat=hanya_lihat)
    penangan._kirim_tautan(isi)
    return True


def tangani_guru_post(penangan, jalur: str) -> bool:
    cocok = _POLA_GURU.fullmatch(jalur)
    if cocok is None:
        return False
    anak_id, lid, aksi = int(cocok.group(1)), cocok.group(2), cocok.group(3)
    ident = penangan._identitas()
    with database.buka() as kon:
        siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (anak_id,)).fetchone()
        if siswa is None or not penangan._bisa_lihat_siswa(kon, anak_id):
            _tidak_ada(penangan)
            return True
        if lid is not None and toko.ambil(kon, anak_id, int(lid)) is None:
            _tidak_ada(penangan)
            return True
        if not ident or ident[1] != "guru":
            from support_pages import halaman_pesan

            penangan._kirim(halaman_pesan("Hanya guru", "<h1>Hanya guru yang dapat mengubah laporan</h1>"), 403)
            return True
        if (lid is None) != (aksi is None):
            if lid is not None:
                _tidak_ada(penangan)
                return True
        data = _baca_form(penangan)
        if data is None:
            _kirim_galat(penangan, guru_pages.halaman_daftar(
                siswa, toko.daftar(kon, anak_id), None, ident, galat="Isian tidak sah atau terlalu besar."), 400)
            return True
        kon.execute("BEGIN IMMEDIATE")
        if lid is None:
            return _buat(penangan, kon, siswa, ident, data)
        return _aksi_laporan(penangan, kon, siswa, ident, int(lid), aksi, data)


def _buat(penangan, kon, siswa, ident, data) -> bool:
    from report_metrics import hari_wib

    periode = periode_dari_form(data, hari_wib())
    if periode is None:
        _kirim_galat(penangan, guru_pages.halaman_daftar(
            siswa, toko.daftar(kon, siswa["id"]), toko.tautan_aktif(kon, siswa["id"]), ident,
            galat="Periode tidak sah. Pilih periode yang ada, atau tanggal Dari sebelum Sampai (maksimal satu tahun, tidak melewati hari ini)."), 400)
        return True
    isi = snapshot.bangun(kon, siswa["id"], periode[0], periode[1])
    lid = toko.buat_draf(kon, siswa["id"], periode[0], periode[1], isi)
    kon.commit()
    _alihkan(penangan, f"/anak/{siswa['id']}/laporan-ortu/{lid}")
    return True


def _detail(penangan, kon, siswa, ident, lid, *, token="", galat="", kode=200, catatan_kiriman=None) -> bool:
    lap = toko.ambil(kon, siswa["id"], lid)
    isi = guru_pages.halaman_detail(
        siswa, lap, ident, tautan=toko.tautan_aktif(kon, siswa["id"]),
        berubah=toko.bukti_berubah(kon, siswa["id"], lid), galat=galat, catatan_kiriman=catatan_kiriman,
        token_url=f"{brand.URL_SITUS}/laporan-ortu/{token}" if token else "")
    penangan._kirim_tautan(isi, kode)
    return True


def _aksi_laporan(penangan, kon, siswa, ident, lid, aksi, data) -> bool:
    sid = siswa["id"]
    dasar = f"/anak/{sid}/laporan-ortu/{lid}"
    try:
        if aksi == "catatan":
            catatan = data.get("catatan", "").replace("\r\n", "\n").replace("\r", "\n")
            if len(catatan) > toko.BATAS_CATATAN:
                kon.rollback()
                return _detail(penangan, kon, siswa, ident, lid, galat="Catatan terlalu panjang (maksimal 2000 karakter).", kode=400)
            if guru_pages.PENANDA_ISI in catatan:
                kon.rollback()
                return _detail(penangan, kon, siswa, ident, lid, kode=400, catatan_kiriman=catatan, galat=(
                    f"Lengkapi setiap {guru_pages.PENANDA_ISI} di catatan atau hapus kalimatnya. Catatan belum disimpan."))
            toko.simpan_catatan(kon, sid, lid, catatan)
            kon.commit()
            _alihkan(penangan, dasar)
        elif aksi == "terbitkan":
            token = toko.terbitkan(kon, sid, lid, ident[0])
            kon.commit()
            return _detail(penangan, kon, siswa, ident, lid, token=token)
        elif aksi == "tautan":
            token = toko.ganti_tautan(kon, sid, lid)
            kon.commit()
            return _detail(penangan, kon, siswa, ident, lid, token=token)
        elif aksi == "tautan/cabut":
            toko.cabut_tautan(kon, sid)
            kon.commit()
            _alihkan(penangan, dasar)
        elif aksi == "hapus":
            toko.hapus_draf(kon, sid, lid)
            kon.commit()
            _alihkan(penangan, f"/anak/{sid}/laporan-ortu")
        else:
            _tidak_ada(penangan)
    except ValueError:
        kon.rollback()
        return _detail(penangan, kon, siswa, ident, lid,
                       galat="Aksi tidak dapat dilakukan pada laporan dengan status ini.", kode=409)
    return True
