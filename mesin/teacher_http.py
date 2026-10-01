"""Permukaan HTTP beranda dan workspace guru.

Modul route menerima renderer dari façade ``web`` agar monkeypatch/caller lama
terus memakai simbol yang sama. Transport, identitas, cookie, dan primitive
respons tetap dimiliki ``web.Penangan``.
"""
from __future__ import annotations

import urllib.parse

import database


def tangani_beranda_get(
    penangan,
    jalur: str,
    jalur_penuh: str,
    *,
    halaman_utama,
) -> bool:
    """Tangani root terautentikasi dan alias beranda guru."""
    if jalur not in ("/", "/guru", "/ortu"):
        return False

    ident = penangan._identitas()
    if not penangan._lolos_sandi():
        return True
    if ident[1] == "admin":
        penangan.send_response(303)
        penangan.send_header("Location", "/admin")
        penangan.send_header("Content-Length", "0")
        penangan.end_headers()
        return True

    q = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query)
    if jalur != "/guru":
        # Alias lama mempertahankan kabar, bukan tujuan bebas dari URL.
        qs = urllib.parse.urlencode({
            kunci: q[kunci][0]
            for kunci in ("pesan", "sorot")
            if kunci in q
        })
        penangan.send_response(303)
        penangan.send_header("Location", "/guru" + ("?" + qs if qs else ""))
        penangan.send_header("Content-Length", "0")
        penangan.end_headers()
        return True

    pesan = (q.get("pesan") or [""])[0][:200]
    try:
        sorot = int((q.get("sorot") or [""])[0])
    except ValueError:
        sorot = None
    with database.buka() as kon:
        isi = halaman_utama(
            kon,
            pesan=pesan,
            pemilik=ident[0],
            peran=ident[1],
            sorot=sorot,
        )
    import product_analytics_http as analitik
    survei = analitik.form_survei(penangan)
    if survei:
        isi = isi.replace(b"</main>", survei.encode() + b"</main>", 1)
        penangan._kirim_privat(isi)
    else:
        penangan._kirim(isi)
    return True


def tangani_profil_get(
    penangan,
    jalur: str,
    jalur_penuh: str,
    *,
    halaman_anak,
    halaman_laporan,
) -> bool:
    """Tangani workspace dan laporan anak setelah palang guru utama lolos."""
    if not (
        (jalur.startswith("/anak/") and jalur.count("/") >= 2)
        or jalur.startswith("/laporan/")
    ):
        return False

    import sessions
    from support_pages import halaman_pesan as halaman_galat

    try:
        with database.buka() as kon:
            if jalur.startswith("/anak/"):
                bagian = jalur.split("/")
                try:
                    anak_id = int(bagian[2])
                except (ValueError, IndexError):
                    penangan._kirim(
                        halaman_galat("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                    return True
                if not penangan._bisa_lihat_siswa(kon, anak_id):
                    penangan._kirim(
                        halaman_galat("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                    return True
                siswa_baris = kon.execute(
                    "SELECT * FROM siswa WHERE id = ?", (anak_id,)
                ).fetchone()
                if not siswa_baris:
                    penangan._kirim(
                        halaman_galat("404", "<h1>Halaman tidak ada</h1>"), 404
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
                        import assistant_http
                        import assistant_inline
                        target_inline = assistant_inline.parse_query_host(
                            "anak", anak_id, pasangan
                        )
                        principal = sessions.ambil_principal_pendamping(
                            penangan._ambil_token()
                        )
                        fragmen_inline = assistant_http.fragmen_inline(
                            principal,
                            target_inline,
                            dalam_form=target_inline.posisi == "latihan",
                        )
                except (ValueError, LookupError):
                    penangan._kirim_privat(
                        halaman_galat("404", "<h1>Halaman tidak ada</h1>"),
                        404,
                    )
                    return True
                q = (
                    urllib.parse.parse_qs(
                        urllib.parse.urlparse(jalur_penuh).query
                    )
                    if jalur_penuh and not target_inline
                    else {}
                )
                try:
                    sorot = int(q.get("sorot", ["0"])[0]) or None
                except (TypeError, ValueError):
                    sorot = None
                pesan = (q.get("pesan", [""])[0] or "")[:200]
                query_profil = (
                    urllib.parse.urlsplit(jalur_penuh).query
                    if not target_inline
                    else ""
                )
                try:
                    import profile_history
                    profile_history.parse_filter(query_profil)
                except (ValueError, UnicodeError):
                    penangan._kirim(
                        halaman_galat("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                    return True
                hasil = halaman_anak(
                    kon,
                    siswa_baris,
                    peran=ident[1] if ident else "guru",
                    pengguna=ident[0] if ident else "",
                    sorot=sorot,
                    pesan=pesan,
                    bantuan_rencana=(
                        fragmen_inline
                        if target_inline and target_inline.posisi == "rencana"
                        else ""
                    ),
                    bantuan_latihan=(
                        fragmen_inline
                        if target_inline and target_inline.posisi == "latihan"
                        else ""
                    ),
                    query=query_profil,
                )
                if target_inline:
                    penangan._kirim_privat(hasil)
                else:
                    penangan._kirim(hasil)
                return True

            siswa_id = int(jalur.split("/")[2])
            if not penangan._bisa_lihat_siswa(kon, siswa_id):
                penangan._kirim(
                    halaman_galat("404", "<h1>Halaman tidak ada</h1>"), 404
                )
                return True
            ident = penangan._identitas()
            penangan._kirim(halaman_laporan(
                kon,
                siswa_id,
                pengguna=ident[0] if ident else "",
                peran=ident[1] if ident else "guru",
                query=urllib.parse.urlsplit(jalur_penuh).query,
            ))
            return True
    except (ValueError, IndexError):
        penangan._kirim(
            halaman_galat("404", "<h1>Halaman tidak ada</h1>"), 404
        )
        return True
