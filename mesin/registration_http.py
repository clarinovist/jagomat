"""Rute HTTP pendaftaran akun keluarga dan profil pertama."""
from __future__ import annotations

import time

import auth
import database
import sessions


def tangani_get(penangan, jalur: str) -> bool:
    """Render formulir pendaftaran sesuai status layanan."""
    if jalur != "/daftar":
        return False
    import admin_http
    import admin_registration
    import admin_store
    import landing

    try:
        status = admin_registration.status(admin_store.BAWAAN)
        token_form = (
            admin_http.buat_token_pendaftaran() if status.dibuka else ""
        )
    except admin_store.StoreBelumSiap:
        penangan._kirim(
            landing.halaman_daftar(
                "Pendaftaran sementara belum tersedia. Akun yang sudah ada "
                "tetap bisa masuk.",
                galat=True,
                pendaftaran_dibuka=False,
                belum_tersedia=True,
            ),
            503,
        )
        return True
    import product_analytics_http as analitik
    penangan._kirim(landing.halaman_daftar(
        pendaftaran_dibuka=status.dibuka,
        token_form=token_form,
        analitik=analitik.form_daftar(),
    ))
    return True


def tangani_post(penangan, jalur: str) -> bool:
    """Daftarkan akun+profil secara idempoten, lalu terbitkan sesi login."""
    if jalur != "/daftar":
        return False

    import admin_http
    import admin_registration
    import admin_security
    import admin_store
    import landing
    import learning_profile_ui
    import product_analytics_http as analitik
    import subscription_registration
    from admin_accounts import DomainAkunTidakSah
    from admin_contracts import KontrakTidakSah

    nama_anak = ""
    kelas_sekolah = None
    profil_parameter = ""

    def halaman_daftar(*args, **kwargs):
        return landing.halaman_daftar(
            *args,
            nama_anak=nama_anak,
            kelas_sekolah=kelas_sekolah,
            profil_parameter=profil_parameter,
            **kwargs,
        )

    try:
        data = admin_security.baca_form(penangan)
        if set(data) - {
            "nama", "sandi", "setuju", "token_form", "analitik",
            "sumber_analitik", "nama_anak", "kelas_sekolah",
            "profil_parameter",
        } or not {"nama", "sandi"} <= set(data):
            raise ValueError("Isian pendaftaran tidak sah.")
        if data.get("analitik", "0") not in ("0", "1"):
            raise ValueError("persetujuan analitik tidak sah")
        if data.get("sumber_analitik", "tidak_diketahui") not in analitik.d.SUMBER:
            raise ValueError("sumber analitik tidak sah")
        nama = data["nama"].strip()
        sandi = data["sandi"]
        nama_anak = data.get("nama_anak", "").strip()
        kelas_sekolah = learning_profile_ui.baca_kelas_form(
            data.get("kelas_sekolah", "")
        )
        profil_parameter = data.get("profil_parameter")
        token_baru = admin_http.buat_token_pendaftaran()
        status_daftar = admin_registration.status(admin_store.BAWAAN)
        if not status_daftar.dibuka:
            raise PermissionError("Pendaftaran ditutup.")
        if not nama:
            penangan._kirim(halaman_daftar(
                "Nama wajib diisi.", galat=True, nama=nama,
                token_form=token_baru,
            ))
            return True
        if len(sandi) < 8:
            penangan._kirim(halaman_daftar(
                "Kata sandi minimal 8 karakter.", galat=True, nama=nama,
                token_form=token_baru,
            ))
            return True
        if data.get("setuju") != "1":
            penangan._kirim(halaman_daftar(
                "Centang persetujuan Kebijakan Privasi dulu, ya.",
                galat=True,
                nama=nama,
                token_form=token_baru,
            ))
            return True
        if sessions.sedang_diblokir(nama, penangan.client_address[0]):
            penangan._kirim(
                halaman_daftar(
                    "Terlalu banyak percobaan. Coba lagi 15 menit lagi.",
                    galat=True,
                    nama=nama,
                    token_form=data.get("token_form", token_baru),
                ),
                429,
            )
            return True
        tinjauan = admin_http.periksa_token_pendaftaran(
            data.get("token_form", "")
        )
        akun_baru = subscription_registration.daftar_web(
            admin_store.BAWAAN,
            auth.BERKAS_SANDI,
            database.BAWAAN,
            operasi_id=tinjauan["op"],
            alias=nama,
            sandi=sandi,
            nama_anak=nama_anak,
            kelas_sekolah=kelas_sekolah,
            profil_parameter=profil_parameter,
            token_form=admin_http.token_domain(data["token_form"]),
            sekarang=int(time.time()),
        ).akun
        analitik.setelah_daftar(
            auth.PrincipalAkun(
                akun_baru.pengguna,
                akun_baru.peran,
                akun_baru.id_akun,
                akun_baru.revisi_auth,
            ),
            setuju=data.get("analitik") == "1" and akun_baru.baru,
            sumber=data.get("sumber_analitik", "tidak_diketahui"),
        )
        token = sessions.buat_dari_principal(akun_baru)
        if token is None:
            penangan._kirim(
                halaman_daftar(
                    "Akun berubah saat pendaftaran. Silakan masuk lagi.",
                    galat=True,
                    nama=nama,
                    token_form=admin_http.buat_token_pendaftaran(),
                ),
                409,
            )
            return True
    except admin_registration.RegistrasiBelumSelesai:
        penangan._kirim(halaman_daftar(
            "Pendaftaran belum selesai. Coba kirim lagi dengan isian yang sama.",
            galat=True,
            nama=locals().get("nama", ""),
            token_form=locals().get("data", {}).get("token_form", ""),
        ), 503)
        return True
    except admin_store.StoreBelumSiap:
        isi = (
            halaman_daftar(
                "Pendaftaran sementara belum tersedia. Akun yang sudah ada "
                "tetap bisa masuk.",
                galat=True,
                pendaftaran_dibuka=False,
                belum_tersedia=True,
            )
            if "tinjauan" not in locals()
            else halaman_daftar(
                "Pendaftaran belum selesai. Coba kirim lagi dengan isian yang sama.",
                galat=True,
                nama=locals().get("nama", ""),
                token_form=data.get("token_form", ""),
            )
        )
        penangan._kirim(isi, 503)
        return True
    except PermissionError as galat:
        ditutup = "ditutup" in str(galat)
        penangan._kirim(
            halaman_daftar(
                "Pendaftaran baru sedang ditutup. Akun yang sudah terdaftar "
                "tetap bisa masuk."
                if ditutup
                else "Form pendaftaran sudah tidak berlaku. Buka ulang halaman "
                     "pendaftaran.",
                galat=True,
                nama=locals().get("nama", ""),
                pendaftaran_dibuka=not ditutup,
                token_form=(
                    "" if ditutup else admin_http.buat_token_pendaftaran()
                ),
            ),
            403,
        )
        return True
    except OSError:
        penangan._kirim(halaman_daftar(
            "Pendaftaran belum selesai. Coba kirim lagi dengan isian yang sama.",
            galat=True,
            nama=locals().get("nama", ""),
            token_form=locals().get("data", {}).get("token_form", ""),
        ), 503)
        return True
    except (ValueError, KontrakTidakSah, DomainAkunTidakSah) as galat:
        teks_galat = str(galat)
        aman = teks_galat
        status = 200
        if "alias tidak tersedia" in teks_galat:
            aman = (
                "Nama sudah dipakai. Pakai nama lain, atau masuk bila memang "
                "akunmu."
            )
        elif aman not in (
            "Nama wajib diisi.",
            "Kata sandi minimal 8 karakter.",
            "Centang persetujuan Kebijakan Privasi dulu, ya.",
            "Nama panggilan anak wajib diisi, maksimal 40 karakter.",
            "Pilih kelas sekolah 1–6 atau Kelas belum diisi.",
            "Pilihan variasi soal tidak sah. Muat ulang formulir pendaftaran.",
        ):
            aman = "Isian pendaftaran belum dapat digunakan."
            status = 400
        penangan._kirim(
            halaman_daftar(
                aman,
                galat=True,
                nama=locals().get("nama", ""),
                token_form=(
                    locals().get("data", {}).get("token_form")
                    or admin_http.buat_token_pendaftaran()
                ),
            ),
            status,
        )
        return True

    tujuan_daftar = (
        f"/anak/{akun_baru.siswa_id}?section=rencana"
        if type(akun_baru.siswa_id) is int and akun_baru.siswa_id > 0
        else "/guru"
    )
    penangan.send_response(303)
    penangan.send_header("Location", tujuan_daftar)
    penangan.send_header("Set-Cookie", penangan._set_cookie(token))
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
    return True
