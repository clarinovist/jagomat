"""Pilihan variasi native tetap memakai kontrak HTTP dan histori yang sama."""
import pytest

import database
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID
from test_combined_mode import FormGabungan
from test_school_profile_ui import Formulir


@pytest.fixture
def server(tmp_path, monkeypatch):
    srv = ServerUji(tmp_path, monkeypatch)
    with srv.buka() as kon:
        srv.siswa = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
    yield srv
    srv.berhenti()


def _data_form(isi, jalur):
    """Ambil kontrol terkirim HTML aktual, termasuk hidden Pendamping dan submitter."""
    data = []
    nama_select, opsi = None, []
    for tag, atribut in FormGabungan(isi).form[jalur]:
        if nama_select and tag != 'option':
            pilihan = next((o for o in opsi if 'selected' in o), opsi[0])
            data.append((nama_select, pilihan['value']))
            nama_select, opsi = None, []
        if 'disabled' in atribut:
            continue
        nama = atribut.get('name')
        if tag == 'select':
            nama_select = nama
        elif tag == 'option' and nama_select:
            opsi.append(atribut)
        elif tag == 'input' and nama:
            if atribut.get('type') in ('checkbox', 'radio') and 'checked' not in atribut:
                continue
            data.append((nama, atribut.get('value', '')))
        elif tag == 'button' and nama == 'aksi_form':
            data.append((nama, atribut['value']))
    assert ('aksi_form', 'bandingkan') in data
    return data


def _form_bandingkan(server, jenis):
    kode, isi, _ = server.minta('/anak/%d?section=latihan' % server.siswa,
                                auth=('guru', SANDI_GURU))
    assert kode == 200
    jalur = '/%s/%d' % (jenis, server.siswa)
    data = _data_form(isi, jalur)
    assert {k for k, _ in data} >= {'inline_host', 'inline_host_id', 'inline_posisi'}
    data = [(k, v) for k, v in data if k not in {'topik', 'jumlah_soal'}]
    topik = ('statistika',) if jenis == 'sesi-baru' else ('statistika', 'pengukuran')
    return jalur, data + [('topik', t) for t in topik] + [('jumlah_soal', '15')]


@pytest.mark.parametrize('jenis', ['sesi-baru', 'sesi-gabungan'])
def test_bandingkan_form_native_dengan_pendamping_tanpa_write(server, jenis):
    jalur, data = _form_bandingkan(server, jenis)
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    # Ulang dari hasil HTML pertama, bukan payload buatan yang kehilangan hidden field.
    for _ in range(2):
        kode, isi, _ = server.minta(jalur, auth=('guru', SANDI_GURU), data=data,
                                  headers={'Origin': 'null', 'Sec-Fetch-Site': 'same-origin'})
        assert kode == 200
        data = _data_form(isi, jalur)
        assert ('topik', 'statistika') in data
        assert ('jumlah_soal', '15') in data
        assert ('mode', 'diagnostik' if jenis == 'sesi-baru' else 'drill') in data
        assert ('format_jawaban', 'isian') in data
        konteks = ','.join(v for k, v in data if k == 'topik_dibandingkan')
        assert 'data-contoh="%s:P4"' % konteks in isi
        if jenis == 'sesi-gabungan':
            assert ('topik', 'pengukuran') in data
            assert set(konteks.split(',')) == {'statistika', 'pengukuran'}
        else:
            assert konteks == 'statistika'
            assert ('durasi_menit', '30') in data and ('timer_auto', '0') in data
        with server.buka() as kon:
            assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('jenis', ['sesi-baru', 'sesi-gabungan'])
