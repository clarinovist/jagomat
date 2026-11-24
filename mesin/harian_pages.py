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
import harian_langganan_dasar as paket_dasar
import harian_style
import harian_tingkat as ht
import murid_shell as MS
import pecahan
import playful_components as C
import visual_renderer
from pesanan_transfer_pages import rupiah
from playful_style import GAYA_CERIA
from style_stitch import gaya_stitch

DASAR = "/murid/latihan-harian"
ALAMAT_AWAL = DASAR
ALAMAT_MULAI = DASAR + "/mulai"
ALAMAT_ORANG_TUA = "/murid/orang-tua"  # halaman orang tua (di balik PIN tirai) memuat kartu langganan F5
COPY_JUDUL = "Latihan Harian"
COPY_HABIS = "Jatah latihan gratis hari ini sudah dipakai"
COPY_HABIS_JUDUL = "Hebat, latihan hari ini selesai!"
COPY_HABIS_BESOK = "Besok kamu bisa latihan lagi."
COPY_TOMBOL_ORTU = "Untuk Ayah/Bunda · lihat paket"
COPY_POIN_ORTU = ("Sesi sebanyak yang anak mau", "1 sesi gratis tetap ada tiap hari")
COPY_PILIH_NETRAL = "Pilih kelasmu ya."
COPY_CATATAN_KELAS = "Boleh pilih kelas lain untuk mengulang atau menantang diri."
COPY_PENGAYAAN = "Pengayaan"
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
{MS.kepala_murid(gaya_stitch() + harian_style.GAYA_HARIAN + GAYA_CERIA, cetak=False)}</head>
<body class="st"><div class="murid-wadah-st">{topbar}
<main id="utama" class="murid-kanvas-st hr-isi">{isi}</main></div></body></html>""".encode("utf-8")


def _judul_tingkat(kode: str) -> str:
    try:
        return ht.ambil_tingkat(kode).judul
    except KeyError:
        return ""


# --- beranda tingkat ---------------------------------------------------------------------------

def _kartu_tingkat(tingkat: ht.Tingkat, saran: Optional[str], terakhir: Optional[str]) -> str:
    """Satu kartu = satu form kecil (POST + `tingkat`). Saran = stiker "Saran"; ringkas hanya untuk pembaca layar."""
    osn = tingkat.kelas is None
    kelas = "hr-tingkat osn" if osn else "hr-tingkat" + (" saran" if tingkat.kode == saran else "")
    ringkas = _e(tingkat.ringkas)
    if osn:
        isi = (f'<span><b>{_e(tingkat.judul)}</b><small>{ringkas}</small></span>'
               f'{C.stiker(COPY_PENGAYAAN, "kanan")}')
    else:
        tanda = ""
        if tingkat.kode == saran:
            tanda = '<span class="hr-saran">Saran</span>'
        elif tingkat.kode == terakhir:
            tanda = '<span class="hr-terakhir">Terakhir</span>'
        isi = f'<b>{_e(tingkat.judul)}</b><span class="hr-sr">{ringkas}</span>{tanda}'
    return (f'<li><form method="post" action="{ALAMAT_MULAI}">'
            f'<input type="hidden" name="tingkat" value="{_e(tingkat.kode)}">'
            f'<button type="submit" class="{kelas}">{isi}</button></form></li>')


def _daftar_tingkat(saran: Optional[str], terakhir: Optional[str]) -> str:
    kelas = [t for t in ht.DAFTAR_TINGKAT if t.kelas is not None]
    osn = [t for t in ht.DAFTAR_TINGKAT if t.kelas is None]

    def blok(judul, daftar, tambahan=""):
        isi = "".join(_kartu_tingkat(t, saran, terakhir) for t in daftar)
        return (f'<section aria-label="{_e(judul)}"><h2>{_e(judul)}</h2>'
                f'<ul class="hr-daftar{tambahan}">{isi}</ul></section>')

    return (blok("Pilih kelas", kelas) + f'<p class="hr-catatan-kelas">{_e(COPY_CATATAN_KELAS)}</p>'
            + blok("Tantangan OSN", osn, " osn"))


def _sapaan_pilih(saran: Optional[str]) -> str:
    """Satu maskot di layar pilih kelas: menyebut kelas saran bila ada dan dikenal, kalau tidak kalimat netral."""
    judul = _judul_tingkat(saran) if saran else ""
    if judul:
        return C.maskot_bicara("menunjuk", "Mulai dari ", judul, " ya, sesuai kelasmu.")
    return C.maskot_bicara("menunjuk", COPY_PILIH_NETRAL)


def _kartu_berjalan(sesi: hs.SesiRingkas) -> str:
    return (f'<section class="hr-kartu" aria-labelledby="judul-berjalan"><h2 id="judul-berjalan">Latihanmu masih berjalan</h2>'
            f'<p>{_e(_judul_tingkat(sesi.tingkat))} · {sesi.terjawab} dari {sesi.jumlah_soal} soal sudah kamu jawab</p>'
            f'<a class="hr-tombol" href="{alamat_sesi(sesi.id, sesi.nomor_berikut)}">Lanjutkan</a></section>')


def teks_harga_ortu() -> str:
    """"mulai Rp39.000/bulan", dihitung dari konstanta paket Bulanan (bukan ditulis tangan)."""
    paket = paket_dasar.PAKET[paket_dasar.PAKET_BULANAN]
    return "mulai %s/bulan" % rupiah(paket.rupiah // paket.bulan)


def kartu_ajakan_langganan() -> str:
    """Kartu navy "Untuk Ayah/Bunda": satu-satunya tautan ke halaman orang tua di layar yang memakainya."""
    return C.kartu_ajakan_ortu(ALAMAT_ORANG_TUA, COPY_TOMBOL_ORTU, teks_harga_ortu(), poin=COPY_POIN_ORTU, level=2)


def _kartu_habis(ada_ortu: bool) -> str:
    banner = C.banner_umpan_balik(True, COPY_HABIS_JUDUL, "%s. %s" % (COPY_HABIS, COPY_HABIS_BESOK), level=2)
    return banner + (kartu_ajakan_langganan() if ada_ortu else "")


def halaman_beranda(sesi_berjalan: Optional[hs.SesiRingkas], habis: bool, saran: Optional[str],
                    terakhir: Optional[str], ada_ortu: bool = True) -> bytes:
    """Beranda tingkat: lanjutkan sesi berjalan, atau jatah habis, atau pilih kelas (dengan saran).

    `ada_ortu` (halaman orang tua tersedia) hanya menentukan apakah kartu ajakan tampil di keadaan jatah habis;
    tampilan saja, bukan gerbang akses.
    """
    if sesi_berjalan is not None:
        badan = _kartu_berjalan(sesi_berjalan)
    elif habis:
        badan = _kartu_habis(ada_ortu)
    else:
        badan = _sapaan_pilih(saran) + _daftar_tingkat(saran, terakhir)
    isi = (f'<header><p class="hr-redup">LATIHAN HARIAN</p><h1>{COPY_JUDUL}</h1>'
           '<p class="hr-redup">10 soal pilihan ganda. Setelah menjawab, kamu langsung tahu benar atau salahnya.</p></header>'
           + badan)
    return dokumen(COPY_JUDUL, isi)


# --- soal ----------------------------------------------------------------------------------------

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
            kelas, tanda = "benar", "Jawaban benar" if i != umpan.pilihan else "Jawabanmu, benar"
        elif i == umpan.pilihan:
            kelas, tanda = "salah", "Jawabanmu"
        else:
            kelas, tanda = "diam", ""
        label = f'<span class="hr-tanda">{_e(tanda)}</span>' if tanda else ""
        butir.append(f'<div class="hr-pilih {kelas}"><span class="hr-huruf">{h}</span>'
                     f'<span class="hr-isi-pilihan">{pecahan.render(t)}</span>{label}</div>')
    return f'<div class="hr-pilihan" role="group" aria-label="Pilihan jawaban, sudah terkunci">{"".join(butir)}</div>'


def _banner_umpan(umpan: hs.UmpanBalik) -> str:
    """Satu-satunya maskot layar soal terjawab. Betul = hijau; belum tepat = hangat (bukan merah)."""
    if umpan.benar:
        huruf = hs.HURUF_PILIHAN[umpan.pilihan]
        return C.banner_umpan_balik(True, "Betul!", "Jawabanmu %s tepat. Hebat!" % huruf, level=2)
    return C.banner_umpan_balik(False, "Belum tepat, tidak apa-apa.", "Yuk lihat caranya.", level=2)


def _cara_dan_lanjut(umpan: hs.UmpanBalik, nomor: int, jumlah: int, sesi_id: int) -> str:
    cara = ('<section class="hr-cara" aria-labelledby="judul-cara"><h2 id="judul-cara" class="hr-cara-judul">Cara mengerjakannya</h2>'
            f'<div>{pecahan.render(umpan.pembahasan).replace(chr(10), "<br>")}</div></section>')
    if nomor < jumlah:
        lanjut = f'<a class="hr-tombol" href="{alamat_sesi(sesi_id, nomor + 1)}">Soal berikutnya</a>'
    else:
        lanjut = f'<a class="hr-tombol" href="{alamat_ringkasan(sesi_id)}">Lihat hasilku</a>'
    return cara + f'<div class="hr-aksi">{lanjut}</div>'


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
        bawah = (_banner_umpan(umpan) + _opsi_terkunci(soal.opsi, umpan)
                 + _cara_dan_lanjut(umpan, soal.nomor, soal.jumlah, sesi_id))
    info = " · ".join(x for x in (_judul_tingkat(tingkat_kode), "Soal %d dari %d" % (soal.nomor, soal.jumlah)) if x)
    sudah = min(max(terjawab, 0), soal.jumlah)
    isi = (f'<header><p class="hr-redup hr-info">{_e(info)}</p></header>'
           f'{C.progres_soal(sudah, soal.nomor, soal.jumlah)}'
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


def halaman_ringkasan(ringkas: hs.RingkasanSesi, tampil_ajakan_ortu: bool = False) -> bytes:
    """Hasil satu sesi: jumlah benar dari jumlah soal. Tanpa peringkat, tanpa perbandingan dengan anak lain.

    `tampil_ajakan_ortu` (dihitung pemanggil: halaman orang tua tersedia dan anak belum tanpa batas) hanya
    menampilkan kartu ajakan; tampilan saja, bukan gerbang akses.
    """
    hero = C.hero(
        C.maskot_bicara("merayakan", "Sesi hari ini ", "selesai", "! Kerja bagus.")
        + C.skor_besar(ringkas.benar, ringkas.jumlah_soal)
        + f'<p>{_e(_semangat(ringkas.benar, ringkas.jumlah_soal))}</p>'
        + C.stiker("Selesai hari ini"), konfeti=True)
    isi = (f'<h1 class="hr-sr">Latihan selesai</h1><p class="hr-redup">{_e(_judul_tingkat(ringkas.tingkat))}</p>{hero}'
           f'<div class="hr-aksi"><a class="hr-tombol" href="{ALAMAT_AWAL}">Latihan lagi</a>'
           '<a class="hr-tombol sekunder" href="/murid">Kembali ke ruang belajar</a></div>'
           + (kartu_ajakan_langganan() if tampil_ajakan_ortu else ""))
    return dokumen("Latihan selesai", isi)


def halaman_gagal_siapkan() -> bytes:
    isi = (f'<section class="hr-kartu"><h1>{COPY_TIDAK_BISA_SIAP}</h1><p>Coba lagi nanti, ya.</p>'
           f'<a class="hr-tombol" href="{ALAMAT_AWAL}">Kembali</a></section>')
    return dokumen(COPY_TIDAK_BISA_SIAP, isi)


# --- kartu beranda murid dan blok halaman orang tua --------------------------------------------

def _indeks_hari(pekan: Sequence[tuple]) -> set:
    """Indeks hari (0 = Senin) pada `pekan` yang ada latihan, untuk `titik_hari`."""
    return {datetime.date.fromisoformat(tanggal).weekday() for tanggal, ada in pekan if ada}


def kartu_beranda(sesi_berjalan: Optional[hs.SesiRingkas], terakhir: Optional[str], habis: bool,
                  pekan: Sequence[tuple]) -> str:
    """Kartu "Latihan Harian" di beranda murid: kelas terpilih, hari latihan pekan ini (titik), tombol Mulai/Lanjut.

    Tanpa tautan ke halaman orang tua (beranda murid punya tepat satu). CSS komponen ceria (titik hari) dimuat
    oleh halaman pemanggil lewat `playful_style.GAYA_CERIA`.
    """
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
            f'<div class="st-kartu hr-kartu-beranda"><p class="hr-kelas">{_e(nama)}</p><p>{_e(teks)}</p>'
            f'{C.titik_hari(_indeks_hari(pekan), latar="krem")}'
            f'<a class="hr-tombol" href="{tombol[1]}">{_e(tombol[0])}</a></div></section>')


def blok_orang_tua(ringkas: hs.RingkasanHarian) -> str:
    """Kartu ringkasan halaman orang tua: kelas terakhir, hari latihan 7 hari terakhir, soal dikerjakan, persen benar.

    CSS komponen ceria (titik hari) dimuat oleh halaman pemanggil lewat `playful_style.GAYA_CERIA`.
    """
    if ringkas.tingkat_terakhir is None and ringkas.soal_dikerjakan == 0:
        isi = "<p>Belum ada Latihan Harian.</p>"
    else:
        persen = "-" if ringkas.persen_benar is None else "%d%%" % ringkas.persen_benar
        isi = (f'<p>Terakhir berlatih: <b>{_e(_judul_tingkat(ringkas.tingkat_terakhir or ""))}</b></p>'
               f'{C.titik_hari(_indeks_hari(ringkas.hari), latar="krem")}'
               f'<p>Hari latihan dalam 7 hari terakhir: <b>{ringkas.jumlah_hari}</b> dari 7</p>'
               f'<p>Soal dikerjakan: <b>{ringkas.soal_dikerjakan}</b> · Persen tepat: <b>{persen}</b></p>')
    return f'<section class="ortu-kartu-st" id="ortu-harian"><h2>{COPY_JUDUL}</h2>{isi}</section>'
