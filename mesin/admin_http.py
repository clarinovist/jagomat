"""HTTP terjaga untuk pusat kendali admin."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import html
import os
import secrets
import sqlite3
import urllib.parse
from pathlib import Path

import admin_accounts
import admin_bulk
import admin_bulk_http
import admin_upload
import admin_pages
import admin_queries
import admin_registration
import admin_security
import admin_service
import admin_store
import admin_students
import auth
import database
import sessions
from admin_contracts import (
    AKSI_BUAT_GURU,
    AKSI_BUAT_LOGIN_MURID,
    AKSI_CABUT_SESI,
    AKSI_HAPUS_LOGIN,
    AKSI_HAPUS_SISWA,
    AKSI_RESET_SANDI,
    AKSI_UBAH_LEVEL,
    AKSI_UBAH_KELAS_SEKOLAH,
    PerintahProfilSiswa,
    KontrakTidakSah,
    PerintahAkun,
    PerintahPembuatanAkun,
    PerintahHapusSiswa,
    PerintahSiswa,
)
from teacher_style import SKRIP_MATA_SANDI

_SECTION = frozenset(("ringkasan", "keluarga", "siswa", "pendaftaran", "riwayat"))
_AKSI_AKUN = frozenset((
    AKSI_BUAT_GURU, AKSI_BUAT_LOGIN_MURID, AKSI_RESET_SANDI,
    AKSI_CABUT_SESI, AKSI_HAPUS_LOGIN,
))
_AKSI_DESTRUKTIF = frozenset((AKSI_CABUT_SESI, AKSI_HAPUS_LOGIN))


def _path_admin() -> Path:
    return admin_store.BAWAAN


def _path_transient() -> Path:
    return Path(os.environ.get(
        "ADMIN_TRANSIENT_DB", str(_path_admin().parent / "transient" / "admin-drafts.db")
    ))


def _akun_penandatangan_publik():
    akun = auth.muat_akun()
    kandidat = sorted(
        (item for item in akun if item.get("peran") == "admin"),
        key=lambda item: item.get("id_akun", ""),
    )
    return kandidat[0] if kandidat else None


def buat_token_pendaftaran() -> str:
    akun = _akun_penandatangan_publik()
    if akun is None:
        raise admin_store.StoreBelumSiap("penandatangan form tidak tersedia")
    return admin_security.buat_tinjauan(
        akun, None, "daftar_publik", {"section": "pendaftaran"}
    )


def periksa_token_pendaftaran(token: str):
    akun = _akun_penandatangan_publik()
    if akun is None:
        raise PermissionError("Form pendaftaran tidak sah.")
    data = admin_security.periksa_tinjauan(akun, None, token)
    if data["aksi"] != "daftar_publik" or data["data"] != {"section": "pendaftaran"}:
        raise PermissionError("Form pendaftaran tidak sah.")
    return data


def _akun_principal(principal):
    akun = auth.cari_akun(principal.pengguna)
    if (
        akun is None or akun.get("peran") != "admin"
        or akun.get("id_akun") != principal.id_akun
        or auth.revisi_auth(akun) != principal.revisi_auth
    ):
        return None
    return akun


def _principal_admin(penangan):
    principal = penangan._principal()
    if principal is None or principal.peran != "admin":
        return None
    return principal if _akun_principal(principal) is not None else None


def _token_sesi(penangan, principal) -> str | None:
    return penangan._ambil_token() if principal.metode == "cookie" else None


def _wajib_cookie(penangan, principal):
    token = _token_sesi(penangan, principal)
    if not token:
        raise PermissionError("Masuk melalui formulir untuk tindakan ini.")
    return token


def _identitas_bulk_hidup(penangan, principal):
    """Pertahankan snapshot actor, tetapi pastikan cookie request masih hidup."""
    token = _wajib_cookie(penangan, principal)
    terbaru = sessions.ambil_principal(
        token, path=sessions.BERKAS_SESI, path_akun=auth.BERKAS_SANDI,
    )
    if (terbaru is None or terbaru.peran != 'admin'
            or terbaru.id_akun != principal.id_akun
            or terbaru.revisi_auth != principal.revisi_auth
            or terbaru.pengguna != principal.pengguna):
        raise PermissionError('Sesi pengelola berubah.')
    return dict(path_auth=auth.BERKAS_SANDI, path_sesi=sessions.BERKAS_SESI,
                token_sesi=token, actor_id=principal.id_akun,
                actor_revisi=principal.revisi_auth)


def _csrf(akun, token_sesi: str | None) -> str:
    return admin_security.buat_tinjauan(akun, token_sesi, "cari", {"section": "search"})


def _cek_csrf(akun, token_sesi, token):
    data = admin_security.periksa_tinjauan(akun, token_sesi, token)
    if data["aksi"] != "cari" or data["data"] != {"section": "search"}:
        raise PermissionError("Form kedaluwarsa atau tidak sah.")


def _kirim_privat(penangan, isi: bytes, kode: int = 200, *, skrip=False):
    penangan.send_response(kode)
    penangan.send_header("Content-Type", "text/html; charset=utf-8")
    penangan.send_header("Content-Length", str(len(isi)))
    for nama, nilai in admin_security.header_privat(
        skrip_sandi=(SKRIP_MATA_SANDI + admin_pages.SKRIP_KONFIRMASI_LOGIN) if skrip else ""
    ).items():
        penangan.send_header(nama, nilai)
    penangan.end_headers()
    penangan.wfile.write(isi)


def _redirect(penangan, lokasi):
    penangan.send_response(303)
    penangan.send_header("Location", lokasi)
    for nama, nilai in admin_security.header_privat().items():
        penangan.send_header(nama, nilai)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def arahkan_admin(penangan, lokasi="/admin"):
    penangan.send_response(303)
    penangan.send_header("Location", lokasi)
    for nama, nilai in admin_security.header_privat().items():
        penangan.send_header(nama, nilai)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def _tidak_ada(penangan):
    _kirim_privat(
        penangan,
        admin_pages.halaman_admin(
            "ringkasan", '<section class="admin-kartu"><h2>Halaman tidak ada</h2></section>',
            pengguna="pengelola",
        ),
        404,
    )


def tidak_ada(penangan):
    """Respons admin generik untuk rute asing tanpa memantulkan parameter."""
    return _tidak_ada(penangan)


def tangani_akun_admin(penangan):
    """Alihkan section lintas keluarga lama; akun saya tetap di /akun."""
    principal = _principal_admin(penangan)
    if principal is None:
        return False
    try:
        query = _query(penangan, diizinkan={"section", "halaman", "chat"})
    except ValueError:
        _tidak_ada(penangan)
        return True
    if query.get("section", "akun") in ("akun", "arsip-pendamping"):
        return False
    arahkan_admin(penangan)
    return True


def _galat(penangan, kode, pesan):
    _kirim_privat(
        penangan,
        admin_pages.halaman_admin(
            "ringkasan",
            '<section class="admin-kartu admin-galat"><h2>Permintaan tidak dapat diproses</h2><p>%s</p></section>'
            % html.escape(pesan),
            pengguna="pengelola",
        ),
        kode,
    )


def _query(penangan, *, diizinkan):
    try:
        pasangan = urllib.parse.parse_qsl(
            urllib.parse.urlsplit(penangan.path).query,
            keep_blank_values=True, errors="strict", max_num_fields=12,
        )
    except (UnicodeError, ValueError):
        raise ValueError("Parameter tidak sah.") from None
    if len(pasangan) != len({nama for nama, _nilai in pasangan}):
        raise ValueError("Parameter ganda tidak sah.")
    hasil = dict(pasangan)
    if set(hasil) - set(diizinkan):
        raise ValueError("Parameter tidak dikenal.")
    return hasil


def _angka(nilai, bawaan=1):
    if nilai in (None, ""):
        return bawaan
    if not nilai.isascii() or not nilai.isdigit():
        raise ValueError("Angka tidak sah.")
    hasil = int(nilai)
    if hasil < 1:
        raise ValueError("Angka tidak sah.")
    return hasil


def _tanggal(nilai, akhir=False):
    if not nilai:
        return None
    waktu = datetime.strptime(nilai, "%Y-%m-%d").replace(tzinfo=timezone(timedelta(hours=7)))
    if waktu.strftime("%Y-%m-%d") != nilai:
        raise ValueError("Tanggal tidak sah.")
    return int(waktu.timestamp()) + (86399 if akhir else 0)


def _konteks(kon):
    return admin_queries.buat_konteks(kon, auth.muat_akun())


def _halaman_admin(principal, section, isi, *, skrip=False, judul=None, subjudul=None):
    return admin_pages.halaman_admin(
        section, isi, pengguna=principal.pengguna, judul=judul,
        subjudul=subjudul,
        skrip_sandi=(SKRIP_MATA_SANDI + admin_pages.SKRIP_KONFIRMASI_LOGIN) if skrip else "",
    )


def _render_get(penangan, principal, query):
    section = query.get("section", "ringkasan")
    import admin_launch_http
    if section in admin_launch_http.SECTION:
        return admin_launch_http.get(penangan, principal, query)
    if section not in _SECTION:
        section = "ringkasan"
    halaman = _angka(query.get("halaman"), 1)
    with database.buka() as kon:
        konteks = _konteks(kon)
        if section == "ringkasan":
            try:
                registrasi = admin_registration.status(_path_admin())
                teks_registrasi = "dibuka" if registrasi.dibuka else "ditutup"
            except admin_store.StoreBelumSiap:
                teks_registrasi = "belum tersedia"
            status_ai = "siap" if __import__("ai_service").siap() else "belum siap"
            ringkas_layanan = {
                "Pendaftaran": teks_registrasi,
                "Konfigurasi AI": status_ai,
                "Pembayaran": "belum tersedia",
                "Bukti backup": "Lihat pemeriksaan operasional",
            }
            belum_pasti = tertunda = 0
            jumlah_antrean = None
            try:
                belum_pasti = admin_store.daftar_riwayat(_path_admin(), status='uncertain', per_halaman=1).total
                tertunda = admin_store.daftar_riwayat(_path_admin(), status='reserved', per_halaman=1).total
                import admin_operations
                import admin_launch_service
                _baris, jumlah_antrean = admin_operations.antrean(_path_admin())
                with admin_store.buka_baca(_path_admin()) as layanan:
                    konfigurasi = admin_launch_service.konfigurasi_pembayaran(layanan)
                ringkas_layanan["Pembayaran"] = "Tahap " + konfigurasi["tahap"] if konfigurasi else "belum tersedia"
            except admin_store.StoreBelumSiap:
                pass  # Sumber hilang tetap dibedakan dari antrean kosong.
            isi = admin_pages.render_ringkasan(
                admin_queries.ringkasan_admin(kon, konteks),
                status_layanan=ringkas_layanan, jumlah_antrean=jumlah_antrean,
                operasi_belum_pasti=belum_pasti, operasi_tertunda=tertunda,
            )
        elif section == "keluarga":
            if query.get("id"):
                detail = admin_queries.detail_keluarga(
                    kon, konteks, query["id"], halaman=halaman
                )
                if detail is None:
                    return _tidak_ada(penangan)
                isi = admin_pages.render_detail_keluarga(
                    detail, tindakan=None if principal.metode == "cookie" else ""
                )
            else:
                csrf = (
                    _csrf(_akun_principal(principal), _token_sesi(penangan, principal))
                    if principal.metode == "cookie" else ""
                )
                isi = admin_pages.render_keluarga(
                    admin_queries.daftar_keluarga(
                        kon, konteks,
                        status=query.get("status", "semua"),
                        memiliki_anak=query.get("memiliki_anak", "semua"),
                        halaman=halaman,
                    ),
                    csrf=csrf, tampilkan_aksi=principal.metode == "cookie",
                )
                if principal.metode == "cookie":
                    token_bulk = admin_security.buat_tinjauan(
                        _akun_principal(principal), _wajib_cookie(penangan, principal),
                        "bulk_teacher_create", {"section": "keluarga"},
                    )
                    isi += admin_pages.render_bulk_awal(csrf, token_bulk)
        elif section == "siswa":
            if query.get("id"):
                detail = admin_queries.detail_siswa(kon, konteks, _angka(query["id"]))
                if detail is None:
                    return _tidak_ada(penangan)
                isi = admin_pages.render_detail_siswa(
                    detail, tindakan=None if principal.metode == "cookie" else ""
                )
                if principal.metode == 'cookie':
                    try:
                        snapshot = admin_students.tinjau_hapus_siswa(database.BAWAAN, auth.BERKAS_SANDI, detail.siswa.id)
                    except admin_accounts.KonflikAkun:
                        snapshot = None
                    if snapshot is not None:
                        isi += '<p><a class="admin-tautan admin-bahaya" href="/admin/tinjau?aksi=student_delete&amp;id=%d">Tinjau hapus siswa kosong</a></p>' % detail.siswa.id
            else:
                csrf = (
                    _csrf(_akun_principal(principal), _token_sesi(penangan, principal))
                    if principal.metode == "cookie" else ""
                )
                keluarga = admin_queries.daftar_keluarga(
                    kon, konteks, per_halaman=100
                ).item
                isi = admin_pages.render_siswa(
                    admin_queries.daftar_siswa(
                        kon, konteks, tingkat=query.get("tingkat", ""),
                        status=query.get("status", "semua"),
                        keluarga_id=query.get("keluarga_id", ""), halaman=halaman,
                    ),
                    keluarga,
                    csrf=csrf,
                )
                if principal.metode == "cookie":
                    isi += '<p><a class="admin-tautan" href="/admin/bulk/pilih?peran=murid">Kelola akun murid terpilih</a></p>'
        elif section == "pendaftaran":
            if principal.metode != "cookie":
                return _galat(
                    penangan, 403,
                    "Masuk melalui formulir untuk membuka pengaturan.",
                )
            status = admin_registration.status(_path_admin())
            akun = _akun_principal(principal)
            token_sesi = _wajib_cookie(penangan, principal)
            token = admin_security.buat_tinjauan(
                akun, token_sesi, "registration_config_update",
                {"revisi": status.revisi, "section": "pendaftaran"},
            )
            isi = admin_pages.render_pendaftaran(
                status, csrf=_csrf(akun, token_sesi), token=token
            )
        else:
            if query.get("sumber", "panel") == "ai":
                import ai_service
                riwayat = ai_service.riwayat_admin(
                    actor_id=query.get("actor_id", ""),
                    aksi=query.get("aksi", ""),
                    mulai=_tanggal(query.get("mulai", "")), selesai=_tanggal(query.get("selesai", ""), True),
                    halaman=halaman,
                )
                isi = admin_pages.render_riwayat_ai(riwayat, filter_data=query)
            elif query.get('sumber', 'panel') == 'batch':
                if query.get('id'):
                    riwayat = admin_store.baca_batch_durable(_path_admin(), query['id'])
                    if riwayat is None:
                        return _tidak_ada(penangan)
                    isi = admin_pages.render_audit_batch_detail(riwayat)
                else:
                    riwayat = admin_store.daftar_batch_durable(
                        _path_admin(), actor_id=query.get('actor_id', ''),
                        aksi=query.get('aksi', ''), status=query.get('status', ''),
                        mulai=_tanggal(query.get('mulai', '')),
                        selesai=_tanggal(query.get('selesai', ''), True), halaman=halaman,
                    )
                    isi = admin_pages.render_audit_batch(riwayat, filter_data=query)
            elif query.get("sumber", "panel") == "panel":
                riwayat = admin_store.daftar_riwayat(
                    _path_admin(), actor_id=query.get("actor_id", ""),
                    aksi=query.get("aksi", ""), status=query.get("status", ""),
                    mulai=_tanggal(query.get("mulai", "")), selesai=_tanggal(query.get("selesai", ""), True),
                    halaman=halaman,
                )
                isi = admin_pages.render_riwayat(riwayat, filter_data=query)
            else:
                raise ValueError("Sumber tidak dikenal.")
    skrip = principal.metode == "cookie" and section in ("keluarga", "pendaftaran")
    _kirim_privat(penangan, _halaman_admin(principal, section, isi, skrip=skrip), skrip=skrip)


def tangani_get(penangan, jalur):
    if jalur not in ("/admin", "/admin/tinjau", "/admin/bulk/pilih", "/admin/bulk/hasil", "/admin/bulk/templat"):
        return False
    principal = _principal_admin(penangan)
    if principal is None:
        _tidak_ada(penangan)
        return True
    try:
        if jalur == "/admin/bulk/pilih":
            admin_bulk_http.get_pilihan(penangan, principal)
            return True
        if jalur == "/admin/bulk/hasil":
            query = _query(penangan, diizinkan={"id"})
            tampilkan_batch(penangan, principal, query.get("id", ""))
            return True
        if jalur == "/admin/bulk/templat":
            isi = b"pengguna\r\n"
            penangan.send_response(200)
            penangan.send_header("Content-Type", "text/csv; charset=utf-8")
            penangan.send_header("Content-Disposition", 'attachment; filename="templat-akun.csv"')
            penangan.send_header("Content-Length", str(len(isi)))
            for nama, nilai in admin_security.header_privat().items():
                penangan.send_header(nama, nilai)
            penangan.end_headers()
            penangan.wfile.write(isi)
            return True
        if jalur == "/admin/tinjau":
            query = _query(penangan, diizinkan={"aksi", "id"})
            _render_tinjauan(penangan, principal, query)
            return True
        query = _query(
            penangan,
            diizinkan={"section", "id", "halaman", "status", "memiliki_anak", "tingkat", "keluarga_id", "actor_id", "aksi", "mulai", "selesai", "sumber", "bulan"},
        )
        _render_get(penangan, principal, query)
    except LookupError:
        _tidak_ada(penangan)
    except PermissionError:
        _galat(penangan, 403, "Masuk melalui formulir untuk tindakan ini.")
    except admin_accounts.KonflikAkun:
        _tidak_ada(penangan)
    except (admin_store.StoreBelumSiap, sqlite3.Error):
        _galat(penangan, 503, "Layanan admin belum siap.")
    except (admin_queries.InputQueryTidakSah, admin_store.DataAuditTidakSah, ValueError):
        _tidak_ada(penangan)
    return True


def _target_akun(id_akun):
    cocok = [item for item in auth.muat_akun() if item.get("id_akun") == id_akun]
    return cocok[0] if len(cocok) == 1 else None


def _render_tinjauan(penangan, principal, query):
    aksi = query.get("aksi", "")
    akun = _akun_principal(principal)
    token_sesi = _wajib_cookie(penangan, principal)
    csrf = _csrf(akun, token_sesi)
    if aksi == AKSI_BUAT_GURU:
        token = admin_security.buat_tinjauan(
            akun, token_sesi, aksi,
            {"target_id": "candidate_" + secrets.token_hex(16), "target_peran": "guru", "section": "keluarga"},
        )
        isi = admin_pages.form_buat_keluarga(csrf, token)
        return _kirim_privat(
            penangan, _halaman_admin(principal, "keluarga", isi, skrip=True),
            skrip=True,
        )
    if aksi in (AKSI_RESET_SANDI, AKSI_CABUT_SESI, AKSI_HAPUS_LOGIN):
        target = _target_akun(query.get("id", ""))
        if target is None or target.get("peran") not in ("guru", "murid"):
            return _tidak_ada(penangan)
        token = admin_security.buat_tinjauan(
            akun, token_sesi, aksi,
            {"target_id": target["id_akun"], "target_revisi": auth.revisi_auth(target), "target_peran": target["peran"], "section": "keluarga" if target["peran"] == "guru" else "siswa"},
        )
        tindakan = admin_pages.form_tindakan_akun(
            target["pengguna"], target["peran"], csrf, {aksi: token},
            kembali="/admin?section=siswa",
        )
        with database.buka() as kon:
            konteks = _konteks(kon)
            if target["peran"] == "guru":
                detail = admin_queries.detail_keluarga(
                    kon, konteks, target["id_akun"]
                )
                if detail is None:
                    return _tidak_ada(penangan)
                tindakan = admin_pages.form_tindakan_akun(
                    target["pengguna"], target["peran"], csrf, {aksi: token},
                    kembali="/admin?section=keluarga&id=" + target["id_akun"],
                    jumlah_siswa=detail.keluarga.jumlah_siswa,
                    jumlah_sesi=detail.keluarga.jumlah_sesi,
                )
                isi = admin_pages.render_detail_keluarga(
                    detail, tindakan=tindakan
                )
                section = "keluarga"
            else:
                siswa_id = target.get("siswa_id")
                detail = (
                    admin_queries.detail_siswa(kon, konteks, int(siswa_id))
                    if type(siswa_id) is int else None
                )
                if detail is None or detail.siswa.login_id != target["id_akun"]:
                    return _tidak_ada(penangan)
                isi = admin_pages.render_detail_siswa(
                    detail, tindakan=tindakan
                )
                section = "siswa"
        return _kirim_privat(
            penangan, _halaman_admin(principal, section, isi, skrip=True),
            skrip=True,
        )
    if aksi == AKSI_HAPUS_SISWA:
        siswa_id = _angka(query.get('id'))
        snapshot = admin_students.tinjau_hapus_siswa(database.BAWAAN, auth.BERKAS_SANDI, siswa_id)
        if snapshot is None:
            return _tidak_ada(penangan)
        payload = {'siswa_id': snapshot.siswa_id, 'tingkat': snapshot.expected_level,
                   'login_id': snapshot.login_id or '', 'login_revisi': snapshot.login_revisi or 0}
        token = admin_security.buat_tinjauan(akun, token_sesi, aksi, payload)
        with database.buka() as kon:
            detail = admin_queries.detail_siswa(kon, _konteks(kon), siswa_id)
        if detail is None:
            return _tidak_ada(penangan)
        isi = admin_pages.render_detail_siswa(detail, tindakan=admin_pages.form_hapus_siswa(csrf, token))
        return _kirim_privat(penangan, _halaman_admin(principal, 'siswa', isi, skrip=True), skrip=True)
    if aksi in (AKSI_UBAH_LEVEL, AKSI_UBAH_KELAS_SEKOLAH, AKSI_BUAT_LOGIN_MURID):
        siswa_id = _angka(query.get("id"))
        with database.buka() as kon:
            konteks = _konteks(kon)
            detail = admin_queries.detail_siswa(kon, konteks, siswa_id)
        if detail is None:
            return _tidak_ada(penangan)
        if aksi == AKSI_UBAH_KELAS_SEKOLAH:
            payload = {'siswa_id': siswa_id, 'revisi_profil': detail.siswa.revisi_profil, 'section': 'siswa'}
            token = admin_security.buat_tinjauan(akun, token_sesi, aksi, payload)
            isi = admin_pages.render_detail_siswa(detail, tindakan=admin_pages.form_kelas_sekolah(detail, csrf, token))
            return _kirim_privat(penangan, _halaman_admin(principal, 'siswa', isi, skrip=True), skrip=True)
        if aksi == AKSI_UBAH_LEVEL:
            payload = {"siswa_id": siswa_id, "tingkat": detail.siswa.tingkat, "section": "siswa"}
            token_level = admin_security.buat_tinjauan(akun, token_sesi, aksi, payload)
            token_login = ""
        else:
            token_level = ""
            token_login = admin_security.buat_tinjauan(
                akun, token_sesi, aksi,
                {"siswa_id": siswa_id, "target_id": "candidate_" + secrets.token_hex(16), "target_peran": "murid", "section": "siswa"},
            )
        isi = admin_pages.render_detail_siswa(
            detail,
            tindakan=admin_pages.form_tindakan_siswa(
                detail, csrf, token_level, token_login
            ),
        )
        return _kirim_privat(
            penangan, _halaman_admin(principal, "siswa", isi, skrip=True),
            skrip=True,
        )
    _tidak_ada(penangan)


def _reauth(principal, sandi):
    akun = auth.autentikasi(principal.pengguna, sandi)
    return akun is not None and (
        akun.id_akun == principal.id_akun
        and akun.revisi_auth == principal.revisi_auth
        and akun.peran == "admin"
    )


def _token_final(penangan, principal, data, aksi):
    akun = _akun_principal(principal)
    if akun is None:
        raise PermissionError('Identitas pengelola berubah.')
    token_sesi = _wajib_cookie(penangan, principal)
    _cek_csrf(akun, token_sesi, data.pop("csrf", None))
    token = data.pop("tinjauan", None)
    tinjauan = admin_security.periksa_tinjauan(akun, token_sesi, token)
    if tinjauan["aksi"] != aksi:
        raise PermissionError("Tinjauan tidak cocok.")
    if not _reauth(principal, data.pop("reauth", "")):
        raise PermissionError("Autentikasi ulang gagal.")
    data.pop("aksi", None)
    return akun, tinjauan, token


def token_domain(token):
    """Opaque bounded untuk receipt; signed token lengkap tetap hanya di request."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _perintah_akun(akun, tinjauan, token):
    meta = tinjauan["data"]
    return PerintahAkun(
        tinjauan["op"], akun["id_akun"], auth.revisi_auth(akun),
        tinjauan["aksi"], meta["target_id"], int(meta["target_revisi"]),
        meta["target_peran"], token_domain(token),
    )


