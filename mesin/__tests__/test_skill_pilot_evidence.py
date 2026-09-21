"""Bukti pilot dipisah per tuntutan dan variasi, tanpa memutasi histori."""
from dataclasses import replace
from datetime import date, timedelta
import pytest
import learning_cycle as lc
import skill_pilot as p
from skill_pilot_evidence import ButirBuktiPilot, BuktiPilot, FokusBuktiPilot

HARI = date(2026,9,21)
LANGSUNG = p.KonteksPilot(p.LANGSUNG,"P4","teks-v1")
BALIK = p.KonteksPilot(p.BALIK,"P4","teks-v1")
KISI = p.KonteksPilot(p.PRASYARAT,"P3","teks-v1")


def paket(daftar, *, opt_in=True):
    sesi,meta,kejadian=[],[],[]
    for identitas,(konteks,benar,hiasan) in enumerate(daftar,1):
        for bagian in (0,1):
            sid = identitas*10+bagian
            hari = HARI-timedelta(days=5-bagian*3)
            outcomes=[]
            for n in (1,2):
                p_sisi = 8 if hiasan else 8+n+bagian*2
                if konteks.tuntutan_id == p.PRASYARAT:
                    p_sisi = 8 if hiasan else 3+n+bagian*2
                    param={"p":p_sisi,"l":8,"satuan":"cm","konteks":"ubin" if n==1 else "keramik"}
                elif konteks.tuntutan_id == p.LANGSUNG:
                    param={"varian":"keliling","p":p_sisi,"l":3}
                else:
                    param={"varian":"balik_luas","p":p_sisi,"K":2*(p_sisi+3)}
                sidik=p.sidik_variasi(konteks,konteks.template_id,param)
                outcomes.append(lc.OutcomeSiklus(konteks.template_id,benar,
                    kode_final=None if benar else "K",cek_pemahaman="bisa_menjelaskan",
                    fingerprint_matematis="historis-%d-%d" % (sid,n),
                    profil_parameter=konteks.profil_parameter,
                    mode_representasi=konteks.mode_representasi))
                meta.append(ButirBuktiPilot(sid,n,sid,konteks,sidik))
            sesi.append(lc.SesiSiklus(sid,1,konteks.profil_parameter,"bebas",hari,
                selesai=str(hari),dikonfirmasi=str(hari),konfirmasi_id=sid,
                outcomes=tuple(outcomes),pola_tersedia=(konteks.template_id,)))
            if opt_in:
                kejadian.append(lc.KejadianSiklus(sid,"sertakan_pemetaan",hari,sesi_id=sid,konfirmasi_id=sid))
    return BuktiPilot(lc.BuktiSiklus(1,"P6",tuple(sesi),kejadian=tuple(kejadian)),tuple(meta))


def status(bukti,konteks,hari=HARI):
    return lc.penguasaan_pilot(bukti,1,(konteks,),hari)[0].hasil.status


def test_langsung_tidak_meluluskan_balik_dan_gagal_balik_tidak_menghapus_langsung():
    b=paket(((LANGSUNG,True,False),))
    assert status(b,LANGSUNG)=="terbukti"
    assert status(b,BALIK)=="belum_dinilai"
    gagal=paket(((LANGSUNG,True,False),(BALIK,False,False)))
    assert status(gagal,LANGSUNG)=="terbukti"
    assert status(gagal,BALIK)=="dipelajari"
    assert gagal.bukti.level_aktif=="P6"
    assert all(o.fingerprint_matematis.startswith("historis") for s in gagal.bukti.sesi for o in s.outcomes)


def test_hiasan_kisi_tidak_meluluskan_prasyarat():
    b=paket(((KISI,True,True),))
    assert status(b,KISI)!="terbukti"
    b=paket(((KISI,True,False),))
    assert status(b,KISI)=="terbukti"