@pytest.mark.parametrize('tambahan', [
    ('field_asing', '1'), ('inline_asing', '1'), ('inline_nomor', '1'),
    ('mode', 'drill'), ('profil_parameter', 'Palsu'),
])
def test_bandingkan_form_native_tetap_menolak_draf_asing_atau_ganda(server, jenis, tambahan):
    jalur, data = _form_bandingkan(server, jenis)
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, _, _ = server.minta(jalur, auth=('guru', SANDI_GURU), data=data + [tambahan])
    assert kode == 400
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('jenis', ['sesi-baru', 'sesi-gabungan'])
def test_bandingkan_form_native_tidak_terbuka_untuk_murid(server, jenis):
    jalur, data = _form_bandingkan(server, jenis)
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, _, _ = server.minta(jalur, auth=('feby', SANDI_MURID), data=data)
    assert kode == 401
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_get_pilihan_isi_kontekstual_tidak_membuat_sesi_atau_bukti(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta('/anak/%d' % server.siswa, auth=('guru', SANDI_GURU))
    assert kode == 200
    assert isi.count('<legend>Pilih isi latihan</legend>') >= 2
    assert 'data-contoh="pola-bilangan:P6"' in isi
    assert '<span class="variasi-penanda"><span class="variasi-sr">Pilihan </span>A</span>' in isi
    Formulir(isi)  # termasuk guard form tidak bersarang
    kode, akun, _ = server.minta('/akun?section=siswa', auth=('guru', SANDI_GURU))
    assert kode == 200 and akun.count('id="panduan-variasi"') == 1
    Formulir(akun)
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_bandingkan_topik_merender_pilihan_baru_tanpa_write(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta('/sesi-baru/%d' % server.siswa, auth=('guru', SANDI_GURU), data={
        'aksi_form': 'bandingkan', 'inline_form': 'manual',
        'topik': 'statistika', 'jumlah_soal': '',
        'mode': 'diagnostik', 'hadir_timer_mode': '1', 'durasi_menit': '30',
        'timer_auto': '0', 'format_jawaban': 'isian',
    })
    assert kode == 200
    manual = isi.split('id="form-latihan-manual-', 1)[1].split('</form>', 1)[0]
    assert '<option value="statistika" selected>' in manual
    assert 'data-contoh="statistika:P3"' in manual
    assert 'data-contoh="pola-bilangan:P3"' not in manual
    assert 'name="aksi_form" value="bandingkan" formnovalidate' in manual
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('jalur', ['sesi-baru', 'sesi-gabungan'])
def test_bandingkan_menjaga_404_identik_dan_tanpa_efek_untuk_resource_asing(server, jalur):
    with server.buka() as kon:
        asing = database.tambah_siswa(kon, 'Asing Sintetis', 'P3', pemilik='keluarga-lain')
        sebelum = tuple(kon.iterdump())
    # Hidden host milik guru tidak boleh mengalihkan otorisasi URL asing.
    _, data = _form_bandingkan(server, jalur)
    respons = []
    for siswa_id in (asing, 999999):
        kode, isi, _ = server.minta('/%s/%d' % (jalur, siswa_id),
                                    auth=('guru', SANDI_GURU), data=data)
        assert kode == 404
        respons.append(isi)
    assert respons[0] == respons[1]
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_bandingkan_gabungan_memakai_irisan_topik_tanpa_write(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    data = [('aksi_form', 'bandingkan'), ('inline_form', 'gabungan'),
            ('topik', 'aritmatika-lanjut'),
            ('topik', 'pola-bilangan'), ('jumlah_soal', '10'),
            ('mode', 'drill'), ('format_jawaban', 'isian')]
    kode, isi, _ = server.minta('/sesi-gabungan/%d' % server.siswa,
                                auth=('guru', SANDI_GURU), data=data)
    assert kode == 200, isi
    gabungan = isi.split('id="form-latihan-gabungan-', 1)[1].split('</form>', 1)[0]
    assert gabungan.count('name="profil_parameter"') == 2
    assert 'value="P5"' in gabungan and 'value="P6"' in gabungan
    assert 'value="P3"' not in gabungan and 'value="P4"' not in gabungan
    assert 'name="aksi_form" value="bandingkan" formnovalidate' in gabungan
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('payload', [
    {'topik_dibandingkan': 'pola-bilangan', 'versi_pilihan_isi': '1'},
    {'topik_dibandingkan': 'statistika'},
    {'versi_pilihan_isi': '1'},
])
def test_submit_menolak_konteks_perbandingan_tidak_utuh_atau_berubah(server, payload):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    data = {'topik': 'statistika', 'profil_parameter': 'P3'}
    data.update(payload)
    kode, isi, _ = server.minta('/sesi-baru/%d' % server.siswa,
                                auth=('guru', SANDI_GURU), data=data)
    assert kode == 409 and 'Tampilkan pilihan isi' in isi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_submit_gabungan_menolak_topik_yang_berubah_setelah_perbandingan(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    data = [('topik', 'pola-bilangan'), ('topik', 'statistika'),
            ('topik_dibandingkan', 'pola-bilangan'),
            ('topik_dibandingkan', 'geometri-datar'),
            ('versi_pilihan_isi', '1'), ('profil_parameter', 'P3'),
            ('jumlah_soal', '10'), ('mode', 'drill'), ('format_jawaban', 'isian')]
    kode, isi, _ = server.minta('/sesi-gabungan/%d' % server.siswa,
                                auth=('guru', SANDI_GURU), data=data)
    assert kode == 409 and 'Bandingkan isi' in isi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('profil', ['P3', 'P4', 'P5', 'P6'])
def test_pilihan_variasi_menyimpan_kode_asli_tanpa_mengubah_profil(server, profil):
    kode, isi, _ = server.minta('/anak/%d' % server.siswa, auth=('guru', SANDI_GURU))
    assert kode == 200
    penanda = dict(zip(('P3','P4','P5','P6'), ('A','B','C','D')))[profil]
    assert '<span class="variasi-sr">Pilihan </span>%s' % penanda in isi
    kode, _, _ = server.minta('/sesi-baru/%d' % server.siswa, auth=('guru', SANDI_GURU), data={
        'topik': 'pola-bilangan', 'profil_parameter': profil, 'jumlah_soal': '4'})
    assert kode == 200
    with server.buka() as kon:
        assert kon.execute('SELECT level FROM sesi').fetchone()[0] == profil
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == 'P3'
        assert kon.execute('SELECT count(*) FROM kejadian_belajar').fetchone()[0] == 0
