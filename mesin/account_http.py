"""Permukaan HTTP akun guru dan compatibility akun admin sendiri."""
from __future__ import annotations

import urllib.parse

import database
import sessions
from support_pages import halaman_pesan as _halaman


def tangani_get(
    penangan,
    jalur: str,
    jalur_penuh: str,
    *,
    halaman,
) -> bool:
    """Render satu section akun dengan query ketat dan panel privat opsional."""
    if jalur != "/akun":
        return False

    import assistant_http
    import subscription_http
    import subscription_produksi_http

    ident = penangan._identitas()
    with database.buka() as kon:
        try:
            pasangan = urllib.parse.parse_qsl(
                urllib.parse.urlsplit(jalur_penuh).query,
                keep_blank_values=True,
                errors="strict",
            )
            if len(pasangan) != len({kunci for kunci, _nilai in pasangan}):
                raise ValueError("parameter ganda")
            q = dict(pasangan)
            if set(q) - {"section", "halaman", "chat"}:
                raise ValueError("parameter asing")
            section = q.get("section", "akun")
            arsip = ""
            if section in ("akun", "arsip-pendamping"):
                diizinkan = (
                    {"section"}
                    if section == "akun"
                    else {"section", "halaman", "chat"}
                )
                if set(q) - diizinkan:
                    raise ValueError("parameter arsip tidak sah")
                nomor_halaman = int(q.get("halaman", "1"))
                if not 1 <= nomor_halaman <= 501:
                    raise ValueError("halaman arsip tidak sah")
                principal = sessions.ambil_principal_pendamping(
                    penangan._ambil_token()
                )
                arsip = assistant_http.fragmen_arsip_akun(
                    principal,
                    halaman=nomor_halaman,
                    chat_id=q.get("chat", ""),
                )
            elif set(q) != {"section"}:
                raise ValueError("parameter tidak sah")
        except (ValueError, UnicodeError, LookupError):
            penangan._kirim_privat(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True

        import product_analytics_http as analitik
        panel_analitik = ""
        if section == "akun" and ident[1] == "guru" and penangan._ambil_token():
            try:
                panel_analitik = analitik.form_akun(penangan)
            except (LookupError, RuntimeError, OSError):
                panel_analitik = "<p>Analitik opsional belum tersedia.</p>"
        hasil = halaman(
            kon,
            pengguna=ident[0] if ident else None,
            peran=ident[1] if ident else "guru",
            section=section,
            arsip_pendamping=arsip,
            privat=bool(arsip or panel_analitik),
            analitik=panel_analitik,
            langganan_sandbox=subscription_http.runtime(penangan) is not None,
            langganan_produksi=subscription_produksi_http.ada(penangan),
        )
    if arsip or panel_analitik:
        assistant_http._kirim_host_privat(penangan, hasil)
    else:
        penangan._kirim(hasil)
    return True


def tangani_post(
    penangan,
    jalur: str,
    *,
    proses,
    halaman,
    peta_section,
) -> bool:
    """Proses mutasi akun dengan guard admin dan profil yang sudah ada."""
    if jalur != "/akun":
        return False

    import admin_http

    ident = penangan._identitas()
    pengguna = ident[0] if ident else "guru"
    peran = ident[1] if ident else "guru"
    if peran == "admin":
        # Jalur lama hanya untuk sandi sendiri, bukan bypass layanan admin.
        import admin_security
        try:
            data = admin_security.baca_form(penangan)
            if data.get("aksi") != "sandi" or set(data) - {
                "aksi", "section", "lama", "baru", "ulang",
            }:
                admin_http.arahkan_admin(penangan)
                return True
        except (ValueError, PermissionError):
            penangan._kirim_privat(b"Form tidak sah.", 400)
            return True
    else:
        panjang = int(penangan.headers.get("Content-Length", 0))
        mentah = penangan.rfile.read(panjang).decode("utf-8")
        pasangan = urllib.parse.parse_qs(mentah, keep_blank_values=True)
        if any(len(nilai) != 1 for nilai in pasangan.values()):
            penangan._kirim(
                _halaman(
                    "Form tidak sah",
                    "<p>Field ganda tidak diizinkan. Muat ulang form.</p>",
                ),
                400,
            )
            return True
        data = {kunci: nilai[0] for kunci, nilai in pasangan.items()}

    with database.buka() as kon:
        import learning_profile
        if data.get("aksi") == "kelas_sekolah":
            try:
                siswa_id = int(data.get("siswa_id", ""))
                if not 0 < siswa_id <= 9_223_372_036_854_775_807:
                    raise ValueError("ID tidak sah")
                learning_profile.baca(kon, siswa_id, pemilik=pengguna)
            except (ValueError, TypeError):
                penangan._kirim(
                    _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                )
                return True
            if set(data) - {
                "aksi", "siswa_id", "kelas_sekolah", "revisi_profil", "section",
            }:
                penangan._kirim(
                    _halaman(
                        "Form tidak sah",
                        "<p>Field profil tidak dikenal. Muat ulang form.</p>",
                    ),
                    400,
                )
                return True
        if data.get("aksi") == "tingkat":
            penangan._kirim(
                _halaman(
                    "Form lama",
                    "<p>Muat ulang form kelas sekolah. Profil parameter lama "
                    "tidak diubah lewat form ini.</p>",
                ),
                409,
            )
            return True
        if data.get("aksi") in ("anak_baru", "siswa"):
            profil_lama = data.get("profil_parameter", "")
            if (
                "tingkat" in data
                or "level" in data
                or profil_lama not in ("", "P3", "P4", "P5", "P6")
            ):
                penangan._kirim(
                    _halaman(
                        "Form lama",
                        "<p>Form pengaturan soal lama tidak cocok. Muat ulang "
                        "sebelum menambahkan anak.</p>",
                    ),
                    409,
                )
                return True
        try:
            pesan, galat = proses(kon, data, pengguna, peran)
        except learning_profile.ProfilTidakDitemukan:
            penangan._kirim(
                _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
            )
            return True
        section = data.get("section") or peta_section.get(
            data.get("aksi", ""), "akun"
        )
        penangan._kirim(
            halaman(
                kon,
                pesan,
                galat,
                pengguna=pengguna,
                peran=peran,
                section=section,
            )
        )
        return True
