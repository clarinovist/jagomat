"""Laporan Peta Kemampuan playful (contoh sintetis Aisyah) dan lembar 1 halaman.

Memeriksa konsistensi angka data, label, posisi dari `hitung_posisi`, klaim yang dilarang,
skrip polos, dan fallback tanpa JS. Semua data sintetis.
"""
from __future__ import annotations

import dataclasses
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import peta_laporan  # noqa: E402
import peta_lembar  # noqa: E402
import peta_posisi  # noqa: E402
import peta_teks  # noqa: E402
from cek_gratis_skor import hitung_skor, kategori_dari_skor, label_materi  # noqa: E402
from peta_contoh_data import DATA_CONTOH, bangun_pembanding_contoh, periksa_konsisten  # noqa: E402
from peta_data import Misi, Temuan  # noqa: E402
from peta_posisi import HasilPosisi, hitung_posisi  # noqa: E402

KATA_TERLARANG = ("tidak ditampilkan", "diagnosa", "pasti", "dijamin", "menjamin", "diagnosis lengkap")
PANEL = ("ringkasan", "per-materi", "pola", "langkah")


def _laporan(data=DATA_CONTOH, contoh=True) -> str:
    return peta_laporan.render_laporan(data, contoh=contoh)


def _teks_tampak(markup: str) -> str:
    """Isi halaman tanpa blok style/script (yang tampil ke pembaca)."""
    return re.sub(r"<(style|script)\b.*?</\1>", "", markup, flags=re.S)


# ---------------------------------------------------------------- konsistensi data

def test_data_contoh_konsisten_dan_angka_sesuai_acuan():
    periksa_konsisten(DATA_CONTOH)
    assert (DATA_CONTOH.jumlah_soal, DATA_CONTOH.jumlah_benar, DATA_CONTOH.jumlah_salah) == (30, 22, 8)
    assert DATA_CONTOH.skor == hitung_skor(22, 30) == 73
    assert DATA_CONTOH.kategori == kategori_dari_skor(73) == "Cukup baik"
    assert (DATA_CONTOH.nama_anak, DATA_CONTOH.kelas) == ("Aisyah", 4)


def test_materi_per_materi_persen_dan_label():
    hasil = {m.kunci: (m.soal, m.benar, hitung_skor(m.benar, m.soal), label_materi(m.benar, m.soal)) for m in DATA_CONTOH.materi}
    assert hasil == {
        "penjumlahan": (8, 7, 88, "Kuat"),
        "perkalian": (6, 3, 50, "Perlu diperkuat"),
        "pembagian": (6, 5, 83, "Kuat"),
        "pecahan": (6, 4, 67, "Perlu diperkuat"),
        "soal-cerita": (4, 3, 75, "Perlu diperkuat"),
    }


def test_pola_jumlah_dan_total_salah():
    assert [p.jumlah for p in DATA_CONTOH.pola] == [4, 2, 1, 1]
    assert sum(p.jumlah for p in DATA_CONTOH.pola) == DATA_CONTOH.jumlah_salah
    assert dict(DATA_CONTOH.pola[0].sebaran) == {"perkalian": 3, "penjumlahan": 1}


def test_pembanding_contoh_214_deterministik_dan_memuat_skor_anak():
    pembanding = bangun_pembanding_contoh()
    assert len(pembanding) == 214 and pembanding == bangun_pembanding_contoh() == DATA_CONTOH.skor_pembanding
    assert DATA_CONTOH.skor in pembanding
    assert all(0 <= s <= 100 for s in pembanding)


@pytest.mark.parametrize("ubah,pesan", [
    (lambda d: dataclasses.replace(d, jumlah_soal=31), "total soal"),
    (lambda d: dataclasses.replace(d, jumlah_benar=21), "total benar"),
    (lambda d: dataclasses.replace(d, pola=d.pola[:-1]), "jumlah pola"),
    (lambda d: dataclasses.replace(d, temuan=(Temuan("px", "x"),)), "temuan"),
    (lambda d: dataclasses.replace(d, misi=(Misi("tak-ada", "x", "x", (), "x"),)), "misi"),
    (lambda d: dataclasses.replace(d, materi=()), "minimal satu materi"),
    (lambda d: dataclasses.replace(d, materi=d.materi + (d.materi[0],)), "ganda"),
])
def test_periksa_konsisten_menolak_data_tidak_cocok(ubah, pesan):
    with pytest.raises(ValueError, match=pesan):
        periksa_konsisten(ubah(DATA_CONTOH))


