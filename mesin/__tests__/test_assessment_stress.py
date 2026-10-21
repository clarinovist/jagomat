"""Stress semantik revisi penilaian lintas seed×level, oracle terpisah dari generator."""
from fractions import Fraction as F
from pathlib import Path
import sys

import pytest
from generator import buat_soal
from diagnosis import diagnosa
from topics import ambil

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from catalog_pilot_oracle import kunci,prosedur
from catalog_pilot import fakta,TOPIK


@pytest.mark.parametrize('tid',tuple(TOPIK))
def test_stress_semantik_pilot_600_seed(tid,monkeypatch):
    monkeypatch.setenv('OSN_PENILAIAN_REVISI','1')
    monkeypatch.setenv('OSN_KATALOG_VERSI','2')
    for level in (lv for lv,ids in ambil(TOPIK[tid]).komposisi.items() if tid in ids):
        for seed in range(600):
            s=buat_soal(tid,seed,level,TOPIK[tid])
            p=s.parameter
            if tid=='satuan_waktu_lama' and p['varian']!='windu_ke_lustrum':continue
            if tid=='luas_permukaan' and not p['varian'].startswith('tabung'):continue
            f=fakta(tid,p)
            assert F(s.kunci.replace(',','.'))==kunci(tid,f)
            seen={F(s.kunci.replace(',','.'))}
            for m in s.malrule:
                value=F(m.jawaban.replace(',','.'))
                assert value==prosedur(tid,f,m.id),(level,seed,m)
                assert value not in seen
                seen.add(value)
                aturan=[dict(malrule_id=r.id,jawaban=r.jawaban,kode=r.kode,alasan=r.alasan) for r in s.malrule]
                jawab=f'{value.numerator*2}/{value.denominator*2}'
                hasil=diagnosa(s.kunci,jawab,'sintetis','',False,aturan,soal=s)
                assert hasil.malrule_id==m.id and not hasil.benar


def test_kecepatan_dan_semua_konversi_tidak_nudge(monkeypatch):
    monkeypatch.setenv('OSN_PENILAIAN_REVISI','1')
    tahun={'abad':100,'windu':8,'lustrum':5,'dasawarsa':10,'tahun':1}
    for seed in range(600):
        for tid,topik in (('kecepatan_jarak_waktu','aritmatika-lanjut'),('satuan_waktu_lama','pengukuran')):
            s=buat_soal(tid,seed,'P6',topik);p=s.parameter
            for m in s.malrule:
                value=F(m.jawaban.replace(',','.'))
                if tid=='kecepatan_jarak_waktu' and m.id.startswith('rev1.kecepatan.balik_'):
                    exp=F(p['t'],p['s']) if p['varian']=='cari_v' else F(p['v'],p['t']) if p['varian']=='cari_s' else F(p['v'],p['s'])
                    assert value==exp
                if tid=='satuan_waktu_lama' and m.id.startswith('rev1.waktu.balik_'):
                    a,b=p['varian'].split('_ke_');assert value==F(p['nilai']*tahun[b],tahun[a])
