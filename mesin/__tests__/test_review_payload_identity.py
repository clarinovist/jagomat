"""Golden payload sintetis diturunkan dari baseline sebelum perapihan tinjauan.

Fixture berisi tepat sepuluh butir; digest token versi boleh berubah bersama
implementasinya sehingga dihitung oleh review_store, bukan disalin sebagai data.
Field selain token dibandingkan persis, termasuk field kosong dan checkbox absen.
"""
import pytest

import database
import review_store
import teacher_pages
from assistant_inline import DrafButir, DrafKoreksi
from test_teacher_corrections import FormKoreksi


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / 'payload.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    return path


@pytest.mark.parametrize('mode,fmt', [('diagnostik','isian'),('drill','isian'),
                                     ('diagnostik','pilihan_ganda'),('drill','pilihan_ganda')])
@pytest.mark.parametrize('pakai_draf', [False, True])
def test_field_sesi_tertutup_sama_dengan_baseline_kontrak(db, mode, fmt, pakai_draf):
    with database.buka(db) as kon:
        anak = database.tambah_siswa(kon, 'Anak Payload Sintetis', 'P3', pemilik='guru')
        sesi = database.buat_sesi(kon, anak, 71, jumlah_soal=10, mode=mode, format_jawaban=fmt)
        database.tandai_selesai(kon, sesi)
        butir = database.isi_sesi(kon, sesi)
        ids = [b['sesi_soal_id'] for b in butir]
        draf = None
        if pakai_draf:
            draf = DrafKoreksi(tuple((sid,DrafButir(
                '', 'H', 'Cara sintetis', 'ragu', True, True,
                'Catatan sintetis', 'setelah_bantuan', 'Hasil bantuan', review_store.tanda(kon,sid)
            )) for sid in ids), False)
        awal = tuple(kon.iterdump())
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi, draf_koreksi=draf).decode()
        harap = {'hadir_sertakan_pemetaan':'1'}
        for sid in ids:
            harap.update({
                f'jwb_{sid}':'', f'kode_{sid}':'H' if pakai_draf else '',
                f'cek_pemahaman_{sid}':'ragu' if pakai_draf else '',
                f'hadir_belum_{sid}':'1', f'hadir_dilewati_{sid}':'1',
                f'catatan_tinjauan_{sid}':'Catatan sintetis' if pakai_draf else '',
                f'provenance_{sid}':'setelah_bantuan' if pakai_draf else '',
                f'jawaban_bantuan_{sid}':'Hasil bantuan' if pakai_draf else '',
                f'versi_tinjauan_{sid}':review_store.tanda(kon,sid),
            })
            if mode!='drill' or fmt=='pilihan_ganda':
                harap[f'cara_{sid}']='Cara sintetis' if pakai_draf else ''
            if pakai_draf:
                harap[f'belum_{sid}']='1'
                harap[f'dilewati_{sid}']='1'
        assert FormKoreksi(isi,sesi).data == harap
        assert f'formaction="/sesi/{sesi}/tinjauan"' in isi
        assert f'formaction="/sesi/{sesi}/konfirmasi"' in isi
        assert tuple(kon.iterdump()) == awal
