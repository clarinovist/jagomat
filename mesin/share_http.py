"""Permukaan HTTP tautan satu sesi dan aksi bagikan milik guru.

Token bearer tetap divalidasi oleh ``share_links``. Modul ini hanya mengatur
parsing request, urutan transaksi, dan pemetaan respons; primitive header tetap
milik ``web.Penangan``.
"""
from __future__ import annotations

import html
import json
import urllib.parse

import brand
import database
import share_links
from support_pages import halaman_pesan as _halaman


def tangani_tautan_get(penangan, jalur: str) -> bool:
    """Buka tepat satu lembar dari capability bearer tanpa membuat login."""
    if not jalur.startswith("/mulai/"):
        return False
    import student_pages

    token = jalur[len("/mulai/"):]
    tidak_ada = _halaman("404", "<h1>Halaman tidak ada</h1>")
    with database.buka() as kon:
        akses = share_links.ambil(kon, token)
        if not akses:
            penangan._kirim_tautan(tidak_ada, 404)
            return True
        isi = student_pages.halaman_kerja_baru(
            kon,
            int(akses["siswa_id"]),
            int(akses["sesi_id"]),
            jalur_aksi=f"/mulai/{token}",
            akses_tautan=True,
        )
    if isi is None:
        penangan._kirim_tautan(tidak_ada, 404)
        return True
    penangan._kirim_tautan(isi)
    return True


def tangani_tautan_post(penangan, jalur: str) -> bool:
    """Simpan jawaban hanya ke sesi yang ditunjuk token aktif."""
    if not jalur.startswith("/mulai/"):
        return False
    import students

    token = jalur[len("/mulai/"):]
    tidak_ada = _halaman("404", "<h1>Halaman tidak ada</h1>")
    panjang = int(penangan.headers.get("Content-Length", 0) or 0)
    if panjang > 1_000_000:
        penangan._kirim_tautan(_halaman(
            "Terlalu besar",
            "<h1>Isian terlalu besar</h1><p>Coba muat ulang halaman.</p>",
        ), 413)
        return True
    mentah = penangan.rfile.read(panjang).decode("utf-8")
    pasangan = urllib.parse.parse_qs(mentah, keep_blank_values=True)
    if any(len(nilai) != 1 for nilai in pasangan.values()):
        penangan._kirim_tautan(
            _halaman("Isian tidak sah", "<h1>Isian ganda tidak diizinkan</h1>"),
            400,
        )
        return True
    data = {nama: nilai[0] for nama, nilai in pasangan.items()}
    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        akses = share_links.ambil(kon, token)
        if not akses:
            penangan._kirim_tautan(tidak_ada, 404)
            return True
        siswa_id = int(akses["siswa_id"])
        sesi_id = int(akses["sesi_id"])
        if data.get("aksi") == "mulai":
            database.tandai_mulai(kon, sesi_id)
            kon.commit()
            penangan._kirim_tautan(
                json.dumps({"mulai": True}).encode("utf-8")
            )
            return True

        import student_submissions as kiriman
        aksi = data.get("aksi", "simpan")
        if aksi not in ("simpan", "selesai", "kirim_latihan", "kembali"):
            aksi = "simpan"
        try:
            kiriman.validasi_versi(kon, sesi_id, data)
            if aksi in ("kirim_latihan", "kembali"):
                kiriman.simpan_refleksi(kon, sesi_id, data)
                hasil = 0
            else:
                hasil = students.simpan_jawaban_murid(
                    kon, siswa_id, sesi_id, data
                )
        except ValueError as galat:
            kon.rollback()
            penangan._kirim_tautan(
                _halaman(
                    "Belum tersimpan",
                    f"<h1>Belum tersimpan</h1><p>{html.escape(str(galat))}</p>",
                ),
                getattr(galat, "status", 400),
            )
            return True
        if hasil is None:
            penangan._kirim_tautan(tidak_ada, 404)
            return True
        info_sesi = students.sesi_murid(kon, siswa_id, sesi_id)
        if aksi == "selesai" and kiriman.perlu_refleksi(
            kon, info_sesi, data
        ):
            from submission_pages import halaman_refleksi
            isi = halaman_refleksi(
                kon, siswa_id, sesi_id, f"/mulai/{token}"
            )
            kon.commit()
            penangan._kirim_tautan(isi)
            return True
        if hasil:
            database.tandai_mulai(kon, sesi_id)
        selesai = aksi in ("selesai", "kirim_latihan")
        kiriman_baru = not kon.execute(
            "SELECT 1 FROM pengiriman_sesi WHERE sesi_id=?", (sesi_id,)
        ).fetchone()
        if selesai:
            from reports import diagnosa_murid
            kiriman.arsipkan(kon, sesi_id, "tautan")
            diagnosa_murid(kon, sesi_id)
            database.tandai_mulai(kon, sesi_id)
            database.tandai_selesai(kon, sesi_id)
            isi = _halaman(
                "Jawaban tersimpan",
                "<h1>Hebat, selesai!</h1>"
                "<p>Semua jawabanmu sudah masuk. Gurumu akan memeriksanya.</p>",
            )
        else:
            import student_pages
            isi = student_pages.halaman_kerja_baru(
                kon, siswa_id, sesi_id, hasil,
                jalur_aksi=f"/mulai/{token}", akses_tautan=True,
            )
            if isi is None:
                penangan._kirim_tautan(tidak_ada, 404)
                return True
        kon.commit()
    if selesai:
        import product_analytics_http as analitik
        analitik.aktivitas_sesi(
            sesi_id, "latihan_dikirim", baru=kiriman_baru
        )
    penangan._kirim_tautan(isi)
    return True


