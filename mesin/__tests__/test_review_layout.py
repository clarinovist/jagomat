"""Hierarki tinjauan dari HTML nyata, tanpa mengubah diagnosis atau bukti."""
from html.parser import HTMLParser

import pytest

import database
import teacher_pages
from assistant_inline import DrafButir, DrafKoreksi
from test_teacher_corrections import FormKoreksi
from test_correction_disclosure import Struktur


class Kartu(HTMLParser):
    """Baca kartu dan disclosure utama tanpa bergantung CSS."""

    def __init__(self, isi):
        super().__init__()
        self.kartu = {}
        self.sumber = []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        kelas = a.get('class', '').split()
        if 'koreksi-kartu-st' in kelas:
            self.kartu[a['id']] = (tag, a)
        if 'koreksi-sumber-st' in kelas:
            self.sumber.append(a)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'tinjauan-sintetis.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    return path


def sesi_contoh(kon, *, arsip=False):
    anak = database.tambah_siswa(kon, 'Anak Contoh', pemilik='guru')
    sesi = database.buat_sesi(kon, anak, 71, jumlah_soal=3)
    butir = database.isi_sesi(kon, sesi)
    for b in butir:
        jid = database.simpan_jawaban(kon, b['sesi_soal_id'], b['kunci'], 'Cara asli')
        database.simpan_diagnosis(kon, jid, True, None, None)
    if arsip:
        import student_submissions
        student_submissions.arsipkan(kon, sesi, 'akun')
    database.tandai_selesai(kon, sesi)
    return sesi, [b['sesi_soal_id'] for b in butir]


def test_benar_tanpa_cek_cara_bukan_tinjauan_tercatat_dan_hanya_prioritas_pertama_terbuka(db):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon)
        sebelum = tuple(kon.iterdump())
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert '0 dari 3 tinjauan tercatat' in isi
        assert '3 soal perlu ditinjau' in isi
        assert 'Periksa cara anak' in isi
        kartu = Kartu(isi).kartu
        for n, sid in enumerate(ids):
            tag, a = kartu[f'tinjau-soal-{sid}']
            assert tag == 'details'
            assert ('open' in a) == (n == 0)
        form = FormKoreksi(isi, sesi).data
        assert all(form[f'cek_pemahaman_{sid}'] == '' for sid in ids)
        assert all(f'versi_tinjauan_{sid}' in form for sid in ids)
        assert tuple(kon.iterdump()) == sebelum


def test_salah_diputuskan_guru_bisa_ringkas_dan_ragu_bukan_klaim_penguasaan(db):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon)
        b = database.isi_sesi(kon, sesi)[1]
        database.simpan_diagnosis(kon, b['jawaban_id'], False, 'H', 'H', manual=True)
        kon.execute("INSERT INTO tinjauan_guru(sesi_soal_id,revisi,pemahaman,guru) VALUES (?,1,'ragu','guru')", (ids[2],))
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert '2 dari 3 tinjauan tercatat' in isi
        kartu = Kartu(isi).kartu
        assert 'open' not in kartu[f'tinjau-soal-{ids[1]}'][1]
        assert 'open' not in kartu[f'tinjau-soal-{ids[2]}'][1]
        assert 'Jawaban tepat · Masih ragu' in isi
        assert 'Tinjauan tercatat bukan berarti materi sudah dikuasai.' in isi
        assert 'koreksi-tercatat-st' in isi


@pytest.mark.parametrize('sumber', ['setelah_bantuan', ''])
def test_galat_dan_sumber_bantuan_tidak_tersembunyi_di_kelompok_tercatat(db, sumber):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon)
        sid = ids[2]
        kon.execute("INSERT INTO tinjauan_guru(sesi_soal_id,revisi,pemahaman,provenance,catatan,guru) VALUES (?,1,'bisa_menjelaskan',?,'Catatan contoh','guru')", (sid, sumber))
        masalah = () if sumber else ((sid, 3, 'provenance'),)
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi, masalah_konfirmasi=masalah).decode()
        kartu = Kartu(isi).kartu
        assert 'open' in kartu[f'tinjau-soal-{sid}'][1]
        assert f'data-tindakan="Periksa {"sumber jawaban" if sumber else "isian yang ditandai"}"' in isi
        assert 'open' in Kartu(isi).sumber[-1]
        assert f'name="versi_tinjauan_{sid}"' in isi
        assert not Struktur(isi).tertutup(f'provenance_{sid}')


