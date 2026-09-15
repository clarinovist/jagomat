"""Penguasaan target Jagomat: cakupan tetap, bukti sah, dan tidak overclaim."""
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import sys

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database
import learning_cycle as lc
import mastery_catalog as katalog
from mastery_evidence import lengkapi_bukti_materi
import reports
import topics

HARI = date(2026, 9, 20)
POLA = "rata_rata"
TARGET = (katalog.TargetMateri("statistika.rata", "Rata-rata", "statistika", "Statistika", (POLA,)),)
FOKUS = (POLA, "K", "uji")


def _sesi(nomor, hari, tujuan="pemetaan", benar=True, paham="bisa_menjelaskan", **opsi):
    outcome = tuple(lc.OutcomeSiklus(POLA, benar, None if benar else "H",
                                   cek_pemahaman=paham,
                                   fingerprint_matematis=f"mat-{nomor}-{i}") for i in range(4))
    return lc.SesiSiklus(nomor, 1, "P5", tujuan, hari, selesai=hari.isoformat(),
                         dikonfirmasi=hari.isoformat(), konfirmasi_id=nomor,
                         putaran_id=1, outcomes=outcome, pola_tersedia=(POLA,), **opsi)


def _bukti(sesi, **opsi):
    return lc.BuktiSiklus(1, "P5", tuple(sesi),
                         putaran=opsi.pop("putaran", (lc.PutaranSiklus(1, 1, "P5", HARI-timedelta(days=20)),)),
                         **opsi)


def _nilai(bukti, hari=HARI, target=TARGET):
    return lc.penguasaan_target(bukti, 1, target, hari)[0]


def _baik():
    return (_sesi(1, HARI-timedelta(days=7)), _sesi(2, HARI-timedelta(days=3)))


@pytest.fixture
def db(tmp_path, monkeypatch):
    import auth
    monkeypatch.setattr(auth, "BERKAS_SANDI", tmp_path / "sandi.json")
    path = tmp_path / "uji.db"
    database.siapkan(path)
    return path


def test_regresi_angka_utama_bukan_rasio_latihan_parsial(db):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Anak Contoh","P5",pemilik="guru")
        sesi=database.buat_sesi_dari_urutan(kon,sid,17,(POLA,)*4,level="P5",topik="statistika")
        for b in database.isi_sesi(kon,sesi):
            j=database.simpan_jawaban(kon,b["sesi_soal_id"],b["kunci"],"cara")
            database.simpan_diagnosis(kon,j,True,None,None)
        h=reports.halaman_laporan(kon,sid).decode()
    assert 'id="peta-penguasaan"' in h
    assert "Progres penguasaan materi Jagomat" in h
    assert "Belum dinilai" in h
    assert "Dasar hitungan dan total seluruh catatan" not in h
    assert "Persentase = benar" not in h
    assert h.index('id="peta-penguasaan"') < h.index('id="judul-aktivitas"')


@pytest.mark.parametrize("level",("P3","P4","P5","P6"))
def test_katalog_memetakan_seluruh_pola_kelas_tepat_sekali(level):
    target=katalog.katalog_target(level)
    assert target and len({t.id for t in target})==len(target)
    semua=[]
    for topik_id in topics.daftar_topik():
        if topik_id=="campuran":continue
        paket=topics.ambil(topik_id)
        harapan=set(paket.komposisi.get(level,()))
        aktual=[p for t in target if t.topik_id==topik_id for p in t.pola]
        assert set(aktual)==harapan
        assert len(aktual)==len(set(aktual))
        semua.extend(aktual)
    assert len(semua)==len(set(semua))
    assert all(t.topik_id!="campuran" for t in target)


def test_grup_target_bukan_kartu_rumus_generik():
    target=katalog.katalog_target("P5")
    pemilik={p:t.id for t in target for p in t.pola}
    assert pemilik["deret_aritmetika"] != pemilik["deret_bertingkat"]
    assert pemilik["luas_arsiran"] != pemilik["keliling_luas_datar"]
    assert pemilik["rata_rata"] != pemilik["rata_rata_gabungan"]
    assert katalog.katalog_target("kelas-asing")==()