def tangani_guru_post(penangan, jalur: str) -> bool:
    """Buat atau cabut tautan sesi setelah palang guru utama lolos."""
    if not (
        jalur.startswith("/sesi/")
        and jalur.endswith(("/bagikan", "/cabut-tautan"))
    ):
        return False
    try:
        sesi_id = int(jalur.split("/")[2])
    except (ValueError, IndexError):
        penangan._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
        return True
    ident = penangan._identitas()
    with database.buka() as kon:
        if not ident or not penangan._bisa_lihat_sesi(kon, sesi_id):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        info = kon.execute(
            """SELECT s.siswa_id, w.nama FROM sesi s
               JOIN siswa w ON w.id = s.siswa_id WHERE s.id = ?""",
            (sesi_id,),
        ).fetchone()
        if not info:
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        if jalur.endswith("/bagikan"):
            kon.execute("BEGIN IMMEDIATE")
            status = kon.execute(
                "SELECT selesai, dibatalkan FROM sesi WHERE id = ?", (sesi_id,)
            ).fetchone()
            if status is None:
                penangan._kirim(
                    _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                )
                return True
            if status["dibatalkan"] is not None:
                penangan._kirim_tautan(_halaman(
                    "Sesi dibatalkan",
                    "<h1>Sesi dibatalkan</h1>"
                    "<p>Tautan sesi tidak dapat dibuat. Riwayat tetap tersimpan; "
                    "kembali ke profil anak untuk melihat rencana berikutnya.</p>",
                ), 409)
                return True
            if status["selesai"]:
                penangan._kirim_tautan(_halaman(
                    "Sesi sudah selesai",
                    f"<h1>Sesi #{sesi_id} sudah selesai dikerjakan</h1>"
                    "<p>Tautan berbagi hanya untuk sesi yang belum selesai. "
                    "Anak bisa melihat hasilnya lewat akun latihannya setelah "
                    "kamu review.</p>",
                ), 400)
                return True
            token = share_links.buat(kon, sesi_id)
            kon.commit()
            tautan = f"{brand.URL_SITUS}/mulai/{token}"
            if penangan.headers.get("X-Requested-With") == "fetch":
                penangan._kirim_json({"tautan": tautan})
                return True
            from teacher_pages import halaman_bagikan_sesi
            isi = halaman_bagikan_sesi(
                sesi_id, info["siswa_id"], tautan, ident[0], ident[1],
            )
            penangan._kirim_tautan(isi)
            return True
        share_links.cabut(kon, sesi_id)
        qs = urllib.parse.urlencode({
            "section": "riwayat",
            "pesan": (
                f"Tautan sesi dicabut — sesi #{sesi_id} tidak bisa lagi "
                "dibuka dari link lama."
            ),
            "sorot": sesi_id,
        })
        tujuan = f"/anak/{info['siswa_id']}?{qs}"
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
    return True
