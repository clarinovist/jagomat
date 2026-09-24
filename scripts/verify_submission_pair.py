#!/usr/bin/env python3
"""Uji lintas image pada volume sintetis berlabel; tidak menyentuh volume keluarga."""
from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess

from verify_release_image import GalatVerifikasi, ParserAman, periksa_inspect, validasi_rujukan
from release_learning_pair import SUMBER_TULIS as TULIS_PILOT, SUMBER_BACA as BACA_PILOT
from release_profile_probe import SUMBER_UJI_PROFIL
from release_focus_pair import SUMBER_TULIS as FOKUS_TULIS, SUMBER_BACA as FOKUS_BACA
from release_admin_pair import SUMBER_TULIS as ADMIN_TULIS, SUMBER_BACA as ADMIN_BACA
from release_subscription_probe import SUMBER_UJI_LANGGANAN
from release_subscription_pair import SUMBER_TULIS as LANGGANAN_TULIS, SUMBER_BACA as LANGGANAN_BACA
from release_subscription_service_pair import SUMBER_TULIS as SERVICE_TULIS, SUMBER_BACA as SERVICE_BACA

TULIS_PILOT = 'FOKUS_TULIS = ' + repr(FOKUS_TULIS) + '\nPROBE_PROFIL = ' + repr(SUMBER_UJI_PROFIL) + '\nADMIN_TULIS = ' + repr(ADMIN_TULIS) + '\n' + TULIS_PILOT
BACA_PILOT = 'FOKUS_BACA = ' + repr(FOKUS_BACA) + '\nADMIN_BACA = ' + repr(ADMIN_BACA) + '\n' + BACA_PILOT

TULIS_PILOT = ('PROBE_LANGGANAN = ' + repr(SUMBER_UJI_LANGGANAN) + '\n'
               + LANGGANAN_TULIS + '\n' + SERVICE_TULIS + '\n' + TULIS_PILOT)
BACA_PILOT = LANGGANAN_BACA + '\n' + SERVICE_BACA + '\n' + BACA_PILOT

LABEL = 'osn.release.submission-probe'
AWALAN = 'osn-submission-pair-'

SUMBER_TULIS = r'''
import os,sys,json,hashlib,sqlite3
from pathlib import Path
os.chmod('/data',0o700)
os.environ['OSN_BERKAS_DB']='/data/probe.db'
os.environ['OSN_PBKDF2_ITERASI']='1000'
import database,student_submissions,review_store
p=Path('/data/probe.db')
database.siapkan(p)
with database.buka(p) as kon:
    siswa=database.tambah_siswa(kon,'Anak Probe Sintetis','P3',pemilik='guru')
    sesi=database.buat_sesi_dari_urutan(kon,siswa,37,('deret_aritmetika',),level='P3')
    sid=database.isi_sesi(kon,sesi)[0]['sesi_soal_id']
    student_submissions.arsipkan(kon,sesi,'akun')
    database.tandai_selesai(kon,sesi)
    review_store.simpan(kon,sesi,{f'catatan_tinjauan_{sid}':'Belum tahu langkah awal.'},'guru')
    kh=database.konfirmasi_hasil(kon,sesi,guru='guru',dilewati={sid})
    tabel=('pengiriman_sesi','pengiriman_butir','konfirmasi_hasil','snapshot_outcome','tinjauan_outcome')
    bukti={t:[tuple(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in tabel}
    assert len(bukti['pengiriman_butir'])==len(bukti['snapshot_outcome'])==1
    assert not kon.execute('PRAGMA foreign_key_check').fetchall()
    assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
Path('/data/manifest.json').write_text(json.dumps({'sesi':sesi,'sid':sid,'bukti':bukti},sort_keys=True))
# PG: data sungguhan sintetis, termasuk draft yang diteruskan recovery.
import choice_store,students,reports
with database.buka(p) as kon:
    pg=database.buat_sesi(kon,siswa,43,topik='logika',jumlah_soal=12,format_jawaban='pilihan_ganda')
    angka=database.buat_sesi(kon,siswa,44,topik='pola-bilangan',format_jawaban='pilihan_ganda')
    jumlah_opsi=set()
    for sesi_pg in (pg,angka):
        pilihan=choice_store.daftar_pilihan(kon,sesi_pg)
        data={'revisi_pekerjaan':str(student_submissions.revisi(kon,sesi_pg))}
        for b in database.isi_sesi(kon,sesi_pg):
            opsi=pilihan[b['sesi_soal_id']]
            jumlah_opsi.add(len(opsi.opsi))
            data['opsi_'+str(b['sesi_soal_id'])]=next(o.id for o in opsi.opsi if o.nilai==b['kunci'])
        students.simpan_jawaban_murid(kon,siswa,sesi_pg,data)
    assert jumlah_opsi=={3,4,5}
    student_submissions.arsipkan(kon,pg,'akun')
    reports.diagnosa_murid(kon,pg)
    database.tandai_selesai(kon,pg)
    kh_pg=database.konfirmasi_hasil(kon,pg,'guru')
    tabel_pg=('pilihan_butir','pengiriman_pilihan','konfirmasi_pilihan')
    salinan={t:[tuple(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in tabel_pg}
    assert all(salinan.values())
    bukti={t:[tuple(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in tabel}
Path('/data/manifest.json').write_text(json.dumps({'sesi':sesi,'sid':sid,'bukti':bukti},sort_keys=True))
Path('/data/pg-manifest.json').write_text(json.dumps({'siswa':siswa,'sesi':pg,'draft':angka,'kh':kh_pg,'bukti':salinan},sort_keys=True))
print('OSN_SUBMISSION_WRITER_OK')
'''