def _pastikan_sukses(hasil):
    if hasil.hasil.status != "succeeded":
        raise admin_store.KonflikOperasi("operasi tidak berhasil")
    return hasil


def _post_akun(penangan, principal, data):
    aksi = data.get("aksi", "")
    if aksi not in _AKSI_AKUN:
        raise ValueError("Aksi akun tidak dikenal.")
    akun, tinjauan, token = _token_final(penangan, principal, data, aksi)
    meta = tinjauan["data"]
    sandi = data.pop("sandi_baru", None)
    if aksi in _AKSI_DESTRUKTIF and data.pop("konfirmasi", None) != "1":
        raise ValueError("Konfirmasi wajib.")
    if aksi == AKSI_BUAT_GURU:
        alias = data.pop("alias", "")
        if data:
            raise ValueError("Field tidak dikenal.")
        perintah = PerintahPembuatanAkun(
            tinjauan["op"], akun["id_akun"], auth.revisi_auth(akun), aksi,
            meta["target_id"], "guru", alias, token_domain(token),
        )
        hasil = _pastikan_sukses(admin_service.buat_akun(
            _path_admin(), auth.BERKAS_SANDI, database.BAWAAN,
            perintah, sandi_baru=sandi,
        ))
        if hasil.credential_sekali is not None:
            isi = admin_pages.render_hasil_credential(
                alias, hasil.credential_sekali
            )
            return _kirim_privat(
                penangan,
                _halaman_admin(
                    principal, "keluarga", isi, skrip=True,
                    judul="Akses baru", subjudul="Simpan akses sebelum meninggalkan halaman.",
                ),
                skrip=True,
            )
    elif aksi == AKSI_BUAT_LOGIN_MURID:
        alias = data.pop("alias", "")
        if data:
            raise ValueError("Field tidak dikenal.")
        perintah = PerintahPembuatanAkun(
            tinjauan["op"], akun["id_akun"], auth.revisi_auth(akun), aksi,
            meta["target_id"], "murid", alias, token_domain(token),
            siswa_id=int(meta["siswa_id"]),
        )
        hasil = _pastikan_sukses(admin_service.buat_akun(
            _path_admin(), auth.BERKAS_SANDI, database.BAWAAN,
            perintah, sandi_baru=sandi,
        ))
        if hasil.credential_sekali is not None:
            isi = admin_pages.render_hasil_credential(alias, hasil.credential_sekali)
            return _kirim_privat(
                penangan, _halaman_admin(principal, "siswa", isi, skrip=True),
                skrip=True,
            )
    else:
        if aksi != AKSI_RESET_SANDI and sandi is not None:
            raise ValueError("Field tidak dikenal.")
        if data:
            raise ValueError("Field tidak dikenal.")
        perintah = _perintah_akun(akun, tinjauan, token)
        hasil = _pastikan_sukses(admin_service.jalankan(
            _path_admin(), auth.BERKAS_SANDI, perintah, sandi_baru=sandi
        ))
        if hasil.credential_sekali is not None:
            target = _target_akun(meta["target_id"])
            alias = target["pengguna"] if target else "Akun"
            isi = admin_pages.render_hasil_credential(
                alias, hasil.credential_sekali
            )
            return _kirim_privat(
                penangan,
                _halaman_admin(
                    principal, meta.get("section", "keluarga"), isi,
                    skrip=True,
                ),
                skrip=True,
            )
    _redirect(penangan, "/admin?section=" + meta.get("section", "keluarga"))