def test_periksa_konsisten_menolak_salah_per_materi_tidak_cocok():
    pola = list(DATA_CONTOH.pola)
    # Pindahkan 1 jawaban salah dari perkalian ke pecahan: total tetap 8, tetapi per materi tidak cocok.
    pola[0] = dataclasses.replace(pola[0], sebaran=(("perkalian", 2), ("penjumlahan", 1), ("pecahan", 1)))
    with pytest.raises(ValueError, match="salah materi"):
        periksa_konsisten(dataclasses.replace(DATA_CONTOH, pola=tuple(pola)))


def test_render_menolak_data_tidak_konsisten():
    with pytest.raises(ValueError):
        _laporan(dataclasses.replace(DATA_CONTOH, jumlah_benar=21))
    with pytest.raises(ValueError):
        peta_lembar.render_lembar(dataclasses.replace(DATA_CONTOH, jumlah_benar=21), contoh=True)


# ---------------------------------------------------------------- posisi

def test_teks_posisi_berasal_dari_hitung_posisi():
    posisi = hitung_posisi(DATA_CONTOH.skor, DATA_CONTOH.skor_pembanding)
    isi = _teks_tampak(_laporan())
    assert f"Peringkat {posisi.peringkat} dari {posisi.penyebut}" in isi
    assert f"Lebih tinggi dari <b>{posisi.persentil}%</b> anak kelas 4" in isi
    assert posisi.peringkat <= posisi.penyebut


def test_teks_posisi_mengikuti_fungsi_bukan_angka_tulis_tangan(monkeypatch):
    monkeypatch.setattr(peta_laporan, "hitung_posisi", lambda skor, pembanding: HasilPosisi(persentil=12, peringkat=190, penyebut=214))
    isi = _teks_tampak(_laporan())
    assert "Peringkat 190 dari 214" in isi and "<b>12%</b>" in isi
    assert "Peringkat 67 dari 214" not in isi


def test_posisi_belum_cukup_data_menampilkan_pesan():
    sedikit = dataclasses.replace(DATA_CONTOH, skor_pembanding=tuple(DATA_CONTOH.skor_pembanding[:29]))
    isi = _teks_tampak(_laporan(sedikit))
    assert "Peringkat muncul setelah cukup data" in isi
    assert "Peringkat " + "67" not in isi and "dari 29" not in isi
    assert "peta-histo-st" not in isi


@pytest.mark.parametrize("posisi,harus,tidak", [
    (HasilPosisi(99, 1, 214), "tertinggi", "100%"),
    (HasilPosisi(100, 2, 214), "<b>99%</b>", "100%"),
    (HasilPosisi(0, 214, 214), "Posisi di antara anak kelas 4", "Lebih tinggi"),
    (HasilPosisi(50, 11, 30), "<b>50%</b>", "tertinggi"),
])
def test_kalimat_posisi_tidak_pernah_100_persen(posisi, harus, tidak):
    kalimat = peta_teks.kalimat_posisi(posisi, 4)
    assert harus in kalimat and tidak not in kalimat


def test_histogram_ikut_data_pembanding():
    isi = _laporan()
    sebaran = peta_teks.sebaran_kelompok(DATA_CONTOH.skor_pembanding)
    assert sum(sebaran) == 214
    assert isi.count("peta-kol-st") >= 10
    assert 'peta-kol-st peta-kol-aktif-st"><span class="peta-bt-st" style="height:100%"><span class="peta-pin-st">Aisyah di sini' in isi
    assert "Aisyah di kelompok skor 70–79" in isi


# ---------------------------------------------------------------- isi laporan

def test_hero_skor_kategori_label_contoh():
    isi = _laporan()
    assert 'aria-label="Skor 73 dari 100"' in isi and ">Cukup baik<" in isi
    assert "Laporan Aisyah · Kelas 4" in isi and "Laporan otomatis" in isi
    assert "30 soal · 1 Nov 2026" in isi
    assert "data sintetis" in isi and "bukan hasil anak sungguhan" in isi


