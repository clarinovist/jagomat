"""Materi terbimbing terikat riwayat sesi, bukan pendekatan global terbaru."""
from datetime import date
import html
import json

import pytest
import database
from test_skill_pilot_flow import db, mulai, lanjut, sahkan
from skill_pilot_service import jalankan, revisi
from skill_pilot_store import baca_kontrak
from skill_pilot_materials import pilihan_materi
from skill_pilot_ui import materi_sesi


def siapkan_terbimbing(kon, siswa):
    sid, _ = mulai(kon, siswa)
    sahkan(kon, sid, salah=True)
    sahkan(kon, lanjut(kon, siswa, '2026-09-04'), '2026-09-04', True)
    jalankan(kon, siswa, {'aksi': 'pelajari', 'revisi': revisi(kon, siswa)}, hari=date(2026, 9, 4))
    return lanjut(kon, siswa, '2026-09-04')


def test_alternatif_tampil_tanpa_menafsir_ulang_sesi_lama(db):
    kon, siswa = db
    pertama = siapkan_terbimbing(kon, siswa)
    butir = baca_kontrak(kon, pertama, siswa).butir[0]
    utama, alternatif = pilihan_materi(butir.konteks, butir.target_fokus)
    awal = materi_sesi(kon, pertama, siswa)
    assert html.escape(utama.contoh_terbimbing, quote=True) in awal
    sahkan(kon, pertama, '2026-09-04')
    sahkan(kon, lanjut(kon, siswa, '2026-09-04'), '2026-09-04')
    sahkan(kon, lanjut(kon, siswa, '2026-09-07'), '2026-09-07', True)
    jalankan(kon, siswa, {'aksi': 'pelajari', 'revisi': revisi(kon, siswa)}, hari=date(2026, 9, 8))
    kedua = lanjut(kon, siswa, '2026-09-08')
    sebelum = tuple(kon.iterdump())
    assert html.escape(alternatif.contoh_terbimbing, quote=True) in materi_sesi(kon, kedua, siswa)
    assert materi_sesi(kon, pertama, siswa) == awal
    assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('rusak', ['hilang', 'asing', 'sumber', 'sumber_kurang', 'putaran'])
def test_intervensi_tidak_sah_tidak_memakai_contoh_default(db, rusak):
    kon, siswa = db
    sid = siapkan_terbimbing(kon, siswa)
    # Korupsi terkontrol hanya fixture sintetis untuk menguji reader gagal tertutup.
    for row in kon.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='kejadian_belajar'").fetchall():
        kon.execute('DROP TRIGGER "' + row[0] + '"')
    event = kon.execute("SELECT * FROM kejadian_belajar WHERE jenis='intervensi_selesai'").fetchone()
    data = json.loads(event['data'])
    if rusak == 'hilang':
        kon.execute('DELETE FROM kejadian_belajar WHERE id=?', (event['id'],))
    elif rusak == 'putaran':
        kon.execute('UPDATE kejadian_belajar SET putaran_id=NULL WHERE id=?', (event['id'],))
    else:
        if rusak == 'asing':
            baru = {**data, 'pendekatan_id': 'asing'}
        elif rusak == 'sumber_kurang':
            baru = {**data, 'sumber_konfirmasi': data['sumber_konfirmasi'][:-1]}
        else:
            baru = {**data, 'sumber_konfirmasi': [999999]}
        kon.execute('UPDATE kejadian_belajar SET data=? WHERE id=?', (json.dumps(baru), event['id']))
    sebelum = tuple(kon.iterdump())
    with pytest.raises(ValueError):
        materi_sesi(kon, sid, siswa)
    assert tuple(kon.iterdump()) == sebelum


def test_pengenalan_tetap_materi_t_tanpa_event_intervensi(db):
    kon, siswa = db
    sid, _ = mulai(kon, siswa, belum_dikenal='1')
    assert 'Pelajari bersama' in materi_sesi(kon, sid, siswa)
    with pytest.raises(ValueError):
        materi_sesi(kon, sid, siswa + 1)