def test_kosong_belum_dinilai_bukan_gagal():
    assert _nilai(_bukti(())).status=="belum_dinilai"


def test_dua_pemetaan_berjeda_cukup_bisa_menjelaskan_terbukti():
    bukti=_bukti(_baik())
    salinan=repr(bukti)
    hasil=_nilai(bukti)
    assert hasil.status=="terbukti"
    assert hasil.pola[0].sesi_ids==(1,2)
    assert repr(bukti)==salinan


@pytest.mark.parametrize("ubah",[
    {"dikonfirmasi":None},{"konfirmasi_id":None},{"selesai":None},{"dibatalkan":"batal"},
    {"level":"P4"},{"siswa_id":2},{"mode":"drill"},{"putaran_id":999},
    {"tujuan":"penguatan"},{"tujuan":"latihan_terbimbing"},{"tujuan":"pengenalan"},
    {"tujuan":"bebas"},
])
def test_bukti_tidak_sah_tidak_menghasilkan_penguasaan(ubah):
    assert _nilai(_bukti(tuple(replace(s,**ubah) for s in _baik()))).status=="belum_dinilai"


def test_pemilik_putaran_tidak_boleh_asing():
    assert _nilai(_bukti(_baik(),putaran=(lc.PutaranSiklus(1,2,"P5",HARI),))).status=="belum_dinilai"
    with pytest.raises(ValueError):lc.penguasaan_target(_bukti(()),2,TARGET,HARI)


@pytest.mark.parametrize("jeda",(0,1,2))
def test_pemetaan_tanpa_jeda_tidak_lulus(jeda):
    assert _nilai(_bukti((_sesi(1,HARI-timedelta(days=jeda)),_sesi(2,HARI)))).status=="dipelajari"


@pytest.mark.parametrize("paham",(None,"ragu","menghafal"))
def test_benar_tanpa_penjelasan_bukan_penguasaan(paham):
    assert _nilai(_bukti(tuple(replace(s,outcomes=tuple(replace(o,cek_pemahaman=paham) for o in s.outcomes)) for s in _baik()))).status=="dipelajari"


def test_soal_diulang_dan_fingerprint_hilang_bukan_variansi():
    for kosong in (False,True):
        sesi=tuple(replace(s,outcomes=tuple(replace(o,fingerprint_matematis=None if kosong else "sama") for o in s.outcomes)) for s in _baik())
        assert _nilai(_bukti(sesi)).status=="dipelajari"


def test_cukup_empat_probe_total_tetapi_bukan_tiga():
    for jumlah,harapan in ((2,"terbukti"),(1,"dipelajari")):
        sesi=tuple(replace(s,outcomes=s.outcomes[:jumlah]) for s in _baik())
        assert _nilai(_bukti(sesi)).status==harapan


def test_dua_varian_target_semua_harus_terbukti():
    target=(replace(TARGET[0],pola=(POLA,"rata_rata_gabungan")),)
    hasil=_nilai(_bukti(_baik()),target=target)
    assert hasil.status=="dipelajari"
    assert [p.status for p in hasil.pola]==["terbukti","belum_dinilai"]


def test_katalog_tetap_meski_latihan_satu_pola_berulang():
    target=katalog.katalog_target("P5")
    nilai=lc.penguasaan_target(_bukti(_baik()),1,target,HARI)
    assert len(nilai)==len(target)
    assert sum(t.status=="terbukti" for t in nilai)==1
    assert sum(t.status=="belum_dinilai" for t in nilai)==len(target)-1


def test_pemetaan_manual_opt_in_terikat_konfirmasi():
    sesi=tuple(replace(s,tujuan="bebas",putaran_id=None) for s in _baik())
    event=tuple(lc.KejadianSiklus(s.id,"sertakan_pemetaan",s.tanggal,sesi_id=s.id,konfirmasi_id=s.konfirmasi_id) for s in sesi)
    assert _nilai(_bukti(sesi,kejadian=event)).status=="terbukti"
    event=tuple(replace(e,konfirmasi_id=777) for e in event)
    assert _nilai(_bukti(sesi,kejadian=event)).status=="belum_dinilai"


