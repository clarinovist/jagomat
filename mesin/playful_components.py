"""Komponen markup ceria bersama (gaya landing page) untuk halaman anak dan Ayah/Bunda.

Fungsi murni: tidak membaca DB dan tidak memakai JS. Semua teks dan atribut dari pemanggil
di-escape di sini. Parameter bernama `isi` / `isi_html` adalah HTML tepercaya yang dirakit
dari komponen lain di modul ini; jangan isi dengan masukan pengguna. CSS-nya `playful_style.GAYA_CERIA`
(pemanggil menambahkannya ke `<head>`; sengaja tidak ikut `gaya_stitch()`).

Aturan layar yang dijaga pemanggil, bukan modul ini: maksimal satu maskot per layar, dan kartu
`kartu_ajakan_ortu` hanya di `/murid/latihan-harian` (satu aksi satu entry point).
Tanpa kode diagnosis, malrule, atau kunci jawaban di komponen sisi anak.
"""
from __future__ import annotations

import html
from typing import Collection, Optional, Sequence

import brand

HARI_PEKAN = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
JUMLAH_SOAL_SESI = 10
UKURAN_MASKOT_BICARA = 96
POSE_BETUL = "merayakan"
POSE_BELUM_TEPAT = "berpikir"
_ALT_POSE = {
    "menyapa": "Jago, maskot Jagomat, menyapa",
    "menunjuk": "Jago, maskot Jagomat, menunjuk",
    "berpikir": "Jago, maskot Jagomat, sedang berpikir",
    "membaca": "Jago, maskot Jagomat, sedang membaca",
    "menulis": "Jago, maskot Jagomat, sedang menulis",
    "merayakan": "Jago, maskot Jagomat, merayakan",
}
_LEVEL_JUDUL = (2, 3, 4)
_SIMBOL_HERO = ("+", "&divide;", "&times;", "7")
_JUMLAH_KONFETI = 8


def _e(nilai: object) -> str:
    return html.escape(str(nilai), quote=True)


def _alamat_dalam(href: str) -> str:
    """Tautan kartu ajakan wajib alamat dalam aplikasi ("/..." bukan "//..."), supaya tak bisa jadi skema lain."""
    if not isinstance(href, str) or not href.startswith("/") or href.startswith("//"):
        raise ValueError(f"tautan harus alamat dalam aplikasi: {href!r}")
    return href


def sorot(teks: str) -> str:
    """Kata kunci bergaris (amber, garis koral); hanya untuk latar gelap (teal atau navy)."""
    return f'<span class="ceria-sorot">{_e(teks)}</span>'


def stiker(teks: str, arah: str = "kiri") -> str:
    """Stiker amber miring. `arah` = "kiri" (bawaan) atau "kanan"."""
    if arah not in ("kiri", "kanan"):
        raise ValueError(f"arah stiker tidak dikenal: {arah!r}")
    tambahan = " ceria-miring-kanan" if arah == "kanan" else ""
    return f'<span class="ceria-stiker{tambahan}">{_e(teks)}</span>'


def hero(isi: str, *, konfeti: bool = False) -> str:
    """Hero teal berisi `isi` (HTML tepercaya) dengan simbol matematika samar; `konfeti` menambah konfeti statis."""
    simbol = "".join(f"<b>{s}</b>" for s in _SIMBOL_HERO)
    hias = f'<div class="ceria-simbol" aria-hidden="true">{simbol}</div>'
    if konfeti:
        hias += f'<div class="ceria-konfeti" aria-hidden="true">{"<i></i>" * _JUMLAH_KONFETI}</div>'
    return f'<div class="ceria-hero">{hias}{isi}</div>'


def maskot_bicara(pose: str, awal: str, tebal: str = "", akhir: str = "", alt: Optional[str] = None) -> str:
    """Baris maskot + gelembung bicara: `awal` + **tebal** + `akhir` (semuanya di-escape).

    `alt` bawaan menyebut pose maskot; pemanggil boleh mengganti bila perlu. Pose tak dikenal -> ValueError.
    """
    teks_alt = alt if alt is not None else _ALT_POSE.get(pose, "")
    gambar = brand.maskot(pose, UKURAN_MASKOT_BICARA, alt=teks_alt, kelas="ceria-maskot")
    isi_tebal = f"<b>{_e(tebal)}</b>" if tebal else ""
    return (f'<div class="ceria-maskot-baris">{gambar}'
            f'<p class="ceria-gelembung">{_e(awal)}{isi_tebal}{_e(akhir)}</p></div>')


