"""Fondasi penilaian opt-in; revisi lama tetap dibaca tanpa interpretasi ulang."""
from collections import Counter
from dataclasses import replace
from fractions import Fraction as F
from functools import wraps
import math
import os

from catalog_exact import baca_angka, format_angka
from templates import Malrule

_TANPA_REVISI = object()
KONTRAK = 'rasional-eksak-v1'
TEMPLATE = frozenset({'pecahan_operasi_campuran','pecahan_kali_bagi','menyusul',
                     'kecepatan_jarak_waktu','satuan_waktu_lama','luas_permukaan'})


def didukung(tid, p):
    return tid in TEMPLATE and (tid!='luas_permukaan' or
        p.get('varian') in ('tabung_LP','tabung_cari_t'))


def aktif():
    nilai=os.environ.get('OSN_PENILAIAN_REVISI','0').strip()
    if nilai not in ('0','1'):
        raise ValueError('OSN_PENILAIAN_REVISI hanya menerima 0 atau 1')
    return nilai=='1'


def kontrak(soal):
    """Metadata dari server menentukan grammar, bukan bentuk teks jawaban."""
    if 'revisi_penilaian' not in soal.parameter:
        return None
    revisi=soal.parameter['revisi_penilaian']
    if type(revisi) is not int or revisi!=1 or not didukung(soal.template_id,soal.parameter):
        raise ValueError('revisi penilaian tidak didukung')
    return KONTRAK


def saring_eksak(kunci, kandidat):
    """Tolak payload invalid; buang kunci dan seluruh collision prosedur ambigu."""
    key=baca_angka(kunci)
    nilai=[baca_angka(m.jawaban) for m in kandidat]
    if key is None or any(v is None for v in nilai):
        raise ValueError('jawaban kandidat wajib rasional sah')
    jumlah=Counter(nilai)
    return tuple(m for m,v in zip(kandidat,nilai) if v!=key and jumlah[v]==1)


def soal_berrevisi(lama):
    @wraps(lama)
    def panggil(*args,revisi_penilaian=_TANPA_REVISI,**kwargs):
        if revisi_penilaian is _TANPA_REVISI:
            return lama(*args,**kwargs)
        if type(revisi_penilaian) is not int or revisi_penilaian!=1:
            raise ValueError('revisi penilaian tidak didukung')
        s=lama(*args,**kwargs)
        if not didukung(s.template_id,s.parameter):
            raise ValueError('cabang tidak mendukung revisi penilaian')
        return perbaiki(s)
    return panggil


def _rule(ident,nilai,alasan,kode='K'):
    return Malrule('rev1.'+ident,format_angka(nilai),kode,alasan)


