"""Bukti per konteks warisan tidak disatukan atau disertifikasi lewat kelas profil."""
from dataclasses import replace
from datetime import date, timedelta

import pytest

import database
import learning_cycle as lc
from mastery_evidence import lengkapi_bukti_materi
from question_context import konteks_warisan

HARI = date(2026, 9, 20)
POLA = 'keliling_luas_datar'
DASAR = konteks_warisan(POLA, 'P3')
LANJUT = konteks_warisan(POLA, 'P4')


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'konteks.db'
    database.siapkan(path)
    return path


def _sesi(kon, siswa, profil, seed, hari, *, salah=False):
    sesi = database.buat_sesi_dari_urutan(kon, siswa, seed, (POLA,) * 4,
                                        topik='geometri-datar', level=profil)
    pemahaman = {}
    for butir in database.isi_sesi(kon, sesi):
        identitas = butir['sesi_soal_id']
        jawaban = database.simpan_jawaban(kon, identitas, '0' if salah else butir['kunci'], 'Cara sintetis')
        database.simpan_diagnosis(kon, jawaban, not salah, 'H' if salah else None, 'H' if salah else None)
        pemahaman[identitas] = 'bisa_menjelaskan'
    kon.execute('UPDATE sesi SET tanggal=?, selesai=? WHERE id=?', (hari.isoformat(), hari.isoformat(), sesi))
    konfirmasi = database.konfirmasi_hasil(kon, sesi, 'guru', cek_pemahaman=pemahaman)
    kon.execute("INSERT INTO kejadian_belajar(siswa_id,sesi_id,konfirmasi_id,jenis) VALUES(?,?,?,'sertakan_pemetaan')",
                (siswa, sesi, konfirmasi))
    return sesi


def _muat(kon, siswa):
    return lengkapi_bukti_materi(kon, database.muat_bukti_siklus(kon, siswa))


def _status(bukti):
    return {x.konteks.id: x.hasil.status for x in lc.penguasaan_konteks(bukti, bukti.siswa_id, (DASAR, LANJUT), HARI)}


