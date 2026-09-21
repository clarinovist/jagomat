"""Persetujuan usulan bukan override; hanya konfirmasi sah yang mengesahkan."""
import html
import re

import pytest

import database
from test_teacher_corrections import server, isi_awal, form, kirim, keadaan, FormKoreksi


def status_penilaian(isi, sid):
    cocok = re.search(rf'<p[^>]*id="penilaian-status-{sid}"[^>]*>(.*?)</p>', isi, re.S)
    assert cocok, 'Status persetujuan per butir harus terlihat.'
    return html.unescape(re.sub('<[^>]+>', '', cocok[1]))


def test_usulan_konkret_dan_alasan_di_dekat_dropdown(server):
    s = server
    isi_awal(s, 'Cara asli')
    data, isi = form(s)
    assert data[f'kode_{s.sid}'] == ''
    assert '<option value="" selected>Otomatis — Jawaban benar</option>' in isi
    sebelum_panduan = isi.split('<summary>Panduan memilih penilaian</summary>', 1)[0]
    assert '<b>Alasan:</b> jawaban benar' in sebelum_panduan
    assert 'tidak perlu mengganti dropdown' in isi
    assert 'Pilihan dropdown baru disimpan setelah menekan Simpan draf atau Konfirmasi hasil sesi.' in isi
    assert 'Penilaian saat halaman dimuat: Jawaban benar — ubah' in isi
    assert 'Belum dikonfirmasi' in status_penilaian(isi, s.sid)
    assert keadaan(s)[1:] == ([], [])


@pytest.mark.parametrize('kasus', ['benar', 'H', 'N'])
def test_konfirmasi_default_adalah_persetujuan_tanpa_override(server, kasus):
    s = server
    if kasus == 'H':
        with s.buka() as kon:
            malrule = next(m for m in database.malrule_soal(kon, s.butir['soal_id']) if m['kode'] == 'H')
        isi_awal(s, 'Cara asli', jawaban=malrule['jawaban'])
    else:
        isi_awal(s, '' if kasus == 'N' else 'Cara asli')
    data, _ = form(s)
    assert data[f'kode_{s.sid}'] == ''
    assert kirim(s, data)[0] == 200  # Tanpa menyentuh dropdown.
    hasil, snapshot, bukti = keadaan(s)
    assert hasil['manual'] == 0
    assert snapshot[0]['benar'] == (kasus == 'benar')
    assert snapshot[0]['kode_final'] == (None if kasus == 'benar' else kasus)
    assert snapshot[0]['cek_pemahaman'] is None  # Persetujuan bukan bukti memahami.
    _, isi = form(s)
    status = status_penilaian(isi, s.sid)
    label = {'benar': 'Jawaban benar', 'H': 'Perlu memeriksa hitungan', 'N': 'Menebak atau belum menunjukkan cara'}[kasus]
    assert label in status
    assert 'Usulan Jagomat · Disetujui saat konfirmasi sesi' in status
    assert isi.index(f'id="penilaian-status-{s.sid}"') < isi.index('koreksi-lanjutan-st"')
    assert kirim(s, form(s)[0])[0] == 200
    assert keadaan(s)[1:] == (snapshot, bukti)


@pytest.mark.parametrize('kode', ['benar', 'H'])
def test_pilihan_sendiri_juga_keputusan_setelah_konfirmasi(server, kode):
    s = server
    isi_awal(s, 'Cara asli', kode=kode)
    assert kirim(s, form(s)[0])[0] == 200
    status = status_penilaian(form(s)[1], s.sid)
    assert 'Pilihan sendiri · Ditetapkan saat konfirmasi sesi' in status
    assert 'Usulan Jagomat · Disetujui' not in status
    assert keadaan(s)[0]['manual'] == 1


def test_simpan_draf_menerapkan_otomatis_tanpa_mengklaim_persetujuan(server):
    s = server
    isi_awal(s, 'Cara asli', kode='H')
    data, isi = form(s)
    assert 'Pilihan ini tetap dipakai' not in isi
    assert 'Usulan ini tidak dipakai selama penilaian guru dipilih' not in isi
    assert 'Penilaian saat halaman dimuat: Perlu memeriksa hitungan — ubah' in isi
    data[f'kode_{s.sid}'] = ''
    assert kirim(s, data, jalur='/tinjauan')[0] == 200
    hasil, snapshot, bukti = keadaan(s)
    assert hasil['manual'] == 0 and hasil['benar'] == 1
    assert snapshot == bukti == []
    assert 'Belum dikonfirmasi' in status_penilaian(form(s)[1], s.sid)


