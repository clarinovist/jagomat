"""Blok "Peta Kemampuan lengkap" untuk halaman orang tua (D1-3): renderer MURNI, tanpa DB dan tanpa token.

Masukan = hasil `peta_laporan_store.terbit_terakhir` (`isi` tervalidasi, `catatan`, `diterbitkan`). Hanya kunci itu yang
dibaca, jadi kunci tambahan (akun Guru, nama anak, kontak) tidak pernah tampil. Label "Ditinjau Guru Jagomat" tanpa nama
pribadi. Penguasaan per materi memakai elemen native `<meter>` (tanpa style inline, JS, atau warna heksa). Catatan Guru
berupa teks biasa: di-escape, paragraf dipisah baris kosong, baris baru dihormati.
Tanpa kunci jawaban, malrule, diagnosis, pembahasan, kontak, atau peringkat. Tanpa maskot (halaman memegang satu maskot).
"""
from __future__ import annotations

import html
import re

import playful_components as C

ID_BLOK = "ortu-peta"
COPY_JUDUL = "Peta Kemampuan lengkap"
COPY_LENCANA = "Ditinjau Guru Jagomat"
COPY_PENGANTAR = "Ini gambaran kemampuan anak dari cek yang sudah dikerjakan, ditinjau oleh Guru."
COPY_PENGANTAR_SISTEM = "Ini gambaran kemampuan anak dari cek yang sudah dikerjakan."
COPY_SKOR_DARI = "dari 100"
COPY_MATERI_JUDUL = "Penguasaan per materi"
COPY_LATIH_JUDUL = "Yang paling perlu dilatih dulu"
COPY_LATIH_KOSONG = "Semua materi sudah baik, pertahankan."
COPY_KUAT_JUDUL = "Materi yang sudah kuat"
COPY_CATATAN_JUDUL = "Catatan dari Guru"
COPY_TANGGAL_CEK = "Cek dikerjakan %s"
COPY_TANGGAL_TERBIT = "Laporan terbit %s"
COPY_BENAR = "%d dari %d benar"
COPY_ARIA = "Penguasaan %s: %d dari %d benar"
BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember")
_PEMISAH_PARAGRAF = re.compile(r"\n[ \t]*\n")
VERSI_ISI_V2 = 2  # sama dengan `peta_laporan_snapshot.VERSI_ISI_V2` (tidak diimpor: renderer ini tetap murni)
# Versi 3 sementara dirender renderer v2 (kunci tambahan v3 tidak dibaca); renderer v3 dikerjakan terpisah.
VERSI_ISI_V3 = 3  # sama dengan `peta_laporan_snapshot.VERSI_ISI_V3`


def _e(teks) -> str:
    return html.escape(str(teks), quote=True)


def _tanggal(teks: str) -> str:
    """"2026-11-24" atau "2026-11-24 15:00:00" (WIB) menjadi "24 November 2026"."""
    tahun, bulan, hari = (int(x) for x in str(teks)[:10].split("-"))
    return "%d %s %d" % (hari, BULAN[bulan - 1], tahun)


def _baris_materi(materi: dict) -> str:
    benar, total, nama = int(materi["benar"]), int(materi["total"]), materi["materi"]
    teks = COPY_BENAR % (benar, total)
    meter = (f'<meter class="ortu-peta-meter-st" min="0" max="{total}" value="{benar}" '
             f'aria-label="{_e(COPY_ARIA % (nama, benar, total))}">{_e(teks)}</meter>')
    return (f'<li><span class="ortu-peta-nama-st"><b>{_e(nama)}</b><span>{_e(teks)}</span></span>{meter}</li>')


def _bagian_materi(per_materi) -> str:
    daftar = "".join(_baris_materi(m) for m in per_materi)
    return (f'<div class="ortu-peta-bagian-st"><h3>{_e(COPY_MATERI_JUDUL)}</h3>'
            f'<ul class="ortu-peta-materi-st">{daftar}</ul></div>')


