"""Regresi hirarki ruang orang tua, tanpa perubahan izin atau data belajar."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import assistant_components
import assistant_inline
import database
import share_links
import teacher_pages
from test_assistant_panel_shell import StrukturPanel


@pytest.mark.parametrize('dalam_form', [False, True])
def test_mulai_tunggal_mode_native_dan_izin_tidak_dicentang(dalam_form):
    target = assistant_inline.tujuan_anak(7, 'latihan')
    panel = assistant_components.panel_konteks(
        target, SimpleNamespace(jenis='anak', versi='v', kategori='ringkasan_netral'),
        sumber={'nama': 'Anak <Sintetis>', 'label': 'Ringkasan anak', 'level': 'P3'},
        dalam_form=dalam_form,
    )
    if dalam_form:
        panel = assistant_components.hubungkan_form(panel, 'form-latihan')
    elemen = StrukturPanel(panel).elemen
    mulai = [a for t, a, _ in elemen if t == 'button' and a.get('formaction') == '/pendamping/inline/mulai']
    assert len(mulai) == 1 and 'name' not in mulai[0]
    cek = next(a for t, a, _ in elemen if a.get('name') == 'setuju_konteks')
    assert 'checked' not in cek and 'required' not in cek
    mode = [(a, atas) for t, a, atas in elemen if t == 'select' and a.get('name') == 'mode_chat']
    assert len(mode) == 1
    assert any(t == 'details' and a.get('class') == 'pendamping-pengaturan' for t, a in mode[0][1])
    if dalam_form:
        assert mode[0][0]['form'] == cek['form'] == mulai[0]['form'] == 'form-latihan'
    assert '<option value="aktif" selected>' in panel
    assert '<option value="tanpa_memori">' in panel
    assert 'Riwayat tetap disimpan pada kedua pilihan.' in panel
    assert 'Mulai tanpa memori' not in panel and 'Konteks belum diizinkan' not in panel
    assert 'Anak &lt;Sintetis&gt;' in panel and 'P3' not in panel.split('</header>')[0]
    assert 'DeepSeek' in panel and 'Nama, jawaban, dan catatan anak tidak ikut dikirim' in panel


def test_header_akun_satu_kelompok_peran_nama_dan_tujuan_tetap():
    for peran, tujuan in [('guru', '/guru'), ('admin', '/admin')]:
        markup = teacher_pages._topbar_stitch('Akun <Sintetis>', peran)
        elemen = StrukturPanel(markup).elemen
        badge = next(atas for t, a, atas in elemen if a.get('class', '').startswith('badge-peran'))
        assert any(t == 'summary' for t, _ in badge)
        assert markup.count('<summary>') == 1
        assert 'Akun &lt;Sintetis&gt;' in markup
        assert f'href="{tujuan}"' in markup
        assert markup.count('action="/keluar"') == 1


@pytest.fixture()
def db(tmp_path):
    jalur = tmp_path / 'workspace.db'
    database.siapkan(jalur)
    with database.buka(jalur) as kon:
        anak = database.tambah_siswa(kon, 'Anak Sintetis', 'P3', pemilik='guru')
        sesi = database.buat_sesi(kon, anak, seed=42, jumlah_soal=2)
        kon.execute('UPDATE sesi SET topik=? WHERE id=?', ('gabungan:statistika,geometri-datar', sesi))
        share_links.buat(kon, sesi)
        yield kon, anak, sesi


def test_kartu_sesi_status_dekat_judul_topik_dilipat_dan_aksi_terkelompok(db):
    kon, anak, sesi = db
    sebelum = tuple(kon.iterdump())
    siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (anak,)).fetchone()
    markup = teacher_pages.halaman_anak(
        kon, siswa, pengguna='guru', query='section=riwayat'
    ).decode().split('</style>')[-1]
    elemen = StrukturPanel(markup).elemen
    status = next(atas for t, a, atas in elemen if a.get('class', '').startswith('badge-direview'))
    assert any(a.get('class') == 'riwayat-tinjauan-st' for _, a in status)
    assert '<small>Statistika &middot; Geometri Datar</small>' in markup
    kelola_utama = next(a for t, a, _ in elemen if a.get('class') == 'riwayat-kelola-st')
    kelola_tautan = next(a for t, a, _ in elemen if a.get('class') == 'tautan-sesi-opsi')
    assert 'open' not in kelola_utama and 'open' not in kelola_tautan
    for akhiran in ['bagikan', 'cabut-tautan']:
        form = next(atas for t, a, atas in elemen if a.get('action') == f'/sesi/{sesi}/{akhiran}')
        assert any(a.get('class') == 'riwayat-kelola-st' for _, a in form)
    assert '<span>Cabut tautan</span>' in markup
    assert 'Membuat tautan baru akan menonaktifkan tautan sebelumnya.' in markup
    assert 'Mencabut tautan menutup akses melalui tautan itu.' in markup
    assert tuple(kon.iterdump()) == sebelum
