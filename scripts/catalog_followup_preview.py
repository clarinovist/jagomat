"""Ekspor contoh sintetis revisi2 untuk review manusia; bukan aktivasi/pengesahan."""
from dataclasses import asdict
from hashlib import sha256
from html import escape
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'mesin'))
from generator import buat_soal
from topics import ambil

TARGET = {'satuan_kuantitas': 'pengukuran', 'rata_rata': 'statistika',
          'luas_arsiran': 'geometri-datar'}


def ekspor(output):
    """Simpan pasangan sebelum/sesudah tiap varian; jangan menimpa review lama."""
    output.mkdir(parents=True, exist_ok=False)
    flags = {'OSN_KATALOG_LANJUTAN': '0', 'OSN_KATALOG_VERSI': '2',
             'OSN_MATEMATIKA_VERSI': '2', 'OSN_PENILAIAN_REVISI': '0'}
    lama_env = {k: os.environ.get(k) for k in flags}
    rows = []
    try:
        os.environ.update(flags)
        for tid, topik in TARGET.items():
            for level, ids in ambil(topik).komposisi.items():
                if tid not in ids:
                    continue
                seen = set()
                for seed in range(600):
                    os.environ['OSN_KATALOG_LANJUTAN'] = '0'
                    lama = buat_soal(tid, seed, level, topik)
                    p = lama.parameter
                    varian = (p['satuan'] + '/' + p['arah'] if tid == 'satuan_kuantitas'
                              else p['varian'])
                    if varian in seen:
                        continue
                    seen.add(varian)
                    os.environ['OSN_KATALOG_LANJUTAN'] = '1'
                    baru = buat_soal(tid, seed, level, topik)
                    rows.append(dict(template=tid, level=level, seed=seed, varian=varian,
                                     lama=asdict(lama), draf=asdict(baru)))
    finally:
        for k, v in lama_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    source = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                            check=True, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain'],
                           check=True, capture_output=True, text=True).stdout.strip()
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    digest = sha256(payload).hexdigest()
    manifest = dict(source_sha=source, source_committed=not bool(dirty),
                    content_sha256=digest, jumlah=len(rows), status='draf',
                    reviewer=None, disahkan=False)
    (output / 'contoh.json').write_bytes(payload)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    body = ['<!doctype html><html lang="id"><meta charset="utf-8"><title>Draf audit katalog</title>',
            '<h1>DRAF — belum direview manusia</h1>',
            '<p>Ini contoh sintetis, bukan data anak. Tidak mengaktifkan revisi2. '
            'Periksa setiap prosedur, kode, bahasa dan batas varian. Setuju/ubah/tolak '
            'harus dicatat manusia atas hash konten exact ini.</p>',
            '<p>SHA isi: <code>' + digest + '</code></p>']
    for row in rows:
        body.append('<hr><h2>' + escape(f"{row['template']} / {row['level']} / {row['varian']} / seed {row['seed']}") + '</h2>')
        for key, label in (('lama', 'Saat ini'), ('draf', 'Draf revisi2')):
            s = row[key]
            body.append('<h3>' + label + '</h3><p>' + escape(s['teks']) + '</p>')
            body.append('<p>Kunci: <b>' + escape(s['kunci']) + '</b></p>')
            body.append('<p>' + escape(s['pembahasan']) + '</p><ul>')
            for m in s['malrule']:
                body.append('<li>' + escape(f"{m['id']} · {m['kode']} · {m['jawaban']} — {m['alasan']}") + '</li>')
            body.append('</ul>')
        body.append('<p>Keputusan manusia: __________ Alasan/koreksi: __________</p>')
    body.append('</html>')
    (output / 'review.html').write_text('\n'.join(body), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(ekspor(args.output), ensure_ascii=False))


if __name__ == '__main__':
    main()
