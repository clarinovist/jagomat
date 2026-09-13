"""Routing ketat panel pengaturan AI khusus admin."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_UP
import html
import sqlite3
import urllib.parse

import admin_pages
import admin_security
import ai_pages
import ai_policy
import ai_service
import ai_store
import assistant_client
import assistant_service
import auth
from teacher_style import SKRIP_MATA_SANDI

BATAS_FORM = 8_000


def _principal_admin(penangan):
    principal = penangan._principal()
    if principal is None or principal.peran != "admin":
        return None
    akun = auth.cari_akun(principal.pengguna)
    if (akun is None or akun.get("peran") != "admin"
            or akun.get("id_akun") != principal.id_akun
            or auth.revisi_auth(akun) != principal.revisi_auth):
        return None
    return principal


def _konteks_form(penangan, principal):
    return (auth.cari_akun(principal.pengguna),
            penangan._ambil_token() if principal.metode == "cookie" else None)


def _kirim(penangan, isi, kode=200):
    penangan.send_response(kode)
    penangan.send_header("Content-Type", "text/html; charset=utf-8")
    penangan.send_header("Content-Length", str(len(isi)))
    for nama, nilai in admin_security.header_privat(skrip_sandi=SKRIP_MATA_SANDI).items():
        penangan.send_header(nama, nilai)
    penangan.end_headers()
    penangan.wfile.write(isi)


def _galat(penangan, kode, pesan):
    if kode == 404:
        import admin_http
        return admin_http.tidak_ada(penangan)
    _kirim(penangan, admin_pages.halaman_admin(
        "ai", '<section class="admin-kartu" role="alert"><p>%s</p>'
        '<a href="/admin/ai">Kembali ke pengaturan AI</a></section>' % html.escape(pesan),
        pengguna="pengelola",
    ), kode)


def _micro(nilai):
    try:
        uang = Decimal(nilai)
    except InvalidOperation:
        raise ValueError("Nilai uang tidak sah.") from None
    if not uang.is_finite() or uang < 0 or uang > Decimal("100"):
        raise ValueError("Nilai uang di luar batas aman.")
    return int((uang * 1_000_000).quantize(Decimal("1"), rounding=ROUND_UP))


def _query_pesan(penangan):
    try:
        data = urllib.parse.parse_qs(
            urllib.parse.urlsplit(penangan.path).query,
            keep_blank_values=True, strict_parsing=True, max_num_fields=1,
            errors="strict",
        )
    except (UnicodeError, ValueError):
        return ""
    if set(data) - {"pesan"} or any(len(nilai) != 1 for nilai in data.values()):
        return ""
    return {
        "Pengaturan AI tersimpan.": "Pengaturan AI tersimpan.",
        "Koneksi sintetis berhasil.": "Koneksi sintetis berhasil.",
    }.get(data.get("pesan", [""])[0], "")


def tangani_get(penangan, jalur):
    if jalur != "/admin/ai":
        return False
    principal = _principal_admin(penangan)
    if principal is None:
        _galat(penangan, 404, "Halaman tidak ada.")
        return True
    if not ai_service.siap():
        _galat(penangan, 503, "Penyimpanan pengaturan AI belum disiapkan.")
        return True
    akun, sesi = _konteks_form(penangan, principal)
    with ai_store.buka(ai_service.path_store()) as kon:
        revisi = ai_store.konfigurasi(kon)[0]["revisi"]
    isi = ai_pages.halaman(
        ai_service.path_store(), pengguna=principal.pengguna,
        csrf=admin_security.buat_tinjauan(akun, sesi, "ai_csrf"),
        tinjauan_pengaturan=admin_security.buat_tinjauan(
            akun, sesi, "ai_settings_update", {"revisi": revisi}),
        tinjauan_uji=admin_security.buat_tinjauan(akun, sesi, "ai_synthetic_test"),
        pesan=_query_pesan(penangan),
    )
    _kirim(penangan, isi)
    return True


def tangani_post(penangan, jalur):
    if jalur not in ("/admin/ai/pengaturan", "/admin/ai/uji"):
        return False
    principal = _principal_admin(penangan)
    if principal is None:
        _galat(penangan, 404, "Halaman tidak ada.")
        return True
    try:
        data = admin_security.baca_form(penangan, batas=BATAS_FORM)
        akun, sesi = _konteks_form(penangan, principal)
        csrf = admin_security.periksa_tinjauan(akun, sesi, data.pop("csrf", None))
        if csrf["aksi"] != "ai_csrf":
            raise PermissionError("Form tidak sah.")
        tinjauan = admin_security.periksa_tinjauan(akun, sesi, data.pop("tinjauan", None))
        aksi = "ai_settings_update" if jalur.endswith("/pengaturan") else "ai_synthetic_test"
        if tinjauan["aksi"] != aksi:
            raise PermissionError("Tinjauan tidak cocok.")
        terbaru = auth.autentikasi(principal.pengguna, data.pop("reauth", ""))
        reauth_sah = (terbaru is not None and terbaru.id_akun == principal.id_akun
                     and terbaru.revisi_auth == principal.revisi_auth and terbaru.peran == "admin")
        if not reauth_sah:
            raise PermissionError("Autentikasi ulang gagal.")
        if jalur.endswith("/pengaturan"):
            diizinkan = {"revisi", "dihentikan", "request_akun_harian", "uji_harian", "uji_cooldown_menit"}
            diizinkan |= {f"aktif_{f}" for f in ai_policy.FITUR}
            diizinkan |= {f"{periode}_{f}" for periode in ("harian", "bulanan") for f in ("global", *ai_policy.FITUR)}
            if set(data) - diizinkan:
                raise ValueError("Field tidak dikenal.")
            for nama in ('dihentikan', *(f'aktif_{f}' for f in ai_policy.FITUR)):
                if data.get(nama) not in (None, '1'):
                    raise ValueError('Nilai sakelar tidak sah.')
            nilai = {
                "dihentikan": 1 if data.get("dihentikan") == "1" else 0,
                "request_akun_harian": int(data["request_akun_harian"]),
                "uji_harian": int(data["uji_harian"]),
                "uji_cooldown_detik": int(data["uji_cooldown_menit"]) * 60,
            }
            for fitur in ai_policy.FITUR:
                nilai[f"aktif_{fitur}"] = 1 if data.get(f"aktif_{fitur}") == "1" else 0
            for fitur in ("global", *ai_policy.FITUR):
                nilai[f"harian_{fitur}"] = _micro(data[f"harian_{fitur}"])
                nilai[f"bulanan_{fitur}"] = _micro(data[f"bulanan_{fitur}"])
            if int(data["revisi"]) != tinjauan["data"].get("revisi"):
                raise PermissionError("Revisi tinjauan tidak cocok.")
            ai_service.ubah_pengaturan_admin(
                nilai, actor_id=principal.id_akun, actor_revisi=principal.revisi_auth,
                operasi_id=tinjauan['op'], revisi=int(data['revisi']),
            )
            lokasi = "/admin/ai?pesan=" + urllib.parse.quote("Pengaturan AI tersimpan.")
        else:
            if data.pop("konfirmasi", None) != "1":
                raise ValueError("Konfirmasi biaya wajib.")
            if data:
                raise ValueError("Field tidak dikenal.")
            config = assistant_service.konfigurasi()
            payload = [{"role": "user", "content": "Balas JSON tepat: {\"status\":\"ok\"}"}]
            hasil = ai_service.panggil_uji_admin(
                lambda: assistant_client.kirim(config, payload, max_tokens=32, timeout=10),
                operasi_id=tinjauan["op"], actor_id=principal.id_akun,
                actor_revisi=principal.revisi_auth,
            )
            if hasil.get("status") != "ok":
                raise ValueError("Respons tes tidak sesuai kontrak.")
            lokasi = "/admin/ai?pesan=" + urllib.parse.quote("Koneksi sintetis berhasil.")
    except ai_store.Ditolak:
        _galat(penangan, 409, "Pengaturan berubah atau operasi sudah diproses. Buka ulang panel.")
        return True
    except PermissionError:
        _galat(penangan, 403, "Form atau autentikasi ulang tidak sah.")
        return True
    except (ValueError, KeyError):
        _galat(penangan, 400, "Isian atau konfirmasi tidak sah.")
        return True
    except (ai_service.AIUnavailable, assistant_client.GalatProvider):
        _galat(penangan, 409, "Tes ditahan atau hasil belum dapat dipastikan. Tidak ada pengulangan otomatis.")
        return True
    except (OSError, RuntimeError, sqlite3.Error):
        _galat(penangan, 503, "Layanan AI belum tersedia.")
        return True
    penangan.send_response(303)
    penangan.send_header("Location", lokasi)
    for nama, nilai in admin_security.header_privat().items():
        penangan.send_header(nama, nilai)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
    return True
