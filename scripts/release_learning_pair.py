"""Probe pasangan admin5/konteks/pilot, hanya data sintetis di volume CI."""
SUMBER_TULIS = r'''
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
import database,admin_students,learning_profile
from skill_pilot import LANGSUNG,PRASYARAT,BALIK
from skill_pilot_service import jalankan,revisi,keadaan
from skill_pilot_store import baca_kontrak
p=Path('/data/learning-pair.db'); database.siapkan(p); admin_students.siapkan(p)
with database.buka(p) as kon:
    siswa=database.tambah_siswa(kon,'Probe Pilot Sintetis','P3',pemilik='guru')
    learning_profile.simpan_kelas(kon,siswa,2,revisi=0,pemilik='guru')
    def mulai(tuntutan,profil,hari):
        return int(jalankan(kon,siswa,{'aksi':'mulai','revisi':revisi(kon,siswa),
            'tuntutan':tuntutan,'profil':profil,'representasi':'teks-v1'},hari=hari).split('/')[-1])
    def lanjut(hari):
        return int(jalankan(kon,siswa,{'aksi':'lanjut','revisi':revisi(kon,siswa)},hari=hari).split('/')[-1])
    def sahkan(sid,hari):
        for b in database.isi_sesi(kon,sid):
            jid=database.simpan_jawaban(kon,b['sesi_soal_id'],b['kunci'])
            database.simpan_diagnosis(kon,jid,True,None,None)
        database.tandai_selesai(kon,sid)
        kh=database.konfirmasi_hasil(kon,sid,'guru',cek_pemahaman={b['sesi_soal_id']:'bisa_menjelaskan' for b in database.isi_sesi(kon,sid)})
        kon.execute('UPDATE sesi SET tanggal=?,selesai=?,dikonfirmasi_guru=? WHERE id=?',(str(hari),str(hari),str(hari),sid))
        return kh
    a=mulai(LANGSUNG,'P3',date(2026,9,1)); sahkan(a,date(2026,9,1))
    b=lanjut(date(2026,9,4)); sahkan(b,date(2026,9,4))
    c=mulai(PRASYARAT,'P3',date(2026,9,4)); sahkan(c,date(2026,9,4))
    d=lanjut(date(2026,9,7)); sahkan(d,date(2026,9,7))
    draft=mulai(BALIK,'P4',date(2026,9,7))
    tabel=('profil_belajar','konteks_sesi','konteks_butir','konteks_konfirmasi',
           'pilot_putaran','pilot_sesi','pilot_konfirmasi','pilot_aksi','snapshot_outcome','konfirmasi_hasil')
    arsip={t:[tuple(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in tabel}
    sesi_awal=[tuple(r) for r in kon.execute('SELECT * FROM sesi ORDER BY id')]
    soal_awal=[tuple(r) for r in kon.execute('SELECT * FROM soal ORDER BY id')]
    assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not kon.execute('PRAGMA foreign_key_check').fetchall()
Path('/data/learning-pair.json').write_text(json.dumps({'siswa':siswa,'draft':draft,'arsip':arsip,'sesi':sesi_awal,'soal':soal_awal},sort_keys=True))
# Receipt admin5 dan migrasi registry diuji terpisah; turunan uji tidak menyentuh keluarga.
exec(PROBE_PROFIL)
assert uji_profil_konteks('/data/profil-pair')==6
exec(ADMIN_TULIS)
exec(FOKUS_TULIS)
print('OSN_LEARNING_WRITER_OK')
'''

