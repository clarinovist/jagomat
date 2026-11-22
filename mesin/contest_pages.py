"""Halaman HTML Latihan Lomba untuk anak (murni render, tanpa akses DB).

Menerima data aman dari ``contest_store`` (``SoalAnak``, ``HasilRingkas``): kunci jawaban,
pembahasan, dan label pengecoh tidak pernah sampai ke sini. Semua teks dari DB di-escape; hanya
``svg`` dan ``gambar_pilihan`` (sudah divalidasi di generator soal) disisipkan sebagai markup.
JS hanya penghitung mundur (``contest_browser.SKRIP_TIMER``) sebagai ``<script>`` polos berhash CSP;
tanpa JS, semua halaman tetap berfungsi dan timer ditegakkan server.
"""
from __future__ import annotations

import html
import urllib.parse
from typing import AbstractSet, Sequence

import brand
import contest_core as C
import contest_komponen as KP
import contest_store as K
from contest_browser import SKRIP_TIMER
from contest_style import GAYA_LOMBA

DASAR = "/murid/lomba"
ALAMAT_AWAL = DASAR
ALAMAT_MULAI = DASAR + "/mulai"
BATAS_MERAH_DETIK = 180
JUMLAH_SOAL = K.NOMOR_TERAKHIR
MAKS_ISI_GALAT = 12               # maxlength input isian = panjang ketikan galat yang dipertahankan; beri ruang untuk spasi ("1 2 3 4"), server tetap memvalidasi
PESAN_GALAT_ANGKA = "Tulis angkanya saja, tanpa huruf atau tanda baca. Contoh: 120"
_DETIK_PER_MENIT = 60
_FONT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700'
    '&family=Plus+Jakarta+Sans:wght@700;800&display=swap" rel="stylesheet">'
)


def alamat_sesi(sesi_id: int, nomor: int = 1, galat: bool = False, isi: str = "") -> str:
    """Alamat satu soal; `isi` (ketikan galat, dipotong MAKS_ISI_GALAT) ikut agar anak tak mengetik ulang."""
    alamat = f"{DASAR}/sesi/{int(sesi_id)}?no={int(nomor)}"
    if not galat:
        return alamat
    tambahan = "&isi=" + urllib.parse.quote(isi[:MAKS_ISI_GALAT], safe="") if isi else ""
    return alamat + "&galat=angka" + tambahan


def alamat_jawab(sesi_id: int) -> str:
    return f"{DASAR}/sesi/{int(sesi_id)}/jawab"


def alamat_selesai(sesi_id: int) -> str:
    return f"{DASAR}/sesi/{int(sesi_id)}/selesai"


def alamat_kumpul(sesi_id: int) -> str:
    return f"{DASAR}/sesi/{int(sesi_id)}/kumpul"


def alamat_hasil(sesi_id: int) -> str:
    return f"{DASAR}/hasil/{int(sesi_id)}"


def mmss(detik: int) -> str:
    detik = max(0, int(detik))
    return f"{detik // _DETIK_PER_MENIT:02d}:{detik % _DETIK_PER_MENIT:02d}"


