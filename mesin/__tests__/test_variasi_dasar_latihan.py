"""Kontrak UI/manual/remedial Dasar, melalui data dan HTTP sintetis."""
import re
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest

import auth
import database
import question_context
import question_variants_ui
import teacher_pages
import topics
from assistant_inline import DrafLatihan
from generator import buat_lembar
from http_test_kit import SANDI_GURU, ServerUji


class Elemen(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tag = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tag.append((tag, dict(attrs)))


def panel(markup, mode):
    awal = markup.index('<fieldset data-mode-latihan="' + mode + '"')
    # Fieldset dasar bersarang; jangan berhenti pada penutup pertamanya.
    kedalaman = 0
    for m in re.finditer(r'</?fieldset\b[^>]*>', markup[awal:]):
        kedalaman += -1 if m.group().startswith('</') else 1
        if kedalaman == 0:
            return markup[awal:awal + m.end()]
    raise AssertionError('fieldset tidak seimbang')


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '1')
    srv = ServerUji(tmp_path, monkeypatch)
    with srv.buka() as kon:
        srv.siswa = database.tambah_siswa(kon, 'Anak Sintetis T2', 'P3', pemilik='guru')
    try:
        yield srv
    finally:
        srv.berhenti()


def halaman(server, mode='manual', draf=None):
    with server.buka() as kon:
        siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (server.siswa,)).fetchone()
        return teacher_pages.halaman_anak(
            kon, siswa, query='section=latihan&mode_latihan=' + mode,
            draf_latihan=draf,
        ).decode()


def post(server, data, route='sesi-baru', siswa=None, pengguna='guru'):
    return server.minta('/%s/%d' % (route, siswa or server.siswa),
                        auth=(pengguna, SANDI_GURU), data=data)


def keadaan(server):
    with server.buka() as kon:
        return tuple(kon.iterdump())


def terbaru(server):
    with server.buka() as kon:
        sesi = dict(kon.execute('SELECT * FROM sesi WHERE siswa_id=? ORDER BY id DESC',
                               (server.siswa,)).fetchone())
        assert kon.execute('SELECT tingkat FROM siswa WHERE id=?', (server.siswa,)).fetchone()[0] == 'P3'
        return sesi, database.isi_sesi(kon, sesi['id'])


def catat(kon, sid, level='P1', tid='tambah_dasar', tanggal='2026-10-01'):
    paket = topics.paket_untuk_template([tid])
    sesi = database.buat_sesi_dari_urutan(
        kon, sid, seed=100 + kon.execute('SELECT COUNT(*) FROM sesi').fetchone()[0],
        urutan=(tid,), level=level, topik=paket,
    )
    butir = database.isi_sesi(kon, sesi)[0]
    jawaban = database.simpan_jawaban(kon, butir['sesi_soal_id'], jawaban='999999', cara='hitung')
    database.simpan_diagnosis(kon, jawaban, benar=False, kode_usulan='K', kode_final='K', alasan='Sintetis')
    kon.execute('UPDATE sesi SET tanggal=?,selesai=?,direview=? WHERE id=?',
                (tanggal, tanggal, tanggal, sesi))
    return sesi


def test_definisi_dasar_berdasarkan_komposisi_bukan_slug(monkeypatch):
    assert question_context.topik_dasar('bilangan-dasar')
    assert not question_context.topik_dasar('pola-bilangan')
    assert not question_context.topik_dasar('campuran')
    assert not question_context.topik_dasar('asing')
    asli = topics.ambil
    daftar = topics.daftar_topik()
    paket = {'dasar-sintetis': {'P1': ('sintetis',)},
             'campur-sintetis': {'P1': ('sintetis',), 'P3': ('sintetis',)},
             'kosong-sintetis': {}}
    monkeypatch.setattr(topics, 'daftar_topik', lambda: daftar + list(paket))
    monkeypatch.setattr(topics, 'ambil', lambda k: SimpleNamespace(komposisi=paket[k]) if k in paket else asli(k))
    assert question_context.topik_dasar('dasar-sintetis')
    assert not question_context.topik_dasar('campur-sintetis')
    assert not question_context.topik_dasar('kosong-sintetis')


