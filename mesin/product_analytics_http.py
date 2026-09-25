"""Consent dan adapter aktivitas; tidak ada endpoint event publik."""

import base64
import hashlib
import hmac
import html
import json
import sqlite3
import os
import time

import admin_security
import admin_store
import auth
import database
from contextlib import closing
from pathlib import Path
import sessions
import product_analytics as d
import product_analytics_store as store
import admin_launch_service as guard
from support_pages import halaman_pesan

# Deployment dan pengaturan admin sama-sama wajib ON. Default tidak mengoleksi.
KOLEKSI_SIAP = os.environ.get('KPI_KOLEKSI_SIAP', '0') == '1'


def aktif():
    if not KOLEKSI_SIAP:
        return False
    try:
        c=store.baca_config(admin_store.BAWAAN)
        return bool(c and c['koleksi'] and c['boot_id'] == store.BOOT_ID)
    except (OSError,RuntimeError,sqlite3.Error):
        _gagal()
        return False


def _principal(penangan):
    p=penangan._principal()
    if p is None or p.metode!='cookie' or p.peran!='guru':
        raise LookupError('resource tidak ditemukan')
    guard.principal_hidup(auth.muat_akun(),p,'guru')
    return p


def _token(p,session,aksi):
    a=auth.cari_akun(p.pengguna)
    body=json.dumps([p.id_akun,p.revisi_auth,hashlib.sha256(session.encode()).hexdigest(),aksi,int(time.time())+900],separators=(',',':')).encode()
    mac=hmac.new(bytes.fromhex(a['kunci']),b'kpi-form-v1:'+body,hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body).decode()+'.'+mac.hex()


def _cek(p,session,aksi,token):
    try:
        encoded,signature=token.split('.')
        body=base64.b64decode(encoded,altchars=b'-_',validate=True)
        nilai=json.loads(body)
        a=auth.cari_akun(p.pengguna)
        mac=hmac.new(bytes.fromhex(a['kunci']),b'kpi-form-v1:'+body,hashlib.sha256).hexdigest()
        if (not hmac.compare_digest(signature,mac) or nilai[:4]!=[p.id_akun,p.revisi_auth,hashlib.sha256(session.encode()).hexdigest(),aksi]
                or type(nilai[4]) is not int or int(time.time())>=nilai[4]):
            raise ValueError()
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):
        raise PermissionError('form analitik tidak sah') from None


def form_daftar():
    if not aktif(): return ''
    return ('<fieldset><legend>Analitik opsional</legend><label><input type="checkbox" name="analitik" value="1"> '
            'Saya setuju ringkasan aktivitas latihan keluarga dipakai untuk evaluasi Jagomat. '
            'Tanpa jawaban, nilai, foto, atau chat. Menolak tidak mengurangi akses; dapat dicabut di Akun. '
            'Data terkait akun maksimal 90 hari sejak daftar; agregat kelompok tanpa mapping maksimal 12 bulan setelah rekrutmen. '
            'Setelah restart/pemulihan, aktivitas memerlukan persetujuan ulang.</label><label>Mengetahui Jagomat dari '
            '<select name="sumber_analitik">'+''.join('<option value="%s">%s</option>'%(v,l) for v,l in [('tidak_diketahui','Tidak ingin menjawab'),('rekomendasi','Rekomendasi pengguna'),('pencarian','Pencarian noniklan'),('komunitas','Komunitas'),('iklan','Iklan'),('lainnya','Lainnya')])+'</select></label></fieldset>')


def setelah_daftar(p,*,setuju,sumber):
    if not aktif() or not setuju: return
    try:
        store.setuju(admin_store.BAWAAN,auth.BERKAS_SANDI,p,sumber=sumber,sekarang=int(time.time()),saat_daftar=True)
    except (LookupError,ValueError,RuntimeError,OSError,sqlite3.Error):
        _gagal()


def _gagal():
    # Hanya kategori, tanpa nama/ID/token; kegagalan sink tidak membuat green palsu.
    print('kpi_pencatatan_gagal')
    try: store.gangguan(admin_store.BAWAAN)
    except (OSError,RuntimeError,sqlite3.Error): pass


def aktivitas_sesi(sesi_id,kode,*,pengguna=None,peran=None,baru=True):
    if not aktif() or not baru or peran=='admin': return
    try:
        with closing(sqlite3.connect(Path(database.BAWAAN).resolve().as_uri()+'?mode=ro',uri=True,timeout=.05)) as c:
            c.execute('PRAGMA query_only=ON')
            r=c.execute('SELECT s.pemilik FROM sesi x JOIN siswa s ON s.id=x.siswa_id WHERE x.id=?',(sesi_id,)).fetchone()
        if not r or (peran=='guru' and pengguna!=r[0]): return
        akun=auth.cari_akun(r[0])
        if akun is None or akun.get('peran')!='guru': return
        p=auth.PrincipalAkun(akun['pengguna'],'guru',akun['id_akun'],auth.revisi_auth(akun))
        with guard.kunci_principal(auth.BERKAS_SANDI,p,'guru'):
            store.catat(admin_store.BAWAAN,p.id_akun,kode=kode,sekarang=int(time.time()))
    except (OSError,ValueError,LookupError,RuntimeError,sqlite3.Error):
        _gagal()


