"""Profil sekolah sintetis: metadata bukan konfigurasi atau bukti belajar."""
from html.parser import HTMLParser

import pytest

import account_pages
import auth
import database
import learning_profile
from learning_cycle import rencana_berikutnya


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / 'profil-ui.db'
    database.siapkan(path)
    monkeypatch.setattr(auth, 'BERKAS_SANDI', tmp_path / 'auth-sintetis.json')
    auth.simpan_sandi('sandi-sintetis-guru', 'guru')
    with database.buka(path) as kon:
        yield kon


class Formulir(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.form = []
        self.kini = None
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        nilai = dict(attrs)
        if tag == 'form':
            assert self.kini is None, 'form tidak boleh bersarang'
            self.kini = {'attrs': nilai, 'input': [], 'select': [], 'option': []}
        elif self.kini is not None and tag in ('input', 'select', 'option'):
            self.kini[tag].append(nilai)

    def handle_endtag(self, tag):
        if tag == 'form':
            self.form.append(self.kini)
            self.kini = None

    def aksi(self, aksi):
        return [f for f in self.form if any(i.get('name') == 'aksi' and i.get('value') == aksi for i in f['input'])]


def _data(sid, kelas='4', revisi='0'):
    return dict(aksi='kelas_sekolah', siswa_id=str(sid), kelas_sekolah=kelas, revisi_profil=revisi)


def _histori(kon):
    tabel = ('siswa', 'soal', 'sesi', 'sesi_soal', 'jawaban', 'diagnosis',
             'putaran_fokus', 'anggota_fokus', 'konfirmasi_hasil',
             'snapshot_outcome', 'penyajian_outcome', 'kejadian_belajar')
    return {nama: tuple(tuple(b) for b in kon.execute('SELECT * FROM ' + nama + ' ORDER BY rowid')) for nama in tabel}


def test_form_kelas_tidak_menebak_pn_dan_get_tanpa_tulis(db):
    sid = database.tambah_siswa(db, 'Sintetis', 'P6', pemilik='guru')
    sebelum = db.total_changes
    isi = account_pages.halaman_akun(db, pengguna='guru', section='siswa').decode()
    formulir = Formulir(isi)
    kelas = formulir.aksi('kelas_sekolah')
    assert len(kelas) == 1
    assert any(i.get('name') == 'revisi_profil' and i.get('value') == '0' for i in kelas[0]['input'])
    assert [(o.get('value'), 'selected' in o) for o in kelas[0]['option']] == [('', True)] + [(str(n), False) for n in range(1, 7)]
    assert 'Kelas belum diisi' in isi and 'Konteks latihan: Profil' not in isi
    assert 'tidak menentukan kemampuan' in isi
    assert not formulir.aksi('tingkat')
    assert db.total_changes == sebelum
    assert learning_profile.baca(db, sid, pemilik='guru').kelas_sekolah is None


def test_perubahan_kelas_lewat_akun_hanya_metadata(db, monkeypatch):
    sid = database.tambah_siswa(db, 'Sintetis', 'P5', pemilik='guru')
    database.buat_putaran_fokus(db, sid, 'P5')
    sesi = database.buat_sesi(db, sid, 42, level='P5', jumlah_soal=1)
    butir = database.isi_sesi(db, sesi)[0]
    jawaban = database.simpan_jawaban(db, butir['sesi_soal_id'], butir['kunci'], 'Langkah sintetis')
    database.simpan_diagnosis(db, jawaban, benar=True, kode_usulan=None, kode_final=None)
    database.tandai_selesai(db, sesi)
    database.konfirmasi_hasil(db, sesi, 'guru')
    sebelum = _histori(db)
    bukti = database.muat_bukti_siklus(db, sid)
    def terlarang(*args, **kwargs):
        pytest.fail('kelas sekolah tidak boleh memanggil ganti_level')
    monkeypatch.setattr(database, 'ganti_level', terlarang)
    for kelas, revisi in [('1', '0'), ('6', '1'), ('', '2')]:
        pesan, galat = account_pages.proses_akun(db, _data(sid, kelas, revisi), 'guru')
        assert pesan and not galat
        assert learning_profile.baca(db, sid, pemilik='guru').kelas_sekolah == (int(kelas) if kelas else None)
        assert _histori(db) == sebelum
        sesudah = database.muat_bukti_siklus(db, sid)
        assert sesudah == bukti
        assert rencana_berikutnya(sesudah, sid) == rencana_berikutnya(bukti, sid)


def test_retry_stale_noop_tidak_menggandakan_perubahan(db):
    sid = database.tambah_siswa(db, 'Sintetis', 'P5', pemilik='guru')
    assert not account_pages.proses_akun(db, _data(sid), 'guru')[1]
    sebelum = db.total_changes
    for kelas in ('4', '5', ''):
        pesan, galat = account_pages.proses_akun(db, _data(sid, kelas), 'guru')
        assert not pesan and 'Muat ulang' in galat
        assert db.total_changes == sebelum
    assert learning_profile.baca(db, sid, pemilik='guru') == learning_profile.ProfilBelajar(sid, 4, 1)
    assert not account_pages.proses_akun(db, _data(sid, '4', '1'), 'guru')[1]
    assert db.total_changes == sebelum


@pytest.mark.parametrize('kelas,revisi', [('P4','0'), ('0','0'), ('7','0'), ('4.0','0'), ('4',''), ('4','-1'), ('4','1.0'), ('4','+0')])
def test_input_invalid_tidak_menulis(db, kelas, revisi):
    sid = database.tambah_siswa(db, 'Sintetis', 'P5', pemilik='guru')
    sebelum = db.total_changes
    pesan, galat = account_pages.proses_akun(db, _data(sid, kelas, revisi), 'guru')
    assert galat and not pesan
    assert db.total_changes == sebelum


@pytest.mark.parametrize('kelas,revisi', [('4','0'), ('P4','-1')])
def test_akun_resource_asing_hilang_identik_sebelum_validasi(db, kelas, revisi):
    sid = database.tambah_siswa(db, 'Rahasia sintetis', 'P5', pemilik='lain')
    sebelum = db.total_changes
    pesan = []
    for identitas in (sid, 999999, 2**80):
        with pytest.raises(learning_profile.ProfilTidakDitemukan) as galat:
            account_pages.proses_akun(db, _data(identitas, kelas, revisi), 'guru')
        pesan.append(str(galat.value))
    assert len(set(pesan)) == 1
    assert db.total_changes == sebelum
    isi = account_pages.halaman_akun(db, pengguna='guru', section='siswa').decode()
    assert 'Rahasia sintetis' not in isi


@pytest.mark.parametrize('peran', ['admin', 'murid'])
def test_update_akun_bukan_bypass_admin_atau_murid(db, peran):
    sid = database.tambah_siswa(db, 'Sintetis', 'P5', pemilik='guru')
    sebelum = db.total_changes
    with pytest.raises(learning_profile.ProfilTidakDitemukan):
        account_pages.proses_akun(db, _data(sid), 'guru', peran)
    assert db.total_changes == sebelum


def test_bingkai_profil_kelas_eksplisit_bukan_tingkat():
    import profile_workspace
    siswa = dict(id=1, nama='Sintetis', tingkat='P6', pemilik='guru')
    kosong = profile_workspace.bingkai(siswa, 'latihan', 0, '')
    kelas = profile_workspace.bingkai(siswa, 'latihan', 0, '', kelas_sekolah=2)
    assert 'Kelas belum diisi' in kosong and 'Kelas 6' not in kosong
    assert 'Kelas 2' in kelas and 'P6' not in kelas
    assert kelas.count('Kelola kelas sekolah') == 1
    assert '<form' not in kelas


def test_onboarding_form_profil_eksplisit_kelas_opsional(db):
    isi = account_pages.halaman_akun(db, pengguna='guru', section='siswa').decode()
    form = Formulir(isi).aksi('anak_baru')[0]
    assert any(s.get('name') == 'profil_parameter' and 'required' in s for s in form['select'])
    assert any(s.get('name') == 'kelas_sekolah' and 'required' not in s for s in form['select'])
    assert not any(s.get('name') in ('tingkat', 'level') for s in form['select'])
    assert not any(o.get('value') in ('P3', 'P4', 'P5', 'P6') and 'selected' in o for o in form['option'])


def test_onboarding_petunjuk_ringkas_satu_pembuka_panduan(db):
    from test_question_variants_ui import Rincian
    isi = account_pages.halaman_akun(db, pengguna='guru', section='siswa').decode()
    awal = isi.split('<fieldset class="pengaturan-awal">', 1)[1].split('</fieldset>', 1)[0]
    rincian = Rincian(awal)
    luar = ''.join(rincian.luar)
    assert 'bukan urutan kemampuan atau kelas anak' in luar
    assert 'latihan dan rencana belajar' in luar
    assert 'latihan bebas' in luar
    assert 'href="#panduan-variasi"' not in awal
    assert awal.count('<summary>Bandingkan isi dan contoh soal</summary>') == 1
    assert '<summary>Tentang variasi dan contoh</summary>' in awal
    assert 'Contoh ini bukan soal sesi yang akan dibuat' in ''.join(rincian.dalam)
    assert 'Nama pola yang sama' not in luar
    assert len(luar.split()) <= 65
    assert '.variasi-daftar {' in isi, 'CSS panduan harus dimuat di akun'


@pytest.mark.parametrize('kelas', ['', '1', '6'])
def test_onboarding_kelas_tidak_memilih_profil(db, kelas):
    pesan, galat = account_pages.proses_akun(db, dict(aksi='anak_baru', nama='Sintetis', profil_parameter='P5', kelas_sekolah=kelas, sandi_anak='sandi-sintetis-anak'), 'guru')
    assert pesan and not galat
    siswa = database.daftar_siswa(db)[0]
    assert siswa['tingkat'] == 'P5'
    assert learning_profile.baca(db, siswa['id'], pemilik='guru').kelas_sekolah == (int(kelas) if kelas else None)


@pytest.mark.parametrize('tambahan', [{}, {'profil_parameter': ''}, {'tingkat': ''}, {'profil_parameter': 'P9'}, {'profil_parameter': 'P5', 'kelas_sekolah': 'P4'}, {'profil_parameter':'P5','tingkat':'P3'}])
def test_onboarding_tidak_punya_default_kemampuan(db, tambahan):
    sebelum = db.total_changes
    akun = auth.BERKAS_SANDI.read_bytes()
    pesan, galat = account_pages.proses_akun(db, dict(aksi='anak_baru', nama='Sintetis', sandi_anak='sandi-sintetis-anak', **tambahan), 'guru')
    assert galat and not pesan
    assert db.total_changes == sebelum
    assert auth.BERKAS_SANDI.read_bytes() == akun


def test_onboarding_auth_gagal_tidak_meninggalkan_profil(db, monkeypatch):
    def gagal(*args, **kwargs):
        raise ValueError('Gagal sintetis')
    monkeypatch.setattr(auth, 'tambah_akun', gagal)
    pesan, galat = account_pages.proses_akun(db, dict(aksi='anak_baru', nama='Sintetis', profil_parameter='P5', kelas_sekolah='2', sandi_anak='sandi-sintetis-anak'), 'guru')
    assert galat and not pesan
    assert not database.daftar_siswa(db)
    assert db.execute('SELECT COUNT(*) FROM profil_belajar').fetchone()[0] == 0