def test_markup_kartu_contoh_default_dan_tanpa_js_baru(server):
    isi = panel(halaman(server), 'manual')
    tag = Elemen(isi).tag
    assert '<legend>Variasi materi dasar</legend>' in isi
    assert 'Berlaku untuk topik Bilangan Dasar' in isi
    radios = [a for t, a in tag if t == 'input' and a.get('name') == 'variasi_dasar']
    assert [r['value'] for r in radios] == ['P1', 'P2']
    assert [r['value'] for r in radios if 'checked' in r] == ['P2']
    assert all('required' not in r for r in radios)
    assert 'name="profil_parameter"' not in isi
    assert '<script' not in isi
    assert len([a for t, a in tag if t == 'article' and a.get('class') == 'variasi-pilihan']) == 2
    for radio in radios:
        assert ('label', {'class': 'variasi-label', 'for': radio['id']}) in tag
    for lv, batas in [('P1', (1, 10)), ('P2', (11, 20))]:
        assert 'Variasi Dasar ' + lv[-1] in isi
        contoh = question_variants_ui._contoh_isi('bilangan-dasar', lv)[1]
        assert contoh in isi
        lembar = buat_lembar(42, urutan=('tambah_dasar',), level=lv, topik='bilangan-dasar')
        assert batas[0] <= int(lembar.soal[0].kunci) <= batas[1]


def test_keterangan_rentang_dasar_tampil_di_kartu_yang_tepat(server):
    isi = panel(halaman(server), 'manual')
    keterangan = {
        'P1': 'Hasil penjumlahan sampai 10',
        'P2': 'Hasil penjumlahan 11–20, termasuk melewati 10',
    }
    for level, teks in keterangan.items():
        kartu = isi.split('data-contoh="bilangan-dasar:' + level + '"', 1)[1].split('</article>', 1)[0]
        assert '<span class="variasi-keterangan-level">' + teks + '</span>' in kartu
        assert all(lain not in kartu for lv, lain in keterangan.items() if lv != level)
    assert topics.ambil('bilangan-dasar').keterangan_level == keterangan


def test_topik_tanpa_keterangan_mempertahankan_markup_kartu():
    from dataclasses import replace
    paket = topics.ambil('pola-bilangan')
    assert paket.keterangan_level is None
    assert replace(paket, keterangan_level=None) == paket
    args = ('P3', ('pola-bilangan',), 'uji', 'P3')
    lama = question_variants_ui._kartu_isi(*args)
    assert 'variasi-keterangan-level' not in lama
    assert question_variants_ui._kartu_isi(*args, keterangan=None) == lama
    assert question_variants_ui._kartu_isi(*args, keterangan='') == lama


def test_keterangan_level_opsional_tidak_mengubah_pemilih_lama(monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '1')
    paket = topics.ambil('bilangan-dasar')
    lama = question_variants_ui.pemilih_isi(['bilangan-dasar'], 'uji', 'P2')
    monkeypatch.setitem(paket.keterangan_level, 'P1', 'Keterangan sintetis tambahan')
    assert question_variants_ui.pemilih_isi(['bilangan-dasar'], 'uji', 'P2') == lama
    assert 'Keterangan sintetis tambahan' in question_variants_ui.pemilih_dasar('bilangan-dasar', 'P2')


def test_keterangan_di_escape_dan_kosong_tidak_menambah_elemen(monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '1')
    paket = topics.ambil('bilangan-dasar')
    monkeypatch.setitem(paket.keterangan_level, 'P1', '<b>Hasil & batas</b>')
    monkeypatch.delitem(paket.keterangan_level, 'P2')
    markup = question_variants_ui.pemilih_dasar('bilangan-dasar', 'P2')
    assert '&lt;b&gt;Hasil &amp; batas&lt;/b&gt;' in markup
    assert '<b>Hasil & batas</b>' not in markup
    assert markup.count('class="variasi-keterangan-level"') == 1