def kirim_dan_catat(penangan, isi, sesi_id, kode, *, pengguna, peran, privat=False):
    """Kegagalan pengiriman HTML tidak dihitung sebagai tampilan berhasil."""
    kirim = penangan._kirim_privat if privat else penangan._kirim
    kirim(isi)
    aktivitas_sesi(sesi_id,kode,pengguna=pengguna,peran=peran)


def form_akun(penangan):
    p=_principal(penangan)
    r=store.status_peserta(admin_store.BAWAAN,auth.BERKAS_SANDI,p)
    if not r and not aktif():
        return ''
    if not r or r['consent_boot'] != store.BOOT_ID:
        token = _token(p,penangan._ambil_token(),'setuju')
        return ('<section class="kartu"><h2>Analitik opsional</h2><p>Analitik tidak aktif untuk akun ini. '
                'Persetujuan ulang diperlukan setelah layanan dimulai ulang atau dipulihkan. '
                'Ringkasan aktivitas keluarga tanpa jawaban, nilai, foto, atau chat; detail maksimal 90 hari sejak pendaftaran. '
                'Agregat kelompok tanpa mapping maksimal 12 bulan setelah rekrutmen. Menolak tidak mengurangi akses.</p>'
                '<form method="post" action="/analitik/setuju"><input type="hidden" name="token" value="'+html.escape(token)+'">'
                '<label><input type="checkbox" name="konfirmasi" value="1" required> Saya setuju pemrosesan analitik opsional</label>'
                '<button type="submit">Setujui analitik</button></form>'
                + ('<p>Data lama tidak dipakai sampai persetujuan diperiksa. Anda juga dapat mencabutnya.</p>'
                   '<form method="post" action="/analitik/cabut"><input type="hidden" name="token" value="'+html.escape(_token(p,penangan._ambil_token(),'cabut'))+'">'
                   '<label><input type="checkbox" name="konfirmasi" value="1" required> Hapus data analitik terkait akun ini</label>'
                   '<button type="submit">Cabut persetujuan dan hapus analitik</button></form>' if r else '')+'</section>')
    token=_token(p,penangan._ambil_token(),'cabut')
    return ('<section class="admin-kartu"><h2>Analitik opsional</h2><p>Ikut evaluasi Jagomat. '
            'Cabut menghapus mapping, aktivitas, dan survei analitik aktif; data belajar/langganan tidak berubah.</p>'
            '<form method="post" action="/analitik/cabut"><input type="hidden" name="token" value="'+html.escape(token)+'">'
            '<label><input type="checkbox" name="konfirmasi" value="1" required> Hapus data analitik terkait akun ini</label>'
            '<button type="submit">Cabut persetujuan dan hapus analitik</button></form></section>')


def form_survei(penangan):
    if not aktif():return ''
    try:
        p=_principal(penangan)
        if not store.survei(admin_store.BAWAAN,auth.BERKAS_SANDI,p,sekarang=int(time.time())):return ''
        token=_token(p,penangan._ambil_token(),'survei')
        return '<section class="admin-kartu"><h2>Apakah Anda lebih tahu cara mendampingi anak?</h2><p>Opsional.</p><form method="post" action="/analitik/survei"><input type="hidden" name="token" value="'+html.escape(token)+'">'+''.join('<button name="jawaban" value="%s">%s</button>'%(v,l) for v,l in [('ya','Ya'),('sebagian','Sebagian'),('belum','Belum')])+'</form></section>'
    except (LookupError,ValueError,RuntimeError,OSError,sqlite3.Error):
        _gagal();return ''


def tangani_post(penangan,jalur):
    if jalur not in ('/analitik/cabut','/analitik/survei','/analitik/setuju'): return False
    try:
        p=_principal(penangan)
        data=admin_security.baca_form(penangan,maksimum_field=3)
        aksi=jalur.rsplit('/',1)[-1]
        _cek(p,penangan._ambil_token(),aksi,data.pop('token',''))
        if aksi=='cabut':
            if data!={'konfirmasi':'1'}: raise ValueError('konfirmasi wajib')
            store.cabut(admin_store.BAWAAN,auth.BERKAS_SANDI,p)
        elif aksi == 'setuju':
            if not aktif() or data != {'konfirmasi':'1'}:
                raise ValueError('persetujuan tidak tersedia')
            store.setuju(admin_store.BAWAAN,auth.BERKAS_SANDI,p,sumber='tidak_diketahui',sekarang=int(time.time()))
        else:
            if not aktif() or set(data)!={'jawaban'}:raise ValueError('survei tidak tersedia')
            if not store.survei(admin_store.BAWAAN,auth.BERKAS_SANDI,p,sekarang=int(time.time()),jawaban=data['jawaban']):
                raise ValueError('survei tidak tersedia')
        penangan.send_response(303)
        penangan.send_header('Location','/akun?section=akun' if aksi in ('cabut','setuju') else '/guru')
        penangan.send_header('Cache-Control','no-store')
        penangan.send_header('Content-Length','0');penangan.end_headers()
    except LookupError:
        penangan._kirim_privat(halaman_pesan('Tidak ada','<h1>Halaman tidak ada</h1>'),404)
    except PermissionError:
        penangan._kirim_privat(halaman_pesan('Form tidak sah','<h1>Form tidak sah</h1>'),403)
    except (ValueError,RuntimeError,OSError,sqlite3.Error):
        penangan._kirim_privat(halaman_pesan('Belum tersimpan','<h1>Belum tersimpan</h1>'),400)
    return True
