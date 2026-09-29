"""Pendaftaran tanpa variasi: pilihan latihan eksplisit, data seluruhnya sintetis."""
import pytest

import auth
import database
import learning_cycle as siklus
import learning_cycle_service as layanan
from http_test_kit import SANDI_GURU
from test_registration_profile import kasus, daftar
from test_registration_profile_http import server, form


@pytest.mark.parametrize('kelas', [None, 1, 4, 6])
def test_daftar_tanpa_variasi_tidak_menebak_dari_kelas(kasus, kelas):
    paths, kw = kasus
    hasil = daftar(kasus, profil_parameter=None, kelas_sekolah=kelas)
    awal = paths[1].read_bytes()
    assert daftar(kasus, profil_parameter=None, kelas_sekolah=kelas).siswa_id == hasil.siswa_id
    assert paths[1].read_bytes() == awal
    with database.buka(paths[2]) as kon:
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == ''
        assert not kon.execute('SELECT 1 FROM sesi').fetchone()
        assert not kon.execute('SELECT 1 FROM putaran_fokus').fetchone()


@pytest.mark.parametrize('titik', ['sebelum_intent', 'setelah_intent', 'setelah_db', 'setelah_auth'])
def test_daftar_kosong_crash_retry_tepat_satu(kasus, titik):
    import admin_registration as reg
    paths, kw = kasus
    with pytest.raises(reg.RegistrasiBelumSelesai):
        daftar(kasus, profil_parameter=None, failpoint=titik)
    hasil = daftar(kasus, profil_parameter=None)
    assert hasil.siswa_id and auth.autentikasi(kw['alias'], kw['sandi'], paths[1])
    with database.buka(paths[2]) as kon:
        assert [tuple(b) for b in kon.execute('SELECT tingkat FROM siswa')] == [('',)]
        assert kon.execute('SELECT COUNT(*) FROM registrasi_profil_anak').fetchone()[0] == 1


def test_pending_tanpa_variasi_tidak_boleh_berubah_jadi_pilihan(kasus):
    import admin_registration as reg
    paths, _ = kasus
    with pytest.raises(reg.RegistrasiBelumSelesai):
        daftar(kasus, profil_parameter=None, failpoint='setelah_db')
    awal = paths[1].read_bytes()
    with pytest.raises(ValueError):
        daftar(kasus, profil_parameter='P3')
    assert paths[1].read_bytes() == awal
    with database.buka(paths[2]) as kon:
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == ''


def test_http_daftar_baru_dan_semua_halaman_profil(server):
    data = form(server)
    data.pop('profil_parameter', None)
    server.minta('/daftar', data=data)
    assert auth.cari_akun(data['nama'])
    with server.buka() as kon:
        siswa = kon.execute('SELECT * FROM siswa').fetchone()
        assert siswa['tingkat'] == ''
        sid = siswa['id']
        awal = tuple(kon.iterdump())
    login = (data['nama'], data['sandi'])
    for url in ('/', '/akun', '/anak/%d' % sid, '/anak/%d?section=rencana' % sid,
                '/anak/%d?section=riwayat' % sid, '/laporan/%d' % sid,
                '/laporan/%d?section=penguasaan' % sid):
        kode, isi, _ = server.minta(url, auth=login)
        assert kode == 200, (url, kode)
        assert 'Konfigurasi lama: ' not in isi
        if url == '/anak/%d' % sid:
            assert '<legend>Pilih isi latihan</legend>' in isi
            assert '<input type="radio" name="profil_parameter" value="P3" checked' not in isi
            assert 'data-contoh="pola-bilangan:P3"' in isi
        if 'section=rencana' in url:
            assert 'Pilih isi untuk pemetaan pertama' in isi
            assert 'Contoh salah satu materi:' in isi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == awal


def siswa_baru(server):
    with server.buka() as kon:
        return database.tambah_siswa(kon, 'Profil Belum Dipilih', '', pemilik='guru')


