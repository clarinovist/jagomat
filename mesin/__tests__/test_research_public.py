"""Kontrak pusat riset bisnis dan laporan persaingan publik."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import design_tokens as T  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JALUR = "/riset/persaingan-bimbel-2026"
JALUR_PDF = f"{JALUR}.pdf"
JALUR_BISNIS = "/riset"
JALUR_BISNIS_PDF = "/riset/laporan-bisnis-2026.pdf"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        database.tambah_siswa(kon, "Putri", pemilik="guru")
    yield s
    s.berhenti()


def test_pusat_riset_bisnis_lengkap_dan_mudah_dinavigasi(server):
    kode, isi, hdr = server.minta(JALUR_BISNIS)
    assert kode == 200
    assert hdr["Content-Type"].startswith("text/html")
    assert "Seberapa besar peluang Jagomat" in isi
    assert "Kalau hanya membaca satu bagian" in isi
    for bagian in (
        "Market opportunity &amp; unit economics",
        "Competitive advantage &amp; growth strategy",
        "Consumer psychology &amp; behavioral barriers",
        "Go-to-market funnel &amp; retention engine",
        "Metodologi dan keterbatasan",
        "Sumber dan provenance",
    ):
        assert bagian in isi, f"modul riset hilang: {bagian}"
    for jangkar in ("#pasar", "#strategi", "#psikologi", "#gtm"):
        assert f'href="{jangkar}"' in isi
    assert f'href="{JALUR_BISNIS_PDF}"' in isi


def test_pusat_riset_membedakan_fakta_proxy_asumsi_dan_hitung(server):
    _, isi, _ = server.minta(JALUR_BISNIS)
    for label in (
        "Fakta sumber", "Proxy", "Asumsi manajemen", "Hasil hitung", "Rekomendasi"
    ):
        assert label in isi
    assert "bukan forecast atau valuasi" in isi.lower()
    assert "TAM rupiah" in isi and "Sengaja tidak dinyatakan" in isi
    assert "TAM volume" in isi and "Denominator resmi masih perlu diverifikasi" in isi
    assert "≈24 juta" not in isi
    assert "2.605" in isi and "13.021" in isi and "26.042" in isi
    assert "Outcome, engagement, WTP, dan defensibility belum terbukti" in isi
    assert isi.count("<small>(Asumsi)</small>") >= 4


def test_pusat_riset_zero_js_statis_dan_tidak_bocor_data(server):
    _, anonim, _ = server.minta(JALUR_BISNIS)
    _, guru, _ = server.minta(JALUR_BISNIS, auth=("guru", SANDI_GURU))
    assert anonim == guru
    assert "Putri" not in anonim
    assert "<script" not in anonim
    assert "onclick=" not in anonim
    assert anonim.count("<details") >= 4
    assert anonim.count('tabindex="0" role="region"') >= 8
    assert 'aria-label="Urutan funnel go-to-market"' in anonim


def test_route_riset_dengan_dan_tanpa_garis_miring_identik(server):
    assert server.minta("/riset")[1] == server.minta("/riset/")[1]


def test_riset_publik_lengkap_tanpa_login(server):
    kode, isi, hdr = server.minta(JALUR)
    assert kode == 200
    assert hdr["Content-Type"].startswith("text/html")
    assert "Analisis lanskap persaingan" in isi
    assert "Snapshot riset" in isi and "13 Oktober 2026" in isi
    for bagian in (
        "Kesimpulan eksekutif",
        "Peta arena",
        "Trade-off model pemain",
        "Candidate advantage",
        "PLG-assisted",
        "Tiga risiko strategis",
        "Prioritas 12 bulan",
        "Metodologi dan batasan",
        "Sumber utama",
    ):
        assert bagian in isi, f"bagian riset hilang: {bagian}"
    for pemain in ("Ruangguru", "Zenius", "Ganesha Operation", "Kumon"):
        assert pemain in isi


def test_riset_membedakan_bukti_dan_inferensi(server):
    _, isi, _ = server.minta(JALUR)
    assert "Observasi" in isi
    assert "Inferensi" in isi
    assert "Implikasi untuk Jagomat" in isi
    assert "Confidence" in isi
    assert "Analisis independen" in isi
    assert "tidak berafiliasi" in isi
    assert "market share" in isi
    assert "tidak diestimasi" in isi
    assert "Zenius" in isi and "7 Juli 2026" in isi


def test_riset_interaktif_native_tanpa_javascript(server):
    _, isi, _ = server.minta(JALUR)
    assert isi.count("<details") >= 6
    assert "<summary" in isi
    assert 'href="#peta-arena"' in isi
    assert 'href="#risiko"' in isi
    assert f'href="{JALUR_PDF}"' in isi
    assert "<script" not in isi
    assert "onclick=" not in isi


def test_riset_statis_dan_tidak_bocor_data_keluarga(server):
    _, anonim, _ = server.minta(JALUR)
    _, guru, _ = server.minta(JALUR, auth=("guru", SANDI_GURU))
    assert anonim == guru
    assert "Putri" not in anonim


def test_riset_tidak_menyentuh_database(server, monkeypatch):
    import database as db_mod

    def meledak(*args, **kwargs):
        raise AssertionError("halaman riset tidak boleh membuka basis data")

    monkeypatch.setattr(db_mod, "buka", meledak)
    assert server.minta(JALUR)[0] == 200
    assert server.minta(JALUR_PDF, biner=True)[0] == 200
    assert server.minta(JALUR_BISNIS)[0] == 200
    assert server.minta(JALUR_BISNIS_PDF, biner=True)[0] == 200


def test_pdf_bisa_diunduh_dengan_header_dan_isi_valid(server):
    kode, isi, hdr = server.minta(JALUR_PDF, biner=True)
    assert kode == 200
    assert hdr["Content-Type"] == "application/pdf"
    assert hdr["Content-Disposition"] == (
        'attachment; filename="jagomat-riset-persaingan-bimbel-2026.pdf"'
    )
    assert hdr["X-Content-Type-Options"] == "nosniff"
    assert isi.startswith(b"%PDF-")
    assert len(isi) > 50_000
    assert isi.rstrip().endswith(b"%%EOF")


def test_pdf_bisnis_bisa_diunduh_dengan_header_dan_isi_valid(server):
    kode, isi, hdr = server.minta(JALUR_BISNIS_PDF, biner=True)
    assert kode == 200
    assert hdr["Content-Type"] == "application/pdf"
    assert hdr["Content-Disposition"] == (
        'attachment; filename="jagomat-riset-bisnis-2026.pdf"'
    )
    assert hdr["X-Content-Type-Options"] == "nosniff"
    assert isi.startswith(b"%PDF-")
    assert len(isi) > 50_000
    assert isi.rstrip().endswith(b"%%EOF")


def test_pdf_bisnis_sinkron_dengan_marker_html():
    pdf = ROOT / "publik" / "jagomat-riset-bisnis-2026.pdf"
    try:
        hasil = subprocess.run(
            ["pdftotext", str(pdf), "-"],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except FileNotFoundError:
        pytest.skip("pdftotext tidak tersedia di environment test")
    for marker in (
        "Seberapa besar peluang",
        "Denominator murid SD perlu tabel primer",
        "Stress-test semantik, bukan survei pasar",
        "Rujukan utama",
    ):
        assert marker in hasil.stdout, f"PDF bisnis belum sinkron: {marker}"


def test_pdf_dan_modul_riset_masuk_image():
    for nama in (
        "jagomat-riset-persaingan-bimbel-2026.pdf",
        "jagomat-riset-bisnis-2026.pdf",
    ):
        pdf = ROOT / "publik" / nama
        assert pdf.is_file() and pdf.stat().st_size > 50_000
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=osn:osn publik/ /app/publik/" in dockerfile
    assert (ROOT / "competitive_research.py").is_file()
    assert (ROOT / "business_research.py").is_file()
    assert "COPY --chown=osn:osn *.py /app/" in dockerfile


def test_gaya_riset_responsif_dan_memakai_token():
    import business_research
    import competitive_research

    gaya = competitive_research.GAYA_RISET + business_research.GAYA_BISNIS
    assert T.BATAS_HP in gaya
    assert T.MULAI_DESKTOP in gaya
    assert f"min-height: {T.TARGET_SENTUH}" in gaya
    assert "overflow-x: auto" in gaya
    assert "@media print" in gaya
    assert "prefers-reduced-motion" in gaya
    assert ":focus-visible" in gaya
