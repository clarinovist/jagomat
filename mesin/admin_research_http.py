"""Rute admin privat untuk aplikasi interviewer riset konsumen."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import secrets
import sqlite3
import urllib.parse

import admin_http as h
import admin_research_pages as ui
import admin_research_service as layanan
import admin_security
import auth
import research_store as store


JUDUL = "Riset konsumen"
SUBJUDUL = "Catat ucapan responden, coding interviewer, dan konteks secara terpisah."
RUTE_GET = frozenset((
    "/admin/riset", "/admin/riset/wawancara", "/admin/riset/isi",
    "/admin/riset/matriks",
))
RUTE_POST = frozenset((
    "/admin/riset/buat", "/admin/riset/jawaban", "/admin/riset/finalisasi",
    "/admin/riset/koreksi", "/admin/riset/redaksi", "/admin/riset/tarik",
    "/admin/riset/ekspor",
))


def _path():
    return store.BAWAAN


def _principal_cookie(penangan):
    principal = h._principal_admin(penangan)
    if principal is None:
        return None
    try:
        h._wajib_cookie(penangan, principal)
    except PermissionError:
        return None
    return principal


def _token(penangan, principal, aksi, data):
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    return admin_security.buat_tinjauan(akun, sesi, aksi, data)


def _csrf(penangan, principal):
    return h._csrf(h._akun_principal(principal), h._wajib_cookie(penangan, principal))


def _periksa_form(penangan, principal, data, aksi):
    csrf = data.pop("csrf", None)
    token = data.pop("tinjauan", None)
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    h._cek_csrf(akun, sesi, csrf)
    hasil = admin_security.periksa_tinjauan(akun, sesi, token)
    if hasil["aksi"] != aksi:
        raise PermissionError("Form tidak sah.")
    return hasil


def _kirim(penangan, principal, isi, *, judul=JUDUL, subjudul=SUBJUDUL, skrip=False, aksi_header=""):
    h._kirim_privat(
        penangan,
        h._halaman_admin(principal, "riset", isi, penangan=penangan, skrip=skrip,
                         judul=judul, subjudul=subjudul, aksi_header=aksi_header),
        skrip=skrip,
    )


def _query(penangan, diizinkan):
    return h._query(penangan, diizinkan=diizinkan)


def _op():
    return "op_" + secrets.token_hex(16)


def _meta_aksi(detail, aksi):
    return {"target_id": detail["id"], "target_revisi": detail["revisi"], "section": "riset"}


def _tokens_aksi(penangan, principal, detail):
    return {
        "finalisasi": _token(penangan, principal, "riset_finalisasi", _meta_aksi(detail, "finalisasi")),
        "koreksi": _token(penangan, principal, "riset_koreksi", _meta_aksi(detail, "koreksi")),
        "redaksi": _token(penangan, principal, "riset_redaksi", _meta_aksi(detail, "redaksi")),
        "tarik": _token(penangan, principal, "riset_tarik", _meta_aksi(detail, "tarik")),
    }


def tangani_get(penangan, jalur):
    if jalur not in RUTE_GET:
        return False
    principal = _principal_cookie(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        if jalur == "/admin/riset":
            query = _query(penangan, {"status", "halaman"})
            status = query.get("status", "")
            halaman = h._angka(query.get("halaman"), 1)
            data = layanan.dashboard(_path(), status=status, halaman=halaman)
            csrf = _csrf(penangan, principal)
            token_buat = _token(penangan, principal, "riset_buat", {"section": "riset"})
            token_ekspor = {
                format_data: _token(penangan, principal, "riset_ekspor", {"section": format_data})
                for format_data in ("csv", "json")
            }
            _kirim(penangan, principal, ui.dashboard(
                data, csrf=csrf, token_buat=token_buat,
                token_ekspor=token_ekspor, status_filter=status,
            ), aksi_header=ui.aksi_data(csrf=csrf, token_ekspor=token_ekspor))
            return True
        if jalur == "/admin/riset/matriks":
            if _query(penangan, set()):
                raise ValueError("parameter tidak sah")
            _kirim(
                penangan, principal, ui.matriks(layanan.matriks(_path())),
                judul="Matriks wawancara", subjudul="Bandingkan pola tanpa mengubah studi eksploratif menjadi klaim populasi.",
            )
            return True
        query = _query(penangan, {"id", "q"})
        identitas = query.get("id", "")
        detail = layanan.detail(_path(), identitas)
        if detail is None:
            h._tidak_ada(penangan)
            return True
        if jalur == "/admin/riset/wawancara":
            isi = ui.ringkasan_wawancara(
                detail, csrf=_csrf(penangan, principal),
                token_aksi=_tokens_aksi(penangan, principal, detail),
            )
            _kirim(
                penangan, principal, isi, judul="Wawancara " + detail["kode_responden"],
                subjudul="Jawaban tidak harus lengkap; setiap topik cukup diberi status.", skrip=True,
            )
            return True
        kode_q = query.get("q", "Q1")
        item = next((x for x in detail["instrumen"]["pertanyaan"] if x["kode"] == kode_q), None)
        if item is None:
            h._tidak_ada(penangan)
            return True
        token = _token(
            penangan, principal, "riset_jawaban",
            {"target_id": identitas, "target_revisi": detail["revisi"], "section": kode_q},
        )
        _kirim(
            penangan, principal,
            ui.formulir_pertanyaan(
                detail, kode_q, csrf=_csrf(penangan, principal), token=token,
                readonly=detail["status"] not in ("draf", "perlu_redaksi"),
            ),
            judul=item["judul"], subjudul="Pertanyaan terbuka dahulu; coding dilakukan setelah mendengar jawaban.",
        )
    except (LookupError, ValueError):
        h._tidak_ada(penangan)
    except (store.StoreRisetBelumSiap, sqlite3.Error, OSError):
        h._galat(penangan, 503, "Layanan riset belum siap.")
    return True


def _waktu_lokal(teks):
    try:
        waktu = datetime.strptime(teks, "%Y-%m-%dT%H:%M").replace(
            tzinfo=timezone(timedelta(hours=7))
        )
    except (TypeError, ValueError):
        raise ValueError("waktu wawancara tidak sah") from None
    if waktu.strftime("%Y-%m-%dT%H:%M") != teks:
        raise ValueError("waktu wawancara tidak sah")
    return int(waktu.timestamp())


def _redirect_detail(penangan, identitas):
    h._redirect(penangan, "/admin/riset/wawancara?id=" + urllib.parse.quote(identitas, safe=""))


def _post_buat(penangan, principal, data):
    hasil = _periksa_form(penangan, principal, data, "riset_buat")
    if hasil["data"] != {"section": "riset"}:
        raise PermissionError("Form tidak sah.")
    if set(data) - {"kode_responden", "sumber", "diwawancarai", "consent_wawancara", "consent_rekaman"}:
        raise ValueError("isian asing")
    if data.get("consent_wawancara") != "1" or data.get("consent_rekaman", "0") not in ("0", "1"):
        raise ValueError("consent tidak sah")
    identitas = store.buat_wawancara(
        _path(), actor_id=principal.id_akun, operasi_id=hasil["op"],
        kode_responden=data.get("kode_responden", ""), sumber=data.get("sumber", ""),
        consent_rekaman=data.get("consent_rekaman", "0") == "1",
        diwawancarai=_waktu_lokal(data.get("diwawancarai", "")),
    )
    h._redirect(penangan, "/admin/riset/isi?id=%s&q=Q1" % urllib.parse.quote(identitas, safe=""))


def _post_jawaban(penangan, principal, data):
    hasil = _periksa_form(penangan, principal, data, "riset_jawaban")
    metadata = hasil["data"]
    identitas = data.pop("id", "")
    kode_q = data.pop("q", "")
    try:
        revisi_wawancara = int(data.pop("revisi_wawancara", ""))
        revisi_jawaban = int(data.pop("revisi_jawaban", ""))
    except (TypeError, ValueError):
        raise ValueError("revisi tidak sah") from None
    if metadata != {"target_id": identitas, "target_revisi": revisi_wawancara, "section": kode_q}:
        raise PermissionError("Snapshot form berubah.")
    tambahan = data.pop("kode_tambahan", [])
    if isinstance(tambahan, str):
        tambahan = [tambahan]
    lanjut = data.pop("lanjut", "ringkasan")
    if lanjut not in ("ringkasan", "berikut") or set(data) - {
        "status_jawaban", "jawaban_responden", "kutipan_responden", "kutipan_terpilih",
        "catatan_interviewer", "kode_utama", "status_klarifikasi",
    }:
        raise ValueError("isian asing")
    store.simpan_jawaban(
        _path(), actor_id=principal.id_akun, operasi_id=hasil["op"],
        wawancara_id=identitas, pertanyaan_kode=kode_q,
        revisi_wawancara=revisi_wawancara, revisi_jawaban=revisi_jawaban,
        status_jawaban=data.get("status_jawaban", ""),
        jawaban_responden=data.get("jawaban_responden", ""),
        kutipan_responden=data.get("kutipan_responden", ""),
        kutipan_terpilih=data.get("kutipan_terpilih", "0") == "1",
        catatan_interviewer=data.get("catatan_interviewer", ""),
        kode_utama=data.get("kode_utama") or None,
        kode_tambahan=tuple(tambahan),
        status_klarifikasi=data.get("status_klarifikasi", ""),
    )
    if lanjut == "berikut":
        detail = layanan.detail(_path(), identitas)
        berikut = layanan.pertanyaan_berikutnya(detail, kode_q)
        if berikut:
            h._redirect(penangan, "/admin/riset/isi?id=%s&q=%s" % (
                urllib.parse.quote(identitas, safe=""), urllib.parse.quote(berikut, safe="")))
            return
    _redirect_detail(penangan, identitas)


def _post_status(penangan, principal, data, *, aksi, fungsi):
    hasil = _periksa_form(penangan, principal, data, aksi)
    identitas = data.pop("id", "")
    meta = hasil["data"]
    if set(data) or meta.get("target_id") != identitas or meta.get("section") != "riset":
        raise PermissionError("Snapshot form berubah.")
    fungsi(
        _path(), actor_id=principal.id_akun, operasi_id=hasil["op"],
        wawancara_id=identitas, revisi=meta.get("target_revisi"),
    )
    _redirect_detail(penangan, identitas)


def _post_tarik(penangan, principal, data):
    hasil = _periksa_form(penangan, principal, data, "riset_tarik")
    identitas = data.pop("id", "")
    sandi = data.pop("reauth", "")
    meta = hasil["data"]
    if set(data) or meta.get("target_id") != identitas or meta.get("section") != "riset":
        raise PermissionError("Snapshot form berubah.")
    if not h._reauth(principal, sandi):
        raise PermissionError("Autentikasi ulang tidak sah.")
    store.tarik_consent(
        _path(), actor_id=principal.id_akun, operasi_id=hasil["op"],
        wawancara_id=identitas, revisi=meta.get("target_revisi"),
    )
    _redirect_detail(penangan, identitas)


def _post_ekspor(penangan, principal, data):
    hasil = _periksa_form(penangan, principal, data, "riset_ekspor")
    format_data = data.pop("format", "")
    if set(data) or hasil["data"] != {"section": format_data} or format_data not in ("csv", "json"):
        raise PermissionError("Form ekspor tidak sah.")
    payload = layanan.ekspor_csv(_path()) if format_data == "csv" else layanan.ekspor_json(_path())
    store.catat_ekspor(
        _path(), actor_id=principal.id_akun, operasi_id=hasil["op"], target_id="ekspor_semua",
    )
    jenis = "text/csv; charset=utf-8" if format_data == "csv" else "application/json; charset=utf-8"
    penangan.send_response(200)
    penangan.send_header("Content-Type", jenis)
    penangan.send_header("Content-Disposition", 'attachment; filename="riset-konsumen.%s"' % format_data)
    penangan.send_header("Content-Length", str(len(payload)))
    for nama, nilai in admin_security.header_privat().items():
        penangan.send_header(nama, nilai)
    penangan.end_headers()
    penangan.wfile.write(payload)


def tangani_post(penangan, jalur):
    if jalur not in RUTE_POST:
        return False
    principal = _principal_cookie(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        data = admin_security.baca_form(
            penangan, batas=32768, maksimum_field=40,
            berulang=("kode_tambahan",) if jalur == "/admin/riset/jawaban" else (),
        )
        if jalur == "/admin/riset/buat":
            _post_buat(penangan, principal, data)
        elif jalur == "/admin/riset/jawaban":
            _post_jawaban(penangan, principal, data)
        elif jalur == "/admin/riset/finalisasi":
            _post_status(penangan, principal, data, aksi="riset_finalisasi", fungsi=store.finalisasi)
        elif jalur == "/admin/riset/koreksi":
            _post_status(penangan, principal, data, aksi="riset_koreksi", fungsi=store.buka_koreksi)
        elif jalur == "/admin/riset/redaksi":
            _post_status(penangan, principal, data, aksi="riset_redaksi", fungsi=store.tandai_redaksi)
        elif jalur == "/admin/riset/tarik":
            _post_tarik(penangan, principal, data)
        else:
            _post_ekspor(penangan, principal, data)
    except LookupError:
        h._tidak_ada(penangan)
    except PermissionError:
        h._galat(penangan, 403, "Form atau autentikasi tidak sah.")
    except (store.KonflikRiset,):
        h._galat(penangan, 409, "Data berubah. Muat ulang wawancara sebelum menyimpan.")
    except (ValueError, KeyError, TypeError):
        h._galat(penangan, 400, "Isian riset tidak sah.")
    except (store.StoreRisetBelumSiap, sqlite3.Error, OSError):
        h._galat(penangan, 503, "Layanan riset belum dapat menyelesaikan tindakan.")
    return True
