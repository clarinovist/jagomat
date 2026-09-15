"""Koreksi benar diringkas tanpa menyembunyikan perhatian atau mengubah bukti."""
from html.parser import HTMLParser
import re

import pytest

import database
import teacher_pages
from assistant_inline import DrafButir, DrafKoreksi
from http_test_kit import ServerUji, SANDI_GURU
from test_teacher_corrections import FormKoreksi


class Struktur(HTMLParser):
    """Catat ancestor detail tertutup dan field form tanpa menafsirkan CSS."""

    def __init__(self, isi):
        super().__init__()
        self.detail = []
        self.kontrol = {}
        self.disclosure = []
        self.ids = []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'details':
            self.detail.append(a)
            if 'koreksi-pendampingan-st' in a.get('class', '').split():
                self.disclosure.append(a)
        if tag in {'input', 'select', 'textarea'} and 'name' in a:
            self.kontrol.setdefault(a['name'], []).append((a, tuple(self.detail)))

    def handle_endtag(self, tag):
        if tag == 'details':
            self.detail.pop()

    def tertutup(self, nama):
        return any('open' not in a for a in self.kontrol[nama][0][1]
                   if a.get('class') != 'panduan-edit-hasil-st')


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        anak = database.tambah_siswa(kon, 'Anak Sintetis', 'P3', pemilik='guru')
        s.sesi = database.buat_sesi(kon, anak, seed=71, level='P3', jumlah_soal=1)
        s.butir = dict(database.isi_sesi(kon, s.sesi)[0])
        s.sid = int(s.butir['sesi_soal_id'])
        database.tandai_selesai(kon, s.sesi)
    yield s
    s.berhenti()


def isi_awal(s, *, cara='Anak menghitung sendiri.', kode='', jawaban=None, belum=False):
    data = {f'jwb_{s.sid}': s.butir['kunci'] if jawaban is None else jawaban,
            f'cara_{s.sid}': cara, f'kode_{s.sid}': kode}
    if belum:
        data[f'belum_{s.sid}'] = '1'
    with s.buka() as kon:
        teacher_pages.simpan_sesi(kon, s.sesi, data)


def halaman(s, **kwargs):
    with s.buka() as kon:
        return teacher_pages.halaman_sesi_stitch(kon, s.sesi, **kwargs).decode()


def kirim(s, data):
    return s.minta(f'/sesi/{s.sesi}/konfirmasi', data=data, auth=('guru', SANDI_GURU))


@pytest.mark.parametrize('tujuan', ['bebas', 'pemetaan', 'latihan_terbimbing', 'penguatan',
                                    'pengenalan', 'maintenance'])
def test_benar_biasa_menggabungkan_pendampingan_tertutup_dan_form_utuh(server, tujuan):
    s = server
    with s.buka() as kon:
        kon.execute('UPDATE sesi SET tujuan=? WHERE id=?', (tujuan, s.sesi))
    isi_awal(s)
    isi = halaman(s)
    m = Struktur(isi)
    assert len(m.disclosure) == 1 and 'open' not in m.disclosure[0]
    assert 'Catatan pendampingan (opsional)' in isi
    for nama in (f'cara_{s.sid}', f'cek_pemahaman_{s.sid}', f'belum_{s.sid}'):
        assert m.tertutup(nama)
        assert len(m.kontrol[nama]) == 1
        assert 'disabled' not in m.kontrol[nama][0][0]
    assert not m.tertutup(f'jwb_{s.sid}')
    assert len(m.ids) == len(set(m.ids))
    assert isi.count(f'id="form-koreksi-{s.sesi}"') == 1
    assert isi.count('>Konfirmasi hasil</button>') == 1
    assert 'catatan tersimpan' in isi
    assert '<div class="usulan-st">' not in isi.split('<details class="koreksi-opsi-st koreksi-penilaian-st"')[0]


@pytest.mark.parametrize('tujuan', ['evaluasi', 'checkpoint'])
def test_evaluasi_checkpoint_semua_butir_tetap_terbuka(server, tujuan):
    s = server
    isi_awal(s)
    with s.buka() as kon:
        kon.execute('UPDATE sesi SET tujuan=? WHERE id=?', (tujuan, s.sesi))
    isi = halaman(s)
    m = Struktur(isi)
    assert not m.tertutup(f'cek_pemahaman_{s.sid}')
    assert not m.tertutup(f'cara_{s.sid}')
    assert 'catatan pemahaman pada soal fokus dipakai untuk menilai penguasaan' in isi


