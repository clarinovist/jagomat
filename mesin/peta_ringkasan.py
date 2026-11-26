"""Panel Ringkasan laporan Peta Kemampuan: posisi, lencana, jago/perlu, misi utama, catatan Guru.

Kalimat angka dibangun dari data (tidak ada angka tulis tangan di sini).
"""
from __future__ import annotations

from cek_gratis_skor import BATAS_KUAT_PERSEN, LABEL_BELUM_CUKUP, LABEL_KUAT
from peta_ikon import ikon, ubin, ubin_materi
from peta_komponen import (
    JALUR_LEMBAR_CONTOH, gabung_nama, kepala_panel, label_dari_materi, persen_materi,
    pola_per_materi, pola_teratas,
)
from peta_posisi import MINIMAL_PEMBANDING
from peta_teks import (
    e, inisial, kalimat_posisi, kelompok_skor, label_kelompok, sebaran_kelompok, teks_peringkat,
)

WARNA_LENCANA = ("teal", "amber")
TINGGI_BAR_MIN = 4


def _kata_senang(kuat: list) -> str:
    if not kuat:
        return "Belum ada materi yang mencapai label Kuat di cek ini; latihan kecil bisa dimulai dari mana saja."
    return "%s sudah Kuat (%d%% ke atas)." % (gabung_nama([m.nama for m in kuat]), BATAS_KUAT_PERSEN)


def _kata_dikejar(data) -> str:
    teratas = pola_teratas(data)
    if teratas is None:
        return "Tidak ada jawaban salah di soal yang diperiksa."
    return "Pola “%s” muncul di %d dari %d jawaban salah. Mulai dari sana." % (
        teratas.nama, teratas.jumlah, data.jumlah_salah)


def _daftar_kata(data) -> str:
    kuat = [m for m in data.materi if label_dari_materi(m) == LABEL_KUAT]
    butir = (
        ("teal", "cek", "Yang bikin senang:", _kata_senang(kuat)),
        ("koral", "panah-atas", "Yang perlu dikejar:", _kata_dikejar(data)),
    )
    li = "".join(
        '<li>%s<span><b>%s</b> %s</span></li>' % (ubin(nama_ikon, warna, "s"), e(judul), e(isi))
        for warna, nama_ikon, judul, isi in butir
    )
    return '<ul class="peta-posisi-kata-st">%s</ul>' % li


def _batang(jumlah: int, terbesar: int, label: str, aktif: bool, nama: str) -> str:
    tinggi = max(TINGGI_BAR_MIN, round(100 * jumlah / terbesar)) if terbesar else TINGGI_BAR_MIN
    pin = '<span class="peta-pin-st">%s di sini</span>' % e(nama) if aktif else ""
    kelas = "peta-kol-st peta-kol-aktif-st" if aktif else "peta-kol-st"
    return '<div class="%s"><span class="peta-bt-st" style="height:%d%%">%s</span><small>%s</small></div>' % (
        kelas, tinggi, pin, e(label))


def _histogram(data, contoh: bool) -> str:
    sebaran = sebaran_kelompok(data.skor_pembanding)
    jumlah = len(sebaran)
    aktif = kelompok_skor(data.skor, jumlah)
    terbesar = max(sebaran)
    batang = "".join(
        _batang(n, terbesar, label_kelompok(i, jumlah), i == aktif, data.nama_anak) for i, n in enumerate(sebaran))
    aria = "Sebaran skor %d anak kelas %d. %s di kelompok skor %s." % (
        len(data.skor_pembanding), data.kelas, data.nama_anak, label_kelompok(aktif, jumlah))
    keterangan = "Sebaran skor %d anak kelas %d yang sudah ikut Cek Jagomat%s" % (
        len(data.skor_pembanding), data.kelas, " (data sintetis)" if contoh else "")
    return (
        '<div class="peta-histo-st" role="img" aria-label="%s"><div class="peta-histo-bar-st" aria-hidden="true">%s</div>'
        '<p class="peta-histo-ket-st">%s</p></div>'
    ) % (e(aria), batang, e(keterangan))


