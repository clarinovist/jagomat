"""Pemulihan sumber pilot tidak mengubah snapshot atau konteks sehat."""
from datetime import date
import pytest
import database
import learning_cycle as lc
from skill_pilot import LANGSUNG, PRASYARAT, KonteksPilot
from skill_pilot_service import jalankan, revisi, keadaan, daftar_putaran

HARI = date(2026, 9, 10)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'pemulihan.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
        yield kon, siswa


def _sahkan(kon, sid, tanggal, salah=False):
    kon.execute('UPDATE sesi SET tanggal=? WHERE id=?', (tanggal, sid))
    for b in database.isi_sesi(kon, sid):
        jid = database.simpan_jawaban(kon, b['sesi_soal_id'], '0' if salah else b['kunci'])
        database.simpan_diagnosis(kon, jid, not salah, 'K' if salah else None,
                                  'K' if salah else None, 'datar.lupa_kali_dua' if salah else None)
    database.tandai_selesai(kon, sid)
    kh = database.konfirmasi_hasil(kon, sid, 'guru', cek_pemahaman={
        b['sesi_soal_id']: 'bisa_menjelaskan' for b in database.isi_sesi(kon, sid)})
    kon.execute('UPDATE sesi SET selesai=?,dikonfirmasi_guru=? WHERE id=?', (tanggal, tanggal, sid))
    return kh


def _aksi(kon, siswa, aksi, hari, **data):
    return jalankan(kon, siswa, {'aksi': aksi, 'revisi': revisi(kon, siswa), **data}, hari=hari)


def siapkan_masalah(kon, siswa, jenis='batal'):
    # Rujukan sehat lebih dahulu; masalah keliling tidak boleh menghapusnya.
    kisi = int(_aksi(kon, siswa, 'mulai', date(2026,9,1), tuntutan=PRASYARAT,
                    profil='P3', representasi='teks-v1').split('/')[-1])
    _sahkan(kon, kisi, '2026-09-01')
    kisi2 = int(_aksi(kon, siswa, 'lanjut', date(2026,9,4)).split('/')[-1])
    _sahkan(kon, kisi2, '2026-09-04')
    awal = int(_aksi(kon, siswa, 'mulai', date(2026,9,4), tuntutan=LANGSUNG,
                    profil='P3', representasi='teks-v1').split('/')[-1])
    _sahkan(kon, awal, '2026-09-04', True)
    kedua = int(_aksi(kon, siswa, 'lanjut', date(2026,9,7)).split('/')[-1])
    _sahkan(kon, kedua, '2026-09-07', True)
    _aksi(kon, siswa, 'pelajari', date(2026,9,7))
    turunan = int(_aksi(kon, siswa, 'lanjut', date(2026,9,7)).split('/')[-1])
    pid = kon.execute('SELECT putaran_id FROM sesi WHERE id=?', (awal,)).fetchone()[0]
    if jenis == 'batal':
        database.batalkan_sesi(kon, awal, 'Uji pembatalan sumber')
    else:
        b = database.isi_sesi(kon, awal)[0]
        database.simpan_jawaban(kon, b['sesi_soal_id'], '99')
    return pid, (awal, kedua, turunan), (kisi, kisi2)


def _snapshot(kon):
    return tuple(tuple(b) for b in kon.execute('SELECT * FROM snapshot_outcome ORDER BY id'))


@pytest.mark.parametrize('jenis', ('batal', 'koreksi'))
def test_masalah_satu_konteks_tidak_memblokir_status_konteks_sehat(db, jenis):
    kon, siswa = db
    pid, sesi, sehat = siapkan_masalah(kon, siswa, jenis)
    sebelum = tuple(kon.iterdump())
    paket, _, aktif, _ = keadaan(kon, siswa, HARI)
    assert aktif[0] == pid and aktif[2].tindakan == 'pulihkan_sumber'
    k = (KonteksPilot(LANGSUNG, 'P3', 'teks-v1'), KonteksPilot(PRASYARAT, 'P3', 'teks-v1'))
    hasil = lc.penguasaan_pilot(paket, siswa, k, HARI)
    assert hasil[0].hasil.status == 'perlu_cek'
    assert hasil[1].hasil.status == 'terbukti'
    assert hasil[1].hasil.sesi_ids == sehat
    assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('jenis', ('batal', 'koreksi'))
