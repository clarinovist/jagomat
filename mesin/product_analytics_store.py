"""Analitik privat opt-in di admin DB; tidak menyalin data belajar atau kontak."""

import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import admin_store
import admin_launch_service as guard
import product_analytics as d
from json_storage import baca_json_ketat

BOOT_ID = secrets.token_hex(16)
PENCATATAN_GAGAL = False


@contextmanager
def _transaksi(path):
    """Analitik tidak menunggu writer lain lebih dari 50 ms di request belajar."""
    kon = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=rw', uri=True, timeout=.05)
    kon.row_factory = sqlite3.Row
    try:
        kon.execute('PRAGMA foreign_keys=ON')
        admin_store._validasi_skema(kon)
        kon.execute('BEGIN IMMEDIATE')
        yield kon
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()


def _eksperimen(kon):
    row = kon.execute('SELECT * FROM kpi_eksperimen ORDER BY mulai DESC LIMIT 1').fetchone()
    return dict(row) if row else None


def baca_config(path):
    with admin_store.buka_baca(path) as kon:
        return _eksperimen(kon)


def pendaftaran_total(path_auth, mulai, akhir):
    """Jumlah receipt publik; tidak mengumpulkan aktivitas nonpeserta."""
    import admin_registration
    raw = baca_json_ketat(path_auth)
    daftar = raw.get('operasi_registrasi', {})
    if type(daftar) is not dict:
        raise ValueError('receipt tidak sah')
    akun = set()
    for operasi, r in daftar.items():
        if (type(r) is not dict or set(r) != admin_registration._RECEIPT_PUBLIC_FIELDS
                or r['operasi_id'] != operasi or r['hasil_kode'] != 'teacher_created'
                or type(r['dibuat']) is not int):
            raise ValueError('receipt tidak sah')
        if mulai <= r['dibuat'] < akhir:
            akun.add(r['hasil_id'])
    return len(akun)


def atur_eksperimen(path, path_auth, principal, *, operasi, mulai, aktif, revisi, sekarang):
    """Aktivasi eksplisit; awal/definisi dibekukan, restart menahan kualitas."""
    d.waktu(mulai); d.waktu(sekarang)
    if type(aktif) is not bool or type(revisi) is not int or revisi < 0 or mulai > sekarang or mulai + 56*d.HARI > 253370739599:
        raise ValueError('pengaturan eksperimen tidak sah')
    with guard.kunci_principal(path_auth, principal):
        with admin_store._transaksi(path) as kon:
            isi = [mulai,aktif,revisi]
            lama_op = guard.reservasi(kon,principal,operasi,'eksperimen','kpi-v1',isi,sekarang)
            if lama_op and lama_op['status'] == 'selesai':
                return
            lama = _eksperimen(kon)
            if revisi != (lama['revisi'] if lama else 0) or (lama and lama['mulai'] != mulai):
                raise admin_store.KonflikOperasi('revisi atau awal eksperimen berbeda')
            if not lama and mulai != sekarang:
                raise ValueError('eksperimen baru dimulai sekarang, tanpa backfill')
            if not lama:
                kon.execute("INSERT INTO kpi_eksperimen VALUES('uji-coba-v1',?,?,?, ?,1,'lengkap',?,?)",
                            (d.VERSI,mulai,mulai+56*d.HARI,int(aktif),BOOT_ID,sekarang))
                kon.execute("INSERT INTO kpi_cakupan VALUES('uji-coba-v1',0,0)")
            else:
                # Menyalakan lagi tidak menghapus interval hilang/restart sebelumnya.
                kualitas = lama['kualitas'] if lama['boot_id'] == BOOT_ID and lama['koleksi'] else 'terganggu'
                kon.execute('UPDATE kpi_eksperimen SET koleksi=?,revisi=revisi+1,kualitas=?,boot_id=?,diperbarui=? WHERE id=?',
                            (int(aktif),kualitas,BOOT_ID,sekarang,lama['id']))
            guard.selesaikan(kon,operasi,'tersimpan',sekarang)


def _receipt_publik(path_auth, akun_id):
    import admin_registration
    raw = baca_json_ketat(path_auth)
    receipts = raw.get('operasi_registrasi', {})
    if type(receipts) is not dict:
        raise ValueError('receipt registrasi tidak sah')
    cocok = []
    for r in receipts.values():
        if type(r) is not dict or set(r) != admin_registration._RECEIPT_PUBLIC_FIELDS:
            raise ValueError('receipt registrasi tidak sah')
        if r['hasil_id'] == akun_id and r['hasil_kode'] == 'teacher_created':
            d.waktu(r['dibuat'])
            cocok.append(r)
    if len(cocok) != 1:
        raise LookupError('pendaftaran publik tidak ditemukan')
    return cocok[0]


