"""Halaman hasil rinci Latihan Lomba untuk anak, dan potongan HTML bersama dengan halaman guru.

Berbeda dari `contest_pages` (halaman SOAL yang tidak boleh memuat kunci), modul ini MENAMPILKAN jawaban
anak, jawaban benar, dan pembahasan, jadi hanya menerima `contest_results.HasilRinci` yang sudah disaring
`hasil_rinci` (menolak sesi berjalan). Label `kesalahan` pengecoh hanya tampil bila `untuk_guru=True`;
`halaman_hasil_anak` tidak pernah menyalakannya. Semua teks dari DB di-escape; hanya `svg` dan
`gambar_pilihan` (divalidasi generator soal) disisipkan sebagai markup, masing-masing sekali.
Tanpa skrip.
"""
from __future__ import annotations

import html
from typing import Sequence

import contest_chart_svg as G
import contest_core as C
import contest_komponen as KP
import contest_pages as P
import contest_paket as PK
import contest_results as R
import contest_store as K
from contest_format import durasi_menit_detik, persen
from contest_style import GAYA_HASIL, GAYA_HASIL_ANAK

BATAS_SEMANGAT_TINGGI = 80
BATAS_SEMANGAT_SEDANG = 50
_PESAN_TINGGI = "Hebat! Terus pertahankan, ya."
_PESAN_SEDANG = "Bagus! Baca pembahasan di bawah untuk soal yang belum pas."
_PESAN_RENDAH = "Tidak apa-apa. Setiap soal adalah kesempatan belajar; baca pembahasannya pelan-pelan, ya."
_STATUS_BENAR = ("hl-benar", "\u2713", "benar")
_STATUS_SALAH = ("hl-salah", "\u2717", "salah")
_STATUS_KOSONG = ("hl-kosong-jawab", "\u2013", "tidak dijawab")


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def label_topik(topik: str) -> str:
    return C.LABEL_TOPIK.get(topik, topik)


def pesan_semangat(nilai: int, jumlah: int) -> str:
    """Kalimat netral dan menyemangati menurut persen benar; tanpa label peringkat."""
    persen_benar = persen(nilai, jumlah)
    if persen_benar >= BATAS_SEMANGAT_TINGGI:
        return _PESAN_TINGGI
    return _PESAN_SEDANG if persen_benar >= BATAS_SEMANGAT_SEDANG else _PESAN_RENDAH


def daftar_topik(per_topik: Sequence[R.NilaiTopik], tampil_persen: bool = False) -> str:
    """Bar nilai per topik: nama, angka benar/total (opsional + persen), dan bar SVG."""
    if not per_topik:
        return ""
    baris = []
    for nilai in per_topik:
        nama = label_topik(nilai.topik)
        angka = f"{nilai.benar}/{nilai.total}" + (f" ({persen(nilai.benar, nilai.total)}%)" if tampil_persen else "")
        bar = G.bar_persen(nilai.benar, nilai.total, f"{nama}: {nilai.benar} dari {nilai.total} benar")
        baris.append(f'<li class="hl-topik-baris"><span class="hl-topik-nama">{_e(nama)}</span>'
                     f'{bar}<span class="hl-topik-angka">{angka}</span></li>')
    return f'<ul class="hl-topik-daftar">{"".join(baris)}</ul>'


def _status(butir: R.ButirRinci) -> tuple:
    if butir.jawaban is None:
        return _STATUS_KOSONG
    return _STATUS_BENAR if butir.benar else _STATUS_SALAH


def _gambar_pilihan(butir: R.ButirRinci) -> Sequence[str]:
    return butir.gambar_pilihan or ("",) * len(butir.pilihan)


def _teks_huruf(butir: R.ButirRinci, huruf: str) -> str:
    """`B. 5` untuk pilihan bergambar hanya `B` (gambarnya tampil di daftar pilihan)."""
    if any(_gambar_pilihan(butir)):
        return _e(huruf)
    return f"{_e(huruf)}. {_e(butir.pilihan[C.HURUF.index(huruf)])}"


def _jawaban_anak(butir: R.ButirRinci) -> str:
    if butir.jawaban is None:
        return "belum diisi"
    return _teks_huruf(butir, butir.jawaban) if butir.jenis == C.JENIS_PG else _e(butir.jawaban)