def test_label_kuat_80_persen_di_laporan():
    isi = _laporan()
    for kunci, label in (("penjumlahan", "Kuat"), ("pembagian", "Kuat"), ("perkalian", "Perlu diperkuat"),
                         ("pecahan", "Perlu diperkuat"), ("soal-cerita", "Perlu diperkuat")):
        ringkas = re.search(rf'<details id="m-{kunci}"><summary>(.*?)</summary>', isi, re.S).group(1)
        assert label in ringkas, kunci
    assert "80% ke atas" in isi and "di bawah 80%" in isi and "kurang dari 3 soal" in isi


def test_donat_berisi_jumlah_bukan_persen():
    isi = _laporan()
    assert isi.count('class="peta-seg-st peta-seg-w') == 4
    for teks in ("4 dari 8", "2 dari 8", "1 dari 8", "4 dari 8 · terbanyak"):
        assert teks in isi
    assert 'data-pola="p1"' in isi and "Dari mana datangnya 8 jawaban salah?" in isi


def test_langkah_anak_dengan_langkah_salah_ditandai():
    isi = _laporan()
    assert isi.count('class="peta-salah-st"') == 5  # satu langkah salah per materi
    assert "simpanan 4 belum ditambahkan (24 + 4 = 28)" in isi
    assert 'role="img" aria-label="Jawaban anak: 242. Seharusnya 282."' in isi


def test_lencana_dua_didapat_dua_terkunci_tanpa_aturan():
    isi = _laporan()
    assert isi.count(">Didapat<") == 2 and isi.count(">Terkunci<") == 2
    assert "Buka lewat misi" not in isi


def test_jalur_empat_minggu_urutan_kegiatan_bukan_janji():
    isi = _laporan()
    assert "Jalur latihan 4 minggu" in isi and "urutan kegiatan, bukan janji hasil" in isi
    assert isi.count("<b>Minggu ") == 4


def test_satu_tombol_utama_dan_harga_kelas_tampil_di_akhir_laporan():
    # Keputusan 20 poin 7 (21 Nov 2026): harga kelas tampil di laporan; halaman publik tetap tanpa harga kelas.
    isi = _laporan()
    assert isi.count('class="tombol-coral"') == 1 and isi.count('href="/daftar?jalur=cek"') == 1
    assert "Kelas kecil Jagomat" in isi and "Rp49.000" in isi
    assert "Rp300.000 per bulan" in _teks_tampak(isi)
    # Titik penutup kalimat ("... dipotong Rp49.000.") bukan bagian angka.
    assert {x.rstrip(".") for x in re.findall(r"Rp\s?[\d.]+", _teks_tampak(isi))} == {"Rp49.000", "Rp300.000"}


def test_cek_ulang_bagian_kelas_dan_tidak_wajib_dengan_bingkai_baru():
    # Keputusan Pemilik 25 Nov 2026: kartu kelas TIDAK menjanjikan cek ulang/laporan
    # perkembangan bulanan; "tidak wajib" tetap jujur (Keputusan 15).
    isi = _teks_tampak(_laporan())
    assert "Cek ulang bersama Guru" in isi and "di kelas" not in isi
    assert "Laporan perkembangan pada fokus" not in isi and "tiap 4 minggu" not in isi
    assert "Tidak wajib ikut kelas" in isi and "tetap milik Anda" in isi
    assert "berlatih sendiri" not in isi
    assert "Minggu 1–3 bisa Anda mulai sendiri" in isi


def test_chip_laporan_mengikuti_data_bukan_statis():
    # Chip mengikuti data `ditinjau` (copy tanpa kata Guru sejak 26 Nov 2026): tanpa data tinjauan tidak mengklaim terbit.
    belum = dataclasses.replace(DATA_CONTOH, ditinjau=False, catatan_guru="")
    ada = _laporan(DATA_CONTOH)
    tidak = _laporan(belum)
    assert "Laporan otomatis</span>" in ada and "Belum diterbitkan</span>" not in ada
    assert "Laporan otomatis</span>" not in tidak and "Belum diterbitkan</span>" in tidak


