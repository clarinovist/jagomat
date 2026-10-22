"""Satu pintu persetujuan awal dan pengaturan; tidak memblokir anak/publik."""
import hashlib
import hmac
import json
import secrets
import sqlite3
import time

import admin_store
import auth
import policy_pages
import policy_store as store
import sensor_http

GALAT=(OSError,ValueError,RuntimeError,sqlite3.Error)


def tersedia():
    if not sensor_http.SIAP or not store.epoch_sah():
        return False
    try:
        import policy_schema
        import sensor_schema
        with admin_store.buka_baca() as kon:
            return policy_schema.validasi(kon) and sensor_schema.validasi(kon)
    except GALAT:
        return False


def pilihan(data):
    if data.get('policy_versi')!=store.VERSI or data.get('policy_epoch')!=store.EPOCH:
        raise ValueError('versi kesepakatan berubah')
    aksi=data.get('policy_aksi')
    if aksi=='semua':
        return (True,True,True)
    if aksi!='pilihan' or any(data.get('policy_'+k,'0') not in ('0','1') for k in ('alur','hasil','chat')):
        raise ValueError('pilihan tidak sah')
    hasil=tuple(data.get('policy_'+k)=='1' for k in ('alur','hasil','chat'))
    if not hasil[0] and any(hasil[1:]):
        raise ValueError('hasil/chat memerlukan sensor alur')
    return hasil


def _ikatan(p, token_sesi, operasi, revisi):
    akun=auth.cari_akun(p.pengguna)
    body=json.dumps([p.id_akun,p.revisi_auth,hashlib.sha256(token_sesi.encode()).hexdigest(),
                     store.VERSI,store.EPOCH,operasi,revisi],separators=(',',':')).encode()
    return hmac.new(bytes.fromhex(akun['kunci']),b'policy-v1:'+body,hashlib.sha256).hexdigest()


def halaman(penangan,p,*,lanjut='/guru',galat=''):
    row=store.baca(admin_store.BAWAAN,p.id_akun)
    revisi=row['revisi'] if row else 0
    operasi=secrets.token_hex(16)
    token=_ikatan(p,penangan._ambil_token(),operasi,revisi)
    pilihan_kini=tuple(bool(row[k]) for k in ('alur','hasil','chat')) if row else (False,False,False)
    if row and store.berlaku(row):
        # Izin sudah berlaku: mode tinjau/ubah. Gate (tanpa izin berlaku) tetap halaman penuh lama.
        import product_analytics_http as lama
        izin=sensor_http.izin_akun(p.id_akun)
        return policy_pages.halaman_tinjau(pengguna=p.pengguna,token=token,operasi=operasi,revisi=revisi,
            pilihan=pilihan_kini,dibuat=row['dibuat'],berakhir=izin.berakhir if izin else None,aktif=izin is not None,
            token_cabut=lama._token(p,penangan._ambil_token(),'sensor-cabut'),lanjut=lanjut,galat=galat)
    return policy_pages.halaman(token=token,
        operasi=operasi,revisi=revisi,lanjut=lanjut,galat=galat,pilihan=pilihan_kini)


def perlu(p):
    if not tersedia():
        return False
    try:
        return not store.berlaku(store.baca(admin_store.BAWAAN,p.id_akun))
    except GALAT:
        return False  # layanan inti tetap hidup; sensor tetap fail-closed


def tangani_get(penangan,jalur):
    # Gate tujuan HTML guru; tidak menyentuh anak/admin/capability/aset/publik.
    tujuan=(jalur in ('/','/guru','/persetujuan') or jalur.startswith('/anak/'))
    if not tujuan:
        return False
    p=penangan._principal()
    if p is None or p.peran!='guru' or p.metode!='cookie':
        return False
    if jalur.startswith('/anak/'):
        import database
        try:
            identitas=int(jalur.split('/')[2])
            with database.buka() as kon:
                if not penangan._bisa_lihat_siswa(kon,identitas):
                    return False
        except (ValueError,IndexError):
            return False
    if jalur!='/persetujuan' and not perlu(p):
        return False
    if not tersedia():
        return False
    try:
        penangan._kirim_privat(halaman(penangan,p,lanjut=jalur if jalur in ('/','/guru') else '/guru'))
    except GALAT:
        from support_pages import halaman_pesan
        penangan._kirim_privat(halaman_pesan('Belum tersedia','<h1>Persetujuan belum tersedia</h1><p>Layanan inti tetap dapat digunakan. Coba lagi nanti.</p>'),503)
    return True


def tangani_post(penangan,jalur):
    if jalur!='/persetujuan':
        return False
    import product_analytics_http as lama
    import admin_security
    from support_pages import halaman_pesan
    try:
        p=lama._principal(penangan)
        data=admin_security.baca_form(penangan,maksimum_field=10)
        if set(data)-{'token','lanjut','policy_versi','policy_revisi','policy_operasi','policy_aksi','policy_alur','policy_hasil','policy_chat','policy_epoch'}:
            raise ValueError('field tidak dikenal')
        if not tersedia():
            raise ValueError('persetujuan belum tersedia')
        revisi=int(data.get('policy_revisi','-1'));operasi=data.get('policy_operasi','')
        if not hmac.compare_digest(data.get('token',''),_ikatan(p,penangan._ambil_token(),operasi,revisi)):
            raise PermissionError('form tidak sah')
        store.simpan(admin_store.BAWAAN,auth.BERKAS_SANDI,p,revisi=revisi,operasi=operasi,
                     pilihan=pilihan(data),sekarang=int(time.time()),versi=data['policy_versi'])
        penangan.send_response(303)
        penangan.send_header('Location','/guru')
        penangan.send_header('Content-Length','0');penangan.end_headers()
    except LookupError:
        penangan._kirim_privat(halaman_pesan('Tidak ada','<h1>Halaman tidak ada</h1>'),404)
    except PermissionError:
        penangan._kirim_privat(halaman_pesan('Form tidak sah','<h1>Form tidak sah</h1>'),403)
    except GALAT:
        penangan._kirim_privat(halaman_pesan('Belum tersimpan','<h1>Persetujuan belum tersimpan</h1><p>Pilihan berubah atau form tidak berlaku. Buka kembali halaman persetujuan.</p>'),409)
    return True


def setelah_daftar(akun_baru,data):
    """Crash/replay tidak memulihkan consent; akun tanpa receipt masuk gate."""
    if not akun_baru.baru or not tersedia() or data.get('policy_versi')!=store.VERSI:
        return
    try:
        p=auth.PrincipalAkun(akun_baru.pengguna,akun_baru.peran,akun_baru.id_akun,akun_baru.revisi_auth)
        store.simpan(admin_store.BAWAAN,auth.BERKAS_SANDI,p,revisi=0,
                     operasi='daftar_'+secrets.token_hex(16),pilihan=pilihan(data),
                     sekarang=int(time.time()),versi=data['policy_versi'])
    except GALAT:
        # Akun sudah committed; tidak membuat akun/profil kedua atau izin palsu.
        return