def _jawaban_benar(butir: R.ButirRinci) -> str:
    return _teks_huruf(butir, butir.kunci_huruf) if butir.jenis == C.JENIS_PG else _e(butir.kunci)


def _blok_pilihan(butir: R.ButirRinci, sebutan_pilihan: str) -> str:
    gambar = _gambar_pilihan(butir)
    item = []
    for i, (huruf, teks) in enumerate(zip(C.HURUF, butir.pilihan)):
        dipilih, kunci = butir.jawaban == huruf, butir.kunci_huruf == huruf
        kelas = "hl-pilih" + (" hl-dipilih" if dipilih else "") + (" hl-kunci" if kunci else "")
        tanda = " \u00b7 ".join(t for t, nyala in ((sebutan_pilihan, dipilih), ("Jawaban benar", kunci)) if nyala)
        item.append(f'<li class="{kelas}"><span class="hl-huruf">{huruf}</span>'
                    f'<span class="hl-isi">{gambar[i] if gambar[i] else _e(teks)}</span>'
                    f'<span class="hl-tanda">{tanda}</span></li>')
    return f'<ul class="hl-pilihan" aria-label="Pilihan jawaban">{"".join(item)}</ul>'


def _blok_pembahasan(butir: R.ButirRinci) -> str:
    if not butir.pembahasan:
        return ""
    langkah = "".join(f"<li>{_e(baris)}</li>" for baris in butir.pembahasan)
    return f'<h4 class="hl-bahas-judul">Pembahasan</h4><ol class="hl-bahas">{langkah}</ol>'


def kartu_soal(butir: R.ButirRinci, *, untuk_guru: bool = False) -> str:
    """Satu kartu soal: jawaban, kunci, pembahasan; label `kesalahan` hanya bila `untuk_guru`."""
    kelas_status, tanda, teks_status = _status(butir)
    sebutan = "Jawaban anak" if untuk_guru else "Jawabanmu"
    gambar = f'<div class="hl-gambar">{butir.svg}</div>' if butir.svg else ""
    pilihan = _blok_pilihan(butir, "Pilihan anak" if untuk_guru else "Pilihanmu") if butir.jenis == C.JENIS_PG else ""
    baris = f'<p>{sebutan}: <strong>{_jawaban_anak(butir)}</strong></p>'
    if not butir.benar:
        baris += f'<p>Jawaban yang benar: <strong>{_jawaban_benar(butir)}</strong></p>'
    kesalahan = ""
    if untuk_guru and butir.kesalahan:
        kesalahan = f'<p class="hl-kesalahan">Kemungkinan kesalahan: {_e(butir.kesalahan)}</p>'
    return (
        f'<article class="hl-soal" aria-labelledby="soal-{butir.nomor}">'
        f'<h3 class="hl-judul" id="soal-{butir.nomor}"><span class="hl-nomor"><span class="hl-sr">Soal </span>'
        f'{butir.nomor}</span><span class="hl-topik">{_e(label_topik(butir.topik))}</span>'
        f'<span class="hl-status {kelas_status}"><span aria-hidden="true">{tanda}</span> {teks_status}</span></h3>'
        f'<p class="hl-teks">{_e(butir.teks)}</p>{gambar}{pilihan}'
        f'<div class="hl-jawaban">{baris}</div>{kesalahan}{_blok_pembahasan(butir)}</article>')


_STATUS_PETA = {
    "benar": ("hl-benar", "\u2713", "benar"),
    "salah": ("hl-salah", "\u2717", "salah"),
    "kosong": ("hl-kosong-jawab", "\u2013", "belum diisi"),
}


def _jenis_hasil(butir: R.ButirRinci) -> str:
    if butir.jawaban is None:
        return "kosong"
    return "benar" if butir.benar else "salah"


def _pose_maskot(nilai: int, jumlah: int) -> str:
    persen_benar = persen(nilai, jumlah)
    if persen_benar >= BATAS_SEMANGAT_TINGGI:
        return "merayakan"
    return "menyapa" if persen_benar >= BATAS_SEMANGAT_SEDANG else "berpikir"


