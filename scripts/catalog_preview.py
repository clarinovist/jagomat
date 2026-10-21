#!/usr/bin/env python3
"""Bekukan contoh katalog sintetis untuk tinjauan manusia; tanpa DB/provider."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import html
import json
import os
from pathlib import Path
import subprocess
import sys

AKAR = Path(__file__).resolve().parents[1]


def ekspor(tujuan):
    """Jalankan pada proses CLI terisolasi agar flag tidak bocor ke aplikasi."""
    os.environ.update(OSN_KATALOG_VERSI='2', OSN_MATEMATIKA_VERSI='2', OSN_TEORI_BILANGAN_VERSI='2')
    sys.path.insert(0, str(AKAR/'mesin'))
    from catalog_versions import TEMPLATE_DIPERBAIKI
    from generator import buat_soal
    from topics import daftar_topik, ambil
    contoh=[]
    for topik in daftar_topik():
        if topik=='campuran':continue
        paket=ambil(topik)
        for tid in sorted(set(paket.templates)&TEMPLATE_DIPERBAIKI):
            level=next(lv for lv,tids in paket.komposisi.items() if tid in tids)
            varian=set()
            for seed in range(100):
                soal=buat_soal(tid,seed,level,topik)
                p=soal.parameter
                bentuk=(p.get('varian'),p.get('tanya'),p.get('bangun'))
                if bentuk in varian:continue
                varian.add(bentuk)
                contoh.append(dict(seed=seed,topik=topik,soal=asdict(soal)))
    serial=json.dumps(contoh,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    sha=subprocess.check_output(['git','-C',str(AKAR),'rev-parse','HEAD'],text=True).strip()
    bersih=subprocess.run(['git','-C',str(AKAR),'diff','--quiet','HEAD','--','mesin','scripts/catalog_preview.py'])
    if bersih.returncode not in (0,1):raise RuntimeError('gagal memeriksa provenance')
    manifest=dict(source_sha=sha,source_bersih=bersih.returncode==0,
        konten_sha256=hashlib.sha256(serial.encode()).hexdigest(),
        status='menunggu_tinjauan_manusia',jumlah_template=len(TEMPLATE_DIPERBAIKI),contoh=contoh)
    tujuan.mkdir(parents=True,exist_ok=False)
    (tujuan/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    e=html.escape
    blok=['<!doctype html><html lang="id"><meta charset="utf-8"><title>Tinjauan katalog</title>',
          '<h1>Katalog A–C: tinjauan manusia belum selesai</h1>',
          '<p>Contoh sintetis, bukan hasil anak. Periksa kunci, prosedur malrule, konteks, bahasa dan pembahasan.</p>']
    for c in contoh:
        s=c['soal']
        blok.append('<section><h2>'+e(s['template_id']+' / '+s['level']+' / seed '+str(c['seed']))+'</h2><pre>'+e(s['teks'])+'</pre>')
        blok.append('<p>Kunci: <b>'+e(s['kunci'])+'</b></p><p>'+e(s['pembahasan'])+'</p><ul>')
        for m in s['malrule']:
            blok.append('<li>'+e(m['kode']+' | '+m['jawaban']+' | '+m['alasan'])+'</li>')
        blok.append('</ul></section><hr>')
    blok.append('</html>')
    (tujuan/'tinjauan.html').write_text('\n'.join(blok))
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--require-committed',action='store_true')
    args=parser.parse_args()
    m=ekspor(args.output)
    if args.require_committed and not m['source_bersih']:
        raise SystemExit('Source tinjauan tidak sesuai commit.')
    print(json.dumps({k:m[k] for k in ('source_sha','konten_sha256','jumlah_template','status')}))


if __name__=='__main__':main()
