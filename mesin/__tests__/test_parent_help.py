"""Bantuan non-AI: sumber soal tepat, form utuh, tanpa outbound atau mutasi."""
import html
from html.parser import HTMLParser
import re
from dataclasses import replace

import pytest

import assistant_service
import database
import parent_help
import teacher_pages
from test_review_layout import db, sesi_contoh
from test_teacher_corrections import FormKoreksi
from test_correction_disclosure import Struktur


class Elemen(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.tags = []
        self.feed(isi)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_kartu_dan_faq_murni_tanpa_kontrol_atau_network():
    kartu = parent_help.kartu_pendampingan()
    assert kartu.count('<details ') == 3
    assert 'tanpa AI' in kartu and 'bukan penilaian kemampuan anak' in kartu
    for judul, _, _, _ in parent_help.KARTU:
        assert kartu.count(html.escape(judul)) == 1
    for isi in [kartu] + [parent_help.faq(k) for k in parent_help.FAQ]:
        tags = Elemen(isi).tags
        assert not any(t in ('form', 'input', 'button', 'script', 'iframe', 'a') for t, _ in tags)
        assert not any('open' in a for t, a in tags if t == 'details')
        assert 'fetch(' not in isi
    with pytest.raises(KeyError):
        parent_help.faq('asing')


def test_pembahasan_tunggal_dekat_soal_dengan_sumber_dan_payload_utuh(db):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon)
        sebelum = tuple(kon.iterdump())
        markup = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        form = FormKoreksi(markup, sesi).data
        struktur = Struktur(markup)
        kartu = re.findall(r'<article\b[^>]*data-kartu-tinjauan.*?</article>', markup, re.S)
        assert len(kartu) == len(ids)
        sumber = {b['sesi_soal_id']: b for b in database.isi_sesi(kon, sesi)}
        for sid, card in zip(ids, kartu):
            b = sumber[sid]
            assert card.count('class="koreksi-opsi-st koreksi-kunci-st"') == 1
            assert card.count(f'id="pembahasan-soal-{sid}"') == 1
            assert f'Lihat kunci &amp; pembahasan soal {b["nomor"]}' in card
            assert card.index('koreksi-jawaban-utama-st') < card.index('koreksi-kunci-st') < card.index('koreksi-pemahaman-st')
            assert html.escape(b['kunci']) in card
            soal = teacher_pages._soal_dari_baris(b)
            assert html.escape(soal.pembahasan) in card
            assert 'hasil setelah dibantu bukan jawaban mandiri' in card
            details = [a for t, a in Elemen(card).tags if t == 'details']
            assert len(details) == 2 and all('open' not in a for a in details)
            assert not struktur.tertutup(f'kode_{sid}')
            assert form[f'jwb_{sid}'] == b['jawaban']
        assert markup.index('judul-bantuan-pendampingan') > markup.index('</form>', markup.index(f'id="form-koreksi-{sesi}"'))
        assert tuple(kon.iterdump()) == sebelum


def test_pembahasan_escaped_dan_kosong_tidak_mengarang(db):
    import teacher_session_pages
    with database.buka(db) as kon:
        sesi, _ = sesi_contoh(kon)
        def sumber(b):
            return replace(teacher_session_pages._soal_dari_baris(b), pembahasan='<script>contoh</script>\n0 < 1')
        isi = teacher_session_pages.halaman_sesi_stitch(kon, sesi, soal_dari_baris=sumber).decode()
        assert '&lt;script&gt;contoh&lt;/script&gt;' in isi and '<script>contoh</script>' not in isi
        def kosong(b):
            return replace(teacher_session_pages._soal_dari_baris(b), pembahasan='')
        isi = teacher_session_pages.halaman_sesi_stitch(kon, sesi, soal_dari_baris=kosong).decode()
        assert isi.count('Pembahasan belum tersedia untuk soal ini.') == 3


