"""Lembar Hasil Peta Kemampuan: ringkasan 1 halaman A4 (cetak, PDF, kirim WhatsApp).

`render_lembar(data, *, contoh)` memberi markup lembar saja; kerangka dokumen
(`halaman_lembar`) memasang CSS `peta_style_lembar` dan skrip cetak polos. Isi
mengikuti PANDUAN §3: kop + maskot, kotak data, hasil + posisi + lencana, materi,
Temuan Guru, resep latihan 7 lingkaran, misi, catatan Guru + paraf "Si Jago" +
cap "KEPALA SEKOLAH ★ JAGOMAT ★", batas lembar. Istilahnya "hasil cek" dan "temuan Guru".
Angka dari data dan `hitung_posisi`; semua teks di-escape.
"""
from __future__ import annotations

import math

import brand
import landing
from peta_browser import SKRIP_CETAK
from peta_data import periksa_konsisten
from peta_ikon import ikon, ubin_materi
from peta_komponen import JALUR_LAPORAN_CONTOH, bar_penguasaan, label_dari_materi, persen_materi, status_chip
from peta_posisi import hitung_posisi
from peta_style_lembar import GAYA_LEMBAR
from peta_teks import e, kalimat_posisi, tanggal_cap, tanggal_pendek, teks_peringkat

JALUR_LOGO = "/aset/lockup-horizontal.svg"
JALUR_MASKOT = "/aset/maskot-merayakan-v3-240.png"
JARI_CINCIN = 50
KELILING_CINCIN = 2 * math.pi * JARI_CINCIN
MAKS_TEMUAN = 3
HARI = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
WARNA_LENCANA = ("teal", "amber")
COPY_BATAS = (
    "Dibuat dari %d soal yang dikerjakan. Materi di luar soal itu belum diperiksa. Lembar ini membantu "
    "memilih latihan yang tepat sasaran; hasil latihan bisa berbeda pada tiap anak dan lembar ini tidak "
    "memperkirakan nilai rapor. Peringkat dihitung dari anak kelas %d yang sudah ikut Cek Jagomat."
)
COPY_SINTETIS = "Contoh dengan data sintetis, bukan hasil anak sungguhan."
JUDUL_DOKUMEN = "Lembar Hasil Peta Kemampuan"
COPY_RINGKASAN_TINJAU = "Ringkasan satu halaman dari cek matematika yang ditinjau Guru."
COPY_RINGKASAN_BELUM = "Ringkasan satu halaman dari cek matematika. Belum ditinjau Guru."
_DOODLE = ((1, 2, 30, -10, "+"), (60, 8, 28, 12, "×"), (82, 1, 26, 0, "÷"), (44, 58, 26, -8, "½"))


def _doodle() -> str:
    span = "".join(
        '<span style="left:%d%%;top:%d%%;font-size:%dpx;transform:rotate(%ddeg)">%s</span>' % (kiri, atas, ukuran, putar, e(s))
        for kiri, atas, ukuran, putar, s in _DOODLE)
    return '<div class="peta-l-doodle-st" aria-hidden="true">%s</div>' % span


def _kop(ditinjau: bool) -> str:
    return (
        '<header class="peta-l-kop-st">%s<div><span class="peta-l-logo-kotak-st"><img src="%s" alt="Jagomat" width="249" height="48"></span>'
        '<h1>%s</h1><p>%s</p></div>'
        '<img src="%s" alt="" width="78" height="78"></header>'
    ) % (_doodle(), JALUR_LOGO, e(JUDUL_DOKUMEN), e(COPY_RINGKASAN_TINJAU if ditinjau else COPY_RINGKASAN_BELUM), JALUR_MASKOT)


def _kotak_data(data) -> str:
    kolom = (
        ("Nama anak", data.nama_anak), ("Kelas", "%d SD" % data.kelas), ("Tanggal cek", tanggal_pendek(data.tanggal_cek)),
        ("Soal", "%d soal" % data.jumlah_soal),
        ("Ditinjau oleh", data.guru.nama) if data.ditinjau else ("Peninjauan", "Belum ditinjau Guru"),
    )
    isi = "".join("<div><small>%s</small><b>%s</b></div>" % (e(k), e(v)) for k, v in kolom)
    return '<section class="peta-l-data-st" aria-label="Data cek">%s</section>' % isi


