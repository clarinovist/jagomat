"""Komponen admin mengikuti acuan bersama: tombol sekunder, pil filter, tab, jejak, menu akun."""
from pathlib import Path
import re
from types import SimpleNamespace as NS

import admin_antrean
import admin_antrean_pages as AP
import admin_daftar_pages as D
import admin_komponen as K
import admin_launch_pages as LP
import admin_operations
import admin_pages as P
import admin_research_pages as RP
import admin_style
import design_roles as R
import design_tokens as T
import product_analytics as PA
from admin_history_store import HalamanRiwayat
from test_admin_launch_pages import _config, _form_pembayaran, _kpi, _laporan, _ringkas, _rows
from test_admin_pages import _keluarga, _riwayat_contoh, _ringkasan, _siswa
from test_admin_research_markup import _item

ROOT = Path(__file__).resolve().parent.parent
MODUL_ADMIN = sorted(ROOT.glob("admin_*.py")) + [ROOT / "ai_pages.py", ROOT / "sensor_pages.py"]
TOMBOL_CARI = re.compile(r'<button\b([^>]*)>\s*(Cari|Terapkan|Saring[^<]*)\s*</button>')


def _aturan(selector):
    cocok = re.search(r'(?:^|\n)' + re.escape(selector) + r'\s*\{([^}]+)\}', admin_style.GAYA_ADMIN)
    assert cocok, selector
    return cocok.group(1)


def _halaman_dengan_pencarian():
    kosong = HalamanRiwayat((), 0, 1, 25, 1)
    riset = {'ringkasan': dict(draf=1, final=0, perlu_redaksi=0, mendekati_retensi=0),
             'daftar': NS(item=[_item('R01')], total=1, per_halaman=20, halaman=1)}
    return {
        'keluarga': P.render_keluarga(_keluarga(), csrf='sintetis'),
        'siswa': P.render_siswa(_siswa(), _keluarga().item, csrf='sintetis'),
        'langganan': LP.daftar_langganan(_rows(), 2, halaman=1, cari='', csrf='c'),
        'kpi': _kpi(_laporan(PA.Metrik('manfaat', 8, 10, 70, 'Memenuhi target', False, 10, 12))),
        'riwayat': P.render_riwayat(_riwayat_contoh(), filter_data={}),
        'riwayat-ai': P.render_riwayat_ai(kosong, filter_data={}),
        'riwayat-batch': P.render_audit_batch(kosong, filter_data={}),
        'riset': RP.dashboard(riset, csrf='c', token_buat='t', token_ekspor={'csv': 'c', 'json': 'j'}),
    }


def test_tombol_cari_terapkan_saring_selalu_sekunder_di_semua_halaman():
    for nama, isi in _halaman_dengan_pencarian().items():
        tombol = TOMBOL_CARI.findall(isi)
        assert tombol, nama
        for atribut, label in tombol:
            assert 'admin-tombol-sekunder' in atribut, (nama, label, atribut)


def test_sumber_admin_tidak_memakai_tombol_utama_untuk_pencarian():
    """Pemindai sumber menangkap halaman tanpa fixture render (mis. bulk pilih)."""
    for path in MODUL_ADMIN:
        teks = path.read_text()
        assert not re.search(r'class="admin-tombol">\s*(?:Cari|Terapkan|Saring)', teks), path.name
        assert not re.search(r'"Saring [^"]*",\s*"admin-tombol"', teks), path.name


