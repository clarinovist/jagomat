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
import sessions
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
    qs = urllib.parse.urlencode({"section": "latihan", "pesan": pesan_sukses, "sorot": sesi_id})
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
            "section": "latihan",
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
        "section": "latihan",
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


def tangani_latihan_serupa(penangan, jalur: str, *, acak_seed) -> bool:
    """Tangani latihan manual serupa dari hasil T dengan transaksi terkunci."""
    if not (
        jalur.startswith("/sesi/")
        and jalur.endswith("/latihan-serupa")
    ):
        return False

    bagian = jalur.split("/")
    if (
        len(bagian) != 4
        or bagian[1] != "sesi"
        or bagian[3] != "latihan-serupa"
    ):
        penangan._kirim(
            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
        )
        return True
    try:
        sesi_id = int(bagian[2])
        if not 0 < sesi_id <= 9_223_372_036_854_775_807:
            raise ValueError("ID sesi di luar rentang")
    except ValueError:
        penangan._kirim(
            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
        )
        return True

    # Jangan menahan lock writer saat menunggu body dari jaringan.
    panjang = int(penangan.headers.get("Content-Length", 0) or 0)
    data = urllib.parse.parse_qs(
        penangan.rfile.read(panjang).decode("utf-8"),
        keep_blank_values=True,
    )
    ident = penangan._identitas()
    with database.buka() as kon:
        # Kepemilikan dan syarat sumber tetap terkunci sampai sesi tersimpan.
        kon.execute("BEGIN IMMEDIATE")
        ada = kon.execute(
            "SELECT 1 FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()
        if (
            not ident
            or ada is None
            or not penangan._bisa_lihat_sesi(kon, sesi_id)
        ):
            kon.rollback()
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        if set(data) != {"sesi_soal_id"} or len(data["sesi_soal_id"]) != 1:
            kon.rollback()
            penangan._kirim(
                _halaman(
                    "Permintaan belum dapat diproses",
                    "<h1>Permintaan belum dapat diproses</h1>"
                    "<p>Referensi soal tidak dikenal.</p>",
                ),
                400,
            )
            return True
        try:
            sesi_soal_id = int(data["sesi_soal_id"][0])
            if not 0 < sesi_soal_id <= 9_223_372_036_854_775_807:
                raise ValueError("ID butir di luar rentang")
        except ValueError:
            sesi_soal_id = -1

        import similar_practice
        try:
            sesi_baru = similar_practice.buat_dari_hasil_t(
                kon,
                sesi_id,
                sesi_soal_id,
                seed=acak_seed(1, 9_999_999),
            )
        except (ValueError, RuntimeError):
            kon.rollback()
            penangan._kirim(
                _halaman(
                    "Latihan belum dapat dibuat",
                    "<h1>Latihan belum dapat dibuat</h1>"
                    "<p>Hasil ini tidak lagi memenuhi syarat atau variasi "
                    "soalnya belum cukup. Muat ulang hasil lalu coba lagi.</p>",
                ),
                409,
            )
            return True

    penangan.send_response(303)
    penangan.send_header(
        "Location",
        f"/sesi/{sesi_baru}?pesan="
        + urllib.parse.quote(
            "5 soal serupa dibuat. Latihan manual ini tidak mengubah progres "
            "rencana terpandu."
        ),
    )
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
    return True


def tangani_pembuatan_remedial(
    penangan,
    jalur: str,
    *,
    level_bawaan: str,
    nama_template,
) -> bool:
    """Tangani ``POST /sesi-remedial/<siswa_id>``; False untuk jalur lain."""
    if not jalur.startswith("/sesi-remedial/"):
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
    jumlah_valid = True
    try:
        jumlah = int((data.get("jumlah_soal") or ["10"])[0] or 10)
    except ValueError:
        jumlah = 0
        jumlah_valid = False
    if not 1 <= jumlah <= 50:
        jumlah_valid = False

    template_ids = [nilai for nilai in data.get("template_id", []) if nilai]
    sumber_mentah = (data.get("sumber_sesi_id") or [""])[0]
    try:
        sumber_sesi_id = int(sumber_mentah) if sumber_mentah else None
    except ValueError:
        sumber_sesi_id = -1

    sesi_id = None
    nama_siswa = None
    pesan_gagal = ""
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
        if (
            sumber_sesi_id is not None
            and not database.sasaran_remedial_sesi(
                kon, siswa_id, sumber_sesi_id
            )
        ):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        if not jumlah_valid:
            pesan_gagal = "Jumlah soal harus antara 1 dan 50."
        else:
            try:
                sesi_id = database.buat_sesi_remedial(
                    kon,
                    siswa_id,
                    level=(baris["tingkat"] if baris else level_bawaan),
                    jumlah_soal=jumlah,
                    template_ids=template_ids,
                    sumber_sesi_id=sumber_sesi_id,
                )
            except ValueError as galat:
                detail = str(galat)
                if "bukan kandidat" in detail:
                    pesan_gagal = (
                        "Pilihan itu bukan pilihan remedial yang tersedia."
                    )
                elif "kosong" in detail:
                    pesan_gagal = (
                        "Pilih setidaknya satu tipe soal untuk remedial."
                    )
                elif "maksimal 3" in detail:
                    pesan_gagal = (
                        "Pilih maksimal 3 tipe soal untuk satu remedial."
                    )
                elif "sumber" in detail:
                    pesan_gagal = "Sesi sumber remedial tidak tersedia."
                elif "jumlah_soal" in detail:
                    pesan_gagal = "Jumlah soal harus antara 1 dan 50."
                else:
                    pesan_gagal = (
                        "Remedial belum dapat dibuat. Periksa pilihannya."
                    )

    if pesan_gagal:
        qs = urllib.parse.urlencode({"section": "latihan", "pesan": pesan_gagal})
    elif sesi_id is None:
        qs = urllib.parse.urlencode({
            "section": "latihan",
            "pesan": "Belum ada kesalahan tercatat untuk dilatih "
                     "ulang — buat sesi biasa dulu, ya.",
        })
    else:
        fokus = " & ".join(
            nama_template(template_id) for template_id in template_ids
        )
        qs = urllib.parse.urlencode({
            "section": "latihan",
            "pesan": (
                f"Remedial {fokus} dibuat — {jumlah} soal baru "
                f"untuk {nama_siswa} (sesi #{sesi_id})."
            ),
            "sorot": sesi_id,
        })
    penangan.send_response(303)
    penangan.send_header("Location", f"/anak/{siswa_id}?{qs}")
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
    return True


def tangani_get(
    penangan,
    jalur: str,
    jalur_penuh: str,
    *,
    halaman_cetak,
    halaman_sesi,
) -> bool:
    """Tangani tampilan/cetak sesi guru; hapus tetap untuk subfase terpisah."""
    if not jalur.startswith("/sesi/") or jalur.endswith("/hapus"):
        return False

    import assistant_http

    try:
        with database.buka() as kon:
            if jalur.endswith("/cetak"):
                try:
                    sesi_id = int(jalur.split("/")[2])
                except (ValueError, IndexError):
                    penangan._kirim(
                        _halaman("404", "<h1>Tidak ada</h1>"), 404
                    )
                    return True
                if not penangan._bisa_lihat_sesi(kon, sesi_id):
                    penangan._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                    return True
                ident = penangan._identitas()
                isi = halaman_cetak(
                    kon,
                    sesi_id,
                    peran=ident[1] if ident else "guru",
                    pengguna=ident[0] if ident else "",
                )
                if isi is None:
                    penangan._kirim(
                        _halaman("404", "<h1>Sesi tidak ada</h1>"), 404
                    )
                    return True
                penangan._kirim(isi)
                return True

            sesi_id = int(jalur.split("/")[2])
            if not penangan._bisa_lihat_sesi(kon, sesi_id):
                penangan._kirim(
                    _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                )
                return True
            ident = penangan._identitas()
            target_inline = None
            fragmen_inline = ""
            try:
                pasangan = urllib.parse.parse_qsl(
                    urllib.parse.urlsplit(jalur_penuh).query,
                    keep_blank_values=True,
                    errors="strict",
                )
                if any(kunci == "bantuan" for kunci, _nilai in pasangan):
                    import assistant_inline
                    target_inline = assistant_inline.parse_query_host(
                        "sesi", sesi_id, pasangan
                    )
                    principal = sessions.ambil_principal_pendamping(
                        penangan._ambil_token()
                    )
                    status_inline = kon.execute(
                        "SELECT selesai, dibatalkan FROM sesi WHERE id = ?",
                        (sesi_id,),
                    ).fetchone()
                    fragmen_inline = assistant_http.fragmen_inline(
                        principal,
                        target_inline,
                        dalam_form=bool(
                            status_inline
                            and status_inline["selesai"]
                            and status_inline["dibatalkan"] is None
                        ),
                    )
            except (ValueError, LookupError):
                penangan._kirim_privat(
                    _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                )
                return True

            # Validasi bantuan selesai sebelum stamp direview.
            if ident and ident[1] == "guru":
                siap = kon.execute(
                    """SELECT 1 FROM sesi
                       WHERE id = ? AND direview IS NULL
                         AND selesai IS NOT NULL""",
                    (sesi_id,),
                ).fetchone()
                if siap:
                    kon.execute(
                        "UPDATE sesi SET direview = "
                        "datetime('now', '+7 hours') WHERE id = ?",
                        (sesi_id,),
                    )
                    kon.commit()

            pesan_tinjauan = (
                "Tinjauan tersimpan. Konfirmasi hasil tetap merupakan langkah "
                "terpisah."
                if [
                    nilai for kunci, nilai in pasangan if kunci == "pesan"
                ] == ["Tinjauan tersimpan"]
                else ""
            )
            hasil = halaman_sesi(
                kon,
                sesi_id,
                pesan=pesan_tinjauan,
                peran=ident[1] if ident else "guru",
                pengguna=ident[0] if ident else "",
                bantuan=fragmen_inline,
                bantuan_nomor=(target_inline.nomor if target_inline else None),
            )
            selesai = bool(
                ident
                and ident[1] == "guru"
                and kon.execute(
                    "SELECT 1 FROM sesi WHERE id=? AND selesai IS NOT NULL",
                    (sesi_id,),
                ).fetchone()
            )
            if selesai:
                # Respons/analitik harus melihat stamp review yang sudah commit.
                kon.commit()
                import product_analytics_http as analitik
                analitik.kirim_dan_catat(
                    penangan,
                    hasil,
                    sesi_id,
                    "panduan_hasil_disajikan",
                    pengguna=ident[0],
                    peran=ident[1],
                    privat=bool(target_inline),
                )
                return True
            if target_inline:
                penangan._kirim_privat(hasil)
            else:
                penangan._kirim(hasil)
            return True
    except (ValueError, IndexError):
        penangan._kirim(
            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
        )
        return True


def tangani_review_post(
    penangan,
    jalur: str,
    *,
    simpan_review,
    halaman_sesi,
) -> bool:
    """Simpan koreksi sesi umum setelah route aksi khusus mendapat prioritas."""
    if not jalur.startswith("/sesi/"):
        return False

    panjang = int(penangan.headers.get("Content-Length", 0))
    mentah = penangan.rfile.read(panjang).decode("utf-8")
    data = {
        kunci: nilai[0]
        for kunci, nilai in urllib.parse.parse_qs(
            mentah, keep_blank_values=True
        ).items()
    }
    data = {
        kunci: nilai
        for kunci, nilai in data.items()
        if kunci != "hadir_sertakan_pemetaan"
        and not kunci.startswith(("hadir_dilewati_", "hadir_belum_"))
    }

    sesi_id = int(jalur.split("/")[2])
    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        if not penangan._bisa_lihat_sesi(kon, sesi_id):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        status = kon.execute(
            "SELECT selesai FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()
        if not status or not status["selesai"]:
            penangan._kirim(
                _halaman(
                    "Belum dikirim",
                    "<h1>Koreksi belum tersedia</h1>"
                    "<p>Anak belum menekan Selesai &amp; kirim.</p>",
                ),
                409,
            )
            return True
        ident = penangan._identitas()
        try:
            pesan = simpan_review(
                kon, sesi_id, data, guru=ident[0]
            )
        except ValueError as galat:
            kon.rollback()
            penangan._kirim(
                _halaman(
                    "Tinjauan belum tersimpan",
                    "<h1>Tinjauan belum tersimpan</h1><p>"
                    + html.escape(str(galat))
                    + "</p>",
                ),
                400,
            )
            return True
        kon.commit()
        ident = penangan._identitas()
        penangan._kirim(
            halaman_sesi(
                kon,
                sesi_id,
                pesan,
                peran=ident[1] if ident else "guru",
                pengguna=ident[0] if ident else "",
            )
        )
        return True


def tangani_lembar_get(penangan, jalur: str, *, halaman_lembar) -> bool:
    """Render lembar anak/kunci dengan freeze commit sebelum respons."""
    if not jalur.startswith("/lembar/"):
        return False
    try:
        bagian = jalur.split("/")
        sesi_id = int(bagian[2])
    except (ValueError, IndexError):
        penangan._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
        return True
    with database.buka() as kon:
        if not penangan._bisa_lihat_sesi(kon, sesi_id):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        untuk_guru = len(bagian) > 3 and bagian[3] == "penilaian"
        isi = halaman_lembar(kon, sesi_id, untuk_guru)
        if not isi:
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        kon.commit()
        if not untuk_guru:
            import product_analytics_http as analitik
            ident = penangan._identitas()
            analitik.kirim_dan_catat(
                penangan,
                isi,
                sesi_id,
                "lembar_soal_disajikan",
                pengguna=ident[0],
                peran=ident[1],
            )
            return True
        penangan._kirim(isi)
        return True


def tangani_cerita_post(
    penangan,
    jalur: str,
    *,
    soal_dari_baris,
    halaman_sesi,
) -> bool:
    """Buat variasi cerita, lalu render ulang sesi yang sama."""
    if not jalur.startswith("/cerita/"):
        return False
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
        import llm
        _, _, catatan = llm.bungkus_sesi(
            kon, sesi_id, soal_dari_baris
        )
        ident = penangan._identitas()
        penangan._kirim(
            halaman_sesi(
                kon,
                sesi_id,
                catatan,
                peran=ident[1] if ident else "guru",
                pengguna=ident[0] if ident else "",
            )
        )
        return True


def tangani_hapus_get(penangan, jalur: str, *, halaman_konfirmasi) -> bool:
    """Tampilkan konfirmasi hapus setelah palang guru utama lolos."""
    if not (jalur.startswith("/sesi/") and jalur.endswith("/hapus")):
        return False
    try:
        sesi_id = int(jalur.split("/")[2])
    except (ValueError, IndexError):
        penangan._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
        return True
    with database.buka() as kon:
        if not penangan._bisa_lihat_sesi(kon, sesi_id):
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        ident = penangan._identitas()
        isi = halaman_konfirmasi(
            kon,
            sesi_id,
            pengguna=ident[0] if ident else "",
            peran=ident[1] if ident else "guru",
        )
    if isi is None:
        penangan._kirim(
            _halaman("404", "<h1>Sesi tidak ada</h1>"), 404
        )
        return True
    penangan._kirim(isi)
    return True


def tangani_hapus_post(
    penangan,
    jalur: str,
    *,
    halaman_konfirmasi,
    bersihkan_berkas,
) -> bool:
    """Hapus hanya sesi tanpa bukti; berkas dibersihkan setelah commit DB."""
    if not (jalur.startswith("/sesi/") and jalur.endswith("/hapus")):
        return False
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
    panjang = int(penangan.headers.get("Content-Length", 0) or 0)
    data = urllib.parse.parse_qs(
        penangan.rfile.read(panjang).decode("utf-8"),
        keep_blank_values=True,
    )
    if (data.get("konfirmasi") or [""])[0] != "1":
        with database.buka() as kon:
            ident = penangan._identitas()
            isi = halaman_konfirmasi(
                kon,
                sesi_id,
                pengguna=ident[0] if ident else "",
                peran=ident[1] if ident else "guru",
            )
        if isi is None:
            penangan._kirim(
                _halaman("404", "<h1>Sesi tidak ada</h1>"), 404
            )
            return True
        penangan._kirim(isi)
        return True

    with database.buka() as kon:
        baris_sesi = kon.execute(
            "SELECT siswa_id FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()
        dilindungi = kon.execute(
            """SELECT 1 FROM konfirmasi_hasil WHERE sesi_id = ?
               UNION ALL SELECT 1 FROM bukti_fokus WHERE sesi_id = ?
               UNION ALL SELECT 1 FROM kejadian_belajar WHERE sesi_id = ?""",
            (sesi_id, sesi_id, sesi_id),
        ).fetchone()
        if dilindungi:
            penangan._kirim(
                _halaman(
                    "Histori sesi dilindungi",
                    "<h1>Histori sesi dilindungi</h1>"
                    "<p>Gunakan Batalkan sesi agar bukti belajar tetap "
                    "tersimpan.</p>",
                ),
                409,
            )
            return True
        dihapus = database.hapus_sesi(kon, sesi_id)
    if not dihapus:
        penangan._kirim(
            _halaman("404", "<h1>Sesi tidak ada</h1>"), 404
        )
        return True

    # Cleanup filesystem hanya setelah penghapusan DB berhasil dan commit.
    bersihkan_berkas(sesi_id)
    tujuan = urllib.parse.urlencode({
        "section": "riwayat", "pesan": f"Sesi {sesi_id} dihapus."
    })
    penangan.send_response(303)
    tujuan_anak = (
        f"/anak/{baris_sesi['siswa_id']}?{tujuan}"
        if baris_sesi
        else f"/?{tujuan}"
    )
    penangan.send_header("Location", tujuan_anak)
    penangan.end_headers()
    return True
