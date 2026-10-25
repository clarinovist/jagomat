"""Skala tipe resmi: literal font-size di luar skala hanya boleh berkurang (ratchet)."""
from pathlib import Path
import re

import design_tokens as T

ROOT = Path(__file__).resolve().parent.parent
POLA = re.compile(r"font-size\s*:\s*(\d*\.?\d+)(rem|px)\b")
TOKEN_SKALA = (
    "UKURAN_TEKS_META", "UKURAN_TEKS_CATATAN", "UKURAN_TEKS_LABEL", "UKURAN_TEKS_BANTUAN",
    "UKURAN_BADAN_LAYAR", "UKURAN_BAGIAN_DEWASA", "UKURAN_ANGKA_DEWASA",
    "UKURAN_JUDUL_STITCH", "UKURAN_BAGIAN_STITCH",
    "ADMIN_UKURAN_ISI", "ADMIN_UKURAN_JUDUL", "ADMIN_UKURAN_KPI",
)

# Baseline 25 Okt 2026: 266 dari 393 deklarasi literal rem/px di luar skala.
# Turunkan angka ini setiap kali literal diganti token/nilai skala; jangan naikkan.
BATAS = {
    "admin_style.py": 7,
    "assistant_style.py": 4,
    "attachments.py": 10,
    "bootstrap_research.py": 1,
    "business_research.py": 2,
    "child_beranda_style.py": 4,
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
    "style_stitch.py": 172,
    "teacher_style.py": 29,
}


def _px(angka, satuan):
    """0.875rem dan .875rem sama; rem dihitung terhadap akar 16px."""
    return round(float(angka) * (16 if satuan == "rem" else 1), 3)


SKALA_PX = frozenset(_px(*re.fullmatch(r"(\d*\.?\d+)(rem|px)", getattr(T, t)).groups()) for t in TOKEN_SKALA)


def _tanpa_komentar(teks):
    teks = re.sub(r"/\*.*?\*/", "", teks, flags=re.S)
    return "\n".join(b for b in teks.splitlines() if not b.lstrip().startswith("#"))


def hitung_di_luar_skala(akar=ROOT):
    """Jumlah deklarasi font-size literal rem/px di luar skala, per berkas modul."""
    hasil = {}
    for path in sorted(akar.glob("*.py")):
        if path.name == "design_tokens.py":
            continue
        n = sum(1 for a, s in POLA.findall(_tanpa_komentar(path.read_text())) if _px(a, s) not in SKALA_PX)
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
        'X = "/* font-size: 9px */ d { font-size: 1.05rem; }"\n'
    )
    assert hitung_di_luar_skala(tmp_path) == {"contoh.py": 2}
