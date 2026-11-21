"""Halaman HTML Latihan Lomba untuk anak (murni render, tanpa akses DB).

Menerima data aman dari ``contest_store`` (``SoalAnak``, ``HasilRingkas``): kunci jawaban,
pembahasan, dan label pengecoh tidak pernah sampai ke sini. Semua teks dari DB di-escape; hanya
``svg`` dan ``gambar_pilihan`` (sudah divalidasi di generator soal) disisipkan sebagai markup.
JS hanya penghitung mundur (``contest_browser.SKRIP_TIMER``) sebagai ``<script>`` polos berhash CSP;
tanpa JS, semua halaman tetap berfungsi dan timer ditegakkan server.
"""
from __future__ import annotations

import html
from typing import AbstractSet, Optional

import brand
import contest_core as C
import contest_store as K
from contest_browser import SKRIP_TIMER
from contest_style import GAYA_LOMBA

DASAR = "/murid/lomba"
ALAMAT_AWAL = DASAR
ALAMAT_MULAI = DASAR + "/mulai"
BATAS_MERAH_DETIK = 180
JUMLAH_SOAL = K.NOMOR_TERAKHIR
PESAN_GALAT_ANGKA = "Tulis angka saja ya"
_DETIK_PER_MENIT = 60
_FONT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700'
    '&family=Plus+Jakarta+Sans:wght@700;800&display=swap" rel="stylesheet">'
)


def alamat_sesi(sesi_id: int, nomor: int = 1, galat: bool = False) -> str:
    return f"{DASAR}/sesi/{int(sesi_id)}?no={int(nomor)}" + ("&galat=angka" if galat else "")


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


def _dokumen(judul: str, isi: str, skrip: str = "") -> bytes:
    """Dokumen lengkap; CSS hanya dimuat di sini, skrip (bila ada) polos tanpa atribut."""
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}
{_FONT}
<style>{GAYA_LOMBA}</style></head>
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


def _strip_nomor(nomor_aktif: int, terjawab: AbstractSet[int]) -> str:
    butir = "".join(_tombol_nomor(n, n == nomor_aktif, n in terjawab) for n in range(1, JUMLAH_SOAL + 1))
    return f'<nav aria-label="Nomor soal"><ol class="strip">{butir}</ol></nav>'


def _tombol_pilihan(huruf: str, teks: str, gambar: str, dipilih: bool) -> str:
    kelas = "pilih dipilih" if dipilih else "pilih"
    isi = gambar if gambar else html.escape(teks)
    return (f'<button type="submit" name="jawaban" value="{huruf}" class="{kelas}" '
            f'aria-pressed="{"true" if dipilih else "false"}">'
            f'<span class="huruf">{huruf}</span><span class="isi-pilihan">{isi}</span></button>')


def _blok_pilihan(soal: K.SoalAnak) -> str:
    gambar = soal.gambar_pilihan or ("",) * len(soal.pilihan)
    tombol = "".join(_tombol_pilihan(huruf, teks, gambar[i], soal.jawaban == huruf)
                     for i, (huruf, teks) in enumerate(zip(C.HURUF, soal.pilihan)))
    kelas = "pilihan bergambar" if any(gambar) else "pilihan"
    return f'<div class="{kelas}" role="group" aria-label="Pilihan jawaban">{tombol}</div>'


def _blok_isian(soal: K.SoalAnak, galat: bool) -> str:
    nilai = html.escape(soal.jawaban or "", quote=True)
    pesan = f'<p class="galat" role="alert">{PESAN_GALAT_ANGKA}</p>' if galat else ""
    return (f'<div class="isian"><label for="isi-jawaban">Tulis jawabanmu (angka saja)</label>'
            f'<input type="text" id="isi-jawaban" inputmode="numeric" pattern="[0-9]*" maxlength="6" '
            f'autocomplete="off" name="jawaban" value="{nilai}">{pesan}'
            f'<button type="submit" name="aksi" value="simpan" class="tombol">Simpan</button></div>')


def _tombol_geser(nomor: int) -> str:
    sebelumnya = (f'<button type="submit" name="pindah" value="{nomor - 1}" class="tombol sekunder">'
                  'Sebelumnya</button>') if nomor > K.NOMOR_PERTAMA else ""
    berikutnya = (f'<button type="submit" name="pindah" value="{nomor + 1}" class="tombol">'
                  'Berikutnya</button>') if nomor < JUMLAH_SOAL else ""
    return f'<div class="aksi">{sebelumnya}{berikutnya}</div>'


