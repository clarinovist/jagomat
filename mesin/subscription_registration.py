"""Registrasi akun+profil publik; sinkron enrollment tetap opt-in.

Akun/receipt committed lebih dahulu, lalu enrollment lewat service terjaga.
Kegagalan billing bukan alasan membuat akun ulang atau menghapus receipt auth.
Recovery baseline dapat menjalankan sinkron_pendaftaran dari receipt yang sama.

Aktivasi publik: `CUTOFF_AKTIVASI` ditetapkan saat pembukaan publik. Selama None,
jalur web membuat akun+profil anak, tanpa sinkron enrollment.
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
           cutoff, sekarang, sakelar=d.SAKELAR, failpoint=None,
           nama_anak=None, kelas_sekolah=None, profil_parameter=None):
    """Default OFF sebelum membuat akun; tidak menangani login/session/consent."""
    sakelar.wajib("fondasi")
    d.waktu(cutoff)
    d.waktu(sekarang)
    if sekarang < cutoff:
        raise ValueError("pendaftaran sebelum cutoff")
    fungsi = admin_registration.daftar_publik if nama_anak is None else admin_registration.daftar_dengan_profil
    profil = {} if nama_anak is None else dict(nama_anak=nama_anak, kelas_sekolah=kelas_sekolah,
                                              profil_parameter=profil_parameter)
    akun = fungsi(path_admin, path_auth, path_db, operasi_id=operasi_id, alias=alias,
                  sandi=sandi, token_form=token_form, sekarang=sekarang, **profil)
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
               sekarang, nama_anak, kelas_sekolah, profil_parameter=None, sakelar=None):
    """Jalur /daftar: pendaftaran selalu berjalan; sinkron hanya saat aktif penuh.

    Sinkron enrollment menuntut DUA kondisi eksplisit: `CUTOFF_AKTIVASI` ditetapkan
    (keputusan pembukaan publik) dan sakelar fondasi efektif dari tahap tersimpan
    (operator). Tanpa keduanya, akun+profil tetap dibuat tanpa enrollment
    (`belum_aktif`) — registrasi tidak pernah gagal karena billing. Kegagalan
    sinkron sendiri tidak menghapus akun (`belum_terverifikasi`, pulih dari
    receipt yang sama).
    """
    if type(nama_anak) is not str or not nama_anak.strip():
        raise ValueError('Nama panggilan anak wajib diisi, maksimal 40 karakter.')
    aktif = CUTOFF_AKTIVASI is not None
    if aktif:
        if sakelar is None:
            import admin_subscription
            sakelar = admin_subscription.sakelar_runtime(path_admin)
        if sakelar.fondasi:
            return daftar(path_admin, path_auth, path_db, operasi_id=operasi_id,
                          alias=alias, sandi=sandi, token_form=token_form,
                          cutoff=CUTOFF_AKTIVASI, sekarang=sekarang, sakelar=sakelar,
                          nama_anak=nama_anak, kelas_sekolah=kelas_sekolah,
                          profil_parameter=profil_parameter)
    akun = admin_registration.daftar_dengan_profil(
        path_admin, path_auth, path_db, operasi_id=operasi_id, alias=alias,
        sandi=sandi, token_form=token_form, sekarang=sekarang, nama_anak=nama_anak,
        kelas_sekolah=kelas_sekolah, profil_parameter=profil_parameter)
    return HasilPendaftaran(akun, "belum_aktif")
