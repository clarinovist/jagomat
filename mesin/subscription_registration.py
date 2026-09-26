"""Wrapper registrasi terisolasi; belum dipakai web atau mengubah akun nyata.

Akun/receipt committed lebih dahulu, lalu enrollment lewat service terjaga.
Kegagalan billing bukan alasan membuat akun ulang atau menghapus receipt auth.
Recovery baseline dapat menjalankan sinkron_pendaftaran dari receipt yang sama.

Aktivasi publik: `CUTOFF_AKTIVASI` ditetapkan saat pembukaan publik. Selama None,
jalur web berperilaku seperti sebelumnya (akun dibuat, tanpa sinkron enrollment).
"""

from dataclasses import dataclass, field

import admin_registration
import auth
import subscription as d
import subscription_service as layanan


# Ambang aktivasi sinkron enrollment publik (epoch detik; receipt `dibuat` <
# cutoff tidak diikutkan). None = belum diaktifkan. Perubahan nilai ini adalah
# keputusan pembukaan publik dan diuji sebagai perilaku eksplisit.
CUTOFF_AKTIVASI = None


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


def daftar_web(path_admin, path_auth, path_db, *, operasi_id, alias, sandi, token_form,
               sekarang, sakelar=None):
    """Jalur /daftar: pendaftaran selalu berjalan; sinkron hanya saat aktif penuh.

    Sinkron enrollment menuntut DUA kondisi eksplisit: `CUTOFF_AKTIVASI` ditetapkan
    (keputusan pembukaan publik) dan sakelar fondasi efektif dari tahap tersimpan
    (operator). Tanpa keduanya, akun tetap dibuat lewat jalur lama tanpa enrollment
    (`belum_aktif`) — registrasi tidak pernah gagal karena billing. Kegagalan
    sinkron sendiri tidak menghapus akun (`belum_terverifikasi`, pulih dari
    receipt yang sama).
    """
    aktif = CUTOFF_AKTIVASI is not None
    if aktif:
        if sakelar is None:
            import admin_subscription
            sakelar = admin_subscription.sakelar_runtime(path_admin)
        if sakelar.fondasi:
            return daftar(path_admin, path_auth, path_db, operasi_id=operasi_id,
                          alias=alias, sandi=sandi, token_form=token_form,
                          cutoff=CUTOFF_AKTIVASI, sekarang=sekarang, sakelar=sakelar)
    akun = admin_registration.daftar_publik(
        path_admin, path_auth, path_db, operasi_id=operasi_id, alias=alias,
        sandi=sandi, token_form=token_form, sekarang=sekarang)
    return HasilPendaftaran(akun, "belum_aktif")