def _post_siswa(penangan, principal, data):
    aksi = data.get("aksi", "")
    if aksi not in (AKSI_UBAH_LEVEL, AKSI_UBAH_KELAS_SEKOLAH, AKSI_HAPUS_SISWA):
        raise ValueError("Aksi siswa tidak dikenal.")
    akun, tinjauan, token = _token_final(penangan, principal, data, aksi)
    if aksi == AKSI_HAPUS_SISWA:
        if data.pop('konfirmasi', None) != '1' or data:
            raise ValueError('Konfirmasi hapus wajib.')
        meta = tinjauan['data']
        login_id = meta['login_id'] or None
        perintah = PerintahHapusSiswa(
            tinjauan['op'], akun['id_akun'], auth.revisi_auth(akun), aksi,
            int(meta['siswa_id']), meta['tingkat'], login_id,
            int(meta['login_revisi']) if login_id else None, token_domain(token),
        )
        _pastikan_sukses(admin_service.hapus_siswa(
            _path_admin(), auth.BERKAS_SANDI, database.BAWAAN, perintah,
        ))
        return _redirect(penangan, '/admin?section=siswa')
    if aksi == AKSI_UBAH_KELAS_SEKOLAH:
        import learning_profile_ui
        kelas = learning_profile_ui.baca_kelas_form(data.pop('kelas_sekolah', None))
        revisi = learning_profile_ui.baca_revisi_form(data.pop('revisi_profil', None))
        meta = tinjauan['data']
        if data or set(meta) != {'siswa_id', 'revisi_profil', 'section'}:
            raise ValueError('Field profil tidak dikenal.')
        if revisi != meta['revisi_profil']:
            raise ValueError('Revisi tidak cocok dengan tinjauan. Muat ulang.')
        perintah = PerintahProfilSiswa(tinjauan['op'], akun['id_akun'], auth.revisi_auth(akun),
            aksi, meta['siswa_id'], revisi, kelas, token_domain(token))
        _pastikan_sukses(admin_service.ubah_kelas_sekolah(
            _path_admin(), auth.BERKAS_SANDI, database.BAWAAN, perintah,
        ))
        return _redirect(penangan, '/admin?section=siswa&id=%d' % meta['siswa_id'])
    level_baru = data.pop("tingkat_baru", "")
    if data:
        raise ValueError("Field tidak dikenal.")
    meta = tinjauan["data"]
    perintah = PerintahSiswa(
        tinjauan["op"], akun["id_akun"], auth.revisi_auth(akun), aksi,
        int(meta["siswa_id"]), meta["tingkat"], level_baru, token_domain(token),
    )
    _pastikan_sukses(admin_service.ubah_kelas(
        _path_admin(), auth.BERKAS_SANDI, database.BAWAAN, perintah
    ))
    _redirect(penangan, "/admin?section=siswa&id=%d" % int(meta["siswa_id"]))


