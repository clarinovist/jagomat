"""Kontrak panel samping Pendamping pada permukaan orang tua."""
from pathlib import Path
import re
import sys
from dataclasses import replace
from html.parser import HTMLParser
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_browser
import assistant_components
import assistant_inline
import style_stitch
import teacher_pages


def test_pembuka_tunggal_adalah_kontrol_panel_kanan_atas():
    target = assistant_inline.tujuan_anak(7, "latihan")
    markup = assistant_components.tombol_buka(target, dalam_form=True)
    assert 'aria-label="Pendamping"' in markup
    assert 'class="pendamping-pemicu"' in markup
    assert "Bahas dengan Pendamping" not in markup
    assert 'formaction="/pendamping/inline/buka"' in markup
    assert 'aria-expanded="false"' in markup
    atribut = StrukturPanel(markup).elemen[0][1]
    assert atribut['data-pendamping-host'] == 'anak'
    assert atribut['data-pendamping-host-id'] == '7'
    assert atribut['data-pendamping-posisi'] == 'latihan'
    assert atribut['data-pendamping-resource-id'] == '7'


def test_fragmen_panel_memakai_header_ringkas_dan_konteks_terlihat():
    target = assistant_inline.tujuan_anak(7, "rencana")
    markup = assistant_components.panel_persetujuan(
        target,
        sumber={"label": "Anak Sintetis", "level": "Variasi B"},
    )
    assert 'class="pendamping-inline pendamping-panel-kanan"' in markup
    assert '<h2' in markup and '>Pendamping</h2>' in markup
    assert 'Anak Sintetis · Membahas rencana belajar' in markup
    assert 'Konteks belum diizinkan' not in markup
    assert 'data-tampilan="ringkas"' in markup
    assert 'aria-label="Tutup Pendamping"' in markup
    assert '<details open><summary>Bantuan Pendamping</summary>' not in markup


def test_css_panel_memotong_header_pada_radius_dan_mobile_penuh():
    css = style_stitch.GAYA_STITCH
    assert '.pendamping-panel-kanan' in css
    assert f'border-radius: {style_stitch.T.RADIUS_KARTU_BESAR}' in css
    assert 'overflow: clip' in css
    assert 'grid-template-columns: minmax(0, 1fr) 400px' in css
    assert '@media (max-width: 59.9375rem)' in css
    assert 'position: fixed' in css


def test_halaman_profil_hanya_satu_pemicu_dan_bukan_di_bawah_cta():
    import sqlite3
    import tempfile
    import database
    with tempfile.TemporaryDirectory() as direktori:
        path = Path(direktori) / "uji.db"
        database.siapkan(path)
        with database.buka(path) as kon:
            sid = database.tambah_siswa(kon, "Anak Sintetis", "P4", pemilik="guru")
            siswa = kon.execute("SELECT * FROM siswa WHERE id=?", (sid,)).fetchone()
            markup = teacher_pages.halaman_anak(kon, siswa, pengguna="guru").decode()
    assert markup.count('class="pendamping-pemicu"') == 2
    assert markup.index('class="pendamping-pemicu"') > markup.index('Buat sesi baru')
    assert 'class="profil-assistant-st"><span class="pendamping-buka-inline"' in markup
    assert '.panel-latihan-st:not(:first-of-type) .pendamping-buka-inline' not in markup
    assert "Bahas dengan Pendamping" not in markup


class StrukturPanel(HTMLParser):
    """Baca hubungan DOM tanpa memperbaiki markup bersarang seperti browser."""

    def __init__(self, markup):
        super().__init__()
        self.tumpukan = []
        self.elemen = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        atribut = dict(attrs)
        self.elemen.append((tag, atribut, tuple(self.tumpukan)))
        if tag not in {'input', 'img', 'br', 'hr', 'meta', 'link', 'path'}:
            self.tumpukan.append((tag, atribut))

    def handle_endtag(self, tag):
        for i in range(len(self.tumpukan) - 1, -1, -1):
            if self.tumpukan[i][0] == tag:
                del self.tumpukan[i:]
                break


@pytest.mark.parametrize('target', [
    assistant_inline.tujuan_anak(7, 'latihan'),
    assistant_inline.tujuan_anak(7, 'rencana'),
    assistant_inline.tujuan_sesi(42),
    assistant_inline.tujuan_sesi(42, nomor=3),
])
def test_metadata_binding_panel_escaped_dan_terikat_resource(target):
    target = replace(target, jenis_host='host"<&', host_id='id"<&', resource_id='resource"<&')
    markup = assistant_components._panel(target, 'Judul', '', sumber={}, chat_id='chat"<&')
    atribut = StrukturPanel(markup).elemen[0][1]
    assert atribut['data-pendamping-host'] == target.jenis_host
    assert atribut['data-pendamping-host-id'] == target.host_id
    assert atribut['data-pendamping-posisi'] == target.posisi
    assert atribut['data-pendamping-resource'] == target.jenis_resource
    assert atribut['data-pendamping-resource-id'] == target.resource_id
    assert atribut['data-pendamping-chat'] == 'chat"<&'
    assert 'chat&quot;&lt;&amp;' in markup
    assert all('jawaban' not in nama and 'draf' not in nama for nama in atribut)


