"""Regresi laporan pilih–lihat, URL langsung, dan cakupan filter presentasi."""
from dataclasses import replace
from datetime import date
from html import unescape
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database
import reports
import mastery_report as mr
from test_mastery_targets import HARI, _baik, _bukti
from test_report_layout import Struktur


@pytest.fixture
def db(tmp_path, monkeypatch):
    import auth
    monkeypatch.setattr(auth, 'BERKAS_SANDI', tmp_path / 'sandi.json')
    path = tmp_path / 'uji.db'
    database.siapkan(path)
    monkeypatch.setattr(reports, 'hari_wib', lambda: date(2026, 9, 16))
    return path


def konten(h):
    return h.split('id="konten-laporan"', 1)[1].split('</main>', 1)[0]


@pytest.mark.parametrize('query', [
    '', 'tampilan=tugas', 'section=penguasaan',
    'section=penguasaan&tampilan=kriteria', 'section=penguasaan&tampilan=perjalanan',
    'section=riwayat', 'section=riwayat&tampilan=mingguan', 'section=riwayat&tampilan=catatan',
])
def test_konten_laporan_tanpa_accordion_dropdown_atau_js(db, query):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'V2 <uji>', pemilik='guru')
        database.buat_sesi_dari_urutan(kon, sid, 99, ('deret_aritmetika',))
        awal = tuple(kon.iterdump())
        h = reports.halaman_laporan(kon, sid, pengguna='guru', query=query).decode()
        assert tuple(kon.iterdump()) == awal
    isi = konten(h)
    assert '<details' not in isi and '<select' not in isi and '<script' not in isi
    assert '&lt;uji&gt;' in h
    assert 'akun-dropdown' in h or '<details' in h  # Menu global bukan scope V2.


def test_materi_kartu_panel_pagination_dan_kembali_tanpa_menyusutkan_target():
    peta = mr.peta_penguasaan(_bukti(_baik()), 1, HARI)
    h = mr.render_peta(peta, reports._tanggal_pendek, siswa_id=1, materi='statistika')
    assert 'class="peta-pilihan"' in h
    assert 'id="detail-materi"' in h and 'data-materi="statistika"' in h
    assert '✓ Dipilih' in h and 'aria-current="true"' in h
    assert 'Kembali ke materi' in h and '<details' not in h
    assert '1/5 target' in h and f'1 dari {len(peta.target)} target' in h
    ringkas = mr.render_peta(peta, reports._tanggal_pendek, ringkas=True)
    assert f'class="peta-angka">1 <small>dari {len(peta.target)} target' in ringkas
    assert 'class="peta-bukti"' in h and '/sesi/' in h
    filter_hasil = mr.render_peta(peta, reports._tanggal_pendek, siswa_id=1, status='terbukti')
    for target in peta.target:
        if target.topik_id == 'statistika':
            assert target.nama in filter_hasil
    assert '1 dari 5 target' in filter_hasil and 'Belum dinilai' in filter_hasil
    kembali = re.search(r'href="([^"]+)"[^>]*>[^<]*Kembali ke materi', h)
    assert kembali
    assert 'materi=' not in unescape(kembali[1])
    dua = mr.render_peta(peta, reports._tanggal_pendek, siswa_id=1, halaman='2')
    assert 'Halaman 2 dari 2' in dua
    assert f'1 dari {len(peta.target)} target' in dua
    assert 'Belum dinilai (9)' in h
    kartu_1 = re.findall(r'class="peta-pilihan"[^>]*data-materi="([^"]+)"', h)
    assert len(kartu_1) <= 6
    for atribut, _ in Struktur(h).tautan:
        if 'peta-pilihan' not in atribut.get('class', ''):
            continue
        from urllib.parse import parse_qs, urlsplit
        opsi = parse_qs(urlsplit(atribut['href']).query)
        langsung = mr.render_peta(peta, reports._tanggal_pendek, siswa_id=1,
                                 materi=opsi['materi'][0], status=opsi['status'][0], halaman=opsi['halaman'][0])
        assert 'id="detail-materi"' in langsung
        assert 'peta-detail-aktif' in langsung