def test_tombol_sekunder_mengikuti_acuan_teal_terang_dan_gelap():
    sekunder = _aturan('.admin-tautan, .admin-tombol-sekunder, .admin-antrean-cta, .admin-pager button')
    assert 'color: ' + T.ADMIN_AKSEN in sekunder
    assert 'border-color: ' + T.ADMIN_AKSEN in sekunder
    assert 'background: ' + T.ADMIN_PERMUKAAN in sekunder
    hover = _aturan('.admin-tautan:hover, .admin-tombol-sekunder:hover, .admin-antrean-cta:hover, .admin-pager button:hover')
    assert 'background: ' + T.ADMIN_AKSEN_LATAR in hover
    assert 'color: ' + T.ADMIN_AKSEN_TEKS in hover
    for tema in ('admin_cerah', 'admin_gelap'):
        peta = R.peta_peran(tema)
        for peran in ('aksi_sekunder', 'batas_aksi_sekunder', 'pil_teks', 'pil_aktif_teks', 'tab_aktif'):
            assert peran in peta, (tema, peran)


def test_chip_admin_adalah_pil_filter_yang_sama_dengan_keluarga():
    assert T.ADMIN_BORDER_PIL_CERAH == T.ANAK_BORDER_PIL
    pasif = _aturan('.admin-chip')
    assert 'min-height: ' + T.TARGET_SENTUH in pasif
    assert 'border-color: ' + T.ADMIN_BORDER_PIL in pasif
    assert 'color: ' + T.ADMIN_REDUP in pasif
    assert 'border-radius: ' + T.RADIUS_PIL in pasif
    aktif = _aturan('.admin-chip[aria-current="true"]')
    assert 'border: 2px solid ' + T.ADMIN_AKSEN in aktif
    assert 'background: ' + T.ADMIN_AKSEN_LATAR in aktif
    assert 'font-weight: 700' in aktif
    assert 'border-color: ' + T.ADMIN_AKSEN in _aturan('.admin-chip:hover')


def test_tab_admin_bergaris_bawah_dan_navigasi_bagian_bukan_tab():
    tab = _aturan('.admin-tab')
    assert 'border-bottom: 3px solid transparent' in tab
    assert T.RADIUS_PIL not in tab
    assert 'min-height: ' + T.TINGGI_KONTROL in tab
    aktif = _aturan('.admin-tab[aria-current="page"]')
    assert 'border-bottom-color: ' + T.ADMIN_AKSEN in aktif and 'color: ' + T.ADMIN_AKSEN in aktif
    assert 'border-bottom: 1px solid ' + T.ADMIN_BORDER in _aturan('.admin-tab-baris')
    operasional = LP.operasional(_ringkas(), _form_pembayaran(), LP.formulir_dukungan('c', 't', _config()))
    assert '<nav class="admin-navigasi-bagian" aria-label="Bagian operasional">' in operasional
    assert 'admin-tab' not in operasional


def test_menu_akun_admin_berpola_peran_nama_dan_chevron():
    isi = P.halaman_admin('ringkasan', '', pengguna='Admin <x>').decode()
    summary = re.search(r'<details class="menu-pengguna"><summary>(.*?)</summary>', isi, re.S).group(1)
    assert '<span class="admin-peran">Pengelola</span>' in summary
    assert '<span class="admin-nama">Admin &lt;x&gt;</span>' in summary
    assert 'class="admin-panah"' in summary and 'aria-hidden="true"' in summary
    assert 'admin-badge' not in summary
    assert 'list-style: none' in _aturan('.menu-pengguna summary')
    assert 'display: none' in _aturan('.menu-pengguna summary::-webkit-details-marker')


def test_badge_normal_satu_nada_di_daftar_dan_detail():
    assert D.pill_kondisi(()) == K.badge_status(()) == '<span class="admin-badge">Normal</span>'


def test_tautan_kembali_berupa_jejak_teks_dan_langganan_punya_kembali():
    for path in MODUL_ADMIN:
        teks = path.read_text()
        assert not re.search(r'class="admin-tautan"[^>]*>←', teks), path.name
    jejak = _aturan('.admin-jejak a')
    assert 'min-height: ' + T.TARGET_SENTUH in jejak and 'color: ' + T.ADMIN_AKSEN in jejak
    assert '<p class="admin-jejak"><a href="/admin?section=keluarga">← Kembali ke daftar keluarga</a></p>' \
        in P.form_buat_keluarga('c', 't')
    detail = LP.detail_langganan(dict(alias='Demo', akses=NS(status='aktif', akhir=1792900000),
                                      jumlah_profil=1, promo_tersisa=0, invoices=[]), {})
    assert detail.startswith('<p class="admin-jejak"><a href="/admin?section=langganan">')


