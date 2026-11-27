"""Blok "Peta Kemampuan lengkap" versi 2 untuk halaman orang tua (F4): renderer MURNI, tanpa DB dan tanpa token.

Dipanggil `peta_laporan_ortu_pages.blok_peta` untuk isi versi 2. Hanya data nyata di snapshot: skor, per materi, materi
kuat dan perlu dilatih, soal dilewati, perkiraan waktu (bila ada), dan grid benar/salah/dilewati per nomor. Seksi yang
datanya belum ada (perilaku belajar, cara berpikir, jenis kesalahan, pola salah) TIDAK dibuat. Tanpa nama anak, kontak,
kunci, malrule, atau peringkat. Tombol cetak memakai `SKRIP_CETAK` (berhash CSP); tanpa JS tombolnya disembunyikan.
"""
from __future__ import annotations

from fractions import Fraction

import cek_gratis_skor as skor
import peta_laporan_ortu_pages as v1
import peta_laporan_snapshot as snap
from peta_browser import SKRIP_CETAK
from peta_saran_rumah import pilih_saran

COPY_GAMBARAN_JUDUL = "Gambaran kemampuan"
COPY_BENAR_DARI = "%d dari %d soal benar"
COPY_PETA_JUDUL = "Peta Kemampuan Matematika"
COPY_TARGET = "Target berikutnya: Siap materi Kelas %d"
COPY_DETAIL_JUDUL = "Detail penguasaan per materi"
COPY_URUTAN_JUDUL = "Urutan belajar"
COPY_URUTAN = "Mulai dari materi yang paling perlu dilatih."
COPY_CARA_JUDUL = "Cara mengerjakan"
COPY_MENIT = "Perkiraan total waktu %d menit"
COPY_RATA = "Perkiraan rata-rata %d detik per soal"
COPY_DILEWATI = "%d soal dilewati"
COPY_TIDAK_DILEWATI = "Tidak ada soal yang dilewati"
COPY_GRID = "Hasil per nomor soal"
COPY_SR_NOMOR = "Nomor %d: %s"
COPY_RUMAH_JUDUL = "Yang bisa dilakukan di rumah"
COPY_REKOM_JUDUL = "Rekomendasi pendampingan"
COPY_CETAK = "Cetak / simpan PDF"
NOSCRIPT_SEMBUNYI_CETAK = "<noscript><style>.ortu-peta-cetak-baris-st{display:none}</style></noscript>"

# Satu kalimat tetap per kategori skor (nilai `cek_gratis_skor.KATEGORI`); tanpa nama anak dan tanpa kata Guru.
TEKS_REKOMENDASI = {
    "Sangat baik": "Bila Ayah/Bunda ingin, anak bisa tetap berlatih di materi yang sudah baik ini.",
    "Cukup baik": "Bila Ayah/Bunda ingin, anak bisa mulai dari materi yang paling perlu dilatih, mengikuti urutan di laporan ini.",
    "Perlu penguatan": "Bila Ayah/Bunda ingin, anak bisa mulai dari materi yang paling perlu dilatih, mengikuti urutan di laporan ini, dengan pendampingan kelas.",
    "Perlu pendampingan": "Bila Ayah/Bunda ingin, anak bisa belajar dengan pendampingan kelas, mulai dari materi yang paling perlu dilatih, mengikuti urutan di laporan ini.",
}

# Simbol tampak ditambah teks aksesibel: warna dan bentuk tidak menjadi satu-satunya pembeda.
_SIMBOL_NILAI = {
    snap.GRID_BENAR: ("✓", "benar", "ortu-peta-soal-benar-st"),
    snap.GRID_SALAH: ("✕", "salah", "ortu-peta-soal-salah-st"),
    snap.GRID_DILEWATI: ("–", "dilewati", "ortu-peta-soal-dilewati-st"),
}
_URUTAN_LEGENDA = (snap.GRID_BENAR, snap.GRID_SALAH, snap.GRID_DILEWATI)


def _urut_materi(per_materi) -> list:
    """Dari yang paling perlu dilatih (rasio benar naik), lalu nama; urutan yang sama dengan `perlu_dilatih`."""
    return sorted(per_materi, key=lambda m: (Fraction(m["benar"], m["total"]), m["materi"]))


def _bagian_peta(isi: dict) -> str:
    daftar = "".join(v1._baris_materi(m) for m in _urut_materi(isi["per_materi"]))
    target = f"<p>{v1._e(COPY_TARGET % isi['kelas'])}</p>" if isi["kelas"] is not None else ""
    return (f'<div class="ortu-peta-bagian-st"><h3>{v1._e(COPY_PETA_JUDUL)}</h3>'
            f'<ul class="ortu-peta-materi-st">{daftar}</ul>{target}</div>')


def _baris_detail(materi: dict) -> str:
    benar, total = int(materi["benar"]), int(materi["total"])
    label = skor.label_materi(benar, total)
    return (f'<li><b>{v1._e(materi["materi"])}</b><span>{v1._e(v1.COPY_BENAR % (benar, total))}</span>'
            f'<span class="ortu-peta-label-st">{v1._e(label)}</span></li>')


def _bagian_detail(isi: dict) -> str:
    daftar = "".join(_baris_detail(m) for m in _urut_materi(isi["per_materi"]))
    return (f'<div class="ortu-peta-bagian-st"><h3>{v1._e(COPY_DETAIL_JUDUL)}</h3>'
            f'<ul class="ortu-peta-detail-st">{daftar}</ul></div>')


