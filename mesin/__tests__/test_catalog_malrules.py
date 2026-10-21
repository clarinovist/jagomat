"""Oracle prosedural audit Batch B; collision boleh hilang, nilai tidak boleh digeser."""
from fractions import Fraction as F
from itertools import combinations
import math

import pytest
from generator import buat_soal
from topics import ambil

TARGET = {
    "statistika": ("median_modus", "rata_rata_gabungan", "diagram_batang_garis", "tabel_turus", "piktogram", "jangkauan_data"),
    "logika": ("jumlah_selisih",), "aritmetika-dasar": ("fpb_dua_bilangan",),
    "geometri-ruang": ("volume_prisma_tabung", "unsur_bangun", "perbandingan_volume"),
    "pengukuran": ("skala_peta", "jam_menit_detik"),
}
PASANGAN = [(topik, tid, lv) for topik, tids in TARGET.items() for tid in tids
            for lv, daftar in ambil(topik).komposisi.items() if tid in daftar]


def angka(s):
    return F(s.replace(",", "."))


def aturan(tid, p):
    d, v, i = p.get("data", []), p.get("varian"), p.get("i", 0)
    if tid == "median_modus" and v == "median":
        n = len(d)
        tengah = F(d[n//2]) if n % 2 else F(d[n//2-1]+d[n//2], 2)
        return {"median.tanpa_urut": {tengah}, "median.terkecil": {min(d)}}
    if tid == "rata_rata_gabungan":
        return {"gabung.total_saja": {p['n1']*p['x1']+p['n2']*p['x2']}, "gabung.rata_rata_rata": {F(p['x1']+p['x2'], 2)}}
    if tid == "diagram_batang_garis":
        if v == "baca":
            return {"batang.baca_tetangga": {d[(i+1)%len(d)]}, "batang.baca_lain": {d[(i+2)%len(d)]}}
        if v == "jumlah":
            return {"batang.terbesar": {max(d)}, "batang.lupa_pertama": {sum(d)-d[0]}}
        return {"batang.jumlah_dua": {d[i]+d[(i+1)%len(d)]}, "batang.selisih_lain": {abs(d[i]-d[(i+2)%len(d)])}}
    if tid == "tabel_turus" and v != "terbanyak":
        return {"turus.salah_baris": {d[(i+1)%len(d)] if v == "baca" else max(d)},
                "turus.salah_baris2": {d[(i+2)%len(d)] if v == "baca" else sum(d)-d[0]}}
    if tid == "piktogram":
        d, u = p["gambar"], p["satuan"]
        if v == "baca": a,b = d[i], d[i]+u
        elif v == "total": a,b = sum(d), max(d)*u
        else: a,b = abs(d[i]-d[(i+1)%len(d)]), (d[i]+d[(i+1)%len(d)])*u
        return {"pikto.lupa_skala": {a}, "pikto.salah_operasi": {b}}
    if tid == "jangkauan_data":
        a,b = ((min(d), sorted(d)[-2]) if v == "terbesar" else
               (max(d), sorted(d)[1]) if v == "terkecil" else (max(d)+min(d), max(d)))
        return {"jangkau.arah_salah": {a}, "jangkau.hampir": {b}}
    if tid == "jumlah_selisih":
        j,s = p["jumlah"],p["selisih"]
        return {"jumlah_selisih.lupa_bagi_"+p["tanya"]: {j-s},
                "jumlah_selisih.terbalik_"+p["tanya"]: {F(j-s if p["tanya"]=="besar" else j+s, 2)}}
    if tid == "volume_prisma_tabung" and v == "prisma_balik":
        return {"volprisma.lupa_setengah_segitiga": {F(p['V'],p['a']*p['t_segitiga'])},
                "volprisma.rumus_lain_segitiga": {F(p['V'],p['a']+p['t_segitiga'])}}
    if tid == "unsur_bangun":
        fakta = {'kubus':(6,12,8),'balok':(6,12,8),'prisma_segitiga':(5,9,6),'tabung':(3,2,0),'limas_segiempat':(5,8,5),'kerucut':(2,1,1)}
        tukar = {'kubus':'prisma_segitiga','balok':'prisma_segitiga','prisma_segitiga':'limas_segiempat','limas_segiempat':'prisma_segitiga','tabung':'kerucut','kerucut':'tabung'}
        bangun,t = p['bangun'],p['tanya']
        ix = {'sisi':0,'rusuk':1,'titik':2}[t.replace('_kali','')]
        alternatif = fakta[bangun][0 if t.startswith('titik') else 1] * (p['n'] if t.endswith('_kali') else 1)
        if t.endswith('_kali'):
            return {'unsur.kali_lupa_'+bangun:{fakta[bangun][ix]}, 'unsur.kali_lebih_'+bangun:{fakta[bangun][ix]*(p['n']+1)},
                    'unsur.jenis_unsur_'+bangun:{alternatif}}
        return {'unsur.tertukar_'+bangun:{fakta[tukar[bangun]][ix]}, 'unsur.jenis_unsur_'+bangun:{alternatif}}
    if tid == "skala_peta":
        if v == "cari_skala": return {'skala.lupa_km_ke_cm': {F(p['peta'],p['sebenarnya'])}}
        if v == "cari_peta": return {'skala.peta_lupa_km': {F(p['sebenarnya'],p['skala'])}}
    if tid == "jam_menit_detik":
        if v == "durasi_ke_menit": return {'jam.lupa_'+v:{p['jam']}}
        if v == "durasi_ke_detik": return {'jam.lupa_'+v:{p['jam']*3600+p['menit']*60}}
    return {}


@pytest.mark.parametrize('topik,tid,lv', PASANGAN)
def test_malrule_mengikuti_prosedur(topik,tid,lv,monkeypatch):
    monkeypatch.setenv('OSN_KATALOG_VERSI','2')
    terlihat = set()
    for seed in range(600):
        soal = buat_soal(tid,seed,lv,topik)
        p = soal.parameter
        oracle = aturan(tid,p)
        for m in soal.malrule:
            if m.id in oracle:
                nilai = F(*map(int,m.jawaban.split(':'))) if ':' in m.jawaban else angka(m.jawaban)
                assert nilai in oracle[m.id], (seed,p,m,oracle[m.id])
                terlihat.add(m.id)
            if tid == 'fpb_dua_bilangan' and m.id == 'fpb.salah_pilih_faktor_bersama':
                nilai = int(m.jawaban)
                assert p['a'] % nilai == p['b'] % nilai == 0 and nilai < int(soal.kunci), (seed,p,m)
            if tid == 'unsur_bangun' and m.kode == 'H':
                assert abs(angka(m.jawaban)-angka(soal.kunci)) == 1 and angka(m.jawaban)>=0, (seed,p,m)
            if tid == 'jam_menit_detik' and p['varian']=='durasi_ke_detik' and m.id=='jam.lupa_durasi_ke_detik':
                assert 'detik' in m.alasan and 'mengabaikan' in m.alasan
            if tid == 'perbandingan_volume' and p['varian']=='cari_k' and m.id=='perbandingan.kali':
                assert angka(m.jawaban) == F(p['V_baru'],3)
                assert 'membagi' in m.alasan and 'tiga' in m.alasan
    if tid in {'median_modus','rata_rata_gabungan','jumlah_selisih','skala_peta'} and not (tid=='median_modus' and lv=='P3'):
        assert terlihat, 'oracle harus benar-benar terpakai'