def test_representasi_baru_tidak_dicampur():
    a,b=_baik()
    b=replace(b,outcomes=tuple(replace(o,mode_representasi="visual-v2") for o in b.outcomes))
    assert _nilai(_bukti((a,b))).status=="dipelajari"
    b=replace(b,outcomes=(replace(b.outcomes[0],mode_representasi="teks-v1"),*b.outcomes[1:]))
    assert _nilai(_bukti((a,b))).status=="perlu_cek"


def test_koreksi_bukti_meminta_cek_ulang_bukan_kembali_ambil_lama():
    sesi=(*_baik(),replace(_sesi(3,HARI),dikonfirmasi=None,konfirmasi_id=None,outcomes=()))
    event=(lc.KejadianSiklus(1,"konfirmasi_dibatalkan",HARI,sesi_id=3),)
    assert _nilai(_bukti(sesi,kejadian=event)).status=="perlu_cek"


def test_hasil_buruk_baru_menahan_penguasaan_tapi_latihan_terbimbing_tidak():
    for tujuan,harapan in (("pemetaan","dipelajari"),("latihan_terbimbing","terbukti")):
        buruk=_sesi(3,HARI,tujuan=tujuan,benar=False)
        assert _nilai(_bukti((*_baik(),buruk))).status==harapan


def test_bukti_tua_perlu_diperiksa_lagi():
    assert _nilai(_bukti(_baik()),HARI+timedelta(days=24)).status=="terbukti"
    assert _nilai(_bukti(_baik()),HARI+timedelta(days=25)).status=="perlu_cek"


def test_ganti_level_tidak_menghidupkan_penguasaan_lama():
    event=(lc.KejadianSiklus(1,"diganti_level",HARI),)
    assert _nilai(_bukti(_baik(),kejadian=event)).status=="belum_dinilai"


def test_evaluasi_hanya_probe_target_bukan_pembanding():
    evaluasi=_sesi(3,HARI,tujuan="evaluasi",target_fokus=(FOKUS,))
    assert _nilai(_bukti((evaluasi,))).status=="terbukti"
    assert _nilai(_bukti((replace(evaluasi,target_fokus=()),))).status=="dipelajari"


def test_dua_miskonsepsi_satu_pola_tidak_diratakan():
    k2=(POLA,"K","kedua")
    p=lc.PutaranSiklus(1,1,"P5",HARI-timedelta(days=20),(FOKUS,k2))
    s=_sesi(1,HARI,tujuan="evaluasi",target_fokus=(FOKUS,))
    assert _nilai(_bukti((s,),putaran=(p,))).status=="dipelajari"


@pytest.mark.parametrize("kode",("K","N","T"))
def test_kode_nonlulus_tidak_disamarkan_oleh_75_persen(kode):
    s=_sesi(1,HARI,tujuan="evaluasi",target_fokus=(FOKUS,))
    s=replace(s,outcomes=(*s.outcomes[:3],replace(s.outcomes[3],benar=False,kode_final=kode)))
    assert _nilai(_bukti((s,))).status=="dipelajari"


def test_bukti_baru_tanpa_cek_pemahaman_tidak_mempertahankan_klaim():
    baru=_sesi(3,HARI,paham=None)
    assert _nilai(_bukti((*_baik(),baru))).status=="dipelajari"


def test_fokus_otomatis_belum_diperbaiki_tidak_tertutup_dua_sesi_benar():
    buruk=tuple(_sesi(i,HARI-timedelta(days=15-i),benar=False) for i in (11,12))
    # Letakkan bukti berulang sebelum dua hasil bagus, agar bukan sekadar efek urutan.
    buruk=(replace(buruk[0],tanggal=HARI-timedelta(days=15)),replace(buruk[1],tanggal=HARI-timedelta(days=12)))
    assert _nilai(_bukti((*buruk,*_baik()))).status=="dipelajari"


