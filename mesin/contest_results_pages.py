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
import contest_pages as P
import contest_results as R
import contest_store as K
from contest_format import durasi_menit_detik, persen
from contest_style import GAYA_HASIL

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


def halaman_hasil_anak(hasil: R.HasilRinci) -> bytes:
    """Hasil setelah sesi selesai: nilai, waktu, bar per topik, lalu sepuluh kartu soal dengan pembahasan."""
    judul = "Waktu habis!" if hasil.sesi.status == K.WAKTU_HABIS else "Sesi selesai!"
    kartu = "".join(kartu_soal(butir) for butir in hasil.butir)
    isi = f"""<main class="isi hasil-lomba"><section class="hl-kartu">
<h1 class="judul">{judul}</h1>
<p class="angka-besar">Nilai: {int(hasil.nilai)} dari {int(hasil.jumlah_soal)}</p>
<p>Waktu: {durasi_menit_detik(hasil.waktu_terpakai_detik)}</p>
<p class="hl-semangat">{pesan_semangat(hasil.nilai, hasil.jumlah_soal)}</p>
<h2>Nilai tiap topik</h2>{daftar_topik(hasil.per_topik)}
<form method="post" action="{P.ALAMAT_MULAI}"><button type="submit" class="tombol besar">Latihan lagi</button></form>
</section>
<section aria-labelledby="judul-soal-hasil"><h2 id="judul-soal-hasil">Lihat lagi soal-soalmu</h2><div class="hl-daftar-soal">{kartu}</div></section>
<a class="tombol sekunder" href="{P.ALAMAT_AWAL}">Kembali</a></main>"""
    return P.dokumen("Hasil latihan", isi, gaya_tambahan=GAYA_HASIL)