def test_umur_antrean_tak_tercatat_tanpa_tanda_visual_yatim():
    item = AP.ItemAntrean('tinjau', 'Contoh', 'Sintetis.', '/admin?section=siswa', 'Tinjau siswa')
    assert AP._umur(item) == '<span class="admin-sr">Umur tidak tersedia</span>'


def test_cta_backup_spesifik_dan_ringkasan_tanpa_duplikat_buka_operasional(monkeypatch):
    for label in ('Belum terverifikasi', 'Bukti backup tidak valid'):
        monkeypatch.setattr(admin_operations, 'bukti_backup', lambda s, label=label: (label, None))
        (item,), _, _ = admin_antrean._item_backup(0.0)
        assert item.cta == 'Periksa backup'
        assert item.jalur == '/admin?section=operasional#kesiapan'
    antrean = AP.AntreanAdmin(item=(item,), total=1)
    isi = P.render_ringkasan(_ringkasan(), antrean=antrean)
    assert isi.count('>Buka operasional') == 1
    assert '>Periksa backup<' in isi


def test_field_sandi_konfirmasi_selebar_kolom_baca_yang_sama():
    assert 'max-width: ' + T.LEBAR_KONTEN in _aturan('.admin-kartu label:has(input[name="reauth"])')
    for daftar, isi in re.findall(r'([^{}]+)\{([^{}]+)\}', admin_style.GAYA_ADMIN):
        if 'label' in daftar or 'form[action' in daftar:
            lebar = re.findall(r'max-width:\s*([^;]+)', isi)
            assert all(x.strip() == T.LEBAR_KONTEN for x in lebar), daftar
    assert 'admin-sempit' not in admin_style.GAYA_ADMIN
    assert 'admin-sempit' not in (ROOT / 'admin_pages.py').read_text()
    bulk = (ROOT / 'admin_bulk_http.py').read_text()
    assert bulk.count('<form class="admin-form-pendek" method="post" action="/admin/bulk/pilih">') == 4


def test_status_tabel_ai_tidak_menyempit_di_layar_hp():
    assert 'min-width: 12rem' in _aturan('.admin-ai-tabel .admin-badge')


def test_pager_pencarian_langganan_sekunder_seperti_pager_lain():
    pager = LP._pager_langganan(2, 60, 'demo', 'c')
    assert pager.count('<button class="admin-tombol admin-tombol-sekunder" type="submit">') == 2
    assert 'class="admin-tombol" type="submit"' not in pager


def test_kartu_batch_massal_hanya_satu_aksi_utama():
    item = NS(item_id='item_demo', operasi_id='op_demo', target_id='akun_demo', target_revisi=1,
              alias_valid='Demo', status='succeeded', hasil_id='akun_demo', credential_status='unconfirmed')
    batch = NS(batch_id='batch_demo', aksi='account_password_reset', target_peran='guru', status='partial',
               item=(item,), draft_tersedia=True, boleh_proses=True, kelompok_aktif_id=None)
    isi = P.render_bulk_batch(batch, (NS(item_id='item_demo', credential_sekali='sandi-sintetis'),), 'c',
                              {'process': 'p', 'stop': 's', 'handover': 'h'}, {})
    assert isi.count('<form method="post" action="/admin/bulk/') == 3
    assert isi.count('<button class="admin-tombol" type="submit">') == 1
    assert '<button class="admin-tombol" type="submit">Proses kelompok berikutnya</button>' in isi
    assert isi.count('<button class="admin-tombol admin-tombol-sekunder" type="submit">') == 2