def kartu_ajakan_ortu(href: str, teks_tombol: str, teks_harga: str, poin: Sequence[str] = (),
                      label: str = "Untuk Ayah/Bunda", judul_awal: str = "Latihan",
                      judul_sorot: str = "tanpa batas", level: int = 3) -> str:
    """Kartu navy ajakan untuk orang dewasa: judul "<awal> <sorot> <teks_harga>", daftar centang, SATU tautan tombol.

    `teks_harga` dihitung pemanggil dari konstanta paket (mis. "mulai Rp39.000/bulan"), bukan ditulis tangan di sini.
    """
    if level not in _LEVEL_JUDUL:
        raise ValueError(f"level judul tidak didukung: {level!r}")
    daftar = "".join(f"<li>{_e(p)}</li>" for p in poin)
    centang = f'<ul class="ceria-centang">{daftar}</ul>' if daftar else ""
    judul = f'{_e(judul_awal)} {sorot(judul_sorot)} {_e(teks_harga)}'
    return (f'<section class="ceria-ortu"><p class="ceria-alis">{_e(label)}</p>'
            f'<h{level} class="ceria-judul">{judul}</h{level}>{centang}'
            f'<a class="ceria-tombol" href="{_e(_alamat_dalam(href))}">{_e(teks_tombol)}</a></section>')


def titik_hari(terisi: Collection[int], latar: str = "teal") -> str:
    """Tujuh titik hari Sen..Min. `terisi` = indeks 0..6 yang berlatih; `latar` = "teal" (di hero) atau "krem"."""
    if latar not in ("teal", "krem"):
        raise ValueError(f"latar titik tidak dikenal: {latar!r}")
    sah = set(terisi)
    if not sah <= set(range(len(HARI_PEKAN))):
        raise ValueError(f"indeks hari harus 0..6: {sorted(sah)!r}")
    butir = "".join(
        f'<li class="{"ceria-isi" if i in sah else "ceria-kosong"}"><i></i>{_e(nama)}'
        f'<span class="ceria-sr">{", berlatih" if i in sah else ", belum berlatih"}</span></li>'
        for i, nama in enumerate(HARI_PEKAN))
    kelas = "ceria-titik ceria-krem" if latar == "krem" else "ceria-titik"
    return f'<ul class="{kelas}">{butir}</ul>'


def progres_soal(sudah: int, kini: Optional[int] = None, jumlah: int = JUMLAH_SOAL_SESI) -> str:
    """Progres kotak soal: kotak 1..`sudah` terisi, kotak nomor `kini` (1-based, opsional) menyala, sisanya kosong."""
    if jumlah < 1 or not 0 <= sudah <= jumlah or (kini is not None and not 1 <= kini <= jumlah):
        raise ValueError(f"progres tidak sah: sudah={sudah!r} kini={kini!r} jumlah={jumlah!r}")
    segmen = "".join(
        f'<span class="{"ceria-sudah" if n <= sudah else ("ceria-kini" if n == kini else "")}"></span>'
        for n in range(1, jumlah + 1))
    return (f'<div class="ceria-progres" role="img" '
            f'aria-label="{sudah} dari {jumlah} soal sudah dijawab">{segmen}</div>')


def skor_besar(benar: int, jumlah: int = JUMLAH_SOAL_SESI) -> str:
    """Skor besar "N dari M benar" + deretan M titik (terisi sebanyak benar). Tanpa peringkat atau pembanding."""
    if jumlah < 1 or not 0 <= benar <= jumlah:
        raise ValueError(f"skor tidak sah: benar={benar!r} jumlah={jumlah!r}")
    titik = "".join(f'<i class="{"ceria-isi" if n < benar else ""}"></i>' for n in range(jumlah))
    return (f'<p class="ceria-skor"><b>{benar}</b> dari {jumlah} benar</p>'
            f'<div class="ceria-bintang" aria-hidden="true">{titik}</div>')


def banner_umpan_balik(betul: bool, judul: str, teks: str, pose: Optional[str] = None,
                       alt: Optional[str] = None, level: int = 3) -> str:
    """Banner umpan balik dengan slot maskot. Betul = hijau; belum tepat = hangat (amber), BUKAN merah.

    Pose bawaan: merayakan (betul) / berpikir (belum tepat). Pemanggil menjaga satu maskot per layar.
    """
    if level not in _LEVEL_JUDUL:
        raise ValueError(f"level judul tidak didukung: {level!r}")
    pose_pakai = pose or (POSE_BETUL if betul else POSE_BELUM_TEPAT)
    teks_alt = alt if alt is not None else _ALT_POSE.get(pose_pakai, "")
    gambar = brand.maskot(pose_pakai, UKURAN_MASKOT_BICARA, alt=teks_alt, kelas="ceria-maskot")
    kelas = "ceria-banner ceria-betul" if betul else "ceria-banner ceria-hampir"
    return (f'<div class="{kelas}" role="status">{gambar}'
            f'<div><h{level} class="ceria-judul">{_e(judul)}</h{level}><p>{_e(teks)}</p></div></div>')
