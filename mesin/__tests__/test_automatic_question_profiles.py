"""Alur baru memilih topik, bukan variasi A–D; kode lama tetap internal."""
from collections import Counter

import pytest

import account_pages
import auth
import database
import learning_cycle as siklus
import learning_cycle_service as layanan
import question_context
import topics
from generator import buat_lembar
from http_test_kit import ServerUji, SANDI_GURU


@pytest.fixture
def server(tmp_path, monkeypatch):
    srv = ServerUji(tmp_path, monkeypatch)
    with srv.buka() as kon:
        srv.siswa = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
    yield srv
    srv.berhenti()


def test_profil_topik_otomatis_stabil_dan_terdekat():
    assert question_context.profil_otomatis(['pola-bilangan'], 'P4') == 'P4'
    assert question_context.profil_otomatis(['aritmatika-lanjut'], 'P3') == 'P5'
    assert question_context.profil_otomatis(['aritmatika-lanjut'], 'P4') == 'P5'
    assert question_context.profil_otomatis(['aritmatika-lanjut'], 'P6') == 'P6'
    assert question_context.profil_otomatis(
        ['pola-bilangan', 'aritmatika-lanjut'], 'P3'
    ) == 'P5'


def test_profil_topik_otomatis_menolak_tanpa_irisan():
    asli = topics.ambil
    daftar_asli = topics.daftar_topik

    class Paket:
        komposisi = {'P3': ('a',)}

    class PaketLain:
        komposisi = {'P6': ('b',)}

    def ambil(topik):
        return Paket() if topik == 'satu' else PaketLain()

    try:
        topics.ambil = ambil
        topics.daftar_topik = lambda: ['satu', 'dua']
        try:
            question_context.profil_otomatis(['satu', 'dua'], 'P3')
        except ValueError as galat:
            assert 'bersama' in str(galat)
        else:
            raise AssertionError('profil tanpa irisan harus ditolak')
    finally:
        topics.ambil = asli
        topics.daftar_topik = daftar_asli


def test_sepuluh_soal_pola_bilangan_tetap_deterministik_dan_sah():
    paket = topics.ambil('pola-bilangan')
    for level in ('P3', 'P4', 'P5', 'P6'):
        lembar = buat_lembar(42, level=level, topik='pola-bilangan', jumlah_soal=10)
        ids = tuple(soal.template_id for soal in lembar.soal)
        assert len(ids) == 10
        assert len(set(ids)) == 10
        assert not (Counter(ids) - Counter(paket.komposisi[level]))
        ulang = buat_lembar(42, level=level, topik='pola-bilangan', jumlah_soal=10)
        assert ulang.tanda_tangan == lembar.tanda_tangan


def test_ui_latihan_baru_tidak_meminta_variasi_atau_bandingkan(server):
    kode, isi, _ = server.minta('/anak/%d?section=latihan' % server.siswa,
                                auth=('guru', SANDI_GURU))
    assert kode == 200
    manual = isi.split('id="form-latihan-manual-', 1)[1].split('</form>', 1)[0]
    gabungan = isi.split('id="form-latihan-gabungan-', 1)[1].split('</form>', 1)[0]
    for panel in (manual, gabungan):
        assert 'name="profil_parameter"' not in panel
        assert 'Bandingkan isi' not in panel
        assert 'Tampilkan pilihan isi' not in panel
        assert 'Variasi A' not in panel and 'Variasi D' not in panel
    # Tidak ada marker refresh pilihan isi, sehingga halaman tidak memuat JS khusus itu.
    assert 'data-pilihan-isi-otomatis' not in isi


def test_manual_memilih_profil_otomatis_tanpa_mengubah_rencana(server):
    with server.buka() as kon:
        kon.execute("UPDATE siswa SET tingkat='P3' WHERE id=?", (server.siswa,))
    kode, _, _ = server.minta('/sesi-baru/%d' % server.siswa,
                              auth=('guru', SANDI_GURU),
                              data={'topik': 'aritmatika-lanjut', 'jumlah_soal': '4'})
    assert kode == 200
    with server.buka() as kon:
        sesi = kon.execute('SELECT level,tujuan FROM sesi').fetchone()
        assert tuple(sesi) == ('P5', 'bebas')
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == 'P3'


