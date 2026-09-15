"""Resume inline, persentase jujur, dan sumber rekomendasi tunggal."""
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database
import reports
import report_dashboard as tampilan
import report_metrics as metrik
from learning_cycle import RencanaBelajar
from learning_journey import PerjalananBelajar
from test_report_metrics import sesi, HARI


@pytest.fixture
def db(tmp_path, monkeypatch):
    import auth
    monkeypatch.setattr(auth, "BERKAS_SANDI", tmp_path / "sandi.json")
    path = tmp_path / "uji.db"
    database.siapkan(path)
    monkeypatch.setattr(metrik, "hari_wib", lambda: HARI)
    monkeypatch.setattr(reports, "hari_wib", lambda: HARI)
    return path


@pytest.mark.parametrize("nilai,hasil", [(99.95,"<100%"),(99.999,"<100%"),(100,"100%"),(0,"0%"),(0.001,"<0,1%"),(None,"—")])
def test_format_persen_tidak_membuat_sempurna_atau_nol_palsu(nilai, hasil):
    assert tampilan.persen(nilai) == hasil


@pytest.mark.parametrize("benar,arah", [(1001,"Naik"),(999,"Turun")])
def test_selisih_kecil_tidak_disebut_naik_nol(benar, arah):
    data = metrik.Materi(("a","P3","diagnostik","bebas","teks-v1"),
                         metrik.Hitungan(2000,benar,2000-benar), metrik.Hitungan(2000,1000,1000))
    assert tampilan._perubahan(data) == arah + " <0,1 poin persentase"


