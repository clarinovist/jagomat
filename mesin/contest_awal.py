"""Halaman awal Latihan Lomba untuk anak (``/murid/lomba``): aturan, Mulai/Lanjutkan, hitung mundur, target, riwayat.

Murni render dari `contest_anak.RingkasAnak` (tanpa DB, tanpa kunci jawaban). Tanpa skrip: sisa waktu sesi
berjalan hanya angka statis dari server.
"""
from __future__ import annotations

import html
from typing import TYPE_CHECKING

import contest_komponen as KP
import contest_pages as P
from contest_format import label_tanggal_relatif
from contest_style import GAYA_AWAL

if TYPE_CHECKING:
    from contest_anak import RingkasAnak

BATAS_LATIHAN_TERAKHIR = 5
CATATAN_WAKTU = "Waktu terus berjalan walaupun kamu keluar dari halaman ini. Jawabanmu tetap tersimpan."


def _chip_aturan(paket) -> str:
    chip = (f"{paket.jumlah_soal} soal", f"{paket.durasi_menit} menit",
            f"{paket.jumlah_pg} pilihan ganda + {paket.jumlah_isian} isian")
    return '<ul class="chip-aturan">' + "".join(f"<li>{html.escape(teks)}</li>" for teks in chip) + "</ul>"


def _aksi(ringkas: "RingkasAnak") -> str:
    if ringkas.berjalan is None:
        return (f'<form method="post" action="{P.ALAMAT_MULAI}">'
                '<button type="submit" class="tombol besar">Mulai</button></form>')
    sesi = ringkas.berjalan
    status = (f'<p class="catatan">Latihanmu masih berjalan. Sisa waktu: <strong>{P.mmss(ringkas.sisa_detik)}</strong>'
              f' &middot; {len(ringkas.terisi)} dari {ringkas.paket.jumlah_soal} soal terisi</p>')
    return status + f'<a class="tombol besar" href="{P.alamat_sesi(sesi.id, ringkas.nomor_lanjut)}">Lanjutkan</a>'


def _kartu_kemajuan(ringkas: "RingkasAnak") -> str:
    isi = KP.blok_hitung_mundur(ringkas.hitung_mundur) + KP.blok_target(
        ringkas.selesai_hari_ini, ringkas.paket.target_harian)
    return f'<section class="kartu" aria-label="Kemajuanmu">{isi}</section>' if isi else ""


def _nilai_terbaik(ringkas: "RingkasAnak") -> str:
    if ringkas.nilai_terbaik is None:
        return ""
    return (f'<section class="kartu nilai-terbaik" aria-label="Nilai terbaikmu"><span>Nilai terbaikmu</span>'
            f'<strong>{int(ringkas.nilai_terbaik)}/{ringkas.paket.jumlah_soal}</strong></section>')


def _latihan_terakhir(ringkas: "RingkasAnak") -> str:
    """Sesi selesai terbaru (maks BATAS_LATIHAN_TERAKHIR, terbaru dulu) dengan tanggal relatif; kosong -> tak tampil."""
    if not ringkas.riwayat:
        return ""
    butir = "".join(
        f'<li><a class="tautan-latihan" href="{P.alamat_hasil(sesi.sesi_id)}">'
        f'<span>{html.escape(label_tanggal_relatif(sesi.mulai_epoch, ringkas.sekarang))}</span>'
        f'<strong>{int(sesi.nilai)}/{int(sesi.jumlah_soal)}</strong></a></li>'
        for sesi in ringkas.riwayat[:BATAS_LATIHAN_TERAKHIR])
    return (f'<section class="latihan-terakhir" aria-labelledby="judul-terakhir"><h2 id="judul-terakhir">'
            f'Latihan terakhir</h2><ul>{butir}</ul></section>')


def halaman_awal(ringkas: "RingkasAnak") -> bytes:
    """Penjelasan singkat + Mulai, atau Lanjutkan (ke soal kosong pertama) bila ada sesi berjalan."""
    paket = ringkas.paket
    isi = f"""{KP.bilah_beranda()}
<main class="isi"><section class="kartu kartu-awal">
{KP.maskot_kartu("menunjuk")}
<h1 class="judul">{html.escape(paket.nama_pendek)}</h1>
{_chip_aturan(paket)}
<p class="catatan">{CATATAN_WAKTU}</p>
{_aksi(ringkas)}
</section>{_kartu_kemajuan(ringkas)}{_nilai_terbaik(ringkas)}{_latihan_terakhir(ringkas)}</main>"""
    return P.dokumen("Latihan Lomba", isi, gaya_tambahan=GAYA_AWAL)
