"""Probe soal C→B→C: bank/arsip sintetis, reader tetap mengenali seluruh ID."""
from release_catalog_pair import TULIS as KATALOG_TULIS, BACA as KATALOG_BACA

BERSAMA = r'''
import hashlib,json,os
from pathlib import Path
os.environ['OSN_PBKDF2_ITERASI']='1000'
import database,teacher_print_pages,teacher_review_service,question_views
from generator import buat_soal,buat_lembar
from templates import REGISTRI
from dataclasses import replace
root=Path('/data/question-pair')
path=root/'belajar.db'
jenis=('banyak_kelipatan','sisa_operasi','banyak_prima','jumlah_kelipatan')
def bank(c):
    return {t:[list(r) for r in c.execute('SELECT * FROM '+t+' ORDER BY rowid')]
            for t in ('soal','malrule','pilihan_butir','pengiriman_sesi','pengiriman_butir','pengiriman_pilihan')}
TABEL_BUKTI=('konteks_sesi','konteks_butir','konteks_konfirmasi','konfirmasi_hasil','snapshot_outcome','konfirmasi_pilihan','tinjauan_outcome')
def bukti(c):
    return {t:[list(r) for r in c.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in TABEL_BUKTI}
def preservasi(c,awal):
    kini=bukti(c)
    assert all(kini[t][:len(rows)]==rows for t,rows in awal.items()), 'bukti_lama_berubah'
def cetak(c,sesi):
    return [hashlib.sha256(teacher_print_pages.halaman_lembar(c,sesi,guru)).hexdigest() for guru in (False,True)]
def sehat(c):
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
def baca_manifest():return json.loads((root/'manifest.json').read_text())
def periksa(c,m):
    assert all(tid in REGISTRI for tid in jenis), 'reader_tidak_mengenal_jenis'
''' + KATALOG_BACA + r'''
    for sesi,hashes in m['cetak']:
        assert cetak(c,sesi)==hashes, 'cetak_bank_berubah'
    import context_store
    from mastery_catalog import katalog_target
    assert set(jenis)<={tid for t in katalog_target('P4') for tid in t.pola}, 'katalog_reader_menyusut'
    for sesi in m['sesi']:
        assert context_store.proyeksi(c,sesi,{}) is not None, 'konteks_hilang'
        for b in database.isi_sesi(c,sesi):
            soal=question_views.soal_dari_baris(b)
            assert soal.teks==b['teks_soal'] and soal.kunci==b['kunci']
            assert database.simpan_soal(c,replace(REGISTRI[b['template_id']](**soal.parameter),level=b['level']))==b['soal_id']
    assert bank(c)==m['bank'], 'bank_arsip_berubah'
    preservasi(c,m['bukti'])
    database.muat_bukti_siklus(c,m['anak'])
    sehat(c)
'''
SUMBER_TULIS = "import os\nos.environ.pop('OSN_TEORI_BILANGAN_VERSI',None)\n" + BERSAMA + r'''
from number_theory_versions import versi_writer
assert versi_writer()==2, 'kandidat_writer_bukan_batch_baru'
root.mkdir()
database.siapkan(path)
import student_submissions
with database.buka(path) as c:
    anak=database.tambah_siswa(c,'Fixture Pasangan Soal','P4',pemilik='guru')
    sesi=[]
    for lv in ('P4','P5'):
        for fmt in ('isian','pilihan_ganda'):
            sid=database.buat_sesi(c,anak,42,topik='teori-bilangan',level=lv,format_jawaban=fmt)
            assert set(jenis)<={b['template_id'] for b in database.isi_sesi(c,sid)}
            if fmt=='isian':
                for b in database.isi_sesi(c,sid):
                    database.simpan_jawaban(c,b['sesi_soal_id'],b['kunci'],'hitung sintetis')
            else:
                from choice_store import daftar_pilihan
                from students import simpan_jawaban_murid
                pilihan=daftar_pilihan(c,sid)
                form={'revisi_pekerjaan':str(student_submissions.revisi(c,sid))}
                for b in database.isi_sesi(c,sid):
                    form['opsi_'+str(b['sesi_soal_id'])]=next(o.id for o in pilihan[b['sesi_soal_id']].opsi if o.nilai==b['kunci'])
                simpan_jawaban_murid(c,anak,sid,form)
            student_submissions.arsipkan(c,sid,'akun')
            sesi.append(sid)
    modus=replace(REGISTRI['median_modus'](varian='modus',data=[5,5,3]),level='P4')
    assert 'modus.pertama' not in {m.id for m in modus.malrule}
    sid=database.buat_sesi_dari_urutan(c,anak,43,('median_modus',),topik='statistika',level='P4',soal_terpilih=(modus,))
    sesi.append(sid)
    # Sertakan bank lama dengan fallback palsu yang tidak boleh ditulis ulang.
    from templates import Malrule
    lama=replace(REGISTRI['median_modus'](varian='modus',data=[7,7,2]),level='P4')
    lama=replace(lama,malrule=(Malrule('modus.pertama','8','K','menjawab data pertama, bukan yang paling sering muncul'),*lama.malrule))
    lama_id=database.buat_sesi_dari_urutan(c,anak,44,('median_modus',),topik='statistika',level='P4',soal_terpilih=(lama,))
    sesi.append(lama_id)
    # Bingkai offline diuji pada C; B tidak perlu memiliki modul bank untuk
    # membaca teks exact snapshotv1. Tidak ada provider atau metadata baru.
    import story_frames
    os.environ['OSN_BANK_KALIMAT']='0'
    asli_kpk=replace(REGISTRI['kpk_dua_bilangan'](a=6,b=8),level='P5')
    sumber_lama=database.buat_sesi_dari_urutan(c,anak,46,('kpk_dua_bilangan',),topik='teori-bilangan',level='P5',soal_terpilih=(asli_kpk,))
    sesi.append(sumber_lama)
    cache_sesi=[sumber_lama]
    os.environ['OSN_BANK_KALIMAT']='1'
    for tid,param,topik in (
        ('kpk_dua_bilangan',{'a':6,'b':8},'teori-bilangan'),
        ('aturan_kali',{'m':3,'n':4},'kombinatorik'),
        ('jabat_tangan',{'n':5},'kombinatorik'),
    ):
        soal=replace(REGISTRI[tid](**param),level='P5')
        sid_bingkai=database.buat_sesi_dari_urutan(c,anak,45,(tid,),topik=topik,level='P5',soal_terpilih=(soal,))
        row=database.isi_sesi(c,sid_bingkai)[0]
        assert row['teks_soal']==story_frames.kalimat_baru(tid,'P5',param).teks
        assert row['teks_soal']!=soal.teks and row['kunci']==soal.kunci
        sesi.append(sid_bingkai)
        if tid=='kpk_dua_bilangan':cache_sesi.append(sid_bingkai)
    # Cache B2 memakai mock lokal: tidak ada provider. Sumber berbeda harus
    # menghasilkan dua cache terpisah dan dapat dibaca recovery.
    import llm
    llm.ensure_table(c)
    llm.aktif=lambda:True
    llm.konfigurasi=lambda:{'model':'model-pair-sintetis'}
    for sid_cache in cache_sesi:
        src=question_views.soal_dari_baris(database.isi_sesi(c,sid_cache)[0])
        llm._panggil=lambda prompt,teks=src.teks:teks
        assert llm.bungkus(c,src)==src.teks, 'cache_sumber_tabrakan'
    assert c.execute('SELECT COUNT(*) FROM llm_cache').fetchone()[0]==2
    cache=[[r['kunci_hash'],r['kalimat']] for r in c.execute('SELECT kunci_hash,kalimat FROM llm_cache ORDER BY kunci_hash')]
    os.environ['OSN_BANK_KALIMAT']='0'
    import reports
    konfirmasi=[]
    for s in sesi[:2]:
        reports.diagnosa_murid(c,s)
        database.tandai_selesai(c,s)
        konfirmasi.append((s,database.konfirmasi_hasil(c,s,'guru')))
''' + '\n'.join('    '+baris if baris else '' for baris in KATALOG_TULIS.splitlines()) + r'''
    hashes=[(s,cetak(c,s)) for s in sesi]
    m={'anak':anak,'sesi':sesi,'modus':sid,'lama':lama_id,'cetak':hashes,'bank':bank(c),
       'bukti':bukti(c),'konfirmasi':konfirmasi,'cache_sesi':cache_sesi,'cache':cache,
       'catalog_versi':catalog_versi,'catalog_pembahasan':catalog_pembahasan}
    sehat(c)
(root/'manifest.json').write_text(json.dumps(m,sort_keys=True))
print('OSN_QUESTION_WRITER_OK')
'''
SUMBER_BACA = "import os\nos.environ.pop('OSN_TEORI_BILANGAN_VERSI',None)\n" + BERSAMA + r'''
from number_theory_versions import versi_writer
assert versi_writer()==1, 'recovery_writer_bukan_konservatif'
from catalog_versions import versi_writer as versi_katalog
assert versi_katalog()==1, 'recovery_writer_katalog_harus_1'
os.environ.pop('OSN_BANK_KALIMAT',None)
assert not set(jenis)&{s.template_id for s in buat_lembar(42,level='P4',topik='teori-bilangan').soal}
m=baca_manifest()
with database.buka(path) as c:
    periksa(c,m)
    import llm
    llm.aktif=lambda:True
    llm.konfigurasi=lambda:{'model':'model-pair-sintetis'}
    def tidak_ada_provider(*args):raise AssertionError('cache_recovery_miss')
    llm._panggil=tidak_ada_provider
    for sid_cache in m['cache_sesi']:
        src=question_views.soal_dari_baris(database.isi_sesi(c,sid_cache)[0])
        assert llm.bungkus(c,src)==src.teks, 'cache_recovery_sumber_berbeda'
    assert [[r['kunci_hash'],r['kalimat']] for r in c.execute('SELECT kunci_hash,kalimat FROM llm_cache ORDER BY kunci_hash')]==m['cache']
    # Diagnosis memakai bank tersimpan untuk aturan lama maupun baru.
    for sid,jwb,harapan in ((m['modus'],'6',None),(m['lama'],'8','modus.pertama')):
        b=database.isi_sesi(c,sid)[0]
        teacher_review_service.simpan_sesi(c,sid,{f"jwb_{b['sesi_soal_id']}":jwb,f"cara_{b['sesi_soal_id']}":'coretan sintetis'})
        assert database.isi_sesi(c,sid)[0]['malrule_id']==harapan
    import reports
    for sid in m['sesi'][:2]:
        assert all(b['benar']==1 for b in database.isi_sesi(c,sid))
    for sid in m['sesi'][2:4]:
        reports.diagnosa_murid(c,sid)
        assert all(b['benar']==1 for b in database.isi_sesi(c,sid))
    for sid,kid in m['konfirmasi']:
        assert database.konfirmasi_hasil(c,sid,'guru')==kid, 'konfirmasi_lama_berubah'
    for sid in m['sesi'][2:4]:
        database.tandai_selesai(c,sid)
        satu=database.konfirmasi_hasil(c,sid,'guru')
        assert database.konfirmasi_hasil(c,sid,'guru')==satu
    preservasi(c,m['bukti'])
    database.muat_bukti_siklus(c,m['anak'])
    (root/'bukti-recovery.json').write_text(json.dumps(bukti(c),sort_keys=True))
    assert bank(c)==m['bank']
    (root/'diagnosis.json').write_text(json.dumps([list(r) for r in c.execute('SELECT * FROM diagnosis ORDER BY id')]))
    sehat(c)
print('OSN_QUESTION_RECOVERY_OK')
'''
SUMBER_KEMBALI = "import os\nos.environ.pop('OSN_TEORI_BILANGAN_VERSI',None)\n" + BERSAMA + r'''
from number_theory_versions import versi_writer
assert versi_writer()==2, 'return_writer_bukan_batch_baru'
os.environ['OSN_BANK_KALIMAT']='0'
m=baca_manifest()
with database.buka(path) as c:
    periksa(c,m)
    assert bukti(c)==json.loads((root/'bukti-recovery.json').read_text()), 'bukti_return_berubah'
    assert [list(r) for r in c.execute('SELECT * FROM diagnosis ORDER BY id')]==json.loads((root/'diagnosis.json').read_text())
    assert set(jenis)<={s.template_id for s in buat_lembar(42,level='P4',topik='teori-bilangan').soal}
print('OSN_QUESTION_RETURN_OK')
'''
