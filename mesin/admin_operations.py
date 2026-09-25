"""Proyeksi operasional read-only; tanpa Docker, shell, secret atau isi chat."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

import admin_store
import ai_service
import ai_store
import admin_subscription

# Operator dapat menginjeksi bundle privat tervalidasi; tidak ada path dari HTTP.
BUNDLE_BACKUP = None


def antrean(path,*,halaman=1):
    if type(halaman) is not int or not 1 <= halaman <= 10000:
        raise ValueError('halaman tidak sah')
    with admin_store.buka_baca(path) as kon:
        sql="""SELECT 'admin' sumber,operasi_id ref,target_id akun,status,diperbarui waktu
               FROM operasi_admin WHERE status IN ('reserved','uncertain')
               UNION ALL SELECT 'layanan',l.operasi_id,COALESCE(i.akun_id,l.target_id),l.status,l.diperbarui
               FROM layanan_operasi l LEFT JOIN langganan_invoice i ON i.invoice_id=l.target_id
               WHERE l.status IN ('tertunda','perlu_diperiksa') AND (i.invoice_id IS NULL OR
                   NOT EXISTS(SELECT 1 FROM langganan_grant g WHERE g.invoice_id=i.invoice_id))
               UNION ALL SELECT 'pembayaran',i.invoice_id,i.akun_id,'perlu_diperiksa',i.dibuat
               FROM langganan_invoice i WHERE
                   EXISTS(SELECT 1 FROM langganan_receipt r WHERE r.invoice_id=i.invoice_id AND r.hasil='perlu_diperiksa')
                   OR (EXISTS(SELECT 1 FROM langganan_rekonsiliasi r WHERE r.invoice_id=i.invoice_id)
                       AND NOT EXISTS(SELECT 1 FROM langganan_grant g WHERE g.invoice_id=i.invoice_id))"""
        total=kon.execute('SELECT COUNT(*) FROM ('+sql+')').fetchone()[0]
        rows=kon.execute('SELECT * FROM ('+sql+') ORDER BY waktu,ref LIMIT 25 OFFSET ?',((halaman-1)*25,)).fetchall()
        return tuple(dict(r) for r in rows),total


def ringkasan(path_admin,*,sekarang,runtime=None,kesiapan=None):
    hasil={'admin':'Belum tersedia','pembayaran':'Belum dikonfigurasi',
           'pembayaran_config':None,'pembayaran_kesiapan':dict(kesiapan or {}),
           'backup':'Belum terverifikasi','backup_cutoff':None,'ai':(), 'ai_gagal':None}
    try:
        with admin_store.buka_baca(path_admin) as kon:
            hasil['admin']='Siap'
            hasil['pembayaran_config']=admin_subscription.guard.konfigurasi_pembayaran(kon)
    except (RuntimeError,sqlite3.Error):
        pass
    if runtime is not None:
        hasil['pembayaran']='Sandbox terkonfigurasi' if runtime.config.lingkungan == 'sandbox' else 'Terkonfigurasi'
    elif hasil['pembayaran_config'] is not None:
        tahap=hasil['pembayaran_config']['tahap']
        hasil['pembayaran']='Nonaktif' if tahap=='nonaktif' else 'Tahap '+tahap
    fitur=[]
    for kode in ('pendamping','cerita','lampiran'):
        aktif,alasan=ai_service.status_fitur(kode)
        fitur.append((kode,'Diizinkan oleh konfigurasi' if aktif else 'Tertahan: '+', '.join(alasan)))
    hasil['ai']=tuple(fitur)
    try:
        with closing(sqlite3.connect(Path(ai_service.path_store()).resolve().as_uri()+'?mode=ro',uri=True)) as c:
            c.execute('PRAGMA query_only=ON')
            hasil['ai_gagal']=c.execute("SELECT COUNT(*) FROM ledger WHERE dibuat>=? AND status IN ('gagal','tak_pasti')",(sekarang-86400,)).fetchone()[0]
    except (OSError,sqlite3.Error):
        pass
    if BUNDLE_BACKUP is not None:
        import admin_backup
        try:
            # Validator tidak memigrasikan, tidak membongkar auth ke DTO/log.
            b=admin_backup.validasi_bundle(BUNDLE_BACKUP)
            if b.cutoff > sekarang:
                raise ValueError('clock backup invalid')
            hasil['backup_cutoff']=b.cutoff
            hasil['backup']='Bundle valid; perlu rekonsiliasi sebelum restore' if b.perlu_rekonsiliasi else 'Bundle valid'
        except (OSError,ValueError,RuntimeError,sqlite3.Error):
            hasil['backup']='Bukti backup tidak valid'
    return hasil