def test_resume_native_tidak_redirect_dan_manual_tidak_mengganti_rekomendasi(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Resume")
        ses = sesi(kon, sid, ("benar","tanpa"), level="P4")
        asli = database.muat_bukti_siklus(kon, sid)
        from learning_journey import perjalanan_belajar
        rekomendasi = perjalanan_belajar(asli, sid).rekomendasi
        awal = tuple(kon.iterdump())
        h = reports.halaman_laporan(kon, sid).decode()
        assert tuple(kon.iterdump()) == awal
    assert '<summary>Lihat rencana belajar</summary>' in h
    assert '<a' not in h.split('<summary>Lihat rencana belajar',1)[1].split('</summary>',1)[0]
    resume = h.split('id="rencana-belajar-laporan"',1)[1].split('class="kartu laporan-bukti"',1)[0]
    assert f'/sesi/{ses}' in resume
    assert "1/2 soal terisi" in resume
    assert 'href="/anak/' in resume
    assert resume.count('class="tombol aksi-rencana-laporan"') == 1
    assert tampilan.judul_tindakan(PerjalananBelajar(rekomendasi)) in resume


def test_clock_resume_mengikuti_profil_bukan_batas_hari_statistik(db, monkeypatch):
    from learning_journey import perjalanan_belajar as asli
    panggilan = []
    def catat(bukti, sid, hari_ini=None):
        panggilan.append(hari_ini)
        return asli(bukti, sid, hari_ini)
    monkeypatch.setattr(reports, "hari_wib", lambda: date(2099,1,1))
    monkeypatch.setattr(reports, "perjalanan_belajar", catat)
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Clock")
        reports.halaman_laporan(kon, sid)
    assert panggilan == [None]


def test_rencana_pending_jadwal_tetap_terlihat_dan_escape():
    p = PerjalananBelajar(RencanaBelajar("tunggu_evaluasi","",tersedia_pada=date(2026,9,19)))
    h = tampilan.render_resume(p,[],1,lambda x:x,lambda x:x,reports._tanggal_pendek)
    assert "19 Sep 2026" in h
    assert "Tunggu evaluasi berjeda" in h
    assert h.count('class="tombol aksi-rencana-laporan"') == 1


def test_kerja_t_dan_lewat_tidak_hilang_karena_koreksi(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Aktivitas Stabil")
        ses = sesi(kon, sid, ("H",))
        b = database.isi_sesi(kon, ses)[0]
        sebelum = metrik.statistik_laporan(kon,sid,HARI)
        database.simpan_diagnosis(kon,b["jawaban_id"],False,"T","T")
        sesudah = metrik.statistik_laporan(kon,sid,HARI)
    assert sebelum.kini.dikerjakan == sesudah.kini.dikerjakan == 1
    assert sesudah.kini.dinilai == 0 and sesudah.kini.belum_dikenalkan == 1


def test_hanya_pilihan_cepat_tanpa_jawaban_bukan_dikerjakan(db):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Pilihan")
        ses=sesi(kon,sid,("tanpa",))
        b=database.isi_sesi(kon,ses)[0]
        jid=database.simpan_jawaban(kon,b["sesi_soal_id"],cara="[pilihan] bingung")
        database.simpan_diagnosis(kon,jid,False,"T","T")
        h=metrik.statistik_laporan(kon,sid,metrik._tanggal(kon.execute("SELECT dicatat FROM jawaban WHERE id=?",(jid,)).fetchone()[0]))
    assert h.kini.dikerjakan == 0 and h.kini.belum_dikenalkan == 1
    isi = tampilan.render_aktivitas(h, reports._tanggal_pendek)
    assert "1 perlu cek pengenalan materi" in isi
    assert "ditandai belum dikenalkan" not in isi
    assert "Dasar hitungan dan total seluruh catatan" not in isi


def test_guard_representasi_beda_tidak_dibandingkan(db):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Representasi")
        ses=sesi(kon,sid,("tanpa",)*5,tanggal="2026-09-03")
        # Metadata sintetis sebelum jawaban mengunci penyajian. Fixture hanya
        # menguji pemisahan query, bukan renderer soal.
        kon.execute("UPDATE sesi_soal SET mode_representasi='pola-uji-v2' WHERE sesi_id=?",(ses,))
        for b in database.isi_sesi(kon,ses):
            jid=database.simpan_jawaban(kon,b["sesi_soal_id"],b["kunci"],"cara")
            kon.execute("UPDATE jawaban SET dicatat='2026-09-03' WHERE id=?",(jid,))
            database.simpan_diagnosis(kon,jid,True,None,None)
        sesi(kon,sid,("benar",)*5)
        h=metrik.statistik_laporan(kon,sid,HARI)
    assert len(h.materi)==2 and not h.sebanding


@pytest.mark.parametrize("kini,lalu", [(4,5),(5,4),(4,4)])
def test_batas_jumlah_dasar_periode_tidak_dilonggarkan(kini,lalu):
    item=metrik.Materi(("a","P3","diagnostik","bebas","teks-v1"),
                      metrik.Hitungan(kini,kini),metrik.Hitungan(lalu,lalu))
    assert not item.sebanding
    assert tampilan._perubahan(item)=="Belum cukup data sebanding"


def test_snapshot_sah_menang_dan_lewat_tanpa_jawaban_tetap_terpisah(db):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Sah")
        ses=sesi(kon,sid,("benar","tanpa"),selesai=True)
        b=database.isi_sesi(kon,ses)
        cid=database.konfirmasi_hasil(kon,ses,"guru",dilewati={b[1]["sesi_soal_id"]})
        # Simulasikan state mutable tak selaras untuk memastikan sumber hasil
        # tetap snapshot aktif. Tidak memutasi snapshot append-only.
        kon.execute("UPDATE diagnosis SET benar=0,kode_final='H' WHERE jawaban_id=?",(b[0]["jawaban_id"],))
        kon.execute("UPDATE jawaban SET dicatat='2026-09-15' WHERE id=?",(b[0]["jawaban_id"],))
        # Tanggal fallback memakai konfirmasi aktual, tidak tanggal sesi 2020.
        tanggal=kon.execute("SELECT dibuat FROM konfirmasi_hasil WHERE id=?",(cid,)).fetchone()[0][:10]
        hasil=metrik.statistik_laporan(kon,sid,date.fromisoformat(tanggal))
    assert hasil.semua.benar == hasil.semua.terkonfirmasi == hasil.semua.dikerjakan == 1
    assert hasil.semua.salah == 0 and hasil.semua.dilewati == 1
    assert hasil.kini.dilewati == 1


@pytest.mark.parametrize("kode",["N","T"])
def test_kategori_terkonfirmasi_tetap_bukan_salah(db,kode):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Kode Sah")
        ses=sesi(kon,sid,(kode,),selesai=True)
        database.konfirmasi_hasil(kon,ses,"guru")
        hasil=metrik.statistik_laporan(kon,sid,HARI)
    assert hasil.kini.dinilai == hasil.kini.terkonfirmasi == 0
    assert hasil.kini.persen is None


def test_tampilan_persen_dan_nama_escape_tanpa_markup_injeksi():
    hitung=metrik.Hitungan(2000,1999,1)
    data=metrik.StatistikLaporan(date(2026,9,9),HARI,hitung,hitung,hitung,
        (metrik.Materi(("<script>x</script>","P3","diagnostik","bebas","teks-v1"),hitung,hitung),))
    h=tampilan.render_materi(data,lambda x:x,reports._tanggal_pendek)
    assert "&lt;100%" in h and "<100%" not in h
    assert "<script>" not in h and "&lt;script&gt;" in h