def test_header_rincian_terlihat_status_stale_jujur_dan_tutup_tidak_ganda():
    chat = SimpleNamespace(id='chat_' + 'a' * 32, mode_memori='aktif')
    markup = assistant_components.panel_chat(
        assistant_inline.tujuan_sesi(42, nomor=3), chat, (), (),
        sumber={'label': 'Soal 3'}, hanya_baca=True,
    )
    header = markup.split('</header>', 1)[0]
    assert 'Informasi belajar berubah · hanya baca' in header
    assert 'Konteks disetujui' not in header
    assert '<summary>Tentang bantuan AI</summary>' in markup
    assert '<details' not in header
    assert 'data-tampilan="percakapan"' in markup
    assert 'class="pendamping-tutup-desktop" aria-hidden="true">×</span>' in header
    assert 'class="pendamping-tutup-hp" aria-hidden="true">← Kembali</span>' in header
    assert header.count('×') == 1
    assert 'aria-label="Tutup Pendamping"' in header
    assert 'autofocus' not in markup


def test_pemicu_tersembunyi_saat_panel_terbuka_tidak_ditampilkan_override_profil():
    css = style_stitch.GAYA_STITCH
    selector = '.pendamping-editorial-st:has(> .pendamping-panel-kanan:not([hidden])) .pendamping-buka-inline'
    assert selector + ' { display: none !important; }' in css


def test_pemicu_tidak_tertutup_stacking_topbar_dan_hp_di_atas_keduanya():
    css = style_stitch.GAYA_STITCH
    topbar = re.search(r'^\.st-topbar \{([^}]*)\}', css, re.M).group(1)
    pemicu = re.search(r'^\.pendamping-editorial-st \.pendamping-pemicu \{([^}]*)\}', css, re.M).group(1)
    mobile = css.split('@media (max-width: 59.9375rem)', 1)[1]
    panel = re.search(r'\.pendamping-panel-kanan \{([^}]*)\}', mobile).group(1)
    lapis = lambda aturan: int(re.search(r'z-index:\s*(\d+)', aturan).group(1))
    assert lapis(topbar) < lapis(pemicu) < lapis(panel)
    assert 'position: absolute' in pemicu and 'position: fixed' not in pemicu


def test_native_panel_latihan_di_samping_workspace_tanpa_melepas_form(tmp_path):
    import database
    path = tmp_path / 'panel.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        sid = database.tambah_siswa(kon, 'Anak Sintetis', 'P4', pemilik='guru')
        siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (sid,)).fetchone()
        panel = assistant_components.panel_persetujuan(
            assistant_inline.tujuan_anak(sid, 'latihan'), sumber={}, dalam_form=True,
        )
        markup = teacher_pages.halaman_anak(kon, siswa, pengguna='guru', bantuan_latihan=panel).decode()
    struktur = StrukturPanel(markup)
    _, _, leluhur = next(e for e in struktur.elemen if e[1].get('id') == 'bantuan-latihan')
    assert 'pendamping-editorial-st' in leluhur[-1][1].get('class', '')
    assert not any(tag == 'form' for tag, _ in leluhur)
    kontrol = [a for tag, a, atas in struktur.elemen if tag in {'input', 'button', 'select', 'textarea'}
               and any(a.get('id') == 'bantuan-latihan' for _, a in atas)]
    assert kontrol and all(a.get('form') == f'form-latihan-manual-{sid}' for a in kontrol)
    assert any(t == 'form' and a.get('id') == f'form-latihan-manual-{sid}' for t, a, _ in struktur.elemen)
    for nama in ('inline_host', 'inline_host_id', 'inline_posisi'):
        target_form = [a for t, a, leluhur in struktur.elemen if a.get('name') == nama
                       and (a.get('form') == f'form-latihan-manual-{sid}' or
                            any(atas.get('id') == f'form-latihan-manual-{sid}' for _, atas in leluhur))]
        assert len(target_form) == 1, nama


def test_entry_sesi_dibatalkan_tetap_punya_form_yang_ada(tmp_path):
    import database
    path = tmp_path / 'sesi.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        sid = database.tambah_siswa(kon, 'Anak Sintetis', 'P3', pemilik='guru')
        sesi = database.buat_sesi(kon, sid, seed=42, jumlah_soal=1)
        database.tandai_selesai(kon, sesi)
        database.batalkan_sesi(kon, sesi, 'Pembatalan sintetis')
        markup = teacher_pages.halaman_sesi_stitch(kon, sesi, pengguna='guru').decode()
    struktur = StrukturPanel(markup)
    tombol = [e for e in struktur.elemen if e[1].get('class') == 'pendamping-pemicu']
    assert len(tombol) == 1
    _, atribut, leluhur = tombol[0]
    ids_form = {a.get('id') for tag, a, _ in struktur.elemen if tag == 'form'}
    assert any(tag == 'form' for tag, _ in leluhur) or atribut.get('form') in ids_form


def test_association_tidak_mengubah_form_mandiri_dan_tetap_escape():
    markup = '<input name="chat" value="aman&amp;&quot;"><textarea name="pesan">&lt;soal&gt; &amp; &#34;</textarea>'
    mandiri = '<form method="post"><input name="lain"><button>Mandiri</button></form>'
    hasil = assistant_components.hubungkan_form(markup + mandiri, 'form"<&')
    assert mandiri in hasil
    assert 'form="form&quot;&lt;&amp;"' in hasil
    assert '&lt;soal&gt; &amp; &#34;' in hasil
    assert 'value="aman&amp;&quot;"' in hasil


def test_enhancement_panel_diizinkan_tanpa_storage_atau_streaming():
    skrip = assistant_browser.SKRIP_CHAT
    assert "var aksiPanel" in skrip
    assert "X-Pendamping-Panel" in skrip
    assert "form.submit()" not in skrip
    assert "panel.replaceWith(baru)" in skrip
    assert "localStorage" not in skrip
    assert "sessionStorage" not in skrip
    assert "EventSource" not in skrip
    assert "WebSocket" not in skrip
    assert re.fullmatch(r"[A-Za-z0-9+/=]+", assistant_browser.HASH_CSP)