def test_filter_materi_status_campuran_kosong_dan_parameter_asing():
    peta = mr.peta_penguasaan(_bukti(_baik()), 1, HARI)
    status = list(peta.status)
    status[0] = replace(status[0], status='dipelajari')
    status[1] = replace(status[1], status='perlu_cek')
    peta = replace(peta, status=tuple(status))
    for kode in ('terbukti', 'dipelajari', 'perlu_cek', 'belum_dinilai', 'dinilai'):
        h = mr.render_peta(peta, reports._tanggal_pendek, siswa_id=1, status=kode)
        assert f'1 dari {len(peta.target)} target' in h
        assert 'aria-current="true"' in h
    kosong = mr.peta_penguasaan(_bukti(()), 1, HARI)
    h = mr.render_peta(kosong, reports._tanggal_pendek, siswa_id=1, status='terbukti')
    assert 'Tidak ada materi yang cocok' in h and 'Tampilkan semua materi' in h
    assert 'id="detail-materi"' not in h
    normal = mr.render_peta(kosong, reports._tanggal_pendek, siswa_id=1)
    asing = mr.render_peta(kosong, reports._tanggal_pendek, siswa_id=1,
                          status='<script>', materi='asing', halaman='-99')
    assert normal == asing
    assert 'data-preview="true"' in normal  # Panel awal desktop; mobile tetap daftar.
    assert 'class="peta-auto-lihat">Lihat target' in normal