def _posisi_kosong(data) -> str:
    return (
        '<div class="peta-kartu-st peta-posisi-st peta-posisi-kosong-st"><div class="peta-posisi-kiri-st">'
        '<span class="peta-alis-st">Posisi %s di antara anak kelas %d</span>'
        '<p class="peta-posisi-besar-st">%s</p>'
        '<p class="peta-bantuan-st">Perbandingan ditampilkan setelah minimal %d anak sekelas ikut Cek Jagomat.</p>'
        '</div></div>'
    ) % (e(data.nama_anak), data.kelas, e(teks_peringkat(None)), MINIMAL_PEMBANDING)


def kartu_posisi(data, posisi, contoh: bool) -> str:
    if posisi is None:
        return _posisi_kosong(data)
    return (
        '<div class="peta-kartu-st peta-posisi-st"><div class="peta-posisi-kiri-st">'
        '<span class="peta-alis-st">Posisi %s di antara anak kelas %d</span>'
        '<p class="peta-posisi-besar-st">%s</p>'
        '<div class="peta-chips-st"><span class="peta-chip-st">%s</span></div>%s</div>%s</div>'
    ) % (e(data.nama_anak), data.kelas, kalimat_posisi(posisi, data.kelas),
         e(teks_peringkat(posisi)), _daftar_kata(data), _histogram(data, contoh))


def _lencana(lencana, indeks: int) -> str:
    keadaan = "dapat" if lencana.didapat else "kunci"
    warna = WARNA_LENCANA[indeks % len(WARNA_LENCANA)] if lencana.didapat else "netral"
    tanda = "Didapat" if lencana.didapat else "Terkunci"
    gambar = ikon(lencana.ikon, 32)
    return (
        '<div class="peta-lencana-st peta-lencana-%s-st peta-lencana-%s-st"><div class="peta-medali-st" aria-hidden="true">'
        '<span class="peta-pita-k-st"></span><span class="peta-pita-n-st"></span><span class="peta-bulat-lencana-st">%s</span></div>'
        '<b>%s</b><small>%s</small><span class="peta-tag-st">%s</span></div>'
    ) % (keadaan, warna, gambar, e(lencana.nama), e(lencana.keterangan), tanda)


def kartu_lencana(data, contoh: bool) -> str:
    catatan = "Lencana menandai capaian yang terlihat di cek ini. Yang terkunci belum didapat."
    if contoh:
        catatan += " Ini contoh tampilan lencana."
    isi = "".join(_lencana(l, i) for i, l in enumerate(data.lencana))
    return (
        '<div class="peta-kartu-st"><h3 class="peta-judul-bagian-st">Lencana %s</h3><p class="peta-bantuan-st">%s</p>'
        '<div class="peta-lencana-wrap-st">%s</div></div>'
    ) % (e(data.nama_anak), e(catatan), isi)


def _butir_kuat(materi) -> str:
    return '<li>%s<span><b>%s</b>: %d dari %d benar (%d%%).</span></li>' % (
        ubin_materi(materi.kunci, "s"), e(materi.nama), materi.benar, materi.soal, persen_materi(materi))


def _butir_perkuat(data, materi) -> str:
    pola = pola_per_materi(data, materi.kunci)
    sebab = " (%s)" % "; ".join(p.nama.lower() for p in pola) if pola else ""
    tautan = '<a href="#m-%s" data-buka="m-%s">%s</a>' % (e(materi.kunci), e(materi.kunci), e(materi.nama))
    return '<li>%s<span>%s: %d dari %d soal salah%s.</span></li>' % (
        ubin_materi(materi.kunci, "s"), tautan, materi.salah, materi.soal, e(sebab))


