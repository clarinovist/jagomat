"""Regresi ruang kerja profil: paging nyata, filter, tab, dan akses sintetis."""
from datetime import date, timedelta
from pathlib import Path
import re
import sys
from urllib.parse import urlencode

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database
import teacher_pages
from http_test_kit import ServerUji, SANDI_GURU


@pytest.fixture()
def db(tmp_path, monkeypatch):
    jalur = tmp_path / 'profil-sintetis.db'
    database.siapkan(jalur)
    monkeypatch.setattr(database, 'BAWAAN', jalur)
    with database.buka(jalur) as kon:
        anak = database.tambah_siswa(kon, 'Anak <Contoh>', 'P3', pemilik='guru')
        asing = database.tambah_siswa(kon, 'Anak keluarga lain', 'P3', pemilik='asing')
        # Header sesi saja cukup untuk paging; tidak memanggil generator 208 kali.
        for i in range(208):
            kon.execute('INSERT INTO sesi(siswa_id,tanggal,seed,level,topik) VALUES(?,?,?,?,?)',
                        (anak, str(date(2026,9,18)-timedelta(days=i)), i, 'P3', 'statistika' if i%2 else 'campuran'))
        kon.execute('INSERT INTO sesi(siswa_id,tanggal,seed,level,topik) VALUES(?,?,?,?,?)',
                    (asing,'2026-09-19',999,'P3','campuran'))
        yield kon, anak, asing


def _isi(kon, anak, **kw):
    siswa = kon.execute('SELECT * FROM siswa WHERE id=?',(anak,)).fetchone()
    return teacher_pages.halaman_anak(kon,siswa,pengguna='guru',privat=True,**kw).decode().split('</style>',1)[1]


def test_default_latihan_dan_hanya_tab_terpilih_dirender(db):
    kon, anak, _ = db
    isi = _isi(kon,anak)
    assert f'href="/anak/{anak}?section=latihan" aria-current="page"' in isi
    assert f'action="/sesi-baru/{anak}"' in isi
    assert f'action="/sesi-gabungan/{anak}"' in isi
    assert '<details class="atur-latihan-st"' not in isi
    assert 'class="kartu-rencana-st"' not in isi
    assert 'class="tabel-riwayat-st"' not in isi
    assert 'Lihat rencana' in isi
    assert isi.count('class="st-kartu-baris kartu-sesi-guru') <= 3


def test_208_sesi_dipaginasi_20_dan_tidak_bocor_keluarga(db):
    kon, anak, asing = db
    sebelum = tuple(kon.iterdump())
    for halaman, jumlah, awal, akhir in [(1,20,1,20),(2,20,21,40),(11,8,201,208)]:
        isi = _isi(kon,anak,query=urlencode({'section':'riwayat','halaman':halaman}))
        assert isi.count('data-sesi-id=') == jumlah
        assert f'Menampilkan {awal}–{akhir} dari 208 sesi' in isi
        assert 'Anak keluarga lain' not in isi
        assert 'data-sesi-id="209"' not in isi
        assert '<th scope="col">Pengerjaan</th>' in isi
        assert '<th scope="col">Tinjauan</th>' in isi
        assert f'action="/sesi-baru/{anak}"' not in isi
        assert 'class="kartu-rencana-st"' not in isi
    assert tuple(kon.iterdump()) == sebelum


def test_riwayat_menyebut_format_pg_dan_id_sumber_remedial(db):
    kon,anak,_=db
    pg=kon.execute("INSERT INTO sesi(siswa_id,tanggal,seed,level,topik,format_jawaban) VALUES(?,'2026-09-19',701,'P3','campuran','pilihan_ganda')",(anak,)).lastrowid
    kon.execute("UPDATE sesi SET jenis='remedial',sumber_sesi_id=1 WHERE id=2")
    isi=_isi(kon,anak,query='section=riwayat')
    satu=re.search(r'<tr data-sesi-id="%d">.*?</tr>' % pg,isi,re.S).group()
    dua=re.search(r'<tr data-sesi-id="2">.*?</tr>',isi,re.S).group()
    assert 'Pilihan ganda · latihan manual' in satu
    assert 'Remedial' in dua and 'dari sesi #1' in dua


def test_filter_bertahan_dalam_pager_dan_query_bounded(db):
    kon, anak, _ = db
    jejak=[]
    kon.set_trace_callback(jejak.append)
    isi = _isi(kon,anak,query='section=riwayat&mulai=2026-01-01&sampai=2026-09-18&topik=statistika&jenis=bebas&tinjauan=belum_dikirim')
    kon.set_trace_callback(None)
    assert 'dari 104 sesi' in isi
    assert 'halaman=2' in isi
    assert 'topik=statistika' in isi and 'tinjauan=belum_dikirim' in isi
    assert isi.count('data-sesi-id=') == 20
    assert any('LIMIT 20' in q.upper() for q in jejak)
    assert not any('SELECT * FROM sesi_soal' in q for q in jejak)


def test_filter_gabungan_topik_dan_tanggal_inklusif(db):
    kon,anak,_=db
    kon.execute("UPDATE sesi SET topik='gabungan:statistika,geometri-datar', tanggal='2026-09-18 10:00:00' WHERE id=1")
    isi=_isi(kon,anak,query='section=riwayat&mulai=2026-09-18&sampai=2026-09-18&topik=statistika')
    assert 'data-sesi-id="1"' in isi and 'dari 1 sesi' in isi


def test_ringkasan_rencana_default_memakai_reducer_bukan_sesi_manual(db):
    kon,anak,_=db
    from learning_cycle import rencana_berikutnya
    import learning_cycle_ui
    bukti=database.muat_bukti_siklus(kon,anak)
    rencana=rencana_berikutnya(bukti,anak)
    judul=learning_cycle_ui._judul(rencana,learning_cycle_ui._fokus_utama(rencana),bukti)
    isi=_isi(kon,anak)
    assert judul in isi
    assert 'class="rencana-cta-utama-st"' not in isi
    assert f'action="/siklus/{anak}/buat"' not in isi


