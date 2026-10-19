"""Kontainer dan komponen bersama halaman /anak/<id> (selaras docs/mockup).

Keempat tab harus berbagi satu lebar isi (ANAK_LEBAR). Lebar dulu tersebar di
beberapa aturan per tab dan saling menimpa; test ini menghitung aturan yang
benar-benar menang (spesifisitas, lalu urutan) untuk tiap section.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import child_components as K  # noqa: E402
import database  # noqa: E402
import design_tokens as T  # noqa: E402
import teacher_pages  # noqa: E402
from child_style import GAYA_ANAK  # noqa: E402

SECTIONS = ("rencana", "latihan", "riwayat", "perkembangan")
LEBAR_ISI = f"calc({T.ANAK_LEBAR} + 2 * {T.ANAK_GUTTER})"


@pytest.fixture()
def anak(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    with database.buka(p) as kon:
        sid = database.tambah_siswa(kon, "Claudia", pemilik="ortu", tingkat="P3")
        database.buat_sesi(kon, sid, seed=11, topik="statistika")
    return p, sid


def _render(db, sid, section) -> str:
    with database.buka(db) as kon:
        baris = kon.execute("SELECT * FROM siswa WHERE id = ?", (sid,)).fetchone()
        return teacher_pages.halaman_anak(
            kon, baris, peran="guru", pengguna="ortu", query="section=" + section
        ).decode()


def _tanpa_media(css: str) -> str:
    keluar, kedalaman, i = [], 0, 0
    while i < len(css):
        if css.startswith("@media", i) or css.startswith("@supports", i):
            i = css.index("{", i)
            kedalaman = 1
            i += 1
            while kedalaman:
                kedalaman += {"{": 1, "}": -1}.get(css[i], 0)
                i += 1
            continue
        keluar.append(css[i])
        i += 1
    return "".join(keluar)


def _lebar_efektif(html: str) -> str:
    kelas = set(re.search(r'<body class="st"><div class="([^"]+)"', html).group(1).split())
    css = re.sub(r"/\*.*?\*/", "", "".join(re.findall(r"<style>(.*?)</style>", html, re.S)), flags=re.S)
    kandidat = []
    for urutan, (sel, isi) in enumerate(re.findall(r"([^{}]+)\{([^{}]*)\}", _tanpa_media(css))):
        lebar = re.findall(r"max-width\s*:\s*([^;]+?)\s*(?:;|$)", isi.strip())
        if not lebar:
            continue
        for satu in sel.split(","):
            satu = satu.strip()
            if re.fullmatch(r"(\.[\w-]+)+", satu) and set(satu.split(".")[1:]) <= kelas:
                kandidat.append((satu.count("."), urutan, lebar[-1]))
    return max(kandidat)[2]


@pytest.mark.parametrize("section", SECTIONS)
def test_lebar_isi_sama_di_keempat_tab(anak, section):
    db, sid = anak
    assert _lebar_efektif(_render(db, sid, section)) == LEBAR_ISI


def test_kontainer_bersama_memakai_gutter_dan_rapat_di_hp():
    assert f"padding-inline: {T.ANAK_GUTTER}" in GAYA_ANAK
    hp = GAYA_ANAK.split(f"@media (max-width: {T.ANAK_BATAS_HP})", 1)[1]
    assert f"padding-inline: {T.SP_4}" in hp


def test_chip_status_memakai_nada_dan_meloloskan_teks():
    assert K.chip_status("Selesai", "baik") == '<span class="anak-chip-st anak-chip-baik-st">Selesai</span>'
    assert "&lt;b&gt;" in K.chip_status("<b>", "netral")
    with pytest.raises(ValueError):
        K.chip_status("x", "merah")


def test_pil_filter_menandai_aktif_dan_meloloskan_href():
    assert 'aria-current="true"' in K.pil_filter("Semua", "/a?x=1&y=2", aktif=True)
    assert 'aria-current' not in K.pil_filter("Selesai", "/a")
    assert 'href="/a?x=1&amp;y=2"' in K.pil_filter("Semua", "/a?x=1&y=2")


def test_disclosure_tertutup_bawaan_dan_bisa_dibuka():
    assert "<details class=\"anak-disclosure-st\"><summary>Cara</summary>" in K.disclosure("Cara", "<p>i</p>")
    assert " open>" in K.disclosure("Cara", "<p>i</p>", terbuka=True)


def test_banner_tautan_memuat_isi_dan_tautan_tebal():
    html = K.banner_tautan("<strong>Tahap 1</strong>", "/anak/1?section=rencana", "Ke Beranda →")
    assert html.startswith('<a class="anak-banner-st" href="/anak/1?section=rencana">')
    assert '<span class="anak-banner-tautan-st">Ke Beranda →</span>' in html


def test_kartu_sesi_satu_baris_dengan_slot_opsional():
    html = K.kartu_sesi(judul="Pola", sub="15 soal", chip_html=K.chip_status("Draf", "info"),
                        aksi_html="<a>Lanjutkan</a>", peringatan="Hasil 0 dari 10")
    assert html.count("anak-kartu-sesi-st") == 1 and "anak-kartu-peringatan-st" in html
    assert "anak-kartu-tanggal-st" not in html


# ── Riwayat ───────────────────────────────────────────────────────────

def _riwayat(db, sid) -> str:
    return _render(db, sid, "riwayat")


def test_riwayat_filter_tambahan_satu_baris_dengan_judul_dan_pil(anak):
    db, sid = anak
    html = _riwayat(db, sid)
    bar = html.split('<div class="anak-filterbar-st">', 1)[1].split("</details>", 1)[0]
    assert bar.index("Semua latihan") < bar.index("riwayat-pilbar-st") < bar.index("Filter tambahan")
    assert 'class="anak-pil-st" href="' in bar and 'aria-current="true"' in bar


def test_riwayat_tombol_terlama_memakai_tombol_bersama_bukan_coral(anak):
    db, sid = anak
    with database.buka(db) as kon:
        a = database.buat_sesi(kon, sid, seed=21, jumlah_soal=1)
        database.tandai_selesai(kon, a)
    html = _riwayat(db, sid)
    aside = html.split('<aside class="riwayat-perhatian-st">', 1)[1].split("</aside>", 1)[0]
    assert 'class="anak-tombol-st"' in aside and "st-tombol-coral" not in aside


def test_riwayat_subteks_tanpa_istilah_teknis(anak):
    db, sid = anak
    kartu = _riwayat(db, sid).split('<li class="riwayat-kartu-st"', 1)[1].split("</li>", 1)[0]
    assert "latihan manual" not in kartu and "Pilihan ganda" not in kartu


def test_riwayat_baris_sesi_satu_lapis_di_desktop_dan_chip_netral_untuk_batal():
    from child_history_style import GAYA_RIWAYAT as css
    desktop = css.split("@media (min-width: 48.0625rem)", 1)[1].split("\n}\n", 1)[0]
    assert "grid-area: auto" in desktop and "3.5rem minmax(0, 1fr) auto auto" in desktop
    batal = [b for b in css.split("\n") if ".badge-direview:is(.belum, .batal)" in b][0]
    assert T.ANAK_NETRAL_LATAR in batal and T.ANAK_NETRAL_TEKS in batal
    assert f"background: {T.ANAK_AKSEN}; color: {T.TEKS_PUTIH}" in css


# ── Perkembangan > Per materi ─────────────────────────────────────────

def _peta_materi(**opsi):
    import mastery_report as mr
    from learning_cycle import BuktiSiklus

    bukti = BuktiSiklus(1, "P3")
    peta = mr.peta_penguasaan(bukti, 1)
    return peta, mr.render_peta(peta, lambda t: t, siswa_id=1, bukti_konteks=bukti, **opsi)


def test_materi_header_dilipat_dan_judul_visual_hanya_untuk_pembaca_layar():
    peta, h = _peta_materi()
    kepala = h.split('<header class="peta-ringkas">', 1)[1].split("</header>", 1)[0]
    assert 'class="profil-sr-st"' in kepala and 'id="judul-peta"' in kepala
    lipatan = kepala.split("<details", 1)[1]
    assert "Cara membaca progres ini" in lipatan
    from question_context import label_profil_parameter
    assert label_profil_parameter(peta.level) in lipatan and "Cakupan target" in lipatan


def test_materi_baris_target_nama_dan_chip_dengan_rincian_pola_dilipat():
    _, h = _peta_materi()
    baris = h.split('<details class="rincian-target-st">', 1)[1].split("</details>", 1)[0]
    ringkasan, badan = baris.split("</summary>", 1)
    assert "anak-chip-netral-st" in ringkasan and "pola menunjukkan pemahaman" not in ringkasan
    assert "pola menunjukkan pemahaman" in badan and 'class="peta-bukti"' in badan


def test_materi_bukti_per_konteks_satu_disclosure_tertutup_tanpa_lipatan_bersarang():
    _, h = _peta_materi()
    awal = h.split('<details class="anak-disclosure-st bukti-konteks-st">', 1)[1]
    blok = awal.split("</details>", 1)[0]
    assert blok.startswith("<summary>Bukti per konteks</summary>")
    assert "Cara Jagomat menilai" in blok and "Bukti per konteks latihan" in blok
    assert "<details" not in blok
    _, terbuka = _peta_materi(rincian="konteks")
    assert '<details class="anak-disclosure-st bukti-konteks-st" open>' in terbuka


def test_materi_detail_satu_kalimat_dan_warna_status_dari_token_anak():
    import mastery_report as mr
    _, h = _peta_materi()
    detail = h.split('id="detail-materi"', 1)[1]
    assert "menunjukkan pemahaman. Belum dinilai bukan berarti tidak mampu.</p>" in detail
    assert "Bukti terkonfirmasi dan anak bisa menjelaskan diperlukan" not in detail
    assert [w for _, _, w in mr.STATUS] == [
        T.ANAK_AKSEN, T.ANAK_STATUS_DIPELAJARI, T.ANAK_STATUS_PERLU_CEK, T.ANAK_STATUS_BELUM]


def test_materi_dua_kolom_hanya_di_layar_lebar():
    from child_materi_style import GAYA_MATERI as css
    lebar = css.split("@media (min-width: 46.0625rem)", 1)[1]
    assert "minmax(16rem, 21.25rem) minmax(0, 1fr)" in lebar
    assert "minmax(16rem, 21.25rem)" not in css.split("@media (min-width: 46.0625rem)", 1)[0]


# ── Perkembangan > Ringkasan ──────────────────────────────────────────

def _aktivitas(**nilai):
    from datetime import date
    from types import SimpleNamespace

    import report_dashboard as rd

    dasar = dict(dikerjakan=3, benar=2, salah=1, perlu_ditinjau=1, dinilai=3, terkonfirmasi=1,
                 belum_dikenalkan=2, dilewati=1)
    dasar.update(nilai)
    kini = SimpleNamespace(**dasar)
    data = SimpleNamespace(kini=kini, semua=kini, mulai=date(2026, 10, 13), akhir=date(2026, 10, 19))
    return rd.render_aktivitas(data, lambda t: t, semua=True)


def test_aktivitas_satu_kalimat_terlihat_dan_sisanya_dalam_satu_disclosure():
    h = _aktivitas()
    luar, lipatan = h.split('<details class="rincian-ui-st">', 1)
    assert luar.count("laporan-catatan") == 1 and "Dari 3 soal yang sudah dinilai" in luar
    for teks in ("Semua waktu", "Hasil sementara", "2 perlu cek pengenalan materi", "1 dilewati"):
        assert teks not in luar and teks in lipatan
    assert h.count("<details") == 1 and "<summary>Tentang catatan aktivitas</summary>" in lipatan
    assert "<a " not in lipatan and "<ul" not in lipatan


def test_aktivitas_tanpa_hasil_sementara_bila_semua_terkonfirmasi():
    assert "Hasil sementara" not in _aktivitas(terkonfirmasi=3)


def test_ringkasan_banner_ke_beranda_memakai_banner_bersama(anak):
    db, sid = anak
    html = _render(db, sid, "perkembangan")
    banner = re.search(r'<a class="laporan-ke-beranda anak-banner-st" href="[^"]+">.*?</a>', html, re.S).group()
    assert "<strong>Tahap sekarang:" in banner and "Ke Beranda →" in banner
    assert f"/anak/{sid}?section=rencana" in banner


def test_ringkasan_css_tanpa_garis_angka_pil_seragam_dan_legenda_satu_baris():
    from child_ringkasan_style import GAYA_RINGKASAN as css
    kartu_stat = css.split(".aktivitas-kartu-st .kartu-stat {", 1)[1].split("}", 1)[0]
    assert "border: 0" in kartu_stat and "border-block" not in kartu_stat
    assert f"background: {T.ANAK_ABU_HANGAT}" in css and f"min-height: {T.TARGET_SENTUH}" in css
    assert f"border: 2px solid {T.ANAK_AKSEN}; background: {T.ANAK_AKSEN_LATAR}" in css
    legenda = css.split(".peta-legenda {", 1)[1].split("}", 1)[0]
    assert "display: flex" in legenda and "flex-wrap: wrap" in legenda


# ── Latihan ───────────────────────────────────────────────────────────

def test_latihan_judul_tunggal_legend_diringkas_dan_panel_tetap_beranama(anak):
    db, sid = anak
    html = _render(db, sid, "latihan")
    assert "<legend>Latihan tentang apa?</legend>" in html and "Pilih latihan tentang apa" not in html
    # legend panel tetap ada untuk pembaca layar, hanya disembunyikan secara visual
    assert "<legend>Pilih satu topik</legend>" in html
    from child_latihan_style import GAYA_LATIHAN as css
    legend = css.split('fieldset[data-mode-latihan] > legend {', 1)[1].split("}", 1)[0]
    assert "position: absolute" in legend and "clip-path: inset(50%)" in legend


def test_latihan_teks_bantuan_cakupan_dilipat_di_pengaturan_lanjutan(anak):
    db, sid = anak
    html = _render(db, sid, "latihan")
    manual = html.split('data-mode-latihan="manual"', 1)[1].split("</fieldset>", 1)[0]
    luar, lanjutan = manual.split('<details class="atur-latihan-st profil-lanjutan-st">', 1)
    teks = "Jagomat memilih cakupan yang sesuai untuk topik ini."
    assert teks not in luar and teks in lanjutan


def test_latihan_css_tanpa_garis_lanjutan_dan_tidak_membuka_panel_tersembunyi():
    from child_latihan_style import GAYA_LATIHAN as css
    lanjutan = css.split(".latihan-terpadu-st .atur-latihan-st {", 1)[1].split("}", 1)[0]
    assert "border: 0" in lanjutan and "border-block" not in lanjutan
    for blok in re.findall(r"([^{}]*data-mode-latihan[^{}]*)\{([^{}]*)\}", css):
        assert "display" not in blok[1], "aturan display di panel mode akan membuka panel [hidden]"
    assert "font-size: 1.625rem; font-weight: 800" in css
    assert f"background: {T.ANAK_AKSEN_LATAR}; border: 2px solid {T.ANAK_AKSEN}" in css


def test_latihan_ketiga_mode_tetap_ada_dan_satu_aktif(anak):
    db, sid = anak
    html = _render(db, sid, "latihan")
    for kode in ("manual", "remedial", "gabungan"):
        assert f'data-mode-latihan="{kode}"' in html
    assert html.count("disabled hidden") == 2