def setuju(path,path_auth,principal,*,sumber,sekarang,saat_daftar=False):
    d.waktu(sekarang)
    if sumber not in d.SUMBER:
        raise ValueError('sumber tidak sah')
    with guard.kunci_principal(path_auth,principal,'guru'):
        r = _receipt_publik(path_auth,principal.id_akun)
        with admin_store._transaksi(path) as kon:
            e = _eksperimen(kon)
            if not e or not e['koleksi'] or not e['mulai'] <= r['dibuat'] < e['akhir'] or sekarang >= r['dibuat']+30*d.HARI:
                raise ValueError('pendaftaran di luar eksperimen')
            lama = kon.execute('SELECT id FROM kpi_peserta WHERE eksperimen=? AND akun_id=?',(e['id'],principal.id_akun)).fetchone()
            if lama:
                # Setelah restart/restore tidak mewarisi izin kirim aktivitas;
                # persetujuan eksplisit baru tidak membackfill interval hilang.
                generasi = kon.execute('SELECT consent_boot FROM kpi_peserta WHERE id=?',(lama['id'],)).fetchone()[0]
                if generasi != BOOT_ID:
                    kon.execute('DELETE FROM kpi_aktivitas WHERE peserta=?',(lama['id'],))
                    kon.execute('DELETE FROM kpi_survei WHERE peserta=?',(lama['id'],))
                    kon.execute('UPDATE kpi_peserta SET terlambat=1 WHERE id=?',(lama['id'],))
                kon.execute('UPDATE kpi_peserta SET consent=?,consent_boot=? WHERE id=?',
                            (sekarang,BOOT_ID,lama['id']))
                return
            if sekarang < r['dibuat']:
                raise ValueError('clock mendahului pendaftaran')
            # Satu respons registrasi dapat melintasi detik. Caller HTTP hanya
            # menandai awal melalui operasi registrasi yang baru committed.
            awal = saat_daftar is True
            kon.execute('INSERT INTO kpi_peserta VALUES(?,?,?,?,?,?,?,?,?)',
                        ('p_'+secrets.token_hex(16),e['id'],principal.id_akun,r['dibuat'],sekarang,d.CONSENT,BOOT_ID,sumber,int(not awal)))


def cabut(path,path_auth,principal):
    """Hapus mapping/event/survei atomik; data belajar dan langganan tetap utuh."""
    with guard.kunci_principal(path_auth,principal,'guru'):
        with admin_store._transaksi(path) as kon:
            rows=kon.execute('SELECT id,eksperimen FROM kpi_peserta WHERE akun_id=?',(principal.id_akun,)).fetchall()
            for r in rows:
                kon.execute('DELETE FROM kpi_peserta WHERE id=?',(r['id'],))
                kon.execute('UPDATE kpi_cakupan SET dicabut=dicabut+1 WHERE eksperimen=?',(r['eksperimen'],))


def status_peserta(path,path_auth,principal):
    with guard.kunci_principal(path_auth,principal,'guru'):
        with admin_store.buka_baca(path) as kon:
            row=kon.execute('SELECT * FROM kpi_peserta WHERE akun_id=?',(principal.id_akun,)).fetchone()
            return dict(row) if row else None


def catat(path,akun_id,*,kode,sekarang):
    """Internal saja; adapter wajib membuktikan pemilik serta commit domain."""
    if kode not in d.KODE:
        raise ValueError('aktivitas tidak dikenal')
    with _transaksi(path) as kon:
        e=_eksperimen(kon)
        if not e or not e['koleksi'] or e['boot_id'] != BOOT_ID:
            return
        p=kon.execute('SELECT * FROM kpi_peserta WHERE akun_id=? AND eksperimen=?',(akun_id,e['id'])).fetchone()
        if not p or p['consent'] > sekarang or p['consent_boot'] != BOOT_ID:
            return
        j=d.jendela(p['t0'],sekarang)
        if j is None:
            return
        kon.execute('INSERT OR IGNORE INTO kpi_aktivitas VALUES(?,?,?,?)',(p['id'],d.hari_wib(sekarang),kode,j))