@pytest.mark.parametrize('section', ['rencana', 'latihan', 'perkembangan', 'riwayat'])
def test_faq_sesuai_tab_tanpa_outbound_dan_tanpa_write(db, monkeypatch, section):
    def terlarang(*a, **kw):
        pytest.fail('Bantuan statis tidak boleh memanggil provider')
    monkeypatch.setattr(assistant_service, 'panggil_provider_default', terlarang)
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    with database.buka(db) as kon:
        sesi, _ = sesi_contoh(kon)
        siswa = kon.execute('SELECT * FROM siswa LIMIT 1').fetchone()
        sebelum = tuple(kon.iterdump())
        markup = teacher_pages.halaman_anak(kon, siswa, query='section=' + section).decode()
        if section == 'riwayat':
            assert 'data-faq-lokal=' not in markup
        else:
            assert markup.count('data-faq-lokal=') == 1
            assert f'data-faq-lokal="{section}"' in markup
            assert html.escape(parent_help.FAQ[section][0]) in markup
        if section != 'riwayat':
            assert 'bantuan-statis-faq' in markup.split('</head>', 1)[0]
            assert 'bantuan-statis-faq {' not in markup.split('<body', 1)[1]
        assert ('id="judul-bantuan-pendampingan"' in markup) == (section == 'rencana')
        assert tuple(kon.iterdump()) == sebelum


def test_http_ownership_dan_murid_tetap_terjaga(tmp_path, monkeypatch):
    from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.setenv('PENDAMPING_AKTIF', '0')
    def terlarang(*a, **kw):
        pytest.fail('GET bantuan tidak boleh memanggil provider')
    monkeypatch.setattr(assistant_service, 'panggil_provider_default', terlarang)
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            sesi, _ = sesi_contoh(kon)
            anak = kon.execute('SELECT siswa_id FROM sesi WHERE id=?', (sesi,)).fetchone()[0]
            asing = database.tambah_siswa(kon, 'Anak Asing Sintetis', pemilik='orang-lain')
            sesi_asing = database.buat_sesi(kon, asing, 72)
        for path in (f'/anak/{anak}', f'/anak/{anak}?section=latihan', f'/sesi/{sesi}'):
            kode, isi, _ = server.minta(path, auth=('guru', SANDI_GURU))
            assert kode == 200 and ('bantuan-statis' in isi)
            _, isi_murid, _ = server.minta(path, auth=('feby', SANDI_MURID))
            assert 'id="judul-bantuan-pendampingan"' not in isi_murid
            assert 'id="pembahasan-soal-' not in isi_murid
        for path in (f'/anak/{asing}', f'/sesi/{sesi_asing}'):
            kode, isi, _ = server.minta(path, auth=('guru', SANDI_GURU))
            assert kode == 404
            assert 'data-faq-lokal=' not in isi and 'kunci-val' not in isi
    finally:
        server.berhenti()


@pytest.mark.parametrize('section', ['rencana', 'latihan', 'perkembangan', 'riwayat'])
def test_disclaimer_belum_dinilai_tidak_diulang_dalam_satu_tab(db, section):
    with database.buka(db) as kon:
        sesi_contoh(kon)
        siswa = kon.execute('SELECT * FROM siswa LIMIT 1').fetchone()
        markup = teacher_pages.halaman_anak(kon, siswa, query='section=' + section).decode()
    assert markup.count('Belum dinilai bukan berarti tidak mampu') <= 1
    assert markup.count('belum dinilai bukan berarti tidak mampu') <= 1


def test_beranda_menggabung_bantuan_dalam_satu_akordeon(db):
    with database.buka(db) as kon:
        sesi_contoh(kon)
        siswa = kon.execute('SELECT * FROM siswa LIMIT 1').fetchone()
        markup = teacher_pages.halaman_anak(kon, siswa, query='section=rencana').decode()
    awal = markup.index('<details class="bantuan-gabungan-st">')
    gabungan = markup[awal:markup.index('</section></details>', awal)]
    assert '<summary>Bantuan</summary>' in gabungan
    assert 'data-faq-lokal="rencana"' in gabungan and 'id="judul-bantuan-pendampingan"' in gabungan
    assert markup.count('<details class="bantuan-statis-faq"') == 1
    # Tidak ada akordeon bantuan di luar gabungan.
    luar = (markup[:awal] + markup[awal + len(gabungan):]).split('<body', 1)[1]
    assert 'class="bantuan-statis-faq"' not in luar and 'class="bantuan-statis-kartu"' not in luar
