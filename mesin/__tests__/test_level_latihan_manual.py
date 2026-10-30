"""P1/P2 hanya variasi Latihan; tingkat siswa dan pilot tetap tertutup."""
from dataclasses import replace
import re

import pytest

import account_pages
import admin_contracts as kontrak
import admin_journal_store
import admin_queries
import database
import landing
import learning_cycle_service as siklus
import question_context as konteks
import question_variants_ui as variasi
import skill_pilot
import templates
import topics
from test_new_student import db
from test_registration_profile import kasus, daftar
from test_account_audit_http import server
from http_test_kit import SANDI_GURU


DASAR = ('P1', 'P2')
TINGKAT = ('P3', 'P4', 'P5', 'P6')


def test_himpunan_level_dan_bawaan():
    assert templates.LEVEL == DASAR + TINGKAT
    assert hasattr(templates, 'LEVEL_TINGKAT')
    assert templates.LEVEL_TINGKAT == TINGKAT
    assert set(templates.LEVEL_TINGKAT) < set(templates.LEVEL)
    assert templates.LEVEL_BAWAAN in templates.LEVEL_TINGKAT


@pytest.mark.parametrize('nilai', [None, [], {}, set(), 1, True, '', 'p3', *DASAR, *TINGKAT])
def test_guard_tingkat_semantik_tuple(nilai):
    assert hasattr(templates, 'tingkat_valid')
    assert templates.tingkat_valid(nilai) is (nilai in TINGKAT)


@pytest.mark.parametrize('profil', DASAR)
def test_bentuk_latihan_dasar_hanya_untuk_konten_yang_disetujui(profil):
    assert templates.level_valid(profil)
    assert konteks.profil_dari_form({'profil_parameter': [profil]}) == profil
    for topik in topics.daftar_topik():
        if topik == 'bilangan-dasar':
            assert profil in topics.ambil(topik).komposisi
            konteks.validasi_pilihan([topik], profil)
        else:
            assert profil not in topics.ambil(topik).komposisi
            with pytest.raises(ValueError, match='Materi tidak tersedia'):
                konteks.validasi_pilihan([topik], profil)


@pytest.mark.parametrize('profil,label', [('P1', 'Variasi Dasar 1'), ('P2', 'Variasi Dasar 2')])
def test_label_dasar_dan_kelas(profil, label):
    assert konteks.label_profil_parameter(profil) == label
    assert templates.label_kelas(profil) == 'Kelas ' + profil[1:]
    assert '<option value="%s">%s</option>' % (profil, label) in variasi.kontrol_variasi('uji')


def test_penanda_enam_level_tidak_ambigu(monkeypatch):
    monkeypatch.setattr(variasi, '_contoh_isi', lambda *a: ('Contoh sintetis', '<p>Soal sintetis</p>'))
    penanda = []
    for profil in DASAR + TINGKAT:
        isi = variasi._kartu_isi(profil, ('pola-bilangan',), 'uji', None)
        cocok = re.search(r'Pilihan </span>([^<]+)</span>', isi)
        assert cocok
        penanda.append(cocok[1])
    assert penanda == ['Dasar 1', 'Dasar 2', 'A', 'B', 'C', 'D']
    assert len(set(penanda)) == 6


def test_campuran_dan_pemetaan_tidak_menawarkan_dasar(monkeypatch):
    # Simulasikan komposisi tahap berikutnya tanpa menambahkan konten aplikasi.
    paket = topics.ambil('pola-bilangan')
    for profil in DASAR:
        monkeypatch.setitem(paket.komposisi, profil, paket.komposisi['P3'])
    monkeypatch.delitem(topics.PAKET, 'campuran')
    topics._daftarkan_campuran()
    try:
        campuran = topics.ambil('campuran')
        assert set(campuran.komposisi) == set(TINGKAT)
        assert set(campuran.komposisi_writer) == set(TINGKAT)
        for isi in (variasi.pemilih_isi(('campuran',), 'uji'), variasi.pemilih_pemetaan('uji')):
            assert all('value="%s"' % p not in isi for p in DASAR)
            assert all('value="%s"' % p in isi for p in TINGKAT)
    finally:
        del topics.PAKET['campuran']


@pytest.fixture
def topik_dasar_sintetis(monkeypatch):
    from types import SimpleNamespace
    paket = SimpleNamespace(id='dasar-sintetis', komposisi={
        'P1': ('soal_dasar_1',), 'P2': ('soal_dasar_2',),
    })
    daftar = {paket.id: paket}
    monkeypatch.setattr(topics, 'daftar_topik', lambda: list(daftar))
    monkeypatch.setattr(topics, 'ambil', daftar.__getitem__)
    return paket


@pytest.mark.parametrize('acuan', ('P3', 'P1', 'P2', 'P4', 'P5', 'P6', '', 'teks-lama'))
def test_profil_otomatis_topik_dasar_memilih_level_sesi(topik_dasar_sintetis, acuan):
    assert konteks.profil_otomatis([topik_dasar_sintetis.id], acuan) == 'P2'


