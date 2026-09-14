"""Kontrak integrasi presentasi tidak mengubah aksi/destruktif yang sah."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database
import teacher_pages
from style_stitch import CSS_SESI


@pytest.fixture()
def db(tmp_path):
    lokasi = tmp_path / 'uji.db'
    database.siapkan(lokasi)
    return lokasi


def test_putaran_lama_tetap_dibatalkan_bukan_dihapus(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Anak Histori', 'P3', pemilik='guru')
        putaran = database.buat_putaran_fokus(kon, siswa, 'P3')
        sesi = database.buat_sesi(kon, siswa, seed=193, level='P3', jumlah_soal=1)
        kon.execute("UPDATE sesi SET tujuan='pemetaan', putaran_id=? WHERE id=?", (putaran, sesi))
        kon.execute("INSERT INTO kejadian_belajar (siswa_id, putaran_id, jenis, data) VALUES (?, ?, 'putaran_ditutup', '{}')", (siswa, putaran))
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
    assert f'action="/sesi/{sesi}/batalkan"' in isi
    assert f'action="/sesi/{sesi}/hapus"' not in isi


def test_default_submit_koreksi_tidak_berubah_menjadi_konfirmasi(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Anak Konfirmasi', 'P3', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, seed=194, level='P3', jumlah_soal=1)
        database.tandai_selesai(kon, sesi)
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
    # Default submit native disabled: Enter tidak membuat bukti atau menyimpan
    # sebagian isian. Konfirmasi hanya lewat tombol yang dipilih eksplisit.
    palang = f'<button type="submit" form="form-koreksi-{sesi}" hidden disabled'
    assert isi.index(palang) < isi.index('>Konfirmasi hasil</button>')
    assert '>Simpan koreksi</button>' not in isi


def test_hierarki_tombol_panduan_memakai_selector_editorial_yang_menang():
    for kelas in ('panduan-aksi-utama-st', 'panduan-aksi-sekunder-st'):
        assert f'.pendamping-editorial-st .panduan-sesi-st .{kelas} button' in CSS_SESI