def dokumen(judul: str, isi: str, skrip: str = "", gaya_tambahan: str = "") -> bytes:
    """Dokumen lengkap; CSS hanya dimuat di sini, skrip (bila ada) polos tanpa atribut."""
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}
{_FONT}
<style>{GAYA_LOMBA}{gaya_tambahan}</style></head>
<body class="lomba"><div class="bingkai">
{isi}
</div>{skrip}</body></html>""".encode()


def _skrip_timer() -> str:
    return f"<script>{SKRIP_TIMER}</script>"


def _timer(sesi_id: int, sisa: int) -> str:
    merah = " merah" if sisa <= BATAS_MERAH_DETIK else ""
    return (f'<div class="timer{merah}" id="timer" data-sisa="{int(sisa)}" '
            f'data-hasil="{alamat_hasil(sesi_id)}">{mmss(sisa)}</div>')


def _bilah(sesi_id: int, sisa: int, kiri: str) -> str:
    return f'<header class="bilah"><span class="bilah-nomor">{kiri}</span>{_timer(sesi_id, sisa)}</header>'


def _tombol_nomor(nomor: int, aktif: bool, terjawab: bool) -> str:
    kelas = "nomor " + ("sudah" if terjawab else "belum") + (" aktif" if aktif else "")
    status = "sudah dijawab" if terjawab else "belum dijawab"
    saat_ini = ' aria-current="step"' if aktif else ""
    return (f'<li><button type="submit" name="pindah" value="{nomor}" class="{kelas}"{saat_ini}>'
            f'{nomor}<span class="sr-saja"> {status}</span></button></li>')


def _strip_nomor(nomor_aktif: int, terjawab: AbstractSet[int], jumlah: int) -> str:
    butir = "".join(_tombol_nomor(n, n == nomor_aktif, n in terjawab) for n in range(1, jumlah + 1))
    return f'<nav aria-label="Nomor soal"><ol class="strip">{butir}</ol></nav>'


def _tombol_pilihan(huruf: str, teks: str, gambar: str, dipilih: bool) -> str:
    kelas = "pilih dipilih" if dipilih else "pilih"
    isi = gambar if gambar else html.escape(teks)
    tersimpan = '<span class="tersimpan"><span aria-hidden="true">\u2713</span> tersimpan</span>' if dipilih else ""
    return (f'<button type="submit" name="jawaban" value="{huruf}" class="{kelas}" '
            f'aria-pressed="{"true" if dipilih else "false"}">'
            f'<span class="huruf">{huruf}</span><span class="isi-pilihan">{isi}</span>{tersimpan}</button>')


def _blok_pilihan(soal: K.SoalAnak) -> str:
    gambar = soal.gambar_pilihan or ("",) * len(soal.pilihan)
    tombol = "".join(_tombol_pilihan(huruf, teks, gambar[i], soal.jawaban == huruf)
                     for i, (huruf, teks) in enumerate(zip(C.HURUF, soal.pilihan)))
    kelas = "pilihan bergambar" if any(gambar) else "pilihan"
    return f'<div class="{kelas}" role="group" aria-label="Pilihan jawaban">{tombol}</div>'


def _blok_isian(soal: K.SoalAnak, galat: bool, isi_galat: str) -> str:
    """Kolom angka tanpa tombol Simpan terlihat: Enter memakai tombol bawaan tersembunyi, pindah soal ikut menyimpan."""
    nilai = html.escape(isi_galat if galat and isi_galat else (soal.jawaban or ""), quote=True)
    pesan = f'<p class="galat" role="alert">{PESAN_GALAT_ANGKA}</p>' if galat else ""
    return (f'<div class="isian"><label for="isi-jawaban">Tulis jawabanmu (angka saja)</label>'
            f'<input type="text" id="isi-jawaban" inputmode="numeric" pattern="[0-9]*" maxlength="{MAKS_ISI_GALAT}" '
            f'autocomplete="off" name="jawaban" value="{nilai}">{pesan}'
            '<p class="bantuan">Tekan Enter atau pindah soal, jawabanmu ikut tersimpan.</p></div>')


def _tombol_geser(nomor: int, jumlah: int) -> str:
    """Maju = tombol utama; mundur = sekunder. Pindah selalu menyimpan isian (teks bantuan isian menyebutnya)."""
    sebelumnya = (f'<button type="submit" name="pindah" value="{nomor - 1}" class="tombol sekunder">'
                  f'\u2190 Soal {nomor - 1}</button>') if nomor > K.NOMOR_PERTAMA else ""
    berikutnya = (f'<button type="submit" name="pindah" value="{nomor + 1}" class="tombol">'
                  f'Soal {nomor + 1} \u2192</button>') if nomor < jumlah else ""
    return f'<div class="aksi">{sebelumnya}{berikutnya}</div>'


def halaman_soal(sesi_id: int, soal: K.SoalAnak, terjawab: AbstractSet[int], sisa: int,
                 galat: bool = False, isi_galat: str = "", jumlah: int = JUMLAH_SOAL) -> bytes:
    """Satu soal per layar (`jumlah` = banyak soal sesi: 10 Latihan, 35 Simulasi).

    Urutan DOM: tombol Simpan bawaan (tersembunyi-visual) paling awal di form.
    """
    isian = soal.jenis != C.JENIS_PG
    jawaban = _blok_isian(soal, galat, isi_galat) if isian else _blok_pilihan(soal)
    gambar = f'<div class="gambar">{soal.svg}</div>' if soal.svg else ""
    topik = html.escape(C.LABEL_TOPIK.get(soal.topik, ""))
    isi = f"""{_bilah(sesi_id, sisa, f"Soal {soal.nomor} dari {int(jumlah)}")}
