"""Renderer laporan Peta Kemampuan lengkap (playful v4) dari `LaporanPeta`.

`render_laporan(data, *, contoh)` mengembalikan markup (str): hero teal dengan
maskot, kartu skor + kategori + posisi, kotak batas laporan, empat tab, dan satu
skrip polos (`peta_browser.SKRIP_PETA`). Posisi (persentil/peringkat) dihitung
`peta_posisi.hitung_posisi`; tidak ada angka posisi tulis tangan.

Fallback tanpa JS: keempat panel tampil berurutan dan tab menjadi tautan jangkar.
Dengan JS, kelas `peta-js-st` pada `<html>` dan atribut `hidden` menyembunyikan
panel yang tidak aktif. Semua teks dari data di-escape.
"""
from __future__ import annotations

import math

from peta_browser import SKRIP_PETA
from peta_data import periksa_konsisten
from peta_ikon import ikon
from peta_materi import panel_per_materi
from peta_misi import panel_misi
from peta_pola import panel_pola
from peta_posisi import hitung_posisi
from peta_ringkasan import panel_ringkasan
from peta_teks import e, kalimat_posisi, tanggal_pendek, teks_biasa

JALUR_ASET = "/aset/maskot-%s-v3-240.png"
UKURAN_MASKOT = 132
JARI_CINCIN = 50
KELILING_CINCIN = 2 * math.pi * JARI_CINCIN
_TAB = (
    ("ringkasan", "Ringkasan", "bintang", "menyapa", "Halo! Ini peta kemampuan %s. Yuk, lihat dulu yang sudah jago."),
    ("per-materi", "Per materi", "peta", "berpikir", "Ketuk satu materi. Aku tunjukkan di langkah mana salahnya."),
    ("pola", "Pola kesalahan", "cari", "membaca", "Salah itu wajar. Yang penting kita tahu polanya."),
    ("langkah", "Misi berikutnya", "roket", "menulis", "Satu misi kecil tiap hari, 10 menit saja. Kumpulkan stikernya!"),
)
# (kiri %, atas %, ukuran px, putar derajat, simbol): hiasan hero.
_DOODLE = (
    (3, 8, 56, -10, "+"), (30, 70, 64, 12, "×"), (52, 4, 48, 0, "÷"), (66, 62, 52, -8, "½"),
    (88, 6, 60, 10, "7"), (93, 70, 54, 0, "="), (18, 40, 40, 16, "3"), (44, 44, 44, 0, "−"),
)
COPY_BATAS = (
    "Dibuat dari %d soal yang dikerjakan %s. Materi di luar soal itu belum diperiksa, "
    "dan laporan ini tidak memperkirakan nilai rapor."
)
COPY_KAKI = (
    "Laporan ini membantu memilih latihan yang tepat sasaran. Hasil latihan bisa berbeda pada tiap anak. "
    "Peringkat dihitung dari anak kelas %d yang sudah ikut Cek Jagomat, bukan seluruh anak kelas %d di Indonesia."
)
COPY_CHIP_TINJAU = "Ditinjau Guru"
COPY_CHIP_BELUM_TINJAU = "Belum ditinjau Guru"
COPY_KAKI_CONTOH = "Contoh dengan data sintetis, bukan hasil anak sungguhan. Laporan sungguhan berbeda untuk tiap anak."


def _aset(pose: str) -> str:
    return JALUR_ASET % pose


def _doodle() -> str:
    span = "".join(
        '<span style="left:%d%%;top:%d%%;font-size:%dpx;transform:rotate(%ddeg)">%s</span>' % (kiri, atas, ukuran, putar, e(s))
        for kiri, atas, ukuran, putar, s in _DOODLE)
    return '<div class="peta-doodle-st" aria-hidden="true">%s</div>' % span


def _cincin_skor(skor: int) -> str:
    isi = KELILING_CINCIN * skor / 100
    return (
        '<div class="peta-cincin-st" role="img" aria-label="Skor %d dari 100">'
        '<svg viewBox="0 0 120 120" aria-hidden="true"><circle class="peta-cincin-trek-st" cx="60" cy="60" r="%d"/>'
        '<circle class="peta-cincin-isi-st" cx="60" cy="60" r="%d" stroke-dasharray="%.1f %.1f"/></svg>'
        '<div class="peta-cincin-angka-st" aria-hidden="true"><b>%d</b><small>dari 100</small></div></div>'
    ) % (skor, JARI_CINCIN, JARI_CINCIN, isi, KELILING_CINCIN, skor)


