"""Label rentang kelas di pemilih topik Latihan dan keterangan Gabungan (data sintetis)."""
import re

import pytest

import database
import practice_workspace
import question_context
import teacher_pages
import topics
from practice_workspace import rentang_kelas


@pytest.fixture()
def halaman(tmp_path, monkeypatch):
    path = tmp_path / 'label-kelas-sintetis.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)

    def render(materi_dasar=True):
        monkeypatch.setattr(question_context, 'materi_dasar_aktif', lambda: materi_dasar)
        with database.buka(path) as kon:
            sid = database.tambah_siswa(kon, 'Anak Contoh', 'P3', pemilik='guru')
            siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (sid,)).fetchone()
            return teacher_pages.halaman_anak(
                kon, siswa, pengguna='guru', privat=True, query='section=latihan&mode_latihan=gabungan'
            ).decode()
    return render


@pytest.mark.parametrize('level, harapan', [
    (('P1', 'P2'), 'Kelas 1–2'),
    (('P5', 'P6'), 'Kelas 5–6'),
    (('P3', 'P5', 'P6'), 'Kelas 3, 5–6'),
    (('P4',), 'Kelas 4'),
    (('P6', 'P3', 'P4', 'P5'), 'Kelas 3–6'),
])
def test_rentang_kelas_meringkas_level_tanpa_menyiratkan_kelas_yang_tak_ada(level, harapan):
    assert rentang_kelas(level) == harapan


def test_pilih_satu_topik_memberi_label_kelas_sesuai_komposisi(halaman):
    isi = halaman()
    assert re.search(r'<option value="bilangan-dasar"[^>]*>Bilangan Dasar \(Kelas 1–2\)</option>', isi)
    assert '<option value="aritmetika-dasar">Aritmetika Dasar (Kelas 5–6)</option>' in isi
    for k in topics.daftar_topik():
        harapan = rentang_kelas(topics.ambil(k).komposisi)
        assert re.search(rf'<option value="{re.escape(k)}"[^>]*>[^<]*\({harapan}\)</option>', isi), k


def test_gabungan_memberi_label_kelas_dan_keterangan_topik_kelas_1_2(halaman):
    isi = halaman()
    gabungan = isi[isi.index('Pilih dua topik atau lebih.'):]
    assert 'value="bilangan-dasar"' not in gabungan
    assert '> Aritmetika Dasar (Kelas 5–6)</label>' in gabungan
    assert 'Bilangan Dasar (Kelas 1–2) tidak bisa digabung' in gabungan
    assert '“Pilih satu topik”' in gabungan


def test_keterangan_gabungan_tidak_muncul_bila_materi_dasar_belum_dibuka(halaman):
    isi = halaman(materi_dasar=False)
    assert 'Bilangan Dasar' not in isi
    assert 'tidak bisa digabung' not in isi


def test_label_hanya_teks_nilai_form_tetap_id_topik(halaman):
    isi = halaman()
    nilai = set(re.findall(r'<option value="([^"]*)"', isi)) | set(re.findall(r'name="topik" value="([^"]*)"', isi))
    assert set(practice_workspace.daftar_topik_latihan()) <= nilai | {''}
    assert not any('Kelas' in v for v in nilai)