def perbaiki(s):
    """Nilai malrule berasal prosedur literal. Tidak mengejar jumlah kandidat."""
    t,p=s.template_id,s.parameter
    key=baca_angka(s.kunci)
    if key is None:raise ValueError('kunci wajib rasional sah')
    if t=='pecahan_operasi_campuran':
        # Bangun kandidat mentah, bukan s.malrule yang sudah first-wins.
        # K/H yang sama nilainya harus sama-sama hilang pada revisi baru.
        L=math.lcm(p['d1'],p['d2'],p['d3'])
        denominator=p['d1']+p['d2']-p['d3']
        mal=[]
        if denominator:
            mal.append(Malrule('pecahan.operasi_pembilang_penyebut_terpisah',
                format_angka(F(p['n1']+p['n2']-p['n3'],denominator)),'K',
                'mengoperasikan pembilang dan penyebut secara terpisah'))
        mal.extend((Malrule('pecahan.pengurangan_pembilang_meleset',format_angka(key-F(1,L)),
                            'H','penyebut sudah disamakan, pengurangan pembilang kurang satu'),
                    Malrule('pecahan.mengabaikan_pengurangan_terakhir',
                            format_angka(F(p['n1'],p['d1'])+F(p['n2'],p['d2'])),
                            'B','menjumlahkan dua pecahan pertama tanpa mengurangi pecahan terakhir')))
    elif t=='pecahan_kali_bagi':
        a,b=F(p['n1'],p['d1']),F(p['n2'],p['d2'])
        if p['op']=='kali':
            salah=F(p['n1']*p['n2'],math.lcm(p['d1'],p['d2']))
            ident='pecahan.kpk_tanpa_penyesuaian'
            alasan='mengalikan pembilang asli dan mengganti penyebut dengan KPK tanpa menyesuaikan pembilang'
        else:
            salah=a*b;ident='pecahan.lupa_balik';alasan='mengalikan kedua pecahan tanpa membalik pecahan kedua'
        mal=[_rule(ident,salah,alasan),
             _rule('pecahan.jumlah_komponen',F(p['n1']+p['n2'],p['d1']+p['d2']),'menjumlahkan pembilang dan penyebut secara terpisah'),
             _rule('pecahan.hasil_terbalik',1/key,'pembilang dan penyebut hasil akhir tertukar','H')]
    elif t=='menyusul':
        mal=[_rule('menyusul.selisih_kecepatan',p['v2']-p['v1'],'menjawab selisih kecepatan, bukan waktu menyusul'),
             _rule('menyusul.berpapasan',F(p['jarak'],p['v1']+p['v2']),'memakai rumus berpapasan: jarak dibagi jumlah kecepatan'),
             _rule('menyusul.meleset',key-1,'hasil waktu meleset satu','H')]
    elif t=='kecepatan_jarak_waktu':
        v=p['varian']
        balik=F(p['t'],p['s']) if v=='cari_v' else F(p['v'],p['t']) if v=='cari_s' else F(p['v'],p['s'])
        nilai=p['s']*p['t'] if v=='cari_v' else p['v']+p['t'] if v=='cari_s' else p['s']*p['v']
        alasan={'cari_v':'mengalikan jarak dengan waktu','cari_s':'menjumlahkan kecepatan dengan waktu','cari_t':'mengalikan jarak dengan kecepatan'}[v]
        mal=[_rule('kecepatan.balik_'+v,balik,'membalik operasi untuk besaran '+v),
             _rule('kecepatan.operasi_'+v,nilai,alasan),_rule('kecepatan.meleset',key-1,'hasil meleset satu','H')]
    elif t=='satuan_waktu_lama':
        src,dst=p['varian'].split('_ke_')
        tahun={'abad':100,'windu':8,'lustrum':5,'dasawarsa':10,'tahun':1}
        salah=F(p['nilai']*tahun[dst],tahun[src])
        mal=[_rule('waktu.balik_'+p['varian'],salah,'membalik faktor konversi '+src+' ke '+dst),
             _rule('waktu.salin_'+p['varian'],p['nilai'],'menyalin angka masukan tanpa konversi'),
             _rule('waktu.meleset',key-1,'hasil konversi meleset satu','H')]
    else:
        if p.get('versi')!=2:raise ValueError('revisi LP tabung memerlukan matematika2')
        r=p['r'];pi=F(22,7) if r%7==0 else F('3.14')
        if p['varian']=='tabung_LP':
            a,b=pi*r*r+2*pi*r*p['t'],pi*r*r*p['t']
            mal=[_rule('lp.satu_lingkaran',a,'menghitung selimut dan satu lingkaran saja, bukan dua'),
                 _rule('lp.volume',b,'menghitung volume tabung, bukan luas permukaan')]
        else:
            total=baca_angka(str(p['LP']))
            mal=[_rule('lp.lupa_kurangi_r',total/(2*pi*r),'membagi luas permukaan dengan keliling alas tetapi lupa mengurangi jari-jari'),
                 _rule('lp.bagi_luas_alas',total/(pi*r*r),'membagi luas permukaan dengan luas alas, memakai bentuk rumus tinggi dari volume')]
        langkah=F(1,10) if key.denominator!=1 else F(1)
        mal.append(_rule('lp.meleset',key-langkah,'hasil hitung meleset '+format_angka(langkah),'H'))
    return replace(s,parameter={**p,'revisi_penilaian':1},malrule=saring_eksak(s.kunci,mal))