@pytest.mark.parametrize('acuan,harapan', [('P3', 'P2'), ('P1', 'P1'), ('P2', 'P2'),
                                         ('teks-lama', 'P2')])
def test_level_terdekat_topik_dasar_memilih_level_sesi(topik_dasar_sintetis, acuan, harapan):
    import session_store
    assert session_store._level_terdekat(acuan, topik_dasar_sintetis.komposisi) == harapan


@pytest.mark.parametrize('acuan', TINGKAT + ('', 'teks-lama'))
@pytest.mark.parametrize('topik', topics.daftar_topik())
def test_pemilih_level_sesi_topik_nyata_tetap_seperti_d0(topik, acuan):
    import session_store
    if topik == 'bilangan-dasar':
        assert set(topics.ambil(topik).komposisi) == set(DASAR)
        assert konteks.profil_otomatis([topik], acuan) == 'P2'
        assert session_store._level_terdekat(acuan, DASAR) == 'P2'
        return
    tersedia = [p for p in TINGKAT if p in topics.ambil(topik).komposisi]
    assert tersedia
    asal = acuan if acuan in TINGKAT else 'P3'
    harapan = min(tersedia, key=lambda p: (abs(TINGKAT.index(p) - TINGKAT.index(asal)),
                                         TINGKAT.index(p)))
    assert konteks.profil_otomatis([topik], acuan) == harapan
    assert session_store._level_terdekat(acuan, tersedia) == harapan


@pytest.mark.parametrize('profil', DASAR)
@pytest.mark.parametrize('pintu', ['store', 'facade'])
def test_guard_tambah_siswa_tanpa_efek(db, profil, pintu):
    import student_profile_store
    tambah = student_profile_store.tambah_siswa if pintu == 'store' else database.tambah_siswa
    awal = tuple(db.iterdump())
    with pytest.raises(ValueError, match='tingkat'):
        tambah(db, 'Sintetis Dasar', profil, pemilik='guru')
    assert tuple(db.iterdump()) == awal


@pytest.mark.parametrize('profil', DASAR)
def test_guard_ganti_level_tanpa_efek(db, profil):
    sid = database.tambah_siswa(db, 'Sintetis', 'P3', pemilik='guru')
    awal = tuple(db.iterdump())
    with pytest.raises(ValueError, match='tingkat'):
        database.ganti_level(db, sid, profil)
    assert tuple(db.iterdump()) == awal


@pytest.mark.parametrize('profil', DASAR)
def test_guard_siklus_sebelum_writer(db, monkeypatch, profil):
    sid = database.tambah_siswa(db, 'Sintetis', '', pemilik='guru')
    panggilan = []
    monkeypatch.setattr(siklus, 'buat_dari_rekomendasi', lambda *a: panggilan.append(a) or (1, True))
    awal = tuple(db.iterdump())
    with pytest.raises(ValueError, match='variasi'):
        siklus.mulai_dengan_variasi(db, sid, profil)
    assert not panggilan
    assert tuple(db.iterdump()) == awal


@pytest.mark.parametrize('profil', DASAR)
@pytest.mark.parametrize('field', ['expected_level', 'level_baru'])
def test_guard_kontrak_admin_ubah_level(profil, field):
    data = dict(operasi_id='operasi_level_1', actor_id='actor_sintetis', actor_revisi=1,
                aksi=kontrak.AKSI_UBAH_LEVEL, siswa_id=1, expected_level='P3', level_baru='P4',
                token_tinjauan='K' * 48)
    kontrak.PerintahSiswa(**data)
    with pytest.raises(kontrak.KontrakTidakSah, match='level'):
        kontrak.PerintahSiswa(**{**data, field: profil})


@pytest.mark.parametrize('profil', DASAR)
def test_guard_kontrak_admin_hapus(profil):
    with pytest.raises(kontrak.KontrakTidakSah, match='level'):
        kontrak.PerintahHapusSiswa('operasi_hapus_1', 'actor_sintetis', 1,
                                  kontrak.AKSI_HAPUS_SISWA, 1, profil, token_tinjauan='K' * 48)


@pytest.mark.parametrize('profil', DASAR)
def test_guard_audit_tingkat(profil):
    with pytest.raises(admin_journal_store.DataAuditTidakSah):
        admin_journal_store._validasi_nilai_audit('student_level', profil)


@pytest.mark.parametrize('profil', DASAR)
def test_guard_filter_tingkat(profil):
    with pytest.raises(admin_queries.InputQueryTidakSah, match='tingkat'):
        admin_queries.daftar_siswa(None, None, tingkat=profil)