def test_invalidasi_latihan_terbimbing_tidak_mengubah_penguasaan():
    baru=replace(_sesi(3,HARI,tujuan="latihan_terbimbing"),dikonfirmasi=None,konfirmasi_id=None,outcomes=())
    event=(lc.KejadianSiklus(1,"konfirmasi_dibatalkan",HARI,sesi_id=3),)
    assert _nilai(_bukti((*_baik(),baru),kejadian=event)).status=="terbukti"


def test_evaluasi_pola_lain_tidak_memperpanjang_bukti():
    evaluasi=_sesi(3,HARI+timedelta(days=27),tujuan="evaluasi",target_fokus=(("lain","K",None),))
    assert _nilai(_bukti((*_baik(),evaluasi)),HARI+timedelta(days=27)).status=="perlu_cek"


def _checkpoint(bagian=2, occurrence=1, paham="bisa_menjelaskan"):
    e=_sesi(10,HARI-timedelta(days=35),tujuan="evaluasi",target_fokus=(FOKUS,))
    a=_sesi(11,HARI-timedelta(days=1),tujuan="checkpoint",target_fokus=(FOKUS,),bagian_checkpoint=1,occurrence=1)
    b=_sesi(12,HARI,tujuan="checkpoint",target_fokus=(FOKUS,),bagian_checkpoint=bagian,occurrence=occurrence,paham=paham)
    return (e,a,b)


def test_checkpoint_dua_bagian_sah_memperbarui_bukti():
    hasil=_nilai(_bukti(_checkpoint()))
    assert hasil.status=="terbukti"
    assert hasil.pola[0].sesi_ids==(11,12)


@pytest.mark.parametrize("opsi",[{"bagian":1},{"occurrence":2}])
def test_checkpoint_tidak_lengkap_tidak_memperbarui_penguasaan(opsi):
    assert _nilai(_bukti(_checkpoint(**opsi))).status=="perlu_cek"


def test_checkpoint_gagal_tidak_bertahan_dari_keberhasilan_lama():
    assert _nilai(_bukti(_checkpoint(paham="ragu"))).status=="dipelajari"


def test_checkpoint_duplikat_tidak_memperbarui_bukti():
    e,a,b=_checkpoint()
    b=replace(b,outcomes=a.outcomes)
    assert _nilai(_bukti((e,a,b))).status=="dipelajari"


def test_tidak_menyimpulkan_dari_outcome_dilewati():
    sesi=tuple(replace(s,outcomes=tuple(replace(o,dilewati=True) for o in s.outcomes)) for s in _baik())
    assert _nilai(_bukti(sesi)).status=="belum_dinilai"


def test_skip_sebagian_tidak_memperkecil_denominator_probe_agar_lulus():
    a,b=_baik()
    b=replace(b,outcomes=(*b.outcomes,replace(b.outcomes[0],dilewati=True,fingerprint_matematis="lewat")))
    assert _nilai(_bukti((a,b))).status=="dipelajari"


def test_semua_probe_baru_dilewati_perlu_cek_bukan_menghidupkan_hasil_lama():
    baru=_sesi(3,HARI)
    baru=replace(baru,outcomes=tuple(replace(o,dilewati=True) for o in baru.outcomes))
    assert _nilai(_bukti((*_baik(),baru))).status=="perlu_cek"


def test_adapter_memuat_mode_pola_dan_sidik_tanpa_menulis(db):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Adapter","P5")
        ses=database.buat_sesi_dari_urutan(kon,sid,31,(POLA,)*4,level="P5",topik="statistika")
        for b in database.isi_sesi(kon,ses):
            j=database.simpan_jawaban(kon,b["sesi_soal_id"],b["kunci"],"cara")
            database.simpan_diagnosis(kon,j,True,None,None)
        database.tandai_selesai(kon,ses)
        database.konfirmasi_hasil(kon,ses,"guru")
        sebelum=kon.total_changes
        bukti=lengkapi_bukti_materi(kon,database.muat_bukti_siklus(kon,sid))
        assert kon.total_changes==sebelum
    assert bukti.sesi[0].mode=="diagnostik" and bukti.sesi[0].pola_tersedia==(POLA,)
    assert all(o.fingerprint_matematis for o in bukti.sesi[0].outcomes)