def kartu_jago_dan_perkuat(data) -> str:
    kuat = [m for m in data.materi if label_dari_materi(m) == LABEL_KUAT]
    perkuat = [m for m in data.materi if label_dari_materi(m) not in (LABEL_KUAT, LABEL_BELUM_CUKUP)]
    belum = [m.nama for m in data.materi if label_dari_materi(m) == LABEL_BELUM_CUKUP]
    kosong = '<li><span>Belum ada.</span></li>'
    kiri = "".join(_butir_kuat(m) for m in kuat) or kosong
    kanan = "".join(_butir_perkuat(data, m) for m in perkuat) or kosong
    catatan = ""
    if belum:
        catatan = '<p class="peta-bantuan-st">Belum cukup soal untuk dinilai: %s.</p>' % e(gabung_nama(belum))
    return (
        '<div class="peta-dua-st"><div class="peta-kartu-st peta-k-kuat-st"><h3 class="peta-judul-bagian-st">Sudah jago</h3>'
        '<ul class="peta-daftar-st">%s</ul></div><div class="peta-kartu-st peta-k-perkuat-st">'
        '<h3 class="peta-judul-bagian-st">Perlu diperkuat</h3><ul class="peta-daftar-st">%s</ul></div></div>%s'
    ) % (kiri, kanan, catatan)


def kartu_misi_utama(data) -> str:
    if not data.misi:
        return ""
    misi = data.misi[0]
    pola = next((p for p in data.pola if p.kunci == misi.pola_kunci), None)
    sebab = " %d dari %d jawaban salah ada di pola ini." % (pola.jumlah, data.jumlah_salah) if pola else ""
    return (
        '<div class="peta-kartu-st peta-fokus-st">%s<div><span class="peta-alis-st">Misi utama</span>'
        '<h3>%s</h3><p class="peta-bantuan-st">%s%s</p></div>'
        '<a class="peta-tombol-st" href="#m-%s" data-buka="m-%s">Lihat di langkah mana</a></div>'
    ) % (ubin_materi(misi.materi_kunci, "xl"), e(misi.judul), e(misi.catatan), e(sebab),
         e(misi.materi_kunci), e(misi.materi_kunci))


def kartu_lembar_ajak() -> str:
    return (
        '<div class="peta-kartu-st peta-lembar-ajak-st">%s<div><h3 class="peta-judul-bagian-st">Lembar ringkasan 1 halaman</h3>'
        '<p class="peta-bantuan-st">Inti laporan dalam satu lembar A4: skor, materi, temuan utama, dan resep latihan. '
        'Bisa dicetak, disimpan sebagai PDF, atau dikirim lewat WhatsApp.</p></div>'
        '<a class="peta-tombol-st" href="%s">Buka lembar</a></div>'
    ) % (ubin("lembar", "amber", "l"), JALUR_LEMBAR_CONTOH)


def kartu_catatan_guru(data, contoh: bool) -> str:
    """Kartu catatan Guru hanya untuk laporan sungguhan yang ditinjau Guru dan punya catatan; contoh publik tidak memajangnya."""
    if contoh or not data.ditinjau or not data.catatan_guru.strip():
        return ""  # tanpa tinjauan atau catatan sungguhan, tidak ada nama atau latar Guru yang dipajang
    guru = data.guru
    return (
        '<div class="peta-kartu-st peta-catatan-st"><h3 class="peta-judul-bagian-st">Catatan Guru</h3>'
        '<blockquote>%s</blockquote><div class="peta-guru-st"><span class="peta-inisial-st" aria-hidden="true">%s</span>'
        '<div><strong>%s</strong><small>%s · %s</small></div></div></div>'
    ) % (e(data.catatan_guru), e(inisial(guru.nama)), e(guru.nama), e(guru.latar), e(guru.lama_mengajar))


def panel_ringkasan(data, posisi, contoh: bool) -> str:
    kepala = kepala_panel("bintang", "amber", "h-ringkasan", "Ringkasan",
                          "Gambaran singkat. Ketuk bagian mana saja untuk melihat rinciannya.")
    lembar = kartu_lembar_ajak() if contoh else ""
    return (
        '<section class="peta-panel-st" id="ringkasan" data-peta-panel aria-labelledby="h-ringkasan">%s%s%s%s%s%s%s</section>'
    ) % (kepala, kartu_posisi(data, posisi, contoh), kartu_lencana(data, contoh), kartu_jago_dan_perkuat(data),
         kartu_misi_utama(data), lembar, kartu_catatan_guru(data, contoh))