def test_adapter_memakai_profil_snapshot_bukan_profil_aktif(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', 'P6', pemilik='guru')
        _sesi(kon, siswa, 'P3', 15, HARI)
        sebelum = tuple(kon.iterdump())
        bukti = _muat(kon, siswa)
        assert tuple(kon.iterdump()) == sebelum
    assert all(getattr(o, 'profil_parameter', None) == 'P3' for o in bukti.sesi[0].outcomes)
    assert bukti.level_aktif == 'P6'


@pytest.mark.parametrize('ubah', ['sesi', 'soal', 'konfirmasi', 'snapshot'])
def test_adapter_menolak_konteks_sumber_berbeda_tanpa_menulis(db, ubah):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
        sesi = _sesi(kon, siswa, 'P3', 16, HARI)
        bukti = database.muat_bukti_siklus(kon, siswa)
        if ubah == 'sesi':
            kon.execute("UPDATE sesi SET level='P4' WHERE id=?", (sesi,))
            # Reader inti kini memeriksa arsip konteks juga, sebelum adapter.
            with pytest.raises(ValueError, match='konteks'):
                database.muat_bukti_siklus(kon, siswa)
        elif ubah == 'soal':
            kon.execute("UPDATE soal SET level='P4' WHERE id IN (SELECT soal_id FROM sesi_soal WHERE sesi_id=?)", (sesi,))
        elif ubah == 'konfirmasi':
            bukti = replace(bukti, sesi=(replace(bukti.sesi[0], konfirmasi_id=99999),))
        else:
            # Fixture korup pada DB sintetis saja: snapshot tidak pernah dimutasi aplikasi.
            kon.execute('DROP TRIGGER snapshot_outcome_tolak_update')
            kon.execute("UPDATE snapshot_outcome SET level_efektif='P4'")
        sebelum = tuple(kon.iterdump())
        with pytest.raises(ValueError):
            lengkapi_bukti_materi(kon, bukti)
        assert tuple(kon.iterdump()) == sebelum


def test_dua_konteks_tidak_bergantung_level_global_dan_tidak_mutasi_bukti(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', 'P6', pemilik='guru')
        for i, hari in enumerate((HARI - timedelta(days=7), HARI - timedelta(days=3))):
            _sesi(kon, siswa, 'P3', 20 + i, hari)
        bukti = _muat(kon, siswa)
        sebelum = repr(bukti)
        hasil = _status(bukti)
        assert hasil == {DASAR.id: 'terbukti', LANJUT.id: 'belum_dinilai'}
        for level in ('P3', 'P4', 'P5', 'P6'):
            assert _status(replace(bukti, level_aktif=level)) == hasil
        assert repr(bukti) == sebelum


def test_probe_lintas_profil_tidak_digabung(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        _sesi(kon, siswa, 'P3', 30, HARI - timedelta(days=7))
        _sesi(kon, siswa, 'P4', 31, HARI - timedelta(days=3))
        assert _status(_muat(kon, siswa)) == {DASAR.id: 'dipelajari', LANJUT.id: 'dipelajari'}


def test_kegagalan_lanjut_tidak_menghapus_bukti_dasar(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        for i, hari in enumerate((HARI - timedelta(days=7), HARI - timedelta(days=3))):
            _sesi(kon, siswa, 'P3', 40 + i, hari)
        _sesi(kon, siswa, 'P4', 42, HARI, salah=True)
        assert _status(_muat(kon, siswa)) == {DASAR.id: 'terbukti', LANJUT.id: 'dipelajari'}


@pytest.mark.parametrize('ubah', ['tanpa_profil', 'salah_profil', 'salah_siswa', 'tanpa_konfirmasi',
                                  'tanpa_optin', 'drill', 'pg', 'tanpa_sidik', 'duplikat', 'tanpa_penjelasan', 'batal'])
def test_konteks_mempertahankan_palang_bukti(db, ubah):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        for i, hari in enumerate((HARI - timedelta(days=7), HARI - timedelta(days=3))):
            _sesi(kon, siswa, 'P3', 50 + i, hari)
        bukti = _muat(kon, siswa)
    if ubah in {'tanpa_profil', 'salah_profil'}:
        sesi = tuple(replace(s, outcomes=tuple(replace(o, profil_parameter=None if ubah == 'tanpa_profil' else 'P4')
                                               for o in s.outcomes)) for s in bukti.sesi)
        with pytest.raises(ValueError, match='konteks'):
            _status(replace(bukti, sesi=sesi))
        return
    if ubah == 'tanpa_optin':
        bukti = replace(bukti, kejadian=())
    else:
        opsi = {'salah_siswa': {'siswa_id': 999}, 'tanpa_konfirmasi': {'konfirmasi_id': None},
                'drill': {'mode': 'drill'}, 'pg': {'format_jawaban': 'pilihan_ganda'}, 'batal': {'dibatalkan': 'batal'}}
        if ubah in opsi:
            bukti = replace(bukti, sesi=tuple(replace(s, **opsi[ubah]) for s in bukti.sesi))
        else:
            perubahan = {'tanpa_sidik': {'fingerprint_matematis': None},
                         'duplikat': {'fingerprint_matematis': 'sama'},
                         'tanpa_penjelasan': {'cek_pemahaman': None}}[ubah]
            bukti = replace(bukti, sesi=tuple(replace(s, outcomes=tuple(replace(o, **perubahan) for o in s.outcomes)) for s in bukti.sesi))
    assert _status(bukti)[DASAR.id] != 'terbukti'


def test_koreksi_dan_ganti_level_historis_tidak_menghidupkan_bukti(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        for i, hari in enumerate((HARI - timedelta(days=7), HARI - timedelta(days=3))):
            sesi = _sesi(kon, siswa, 'P3', 60 + i, hari)
        butir = database.isi_sesi(kon, sesi)[0]
        database.simpan_diagnosis(kon, butir['jawaban_id'], False, 'H', 'H')
        bukti = _muat(kon, siswa)
        assert _status(bukti)[DASAR.id] == 'perlu_cek'
        event = lc.KejadianSiklus(99999, 'diganti_level', HARI)
        assert _status(replace(bukti, kejadian=(*bukti.kejadian, event)))[DASAR.id] == 'belum_dinilai'


@pytest.mark.parametrize('perubahan', [
    {'tujuan': 'evaluasi'}, {'tanggal': HARI - timedelta(days=10)},
    {'selesai': None}, {'dibatalkan': 'batal'}, {'putaran_id': 99},
])
def test_adapter_menolak_metadata_sesi_usang(db, perubahan):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        _sesi(kon, siswa, 'P3', 71, HARI)
        bukti = database.muat_bukti_siklus(kon, siswa)
        bukti = replace(bukti, sesi=(replace(bukti.sesi[0], **perubahan),))
        sebelum = tuple(kon.iterdump())
        with pytest.raises(ValueError, match='versi bukti'):
            lengkapi_bukti_materi(kon, bukti)
        assert tuple(kon.iterdump()) == sebelum


def test_adapter_tidak_memberi_metadata_sah_ke_outcome_diubah(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        _sesi(kon, siswa, 'P3', 72, HARI, salah=True)
        bukti = database.muat_bukti_siklus(kon, siswa)
        sesi = bukti.sesi[0]
        palsu = tuple(replace(o, benar=True, kode_final=None) for o in sesi.outcomes)
        sebelum = tuple(kon.iterdump())
        with pytest.raises(ValueError, match='outcome'):
            lengkapi_bukti_materi(kon, replace(bukti, sesi=(replace(sesi, outcomes=palsu),)))
        assert tuple(kon.iterdump()) == sebelum


def _domain_sesi(nomor, hari, *, tujuan='pemetaan', level='P3', **opsi):
    fokus = (POLA, 'K', 'sintetis')
    outcomes = tuple(lc.OutcomeSiklus(POLA, True, cek_pemahaman='bisa_menjelaskan',
                                     target_fokus=fokus if tujuan != 'pemetaan' else None,
                                     fingerprint_matematis='mat-%d-%d' % (nomor, i),
                                     profil_parameter=level) for i in range(4))
    return lc.SesiSiklus(nomor, 1, level, tujuan, hari, selesai=str(hari),
                         dikonfirmasi=str(hari), konfirmasi_id=nomor, putaran_id=1,
                         outcomes=outcomes, target_fokus=(fokus,) if tujuan != 'pemetaan' else (),
                         pola_tersedia=(POLA,), **opsi)


def _domain(sesi):
    return lc.BuktiSiklus(1, 'P6', sesi=tuple(sesi),
                          putaran=(lc.PutaranSiklus(1, 1, 'P3', HARI - timedelta(days=60)),))


def test_konteks_retensi_representasi_dan_penyebut_probe_tidak_dilonggarkan():
    a = _domain_sesi(1, HARI - timedelta(days=7))
    b = _domain_sesi(2, HARI - timedelta(days=3))
    assert _status(_domain((a, b)))[DASAR.id] == 'terbukti'
    hasil = lc.penguasaan_konteks(_domain((a, b)), 1, (DASAR,), HARI + timedelta(days=25))
    assert hasil[0].hasil.status == 'perlu_cek'
    for perubahan in ({'cek_pemahaman': 'ragu'}, {'mode_representasi': 'visual-v2'},
                      {'dilewati': True}, {'benar': False, 'kode_final': 'K'}):
        beda = replace(b, outcomes=tuple(replace(o, **perubahan) for o in b.outcomes))
        assert _status(_domain((a, beda)))[DASAR.id] != 'terbukti'
    kurang = (replace(a, outcomes=a.outcomes[:1]), replace(b, outcomes=b.outcomes[:2]))
    assert _status(_domain(kurang))[DASAR.id] != 'terbukti'
    assert _status(_domain((a, replace(b, tanggal=a.tanggal))))[DASAR.id] != 'terbukti'


def test_evaluasi_konteks_benar_tanpa_penjelasan_tidak_lulus():
    sesi = _domain_sesi(1, HARI, tujuan='evaluasi')
    assert _status(_domain((sesi,)))[DASAR.id] == 'terbukti'
    tanpa = replace(sesi, outcomes=tuple(replace(o, cek_pemahaman=None) for o in sesi.outcomes))
    assert _status(_domain((tanpa,)))[DASAR.id] != 'terbukti'


def test_konteks_checkpoint_memerlukan_pasangan_sama_dan_fokus_target():
    evaluasi = _domain_sesi(1, HARI - timedelta(days=35), tujuan='evaluasi')
    awal = _domain_sesi(2, HARI - timedelta(days=1), tujuan='checkpoint', bagian_checkpoint=1, occurrence=1)
    akhir = _domain_sesi(3, HARI, tujuan='checkpoint', bagian_checkpoint=2, occurrence=1)
    assert _status(_domain((evaluasi, awal, akhir)))[DASAR.id] == 'terbukti'
    assert _status(_domain((evaluasi, awal, replace(akhir, occurrence=2))))[DASAR.id] != 'terbukti'
    assert _status(_domain((evaluasi, awal)))[DASAR.id] != 'terbukti'
    assert _status(_domain((replace(evaluasi, target_fokus=()),)))[DASAR.id] != 'terbukti'
    kedua = (POLA, 'K', 'kedua')
    bukti = _domain((evaluasi,))
    fokus = evaluasi.target_fokus[0]
    bukti = replace(bukti, putaran=(replace(bukti.putaran[0], fokus=(fokus, kedua)),))
    assert _status(bukti)[DASAR.id] != 'terbukti'


def test_konteks_dua_profil_berhasil_tetap_masing_masing_dan_tanpa_duplikasi():
    a = _domain_sesi(1, HARI - timedelta(days=7))
    b = _domain_sesi(2, HARI - timedelta(days=3))
    c = replace(_domain_sesi(3, HARI - timedelta(days=7), level='P4'), putaran_id=2)
    d = replace(_domain_sesi(4, HARI - timedelta(days=3), level='P4'), putaran_id=2)
    bukti = _domain((a, b, c, d))
    bukti = replace(bukti, putaran=(*bukti.putaran, lc.PutaranSiklus(2, 1, 'P4', HARI - timedelta(days=30))))
    hasil = lc.penguasaan_konteks(bukti, 1, (LANJUT, DASAR), HARI)
    assert [x.konteks for x in hasil] == [LANJUT, DASAR]
    assert [x.hasil.sesi_ids for x in hasil] == [(3, 4), (1, 2)]
    assert all(x.hasil.status == 'terbukti' for x in hasil)


def test_adapter_menolak_provenance_yang_berbeda_dari_pertanyaan(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        _sesi(kon, siswa, 'P3', 73, HARI)
        bukti = database.muat_bukti_siklus(kon, siswa)
        s = bukti.sesi[0]
        palsu = tuple(replace(o, fingerprint_penyajian='a' * 64) for o in s.outcomes)
        with pytest.raises(ValueError, match='penyajian'):
            lengkapi_bukti_materi(kon, replace(bukti, sesi=(replace(s, outcomes=palsu),)))


def test_metadata_kelas_sekolah_tidak_mereset_status_konteks(db):
    import learning_profile
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        for i, hari in enumerate((HARI - timedelta(days=7), HARI - timedelta(days=3))):
            _sesi(kon, siswa, 'P3', 80 + i, hari)
        sebelum = _status(_muat(kon, siswa))
        learning_profile.simpan_kelas(kon, siswa, 4, revisi=0, pemilik='guru')
        learning_profile.simpan_kelas(kon, siswa, 5, revisi=1, pemilik='guru')
        assert _status(_muat(kon, siswa)) == sebelum
        assert kon.execute("SELECT COUNT(*) FROM kejadian_belajar WHERE jenis='diganti_level'").fetchone()[0] == 0


def test_adapter_warisan_tanpa_sidik_tidak_merekonstruksi_probe(db):
    import question_views
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 82, jumlah_soal=1)
        kolom = ', '.join(n + '=NULL' for n in question_views.KOLOM_SNAPSHOT)
        kon.execute('UPDATE sesi_soal SET ' + kolom + ' WHERE sesi_id=?', (sesi,))
        butir = database.isi_sesi(kon, sesi)[0]
        jawaban = database.simpan_jawaban(kon, butir['sesi_soal_id'], butir['kunci'], 'Cara sintetis')
        database.simpan_diagnosis(kon, jawaban, True, None, None)
        database.tandai_selesai(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, 'guru')
        sebelum = tuple(kon.iterdump())
        bukti = _muat(kon, siswa)
        assert bukti.sesi[0].outcomes[0].fingerprint_matematis is None
        assert bukti.sesi[0].outcomes[0].profil_parameter == 'P3'
        assert tuple(kon.iterdump()) == sebelum


def test_seluruh_konteks_kosong_tidak_menjadi_persen_kemampuan():
    from question_context import daftar_konteks
    konteks = daftar_konteks()
    hasil = lc.penguasaan_konteks(lc.BuktiSiklus(1, 'P3'), 1, konteks, HARI)
    assert tuple(x.konteks for x in hasil) == konteks
    assert all(x.hasil.status == 'belum_dinilai' and x.hasil.sesi_ids == () for x in hasil)


def test_input_konteks_asing_duplikat_atau_siswa_asing_ditolak():
    bukti = lc.BuktiSiklus(1, 'P3')
    for konteks in ((DASAR, DASAR), ('warisan-v1:asing:P3',)):
        with pytest.raises(ValueError):
            lc.penguasaan_konteks(bukti, 1, konteks, HARI)
    with pytest.raises(ValueError):
        lc.penguasaan_konteks(bukti, 2, (DASAR,), HARI)
    assert lc.penguasaan_konteks(bukti, 1, (), HARI) == ()
