"""Halaman akun cek kemampuan gratis (funnel Fase 2b): mulai, hasil, tautan anak.

Hanya HTML native (tanpa JS). Renderer murni: tidak membuka basis data dan tidak
membuat token; pemanggil (`cek_http`) memberi nilai yang sudah diputuskan.

Batas isi (plan Fase 2 §2.11, §3.5): hasil gratis hanya skor, kategori, ringkasan
nama topik, label gambaran awal, batas klaim, dan kerangka terkunci. Kerangka
terkunci (`_blok_terkunci`) tidak menerima argumen apa pun, jadi tidak mungkin
memuat angka, nama materi, atau peringkat dari data. Nama panggilan anak boleh
tampil di badan halaman (di-escape), tidak pernah di URL atau pesan galat.
"""
from __future__ import annotations

import html

import share_links
from funnel_pages import COPY_BATAS_HASIL
from teacher_shell import _halaman

RUTE_MULAI = "/cek-kemampuan/mulai"
RUTE_HASIL = "/cek-kemampuan/hasil"
RUTE_TAUTAN = "/cek-kemampuan/tautan"
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
COPY_CTA_PAKET = "Lihat Paket Coba"
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


def _form_mulai(token: str) -> str:
    return (
        f'<form method="post" action="{RUTE_MULAI}">'
        f'<input type="hidden" name="token" value="{_a(token)}">'
        '<label class="akun-label-persetujuan" for="setuju-cek">'
        '<input type="checkbox" id="setuju-cek" name="setuju" value="1" required>'
        f"<span>{_e(COPY_SETUJU)}</span></label>"
        '<p class="akun-aksi-sandi">'
        f'<button type="submit" class="tombol-utama-akun">{_e(COPY_TOMBOL_MULAI)}</button></p>'
        "</form>"
    )


def halaman_mulai(ident, token: str, nama_anak: str, *, galat: str = "") -> bytes:
    """Pemberitahuan data + centang persetujuan + tombol mulai (satu anak per akun)."""
    isi = (
        _kepala("CEK KEMAMPUAN GRATIS", "Mulai cek kemampuan", "judul-cek-mulai", nama_anak)
        + _galat(galat)
        + '<section class="kartu-st funnel-kartu-batas-st" aria-labelledby="judul-notice">'
        f'<h2 id="judul-notice">{_e(COPY_NOTICE_JUDUL)}</h2><ul>{_daftar(COPY_NOTICE)}</ul>'
        "</section>"
        f'<div class="kartu-st">{_form_mulai(token)}</div>'
    )
    return _bungkus(ident, "Mulai cek kemampuan", "judul-cek-mulai", isi)


def _blok_belum_selesai(token_tautan: str) -> str:
    """Tanpa skor, kategori, atau ringkasan: hanya status dan tombol tautan anak."""
    return (
        '<div class="kartu-st"><h2>Cek belum selesai</h2>'
        f"<p>{_e(COPY_BELUM_SELESAI)}</p>"
        f'<form method="post" action="{RUTE_TAUTAN}">'
        f'<input type="hidden" name="token" value="{_a(token_tautan)}">'
        '<p class="akun-aksi-sandi">'
        f'<button type="submit" class="tombol-utama-akun">{_e(COPY_TOMBOL_TAUTAN)}</button>'
        f'<a href="{RUTE_HASIL}">Periksa lagi</a></p></form></div>'
    )


def _blok_ringkasan(ringkasan: dict) -> str:
    kuat, perlu = ringkasan["kuat"], ringkasan["perlu"]
    if not kuat and not perlu:
        return f'<p class="funnel-catatan-st">{_e(COPY_RINGKASAN_KOSONG)}</p>'
    bagian = ""
    if kuat:
        bagian += f"<h3>Sudah kuat</h3><ul>{_daftar(kuat)}</ul>"
    if perlu:
        bagian += f"<h3>Perlu diperkuat</h3><ul>{_daftar(perlu)}</ul>"
    return bagian


