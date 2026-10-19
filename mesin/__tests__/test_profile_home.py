"""Beranda ringkas tetap mengikuti bukti, CTA dan antrian yang sah."""
from datetime import date

import pytest

import database
import interventions
import profile_history
import profile_home
import teacher_pages
from learning_cycle import BuktiSiklus, PutaranFokus, RencanaBelajar, SesiSiklus, StatusFokus
from test_concise_ui import Markup


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / 'beranda.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    with database.buka(path) as kon:
        anak = database.tambah_siswa(kon, 'Anak <Sintetis>', 'P3', pemilik='guru')
        yield kon, anak


def test_antrian_terlama_memilih_sebelum_limit_dan_tidak_menghidupkan_konfirmasi(db):
    kon, anak = db
    asing = database.tambah_siswa(kon, 'Asing', 'P3', pemilik='lain')
    sesi = []
    for n in range(8):
        sid = database.buat_sesi(kon, anak, seed=99+n, jumlah_soal=1)
        kon.execute('UPDATE sesi SET tanggal=? WHERE id=?', (f'2026-09-{n+1:02d}', sid))
        database.tandai_selesai(kon, sid)
        sesi.append(sid)
    database.batalkan_sesi(kon, sesi[0], 'Sintetis')
    kon.execute('UPDATE sesi SET selesai=NULL WHERE id=?', (sesi[1],))
    soal = database.isi_sesi(kon, sesi[2])[0]['sesi_soal_id']
    database.konfirmasi_hasil(kon, sesi[2], guru='guru', dilewati={soal})
    sid_asing = database.buat_sesi(kon, asing, seed=1, jumlah_soal=1)
    database.tandai_selesai(kon, sid_asing)
    sebelum = tuple(kon.iterdump())
    hasil = profile_history.tinjauan_terlama(kon, anak, kecuali=sesi[3])
    assert [r['id'] for r in hasil] == sesi[4:7]
    assert tuple(kon.iterdump()) == sebelum
    # Snapshot yang tidak lagi aktif harus kembali masuk antrian, tanpa tulis oleh query.
    kon.execute("UPDATE sesi SET fingerprint_konfirmasi='usang' WHERE id=?", (sesi[2],))
    assert [r['id'] for r in profile_history.tinjauan_terlama(kon, anak)] == sesi[2:5]


def test_kartu_tinjau_ringkas_dan_peta_terlihat_tanpa_mutasi():
    siswa = {'id': 9, 'nama': '<Anak>'}
    bukti = BuktiSiklus(9, 'P3', sesi=(SesiSiklus(41, 9, 'P3', 'evaluasi', date(2026, 9, 1)),))
    rencana = RencanaBelajar('konfirmasi_hasil', 'uji', sesi_id=41)
    isi = profile_home.kartu(rencana, bukti, siswa, jumlah_soal=15, hari_ini=date(2026, 9, 28))
    terlihat = Markup(isi).terlihat()
    assert 'Tinjau hasil latihan &lt;Anak&gt;' in isi
    assert 'Menunggu 27 hari' in terlihat
    assert '15 soal · sekitar 45 menit pengerjaan' in terlihat
    assert 'Caranya' in terlihat and 'tanpa memberi jawaban' in terlihat
    assert 'Konfirmasi hanya setelah hasil diperiksa.' in terlihat
    assert 'Bisa disimpan sebagai draf dan dilanjutkan nanti.' in terlihat
    assert 'Posisi <Anak>: tahap 4 dari 6' in terlihat
    assert isi.count('aria-current="step"') == 1
    assert isi.count('href="/sesi/41"') == 1
    assert 'class="studio-layout-st"' not in isi
    assert 'Kapan kembali' not in terlihat and 'Tahap latihan awal' not in terlihat
    assert 'Waktu' not in terlihat
    assert isi.index('</section>') < isi.index('class="strip-rencana-st"')
    assert isi.index('class="strip-rencana-st"') < isi.index('Apa yang terjadi di setiap tahap?')


@pytest.mark.parametrize('tindakan', [
    'pilih_variasi', 'pemetaan', 'tunggu_pemetaan', 'probe_diagnostik', 'intervensi',
    'pengenalan', 'latihan_terbimbing', 'penguatan', 'tunggu_evaluasi', 'evaluasi',
    'tunggu_checkpoint', 'checkpoint', 'probe_setelah_pengenalan', 'mixed_maintenance',
    'putaran_baru', 'eskalasi',
])
def test_semua_langkah_menjaga_satu_aksi_dan_tanggal_tunggu(tindakan):
    fokus = ('deret_aritmetika', 'K', None)
    putaran = PutaranFokus(7, 'P3', (StatusFokus(fokus, 'perlu_dipelajari', jumlah_sesi=2),))
    rencana = RencanaBelajar(tindakan, 'uji', putaran=putaran, kandidat=(fokus,),
                            tersedia_pada=date(2026, 10, 22) if tindakan.startswith('tunggu') else None)
    isi = profile_home.kartu(rencana, BuktiSiklus(9, 'P3'), {'id':9, 'nama':'Sintetis'})
    terlihat = Markup(isi).terlihat()
    tanpa = tindakan.startswith('tunggu') or tindakan == 'eskalasi'
    assert isi.count('class="rencana-cta-utama-st"') == (0 if tanpa else 1)
    assert isi.count('aria-current="step"') == 1
    if tindakan.startswith('tunggu'):
        assert '22 Oktober 2026' in terlihat
    if tindakan == 'intervensi':
        materi = interventions.untuk_fokus(fokus)
        assert materi.instruksi_orang_tua in terlihat and materi.contoh_terbimbing in terlihat