<main class="isi"><h1 class="sr-saja">Latihan Lomba</h1>
<form method="post" action="{alamat_jawab(sesi_id)}" novalidate>
<button type="submit" name="aksi" value="simpan" class="sr-saja">Simpan</button>
<input type="hidden" name="no" value="{soal.nomor}">
{_strip_nomor(soal.nomor, terjawab, jumlah)}
<section class="kartu"><p class="topik">{topik}</p>
<p class="teks-soal">{html.escape(soal.teks)}</p>{gambar}{jawaban}</section>
{_tombol_geser(soal.nomor, jumlah)}
<button type="submit" name="aksi" value="selesai" class="tautan-selesai">Selesai &amp; kumpulkan</button>
</form>
</main>"""
    return dokumen(f"Soal {soal.nomor}", isi, _skrip_timer())


def _nomor_ringkas(nomor: int, kosong: bool, sesi_id: int) -> str:
    if kosong:
        return (f'<li><a class="nomor belum" href="{alamat_sesi(sesi_id, nomor)}">{nomor}'
                '<span class="sr-saja"> belum dijawab, buka soal</span></a></li>')
    return f'<li><span class="nomor sudah">{nomor}<span class="sr-saja"> sudah dijawab</span></span></li>'


def _strip_konfirmasi(sesi_id: int, kosong: AbstractSet[int], jumlah: int) -> str:
    butir = "".join(_nomor_ringkas(n, n in kosong, sesi_id) for n in range(1, jumlah + 1))
    return f'<nav aria-label="Nomor soal"><ol class="strip">{butir}</ol></nav>'


def teks_sisa_waktu(sisa: int) -> str:
    """"Waktumu masih 7 menit" (dibulatkan ke bawah); "kurang dari 1 menit" bila belum genap semenit."""
    menit = max(0, int(sisa)) // _DETIK_PER_MENIT
    return f"Waktumu masih {menit} menit" if menit >= 1 else "Waktumu masih kurang dari 1 menit"


def _form_kumpul(sesi_id: int, label: str, kelas: str) -> str:
    return (f'<form method="post" action="{alamat_kumpul(sesi_id)}">'
            f'<button type="submit" class="{kelas}">{label}</button></form>')


def _isi_masih_kosong(sesi_id: int, kosong: Sequence[int], sisa: int, jumlah: int) -> str:
    pertama = min(kosong)
    return f"""<h1 class="judul">Masih ada {len(kosong)} soal kosong</h1>
<p>{teks_sisa_waktu(sisa)}. Coba isi dulu, ya.</p>
{_strip_konfirmasi(sesi_id, frozenset(kosong), jumlah)}
<a class="tombol besar" href="{alamat_sesi(sesi_id, pertama)}">Kerjakan soal {pertama}</a>
{_form_kumpul(sesi_id, "Kumpulkan sekarang", "tombol sekunder")}"""


def _isi_semua_terisi(sesi_id: int, jumlah: int) -> str:
    return f"""{KP.maskot_kartu("merayakan")}
<h1 class="judul">Semua soal sudah kamu jawab!</h1>
{_strip_konfirmasi(sesi_id, frozenset(), jumlah)}
{_form_kumpul(sesi_id, "Kumpulkan", "tombol besar")}
<a class="tombol sekunder" href="{alamat_sesi(sesi_id, K.NOMOR_PERTAMA)}">Periksa lagi</a>"""


def halaman_selesai(sesi_id: int, kosong: Sequence[int], sisa: int, jumlah: int = JUMLAH_SOAL) -> bytes:
    """Konfirmasi native sebelum mengumpulkan; `kosong` = nomor soal yang belum dijawab dari `jumlah` soal."""
    bagian = _isi_masih_kosong(sesi_id, kosong, sisa, jumlah) if kosong else _isi_semua_terisi(sesi_id, jumlah)
    isi = f"""{_bilah(sesi_id, sisa, "Selesai?")}
<main class="isi"><section class="kartu">
{bagian}
</section></main>"""
    return dokumen("Kumpulkan", isi, _skrip_timer())


def halaman_gagal_siapkan() -> bytes:
    """Ramah anak saat soal gagal dirakit; tanpa detail teknis."""
    isi = f"""<main class="isi"><section class="kartu">
<h1 class="judul">Soal belum bisa disiapkan</h1><p>Coba lagi nanti, ya.</p>
<a class="tombol besar" href="{ALAMAT_AWAL}">Kembali</a>
</section></main>"""
    return dokumen("Soal belum siap", isi)
