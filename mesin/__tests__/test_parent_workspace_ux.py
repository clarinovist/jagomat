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
    mode = [(a, atas) for t, a, atas in elemen if t == 'input' and a.get('name') == 'mode_chat']
    assert len(mode) == 1
    assert mode[0][0]['type'] == 'hidden' and mode[0][0]['value'] == 'tanpa_memori'
    if dalam_form:
        assert mode[0][0]['form'] == cek['form'] == mulai[0]['form'] == 'form-latihan'
    assert not any(t == 'select' and a.get('name') == 'mode_chat' for t, a, _ in elemen)
    assert 'Preferensi lintas percakapan tidak digunakan.' in panel
    assert 'Tidak ada pesan yang dikirim otomatis.' in panel
    assert 'Mulai tanpa memori' not in panel and 'Konteks belum diizinkan' not in panel
    assert 'Anak &lt;Sintetis&gt;' in panel and 'P3' not in panel.split('</header>')[0]
    assert 'DeepSeek' in panel and 'Ringkasan otomatis ini tidak memuat nama, jawaban, atau catatan anak' in panel
    assert 'maksimal tiga sesi perlu ditinjau (alias, jumlah soal, urutan tinjauan)' in panel


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
    assert any(a.get('class') == 'riwayat-status-st' for _, a in status)
    assert 'Gabungan 2 topik' in markup
    assert markup.count(f'href="/sesi/{sesi}"') == 1
    assert 'riwayat-kelola-st' not in markup
    halaman_sesi = teacher_pages.halaman_sesi_stitch(kon, sesi, pengguna='guru').decode()
    for akhiran in ['bagikan', 'cabut-tautan']:
        assert f'action="/sesi/{sesi}/{akhiran}"' in halaman_sesi
    assert 'Membuat tautan baru akan menonaktifkan tautan sebelumnya.' in halaman_sesi
    assert tuple(kon.iterdump()) == sebelum
