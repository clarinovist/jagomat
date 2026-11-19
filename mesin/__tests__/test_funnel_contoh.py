"""Halaman contoh Peta Kemampuan (`/contoh-peta-kemampuan`) dan kartu profil guru. Data sintetis."""
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


def test_label_data_sintetis_dan_bagian_berurutan():
    isi = _halaman()
    assert "data sintetis, bukan hasil anak sungguhan" in isi
    urutan = ["Aisyah · kelas 4", "Penguasaan per materi", "Pola kesalahan",
              "Urutan belajar prioritas", "Satu langkah minggu ini", "Catatan guru (contoh)",
              funnel_contoh.COPY_CONTOH_PENUTUP]
    posisi = [isi.index(t) for t in urutan]
    assert posisi == sorted(posisi)


def test_bar_materi_lebar_persen_dan_chip():
    isi = _halaman()
    for _nama, persen in funnel_contoh.CONTOH_MATERI:
        assert f'style="width:{persen}%"' in isi
    assert isi.count("Perlu diperkuat") == 4 and isi.count(">Kuat<") + isi.count("Kuat</span>") >= 1


def test_satu_cta_utama_dan_tanpa_script():
    isi = _halaman()
    assert isi.count('href="/daftar?jalur=cek"') == 1
    assert "Cek anak saya, gratis" in isi
    # Kerangka bersama boleh membawa skrip bawaan; halaman contoh tidak menambah JS baru.
    assert "<script" not in Path(funnel_contoh.__file__).read_text(encoding="utf-8")
    assert isi.count("<script") == funnel_pages.halaman_paket_coba().decode().count("<script")


def test_copy_tanpa_kata_terlarang():
    teks = " ".join(
        v if isinstance(v, str) else " ".join(v)
        for k, v in vars(funnel_contoh).items()
        if k.startswith("COPY_CONTOH_") and isinstance(v, (str, tuple))
    ).lower()
    for kata in KATA_TERLARANG:
        assert kata not in teks
        assert kata not in _halaman().lower()


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