def _post_pendaftaran(penangan, principal, data):
    aksi = data.get("aksi", "")
    if aksi != "registration_config_update":
        raise ValueError("Aksi pendaftaran tidak dikenal.")
    akun, tinjauan, token = _token_final(penangan, principal, data, aksi)
    pesan = data.pop("pesan_kode", "")
    nilai_dibuka = data.pop("dibuka", None)
    if nilai_dibuka not in (None, "1"):
        raise ValueError("Nilai sakelar tidak sah.")
    dibuka = nilai_dibuka == "1"
    if data:
        raise ValueError("Field tidak dikenal.")
    hasil = admin_registration.ubah(
        _path_admin(), operasi_id=tinjauan["op"], actor_id=akun["id_akun"],
        path_auth=auth.BERKAS_SANDI, actor_revisi=principal.revisi_auth,
        revisi=int(tinjauan["data"]["revisi"]), dibuka=dibuka,
        pesan_kode=pesan, token_tinjauan=token_domain(token),
    )
    if hasil.status != "succeeded":
        raise admin_store.KonflikOperasi("pengaturan tidak tersimpan")
    _redirect(penangan, "/admin?section=pendaftaran")


def _post_cari(penangan, principal, data):
    section = data.pop("section", "")
    if data.pop("mode", "") != "cari" or section not in ("keluarga", "siswa"):
        raise ValueError("Pencarian tidak sah.")
    akun = _akun_principal(principal)
    token_sesi = _wajib_cookie(penangan, principal)
    _cek_csrf(akun, token_sesi, data.pop("csrf", None))
    halaman = _angka(data.pop("halaman", None), 1)
    with database.buka() as kon:
        konteks = _konteks(kon)
        if section == "keluarga":
            diizinkan = {"cari", "status", "memiliki_anak"}
            if set(data) - diizinkan:
                raise ValueError("Field tidak dikenal.")
            hasil = admin_queries.daftar_keluarga(
                kon, konteks, cari=data.get("cari", ""),
                status=data.get("status", "semua"),
                memiliki_anak=data.get("memiliki_anak", "semua"),
                halaman=halaman,
            )
            isi = admin_pages.render_keluarga(
                hasil, csrf=_csrf(akun, token_sesi)
            )
        else:
            diizinkan = {"cari", "tingkat", "keluarga_id", "status"}
            if set(data) - diizinkan:
                raise ValueError("Field tidak dikenal.")
            keluarga = admin_queries.daftar_keluarga(
                kon, konteks, per_halaman=100
            ).item
            hasil = admin_queries.daftar_siswa(
                kon, konteks, cari=data.get("cari", ""),
                tingkat=data.get("tingkat", ""),
                keluarga_id=data.get("keluarga_id", ""),
                status=data.get("status", "semua"), halaman=halaman,
            )
            isi = admin_pages.render_siswa(
                hasil, keluarga, csrf=_csrf(akun, token_sesi),
            )
    _kirim_privat(penangan, _halaman_admin(principal, section, isi))