def test_tawaran_balik_memerlukan_dua_bukti_sah_bukan_kelulusan():
    b=paket(((LANGSUNG,True,False),(KISI,True,False)))
    assert lc.tawaran_probe_balik(b,1,LANGSUNG,KISI,HARI)
    assert status(b,BALIK)=="belum_dinilai"
    for g in (paket(((LANGSUNG,True,False),)),paket(((LANGSUNG,True,False),(KISI,True,True)))):
        assert not lc.tawaran_probe_balik(g,1,LANGSUNG,KISI,HARI)
    assert not lc.tawaran_probe_balik(b,1,LANGSUNG,KISI,HARI+timedelta(days=28))
    for langsung, kisi in ((None,KISI),(LANGSUNG,None),(BALIK,KISI),(LANGSUNG,BALIK)):
        with pytest.raises(ValueError): lc.tawaran_probe_balik(b,1,langsung,kisi,HARI)


@pytest.mark.parametrize("ubah", ("pg","drill","penguatan","terbimbing","batal","tanpa_optin","ragu","jeda","kurang"))
def test_palang_bukti_tetap(ubah):
    b=paket(((LANGSUNG,True,False),),opt_in=ubah!="tanpa_optin")
    ss=[]
    mm=list(b.butir)
    for s in b.bukti.sesi:
        if ubah=="pg": s=replace(s,format_jawaban="pilihan_ganda")
        if ubah=="drill": s=replace(s,mode="drill")
        if ubah=="penguatan": s=replace(s,tujuan="penguatan")
        if ubah=="terbimbing": s=replace(s,tujuan="latihan_terbimbing")
        if ubah=="batal": s=replace(s,dibatalkan=str(HARI))
        if ubah=="ragu": s=replace(s,outcomes=tuple(replace(o,cek_pemahaman="ragu") for o in s.outcomes))
        if ubah=="jeda": s=replace(s,tanggal=HARI)
        if ubah=="kurang":
            s=replace(s,outcomes=s.outcomes[:1])
            mm=[m for m in mm if m.sesi_id!=s.id or m.nomor==1]
        ss.append(s)
    b=BuktiPilot(replace(b.bukti,sesi=tuple(ss)),tuple(mm))
    assert status(b,LANGSUNG)!="terbukti"


def test_invalidasi_balik_tidak_mencabut_langsung():
    b=paket(((LANGSUNG,True,False),(BALIK,True,False)))
    ids={m.sesi_id for m in b.butir if m.konteks==BALIK}
    ss=tuple(replace(s,dikonfirmasi=None,konfirmasi_id=None,outcomes=()) if s.id in ids else s for s in b.bukti.sesi)
    mm=tuple(replace(m,konfirmasi_id=None) if m.sesi_id in ids else m for m in b.butir)
    e=tuple(lc.KejadianSiklus(100+i,"konfirmasi_dibatalkan",HARI,sesi_id=i) for i in ids)
    baru=BuktiPilot(replace(b.bukti,sesi=ss,kejadian=(*b.bukti.kejadian,*e)),mm)
    assert status(baru,LANGSUNG)=="terbukti"
    assert status(baru,BALIK)=="perlu_cek"


def test_representasi_dan_profil_tidak_disatukan():
    b=paket(((LANGSUNG,True,False),))
    for k in (replace(LANGSUNG,profil_parameter="P5"),replace(LANGSUNG,mode_representasi="geometri_datar-v1")):
        assert status(b,k)=="belum_dinilai"
    with pytest.raises(ValueError): lc.penguasaan_pilot(b,2,(LANGSUNG,),HARI)
    with pytest.raises(ValueError): lc.penguasaan_pilot(b,1,(LANGSUNG,LANGSUNG),HARI)


