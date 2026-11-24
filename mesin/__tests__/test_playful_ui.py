"""Kontrak komponen ceria bersama (`playful_components` + `playful_style.GAYA_CERIA`)."""
import re

import pytest

import brand
import playful_components as C
import playful_style as S
import style_stitch

JAHAT = '<script>alert(1)</script>"&\''
JAHAT_ATRIBUT = '" onerror="alert(1)" onclick="x'


def _semua_komponen(teks=JAHAT):
    return {
        "sorot": C.sorot(teks),
        "stiker": C.stiker(teks),
        "stiker_kanan": C.stiker(teks, "kanan"),
        "hero": C.hero(C.sorot("x"), konfeti=True),
        "bicara": C.maskot_bicara("menyapa", teks, teks, teks),
        "ortu": C.kartu_ajakan_ortu("/murid/orang-tua", teks, teks, [teks, teks], label=teks,
                                    judul_awal=teks, judul_sorot=teks),
        "navy": C.kartu_navy(C.sorot(teks), "<p>isi</p>", "/murid/langganan", teks, label=teks, id_=teks),
        "lencana": C.lencana(teks, "kuning"),
        "status": C.kartu_status("koral", teks, teks, "<p>isi</p>", id_=teks, tombol=("/murid/langganan", teks)),
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


@pytest.mark.parametrize("nama,isi", sorted(_semua_komponen(JAHAT_ATRIBUT).items()))
def test_kutip_penutup_atribut_dari_pemanggil_tidak_lolos(nama, isi):
    assert '" onerror' not in isi and '" onclick' not in isi, nama


def test_nilai_atribut_berkutip_ter_escape_jadi_entitas():
    navy = C.kartu_navy("j", "", "/x", "t", label="l", id_=JAHAT_ATRIBUT)
    status = C.kartu_status("hijau", "l", "j", id_=JAHAT_ATRIBUT)
    aman = "&quot; onerror=&quot;alert(1)&quot; onclick=&quot;x"
    assert f'id="{aman}"' in navy and f'id="{aman}"' in status


def test_teks_pemanggil_muncul_sebagai_entitas():
    isi = C.maskot_bicara("menyapa", "<b>a</b>", "<i>b</i>", "&c")
    assert "&lt;b&gt;a&lt;/b&gt;" in isi and "<b>&lt;i&gt;b&lt;/i&gt;</b>" in isi and "&amp;c" in isi


def test_maskot_bicara_memakai_brand_sebagai_hiasan_beralt_kosong():
    isi = C.maskot_bicara("menyapa", "Halo, ", "Aisyah", "!")
    assert "/aset/maskot-menyapa-v3-96.png" in isi
    assert 'width="96"' in isi and 'class="ceria-maskot"' in isi
    assert 'alt=""' in isi  # hiasan: pesan sudah dibawa teks gelembung
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
    assert 'alt=""' in isi and "Judul</h3>" in isi and "<p>Teks</p>" in isi
    assert 'alt="Maskot gembira"' in C.banner_umpan_balik(betul, "J", "T", alt="Maskot gembira")


def test_banner_belum_tepat_bukan_merah():
    css = S.GAYA_CERIA
    aturan = re.search(r"\.ceria-banner\.ceria-hampir\s*\{([^}]*)\}", css).group(1)
    import design_tokens as T
    assert T.LATAR_CATATAN in aturan and T.BORDER_CATATAN in aturan
    for merah in (T.LATAR_GALAT, T.BORDER_GALAT, T.TEKS_GALAT, T.AKSEN_KORAL_TUA, T.AKSEN_MURID_KORAL):
        assert merah not in aturan


def test_kartu_ajakan_ortu_hanya_satu_tautan():
    isi = C.kartu_ajakan_ortu("/murid/orang-tua", "Untuk Ayah/Bunda · lihat paket", "Rp39.000/bulan",
                              ["Sesi sebanyak yang anak mau", "1 sesi gratis tetap ada tiap hari"])
    assert isi.count("<a ") == 1 and isi.count("href=") == 1
    assert 'href="/murid/orang-tua"' in isi
    assert isi.count("<li>") == 2 and "Rp39.000/bulan" in isi and "mulai" not in isi
    assert 'class="ceria-sorot">tanpa batas<' in isi
    assert "UNTUK" not in isi and "Untuk Ayah/Bunda</p>" in isi


@pytest.mark.parametrize("href", ["https://x.example/", "//x.example/", "javascript:alert(1)", "", "murid/orang-tua",
                                  "/\\evil.com", "/\t/evil.com", "/ x", "/x\n", "/x\x00", "/x\x7f", "/x\u00a0y"])
def test_kartu_ajakan_ortu_menolak_tautan_luar(href):
    with pytest.raises(ValueError):
        C.kartu_ajakan_ortu(href, "a", "b")


@pytest.mark.parametrize("href", ["/murid/orang-tua", "/murid/langganan?x=1"])
def test_kartu_ajakan_ortu_meloloskan_alamat_dalam(href):
    assert f'href="{href}"' in C.kartu_ajakan_ortu(href, "a", "b")


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


def test_kartu_ajakan_ortu_bentuk_html_tidak_berubah_setelah_memakai_kartu_navy():
    isi = C.kartu_ajakan_ortu("/murid/orang-tua", "Lihat", "Rp1/bulan", poin=("a", "b"), level=2)
    assert isi == ('<section class="ceria-ortu"><p class="ceria-alis">Untuk Ayah/Bunda</p><h2 class="ceria-judul">'
                   'Latihan <span class="ceria-sorot">tanpa batas</span> Rp1/bulan</h2>'
                   '<ul class="ceria-centang"><li>a</li><li>b</li></ul>'
                   '<a class="ceria-tombol" href="/murid/orang-tua">Lihat</a></section>')


def test_kartu_navy_bebas_judul_id_dan_tepat_satu_tautan():
    isi = C.kartu_navy("Belum berlangganan", "<p>x</p>", "/murid/langganan", "Lihat paket", label="Langganan", id_="ortu-langganan")
    assert 'id="ortu-langganan"' in isi and isi.count("<a ") == 1 and "Belum berlangganan</h3>" in isi
    assert C.kartu_navy("j", "", "/x", "t", label="l", id_="").count("id=") == 0


@pytest.mark.parametrize("href", ["https://contoh.id", "//contoh.id", "murid", "javascript:alert(1)"])
def test_kartu_navy_dan_status_menolak_tautan_luar(href):
    with pytest.raises(ValueError):
        C.kartu_navy("j", "", href, "t", label="l")
    with pytest.raises(ValueError):
        C.kartu_status("hijau", "l", "j", tombol=(href, "t"))


def test_lencana_dan_kartu_status_menolak_nada_dan_level_tak_dikenal():
    with pytest.raises(ValueError):
        C.lencana("x", "merah")
    with pytest.raises(ValueError):
        C.kartu_status("ungu", "x", "y")
    with pytest.raises(ValueError):
        C.kartu_status("hijau", "x", "y", level=5)
    with pytest.raises(ValueError):
        C.kartu_navy("j", "", "/x", "t", label="l", level=1)


@pytest.mark.parametrize("nada", C.NADA_STATUS)
def test_kartu_status_selalu_berlencana_teks_dan_tanpa_tombol_bila_tak_diminta(nada):
    isi = C.kartu_status(nada, "Teks status", "Judul", "<p>isi</p>")
    assert 'class="ceria-lencana ceria-lencana-%s">Teks status</span>' % nada in isi and "<a " not in isi
    assert "ceria-status-%s" % nada in isi


def test_gelembung_lebih_spesifik_dari_aturan_paragraf_halaman_harian():
    import harian_style
    assert ".ceria-maskot-baris .ceria-gelembung {" in S.GAYA_CERIA
    assert not re.search(r"(?m)^\.ceria-gelembung \{", S.GAYA_CERIA)  # selektor polos (0,1,0) kalah dari `.hr-isi p`
    assert ".hr-isi h1, .hr-isi h2, .hr-isi h3, .hr-isi p { margin: 0; }" in harian_style.GAYA_HARIAN