def test_reducer_belum_dipilih_tidak_merekomendasikan_pemetaan():
    bukti = siklus.BuktiSiklus(1, '')
    rencana = siklus.rencana_berikutnya(bukti, 1)
    assert rencana.tindakan == 'pilih_variasi'
    assert rencana.putaran is None
    assert siklus.pengingat_berikutnya(bukti, 1) is None
    assert siklus.prioritas_warisan(bukti) is None


def test_service_tanpa_pilihan_tidak_membuat_putaran(server, monkeypatch):
    sid = siswa_baru(server)
    def dilarang(*args, **kwargs):
        pytest.fail('profil kosong tidak boleh mencapai writer putaran')
    monkeypatch.setattr(database, 'buat_putaran_fokus', dilarang)
    with server.buka() as kon:
        awal = tuple(kon.iterdump())
        with pytest.raises(ValueError, match='variasi'):
            layanan.buat_dari_rekomendasi(kon, sid)
        assert tuple(kon.iterdump()) == awal


@pytest.mark.parametrize('data', [{}, {'profil_parameter': ''}, {'profil_parameter': 'asing'},
    {'profil_parameter': 'P3', 'kelas_sekolah': '3'},
    [('profil_parameter', 'P3'), ('profil_parameter', 'P6')]])
def test_http_persiapan_invalid_tanpa_efek(server, data):
    sid = siswa_baru(server)
    with server.buka() as kon:
        awal = tuple(kon.iterdump())
    kode, _, _ = server.minta('/siklus/%d/buat' % sid, auth=('guru', SANDI_GURU), data=data)
    assert kode in (400, 409)
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == awal


def test_http_persiapan_eksplisit_idempoten_dan_tab_lama(server):
    sid = siswa_baru(server)
    data = {'profil_parameter': 'P4'}
    for _ in range(2):
        kode, _, _ = server.minta('/siklus/%d/buat' % sid, auth=('guru', SANDI_GURU), data=data)
        assert kode == 200
    with server.buka() as kon:
        assert kon.execute('SELECT tingkat FROM siswa WHERE id=?', (sid,)).fetchone()[0] == 'P4'
        assert [tuple(b) for b in kon.execute('SELECT level,tujuan FROM sesi')] == [('P4', 'pemetaan')]
        assert kon.execute('SELECT COUNT(*) FROM putaran_fokus').fetchone()[0] == 1
        assert not kon.execute("SELECT 1 FROM kejadian_belajar WHERE jenis='diganti_level'").fetchone()
        awal = tuple(kon.iterdump())
    kode, _, _ = server.minta('/siklus/%d/buat' % sid, auth=('guru', SANDI_GURU),
                              data={'profil_parameter': 'P6'})
    assert kode == 409
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == awal


def test_retry_persiapan_tidak_mengambil_pemetaan_histori(server):
    sid = siswa_baru(server)
    with server.buka() as kon:
        layanan.mulai_dengan_variasi(kon, sid, 'P4')
        database.ganti_level(kon, sid, 'P6')
        awal = tuple(kon.iterdump())
        with pytest.raises(ValueError, match='sudah dipilih'):
            layanan.mulai_dengan_variasi(kon, sid, 'P4')
        assert tuple(kon.iterdump()) == awal


def test_persiapan_gagal_membuat_sesi_rollback_variasi(server, monkeypatch):
    sid = siswa_baru(server)
    def gagal(*args, **kwargs):
        raise ValueError('gagal sintetis setelah pilihan')
    monkeypatch.setattr(database, 'buat_sesi_dari_rencana', gagal)
    with server.buka() as kon:
        awal = tuple(kon.iterdump())
        with pytest.raises(ValueError, match='gagal sintetis'):
            layanan.mulai_dengan_variasi(kon, sid, 'P4')
        assert tuple(kon.iterdump()) == awal


def test_http_persiapan_asing_dan_hilang_identik(server):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, 'Profil Asing', '', pemilik='keluarga-lain')
        awal = tuple(kon.iterdump())
    respons = []
    for nomor in (sid, 999999):
        kode, isi, _ = server.minta('/siklus/%d/buat' % nomor, auth=('guru', SANDI_GURU),
                                    data={'profil_parameter': 'P4'})
        assert kode == 404
        respons.append(isi)
    assert respons[0] == respons[1]
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == awal


