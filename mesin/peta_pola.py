"""Panel Pola kesalahan: donat berpanah keterangan, daftar pola, detail per pola.

Tanpa JS: daftar pola menjadi tautan ke materi dan semua detail pola tampil
berurutan. Dengan JS (`peta_browser`): irisan/kartu bisa diklik dan satu detail tampil.
"""
from __future__ import annotations

from peta_donat import render_donat
from peta_ikon import ubin_materi
from peta_komponen import kepala_panel, pola_teratas
from peta_teks import e

# (kiri %, atas %, ukuran px, putar derajat, simbol): hiasan kertas petak.
_SIMBOL = (
    (2, 4, 54, -12, "+"), (90, 3, 50, 8, "÷"), (46, 2, 40, 10, "×"), (94, 40, 46, 0, "−"),
    (3, 52, 44, 0, "="), (86, 64, 48, -8, "½"), (30, 60, 40, 14, "7"), (64, 46, 36, -10, "3"),
)


def _hiasan() -> str:
    span = "".join(
        '<span class="peta-simbol-hias-st" style="left:%d%%;top:%d%%;font-size:%dpx;transform:rotate(%ddeg)">%s</span>'
        % (kiri, atas, ukuran, putar, e(simbol)) for kiri, atas, ukuran, putar, simbol in _SIMBOL)
    return '<div class="peta-hias-st" aria-hidden="true">%s</div>' % span


def _isi_tombol(pola, data) -> str:
    return '%s<span>%s<small>%s</small></span><b>%d dari %d</b>' % (
        ubin_materi(pola.materi_tujuan, "m"), e(pola.nama), e(pola.asal), pola.jumlah, data.jumlah_salah)


def _daftar(data) -> str:
    butir = []
    for pola in data.pola:
        dalam = _isi_tombol(pola, data)
        butir.append(
            '<li><button type="button" class="peta-pola-tombol-st peta-hanya-js-st" data-pola="%s" aria-pressed="false">%s</button>'
            '<a class="peta-pola-tombol-st peta-tanpa-js-st" href="#m-%s">%s</a></li>'
            % (e(pola.kunci), dalam, e(pola.materi_tujuan), dalam))
    return '<ul class="peta-pola-daftar-st">%s</ul>' % "".join(butir)


def _detail(data) -> str:
    teratas = pola_teratas(data)
    awal = (
        '<div class="peta-detail-st peta-hanya-js-st" data-detail="semua"><strong>Yang paling sering: %s.</strong>'
        '<p class="peta-bantuan-st">%d dari %d jawaban salah datang dari pola ini. %s</p></div>'
    ) % (e(teratas.nama.lower()), teratas.jumlah, data.jumlah_salah, e(teratas.penjelasan))
    per_pola = "".join(
        '<div class="peta-detail-st" data-detail="%s"><strong>%s</strong><p class="peta-bantuan-st">%s</p>'
        '<p class="peta-bantuan-st">Contoh: %s</p>'
        '<p><a href="#m-%s" data-buka="m-%s">Lihat contoh soal dan langkahnya</a></p></div>'
        % (e(p.kunci), e(p.nama), e(p.penjelasan), e(p.contoh), e(p.materi_tujuan), e(p.materi_tujuan))
        for p in data.pola)
    return '<div class="peta-pola-detail-st" id="peta-pola-detail" aria-live="polite">%s%s</div>' % (awal, per_pola)


def _kartu_pola(data) -> str:
    return (
        '<div class="peta-kartu-st peta-pola-st">%s<p class="peta-pita-judul-st">Dari mana datangnya %d jawaban salah?</p>'
        '%s<p class="peta-cara-baca-st">Cara membaca: <strong>semakin lebar irisannya, semakin sering salah di langkah itu.</strong> '
        'Angka di irisan = jumlah jawaban salah.<span class="peta-hanya-js-st peta-sebaris-st"> Ketuk irisan atau kartu di bawah.</span></p>'
        '<div class="peta-pola-bawah-st">%s%s</div></div>'
    ) % (_hiasan(), data.jumlah_salah, render_donat(data.pola, data.jumlah_soal, data.jumlah_salah), _daftar(data), _detail(data))


def _kosong(data) -> str:
    return (
        '<div class="peta-kartu-st"><p>Tidak ada jawaban salah di %d soal yang diperiksa, jadi belum ada pola kesalahan '
        'yang perlu dikelompokkan.</p></div>' % data.jumlah_soal
    )


def panel_pola(data) -> str:
    bantuan = ("%d jawaban salah dari %d soal, dikelompokkan Guru menurut langkah tempat salahnya muncul."
               % (data.jumlah_salah, data.jumlah_soal))
    kepala = kepala_panel("cari", "navy", "h-pola", "Pola kesalahan", bantuan)
    isi = _kartu_pola(data) if data.pola else _kosong(data)
    return '<section class="peta-panel-st" id="pola" data-peta-panel aria-labelledby="h-pola">%s%s</section>' % (kepala, isi)
