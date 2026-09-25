"""Rute layanan admin menggunakan palang principal/form existing."""

import sqlite3
import time
import urllib.parse

import admin_http as h
import admin_security
import admin_store
import auth
import database
import sessions
import admin_subscription as billing
import admin_operations
import admin_launch_pages as ui
import admin_launch_service as guard
import product_analytics as d
import product_analytics_store as kpi

SECTION = {'langganan','perhatian','operasional','kpi'}
JUDUL = {'langganan':'Langganan','perhatian':'Perlu ditangani','operasional':'Status operasional','kpi':'KPI Uji Coba'}


def _form(penangan,p,aksi,meta):
    akun=h._akun_principal(p)
    token_sesi=h._wajib_cookie(penangan,p)
    return h._csrf(akun,token_sesi),admin_security.buat_tinjauan(akun,token_sesi,aksi,meta)


def _kirim(penangan,p,section,isi):
    if h._principal_admin(penangan) != p:
        return h._tidak_ada(penangan)
    h._kirim_privat(penangan,h._halaman_admin(p,section,isi,skrip=True,judul=JUDUL[section],subjudul=''),skrip=True)


def get(penangan,p,q):
    section=q['section']; kini=int(time.time()); csrf=''
    runtime = billing.runtime_penangan(penangan)
    if p.metode=='cookie': csrf=h._csrf(h._akun_principal(p),h._wajib_cookie(penangan,p))
    if section=='langganan':
        if q.get('id'):
            r=billing.detail(h._path_admin(),auth.BERKAS_SANDI,p,q['id'],sekarang=kini)
            forms={}
            target=next((a for a in auth.muat_akun() if a.get('id_akun')==q['id'] and a.get('peran')=='guru'),None)
            if p.metode=='cookie' and target and runtime:
                for inv in r['invoices']:
                    if inv['dapat_periksa']:
                        meta=dict(akun=q['id'],invoice=inv['invoice_id'],revisi=auth.revisi_auth(target))
                        c,t=_form(penangan,p,'periksa_pembayaran',meta)
                        forms[inv['invoice_id']]=ui.formulir('periksa',c,t,'<p>Query order yang sama; tidak membuat pembayaran baru.</p>','Periksa pembayaran')
            isi=ui.detail_langganan(r,forms)
        else:
            halaman=h._angka(q.get('halaman'),1)
            rows,total=billing.daftar(h._path_admin(),auth.BERKAS_SANDI,p,halaman=halaman)
            isi=ui.daftar_langganan(rows,total,halaman=halaman,cari='',csrf=csrf)
    elif section=='perhatian':
        rows,total=admin_operations.antrean(h._path_admin(),halaman=h._angka(q.get('halaman'),1))
        isi=ui.antrean(rows,total,halaman=h._angka(q.get('halaman'),1))
    elif section=='operasional':
        kesiapan=billing.kesiapan_penangan(penangan)
        ringkas=admin_operations.ringkasan(h._path_admin(),sekarang=kini,runtime=runtime,
                                           kesiapan=kesiapan)
        form=''
        config=ringkas['pembayaran_config']
        if p.metode=='cookie' and config:
            c,t=_form(penangan,p,'atur_pembayaran',{'revisi':config['revisi'],'tahap':config['tahap']})
            opsi=''.join('<option value="%s"%s>%s</option>'%(nilai,' selected' if nilai==config['tahap'] else '',label) for nilai,label in (
                ('nonaktif','Nonaktif'),('rekonsiliasi','Rekonsiliasi'),('checkout','Checkout'),('penegakan','Penegakan')))
            fields='<p><strong>Aturan perubahan:</strong> kenaikan hanya satu tahap. Penurunan dapat langsung dipakai saat insiden; pilih Rekonsiliasi agar transaksi berjalan tetap bisa diperiksa.</p><label>Tahap tujuan<select name="tahap">%s</select></label><label><input type="checkbox" name="konfirmasi" value="1" required> Saya sudah meninjau tahap saat ini, tahap tujuan, prasyarat, dan dampaknya pada pembayaran baru serta transaksi berjalan.</label>'%opsi
            form=ui.formulir('pembayaran',c,t,fields,'Terapkan perubahan tahap')
        isi=ui.operasional(ringkas,form)
    else:
        bulan=q.get('bulan',d.hari_wib(kini)[:7])
        import re
        if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',bulan): raise ValueError('bulan tidak sah')
        config,r,biaya,cakupan=kpi.laporan(h._path_admin(),sekarang=kini,bulan=bulan)
        cakupan['pendaftaran'] = kpi.pendaftaran_total(auth.BERKAS_SANDI,config['mulai'],min(config['akhir'],kini+1)) if config else None
        fb=fc=''
        if p.metode=='cookie':
            c,t=_form(penangan,p,'biaya',{'bulan':bulan,'revisi':biaya['revisi'] if biaya else 0})
            fields=''.join('<label>%s (rupiah)<input name="%s" type="number" min="0" max="1000000000" value="%d" required></label>'%(label,k,biaya[k] if biaya else 475000 if k=='anggaran' else 0) for k,label in [('anggaran','Anggaran'),('server','Server'),('domain','Domain, alokasi bulanan'),('ai','AI, realisasi'),('pendukung','Pendukung')])
            fields+='<label><input type="checkbox" name="lengkap" value="1"%s> Seluruh biaya periode ini sudah dicatat</label><p>Angka awal anggaran bukan realisasi. Jangan menjumlahkan estimasi AI dengan tagihan yang sama.</p>'%(' checked' if biaya and biaya['lengkap'] else '')
            fb=ui.formulir('biaya',c,t,fields,'Simpan biaya')
            c,t=_form(penangan,p,'eksperimen',{'revisi':config['revisi'] if config else 0})
            fields='<p>Aktivasi koleksi ditahan sampai audit privasi, seluruh jalur pencatatan, dan recovery diselesaikan. Mulai eksperimen sekarang setelah pemberitahuan dan persetujuan opsional siap. Tidak ada backfill atau enrollment otomatis.</p><label><input type="checkbox" name="aktif" value="1"%s> Aktifkan koleksi yang disetujui keluarga</label><label><input type="checkbox" name="konfirmasi" value="1" required> Pemberitahuan, alur pencabutan, dan kesiapan pencatatan telah diperiksa</label>'%(' checked' if config and config['koleksi'] else '')
            fc=ui.formulir('eksperimen',c,t,fields,'Simpan pengaturan eksperimen')
        isi=ui.halaman_kpi(config,r,biaya,cakupan,bulan=bulan,form_biaya=fb,form_config=fc)
    return _kirim(penangan,p,section,isi)