@pytest.mark.parametrize('nilai', ['', 'P1', 'P7', 4, False, [], ' P3'])
def test_registrasi_nilai_cacat_tetap_ditolak(kasus, nilai):
    paths, _ = kasus
    awal = paths[1].read_bytes()
    with pytest.raises(ValueError, match='variasi'):
        daftar(kasus, profil_parameter=nilai)
    assert paths[1].read_bytes() == awal
    with database.buka(paths[2]) as kon:
        assert not kon.execute('SELECT 1 FROM siswa').fetchone()


def test_http_retry_form_lama_mempertahankan_pilihan_exact(server, monkeypatch):
    import re
    import admin_registration as reg
    data = form(server)
    asli = reg.daftar_dengan_profil
    def gagal(*args, **kwargs):
        return asli(*args, **kwargs, failpoint='setelah_db')
    monkeypatch.setattr(reg, 'daftar_dengan_profil', gagal)
    kode, isi, _ = server.minta('/daftar', data=data)
    assert kode == 503
    assert re.search(r'<input type="hidden" name="profil_parameter" value="P4">', isi)
    assert '<select id="daftar-anak-profil"' not in isi
    monkeypatch.setattr(reg, 'daftar_dengan_profil', asli)
    server.minta('/daftar', data=data)
    assert auth.cari_akun(data['nama'])
    with server.buka() as kon:
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == 'P4'


def test_http_persiapan_origin_asing_dan_murid_ditolak(server):
    sid = siswa_baru(server)
    auth.tambah_akun('murid-sintetis', 'sandi-murid-sintetis', 'murid', siswa_id=sid)
    with server.buka() as kon:
        awal = tuple(kon.iterdump())
    kode, _, _ = server.minta('/siklus/%d/buat' % sid, auth=('guru', SANDI_GURU),
        data={'profil_parameter': 'P4'}, headers={'Origin': 'https://asing.invalid'})
    assert kode == 403
    import sessions
    principal = auth.autentikasi('murid-sintetis', 'sandi-murid-sintetis')
    cookie = sessions.buat_dari_principal(principal)
    assert cookie
    kode, _, _ = server.minta('/siklus/%d/buat' % sid,
        cookie=cookie, data={'profil_parameter': 'P4'})
    assert kode == 401  # Permukaan guru menolak sesi murid sebelum dispatcher.
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == awal


def test_pilot_tetap_boleh_tanpa_memilih_variasi_rencana(server):
    from skill_pilot import LANGSUNG
    from skill_pilot_service import revisi
    sid = siswa_baru(server)
    with server.buka() as kon:
        data = {'aksi': 'mulai', 'revisi': revisi(kon, sid), 'tuntutan': LANGSUNG,
                'profil': 'P3', 'representasi': 'teks-v1'}
    kode, _, _ = server.minta('/siklus/%d/pilot' % sid, auth=('guru', SANDI_GURU), data=data)
    assert kode == 200
    kode, isi, _ = server.minta('/anak/%d?section=rencana' % sid, auth=('guru', SANDI_GURU))
    assert kode == 200 and 'Lanjutkan sesi pilot' in isi
    with server.buka() as kon:
        assert kon.execute('SELECT tingkat FROM siswa WHERE id=?', (sid,)).fetchone()[0] == ''
        assert kon.execute('SELECT COUNT(*) FROM pilot_sesi').fetchone()[0] == 1


def test_manual_memilih_variasi_tanpa_mengubah_rencana(server):
    sid = siswa_baru(server)
    kode, _, _ = server.minta('/sesi-baru/%d' % sid, auth=('guru', SANDI_GURU),
                              data={'profil_parameter': 'P4', 'topik': 'pola-bilangan', 'jumlah_soal': '4'})
    assert kode == 200
    with server.buka() as kon:
        assert kon.execute('SELECT tingkat FROM siswa WHERE id=?', (sid,)).fetchone()[0] == ''
        assert [tuple(b) for b in kon.execute('SELECT level,tujuan FROM sesi')] == [('P4', 'bebas')]
        assert not kon.execute('SELECT 1 FROM putaran_fokus').fetchone()
