"""Permukaan HTTP murid; parsing, palang akun, dan pemetaan respons.

Modul ini sengaja tidak diimpor balik oleh ``students`` atau ``student_pages``.
``web.Penangan`` tetap memiliki primitive respons, identitas, dan provider foto;
rute di sini hanya mengatur alur HTTP murid di atas primitive tersebut.
"""
from __future__ import annotations

import html
import urllib.parse

import attachments as lampiran_mod
import database
from support_pages import halaman_pesan_murid as _halaman

PESAN_SESI_HABIS = ("Sesi kamu sudah habis atau akun lain masuk di perangkat ini. "
                    "Masuk lagi dengan nama & sandimu, ya.")


def alamat_masuk_murid(penangan) -> str:
    """Tujuan 303 saat murid belum sah: pesan sesi habis hanya bila ada kuki sesi.

    Anak yang belum pernah masuk (tanpa kuki/Basic) cukup melihat form /masuk polos;
    kredensial yang ada tetapi tidak sah untuk murid (kedaluwarsa, akun lain, peran
    bukan murid) tetap diberi tahu alasannya. Status dan palang tidak berubah.
    """
    if not penangan._ambil_token() and not penangan.headers.get("Authorization"):
        return "/masuk"
    return "/masuk?" + urllib.parse.urlencode({"galat": PESAN_SESI_HABIS})


def _id_akun(pengguna: str):
    """`id_akun` akun murid ini (None bila akun warisan tanpa id)."""
    import auth

    akun = auth.cari_akun(pengguna)
    return None if akun is None else akun.get("id_akun")


def tangani_get(penangan, jalur: str, jalur_penuh: str = "") -> bool:
    """Tangani seluruh GET ``/murid``; False bila jalur bukan milik modul."""
    if jalur != "/murid" and not jalur.startswith("/murid/"):
        return False
    try:
        with database.buka() as kon:
            _get(penangan, kon, jalur, jalur_penuh)
    except (ValueError, IndexError):
        penangan._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
    return True