def _cincin(skor: int) -> str:
    return (
        '<div class="peta-l-cincin-st" role="img" aria-label="Skor %d dari 100"><svg viewBox="0 0 120 120" aria-hidden="true">'
        '<circle class="peta-cincin-trek-st" cx="60" cy="60" r="%d"/><circle class="peta-cincin-isi-st" cx="60" cy="60" r="%d" '
        'stroke-dasharray="%.1f %.1f"/></svg><div class="peta-l-cincin-angka-st" aria-hidden="true"><b>%d</b><small>dari 100</small></div></div>'
    ) % (skor, JARI_CINCIN, JARI_CINCIN, KELILING_CINCIN * skor / 100, KELILING_CINCIN, skor)


def _lencana_dapat(data) -> str:
    dapat = [l for l in data.lencana if l.didapat]
    isi = "".join(
        '<span class="peta-l-lencana-%s-st"><i>%s</i><em>%s</em></span>' % (WARNA_LENCANA[i % len(WARNA_LENCANA)], ikon(l.ikon, 16), e(l.nama))
        for i, l in enumerate(dapat))
    return '<div class="peta-l-lencana-st">%s</div>' % isi if dapat else ""


def _kartu_hasil(data, posisi) -> str:
    return (
        '<section class="peta-l-kartu-st peta-l-skor-st"><p class="peta-l-ttl-st"><span class="peta-l-nomor-st">1</span>Hasil keseluruhan</p>'
        '%s<span class="peta-l-pita-st">%s</span><p class="peta-l-posisi-st">%s<br><span>%s</span></p>%s</section>'
    ) % (_cincin(data.skor), e(data.kategori), kalimat_posisi(posisi, data.kelas), e(teks_peringkat(posisi)), _lencana_dapat(data))


def _baris_materi(materi) -> str:
    return (
        '<li>%s<span class="peta-l-nm-st">%s</span>%s<b>%d%%</b>%s</li>'
    ) % (ubin_materi(materi.kunci, "s"), e(materi.nama), bar_penguasaan(materi), persen_materi(materi),
         status_chip(label_dari_materi(materi)))


def _kartu_materi(data) -> str:
    return (
        '<section class="peta-l-kartu-st"><p class="peta-l-ttl-st"><span class="peta-l-nomor-st">2</span>Penguasaan per materi</p>'
        '<ul class="peta-l-materi-st">%s</ul></section>'
    ) % "".join(_baris_materi(m) for m in data.materi)


def _temuan(data) -> str:
    per_kunci = {p.kunci: p for p in data.pola}
    butir = []
    for t in data.temuan[:MAKS_TEMUAN]:
        pola = per_kunci[t.pola_kunci]
        butir.append(
            '<li>%s<div><b>%s</b><span class="peta-l-hit-st">%d dari %d jawaban salah</span>'
            '<span class="peta-l-ct-st">Contoh: %s</span></div></li>'
            % (ubin_materi(pola.materi_tujuan, "m"), e(t.judul), pola.jumlah, data.jumlah_salah, e(pola.contoh)))
    return (
        '<section class="peta-l-kartu-st"><p class="peta-l-ttl-st"><span class="peta-l-nomor-st">3</span>'
        'Temuan Guru: di langkah mana salahnya</p><ul class="peta-l-temuan-st">%s</ul></section>'
    ) % "".join(butir)


def _resep(data) -> str:
    lingkaran = "".join('<span class="peta-l-hr-st"><i></i>%s</span>' % h for h in HARI)
    return (
        '<section class="peta-l-resep-st"><span class="peta-l-rx-st" aria-hidden="true">%s</span><div>'
        '<h3>Resep latihan minggu ini</h3><p><b>%s.</b> %s</p><div class="peta-l-hari-st">%s</div></div></section>'
    ) % (ikon("resep", 26, "2.2"), e(data.resep.judul), e(data.resep.teks), lingkaran)


def _misi(data) -> str:
    butir = "".join(
        '<li><span class="peta-l-no-st">Misi %d</span><span><b>%s</b><span class="peta-l-k-st">%s</span></span></li>'
        % (i, e(m.judul), e(m.catatan)) for i, m in enumerate(data.misi, start=1))
    return (
        '<section><p class="peta-l-ttl-st"><span class="peta-l-nomor-st">4</span>Misi berikutnya</p>'
        '<ol class="peta-l-misi-st">%s</ol></section>'
    ) % butir


