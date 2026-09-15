"""Palang murid untuk modul pengiriman/refleksi dan atribusi sumber guru."""
import sqlite3

import pytest

import database
import review_pages
import student_submissions
from submission_pages import halaman_refleksi


@pytest.fixture()
def db_terjaga(tmp_path, monkeypatch):
    path = tmp_path / 'terjaga.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    asli = sqlite3.Row

    class RowTerjaga(asli):
        def __getitem__(self, kunci):
            if isinstance(kunci, str) and kunci in {'kunci', 'malrule_id', 'kode_usulan', 'kode_final', 'alasan'}:
                raise AssertionError(f'Kolom internal terlarang: {kunci}')
            return super().__getitem__(kunci)

    monkeypatch.setattr(sqlite3, 'Row', RowTerjaga)
    return path


def test_pengiriman_refleksi_renderer_tidak_membaca_kunci(db_terjaga):
    with database.buka(db_terjaga) as kon:
        siswa = database.tambah_siswa(kon, 'Peserta Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=2)
        ids = student_submissions.kosong(kon, sesi)
        assert len(ids) == 2
        student_submissions.simpan_refleksi(kon, sesi, {f'alasan_kosong_{ids[0]}':'langkah_awal'})
        assert student_submissions.refleksi(kon, sesi)[ids[0]] == 'langkah_awal'
        html = halaman_refleksi(kon, siswa, sesi, f'/murid/kerjakan/{sesi}').decode()
        assert 'Kirim latihan' in html and 'malrule' not in html
        student_submissions.arsipkan(kon, sesi, 'akun')
        assert kon.execute('SELECT count(*) FROM pengiriman_butir').fetchone()[0] == 2


def test_hasil_murid_status_netral_tidak_membaca_kode(db_terjaga, monkeypatch):
    import students
    import teacher_pages
    from templates import Soal
    with database.buka(db_terjaga) as kon:
        siswa = database.tambah_siswa(kon, 'Peserta Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=1)
        sid = kon.execute('SELECT id FROM sesi_soal WHERE sesi_id=?',(sesi,)).fetchone()[0]
        database.simpan_jawaban(kon,sid,'','[pilihan] bingung')
        database.tandai_selesai(kon,sesi)
        kon.execute("UPDATE sesi SET direview='2026-09-15' WHERE id=?",(sesi,))
        # Pembahasan existing adalah permukaan guru terpisah; isolasikan agar
        # guard ini membuktikan status baru tidak mengakses kode diagnosis.
        monkeypatch.setattr(teacher_pages,'_soal_dari_baris',lambda b: Soal('uji',{},'Soal sintetis','',pembahasan='Langkah sintetis'))
        hasil = students.hasil_murid(kon,siswa,sesi)
        assert hasil['soal'][0]['perlu_ditinjau']
        assert not {'kode_final','kode_usulan','alasan','malrule_id'} & set(hasil['soal'][0])


def test_warisan_tidak_mengklaim_catatan_mutable_sebagai_ucapan_anak():
    b = {'jawaban':'', 'cara':'Catatan guru yang mutable', 'restatement':'Sebagian pemahaman soal', 'belum_pernah':1}
    html, pertanyaan, kosong = review_pages.sumber_html(None, b, foto=True)
    assert 'Catatan tersimpan' in html and 'sumber awal belum tersedia' in html
    assert 'Catatan dari anak' not in html and 'Pengalaman yang dicatat anak' not in html
    assert 'Sebagian pemahaman soal' in html and 'foto' in html
    assert 'Jawaban akhir belum diisi' in html and kosong
    assert 'apa yang membuatmu belum menjawab' in pertanyaan


def test_bingung_diarsipkan_adalah_petunjuk_belum_diperjelas():
    awal = {'jawaban':'', 'cara':'[pilihan] bingung', 'restatement':'', 'belum_pernah':0, 'alasan':''}
    html, _, _ = review_pages.sumber_html(awal, {})
    assert 'bagian yang membingungkan belum diperjelas' in html
    assert 'Penyebabnya belum diketahui' not in html
