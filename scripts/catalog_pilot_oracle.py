"""Oracle pilot dari fakta publik; tidak mengimpor template atau pembuat kunci."""
from fractions import Fraction as F
from math import gcd

KONSEP=('pecahan_operasi_campuran','pecahan_kali_bagi','menyusul','satuan_waktu_lama','luas_permukaan')


def angka(s):
    return F(str(s).replace(',','.'))


def kunci(konsep,f):
    if konsep=='pecahan_operasi_campuran':
        # Hitung dalam unit terkecil, bukan meminjam hasil template.
        ds=[f['d1'],f['d2'],f['d3']]
        L=1
        for d in ds:L=L*d//gcd(L,d)
        return F(f['n1']*(L//ds[0])+f['n2']*(L//ds[1])-f['n3']*(L//ds[2]),L)
    if konsep=='pecahan_kali_bagi':
        a,b=F(f['n1'],f['d1']),F(f['n2'],f['d2'])
        return a*b if f['op']=='kali' else a/b
    if konsep=='menyusul':return F(f['jarak'],f['v2']-f['v1'])
    if konsep=='satuan_waktu_lama':return F(f['nilai']*8,5)
    r=f['r'];pi=F(22,7) if r%7==0 else F('3.14')
    if f['varian']=='tabung_LP':return sum((pi*r*r,pi*r*r,2*pi*r*f['t']))
    # Cari tinggi yang memenuhi luas dua lingkaran + selimut.
    return next(F(t) for t in range(2,21) if 2*pi*r*r+2*pi*r*t==angka(f['LP']))


def sah_domain(konsep,f):
    if konsep=='pecahan_operasi_campuran':
        return set(f)=={a+str(i) for a in ('n','d') for i in (1,2,3)} and all(
            type(f['d'+str(i)]) is int and f['d'+str(i)] in (3,4,5,6,8)
            and type(f['n'+str(i)]) is int and 1<=f['n'+str(i)]<f['d'+str(i)] for i in (1,2,3))
    if konsep=='pecahan_kali_bagi':
        return set(f)=={'n1','d1','n2','d2','op'} and f['op'] in ('kali','bagi') and all(
            type(f['d'+str(i)]) is int and 3<=f['d'+str(i)]<=10
            and type(f['n'+str(i)]) is int and 1<=f['n'+str(i)]<f['d'+str(i)] for i in (1,2))
    if konsep=='menyusul':
        return set(f)=={'jarak','v1','v2'} and all(type(x) is int for x in f.values()) and 20<=f['v1']<=50 and 40<=f['v2']<=80 and f['v2']>f['v1'] and F(f['jarak'],f['v2']-f['v1']) in range(1,6)
    if konsep=='satuan_waktu_lama':
        return set(f)=={'varian','nilai'} and f['varian']=='windu_ke_lustrum' and type(f['nilai']) is int and 5<=f['nilai']<=250 and f['nilai']%5==0
    if konsep=='luas_permukaan':
        maju=f.get('varian')=='tabung_LP'
        return set(f)==({'varian','r','t'} if maju else {'varian','r','LP'}) and f['varian'] in ('tabung_LP','tabung_cari_t') and type(f['r']) is int and 2<=f['r']<=28 and (not maju or type(f['t']) is int and 2<=f['t']<=20)
    return False


def prosedur(konsep,f,ident):
    izin={
        'pecahan_operasi_campuran':{'pecahan.operasi_pembilang_penyebut_terpisah','pecahan.pengurangan_pembilang_meleset','pecahan.mengabaikan_pengurangan_terakhir'},
        'pecahan_kali_bagi':{'rev1.pecahan.jumlah_komponen','rev1.pecahan.hasil_terbalik',
            'rev1.pecahan.kpk_tanpa_penyesuaian' if f.get('op')=='kali' else 'rev1.pecahan.lupa_balik'},
        'menyusul':{'rev1.menyusul.selisih_kecepatan','rev1.menyusul.berpapasan','rev1.menyusul.meleset'},
        'satuan_waktu_lama':{'rev1.waktu.balik_windu_ke_lustrum','rev1.waktu.salin_windu_ke_lustrum','rev1.waktu.meleset'},
        'luas_permukaan':({'rev1.lp.satu_lingkaran','rev1.lp.volume','rev1.lp.meleset'} if f.get('varian')=='tabung_LP'
                         else {'rev1.lp.lupa_kurangi_r','rev1.lp.bagi_luas_alas','rev1.lp.meleset'}),
    }
    if ident not in izin.get(konsep,set()):raise ValueError('prosedur tidak cocok konsep/cabang')
    hasil=kunci(konsep,f)
    if ident=='pecahan.operasi_pembilang_penyebut_terpisah':return F(f['n1']+f['n2']-f['n3'],f['d1']+f['d2']-f['d3'])
    if ident=='pecahan.pengurangan_pembilang_meleset':
        L=1
        for i in (1,2,3):L=L*f['d'+str(i)]//gcd(L,f['d'+str(i)])
        return hasil-F(1,L)
    if ident=='pecahan.mengabaikan_pengurangan_terakhir':return F(f['n1'],f['d1'])+F(f['n2'],f['d2'])
    if ident=='rev1.pecahan.kpk_tanpa_penyesuaian':return F(f['n1']*f['n2'],f['d1']*f['d2']//gcd(f['d1'],f['d2']))
    if ident=='rev1.pecahan.lupa_balik':return F(f['n1'],f['d1'])*F(f['n2'],f['d2'])
    if ident=='rev1.pecahan.jumlah_komponen':return F(f['n1']+f['n2'],f['d1']+f['d2'])
    if ident=='rev1.pecahan.hasil_terbalik':return 1/hasil
    if ident=='rev1.menyusul.selisih_kecepatan':return F(f['v2']-f['v1'])
    if ident=='rev1.menyusul.berpapasan':return F(f['jarak'],f['v1']+f['v2'])
    if ident in ('rev1.menyusul.meleset','rev1.waktu.meleset'):return hasil-1
    if ident=='rev1.waktu.balik_windu_ke_lustrum':return F(f['nilai']*5,8)
    if ident=='rev1.waktu.salin_windu_ke_lustrum':return F(f['nilai'])
    if konsep=='luas_permukaan':
        r=f['r'];pi=F(22,7) if r%7==0 else F('3.14')
        if ident=='rev1.lp.satu_lingkaran':return pi*r*r+2*pi*r*f['t']
        if ident=='rev1.lp.volume':return pi*r*r*f['t']
        if ident=='rev1.lp.lupa_kurangi_r':return angka(f['LP'])/(2*pi*r)
        if ident=='rev1.lp.bagi_luas_alas':return angka(f['LP'])/(pi*r*r)
        if ident=='rev1.lp.meleset':return hasil-(F(1,10) if hasil.denominator!=1 else 1)
    raise ValueError('prosedur belum mempunyai oracle')
