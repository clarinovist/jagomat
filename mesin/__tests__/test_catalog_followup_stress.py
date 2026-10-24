"""Oracle independen revisi2: 600 seed per konteks dan jalur penyajian nyata."""
from collections import Counter
from dataclasses import replace
from fractions import Fraction as F
import random

import pytest
from generator import buat_soal
from topics import ambil
from test_catalog_followup import TARGET, angka, usulan

PASANGAN = [(tid, topik, lv) for tid, topik in TARGET.items()
            for lv, ids in ambil(topik).komposisi.items() if tid in ids]


def oracle(tid, p):
    """Hitung dari fakta mentah; tidak mengimpor helper perbaikan runtime."""
    if tid == 'satuan_kuantitas':
        isi, salah = {'lusin': (12, 20), 'kodi': (20, 12), 'gros': (144, 12), 'rim': (500, 100)}[p['satuan']]
        if p['arah'] == 'ke_satuan':
            key, keliru = F(sum([p['nilai']] * isi)), F(sum([p['nilai']] * salah))
        else:
            key, keliru = F(p['nilai'], isi), F(p['nilai'], salah)
        return key, {f'rev2.kuantitas.faktor_tertukar_{p["satuan"]}': keliru,
                     f'rev2.kuantitas.belum_dikonversi_{p["satuan"]}': F(p['nilai']),
                     'rev2.kuantitas.kurang_satu': key - 1}
    if tid == 'rata_rata':
        d = p['data']
        if p['varian'] == 'cari_rata':
            key = F(sum(d), len(d))
            mal = {'rev2.rata.jumlah_saja': F(sum(d)),
                   'rev2.rata.bagi_n_tambah_satu': F(sum(d), len(d) + 1)}
        else:
            key = F(sum([p['rata']] * len(d)) - sum(d[:-1]))
            mal = {'rev2.rata.total_saja': key + sum(d[:-1]),
                   'rev2.rata.abaikan_data_diketahui_terakhir': key + d[-2]}
        return key, dict(mal, **{'rev2.rata.kurang_satu': key - 1})
    if p['varian'] == 'persegi_titik_tengah':
        r = p['r']
        persegi = F(4*r*r)
        key = persegi - sum([F(22*r*r, 28)] * 4)
        mal = {'rev2.arsiran.pakai_diameter': persegi - F(88*r*r, 7),
               'rev2.arsiran.pakai_pi_314': persegi - F(314*r*r, 100)}
    else:
        l, d = p['luar'], p['dalam']
        key = F((l-d)*(l+d))
        sisi_keliru = F(l+d, 2)
        mal = {'rev2.arsiran.lebar_hanya_sekali': l*l-sisi_keliru*sisi_keliru,
               'rev2.arsiran.jawab_selisih_sisi': F(l-d)}
    return key, dict(mal, **{'rev2.arsiran.kurang_satu': key - 1})


@pytest.mark.parametrize('tid,topik,level', PASANGAN)
def test_seed_level_kunci_prosedur_collision_determinisme(monkeypatch, tid, topik, level):
    monkeypatch.setenv('OSN_KATALOG_LANJUTAN', '1')
    monkeypatch.setenv('OSN_PENILAIAN_REVISI', '0')
    tanpa_k = 0
    for seed in range(600):
        soal = buat_soal(tid, seed, level, topik)
        key, kandidat = oracle(tid, soal.parameter)
        assert angka(soal.kunci) == key, (seed, soal.parameter)
        counts = Counter(kandidat.values())
        eligible = {i: v for i, v in kandidat.items() if v != key and counts[v] == 1}
        assert {m.id: angka(m.jawaban) for m in soal.malrule} == eligible, (seed, soal.parameter)
        tanpa_k += not any(m.kode == 'K' for m in soal.malrule)
        for m in soal.malrule:
            assert usulan(soal, str(eligible[m.id])).malrule_id == m.id
        if seed < 25:
            assert buat_soal(tid, seed, level, topik) == soal
            paket = ambil(topik)
            p = paket.parameter_untuk(tid, random.Random(seed), level)
            assert replace(paket.templates[tid](**p), level=level) == soal
    assert tanpa_k <= 600 * .02


@pytest.mark.parametrize('tid,topik,level', PASANGAN)
def test_render_dan_pg_revisi2(monkeypatch, tid, topik, level):
    from choice_generation import buat_lembar_pilihan, kandidat
    from question_views import penyajian_dari_soal
    from render import _badan_soal
    monkeypatch.setenv('OSN_KATALOG_LANJUTAN', '1')
    monkeypatch.setenv('OSN_VISUAL_KELUARGA', 'statistika,geometri-datar,pengukuran')
    paket = ambil(topik)
    for seed in range(25):
        soal = buat_soal(tid, seed, level, topik)
        penyajian = penyajian_dari_soal(soal)
        assert _badan_soal(replace(soal, penyajian=penyajian), paket)
        assert soal.pembahasan and soal.kunci in soal.pembahasan
        lembar = buat_lembar_pilihan(seed, level=level, topik=topik)
        for item in lembar.soal:
            assert kandidat(item)
            assert penyajian_dari_soal(item)


def test_jalur_tersimpan_bank_diagnosis_dan_outcome(tmp_path, monkeypatch):
    import database
    import reports
    from question_views import soal_dari_baris
    path = tmp_path / 'sintetis.db'
    database.siapkan(path)
    with database.buka(path) as db:
        anak = database.tambah_siswa(db, 'Fixture sintetis', 'P5', pemilik='guru')
        for tid, topik in TARGET.items():
            monkeypatch.setenv('OSN_KATALOG_LANJUTAN', '0')
            lama = buat_soal(tid, 1, 'P5', topik)
            monkeypatch.setenv('OSN_KATALOG_LANJUTAN', '1')
            baru = buat_soal(tid, 1, 'P5', topik)
            sid = database.buat_sesi_dari_urutan(db, anak, 1, urutan=(tid, tid),
                topik=topik, level='P5', soal_terpilih=(lama, baru))
            rows = database.isi_sesi(db, sid)
            assert rows[0]['soal_id'] != rows[1]['soal_id']
            for row, s in zip(rows, (lama, baru)):
                database.simpan_jawaban(db, row['sesi_soal_id'], s.kunci, 'cara sintetis')
            reports.diagnosa_murid(db, sid)
            assert [r['benar'] for r in database.isi_sesi(db, sid)] == [1, 1]
            database.tandai_selesai(db, sid)
            database.konfirmasi_hasil(db, sid, 'guru')
            before = tuple(tuple(r) for r in db.execute('SELECT * FROM snapshot_outcome'))
            for flag in ('0', 'rusak'):
                monkeypatch.setenv('OSN_KATALOG_LANJUTAN', flag)
                got = [soal_dari_baris(r) for r in database.isi_sesi(db, sid)]
                assert [s.kunci for s in got] == [lama.kunci, baru.kunci]
                assert [s.malrule for s in got] == [lama.malrule, baru.malrule]
                assert tuple(tuple(r) for r in db.execute('SELECT * FROM snapshot_outcome')) == before
