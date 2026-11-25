"""Panel Misi berikutnya: misi 1-3, stiker hari, tantangan, jalur 4 minggu, program.

Jalur latihan adalah URUTAN KEGIATAN, bukan janji hasil. Satu tombol utama: CTA
`funnel_pages` hanya dipasang untuk halaman contoh. Tanpa JS: stiker tetap bisa
dicentang (tidak tersimpan) dan jawaban tantangan terbuka lewat `<details>`.
"""
from __future__ import annotations

import paket_belajar_katalog as katalog
from peta_ikon import ikon, ubin_materi
from peta_komponen import kepala_panel
from peta_teks import e

HARI = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
KUNCI_STIKER_CONTOH = "jagomat-contoh-peta-hari"
KUNCI_STIKER = "jagomat-peta-hari"
MINGGU_CEK_ULANG = "Cek ulang bersama Guru, lalu peta baru"
# Keputusan 20 poin 7 (21 Nov 2026): harga kelas tampil di akhir laporan. Angka kelas dari katalog Mini Class
# (`paket_belajar_katalog`, keputusan Pemilik 24 Nov 2026), bukan tulis tangan di sini.
COPY_LOKASI_KELAS = "Kelas berlangsung online lewat Zoom atau Google Meet. Tautan dikirim setelah Anda daftar."
_LABEL_MODE = {katalog.MODE_ONLINE: "online", katalog.MODE_OFFLINE: "tatap muka"}


def _rupiah(nilai: int) -> str:
    return "Rp" + f"{nilai:,}".replace(",", ".")


def _misi(data, indeks: int, misi) -> str:
    pola = next((p for p in data.pola if p.kunci == misi.pola_kunci), None)
    sebab = " (%d dari %d jawaban salah)" % (pola.jumlah, data.jumlah_salah) if pola else ""
    langkah = "".join("<li>%s</li>" % e(l) for l in misi.langkah)
    buka = " open" if indeks == 0 else ""
    return (
        '<li><details%s><summary><span class="peta-no-st">Misi %d</span>%s<span><strong>%s</strong><small>%s%s</small></span>'
        '<span class="peta-panah-st">%s</span></summary><div class="peta-isi-st"><ul>%s</ul></div></details></li>'
    ) % (buka, indeks + 1, ubin_materi(misi.materi_kunci, "m"), e(misi.judul), e(misi.catatan), e(sebab),
         ikon("panah-bawah", 24, "2.2"), langkah)


def _daftar_misi(data) -> str:
    return '<ol class="peta-prioritas-st">%s</ol>' % "".join(_misi(data, i, m) for i, m in enumerate(data.misi))


def _stiker(data, contoh: bool) -> str:
    kunci = KUNCI_STIKER_CONTOH if contoh else KUNCI_STIKER
    bintang = ikon("bintang", 30, "1.2")
    kotak = "".join(
        '<input type="checkbox" id="hari-%d" data-peta-hari data-peta-kunci="%s"><label for="hari-%d"><span class="peta-ck-st">%s</span>%s</label>'
        % (i, e(kunci), i, bintang, hari) for i, hari in enumerate(HARI, start=1))
    return (
        '<div class="peta-kartu-st peta-minggu-st"><div class="peta-kepala-kartu-st"><span class="peta-alis-st">Stiker misi minggu ini</span>'
        '<h3 class="peta-judul-bagian-st">%s</h3><p class="peta-bantuan-st">%s Tempel stiker bintang tiap hari yang sudah dicoba.'
        '<span class="peta-hanya-js-st peta-sebaris-st"> Stiker hanya tersimpan di perangkat ini.</span></p></div>'
        '<div class="peta-hari-st" role="group" aria-label="Hari yang sudah dicoba">%s</div>'
        '<p class="peta-bantuan-st peta-hanya-js-st" id="peta-hari-status">Belum ada hari yang ditandai.</p></div>'
    ) % (e(data.resep.judul), e(data.resep.teks), kotak)


def _tombol_jawab(pilihan) -> str:
    return '<button type="button" data-peta-jawab="%s">%s</button>' % (e(pilihan.kunci), e(pilihan.label))


