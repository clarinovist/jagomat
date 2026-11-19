"""Halaman akun cek kemampuan gratis (funnel Fase 2b/3): hasil, info, kerangka bersama.

Halaman siap mulai dan halaman QR ada di `cek_pages_mulai`. Hanya HTML native
(tanpa JS). Renderer murni: tidak membuka basis data dan tidak membuat token;
pemanggil (`cek_http`) memberi nilai yang sudah diputuskan.

Batas isi (plan Fase 2 §2.11, §3.5): hasil gratis hanya skor, kategori, ringkasan
nama topik, label gambaran awal, batas klaim, dan kerangka terkunci. Kerangka
terkunci (`_blok_terkunci`) tidak menerima argumen apa pun, jadi tidak mungkin
memuat angka, nama materi, atau peringkat dari data. Nama panggilan anak boleh
tampil di badan halaman (di-escape), tidak pernah di URL atau pesan galat.
"""
from __future__ import annotations

import html

import cek_gratis_skor
import funnel_pages
import topik_awam
from funnel_pages import COPY_BATAS_HASIL
from funnel_pages import _D_CENTANG, _D_SERU, _ikon

# Ikon gembok daftar terkunci (dulu di funnel_pages; landing v4 tak memakainya lagi).
_D_GEMBOK = '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>'
from teacher_shell import _halaman

RUTE_MULAI = "/cek-kemampuan/mulai"
RUTE_HASIL = "/cek-kemampuan/hasil"
RUTE_TAUTAN = "/cek-kemampuan/tautan"
RUTE_PESAN = "/paket-coba/pesan"
ID_KERANGKA_TERKUNCI = "kerangka-terkunci"

KELAS_BUNGKUS = "pendamping-editorial-st akun-editorial-st akun-sempit-st funnel-halaman-st"
KELAS_BUNGKUS_TAUTAN = "pendamping-editorial-st bagikan-editorial-st funnel-halaman-st"