def test_lembar_tidak_mengklaim_tinjauan_bila_belum_ditinjau():
    belum = dataclasses.replace(DATA_CONTOH, ditinjau=False, catatan_guru="")
    ada = peta_lembar.render_lembar(DATA_CONTOH, contoh=True)
    tidak = peta_lembar.render_lembar(belum, contoh=True)
    assert "Ringkasan satu halaman dari cek matematika." in ada and "Ditinjau oleh" not in ada
    assert "yang ditinjau Guru" not in tidak and "Ditinjau oleh" not in tidak
    assert "Belum ditinjau Guru" not in tidak


def test_periksa_konsisten_menolak_catatan_guru_tanpa_tinjauan():
    with pytest.raises(ValueError, match="tinjauan"):
        periksa_konsisten(dataclasses.replace(DATA_CONTOH, ditinjau=False))
    periksa_konsisten(dataclasses.replace(DATA_CONTOH, ditinjau=False, catatan_guru=""))


def test_laporan_nyata_tanpa_cta_contoh_dan_tautan_lembar():
    isi = _laporan(contoh=False)
    assert 'href="/daftar?jalur=cek"' not in isi and "/contoh-peta-kemampuan/lembar" not in isi
    assert "<h1 id=\"peta-judul\">" in isi and "data sintetis" not in isi
    contoh = _laporan(contoh=True)
    assert 'href="/contoh-peta-kemampuan/lembar"' in contoh and "Lembar ringkasan 1 halaman" in contoh


def test_semua_teks_data_di_escape():
    jahat = dataclasses.replace(DATA_CONTOH, nama_anak="<img src=x onerror=1>", catatan_guru="<b>x</b>")
    for isi in (_laporan(jahat), peta_lembar.render_lembar(jahat, contoh=True)):
        assert "<img src=x" not in isi and "<b>x</b>" not in isi
        assert "&lt;img src=x onerror=1&gt;" in isi


def test_tanpa_kata_terlarang_di_laporan_dan_lembar():
    halaman = [_teks_tampak(_laporan()), _teks_tampak(peta_lembar.halaman_lembar(DATA_CONTOH, contoh=True).decode())]
    for isi in halaman:
        for kata in KATA_TERLARANG:
            assert kata not in isi.lower(), kata


def test_kata_terlarang_tidak_ada_di_sumber_teks():
    for nama in ("peta_data", "peta_contoh_data", "peta_laporan", "peta_ringkasan", "peta_materi", "peta_pola", "peta_misi",
                 "peta_lembar", "peta_komponen", "peta_teks", "peta_browser"):
        sumber = (Path(__file__).resolve().parent.parent / (nama + ".py")).read_text(encoding="utf-8").lower()
        for kata in ("diagnosa", "dijamin", "menjamin", "tidak ditampilkan"):
            assert kata not in sumber, (nama, kata)


# ---------------------------------------------------------------- skrip dan fallback tanpa JS

def test_skrip_polos_tanpa_handler_inline_dan_tanpa_jaringan():
    for isi in (_laporan(), peta_lembar.halaman_lembar(DATA_CONTOH, contoh=True).decode()):
        assert len(re.findall(r"<script\b", isi)) == len(re.findall(r"<script>", isi)) >= 1
        for terlarang in ("onclick=", "onerror=", "onload=", "fetch(", "XMLHttpRequest", "eval(", "innerHTML", "sendBeacon", "WebSocket"):
            assert terlarang not in isi, terlarang
    skrip = re.findall(r"<script>(.*?)</script>", _laporan(), re.S)
    assert len(skrip) == 1 and "localStorage" in skrip[0] and "try" in skrip[0]


def test_tanpa_js_semua_panel_tampil_berurutan():
    isi = _laporan()
    posisi = [isi.index(f'id="{p}"') for p in PANEL]
    assert posisi == sorted(posisi)
    assert not re.search(r"\shidden[\s>=]", re.sub(r"<script>.*?</script>", "", isi, flags=re.S))
    for panel in PANEL:
        assert f'href="#{panel}"' in isi and f'data-peta-tab="{panel}"' in isi
    assert "<details" in isi and "peta-tanpa-js-st" in isi and "Lihat jawabannya" in isi