SUMBER_BACA = r'''
import os,json,sqlite3
from pathlib import Path
os.environ['OSN_BERKAS_DB']='/data/probe.db'
import database,student_submissions,review_store
p=Path('/data/probe.db'); awal=json.loads(Path('/data/manifest.json').read_text())
for _ in range(2): database.siapkan(p)
with database.buka(p) as kon:
    for t,rows in awal['bukti'].items():
        assert [list(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')]==rows
    sesi=awal['sesi'];sid=awal['sid']
    assert review_store.pengiriman(kon,sesi)[sid]['jawaban']==''
    assert review_store.muat(kon,sesi)[sid]['catatan']=='Belum tahu langkah awal.'
    kh=database.konfirmasi_hasil(kon,sesi,guru='guru',dilewati={sid})
    assert kh==awal['bukti']['konfirmasi_hasil'][0][0]
    for sql in ("UPDATE pengiriman_butir SET jawaban='123'",'DELETE FROM pengiriman_butir'):
        try: kon.execute(sql)
        except sqlite3.IntegrityError: pass
        else: raise AssertionError('immutable_hilang')
    review_store.simpan(kon,sesi,{f'catatan_tinjauan_{sid}':'Diberi contoh.',f'provenance_{sid}':'setelah_bantuan',
        f'jawaban_bantuan_{sid}':'123',f'versi_tinjauan_{sid}':review_store.tanda(kon,sid)},'guru')
    jid=database.simpan_jawaban(kon,sid,'123','Diberi contoh')
    for benar,kode in ((True,None),(False,'K'),(False,'H')):
        if not benar: database.simpan_jawaban(kon,sid,'','')
        database.simpan_diagnosis(kon,jid,benar,None,kode,manual=True)
        try: database.konfirmasi_hasil(kon,sesi,guru='guru')
        except ValueError: pass
        else: raise AssertionError('bantuan_menjadi_bukti')
    for t,rows in awal['bukti'].items():
        assert [list(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')]==rows
    assert not kon.execute('PRAGMA foreign_key_check').fetchall()
    assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
# Recovery wajib memahami PG, bukan hanya membiarkan tabel baru tetap ada.
import choice_store,students,reports
from choice_contract import serialisasi
from learning_cycle_service import konfirmasi_dari_form
pg=json.loads(Path('/data/pg-manifest.json').read_text())
with database.buka(p) as kon:
    for t,rows in pg['bukti'].items():
        assert [list(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')]==rows
    pilihan=choice_store.daftar_pilihan(kon,pg['sesi'])
    assert pilihan and database.konfirmasi_hasil(kon,pg['sesi'],'guru')==pg['kh']
    choice_store.validasi_arsip(kon,pg['sesi'],pg['kh'])
    halaman=__import__('student_pages').halaman_kerja_baru(kon,pg['siswa'],pg['draft'])
    assert b'name="opsi_' in halaman and b'name="jwb_' not in halaman
    for tabel in ('pilihan_butir','pengiriman_pilihan','konfirmasi_pilihan'):
        try: kon.execute('UPDATE '+tabel+" SET snapshot_json='{}'")
        except sqlite3.IntegrityError: pass
        else: raise AssertionError('arsip_pg_mutable')
    try: konfirmasi_dari_form(kon,pg['sesi'],'guru',{'sertakan_pemetaan':'1'})
    except ValueError: pass
    else: raise AssertionError('pg_menjadi_pemetaan')
    draft=pg['draft']; opsi=choice_store.daftar_pilihan(kon,draft)
    sid=next(iter(opsi)); rev=student_submissions.revisi(kon,draft)
    students.simpan_jawaban_murid(kon,pg['siswa'],draft,{'revisi_pekerjaan':str(rev),'opsi_'+str(sid):''})
    assert not kon.execute('SELECT jawaban FROM jawaban WHERE sesi_soal_id=?',(sid,)).fetchone()
    try: students.simpan_jawaban_murid(kon,pg['siswa'],draft,{'revisi_pekerjaan':str(rev),'opsi_'+str(sid):'opsi_1'})
    except ValueError: pass
    else: raise AssertionError('revisi_pg_diabaikan')
    student_submissions.arsipkan(kon,draft,'akun')
    reports.diagnosa_murid(kon,draft); database.tandai_selesai(kon,draft)
    assert all(b['kode_final'] is None for b in database.isi_sesi(kon,draft))
    assert not kon.execute('PRAGMA foreign_key_check').fetchall()
    assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
print('OSN_SUBMISSION_RECOVERY_OK')
'''