def _tantangan(data, pose_hore: str) -> str:
    t = data.tantangan
    tombol = "".join(_tombol_jawab(p) for p in t.pilihan)
    return (
        '<div class="peta-kartu-st peta-coba-st" data-peta-coba data-benar="%s" data-umpan-benar="%s" data-umpan-salah="%s" '
        'data-pose-hore="%s" data-kata-hore="%s"><div class="peta-kepala-kartu-st"><span class="peta-alis-st">Tantangan malam ini</span>'
        '<h3 class="peta-judul-bagian-st">%s</h3><p class="peta-bantuan-st">%s</p></div>'
        '<div class="peta-konfeti-st" id="peta-konfeti" aria-hidden="true"></div>'
        '<div class="peta-coba-opsi-st peta-hanya-js-st" role="group" aria-label="Pilih operasi">%s</div>'
        '<p class="peta-coba-umpan-st peta-hanya-js-st" id="peta-coba-umpan" aria-live="polite"></p>'
        '<details class="peta-tanpa-js-st peta-jawaban-st"><summary>Lihat jawabannya</summary><p>%s</p></details></div>'
    ) % (e(t.benar), e(t.umpan_benar), e(t.umpan_salah), e(pose_hore), e(t.kata_maskot), e(t.soal), e(t.petunjuk),
         tombol, e(t.umpan_benar))


def _jalur(data) -> str:
    langkah = [m.minggu for m in data.misi[:3]] + [MINGGU_CEK_ULANG]
    butir = []
    for i, teks in enumerate(langkah, start=1):
        terakhir = i == len(langkah)
        batu = ikon("bintang", 26, "2.2") if terakhir else str(i)
        butir.append('<li><span class="peta-batu-st">%s</span><b>Minggu %d</b>%s</li>' % (batu, i, e(teks)))
    return (
        '<div class="peta-kartu-st"><div class="peta-kepala-kartu-st"><span class="peta-alis-st">Jalur latihan %d minggu</span>'
        '<p class="peta-bantuan-st">Ini urutan kegiatan, bukan janji hasil. Minggu 1–3 bisa Anda mulai sendiri; '
        'cek ulang dengan soal baru di minggu ke-4 dikerjakan bersama Guru.</p></div>'
        '<ol class="peta-jalur-st">%s</ol></div>'
    ) % (len(langkah), "".join(butir))


def _centang(teks: str) -> str:
    return '<li>%s<span>%s</span></li>' % (ikon("cek", 20, "2.6"), e(teks))


def _program(cta_html: str) -> str:
    from funnel_pages import COPY_DEPOSIT, COPY_KONSULTASI, COPY_TIDAK_WAJIB_KELAS

    mini = katalog.ambil(katalog.KODE_MINI)
    kelas = (
        "Mulai dari fokus di laporan ini.",
        "Kelas kecil maksimal %d anak, %s, %d menit per pertemuan, dipandu Guru."
        % (mini.kuota, _LABEL_MODE[mini.mode], mini.menit),
        "%d pertemuan dalam sebulan, jadwal diatur tim." % mini.pertemuan,
    )
    harga = "%s per bulan, %d pertemuan." % (_rupiah(mini.harga), mini.pertemuan)
    return (
        '<div class="peta-program-st"><div class="peta-kartu-st peta-konsul-st"><span class="peta-alis-st">Termasuk dalam Peta Kemampuan</span>'
        '<h3 class="peta-judul-bagian-st">Konsultasi 20 menit dengan Guru</h3><p>%s</p>%s</div>'
        '<div class="peta-kartu-st peta-kelas-st"><span class="peta-alis-st">Kalau ingin didampingi</span>'
        '<h3 class="peta-judul-bagian-st">Kelas kecil Jagomat</h3><ul class="peta-cek-st">%s</ul>'
        '<p class="peta-bantuan-st"><b>%s</b></p>'
        '<div class="peta-voucher-st">%s<span>%s %s</span></div>'
        '<p class="peta-bantuan-st">%s Jadwal dan rincian lain kita bahas saat konsultasi.</p></div></div>'
    ) % (e(COPY_KONSULTASI), cta_html, "".join(_centang(k) for k in kelas), e(harga), ikon("voucher", 22, "2"),
         e(COPY_DEPOSIT), e(COPY_TIDAK_WAJIB_KELAS), e(COPY_LOKASI_KELAS))


def panel_misi(data, contoh: bool, cta_html: str, pose_hore: str) -> str:
    kepala = kepala_panel("roket", "koral", "h-langkah", "Misi berikutnya",
                          "Urutan yang disarankan Guru. Satu misi kecil dulu, 10 menit sehari.")
    return (
        '<section class="peta-panel-st" id="langkah" data-peta-panel aria-labelledby="h-langkah">%s%s%s%s%s%s</section>'
    ) % (kepala, _daftar_misi(data), _stiker(data, contoh), _tantangan(data, pose_hore), _jalur(data), _program(cta_html))
