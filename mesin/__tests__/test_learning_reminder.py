"""Pengingat sekunder dari reducer, bukan ajakan pemetaan pada setiap profil."""
from dataclasses import replace
from datetime import date, timedelta

import pytest

import database
import learning_cycle as lc
import learning_cycle_ui as ui
from http_test_kit import ServerUji, SANDI_GURU

HARI = date(2026, 9, 20)


def test_anak_baru_tidak_mendapat_pengajak_pemetaan(tmp_path):
    path = tmp_path / 'pengingat.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        sebelum = tuple(kon.iterdump())
        assert ui.pengingat_rencana(kon, sid) == ''
        assert tuple(kon.iterdump()) == sebelum


def _bukti_pemetaan(*, optin=True):
    tanggal = HARI - timedelta(days=3)
    sesi = lc.SesiSiklus(1, 1, 'P3', 'bebas', tanggal, selesai=str(tanggal),
                         dikonfirmasi=str(tanggal), konfirmasi_id=7,
                         outcomes=(lc.OutcomeSiklus('deret_aritmetika', True),))
    kejadian = (lc.KejadianSiklus(1, 'sertakan_pemetaan', tanggal, sesi_id=1, konfirmasi_id=7),) if optin else ()
    return lc.BuktiSiklus(1, 'P3', sesi=(sesi,), kejadian=kejadian)


def test_pemetaan_manual_optin_sah_memunculkan_pengingat():
    bukti = _bukti_pemetaan()
    assert lc.pengingat_berikutnya(bukti, 1, HARI) == lc.rencana_berikutnya(bukti, 1, HARI)
    assert lc.pengingat_berikutnya(bukti, 1, HARI).tindakan == 'pemetaan'


@pytest.mark.parametrize('kasus', ['kosong', 'manual', 'optin_lama', 'belum_sah', 'pg', 'dibatalkan', 'beda_level', 'putaran_kosong', 'menunggu'])
def test_tidak_mengajak_tanpa_aktivitas_sah_atau_saat_menunggu(kasus):
    bukti = _bukti_pemetaan()
    s = bukti.sesi[0]
    if kasus == 'kosong':
        bukti = lc.BuktiSiklus(1, 'P3')
    elif kasus == 'manual':
        bukti = replace(bukti, kejadian=())
    elif kasus == 'optin_lama':
        bukti = replace(bukti, kejadian=(replace(bukti.kejadian[0], konfirmasi_id=6),))
    elif kasus == 'putaran_kosong':
        bukti = lc.BuktiSiklus(1, 'P3', putaran=(lc.PutaranSiklus(1, 1, 'P3', HARI),))
    else:
        opsi = {'belum_sah': {'dikonfirmasi': None}, 'pg': {'format_jawaban': 'pilihan_ganda'},
                'dibatalkan': {'dibatalkan': 'batal'}, 'beda_level': {'level': 'P4'},
                'menunggu': {'tanggal': HARI}}[kasus]
        bukti = replace(bukti, sesi=(replace(s, **opsi),))
    assert lc.pengingat_berikutnya(bukti, 1, HARI) is None


@pytest.mark.parametrize('selesai,harapan', [(None, 'lanjutkan_sesi'), ('2026-09-19', 'konfirmasi_hasil')])
def test_sesi_aktif_tanpa_objek_putaran_rencana_tetap_diingatkan(selesai, harapan):
    putaran = lc.PutaranSiklus(1, 1, 'P3', HARI)
    sesi = lc.SesiSiklus(9, 1, 'P3', 'pemetaan', HARI, selesai=selesai, putaran_id=1)
    bukti = lc.BuktiSiklus(1, 'P3', sesi=(sesi,), putaran=(putaran,))
    rencana = lc.pengingat_berikutnya(bukti, 1, HARI)
    assert rencana is not None
    assert rencana.tindakan == harapan and rencana.sesi_id == 9
    assert rencana.putaran is None


@pytest.mark.parametrize('tindakan', ['intervensi', 'pengenalan', 'probe_setelah_pengenalan',
    'probe_diagnostik', 'latihan_terbimbing', 'penguatan', 'evaluasi', 'checkpoint', 'eskalasi', 'putaran_baru'])
def test_tindakan_domain_tidak_hilang_hanya_karena_tanpa_cta_buat(monkeypatch, tindakan):
    rencana = lc.RencanaBelajar(tindakan, 'Alasan domain')
    jejak = []
    def tentukan(*args):
        jejak.append(args)
        return rencana
    monkeypatch.setattr(lc, 'rencana_berikutnya', tentukan)
    bukti = lc.BuktiSiklus(1, 'P3')
    assert lc.pengingat_berikutnya(bukti, 1, HARI) is rencana
    assert jejak == [(bukti, 1, HARI)]


