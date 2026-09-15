"""Parser ketat dan handler POST permukaan guru siklus belajar."""
from __future__ import annotations

import html
import re
import threading
import time
import urllib.parse

import database
import learning_cycle_service as layanan

_POLA = re.compile(r"/(sesi|siklus)/([1-9][0-9]*)/(konfirmasi|batalkan|aksi|buat)")
_AKSI = {"sesi": {"konfirmasi", "batalkan"}, "siklus": {"aksi", "buat"}}
_BATAS_FORM = 1_000_000
_BATAS_PER_MENIT = 120
_riwayat = {}
_kunci_laju = threading.Lock()


def _batasi_laju(penangan, guru):
    """Batasi burst per akun/IP tanpa menahan transaksi database."""
    global _riwayat
    kini = time.monotonic()
    kunci = (penangan.server.server_address, guru, penangan.client_address[0])
    with _kunci_laju:
        aktif = {k: tuple(t for t in waktu if kini - t < 60)
                 for k, waktu in _riwayat.items() if waktu and kini - waktu[-1] < 60}
        waktu = aktif.get(kunci, ())
        if len(waktu) >= _BATAS_PER_MENIT:
            raise GalatForm("Terlalu banyak permintaan. Coba lagi sebentar.", 429)
        _riwayat = {**aktif, kunci: (*waktu, kini)}


class GalatForm(ValueError):
    """Permintaan tidak dapat dibaca secara aman."""

    def __init__(self, pesan: str, status: int = 400):
        super().__init__(pesan)
        self.status = status


def _baca_form(penangan) -> dict[str, str]:
    asal = penangan.headers.get("Origin")
    situs = penangan.headers.get("Sec-Fetch-Site")
    # no-referrer dapat membuat Origin null pada POST dari situs sendiri.
    # Pengecualian hanya dengan bukti same-origin dari header milik browser.
    if asal == "null":
        asal_ditolak = situs != "same-origin"
    else:
        asal_ditolak = bool(asal) and urllib.parse.urlsplit(asal).netloc != penangan.headers.get("Host")
    if asal_ditolak:
        raise GalatForm("Permintaan harus berasal dari situs ini.", 403)
    if situs == "cross-site":
        raise GalatForm("Permintaan harus berasal dari situs ini.", 403)
    panjang = penangan.headers.get("Content-Length", "0")
    if not re.fullmatch(r"[0-9]+", panjang) or penangan.headers.get("Transfer-Encoding"):
        raise GalatForm("Panjang isian tidak dikenal.")
    if int(panjang) > _BATAS_FORM:
        raise GalatForm("Isian terlalu besar.", 413)
    if penangan.headers.get_content_type() != "application/x-www-form-urlencoded":
        raise GalatForm("Format isian tidak dikenal.")
    try:
        mentah = penangan.rfile.read(int(panjang)).decode("utf-8")
        data = urllib.parse.parse_qs(mentah, keep_blank_values=True, errors="strict", max_num_fields=2000)
    except (UnicodeError, ValueError) as galat:
        raise GalatForm("Isian tidak dapat dibaca.") from galat
    if any(len(nilai) != 1 for nilai in data.values()):
        raise GalatForm("Isian ganda tidak diizinkan.")
    return {nama: nilai[0] for nama, nilai in data.items()}


def _tanpa_marker_transport(kon, sesi_id, data):
    """Validasi lalu buang marker draf sebelum boundary bukti resmi."""
    ids = {int(b["sesi_soal_id"]) for b in database.isi_sesi(kon, sesi_id)}
    hasil = dict(data)
    for nama in tuple(hasil):
        if nama == "hadir_sertakan_pemetaan":
            if hasil[nama] != "1":
                raise ValueError("marker formulir tidak sah")
            del hasil[nama]
            continue
        cocok = re.fullmatch(r"hadir_(?:dilewati|belum)_([1-9][0-9]*)", nama)
        if nama.startswith("hadir_"):
            if cocok is None or int(cocok[1]) not in ids or hasil[nama] != "1":
                raise ValueError("marker formulir tidak sah")
            del hasil[nama]
    return hasil


def _jalankan(kon, jenis, identitas, aksi, guru, data):
    if jenis == "sesi":
        if aksi == "konfirmasi":
            layanan.konfirmasi_dari_form(
                kon, identitas, guru, _tanpa_marker_transport(kon, identitas, data)
            )
            return f"/sesi/{identitas}"
        if set(data) - {"alasan"}:
            raise ValueError("Isian pembatalan tidak dikenal.")
        siswa_id = layanan.batalkan_sesi(kon, identitas, data.get("alasan", ""))
        return f"/anak/{siswa_id}"
    if aksi == "aksi":
        layanan.proses_aksi(kon, identitas, data)
        return f"/anak/{identitas}"
    if data:
        raise GalatForm("Rencana dihitung ulang oleh server.")
    sesi_id, _ = layanan.buat_dari_rekomendasi(kon, identitas)
    return f"/sesi/{sesi_id}"


def tangani(penangan, jalur: str, halaman) -> None:
    """Tegakkan kepemilikan sebelum payload; commit sebelum redirect."""
    cocok = _POLA.fullmatch(jalur)
    if not cocok or cocok[3] not in _AKSI[cocok[1]]:
        return penangan._kirim(halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
    jenis, nomor, aksi = cocok.groups()
    identitas = int(nomor)
    guru = penangan._identitas()
    with database.buka() as kon:
        boleh = penangan._bisa_lihat_sesi if jenis == "sesi" else penangan._bisa_lihat_siswa
        if not guru or not boleh(kon, identitas):
            return penangan._kirim(halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
        try:
            _batasi_laju(penangan, guru[0])
            data = _baca_form(penangan)
            kon.execute("BEGIN IMMEDIATE")
            tujuan = _jalankan(kon, jenis, identitas, aksi, guru[0], data)
        except layanan.KonfirmasiBelumLengkap as galat:
            kon.rollback()
            from teacher_pages import halaman_sesi_stitch

            return penangan._kirim_privat(halaman_sesi_stitch(
                kon, identitas, peran=guru[1], pengguna=guru[0],
                draf_koreksi=galat.draf, masalah_konfirmasi=galat.masalah,
                privat=True,
            ), 400)
        except (ValueError, GalatForm) as galat:
            kon.rollback()
            status = getattr(galat, "status", 409 if aksi in {"buat", "batalkan"} else 400)
            return penangan._kirim(halaman("Permintaan belum dapat diproses", "<h1>Permintaan belum dapat diproses</h1>" + f"<p>{html.escape(str(galat))}</p>"), status)
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
