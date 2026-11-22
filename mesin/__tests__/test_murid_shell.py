"""Shell murid (audit area anak, Fase 1): satu topbar, font lokal, tanpa Google/Material Symbols."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import auth_http
import contest_awal
import contest_komponen
import contest_pages
import contest_store as K
import database
import murid_shell
import student_pages
from support_pages import halaman_pesan, halaman_pesan_murid
import design_tokens as T

# Aturan CSS global `.material-symbols-outlined` masih ikut GAYA_STITCH (guru/publik memakainya);
# yang dilarang di halaman anak adalah markupnya dan pemuatan font Material Symbols.
DILARANG = ("fonts.googleapis", "fonts.gstatic", "Material+Symbols", 'class="material-symbols-outlined')


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "shell.db"
    database.siapkan(path)
    monkeypatch.setattr(database, "BAWAAN", path)
    return path


def _soal_lomba() -> K.SoalAnak:
    return K.SoalAnak(nomor=1, jenis="pg", topik="bilangan", teks="Berapa 2 + 3?", svg="",
                      pilihan=("4", "5", "6", "7"), gambar_pilihan=(), jawaban=None)


def _halaman_anak(db) -> dict:
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", pemilik="guru")
        sesi = database.buat_sesi(kon, siswa, seed=3, jumlah_soal=4, mode="drill", timer_mode="sesi")
        selesai = database.buat_sesi(kon, siswa, seed=4, jumlah_soal=4)
        kon.execute("UPDATE sesi SET selesai = '2026-11-22T10:00:00' WHERE id = ?", (selesai,))
        halaman = {
            "beranda": student_pages.halaman_daftar_sesi_baru(kon, siswa, "Anak Sintetis"),
            "kerja": student_pages.halaman_kerja_baru(kon, siswa, sesi),
            "kerja-tautan": student_pages.halaman_kerja_baru(kon, siswa, sesi, akses_tautan=True,
                                                             jalur_aksi="/mulai/contoh"),
            "kerja-terkirim": student_pages.halaman_kerja_baru(kon, siswa, selesai),
        }
    halaman["pesan"] = halaman_pesan_murid("404", "<h1>Halaman tidak ada</h1>")
    halaman["lomba-soal"] = contest_pages.halaman_soal(9, _soal_lomba(), frozenset(), 600)
    halaman["lomba-selesai"] = contest_pages.halaman_selesai(9, [1, 2], 500)
    halaman["lomba-gagal"] = contest_pages.halaman_gagal_siapkan()
    halaman["masuk"] = auth_http.halaman_masuk()
    return {nama: isi.decode() for nama, isi in halaman.items()}


def test_halaman_anak_tanpa_google_dan_material_symbols(db):
    for nama, isi in _halaman_anak(db).items():
        for kata in DILARANG:
            assert kata not in isi, (nama, kata)
        assert "@import" not in isi, nama
        assert 'font-family:"Be Vietnam Pro"' in isi, nama


def test_halaman_anak_memakai_topbar_bersama_dengan_logo_dan_nama(db):
    halaman = _halaman_anak(db)
    for nama, isi in halaman.items():
        if nama == "masuk":
            continue
        assert isi.count('<header class="murid-topbar-st">') == 1, nama
        assert f'<span class="murid-brand-st">{murid_shell.brand.mark("topbar")}<span>{T.NAMA_PRODUK}</span></span>' in isi, nama
        assert "murid-wadah-st" in isi, nama


def test_tautan_hp_tanpa_login_tidak_menautkan_ke_murid_di_topbar(db):
    isi = _halaman_anak(db)["kerja-tautan"]
    topbar = re.search(r'<header class="murid-topbar-st">.*?</header>', isi, re.S).group(0)
    assert "/murid" not in topbar and "<a " not in topbar and "<button" not in topbar


def test_slot_kanan_topbar_per_halaman(db):
    halaman = _halaman_anak(db)
    assert 'action="/keluar"' in halaman["beranda"].split('<main')[0]
    assert ">Tutup</a>" in halaman["kerja"] and 'href="/murid"' in halaman["kerja"]
    assert ">Beranda</a>" in halaman["kerja-terkirim"]
    assert 'id="timer" data-sisa="600"' in halaman["lomba-soal"]


def test_beranda_satu_kolom_tanpa_grid_dua_kolom(db):
    isi = _halaman_anak(db)["beranda"]
    assert "satu-kolom" not in isi
    assert "grid-template-columns: minmax(0, 1fr) 20rem" not in isi
    assert "max-width: 70rem" not in isi


def test_lomba_bilah_lama_dan_header_tanpa_logo_hilang():
    isi = contest_pages.halaman_soal(9, _soal_lomba(), frozenset(), 600).decode()
    assert 'class="bilah"' not in isi and 'class="bilah-atas"' not in isi
    assert contest_komponen.bilah_beranda().startswith('<header class="murid-topbar-st">')
    assert "Soal 1 dari 35" in isi or "Soal 1 dari" in isi


def test_pesan_umum_tetap_tanpa_shell_murid_agar_guru_tidak_berubah():
    isi = halaman_pesan("404", "<h1>x</h1>").decode()
    assert 'class="st-topbar"' in isi and "pesan-brand-st" not in isi and "murid-topbar-st" not in isi
    assert "fonts.googleapis" not in isi and "<a " not in isi  # lockup tanpa tautan: halaman pesan bisa anonim


def test_ikon_murid_dekoratif_dan_menolak_nama_tak_dikenal():
    for nama in ("panah", "buku", "grafik", "bilangan", "jam", "lipat", "kamera", "tutup", "lampu"):
        svg = murid_shell.ikon_murid(nama)
        assert 'aria-hidden="true"' in svg and 'stroke="currentColor"' in svg
    with pytest.raises(ValueError):
        murid_shell.ikon_murid("tidak-ada")


def test_css_shell_hanya_token_tanpa_hex_dan_kolom_46rem():
    sumber = Path(murid_shell.__file__).read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", sumber)
    css = murid_shell.GAYA_SHELL_MURID
    assert T.LEBAR_KONTEN in css and T.ANAK_GUTTER in css


def test_cetak_murid_tidak_ikut_di_lomba():
    assert "display: none" in murid_shell.kepala_murid("a{}")
    assert "display: none" not in murid_shell.kepala_murid("a{}", cetak=False)
