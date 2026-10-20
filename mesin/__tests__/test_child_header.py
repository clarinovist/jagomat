"""Kontrak header anak terisolasi; semua identitas/DB pengujian sintetis."""
import re
from types import SimpleNamespace

import pytest

import child_header as H
import profile_workspace as P
import teacher_shell as S
import teacher_pages
import assistant_entitlement_runtime
from test_concise_ui import db
from test_assistant_panel_shell import StrukturPanel


@pytest.mark.parametrize('asal,hasil', [
    ('keluarga-a', 'Keluarga A'), ('keluarga-baru', 'Keluarga Baru'),
    ('Budi Santoso', 'Budi Santoso'), ('Bu-ANI', 'Bu-ANI'),
    ('andi', 'andi'), ('', 'Menu akun'),
])
def test_format_nama_tidak_mengubah_identitas_login(asal, hasil):
    assert H.nama_akun(asal) == hasil


def test_identitas_sibling_inisial_dan_escape():
    h = H.identitas({'nama':'<Anak & Uji>'}, kelas_sekolah=5, kembali='/guru')
    assert '<h1 class="st" id="judul-profil">&lt;Anak &amp; Uji&gt;</h1><span class="anak-meta-st">Kelas 5</span>' in h
    assert 'class="anak-avatar-st" aria-hidden="true">&lt;</span>' in h
    assert all(teks not in h for teks in ('st-badge','selesai','RUANG BELAJAR','profil-aksi-kepala-st'))
    assert '<svg aria-hidden="true" focusable="false"' in h
    assert 'anak-meta-st' not in H.identitas({'nama':'Contoh'})


def test_shell_shared_dan_admin_tidak_memakai_varian_baru():
    biasa = S._topbar_stitch('keluarga-a', 'guru')
    ringkas = S._topbar_stitch('keluarga-a', 'guru', ringkas=True)
    assert 'class="identitas-akun-st"' in biasa and '>keluarga-a</span>' in biasa
    assert 'class="identitas-akun-st"' not in ringkas and '>Keluarga A</span>' in ringkas
    assert 'Orang Tua / Guru' not in ringkas.split('</summary>')[0]
    assert 'Orang Tua / Guru' in ringkas.split('class="menu-isi"')[1]
    assert 'keluarga-&lt;uji&gt;' not in S._topbar_stitch('keluarga-<uji>', 'guru', ringkas=True)
    assert 'Keluarga &lt;Uji&gt;' in S._topbar_stitch('keluarga-<uji>', 'guru', ringkas=True)
    admin = P.bingkai(dict(id=1,nama='Contoh',pemilik='keluarga-a'), 'rencana', 0, '', peran='admin')
    assert 'anak-avatar-st' not in admin and 'href="/admin"' in admin
    assert 'anak-header-st' not in S._halaman_stitch('Uji', '', kelas_bungkus='guru-beranda-st').decode()


@pytest.mark.parametrize('section', ['rencana','latihan','riwayat','perkembangan'])
def test_semua_tab_header_tunggal_readonly_dan_form_native(db, monkeypatch, section):
    monkeypatch.setattr(assistant_entitlement_runtime, 'status_pengguna', lambda _: SimpleNamespace(status='aktif'))
    kon, sid, _ = db
    siswa = kon.execute('SELECT * FROM siswa WHERE id=?',(sid,)).fetchone()
    awal = tuple(kon.iterdump())
    h = teacher_pages.halaman_anak(kon, siswa, pengguna='guru', query='section='+section).decode()
    assert tuple(kon.iterdump()) == awal
    badan = h.split('<body',1)[1]
    assert badan.count('class="pendamping-pemicu"') == 1
    assert 'anak-header-st' in badan and 'RUANG BELAJAR ANAK' not in badan
    struktur = StrukturPanel(badan)
    _, tombol, leluhur = next(e for e in struktur.elemen if e[1].get('class') == 'pendamping-pemicu')
    assert any(a.get('class') == 'st-topbar' for _, a in leluhur)
    assert tombol['aria-label'] == 'Tanya Pendamping'
    assert tombol['formaction'] == '/pendamping/inline/buka'
    if section == 'latihan':
        form_id = f'form-latihan-manual-{sid}'
        assert tombol['form'] == form_id
        assert not any(t == 'form' for t, _ in leluhur)
        for nama in ('inline_host','inline_host_id','inline_posisi'):
            champs = [a for t,a,_ in struktur.elemen if t=='input' and a.get('name')==nama]
            assert len(champs)==1 and champs[0]['form']==form_id
    else:
        assert any(t == 'form' and a.get('method')=='post' for t,a in leluhur)
    nav = re.search(r'<nav class="profil-tabs-st".*?</nav>', badan).group()
    assert nav.count('aria-current="page"')==1
    assert f'?section={section}" aria-current="page"' in nav
    assert 'aria-label="Bagian profil anak"' in nav


def test_status_akses_pendamping_tetap_terbaca():
    import assistant_inline
    h = H.tombol_pendamping(assistant_inline.tujuan_anak(1), status_akses=SimpleNamespace(status='kuota_habis'))
    assert 'aria-label="Tanya Pendamping — kuota balasan habis"' in h
    assert 'pendamping-lencana-akses' in h


def test_css_header_scoped_sticky_dan_target_sentuh():
    css = H.GAYA_HEADER_ANAK
    assert 'position: sticky; top: 0' in css
    assert 'padding-top: 0; overflow: visible' in css
    assert 'height: 56px' in css and 'height: 48px' in css
    assert 'height: 44px' in css and 'font-weight: 700' in css
    assert '@media (max-width: 36rem)' in css and '@media (max-width: 24rem)' in css
    assert 'clip-path: inset(50%)' not in css
    assert 'position: fixed; top: auto' in css
    assert 'display: none' not in css and 'display:none' not in css
    assert 'outline: 3px solid' in css
    assert '--anak-identitas' in css and 'animation-range: exit 99% exit 100%' in css
    assert 'RUANG BELAJAR ANAK' not in P.bagian_identitas({'nama':'Contoh','pemilik':'guru'})
