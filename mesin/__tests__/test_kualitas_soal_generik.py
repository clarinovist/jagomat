"""G1–G4: cakupan eksplisit dan lantai regresi, bukan skor kualitas pedagogis.

Baseline sintetis: SHA a96a7e16c0c427f20c014339ced46b3c4b939055, Python 3.9.6,
writer matematika v2, seed soal 0..299 dan lembar 0..99. Tidak membutuhkan
artefak docs/plan yang di-ignore. Kebenaran kunci/malrule tetap solver domain.
G1 numerik ada di test_question_position; registry di sini menolak kelompok
baru tanpa triage. Belum berarti semua template diaudit bias posisi.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
import random
import re

import pytest

import generator
import topics
from generator_version import versi_generator_baru
from test_question_position import (
    test_keterbagian_posisi_seimbang_dengan_solver_independen as _cek_keterbagian,
    test_modus_posisi_mengikuti_frekuensi_data as _cek_modus,
)

# topik template level:bentuk:tanda_tangan:varian (nilai per level, bukan gabungan).
# Lantai = observasi seed tetap, bukan target kualitas atau ukuran seluruh support.
_DATA = """
aritmatika-lanjut debit P5:3:285:cari_debit,cari_volume,cari_waktu P6:3:285:cari_debit,cari_volume,cari_waktu
aritmatika-lanjut kecepatan_jarak_waktu P5:3:280:cari_s,cari_t,cari_v P6:3:280:cari_s,cari_t,cari_v
aritmatika-lanjut kerja_bersama P5:5:227:- P6:5:227:-
aritmatika-lanjut perbandingan_berbalik P5:5:239:- P6:5:239:-
aritmatika-lanjut perbandingan_senilai P5:5:278:- P6:5:278:-
aritmatika-lanjut persen_diskon P5:5:300:-
aritmatika-lanjut satuan_konversi P5:8:297:g_ke_kg,jam_ke_menit,kg_ke_g,km_ke_m,liter_ke_ml,m_ke_km,menit_ke_jam,ml_ke_liter P6:8:297:g_ke_kg,jam_ke_menit,kg_ke_g,km_ke_m,liter_ke_ml,m_ke_km,menit_ke_jam,ml_ke_liter
aritmatika-lanjut berpapasan P6:25:297:-
aritmatika-lanjut menyusul P6:25:293:-
aritmatika-lanjut persen_bertingkat P6:5:300:-
aritmatika-lanjut persen_untung_rugi P6:10:299:-
aritmetika-dasar fpb_dua_bilangan P5:1:231:- P6:1:229:-
aritmetika-dasar operasi_berkurung P5:1:299:- P6:1:299:-
aritmetika-dasar pecahan_kali_bagi P5:2:231:- P6:2:271:-
aritmetika-dasar pecahan_operasi_campuran P5:1:199:- P6:1:288:-
aritmetika-dasar pembulatan_taksiran P5:4:299:- P6:4:300:-
aritmetika-dasar urut_pecahan_desimal_persen P5:1:275:- P6:1:290:-
aritmetika-dasar urutan_operasi_1 P5:1:285:- P6:1:294:-
geometri-datar keliling_luas_datar P3:5:167:keliling P4:10:283:balik_luas,keliling P5:10:283:balik_luas,keliling P6:10:283:balik_luas,keliling
geometri-datar luas_kotak_satuan P3:12:235:-
geometri-datar simetri_bangun P3:48:258:-
geometri-datar jumlah_sudut_segitiga P4:9:167:dua_sudut,perbandingan P5:9:167:dua_sudut,perbandingan
geometri-datar luas_segitiga_jajargenjang P4:10:293:jajargenjang,segitiga P5:10:293:jajargenjang,segitiga P6:10:293:jajargenjang,segitiga
geometri-datar sudut_pelurus_berpenyiku P4:5:189:balik_pelurus,balik_penyiku,pelurus,penyiku,tiga_kali P5:5:189:balik_pelurus,balik_penyiku,pelurus,penyiku,tiga_kali
geometri-datar lingkaran_keliling_luas P5:4:177:keliling,luas P6:4:177:keliling,luas
geometri-datar luas_arsiran P5:2:196:jalan_pinggir,persegi_titik_tengah P6:2:196:jalan_pinggir,persegi_titik_tengah
geometri-datar luas_segiempat_lain P5:3:281:balik_diagonal,ketupat_layang,trapesium P6:3:281:balik_diagonal,ketupat_layang,trapesium
geometri-datar sudut_luar_segitiga P5:5:273:- P6:5:273:-
geometri-datar juring P6:4:225:keliling_juring,luas_juring
geometri-datar perbandingan_ukuran P6:3:201:keliling,luas,volume
geometri-ruang luas_permukaan P5:7:213:balok_LP,balok_cari_p,kubus_LP,kubus_cari_s,tabung_LP,tabung_cari_t P6:7:213:balok_LP,balok_cari_p,kubus_LP,kubus_cari_s,tabung_LP,tabung_cari_t
geometri-ruang unsur_bangun P5:36:135:- P6:36:135:-
geometri-ruang volume_kubus_balok P5:4:176:balok_cari_V,balok_cari_p,kubus_cari_V,kubus_cari_s P6:4:176:balok_cari_V,balok_cari_p,kubus_cari_V,kubus_cari_s
geometri-ruang volume_prisma_tabung P5:6:290:prisma_V,prisma_balik,tabung_V,tabung_balik P6:6:290:prisma_V,prisma_balik,tabung_V,tabung_balik
geometri-ruang jaring_jaring P6:1:297:-
geometri-ruang kubus_dicat P6:8:160:-
geometri-ruang perbandingan_volume P6:3:205:balok_V_baru,cari_V_baru,cari_k
kombinatorik aturan_kali P5:5:199:-
kombinatorik aturan_tambah P5:5:247:-
kombinatorik inklusi_eksklusi_2 P5:5:300:- P6:5:300:-
kombinatorik jabat_tangan P5:5:179:-
kombinatorik susun_bilangan P5:6:224:dengan_nol,tanpa_nol
kombinatorik susun_bilangan_syarat P5:4:237:genap,lebih_dari P6:4:237:genap,lebih_dari
kombinatorik jalur_petak P6:1:186:-
kombinatorik kombinasi_pilih P6:299:300:-
kombinatorik permutasi_blok P6:300:300:-
kombinatorik permutasi_urutan P6:300:300:-
kombinatorik sarang_merpati P6:1:250:-
logika benar_salah_pengandaian P3:292:300:bekal,warna P5:293:300:bekal,warna P6:293:300:bekal,warna
logika soal_uang P3:2:174:- P5:2:242:- P6:2:242:-
logika soal_umur P3:2:161:- P6:2:227:-
logika tabel_penalaran P3:233:233:- P5:236:236:- P6:236:236:-
logika jumlah_selisih P5:2:268:- P6:2:268:-
logika dua_besaran_selisih P6:2:234:-
pengukuran jam_menit_detik P4:8:298:detik_ke_jam,detik_ke_menit,durasi_ke_detik,durasi_ke_menit,jam_ke_detik,jam_ke_menit,menit_ke_detik,menit_ke_jam P5:8:298:detik_ke_jam,detik_ke_menit,durasi_ke_detik,durasi_ke_menit,jam_ke_detik,jam_ke_menit,menit_ke_detik,menit_ke_jam P6:8:298:detik_ke_jam,detik_ke_menit,durasi_ke_detik,durasi_ke_menit,jam_ke_detik,jam_ke_menit,menit_ke_detik,menit_ke_jam
pengukuran jam_selesai P4:3:300:cari_durasi,cari_mulai,cari_selesai P5:3:300:cari_durasi,cari_mulai,cari_selesai P6:3:300:cari_durasi,cari_mulai,cari_selesai
pengukuran satuan_kuantitas P4:30:242:- P5:30:275:- P6:30:275:-
pengukuran satuan_waktu_lama P4:10:246:abad_ke_dasawarsa,abad_ke_tahun,dasawarsa_ke_tahun,lustrum_ke_tahun,tahun_ke_abad,tahun_ke_dasawarsa,tahun_ke_lustrum,tahun_ke_windu,windu_ke_lustrum,windu_ke_tahun P5:10:246:abad_ke_dasawarsa,abad_ke_tahun,dasawarsa_ke_tahun,lustrum_ke_tahun,tahun_ke_abad,tahun_ke_dasawarsa,tahun_ke_lustrum,tahun_ke_windu,windu_ke_lustrum,windu_ke_tahun P6:10:246:abad_ke_dasawarsa,abad_ke_tahun,dasawarsa_ke_tahun,lustrum_ke_tahun,tahun_ke_abad,tahun_ke_dasawarsa,tahun_ke_lustrum,tahun_ke_windu,windu_ke_lustrum,windu_ke_tahun
pengukuran tangga_satuan_campuran P4:16:299:- P5:78:300:- P6:78:300:-
pengukuran satuan_luas_volume P5:13:258:- P6:14:266:-
pengukuran skala_peta P5:3:252:cari_peta,cari_sebenarnya,cari_skala P6:3:252:cari_peta,cari_sebenarnya,cari_skala
pola-bilangan deret_aritmetika P3:1:55:- P4:1:66:- P5:1:75:- P6:1:95:-
pola-bilangan deret_aritmetika_turun P3:2:69:- P4:2:80:-
pola-bilangan deret_bertingkat P3:2:163:- P4:2:163:- P5:2:163:- P6:2:175:-
pola-bilangan deret_geometri P3:2:24:- P4:2:24:- P5:3:24:- P6:4:14:-
pola-bilangan deret_terbalik_aritmetika P3:1:147:- P4:1:194:- P5:1:215:- P6:1:233:-
pola-bilangan deret_terbalik_geometri P3:1:22:- P4:1:22:- P5:1:22:- P6:1:13:-
pola-bilangan jumlah_siklus P3:2:283:- P5:2:292:- P6:2:295:-
pola-bilangan korek_api P3:1:153:- P4:1:215:- P5:1:232:-
pola-bilangan siklus_hari P3:7:49:- P4:7:49:- P6:7:42:-
pola-bilangan siklus_huruf P3:32:213:- P4:32:244:- P5:32:268:-
pola-bilangan siklus_warna P3:282:299:-
pola-bilangan titik_segitiga P3:1:7:- P4:1:9:- P5:1:11:- P6:1:14:-
pola-bilangan sisa_bagi_siklus P4:61:287:- P5:61:292:- P6:61:298:-
pola-bilangan suku_ke_n P4:1:184:- P5:1:202:- P6:1:230:-
pola-bilangan pola_pecahan P5:1:36:- P6:1:36:-
pola-bilangan jumlah_deret P6:1:119:-
statistika diagram_batang_garis P3:3:300:baca,jumlah,selisih P4:9:300:baca,jumlah,selisih P5:9:300:baca,jumlah,selisih P6:9:300:baca,jumlah,selisih
statistika jangkauan_data P3:6:300:jangkauan,terbesar,terkecil P4:12:300:jangkauan,terbesar,terkecil
statistika median_modus P3:3:280:modus P4:13:300:median,modus P5:13:300:median,modus P6:13:300:median,modus
statistika piktogram P3:17:292:baca,selisih,total P4:17:299:baca,selisih,total
statistika tabel_turus P3:24:300:baca,jumlah,terbanyak P4:24:300:baca,jumlah,terbanyak
statistika rata_rata P4:12:300:cari_data_ke_n,cari_rata P5:12:300:cari_data_ke_n,cari_rata P6:12:300:cari_data_ke_n,cari_rata
statistika diagram_lingkaran P5:2:268:cari_nilai,cari_sudut P6:2:268:cari_nilai,cari_sudut
statistika rata_rata_gabungan P5:1:300:- P6:1:300:-
teori-bilangan keterbagian P4:1:299:- P5:1:300:- P6:1:300:-
teori-bilangan paritas P4:2:185:- P5:2:185:-
teori-bilangan sisa_pembagian P4:1:293:- P5:1:293:- P6:1:293:-
teori-bilangan gauss_deret P5:1:185:- P6:1:185:-
teori-bilangan kpk_dua_bilangan P5:5:299:- P6:5:299:-
teori-bilangan prima_faktorisasi P5:1:276:- P6:1:290:-
teori-bilangan angka_satuan_pangkat P6:1:220:-
teori-bilangan fpb_kpk_hubungan P6:1:299:-
"""

# topik level panjang_bawaan jenis_minimum. Tidak mengubah komposisi yang disetujui.
_LEMBAR = """
aritmatika-lanjut P5 10 7
aritmatika-lanjut P6 10 10
aritmetika-dasar P5 10 7
aritmetika-dasar P6 10 7
geometri-datar P3 8 3
geometri-datar P4 8 4
geometri-datar P5 10 8
geometri-datar P6 10 8
geometri-ruang P5 10 4
geometri-ruang P6 10 7
kombinatorik P5 10 6
kombinatorik P6 10 7
logika P3 10 4
logika P5 10 4
logika P6 10 6
pengukuran P4 10 5
pengukuran P5 10 7
pengukuran P6 10 7
pola-bilangan P3 12 12
pola-bilangan P4 12 12
pola-bilangan P5 12 12
pola-bilangan P6 12 12
statistika P3 10 5
statistika P4 10 6
statistika P5 10 5
statistika P6 10 5
teori-bilangan P4 10 3
teori-bilangan P5 10 6
teori-bilangan P6 10 7
"""

# Keputusan existing README dan test_latar_teori_bilangan; bukan izin baru
# untuk menyebut semua satu-bentuk sah. Lantai numerik tetap dijaga per level.
HITUNG_MURNI = frozenset({
    "fpb_dua_bilangan", "operasi_berkurung", "pecahan_kali_bagi",
    "pecahan_operasi_campuran", "urut_pecahan_desimal_persen", "urutan_operasi_1",
    "keterbagian", "sisa_pembagian", "paritas", "prima_faktorisasi",
    "gauss_deret", "angka_satuan_pangkat", "fpb_kpk_hubungan",
})
# Semua nama lain memakai lantai provisional, bukan otomatis UTANG_BENTUK.
# Keputusan pemilik untuk klasifikasi tambahan/target baru tetap diperlukan.
ALASAN_RUANG = {
    "titik_segitiga": "Batas gambar per level terdokumentasi; jangan perlebar demi hitungan.",
    "deret_geometri": "Rasio/awal dan plafon nilai membatasi support; README.",
    "deret_terbalik_geometri": "Posisi dan plafon 4000 membatasi awal; README.",
    "pola_pecahan": "Pembilang 1..4, beda 1..3, penyebut terbatas menjaga pecahan sejati.",
    "unsur_bangun": "Separuh undian ke 18 kombinasi dasar; 135 sampel bukan kardinalitas support.",
    "deret_aritmetika": "Awal 2..12 dikali pool beda; jumlah isian/tampil tetap per level.",
    "deret_aritmetika_turun": "Pool beda x panjang 4/5 x tujuh pengali awal.",
    "deret_terbalik_aritmetika": "Awal/beda/posisi terbatas; 147 sampel bukan batas matematis.",
    "siklus_hari": "Tujuh hari dikali pool 6/7 jarak hari; support 42/49.",
    "jumlah_deret": "P6 awal 1..9 x empat beda x empat panjang; 119 sampel dari support 144.",
}
UTANG_LEMBAR = {("teori-bilangan", "P4"): (4.0, "Tiga jenis hitung murni untuk 10 soal; tambahan jenis menunggu pemilik.")}
POLA_ANGKA = re.compile(r"\d+(?:[.,]\d+)?")


def _baseline():
    hasil = {}
    for baris in _DATA.strip().splitlines():
        topik, tid, *level = baris.split()
        for kolom in level:
            lv, bentuk, tanda, varian = kolom.split(":")
            kunci = (topik, lv, tid)
            assert kunci not in hasil, ("baseline duplikat", kunci)
            hasil[kunci] = (int(bentuk), int(tanda), frozenset(varian.split(",")))
    return hasil


BASELINE = _baseline()
LEMBAR = {(t, lv): (int(n), int(j)) for t, lv, n, j in (b.split() for b in _LEMBAR.strip().splitlines())}
# Per kelompok yang memiliki varian, status yang sama berlaku pada tiap varian.
# Mapping hasil triage administratif bukan audit semantik terhadap 91 template lain.
POSISI_TERUJI = {("keterbagian", "-"), ("median_modus", "modus")}


def _kerangka(teks):
    return " ".join(POLA_ANGKA.sub("#", teks).split())


def _pasangan():
    for nama in topics.daftar_topik():
        if nama == "campuran":
            continue
        paket = topics.ambil(nama)
        for level, urutan in paket.komposisi.items():
            for tid in sorted(set(urutan)):
                yield (nama, level, tid), paket


def _ukur(paket, level, tid):
    bentuk, tanda, varian = set(), set(), set()
    for seed in range(300):
        soal = generator._soal_layak(paket, tid, random.Random(seed), level)
        bentuk.add(_kerangka(soal.teks))
        tanda.add(soal.tanda_tangan)
        varian.add(str(soal.parameter.get("varian", "-")))
    return len(bentuk), len(tanda), frozenset(varian)


def _ukur_katalog():
    return {k: _ukur(paket, k[1], k[2]) for k, paket in _pasangan()}


@pytest.fixture(scope="module")
def pengukuran():
    assert versi_generator_baru() == 2, "baseline hanya untuk writer matematika v2"
    return _ukur_katalog()


def test_g1_katalog_dan_varian_wajib_tercatat(pengukuran):
    assert set(pengukuran) == set(BASELINE), "kelompok baru/hilang memerlukan triage baseline"
    for k, (_, _, varian) in pengukuran.items():
        assert varian == BASELINE[k][2], ("varian baru/hilang memerlukan triage", k)
    # Selain struktur berikut statusnya masih pending; jangan sebut audit lengkap.
    assert all(any(k[2] == tid and varian in b[2] for k, b in BASELINE.items()) for tid, varian in POSISI_TERUJI)


@pytest.mark.parametrize("level", ("P4", "P5", "P6"))
def test_g1_posisi_keterbagian(level):
    _cek_keterbagian(level)


@pytest.mark.parametrize("level", ("P3", "P4", "P5", "P6"))
def test_g1_posisi_modus(level):
    _cek_modus(level)


def test_g2_bentuk_tidak_turun(pengukuran):
    assert HITUNG_MURNI <= {k[2] for k in BASELINE}
    for k, (bentuk, _, _) in pengukuran.items():
        assert bentuk >= BASELINE[k][0], ("bentuk turun", k, bentuk, BASELINE[k][0])


def test_g2_jumlah_jenis_per_level_tidak_turun():
    aktual = {(nama, level): paket for (nama, level, _), paket in _pasangan()}
    assert set(aktual) == set(LEMBAR), "topik/level baru memerlukan triage lembar"
    for k, paket in aktual.items():
        assert len(set(paket.komposisi_untuk(k[1]))) >= LEMBAR[k][1], ("jenis turun", k)


def test_g3_ruang_parameter_tidak_turun(pengukuran):
    sempit = {k[2] for k, (_, n, _) in BASELINE.items() if n < 150}
    assert sempit == set(ALASAN_RUANG), "triage seluruh baseline <150, bukan hanya 14 hasil cetak pertama"
    assert all(alasan.strip() for alasan in ALASAN_RUANG.values())
    for k, (_, tanda, _) in pengukuran.items():
        assert tanda >= BASELINE[k][1], ("ruang parameter turun", k, tanda, BASELINE[k][1])


def test_g4_konsentrasi_lembar_bawaan():
    for (nama, level), (panjang, _) in LEMBAR.items():
        maksimum = []
        for seed in range(100):
            soal = generator.buat_lembar(seed, level=level, topik=nama).soal
            assert len(soal) == panjang, ("panjang lembar berubah", nama, level)
            maksimum.append(max(Counter(_kerangka(s.teks) for s in soal).values()))
        nilai = sum(maksimum) / len(maksimum)
        batas = UTANG_LEMBAR.get((nama, level), (2.1, ""))[0]
        assert nilai <= batas, ("konsentrasi naik", nama, level, nilai, batas)
    for k, (batas, alasan) in UTANG_LEMBAR.items():
        assert k in LEMBAR and alasan.strip() and batas > 2.1


# Mutation in-memory melalui jalur generator sungguhan; monkeypatch memulihkan
# sesudah setiap test. Tidak menulis source, DB, ataupun memanggil provider.
def test_mutation_g1_rotasi_nol_dengan_kunci_tetap_sah(monkeypatch):
    paket = topics.ambil("teori-bilangan")
    asli = paket.parameter_untuk

    def rusak(tid, rng, level):
        p = asli(tid, rng, level)
        if tid == "keterbagian":
            nilai = [p[k] for k in ("a", "b", "c")]
            nilai = nilai[p["jawab"]:] + nilai[:p["jawab"]]
            p.update(zip(("a", "b", "c"), nilai))
            p["jawab"] = 0
        return p

    monkeypatch.setitem(topics.PAKET, paket.id, replace(paket, parameter_untuk=rusak))
    with pytest.raises(AssertionError, match="Counter"):
        test_g1_posisi_keterbagian("P4")


def test_mutation_g1_modus_tanpa_shuffle(monkeypatch):
    monkeypatch.setattr(random.Random, "shuffle", lambda self, data: None)
    with pytest.raises(AssertionError, match="P3"):
        test_g1_posisi_modus("P3")


def test_mutation_g1_template_baru_tanpa_baseline(monkeypatch):
    paket = topics.ambil("teori-bilangan")
    fn, param = paket.templates["keterbagian"], paket.parameter_untuk
    baru = "baru_tanpa_triage"
    paket = replace(
        paket,
        templates={**paket.templates, baru: lambda **p: replace(fn(**p), template_id=baru)},
        komposisi={**paket.komposisi, "P4": paket.komposisi["P4"] + (baru,)},
        parameter_untuk=lambda tid, rng, lv: param("keterbagian" if tid == baru else tid, rng, lv),
    )
    monkeypatch.setitem(topics.PAKET, paket.id, paket)
    # Template sintetis benar-benar menghasilkan soal sah; yang gagal adalah
    # coverage, bukan import, sampler tidak dikenal, atau struktur fixture.
    k = (paket.id, "P4", baru)
    aktual = _ukur_katalog()
    assert k in aktual and aktual[k][0] == 1
    with pytest.raises(AssertionError, match="kelompok baru/hilang"):
        test_g1_katalog_dan_varian_wajib_tercatat(aktual)


def test_g2_satu_bentuk_hitung_murni_tetap_diterima(pengukuran):
    k = ("teori-bilangan", "P4", "keterbagian")
    assert k[2] in HITUNG_MURNI and pengukuran[k][0] == 1
    test_g2_bentuk_tidak_turun({k: pengukuran[k]})


def test_mutation_g2_bentuk_kpk_runtuh(monkeypatch):
    import topic_number_theory
    monkeypatch.setattr(topic_number_theory, "putar", lambda pilihan, *angka: pilihan[0])
    k = ("teori-bilangan", "P5", "kpk_dua_bilangan")
    aktual = {k: _ukur(topics.ambil(k[0]), k[1], k[2])}
    with pytest.raises(AssertionError, match="bentuk turun"):
        test_g2_bentuk_tidak_turun(aktual)


def test_mutation_g3_sampler_runtuh(monkeypatch):
    paket = topics.ambil("teori-bilangan")
    asli = paket.parameter_untuk
    paket = replace(paket, parameter_untuk=lambda tid, rng, lv: asli(tid, random.Random(0), lv))
    monkeypatch.setitem(topics.PAKET, paket.id, paket)
    k = (paket.id, "P4", "keterbagian")
    with pytest.raises(AssertionError, match="ruang parameter turun"):
        test_g3_ruang_parameter_tidak_turun({k: _ukur(paket, k[1], k[2])})


def test_mutation_g2_jenis_turun_dan_g4_terkonsentrasi(monkeypatch):
    paket = topics.ambil("teori-bilangan")
    monkeypatch.setitem(paket.komposisi, "P4", ("keterbagian",) * 10)
    with pytest.raises(AssertionError, match="jenis turun"):
        test_g2_jumlah_jenis_per_level_tidak_turun()
    with pytest.raises(AssertionError, match="konsentrasi naik"):
        test_g4_konsentrasi_lembar_bawaan()


def test_mutation_g4_panjang_lembar_tidak_boleh_dipangkas(monkeypatch):
    asli = generator.buat_lembar

    def pangkas(*args, **kwargs):
        lembar = asli(*args, **kwargs)
        return replace(lembar, soal=lembar.soal[:1])

    monkeypatch.setattr(generator, "buat_lembar", pangkas)
    with pytest.raises(AssertionError, match="panjang lembar berubah"):
        test_g4_konsentrasi_lembar_bawaan()
