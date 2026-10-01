"""Permukaan HTTP lampiran dan foto untuk guru/pengelola.

Parsing, kepemilikan, upload, dan pemetaan respons berada di sini. Primitive
respons serta provider fencing tetap dimiliki ``web.Penangan``.
"""
from __future__ import annotations

import html
import urllib.parse

import attachments as lampiran_mod
import database
from support_pages import halaman_pesan as _halaman
from teacher_pages import halaman_sesi_lampiran


def tangani_get(penangan, jalur: str) -> bool:
    """Tangani file/konfirmasi lampiran dan tab lampiran satu sesi."""
    if jalur.startswith("/lampiran/berkas/"):
        try:
            lampiran_id = int(jalur.rsplit("/", 1)[1])
        except (ValueError, IndexError):
            penangan._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
            return True
        with database.buka() as kon:
            _kirim_berkas(penangan, kon, lampiran_id)
        return True

    if jalur.startswith("/lampiran/"):
        try:
            lampiran_id = int(jalur.split("/")[2])
        except (ValueError, IndexError):
            penangan._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
            return True
        with database.buka() as kon:
            if not penangan._bisa_lihat_lampiran(kon, lampiran_id):
                penangan._kirim(
                    _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                )
                return True
            isi = lampiran_mod.halaman_konfirmasi(kon, lampiran_id)
        if isi:
            penangan._kirim(isi)
        else:
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
        return True

    if jalur.startswith("/sesi/") and jalur.endswith("/lampiran"):
        try:
            sesi_id = int(jalur.split("/")[2])
        except (ValueError, IndexError):
            penangan._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
            return True
        with database.buka() as kon:
            if not penangan._bisa_lihat_sesi(kon, sesi_id):
                penangan._kirim(
                    _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                )
                return True
            ident = penangan._identitas()
            isi = halaman_sesi_lampiran(
                kon, sesi_id,
                peran=ident[1] if ident else "guru",
                pengguna=ident[0] if ident else "",
            )
        if isi is None:
            penangan._kirim(_halaman("404", "<h1>Sesi tidak ada</h1>"), 404)
        else:
            penangan._kirim(isi)
        return True

    return False


def _kirim_berkas(penangan, kon, lampiran_id: int) -> None:
    """Kirim isi foto hanya bila lampiran dan sesi berada dalam scope akun."""
    lampiran = database.ambil_lampiran(kon, lampiran_id)
    if not lampiran or not penangan._bisa_lihat_sesi(
        kon, int(lampiran["sesi_id"])
    ):
        penangan._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
        return
    berkas = (
        lampiran_mod.direktori_lampiran()
        / str(lampiran["sesi_id"])
        / lampiran["nama_berkas"]
    )
    try:
        isi = berkas.read_bytes()
    except OSError:
        penangan._kirim(_halaman("404", "<h1>Berkas hilang</h1>"), 404)
        return
    penangan.send_response(200)
    penangan.send_header("Content-Type", lampiran["mime"])
    penangan.send_header("Content-Length", str(len(isi)))
    penangan.send_header("Cache-Control", "private, max-age=3600")
    penangan.end_headers()
    penangan.wfile.write(isi)


def tangani_post(penangan, jalur: str) -> bool:
    """Tangani baca ulang, penerapan, atau upload foto lampiran."""
    if not jalur.startswith("/lampiran/"):
        return False
    bagian = jalur.split("/")
    try:
        angka = int(bagian[2])
    except (ValueError, IndexError):
        penangan._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
        return True

    if len(bagian) >= 4 and bagian[3] == "baca-ulang":
        _baca_ulang(penangan, angka)
        return True
    if len(bagian) >= 4 and bagian[3] == "terapkan":
        _terapkan(penangan, angka)
        return True
    _unggah(penangan, angka)
    return True