def _bagian_urutan(perlu_dilatih: list) -> str:
    if not perlu_dilatih:
        return ""
    butir = "".join(f"<li>{v1._e(nama)}</li>" for nama in perlu_dilatih)
    return (f'<div class="ortu-peta-bagian-st"><h3>{v1._e(COPY_URUTAN_JUDUL)}</h3>'
            f'<p>{v1._e(COPY_URUTAN)}</p><ol class="ortu-peta-daftar-st">{butir}</ol></div>')


def _sel_grid(nomor: int, nilai: int) -> str:
    simbol, kata, kelas_sel = _SIMBOL_NILAI[nilai]
    return (f'<li class="ortu-peta-soal-st {kelas_sel}"><span aria-hidden="true">{nomor} {simbol}</span>'
            f'<span class="ortu-peta-sr-st">{v1._e(COPY_SR_NOMOR % (nomor, kata))}</span></li>')


def _grid(grid: list) -> str:
    sel = "".join(_sel_grid(nomor, nilai) for nomor, nilai in enumerate(grid, start=1))
    legenda = "".join(f"<li>{_SIMBOL_NILAI[nilai][0]} {_SIMBOL_NILAI[nilai][1]}</li>" for nilai in _URUTAN_LEGENDA)
    return (f'<p>{v1._e(COPY_GRID)}</p><ol class="ortu-peta-grid-st">{sel}</ol>'
            f'<ul class="ortu-peta-legenda-st">{legenda}</ul>')


def _waktu_perkiraan(isi: dict) -> str:
    """Perkiraan waktu hanya bila angkanya ada (None berarti tanpa angka sama sekali)."""
    if isi["menit_total"] is None:
        return ""
    return (f'<p>{v1._e(COPY_MENIT % isi["menit_total"])}</p>'
            f'<p>{v1._e(COPY_RATA % isi["rata_detik"])}</p>')


def _bagian_cara(isi: dict) -> str:
    dilewati = COPY_DILEWATI % isi["dilewati"] if isi["dilewati"] else COPY_TIDAK_DILEWATI
    return (f'<div class="ortu-peta-bagian-st"><h3>{v1._e(COPY_CARA_JUDUL)}</h3>'
            f'{_waktu_perkiraan(isi)}<p>{v1._e(dilewati)}</p>{_grid(isi["grid"])}</div>')


def _bagian_rumah(isi: dict) -> str:
    saran = pilih_saran(isi["perlu_dilatih"], isi["dilewati"])
    if not saran:
        return ""
    butir = "".join(f"<li>{v1._e(teks)}</li>" for teks in saran)
    return (f'<div class="ortu-peta-bagian-st"><h3>{v1._e(COPY_RUMAH_JUDUL)}</h3>'
            f'<ul class="ortu-peta-daftar-st">{butir}</ul></div>')


# Tanpa tautan "Lihat pilihan kelas": kartu lunas sudah memuat satu-satunya pintu kelas di halaman
# (commit 0441f95, test_halaman_penuh_lunas_dengan_paket_hanya_satu_pintu_kelas). Keputusan Pemilik menunggu.
def _bagian_rekomendasi(kategori: str) -> str:
    kalimat = TEKS_REKOMENDASI.get(kategori)
    if kalimat is None:
        return ""
    return (f'<div class="ortu-peta-bagian-st"><h3>{v1._e(COPY_REKOM_JUDUL)}</h3>'
            f'<p>{v1._e(kalimat)}</p></div>')


def _tombol_cetak() -> str:
    return (f'<p class="ortu-peta-cetak-baris-st"><button type="button" class="ortu-peta-cetak-st" data-peta-cetak>'
            f'{v1._e(COPY_CETAK)}</button></p>{NOSCRIPT_SEMBUNYI_CETAK}')


def _bagian_gambaran(isi: dict, peta: dict, oleh_sistem: bool) -> str:
    benar = isi["grid"].count(snap.GRID_BENAR)
    return (f'<div class="ortu-peta-bagian-st"><h3>{v1._e(COPY_GAMBARAN_JUDUL)}</h3>'
            f'{v1._bagian_kepala(isi, peta["diterbitkan"], oleh_sistem)}'
            f"<p>{v1._e(COPY_BENAR_DARI % (benar, isi['jumlah_soal']))}</p></div>")


def blok_peta_v2(peta: dict) -> str:
    """HTML blok Peta Kemampuan versi 2 (`peta["isi"]["versi"] == 2`)."""
    isi = peta["isi"]
    oleh_sistem = bool(peta.get("oleh_sistem", False))
    badan = (
        _bagian_gambaran(isi, peta, oleh_sistem)
        + _bagian_peta(isi) + _bagian_detail(isi) + v1._bagian_latih(isi["perlu_dilatih"])
        + v1._bagian_kuat(isi["kuat"]) + _bagian_urutan(isi["perlu_dilatih"]) + _bagian_cara(isi)
        + _bagian_rumah(isi) + _bagian_rekomendasi(isi["kategori"])
        + v1._catatan_bila_guru(peta, oleh_sistem)
    )
    return (f'<section class="ortu-kartu-st ortu-peta-st ortu-peta-v2-st" id="{v1.ID_BLOK}">'
            f'<h2>{v1._e(v1.COPY_JUDUL)}</h2>{_tombol_cetak()}{badan}<script>{SKRIP_CETAK}</script></section>')