def _peta_nomor(butir: Sequence[R.ButirRinci]) -> str:
    """Semua nomor (10 atau 35) ber-tautan ke kartu soalnya: benar hijau, salah merah, kosong putus-putus (teks sr-saja)."""
    sel = []
    for item in butir:
        kelas, tanda, kata = _STATUS_PETA[_jenis_hasil(item)]
        sel.append(f'<li><a class="peta-nomor {kelas}" href="#soal-{item.nomor}"><span>{item.nomor}</span>'
                   f'<span aria-hidden="true">{tanda}</span><span class="sr-saja"> {kata}</span></a></li>')
    return f'<nav aria-label="Peta soal"><ol class="peta">{"".join(sel)}</ol></nav>'


def _daftar_kartu(butir: Sequence[R.ButirRinci]) -> str:
    return f'<div class="hl-daftar-soal">{"".join(kartu_soal(item) for item in butir)}</div>'


def _soal_lipat(butir: R.ButirRinci) -> str:
    kata = _STATUS_PETA[_jenis_hasil(butir)][2]
    ringkas = f"Soal {butir.nomor} \u00b7 {_e(label_topik(butir.topik))} \u00b7 {kata}"
    return f'<details class="hl-lipat" open><summary>{ringkas}</summary>{_daftar_kartu([butir])}</details>'


def _kelompok_soal(butir: Sequence[R.ButirRinci]) -> str:
    """Salah/kosong terbuka satu per satu; yang benar dilipat jadi satu (terbuka bila semuanya benar)."""
    perlu = [item for item in butir if _jenis_hasil(item) != "benar"]
    benar = [item for item in butir if _jenis_hasil(item) == "benar"]
    bagian = ""
    if perlu:
        bagian += (f'<section class="hl-kelompok" aria-labelledby="judul-perlu"><h2 id="judul-perlu">'
                   f'Yang perlu dilihat lagi ({len(perlu)})</h2>{"".join(_soal_lipat(item) for item in perlu)}</section>')
    if benar:
        terbuka = "" if perlu else " open"
        bagian += (f'<details class="hl-lipat"{terbuka}><summary>Soal yang benar ({len(benar)})</summary>'
                   f'{_daftar_kartu(benar)}</details>')
    return bagian


def halaman_hasil_anak(hasil: R.HasilRinci, banding: str = "") -> bytes:
    """Hasil setelah sesi selesai: ringkasan, peta nomor, bar topik, soal yang perlu dilihat lagi, lalu yang benar.

    `banding` = kalimat pembanding dengan latihan sebelumnya (kosong bila tidak ada pembanding yang sah).
    """
    judul = "Waktu habis!" if hasil.sesi.status == K.WAKTU_HABIS else "Sesi selesai!"
    kalimat = f'<p class="hl-banding">{_e(banding)}</p>' if banding else ""
    mode = hasil.sesi.mode if hasil.sesi.mode in PK.MODE_SAH else PK.MODE_LATIHAN
    label_ulang = "Simulasi lagi" if mode == PK.MODE_SIMULASI else "Latihan lagi"
    isi = f"""{KP.bilah_beranda()}
<main class="isi hasil-lomba"><section class="hl-kartu hl-ringkas-anak">
{KP.maskot_kartu(_pose_maskot(hasil.nilai, hasil.jumlah_soal))}
<p class="hl-mode">{PK.LABEL_MODE[mode]}</p>
<h1 class="judul">{judul}</h1>
<p class="angka-besar"><span class="sr-saja">Nilai: </span>{int(hasil.nilai)}/{int(hasil.jumlah_soal)}</p>
<p>Waktu: {durasi_menit_detik(hasil.waktu_terpakai_detik)}</p>{kalimat}
<p class="hl-semangat">{pesan_semangat(hasil.nilai, hasil.jumlah_soal)}</p>
</section>
<section aria-labelledby="judul-peta"><h2 id="judul-peta" class="sr-saja">Peta soal</h2>{_peta_nomor(hasil.butir)}</section>
<section class="hl-kartu"><h2>Nilai tiap topik</h2>{daftar_topik(hasil.per_topik)}</section>
{_kelompok_soal(hasil.butir)}
<div class="aksi"><form method="post" action="{P.ALAMAT_MULAI}"><input type="hidden" name="mode" value="{mode}">
<button type="submit" class="tombol">{label_ulang}</button></form>
<a class="tombol sekunder" href="{KP.ALAMAT_BERANDA}">Beranda</a></div></main>"""
    return P.dokumen("Hasil latihan", isi, gaya_tambahan=GAYA_HASIL + GAYA_HASIL_ANAK)
