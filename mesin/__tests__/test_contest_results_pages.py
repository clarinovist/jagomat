"""Halaman hasil rinci anak dan kartu soal bersama (unit): jawaban, kunci, pembahasan, escape, tanpa label kesalahan."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import contest_results as R  # noqa: E402
import contest_results_pages as RP  # noqa: E402
import contest_store as K  # noqa: E402

SVG_SOAL = '<svg id="gambar-uji" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>'
SVG_PILIHAN = ['<svg id="pilihan-%s" viewBox="0 0 10 10"><rect width="9" height="9"/></svg>' % h for h in "abcd"]
KESALAHAN = "memilih angka terkecil padahal diminta yang terbesar"


def _butir(**ubah):
    dasar = dict(nomor=3, topik="bilangan", jenis="pg", tingkat=1, template_id="bil_uji", teks="Berapa 2 + 3?", svg="",
                 pilihan=("4", "5", "6", "7"), gambar_pilihan=("", "", "", ""), jawaban="B", jawaban_teks="5", kunci="5",
                 kunci_huruf="B", benar=True, kesalahan=None, pembahasan=("2 + 3 = 5.", "Jadi 5."), inggris=False)
    return R.ButirRinci(**{**dasar, **ubah})


def _salah(**ubah):
    dasar = dict(jawaban="A", jawaban_teks="4", benar=False, kesalahan=KESALAHAN)
    return _butir(**{**dasar, **ubah})


def _isian(**ubah):
    dasar = dict(jenis="isian", pilihan=(), gambar_pilihan=(), jawaban="12", jawaban_teks="12", kunci="12",
                 kunci_huruf=None, benar=True)
    return _butir(**{**dasar, **ubah})


def _hasil(butir=None, status="dikumpul", mulai=1_800_000_000, selesai=1_800_000_330):
    butir = tuple(butir if butir is not None else [_butir(nomor=1), _salah(nomor=2)])
    sesi = K.SesiRingkas(id=7, siswa_id=1, status=status, mulai_epoch=mulai, batas_epoch=mulai + 900, selesai_epoch=selesai)
    return R.HasilRinci(sesi=sesi, nilai=sum(1 for b in butir if b.benar), jumlah_soal=len(butir),
                        waktu_terpakai_detik=selesai - mulai,
                        per_topik=(R.NilaiTopik("bilangan", 1, 2),), butir=butir)


def _halaman(**kw):
    return RP.halaman_hasil_anak(_hasil(**kw)).decode()


def _kartu(butir, **kw):
    return RP.kartu_soal(butir, **kw)


# --- judul, nilai, waktu (teks yang dipakai tes Tahap 2) -----------------------------------

@pytest.mark.parametrize("status,judul", [("dikumpul", "Sesi selesai!"), ("waktu_habis", "Waktu habis!")])
def test_judul_nilai_dan_waktu_memakai_teks_tahap_dua(status, judul):
    isi = _halaman(status=status)

    assert f'<h1 class="judul">{judul}</h1>' in isi
    assert '<p class="angka-besar"><span class="sr-saja">Nilai: </span>1/2</p>' in isi and "Waktu: 05:30" in isi
    assert 'action="/murid/lomba/mulai"' in isi and "Latihan lagi" in isi


def test_bar_nilai_per_topik_menampilkan_angka_benar_per_total():
    isi = _halaman()

    assert re.search(r'<span class="hl-topik-nama">Bilangan</span><svg [^>]*aria-label="Bilangan: 1 dari 2 benar".*?</svg>'
                     r'<span class="hl-topik-angka">1/2</span>', isi)


@pytest.mark.parametrize("nilai,jumlah,kalimat", [
    (9, 10, "Hebat!"), (8, 10, "Hebat!"), (7, 10, "Bagus!"), (5, 10, "Bagus!"), (4, 10, "Tidak apa-apa."), (0, 10, "Tidak apa-apa."),
])
def test_kalimat_semangat_netral_menurut_persen_benar(nilai, jumlah, kalimat):
    assert RP.pesan_semangat(nilai, jumlah).startswith(kalimat)


def test_nada_halaman_tidak_memberi_label_bodoh_atau_peringkat():
    isi = _halaman(butir=[_salah(nomor=n) for n in range(1, 11)]).lower()

    assert not any(kata in isi for kata in ("bodoh", "peringkat", "ranking", "juara", "gagal", "payah"))


# --- kartu soal -----------------------------------------------------------------------------

def test_kartu_benar_menampilkan_jawabanmu_dengan_tanda_dan_teks_aksesibel_tanpa_jawaban_yang_benar():
    kartu = _kartu(_butir())

    assert "Jawabanmu: <strong>B. 5</strong>" in kartu
    assert '<span class="hl-status hl-benar"><span aria-hidden="true">✓</span> benar</span>' in kartu
    assert "Jawaban yang benar" not in kartu


def test_kartu_salah_menampilkan_jawaban_yang_benar_huruf_dan_teks():
    kartu = _kartu(_salah())

    assert "Jawabanmu: <strong>A. 4</strong>" in kartu and "Jawaban yang benar: <strong>B. 5</strong>" in kartu
    assert '<span aria-hidden="true">✗</span> salah' in kartu


def test_kartu_tidak_dijawab_menyebut_status_dan_jawaban_yang_benar():
    kartu = _kartu(_butir(jawaban=None, jawaban_teks=None, benar=False))

    assert "tidak dijawab" in kartu and "Jawabanmu: <strong>belum diisi</strong>" in kartu
    assert "Jawaban yang benar: <strong>B. 5</strong>" in kartu


def test_pilihan_ganda_menampilkan_empat_pilihan_dengan_penanda_pilihanmu_dan_jawaban_benar():
    kartu = _kartu(_salah())

    pilihan = re.findall(r'<li class="(hl-pilih[^"]*)"><span class="hl-huruf">([A-D])</span>.*?<span class="hl-tanda">(.*?)</span></li>',
                         kartu)
    assert [(kelas, huruf) for kelas, huruf, _ in pilihan] == [
        ("hl-pilih hl-dipilih", "A"), ("hl-pilih hl-kunci", "B"), ("hl-pilih", "C"), ("hl-pilih", "D")]
    assert [t for _, _, t in pilihan] == ["Pilihanmu", "Jawaban benar", "", ""]


def test_pilihan_yang_dipilih_benar_menyatukan_dua_penanda():
    kartu = _kartu(_butir())

    assert '<span class="hl-tanda">Pilihanmu · Jawaban benar</span>' in kartu
    assert 'class="hl-pilih hl-dipilih hl-kunci"' in kartu


def test_pilihan_bergambar_menampilkan_svg_pilihan_sekali_dan_teks_huruf_tanpa_isi_pilihan():
    butir = _salah(pilihan=("teks-a", "teks-b", "teks-c", "teks-d"), gambar_pilihan=tuple(SVG_PILIHAN))

    kartu = _kartu(butir)

    assert all(kartu.count(svg) == 1 for svg in SVG_PILIHAN)
    assert "teks-a" not in kartu and "Jawaban yang benar: <strong>B</strong>" in kartu


def test_svg_soal_disisipkan_sekali_apa_adanya():
    assert _kartu(_butir(svg=SVG_SOAL)).count(SVG_SOAL) == 1


def test_soal_isian_menampilkan_jawaban_angka_dan_kunci_tanpa_daftar_pilihan():
    kartu = _kartu(_isian(jawaban="13", jawaban_teks="13", benar=False))

    assert "Jawabanmu: <strong>13</strong>" in kartu and "Jawaban yang benar: <strong>12</strong>" in kartu
    assert "hl-pilihan" not in kartu


def test_pembahasan_berupa_daftar_bernomor_dengan_isi_di_escape():
    kartu = _kartu(_butir(pembahasan=("a < b & c", "<script>x</script>")))

    assert '<ol class="hl-bahas"><li>a &lt; b &amp; c</li><li>&lt;script&gt;x&lt;/script&gt;</li></ol>' in kartu
    assert "<script" not in kartu


def test_tanpa_pembahasan_tidak_ada_daftar_pembahasan():
    assert "Pembahasan" not in _kartu(_butir(pembahasan=()))


def test_teks_soal_topik_dan_jawaban_isian_di_escape():
    butir = _isian(teks='<b onclick="x">Tia & "Budi"</b>', jawaban='"><i>1</i>', kunci="<u>9</u>", benar=False)

    kartu = _kartu(butir)

    assert "&lt;b onclick=&quot;x&quot;&gt;Tia &amp; &quot;Budi&quot;&lt;/b&gt;" in kartu
    assert "<b onclick" not in kartu and "<i>1</i>" not in kartu and "<u>9</u>" not in kartu
    assert "&lt;u&gt;9&lt;/u&gt;" in kartu


def test_topik_tak_dikenal_tetap_di_escape():
    assert "&lt;x&gt;" in _kartu(_butir(topik="<x>")) and "<x>" not in _kartu(_butir(topik="<x>"))


# --- label kesalahan hanya untuk guru --------------------------------------------------------

def test_halaman_anak_tidak_pernah_memuat_label_kesalahan_pengecoh():
    isi = _halaman(butir=[_salah(nomor=n) for n in range(1, 4)])

    assert KESALAHAN not in isi and "Kemungkinan kesalahan" not in isi and "kesalahan" not in isi.lower().replace("salah", "")


def test_kartu_untuk_anak_default_tidak_memuat_kesalahan_dan_untuk_guru_memuatnya_di_escape():
    butir = _salah(kesalahan='memilih <b>kecil</b> & "lupa"')

    anak = _kartu(butir)
    guru = _kartu(butir, untuk_guru=True)

    assert "Kemungkinan kesalahan" not in anak and "kecil" not in anak
    assert 'Kemungkinan kesalahan: memilih &lt;b&gt;kecil&lt;/b&gt; &amp; &quot;lupa&quot;' in guru
    assert "Jawaban anak:" in guru and "Pilihan anak" in guru and "Jawabanmu" not in guru


def test_kartu_guru_tanpa_kesalahan_bila_jawaban_benar_atau_kosong_atau_isian():
    for butir in (_butir(), _butir(jawaban=None, jawaban_teks=None, benar=False), _isian(benar=False)):
        assert "Kemungkinan kesalahan" not in _kartu(butir, untuk_guru=True)


# --- markup aman -----------------------------------------------------------------------------

def test_halaman_tanpa_skrip_penangan_kejadian_atau_tautan_luar():
    isi = _halaman()

    assert "<script" not in isi and not re.search(r"\son[a-z]+\s*=", isi, re.I)
    assert "fetch(" not in isi and "XMLHttpRequest" not in isi


def test_halaman_memuat_gaya_hasil_dan_tidak_memakai_gaya_inline_atribut():
    isi = _halaman()

    assert ".hl-soal" in isi and ' style="' not in re.sub(r"<img[^>]*>", "", isi)  # hanya <img> maskot memakai style


def test_sepuluh_kartu_memakai_id_judul_unik_untuk_aksesibilitas():
    isi = _halaman(butir=[_butir(nomor=n) for n in range(1, 11)])

    ids = re.findall(r'<h3 class="hl-judul" id="(soal-\d+)"', isi)
    assert ids == [f"soal-{n}" for n in range(1, 11)]
    assert len(re.findall(r'aria-labelledby="soal-\d+"', isi)) == 10


def test_halaman_anak_tidak_membuka_id_templat_atau_tingkat_soal():
    isi = re.sub(r"<style>.*?</style>", "", _halaman(butir=[_butir(template_id="bil_rahasia_uji", tingkat=3)]), flags=re.S)

    assert "bil_rahasia_uji" not in isi and "rahasia uji" not in isi and "tingkat" not in isi.lower()


# --- ringkasan, peta nomor, kelompok soal (hasil anak) ---------------------------------------

def _sepuluh(salah=(), kosong=()):
    butir = []
    for n in range(1, 11):
        if n in kosong:
            butir.append(_butir(nomor=n, jawaban=None, jawaban_teks=None, benar=False))
        elif n in salah:
            butir.append(_salah(nomor=n))
        else:
            butir.append(_butir(nomor=n))
    return butir


def _tanpa_gaya(isi):
    return re.sub(r"<style>.*?</style>", "", isi, flags=re.S)


@pytest.mark.parametrize("benar,berkas", [(10, "piala-v4"), (8, "piala-v4"), (7, "menyapa-v3"), (5, "menyapa-v3"),
                                            (4, "berpikir-v3"), (0, "berpikir-v3")])
def test_pose_maskot_menurut_persen_benar(benar, berkas):
    butir = _sepuluh(salah=range(benar + 1, 11))

    isi = _halaman(butir=butir)

    assert f"maskot-{berkas}-96.png" in isi and isi.count("/aset/maskot-") == 1


@pytest.mark.parametrize("benar,naik,berkas", [(5, True, "naik-level-v4"), (0, True, "naik-level-v4"),
                                               (5, False, "menyapa-v3"), (9, True, "piala-v4")])
def test_pose_naik_level_bila_nilai_naik_tapi_belum_tinggi(benar, naik, berkas):
    butir = _sepuluh(salah=range(benar + 1, 11))

    isi = RP.halaman_hasil_anak(_hasil(butir=butir), "Naik 2 dari latihan sebelumnya", naik).decode()

    assert f"maskot-{berkas}-96.png" in isi and isi.count("/aset/maskot-") == 1


def test_bilah_atas_dan_tombol_bawah_menautkan_ke_beranda_murid():
    isi = _halaman()

    assert '<a class="tautan-beranda" href="/murid">' in isi and "Beranda</a></header>" in isi
    assert '<a class="tombol sekunder" href="/murid">Beranda</a>' in isi
    assert isi.index("Latihan lagi") > isi.index("Soal yang benar")


def test_kalimat_banding_tampil_hanya_bila_diberikan():
    tanpa = _halaman()
    dengan = RP.halaman_hasil_anak(_hasil(), "Naik 2 dari latihan sebelumnya").decode()

    assert "hl-banding" not in _tanpa_gaya(tanpa) and "latihan sebelumnya" not in tanpa
    assert '<p class="hl-banding">Naik 2 dari latihan sebelumnya</p>' in dengan


def test_kalimat_banding_di_escape():
    isi = RP.halaman_hasil_anak(_hasil(), '<b>x</b> & "y"').decode()

    assert "&lt;b&gt;x&lt;/b&gt; &amp; &quot;y&quot;" in isi and "<b>x</b>" not in isi


def test_peta_memuat_sepuluh_nomor_bertaut_ke_kartu_dengan_status_benar_salah_kosong():
    isi = _tanpa_gaya(_halaman(butir=_sepuluh(salah={2}, kosong={5})))

    peta = isi[isi.index('<ol class="peta">'):isi.index("</ol>", isi.index('<ol class="peta">'))]
    assert len(re.findall(r'<a class="peta-nomor ', peta)) == 10
    assert re.findall(r'href="#soal-(\d+)"', peta) == [str(n) for n in range(1, 11)]
    assert 'class="peta-nomor hl-salah" href="#soal-2"' in peta and 'class="peta-nomor hl-kosong-jawab" href="#soal-5"' in peta
    assert peta.count("hl-benar") == 8
    assert "salah</span>" in peta and "belum diisi</span>" in peta and peta.count("benar</span>") == 8


def test_soal_salah_dan_kosong_masing_masing_dalam_details_terbuka_dengan_ringkasan_nomor_topik_status():
    isi = _tanpa_gaya(_halaman(butir=_sepuluh(salah={2}, kosong={5})))

    assert "Yang perlu dilihat lagi (2)" in isi
    assert "<details class=\"hl-lipat\" open><summary>Soal 2 \u00b7 Bilangan \u00b7 salah</summary>" in isi
    assert "<details class=\"hl-lipat\" open><summary>Soal 5 \u00b7 Bilangan \u00b7 belum diisi</summary>" in isi
    assert isi.count('class="hl-lipat" open') == 2


def test_soal_benar_dalam_satu_details_tertutup_bila_ada_yang_salah():
    isi = _tanpa_gaya(_halaman(butir=_sepuluh(salah={2})))

    assert '<details class="hl-lipat"><summary>Soal yang benar (9)</summary>' in isi
    benar = isi[isi.index("Soal yang benar (9)"):]
    assert benar.count('class="hl-soal"') == 9 and 'id="soal-2"' not in benar


def test_semua_benar_hanya_details_benar_dan_terbuka_tanpa_bagian_perlu_dilihat():
    isi = _tanpa_gaya(_halaman(butir=_sepuluh()))

    assert "Yang perlu dilihat lagi" not in isi
    assert '<details class="hl-lipat" open><summary>Soal yang benar (10)</summary>' in isi


def test_semua_sepuluh_id_soal_tetap_ada_tepat_satu_kali_untuk_anchor_peta():
    for butir in (_sepuluh(), _sepuluh(salah={1, 2, 3}, kosong={10}), _sepuluh(kosong=range(1, 11))):
        isi = _halaman(butir=butir)

        assert re.findall(r'<h3 class="hl-judul" id="(soal-\d+)"', isi) == [f"soal-{n}" for n in range(1, 11)] or \
            sorted(re.findall(r'<h3 class="hl-judul" id="(soal-\d+)"', isi)) == sorted(f"soal-{n}" for n in range(1, 11))


def test_kartu_soal_tidak_berubah_dibungkus_di_luar():
    butir = _salah(nomor=4)

    isi = _halaman(butir=[butir])

    assert _kartu(butir) in isi


def test_hasil_anak_tanpa_skrip_dan_tanpa_label_kesalahan_walau_ada_banyak_salah():
    isi = _halaman(butir=[_salah(nomor=n) for n in range(1, 11)])

    assert "<script" not in isi and KESALAHAN not in isi and "Kemungkinan kesalahan" not in isi
    assert not re.search(r"\son[a-z]+\s*=", isi, re.I)
