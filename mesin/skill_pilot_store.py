"""Reader dua versi pilot/v1 dan arsip konfirmasi terikat fingerprint.

Tidak backfill. Tanpa marker pilot adalah histori v1, bukan tuntutan yang boleh
direka dari parameter. Caller tetap wajib mengotorisasi keluarga sebelum query.
"""
import hashlib
import json

import question_views
from skill_pilot import sidik_variasi
from skill_pilot_contract import deserialisasi, fingerprint, serialisasi


def daftar_pilot(kon, siswa_id):
    """Metadata operasional saja; aman tanpa membaca diagnosis/kunci anak."""
    tabel = {b[0] for b in kon.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    sesi = set() if 'pilot_sesi' not in tabel else {b[0] for b in kon.execute(
        'SELECT ps.sesi_id FROM pilot_sesi ps JOIN sesi s ON s.id=ps.sesi_id WHERE s.siswa_id=?', (siswa_id,))}
    putaran = set() if 'pilot_putaran' not in tabel else {b[0] for b in kon.execute(
        'SELECT pp.putaran_id FROM pilot_putaran pp JOIN putaran_fokus pf ON pf.id=pp.putaran_id WHERE pf.siswa_id=?', (siswa_id,))}
    return sesi, putaran


def bungkus_konfirmasi(hasil, kontrak):
    """V1 byte-identik; hanya sesi pilot baru mengikat kontrak dalam sidik."""
    if kontrak is None:
        return hasil
    return {'hasil': hasil, 'pilot': json.loads(serialisasi(kontrak))}


def arsipkan_konfirmasi(kon, kontrak, konfirmasi_id):
    if kontrak is not None:
        kon.execute('INSERT INTO pilot_konfirmasi VALUES(?,?,?,?)',
                    (konfirmasi_id, kontrak.sesi_id, serialisasi(kontrak), fingerprint(kontrak)))


def baca_kontrak(kon,sesi_id,siswa_id):
    """Baca saja dan cocokkan seluruh butir dengan sumber penyajian beku."""
    sesi=kon.execute("SELECT siswa_id,level,seed,tujuan,putaran_id FROM sesi WHERE id=?",(sesi_id,)).fetchone()
    if sesi is None or sesi["siswa_id"]!=siswa_id:
        raise ValueError("sesi bukan milik siswa")
    if kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pilot_sesi'").fetchone() is None:
        return None
    baris=kon.execute("SELECT * FROM pilot_sesi WHERE sesi_id=?",(sesi_id,)).fetchone()
    if baris is None:
        if sesi['putaran_id'] is not None and kon.execute(
                'SELECT 1 FROM pilot_putaran WHERE putaran_id=?',(sesi['putaran_id'],)).fetchone():
            raise ValueError('Kontrak sesi pilot hilang; histori tidak ditafsir ulang sebagai v1.')
        return None
    if baris["versi"]!=1: raise ValueError("versi pilot tidak dikenal")
    kontrak=deserialisasi(baris["kontrak_json"])
    if (kontrak.sesi_id!=sesi_id or kontrak.siswa_id!=siswa_id
            or kontrak.profil_parameter!=sesi["level"] or fingerprint(kontrak)!=baris["fingerprint"]):
        raise ValueError("identitas kontrak pilot tidak cocok")
    if kontrak.seed is None or (kontrak.seed!=sesi['seed'] or kontrak.tujuan!=sesi['tujuan']
            or kontrak.putaran_id!=sesi['putaran_id']):
        raise ValueError('envelope sesi pilot berubah')
    if kontrak.putaran_id is not None:
        pp=kon.execute('SELECT konteks_json FROM pilot_putaran WHERE putaran_id=?',(kontrak.putaran_id,)).fetchone()
        from skill_pilot import KonteksPilot
        konteks_putaran=KonteksPilot(**json.loads(pp[0])) if pp else None
        if konteks_putaran is None or any(b.konteks is not None and b.konteks!=konteks_putaran for b in kontrak.butir):
            raise ValueError('konteks sesi tidak cocok putaran sumber')
    for khid in kontrak.sumber_konfirmasi:
        asal=kon.execute('''SELECT s.siswa_id FROM konfirmasi_hasil kh JOIN sesi s ON s.id=kh.sesi_id WHERE kh.id=?''',(khid,)).fetchone()
        if asal is None or asal['siswa_id']!=siswa_id:
            raise ValueError('rujukan konfirmasi bukan milik siswa')
    if kontrak.putaran_id is not None:
        event=kon.execute("SELECT data FROM kejadian_belajar WHERE sesi_id=? AND jenis='sesi_dibuat' ORDER BY id DESC LIMIT 1",(sesi_id,)).fetchone()
        if event is None: raise ValueError('event sesi pilot hilang')
        isi=json.loads(event[0])
        target={str(b.nomor):list(b.target_fokus) for b in kontrak.butir if b.target_fokus is not None}
        if isi.get('target_per_nomor')!=target or isi.get('tindakan')!=kontrak.tujuan:
            raise ValueError('target sesi pilot berubah dari sumber')
    sumber=kon.execute("""SELECT ss.*,so.template_id,so.parameter,so.level,so.cerita
         FROM sesi_soal ss JOIN soal so ON so.id=ss.soal_id WHERE ss.sesi_id=? ORDER BY ss.nomor""",
         (sesi_id,)).fetchall()
    if len(sumber)!=len(kontrak.butir): raise ValueError("butir kontrak pilot tidak lengkap")
    for b,s in zip(kontrak.butir,sumber):
        penyajian=question_views.penyajian_dari_baris(s)
        if (b.sesi_soal_id!=s["id"] or b.nomor!=s["nomor"] or s["level"]!=kontrak.profil_parameter
                or b.fingerprint_penyajian!=penyajian.fingerprint_penyajian):
            raise ValueError("butir sumber pilot tidak cocok")
        if b.konteks is not None:
            if (b.konteks.mode_representasi!=penyajian.mode_representasi
                    or sidik_variasi(b.konteks,s["template_id"],json.loads(s["parameter"]))!=b.sidik_variasi):
                raise ValueError("tuntutan atau variasi sumber pilot tidak cocok")
    return kontrak


def muat_bukti(kon, siswa_id):
    """Perkaya hanya kontrak pilot dan rujukan kisiP3 dengan sumber sah.

    Bukti kisi lama adalah rujukan terbatas, bukan histori yang di-retag sebagai
    tuntutan baru. Adapter laporan existing memeriksa outcome/provenance dahulu.
    """
    import database
    import review_store
    from mastery_evidence import lengkapi_bukti_materi
    from skill_pilot import KonteksPilot, PRASYARAT, POLA_KISI
    from skill_pilot_evidence import BuktiPilot, ButirBuktiPilot, FokusBuktiPilot, SumberFokusDicabut
    bukti=lengkapi_bukti_materi(kon,database.muat_bukti_siklus(kon,siswa_id, validasi_pilot=False))
    butir=[]
    fokus=[]
    masalah=[]
    for s in bukti.sesi:
        if s.konfirmasi_id is not None:
            outcome=database.isi_sesi(kon,s.id)
            lewat={b['sesi_soal_id'] for b in kon.execute(
                'SELECT sesi_soal_id FROM snapshot_outcome WHERE konfirmasi_id=? AND dilewati=1',
                (s.konfirmasi_id,))}
            tinjauan=review_store.validasi_bukti(kon,s.id,outcome,lewat)
            arsip=kon.execute('SELECT data_json FROM tinjauan_outcome WHERE konfirmasi_id=?',
                              (s.konfirmasi_id,)).fetchone()
            if (arsip is None and tinjauan) or (arsip is not None and json.loads(arsip[0])!=tinjauan):
                raise ValueError('provenance pilot tidak cocok konfirmasi aktif')
        kontrak=(validasi_konfirmasi(kon,s.id,siswa_id,s.konfirmasi_id)
                 if s.konfirmasi_id is not None else baca_kontrak(kon,s.id,siswa_id))
        if kontrak is not None:
            butir.extend(ButirBuktiPilot(s.id,b.nomor,s.konfirmasi_id,b.konteks,b.sidik_variasi)
                         for b in kontrak.butir if b.konteks is not None)
            continue
        if s.level!='P3' or s.mode!='diagnostik' or s.format_jawaban!='isian' or s.tujuan not in ('bebas','pemetaan','evaluasi','checkpoint'):
            continue
        if s.tujuan=='bebas' and not any(e.jenis=='sertakan_pemetaan' and e.sesi_id==s.id for e in bukti.kejadian):
            continue  # Latihan manual tanpa opt-in bukan bukti/prasyarat pilot.
        sumber=kon.execute('''SELECT ss.*,so.template_id,so.parameter,so.level,so.cerita FROM sesi_soal ss
            JOIN soal so ON so.id=ss.soal_id WHERE ss.sesi_id=? AND so.template_id=?''',
            (s.id,POLA_KISI)).fetchall()
        for baris in sumber:
            n=baris['nomor']
            # Simpan konteks sumber juga ketika konfirmasi dicabut agar reducer
            # tidak diam-diam memilih keberhasilan lebih lama sebagai pengganti.
            penyajian=question_views.penyajian_dari_baris(baris)
            if not baris['fingerprint_matematis'] or not baris['fingerprint_penyajian']:
                # Jangan memilih keberhasilan lebih tua ketika sumber terbaru
                # tidak dapat diverifikasi. Histori tetap dapat dibaca via v1.
                raise ValueError('Rujukan luas belum dapat diverifikasi; gunakan probe baru.')
            k=KonteksPilot(PRASYARAT,'P3',penyajian.mode_representasi)
            butir.append(ButirBuktiPilot(s.id,n,s.konfirmasi_id,k,
                sidik_variasi(k,POLA_KISI,json.loads(baris['parameter']))))
    # Fokus terikat konteks dan snapshot sumber, bukan diagnosis mutable.
    if kon.execute("SELECT 1 FROM sqlite_master WHERE name='pilot_putaran' AND type='table'").fetchone():
        for row in kon.execute('''SELECT pp.* FROM pilot_putaran pp JOIN putaran_fokus pf
            ON pf.id=pp.putaran_id WHERE pf.siswa_id=?''',(siswa_id,)):
            isi=json.loads(row['konteks_json'])
            if type(isi) is not dict or set(isi)!={'tuntutan_id','profil_parameter','mode_representasi','versi_rubrik'}:
                raise ValueError('konteks putaran pilot tidak sah')
            k=KonteksPilot(**isi)
            putaran=next(p for p in bukti.putaran if p.id==row['putaran_id'])
            dicabut=set()
            for f in putaran.fokus:
                sumber=kon.execute('''SELECT pfs.konfirmasi_id,kh.sesi_id,s.dikonfirmasi_guru,s.dibatalkan,s.fingerprint_konfirmasi,kh.fingerprint
                    FROM anggota_fokus af JOIN pilot_fokus_sumber pfs ON pfs.anggota_id=af.id
                    JOIN konfirmasi_hasil kh ON kh.id=pfs.konfirmasi_id JOIN sesi s ON s.id=kh.sesi_id
                    WHERE af.putaran_id=? AND af.template_id=? AND af.kode_intervensi=? AND af.malrule_id_kanonis=?''',
                    (putaran.id,f[0],f[1],f[2] or '')).fetchall()
                if len(sumber)<2:
                    raise ValueError('Sumber fokus pilot belum lengkap; metadata perlu diperiksa.')
                for s in sumber:
                    kontrak_sumber=validasi_konfirmasi(kon,s['sesi_id'],siswa_id,s['konfirmasi_id'])
                    if kontrak_sumber is None or not any(b.konteks==k for b in kontrak_sumber.butir):
                        raise ValueError('Sumber fokus tidak cocok tuntutan')
                    # Periksa diagnosis snapshot sumber, bukan versi mutablenya.
                    cocok=kon.execute('''SELECT 1 FROM snapshot_outcome WHERE konfirmasi_id=?
                        AND template_id=? AND dilewati=0 AND
                        ((kode_final=? AND malrule_id IS ?) OR
                         (?='K' AND kode_final='N' AND cek_pemahaman IN ('ragu','menghafal') AND malrule_id IS ?))''',
                        (s['konfirmasi_id'],f[0],f[1],f[2],f[1],f[2])).fetchone()
                    if cocok is None:
                        raise ValueError('Sumber fokus tidak memiliki diagnosis yang cocok')
                    aktif=kon.execute('''SELECT id FROM konfirmasi_hasil WHERE sesi_id=?
                        AND fingerprint=? ORDER BY nomor_urut DESC,id DESC LIMIT 1''',
                        (s['sesi_id'],s['fingerprint_konfirmasi'])).fetchone()
                    if (s['dibatalkan'] is not None or not s['dikonfirmasi_guru']
                            or aktif is None or aktif['id']!=s['konfirmasi_id']):
                        dicabut.add(s['sesi_id'])
                fokus.append(FokusBuktiPilot(putaran.id,f,k))
            if dicabut:
                masalah.append(SumberFokusDicabut(putaran.id,k,tuple(sorted(dicabut))))
    return BuktiPilot(bukti,tuple(butir),tuple(fokus),tuple(masalah))


def validasi_konfirmasi(kon,sesi_id,siswa_id,konfirmasi_id):
    """Arsip pilot harus identik sumber dan terikat snapshot yang diminta."""
    kontrak=baca_kontrak(kon,sesi_id,siswa_id)
    if kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pilot_konfirmasi'").fetchone() is None:
        if kontrak is not None: raise ValueError("arsip pilot belum tersedia")
        return None
    arsip=kon.execute("SELECT * FROM pilot_konfirmasi WHERE konfirmasi_id=?",(konfirmasi_id,)).fetchone()
    if kontrak is None:
        if arsip is not None: raise ValueError("arsip pilot tanpa sumber")
        return None
    if (arsip is None or arsip["sesi_id"]!=sesi_id or arsip["fingerprint"]!=fingerprint(kontrak)
            or deserialisasi(arsip["kontrak_json"])!=kontrak):
        raise ValueError("arsip konfirmasi pilot tidak cocok")
    kh=kon.execute("SELECT sesi_id,fingerprint FROM konfirmasi_hasil WHERE id=?",(konfirmasi_id,)).fetchone()
    if kh is None or kh["sesi_id"]!=sesi_id: raise ValueError("konfirmasi bukan sumber pilot")
    outcome=kon.execute("SELECT * FROM snapshot_outcome WHERE konfirmasi_id=? ORDER BY nomor",(konfirmasi_id,)).fetchall()
    if len(outcome)!=len(kontrak.butir): raise ValueError("outcome pilot tidak lengkap")
    for o,b in zip(outcome,kontrak.butir):
        target=None if o["target_template_id"] is None else (o["target_template_id"],o["target_kode_intervensi"],o["target_malrule_id"])
        if (o["sesi_soal_id"]!=b.sesi_soal_id or o["nomor"]!=b.nomor
                or o["level_efektif"]!=kontrak.profil_parameter or target!=b.target_fokus
                or (b.konteks is not None and o["template_id"]!=b.konteks.template_id)):
            raise ValueError("outcome pilot tidak cocok sumber")
    kolom = ('nomor','template_id','jawaban','benar','kode_final','malrule_id','dilewati',
             'level_efektif','cek_pemahaman','target_template_id','target_kode_intervensi','target_malrule_id')
    hasil = [{k:o[k] for k in kolom} for o in outcome]
    tinjauan = kon.execute('SELECT data_json FROM tinjauan_outcome WHERE konfirmasi_id=?', (konfirmasi_id,)).fetchone()
    if tinjauan is not None:
        hasil = {'outcome':hasil, 'tinjauan':json.loads(tinjauan[0])}
    sidik = hashlib.sha256(json.dumps(bungkus_konfirmasi(hasil,kontrak), ensure_ascii=False,
                             sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if sidik != kh['fingerprint']:
        raise ValueError('fingerprint konfirmasi tidak mengikat kontrak pilot')
    return kontrak