def gangguan(path):
    global PENCATATAN_GAGAL
    PENCATATAN_GAGAL = True
    with _transaksi(path) as kon:
        kon.execute("UPDATE kpi_eksperimen SET kualitas='terganggu'")


def survei(path,path_auth,principal,*,sekarang,jawaban=None):
    """Penawaran dahulu, respons sekali; tidak menganggap tidak menjawab negatif."""
    with guard.kunci_principal(path_auth,principal,'guru'):
        with admin_store._transaksi(path) as kon:
            p=kon.execute('SELECT * FROM kpi_peserta WHERE akun_id=?',(principal.id_akun,)).fetchone()
            e=_eksperimen(kon)
            if not p or not e or not e['koleksi'] or e['boot_id'] != BOOT_ID or p['consent_boot'] != BOOT_ID or p['terlambat'] or not 0 <= sekarang-p['t0'] < 14*d.HARI:
                return False
            if not kon.execute("SELECT 1 FROM kpi_aktivitas WHERE peserta=? AND jendela=1 AND kode!='panduan_hasil_disajikan'",(p['id'],)).fetchone():
                return False
            lama=kon.execute('SELECT * FROM kpi_survei WHERE peserta=?',(p['id'],)).fetchone()
            if jawaban is None:
                if lama and lama['jawaban']:
                    return False
                if not lama:
                    kon.execute('INSERT INTO kpi_survei VALUES(?,?,NULL,NULL,?)',(p['id'],sekarang,d.SURVEI))
                return True
            if jawaban not in ('ya','sebagian','belum') or not lama:
                raise ValueError('jawaban atau penawaran tidak sah')
            if lama['jawaban'] and lama['jawaban'] != jawaban:
                raise admin_store.KonflikOperasi('jawaban sudah tersimpan')
            kon.execute('UPDATE kpi_survei SET jawaban=?,dijawab=COALESCE(dijawab,?) WHERE peserta=?',(jawaban,sekarang,p['id']))
            return True


def simpan_biaya(path,path_auth,principal,*,operasi,bulan,revisi,nilai,sekarang):
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',bulan):
        raise ValueError('bulan tidak sah')
    if set(nilai) != {'anggaran','server','domain','ai','pendukung','lengkap'}:
        raise ValueError('kolom biaya tidak sah')
    if type(nilai['lengkap']) is not bool or any(type(nilai[k]) is not int or not 0 <= nilai[k] <= 10**9 for k in nilai if k != 'lengkap'):
        raise ValueError('nominal biaya tidak sah')
    if type(revisi) is not int or revisi < 0:
        raise ValueError('revisi tidak sah')
    with guard.kunci_principal(path_auth,principal):
        with admin_store._transaksi(path) as kon:
            isi=[bulan,revisi,nilai]
            lama_op=guard.reservasi(kon,principal,operasi,'biaya',bulan,isi,sekarang)
            if lama_op and lama_op['status']=='selesai':
                return
            lama=kon.execute('SELECT revisi FROM kpi_biaya WHERE bulan=?',(bulan,)).fetchone()
            if revisi != (lama[0] if lama else 0):
                raise admin_store.KonflikOperasi('revisi biaya berubah')
            kon.execute('INSERT OR REPLACE INTO kpi_biaya VALUES(?,?,?,?,?,?,?,?,?)',
                        (bulan,revisi+1,nilai['anggaran'],nilai['server'],nilai['domain'],nilai['ai'],nilai['pendukung'],int(nilai['lengkap']),sekarang))
            kon.execute('INSERT INTO kpi_audit_biaya VALUES(?,?,?,?)',(operasi,bulan,revisi+1,json.dumps(nilai,sort_keys=True)))
            guard.selesaikan(kon,operasi,'tersimpan',sekarang)


