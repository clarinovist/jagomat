"""Probe fokus berprovenance dan pemulihan non-destruktif lintas image."""
SUMBER_BANTU = r'''
import json,sqlite3
from pathlib import Path
from datetime import date
import database
from skill_pilot import LANGSUNG
from skill_pilot_service import jalankan,revisi,keadaan
from skill_pilot_store import baca_kontrak
p_fokus=Path('/data/focus-pair.db')
def aksi_fokus(kon,siswa,aksi,hari,**lain):
    return jalankan(kon,siswa,{'aksi':aksi,'revisi':revisi(kon,siswa),**lain},hari=date.fromisoformat(hari))
def konfirmasi_fokus(kon,sid,hari,salah=False):
    kon.execute('UPDATE sesi SET tanggal=? WHERE id=?',(hari,sid))
    for b in database.isi_sesi(kon,sid):
        jid=database.simpan_jawaban(kon,b['sesi_soal_id'],'0' if salah else b['kunci'])
        database.simpan_diagnosis(kon,jid,not salah,'K' if salah else None,
            'K' if salah else None,'datar.lupa_kali_dua' if salah else None)
    database.tandai_selesai(kon,sid)
    kh=database.konfirmasi_hasil(kon,sid,'guru',cek_pemahaman={b['sesi_soal_id']:'bisa_menjelaskan' for b in database.isi_sesi(kon,sid)})
    kon.execute('UPDATE sesi SET selesai=?,dikonfirmasi_guru=? WHERE id=?',(hari,hari,sid))
    return kh
TABEL_FOKUS=('pilot_fokus_sumber','anggota_fokus','konfirmasi_hasil','snapshot_outcome',
    'pilot_sesi','pilot_putaran','pilot_konfirmasi','konteks_konfirmasi','kejadian_belajar')
def arsip_fokus(kon):
    return {t:[list(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in TABEL_FOKUS}
'''
SUMBER_TULIS = SUMBER_BANTU + r'''
database.siapkan(p_fokus)
with database.buka(p_fokus) as kon:
    siswa=database.tambah_siswa(kon,'Fokus Sintetis','P3',pemilik='guru')
    a=int(aksi_fokus(kon,siswa,'mulai','2026-09-01',tuntutan=LANGSUNG,profil='P3',representasi='teks-v1').split('/')[-1])
    ka=konfirmasi_fokus(kon,a,'2026-09-01',True)
    b=int(aksi_fokus(kon,siswa,'lanjut','2026-09-04').split('/')[-1])
    kb=konfirmasi_fokus(kon,b,'2026-09-04',True)
    aksi_fokus(kon,siswa,'pelajari','2026-09-04')
    draft=int(aksi_fokus(kon,siswa,'lanjut','2026-09-04').split('/')[-1])
    kontrak=baca_kontrak(kon,draft,siswa)
    assert kontrak.sumber_konfirmasi==(ka,kb)
    assert kontrak.butir[0].target_fokus==('keliling_luas_datar','K','datar.lupa_kali_dua')
    awal_fokus={'siswa':siswa,'sumber':a,'draft':draft,'arsip':arsip_fokus(kon)}
Path('/data/focus-pair.json').write_text(json.dumps(awal_fokus,sort_keys=True))
'''
SUMBER_BACA = SUMBER_BANTU + r'''
awal_fokus=json.loads(Path('/data/focus-pair.json').read_text())
for _ in range(2): database.siapkan(p_fokus)
with database.buka(p_fokus) as kon:
    assert arsip_fokus(kon)==awal_fokus['arsip'], 'arsip_fokus_berubah'
    siswa=awal_fokus['siswa'];draft=awal_fokus['draft']
    kontrak=baca_kontrak(kon,draft,siswa)
    assert kontrak.tujuan=='latihan_terbimbing'
    assert len(kontrak.sumber_konfirmasi)==2
    konfirmasi_fokus(kon,draft,'2026-09-04')
    berikut=int(aksi_fokus(kon,siswa,'lanjut','2026-09-04').split('/')[-1])
    assert baca_kontrak(kon,berikut,siswa).tujuan=='penguatan'
    database.batalkan_sesi(kon,awal_fokus['sumber'],'Uji sumber dicabut sintetis')
    assert keadaan(kon,siswa,date(2026,9,5))[2][2].tindakan=='pulihkan_sumber'
    sebelum=tuple(kon.iterdump())
    try: aksi_fokus(kon,siswa,'pulihkan_sumber','2026-09-05')
    except ValueError: pass
    else: raise AssertionError('pemulihan_tanpa_persetujuan')
    assert tuple(kon.iterdump())==sebelum
    data={'aksi':'pulihkan_sumber','revisi':revisi(kon,siswa),'konfirmasi_pemulihan':'1'}
    tujuan=jalankan(kon,siswa,data,hari=date(2026,9,5))
    assert jalankan(kon,siswa,data,hari=date(2026,9,5))==tujuan
    assert kon.execute('SELECT COUNT(*) FROM sesi WHERE dibatalkan IS NULL').fetchone()[0]==0
    assert kon.execute("SELECT COUNT(*) FROM kejadian_belajar WHERE jenis='putaran_ditutup'").fetchone()[0]==1
    for t,baris in awal_fokus['arsip'].items():
        assert arsip_fokus(kon)[t][:len(baris)]==baris, 'histori_fokus_dihapus'
    assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not kon.execute('PRAGMA foreign_key_check').fetchall()
'''
