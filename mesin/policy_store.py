"""Pilihan persetujuan berversi, atomik dengan sensor dan tahan restart biasa."""
import os
import re
import secrets

import admin_store
import admin_launch_service
import policy_schema

VERSI='jagomat-2026-10-18-v2'
EPOCH=os.environ.get('SENSOR_CONSENT_EPOCH','')


def epoch_sah():
    return bool(re.fullmatch(r'[0-9a-f]{32}', EPOCH))


def baca(path, akun_id):
    with admin_store.buka_baca(path) as kon:
        if not policy_schema.validasi(kon):
            return None
        row=kon.execute('SELECT * FROM policy_receipt WHERE akun_id=?',(akun_id,)).fetchone()
        return dict(row) if row else None


def berlaku(row):
    return bool(epoch_sah() and row and row['versi']==VERSI and row['epoch']==EPOCH)


def simpan(path,path_auth,principal,*,revisi,operasi,pilihan,sekarang,versi):
    """Replay identik no-op; stale tab tidak menghidupkan pemrosesan yang dicabut."""
    import sensor_store
    import sensor_domain
    if (not epoch_sah() or sensor_store.BOOT!=EPOCH or versi!=VERSI or type(revisi) is not int or revisi<0
            or type(operasi) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',operasi)
            or type(pilihan) is not tuple or len(pilihan)!=3
            or any(type(x) is not bool for x in pilihan)
            or (not pilihan[0] and any(pilihan[1:]))):
        raise ValueError('persetujuan tidak sah')
    sensor_store.waktu(sekarang)
    with admin_launch_service.kunci_principal(path_auth,principal,'guru'):
        with sensor_store.buka(path,tulis=True) as kon:
            if not policy_schema.validasi(kon):
                raise admin_store.StoreBelumSiap('persetujuan belum dipasang')
            row=kon.execute('SELECT * FROM policy_receipt WHERE akun_id=?',(principal.id_akun,)).fetchone()
            if row and row['operasi']==operasi:
                if (row['versi'],row['epoch'],row['alur'],row['hasil'],row['chat']) != (VERSI,EPOCH,*pilihan):
                    raise ValueError('operasi persetujuan berbeda')
                return
            if revisi!=(row['revisi'] if row else 0):
                raise admin_store.KonflikOperasi('pilihan persetujuan berubah')
            # Modifikasi pilihan menghapus seluruh turunan dan mulai prospektif.
            kon.execute('DELETE FROM sensor_peserta WHERE akun_id=?',(principal.id_akun,))
            if pilihan[0]:
                kon.execute('INSERT INTO sensor_peserta VALUES(?,?,?,?,?,?,?,?,?)',(
                    principal.id_akun,secrets.token_hex(16),secrets.token_hex(32),EPOCH,
                    sekarang,sekarang+sensor_domain.RETENSI_CONSENT,sensor_domain.CONSENT,
                    int(pilihan[1]),int(pilihan[2])))
            kon.execute('INSERT INTO policy_receipt VALUES(?,?,?,?,?,?,?,?,?) '
                        'ON CONFLICT(akun_id) DO UPDATE SET versi=excluded.versi,epoch=excluded.epoch,revisi=excluded.revisi,'
                        'operasi=excluded.operasi,dibuat=excluded.dibuat,alur=excluded.alur,hasil=excluded.hasil,chat=excluded.chat',
                        (principal.id_akun,VERSI,EPOCH,revisi+1,operasi,sekarang,*(int(x) for x in pilihan)))


def cabut_dalam_transaksi(kon,akun_id):
    """Pencabutan juga memperbarui receipt agar penolakan tidak diminta ulang."""
    if policy_schema.validasi(kon):
        operasi='cabut_'+secrets.token_hex(16)
        # Tombstone bukan persetujuan Terms; tetap membatalkan form revisi0.
        kon.execute("INSERT INTO policy_receipt VALUES(?,'belum_disetujui',?,1,?,0,0,0,0) "
                    'ON CONFLICT(akun_id) DO UPDATE SET alur=0,hasil=0,chat=0,revisi=policy_receipt.revisi+1,operasi=excluded.operasi',
                    (akun_id,EPOCH if epoch_sah() else '0'*32,operasi))
