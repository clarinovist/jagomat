"""Halaman HTML Latihan Harian untuk anak, kartu beranda murid, dan blok ringkasan halaman orang tua (murni render).

Menerima data AMAN dari `harian_latihan_store`. `SoalAnak` tidak memuat kunci atau pembahasan; `UmpanBalik` (kunci,
pembahasan, benar/salah) hanya diberikan setelah soal itu terjawab, jadi halaman soal yang belum dijawab TIDAK PERNAH
berisi kunci atau pembahasan. Semua teks dari DB di-escape (`pecahan.render` meng-escape sendiri); hanya markup visual
dari `visual_renderer` yang disisipkan apa adanya. Tanpa JS: pilihan = radio native, kirim = tombol form.
Tanpa peringkat atau perbandingan antar anak.
"""
from __future__ import annotations

import datetime
import html
from typing import Optional, Sequence

import brand
import harian_latihan_store as hs
import harian_style
import harian_tingkat as ht
import murid_shell as MS
import pecahan
import visual_renderer
from style_stitch import gaya_stitch

DASAR = "/murid/latihan-harian"
ALAMAT_AWAL = DASAR
ALAMAT_MULAI = DASAR + "/mulai"
ALAMAT_ORANG_TUA = "/murid/orang-tua"  # halaman orang tua (di balik PIN tirai) memuat kartu langganan F5
NAMA_HARI = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
COPY_JUDUL = "Latihan Harian"
COPY_HABIS = "Jatah latihan gratis hari ini sudah dipakai"
COPY_HABIS_ISI = ("Besok kamu bisa latihan lagi. Ayah atau Bunda juga bisa berlangganan supaya kamu bisa "
                  "berlatih sebanyak yang kamu mau.")
COPY_TIDAK_BISA_SIAP = "Soal belum bisa disiapkan"


def _e(teks) -> str:
    return html.escape(str(teks), quote=True)


def alamat_sesi(sesi_id: int, nomor: Optional[int] = None) -> str:
    dasar = "%s/sesi/%d" % (DASAR, int(sesi_id))
    return dasar if nomor is None else "%s?no=%d" % (dasar, int(nomor))


def alamat_jawab(sesi_id: int) -> str:
    return "%s/sesi/%d/jawab" % (DASAR, int(sesi_id))


def alamat_ringkasan(sesi_id: int) -> str:
    return "%s/sesi/%d/ringkasan" % (DASAR, int(sesi_id))