def test_filter_sesi_tanggal_bukan_aktivitas_topik_dan_pagination(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Riwayat V2', 'P5', pemilik='guru')
        ids = []
        for n in range(23):
            sesi = database.buat_sesi_dari_urutan(kon, sid, n, ('deret_aritmetika',), level='P3')
            database.tandai_selesai(kon, sesi)
            kon.execute('UPDATE sesi SET tanggal=?, topik=? WHERE id=?',
                        ('2026-09-10' if n < 22 else '2020-01-01',
                         'gabungan:logika,pola-bilangan' if n == 21 else 'pola-bilangan', sesi))
            ids.append(sesi)
        h = reports.halaman_laporan(kon, sid, query='section=riwayat&periode=7').decode()
        tabel = h.split('class="tabel-wrap tabel-tren"', 1)[1].split('</table>', 1)[0]
        assert tabel.count('data-label="Sesi"') == 20
        assert f'/sesi/{ids[-1]}"' not in tabel
        assert 'Variasi A' in tabel and 'Gabungan 2 topik' in tabel
        assert 'tanggal sesi' in h.lower() and 'tanggal aktivitas jawaban' in h.lower()
        assert 'Halaman 1 dari 2' in h
        h = reports.halaman_laporan(kon, sid, query='section=riwayat&periode=7&topik=gabungan').decode()
        tabel = h.split('class="tabel-wrap tabel-tren"', 1)[1].split('</table>', 1)[0]
        assert tabel.count('data-label="Sesi"') == 1
        assert 'class="rasio-laporan">0 / 1</span>' in tabel
        h = reports.halaman_laporan(kon, sid, query='section=riwayat&periode=7&halaman=999').decode()
        assert 'Halaman 2 dari 2' in h
        assert 'Catatan pola pada semua latihan' not in h
        mingguan = reports.halaman_laporan(kon, sid, query='section=riwayat&tampilan=mingguan&periode=30&topik=gabungan').decode()
        assert 'tanggal pencatatan jawaban pertama' in mingguan.lower()
        assert 'id="riwayat-hasil-sesi"' not in mingguan
        catatan = reports.halaman_laporan(kon, sid, query='section=riwayat&tampilan=catatan').decode()
        assert 'Catatan pola pada semua latihan' in catatan
        assert 'Catatan pengenalan materi' in catatan and 'K — Keliru konsep' in catatan


@pytest.mark.parametrize('query', [
    'section=penguasaan&materi=statistika&status=dinilai&halaman=2',
    'section=penguasaan&tampilan=kriteria',
    'section=penguasaan&tampilan=perjalanan&halaman=2',
    'section=riwayat&periode=7&topik=gabungan&halaman=2',
    'section=riwayat&tampilan=mingguan', 'section=riwayat&tampilan=catatan',
    'tampilan=tugas&halaman=2',
    'section=penguasaan&materi=%3Cscript%3E&halaman=nan&status=asing',
    'section=riwayat&tampilan=sesi&tampilan=catatan&topik=asing',
])
def test_http_v2_guard_tanpa_write_ai_dan_url_langsung(tmp_path, monkeypatch, query):
    from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID
    import assistant_client
    import assistant_service
    import llm

    def terlarang(*args, **kwargs):
        pytest.fail('GET laporan memanggil AI')

    monkeypatch.setattr(assistant_service, 'panggil_provider_default', terlarang)
    monkeypatch.setattr(assistant_client, 'kirim', terlarang)
    monkeypatch.setattr(llm, '_panggil', terlarang)
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            sid = database.tambah_siswa(kon, 'V2 Sintetis', 'P5', pemilik='guru')
            asing = database.tambah_siswa(kon, 'Bukan Milik', pemilik='lain')
            from test_mastery_report import _buat_bukti
            pid = database.buat_putaran_fokus(kon, sid, 'P5')
            _buat_bukti(kon, sid, pid, 181, date.today())
            database.buat_sesi_dari_urutan(kon, sid, 182, ('rata_rata',), level='P5', topik='statistika')
            awal = tuple(kon.iterdump())
        jalur = f'/laporan/{sid}?{query}'
        kode, h, _ = server.minta(jalur, auth=('guru', SANDI_GURU))
        assert kode == 200 and '<details' not in konten(h)
        assert server.minta(jalur, auth=('guru', SANDI_GURU))[1] == h
        a = server.minta(f'/laporan/{asing}?{query}', auth=('guru', SANDI_GURU))
        b = server.minta(f'/laporan/999999?{query}', auth=('guru', SANDI_GURU))
        assert a[0] == b[0] == 404 and a[1] == b[1]
        m = server.minta(jalur, auth=('feby', SANDI_MURID))
        assert m[0] in (401, 403) and 'id="konten-laporan"' not in m[1]
        with server.buka() as kon:
            assert tuple(kon.iterdump()) == awal
    finally:
        server.berhenti()


def test_query_asing_ganda_dan_pilihan_tidak_cocok_filter_deterministik(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Parameter', 'P5', pemilik='guru')
        biasa = reports.halaman_laporan(kon, sid).decode()
        assert reports.halaman_laporan(kon, sid, query='section=riwayat&section=penguasaan').decode() == biasa
        assert reports.halaman_laporan(kon, sid, query='section=<script>&asing=<img>').decode() == biasa
    peta = mr.peta_penguasaan(_bukti(_baik()), 1, HARI)
    a = mr.render_peta(peta, reports._tanggal_pendek, siswa_id=1, status='belum_dinilai')
    b = mr.render_peta(peta, reports._tanggal_pendek, siswa_id=1, status='belum_dinilai', materi='statistika')
    assert a == b  # Pilihan yang tersembunyi filter tidak menyelundup ke detail.
    assert 'peta-detail-aktif' not in b


def test_batas_7_30_hari_dan_filter_kosong_tanggal_warisan(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Batas V2', pemilik='guru')
        ids = {}
        for tanggal in ('2026-09-16', '2026-09-10', '2026-09-09', '2026-08-18', '2026-08-17', '2026-09-17', 'warisan'):
            sesi = database.buat_sesi_dari_urutan(kon, sid, 711, ('deret_aritmetika',))
            database.tandai_selesai(kon, sesi)
            kon.execute('UPDATE sesi SET tanggal=?,topik=? WHERE id=?', (tanggal, 'lama' if tanggal == 'warisan' else 'pola-bilangan', sesi))
            ids[tanggal] = sesi
        for periode, harapan in [('7', {'2026-09-16', '2026-09-10'}),
                                ('30', {'2026-09-16', '2026-09-10', '2026-09-09', '2026-08-18'}),
                                ('semua', set(ids))]:
            h = reports.halaman_laporan(kon, sid, query='section=riwayat&periode='+periode).decode()
            for tanggal, sesi in ids.items():
                assert (f'href="/sesi/{sesi}"' in h) == (tanggal in harapan)
        kosong = reports.halaman_laporan(kon, sid, query='section=riwayat&periode=7&topik=lama').decode()
        assert 'Tidak ada sesi yang cocok' in kosong
        assert '0 sesi sesuai filter · 7 sesi seluruh catatan' in kosong


def test_escaping_catatan_target_dan_url_data_warisan(db):
    from test_laporan_ortu import _beri_diagnosis
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Escape V2', pemilik='guru')
        for seed in (711, 711):
            sesi = database.buat_sesi(kon, sid, seed=seed)
            _beri_diagnosis(kon, sesi, 0, 'K', 'uji', '<script>contoh</script>')
            kon.execute('UPDATE sesi SET topik=? WHERE id=?', ('topik<&"', sesi))
        h = reports.halaman_laporan(kon, sid, query='section=riwayat&tampilan=catatan').decode()
        assert '&lt;script&gt;contoh&lt;/script&gt;' in h
        assert '<script>contoh' not in h
        h = reports.halaman_laporan(kon, sid, query='section=riwayat').decode()
        assert 'topik&lt;&amp;&quot;' in h
        for a, _ in Struktur(h).tautan:
            if 'topik=' in a.get('href', ''):
                assert '<' not in a['href'] and '"' not in a['href']
    peta = mr.peta_penguasaan(_bukti(()), 1, HARI)
    target = list(peta.target)
    target[0] = replace(target[0], nama='<img src=x>')
    h = mr.render_peta(replace(peta, target=tuple(target)), reports._tanggal_pendek)
    assert '&lt;img src=x&gt;' in h and '<img src=x>' not in h


def test_histori_dan_tugas_pagination_tidak_menghilangkan_rincian(db):
    from learning_cycle import RencanaBelajar
    from learning_journey import BuktiFokusPerjalanan, HistoriPutaran, PerjalananBelajar
    from cycle_report import render_perjalanan
    histori = tuple(HistoriPutaran(n, 'P3', HARI, HARI, 'diganti_level', (),
                    (BuktiFokusPerjalanan(HARI, n, 'bukti_dibatalkan', status='perlu_konfirmasi_ulang'),))
                    for n in range(1, 13))
    data = PerjalananBelajar(RencanaBelajar('pemetaan', ''), histori=histori)
    halaman = [render_perjalanan(data, reports._nama_tipe_soal, reports._tanggal_pendek,
                                 siswa_id=1, halaman=str(n)) for n in (1, 2, 3)]
    assert all('<details' not in h and 'Variasi A' in h and 'konfirmasi ulang' in h for h in halaman)
    for n in range(1, 13):
        assert ''.join(halaman).count(f'href="/sesi/{n}"') == 1
    assert 'Halaman 3 dari 3' in halaman[2]
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Banyak tugas', pemilik='guru')
        ids = [database.buat_sesi_dari_urutan(kon, sid, n, ('deret_aritmetika',)) for n in range(23)]
        a = reports.halaman_laporan(kon, sid, query='tampilan=tugas').decode()
        b = reports.halaman_laporan(kon, sid, query='tampilan=tugas&halaman=2').decode()
        for sesi in ids:
            assert (a+b).count(f'href="/sesi/{sesi}"') == 1
        assert 'Halaman 2 dari 2' in b
        assert 'Kembali ke ringkasan' in a