def evaluasi_pilot():
    kunci=(p.POLA,'K','datar.tukar_luas')
    outcomes=tuple(lc.OutcomeSiklus(p.POLA,True,cek_pemahaman='bisa_menjelaskan',
        target_fokus=kunci,profil_parameter='P4',fingerprint_matematis='historis-%d'%i)
        for i in range(4))
    sesi=lc.SesiSiklus(1,1,'P4','evaluasi',HARI-timedelta(days=1),selesai=str(HARI),
        dikonfirmasi=str(HARI),konfirmasi_id=1,putaran_id=1,outcomes=outcomes,target_fokus=(kunci,))
    putaran=lc.PutaranSiklus(1,1,'P4',HARI-timedelta(days=10),(kunci,))
    meta=tuple(ButirBuktiPilot(1,i+1,1,LANGSUNG,'%064x'%(i+1)) for i in range(4))
    return BuktiPilot(lc.BuktiSiklus(1,'P4',(sesi,),(putaran,)),meta,
                      (FokusBuktiPilot(1,kunci,LANGSUNG),))


def test_evaluasi_tetap_empat_probe_penjelasan_dan_target_sumber():
    b=evaluasi_pilot()
    assert status(b,LANGSUNG)=='terbukti'
    for perubahan in ({'cek_pemahaman':'ragu'},{'kode_final':'N'},
                      {'kode_final':'K','benar':False}):
        sesi=replace(b.bukti.sesi[0],outcomes=tuple(replace(o,**perubahan) for o in b.bukti.sesi[0].outcomes))
        assert status(BuktiPilot(replace(b.bukti,sesi=(sesi,)),b.butir,b.fokus),LANGSUNG)!='terbukti'
    sesi=replace(b.bukti.sesi[0],outcomes=b.bukti.sesi[0].outcomes[:3])
    assert status(BuktiPilot(replace(b.bukti,sesi=(sesi,)),b.butir[:3],b.fokus),LANGSUNG)!='terbukti'
    with pytest.raises(ValueError,match='target outcome'):
        BuktiPilot(b.bukti,b.butir)
    with pytest.raises(ValueError,match='tidak lengkap'):
        BuktiPilot(b.bukti,b.butir[:3],b.fokus)


def test_checkpoint_dua_bagian_occurrence_retensi_dan_kuota():
    b=evaluasi_pilot()
    kunci=b.fokus[0].kunci
    e=replace(b.bukti.sesi[0],tanggal=HARI-timedelta(days=30))
    awal=replace(b.bukti.putaran[0],dibuka=HARI-timedelta(days=50))
    satu=replace(e,id=2,tujuan='checkpoint',tanggal=HARI-timedelta(days=1),konfirmasi_id=2,
                  bagian_checkpoint=1,occurrence=1,outcomes=e.outcomes[:2])
    dua=replace(satu,id=3,tanggal=HARI,konfirmasi_id=3,bagian_checkpoint=2,outcomes=e.outcomes[:1])
    meta=(*b.butir,*tuple(ButirBuktiPilot(s.id,n,s.konfirmasi_id,LANGSUNG,'%064x'%(s.id*10+n))
         for s in (satu,dua) for n in range(1,len(s.outcomes)+1)))
    lengkap=BuktiPilot(replace(b.bukti,sesi=(e,satu,dua),putaran=(awal,)),meta,b.fokus)
    assert status(lengkap,LANGSUNG)=='terbukti'
    for ss in ((e,satu), (e,satu,replace(dua,occurrence=2))):
        ids={s.id for s in ss}
        kurang=BuktiPilot(replace(lengkap.bukti,sesi=ss),tuple(m for m in meta if m.sesi_id in ids),b.fokus)
        assert status(kurang,LANGSUNG)!='terbukti'


def test_metadata_bukan_pengesahan_sumber_yang_berbeda():
    b=paket(((LANGSUNG,True,False),))
    for perubahan in ({"konfirmasi_id":99},{"nomor":99},{"konteks":replace(LANGSUNG,profil_parameter="P5")}):
        with pytest.raises(ValueError): BuktiPilot(b.bukti,(replace(b.butir[0],**perubahan),*b.butir[1:]))
    with pytest.raises(ValueError): BuktiPilot(b.bukti,(*b.butir,b.butir[0]))
    with pytest.raises(ValueError): FokusBuktiPilot(1,(p.POLA,"K","datar.tukar_luas"),BALIK)