def test_rencana_hanya_di_tab_rencana_dan_tetap_readonly(db):
    kon,anak,_=db
    sebelum=tuple(kon.iterdump())
    isi=_isi(kon,anak,query='section=rencana')
    assert isi.count('class="kartu-rencana-st"') == 1
    assert f'action="/sesi-baru/{anak}"' not in isi
    assert 'class="tabel-riwayat-st"' not in isi
    assert tuple(kon.iterdump()) == sebelum


def test_urutan_tanggal_sama_stabil_dan_sorot_tetap_milik_anak(db):
    kon,anak,asing=db
    kon.execute("UPDATE sesi SET tanggal='2026-09-18' WHERE siswa_id=?", (anak,))
    halaman_satu=_isi(kon,anak,query='section=riwayat')
    halaman_dua=_isi(kon,anak,query='section=riwayat&halaman=2')
    ids=lambda isi: [int(n) for n in re.findall('data-sesi-id="([0-9]+)"',isi)]
    assert ids(halaman_satu)==list(range(208,188,-1))
    assert ids(halaman_dua)==list(range(188,168,-1))
    kon.execute("UPDATE sesi SET selesai='2026-09-18', dikonfirmasi_guru='2026-09-18' WHERE siswa_id=?",(anak,))
    isi=_isi(kon,anak,sorot=1)
    assert 'Sesi #1<' in isi and 'sorot-baru' in isi
    assert 'Sesi #209<' not in _isi(kon,anak,sorot=209)


def test_filter_status_konfirmasi_sesuai_snapshot_bukan_stamp(db):
    kon,anak,_=db
    kon.execute("UPDATE sesi SET tujuan='pemetaan' WHERE id=1")
    # Bentuk legal konfirmasi dibuat lewat domain pada sesi dengan butir.
    sesi=database.buat_sesi(kon,anak,seed=321,jumlah_soal=1)
    butir=database.isi_sesi(kon,sesi)[0]['sesi_soal_id']
    database.tandai_selesai(kon,sesi)
    database.konfirmasi_hasil(kon,sesi,guru='guru',dilewati={butir})
    kon.execute("UPDATE sesi SET selesai='2026-09-18', dikonfirmasi_guru='2026-09-18', fingerprint_konfirmasi='palsu' WHERE id=2")
    isi=_isi(kon,anak,query='section=riwayat&tinjauan=dikonfirmasi')
    assert 'dari 1 sesi' in isi and f'data-sesi-id="{sesi}"' in isi
    assert 'data-sesi-id="2"' not in isi
    kon.execute("UPDATE sesi SET fingerprint_konfirmasi='usang' WHERE id=?",(sesi,))
    assert 'dari 0 sesi' in _isi(kon,anak,query='section=riwayat&tinjauan=dikonfirmasi')
    assert f'data-sesi-id="{sesi}"' in _isi(kon,anak,query='section=riwayat&tinjauan=ulang')
    database.batalkan_sesi(kon,sesi,'Sintetis')
    assert f'data-sesi-id="{sesi}"' not in _isi(kon,anak,query='section=riwayat&tinjauan=ulang')
    assert f'data-sesi-id="{sesi}"' in _isi(kon,anak,query='section=riwayat&tinjauan=dibatalkan')
    assert 'dari 1 sesi' in _isi(kon,anak,query='section=riwayat&jenis=terpandu')


def test_filter_kosong_dan_halaman_melampaui_total(db):
    kon,anak,_=db
    isi=_isi(kon,anak,query='section=riwayat&mulai=2027-01-01')
    assert 'Tidak ada sesi yang cocok' in isi
    assert 'Menampilkan 0–0 dari 0 sesi' in isi
    terakhir=_isi(kon,anak,query='section=riwayat&halaman=999999')
    assert 'Menampilkan 201–208 dari 208 sesi' in terakhir


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s=ServerUji(tmp_path,monkeypatch)
    with s.buka() as kon:
        anak=database.tambah_siswa(kon,'Anak navigasi','P3',pemilik='guru')
        asing=database.tambah_siswa(kon,'Anak asing','P3',pemilik='asing')
    yield s,anak,asing
    s.berhenti()


@pytest.mark.parametrize('query', ['section=asing','section=riwayat&halaman=0','section=riwayat&halaman=-1','section=riwayat&halaman=1&halaman=2','section=riwayat&mulai=2026-02-30','section=riwayat&mulai=2026-10-01&sampai=2026-09-01','section=riwayat&tinjauan=palsu','section=riwayat&jenis=hapus','section=riwayat&topik=%27%20OR%201%3D1--'])
def test_query_invalid_ditolak_tanpa_write(server,query):
    s,anak,_=server
    with s.buka() as kon: sebelum=tuple(kon.iterdump())
    assert s.minta(f'/anak/{anak}?{query}',auth=('guru',SANDI_GURU))[0] == 404
    with s.buka() as kon: assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('section',['latihan','rencana','riwayat'])
def test_keluarga_asing_404_identik_tanpa_efek_samping(server,section):
    s,_,asing=server
    with s.buka() as kon: sebelum=tuple(kon.iterdump())
    a=s.minta(f'/anak/{asing}?section={section}',auth=('guru',SANDI_GURU))
    b=s.minta(f'/anak/999999?section={section}',auth=('guru',SANDI_GURU))
    assert a[0] == b[0] == 404 and a[1] == b[1]
    with s.buka() as kon: assert tuple(kon.iterdump()) == sebelum
