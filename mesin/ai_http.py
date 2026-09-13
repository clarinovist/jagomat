"""Routing ketat panel pengaturan AI khusus admin."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_UP
import html
import json
import secrets
import urllib.parse

import ai_pages
import ai_policy
import ai_service
import ai_store
import assistant_client
import assistant_service
import auth
import sessions

BATAS_FORM = 8_000


def _principal_admin(penangan):
    ident = penangan._identitas()
    if not ident or ident[1] != "admin":
        return None
    akun = auth.cari_akun(ident[0])
    if not akun or akun.get("peran") != "admin":
        return None
    token = penangan._ambil_token()
    if token:
        sesi = sessions.muat().get(token)
        if not sesi or sesi.get("id_akun") != akun.get("id_akun"):
            return None
    return ident[0], akun.get("id_akun", ident[0])


def _csrf(penangan, actor_id):
    token = penangan._ambil_token()
    if token:
        principal = sessions.muat().get(token)
        if not principal or principal.get("id_akun") != actor_id:
            return None
        return "sesi:" + token[-24:]
    # Basic Auth tidak memiliki cookie CSRF; token request terikat account-generation.
    return "basic:" + actor_id


def _baca_form(penangan):
    asal = penangan.headers.get("Origin")
    situs = penangan.headers.get("Sec-Fetch-Site")
    if asal and urllib.parse.urlsplit(asal).netloc != penangan.headers.get("Host"):
        raise ValueError("Permintaan lintas situs ditolak.")
    if situs == "cross-site":
        raise ValueError("Permintaan lintas situs ditolak.")
    panjang = penangan.headers.get("Content-Length", "0")
    if not panjang.isdigit() or int(panjang) > BATAS_FORM:
        raise ValueError("Ukuran isian tidak sah.")
    if penangan.headers.get_content_type() != "application/x-www-form-urlencoded":
        raise ValueError("Format isian tidak sah.")
    data = urllib.parse.parse_qs(
        penangan.rfile.read(int(panjang)).decode("utf-8"), keep_blank_values=True,
        strict_parsing=True, max_num_fields=32,
    )
    if any(len(v) != 1 for v in data.values()):
        raise ValueError("Isian ganda ditolak.")
    return {k: v[0] for k, v in data.items()}


def _micro(nilai):
    try:
        uang = Decimal(nilai)
    except InvalidOperation:
        raise ValueError("Nilai uang tidak sah.") from None
    if not uang.is_finite() or uang < 0 or uang > Decimal("100"):
        raise ValueError("Nilai uang di luar batas aman.")
    return int((uang * 1_000_000).quantize(Decimal("1"), rounding=ROUND_UP))


def tangani_get(penangan, jalur):
    if jalur != "/admin/ai":
        return False
    principal = _principal_admin(penangan)
    if principal is None:
        penangan._kirim_privat(b"Tidak diizinkan", 404)
        return True
    if not ai_service.siap():
        penangan._kirim_privat(b"Penyimpanan pengaturan AI belum disiapkan.", 503)
        return True
    isi = ai_pages.halaman(
        ai_service.path_store(), pengguna=principal[0], csrf=_csrf(penangan, principal[1]) or "",
    )
    penangan._kirim_privat(isi)
    return True


def tangani_post(penangan, jalur):
    if jalur not in ("/admin/ai/pengaturan", "/admin/ai/uji"):
        return False
    principal = _principal_admin(penangan)
    if principal is None:
        penangan._kirim_privat(b"Tidak diizinkan", 404)
        return True
    try:
        data = _baca_form(penangan)
        if data.pop("csrf", None) != _csrf(penangan, principal[1]):
            raise PermissionError("Form kedaluwarsa atau tidak sah.")
        if jalur.endswith("/pengaturan"):
            diizinkan = {"revisi", "dihentikan", "request_akun_harian", "uji_harian", "uji_cooldown_menit"}
            diizinkan |= {f"aktif_{f}" for f in ai_policy.FITUR}
            diizinkan |= {f"{periode}_{f}" for periode in ("harian", "bulanan") for f in ("global", *ai_policy.FITUR)}
            if set(data) - diizinkan:
                raise ValueError("Field tidak dikenal.")
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
            ai_store.ubah(ai_service.path_store(), nilai, principal[1], revisi=int(data["revisi"]))
            lokasi = "/admin/ai?pesan=" + urllib.parse.quote("Pengaturan AI tersimpan.")
        else:
            if data:
                raise ValueError("Field tidak dikenal.")
            config = assistant_service.konfigurasi()
            payload = [{"role": "user", "content": "Balas JSON tepat: {\"status\":\"ok\"}"}]
            hasil = ai_service.panggil(
                "uji_sintetis", None,
                lambda: assistant_client.kirim(config, payload, max_tokens=32, timeout=10),
                operasi_id="uji_" + secrets.token_hex(16),
            )
            if hasil.get("status") != "ok":
                raise ValueError("Respons tes tidak sesuai kontrak.")
            lokasi = "/admin/ai?pesan=" + urllib.parse.quote("Koneksi sintetis berhasil.")
    except ai_store.Ditolak as galat:
        penangan._kirim_privat(html.escape(str(galat)).encode(), 409)
        return True
    except PermissionError as galat:
        penangan._kirim_privat(html.escape(str(galat)).encode(), 403)
        return True
    except (ValueError, KeyError, ai_service.AIUnavailable, assistant_client.GalatProvider) as galat:
        penangan._kirim_privat(html.escape(str(galat)).encode(), 400)
        return True
    penangan.send_response(303)
    penangan.send_header("Location", lokasi)
    penangan.send_header("Cache-Control", "no-store")
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
    return True
