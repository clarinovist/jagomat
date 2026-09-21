"""Transaksi orang tua untuk pilot; tidak menerima tahap atau kuota dari form."""
from dataclasses import asdict
import hashlib
import json
import random
import domain_clock

import database
import learning_cycle as lc
from skill_pilot import KonteksPilot, LANGSUNG, BALIK, PRASYARAT
from skill_pilot_store import muat_bukti, baca_kontrak
from skill_pilot_materials import pilihan_materi


def daftar_putaran(kon,siswa_id):
    hasil=[]
    for b in kon.execute('''SELECT pp.* FROM pilot_putaran pp JOIN putaran_fokus pf
          ON pf.id=pp.putaran_id WHERE pf.siswa_id=?
          AND NOT EXISTS (SELECT 1 FROM kejadian_belajar kb WHERE kb.putaran_id=pf.id
              AND kb.jenis IN ('putaran_ditutup','override_ditutup','diganti_level')) ORDER BY pp.putaran_id''',(siswa_id,)):
        hasil.append((b['putaran_id'],KonteksPilot(**json.loads(b['konteks_json']))))
    return tuple(hasil)


def keadaan(kon,siswa_id,hari=None):
    paket=muat_bukti(kon,siswa_id)
    putaran=daftar_putaran(kon,siswa_id)
    rencana=tuple((pid,k,*lc.rencana_pilot(paket,siswa_id,k,pid,hari)) for pid,k in putaran)
    aktif=lc.pilih_rencana_pilot(rencana)
    return paket, rencana, aktif, lc.prioritas_warisan(paket.bukti,hari)