def test_pulihkan_menutup_dan_membatalkan_tanpa_menghapus_histori(db, jenis):
    kon, siswa = db
    pid, sesi, sehat = siapkan_masalah(kon, siswa, jenis)
    sebelum = _snapshot(kon)
    sumber = tuple(tuple(b) for b in kon.execute('SELECT * FROM pilot_fokus_sumber'))
    data = {'aksi': 'pulihkan_sumber', 'revisi': revisi(kon,siswa), 'konfirmasi_pemulihan': '1'}
    assert jalankan(kon,siswa,data,hari=HARI) == '/anak/%d?section=rencana' % siswa
    assert pid not in {p for p, _ in daftar_putaran(kon,siswa)}
    assert all(kon.execute('SELECT dibatalkan FROM sesi WHERE id=?',(s,)).fetchone()[0] for s in sesi)
    assert all(kon.execute('SELECT dibatalkan FROM sesi WHERE id=?',(s,)).fetchone()[0] is None for s in sehat)
    assert _snapshot(kon) == sebelum
    assert tuple(tuple(b) for b in kon.execute('SELECT * FROM pilot_fokus_sumber')) == sumber
    setelah = tuple(kon.iterdump())
    assert jalankan(kon,siswa,data,hari=HARI).endswith('section=rencana')
    assert tuple(kon.iterdump()) == setelah
    # Pemeriksaan baru tetap keputusan eksplisit, tanpa carry/sertifikasi otomatis.
    sid = int(_aksi(kon,siswa,'mulai',HARI,tuntutan=LANGSUNG,profil='P3',representasi='teks-v1').split('/')[-1])
    assert sid not in sesi
    from skill_pilot_store import baca_kontrak
    assert baca_kontrak(kon,sid,siswa).sumber_konfirmasi == ()
    paket,_,a,_ = keadaan(kon,siswa,HARI)
    assert a[2].tindakan == 'lanjutkan_sesi'
    assert lc.penguasaan_pilot(paket,siswa,(a[1],),HARI)[0].hasil.status != 'terbukti'


@pytest.mark.parametrize('konfirmasi', (None, '', '0'))
def test_pemulihan_memerlukan_persetujuan_backend(db, konfirmasi):
    kon, siswa = db
    siapkan_masalah(kon,siswa)
    data = {'aksi':'pulihkan_sumber','revisi':revisi(kon,siswa)}
    if konfirmasi is not None: data['konfirmasi_pemulihan'] = konfirmasi
    sebelum = tuple(kon.iterdump())
    with pytest.raises(ValueError, match='konfirmasi'):
        jalankan(kon,siswa,data,hari=HARI)
    assert tuple(kon.iterdump()) == sebelum


def test_pemulihan_stale_dan_rollback(db, monkeypatch):
    kon,siswa=db
    _,sesi,_=siapkan_masalah(kon,siswa)
    data={'aksi':'pulihkan_sumber','revisi':revisi(kon,siswa),'konfirmasi_pemulihan':'1'}
    kon.execute("INSERT INTO kejadian_belajar(siswa_id,jenis,data) VALUES(?,'catatan_sintetis','{}')",(siswa,))
    sebelum=tuple(kon.iterdump())
    with pytest.raises(ValueError,match='Rencana berubah'): jalankan(kon,siswa,data,hari=HARI)
    assert tuple(kon.iterdump())==sebelum
    data['revisi']=revisi(kon,siswa)
    asli=database.batalkan_sesi
    def gagal(kon,sid,alasan):
        asli(kon,sid,alasan)
        raise ValueError('uji gagal sesudah membatalkan')
    monkeypatch.setattr(database,'batalkan_sesi',gagal)
    with pytest.raises(ValueError,match='uji gagal'): jalankan(kon,siswa,data,hari=HARI)
    assert tuple(kon.iterdump())==sebelum


def test_konfirmasi_baru_tidak_otomatis_mengikat_fokus_lama(db):
    kon,siswa=db
    _,sesi,_=siapkan_masalah(kon,siswa,'koreksi')
    _sahkan(kon,sesi[0],'2026-09-09',True)
    _,_,aktif,_=keadaan(kon,siswa,HARI)
    assert aktif[2].tindakan=='pulihkan_sumber'