@pytest.mark.parametrize('cara,kode,jawaban,belum', [
    ('', '', None, False), ('[pilihan] tebak', '', None, False),
    ('[pilihan] bingung', '', None, False), ('Cara', '', None, True),
    ('Cara', 'H', None, False), ('Cara', '', '999999', False),
    ('', '', '', False),
])
def test_salah_nt_dan_belum_dinilai_tidak_diringkas(server, cara, kode, jawaban, belum):
    s = server
    isi_awal(s, cara=cara, kode=kode, jawaban=jawaban, belum=belum)
    m = Struktur(halaman(s))
    assert not m.tertutup(f'cara_{s.sid}')
    assert not m.tertutup(f'cek_pemahaman_{s.sid}')


@pytest.mark.parametrize('cara,paham,belum,indikator', [
    ('Cara', 'ragu', False, 'Masih ragu'),
    ('Cara', 'menghafal', False, 'Cenderung menghafal'),
    ('[pilihan] tebak — catatan', '', False, 'Anak menandai menebak'),
    ('[pilihan] bingung', '', False, 'Anak menandai bingung'),
    ('Cara', '', True, 'Belum pernah melihat soal seperti ini'),
])
def test_override_benar_tidak_menyamarkan_sinyal_perhatian(server, cara, paham, belum, indikator):
    s = server
    isi_awal(s, cara=cara, kode='benar', belum=belum)
    data = FormKoreksi(halaman(s), s.sesi).data
    data[f'cek_pemahaman_{s.sid}'] = paham
    assert kirim(s, data)[0] == 200
    isi = halaman(s)
    m = Struktur(isi)
    assert not m.tertutup(f'cara_{s.sid}')
    assert not m.tertutup(f'cek_pemahaman_{s.sid}')
    ringkasan = re.search(r'<details class="koreksi-opsi-st koreksi-pendampingan-st"[^>]*>\s*<summary>(.*?)</summary>', isi, re.S)[1]
    assert 'perlu perhatian' in ringkasan and indikator in ringkasan


@pytest.mark.parametrize('kode_lama', ['', 'H'])
@pytest.mark.parametrize('kode,jawaban,label,tertutup', [
    ('', '999999', 'Belum dinilai', False),
    ('H', None, 'Salah hitung', False),
    ('benar', '999999', 'Tepat', True),
    ('', None, 'Tepat', True),
])
def test_status_dan_disclosure_mengikuti_draf_bukan_lencana_db(server, kode, jawaban, label, tertutup, kode_lama):
    s = server
    isi_awal(s, kode=kode_lama)
    draf = DrafKoreksi(((s.sid, DrafButir(s.butir['kunci'] if jawaban is None else jawaban,
                                       kode, 'Cara draf', '', False, False)),), False)
    isi = halaman(s, draf_koreksi=draf)
    assert f'<span class="koreksi-status-label-st">{label}</span>' in isi
    assert Struktur(isi).tertutup(f'cek_pemahaman_{s.sid}') == tertutup
    if tertutup:
        assert Struktur(isi).tertutup(f'kode_{s.sid}')
        assert 'catatan belum disimpan' in isi
        assert 'catatan tersimpan' not in isi.split('</style>')[-1]


@pytest.mark.parametrize('paham', ['', 'bisa_menjelaskan', 'ragu', 'menghafal'])
def test_roundtrip_tidak_mengubah_nilai_snapshot_laporan_dan_siklus(server, paham):
    import reports
    s = server
    isi_awal(s, cara='[pilihan] hitung_satu_satu — <catatan sintetis>')
    data = FormKoreksi(halaman(s), s.sesi).data
    data[f'cek_pemahaman_{s.sid}'] = paham
    assert kirim(s, data)[0] == 200
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())
        anak = kon.execute('SELECT siswa_id FROM sesi WHERE id=?', (s.sesi,)).fetchone()[0]
        bukti = database.muat_bukti_siklus(kon, anak)
        laporan = reports.halaman_laporan(kon, anak)
    isi = halaman(s)
    pulih = FormKoreksi(isi, s.sesi).data
    assert pulih[f'cek_pemahaman_{s.sid}'] == paham
    assert pulih[f'kode_{s.sid}'] == ''
    assert kirim(s, pulih)[0] == 200
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
        assert database.muat_bukti_siklus(kon, anak) == bukti
        assert reports.halaman_laporan(kon, anak) == laporan
        nilai = kon.execute('SELECT cek_pemahaman FROM snapshot_outcome').fetchone()[0]
        assert nilai == (paham or None)
    assert Struktur(isi).tertutup(f'cek_pemahaman_{s.sid}') == (paham not in {'ragu', 'menghafal'})