def _post_bulk_impor(penangan, principal, data):
    akun, tinjauan, _token = _token_final(
        penangan, principal, data, "bulk_teacher_create"
    )
    isi_csv = data.pop("csv", b"")
    if data:
        raise ValueError("Field tidak dikenal.")
    alias = admin_bulk.parse_csv_alias(isi_csv)
    existing = {a["pengguna"].casefold() for a in auth.muat_akun()}
    with database.buka() as kon:
        if any(nama.casefold() in existing or admin_registration.alias_pemilik_ada(kon, nama) for nama in alias):
            raise admin_bulk.BulkTidakSah("Alias sudah digunakan atau memiliki data lama.")
    target = tuple(
        admin_bulk.TargetBulk(
            "item_" + secrets.token_hex(16), "op_" + secrets.token_hex(16),
            "candidate_" + secrets.token_hex(16), 0, "guru", nama,
        )
        for nama in alias
    )
    return buat_tinjauan_batch(penangan, principal, AKSI_BUAT_GURU, "guru", target)


def buat_tinjauan_batch(penangan, principal, aksi, peran, target):
    identitas = _identitas_bulk_hidup(penangan, principal)
    batch_id = "batch_" + secrets.token_hex(16)
    admin_bulk.buat_batch(
        _path_admin(), _path_transient(), batch_id=batch_id,
        aksi=aksi, target_peran=peran, target=target, **identitas,
    )
    tampilkan_batch(penangan, principal, batch_id)


