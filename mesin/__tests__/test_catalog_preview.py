"""Artefak review katalog memakai data sintetis, SHA/hash dan status belum disetujui."""
import json
import os
from pathlib import Path
import subprocess
import sys

AKAR=Path(__file__).resolve().parents[2]


def test_ekspor_katalog_deterministik_dan_umur_sah(tmp_path):
    manifest=[]
    for nama in ('a','b'):
        tujuan=tmp_path/nama
        hasil=subprocess.run([sys.executable,'-B',str(AKAR/'scripts/catalog_preview.py'),
            '--output',str(tujuan)],capture_output=True,text=True,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=30)
        assert hasil.returncode==0,hasil.stderr
        m=json.loads((tujuan/'manifest.json').read_text())
        assert m['status']=='menunggu_tinjauan_manusia' and m['jumlah_template']==26
        assert len(m['source_sha'])==40 and len(m['konten_sha256'])==64
        umur=[c['soal'] for c in m['contoh'] if c['soal']['template_id']=='soal_umur']
        assert umur
        assert all('ayah' not in s['teks'] and 'Ari' in s['teks'] and 'Bima' in s['teks'] for s in umur)
        assert (tujuan/'tinjauan.html').exists()
        manifest.append(m)
    assert manifest[0]==manifest[1]