def _get(penangan, kon, jalur: str, jalur_penuh: str) -> None:
    """Rute GET murid dengan koneksi yang sudah dibuka caller dispatch."""
    import student_pages
    import students

    kredensial = penangan._sesi_atau_basic(peran_wajib="murid")
    if not kredensial:
        penangan.send_response(303)
        penangan.send_header("Location", alamat_masuk_murid(penangan))
        penangan.send_header("Content-Length", "0")
        penangan.end_headers()
        return

    siswa_id = students.siswa_dari_akun(kon, kredensial[0])
    if siswa_id is None:
        nama = html.escape(kredensial[0])
        penangan._kirim(_halaman(
            "Belum terhubung",
            f"<h1>Halo, {nama}</h1>"
            "<p>Akunmu belum dihubungkan ke daftar siswa. "
            "Minta gurumu menyiapkannya.</p>",
        ))
        return

    import orang_tua_http
    if jalur == orang_tua_http.RUTE and orang_tua_http.tangani_get(penangan, kon, siswa_id):
        return

    if jalur == "/murid":
        sesi_selesai = None
        if jalur_penuh:
            q = urllib.parse.parse_qs(
                urllib.parse.urlparse(jalur_penuh).query
            )
            try:
                sesi_selesai = int(q.get("selesai", ["0"])[0]) or None
            except (ValueError, TypeError):
                sesi_selesai = None
        import cek_murid
        import contest_gate
        import contest_http
        import domain_clock
        import guru_tugas_kartu
        import harian_http
        import jadwal_anak_kartu
        kartu_cek, sembunyikan_sesi = cek_murid.untuk_beranda(kon, _id_akun(kredensial[0]), siswa_id)
        kartu_jadwal = jadwal_anak_kartu.kartu_beranda_untuk(_id_akun(kredensial[0]), siswa_id)
        kartu_tugas, sembunyi_tugas = guru_tugas_kartu.tugas_beranda_untuk(kon, siswa_id, domain_clock.hari_wib())
        penangan._kirim(student_pages.halaman_daftar_sesi_baru(
            kon, siswa_id, kredensial[0], sesi_selesai, lomba_aktif=contest_gate.aktif_untuk(kon, siswa_id),
            sekarang=contest_http._sekarang(), orang_tua=orang_tua_http.tersedia(),
            kartu_cek=kartu_cek, sembunyikan_sesi=sembunyikan_sesi | sembunyi_tugas,
            kartu_harian=harian_http.kartu_beranda_untuk(kon, siswa_id), kartu_jadwal=kartu_jadwal,
            kartu_tugas=kartu_tugas,
        ))
        return

    bagian = jalur.split("/")
    if len(bagian) >= 4 and bagian[2] == "hasil":
        try:
            sesi_id_hasil = int(bagian[3])
        except ValueError:
            penangan._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
            return
        isi = student_pages.halaman_hasil_murid(
            kon, siswa_id, sesi_id_hasil
        )
        if isi is None:
            penangan._kirim(
                _halaman(
                    "Belum ada hasil",
                    "<h1>Belum ada hasil</h1><p>Sesi ini belum selesai "
                    "diperiksa gurumu. Coba lagi nanti, ya.</p>"
                    '<p><a href="/murid">Kembali ke daftar sesi</a></p>',
                ),
                404,
            )
            return
        penangan._kirim(isi)
        return

    if len(bagian) >= 3 and bagian[2] == "kerjakan":
        tersimpan = 0
        if jalur_penuh:
            q = urllib.parse.parse_qs(
                urllib.parse.urlparse(jalur_penuh).query
            )
            try:
                tersimpan = max(0, min(99, int(q.get("tersimpan", ["0"])[0])))
            except (ValueError, TypeError):
                tersimpan = 0
        sesi_id_kerja = int(bagian[3])
        kabar_foto = ""
        foto_galat = False
        if jalur_penuh:
            q_foto = urllib.parse.parse_qs(
                urllib.parse.urlparse(jalur_penuh).query
            )
            kabar_foto = (q_foto.get("foto", [""])[0] or "")[:200]
            foto_galat = q_foto.get("foto_galat", [""])[0] == "1"
        if students.sesi_murid(kon, siswa_id, sesi_id_kerja):
            database.tandai_mulai(kon, sesi_id_kerja)
            kon.commit()
        isi = student_pages.halaman_kerja_baru(
            kon, siswa_id, sesi_id_kerja, tersimpan,
            kabar_foto=kabar_foto, foto_galat=foto_galat,
        )
        if isi is None:
            penangan._kirim(
                _halaman("404", "<h1>Sesi tidak ada</h1>"), 404
            )
            return
        penangan._kirim(isi)
        return

    penangan._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)


def tangani_post(penangan, jalur: str) -> bool:
    """Tangani POST jawaban/foto murid; False untuk jalur lain."""
    if jalur.startswith("/murid/kerjakan/"):
        _post_kerjakan(penangan, jalur)
        return True
    if jalur.startswith("/murid/foto/"):
        _post_foto(penangan, jalur)
        return True
    import orang_tua_tautan_http
    if orang_tua_tautan_http.tangani_post(penangan, jalur):
        return True
    import orang_tua_http
    return orang_tua_http.tangani_post(penangan, jalur)