def laporan(path,*,sekarang,bulan):
    """Agregat tanpa identitas akun/anak; tidak membaca basis data belajar."""
    with admin_store.buka_baca(path) as kon:
        kon.execute('BEGIN')
        e=_eksperimen(kon)
        biaya=kon.execute('SELECT * FROM kpi_biaya WHERE bulan=?',(bulan,)).fetchone()
        if not e:
            return None,None,dict(biaya) if biaya else None,{'dicabut':0,'kedaluwarsa':0,'arsip':()}
        peserta=[]
        for p in kon.execute('SELECT * FROM kpi_peserta WHERE eksperimen=? AND t0>? AND consent_boot=?',(e['id'],sekarang-90*d.HARI,BOOT_ID)):
            acts=tuple(tuple(r) for r in kon.execute('SELECT hari,kode,jendela FROM kpi_aktivitas WHERE peserta=?',(p['id'],)))
            s=kon.execute('SELECT * FROM kpi_survei WHERE peserta=?',(p['id'],)).fetchone()
            peserta.append(d.Peserta(p['t0'],bool(p['terlambat']),acts,bool(s),s['jawaban'] or '' if s else '',p['sumber']))
        tertinggal = kon.execute('SELECT COUNT(*) FROM kpi_peserta WHERE eksperimen=? AND t0<=?',
                                 (e['id'],sekarang-90*d.HARI)).fetchone()[0]
        kualitas=(e['kualitas']=='lengkap' and e['boot_id']==BOOT_ID and bool(e['koleksi'])
                  and not PENCATATAN_GAGAL and not tertinggal)
        ringkas=d.hitung(peserta,mulai=e['mulai'],sekarang=sekarang,lengkap=kualitas)
        cakupan=dict(kon.execute('SELECT dicabut,kedaluwarsa FROM kpi_cakupan WHERE eksperimen=?',(e['id'],)).fetchone())
        if cakupan['kedaluwarsa'] or tertinggal:
            # Kartu aktif tidak menganggap data yang sudah dipurge sebagai nol.
            ringkas=d.hitung(peserta,mulai=e['mulai'],sekarang=sekarang,lengkap=False)
        cakupan['arsip'] = tuple(tuple(r) for r in kon.execute(
            'SELECT minggu,peserta,aktivasi,kembali,penawaran,respons,positif,organik FROM kpi_agregat WHERE eksperimen=? AND hapus_setelah>? ORDER BY minggu',
            (e['id'],sekarang)))
        return e,ringkas,dict(biaya) if biaya else None,cakupan


def retensi(path,*,sekarang):
    """Hapus detail ≥90 hari; agregat tanpa mapping hanya untuk kelompok ≥5."""
    with admin_store._transaksi(path) as kon:
        rows=kon.execute('SELECT id,eksperimen,t0,terlambat,sumber,consent_boot FROM kpi_peserta WHERE t0<=? LIMIT 500',
                         (sekarang-90*d.HARI,)).fetchall()
        kelompok={}
        for p in rows:
            e=kon.execute('SELECT mulai,akhir FROM kpi_eksperimen WHERE id=?',(p['eksperimen'],)).fetchone()
            minggu=(p['t0']-e[0])//(7*d.HARI)+1
            kelompok.setdefault((p['eksperimen'],minggu,e[1]),[]).append(p)
        for (eksperimen,minggu,akhir),grup in kelompok.items():
            sah = [p for p in grup if p['consent_boot'] == BOOT_ID]
            if len(sah)>=5:
                angka=[0]*8
                for p in sah:
                    angka[7]+=p['terlambat']
                    if p['terlambat']: continue
                    acts=tuple(tuple(r) for r in kon.execute('SELECT hari,kode,jendela FROM kpi_aktivitas WHERE peserta=?',(p['id'],)))
                    peserta=d.Peserta(p['t0'],False,acts)
                    pertama=d._aktif(peserta,1)
                    s=kon.execute('SELECT jawaban FROM kpi_survei WHERE peserta=?',(p['id'],)).fetchone()
                    nilai=[1,int(pertama),int(pertama and d._aktif(peserta,2)),int(s is not None),
                           int(bool(s and s[0])),int(bool(s and s[0]=='ya')),
                           int(pertama and minggu>=5 and p['sumber'] in ('rekomendasi','pencarian'))]
                    angka[:7]=[a+b for a,b in zip(angka[:7],nilai)]
                lama=kon.execute('SELECT peserta,aktivasi,kembali,penawaran,respons,positif,organik,terlambat FROM kpi_agregat WHERE eksperimen=? AND minggu=?',(eksperimen,minggu)).fetchone()
                if lama: angka=[a+b for a,b in zip(angka,lama)]
                kon.execute('INSERT OR REPLACE INTO kpi_agregat VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                            (eksperimen,minggu,*angka,sekarang,d.akhir_retensi_agregat(akhir)))
            for p in grup:
                kon.execute('DELETE FROM kpi_peserta WHERE id=?',(p['id'],))
                kon.execute('UPDATE kpi_cakupan SET kedaluwarsa=kedaluwarsa+1 WHERE eksperimen=?',(p['eksperimen'],))
        kon.execute('DELETE FROM kpi_agregat WHERE hapus_setelah<=?',(sekarang,))
