"""Otorisasi dan jurnal operasi layanan; tidak menyamar sebagai akun keluarga."""

from contextlib import contextmanager
import hashlib
import json

import admin_accounts
import admin_store
import auth
import sessions
from json_storage import transaksi_json


def principal_hidup(daftar, principal, peran='admin'):
    if not isinstance(principal, (auth.PrincipalAkun, sessions.Principal)) or principal.peran != peran:
        raise LookupError('resource tidak ditemukan')
    cocok = [a for a in daftar if a.get('id_akun') == principal.id_akun]
    if (len(cocok) != 1 or cocok[0].get('peran') != peran
            or cocok[0]['pengguna'] != principal.pengguna
            or auth.revisi_auth(cocok[0]) != principal.revisi_auth):
        raise LookupError('resource tidak ditemukan')
    return cocok[0]


@contextmanager
def kunci_principal(path_auth, principal, peran='admin'):
    """Lock existing JSON; tidak menulis akun atau mengubah receipt autentikasi."""
    with transaksi_json(path_auth) as path:
        _, daftar, _ = admin_accounts._baca_state_terkunci(path)
        yield principal_hidup(daftar, principal, peran), daftar


def sidik(isi):
    return hashlib.sha256(json.dumps(isi, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def reservasi(kon, principal, operasi, aksi, target, isi, kini):
    from subscription import identitas
    identitas(operasi, 'operasi')
    jejak = sidik(isi)
    lama = kon.execute('SELECT * FROM layanan_operasi WHERE operasi_id=?', (operasi,)).fetchone()
    if lama:
        if (lama['actor_id'],lama['actor_revisi'],lama['aksi'],lama['target_id'],lama['sidik']) != (
                principal.id_akun,principal.revisi_auth,aksi,target,jejak):
            raise admin_store.KonflikOperasi('operasi layanan berbeda')
        return dict(lama)
    kon.execute("INSERT INTO layanan_operasi VALUES(?,?,?,?,?,?,'tertunda','',?,?)",
                (operasi,principal.id_akun,principal.revisi_auth,aksi,target,jejak,kini,kini))
    return None


TAHAP_PEMBAYARAN = ('nonaktif', 'rekonsiliasi', 'checkout', 'penegakan')


def konfigurasi_pembayaran(kon):
    row = kon.execute('SELECT tahap,revisi,diperbarui,actor_id FROM pembayaran_konfigurasi WHERE id=1').fetchone()
    if row is None or row['tahap'] not in TAHAP_PEMBAYARAN:
        raise admin_store.StoreBelumSiap('konfigurasi pembayaran tidak tersedia')
    return dict(row)


def sakelar_pembayaran(kon):
    """Fail-closed: state Admin hanya menjadi injeksi eksplisit, global tetap OFF."""
    import subscription as d
    tahap = konfigurasi_pembayaran(kon)['tahap']
    tingkat = TAHAP_PEMBAYARAN.index(tahap)
    return d.Sakelar(fondasi=tingkat >= 1, buat_pembayaran=tingkat >= 2,
                     rekonsiliasi=tingkat >= 1, penegakan=tingkat >= 3)


def atur_pembayaran(path, path_auth, principal, *, operasi, tahap, revisi,
                     kesiapan, sekarang):
    principal_hidup(auth.muat_akun(path_auth), principal)
    if tahap not in TAHAP_PEMBAYARAN or type(revisi) is not int or revisi < 1:
        raise ValueError('tahap pembayaran tidak sah')
    if (type(kesiapan) is not dict or set(kesiapan) != {
            'provider_produksi', 'callback', 'recovery', 'kebijakan'}
            or any(type(v) is not bool for v in kesiapan.values())):
        raise ValueError('kesiapan pembayaran tidak sah')
    with kunci_principal(path_auth, principal):
        with admin_store._transaksi(path) as kon:
            lama = konfigurasi_pembayaran(kon)
            jejak = kon.execute('SELECT * FROM layanan_operasi WHERE operasi_id=?', (operasi,)).fetchone()
            if jejak:
                if (jejak['actor_id'], jejak['actor_revisi'], jejak['aksi'], jejak['target_id'], jejak['sidik']) != (
                        principal.id_akun, principal.revisi_auth, 'atur_pembayaran', 'pembayaran',
                        sidik([tahap, revisi])):
                    raise admin_store.KonflikOperasi('operasi layanan berbeda')
                if jejak['status'] != 'tertunda':
                    return konfigurasi_pembayaran(kon)
            if revisi != lama['revisi']:
                raise admin_store.KonflikOperasi('revisi pembayaran berubah')
            awal = TAHAP_PEMBAYARAN.index(lama['tahap'])
            tujuan = TAHAP_PEMBAYARAN.index(tahap)
            if tujuan > awal + 1:
                raise ValueError('tahap pembayaran harus berurutan')
            # Gate readiness berlaku saat menaikkan kemampuan. Penurunan insiden
            # harus tetap mungkin walau provider/callback sedang tidak sehat.
            if tujuan > awal:
                if tujuan > 0 and not kesiapan['provider_produksi']:
                    raise ValueError('provider produksi belum siap')
                if tujuan > 1 and not (kesiapan['callback'] and kesiapan['recovery']):
                    raise ValueError('callback/recovery belum siap')
                if tujuan > 2 and not kesiapan['kebijakan']:
                    raise ValueError('kebijakan pembayaran belum siap')
            if jejak is None:
                reservasi(kon, principal, operasi, 'atur_pembayaran', 'pembayaran',
                          [tahap, revisi], sekarang)
            if tahap == lama['tahap']:
                selesaikan(kon, operasi, tahap, sekarang)
                return lama
            baru = revisi + 1
            kursor = kon.execute('UPDATE pembayaran_konfigurasi SET tahap=?,revisi=?,diperbarui=?,actor_id=? WHERE id=1 AND revisi=?',
                                 (tahap, baru, sekarang, principal.id_akun, revisi))
            if kursor.rowcount != 1:
                raise admin_store.KonflikOperasi('revisi pembayaran berubah')
            kon.execute('INSERT INTO pembayaran_audit VALUES(?,?,?,?,?,?,?)',
                        (operasi, principal.id_akun, principal.revisi_auth,
                         lama['tahap'], tahap, baru, sekarang))
            selesaikan(kon, operasi, tahap, sekarang)
            return konfigurasi_pembayaran(kon)


def selesaikan(kon, operasi, hasil, kini):
    status = 'perlu_diperiksa' if hasil in ('perlu_diperiksa','belum_terverifikasi') else 'selesai'
    kon.execute('UPDATE layanan_operasi SET status=?,hasil=?,diperbarui=? WHERE operasi_id=?',
                (status,hasil,kini,operasi))


def aktifkan_transisi(path, path_auth, principal, *, operasi, akun_id, target_revisi,
                      sekarang, sakelar=None):
    """Aktivasi transisi akun lama: enrollment eksplisit + provenance di ledger.

    Hanya akun guru tanpa enrollment; idempoten lewat `sumber_id=operasi` pada
    baris enrollment (unik per akun), sehingga replay/dua tab tidak menggandakan.
    Tanpa efek pembayaran. Sakelar efektif dari tahap tersimpan (fondasi wajib;
    readiness provider tidak relevan — operasi ini tidak memanggil jaringan).

    Jurnal `layanan_operasi` sengaja TIDAK dipakai: CHECK `aksi` di schema
    admin-control terikat kontrak pair rilis (tidak boleh berubah tanpa re-pin
    recovery). Bukti operasi = baris `langganan_enrollment` (asal 'transisi',
    sumber_id=operasi) yang tampil di panel Langganan.
    """
    import subscription as d
    import subscription_store as store
    d.identitas(operasi, 'operasi')
    d.identitas(akun_id, 'akun')
    d.waktu(sekarang)
    # Revisi akun legacy = 0 (auth.revisi_auth mendokumentasikan itu); hanya
    # nilai negatif/non-int yang tidak sah.
    if type(target_revisi) is not int or target_revisi < 0:
        raise ValueError('revisi target tidak sah')
    with kunci_principal(path_auth, principal) as (_, daftar):
        target = next((a for a in daftar if a.get('id_akun') == akun_id), None)
        if (target is None or target.get('peran') != 'guru'
                or auth.revisi_auth(target) != target_revisi):
            raise LookupError('resource tidak ditemukan')
        with admin_store.buka_baca(path) as kon:
            sakelar_efektif = sakelar if sakelar is not None else sakelar_pembayaran(kon)
            lama = kon.execute('SELECT sumber_id FROM langganan_enrollment WHERE akun_id=?',
                               (akun_id,)).fetchone()
        if lama is None:
            sakelar_efektif.wajib('fondasi')
            try:
                store.enroll(path, akun_id, sumber_id=operasi, asal='transisi',
                             mulai=sekarang, peran='guru', promo_lama=False,
                             sakelar=sakelar_efektif)
            except store.KonflikLangganan:
                # Balapan operator lain: menangkan observasi ulang, bukan tulis ganda.
                with admin_store.buka_baca(path) as kon:
                    ulang = kon.execute('SELECT sumber_id FROM langganan_enrollment WHERE akun_id=?',
                                        (akun_id,)).fetchone()
                if ulang is None:
                    raise
                return 'diaktifkan' if ulang['sumber_id'] == operasi else 'sudah_terdaftar'
            return 'diaktifkan'
        return 'diaktifkan' if lama['sumber_id'] == operasi else 'sudah_terdaftar'