def dokumen(judul: str, isi: str, kanan: str = "") -> bytes:
    """Dokumen lengkap bergaya murid; slot kanan topbar = tautan kembali."""
    topbar = MS.topbar_murid(kanan or MS.aksi_topbar("/murid", "Beranda", MS.PANAH_KEMBALI))
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{_e(brand.judul(judul))}</title>{brand.tag_kepala()}
{MS.kepala_murid(gaya_stitch() + harian_style.GAYA_HARIAN, cetak=False)}</head>
<body class="st"><div class="murid-wadah-st">{topbar}
<main id="utama" class="murid-kanvas-st hr-isi">{isi}</main></div></body></html>""".encode("utf-8")


def _judul_tingkat(kode: str) -> str:
    try:
        return ht.ambil_tingkat(kode).judul
    except KeyError:
        return ""


# --- beranda tingkat ---------------------------------------------------------------------------

def _kartu_tingkat(tingkat: ht.Tingkat, saran: Optional[str], terakhir: Optional[str]) -> str:
    lencana = ""
    if tingkat.kode == saran:
        lencana = '<span class="hr-lencana">Disarankan untukmu</span>'
    elif tingkat.kode == terakhir:
        lencana = '<span class="hr-lencana">Terakhir kamu pilih</span>'
    return (f'<li><form method="post" action="{ALAMAT_MULAI}">'
            f'<input type="hidden" name="tingkat" value="{_e(tingkat.kode)}">'
            f'<button type="submit" class="hr-tingkat"><b>{_e(tingkat.judul)}</b>'
            f'<span>{_e(tingkat.ringkas)}</span>{lencana}</button></form></li>')


def _daftar_tingkat(saran: Optional[str], terakhir: Optional[str]) -> str:
    kelas = [t for t in ht.DAFTAR_TINGKAT if t.kelas is not None]
    osn = [t for t in ht.DAFTAR_TINGKAT if t.kelas is None]

    def blok(judul, daftar):
        isi = "".join(_kartu_tingkat(t, saran, terakhir) for t in daftar)
        return f'<section aria-label="{_e(judul)}"><h2>{_e(judul)}</h2><ul class="hr-daftar">{isi}</ul></section>'

    return blok("Pilih kelas", kelas) + blok("Tantangan OSN", osn)


def _kartu_berjalan(sesi: hs.SesiRingkas) -> str:
    return (f'<section class="hr-kartu" aria-labelledby="judul-berjalan"><h2 id="judul-berjalan">Latihanmu masih berjalan</h2>'
            f'<p>{_e(_judul_tingkat(sesi.tingkat))} · {sesi.terjawab} dari {sesi.jumlah_soal} soal sudah kamu jawab</p>'
            f'<a class="hr-tombol" href="{alamat_sesi(sesi.id, sesi.nomor_berikut)}">Lanjutkan</a></section>')


def _kartu_habis() -> str:
    return (f'<section class="hr-kartu catatan" role="status" aria-labelledby="judul-habis"><h2 id="judul-habis">{_e(COPY_HABIS)}</h2>'
            f'<p>{_e(COPY_HABIS_ISI)}</p>'
            f'<a class="hr-tombol sekunder" href="{ALAMAT_ORANG_TUA}">Untuk Ayah/Bunda</a></section>')


def halaman_beranda(sesi_berjalan: Optional[hs.SesiRingkas], habis: bool, saran: Optional[str],
                    terakhir: Optional[str]) -> bytes:
    """Beranda tingkat: lanjutkan sesi berjalan, atau jatah habis, atau pilih tingkat (dengan saran)."""
    if sesi_berjalan is not None:
        badan = _kartu_berjalan(sesi_berjalan)
    elif habis:
        badan = _kartu_habis()
    else:
        badan = _daftar_tingkat(saran, terakhir)
    isi = (f'<header><p class="hr-redup">LATIHAN HARIAN</p><h1>{COPY_JUDUL}</h1>'
           '<p class="hr-redup">10 soal pilihan ganda. Setelah menjawab, kamu langsung tahu benar atau salahnya.</p></header>'
           + badan)
    return dokumen(COPY_JUDUL, isi)


# --- soal ----------------------------------------------------------------------------------------

def _progres(nomor: int, terjawab_sampai: int, jumlah: int) -> str:
    butir = []
    for n in range(1, jumlah + 1):
        kelas = ("sudah " if n <= terjawab_sampai else "") + ("aktif" if n == nomor else "")
        status = "sudah dijawab" if n <= terjawab_sampai else ("soal ini" if n == nomor else "belum")
        saat = ' aria-current="step"' if n == nomor else ""
        butir.append(f'<li class="{kelas.strip()}"{saat}>{n}<span class="hr-sr"> {status}</span></li>')
    return f'<nav aria-label="Nomor soal"><ol class="hr-progres">{"".join(butir)}</ol></nav>'


def _opsi_belum_dijawab(opsi: Sequence[str]) -> str:
    """Empat label seragam: hanya huruf dan teks yang berbeda; tanpa atribut yang menandai posisi atau kebenaran."""
    isi = "".join(
        f'<label class="hr-pilih"><input type="radio" name="pilihan" value="{h}" required>'
        f'<span class="hr-huruf">{h}</span><span class="hr-isi-pilihan">{pecahan.render(t)}</span></label>'
        for h, t in zip(hs.HURUF_PILIHAN, opsi))
    return f'<fieldset class="hr-pilihan"><legend>Pilih satu jawaban</legend>{isi}</fieldset>'


def _opsi_terkunci(opsi: Sequence[str], umpan: hs.UmpanBalik) -> str:
    butir = []
    for i, (h, t) in enumerate(zip(hs.HURUF_PILIHAN, opsi)):
        if i == umpan.kunci_indeks:
            kelas, tanda = "benar", "Jawaban yang benar" if i != umpan.pilihan else "Jawabanmu, benar"
        elif i == umpan.pilihan:
            kelas, tanda = "salah", "Jawabanmu"
        else:
            kelas, tanda = "diam", ""
        label = f'<span class="hr-tanda">{_e(tanda)}</span>' if tanda else ""
        butir.append(f'<div class="hr-pilih {kelas}"><span class="hr-huruf">{h}</span>'
                     f'<span class="hr-isi-pilihan">{pecahan.render(t)}</span>{label}</div>')
    return f'<div class="hr-pilihan" role="group" aria-label="Pilihan jawaban, sudah terkunci">{"".join(butir)}</div>'


def _umpan(umpan: hs.UmpanBalik, nomor: int, jumlah: int, sesi_id: int) -> str:
    if umpan.benar:
        kepala = '<div class="hr-umpan benar" role="status"><h2>Benar! Hebat.</h2></div>'
    else:
        kepala = ('<div class="hr-umpan salah" role="status"><h2>Belum tepat, tidak apa-apa.</h2>'
                  '<p>Lihat caranya di bawah, ya.</p></div>')
    cara = ('<div class="hr-cara"><b>Caranya</b>'
            f'{pecahan.render(umpan.pembahasan).replace(chr(10), "<br>")}</div>')
    if nomor < jumlah:
        lanjut = f'<a class="hr-tombol" href="{alamat_sesi(sesi_id, nomor + 1)}">Soal berikutnya</a>'
    else:
        lanjut = f'<a class="hr-tombol" href="{alamat_ringkasan(sesi_id)}">Lihat hasilku</a>'
    return kepala + cara + f'<div class="hr-aksi">{lanjut}</div>'


def halaman_soal(sesi_id: int, tingkat_kode: str, soal: hs.SoalAnak, umpan: Optional[hs.UmpanBalik],
                 terjawab: int) -> bytes:
    """Satu soal. Tanpa `umpan`: form pilih-lalu-periksa tanpa kunci/pembahasan. Dengan `umpan`: terkunci + pembahasan."""
    penyajian = visual_renderer.render_pertanyaan(soal.penyajian, gaya="stitch", namespace="h%d" % soal.nomor)
    if umpan is None:
        bawah = (f'<form method="post" action="{alamat_jawab(sesi_id)}">'
                 f'<input type="hidden" name="no" value="{soal.nomor}">'
                 f'{_opsi_belum_dijawab(soal.opsi)}'
                 '<div class="hr-aksi"><button type="submit" class="hr-tombol">Periksa jawabanku</button></div></form>')
    else:
        bawah = _opsi_terkunci(soal.opsi, umpan) + _umpan(umpan, soal.nomor, soal.jumlah, sesi_id)
    isi = (f'<header><p class="hr-redup">{_e(_judul_tingkat(tingkat_kode))} · Soal {soal.nomor} dari {soal.jumlah}</p></header>'
           f'{_progres(soal.nomor, terjawab, soal.jumlah)}'
           f'<section class="hr-kartu"><h1 class="hr-sr">Soal {soal.nomor}</h1><div class="hr-soal">{penyajian}</div></section>'
           f'{bawah}')
    return dokumen("Soal %d" % soal.nomor, isi, MS.aksi_topbar(ALAMAT_AWAL, "Tutup"))


# --- ringkasan -----------------------------------------------------------------------------------

def _semangat(benar: int, jumlah: int) -> str:
    if benar == jumlah:
        return "Sempurna! Semua jawabanmu benar."
    if benar * 10 >= jumlah * 7:
        return "Bagus sekali! Terus berlatih, ya."
    if benar * 10 >= jumlah * 4:
        return "Lumayan! Soal yang belum tepat bisa kamu coba lagi besok."
    return "Tidak apa-apa. Setiap latihan bikin kamu makin paham."


def halaman_ringkasan(ringkas: hs.RingkasanSesi) -> bytes:
    """Hasil satu sesi: jumlah benar dari jumlah soal. Tanpa peringkat, tanpa perbandingan dengan anak lain."""
    isi = (f'<section class="hr-kartu"><p class="hr-redup">{_e(_judul_tingkat(ringkas.tingkat))}</p>'
           f'<h1>Latihan selesai!</h1>'
           f'<p class="hr-angka">{ringkas.benar} dari {ringkas.jumlah_soal}</p>'
           f'<p>jawabanmu benar.</p><p>{_e(_semangat(ringkas.benar, ringkas.jumlah_soal))}</p>'
           f'<div class="hr-aksi"><a class="hr-tombol" href="{ALAMAT_AWAL}">Latihan lagi</a>'
           '<a class="hr-tombol sekunder" href="/murid">Kembali ke ruang belajar</a></div></section>')
    return dokumen("Latihan selesai", isi)


def halaman_gagal_siapkan() -> bytes:
    isi = (f'<section class="hr-kartu"><h1>{COPY_TIDAK_BISA_SIAP}</h1><p>Coba lagi nanti, ya.</p>'
           f'<a class="hr-tombol" href="{ALAMAT_AWAL}">Kembali</a></section>')
    return dokumen(COPY_TIDAK_BISA_SIAP, isi)


# --- kartu beranda murid dan blok halaman orang tua --------------------------------------------

def _hari_html(hari: Sequence[tuple]) -> str:
    butir = []
    for tanggal, ada in hari:
        nama = NAMA_HARI[datetime.date.fromisoformat(tanggal).weekday()]
        butir.append(f'<li class="{"ada" if ada else "kosong"}"><span class="hr-titik" aria-hidden="true"></span>'
                     f'<span aria-hidden="true">{nama}</span><span class="hr-sr">{nama}, '
                     f'{"ada latihan" if ada else "belum latihan"}</span></li>')
    return f'<ol class="hr-hari">{"".join(butir)}</ol>'


def kartu_beranda(sesi_berjalan: Optional[hs.SesiRingkas], terakhir: Optional[str], habis: bool,
                  pekan: Sequence[tuple]) -> str:
    """Kartu "Latihan Harian" di beranda murid: tingkat terpilih, hari latihan pekan ini (titik), tombol Mulai/Lanjut."""
    if sesi_berjalan is not None:
        tingkat, tombol, teks = sesi_berjalan.tingkat, ("Lanjutkan", alamat_sesi(sesi_berjalan.id, sesi_berjalan.nomor_berikut)), \
            "Latihanmu masih berjalan."
    else:
        tingkat = terakhir
        teks = "Jatah latihan gratis hari ini sudah dipakai." if habis else "10 soal pilihan ganda, langsung tahu benar atau salah."
        tombol = ("Lihat latihan", ALAMAT_AWAL) if habis else ("Mulai latihan", ALAMAT_AWAL)
    nama = _judul_tingkat(tingkat) if tingkat else "Pilih kelasmu"
    return (f'<style>{harian_style.GAYA_KARTU}</style>'
            '<section class="murid-latihan-lain-st" aria-labelledby="judul-harian" style="margin-block-end: 1rem">'
            f'<div class="murid-kepala-bagian-st"><h2 id="judul-harian">{COPY_JUDUL}</h2></div>'
            f'<div class="st-kartu"><p><b>{_e(nama)}</b></p><p>{_e(teks)}</p>{_hari_html(pekan)}'
            f'<a class="hr-tombol" href="{tombol[1]}">{_e(tombol[0])}</a></div></section>')


def blok_orang_tua(ringkas: hs.RingkasanHarian) -> str:
    """Kartu ringkasan halaman orang tua: tingkat, hari latihan 7 hari terakhir, soal dikerjakan, persen benar."""
    if ringkas.tingkat_terakhir is None and ringkas.soal_dikerjakan == 0:
        isi = "<p>Belum ada Latihan Harian.</p>"
    else:
        persen = "-" if ringkas.persen_benar is None else "%d%%" % ringkas.persen_benar
        isi = (f'<p>Terakhir berlatih: <b>{_e(_judul_tingkat(ringkas.tingkat_terakhir or ""))}</b></p>'
               f'{_hari_html(ringkas.hari)}'
               f'<p>Hari latihan dalam 7 hari terakhir: <b>{ringkas.jumlah_hari}</b> dari 7</p>'
               f'<p>Soal dikerjakan: <b>{ringkas.soal_dikerjakan}</b> · Persen tepat: <b>{persen}</b></p>')
    return (f'<style>{harian_style.GAYA_KARTU}</style>'
            f'<section class="ortu-kartu-st" id="ortu-harian"><h2>{COPY_JUDUL}</h2>{isi}</section>')
