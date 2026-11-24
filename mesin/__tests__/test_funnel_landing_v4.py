"""Landing `/cek-kemampuan` gaya playful v4: markup, klaim, skrip, CSS (data sintetis)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand  # noqa: E402
import design_tokens as T  # noqa: E402
import funnel_landing_browser  # noqa: E402
import funnel_landing_pages  # noqa: E402
import funnel_landing_style  # noqa: E402
import funnel_pages  # noqa: E402

CTA_HREF = 'href="/daftar?jalur=cek"'
KATA_TERLARANG = (
    "Paket Coba", "pasti", "dijamin", "menjamin", "diagnosis lengkap", "pasti akurat",
    "Rp200.000", "Rp151.000",
)


@pytest.fixture()
def halaman(monkeypatch) -> str:
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    return funnel_pages.halaman_cek_kemampuan().decode()


def _utama(isi: str) -> str:
    return isi.split('id="konten"', 1)[1].split("</main>", 1)[0]


def _pisah_selektor(daftar: str) -> list:
    """Pisahkan daftar selektor pada koma tingkat atas (bukan di dalam kurung)."""
    hasil, kedalaman, awal = [], 0, 0
    for i, c in enumerate(daftar):
        kedalaman += {"(": 1, ")": -1}.get(c, 0)
        if c == "," and kedalaman == 0:
            hasil.append(daftar[awal:i])
            awal = i + 1
    hasil.append(daftar[awal:])
    return hasil


def _teks_terlihat(isi: str) -> str:
    badan = isi.rsplit("</style>", 1)[1]
    badan = re.sub(r"<script>.*?</script>|<svg.*?</svg>", " ", badan, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", badan).split())


def test_satu_cta_utama_dan_satu_h1(halaman):
    utama = _utama(halaman)
    assert utama.count('class="tombol-coral"') == 1
    assert halaman.count(CTA_HREF) == 1
    assert len(re.findall(r"<h1[ >]", utama)) == 1
    h1, em = funnel_landing_pages.COPY_H1
    assert f"{h1}<em>{em}</em>" in utama
    assert f"{funnel_landing_pages.COPY_CTA_LANDING} " in utama


def test_tautan_mulai_bukan_tombol_cta(halaman):
    utama = _utama(halaman)
    assert utama.count('href="#mulai"') == 3  # tautan solusi, demo, penutup
    assert 'id="mulai"' in utama
    assert funnel_landing_pages.COPY_TAUTAN_MULAI in utama


def test_tanpa_kata_terlarang_di_teks_terlihat_dan_skrip(halaman):
    teks = _teks_terlihat(halaman).lower()
    skrip = funnel_landing_browser.SKRIP_LANDING_CEK.lower()
    for kata in KATA_TERLARANG:
        assert kata.lower() not in teks, kata
        assert kata.lower() not in skrip, kata
    assert "25 menit" not in teks


def test_harga_hanya_di_faq_dan_pembatalan_15_soal(halaman):
    utama = _utama(halaman)
    faq = utama.split('id="judul-faq"', 1)[1]
    assert utama.count("Rp49.000") == faq.count("Rp49.000") == 2      # harga sekali bayar + deposit, keduanya di FAQ
    assert "tidak dapat dikembalikan" in faq
    # DRAF 5 (24 Nov 2026, deposit): deposit memotong tagihan kelas 90 hari, janji 48 jam, hubungi tim bila terlambat.
    assert "deposit yang memotong tagihan kelas bersama Guru (berlaku 90 hari)" in faq and "48 jam" in faq
    assert "Tidak ada uang kembali otomatis" in faq and "hubungi tim lewat WhatsApp" in faq
    for lama in ("3×24 jam", "uang kembali penuh", "voucher", "memilih menunggu", "halaman pesanan", "program belajar"):
        assert lama not in faq, lama
    assert "15 soal" in faq
    assert "25 menit" not in halaman
    assert "cek-tiket-st" not in utama
    assert funnel_pages.COPY_KUOTA_AWAL not in utama


def test_tautan_ke_contoh_tanpa_tiket_peta(halaman):
    assert f'href="{funnel_pages.JALUR_CONTOH}"' in halaman
    assert 'href="/paket-coba"' not in _utama(halaman)
    assert funnel_landing_pages.COPY_PETA_LANJUT in halaman
    assert funnel_pages.COPY_LABEL_CONTOH in halaman
    assert 'id="contoh-hasil"' in halaman


def test_bagian_cerita_statis_tiga_situasi_dan_solusi(halaman):
    utama = _utama(halaman)
    cerita = utama.split('aria-labelledby="judul-cerita"', 1)[1].split("</section>", 1)[0]
    assert cerita.count('<li><span class="cek-ubin-st') == len(funnel_landing_pages.COPY_SITUASI) == 3
    for _i, _w, judul, isi in funnel_landing_pages.COPY_SITUASI:
        assert judul in cerita and isi in cerita
    assert "<q>" in cerita and funnel_landing_pages.COPY_JEMBATAN in cerita
    assert funnel_landing_pages.COPY_AKAR_JUDUL in cerita
    for butir in funnel_landing_pages.COPY_SOLUSI_ISI:
        assert butir in cerita
    assert "<button" not in cerita and "data-cek" not in cerita
    assert "cek-chip-st" not in utama and "Coba malam ini" not in utama


def test_sapaan_bunda_tanpa_anda_di_landing(halaman):
    teks = _teks_terlihat("<style></style>" + halaman.split('id="konten"', 1)[1].split("</main>", 1)[0])
    assert "Anda" not in teks and "anda" not in teks.split()
    assert "Bunda" in teks


def test_contoh_berlabel_dan_hanya_nama_sintetis_aisyah(halaman):
    utama = _utama(halaman)
    assert "Aisyah · kelas 4" in utama
    assert "Contoh hasil" in utama and "Peta Kemampuan" in utama
    assert "Bu Contoh" not in utama
    assert "(sintetis)" not in utama.replace("Contoh sintetis", "")


def test_kartu_guru_tidak_tampil_saat_profil_kosong(halaman):
    assert funnel_pages.PROFIL_GURU == ()
    assert "funnel-guru-st" not in _utama(halaman)
    assert funnel_pages.COPY_JUDUL_PROFIL_GURU not in _utama(halaman)
    assert funnel_pages.COPY_JUDUL_PROFIL_GURU_LANDING not in _utama(halaman)


def test_kartu_guru_tampil_bila_profil_terisi(monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    monkeypatch.setattr(funnel_pages, "PROFIL_GURU", ({"nama": "Guru Uji", "latar": "S1", "lama_mengajar": "3 tahun"},))
    isi = funnel_pages.halaman_cek_kemampuan().decode()
    assert "funnel-guru-st" in _utama(isi) and "Guru Uji" in isi
    assert funnel_pages.COPY_JUDUL_PROFIL_GURU_LANDING in _utama(isi)
    assert funnel_pages.COPY_JUDUL_PROFIL_GURU not in _utama(isi)


def test_maskot_satu_per_section(halaman):
    utama = _utama(halaman)
    bagian = re.findall(r"<section.*?</section>", utama, flags=re.S)
    assert len(bagian) >= 7
    assert all(b.count("<img") <= 1 for b in bagian)
    assert utama.count("<img") == 2
    assert funnel_pages.MASKOT_MENYAPA in bagian[0]
    assert funnel_landing_pages.MASKOT_MERAYAKAN in bagian[-1]


def test_topbar_logo_asli_tanpa_gambar_ulang(halaman):
    assert brand.mark("topbar") in halaman
    assert "lockup-horizontal" not in halaman or '<img src="/aset/lockup-horizontal.svg"' in halaman
    assert 'aria-label="Jagomat"' not in halaman  # tidak ada logo SVG inline buatan sendiri


def test_tanpa_style_inline_hex_dan_entitas_numerik_di_badan(halaman):
    badan = _utama(halaman)
    assert 'style="' not in badan
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b(?![\w-])", re.sub(r'href="#[\w-]+"', "", badan))
    assert "&#" not in badan


def test_skrip_polos_tanpa_atribut_dan_tanpa_api_terlarang(halaman):
    skrip = funnel_landing_browser.SKRIP_LANDING_CEK
    assert f"<script>{skrip}</script>" in halaman
    assert not re.search(r"<script\s", halaman)
    assert "<script" not in _utama(halaman)
    for terlarang in ("onclick=", "onerror=", "fetch(", "XMLHttpRequest", "localStorage", "sessionStorage",
                      "eval(", "innerHTML", "document.cookie", "</script"):
        assert terlarang not in skrip, terlarang
    assert not re.search(r"\son[a-z]+\s*=", _utama(halaman))
    assert skrip.count("{") == skrip.count("}")


def test_fallback_tanpa_js_penjelasan_demo_dan_faq(halaman):
    utama = _utama(halaman)
    assert funnel_landing_pages.COPY_DEMO_TEPAT in utama
    kunci = re.search(r"<details class=\"cek-kunci-d-st\".*?</details>", utama, flags=re.S).group(0)
    assert "24 + 4 = 28" in kunci
    assert "data-cek-umpan" in utama and re.search(r"data-cek-umpan[^>]*hidden", utama)
    for _i, _w, tanya, _j in funnel_landing_pages.COPY_FAQ:
        assert tanya in utama
    for butir in funnel_pages.COPY_BATAS_HASIL:
        assert butir in utama


def test_demo_hanya_menandai_satu_langkah_salah(halaman):
    utama = _utama(halaman)
    assert utama.count("data-cek-langkah") == 3
    assert utama.count("data-cek-tepat") == 1
    assert utama.count("data-cek-digit") == 1


def test_skrip_tanpa_sisa_chip_gejala_dan_memakai_kait_di_markup(halaman):
    utama = _utama(halaman)
    skrip = funnel_landing_browser.SKRIP_LANDING_CEK
    for kait in ("data-cek-demo", "data-cek-langkah", "data-cek-tepat", "data-cek-umpan", "data-cek-digit", "data-cek-kunci"):
        assert kait in skrip, kait
        assert kait in utama, kait
    assert "aktifkanGejala" not in skrip and "data-cek-gejala" not in skrip
    assert "data-umpan-salah" in utama and "data-umpan-tepat" in utama


def test_kartu_hero_dapat_difokus_tanpa_js(halaman):
    assert _utama(halaman).count('class="cek-kt-st') == 3
    assert _utama(halaman).count('tabindex="0"') == 3


def test_semua_kelas_cek_di_markup_terdefinisi_di_css(halaman):
    kelas_markup = set(re.findall(r"cek-[a-z0-9-]+-st", _utama(halaman)))
    kelas_skrip = set(re.findall(r"cek-[a-z0-9-]+-st", funnel_landing_browser.SKRIP_LANDING_CEK))
    css = funnel_landing_style.GAYA_LANDING_CEK
    for kelas in kelas_markup | kelas_skrip:
        assert f".{kelas}" in css or f"@keyframes {kelas}" in css, kelas


def test_css_tanpa_hex_rgba_important_dan_animasi_hanya_saat_gerak_boleh():
    sumber = Path(funnel_landing_style.__file__).read_text()
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", sumber)
    css = funnel_landing_style.GAYA_LANDING_CEK
    assert "!important" not in css
    luar = re.sub(r"@media \(prefers-reduced-motion: no-preference\) \{.*?\n\}\n", "", css, flags=re.S)
    assert "transition:" not in luar
    assert "animation:" not in luar
    assert "scroll-behavior" not in luar


def test_css_hanya_memakai_namespace_cek_dan_font_minimal_14px():
    css = funnel_landing_style.GAYA_LANDING_CEK
    css_tanpa_media = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for pemilih in re.findall(r"(?:^|\n)([^\s@}{][^{}\n]*)\{", css_tanpa_media):
        for bagian in _pisah_selektor(pemilih):
            assert "cek-" in bagian, bagian
    for ukuran in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", css):
        assert float(ukuran) >= 14 or ukuran in ("28", "34"), ukuran
    assert T.UKURAN_TEKS_LABEL == ".875rem"


def test_css_dipasang_hanya_saat_funnel_aktif(monkeypatch):
    from style_stitch import gaya_stitch

    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    assert ".cek-halaman-st" not in gaya_stitch()
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    assert ".cek-halaman-st" in gaya_stitch()


def test_paket_coba_dan_contoh_tidak_memuat_skrip_landing(monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    isi = funnel_pages.halaman_paket_coba().decode()
    assert funnel_landing_browser.SKRIP_LANDING_CEK not in isi
    assert "cek-halaman-st" not in isi.rsplit("</style>", 1)[1]


def test_jumlah_kata_landing_wajar(halaman):
    jumlah = len(_teks_terlihat("<style></style>" + _utama(halaman)).split())
    assert jumlah <= 900, jumlah
