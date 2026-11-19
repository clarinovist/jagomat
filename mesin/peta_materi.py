"""Panel Per materi: tiap materi satu `<details>` (jalan tanpa JS).

Isi saat dibuka: ringkasan Guru, contoh soal, langkah anak dengan langkah salah
ditandai, yang perlu dilatih, latihan 10 menit. Angka (persen, jumlah salah)
dari data, bukan dari teks tulis tangan.
"""
from __future__ import annotations

from cek_gratis_skor import BATAS_KUAT_PERSEN, LABEL_BELUM_CUKUP, LABEL_KUAT, LABEL_PERLU_DIPERKUAT, MIN_SOAL_PER_TOPIK
from peta_data import Bagian, Susun
from peta_ikon import ikon, ubin_materi
from peta_komponen import bar_penguasaan, kepala_panel, label_dari_materi, persen_materi, status_chip
from peta_teks import e

LEBAR_BAGIAN = 232
TINGGI_BAGIAN = 38


def _legenda() -> str:
    return (
        '<p class="peta-legenda-st"><span>%s %d%% ke atas</span><span>%s di bawah %d%%</span>'
        '<span>%s kurang dari %d soal</span></p>'
    ) % (status_chip(LABEL_KUAT), BATAS_KUAT_PERSEN, status_chip(LABEL_PERLU_DIPERKUAT), BATAS_KUAT_PERSEN,
         status_chip(LABEL_BELUM_CUKUP), MIN_SOAL_PER_TOPIK)


def _susun(visual: Susun) -> str:
    benar = str(visual.atas * visual.bawah)
    anak = str(visual.hasil_anak)
    kolom = 1 + max(len(str(visual.atas)), len(anak))
    sel = ["<span></span>"] * kolom
    baris = []
    atas = ["<span></span>"] * kolom
    atas[kolom - 2] = '<span class="peta-bawa-st">%d</span>' % visual.simpanan
    baris.append("".join(atas))
    digit = str(visual.atas).rjust(kolom, " ")
    baris.append("".join("<span>%s</span>" % e(d.strip()) for d in digit))
    pengali = list(sel)
    pengali[0], pengali[-1] = "<span>×</span>", "<span>%d</span>" % visual.bawah
    baris.append("".join(pengali))
    sejajar = anak.rjust(kolom, " ")
    sebanding = benar.rjust(kolom, " ")
    hasil = []
    for jawab, patut in zip(sejajar, sebanding):
        salah = jawab.strip() and jawab != patut
        isi = '<span class="peta-x-st">%s</span>' % e(jawab) if salah else e(jawab.strip())
        hasil.append('<span class="peta-garis-hasil-st">%s</span>' % isi)
    baris.append("".join(hasil))
    label = "Jawaban anak: %s. Seharusnya %s." % (anak, benar)
    return '<div class="peta-susun-st" style="--peta-kol:%d" role="img" aria-label="%s">%s</div>' % (
        kolom, e(label), "".join(baris))


def _bagian(visual: Bagian) -> str:
    lebar = LEBAR_BAGIAN / visual.total
    petak = "".join(
        '<rect class="%s" x="%.1f" y="1" width="%.1f" height="%d"/>' % (
            "peta-petak-isi-st" if i < visual.terisi else "peta-petak-kosong-st", 1 + i * lebar, lebar, TINGGI_BAGIAN - 2)
        for i in range(visual.total))
    label = "Satu kotak dibagi %d, %d bagian diarsir: %d per %d" % (visual.total, visual.terisi, visual.terisi, visual.total)
    return '<svg viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s">%s</svg>' % (
        LEBAR_BAGIAN + 2, TINGGI_BAGIAN, LEBAR_BAGIAN + 2, TINGGI_BAGIAN, e(label), petak)


def _visual(visual) -> str:
    if isinstance(visual, Susun):
        return _susun(visual)
    if isinstance(visual, Bagian):
        return _bagian(visual)
    return ""


def _daftar_langkah(contoh) -> str:
    butir = []
    for nomor, langkah in enumerate(contoh.langkah, start=1):
        kelas = ' class="peta-salah-st"' if langkah.salah else ""
        tanda = '<span class="peta-tanda-st">%s</span>' % e(langkah.tanda) if langkah.salah and langkah.tanda else ""
        butir.append('<li%s><span class="peta-n-st">%d</span><span>%s%s</span></li>' % (kelas, nomor, e(langkah.teks), tanda))
    return '<ol class="peta-langkah-st">%s</ol>' % "".join(butir)


def _contoh(materi, nama_anak: str) -> str:
    contoh = materi.contoh
    return (
        '<div class="peta-grid-st"><div class="peta-soal-st"><span class="peta-label-st">Contoh soal</span>'
        '<p class="peta-mono-st">%s</p>%s<p class="peta-bantuan-st">Jawaban %s <b>%s</b>, seharusnya <b>%s</b>.</p></div>'
        '<div class="peta-soal-st"><span class="peta-label-st">Langkah %s</span>%s</div></div>'
    ) % (e(contoh.soal), _visual(contoh.visual), e(nama_anak), e(contoh.jawaban_anak), e(contoh.jawaban_benar),
         e(nama_anak), _daftar_langkah(contoh))


def _dilatih(materi) -> str:
    sebab = " Muncul di %d dari %d soal %s." % (materi.salah, materi.soal, materi.nama.lower()) if materi.salah else ""
    return '<p><strong>Yang perlu dilatih:</strong> %s%s</p>' % (e(materi.yang_dilatih), e(sebab))


def _isi_materi(materi, nama_anak: str) -> str:
    badan = '<p>%s</p>' % e(materi.ringkas)
    if materi.contoh is not None:
        badan += _contoh(materi, nama_anak) + _dilatih(materi)
    judul = "Latihan 10 menit" if materi.salah else "Pertahankan"
    badan += '<div class="peta-latih-st"><h4>%s</h4><p>%s</p></div>' % (judul, e(materi.latihan))
    return '<div class="peta-isi-st">%s</div>' % badan


def _materi(materi, nama_anak: str) -> str:
    label = label_dari_materi(materi)
    sub = "%d soal" % materi.soal + (" · %d salah" % materi.salah if materi.salah else "")
    return (
        '<details id="m-%s"><summary>%s<span class="peta-nama-st">%s<small>%s</small></span>'
        '<span class="peta-kanan-st"><span class="peta-persen-st">%d%%</span>%s</span>'
        '<span class="peta-panah-st">%s</span>%s</summary>%s</details>'
    ) % (e(materi.kunci), ubin_materi(materi.kunci, "l"), e(materi.nama), e(sub), persen_materi(materi),
         status_chip(label), ikon("panah-bawah", 24, "2.2"), bar_penguasaan(materi), _isi_materi(materi, nama_anak))


def panel_per_materi(data) -> str:
    kepala = kepala_panel("peta", "teal", "h-materi", "Penguasaan per materi",
                          "Ketuk materi untuk melihat contoh soal, langkah yang salah, dan latihan 10 menit.")
    daftar = "".join(_materi(m, data.nama_anak) for m in data.materi)
    return (
        '<section class="peta-panel-st" id="per-materi" data-peta-panel aria-labelledby="h-materi">%s%s'
        '<div class="peta-materi-st">%s</div></section>'
    ) % (kepala, _legenda(), daftar)
