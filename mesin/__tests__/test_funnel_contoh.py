"""Halaman contoh Peta Kemampuan (`/contoh-peta-kemampuan`) dan kartu profil guru. Data sintetis.

Isi laporan playful v4 diuji di `test_peta_contoh.py`; berkas ini menjaga kerangka halaman,
sakelar, CTA tunggal, dan profil guru.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import funnel_contoh  # noqa: E402
import funnel_pages  # noqa: E402
import funnel_style  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402

JALUR = "/contoh-peta-kemampuan"
KATA_TERLARANG = ("pasti naik", "dijamin", "menjamin", "diagnosis lengkap", "pasti akurat")
PROFIL_UJI = (
    {"nama": "Guru Contoh <b>X</b>", "latar": "S1 Pendidikan Matematika (contoh)", "lama_mengajar": "5 tahun (contoh)"},
)


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        yield uji
    finally:
        uji.berhenti()


def _halaman() -> str:
    return funnel_contoh.halaman_contoh_peta().decode()


def test_sakelar_mati_menampilkan_belum_dibuka_tanpa_cta(server):
    kode, isi, _ = server.minta(JALUR)
    assert kode == 200 and "belum dibuka" in isi.lower()
    assert "/daftar?jalur=cek" not in isi


def test_sakelar_aktif_mengembalikan_contoh(server, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    kode, isi, _ = server.minta(JALUR)
    assert kode == 200 and "Penguasaan per materi" in isi


def test_contoh_v1_valid_dan_sesuai_laporan_nyata():
    import peta_laporan_snapshot
    import peta_laporan_store

    isi = _halaman()
    assert "data sintetis, bukan hasil anak sungguhan" in isi
    assert funnel_contoh.COPY_CONTOH_JUDUL in isi
    assert "Contoh untuk Aisyah · Kelas 4 · 15 soal" in isi
    peta_laporan_snapshot.periksa_isi(funnel_contoh.CONTOH_PETA_V1["isi"])
    assert peta_laporan_store.periksa_catatan(funnel_contoh.CONTOH_PETA_V1["catatan"]) is None
    for wajib in ("Ditinjau Guru Jagomat", "Penguasaan per materi", "Yang paling perlu dilatih dulu",
                  "Catatan dari Guru", "Rp300.000 per bulan", "Rp49.000"):
        assert wajib in isi, wajib
    for lama in ("Pola kesalahan", "peringkat", "persentil", "Lencana", "/contoh-peta-kemampuan/lembar",
                 "otomatis dipotong", "otomatis memotong"):
        assert lama not in isi, lama


def test_bar_meter_dari_data_contoh():
    isi = _halaman()
    for materi in funnel_contoh.CONTOH_PETA_V1["isi"]["per_materi"]:
        assert f'min="0" max="{materi["total"]}" value="{materi["benar"]}"' in isi


def test_satu_cta_utama_dan_tanpa_skrip_tambahan():
    isi = _halaman()
    assert isi.count('href="/daftar?jalur=cek"') == 1
    assert "Cek anak saya, gratis" in isi
    # Skrip di berkas renderer tidak ditulis langsung; jumlah skrip identik dengan /paket-coba (Zero-JS tambahan).
    assert "<script" not in Path(funnel_contoh.__file__).read_text(encoding="utf-8")
    assert len(re.findall(r"<script\b", isi)) == len(re.findall(r"<script>", isi))
    assert len(re.findall(r"<script>", isi)) == len(re.findall(r"<script>", funnel_pages.halaman_paket_coba().decode()))


def test_copy_tanpa_kata_terlarang():
    teks = " ".join(
        v for k, v in vars(funnel_contoh).items() if k.startswith("COPY_CONTOH_") and isinstance(v, str)
    ).lower()
    badan = re.sub(r"<(style|script)\b.*?</\1>", "", _halaman(), flags=re.S).lower()
    for kata in KATA_TERLARANG:
        assert kata not in teks
        assert kata not in badan


def test_tautan_contoh_di_cek_paket_dan_bukan_tombol_koral():
    for isi in (funnel_pages.halaman_cek_kemampuan().decode(), funnel_pages.halaman_paket_coba().decode()):
        assert f'href="{JALUR}"' in isi
        assert funnel_pages.COPY_TAUTAN_CONTOH in isi
        assert re.search(rf'class="tombol-coral"[^>]*href="{JALUR}"|href="{JALUR}"[^>]*tombol-coral', isi) is None


def test_gaya_tanpa_hex_dan_important():
    sumber = Path(funnel_style.__file__).read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", sumber)
    assert "!important" not in sumber


def test_profil_guru_kosong_bawaan_tanpa_kartu():
    assert funnel_pages.PROFIL_GURU == ()
    assert funnel_pages.kartu_profil_guru() == ""
    for isi in (_halaman(), funnel_pages.halaman_paket_coba().decode()):
        assert "funnel-guru-st\"" not in isi.split("</style>", 1)[1]
        assert funnel_pages.COPY_JUDUL_PROFIL_GURU not in isi


def test_profil_guru_terisi_tampil_dan_ter_escape(monkeypatch):
    monkeypatch.setattr(funnel_pages, "PROFIL_GURU", PROFIL_UJI)
    for isi in (_halaman(), funnel_pages.halaman_paket_coba().decode()):
        assert funnel_pages.COPY_JUDUL_PROFIL_GURU in isi
        assert "S1 Pendidikan Matematika (contoh)" in isi and "5 tahun (contoh)" in isi
        assert "<b>X</b>" not in isi and "&lt;b&gt;X&lt;/b&gt;" in isi
