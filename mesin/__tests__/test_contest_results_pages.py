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
    assert "Nilai: 1 dari 2" in isi and "Waktu: 05:30" in isi
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

    assert ".hl-soal" in isi and ' style="' not in isi


def test_sepuluh_kartu_memakai_id_judul_unik_untuk_aksesibilitas():
    isi = _halaman(butir=[_butir(nomor=n) for n in range(1, 11)])

    ids = re.findall(r'<h3 class="hl-judul" id="(soal-\d+)"', isi)
    assert ids == [f"soal-{n}" for n in range(1, 11)]
    assert len(re.findall(r'aria-labelledby="soal-\d+"', isi)) == 10


def test_halaman_anak_tidak_membuka_id_templat_atau_tingkat_soal():
    isi = re.sub(r"<style>.*?</style>", "", _halaman(butir=[_butir(template_id="bil_rahasia_uji", tingkat=3)]), flags=re.S)

    assert "bil_rahasia_uji" not in isi and "rahasia uji" not in isi and "tingkat" not in isi.lower()
