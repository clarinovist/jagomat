"""Catatan diagnosis yang ditopang prosedur, bukan urutan pilihan."""
from dataclasses import replace
from fractions import Fraction as F

from catalog_exact import format_angka as fmt
from templates import Malrule, saring_malrule


def jaring(soal):
    # Semua pengecoh v2 sama-sama gagal menutup enam muka berbeda. Huruf
    # jawaban tidak memberi bukti salah baca atau salah hitung.
    from solid_geometry_nets import opsi_jaring_v2, JARING_TIDAK_SAH
    p = soal.parameter
    if p.get('versi') != 2:
        raise ValueError('koreksi jaring memerlukan topologi versi 2')
    opsi = opsi_jaring_v2(p['pilihan_benar'], p['urutan'])
    return replace(soal,malrule=tuple(Malrule(
        'jaring.susunan_tidak_sah_' + str(JARING_TIDAK_SAH.index(opsi['ABCDE'.index(m.jawaban)])),
        m.jawaban,'K','memilih susunan yang tidak dapat menutup enam muka kubus berbeda; periksa cara melipatnya')
        for m in soal.malrule))


def pengandaian(soal):
    p=soal.parameter
    nama,kelas,warna,barang=p['nama'],p['kelas'],p['warna'],p['barang']
    if p['varian']=='warna':
        fakta=(f"{nama} adalah siswa kelas {kelas}. Semua siswa kelas {kelas} memakai sepatu "
               f"berwarna {warna}. Dalam soal ini setiap sepatu hanya satu warna.")
        pernyataan=(f"{nama} memakai sepatu berwarna {warna}.",
            f"{nama} memakai sepatu berwarna lain selain {warna}.",
            f"Semua siswa kelas {kelas} memakai sepatu berwarna lain selain {warna}.",
            f"{nama} bukan siswa kelas {kelas}.","Tidak ada siswa yang memakai sepatu.")
        alasan={i:'memilih kesimpulan yang bertentangan dengan fakta tentang kelas dan sepatu' for i in range(1,5)}
        pembahasan=f"{nama} anggota kelas {kelas}. Aturan sepatu berlaku untuk semua anggotanya, jadi {nama} memakai sepatu {warna}. Pilihan lain bertentangan dengan fakta."
    else:
        fakta=f"Setiap hari sekolah {nama} membawa bekal {barang}. Hari ini {nama} bersekolah."
        pernyataan=(f"Hari ini {nama} membawa bekal {barang}.",
            f"Hari ini {nama} juga membawa bekal lain selain {barang}.",
            f"{nama} tidak pernah membawa bekal.",
            f"{nama} membawa {barang} hanya ketika tidak hujan.","Tidak ada siswa yang membawa bekal.")
        alasan={1:'menambah kesimpulan tentang bekal tambahan yang tidak dijamin fakta',
                2:'memilih kesimpulan yang bertentangan dengan kebiasaan membawa bekal',
                3:'menambah syarat cuaca yang tidak dijamin fakta',
                4:'memilih kesimpulan yang bertentangan dengan adanya siswa yang membawa bekal'}
        pembahasan=f"Hari ini termasuk hari sekolah bagi {nama}. Maka kebiasaan membawa {barang} berlaku hari ini. Bekal tambahan dan cuaca tidak dijelaskan, sehingga tidak dapat disimpulkan."
    urutan=p['urutan_tampil']
    if sorted(urutan)!=list(range(5)) or urutan[p['pilihan_benar']]!=0:
        raise ValueError('urutan pengandaian tidak konsisten')
    mal=tuple(Malrule(f'pengandaian.{p["varian"]}_{i}', 'ABCDE'[pos], 'K', alasan[i])
              for pos,i in enumerate(urutan) if i)
    teks=fakta+'\nManakah pernyataan yang PASTI benar?\n'+'\n'.join(
        f"{'ABCDE'[pos]}. {pernyataan[i]}" for pos,i in enumerate(urutan))
    return replace(soal,teks=teks,malrule=mal,pembahasan=pembahasan+f' Jawabannya {soal.kunci}.')


def jumlah_deret(soal):
    p=soal.parameter
    akhir=p['awal']+(p['n']-1)*p['beda']
    mal=[replace(m,jawaban=fmt(F(p['awal']+akhir,2)))
         if m.id=='jumlah_deret.rata_rata_ujung_tanpa_kali_n' else m for m in soal.malrule]
    return replace(soal,malrule=saring_malrule(soal.kunci,mal))


def kotak(soal):
    p,l=soal.parameter['p'],soal.parameter['l']
    tepi=p*l-max(0,p-2)*max(0,l-2)
    mal=[replace(m,jawaban=str(tepi),kode='K',alasan='menghitung hanya kotak-kotak pada tepi, bukan seluruh kotak pengisi')
         if m.id=='datar.hitung_keliling' else m for m in soal.malrule]
    return replace(soal,malrule=saring_malrule(soal.kunci,mal))


def satuan(soal):
    p=soal.parameter
    src,dst=p['varian'].split('_ke_')
    waktu={src,dst}=={'jam','menit'}
    faktor=60 if waktu else 1000
    besar=src in ('km','jam','kg','liter')
    relasi='1 jam = 60 menit' if waktu else {
        frozenset({'km','m'}):'1 km = 1000 m',frozenset({'kg','g'}):'1 kg = 1000 g',
        frozenset({'liter','ml'}):'1 liter = 1000 ml'}[frozenset({src,dst})]
    operasi='×' if besar else ':'
    return replace(soal,pembahasan=f"{relasi}. Jadi {p['nilai']} {src} = {p['nilai']} {operasi} {faktor} = {soal.kunci} {dst}.")


def korek(soal):
    p=soal.parameter
    contoh=', '.join(str(p['awal']+p['tambah']*i) for i in range(3))
    teks=(f"Pola batang korek api bertumbuh. Gambar 1, 2, 3 memakai {contoh} batang. "
          f"Setiap langkah menambah {p['tambah']} batang. Gambar ke-{p['gambar_ke']} membutuhkan berapa batang?")
    mal=tuple(replace(m,alasan='menganggap setiap langkah membutuhkan sebanyak batang gambar awal, bukan hanya tambahan')
              if m.id=='korek.tidak_sadar_batang_bersama' else m for m in soal.malrule)
    return replace(soal,teks=teks,malrule=mal)