def _blok_terkunci() -> str:
    """Kerangka terkunci: teks tetap, tanpa argumen, jadi tanpa data apa pun."""
    return (
        f'<section class="funnel-kunci-st" id="{ID_KERANGKA_TERKUNCI}" '
        'aria-labelledby="judul-kunci">'
        f'<h2 id="judul-kunci">{_e(COPY_KUNCI_JUDUL)}</h2>'
        f"<ul>{_daftar(COPY_KUNCI_BUTIR)}</ul>"
        f'<p class="funnel-catatan-st">{_e(COPY_KUNCI_CATATAN)}</p>'
        "</section>"
    )


def _blok_batas() -> str:
    return (
        '<section class="kartu-st funnel-kartu-batas-st" aria-labelledby="judul-batas">'
        '<h2 id="judul-batas">Batas hasil ini</h2>'
        f"<ul>{_daftar(COPY_BATAS_HASIL)}</ul></section>"
    )


def _blok_selesai(hasil: dict) -> str:
    return (
        '<section class="kartu-st" aria-labelledby="judul-skor">'
        f'<p class="funnel-pil-st funnel-pil-jujur-st">{_e(COPY_LABEL_GAMBARAN)}</p>'
        '<h2 id="judul-skor">Skor keseluruhan</h2>'
        '<p class="funnel-skor-st">'
        f'<span class="funnel-skor-angka-st">{int(hasil["skor"])}</span>'
        '<span class="funnel-skor-satuan-st">dari 100</span></p>'
        f'<p>Kategori: <b>{_e(hasil["kategori"])}</b></p>'
        "<h2>Ringkasan awal</h2>"
        f'{_blok_ringkasan(hasil["ringkasan"])}</section>'
        f"{_blok_batas()}{_blok_terkunci()}"
        '<p class="funnel-tautan-baris-st">'
        f'<a class="funnel-tautan-st" href="/paket-coba">{_e(COPY_CTA_PAKET)}</a></p>'
    )


def halaman_hasil(ident, hasil: dict, nama_anak: str, token_tautan: str) -> bytes:
    """Hasil milik akun sesi: status `selesai` atau `belum_selesai` (selain itu tidak dirender)."""
    isi = _kepala("CEK KEMAMPUAN GRATIS", "Hasil cek kemampuan", "judul-cek-hasil", nama_anak)
    if hasil["status"] == "selesai":
        isi += _blok_selesai(hasil)
    else:
        isi += _blok_belum_selesai(token_tautan)
    return _bungkus(ident, "Hasil cek kemampuan", "judul-cek-hasil", isi)


def halaman_tautan(ident, nama_anak: str, tautan: str) -> bytes:
    """Kode QR + tautan teks untuk HP anak; hanya di respons POST pembuatnya."""
    from teacher_print_pages import _blok_qr

    isi = (
        _kepala("MULAI DI HP ANAK", "Tautan untuk anak", "judul-cek-tautan", nama_anak)
        + '<section class="kartu-st bagikan-kartu-st" aria-labelledby="label-tautan">'
        f"{_blok_qr(tautan)}"
        '<label id="label-tautan" for="tautan-sesi">Atau kirim tautan ini ke HP anak</label>'
        f'<input id="tautan-sesi" type="text" readonly value="{_a(tautan)}" '
        'aria-describedby="petunjuk-tautan" spellcheck="false">'
        '<p id="petunjuk-tautan" class="sub">Pilih seluruh isi kotak, lalu salin. '
        f"Tautan berlaku {_e(share_links.LABEL_MASA_BERLAKU)}, atau sampai cek selesai "
        "maupun tautan baru dibuat.</p>"
        '<p class="bagikan-perhatian-st">Siapa pun yang memegang tautan dapat mengerjakan '
        "cek ini tanpa masuk. Berikan hanya kepada anak yang dituju. Tautan ini hanya "
        "tampil di halaman ini; bila hilang, buat tautan baru dari halaman hasil. "
        "Jangan masuk sebagai guru di HP anak.</p>"
        "</section>"
        f'<p class="akun-aksi-sandi"><a href="{RUTE_HASIL}">Kembali ke halaman hasil</a></p>'
    )
    return _bungkus(ident, "Tautan untuk anak", "judul-cek-tautan", isi, kelas=KELAS_BUNGKUS_TAUTAN)