def test_jawaban_utama_dan_koreksi_sumber_native_tanpa_duplikasi_terbuka(db):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon)
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert isi.count('class="koreksi-jawaban-utama-st"') == 3
        assert len(Kartu(isi).sumber) == 3
        assert all('open' not in a for a in Kartu(isi).sumber)
        assert 'rekaman saat pengiriman belum tersedia' in isi
        assert isi.count('>Simpan draf</button>') == 1
        assert isi.count('>Konfirmasi hasil sesi</button>') == 1
        for sid in ids:
            assert isi.count(f'name="jwb_{sid}"') == 1
        assert 'Konfirmasi menyimpan semua isian dan mengesahkan hasil sesi.' in isi


@pytest.mark.parametrize('pemahaman', ['', 'bisa_menjelaskan'])
def test_t_otomatis_tidak_diringkas_meski_ada_catatan_paham(db, pemahaman):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon)
        b = database.isi_sesi(kon, sesi)[1]
        database.simpan_diagnosis(kon, b['jawaban_id'], False, 'T', 'T')
        kon.execute("INSERT INTO tinjauan_guru(sesi_soal_id,revisi,pemahaman,guru) VALUES (?,1,?,'guru')", (ids[1], pemahaman))
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        a = Kartu(isi).kartu[f'tinjau-soal-{ids[1]}'][1]
        assert a['data-tindakan'] == 'Pastikan kebutuhan pengenalan'
        assert FormKoreksi(isi, sesi).data[f'kode_{ids[1]}'] == ''


def test_koreksi_arsip_tanpa_sumber_membuka_recovery_bukan_menghapus_asli(db):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon, arsip=True)
        sid = ids[1]
        draf = DrafKoreksi(((sid, DrafButir('9999', 'benar', 'Cara asli', 'bisa_menjelaskan', False, False)),), False)
        sebelum = tuple(kon.iterdump())
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi, draf_koreksi=draf).decode()
        a = Kartu(isi).kartu[f'tinjau-soal-{sid}'][1]
        assert a['data-tindakan'] == 'Periksa sumber jawaban' and 'open' in a
        assert not Struktur(isi).tertutup(f'provenance_{sid}')
        assert 'Jawaban anak — salinan dikoreksi' in isi
        assert tuple(kon.iterdump()) == sebelum


def test_override_benar_dengan_jawaban_kosong_tetap_perlu_sumber(db):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon)
        sid = ids[0]
        draf = DrafKoreksi(((sid, DrafButir('', 'benar', 'Cara asli', 'bisa_menjelaskan', False, False)),), False)
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi, draf_koreksi=draf).decode()
        a = Kartu(isi).kartu[f'tinjau-soal-{sid}'][1]
        assert a['data-tindakan'] == 'Periksa sumber jawaban' and 'open' in a
        assert '0 dari 3 tinjauan tercatat' in isi


def test_draf_pemahaman_dikosongkan_mengembalikan_soal_ke_antrean(db):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon)
        sid = ids[0]
        kon.execute("INSERT INTO tinjauan_guru(sesi_soal_id,revisi,pemahaman,guru) VALUES (?,1,'bisa_menjelaskan','guru')", (sid,))
        b = database.isi_sesi(kon, sesi)[0]
        draf = DrafKoreksi(((sid, DrafButir(b['kunci'], '', 'Cara asli', '', False, False)),), False)
        sebelum = tuple(kon.iterdump())
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi, draf_koreksi=draf).decode()
        assert '0 dari 3 tinjauan tercatat' in isi
        assert 'open' in Kartu(isi).kartu[f'tinjau-soal-{sid}'][1]
        assert FormKoreksi(isi, sesi).data[f'cek_pemahaman_{sid}'] == ''
        assert tuple(kon.iterdump()) == sebelum
