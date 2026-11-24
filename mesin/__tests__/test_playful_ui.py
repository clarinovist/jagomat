"""Kontrak komponen ceria bersama (`playful_components` + `playful_style.GAYA_CERIA`)."""
import re

import pytest

import brand
import playful_components as C
import playful_style as S
import style_stitch

JAHAT = '<script>alert(1)</script>"&\''


def _semua_komponen(teks=JAHAT):
    return {
        "sorot": C.sorot(teks),
        "stiker": C.stiker(teks),
        "stiker_kanan": C.stiker(teks, "kanan"),
        "hero": C.hero(C.sorot("x"), konfeti=True),
        "bicara": C.maskot_bicara("menyapa", teks, teks, teks),
        "ortu": C.kartu_ajakan_ortu("/murid/orang-tua", teks, teks, [teks, teks], label=teks,
                                    judul_awal=teks, judul_sorot=teks),
        "titik_teal": C.titik_hari({0, 3}),
        "titik_krem": C.titik_hari({6}, latar="krem"),
        "progres": C.progres_soal(2, 3),
        "skor": C.skor_besar(8),
        "banner_betul": C.banner_umpan_balik(True, teks, teks),
        "banner_belum": C.banner_umpan_balik(False, teks, teks),
    }


@pytest.mark.parametrize("nama,isi", sorted(_semua_komponen().items()))
def test_komponen_meng_escape_input_dan_tanpa_script(nama, isi):
    assert "<script" not in isi.lower(), nama
    assert "alert(1)" not in isi.replace("&lt;script&gt;alert(1)&lt;/script&gt;", ""), nama
    assert "onerror" not in isi.lower() and "onclick" not in isi.lower()


def test_teks_pemanggil_muncul_sebagai_entitas():
    isi = C.maskot_bicara("menyapa", "<b>a</b>", "<i>b</i>", "&c")
    assert "&lt;b&gt;a&lt;/b&gt;" in isi and "<b>&lt;i&gt;b&lt;/i&gt;</b>" in isi and "&amp;c" in isi


def test_maskot_bicara_memakai_brand_dengan_alt_bermakna():
    isi = C.maskot_bicara("menyapa", "Halo, ", "Aisyah", "!")
    assert "/aset/maskot-menyapa-v3-96.png" in isi
    assert 'width="96"' in isi and 'class="ceria-maskot"' in isi
    alt = re.search(r'alt="([^"]*)"', isi).group(1)
    assert alt and "menyapa" in alt
    assert isi.count("<img") == 1
    assert "Halo, <b>Aisyah</b>!" in isi


def test_alt_boleh_diganti_pemanggil():
    assert 'alt="Maskot gembira"' in C.maskot_bicara("merayakan", "ok", alt="Maskot gembira")


def test_pose_tidak_dikenal_ditolak():
    with pytest.raises(ValueError):
        C.maskot_bicara("terbang", "x")
    with pytest.raises(ValueError):
        C.banner_umpan_balik(True, "a", "b", pose="terbang")


@pytest.mark.parametrize("betul,pose,kelas", [(True, "merayakan", "ceria-betul"), (False, "berpikir", "ceria-hampir")])
def test_banner_umpan_balik_varian_dan_slot_maskot(betul, pose, kelas):
    isi = C.banner_umpan_balik(betul, "Judul", "Teks")
    assert kelas in isi and f"maskot-{pose}-v3-96.png" in isi and 'role="status"' in isi
    assert re.search(r'alt="[^"]+"', isi)


def test_banner_belum_tepat_bukan_merah():
    css = S.GAYA_CERIA
    aturan = re.search(r"\.ceria-banner\.ceria-hampir\s*\{([^}]*)\}", css).group(1)
    import design_tokens as T
    assert T.LATAR_CATATAN in aturan and T.BORDER_CATATAN in aturan
    for merah in (T.LATAR_GALAT, T.BORDER_GALAT, T.TEKS_GALAT, T.AKSEN_KORAL_TUA, T.AKSEN_MURID_KORAL):
        assert merah not in aturan