def test_maskot_awal_dan_pose_per_tab_dari_aset_ada():
    isi = _laporan()
    aset = Path(__file__).resolve().parent.parent / "aset"
    pose = set(re.findall(r'/aset/(maskot-[a-z]+-v3-240\.png)', isi))
    assert pose == {f"maskot-{n}-v3-240.png" for n in ("menyapa", "berpikir", "membaca", "menulis", "merayakan")}
    for berkas in pose:
        assert (aset / berkas).is_file()


def test_gaya_peta_tanpa_literal_dan_important():
    import peta_style
    import peta_style_lembar

    for modul in (peta_style, peta_style_lembar):
        sumber = Path(modul.__file__).read_text(encoding="utf-8")
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", sumber)
        assert "!important" not in sumber
    for css in (peta_style.GAYA_PETA, peta_style_lembar.GAYA_LEMBAR):
        assert "{T." not in css and "}}" not in css  # semua interpolasi token sudah terisi
    assert "prefers-reduced-motion" in peta_style.GAYA_PETA
    assert "@page { size: A4 portrait; margin: 0; }" in peta_style_lembar.GAYA_LEMBAR


# ---------------------------------------------------------------- lembar

def test_lembar_isi_wajib_panduan():
    isi = peta_lembar.halaman_lembar(DATA_CONTOH, contoh=True).decode()
    for teks in ("Lembar Hasil Peta Kemampuan", "Temuan: di langkah mana salahnya", "Resep latihan minggu ini", "Misi berikutnya", "Catatan",
                 "Si Jago", "KEPALA SEKOLAH ★ JAGOMAT ★", ">JAGO<", "19·11·26", "Batas lembar ini",
                 "Contoh dengan data sintetis, bukan hasil anak sungguhan"):
        assert teks in isi, teks
    posisi = hitung_posisi(DATA_CONTOH.skor, DATA_CONTOH.skor_pembanding)
    assert f"Peringkat {posisi.peringkat} dari {posisi.penyebut}" in isi
    assert isi.count('class="peta-l-hr-st"') == 7
    assert isi.count("peta-l-no-st") >= 3 and isi.count("Misi ") >= 3
    assert 'href="/contoh-peta-kemampuan"' in isi and "data-peta-cetak" in isi
    assert "/aset/lockup-horizontal.svg" in isi and "maskot-merayakan-v3-240.png" in isi


def test_lembar_posisi_sama_dengan_laporan(monkeypatch):
    monkeypatch.setattr(peta_lembar, "hitung_posisi", lambda skor, pembanding: HasilPosisi(persentil=33, peringkat=140, penyebut=214))
    isi = peta_lembar.halaman_lembar(DATA_CONTOH, contoh=True).decode()
    assert "Peringkat 140 dari 214" in isi and "<b>33%</b>" in isi


def test_lembar_temuan_tiga_pola_dengan_jumlah_dan_contoh():
    isi = peta_lembar.render_lembar(DATA_CONTOH, contoh=True)
    assert isi.count('class="peta-l-hit-st"') == 3
    for teks in ("4 dari 8 jawaban salah", "2 dari 8 jawaban salah", "1 dari 8 jawaban salah", "47 × 6 ditulis 242, seharusnya 282."):
        assert teks in isi


def test_lembar_nyata_tanpa_label_sintetis():
    isi = peta_lembar.render_lembar(DATA_CONTOH, contoh=False)
    assert "data sintetis" not in isi


# ---------------------------------------------------------------- kasus tepi renderer

def _semua_benar():
    materi = tuple(dataclasses.replace(m, benar=m.soal, contoh=None) for m in DATA_CONTOH.materi)
    misi = tuple(dataclasses.replace(m, pola_kunci="") for m in DATA_CONTOH.misi)
    return dataclasses.replace(DATA_CONTOH, jumlah_benar=30, materi=materi, pola=(), temuan=(), misi=misi)


def test_semua_benar_tanpa_pola_tetap_render_donat_kosong():
    data = _semua_benar()
    periksa_konsisten(data)
    isi = _laporan(data)
    assert "Tidak ada jawaban salah" in isi and data.skor == 100 and data.kategori == "Sangat baik"
    assert "peta-seg-st" not in isi.split('id="pola"', 1)[1].split("</section>", 1)[0]
    assert peta_lembar.render_lembar(data, contoh=True)