def _panggil(argv, masukan=None):
    hasil = subprocess.run(['docker', *argv], input=masukan, capture_output=True,
                           text=True, timeout=180, check=False, shell=False)
    if hasil.returncode:
        raise GalatVerifikasi('probe_pasangan_gagal')
    return hasil.stdout.strip()


def _jalankan(image, volume, sumber, token, nomor, *, siapkan_izin=False):
    nama = AWALAN + token + '-' + str(nomor)
    try:
        return _panggil([
            'run', '--rm', '-i', '--pull', 'never', '--name', nama,
            '--label', LABEL + '=' + token, '--network', 'none', '--read-only',
            '--user', '0:0' if siapkan_izin else '10001:10001', '--cap-drop', 'ALL',
            *(['--cap-add', 'CHOWN'] if siapkan_izin else []), '--security-opt', 'no-new-privileges',
            '--memory', '512m', '--cpus', '1', '--pids-limit', '128',
            '--mount', 'type=volume,src=' + volume + ',dst=/data',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=32m',
            '--workdir', '/app', '--entrypoint', 'python', image, '-E', '-B', '-',
        ], sumber)
    finally:
        # Timeout bukan bukti container selesai; hapus hanya ID dengan label kita.
        identitas = _panggil(['container', 'ls', '-aq', '--no-trunc', '--filter', 'name=^/' + nama + '$'])
        if identitas:
            if not re.fullmatch(r'[0-9a-f]{64}', identitas):
                raise GalatVerifikasi('identitas_probe_tidak_sah')
            pemilik = _panggil(['container', 'inspect', '--format', '{{index .Config.Labels "' + LABEL + '"}}', identitas])
            if pemilik != token:
                raise GalatVerifikasi('pemilik_probe_tidak_sah')
            _panggil(['container', 'rm', '--force', identitas])


def verifikasi(candidate_image, candidate_revision, recovery_image, recovery_revision):
    for image, revision in ((candidate_image, candidate_revision), (recovery_image, recovery_revision)):
        validasi_rujukan(image, revision)
        periksa_inspect(_panggil(['image', 'inspect', image]), image, revision)
    if candidate_image == recovery_image or candidate_revision == recovery_revision:
        raise GalatVerifikasi('pasangan_harus_berbeda')
    token = secrets.token_hex(16)
    volume = AWALAN + token
    # Volume baru milik probe, tanpa bind mount source/DB/kunci/volume produksi.
    # Bukan tmpfs: driver dapat unmount antara dua container dan menghilangkan data.
    _panggil(['volume', 'create', '--label', LABEL + '=' + token, '--driver', 'local', volume])
    try:
        pemilik = _panggil(['volume', 'inspect', '--format', '{{index .Labels "' + LABEL + '"}}', volume])
        if pemilik != token:
            raise GalatVerifikasi('pemilik_volume_tidak_sah')
        _jalankan(candidate_image, volume,
                  "import os; os.chown('/data',10001,10001)",
                  token, 0, siapkan_izin=True)
        if _jalankan(candidate_image, volume, SUMBER_TULIS, token, 1) != 'OSN_SUBMISSION_WRITER_OK':
            raise GalatVerifikasi('probe_penulis_gagal')
        if _jalankan(recovery_image, volume, SUMBER_BACA, token, 2) != 'OSN_SUBMISSION_RECOVERY_OK':
            raise GalatVerifikasi('probe_pemulihan_gagal')
        if _jalankan(candidate_image, volume, TULIS_PILOT, token, 3) != 'OSN_LEARNING_WRITER_OK':
            raise GalatVerifikasi('probe_penulis_pilot_gagal')
        if _jalankan(recovery_image, volume, BACA_PILOT, token, 4) != 'OSN_LEARNING_RECOVERY_OK':
            raise GalatVerifikasi('probe_pemulihan_pilot_gagal')
    finally:
        pemilik = _panggil(['volume', 'inspect', '--format', '{{index .Labels "' + LABEL + '"}}', volume])
        if pemilik != token:
            raise GalatVerifikasi('pemilik_volume_tidak_sah')
        _panggil(['volume', 'rm', volume])
    return {'ok': True, 'candidate_revision': candidate_revision,
            'candidate_digest': candidate_image.split('@')[1],
            'recovery_revision': recovery_revision,
            'recovery_digest': recovery_image.split('@')[1], 'pengiriman_pair_checks': 6,
            'pilihan_pair_checks': 8, 'learning_pair_checks': 8, 'subscription_pair_checks': 4,
            'provider_calls': 0}


def main(argv=None):
    parser = ParserAman(description=__doc__, allow_abbrev=False)
    for nama in ('candidate-image', 'candidate-revision', 'recovery-image', 'recovery-revision'):
        parser.add_argument('--' + nama, required=True)
    try:
        args = parser.parse_args(argv)
        hasil = verifikasi(args.candidate_image, args.candidate_revision, args.recovery_image, args.recovery_revision)
    except Exception:
        print(json.dumps({'ok': False, 'kode': 'probe_pasangan_gagal'}))
        return 1
    print(json.dumps(hasil, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