def _bagian_latih(perlu_dilatih) -> str:
    if perlu_dilatih:
        isi = '<ol class="ortu-peta-daftar-st">' + "".join(f"<li>{_e(n)}</li>" for n in perlu_dilatih) + "</ol>"
    else:
        isi = f"<p>{_e(COPY_LATIH_KOSONG)}</p>"
    return f'<div class="ortu-peta-bagian-st"><h3>{_e(COPY_LATIH_JUDUL)}</h3>{isi}</div>'


def _bagian_kuat(kuat) -> str:
    if not kuat:
        return ""
    isi = "".join(f"<li>{_e(n)}</li>" for n in kuat)
    return (f'<div class="ortu-peta-bagian-st"><h3>{_e(COPY_KUAT_JUDUL)}</h3>'
            f'<ul class="ortu-peta-daftar-st">{isi}</ul></div>')


def _paragraf(catatan: str) -> str:
    teks = str(catatan).replace("\r\n", "\n").replace("\r", "\n").strip()
    potongan = [p.strip() for p in _PEMISAH_PARAGRAF.split(teks) if p.strip()]
    return "".join("<p>" + _e(p).replace("\n", "<br>") + "</p>" for p in potongan)


def _bagian_catatan(catatan) -> str:
    isi = _paragraf(catatan) if catatan else ""
    if not isi:
        return ""
    return f'<div class="ortu-peta-bagian-st ortu-peta-catatan-st"><h3>{_e(COPY_CATATAN_JUDUL)}</h3>{isi}</div>'


def _pengantar(oleh_sistem: bool) -> str:
    """Kalimat pembuka laporan; laporan sistem tanpa lencana dan tanpa kata Guru."""
    if oleh_sistem:
        return f'<p class="ortu-peta-pengantar-st">{_e(COPY_PENGANTAR_SISTEM)}</p>'
    return f'<p class="ortu-peta-pengantar-st">{C.lencana(COPY_LENCANA, "hijau")} {_e(COPY_PENGANTAR)}</p>'


def _bagian_kepala(isi: dict, diterbitkan: str, oleh_sistem: bool) -> str:
    return (
        _pengantar(oleh_sistem)
        + f'<p class="ortu-peta-tanggal-st">{_e(COPY_TANGGAL_CEK % _tanggal(isi["tanggal_cek"]))}'
        f' &middot; {_e(COPY_TANGGAL_TERBIT % _tanggal(diterbitkan))}</p>'
        f'<p class="ortu-peta-skor-st"><b>{int(isi["skor"])}</b> {_e(COPY_SKOR_DARI)}'
        f' &middot; {_e(isi["kategori"])}</p>'
    )


def _catatan_bila_guru(peta, oleh_sistem: bool) -> str:
    """Catatan Guru hanya untuk laporan jalur lama; catatan sistem tidak pernah dirender."""
    return "" if oleh_sistem else _bagian_catatan(peta["catatan"])


def blok_peta(peta) -> str:
    """HTML blok Peta Kemampuan lengkap; "" bila `peta` None (tidak ada laporan terbit yang boleh tampil).

    `oleh_sistem` (kunci opsional, False bila absen): laporan diterbitkan otomatis, tanpa lencana dan catatan Guru.
    Isi versi 2 dan 3 dirender `peta_laporan_ortu_v2` (impor lokal: modul itu memakai helper di sini).
    """
    if peta is None:
        return ""
    if peta["isi"].get("versi") in (VERSI_ISI_V2, VERSI_ISI_V3):
        import peta_laporan_ortu_v2
        return peta_laporan_ortu_v2.blok_peta_v2(peta)
    isi = peta["isi"]
    oleh_sistem = bool(peta.get("oleh_sistem", False))
    badan = (_bagian_kepala(isi, peta["diterbitkan"], oleh_sistem) + _bagian_materi(isi["per_materi"])
             + _bagian_latih(isi["perlu_dilatih"]) + _bagian_kuat(isi["kuat"]) + _catatan_bila_guru(peta, oleh_sistem))
    return f'<section class="ortu-kartu-st ortu-peta-st" id="{ID_BLOK}"><h2>{_e(COPY_JUDUL)}</h2>{badan}</section>'