def test_kartu_ajakan_ortu_hanya_satu_tautan():
    isi = C.kartu_ajakan_ortu("/murid/orang-tua", "Untuk Ayah/Bunda · lihat paket", "mulai Rp39.000/bulan",
                              ["Sesi sebanyak yang anak mau", "1 sesi gratis tetap ada tiap hari"])
    assert isi.count("<a ") == 1 and isi.count("href=") == 1
    assert 'href="/murid/orang-tua"' in isi
    assert isi.count("<li>") == 2 and "mulai Rp39.000/bulan" in isi
    assert 'class="ceria-sorot">tanpa batas<' in isi
    assert "UNTUK" not in isi and "Untuk Ayah/Bunda</p>" in isi


@pytest.mark.parametrize("href", ["https://x.example/", "//x.example/", "javascript:alert(1)", "", "murid/orang-tua"])
def test_kartu_ajakan_ortu_menolak_tautan_luar(href):
    with pytest.raises(ValueError):
        C.kartu_ajakan_ortu(href, "a", "b")


def test_kartu_ajakan_ortu_tanpa_poin_tak_membuat_daftar():
    assert "<ul" not in C.kartu_ajakan_ortu("/x", "a", "b")


def test_level_judul_dibatasi():
    for fn in (lambda: C.kartu_ajakan_ortu("/x", "a", "b", level=1), lambda: C.banner_umpan_balik(True, "a", "b", level=6)):
        with pytest.raises(ValueError):
            fn()
    assert "<h2 " in C.kartu_ajakan_ortu("/x", "a", "b", level=2)


def test_titik_hari_tujuh_hari_label_dan_status_bukan_warna_saja():
    isi = C.titik_hari({0, 2})
    for nama in ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"):
        assert nama in isi
    assert isi.count("<li ") == 7 and isi.count('class="ceria-isi"') == 2
    assert isi.count(", berlatih<") == 2 and isi.count(", belum berlatih<") == 5
    assert "ceria-krem" not in isi and "ceria-krem" in C.titik_hari(set(), latar="krem")


@pytest.mark.parametrize("terisi", [{7}, {-1}, {0, 9}])
def test_titik_hari_menolak_indeks_di_luar_pekan(terisi):
    with pytest.raises(ValueError):
        C.titik_hari(terisi)


def test_titik_hari_menolak_latar_tak_dikenal():
    with pytest.raises(ValueError):
        C.titik_hari(set(), latar="merah")


def test_progres_soal_sepuluh_segmen_sudah_kini_belum():
    isi = C.progres_soal(2, 3)
    assert isi.count("<span") == 10
    assert isi.count("ceria-sudah") == 2 and isi.count("ceria-kini") == 1
    assert 'aria-label="2 dari 10 soal sudah dijawab"' in isi
    assert C.progres_soal(10).count("ceria-sudah") == 10 and "ceria-kini" not in C.progres_soal(10)


@pytest.mark.parametrize("sudah,kini", [(-1, None), (11, None), (2, 0), (2, 11)])
def test_progres_soal_menolak_nilai_tidak_sah(sudah, kini):
    with pytest.raises(ValueError):
        C.progres_soal(sudah, kini)


def test_skor_besar_teks_dan_titik_terisi_sebanyak_benar():
    isi = C.skor_besar(8)
    assert '<p class="ceria-skor"><b>8</b> dari 10 benar</p>' in isi
    assert isi.count("<i") == 10 and isi.count('class="ceria-isi"') == 8
    assert 'class="ceria-bintang" aria-hidden="true"' in isi
    assert C.skor_besar(0).count("ceria-isi") == 0 and C.skor_besar(10).count("ceria-isi") == 10
    for kata in ("peringkat", "persentil", "dibanding"):
        assert kata not in isi.lower()


@pytest.mark.parametrize("benar,jumlah", [(-1, 10), (11, 10), (1, 0)])
def test_skor_besar_menolak_nilai_tidak_sah(benar, jumlah):
    with pytest.raises(ValueError):
        C.skor_besar(benar, jumlah)


