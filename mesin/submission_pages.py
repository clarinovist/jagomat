"""Halaman refleksi opsional anak tanpa kunci, diagnosis, atau layanan AI."""
from html import escape

import brand
import student_submissions as kiriman
import students
import visual_renderer
from style_stitch import gaya_stitch


def halaman_refleksi(kon, siswa_id, sesi_id, jalur_aksi):
    info = students.sesi_murid(kon, siswa_id, sesi_id)
    if not info or info['selesai']:
        return None
    ids = set(kiriman.kosong(kon, sesi_id))
    alasan = kiriman.refleksi(kon, sesi_id)
    kartu = []
    for soal in students.soal_murid(kon, sesi_id, siswa_id):
        sid = soal['sesi_soal_id']
        if sid not in ids:
            continue
        cara = (soal['terjawab'] or {}).get('cara', '')
        if cara.startswith('[pilihan] bingung'):
            catatan = '<p>Kamu sudah mencatat: aku bingung. Kalau bisa, pilih bagian yang membingungkan.</p>'
        elif cara:
            catatan = '<p>Caramu sudah tersimpan; jawaban akhir belum diisi.</p>'
        else:
            catatan = '<p>Jawaban akhir belum diisi.</p>'
        pilihan = ''.join(
            f'<label class="kerja-pill-st"><input type="radio" name="alasan_kosong_{sid}" value="{nilai}"'
            f'{" checked" if alasan.get(sid) == nilai else ""}><span>{escape(label)}</span></label>'
            for nilai, label in [('', 'Belum ingin memberi alasan'), *kiriman.ALASAN.items()]
        )
        kartu.append(
            '<section class="kerja-soal-st">'
            f'<h2>Soal {soal["nomor"]}</h2>'
            + visual_renderer.render_pertanyaan(soal['penyajian'], gaya='stitch', namespace=str(soal['nomor']))
            + catatan + '<fieldset class="kerja-cara-pilih-st"><legend>Alasan (boleh tidak diisi)</legend>'
            f'<div class="refleksi-pilihan-st">{pilihan}</div></fieldset></section>'
        )
    foto = kon.execute('SELECT 1 FROM lampiran WHERE sesi_id=? LIMIT 1', (sesi_id,)).fetchone()
    petunjuk_foto = ('<p>Isian digital masih kosong; jawaban mungkin ada di foto. '
                     'Tidak perlu mengetik ulang jawaban dari foto.</p>' if foto else '')
    return (f'<!doctype html><html lang="id"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{brand.judul("Sebelum dikirim")}</title>'
            f'<style>{gaya_stitch()}</style></head><body class="st kerja-editorial-st">'
            '<main class="kerja-badan-st"><h1>Ada jawaban yang masih kosong. Tidak apa-apa.</h1>'
            '<p>Jawaban tersimpan sementara. Latihan belum dikirim.</p>'
            '<p>Kalau kamu bisa, ceritakan apa yang membuatmu belum menjawab.</p>'
            + petunjuk_foto + f'<form method="post" action="{escape(jalur_aksi, quote=True)}">'
            f'<input type="hidden" name="revisi_pekerjaan" value="{kiriman.revisi(kon, sesi_id)}">'
            '<input type="hidden" name="flow_kosong" value="1">' + ''.join(kartu)
            + '<p>Boleh tanpa mengisi alasan.</p><div class="kerja-simpan-strip-st">'
            '<button class="sekunder" name="aksi" value="kembali" type="submit">Kembali mengerjakan</button>'
            '<button name="aksi" value="kirim_latihan" type="submit">Kirim latihan</button>'
            '</div></form></main></body></html>').encode()
