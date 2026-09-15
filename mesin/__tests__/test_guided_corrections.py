"""Koreksi terpandu ringkas: hierarki terlihat dan bukti tetap jujur."""
import re

import pytest

from test_teacher_corrections import server, isi_awal, form, kirim, keadaan, FormKoreksi
from test_correction_disclosure import Struktur


def test_tinjau_tanpa_usulan_palsu_dan_pendampingan_sebelum_penilaian(server):
    s = server
    isi_awal(s, 'Cara belum terpetakan', jawaban='999999')
    data, isi = form(s)
    badan = isi.split('</style>')[-1]
    assert 'Usulan Jagomat: Perlu penilaian' not in badan
    assert 'Belum yakin — perlu ditinjau' in badan
    assert 'Gunakan usulan Jagomat' not in badan
    assert badan.index('class="koreksi-pemahaman-st"') < badan.index('class="koreksi-opsi-st koreksi-penilaian-st"')
    assert 'Tanyakan: “Kamu dapat jawaban ini dari mana?”' in badan
    assert 'Tentukan penilaian — belum dipilih' in badan
    assert data[f'kode_{s.sid}'] == ''
    sebelum = keadaan(s)
    status, galat, _ = kirim(s, data)
    assert status == 400 and keadaan(s) == sebelum
    assert FormKoreksi(galat, s.sesi).data == data
    assert not Struktur(galat).tertutup(f'kode_{s.sid}')


def test_radio_empat_pilihan_native_tanpa_menciptakan_bukti(server):
    s = server
    isi_awal(s, 'Cara tertulis', jawaban='999999')
    data, isi = form(s)
    radio = re.findall(rf'<input[^>]+name="cek_pemahaman_{s.sid}"[^>]*>', isi)
    assert len(radio) == 4
    assert all('type="radio"' in r for r in radio)
    assert {re.search(r'value="([^"]*)"', r)[1] for r in radio} == {'', 'bisa_menjelaskan', 'ragu', 'menghafal'}
    aktif = [r for r in radio if 'checked' in r]
    assert len(aktif) == 1 and 'value=""' in aktif[0]
    for r in radio:
        identitas = re.search(r'id="([^"]*)"', r)[1]
        assert f'<label for="{identitas}">' in isi
    assert data[f'cek_pemahaman_{s.sid}'] == ''
    assert 'Cenderung menghafal' in isi and 'Belum dicatat' in isi


@pytest.mark.parametrize('paham', ['', 'bisa_menjelaskan', 'ragu', 'menghafal'])
def test_radio_roundtrip_pilihan_tersimpan_dan_draf_gagal(server, paham):
    s = server
    isi_awal(s, 'Cara tertulis')
    data, _ = form(s)
    data[f'cek_pemahaman_{s.sid}'] = paham
    assert kirim(s, data)[0] == 200
    pulih, isi = form(s)
    assert pulih[f'cek_pemahaman_{s.sid}'] == paham
    aktif = re.findall(rf'<input[^>]+name="cek_pemahaman_{s.sid}"[^>]*checked[^>]*>', isi)
    assert len(aktif) == 1 and f'value="{paham}"' in aktif[0]
    pulih.update({f'jwb_{s.sid}': '999999', f'cara_{s.sid}': 'Catatan draf'})
    sebelum = keadaan(s)
    status, galat, _ = kirim(s, pulih)
    assert status == 400 and keadaan(s) == sebelum
    assert FormKoreksi(galat, s.sesi).data == pulih


def test_detail_sekunder_dilipat_tanpa_menghilangkan_field(server):
    s = server
    isi_awal(s, 'Cara belum terpetakan', jawaban='999999')
    data, isi = form(s)
    m = Struktur(isi)
    assert m.tertutup(f'cara_{s.sid}')
    assert m.tertutup(f'belum_{s.sid}')
    assert not m.tertutup(f'cek_pemahaman_{s.sid}')
    assert data[f'cara_{s.sid}'] == 'Cara belum terpetakan'
    assert data.get(f'hadir_belum_{s.sid}') == '1'
    assert data.get(f'hadir_dilewati_{s.sid}') == '1'
    assert not any('disabled' in a for kontrol in m.kontrol.values() for a, _ in kontrol)
    assert 'Centang hanya jika anak mengatakannya, bukan karena ia bingung.' in isi


def test_lewati_bernama_jelas_dan_tidak_diaktifkan_otomatis(server):
    s = server
    isi_awal(s, 'Catatan asli', jawaban='999999')
    data, isi = form(s)
    assert '>Opsi lain' not in isi
    assert '>Lewati soal ini dari penilaian</summary>' in isi
    assert 'Jangan sertakan soal ini dalam penilaian' in isi
    assert f'dilewati_{s.sid}' not in data
    assert 'bukan benar atau salah' in isi
    data[f'dilewati_{s.sid}'] = '1'
    assert kirim(s, data)[0] == 200
    hasil, snapshot, _ = keadaan(s)
    assert hasil['cara'] == 'Catatan asli' and hasil['jawaban'] == '999999'
    assert snapshot[0]['dilewati'] == 1 and snapshot[0]['kode_final'] is None
    assert snapshot[0]['jawaban'] == ''
    _, isi = form(s)
    assert '>Dilewati dari penilaian — ubah</summary>' in isi


def test_radio_gaya_terbaca_fokus_dan_target_sentuh():
    from style_stitch import CSS_SESI
    import design_tokens as T

    assert '.koreksi-pilihan-paham-st' in CSS_SESI
    blok = re.search(r'\.koreksi-pilihan-paham-st label \{([^}]+)', CSS_SESI)[1]
    assert f'min-height: {T.TARGET_SENTUH}' in blok
    assert f'color: {T.TEKS_JUDUL}' in blok
    assert '.koreksi-pilihan-paham-st input:focus-visible + label' in CSS_SESI
    assert '.koreksi-pilihan-paham-st input:checked + label' in CSS_SESI
