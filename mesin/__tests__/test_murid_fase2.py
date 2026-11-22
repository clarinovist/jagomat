"""Perbaikan visual area anak, Fase 2 (22 Nov 2026): grid nomor Simulasi, tanpa label Variasi, tanggal, Keluar, PG kartu."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import choice_pages
import contest_pages as P
import contest_store as K
import database
import design_tokens as T
import murid_lembar_style
import student_pages

BULAN = "Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember"
TANGGAL_MANUSIAWI = re.compile(rf"\b\d{{1,2}} (?:{BULAN}) \d{{4}}\b")
TANGGAL_ISO = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "fase2.db"
    database.siapkan(path)
    monkeypatch.setattr(database, "BAWAAN", path)
    return path


def _soal(nomor: int = 1) -> K.SoalAnak:
    return K.SoalAnak(nomor=nomor, jenis="pg", topik="bilangan", teks="Berapa 2 + 3?", svg="",
                      pilihan=("4", "5", "6", "7"), gambar_pilihan=("", "", "", ""), jawaban=None)


def _halaman(jumlah: int, terjawab=frozenset()) -> str:
    return P.halaman_soal(9, _soal(), terjawab, 600, jumlah=jumlah).decode()


# --- #1 grid nomor Simulasi ----------------------------------------------------------

def test_simulasi_35_grid_nomor_dilipat_di_bawah_kartu_dan_tombol_geser():
    isi = _halaman(35, frozenset(range(1, 13)))

    assert isi.index('<section class="kartu">') < isi.index('<details class="daftar-nomor">')
    assert isi.index('class="aksi"') < isi.index('<details class="daftar-nomor">')
    assert isi.index('<details class="daftar-nomor">') < isi.index('class="tautan-selesai"')
    assert "<summary>Semua nomor · 12 dari 35 terjawab</summary>" in isi
    assert "open" not in re.search(r"<details class=\"daftar-nomor\"[^>]*>", isi).group(0)
    detail = isi[isi.index('<details class="daftar-nomor">'):isi.index("</details>")]
    assert len(re.findall(r'<button type="submit" name="pindah" value="\d+" class="nomor ', detail)) == 35
    assert isi.count('<ol class="strip">') == 1


def test_simulasi_35_tombol_nomor_ada_di_form_yang_sama_dan_simpan_tetap_submit_pertama():
    isi = _halaman(35)

    form = isi[isi.index("<form"):isi.index("</form>")]
    assert '<details class="daftar-nomor">' in form
    kontrol = re.search(r"<(button|input|select|textarea)\b[^>]*>", form).group(0)
    assert kontrol == '<button type="submit" name="aksi" value="simpan" class="sr-saja">'
    assert form.index('value="simpan"') < form.index('name="pindah"')
    assert 'id="timer" data-sisa="600"' in isi


def test_latihan_10_strip_nomor_tetap_di_atas_kartu_tanpa_details():
    isi = _halaman(10, frozenset({1}))

    assert isi.index('<ol class="strip">') < isi.index('<section class="kartu">')
    assert "daftar-nomor" not in re.sub(r"<style>.*?</style>", "", isi, flags=re.S)


# --- #10 #9 #14 lembar kerja, beranda, hasil -----------------------------------------

def _buat_halaman(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", "P5", pemilik="guru")
        sesi = database.buat_sesi(kon, siswa, seed=3, jumlah_soal=3, level="P5")
        lain = database.buat_sesi(kon, siswa, seed=4, jumlah_soal=3, level="P5")
        selesai = database.buat_sesi(kon, siswa, seed=5, jumlah_soal=3, level="P5")
        database.tandai_selesai(kon, selesai)
        kon.execute("UPDATE sesi SET direview = datetime('now') WHERE id = ?", (selesai,))
        return {
            "beranda": student_pages.halaman_daftar_sesi_baru(kon, siswa, "Anak Sintetis").decode(),
            "kerja": student_pages.halaman_kerja_baru(kon, siswa, sesi).decode(),
            "hasil": student_pages.halaman_hasil_murid(kon, siswa, selesai).decode(),
        }


def test_label_variasi_tidak_tampil_di_halaman_anak(db):
    for nama, isi in _buat_halaman(db).items():
        badan = re.sub(r"<style>.*?</style>", "", isi, flags=re.S)
        assert "Variasi" not in badan, nama


def test_tanggal_lembar_kerja_dan_hasil_memakai_format_beranda(db):
    halaman = _buat_halaman(db)
    for nama in ("beranda", "kerja", "hasil"):
        badan = re.sub(r"<style>.*?</style>", "", halaman[nama], flags=re.S)
        assert TANGGAL_MANUSIAWI.search(badan), nama
        assert not TANGGAL_ISO.search(badan), nama


def test_lembar_kerja_tanpa_form_keluar_dan_beranda_tetap_punya_satu(db):
    halaman = _buat_halaman(db)

    assert 'action="/keluar"' not in halaman["kerja"] and 'action="/keluar"' not in halaman["hasil"]
    assert halaman["beranda"].count('action="/keluar"') == 1
    assert ">Tutup</a>" in halaman["kerja"]


# --- #11 badge netral -----------------------------------------------------------------

def test_belum_dimulai_memakai_badge_netral_bukan_koral(db):
    isi = _buat_halaman(db)["beranda"]

    assert '<span class="st-badge netral">Belum dimulai</span>' in isi
    assert re.search(r"\.murid-beranda-st \.st-badge\.netral \{ background: transparent; color: " + re.escape(T.TEKS_SUBTLE), isi)
    assert ".murid-beranda-st .st-badge.baru" in isi  # kelas lama tidak dipakai kartu ini, aturannya tetap untuk hasil


# --- #5 PG kartu ----------------------------------------------------------------------

class _Opsi:
    def __init__(self, id_, label, teks, nilai):
        self.id, self.label, self.teks, self.nilai = id_, label, teks, nilai


class _Pilihan:
    sesi_soal_id = 7
    opsi = (_Opsi("opsi_1", "A", "12", "12"), _Opsi("opsi_2", "B", "15", "15"))


def test_radio_pilihan_memisahkan_huruf_tanpa_mengubah_name_value_checked():
    isi = choice_pages.radio_pilihan(_Pilihan(), jawaban="15")

    assert '<input type="radio" name="opsi_7" value="opsi_1">' in isi
    assert '<input type="radio" name="opsi_7" value="opsi_2" checked>' in isi
    assert '<span class="pg-huruf">A</span><span class="pg-teks">12</span>' in isi
    assert 'class="pg-kosong"' in isi and 'name="opsi_7" value=""' in isi


def test_radio_pilihan_jaring_jaring_menyimpan_teks_pilihan_untuk_pembaca_layar():
    isi = choice_pages.radio_pilihan(_Pilihan(), template_id="jaring_jaring")

    assert '<span class="pg-teks pg-teks-sr">Pilihan A</span>' in isi


def test_css_pg_kartu_target_sentuh_dan_tanpa_hex():
    css = murid_lembar_style.GAYA_MURID_LEMBAR
    sumber = Path(murid_lembar_style.__file__).read_text()

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", sumber)
    assert re.search(r"\.pg-opsi, body\.st\.kerja-editorial-st \.pg-kosong \{[^}]*min-height: " + re.escape(T.TARGET_SENTUH), css)
    assert T.UKURAN_SOAL in css and T.BOBOT_SOAL in css and T.LINE_HEIGHT_SOAL in css


# --- #6 #13 beranda dan halaman Lomba -------------------------------------------------

def test_tombol_kartu_lomba_kecil_sekunder_dan_besar_utama():
    from contest_style import GAYA_BERANDA

    kecil = re.search(r"\.lb-tombol \{\s*[^}]*\}", GAYA_BERANDA).group(0)
    assert T.LATAR_KARTU in kecil and T.AKSEN_KORAL_TUA not in kecil and T.AKSEN_TEAL_TUA in kecil.split("color:")[1]
    assert re.search(r"\.lomba-beranda\.besar \.lb-tombol \{ background: " + re.escape(T.AKSEN_KORAL_TUA), GAYA_BERANDA)


def test_tombol_utama_lomba_anak_koral_dan_sekunder_tetap_sekunder():
    from contest_style import GAYA_LOMBA

    utama = re.search(r"\n\.tombol \{\{?[^}]*\}", GAYA_LOMBA).group(0)
    assert T.AKSEN_KORAL_TUA in utama and T.AKSEN_TEAL_TUA not in utama
    assert re.search(r"\.tombol\.sekunder \{ background: " + re.escape(T.LATAR_KARTU), GAYA_LOMBA)