@pytest.mark.parametrize('kasus', ['invalidasi', 'fingerprint', 'dibatalkan', 'outcome', 'tanpa_snapshot'])
def test_konfirmasi_tidak_aktif_atau_tidak_cocok_bukan_persetujuan(server, kasus):
    s = server
    isi_awal(s, 'Cara asli')
    assert kirim(s, form(s)[0])[0] == 200
    with s.buka() as kon:
        if kasus == 'invalidasi':
            b = database.isi_sesi(kon, s.sesi)[0]
            database.simpan_diagnosis(kon, b['jawaban_id'], False, 'H', 'H')
        elif kasus == 'fingerprint':
            kon.execute("UPDATE sesi SET fingerprint_konfirmasi='tidak-cocok' WHERE id=?", (s.sesi,))
        elif kasus == 'dibatalkan':
            database.batalkan_sesi(kon, s.sesi)
        elif kasus == 'outcome':
            # Cache mutable menyimpang tidak boleh diklaim disetujui snapshot lama.
            kon.execute("UPDATE diagnosis SET benar=0,kode_final='H' WHERE jawaban_id=?", (database.isi_sesi(kon, s.sesi)[0]['jawaban_id'],))
        else:
            # Header sintetis tidak lengkap: arsip lama tetap append-only.
            kon.execute('''INSERT INTO konfirmasi_hasil(sesi_id,nomor_urut,guru,fingerprint)
                SELECT sesi_id,2,guru,fingerprint FROM konfirmasi_hasil WHERE sesi_id=?''', (s.sesi,))
    if kasus == 'tanpa_snapshot':
        from http_test_kit import SANDI_GURU
        kode, isi, _ = s.minta(f'/sesi/{s.sesi}', auth=('guru', SANDI_GURU))
        assert kode == 404  # Reader bukti menolak arsip rusak sebelum render.
        assert 'Disetujui saat konfirmasi sesi' not in isi
        return
    status = status_penilaian(form(s)[1], s.sid)
    assert 'Disetujui saat konfirmasi sesi' not in status
    assert 'Ditetapkan saat konfirmasi sesi' not in status


def test_gagal_konfirmasi_menampilkan_draf_bukan_persetujuan_lama(server):
    s = server
    isi_awal(s, 'Cara asli')
    assert kirim(s, form(s)[0])[0] == 200
    data, _ = form(s)
    data[f'jwb_{s.sid}'] = ''
    data[f'cara_{s.sid}'] = ''
    sebelum = keadaan(s)
    kode, isi, _ = kirim(s, data)
    assert kode == 400 and keadaan(s) == sebelum
    assert FormKoreksi(isi, s.sesi).data == data
    status = status_penilaian(isi, s.sid)
    assert 'Belum disimpan' in status
    assert 'Disetujui saat konfirmasi sesi' not in status


def test_dilewati_bukan_usulan_yang_disetujui(server):
    s = server
    isi_awal(s, 'Cara asli')
    data, _ = form(s)
    data[f'dilewati_{s.sid}'] = '1'
    assert kirim(s, data)[0] == 200
    status = status_penilaian(form(s)[1], s.sid)
    assert 'Dilewati dari penilaian' in status
    assert 'Disetujui saat konfirmasi sesi' not in status
    assert keadaan(s)[1][0]['dilewati'] == 1


def test_tanpa_usulan_tetap_perlu_tinjauan_dan_tidak_dikonfirmasi(server):
    s = server
    isi_awal(s, 'Cara belum terpetakan', jawaban='999999')
    data, isi = form(s)
    assert 'Belum yakin — perlu ditinjau' in isi
    assert 'Otomatis —' not in isi
    assert 'Jagomat belum dapat mengusulkan penilaian.' in isi
    assert '<b>Alasan:</b>' in isi.split('<summary>Panduan memilih penilaian</summary>', 1)[0]
    sebelum = keadaan(s)
    assert kirim(s, data)[0] == 400
    assert keadaan(s) == sebelum


def test_alasan_di_escape_dan_tidak_digandakan(server):
    s = server
    isi_awal(s, 'Cara asli')
    with s.buka() as kon:
        b = database.isi_sesi(kon, s.sesi)[0]
        database.simpan_diagnosis(kon, b['jawaban_id'], False, 'H', 'H', alasan='<script>contoh</script>')
    _, isi = form(s)
    assert '<script>contoh</script>' not in isi
    assert isi.count('&lt;script&gt;contoh&lt;/script&gt;') == 1
    assert '&lt;script&gt;contoh&lt;/script&gt;' in isi.split('<summary>Panduan memilih penilaian</summary>', 1)[0]
