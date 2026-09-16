"""Kebijakan PG per pola; tidak mengubah generator atau malrule isian."""
from dataclasses import replace
import random
import re

from generator import Lembar, buat_lembar
from multiple_choice import buat_pilihan, pilihan_tertanam, nilai_semantis
from topics import paket_untuk_template

TERTANAM = frozenset({'benar_salah_pengandaian', 'jaring_jaring'})
TIGA = frozenset({'deret_geometri', 'simetri_bangun', 'prima_faktorisasi',
                  'susun_bilangan_syarat', 'unsur_bangun', 'luas_permukaan',
                  'luas_arsiran', 'jam_selesai'})


def kebijakan_soal(soal):
    """Jumlah tetap menurut pola/cabang, tidak menurut kandidat yang selamat."""
    tid, p = soal.template_id, soal.parameter
    if tid in TERTANAM:
        return 'tertanam-lima-v1', 'kategori'
    if tid == 'deret_aritmetika' and p.get('n_minta', 1) > 1:
        return 'empat-v1', 'daftar_bulat'
    if tid == 'urut_pecahan_desimal_persen':
        return 'empat-v1', 'urutan_bilangan'
    if tid == 'jam_selesai':
        return 'tiga-v1', 'durasi' if p['varian'] == 'cari_durasi' else 'jam'
    if tid == 'skala_peta' and p['varian'] == 'cari_skala':
        return 'empat-v1', 'rasio'
    if tid in {'siklus_huruf', 'siklus_warna', 'sisa_bagi_siklus'}:
        return ('tiga-v1' if len(set(p['pola'])) <= 3 else 'empat-v1'), 'kategori'
    if tid == 'tabel_penalaran':
        return ('tiga-v1' if len(p['urutan']) == 3 else 'empat-v1'), 'kategori'
    if tid == 'siklus_hari' or tid == 'tabel_turus' and p['varian'] == 'terbanyak':
        return 'empat-v1', 'kategori'
    return ('tiga-v1' if tid in TIGA else 'empat-v1'), 'angka'


def opsi_asal(teks):
    """Ambil A–E publik dari teks, bukan parameter penanda kebenaran."""
    pola = r'^([A-E])\.\s*(.*?)(?=^[A-E]\.\s|\Z)'
    cocok = list(re.finditer(pola, teks, re.M | re.S))
    if [m.group(1) for m in cocok] != list('ABCDE'):
        raise ValueError('Lima pilihan asal belum dapat disajikan.')
    hasil = [m.group(2).strip() for m in cocok]
    # Jaring versi2 memiliki pertanyaan penutup, bukan bagian pilihan E.
    hasil[-1] = hasil[-1].split('\nSusunan manakah')[0].strip()
    return tuple(hasil)


def kandidat(soal):
    """Pengecoh dari kesalahan terdaftar atau kategori yang benar-benar ada."""
    kebijakan, jenis = kebijakan_soal(soal)
    if kebijakan == 'tertanam-lima-v1':
        return kebijakan, jenis, opsi_asal(soal.teks)
    nilai = [m.jawaban for m in soal.malrule]
    p, tid = soal.parameter, soal.template_id
    if tid in {'siklus_huruf', 'siklus_warna', 'sisa_bagi_siklus'}:
        nilai += list(p['pola'])
    elif tid == 'tabel_penalaran':
        nilai += list(p['urutan'])
    elif tid == 'tabel_turus' and p['varian'] == 'terbanyak':
        nilai += list(p['nama'])
    elif tid == 'unsur_bangun' and p['bangun'] == 'tabung' and p['tanya'].startswith('titik'):
        # Menghitung dua lingkaran alas/tutup sebagai titik sudut, per tabung.
        nilai.append(str(2 * (p.get('n', 1) if p['tanya'].endswith('_kali') else 1)))
    elif tid == 'siklus_hari':
        from templates import HARI
        nilai += HARI
    benar = nilai_semantis(soal.kunci, jenis)
    terpakai = {benar}
    bersih = []
    for teks in nilai:
        try:
            n = nilai_semantis(teks, jenis)
        except ValueError:
            continue
        if isinstance(benar, tuple) and len(n) != len(benar):
            continue
        if jenis == 'angka' and benar >= 0 and n < 0:
            continue
        if n not in terpakai:
            bersih.append(teks)
            terpakai.add(n)
    jumlah = 2 if kebijakan == 'tiga-v1' else 3
    if len(bersih) < jumlah:
        raise ValueError('Pengecoh yang layak belum cukup untuk pola ini.')
    return kebijakan, jenis, tuple(bersih[:jumlah])


def pilihan_soal(soal, sid, sidik, seed, nomor):
    kebijakan, jenis, nilai = kandidat(soal)
    arg = dict(sesi_soal_id=sid, fingerprint_pertanyaan=sidik, kunci=soal.kunci)
    if kebijakan == 'tertanam-lima-v1':
        return pilihan_tertanam(**arg, teks_opsi=nilai)
    return buat_pilihan(**arg, kebijakan=kebijakan, jenis=jenis, pengecoh=nilai,
                       seed=seed, identitas=f'{soal.tanda_tangan}|{nomor}')


def buat_lembar_pilihan(seed, *, level, topik, jumlah_soal=None):
    """Pertahankan komposisi; retry hanya cabang dan jumlah opsi yang sama."""
    lembar = buat_lembar(seed, level=level, topik=topik, jumlah_soal=jumlah_soal)
    hasil = []
    for nomor, awal in enumerate(lembar.soal, 1):
        soal = awal
        rng = random.Random(f'pg-v1|{seed}|{nomor}')
        paket = paket_untuk_template([awal.template_id])
        cabang = {k: awal.parameter[k] for k in ('varian', 'tanya', 'bangun', 'n_minta') if k in awal.parameter}
        kebijakan = kebijakan_soal(awal)
        for _ in range(500):
            try:
                kandidat(soal)
                break
            except ValueError:
                pass
            baru = replace(paket.templates[awal.template_id](**paket.parameter_untuk(awal.template_id, rng, lembar.level)), level=lembar.level)
            if kebijakan_soal(baru) == kebijakan and all(baru.parameter.get(k) == v for k, v in cabang.items()):
                soal = baru
        else:
            raise ValueError('Pilihan ganda belum tersedia untuk komposisi ini. Gunakan isian dahulu.')
        hasil.append(soal)
    return Lembar(seed, tuple(hasil), lembar.level)
