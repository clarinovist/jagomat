"""Kontrak token UI: sumber tunggal, bukan kebetulan nilai rendered sama."""
import ast
import importlib
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import design_tokens as T
from test_parent_editorial import db  # noqa: F401 — fixture sintetis existing

ROOT = Path(__file__).resolve().parent.parent


def _definisi_gaya(sumber):
    for node in ast.walk(ast.parse(sumber)):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id.startswith(('GAYA', 'CSS')) for t in node.targets):
            continue
        if isinstance(node.value, ast.JoinedStr) or (
            isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        ):
            yield node.value


def test_warna_css_bersumber_token_bukan_literal():
    """Komentar dikecualikan; semua assignment CSS baru ikut diperiksa."""
    temuan = []
    for path in sorted(ROOT.glob('*.py')):
        if path.name == 'design_tokens.py':
            continue
        for node in _definisi_gaya(path.read_text()):
            teks = node.value if isinstance(node, ast.Constant) else ''.join(
                v.value if isinstance(v, ast.Constant) else '<token>' for v in node.values
            )
            teks = re.sub(r'/\*.*?\*/', '', teks, flags=re.S)
            literal = re.findall(r'#[0-9a-fA-F]{3,8}\b|rgba?\(|%23[0-9a-fA-F]{3,8}\b', teks)
            if literal:
                temuan.append((path.name, node.lineno, literal))
    assert not temuan, temuan


@pytest.mark.parametrize('modul,konstanta,token,selektor,deklarasi', [
    ('teacher_style', 'GAYA_GURU', 'BAYANGAN_KARTU_GURU', '.kartu', 'box-shadow: __uji__'),
    ('style_stitch', 'GAYA_STITCH', 'LATAR_REVIEW', '.st-badge.review', 'background: __uji__'),
    ('style_stitch', 'CSS_SESI', 'BAYANGAN_FOKUS', '.koreksi-textarea-st:focus', 'box-shadow: __uji__'),
    ('screen_style', 'GAYA_LAYAR', 'GARIS_ISIAN', '.garis', 'border-bottom: 2px solid __uji__'),
    ('print_style', 'GAYA_CETAK', 'CETAK_TINTA', '.soal', 'border: 1.2pt solid __uji__'),
    ('assistant_style', 'GAYA_PENDAMPING', 'UKURAN_BAGIAN_DEWASA', '.pendamping-halaman h2', 'font-size:__uji__'),
    ('admin_style', 'GAYA_ADMIN', 'UKURAN_TEKS_META', '.admin-konteks', 'font-size: __uji__'),
    ('report_dashboard', 'GAYA_LAPORAN', 'TEBAL_GARIS', '.laporan-editorial-st .laporan-metrik .stat', 'border:__uji__ solid'),
    ('subscription_style', 'GAYA_LANGGANAN', 'SP_4', '.langganan-panel fieldset', 'margin:__uji__ 0'),
])
def test_perubahan_token_mencapai_aturan_yang_tepat(modul, konstanta, token, selektor, deklarasi):
    """Evaluasi CSS di namespace terisolasi, tanpa reload/global monkeypatch."""
    module = importlib.import_module(modul)
    tree = ast.parse((ROOT / (modul + '.py')).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == konstanta for t in n.targets))
    nilai = dict(vars(T), **{token: '__uji__'})
    lingkup = dict(vars(module), T=SimpleNamespace(**nilai))
    css = eval(compile(ast.Expression(node.value), modul, 'eval'), lingkup)
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    aturan = [isi for daftar, isi in re.findall(r'([^{}]+)\{([^{}]+)\}', css)
              if selektor in [s.strip() for s in daftar.split(',')]]
    assert aturan, selektor
    assert any(deklarasi in isi for isi in aturan)


def test_breakpoint_bersama_tidak_terpisah_dari_token():
    for nama in ('teacher_style', 'style_stitch', 'assistant_style', 'profile_workspace', 'report_dashboard', 'mastery_report'):
        sumber = (ROOT / (nama + '.py')).read_text()
        sumber = re.sub(r'/\*.*?\*/', '', sumber, flags=re.S)
        assert not re.search(r'(?:min|max)-width:\s*(?:30|46|48|64)rem\)', sumber), nama


def test_checkout_memakai_satu_stylesheet_tanpa_logika_bayar():
    from subscription_style import GAYA_LANGGANAN
    import subscription_pages
    import subscription_produksi_pages

    assert subscription_pages.GAYA is GAYA_LANGGANAN
    assert subscription_produksi_pages.GAYA is GAYA_LANGGANAN
    tree = ast.parse((ROOT / 'subscription_style.py').read_text())
    assert not any(isinstance(n, (ast.FunctionDef, ast.ClassDef)) for n in tree.body)


def test_akun_pakai_kelas_bukan_style_inline(db):
    import account_pages
    from test_parent_editorial import Markup

    kon = db[0]
    for section in ('akun', 'siswa', 'akun-murid'):
        isi = account_pages.halaman_akun(kon, pengguna='pendamping-uji', section=section).decode()
        markup = Markup(isi.split('<div class="layout-samping">', 1)[1])
        # Hanya isi akun; topbar/brand berada di bingkai bersama.
        assert not [(tag, a) for tag, a, _ in markup.elemen
                    if tag in ('form', 'label', 'input', 'p') and 'style' in a]
    assert 'class="akun-form-aksi akun-form-sandi"' in isi
    assert 'class="akun-pulihkan"' in isi


def test_nama_paket_landing_mengikuti_brand(monkeypatch):
    import landing

    monkeypatch.setattr(T, 'NAMA_PRODUK', 'Produk <Sintetis>')
    isi = landing._harga_landing()
    assert 'RENCANA PAKET PRODUK &lt;SINTETIS&gt;' in isi
    assert 'RENCANA PAKET JAGOMAT' not in isi