# DRAF: teks final menunggu persetujuan Pemilik
COPY_NOTICE_JUDUL = "Sebelum anak mulai"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_NOTICE = (
    "Jawaban anak hanya dipakai untuk membuat hasil cek ini.",
    "Bahan mentah (soal dan jawaban anak) dihapus 30 hari setelah cek selesai.",
    "Ringkasan hasil (skor, kategori, dan ringkasan awal) tetap tersimpan selama akun Anda aktif.",
    "Data ini tidak dibagikan ke pihak lain.",
    "Hasil dibuat otomatis dan belum ditinjau guru.",
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_SETUJU = (
    "Saya orang tua atau wali anak ini, sudah membaca pemberitahuan di atas, "
    "dan setuju jawaban anak dipakai untuk membuat hasil cek ini."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_TOMBOL_MULAI = "Mulai cek"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_TOMBOL_TAUTAN = "Buat tautan untuk anak"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_LABEL_GAMBARAN = "Gambaran awal · belum ditinjau guru"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_BELUM_SELESAI = (
    "Anak belum menyelesaikan cek ini. Hasil muncul di halaman ini setelah anak "
    "menekan tombol selesai di HP-nya. Belum ada skor sebelum itu."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_LIHAT_STATUS = "Lihat status cek"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_RINGKASAN_KOSONG = "Belum ada bagian yang cukup jelas dari soal yang dikerjakan."
# DRAF: teks final menunggu persetujuan Pemilik
COPY_KUNCI_JUDUL = "Ada di laporan lengkap"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_KUNCI_BUTIR = (
    "Penguasaan per materi",
    "Analisis kesalahan",
    "Urutan belajar prioritas",
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_KUNCI_CATATAN = (
    "Bagian ini terkunci dan baru terbuka di laporan lengkap yang diperiksa guru."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_CTA_PAKET = "Lihat Peta Kemampuan"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_JUDUL_PESAN = "Peta Kemampuan"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_TOMBOL_PESAN = "Pesan Peta Kemampuan"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_TANPA_ANAK = (
    "Akun ini belum punya data anak, jadi cek belum bisa dimulai. "
    "Hubungi kami lewat halaman bantuan supaya data anak dilengkapi."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_BELUM_TERSEDIA = (
    "Cek belum bisa dimulai untuk anak ini. Kemungkinan kelas anak belum diisi "
    "atau cek belum tersedia untuk kelas ini."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_WAJIB_CENTANG = "Centang persetujuan dulu, ya, supaya cek bisa dimulai."


def _e(teks: str) -> str:
    return html.escape(str(teks))


def _a(teks: str) -> str:
    return html.escape(str(teks), quote=True)


def _kepala(alis: str, judul: str, id_judul: str, nama_anak: str = "") -> str:
    untuk = f'<p class="sub">Untuk {_e(nama_anak)}</p>' if nama_anak else ""
    return (
        '<div class="jejak"><a href="/guru">&larr; Beranda</a></div>'
        '<header class="editorial-kepala-st"><div>'
        f'<p class="editorial-alis-st">{_e(alis)}</p>'
        f'<h1 id="{id_judul}">{_e(judul)}</h1>{untuk}'
        "</div></header>"
    )


def _galat(pesan: str) -> str:
    return f'<div class="pesan galat" role="alert">{_e(pesan)}</div>' if pesan else ""


def _bungkus(ident, judul: str, id_judul: str, isi: str, *, kelas: str = KELAS_BUNGKUS) -> bytes:
    return _halaman(
        judul, isi, ident=ident, stitch=True, kelas_bungkus=kelas,
        id_utama=id_judul, privat=True, keluar_topbar=False,
    )


def _daftar(butir) -> str:
    return "".join(f"<li>{_e(b)}</li>" for b in butir)


def halaman_info(ident, judul: str, teks: str) -> bytes:
    """Pesan jujur tanpa form (tanpa anak, belum tersedia untuk kelas ini)."""
    isi = (
        _kepala("CEK KEMAMPUAN GRATIS", judul, "judul-cek-info")
        + f'<div class="kartu-st"><p>{_e(teks)}</p></div>'
    )
    return _bungkus(ident, judul, "judul-cek-info", isi)


def _blok_belum_selesai(token_tautan: str) -> str:
    """Tanpa skor, kategori, ringkasan, atau angka: status, tautan anak, dan jalan ke siap mulai."""
    return (
        '<div class="kartu-st"><h2>Cek belum selesai</h2>'
        f"<p>{_e(COPY_BELUM_SELESAI)}</p>"
        f'<form method="post" action="{RUTE_TAUTAN}">'
        f'<input type="hidden" name="token" value="{_a(token_tautan)}">'
        '<p class="akun-aksi-sandi">'
        f'<button type="submit" class="tombol-utama-akun">{_e(COPY_TOMBOL_TAUTAN)}</button>'
        f'<a href="{RUTE_HASIL}">Periksa lagi</a></p></form>'
        f'<p class="funnel-tautan-baris-st"><a class="funnel-tautan-st" href="{RUTE_MULAI}">'
        f"{_e(COPY_LIHAT_STATUS)}</a></p></div>"
    )


def _chip(kelas: str, ikon: str, teks: str) -> str:
    return f'<li class="funnel-chip-st {kelas}">{ikon}<span>{_e(teks)}</span></li>'


def _blok_ringkasan(ringkasan: dict) -> str:
    kuat = [topik_awam.dari_nama_lama(b)
            for b in ringkasan["kuat"][:cek_gratis_skor.MAKS_BUTIR_RINGKASAN]]
    perlu = [topik_awam.dari_nama_lama(b)
             for b in ringkasan["perlu"][:cek_gratis_skor.MAKS_BUTIR_RINGKASAN]]
    if not kuat and not perlu:
        return f'<p class="funnel-catatan-st">{_e(COPY_RINGKASAN_KOSONG)}</p>'
    bagian = ""
    if kuat:
        butir = "".join(_chip("funnel-chip-kuat-st", _ikon(_D_CENTANG, 20, "2.6"), b) for b in kuat)
        bagian += f'<h3 class="funnel-sub-judul-st">Sudah kuat</h3><ul class="funnel-chip-baris-st">{butir}</ul>'
    if perlu:
        butir = "".join(_chip("funnel-chip-lemah-st", _ikon(_D_SERU), b) for b in perlu)
        bagian += f'<h3 class="funnel-sub-judul-st">Perlu diperkuat</h3><ul class="funnel-chip-baris-st">{butir}</ul>'
    return bagian


def _blok_terkunci() -> str:
    """Kerangka terkunci: teks tetap, tanpa argumen, jadi tanpa data apa pun."""
    butir = "".join(
        f'<li class="funnel-terkunci-butir-st">{_ikon(_D_GEMBOK, 20, "2.2")}<span>{_e(b)}</span></li>'
        for b in COPY_KUNCI_BUTIR
    )
    return (
        f'<section class="funnel-kunci-st" id="{ID_KERANGKA_TERKUNCI}" '
        'aria-labelledby="judul-kunci">'
        f'<h2 class="funnel-sub-judul-st" id="judul-kunci">{_e(COPY_KUNCI_JUDUL)}</h2>'
        f'<ul class="funnel-terkunci-st">{butir}</ul>'
        f'<p class="funnel-catatan-st">{_e(COPY_KUNCI_CATATAN)}</p>'
        "</section>"
    )


def _blok_batas() -> str:
    return (
        '<section class="funnel-batas-hasil-st" aria-labelledby="judul-batas">'
        '<h2 class="funnel-sub-judul-st" id="judul-batas">Batas hasil ini</h2>'
        f"<ul>{_daftar(COPY_BATAS_HASIL)}</ul></section>"
    )


def _blok_pesan(token_pesan) -> str:
    """CTA pesan Peta Kemampuan; kosong (tanpa byte) bila gerbang pembayaran tertutup."""
    if token_pesan is None:
        return ""
    return (
        '<section class="kartu-st" aria-labelledby="judul-pesan">'
        f'<h2 id="judul-pesan">{_e(COPY_JUDUL_PESAN)}</h2><p>{_e(funnel_pages.COPY_HARGA)}</p>'
        f'<form method="post" action="{RUTE_PESAN}">'
        f'<input type="hidden" name="token" value="{_a(token_pesan)}">'
        '<p class="akun-aksi-sandi">'
        f'<button type="submit" class="tombol-utama-akun">{_e(COPY_TOMBOL_PESAN)}</button></p>'
        "</form></section>"
    )


def _cincin(skor: int) -> str:
    """Cincin skor SVG: busur dihitung server lewat atribut (tanpa gaya inline); warna dari kelas CSS."""
    persen = max(0, min(100, int(skor)))
    return (
        '<div class="funnel-cincin-wadah-st">'
        '<svg class="funnel-cincin-svg-st" viewBox="0 0 104 104" aria-hidden="true">'
        '<circle class="funnel-cincin-latar-st" cx="52" cy="52" r="42" pathLength="100"/>'
        '<circle class="funnel-cincin-busur-st" cx="52" cy="52" r="42" pathLength="100" '
        f'stroke-dasharray="{persen} 100"/></svg>'
        f'<p class="funnel-cincin-angka-st"><b>{persen}</b><small>dari 100</small></p></div>'
    )


def _baris_benar(hasil: dict) -> str:
    benar = cek_gratis_skor.jumlah_benar(int(hasil["skor"]), int(hasil["jumlah_soal"]))
    if benar is None:
        return ""
    return f'<p class="funnel-benar-st">{benar} dari {int(hasil["jumlah_soal"])} soal benar</p>'


def _blok_kepala_hasil(hasil: dict, nama_anak: str, kelas) -> str:
    untuk = f"Hasil {nama_anak}" + (f" \u00b7 kelas {int(kelas)}" if type(kelas) is int else "")
    return (
        '<section class="funnel-hasil-kepala-st" aria-labelledby="judul-skor">'
        '<h2 class="funnel-sr-st" id="judul-skor">Skor keseluruhan</h2>'
        f'{_cincin(hasil["skor"])}'
        '<div class="funnel-hasil-teks-st">'
        f'<p class="funnel-hasil-untuk-st">{_e(untuk)}</p>'
        f'<p class="funnel-kategori-judul-st">{_e(hasil["kategori"])}</p>'
        f'<span class="funnel-pil-hasil-st">{_e(COPY_LABEL_GAMBARAN)}</span>'
        "</div></section>"
        f"{_baris_benar(hasil)}"
    )


def _blok_selesai(hasil: dict, token_pesan, nama_anak: str, kelas) -> str:
    return (
        f"{_blok_kepala_hasil(hasil, nama_anak, kelas)}"
        '<section class="funnel-ringkasan-st" aria-labelledby="judul-ringkasan">'
        '<h2 class="funnel-sub-judul-st" id="judul-ringkasan">Ringkasan awal</h2>'
        f'{_blok_ringkasan(hasil["ringkasan"])}</section>'
        f"{_blok_terkunci()}{_blok_batas()}{_blok_pesan(token_pesan)}"
        '<p class="funnel-tautan-baris-st">'
        f'<a class="funnel-tautan-st" href="/paket-coba">{_e(COPY_CTA_PAKET)}</a>'
        f'<a class="funnel-tautan-sekunder-st" href="{funnel_pages.JALUR_CONTOH}">'
        f"{_e(funnel_pages.COPY_TAUTAN_CONTOH)}</a></p>"
    )


def halaman_hasil(ident, hasil: dict, nama_anak: str, token_tautan: str,
                  token_pesan=None, kelas=None) -> bytes:
    """Hasil milik akun sesi: status `selesai` atau `belum_selesai` (selain itu tidak dirender).

    `token_pesan` (hanya saat gerbang pembayaran terbuka) menambah CTA pesan di hasil
    selesai; None = tanpa byte CTA. `kelas` (int 1-6 atau None) hanya untuk judul kartu skor.
    `token_tautan` (hasil belum selesai) memberi tombol tautan anak bawaan (QR, HP anak);
    pilihan HP ini / HP anak lengkap ada di halaman siap mulai.
    """
    selesai = hasil["status"] == "selesai"
    isi = _kepala("CEK KEMAMPUAN GRATIS", "Hasil cek kemampuan", "judul-cek-hasil",
                  "" if selesai else nama_anak)
    if selesai:
        isi += _blok_selesai(hasil, token_pesan, nama_anak, kelas)
    else:
        isi += _blok_belum_selesai(token_tautan)
    return _bungkus(ident, "Hasil cek kemampuan", "judul-cek-hasil", f'<div class="funnel-alur-st">{isi}</div>')
