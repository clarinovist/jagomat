"""Koreksi prosedur malrule Batch B; tidak menggeser angka untuk mengisi quota."""
from dataclasses import replace
from fractions import Fraction as F
import math

from catalog_exact import format_angka as fmt
from templates import Malrule, saring_malrule


def _hasil(soal, kandidat, h_id, langkah=None):
    """Kandidat K tetap literal prosedurnya; H hanya ±1 yang belum terpakai."""
    mal = [Malrule(ident, fmt(nilai), kode, alasan) for ident, nilai, kode, alasan in kandidat]
    terpakai = {soal.kunci, *(m.jawaban for m in mal)}
    kunci = F(soal.kunci.replace(',', '.'))
    for h in (kunci - 1, kunci + 1):
        if h >= 0 and fmt(h) not in terpakai:
            mal.append(Malrule(h_id, fmt(h), 'H', 'perhitungan benar, hasilnya meleset satu'))
            break
    return replace(soal, malrule=saring_malrule(soal.kunci, mal),
                   pembahasan=langkah if langkah is not None else soal.pembahasan)


def statistika(soal):
    tid,p = soal.template_id,soal.parameter
    d,v,i = p.get('data',[]),p.get('varian'),p.get('i',0)
    if tid == 'median_modus':
        if v == 'modus':
            return soal
        n=len(d)
        tengah=F(d[n//2]) if n%2 else F(d[n//2-1]+d[n//2],2)
        k=(('median.tanpa_urut',tengah,'K','mengambil nilai tengah tanpa mengurutkan data'),
           ('median.terkecil',min(d),'K','menjawab data terkecil, bukan median'))
        prefix='median'
    elif tid == 'rata_rata_gabungan':
        total=p['n1']*p['x1']+p['n2']*p['x2']
        k=(('gabung.total_saja',total,'K','menjumlahkan total kedua kelompok tanpa membagi'),
           ('gabung.rata_rata_rata',F(p['x1']+p['x2'],2),'K','merata-ratakan dua rata-rata tanpa memperhitungkan jumlah data'))
        prefix='gabung'
    elif tid == 'diagram_batang_garis':
        n=len(d)
        if v=='baca':
            k=(('batang.baca_tetangga',d[(i+1)%n],'K','membaca batang berikutnya, bukan batang yang ditanya'),
               ('batang.baca_lain',d[(i+2)%n],'K','membaca batang dua posisi berikutnya, bukan batang yang ditanya'))
        elif v=='jumlah':
            k=(('batang.terbesar',max(d),'K','menjawab batang terbesar, bukan jumlah'),
               ('batang.lupa_pertama',sum(d)-d[0],'K','menjumlahkan dengan melupakan batang pertama'))
        else:
            k=(('batang.jumlah_dua',d[i]+d[(i+1)%n],'K','menjumlahkan dua batang padahal yang diminta selisih'),
               ('batang.selisih_lain',abs(d[i]-d[(i+2)%n]),'K','menghitung selisih batang yang ditanya dengan batang dua posisi berikutnya'))
        prefix='batang'
    elif tid=='tabel_turus':
        if v=='terbanyak':
            return soal
        if v=='baca':
            a,b=d[(i+1)%len(d)],d[(i+2)%len(d)]
            alasan=('membaca baris berikutnya, bukan baris yang ditanya','membaca baris dua posisi berikutnya, bukan baris yang ditanya')
        else:
            a,b=max(d),sum(d)-d[0]
            alasan=('menjawab baris terbesar, bukan jumlah','menjumlahkan dengan melupakan baris pertama')
        k=(('turus.salah_baris',a,'K',alasan[0]),('turus.salah_baris2',b,'K',alasan[1]))
        prefix='turus'
    elif tid=='piktogram':
        d,u=p['gambar'],p['satuan']
        if v=='baca':
            a,b=d[i],d[i]+u
            alasan=('menjawab banyak gambar, lupa nilai satu gambar','menambahkan nilai satu gambar, bukan mengalikan')
        elif v=='total':
            a,b=sum(d),max(d)*u
            alasan=('menjumlahkan gambar tanpa mengalikan nilai satu gambar','menghitung baris terbesar saja, bukan seluruhnya')
        else:
            a,b=abs(d[i]-d[(i+1)%len(d)]),(d[i]+d[(i+1)%len(d)])*u
            alasan=('menjawab selisih gambar tanpa mengalikan nilai satu gambar','menjumlahkan dua baris padahal yang diminta selisih')
        k=(('pikto.lupa_skala',a,'K',alasan[0]),('pikto.salah_operasi',b,'K',alasan[1]))
        prefix='pikto'
    else:
        if v=='terbesar':
            a,b=min(d),sorted(d)[-2]
            alasan=('menjawab nilai terkecil, bukan terbesar','menjawab data urutan kedua dari akhir setelah diurutkan')
        elif v=='terkecil':
            a,b=max(d),sorted(d)[1]
            alasan=('menjawab nilai terbesar, bukan terkecil','menjawab data urutan kedua setelah diurutkan')
        else:
            a,b=max(d)+min(d),max(d)
            alasan=('menjumlahkan nilai terbesar dan terkecil, bukan menguranginya','menjawab nilai terbesar, bukan selisihnya')
        k=(('jangkau.arah_salah',a,'K',alasan[0]),('jangkau.hampir',b,'K',alasan[1]))
        prefix='jangkau'
    return _hasil(soal,k,prefix+'.kurang_satu')


def jumlah_selisih(soal):
    p=soal.parameter
    j,s,t=p['jumlah'],p['selisih'],p['tanya']
    lain=F(j-s if t=='besar' else j+s,2)
    return _hasil(soal, (
        ('jumlah_selisih.terbalik_'+t,lain,'K','menjawab bilangan yang lain (terbalik besar/kecil)'),
        ('jumlah_selisih.lupa_bagi_'+t,j-s,'K','menghitung jumlah−selisih tanpa membagi dua')),
        'jumlah_selisih.kurang_satu')


def fpb(soal):
    a,b=soal.parameter['a'],soal.parameter['b']
    terbesar=math.gcd(a,b)
    # Cari pembagi sejati, bukan floor(FPB/2) yang bisa bukan faktor.
    kecil=next((d for d in range(terbesar//2,0,-1) if a%d==b%d==0),None)
    k=[('fpb.tertukar_dengan_kpk',math.lcm(a,b),'B','menjawab KPK padahal yang diminta FPB')]
    if kecil is not None:
        k.append(('fpb.salah_pilih_faktor_bersama',kecil,'K','berhenti pada faktor bersama kecil, belum mencari yang terbesar'))
    return _hasil(soal,k,'fpb.faktor_terbesar_kurang_satu')


def prisma(soal):
    p=soal.parameter
    if p['varian'] not in ('prisma_V','prisma_balik'):
        if p.get('versi') != 2:
            raise ValueError('katalog tabung memerlukan matematika versi 2')
        return soal
    a,t=p['a'],p['t_segitiga']
    if p['varian']=='prisma_balik':
        kunci=F(2*p['V'],a*t)
        nilai=(F(p['V'],a*t),F(p['V'],a+t))
        alasan=('lupa membagi dua luas alas segitiga sebelum membagi volume dengan luas alas',
                'membagi volume dengan jumlah alas dan tinggi segitiga, bukan luas alas')
        langkah=f"Luas alas = {a} × {t} : 2 = {fmt(F(a*t,2))}. Tinggi prisma = {p['V']} : {fmt(F(a*t,2))} = {fmt(kunci)} cm."
    else:
        kunci=F(a*t*p['t_prisma'],2)
        nilai=(a*t*p['t_prisma'],a*p['t_prisma'])
        alasan=('lupa membagi dua pada luas alas segitiga','mengalikan alas segitiga dengan tinggi prisma saja')
        langkah=f"Volume = luas alas × tinggi prisma = {a} × {t} : 2 × {p['t_prisma']} = {fmt(kunci)} cm³."
    return _hasil(replace(soal,kunci=fmt(kunci)), (
        ('volprisma.lupa_setengah_segitiga',nilai[0],'K',alasan[0]),
        ('volprisma.rumus_lain_segitiga',nilai[1],'K',alasan[1])), 'volprisma.kurang_satu',langkah)


def unsur(soal):
    from topic_solid_geometry import BANGUN, TANYA_INDEKS, TERTUKAR
    p=soal.parameter
    b,t=p['bangun'],p['tanya']
    ix=TANYA_INDEKS[t.replace('_kali','')]
    nilai=BANGUN[b][ix]
    if t.endswith('_kali'):
        n=p['n']
        k=[('unsur.kali_lupa_'+b,nilai,'K',f'menjawab jumlah satu bangun, bukan {n} bangun'),
           ('unsur.kali_lebih_'+b,nilai*(n+1),'K',f'menghitung {n+1} bangun, bukan {n}')]
        h='unsur.kali_kurang_'+b
        langkah=f"Satu {b.replace('_',' ')} mempunyai {nilai} {t.replace('_kali','')}. Total = {nilai} × {n} = {nilai*n}."
    else:
        k=[('unsur.tertukar_'+b,BANGUN[TERTUKAR[b]][ix],'K',f"menjawab jumlah {t} bangun {TERTUKAR[b].replace('_',' ')}"),
           ('unsur.anggap_satu',1,'B','menjawab satu (seolah-olah hanya ada satu)')]
        h='unsur.kurang_satu_'+b
        langkah=f"Bangun {b.replace('_',' ')} mempunyai {nilai} {t}. Jawabannya {nilai}."
    # Kesamaan jumlah sisi antarbangun bukan miskonsepsi. Alternatif yang
    # dapat diuji: tertukar JENIS unsur pada bangun yang sama, bukan angka nudge.
    if not any(kode == 'K' and fmt(v) != soal.kunci for _,v,kode,_ in k):
        unsur_lain = 'sisi' if t.startswith('titik') else 'rusuk'
        nilai_lain = BANGUN[b][TANYA_INDEKS[unsur_lain]]
        jumlah = p.get('n',1) if t.endswith('_kali') else 1
        k.append(('unsur.jenis_unsur_'+b, nilai_lain*jumlah, 'K',
                  f"menghitung {unsur_lain} bangun yang sama, bukan {t.replace('_kali','')}"))
    return _hasil(soal,k,h,langkah)


def perbandingan_volume(soal):
    p=soal.parameter
    if p.get('versi') != 2:
        raise ValueError('katalog perbandingan volume memerlukan matematika versi 2')
    if p['varian']!='cari_k':
        return soal
    return _hasil(soal, (
        ('perbandingan.kali',F(p['V_baru'],3),'K','membagi faktor volume dengan tiga, bukan mencari akar pangkat tiga'),
        ('perbandingan.kuadrat',p['V_baru'],'K','menjawab faktor volume sebagai faktor panjang')),
        'perbandingan.kurang_satu')


def skala(soal):
    p=soal.parameter
    if p.get('versi') != 2:
        raise ValueError('katalog skala memerlukan matematika versi 2')
    v,a,b,n=p['varian'],p['sebenarnya'],p['peta'],p['skala']
    if v=='cari_skala':
        # Rasio integer ekuivalen peta:km tanpa konversi; tidak butuh codec baru.
        g=math.gcd(a,b)
        mal=[Malrule('skala.terbalik',f'{n}:1','K','membalik skala peta:sebenarnya'),
             Malrule('skala.lupa_km_ke_cm',f'{b//g}:{a//g}','K','membandingkan cm pada peta dengan km sebenarnya tanpa menyamakan satuan'),
             Malrule('skala.kurang_satu',f'1:{n+1}','H','melakukan konversi dengan benar tetapi penyebut meleset satu')]
        return replace(soal,malrule=saring_malrule(soal.kunci,mal))
    if v=='cari_peta':
        k=(('skala.peta_terbalik',a*100000,'K','menjawab jarak sebenarnya dalam cm, bukan jarak peta'),
           ('skala.peta_lupa_km',F(a,n),'K','membagi jarak km dengan penyebut skala tanpa mengubah km ke cm'))
    else:
        k=(('skala.sebenarnya_lupa_bagi',b*n,'K','menghitung peta×skala tanpa mengubah cm ke km'),
           ('skala.sebenarnya_terbalik',F(b,n),'K','membagi angka jarak peta dengan penyebut skala dan tidak mengubah satuan'))
    return _hasil(soal,k,'skala.peta_kurang_satu' if v=='cari_peta' else 'skala.sebenarnya_kurang_satu')


def waktu(soal):
    p=soal.parameter
    if p.get('versi') != 2:
        raise ValueError('katalog waktu memerlukan matematika versi 2')
    v,j,m,d=p['varian'],p['jam'],p['menit'],p['detik']
    if v=='durasi_ke_menit':
        k=(('jam.terbalik_'+v,j+F(m,60),'K','mengubah menit menjadi jam dan menjumlahkan jam, tetapi menjawabnya sebagai menit'),
           ('jam.lupa_'+v,j,'K','menyalin angka jam saja sebagai menit, mengabaikan menit tambahan'))
    elif v=='durasi_ke_detik':
        k=(('jam.terbalik_'+v,j*60+m,'K','mengubah jam ke menit lalu menambah menit, tetapi menjawabnya sebagai detik'),
           ('jam.lupa_'+v,j*3600+m*60,'K','mengubah jam dan menit ke detik tetapi mengabaikan detik tambahan'))
    else:
        sumber,faktor = {'jam_ke_menit':(j,60),'menit_ke_jam':(m,F(1,60)),
            'menit_ke_detik':(m,60),'detik_ke_menit':(d,F(1,60)),
            'jam_ke_detik':(j,3600),'detik_ke_jam':(d,F(1,3600))}[v]
        balik=F(sumber)/faktor
        k=(('jam.terbalik_'+v,balik,'K','membalik arah konversi: membagi saat seharusnya mengalikan, atau sebaliknya'),
           ('jam.lupa_'+v,sumber,'K','tidak mengkonversi: menyalin angka masukan'))
    return _hasil(soal,k,'jam.kurang_satu')