def test_draf_dasar_dan_pilihan_terakhir_konsisten(server):
    with server.buka() as kon:
        catat(kon, server.siswa, 'P1')
    for draf in (None, DrafLatihan('bilangan-dasar', '10', 'drill', False, '15', '0', profil_parameter='P1')):
        tag = Elemen(panel(halaman(server, draf=draf), 'manual')).tag
        assert any(t == 'option' and a.get('value') == 'bilangan-dasar' and 'selected' in a for t, a in tag)
        assert any(a.get('name') == 'variasi_dasar' and a.get('value') == 'P1' and 'checked' in a for _, a in tag)


@pytest.mark.parametrize('mode', ['gabungan', 'remedial'])
def test_variasi_tidak_masuk_panel_mode_lain_dan_dasar_tidak_ditawarkan_gabungan(server, mode):
    isi = panel(halaman(server, mode), mode)
    assert 'name="variasi_dasar"' not in isi
    assert 'Variasi materi dasar' not in isi
    assert 'value="bilangan-dasar"' not in isi


def test_css_has_menyembunyikan_non_dasar_dengan_prefix_halaman(server):
    from child_latihan_style import GAYA_LATIHAN, _R
    pola = re.escape(_R) + r'[^{}]*:has\(#manual-topik option:checked:not\(\[data-topik-dasar\]\)\)[^{}]*\.variasi-dasar-st\s*\{[^{}]*display:\s*none'
    assert re.search(pola, GAYA_LATIHAN)
    tag = Elemen(panel(halaman(server), 'manual')).tag
    dasar = next(a for t, a in tag if t == 'option' and a.get('value') == 'bilangan-dasar')
    assert 'data-topik-dasar' in dasar
    assert all('data-topik-dasar' not in a for t, a in tag if t == 'option' and a.get('value') in ('pola-bilangan', 'campuran'))
    for nama in ('practice_workspace.py', 'child_latihan_style.py', 'question_variants_ui.py'):
        assert not re.search(r'#[0-9a-fA-F]{3,8}\b', (Path(__file__).resolve().parents[1] / nama).read_text())


def test_http_manual_p1(server):
    status, _, _ = post(server, {'topik': 'bilangan-dasar', 'variasi_dasar': 'P1', 'jumlah_soal': '10'})
    assert status == 200
    sesi, soal = terbaru(server)
    assert sesi['level'] == 'P1'
    assert sesi['tujuan'] == 'bebas'
    assert len(soal) == 10
    assert all(s['template_id'] == 'tambah_dasar' and 1 <= int(s['kunci']) <= 10 for s in soal)


@pytest.mark.parametrize('tambahan,level', [({}, 'P2'), ({'variasi_dasar': 'P2'}, 'P2'),
                                           ({'profil_parameter': 'P1'}, 'P1')])
def test_http_default_dan_payload_lama(server, tambahan, level):
    assert post(server, dict({'topik': 'bilangan-dasar'}, **tambahan))[0] == 200
    assert terbaru(server)[0]['level'] == level


@pytest.mark.parametrize('nilai', [['P3'], [''], ['', ''], ['P1', 'P2'], ['P1', 'P1'], ['asing']])
def test_http_nilai_tidak_sah_tanpa_efek(server, nilai):
    awal = keadaan(server)
    data = [('topik', 'bilangan-dasar')] + [('variasi_dasar', n) for n in nilai]
    status, isi, _ = post(server, data)
    assert status == 400
    assert 'Variasi materi dasar' in isi
    assert keadaan(server) == awal


@pytest.mark.parametrize('nilai', [['P1'], ['P3'], [''], ['', ''], ['P1', 'P2']])
def test_http_non_dasar_mengabaikan_variasi(server, nilai):
    data = [('topik', 'pola-bilangan')] + [('variasi_dasar', n) for n in nilai]
    assert post(server, data)[0] == 200
    assert terbaru(server)[0]['level'] == 'P3'


def test_http_payload_lama_non_dasar_tetap_berlaku(server):
    assert post(server, {'topik': 'pola-bilangan', 'profil_parameter': 'P4', 'variasi_dasar': 'P1'})[0] == 200
    assert terbaru(server)[0]['level'] == 'P4'