def tangani_post(penangan,jalur):
    if jalur not in ('/admin/layanan/cari','/admin/layanan/periksa','/admin/layanan/pembayaran','/admin/layanan/biaya','/admin/layanan/eksperimen'):
        return False
    p=h._principal_admin(penangan)
    if p is None:
        h._tidak_ada(penangan);return True
    try:
        h._wajib_cookie(penangan,p)
        data=admin_security.baca_form(penangan,maksimum_field=16)
        if jalur.endswith('/cari'):
            h._cek_csrf(h._akun_principal(p),h._wajib_cookie(penangan,p),data.pop('csrf',None))
            cari=data.pop('cari','')
            if data: raise ValueError('isian asing')
            rows,total=billing.daftar(h._path_admin(),auth.BERKAS_SANDI,p,cari=cari)
            csrf=h._csrf(h._akun_principal(p),h._wajib_cookie(penangan,p))
            _kirim(penangan,p,'langganan',ui.daftar_langganan(rows,total,halaman=1,cari=cari,csrf=csrf))
            return True
        aksi={'periksa':'periksa_pembayaran','pembayaran':'atur_pembayaran','biaya':'biaya','eksperimen':'eksperimen'}[jalur.rsplit('/',1)[-1]]
        akun,tinjauan,token=h._token_final(penangan,p,data,aksi)
        meta=tinjauan['data']; operasi=tinjauan['op']; kini=int(time.time())
        if aksi=='periksa_pembayaran':
            if data: raise ValueError('isian asing')
            tok=penangan._ambil_token()
            def hidup():
                current=sessions.ambil_principal(tok,path=sessions.BERKAS_SESI,path_akun=auth.BERKAS_SANDI)
                return current is not None and current.id_akun==p.id_akun and current.revisi_auth==p.revisi_auth
            hasil = billing.periksa(h._path_admin(),auth.BERKAS_SANDI,database.BAWAAN,p,
                            akun_id=meta['akun'],invoice_id=meta['invoice'],target_revisi=meta['revisi'],
                            operasi=operasi,sekarang=kini,periksa_sesi=hidup,
                            runtime=billing.runtime_penangan(penangan),jam=time.time)
            h._redirect(penangan,'/admin?section=langganan&id='+meta['akun'])
        elif aksi=='atur_pembayaran':
            if set(data)-{'tahap','konfirmasi'} or data.get('konfirmasi')!='1':
                raise ValueError('konfirmasi pembayaran tidak sah')
            if meta.get('tahap') not in guard.TAHAP_PEMBAYARAN:
                raise ValueError('snapshot pembayaran tidak sah')
            guard.atur_pembayaran(h._path_admin(),auth.BERKAS_SANDI,p,
                operasi=operasi,tahap=data.get('tahap',''),revisi=meta['revisi'],
                kesiapan=billing.kesiapan_penangan(penangan),sekarang=kini)
            h._redirect(penangan,'/admin?section=operasional')
        elif aksi=='biaya':
            if set(data)-{'anggaran','server','domain','ai','pendukung','lengkap'}: raise ValueError('isian asing')
            lengkap=data.pop('lengkap','0')
            if lengkap not in ('0','1'): raise ValueError('kelengkapan tidak sah')
            nilai={k:int(data[k]) for k in ('anggaran','server','domain','ai','pendukung')}
            nilai['lengkap']=lengkap=='1'
            kpi.simpan_biaya(h._path_admin(),auth.BERKAS_SANDI,p,operasi=operasi,bulan=meta['bulan'],revisi=meta['revisi'],nilai=nilai,sekarang=kini)
            h._redirect(penangan,'/admin?section=kpi&bulan='+meta['bulan'])
        else:
            if set(data)-{'aktif','konfirmasi'} or data.get('konfirmasi')!='1' or data.get('aktif','0') not in ('0','1'):
                raise ValueError('konfirmasi tidak sah')
            import product_analytics_http
            if data.get('aktif') == '1' and not product_analytics_http.KOLEKSI_SIAP:
                raise RuntimeError('koleksi belum lolos gate aktivasi')
            config=kpi.baca_config(h._path_admin())
            kpi.atur_eksperimen(h._path_admin(),auth.BERKAS_SANDI,p,operasi=operasi,
                                mulai=config['mulai'] if config else kini,aktif=data.get('aktif')=='1',
                                revisi=meta['revisi'],sekarang=kini)
            h._redirect(penangan,'/admin?section=kpi')
    except LookupError:
        h._tidak_ada(penangan)
    except PermissionError:
        h._galat(penangan,403,'Form atau autentikasi ulang tidak sah.')
    except admin_store.KonflikOperasi:
        h._galat(penangan,409,'Data berubah. Periksa hasil sebelum mencoba lagi.')
    except (ValueError,KeyError,TypeError):
        h._galat(penangan,400,'Isian layanan tidak sah.')
    except (RuntimeError,sqlite3.Error,OSError):
        h._galat(penangan,503,'Layanan belum tersedia; jangan membuat transaksi pengganti.')
    return True