@pytest.mark.parametrize('tindakan', ['tunggu_pemetaan', 'tunggu_evaluasi', 'tunggu_checkpoint', 'mixed_maintenance'])
def test_menunggu_dan_pemeliharaan_tidak_membuat_banner(monkeypatch, tindakan):
    rencana = lc.RencanaBelajar(tindakan, 'Alasan domain')
    monkeypatch.setattr(lc, 'rencana_berikutnya', lambda *a: rencana)
    assert lc.pengingat_berikutnya(lc.BuktiSiklus(1, 'P3'), 1, HARI) is None


def test_eskalasi_nyata_tetap_diingatkan_meski_tidak_ada_cta_buat():
    fokus = ('deret_aritmetika', 'K', 'uji')
    putaran = lc.PutaranSiklus(1, 1, 'P3', HARI - timedelta(days=20), (fokus,))
    hasil = tuple(lc.OutcomeSiklus(fokus[0], False, 'K', 'uji',
                                  cek_pemahaman='bisa_menjelaskan', target_fokus=fokus) for _ in range(4))
    sesi = lc.SesiSiklus(1, 1, 'P3', 'evaluasi', HARI - timedelta(days=3),
                         selesai='2026-09-17', dikonfirmasi='2026-09-17', konfirmasi_id=1,
                         putaran_id=1, target_fokus=(fokus,), outcomes=hasil)
    bukti = lc.BuktiSiklus(1, 'P3', sesi=(sesi,), putaran=(putaran,), pendekatan_tersedia=((fokus, ()),))
    rencana = lc.pengingat_berikutnya(bukti, 1, HARI)
    assert rencana.tindakan == 'eskalasi'
    assert rencana == lc.rencana_berikutnya(bukti, 1, HARI)


def test_pengingat_bukti_siswa_asing_ditolak():
    with pytest.raises(ValueError):
        lc.pengingat_berikutnya(lc.BuktiSiklus(1, 'P3'), 2, HARI)


@pytest.fixture
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    try:
        yield s
    finally:
        s.berhenti()


def test_http_manual_langsung_rencana_tetap_tersedia_dan_pengingat_aktif(server):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        asing = database.tambah_siswa(kon, 'Asing', pemilik='keluarga-lain')
        awal = tuple(kon.iterdump())
    status, isi, _ = server.minta('/anak/%d' % sid, auth=('guru', SANDI_GURU))
    assert status == 200
    assert f'action="/sesi-baru/{sid}"' in isi
    assert 'class="profil-rappel-st"' not in isi
    assert f'href="/anak/{sid}?section=rencana"' in isi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == awal
    assert server.minta(f'/anak/{sid}?section=rencana', auth=('guru', SANDI_GURU))[0] == 200
    server.minta(f'/siklus/{sid}/buat', auth=('guru', SANDI_GURU), data={})
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    status, isi, _ = server.minta('/anak/%d' % sid, auth=('guru', SANDI_GURU))
    assert status == 200 and isi.count('class="profil-rappel-st"') == 1
    banner = isi.split('class="profil-rappel-st"', 1)[1].split('</div>', 1)[0]
    assert 'Lanjutkan' in banner and '<form' not in banner
    assert f'?section=rencana' in banner
    ditolak = [server.minta('/anak/%d' % identitas, auth=('guru', SANDI_GURU))[:2] for identitas in (asing, 99999)]
    assert ditolak[0] == ditolak[1] and ditolak[0][0] == 404
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
        sesi = kon.execute('SELECT id FROM sesi WHERE siswa_id=?', (sid,)).fetchone()[0]
        kon.execute('UPDATE sesi SET selesai=CURRENT_TIMESTAMP WHERE id=?', (sesi,))
    status, isi, _ = server.minta('/anak/%d' % sid, auth=('guru', SANDI_GURU))
    assert status == 200
    banner = isi.split('class="profil-rappel-st"', 1)[1].split('</div>', 1)[0]
    assert 'Tinjau' in banner and '<form' not in banner


def test_http_optin_manual_terkonfirmasi_bukan_direview_memunculkan_banner(server):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, sid, 88, jumlah_soal=1)
        butir = database.isi_sesi(kon, sesi)[0]
        jawaban = database.simpan_jawaban(kon, butir['sesi_soal_id'], butir['kunci'], 'Cara sintetis')
        database.simpan_diagnosis(kon, jawaban, True, None, None)
        database.tandai_selesai(kon, sesi)
        kon.execute("UPDATE sesi SET tanggal='2020-01-01', direview=CURRENT_TIMESTAMP WHERE id=?", (sesi,))
        konfirmasi = database.konfirmasi_hasil(kon, sesi, 'guru')
    status, isi, _ = server.minta('/anak/%d' % sid, auth=('guru', SANDI_GURU))
    assert status == 200 and 'class="profil-rappel-st"' not in isi
    with server.buka() as kon:
        kon.execute("INSERT INTO kejadian_belajar(siswa_id,sesi_id,konfirmasi_id,jenis) VALUES(?,?,?,'sertakan_pemetaan')", (sid, sesi, konfirmasi))
        sebelum = tuple(kon.iterdump())
    status, isi, _ = server.minta('/anak/%d' % sid, auth=('guru', SANDI_GURU))
    assert status == 200 and isi.count('class="profil-rappel-st"') == 1
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
