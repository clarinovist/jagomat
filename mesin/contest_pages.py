"""Halaman HTML Latihan Lomba untuk anak (murni render, tanpa akses DB).

Menerima data aman dari ``contest_store`` (``SoalAnak``, ``HasilRingkas``): kunci jawaban,
pembahasan, dan label pengecoh tidak pernah sampai ke sini. Semua teks dari DB di-escape; hanya
``svg`` dan ``gambar_pilihan`` (sudah divalidasi di generator soal) disisipkan sebagai markup.
JS hanya penghitung mundur (``contest_browser.SKRIP_TIMER``) sebagai ``<script>`` polos berhash CSP;
tanpa JS, semua halaman tetap berfungsi dan timer ditegakkan server.
"""
from __future__ import annotations

import html
from typing import TYPE_CHECKING, AbstractSet, Optional, Sequence

import brand
import contest_core as C
import contest_store as K
from contest_browser import SKRIP_TIMER
from contest_format import tanggal_wib
from contest_style import GAYA_AWAL_RIWAYAT, GAYA_LOMBA

if TYPE_CHECKING:  # hanya tipe RingkasSesi (tanpa kunci); modul hasil tidak diimpor saat dijalankan
    from contest_results import RingkasSesi

DASAR = "/murid/lomba"
ALAMAT_AWAL = DASAR
ALAMAT_MULAI = DASAR + "/mulai"
BATAS_MERAH_DETIK = 180
BATAS_LATIHAN_TERAKHIR = 5
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
    return dokumen(f"Soal {soal.nomor}", isi, _skrip_timer())


def _latihan_terakhir(riwayat: Sequence["RingkasSesi"]) -> str:
    """Daftar sesi selesai terbaru (maks BATAS_LATIHAN_TERAKHIR, terbaru dulu); kosong -> tidak tampil."""
    if not riwayat:
        return ""
    butir = "".join(
        f'<li><a class="tautan-latihan" href="{alamat_hasil(sesi.sesi_id)}">'
        f'<span>{html.escape(tanggal_wib(sesi.mulai_epoch))}</span>'
        f'<strong>{int(sesi.nilai)}/{int(sesi.jumlah_soal)}</strong></a></li>'
        for sesi in riwayat[:BATAS_LATIHAN_TERAKHIR])
    return (f'<section class="latihan-terakhir" aria-labelledby="judul-terakhir"><h2 id="judul-terakhir">'
            f'Latihan terakhir</h2><ul>{butir}</ul></section>')


def halaman_awal(sesi: Optional[K.SesiRingkas], sisa: int = 0, riwayat: Sequence["RingkasSesi"] = ()) -> bytes:
    """Penjelasan singkat + Mulai, atau Lanjutkan bila ada sesi berjalan; `riwayat` = sesi selesai, terbaru dulu."""
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
</section>{_latihan_terakhir(riwayat)}</main>"""
    return dokumen("Latihan Lomba", isi, gaya_tambahan=GAYA_AWAL_RIWAYAT if riwayat else "")


_IKON_LOMBA = ('<svg class="murid-ikon-st" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
               'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
               '<path d="M8 21h8m-4-4v4M7 4h10v5a5 5 0 0 1-10 0V4Zm0 2H4v1a3 3 0 0 0 3 3m10-4h3v1a3 3 0 0 1-3 3"/></svg>')


def tautan_beranda_murid() -> str:
    """Kartu tautan besar "Latihan Lomba" di beranda murid (hanya dipanggil bila gerbang hidup)."""
    return (
        '<section class="murid-latihan-lain-st" aria-labelledby="judul-lomba">'
        '<div class="murid-kepala-bagian-st"><h2 id="judul-lomba">Latihan Lomba</h2></div>'
        f'<a class="st-kartu-baris" href="{ALAMAT_AWAL}">'
        f'<span class="murid-ikon-topik-st">{_IKON_LOMBA}</span>'
        '<span class="st-kartu-teks"><span class="murid-judul-kartu-st">Latihan Lomba</span>'
        f'<span class="murid-meta-st">{JUMLAH_SOAL} soal, {K.DURASI_DETIK // _DETIK_PER_MENIT} menit</span></span>'
        '<span class="murid-ujung-st st-jumlah-soal"><span class="murid-aksi-st">Coba</span></span></a></section>')


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
    return dokumen("Kumpulkan", isi, _skrip_timer())


def halaman_gagal_siapkan() -> bytes:
    """Ramah anak saat soal gagal dirakit; tanpa detail teknis."""
    isi = f"""<main class="isi"><section class="kartu">
<h1 class="judul">Soal belum bisa disiapkan</h1><p>Coba lagi nanti, ya.</p>
<a class="tombol besar" href="{ALAMAT_AWAL}">Kembali</a>
</section></main>"""
    return dokumen("Soal belum siap", isi)