SUMBER_BACA = r'''
import json,sqlite3
from pathlib import Path
from datetime import date
import database,admin_students,learning_profile
from skill_pilot_store import baca_kontrak,muat_bukti,validasi_konfirmasi
from learning_cycle import penguasaan_pilot
from skill_pilot import KonteksPilot,LANGSUNG,PRASYARAT,BALIK
from skill_pilot_service import jalankan,revisi
awal=json.loads(Path('/data/learning-pair.json').read_text());p=Path('/data/learning-pair.db')
for _ in range(2): database.siapkan(p);admin_students.siapkan(p)
with database.buka(p) as kon:
    for t,baris in awal['arsip'].items():
        assert [list(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')]==baris
    assert [list(r) for r in kon.execute('SELECT * FROM sesi ORDER BY id')]==awal['sesi']
    assert [list(r) for r in kon.execute('SELECT * FROM soal ORDER BY id')]==awal['soal']
    siswa=awal['siswa'];draft=awal['draft']
    assert learning_profile.baca(kon,siswa,pemilik='guru').kelas_sekolah==2
    sumber=baca_kontrak(kon,draft,siswa)
    assert len(sumber.sumber_konfirmasi)==4 and sumber.profil_parameter=='P4'
    bukti=muat_bukti(kon,siswa)
    hasil=penguasaan_pilot(bukti,siswa,(KonteksPilot(LANGSUNG,'P3','teks-v1'),KonteksPilot(PRASYARAT,'P3','teks-v1'),KonteksPilot(BALIK,'P4','teks-v1')),date(2026,9,7))
    assert [h.hasil.status for h in hasil]==['terbukti','terbukti','belum_dinilai']
    before=tuple(kon.iterdump())
    try:baca_kontrak(kon,draft,siswa+1)
    except ValueError:pass
    else:raise AssertionError('owner_pilot_hilang')
    assert tuple(kon.iterdump())==before
    for b in database.isi_sesi(kon,draft):
        jid=database.simpan_jawaban(kon,b['sesi_soal_id'],b['kunci'])
        database.simpan_diagnosis(kon,jid,True,None,None)
    database.tandai_selesai(kon,draft)
    pemahaman={b['sesi_soal_id']:'bisa_menjelaskan' for b in database.isi_sesi(kon,draft)}
    kh=database.konfirmasi_hasil(kon,draft,'guru',cek_pemahaman=pemahaman)
    assert database.konfirmasi_hasil(kon,draft,'guru',cek_pemahaman=pemahaman)==kh
    assert validasi_konfirmasi(kon,draft,siswa,kh)==sumber
    for t in ('pilot_konfirmasi','konteks_konfirmasi','snapshot_outcome'):
        try:kon.execute('DELETE FROM '+t)
        except sqlite3.IntegrityError:pass
        else:raise AssertionError('arsip_pilot_mutable')
    for t,rows in awal['arsip'].items():
        sesudah=[list(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')]
        assert sesudah[:len(rows)]==rows
    assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not kon.execute('PRAGMA foreign_key_check').fetchall()
# Recovery membaca receipt admin5 yang benar-benar ditulis candidate.
import admin_store,admin_contracts,learning_profile_admin,auth
akar=Path('/data/profil-pair');sandi=akar/'sandi.json'
# Probe fungsi telah menutup rollback korupsi konteks, tetapi receipt sengaja
# dikorupkan di akhir uji negatif. Recovery wajib menolak, bukan menganggap sukses.
akun=auth.cari_akun('probe-profil-admin',path=sandi)
perintah=admin_contracts.PerintahProfilSiswa('op_profil_probe',akun['id_akun'],auth.revisi_auth(akun),admin_contracts.AKSI_UBAH_KELAS_SEKOLAH,1,0,5,'t'*64)
try:learning_profile_admin.baca_receipt(akar/'belajar.db',sandi,perintah)
except admin_students.KonflikSiswa:pass
else:raise AssertionError('receipt_rusak_diterima_recovery')
with admin_store.buka_baca(akar/'admin.db') as kon:
    assert kon.execute('PRAGMA user_version').fetchone()[0]==6
    assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
exec(ADMIN_BACA)
exec(FOKUS_BACA)
print('OSN_LEARNING_RECOVERY_OK')
'''