def halaman_soal(sesi_id: int, soal: K.SoalAnak, terjawab: AbstractSet[int], sisa: int,
                 galat: bool = False) -> bytes:
    """Satu soal per layar. Urutan DOM: tombol Simpan bawaan (tersembunyi-visual) paling awal di form."""
    jawaban = _blok_pilihan(soal) if soal.jenis == C.JENIS_PG else _blok_isian(soal, galat)
    gambar = f'<div class="gambar">{soal.svg}</div>' if soal.svg else ""
    topik = html.escape(C.LABEL_TOPIK.get(soal.topik, ""))
    isi = f"""{_bilah(sesi_id, sisa, f"Soal {soal.nomor} dari {JUMLAH_SOAL}")}
<main class="isi"><h1 class="sr-saja">Latihan Lomba</h1>
<form method="post" action="{alamat_jawab(sesi_id)}">
<button type="submit" name="aksi" value="simpan" class="sr-saja">Simpan</button>
<input type="hidden" name="no" value="{soal.nomor}">
{_strip_nomor(soal.nomor, terjawab)}
<section class="kartu"><p class="topik">{topik}</p>
<p class="teks-soal">{html.escape(soal.teks)}</p>{gambar}{jawaban}</section>
{_tombol_geser(soal.nomor)}
<button type="submit" name="aksi" value="selesai" class="tombol besar">Selesai</button>
</form>
</main>"""
    return _dokumen(f"Soal {soal.nomor}", isi, _skrip_timer())


def halaman_awal(sesi: Optional[K.SesiRingkas], sisa: int = 0) -> bytes:
    """Penjelasan singkat + Mulai, atau Lanjutkan bila ada sesi berjalan."""
    if sesi is None:
        aksi = (f'<form method="post" action="{ALAMAT_MULAI}">'
                '<button type="submit" class="tombol besar">Mulai</button></form>')
        status = ""
    else:
        aksi = f'<a class="tombol besar" href="{alamat_sesi(sesi.id)}">Lanjutkan</a>'
        status = f'<p class="catatan">Latihanmu masih berjalan. Sisa waktu: <strong>{mmss(sisa)}</strong></p>'
    isi = f"""<main class="isi"><section class="kartu">
<h1 class="judul">Latihan Lomba</h1>
<ul class="daftar-aturan"><li>{JUMLAH_SOAL} soal</li><li>Waktumu {K.DURASI_DETIK // _DETIK_PER_MENIT} menit</li>
<li>Boleh pindah-pindah soal, jawabanmu tersimpan</li></ul>
{status}{aksi}
</section></main>"""
    return _dokumen("Latihan Lomba", isi)


def halaman_selesai(sesi_id: int, belum: int, sisa: int) -> bytes:
    """Konfirmasi native sebelum mengumpulkan."""
    pesan = (f"Masih ada <strong>{int(belum)}</strong> soal belum dijawab" if belum > 0
             else "Semua soal sudah dijawab")
    isi = f"""{_bilah(sesi_id, sisa, "Selesai?")}
<main class="isi"><section class="kartu">
<h1 class="judul">Kumpulkan sekarang?</h1><p>{pesan}</p>
<form method="post" action="{alamat_kumpul(sesi_id)}"><button type="submit" class="tombol besar">Ya, kumpulkan</button></form>
<a class="tombol sekunder" href="{alamat_sesi(sesi_id)}">Kembali ke soal</a>
</section></main>"""
    return _dokumen("Kumpulkan", isi, _skrip_timer())


def halaman_hasil(hasil: K.HasilRingkas) -> bytes:
    """Hasil Tahap 2: nilai dan waktu saja (tanpa jawaban benar atau pembahasan)."""
    judul = "Waktu habis!" if hasil.status == K.WAKTU_HABIS else "Sesi selesai!"
    isi = f"""<main class="isi"><section class="kartu">
<h1 class="judul">{judul}</h1>
<p class="angka-besar">Nilai: {int(hasil.nilai)} dari {int(hasil.jumlah_soal)}</p>
<p>Waktu: {mmss(hasil.waktu_terpakai_detik)}</p>
<form method="post" action="{ALAMAT_MULAI}"><button type="submit" class="tombol besar">Latihan lagi</button></form>
</section></main>"""
    return _dokumen("Hasil latihan", isi)


def halaman_gagal_siapkan() -> bytes:
    """Ramah anak saat soal gagal dirakit; tanpa detail teknis."""
    isi = f"""<main class="isi"><section class="kartu">
<h1 class="judul">Soal belum bisa disiapkan</h1><p>Coba lagi nanti, ya.</p>
<a class="tombol besar" href="{ALAMAT_AWAL}">Kembali</a>
</section></main>"""
    return _dokumen("Soal belum siap", isi)
