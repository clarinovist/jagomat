"""Penulis sesi pilot homogen; caller layanan sudah mengotorisasi dan memvalidasi state."""
from dataclasses import replace
import json

import database
import presentation_lock
import question_views
from generator import buat_soal
from skill_pilot import KonteksPilot, sidik_variasi
from skill_pilot_contract import ButirKontrakPilot, KontrakPilot, serialisasi, fingerprint
from skill_pilot_selector import pilih_probe
from skill_pilot_store import baca_kontrak
from visual_contract import buat_penyajian
from topic_plane_geometry_visual import proyeksi_geometri_datar


def penyajian(soal, mode):
    teks, descriptor = soal.teks, None
    if mode == 'geometri_datar-v1':
        teks, descriptor = proyeksi_geometri_datar(soal.template_id, soal.parameter)
    return buat_penyajian(template_id=soal.template_id,level=soal.level,parameter=soal.parameter,
        teks_soal=teks,bagian_soal=soal.bagian,tantangan_soal=soal.tantangan,
        minta_restatement=soal.minta_restatement,asal_teks='bawaan',
        status_visual='siap' if descriptor else 'tanpa_visual',mode_representasi=mode,descriptor=descriptor)


def buat_sesi(kon, siswa_id, putaran_id, konteks, rencana, *, seed, kunci, sumber=()):
    """Simpan soal, target, envelope, marker dan freeze dalam satu savepoint."""
    from skill_pilot_store import validasi_konfirmasi
    if type(konteks) is not KonteksPilot:
        raise ValueError('konteks penulis pilot tidak sah')
    asal=kon.execute('SELECT pf.siswa_id,pp.konteks_json FROM pilot_putaran pp JOIN putaran_fokus pf ON pf.id=pp.putaran_id WHERE pf.id=?',(putaran_id,)).fetchone()
    if asal is None or asal['siswa_id']!=siswa_id or KonteksPilot(**json.loads(asal['konteks_json']))!=konteks:
        raise ValueError('putaran sumber bukan milik siswa/konteks')
    for kh in sumber:
        ss=kon.execute('''SELECT s.id,s.siswa_id,s.dibatalkan,s.dikonfirmasi_guru,s.fingerprint_konfirmasi,kh.fingerprint
              FROM konfirmasi_hasil kh JOIN sesi s ON s.id=kh.sesi_id WHERE kh.id=?''',(kh,)).fetchone()
        if ss is None or ss['siswa_id']!=siswa_id or ss['dibatalkan'] is not None or not ss['dikonfirmasi_guru'] or ss['fingerprint_konfirmasi']!=ss['fingerprint']:
            raise ValueError('konfirmasi sumber tidak lagi aktif')
        validasi_konfirmasi(kon,ss['id'],siswa_id,kh)
    lama=kon.execute('SELECT id FROM sesi WHERE siswa_id=? AND kunci_idempotensi=? AND dibatalkan IS NULL',
                     (siswa_id,kunci)).fetchone()
    if lama:
        baca_kontrak(kon,lama['id'],siswa_id)
        return lama['id']
    tujuan=rencana.tindakan
    if tujuan not in ('pemetaan','pengenalan','latihan_terbimbing','penguatan','evaluasi','checkpoint'):
        raise ValueError('tahap pilot tidak membuat sesi')
    fokus=rencana.kandidat
    jumlah=4 if tujuan in ('pemetaan','evaluasi') else 1 if tujuan in ('pengenalan','latihan_terbimbing') else 10
    if tujuan=='checkpoint': jumlah=2 if rencana.bagian_checkpoint==1 else 1
    per_fokus=fokus or (None,)
    if len(fokus)>2: raise ValueError('maksimal dua fokus')
    lama=[]
    for row in kon.execute('''SELECT so.template_id,so.parameter,so.level FROM sesi_soal ss
         JOIN soal so ON so.id=ss.soal_id JOIN sesi s ON s.id=ss.sesi_id
         WHERE s.siswa_id=? AND so.template_id=? AND so.level=?''',
         (siswa_id,konteks.template_id,konteks.profil_parameter)):
        try: lama.append(sidik_variasi(konteks,row['template_id'],json.loads(row['parameter'])))
        except ValueError: pass  # varian lain tidak pernah menjadi probe tuntutan ini
    # Contoh materi tidak menjadi probe baru.
    for parameter in ({'varian':'keliling','p':8,'l':3},{'varian':'balik_luas','p':8,'K':22},
                      {'p':8,'l':3,'satuan':'cm','konteks':'ubin'}):
        try: lama.append(sidik_variasi(konteks,konteks.template_id,parameter))
        except ValueError: pass
    probe=[]
    for fokus_satu in per_fokus:
        bagian=pilih_probe(konteks,seed+len(probe)*41,jumlah,
                          sidik_terpakai=tuple(set(lama)),fokus=fokus_satu)
        probe.extend(bagian); lama.extend(p.sidik_variasi for p in bagian)
    soal=[replace(b.soal,penyajian=penyajian(b.soal,konteks.mode_representasi)) for b in probe]
    # Pembanding tidak memiliki konteks pilot/target fokus dan tidak masuk kuota.
    if tujuan in ('evaluasi','checkpoint'):
        from learning_sessions import _template_lintas_topik
        for n,tid in enumerate(_template_lintas_topik(konteks.profil_parameter,10-len(soal),(konteks.template_id,))):
            soal.append(buat_soal(tid,seed+100+n,konteks.profil_parameter,__import__('topics').pemilik_template(tid)))
    kon.execute('SAVEPOINT tulis_pilot')
    try:
        from topics import paket_untuk_template
        urutan=tuple(s.template_id for s in soal)
        sid=database.buat_sesi_dari_urutan(kon,siswa_id,seed,urutan,
                level=konteks.profil_parameter,topik=paket_untuk_template(urutan),
                soal_terpilih=tuple(soal),mode='diagnostik')
        kon.execute('UPDATE sesi SET tujuan=?,putaran_id=?,bagian_checkpoint=?,kunci_idempotensi=? WHERE id=?',
                    (tujuan,putaran_id,rencana.bagian_checkpoint,kunci,sid))
        baris=kon.execute('''SELECT ss.*,so.template_id,so.parameter,so.level,so.cerita
            FROM sesi_soal ss JOIN soal so ON so.id=ss.soal_id WHERE ss.sesi_id=? ORDER BY nomor''',(sid,)).fetchall()
        butir=[]; target={}
        for i,b in enumerate(baris):
            pro=probe[i] if i<len(probe) else None
            snapshot=question_views.penyajian_dari_baris(b)
            if pro:
                snapshot=penyajian(pro.soal,konteks.mode_representasi)
                if not presentation_lock.perbarui_snapshot(kon,b['id'],b['fingerprint_penyajian'],snapshot):
                    raise ValueError('Penyajian pilot tidak dapat dibekukan.')
            butir.append(ButirKontrakPilot(b['nomor'],b['id'],konteks if pro else None,
                         pro.sidik_variasi if pro else None,
                         snapshot.fingerprint_penyajian,
                         pro.target_fokus if pro else None))
            if pro and pro.target_fokus: target[str(b['nomor'])]=list(pro.target_fokus)
        kontrak=KontrakPilot(siswa_id,sid,konteks.profil_parameter,probe[0].versi_generator,
                            tuple(butir),seed=seed,tujuan=tujuan,putaran_id=putaran_id,
                            sumber_konfirmasi=tuple(sorted(set(sumber))))
        kon.execute('INSERT INTO pilot_sesi VALUES(?,?,?,?)',(sid,1,serialisasi(kontrak),fingerprint(kontrak)))
        data={'tindakan':tujuan,'fokus':[list(f) for f in fokus],'target_per_nomor':target,
              'occurrence':_occurrence(kon,putaran_id,tujuan,rencana.bagian_checkpoint)}
        kon.execute("INSERT INTO kejadian_belajar(siswa_id,putaran_id,sesi_id,jenis,data) VALUES(?,?,?,'sesi_dibuat',?)",
                    (siswa_id,putaran_id,sid,json.dumps(data,sort_keys=True)))
        presentation_lock.bekukan_penyajian(kon,sid)
        baca_kontrak(kon,sid,siswa_id)
        kon.execute('RELEASE SAVEPOINT tulis_pilot')
        return sid
    except Exception:
        kon.execute('ROLLBACK TO SAVEPOINT tulis_pilot'); kon.execute('RELEASE SAVEPOINT tulis_pilot'); raise


def _occurrence(kon,putaran_id,tujuan,bagian):
    return 1+kon.execute('''SELECT count(*) FROM sesi WHERE putaran_id=? AND tujuan=?
        AND bagian_checkpoint IS ? AND dikonfirmasi_guru IS NOT NULL AND dibatalkan IS NULL''',
        (putaran_id,tujuan,bagian)).fetchone()[0]