def tampilkan_batch(penangan, principal, batch_id, hasil=()):
    identitas = _identitas_bulk_hidup(penangan, principal)
    akun = _akun_principal(principal)
    if akun is None:
        raise PermissionError('Identitas pengelola berubah.')
    sesi = identitas['token_sesi']
    batch = admin_bulk.baca_batch(
        _path_admin(), _path_transient(), batch_id=batch_id, **identitas,
    )
    item_serah = ','.join(x.item_id for x in batch.item
                         if x.status == 'succeeded' and x.credential_status == 'unconfirmed')
    tokens = {aksi: admin_security.buat_tinjauan(
        akun, sesi, "bulk_" + aksi,
        {"batch_id": batch_id, **({"item_ids": item_serah} if aksi == 'handover' else {})},
        operasi_id=batch.kelompok_aktif_id if aksi == 'process' else None,
    ) for aksi in ("process", "stop", "handover")}
    aliases = {a['id_akun']: a['pengguna'] for a in auth.muat_akun()}
    isi = admin_pages.render_bulk_batch(batch, hasil, _csrf(akun, sesi), tokens, aliases)
    # Perubahan cookie selama query/render juga membuang credential response.
    _identitas_bulk_hidup(penangan, principal)
    _kirim_privat(penangan, _halaman_admin(
        principal, "keluarga" if batch.target_peran == "guru" else "siswa",
        isi, skrip=True, judul="Tinjau batch", subjudul="Target tetap; maksimal 10 akun per permintaan.",
    ), skrip=True)