def test_css_disclosure_native_dan_grid_tanpa_kolom_kosong():
    from style_stitch import CSS_SESI
    import design_tokens as T

    tunggal = re.search(r'\.koreksi-bukti-st\.koreksi-bukti-tunggal-st \{([^}]+)', CSS_SESI)[1]
    assert 'grid-template-columns: minmax(0, 1fr)' in tunggal
    assert f'min-height: {T.TARGET_SENTUH}' in re.search(r'\.koreksi-opsi-st summary \{([^}]+)', CSS_SESI)[1]
    assert f'outline: 2px solid {T.FOKUS_AKSEN}' in re.search(r'\.koreksi-opsi-st summary:focus-visible \{([^}]+)', CSS_SESI)[1]
    ringkasan = re.search(r'\.koreksi-ringkasan-catatan-st \{([^}]+)', CSS_SESI)[1]
    assert 'overflow-wrap: anywhere' in ringkasan


def test_drill_ringkas_tanpa_field_cara_dan_tanpa_bukti_paham_baru(server):
    s = server
    with s.buka() as kon:
        kon.execute("UPDATE sesi SET mode='drill' WHERE id=?", (s.sesi,))
    isi_awal(s, cara='')
    isi = halaman(s)
    assert f'name="cara_{s.sid}"' not in isi
    assert Struktur(isi).tertutup(f'cek_pemahaman_{s.sid}')
    assert kirim(s, FormKoreksi(isi, s.sesi).data)[0] == 200
    with s.buka() as kon:
        assert kon.execute('SELECT cek_pemahaman FROM snapshot_outcome').fetchone()[0] is None


@pytest.mark.parametrize('paham', ['', 'bisa_menjelaskan', 'ragu', 'menghafal'])
def test_draf_pemahaman_mengalahkan_snapshot_termasuk_dikosongkan(server, paham):
    s = server
    isi_awal(s)
    data = FormKoreksi(halaman(s), s.sesi).data
    data[f'cek_pemahaman_{s.sid}'] = 'ragu'
    assert kirim(s, data)[0] == 200
    draf = DrafKoreksi(((s.sid, DrafButir(s.butir['kunci'], '', 'Cara draf', paham, False, False)),), False)
    isi = halaman(s, draf_koreksi=draf)
    assert FormKoreksi(isi, s.sesi).data[f'cek_pemahaman_{s.sid}'] == paham
    assert Struktur(isi).tertutup(f'cek_pemahaman_{s.sid}') == (paham not in {'ragu', 'menghafal'})
    assert 'catatan belum disimpan' in isi


def test_konfirmasi_gagal_membuka_kontrol_dan_mempertahankan_draf(server):
    s = server
    isi_awal(s)
    data = FormKoreksi(halaman(s), s.sesi).data
    data[f'jwb_{s.sid}'] = '999999'
    data[f'cara_{s.sid}'] = 'Cara baru <sintetis>'
    data[f'cek_pemahaman_{s.sid}'] = 'ragu'
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())
    status, isi, _ = kirim(s, data)
    assert status == 400
    assert FormKoreksi(isi, s.sesi).data == data
    assert not Struktur(isi).tertutup(f'cara_{s.sid}')
    assert not Struktur(isi).tertutup(f'cek_pemahaman_{s.sid}')
    assert f'id="masalah-soal-{s.sid}"' in isi
    assert 'koreksi-status-st">Perlu ditinjau' in isi
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_diagnosis_warisan_noop_tidak_diringkas_karena_kunci_cocok(server):
    s = server
    isi_awal(s)
    with s.buka() as kon:
        jid = database.isi_sesi(kon, s.sesi)[0]['jawaban_id']
        database.simpan_diagnosis(kon, jid, False, 'H', 'H', alasan='Diagnosis warisan')
    isi = halaman(s)
    assert '<span class="koreksi-status-label-st">Salah hitung</span>' in isi
    assert not Struktur(isi).tertutup(f'cek_pemahaman_{s.sid}')


def test_error_dan_dilewati_membuka_kontrol_walaupun_override_benar(server):
    s = server
    isi_awal(s, kode='benar')
    isi = halaman(s, masalah_konfirmasi=((s.sid, 1, 'tidak_konsisten'),))
    assert not Struktur(isi).tertutup(f'cara_{s.sid}')
    assert f'id="masalah-soal-{s.sid}"' in isi
    draf = DrafKoreksi(((s.sid, DrafButir(s.butir['kunci'], 'benar', 'Cara', '', True, False)),), False)
    isi = halaman(s, draf_koreksi=draf)
    assert not Struktur(isi).tertutup(f'cek_pemahaman_{s.sid}')
    assert 'Opsi lain — butir ditandai dilewati' in isi