def test_hero_simbol_dan_konfeti_dekoratif_untuk_pembaca_layar():
    tanpa = C.hero("<p>isi</p>")
    dengan = C.hero("<p>isi</p>", konfeti=True)
    assert "<p>isi</p>" in tanpa and 'class="ceria-simbol" aria-hidden="true"' in tanpa
    assert "ceria-konfeti" not in tanpa
    assert dengan.count("<i></i>") == 8 and 'class="ceria-konfeti" aria-hidden="true"' in dengan


def test_stiker_arah():
    assert "ceria-miring-kanan" not in C.stiker("a") and "ceria-miring-kanan" in C.stiker("a", "kanan")
    with pytest.raises(ValueError):
        C.stiker("a", "atas")


def test_tanpa_istilah_diagnosis_atau_kunci_di_komponen_dan_css():
    css = re.sub(r"/\*.*?\*/", "", S.GAYA_CERIA, flags=re.S)  # komentar bukan teks tampil
    gabungan = (" ".join(_semua_komponen("teks biasa").values()) + css).lower()
    for terlarang in ("diagnosis", "malrule", "kode_final", "kunci", "laporan guru"):
        assert terlarang not in gabungan, terlarang


def test_css_token_saja_tanpa_hex_atau_rgba():
    """Periksa SUMBER (placeholder `{T.X}` dibuang): CSS hasil render memang berisi nilai token."""
    from pathlib import Path
    sumber = (Path(S.__file__)).read_text()
    sumber = re.sub(r"\{T\.[A-Z0-9_]+\}", "", sumber)
    sumber = re.sub(r"/\*.*?\*/", "", sumber, flags=re.S)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|%23[0-9a-fA-F]{3,8}\b", sumber)


def _tanpa_blok_media(css):
    """Buang blok `@media (prefers-reduced-motion: no-preference) { ... }` dengan pencocokan kurung."""
    mulai = css.index("@media (prefers-reduced-motion: no-preference)")
    kedalaman, i = 0, css.index("{", mulai)
    for j in range(i, len(css)):
        kedalaman += (css[j] == "{") - (css[j] == "}")
        if kedalaman == 0:
            return css[:mulai] + css[j + 1:], css[mulai:j + 1]
    raise AssertionError("blok media tidak seimbang")


def test_animasi_hanya_di_dalam_prefers_reduced_motion_no_preference():
    luar, dalam = _tanpa_blok_media(S.GAYA_CERIA)
    assert "prefers-reduced-motion" in S.GAYA_CERIA
    for kata in ("animation", "transition", "@keyframes"):
        assert kata not in luar, kata
        assert kata in dalam, kata
    assert "!important" not in S.GAYA_CERIA


def test_keadaan_diam_lengkap_tanpa_opacity_nol_di_luar_media():
    luar, _ = _tanpa_blok_media(S.GAYA_CERIA)
    assert "opacity: 0" not in luar and "visibility: hidden" not in luar and "display: none" not in luar


def test_semua_kelas_css_berawalan_ceria_dan_tidak_bentrok():
    css = re.sub(r"/\*.*?\*/", "", S.GAYA_CERIA, flags=re.S)
    css = re.sub(r"\.\d[\w.]*", "", css)  # buang angka desimal (".6s")
    kelas = set(re.findall(r"\.([a-zA-Z][\w-]*)", css))
    assert kelas and all(k.startswith("ceria-") for k in kelas), sorted(k for k in kelas if not k.startswith("ceria-"))


def test_gaya_ceria_tidak_masuk_gaya_stitch():
    assert "ceria-" not in style_stitch.gaya_stitch()


def test_modul_tidak_memuat_kode_debug_dan_tidak_mengimpor_basis_data():
    from pathlib import Path
    for nama in ("playful_components.py", "playful_style.py"):
        sumber = (Path(brand.__file__).parent / nama).read_text()
        assert "print(" not in sumber and "console." not in sumber
        assert "sqlite3" not in sumber and "import database" not in sumber