def revisi(kon,siswa_id):
    """CAS atas state relevan, bukan hash tampilan; tidak mengandung data ke AI."""
    tabel=(('sesi','siswa_id'),('putaran_fokus','siswa_id'),('kejadian_belajar','siswa_id'))
    isi=[]
    for nama,kolom in tabel:
        isi.append([tuple(b) for b in kon.execute('SELECT * FROM '+nama+' WHERE '+kolom+'=? ORDER BY id',(siswa_id,))])
    return hashlib.sha256(json.dumps(isi,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _sumber_balik(paket,siswa_id,konteks,hari):
    kandidat=tuple(dict.fromkeys(b.konteks for b in paket.butir
                  if b.konteks.tuntutan_id==LANGSUNG and b.konteks.mode_representasi==konteks.mode_representasi))
    kisi=KonteksPilot(PRASYARAT,'P3',konteks.mode_representasi)
    for langsung in kandidat:
        if lc.tawaran_probe_balik(paket,siswa_id,langsung,kisi,hari):
            hasil=lc.penguasaan_pilot(paket,siswa_id,(langsung,kisi),hari)
            ids={i for h in hasil for i in h.hasil.sesi_ids}
            return tuple(s.konfirmasi_id for s in paket.bukti.sesi if s.id in ids)
    raise ValueError('Bukti keliling langsung dan rujukan luas yang sah belum tersedia. Periksa prasyarat dahulu.')


def jalankan(kon,siswa_id,data,*,hari=None):
    """Dipanggil HTTP setelah owner guard; transaksi bersifat gagal atomik."""
    hari=hari or domain_clock.hari_wib()
    if set(data)-{'aksi','revisi','tuntutan','profil','representasi','belum_dikenal','konfirmasi_pemulihan'}:
        raise ValueError('Isian pilot tidak dikenal.')
    if data.get('aksi') not in ('mulai','lanjut','pelajari','putaran_baru','pulihkan_sumber'):
        raise ValueError('Aksi pilot tidak dikenal.')
    if data.get('aksi')=='pulihkan_sumber' and data.get('konfirmasi_pemulihan')!='1':
        raise ValueError('Berikan konfirmasi penutupan putaran dan pembatalan sesi.')
    if not data.get('revisi') or len(data['revisi'])!=64:
        raise ValueError('Muat ulang rencana pilot.')
    kon.execute('SAVEPOINT aksi_pilot')
    try:
        # Receipt retry terikat request; stale berbeda tidak menjadi request baru.
        kunci=hashlib.sha256(json.dumps([siswa_id,sorted(data.items())],separators=(',',':')).encode()).hexdigest()
        receipt=kon.execute('SELECT tujuan FROM pilot_aksi WHERE kunci=? AND siswa_id=?',(kunci,siswa_id)).fetchone()
        if receipt:
            if receipt[0].startswith('/sesi/'):
                sid=int(receipt[0].split('/')[-1])
                sesi=kon.execute('SELECT dibatalkan FROM sesi WHERE id=? AND siswa_id=?',(sid,siswa_id)).fetchone()
                if sesi is None or sesi['dibatalkan'] is not None:
                    raise ValueError('Sesi hasil aksi sudah dibatalkan; muat ulang rencana.')
                baca_kontrak(kon,sid,siswa_id)
            kon.execute('RELEASE SAVEPOINT aksi_pilot'); return receipt[0]
        if data['revisi']!=revisi(kon,siswa_id): raise ValueError('Rencana berubah; muat ulang sebelum melanjutkan.')
        paket,rencana,aktif,warisan=keadaan(kon,siswa_id,hari)
        if warisan is not None: raise ValueError('Selesaikan langkah rencana yang sedang diprioritaskan dahulu.')
        if data['aksi']=='mulai':
            if not lc.boleh_mulai_pilot(paket,siswa_id,rencana,hari):
                raise ValueError('Selesaikan langkah pilot yang sedang berjalan dahulu.')
            k=KonteksPilot(data.get('tuntutan'),data.get('profil'),data.get('representasi'))
            if data.get('belum_dikenal','') not in ('','1'): raise ValueError('Pilihan pengenalan tidak sah.')
            if any(x[1]==k for x in rencana): raise ValueError('Konteks ini sudah memiliki rencana pilot.')
            sumber=_sumber_balik(paket,siswa_id,k,hari) if k.tuntutan_id==BALIK else ()
            pid=database.buat_putaran_fokus(kon,siswa_id,k.profil_parameter)
            kon.execute('INSERT INTO pilot_putaran VALUES(?,?)',(pid,json.dumps(asdict(k),sort_keys=True)))
            if data.get('belum_dikenal')=='1':
                kon.execute("INSERT INTO kejadian_belajar(siswa_id,putaran_id,jenis,data) VALUES(?,?,'pilot_belum_dikenal','{}')",(siswa_id,pid))
            tindakan='pengenalan' if data.get('belum_dikenal')=='1' else 'pemetaan'
            langkah=lc.RencanaBelajar(tindakan,'Keputusan orang tua untuk memulai pilot.')
        else:
            field={'aksi','revisi','konfirmasi_pemulihan'} if data['aksi']=='pulihkan_sumber' else {'aksi','revisi'}
            if set(data)!=field or aktif is None: raise ValueError('Aksi lanjutan tidak sesuai rencana.')
            pid,k,langkah,_=aktif
            sumber=tuple(s.konfirmasi_id for s in paket.bukti.sesi
                         if s.putaran_id==pid and s.konfirmasi_id is not None and s.dibatalkan is None)
        if data['aksi']=='pulihkan_sumber' or langkah.tindakan=='pulihkan_sumber':
            if data['aksi']!='pulihkan_sumber' or langkah.tindakan!='pulihkan_sumber':
                raise ValueError('Pemulihan hanya untuk putaran dengan sumber yang perlu ditinjau.')
            sumber_lama=[m for m in lc.sumber_pilot_perlu_tinjauan(paket) if m.putaran_id==pid]
            if not sumber_lama: raise ValueError('Sumber putaran tidak memerlukan pemulihan.')
            kon.execute("INSERT INTO kejadian_belajar(siswa_id,putaran_id,jenis,data) VALUES(?,?,'putaran_ditutup',?)",
                        (siswa_id,pid,json.dumps({'alasan':'sumber_pilot_dicabut',
                            'sesi_sumber':sorted({sid for m in sumber_lama for sid in m.sesi_ids})},sort_keys=True)))
            sesi_lama=kon.execute('SELECT id FROM sesi WHERE siswa_id=? AND putaran_id=? AND dibatalkan IS NULL',
                                  (siswa_id,pid)).fetchall()
            for s in sesi_lama:
                database.batalkan_sesi(kon,s['id'],'Putaran pilot ditutup setelah sumber fokus dicabut.')
            tujuan='/anak/%d?section=rencana'%siswa_id
        elif langkah.tindakan in ('lanjutkan_sesi','konfirmasi_hasil'):
            tujuan='/sesi/%d'%langkah.sesi_id
        elif langkah.tindakan=='putaran_baru':
            if data['aksi']!='putaran_baru': raise ValueError('Pembukaan putaran penguatan perlu keputusan eksplisit.')
            fokus=tuple(f.kunci for f in langkah.putaran.fokus)
            from skill_pilot_evidence import proyeksi_bukti
            proyeksi=proyeksi_bukti(paket,k)
            kon.execute("INSERT INTO kejadian_belajar(siswa_id,putaran_id,jenis,data) VALUES(?,?,'putaran_ditutup','{}')",(siswa_id,pid))
            pid_baru=database.buat_putaran_fokus(kon,siswa_id,k.profil_parameter)
            kon.execute('INSERT INTO pilot_putaran VALUES(?,?)',(pid_baru,json.dumps(asdict(k),sort_keys=True)))
            for f in fokus:
                sah=[s for s in proyeksi.sesi if s.konfirmasi_id is not None and s.dibatalkan is None
                     and any(lc._kunci_outcome(o)==f for o in s.outcomes)]
                if not sah: raise ValueError('Bukti kekambuhan fokus belum tersedia.')
                anggota=database.tambah_anggota_fokus(kon,pid_baru,*f,[s.id for s in sah],izinkan_provenance_historis=True)
                for s in sah: kon.execute('INSERT INTO pilot_fokus_sumber VALUES(?,?)',(anggota,s.konfirmasi_id))
            tujuan='/anak/%d?section=rencana'%siswa_id
        elif langkah.tindakan=='intervensi':
            if data['aksi']!='pelajari': raise ValueError('Pelajari materi bersama terlebih dahulu.')
            fokus=langkah.kandidat or tuple(f.kunci for f in langkah.putaran.fokus)
            if len(fokus)>2: raise ValueError('Maksimal dua fokus.')
            for f in fokus:
                ada=kon.execute('SELECT 1 FROM anggota_fokus WHERE putaran_id=? AND template_id=? AND kode_intervensi=? AND malrule_id_kanonis=?',(pid,*f[:2],f[2] or '')).fetchone()
                if not ada:
                    from skill_pilot_evidence import proyeksi_bukti
                    proyeksi=proyeksi_bukti(paket,k)
                    sah=[s for s in proyeksi.sesi if s.putaran_id==pid and s.konfirmasi_id in sumber
                         and s.tujuan=='pemetaan' and s.dibatalkan is None
                         and any(lc._kunci_outcome(o)==f for o in s.outcomes)]
                    if len({s.id for s in sah})<2:
                        raise ValueError('Fokus belum memiliki dua sumber konfirmasi yang cocok.')
                    anggota=database.tambah_anggota_fokus(kon,pid,*f,[s.id for s in sah])
                    for s in sah:
                        kon.execute('INSERT INTO pilot_fokus_sumber VALUES(?,?)',(anggota,s.konfirmasi_id))
                pilihan=pilihan_materi(k,f)
                status=next((x for x in langkah.putaran.fokus if x.kunci==f),None)
                materi=next((x for x in pilihan if status and x.pendekatan_id==status.pendekatan_berikutnya),pilihan[0])
                kon.execute("INSERT INTO kejadian_belajar(siswa_id,putaran_id,jenis,data) VALUES(?,?,'intervensi_selesai',?)",
                            (siswa_id,pid,json.dumps({'fokus':list(f),'pendekatan_id':materi.pendekatan_id,'sumber_konfirmasi':sumber},sort_keys=True)))
            tujuan='/anak/%d?section=rencana'%siswa_id
        else:
            if data['aksi'] not in ('lanjut','mulai'): raise ValueError('Aksi tidak sesuai tahap pilot.')
            from skill_pilot_sessions import buat_sesi
            sid=buat_sesi(kon,siswa_id,pid,k,langkah,seed=random.SystemRandom().randint(1,9999999),kunci=kunci,sumber=sumber)
            tujuan='/sesi/%d'%sid
        kon.execute('INSERT INTO pilot_aksi VALUES(?,?,?)',(kunci,siswa_id,tujuan))
        kon.execute('RELEASE SAVEPOINT aksi_pilot'); return tujuan
    except Exception:
        kon.execute('ROLLBACK TO SAVEPOINT aksi_pilot'); kon.execute('RELEASE SAVEPOINT aksi_pilot'); raise
