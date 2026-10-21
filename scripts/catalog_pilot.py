#!/usr/bin/env python3
"""Pilot offline A/B/C: paket draft sintetis, tanpa DB/provider atau serving aplikasi."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import html
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time

AKAR=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AKAR/'mesin'))
from catalog_exact import baca_angka
from assessment_revision import KONTRAK
from catalog_pilot_oracle import KONSEP, angka, kunci, prosedur, sah_domain
from catalog_pilot_authored import ITEM

TOPIK={KONSEP[0]:'aritmetika-dasar',KONSEP[1]:'aritmetika-dasar',
       'menyusul':'aritmatika-lanjut','satuan_waktu_lama':'pengukuran','luas_permukaan':'geometri-ruang'}
# Tetap sebelum produksi kandidat. A/C berpasangan; seed bukan hasil memilih skor bagus.
CABANG={KONSEP[0]:(None,)*6,KONSEP[1]:('kali',)*3+('bagi',)*3,
        'menyusul':(None,)*6,'satuan_waktu_lama':('windu_ke_lustrum',)*6,
        'luas_permukaan':('tabung_LP',)*3+('tabung_cari_t',)*3}
RUBRIK_MANUSIA=('matematika_teks','konteks_bahasa','beban_baca','pembahasan','diagnosis','menit_review','menit_revisi')


def serial(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def sidik(obj):return hashlib.sha256(serial(obj).encode()).hexdigest()


def fakta(tid,p):
    fields={KONSEP[0]:('n1','d1','n2','d2','n3','d3'),KONSEP[1]:('n1','d1','n2','d2','op'),
            'menyusul':('jarak','v1','v2'),'satuan_waktu_lama':('varian','nilai')}
    if tid=='luas_permukaan':names=('varian','r','t') if p['varian']=='tabung_LP' else ('varian','r','LP')
    else:names=fields[tid]
    return {k:p[k] for k in names}


def bungkus(tid,lengan,n,f,teks,key,solusi,mal,source,seed=None):
    payload={'publik':{'konsep':tid,'level':'P6','fakta':f,'teks':teks},
             'guru':{'kontrak':KONTRAK,'kunci':key,'pembahasan':solusi,'malrule':mal}}
    h=sidik(payload)
    return {'id':f'{lengan}-{tid}-{n}', 'revisi':1,'lengan':lengan,'source_sha':source['base_sha'],
            'source_committed':source['committed'],'source_digest':sidik(source),
            'seed':seed,'payload':payload,'content_sha256':h,
            'review':{'status':'belum_ditinjau','content_sha256':h}}


def gate(item):
    """Gate mesin bukan penilai bahasa/psikologi atau bukti review manusia."""
    errors=[]
    try:
        if set(item)!={'id','revisi','lengan','source_sha','source_committed','source_digest','seed','payload','content_sha256','review'}:
            return ['envelope_field']
        if type(item['revisi']) is not int or item['revisi']!=1 or item['lengan'] not in ('A','B','C'):errors.append('envelope_versi')
        if type(item['source_sha']) is not str or re.fullmatch('[0-9a-f]{40}',item['source_sha']) is None:errors.append('source_sha')
        if (type(item['source_committed']) is not bool or type(item['source_digest']) is not str
                or re.fullmatch('[0-9a-f]{64}',item['source_digest']) is None):errors.append('source_snapshot')
        if (item['lengan']=='B' and item['seed'] is not None or
                item['lengan']!='B' and (type(item['seed']) is not int or item['seed']<0)):errors.append('seed')
        if sidik(item['payload'])!=item['content_sha256']:errors.append('hash_konten')
        if item['review']!={'status':'belum_ditinjau','content_sha256':item['content_sha256']}:
            errors.append('review_bukan_draft_terikat')
        pub,guru=item['payload']['publik'],item['payload']['guru']
        if set(item['payload'])!={'publik','guru'} or set(pub)!={'konsep','level','fakta','teks'}:
            errors.append('payload_publik')
        if set(guru)!={'kontrak','kunci','pembahasan','malrule'}:errors.append('payload_guru')
        t,f=pub['konsep'],pub['fakta']
        if (type(item['id']) is not str or type(t) is not str or
                re.fullmatch(re.escape(str(item['lengan'])+'-'+t)+'-[0-5]',item['id']) is None):errors.append('identitas')
        if pub['level']!='P6' or not sah_domain(t,f):return errors+['domain']
        expected=kunci(t,f)
        actual=baca_angka(guru['kunci'])
        if guru['kontrak']!=KONTRAK:errors.append('kontrak')
        if actual!=expected:errors.append('kunci')
        if (not isinstance(pub['teks'],str) or not pub['teks'].strip()
                or not isinstance(guru['pembahasan'],str) or not guru['pembahasan'].strip()):errors.append('teks_kosong')
        # Struktur publik dipagari; kecukupan/makna teks tetap review manusia.
        nilai=[]
        for m in guru['malrule']:
            if set(m)!={'id','jawaban','kode','alasan'}:errors.append('malrule_field');continue
            value=baca_angka(m['jawaban'])
            if m['kode'] not in ('B','K','H','E') or not isinstance(m['alasan'],str) or not m['alasan'].strip():errors.append('malrule_label')
            if value!=prosedur(t,f,m['id']):errors.append('malrule_prosedur')
            if value==actual:errors.append('malrule_kunci')
            nilai.append(value)
        if len(nilai)!=len(set(nilai)):errors.append('malrule_ambigu')
        for buruk in ('1/0','1+2','nan','1e3','1, 2','2 kg','9'*129):
            if baca_angka(buruk) is not None:errors.append('codec_invalid')
        if actual is not None:
            equivalent=f'{actual.numerator*2}/{actual.denominator*2}'
            if baca_angka(equivalent)!=actual:errors.append('codec_equivalent')
    except (KeyError,TypeError,ValueError,ZeroDivisionError,StopIteration,AttributeError):
        errors.append('payload_invalid')
    return sorted(set(errors))


def baca_paket(path):
    """B/C replay dari bytes beku; tidak memanggil generator atau REGISTRI."""
    data=json.loads(Path(path).read_text())
    if (type(data) is not dict or set(data)!={'versi','items','hash','source_manifest'} or type(data['versi']) is not int
            or data['versi']!=1 or type(data['items']) is not list or sidik(data['items'])!=data['hash']):
        raise ValueError('paket tidak utuh')
    source=data['source_manifest']
    if (type(source) is not dict or set(source)!={'base_sha','committed','files'}
            or type(source['committed']) is not bool or type(source['files']) is not dict or not source['files']):
        raise ValueError('provenance source tidak sah')
    identities=set()
    for item in data['items']:
        if gate(item):raise ValueError('item gagal gate')
        if (item['source_digest']!=sidik(source) or item['source_sha']!=source['base_sha']
                or item['source_committed']!=source['committed']):raise ValueError('provenance source tidak cocok')
        ident=(item['id'],item['revisi'])
        if ident in identities:raise ValueError('identitas item duplikat')
        identities.add(ident)
    return data['items']


def _pilih(tid):
    from generator import buat_soal
    hasil=[];dipindai=0
    for n,target in enumerate(CABANG[tid]):
        start=10000+n*4000
        for seed in range(start,start+4000):
            s=buat_soal(tid,seed,'P6',TOPIK[tid]);dipindai+=1
            if target is None or s.parameter.get('op',s.parameter.get('varian'))==target:
                hasil.append((seed,s));break
        else:raise ValueError('cabang blueprint tidak ditemukan')
    return hasil,dipindai


def ekspor(tujuan):
    """Flag eksperimen hanya selama ekspor, juga dipulihkan jika ekspor gagal."""
    flags={'OSN_PENILAIAN_REVISI':'1','OSN_KATALOG_VERSI':'2','OSN_MATEMATIKA_VERSI':'2','OSN_TEORI_BILANGAN_VERSI':'2'}
    lama={k:os.environ.get(k) for k in flags}
    try:
        os.environ.update(flags)
        return _ekspor(tujuan)
    finally:
        for k,v in lama.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v


def _ekspor(tujuan):
    from choice_generation import kandidat
    from generator import buat_soal
    sha=subprocess.check_output(['git','-C',str(AKAR),'rev-parse','HEAD'],text=True).strip()
    source_paths=[*(AKAR/'mesin').glob('*.py'),*(AKAR/'scripts').glob('catalog_pilot*.py')]
    provenance={str(p.relative_to(AKAR)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    # Tracked diff saja tidak menangkap berkas baru; kedua pemeriksaan diperlukan.
    status=subprocess.check_output(['git','-C',str(AKAR),'status','--porcelain','--','mesin','scripts'],text=True)
    source_bersih=not status.strip()
    source={'base_sha':sha,'committed':source_bersih,'files':provenance}
    items=[];scans={};durasi={};pg={};paired={}
    for tid in KONSEP:
        awal=time.perf_counter();pool,jumlah=_pilih(tid);durasi[tid]=time.perf_counter()-awal
        scans[tid]=jumlah
        for n,(seed,s) in enumerate(pool):
            f=fakta(tid,s.parameter)
            for arm in ('A','C'):
                item=bungkus(tid,arm,n,f,s.teks,s.kunci,s.pembahasan,[asdict(m) for m in s.malrule],source,seed)
                items.append(item)
                try:kandidat(s);pg[item['id']]='tersedia'
                except ValueError:pg[item['id']]='kandidat_tidak_cukup'
                if arm=='A':
                    ulang=buat_soal(tid,seed,'P6',TOPIK[tid])
                    assert ulang==s,'replay_generator_berubah'
                else:paired[item['id']]=item['content_sha256']
        for n,(f,key,teks,solusi) in enumerate(ITEM[tid]):
            items.append(bungkus(tid,'B',n,f,teks,key,solusi,[],source))
            pg[items[-1]['id']]='tidak_eligible_tanpa_pengecoh'
    assert len(items)==90
    hasil=[dict(id=i['id'],lengan=i['lengan'],konsep=i['payload']['publik']['konsep'],errors=gate(i),pg=pg[i['id']]) for i in items]
    tujuan.mkdir(parents=True,exist_ok=False)
    (tujuan/'semua-kandidat.json').write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n')
    summaries={}
    for arm in ('A','B','C'):
        subset=[r for r in hasil if r['lengan']==arm]
        lolos=[i for i in items if i['lengan']==arm and not gate(i)]
        paket={'versi':1,'items':lolos,'hash':sidik(lolos),'source_manifest':source}
        file=tujuan/(arm+'-draft.json');file.write_text(json.dumps(paket,ensure_ascii=False,indent=2)+'\n')
        assert baca_paket(file)==lolos
        summaries[arm]={'kandidat':len(subset),'lolos_gate_mesin':len(lolos),'gagal_gate':sum(bool(r['errors']) for r in subset),
                        'terbit':0,'review_manusia':0,'pg_tersedia':sum(r['pg']=='tersedia' for r in subset),
                        'item_bermalrule':sum(bool(i['payload']['guru']['malrule']) for i in lolos),
                        'fakta_unik':len({serial(i['payload']['publik']['fakta'])+i['payload']['publik']['konsep'] for i in lolos}),
                        'menit_authoring':None,'menit_review':None,'menit_revisi':None}
    random.Random(20261021).shuffle(items)
    # ID buta tidak membawa lengan pada paket reviewer. Kunci tersedia hanya guru.
    blinded=[{'nomor':n+1,'payload':i['payload'],'content_sha256':i['content_sha256'],
              'gate_errors':gate(i)} for n,i in enumerate(items)]
    (tujuan/'review-buta.json').write_text(json.dumps(blinded,ensure_ascii=False,indent=2)+'\n')
    (tujuan/'review-map.json').write_text(json.dumps({str(n+1):i['id'] for n,i in enumerate(items)},indent=2)+'\n')
    e=html.escape
    htmls=['<!doctype html><html lang="id"><meta charset="utf-8"><title>Pilot A/B/C</title><h1>90 draf untuk tinjauan buta</h1><p>Belum terbit. Gate mesin tidak menggantikan penilaian bahasa, konteks dan pedagogi manusia.</p>']
    for r in blinded:
        if r['gate_errors']:
            htmls.append('<section><h2>Item '+str(r['nomor'])+'</h2><p>Ditolak gate mesin: '
                         +e(', '.join(r['gate_errors']))+'. Lihat arsip kandidat untuk koreksi.</p></section><hr>')
            continue
        p,g=r['payload']['publik'],r['payload']['guru']
        htmls.append('<section><h2>Item '+str(r['nomor'])+'</h2><p>'+e(p['teks'])+'</p><details><summary>Kunci dan pembahasan</summary><p>'+e(g['kunci'])+'</p><p>'+e(g['pembahasan'])+'</p><ul>')
        for m in g['malrule']:htmls.append('<li>'+e(m['jawaban']+' | '+m['alasan'])+'</li>')
        htmls.append('</ul></details></section><hr>')
    (tujuan/'review.html').write_text('\n'.join(htmls)+'</html>')
    import csv
    with (tujuan/'review.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(('nomor','content_sha256',*RUBRIK_MANUSIA,'catatan'))
        for i in blinded:w.writerow((i['nomor'],i['content_sha256'],*['']*(len(RUBRIK_MANUSIA)+1)))
    report={'versi':1,'source_sha':sha,'source_bersih':source_bersih,'source_hashes':provenance,'lengan':summaries,'hasil_gate':hasil,'dipindai_untuk_cabang':scans,
            'detik_mesin_generasi_AC':durasi,'pair_AC_identik':all(next(x for x in items if x['id']==id.replace('C-','A-',1))['content_sha256']==h for id,h in paired.items()),
            'keputusan':'belum_cukup_bukti_manusia','catatan':'Waktu mesin bukan waktu authoring/review. B authored agent, belum reviewer manusia. A/C hanya beda waktu pembekuan; belum ada seleksi manusia. Tidak mengklaim lengan unggul.'}
    (tujuan/'hasil.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();r=ekspor(args.output)
    print(json.dumps({'source_sha':r['source_sha'],'lengan':r['lengan'],'pair_AC_identik':r['pair_AC_identik'],'keputusan':r['keputusan']},indent=2))