def test_draf_baru_tidak_memerlukan_profil_dan_payload_lama_tetap_terbaca():
    from assistant_inline import GalatInline, parse_draf_gabungan, parse_draf_latihan
    manual = {
        'topik': ['pola-bilangan'], 'jumlah_soal': ['10'], 'mode': ['drill'],
        'hadir_timer_mode': ['1'], 'durasi_menit': ['30'], 'timer_auto': ['0'],
    }
    assert parse_draf_latihan(manual, ['pola-bilangan']).profil_parameter == ''
    assert parse_draf_latihan(
        dict(manual, profil_parameter=['P3']), ['pola-bilangan']
    ).profil_parameter == 'P3'
    gabungan = {
        'topik': ['pola-bilangan', 'statistika'], 'jumlah_soal': ['10'],
        'mode': ['drill'], 'format_jawaban': ['isian'],
    }
    assert parse_draf_gabungan(
        gabungan, topics.daftar_topik(), profil_wajib=False
    ).profil_parameter == ''
    assert parse_draf_gabungan(
        dict(gabungan, profil_parameter=['P3']), topics.daftar_topik()
    ).profil_parameter == 'P3'


def test_onboarding_tanpa_variasi_menyimpan_profil_kosong(server):
    kode, isi, _ = server.minta('/akun?section=siswa', auth=('guru', SANDI_GURU))
    assert kode == 200
    form = isi.split('name="aksi" value="anak_baru"', 1)[1].split('</form>', 1)[0]
    assert 'name="profil_parameter"' not in form
    assert 'Variasi A' not in form
    with server.buka() as kon:
        akun_awal = auth.BERKAS_SANDI.read_bytes()
        pesan, galat = account_pages.proses_akun(
            kon,
            {
                'aksi': 'anak_baru', 'nama': 'Fondasi Otomatis',
                'kelas_sekolah': '6', 'sandi_anak': 'sandi-sintetis-anak',
            },
            'guru',
        )
        assert pesan and not galat
        assert kon.execute(
            "SELECT tingkat FROM siswa WHERE nama='Fondasi Otomatis'"
        ).fetchone()[0] == ''
        assert auth.BERKAS_SANDI.read_bytes() != akun_awal


def test_pemetaan_pertama_satu_aksi_memakai_fondasi_dan_idempoten(server):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, 'Belum Disiapkan', '', pemilik='guru')
    bukti = siklus.BuktiSiklus(sid, '')
    assert siklus.rencana_berikutnya(bukti, sid).tindakan == 'pilih_variasi'
    for _ in range(2):
        kode, _, _ = server.minta('/siklus/%d/buat' % sid,
                                  auth=('guru', SANDI_GURU), data={})
        assert kode == 200
    with server.buka() as kon:
        assert kon.execute('SELECT tingkat FROM siswa WHERE id=?', (sid,)).fetchone()[0] == 'P3'
        assert [tuple(x) for x in kon.execute('SELECT level,tujuan FROM sesi WHERE siswa_id=?', (sid,))] == [('P3', 'pemetaan')]
        assert kon.execute('SELECT COUNT(*) FROM putaran_fokus WHERE siswa_id=?', (sid,)).fetchone()[0] == 1


def test_pemetaan_fondasi_gagal_rollback_semua(server, monkeypatch):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, 'Rollback Fondasi', '', pemilik='guru')
        awal = tuple(kon.iterdump())
        monkeypatch.setattr(database, 'buat_sesi_dari_rencana',
                            lambda *a, **k: (_ for _ in ()).throw(ValueError('gagal sintetis')))
        try:
            layanan.mulai_dengan_fondasi(kon, sid)
        except ValueError as galat:
            assert 'gagal sintetis' in str(galat)
        else:
            raise AssertionError('writer sintetis harus gagal')
        assert tuple(kon.iterdump()) == awal