@pytest.mark.parametrize('variasi', ['P1', 'P3'])
def test_http_kepemilikan_404_identik_tanpa_efek(server, variasi):
    auth.tambah_akun('guru-lain', SANDI_GURU, 'guru', path=auth.BERKAS_SANDI)
    awal = keadaan(server)
    data = {'topik': 'bilangan-dasar', 'variasi_dasar': variasi}
    asing = post(server, data, pengguna='guru-lain')
    hilang = post(server, data, pengguna='guru-lain', siswa=999999)
    assert asing[0] == hilang[0] == 404
    assert asing[1] == hilang[1]
    assert keadaan(server) == awal


def test_http_variasi_harus_didukung_topik_sebelum_writer(server, monkeypatch):
    paket = topics.ambil('bilangan-dasar')
    monkeypatch.delitem(paket.komposisi, 'P1')
    awal = keadaan(server)
    status, isi, _ = post(server, {'topik': 'bilangan-dasar', 'variasi_dasar': 'P1'})
    assert status == 400
    assert 'Materi tidak tersedia pada variasi ini' in isi
    assert keadaan(server) == awal


def test_http_gabungan_dasar_ditolak(server):
    awal = keadaan(server)
    data = [('topik', 'bilangan-dasar'), ('topik', 'pola-bilangan'), ('jumlah_soal', '10')]
    assert post(server, data, route='sesi-gabungan')[0] == 400
    assert keadaan(server) == awal


@pytest.mark.parametrize('sumber_eksplisit', [True, False])
def test_remedial_dasar_mempertahankan_p1(server, sumber_eksplisit):
    with server.buka() as kon:
        sumber = catat(kon, server.siswa, 'P1')
        # Sesi lebih baru topik lain tidak boleh menjadi acuan Dasar.
        catat(kon, server.siswa, 'P3', 'deret_aritmetika', tanggal='2026-10-02')
        lain = database.tambah_siswa(kon, 'Anak Lain Sintetis', 'P3', pemilik='guru')
        catat(kon, lain, 'P2', tanggal='2026-10-03')
    data = {'template_id': 'tambah_dasar', 'jumlah_soal': '5'}
    if sumber_eksplisit:
        data['sumber_sesi_id'] = str(sumber)
    assert post(server, data, route='sesi-remedial')[0] == 200
    sesi, soal = terbaru(server)
    assert sesi['jenis'] == 'remedial'
    assert sesi['level'] == 'P1'
    assert all(int(s['kunci']) <= 10 for s in soal)
    assert sesi['sumber_sesi_id'] == (sumber if sumber_eksplisit else None)


def test_remedial_sumber_dan_terbaru_memilih_level_masing_masing(server):
    with server.buka() as kon:
        sumber = catat(kon, server.siswa, 'P1')
        catat(kon, server.siswa, 'P2', tanggal='2026-10-02')
        tanpa = database.buat_sesi_remedial(kon, server.siswa, template_ids=['tambah_dasar'])
        dengan = database.buat_sesi_remedial(kon, server.siswa, template_ids=['tambah_dasar'], sumber_sesi_id=sumber)
        assert kon.execute('SELECT level FROM sesi WHERE id=?', (tanpa,)).fetchone()[0] == 'P2'
        assert kon.execute('SELECT level FROM sesi WHERE id=?', (dengan,)).fetchone()[0] == 'P1'


def test_remedial_sumber_asing_ditolak_sebelum_memilih_level(server):
    with server.buka() as kon:
        catat(kon, server.siswa, 'P1')
        lain = database.tambah_siswa(kon, 'Sumber Lain Sintetis', 'P3', pemilik='guru')
        sumber = catat(kon, lain, 'P2')
    awal = keadaan(server)
    data = {'template_id': 'tambah_dasar', 'sumber_sesi_id': str(sumber)}
    asing = post(server, data, route='sesi-remedial')
    data['sumber_sesi_id'] = '999999'
    hilang = post(server, data, route='sesi-remedial')
    assert asing[0] == hilang[0] == 404
    assert asing[1] == hilang[1]
    assert keadaan(server) == awal


def test_remedial_non_dasar_tetap_acuan_tingkat(server):
    with server.buka() as kon:
        sumber = catat(kon, server.siswa, 'P4', 'deret_aritmetika')
    assert post(server, {'template_id': 'deret_aritmetika', 'sumber_sesi_id': str(sumber)}, route='sesi-remedial')[0] == 200
    assert terbaru(server)[0]['level'] == 'P3'