def _post_bulk_proses(penangan, principal, data, mode="process"):
    akun, tinjauan, _token = _token_final(
        penangan, principal, data, "bulk_" + mode
    )
    batch_id = data.pop("batch_id", "")
    item_ids = data.pop("item_ids", "").split(",") if mode == "handover" else []
    if data.pop("konfirmasi", None) != "1":
        raise ValueError("Konfirmasi dampak wajib.")
    if data or batch_id != tinjauan["data"].get("batch_id"):
        raise ValueError("Batch tidak sah.")
    identitas = dict(_identitas_bulk_hidup(penangan, principal), batch_id=batch_id)
    if mode == "stop":
        admin_bulk.hentikan(_path_admin(), _path_transient(), **identitas)
        return _redirect(penangan, "/admin/bulk/hasil?id=" + batch_id)
    if mode == "handover":
        if ','.join(item_ids) != tinjauan['data'].get('item_ids'):
            raise ValueError("Item penyerahan tidak sesuai tinjauan.")
        admin_bulk.konfirmasi_penyerahan(
            _path_admin(), _path_transient(), item_ids=tuple(item_ids),
            operasi_id=tinjauan['op'], **identitas,
        )
        return _redirect(penangan, "/admin/bulk/hasil?id=" + batch_id)
    path_auth = identitas.pop('path_auth')
    hasil = admin_bulk.proses_kelompok(
        _path_admin(), path_auth, database.BAWAAN,
        path_transient=_path_transient(), kelompok_id=tinjauan["op"], **identitas,
    )
    tampilkan_batch(penangan, principal, batch_id, hasil)


