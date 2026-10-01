"""Permukaan HTTP sesi guru yang diekstrak dari dispatcher utama.

Modul ini mengatur parsing, kepemilikan, pemanggilan layanan sesi, dan pemetaan
respons. ``web.Penangan`` tetap memiliki primitive respons, identitas, dan
ordered dispatch. Dependency pembuatan sesi diterima dari façade ``web`` agar
lookup runtime yang dipakai caller/monkeypatch lama tetap kompatibel.
"""
from __future__ import annotations

import html
import urllib.parse

import database
from support_pages import halaman_pesan as _halaman


def tangani_pembuatan_biasa(
    penangan,
    jalur: str,
    *,
    buat_sesi,
    topik_bawaan: str,
    daftar_topik,
) -> bool:
    """Tangani ``POST /sesi-baru/<siswa_id>``; False untuk jalur lain."""
    if not jalur.startswith("/sesi-baru/"):
        return False

    try:
        siswa_id = int(jalur.split("/")[2])
    except (ValueError, IndexError):
        penangan._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
        return True

    panjang = int(penangan.headers.get("Content-Length", 0) or 0)
    data = urllib.parse.parse_qs(
        penangan.rfile.read(panjang).decode("utf-8"),
        keep_blank_values=True,
    )
    pilihan_topik = (data.get("topik") or [topik_bawaan])[0].strip()
    aksi_form = data.get("aksi_form", [])
    versi_pilihan = data.get("versi_pilihan_isi", [])
    topik_dibandingkan = data.get("topik_dibandingkan", [])
    if aksi_form:
        penangan._kirim(
            _halaman(
                "Form lama",
                "<p>Pilihan variasi sudah otomatis. Muat ulang halaman anak.</p>",
            ),
            409,
        )
        return True
    if pilihan_topik not in daftar_topik():
        # Topik asing ditolak jelas, bukan jatuh diam-diam ke topik bawaan.
        pesan = (
            f"<h1>Topik tidak dikenal</h1>"
            f"<p><code>{html.escape(pilihan_topik)}</code> tidak "
            f"terdaftar. Yang tersedia: "
            f"{', '.join(html.escape(t) for t in daftar_topik())}.</p>"
        )
        penangan._kirim(_halaman("Topik tidak dikenal", pesan), 400)
        return True
    if versi_pilihan or topik_dibandingkan:
        penangan._kirim(
            _halaman(
                "Form lama",
                "<p>Pilihan variasi sudah otomatis. Muat ulang halaman anak.</p>",
            ),
            409,
        )
        return True

    sesi_id = None
    nama_siswa = None
    with database.buka() as kon:
        if not penangan._bisa_lihat_siswa(kon, siswa_id):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        siswa = kon.execute(
            "SELECT nama, tingkat FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()
        if not siswa:
            penangan._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
            return True

        from question_context import profil_otomatis, validasi_pilihan
        try:
            profil_lama = data.get("profil_parameter", [])
            if profil_lama:
                if len(profil_lama) != 1:
                    raise ValueError(
                        "Pilihan variasi soal tidak sah. Muat ulang form."
                    )
                level = profil_lama[0]
                validasi_pilihan([pilihan_topik], level)
            else:
                level = profil_otomatis([pilihan_topik], siswa["tingkat"])
        except ValueError as galat:
            penangan._kirim(
                _halaman(
                    "Latihan belum dibuat",
                    "<p>" + html.escape(str(galat)) + "</p>",
                ),
                400,
            )
            return True

        nama_siswa = siswa["nama"]
        pilihan_mode = (data.get("mode") or ["diagnostik"])[0].strip()
        if pilihan_mode not in ("diagnostik", "drill"):
            pesan = (
                f"<h1>Mode tidak dikenal</h1>"
                f"<p><code>{html.escape(pilihan_mode)}</code> tidak terdaftar. "
                "Yang tersedia: diagnostik (Diagnosa), drill (Latihan Cepat).</p>"
            )
            penangan._kirim(_halaman("Mode tidak dikenal", pesan), 400)
            return True

        timer_mode, durasi_menit, timer_auto = "tanpa", 15, 0
        if pilihan_mode == "drill":
            timer_mode = (data.get("timer_mode") or ["tanpa"])[0].strip()
            if timer_mode not in ("tanpa", "sesi", "soal"):
                pesan = (
                    f"<h1>Timer tidak dikenal</h1>"
                    f"<p><code>{html.escape(timer_mode)}</code> tidak terdaftar. "
                    "Yang tersedia: tanpa (tanpa timer), sesi (per sesi, tampil jalan), "
                    "soal (per soal, internal).</p>"
                )
                penangan._kirim(_halaman("Timer tidak dikenal", pesan), 400)
                return True
            if timer_mode in ("sesi", "soal"):
                nilai_durasi = (data.get("durasi_menit") or [""])[0].strip()
                try:
                    durasi_diajukan = int(nilai_durasi)
                except ValueError:
                    durasi_diajukan = 0
                if not 1 <= durasi_diajukan <= 180:
                    pesan = (
                        "<h1>Durasi tidak wajar</h1>"
                        f"<p>Durasi Latihan Cepat harus angka 1–180 menit "
                        f"(terima: {html.escape(nilai_durasi or '(kosong)')}).</p>"
                    )
                    penangan._kirim(_halaman("Durasi tidak wajar", pesan), 400)
                    return True
                durasi_menit = durasi_diajukan
                timer_auto = (
                    1 if (data.get("timer_auto") or ["0"])[0] == "1" else 0
                )

        nilai_jumlah = (data.get("jumlah_soal") or [""])[0].strip()
        jumlah_soal = (
            int(nilai_jumlah)
            if nilai_jumlah.isdigit() and 1 <= int(nilai_jumlah) <= 50
            else None
        )
        try:
            from choice_pages import format_dari_form
            sesi_id = buat_sesi(
                kon,
                siswa_id,
                level=level,
                topik=pilihan_topik,
                mode=pilihan_mode,
                timer_mode=timer_mode,
                durasi_menit=durasi_menit,
                timer_auto=timer_auto,
                jumlah_soal=jumlah_soal,
                format_jawaban=format_dari_form(data),
            )
        except ValueError as galat:
            penangan._kirim(
                _halaman(
                    "Latihan belum dibuat",
                    "<p>" + html.escape(str(galat)) + "</p>",
                ),
                400,
            )
            return True

    # PRG tetap menuju profil anak; refresh tidak membuat sesi kedua.
    pesan_sukses = (
        f"Sesi baru untuk {nama_siswa} berhasil dibuat — "
        f"sesi #{sesi_id} siap dikerjakan."
    )
    qs = urllib.parse.urlencode({"pesan": pesan_sukses, "sorot": sesi_id})
    penangan.send_response(303)
    penangan.send_header("Location", f"/anak/{siswa_id}?{qs}")
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
    return True


def tangani_pembuatan_gabungan(
    penangan,
    jalur: str,
    *,
    daftar_topik,
    acak_seed,
) -> bool:
    """Tangani ``POST /sesi-gabungan/<siswa_id>``; False untuk jalur lain."""
    if not jalur.startswith("/sesi-gabungan/"):
        return False

    try:
        siswa_id = int(jalur.split("/")[2])
    except (ValueError, IndexError):
        penangan._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
        return True

    panjang = int(penangan.headers.get("Content-Length", 0) or 0)
    data = urllib.parse.parse_qs(
        penangan.rfile.read(panjang).decode("utf-8"),
        keep_blank_values=True,
    )
    # Checkbox bernama sama menghasilkan daftar nilai.
    dipilih = [topik.strip() for topik in data.get("topik", []) if topik.strip()]
    aksi_form = data.get("aksi_form", [])
    versi_pilihan = data.get("versi_pilihan_isi", [])
    topik_dibandingkan = data.get("topik_dibandingkan", [])
    if aksi_form:
        penangan._kirim(
            _halaman(
                "Form lama",
                "<p>Pilihan variasi sudah otomatis. Muat ulang halaman anak.</p>",
            ),
            409,
        )
        return True

    sah = set(daftar_topik())
    asing = [topik for topik in dipilih if topik not in sah]
    if asing:
        penangan._kirim(
            _halaman(
                "Topik tidak dikenal",
                "<h1>Topik tidak dikenal</h1><p>"
                + ", ".join(html.escape(topik) for topik in asing)
                + " tidak terdaftar.</p>",
            ),
            400,
        )
        return True
    if versi_pilihan or topik_dibandingkan:
        penangan._kirim(
            _halaman(
                "Form lama",
                "<p>Pilihan variasi sudah otomatis. Muat ulang halaman anak.</p>",
            ),
            409,
        )
        return True

    try:
        jumlah = int((data.get("jumlah_soal") or ["10"])[0] or 10)
    except ValueError:
        jumlah = 10
    if not 1 <= jumlah <= 50:
        jumlah = 10

    if len(dipilih) < 2:
        qs = urllib.parse.urlencode({
            "pesan": "Pilih minimal DUA topik untuk latihan gabungan. "
                     "Kalau hanya satu, pakai form buat sesi biasa.",
        })
        penangan.send_response(303)
        penangan.send_header("Location", f"/anak/{siswa_id}?{qs}")
        penangan.send_header("Content-Length", "0")
        penangan.end_headers()
        return True

    with database.buka() as kon:
        if not penangan._bisa_lihat_siswa(kon, siswa_id):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        baris = kon.execute(
            "SELECT nama, tingkat FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()
        nama_siswa = baris["nama"] if baris else ""
        # Gabungan baru default cepat; pilihan diagnostik tetap eksplisit.
        mode_dikirim = data.get("mode", ["drill"])
        if (
            len(mode_dikirim) != 1
            or mode_dikirim[0] not in ("drill", "diagnostik")
        ):
            penangan._kirim(
                _halaman(
                    "Mode tidak dikenal",
                    "<h1>Mode tidak dikenal</h1>"
                    "<p>Pilih satu mode: Latihan Cepat atau Diagnostik.</p>",
                ),
                400,
            )
            return True
        try:
            from choice_pages import format_dari_form
            from question_context import profil_otomatis, validasi_pilihan
            profil_lama = data.get("profil_parameter", [])
            if profil_lama:
                if len(profil_lama) != 1:
                    raise ValueError(
                        "Pilihan variasi soal tidak sah. Muat ulang form."
                    )
                profil = profil_lama[0]
                validasi_pilihan(dipilih, profil)
            else:
                profil = profil_otomatis(
                    dipilih, baris["tingkat"] if baris else "P3"
                )
            sesi_id = database.buat_sesi_gabungan(
                kon,
                siswa_id,
                seed=acak_seed(1, 9_999_999),
                topik_ids=dipilih,
                level=profil,
                mode=mode_dikirim[0],
                jumlah_soal=jumlah,
                format_jawaban=format_dari_form(data),
            )
        except ValueError as galat:
            penangan._kirim(
                _halaman(
                    "Latihan belum dibuat",
                    "<p>" + html.escape(str(galat)) + "</p>",
                ),
                400,
            )
            return True

    qs = urllib.parse.urlencode({
        "pesan": (
            f"Latihan gabungan untuk {nama_siswa} dibuat — "
            f"sesi #{sesi_id}, {jumlah} soal dari {len(dipilih)} topik."
        ),
        "sorot": sesi_id,
    })
    penangan.send_response(303)
    penangan.send_header("Location", f"/anak/{siswa_id}?{qs}")
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
    return True