def _kartu_skor(data, posisi) -> str:
    bantuan = teks_biasa(kalimat_posisi(posisi, data.kelas)) + "." if posisi else kalimat_posisi(posisi, data.kelas)
    return (
        '<div class="peta-skor-st">%s<span class="peta-pita-st">%s</span><span class="peta-bantuan-st">%s</span></div>'
    ) % (_cincin_skor(data.skor), e(data.kategori), e(bantuan))


def _hero(data, posisi, contoh: bool) -> str:
    judul = "h2" if contoh else "h1"
    chip_contoh = '<span class="peta-chip-st peta-chip-netral-st">Contoh · data sintetis</span>' if contoh else ""
    return (
        '<section class="peta-hero-st" aria-labelledby="peta-judul">%s'
        '<div class="peta-maskot-st"><img id="peta-maskot" src="%s" alt="" width="%d" height="%d"></div>'
        '<div class="peta-hero-tengah-st"><p class="peta-gelembung-st" id="peta-gelembung" aria-live="polite">%s</p>'
        '<span class="peta-alis-st">Peta Kemampuan</span><%s id="peta-judul">Laporan %s · Kelas %d</%s>'
        '<div class="peta-chips-st"><span class="peta-chip-st">%s %s</span>'
        '<span class="peta-chip-st peta-chip-netral-st">%d soal · %s</span>%s</div></div>%s</section>'
    ) % (_doodle(), _aset("menyapa"), UKURAN_MASKOT, UKURAN_MASKOT, e(_TAB[0][4] % data.nama_anak), judul,
         e(data.nama_anak), data.kelas, judul, ikon("cek", 16, "2.6"), COPY_CHIP_TINJAU if data.ditinjau else COPY_CHIP_BELUM_TINJAU,
         data.jumlah_soal, e(tanggal_pendek(data.tanggal_cek)),
         chip_contoh, _kartu_skor(data, posisi))


def _batas(data) -> str:
    return (
        '<p class="peta-batas-st">%s<span><strong>Batas laporan ini:</strong> %s</span></p>'
    ) % (ikon("peta", 22, "2"), e(COPY_BATAS % (data.jumlah_soal, data.nama_anak)))


def _tab(data) -> str:
    tautan = "".join(
        '<a href="#%s" data-peta-tab="%s" data-pose="%s" data-kata="%s">%s%s</a>' % (
            kunci, kunci, e(_aset(pose)), e(kata % data.nama_anak if "%s" in kata else kata), ikon(nama_ikon, 20), e(label))
        for kunci, label, nama_ikon, pose, kata in _TAB)
    return '<nav class="peta-tabs-st" aria-label="Bagian laporan">%s</nav>' % tautan


def _kaki(data, contoh: bool) -> str:
    kalimat = [COPY_KAKI % (data.kelas, data.kelas)]
    if contoh:
        kalimat.append(COPY_KAKI_CONTOH)
    return '<footer class="peta-kaki-st">%s</footer>' % "".join("<p>%s</p>" % e(k) for k in kalimat)


def _cta(contoh: bool) -> str:
    if not contoh:
        return ""
    import funnel_pages

    return funnel_pages._cta_utama(funnel_pages.COPY_CTA)


def render_laporan(data, *, contoh: bool) -> str:
    """Markup laporan lengkap; ValueError bila angka `data` tidak saling cocok."""
    periksa_konsisten(data)
    posisi = hitung_posisi(data.skor, data.skor_pembanding)
    panel = "".join((
        panel_ringkasan(data, posisi, contoh),
        panel_per_materi(data),
        panel_pola(data),
        panel_misi(data, contoh, _cta(contoh), _aset("merayakan")),
    ))
    return (
        '<div class="peta-laporan-st">%s%s%s%s%s<script>%s</script></div>'
    ) % (_hero(data, posisi, contoh), _batas(data), _tab(data), panel, _kaki(data, contoh), SKRIP_PETA)