def tangani_post(penangan, jalur):
    import admin_launch_http
    if admin_launch_http.tangani_post(penangan, jalur):
        return True
    if jalur not in (
        "/admin", "/admin/akun", "/admin/siswa", "/admin/pendaftaran",
        "/admin/bulk/impor", "/admin/bulk/proses", "/admin/bulk/pilih",
        "/admin/bulk/hentikan", "/admin/bulk/serahkan",
    ):
        return False
    principal = _principal_admin(penangan)
    if principal is None:
        _tidak_ada(penangan)
        return True
    try:
        if jalur == "/admin/bulk/impor":
            data = admin_upload.baca_csv(penangan)
        else:
            data = admin_security.baca_form(
                penangan, batas=65536 if jalur.startswith("/admin/bulk/") else admin_security.BATAS_FORM,
                maksimum_field=132 if jalur.startswith("/admin/bulk/") else 32,
                berulang=("target", "hapus") if jalur == "/admin/bulk/pilih" else (),
            )
        if jalur == "/admin":
            _post_cari(penangan, principal, data)
        elif jalur == "/admin/akun":
            _post_akun(penangan, principal, data)
        elif jalur == "/admin/siswa":
            _post_siswa(penangan, principal, data)
        elif jalur == "/admin/pendaftaran":
            _post_pendaftaran(penangan, principal, data)
        elif jalur == "/admin/bulk/pilih":
            admin_bulk_http.post_pilihan(penangan, principal, data)
        elif jalur == "/admin/bulk/impor":
            _post_bulk_impor(penangan, principal, data)
        else:
            mode = {"/admin/bulk/proses": "process", "/admin/bulk/hentikan": "stop", "/admin/bulk/serahkan": "handover"}[jalur]
            _post_bulk_proses(penangan, principal, data, mode)
    except KeyError:
        _galat(penangan, 400, "Isian tidak sah.")
    except LookupError:
        _tidak_ada(penangan)
    except PermissionError:
        _galat(penangan, 403, "Form kedaluwarsa atau tidak sah.")
    except (KontrakTidakSah, admin_bulk.BulkTidakSah, admin_queries.InputQueryTidakSah, ValueError, KeyError):
        _galat(penangan, 400, "Isian tidak sah.")
    except (admin_accounts.KonflikAkun, admin_students.KonflikSiswa, admin_store.KonflikOperasi):
        _galat(penangan, 409, "Data berubah. Buka ulang tinjauan.")
    except admin_service.OperasiTidakDapatDilanjutkan:
        _galat(penangan, 409, "Operasi tidak dapat dilanjutkan dengan aman.")
    except (admin_service.CrashSebelumFinalisasi, admin_service.CrashSetelahFinalisasi):
        _galat(penangan, 503, "Hasil tindakan belum dapat dipastikan. Perlu pemeriksaan receipt, bukan tindakan baru.")
    except (admin_store.StoreBelumSiap, sqlite3.Error, OSError):
        _galat(penangan, 503, "Layanan admin belum dapat menyelesaikan tindakan.")
    return True
