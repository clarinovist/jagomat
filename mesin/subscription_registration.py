"""Wrapper registrasi terisolasi; belum dipakai web atau mengubah akun nyata.

Akun/receipt committed lebih dahulu, lalu enrollment lewat service terjaga.
Kegagalan billing bukan alasan membuat akun ulang atau menghapus receipt auth.
Recovery baseline dapat menjalankan sinkron_pendaftaran dari receipt yang sama.
"""

from dataclasses import dataclass, field

import admin_registration
import auth
import subscription as d
import subscription_service as layanan


@dataclass(frozen=True)
class HasilPendaftaran:
    akun: admin_registration.AkunBaru = field(repr=False)
    status_langganan: str


def daftar(path_admin, path_auth, path_db, *, operasi_id, alias, sandi, token_form,
           cutoff, sekarang, sakelar=d.SAKELAR, failpoint=None):
    """Default OFF sebelum membuat akun; tidak menangani login/session/consent."""
    sakelar.wajib("fondasi")
    d.waktu(cutoff)
    d.waktu(sekarang)
    if sekarang < cutoff:
        raise ValueError("pendaftaran sebelum cutoff")
    akun = admin_registration.daftar_publik(
        path_admin, path_auth, path_db, operasi_id=operasi_id, alias=alias,
        sandi=sandi, token_form=token_form, sekarang=sekarang)
    if failpoint == "setelah_auth":
        raise layanan.SinkronBelumSelesai("akun committed; sinkron receipt yang sama")
    principal = auth.PrincipalAkun(akun.pengguna, akun.peran, akun.id_akun, akun.revisi_auth)
    try:
        layanan.sinkron_pendaftaran(path_admin, path_auth, path_db, principal,
                                   sumber_id=operasi_id, cutoff=cutoff,
                                   sekarang=sekarang, sakelar=sakelar)
    except (RuntimeError, ValueError, LookupError, OSError):
        # Tidak mengklaim enrollment berhasil; sumber auth tetap untuk recovery.
        return HasilPendaftaran(akun, "belum_terverifikasi")
    return HasilPendaftaran(akun, "tersinkron")
