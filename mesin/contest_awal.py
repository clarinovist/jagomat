"""Halaman awal Latihan Lomba untuk anak (``/murid/lomba``): dua tombol mode, Lanjutkan, hitung mundur, target, riwayat.

Dua tombol mulai: "Latihan" / "10 soal · 15 menit" dan "Simulasi Lomba" / "35 soal · 60 menit"; angka menit dari paket
yang sudah ditimpa durasi Guru untuk anak itu (`contest_anak.paket_untuk_anak`). Riwayat diberi label mode.

Murni render dari `contest_anak.RingkasAnak` (tanpa DB, tanpa kunci jawaban). Tanpa skrip: sisa waktu sesi
berjalan hanya angka statis dari server.
"""
from __future__ import annotations

import html
from typing import TYPE_CHECKING

import contest_komponen as KP
import contest_paket as PK
import contest_pages as P
from contest_format import label_tanggal_relatif
from contest_style import GAYA_AWAL

if TYPE_CHECKING:
    from contest_anak import RingkasAnak

BATAS_LATIHAN_TERAKHIR = 5
CATATAN_WAKTU = "Waktu terus berjalan walaupun kamu keluar dari halaman ini. Jawabanmu tetap tersimpan."


CATATAN_SIMULASI = "Simulasi Lomba mirip lomba sungguhan: {pg} pilihan ganda + {isian} isian."


def isi_tombol_mode(format_mode) -> str:
    """Dua baris yang disengaja: nama mode, lalu "35 soal · 60 menit" (tidak patah acak di HP)."""
    detail = f"{format_mode.jumlah_soal} soal \u00b7 {format_mode.durasi_menit} menit"
    return (f'<span class="mode-nama">{html.escape(format_mode.label)}</span>'
            f'<span class="mode-detail">{html.escape(detail)}</span>')


def _tombol_mode(paket, mode: str, kelas: str) -> str:
    format_mode = paket.format_mode(mode)
    return (f'<form method="post" action="{P.ALAMAT_MULAI}"><input type="hidden" name="mode" value="{mode}">'
            f'<button type="submit" class="{kelas}">{isi_tombol_mode(format_mode)}</button></form>')


def _pilih_mode(paket) -> str:
    simulasi = paket.format_mode(PK.MODE_SIMULASI)
    catatan = CATATAN_SIMULASI.format(pg=simulasi.jumlah_pg, isian=simulasi.jumlah_isian)
    return ('<div class="pilih-mode">' + _tombol_mode(paket, PK.MODE_LATIHAN, "tombol besar")
            + _tombol_mode(paket, PK.MODE_SIMULASI, "tombol besar sekunder") + "</div>"
            + f'<p class="catatan-kecil">{html.escape(catatan)}</p>')


def _aksi(ringkas: "RingkasAnak") -> str:
    if ringkas.berjalan is None:
        return _pilih_mode(ringkas.paket)
    sesi = ringkas.berjalan
    siapa = PK.LABEL_BERJALAN.get(sesi.mode, PK.LABEL_BERJALAN[PK.MODE_LATIHAN])
    status = (f'<p class="catatan">{siapa} masih berjalan. Sisa waktu: <strong>{P.mmss(ringkas.sisa_detik)}</strong>'
              f' &middot; {len(ringkas.terisi)} dari {int(sesi.jumlah_soal)} soal terisi</p>')
    return status + f'<a class="tombol besar" href="{P.alamat_sesi(sesi.id, ringkas.nomor_lanjut)}">Lanjutkan</a>'


def _kartu_kemajuan(ringkas: "RingkasAnak") -> str:
    isi = KP.blok_hitung_mundur(ringkas.hitung_mundur) + KP.blok_target(
        ringkas.selesai_hari_ini, ringkas.paket.target_harian)
    return f'<section class="kartu" aria-label="Kemajuanmu">{isi}</section>' if isi else ""


def _baris_terbaik(label: str, nilai, jumlah: int) -> str:
    return f'<p class="nilai-terbaik-baris"><span>{label}</span><strong>{int(nilai)}/{int(jumlah)}</strong></p>'


def _nilai_terbaik(ringkas: "RingkasAnak") -> str:
    """Nilai terbaik per mode (Latihan dari 10, Simulasi dari 35); kosong bila belum ada sesi sah."""
    paket = ringkas.paket
    baris = []
    if ringkas.nilai_terbaik is not None:
        baris.append(_baris_terbaik("Nilai terbaikmu" if ringkas.terbaik_simulasi is None else "Latihan terbaik",
                                    ringkas.nilai_terbaik, paket.jumlah_soal))
    if ringkas.terbaik_simulasi is not None:
        baris.append(_baris_terbaik("Simulasi terbaik", ringkas.terbaik_simulasi, paket.jumlah_soal_simulasi))
    if not baris:
        return ""
    return f'<section class="kartu nilai-terbaik" aria-label="Nilai terbaikmu">{"".join(baris)}</section>'


def _latihan_terakhir(ringkas: "RingkasAnak") -> str:
    """Sesi selesai terbaru (maks BATAS_LATIHAN_TERAKHIR, terbaru dulu) dengan tanggal relatif; kosong -> tak tampil."""
    if not ringkas.riwayat:
        return ""
    butir = "".join(
        f'<li><a class="tautan-latihan" href="{P.alamat_hasil(sesi.sesi_id)}">'
        f'<span>{html.escape(label_tanggal_relatif(sesi.mulai_epoch, ringkas.sekarang))}'
        f' <span class="label-mode">{PK.LABEL_MODE_PENDEK.get(sesi.mode, "")}</span></span>'
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
<h1 class="judul">{PK.JUDUL_ANAK}</h1>
<p class="catatan-kecil">{CATATAN_WAKTU}</p>
{_aksi(ringkas)}
</section>{_kartu_kemajuan(ringkas)}{_nilai_terbaik(ringkas)}{_latihan_terakhir(ringkas)}</main>"""
    return P.dokumen("Latihan Lomba", isi, gaya_tambahan=GAYA_AWAL)