@pytest.mark.parametrize('profil', DASAR)
@pytest.mark.parametrize('aksi', ['anak_baru', 'tingkat'])
def test_guard_akun_programatis(db, profil, aksi):
    sid = database.tambah_siswa(db, 'Sintetis Lama', 'P3', pemilik='guru')
    awal = tuple(db.iterdump())
    _, galat = account_pages.proses_akun(db, dict(aksi=aksi, nama='Sintetis Baru',
        tingkat=profil, siswa_id=str(sid), sandi_anak='sandi-sintetis-panjang'), 'guru')
    assert galat
    assert tuple(db.iterdump()) == awal


@pytest.mark.parametrize('profil', DASAR)
def test_guard_registrasi_profil_sebelum_intent(kasus, profil):
    paths, _ = kasus
    awal_auth = paths[1].read_bytes()
    with database.buka(paths[2]) as kon:
        awal = tuple(kon.iterdump())
    with pytest.raises(ValueError, match='variasi'):
        daftar(kasus, profil_parameter=profil)
    assert paths[1].read_bytes() == awal_auth
    with database.buka(paths[2]) as kon:
        assert tuple(kon.iterdump()) == awal


@pytest.mark.parametrize('profil', DASAR)
def test_guard_form_retry_registrasi(profil):
    assert b'name="profil_parameter"' not in landing.halaman_daftar(profil_parameter=profil)


@pytest.mark.parametrize('profil', DASAR)
def test_guard_http_akun_dan_siklus(server, profil):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, 'Sintetis Kosong', '', pemilik='guru')
        awal = tuple(kon.iterdump())
    kode, _, _ = server.minta('/akun', auth=('guru', SANDI_GURU), data=dict(
        aksi='anak_baru', nama='Sintetis Baru', profil_parameter=profil,
        sandi_anak='sandi-sintetis-panjang'))
    assert kode == 409
    kode, _, _ = server.minta('/siklus/%d/buat' % sid, auth=('guru', SANDI_GURU),
                              data={'profil_parameter': profil})
    assert kode == 409
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == awal


@pytest.mark.parametrize('profil', ('',) + TINGKAT)
def test_tingkat_lama_dan_kosong_tetap_dapat_disimpan(db, profil):
    sid = database.tambah_siswa(db, 'Sintetis', profil, pemilik='guru')
    assert db.execute('SELECT tingkat FROM siswa WHERE id=?', (sid,)).fetchone()[0] == profil
    for baru in TINGKAT:
        database.ganti_level(db, sid, baru)
        assert db.execute('SELECT tingkat FROM siswa WHERE id=?', (sid,)).fetchone()[0] == baru


@pytest.mark.parametrize('profil', DASAR)
def test_draf_pendamping_tetap_menerima_bentuk_dasar(profil):
    from assistant_inline import parse_draf_latihan
    data = dict(topik=['pola-bilangan'], jumlah_soal=['10'], mode=['drill'],
                hadir_timer_mode=['1'], durasi_menit=['15'], timer_auto=['0'],
                profil_parameter=[profil])
    assert parse_draf_latihan(data, ['pola-bilangan']).profil_parameter == profil


def test_opsi_admin_hanya_tingkat():
    from types import SimpleNamespace
    import admin_pages
    import admin_daftar_pages
    from test_admin_pages import _siswa
    data = _siswa()
    isi = admin_pages.form_tindakan_siswa(SimpleNamespace(siswa=data.item[0]), 'csrf', 'token')
    daftar_isi = admin_daftar_pages.render_siswa(data, (), csrf='csrf')
    for markup in (isi, daftar_isi):
        opsi = re.findall(r'<option value="(P[0-9]+)"', markup)
        assert tuple(opsi) == TINGKAT


@pytest.mark.parametrize('profil', DASAR)
def test_target_terpandu_dan_pilihan_campuran_tidak_mengikuti_dasar(monkeypatch, profil):
    import mastery_catalog
    import teacher_workspace
    paket = topics.ambil('pola-bilangan')
    monkeypatch.setitem(paket.komposisi, profil, paket.komposisi['P3'])
    assert mastery_catalog.katalog_target(profil) == ()
    assert 'campuran' not in teacher_workspace._topik_untuk_level(profil)


def test_pilot_tetap_empat_level():
    from skill_pilot_contract import KontrakPilot, ButirKontrakPilot
    from skill_pilot_ui import form_mulai
    assert hasattr(skill_pilot, 'LEVEL_PILOT')
    assert skill_pilot.LEVEL_PILOT == TINGKAT
    isi = form_mulai(1, 1)
    assert all('value="%s"' % p not in isi for p in DASAR)
    for profil in DASAR:
        with pytest.raises(ValueError):
            skill_pilot.KonteksPilot(skill_pilot.LANGSUNG, profil, 'teks-v1')
    k = skill_pilot.KonteksPilot(skill_pilot.LANGSUNG, 'P3', 'teks-v1')
    butir = ButirKontrakPilot(1, 1, k, 'a' * 64, 'b' * 64)
    sah = KontrakPilot(1, 1, 'P3', 1, (butir,))
    for profil in DASAR:
        with pytest.raises(ValueError, match='kontrak pilot tidak sah'):
            replace(sah, profil_parameter=profil)