def test_gaya_beranda_scoped_dan_enam_segmen_tanpa_status_kelulusan():
    import profile_workspace
    css = profile_workspace.GAYA_PROFIL
    assert 'beranda-profil-st {{ max-width' not in css and 'beranda-profil-st { max-width' not in css
    assert 'grid-template-columns:repeat(6,minmax(0,1fr))' in css
    assert '.beranda-profil-st .beranda-posisi-st .tahap-rencana-st::after { display:none;' in css


def test_sesi_sekunder_satu_aksi_draf_dan_tanpa_kelola_tautan(db):
    import review_store
    kon, anak = db
    sid = database.buat_sesi(kon, anak, seed=22, jumlah_soal=1)
    database.tandai_selesai(kon, sid)
    butir = database.isi_sesi(kon, sid)[0]['sesi_soal_id']
    review_store.simpan(kon, sid, {f'catatan_tinjauan_{butir}':'Catatan sintetis.'})
    siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (anak,)).fetchone()
    isi = teacher_pages.halaman_anak(kon, siswa, query='section=rencana').decode()
    daftar = isi.split('class="profil-taches-st"', 1)[1].split('</section>', 1)[0]
    assert daftar.count(f'href="/sesi/{sid}"') == 1
    assert 'Draf tersimpan' in daftar and '>Lanjutkan</a>' in daftar
    assert 'Kelola tautan' not in daftar and '<form' not in daftar


def test_materi_tidak_tersedia_tidak_menawarkan_aksi(monkeypatch):
    m = interventions.MateriIntervensi('uji', 'Materi <belum> tersedia.', '', '', tersedia=False)
    monkeypatch.setattr(interventions, 'pilihan_untuk_fokus', lambda _: (m,))
    r = RencanaBelajar('intervensi', 'uji', kandidat=(('deret_aritmetika','K',None),))
    isi = profile_home.kartu(r, BuktiSiklus(9,'P3'), {'id':9,'nama':'Sintetis'})
    assert 'Materi &lt;belum&gt; tersedia.' in isi
    assert 'rencana-cta-utama-st' not in isi


def test_beranda_tidak_menampilkan_sesi_belum_dikirim_dan_progres_sama_laporan(db):
    kon, anak = db
    sid = database.buat_sesi(kon, anak, seed=29, jumlah_soal=1)
    siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (anak,)).fetchone()
    sebelum = tuple(kon.iterdump())
    isi = teacher_pages.halaman_anak(kon, siswa, query='section=rencana').decode()
    assert f'href="/sesi/{sid}"' not in isi
    assert f'href="/anak/{anak}?section=perkembangan"' in isi
    from mastery_catalog import katalog_target
    total = len(katalog_target('P3'))
    assert f'0 dari {total} target sedang dipelajari' in isi
    assert f'{total} belum dinilai' in isi
    assert tuple(kon.iterdump()) == sebelum


def test_progres_tidak_menyamakan_sisa_dengan_belum_dinilai(db, monkeypatch):
    import mastery_report
    kon, anak = db
    class Peta:
        target = range(10)
        jumlah = {'dipelajari':3, 'terbukti':2, 'perlu_cek':1, 'belum_dinilai':4}
    monkeypatch.setattr(mastery_report, 'peta_penguasaan', lambda *a: Peta())
    isi = profile_home.tautan_perkembangan(kon, anak)
    for teks in ('3 dari 10', '2 menunjukkan pemahaman', '1 perlu dicek kembali', '4 belum dinilai'):
        assert teks in isi
    assert 'Sisanya belum dinilai' not in isi


def test_progres_snapshot_dan_invalidasi_sama_dengan_laporan(db, monkeypatch):
    from datetime import timedelta
    import domain_clock
    from mastery_evidence import lengkapi_bukti_materi
    from mastery_report import peta_penguasaan
    from test_mastery_report import _buat_bukti, HARI

    monkeypatch.setattr(domain_clock, 'hari_wib', lambda: HARI)
    kon, _ = db
    anak = database.tambah_siswa(kon, 'Progres Sintetis', 'P5', pemilik='guru')
    pid = database.buat_putaran_fokus(kon, anak, 'P5')
    _buat_bukti(kon, anak, pid, 11, HARI-timedelta(days=7))
    akhir = _buat_bukti(kon, anak, pid, 12, HARI-timedelta(days=3))
    for invalidasi in (False, True):
        if invalidasi:
            butir = database.isi_sesi(kon, akhir)[0]
            database.simpan_diagnosis(kon, butir['jawaban_id'], False, 'K', 'K')
        sebelum = tuple(kon.iterdump())
        peta = peta_penguasaan(lengkapi_bukti_materi(kon, database.muat_bukti_siklus(kon, anak)), anak)
        isi = profile_home.tautan_perkembangan(kon, anak)
        assert f'{peta.jumlah["dipelajari"]} dari {len(peta.target)} target' in isi
        assert ('1 menunjukkan pemahaman' in isi) == (not invalidasi)
        assert ('1 perlu dicek kembali' in isi) == invalidasi
        assert tuple(kon.iterdump()) == sebelum


def test_progres_berubah_gagal_aman_tanpa_menahan_cta(db, monkeypatch):
    import mastery_evidence
    kon, anak = db
    def berubah(*args):
        raise ValueError('versi bukti berubah')
    monkeypatch.setattr(mastery_evidence, 'lengkapi_bukti_materi', berubah)
    isi = profile_home.tautan_perkembangan(kon, anak)
    assert 'Lihat perkembangan' in isi and 'target' not in isi
