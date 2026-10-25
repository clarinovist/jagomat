"""Skala tipe resmi: literal font-size di luar skala hanya boleh berkurang (ratchet)."""
import ast
from pathlib import Path
import re

import design_tokens as T

ROOT = Path(__file__).resolve().parent.parent
# font-size: N dan shorthand `font: [gaya/berat] N...`; hanya satuan rem/px.
POLA = re.compile(r"font(?:-size\s*:\s*|\s*:\s*(?:(?:italic|oblique|normal|bold|bolder|lighter|small-caps|\d{3})\s+)*)"
                  r"(\d*\.?\d+)(rem|px)\b")
TOKEN_SKALA = (
    "UKURAN_TEKS_META", "UKURAN_TEKS_CATATAN", "UKURAN_TEKS_LABEL", "UKURAN_TEKS_BANTUAN",
    "UKURAN_BADAN_LAYAR", "UKURAN_BAGIAN_DEWASA", "UKURAN_ANGKA_DEWASA",
    "UKURAN_JUDUL_STITCH", "UKURAN_BAGIAN_STITCH",
)

# Baseline 25 Okt 2026: 293 dari 444 deklarasi literal rem/px di luar skala.
# Turunkan angka ini setiap kali literal diganti token/nilai skala; jangan naikkan.
BATAS = {
    "assistant_style.py": 4,
    "attachments.py": 10,
    "bootstrap_research.py": 1,
    "business_research.py": 2,
    "child_beranda_style.py": 4,
    "child_header.py": 1,
    "child_history_style.py": 1,
    "child_latihan_style.py": 6,
    "child_materi_style.py": 2,
    "child_ringkasan_style.py": 3,
    "child_style.py": 2,
    "competitive_research.py": 1,
    "parent_help.py": 1,
    "profile_workspace.py": 2,
    "report_dashboard.py": 3,
    "screen_style.py": 14,
    "student_pages.py": 2,
    "style_stitch.py": 197,
    "teacher_style.py": 29,
}


def _px(angka, satuan):
    """0.875rem dan .875rem sama; rem dihitung terhadap akar 16px."""
    return round(float(angka) * (16 if satuan == "rem" else 1), 3)


SKALA_PX = frozenset(_px(*re.fullmatch(r"(\d*\.?\d+)(rem|px)", getattr(T, t)).groups()) for t in TOKEN_SKALA)
# Dua judul promosi 40px sudah diizinkan sebelum skala admin dihapus.
# Pertahankan cakupan ratchet permukaan lain tanpa mengubah tampilannya.
# Ini bukan token/skala admin; test_admin_shared_design menolak literal admin.
SKALA_RATCHET_PX = SKALA_PX | {40.0}


def _isi_string(teks):
    """Isi literal string (tempat CSS berada) via AST, sama di Python 3.9 dan 3.12.

    Komentar Python tidak masuk AST; bagian f-string di luar ekspresi ikut, komentar CSS dibuang.
    """
    isi = "\n".join(n.value for n in ast.walk(ast.parse(teks))
                    if isinstance(n, ast.Constant) and isinstance(n.value, str))
    return re.sub(r"/\*.*?\*/", "", isi, flags=re.S)


def hitung_di_luar_skala(akar=ROOT):
    """Jumlah deklarasi font-size literal rem/px di luar skala, per berkas modul."""
    hasil = {}
    for path in sorted(akar.glob("*.py")):
        if path.name == "design_tokens.py":
            continue
        n = sum(1 for a, s in POLA.findall(_isi_string(path.read_text())) if _px(a, s) not in SKALA_RATCHET_PX)
        if n:
            hasil[path.name] = n
    return hasil


def test_skala_resmi_berasal_dari_token():
    assert {12.0, 13.0, 14.0, 14.4, 16.0, 18.0, 20.0, 24.0, 28.0} <= SKALA_PX


def test_literal_di_luar_skala_tidak_bertambah_dan_batas_diperketat():
    kini = hitung_di_luar_skala()
    naik = {f: (n, BATAS.get(f, 0)) for f, n in kini.items() if n > BATAS.get(f, 0)}
    assert not naik, f"font-size literal di luar skala bertambah (kini, batas): {naik}; pakai token UKURAN_*"
    turun = {f: (kini.get(f, 0), n) for f, n in BATAS.items() if kini.get(f, 0) < n}
    assert not turun, f"literal berkurang (kini, batas): {turun}; turunkan BATAS agar ratchet terkunci"


def test_penghitung_menyamakan_ejaan_dan_melewati_komentar(tmp_path):
    (tmp_path / "contoh.py").write_text(
        'CSS = """a { font-size: 0.875rem; } b { font-size: .875rem; } c { font-size: 15px; }"""\n'
        '# font-size: 11px di komentar Python\n'
        'X = "/* font-size: 9px */ d { font-size: 1.05rem; } e { font: 700 .8rem/1.5 x; } f { font: inherit; }"\n'
        'Y = """\n#id { font: italic 1rem x; }"""\n'
    )
    assert hitung_di_luar_skala(tmp_path) == {"contoh.py": 3}