def _baca_ulang(penangan, lampiran_id: int) -> None:
    with database.buka() as kon:
        if not penangan._bisa_lihat_lampiran(kon, lampiran_id):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return
        terjaga = lampiran_mod.penegakan_foto()
        if not terjaga:
            pesan = lampiran_mod.baca_ulang(kon, lampiran_id)
            isi = lampiran_mod.halaman_konfirmasi(kon, lampiran_id, pesan)
            if isi is None:
                penangan._kirim(
                    _halaman("404", "<h1>Lampiran hilang</h1>"), 404
                )
            else:
                penangan._kirim(isi)
            return
        sesi_foto = database.ambil_lampiran(kon, lampiran_id)["sesi_id"]

    panjang = int(penangan.headers.get("Content-Length", 0) or 0)
    if not 0 < panjang <= 512:
        penangan._kirim(
            _halaman("Ditolak", "<h1>Permintaan foto tidak sah</h1>"), 400
        )
        return
    try:
        bidang = urllib.parse.parse_qs(
            penangan.rfile.read(panjang).decode("utf-8"), keep_blank_values=True
        )
    except UnicodeError:
        penangan._kirim(
            _halaman("Ditolak", "<h1>Permintaan foto tidak sah</h1>"), 400
        )
        return
    if set(bidang) != {"operasi_foto"} or len(bidang["operasi_foto"]) != 1:
        penangan._kirim(
            _halaman("Ditolak", "<h1>Permintaan foto tidak sah</h1>"), 400
        )
        return
    _lid, pesan = penangan._proses_foto_terjaga(
        sesi_foto, target_id=lampiran_id,
        operasi_id=bidang["operasi_foto"][0],
    )
    if pesan == "not_found":
        penangan._kirim(
            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
        )
        return
    with database.buka() as kon:
        if not penangan._bisa_lihat_lampiran(kon, lampiran_id):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return
        penangan._kirim(
            lampiran_mod.halaman_konfirmasi(kon, lampiran_id, pesan)
        )


def _terapkan(penangan, lampiran_id: int) -> None:
    panjang = int(penangan.headers.get("Content-Length", 0) or 0)
    mentah = penangan.rfile.read(panjang).decode("utf-8")
    data = {
        nama: nilai[0]
        for nama, nilai in urllib.parse.parse_qs(
            mentah, keep_blank_values=True
        ).items()
    }
    with database.buka() as kon:
        if not penangan._bisa_lihat_lampiran(kon, lampiran_id):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return
        info_lampiran = database.ambil_lampiran(kon, lampiran_id)
        sesi_foto = info_lampiran["sesi_id"]
        sudah_kirim = kon.execute(
            "SELECT 1 FROM pengiriman_sesi WHERE sesi_id=?", (sesi_foto,)
        ).fetchone()
        _jumlah, pesan = lampiran_mod.terapkan(kon, lampiran_id, data)
        isi = lampiran_mod.halaman_konfirmasi(kon, lampiran_id, pesan)
        if isi is None:
            penangan._kirim(
                _halaman("404", "<h1>Lampiran hilang</h1>"), 404
            )
            return
        baru_kirim = not sudah_kirim and bool(kon.execute(
            "SELECT 1 FROM pengiriman_sesi WHERE sesi_id=?", (sesi_foto,)
        ).fetchone())
    ident = penangan._identitas()
    import product_analytics_http as analitik
    analitik.aktivitas_sesi(
        sesi_foto, "latihan_dikirim",
        pengguna=ident[0], peran=ident[1], baru=baru_kirim,
    )
    penangan._kirim(isi)


def _unggah(penangan, sesi_id: int) -> None:
    content_type = penangan.headers.get("Content-Type", "")
    panjang = int(penangan.headers.get("Content-Length", 0) or 0)
    if panjang > lampiran_mod.BATAS_UKURAN * 2:
        penangan._kirim(
            _halaman("Terlalu besar", "<h1>Upload terlalu besar</h1>"), 400
        )
        return
    tubuh = penangan.rfile.read(panjang)
    with database.buka() as kon:
        if not kon.execute(
            "SELECT 1 FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone() or not penangan._bisa_lihat_sesi(kon, sesi_id):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return
        terjaga = lampiran_mod.penegakan_foto()
        if not terjaga:
            lid, pesan = lampiran_mod.proses_upload(
                kon, sesi_id, content_type, tubuh
            )
    if terjaga:
        lid, pesan = penangan._proses_foto_terjaga(
            sesi_id, content_type=content_type, tubuh=tubuh
        )
        if pesan == "not_found":
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return
    if lid is None:
        penangan._kirim(
            _halaman(
                "Upload ditolak",
                f"<h1>Upload ditolak</h1><p>{html.escape(pesan)}</p>",
            ),
            400,
        )
        return
    penangan.send_response(303)
    penangan.send_header("Location", f"/lampiran/{lid}")
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