def _post_kerjakan(penangan, jalur: str) -> None:
    import students

    kredensial = penangan._sesi_atau_basic(peran_wajib="murid")
    if not kredensial:
        penangan._kirim(
            _halaman("Perlu masuk", "<h1>Halaman murid</h1>"), 401
        )
        return
    panjang = int(penangan.headers.get("Content-Length", 0))
    if panjang < 0 or panjang > 1_000_000:
        penangan._kirim(
            _halaman("Isian terlalu besar", "<h1>Isian terlalu besar</h1>"),
            413,
        )
        return
    mentah = penangan.rfile.read(panjang).decode("utf-8")
    pasangan = urllib.parse.parse_qs(mentah, keep_blank_values=True)
    if any(len(nilai) != 1 for nilai in pasangan.values()):
        penangan._kirim(
            _halaman("Isian tidak sah", "<h1>Isian ganda tidak diizinkan</h1>"),
            400,
        )
        return
    data = {nama: nilai[0] for nama, nilai in pasangan.items()}
    sesi_id = int(jalur.split("/")[3])
    aksi = data.get("aksi", "simpan")
    if aksi not in ("simpan", "selesai", "kirim_latihan", "kembali"):
        aksi = "simpan"

    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        siswa_id = students.siswa_dari_akun(kon, kredensial[0])
        info_sesi = (
            students.sesi_murid(kon, siswa_id, sesi_id)
            if siswa_id is not None else None
        )
        if not info_sesi or info_sesi.get("dibatalkan"):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return
        if info_sesi.get("selesai"):
            penangan._kirim(
                _halaman(
                    "Sudah dikirim",
                    "<h1>Jawaban sudah dikirim</h1>"
                    "<p>Sesi ini tidak dapat diubah lagi.</p>",
                ),
                409,
            )
            return

        import student_submissions as kiriman
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
            penangan._kirim(
                _halaman(
                    "Belum tersimpan",
                    f"<h1>Belum tersimpan</h1><p>{html.escape(str(galat))}</p>"
                    f'<p><a href="/murid/kerjakan/{sesi_id}">Buka kembali latihan</a></p>',
                ),
                getattr(galat, "status", 400),
            )
            return
        if aksi == "selesai" and kiriman.perlu_refleksi(kon, info_sesi, data):
            from submission_pages import halaman_refleksi
            isi = halaman_refleksi(
                kon, siswa_id, sesi_id, f"/murid/kerjakan/{sesi_id}"
            )
            kon.commit()
            if hasil:
                import sensor_http
                sensor_http.sesi(sesi_id, 'pekerjaan_disimpan')
            penangan._kirim_privat(isi)
            return

        selesai = aksi in ("selesai", "kirim_latihan")
        if hasil:
            database.tandai_mulai(kon, sesi_id)
        if selesai:
            from reports import diagnosa_murid
            kiriman.arsipkan(kon, sesi_id, "akun")
            diagnosa_murid(kon, sesi_id)
            database.tandai_mulai(kon, sesi_id)
            database.tandai_selesai(kon, sesi_id)

    if hasil is None:
        penangan._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
        return
    import sensor_http
    if hasil:
        sensor_http.sesi(sesi_id, 'pekerjaan_disimpan')
    if selesai:
        sensor_http.sesi(sesi_id, 'dikirim')
        import product_analytics_http as analitik
        analitik.aktivitas_sesi(sesi_id, "latihan_dikirim", baru=True)
        penangan.send_response(303)
        penangan.send_header("Location", f"/murid?selesai={sesi_id}")
        penangan.send_header("Content-Length", "0")
        penangan.end_headers()
        return
    penangan.send_response(303)
    penangan.send_header(
        "Location", f"/murid/kerjakan/{sesi_id}?tersimpan={hasil}"
    )
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def _post_foto(penangan, jalur: str) -> None:
    import students

    kredensial = penangan._sesi_atau_basic(peran_wajib="murid")
    if not kredensial:
        penangan._kirim(
            _halaman("Perlu masuk", "<h1>Halaman murid</h1>"), 401
        )
        return
    try:
        sesi_id = int(jalur.split("/")[3])
    except (ValueError, IndexError):
        penangan._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
        return

    content_type = penangan.headers.get("Content-Type", "")
    panjang = int(penangan.headers.get("Content-Length", 0) or 0)
    if panjang > lampiran_mod.BATAS_UKURAN * 2:
        penangan._kirim(
            _halaman("Terlalu besar", "<h1>Fotonya terlalu besar</h1>"), 400
        )
        return
    tubuh = penangan.rfile.read(panjang)
    with database.buka() as kon:
        siswa_id = students.siswa_dari_akun(kon, kredensial[0])
        if siswa_id is None or not students.sesi_murid(
            kon, siswa_id, sesi_id
        ):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return
        terjaga = lampiran_mod.penegakan_foto()
        if not terjaga:
            _lid, pesan = lampiran_mod.proses_upload_murid(
                kon, sesi_id, content_type, tubuh
            )
    if terjaga:
        _lid, pesan = penangan._proses_foto_terjaga(
            sesi_id, content_type=content_type, tubuh=tubuh
        )
        if pesan == "not_found":
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return
        if _lid is None:
            pesan = lampiran_mod.PESAN_FOTO_TERTAHAN
    qs = urllib.parse.urlencode({"foto": pesan, **({"foto_galat": "1"} if _lid is None else {})})
    penangan.send_response(303)
    penangan.send_header("Location", f"/murid/kerjakan/{sesi_id}?{qs}#kabar-foto")
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
