"""Kebijakan PG per pola; tidak mengubah generator atau malrule isian."""
from dataclasses import replace
import random
import re

from awal_pola_posisi import pengecoh_tambahan as pengecoh_pola_posisi
from awal_ukur_satuan_tak_baku import pengecoh_tambahan as pengecoh_ukur_satuan_tak_baku
from awal_unsur_bangun_datar import pengecoh_tambahan as pengecoh_unsur_bangun_datar
from generator import Lembar, buat_lembar
from multiple_choice import SIMBOL_PERBANDINGAN, buat_pilihan, pilihan_tertanam, nilai_semantis
from topics import paket_untuk_template

TERTANAM = frozenset({'benar_salah_pengandaian', 'jaring_jaring'})
TIGA = frozenset({'deret_geometri', 'simetri_bangun', 'prima_faktorisasi',
                  'susun_bilangan_syarat', 'unsur_bangun', 'luas_permukaan',
                  'luas_arsiran', 'jam_selesai',
                  # Dua pengecoh selalu sah; collision tidak diisi angka rekaan.
                  'tambah_dasar', 'kurang_dasar', 'bilangan_hilang', 'nilai_tempat',
                  # Dua jalur K selalu ada (angka saja, tempat sebelah); H hanya kadang ada.
                  'nilai_tempat_besar',
                  # Tahap B: jalur K selalu ada dan H hanya kadang; 2 pengecoh cukup.
                  'tambah_kurang_bersusun', 'kali_bagi_sekolah', 'kalimat_matematika',
                  # Matematika Awal: pengecoh = bangun lain di himpunan level (K) atau salah hitung sisi.
                  'kenali_bentuk',
                  # Matematika Awal lanjutan: jalur K/H dari malrule (atau benda lain di soal) selalu >= 2 per
                  # parameter domain; 'empat-v1' tidak terjamin. ukur_konversi_awal tetap 'empat-v1' (>= 3).
                  'ukur_satuan_tak_baku', 'baca_diagram_gambar', 'pola_posisi', 'pecahan_setengah',
                  'waktu_berat_awal', 'turus_gambar_awal', 'bandingkan_ciri_bangun',
                  # Matematika Awal gelombang 1: 2 pengecoh dari malrule selalu ada; 'empat-v1' tidak terjamin
                  # (bilang_benda_awal: `empat-v1` kurang di sebagian parameter; pecahan_senilai_desimal: 23 dari
                  # 275 parameter hanya punya 2 pengecoh berbeda nilai).
                  'bilang_benda_awal', 'pecahan_senilai_desimal',
                  # kenali_bangun_awal: hitung_bentuk (kunci angka) selalu punya >= 2 pengecoh dari malrule
                  # (jenis lain, semua bangun, lebih satu); 'empat-v1' tidak terjamin (hanya dua pengecoh pada
                  # 9 dari 1143 parameter P1 dan 48 dari 2424 parameter P2).
                  'kenali_bangun_awal'})
# Kunci kategori (nama/kata/benda) per jenis Matematika Awal; sisanya jatuh ke 'angka'.
KATEGORI_AWAL = {
    'ukur_satuan_tak_baku': frozenset({'banding'}),
    'baca_diagram_gambar': frozenset({'terbanyak'}),
    'turus_gambar_awal': frozenset({'terbanyak'}),
    'peluang_dasar': frozenset({'lebih_mungkin', 'kepastian'}),
    'bilang_benda_awal': frozenset({'angka_ke_kata'}),  # kunci kata bilangan huruf kecil
    # kenali_bangun_awal: tiga varian berkunci nama bangun; hitung_bentuk berkunci angka (tiga opsi).
    'kenali_bangun_awal': frozenset({'datar_gambar', 'ruang_gambar', 'benda_ruang'}),
}


def kebijakan_soal(soal):
    """Jumlah tetap menurut pola/cabang, tidak menurut kandidat yang selamat."""
    tid, p = soal.template_id, soal.parameter
    if tid in TERTANAM:
        return 'tertanam-lima-v1', 'kategori'
    if tid == 'deret_aritmetika' and p.get('n_minta', 1) > 1:
        return 'empat-v1', 'daftar_bulat'
    if tid == 'urut_pecahan_desimal_persen':
        return 'empat-v1', 'urutan_bilangan'
    if tid == 'bandingkan_bilangan':
        return 'tiga-v1', 'simbol_perbandingan'
    if tid == 'kenali_bentuk' and p['varian'] != 'banyak_sisi':
        return 'tiga-v1', 'kategori'  # kunci nama bangun; banyak_sisi jatuh ke 'angka'
    if tid == 'pola_posisi':
        return 'tiga-v1', 'kategori'  # semua varian: kunci satu kata huruf kecil
    if tid == 'unsur_bangun_datar' and p['varian'] == 'istilah':
        return 'tiga-v1', 'kategori'  # kunci "sejajar"/"tegak lurus"; pengecoh malrule + "miring"
    if tid == 'ciri_komposisi_bangun' and (
            p['varian'] == 'uraikan_nama'
            or (p['varian'] == 'dua_persegi' and p['tanya'] == 'nama')
            or p.get('tanya') in ('jenis_tiga_sama', 'jenis_dua_sama', 'jenis_siku')):
        return 'tiga-v1', 'kategori'  # kunci nama bangun; varian berkunci angka jatuh ke 'empat-v1'
    if p.get('varian') in KATEGORI_AWAL.get(tid, ()):
        return 'tiga-v1', 'kategori'  # kunci nama benda/kategori/kata
    if tid == 'peluang_dasar':
        # banyak_hasil: kunci angka, 2 pengecoh; peluang_pecahan: kunci "3/5", 4 pengecoh murni malrule.
        return ('tiga-v1' if p['varian'] == 'banyak_hasil' else 'empat-v1'), 'angka'
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
    elif tid == 'urutkan_bilangan':
        # Pengecoh sah: bilangan lain yang memang tertulis di soal (kunci dibuang oleh saringan).
        nilai += [str(x) for x in p['bilangan']]
    elif tid == 'pola_posisi':
        # Pengecoh sah: benda lain yang ada di soal/himpunan soal (periode 2 hanya punya 1 malrule).
        nilai += list(pengecoh_pola_posisi(p))
    elif tid == 'ukur_satuan_tak_baku':
        # Varian banding hanya punya satu malrule (benda lebih pendek); tambahan "sama panjang"
        # bukan hipotesis kesalahan, jadi tidak masuk malrule.
        nilai += list(pengecoh_ukur_satuan_tak_baku(p))
    elif tid == 'unsur_bangun_datar':
        # istilah: "miring" bukan hipotesis kesalahan, jadi tidak masuk malrule.
        nilai += list(pengecoh_unsur_bangun_datar(p))
    elif tid == 'bandingkan_bilangan':
        # Tiga opsi tetap <, >, = ; dua pengecoh = dua simbol lain, bukan dari malrule.
        nilai += list(SIMBOL_PERBANDINGAN)
    elif tid == 'median_modus' and p['varian'] == 'modus':
        # PG boleh menawarkan nilai lain yang benar-benar ada di data.
        # Tidak menambah label miskonsepsi pada malrule isian.
        nilai += [str(x) for x in p['data']]
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