def test_donat_satu_pola_memakai_lingkaran_penuh():
    from peta_donat import render_donat

    svg = render_donat((DATA_CONTOH.pola[0],), 30, 4)
    assert '<circle class="peta-seg-st' in svg and '<path class="peta-seg-st' not in svg


def test_donat_banyak_pola_tidak_gagal_dan_sudut_menutup_lingkaran():
    from peta_donat import _irisan, render_donat

    pola = tuple(dataclasses.replace(DATA_CONTOH.pola[1], kunci=f"x{i}", nama=f"Pola nomor {i}", sebaran=(("pecahan", i + 1),))
                 for i in range(6))
    irisan = _irisan(pola)
    assert abs(irisan[-1][2] + 1.0 - 360.0) < 1e-6  # tiap sisi menyisakan setengah celah
    assert render_donat(pola, 60, 21).count('data-pola="x5"') >= 3


def test_tautan_lembar_sama_dengan_rute_funnel_dan_tabel_akses():
    import funnel_http
    import peta_komponen
    import web

    assert funnel_http.JALUR_LEMBAR_CONTOH == peta_komponen.JALUR_LEMBAR_CONTOH
    assert funnel_http.JALUR_LEMBAR_CONTOH in funnel_http.JALUR_FUNNEL
    assert dict(web.AKSES_RUTE_GET)[funnel_http.JALUR_LEMBAR_CONTOH] == "publik"


def test_perkalian_bersusun_digit_salah_dicoret():
    isi = _laporan()
    assert isi.count('<span class="peta-x-st">4</span>') == 1  # 242 vs 282: hanya digit puluhan
    assert '<span class="peta-bawa-st">4</span>' in isi



def test_kartu_catatan_dan_identitas_guru_tidak_tampil_bila_belum_ditinjau():
    # Sisa kebocoran 2 (review 21 Nov 2026): tanpa tinjauan, laporan dan lembar tidak boleh memajang kartu Catatan Guru,
    # nama/latar Guru, atau tanda tangan seolah sudah disahkan.
    belum = dataclasses.replace(DATA_CONTOH, ditinjau=False, catatan_guru="")
    nama = DATA_CONTOH.guru.nama
    ada_laporan, ada_lembar = _laporan(DATA_CONTOH), peta_lembar.render_lembar(DATA_CONTOH, contoh=True)
    # Contoh publik tidak memajang kartu catatan Guru (copy sistem); laporan sungguhan (contoh=False) tetap memajangnya.
    sungguhan = _laporan(DATA_CONTOH, contoh=False)
    assert "Catatan Guru" in sungguhan and nama in sungguhan
    assert "Catatan Guru" not in ada_laporan and nama not in ada_laporan
    assert "Catatan</p>" in ada_lembar and "Kepala Sekolah Jagomat" in ada_lembar
    laporan, lembar = _laporan(belum), peta_lembar.render_lembar(belum, contoh=True)
    assert "Catatan Guru" not in laporan and nama not in laporan
    assert "Catatan</p>" not in lembar and nama not in lembar and "Kepala Sekolah Jagomat" not in lembar


def test_kartu_kelas_kecil_membaca_katalog_mini_class(monkeypatch):
    """Angka kartu kelas = katalog Mini Class (24 Nov 2026), bukan teks lama; lokasi belum ada, jadi tidak dijanjikan."""
    import paket_belajar_katalog as katalog
    teks = _teks_tampak(_laporan())
    for harapan in ("Rp300.000 per bulan, 8 pertemuan.", "Kelas kecil maksimal 5 anak, online, 60 menit per pertemuan",
                    "Kelas berlangsung online lewat Zoom atau Google Meet. Tautan dikirim setelah Anda daftar."):
        assert harapan in teks, harapan
    for lama in ("Dua pertemuan seminggu", "45 menit, dipandu", "Rp200.000"):
        assert lama not in teks, lama
    mini = dataclasses.replace(katalog.ambil(katalog.KODE_MINI), harga=275_000, kuota=4)
    monkeypatch.setattr(katalog, "DAFTAR_PAKET", (katalog.ambil(katalog.KODE_PRIVATE), mini))
    baru = _teks_tampak(_laporan())
    assert "Rp275.000 per bulan" in baru and "maksimal 4 anak" in baru