def _cap(data) -> str:
    return (
        '<svg class="peta-l-cap-st" viewBox="0 0 100 100" aria-hidden="true"><defs><path id="peta-lingkar-cap" '
        'd="M50 50 m-36 0 a36 36 0 1 1 72 0 a36 36 0 1 1 -72 0"/></defs><circle class="peta-l-cap-garis-st" cx="50" cy="50" r="46"/>'
        '<circle class="peta-l-cap-garis-tipis-st" cx="50" cy="50" r="28"/><text class="peta-l-cap-t-st"><textPath href="#peta-lingkar-cap" '
        'startOffset="0">KEPALA SEKOLAH ★ JAGOMAT ★</textPath></text><text class="peta-l-cap-b-st" x="50" y="47" text-anchor="middle">JAGO</text>'
        '<text class="peta-l-cap-k-st" x="50" y="60" text-anchor="middle">%s</text></svg>'
    ) % e(tanggal_cap(data.tanggal_terbit))


def _paraf() -> str:
    return (
        '<svg class="peta-l-paraf-st" viewBox="0 0 170 46" aria-hidden="true"><text class="peta-l-paraf-t-st" x="6" y="32">Si Jago</text>'
        '<path class="peta-l-paraf-garis-st" d="M8 40 C 50 34, 92 46, 120 36 S 160 30, 166 22"/></svg>'
    )


def _catatan(data) -> str:
    if not data.ditinjau:
        return ""  # tanpa tinjauan tidak ada catatan, paraf, atau cap yang menyiratkan pengesahan
    return (
        '<section class="peta-l-kartu-st peta-l-guru-st"><div><p class="peta-l-ttl-st"><span class="peta-l-nomor-st">5</span>Catatan Guru</p>'
        '<blockquote>%s</blockquote></div><div class="peta-l-ttd-st"><div class="peta-l-garis-st">%s%s</div>'
        '<b>Si Jago</b>Kepala Sekolah Jagomat</div></section>'
    ) % (e(data.catatan_guru), _paraf(), _cap(data))


def _kaki(data, contoh: bool) -> str:
    sintetis = '<span class="peta-l-sint-st">%s</span><br>' % e(COPY_SINTETIS) if contoh else ""
    return (
        '<footer class="peta-l-kaki-st"><div>%s<b>Batas lembar ini:</b> %s</div>'
        '<div class="peta-l-situs-st"><b>jagomat.id</b><br>Jago karena tahu caranya.</div></footer>'
    ) % (sintetis, e(COPY_BATAS % (data.jumlah_soal, data.kelas)))


def render_lembar(data, *, contoh: bool) -> str:
    """Markup satu lembar A4; ValueError bila angka `data` tidak saling cocok."""
    periksa_konsisten(data)
    posisi = hitung_posisi(data.skor, data.skor_pembanding)
    return (
        '<main class="peta-l-hal-st">%s%s<div class="peta-l-dua-st">%s%s</div>%s%s%s%s%s</main>'
    ) % (_kop(data.ditinjau), _kotak_data(data), _kartu_hasil(data, posisi), _kartu_materi(data), _temuan(data), _resep(data),
         _misi(data), _catatan(data), _kaki(data, contoh))


def halaman_lembar(data, *, contoh: bool, tautan_kembali: str = JALUR_LAPORAN_CONTOH) -> bytes:
    """Dokumen HTML lengkap (A4, siap cetak); satu skrip polos untuk tombol cetak."""
    alat = (
        '<div class="peta-l-alat-st"><a href="%s">← Kembali ke laporan</a>'
        '<button type="button" class="peta-l-utama-st" data-peta-cetak>Cetak / simpan PDF</button></div>'
    ) % e(tautan_kembali)
    judul = JUDUL_DOKUMEN + (" (contoh)" if contoh else "")
    return ((
        '<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>%s</title>%s%s<style>%s</style></head>'
        '<body class="peta-l-badan-st">%s<div class="peta-l-bungkus-st">%s</div><script>%s</script></body></html>'
    ) % (e(brand.judul(judul)), brand.tag_kepala(None), landing._font_link(), GAYA_LEMBAR, alat,
         render_lembar(data, contoh=contoh), SKRIP_CETAK)).encode()
