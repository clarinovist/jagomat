"""Render halaman guru `Jadwal saya` dan `Kelas saya` (baca-saja): murni render, tanpa DB, HTTP, atau berkas.

View-model hanya berisi teks dan `id` kelompok milik guru yang sedang dilihat (untuk href detail). Tidak ada
siswa_id, order_id, guru_id, atau kontak. Semua teks di-escape; waktu tampil WIB lewat `waktu_wib`. Tanpa JS.
"""
from __future__ import annotations

import html
from typing import Sequence

import design_tokens as T
from kelas_pages import _baris_lokasi
from pesanan_transfer_pages import waktu_wib
from teacher_shell import _halaman_stitch

RUTE_KELAS = "/guru/kelas"
KELAS_BUNGKUS_JADWAL = "jadwal-guru-st"      # menandai item "Jadwal saya" di topbar
KELAS_BUNGKUS_KELAS = "kelas-guru-st"        # menandai item "Kelas saya" di topbar
KELAS_BUNGKUS_DETAIL = "kelas-detail-guru-st"  # halaman turunan: tidak menandai item induk
COPY_KOSONG_JADWAL = "Belum ada jadwal."
COPY_KOSONG_KELAS = "Belum ada kelas untuk Anda."
COPY_KOSONG_ANAK = "Belum ada anak di kelas ini."
COPY_DIBATALKAN = "Dibatalkan"
COPY_TIDAK_ADA_BERIKUT = "Tidak ada pertemuan mendatang."
COPY_AKSES_HABIS = "Akses habis"
COPY_BERLANGSUNG = "Sudah berlangsung"
COPY_KETERANGAN_BERLANGSUNG = ("Catat atau ubah kehadiran dan jurnal. "
                               "Bisa diubah sampai 7 hari setelah pertemuan selesai.")
COPY_BELUM_DICATAT = "Belum dicatat"
COPY_SUDAH_DICATAT = "Sudah dicatat"
COPY_CATAT = "Catat"
COPY_UBAH_CATATAN = "Ubah catatan"
RUTE_PERTEMUAN = "/guru/pertemuan/"
RUTE_TUGAS = "/guru/tugas"
COPY_TUGAS_ANAK = "Tugas untuk anak"

GAYA = f"""<style>
.jadwal-st {{ display: grid; gap: {T.SP_4}; }}
.jadwal-st h1 {{ margin: 0 0 {T.SP_2}; }}
.jadwal-alis-st {{ color: {T.TEKS_SUBTLE}; font-size: {T.UKURAN_TEKS_LABEL}; letter-spacing: .04em; margin: 0; }}
.jadwal-kartu-st {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_4}; display: grid; gap: {T.SP_3}; }}
.jadwal-kartu-st h2 {{ margin: 0; font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.jadwal-daftar-st {{ list-style: none; margin: 0; padding: 0; display: grid; gap: {T.SP_3}; }}
.jadwal-daftar-st li {{ border-bottom: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; padding-bottom: {T.SP_2}; }}
.jadwal-meta-st {{ color: {T.TEKS_SUBTLE}; font-size: {T.UKURAN_TEKS_LABEL}; margin: 0; }}
.jadwal-tautan-st {{ color: {T.AKSEN_TEAL_TUA}; }}
.jadwal-tautan-st:focus-visible {{ outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 2px; }}
</style>"""


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _p(teks: str, kelas: str = "") -> str:
    atribut = f' class="{kelas}"' if kelas else ""
    return f"<p{atribut}>{_e(teks)}</p>"


def _daftar_atau_kosong(baris: Sequence[str], kosong: str) -> str:
    if not baris:
        return _p(kosong, "jadwal-meta-st")
    return '<ol class="jadwal-daftar-st">' + "".join(baris) + "</ol>"


def _teks_pertemuan(ke, mulai: str) -> str:
    return f"Pertemuan {int(ke)} · {waktu_wib(mulai)}"


def _keterangan_sesi(sesi: dict) -> str:
    """'Pertemuan N · <waktu WIB>' (+ ' · Dibatalkan'); status selalu teks, bukan hanya warna."""
    teks = _teks_pertemuan(sesi["ke"], sesi["mulai"])
    return teks + (f" · {COPY_DIBATALKAN}" if sesi["dibatalkan"] else "")


def _status_dan_tautan(id_pertemuan, tercatat: bool) -> str:
    """Status teks ('Sudah dicatat' / 'Belum dicatat') dan tautan ke form catat. Hanya id integer yang masuk href."""
    status = COPY_SUDAH_DICATAT if tercatat else COPY_BELUM_DICATAT
    label = COPY_UBAH_CATATAN if tercatat else COPY_CATAT
    href = _e(f"{RUTE_PERTEMUAN}{int(id_pertemuan)}")
    return f'{status} · <a class="jadwal-tautan-st" href="{href}">{label}</a>'


def _baris_pertemuan(pertemuan: dict) -> str:
    keterangan = _e(_keterangan_sesi(pertemuan))
    tautan = ""
    if pertemuan.get("kelas_id"):
        tautan = (f' <a class="jadwal-tautan-st" href="{RUTE_KELAS}/{_e(pertemuan["kelas_id"])}">'
                  "Buka kelas</a>")
    return (f"<li><strong>{_e(pertemuan['judul'])}</strong>"
            f'<p class="jadwal-meta-st">{keterangan}{tautan}</p></li>')


def _baris_kelas(kelas: dict) -> str:
    berikut = kelas["berikut"]
    info_berikut = f"Pertemuan berikut: {waktu_wib(berikut)}" if berikut else COPY_TIDAK_ADA_BERIKUT
    terisi = f"Terisi {int(kelas['terisi'])} dari {int(kelas['kuota'])} anak · {info_berikut}"
    return (f"<li><strong>{_e(kelas['nama'])}</strong>"
            f'<p class="jadwal-meta-st">{_e(terisi)}</p>'
            f'<p><a class="jadwal-tautan-st" href="{RUTE_KELAS}/{_e(kelas["id"])}">Buka kelas</a></p></li>')


def _baris_berlangsung(pertemuan: dict) -> str:
    teks = _e(_teks_pertemuan(pertemuan["ke"], pertemuan["mulai"]))
    return (f"<li><strong>{_e(pertemuan['judul'])}</strong>"
            f'<p class="jadwal-meta-st">{teks} · '
            f"{_status_dan_tautan(pertemuan['id_pertemuan'], pertemuan['tercatat'])}</p></li>")


def _bagian_berlangsung(berlangsung: Sequence[dict]) -> str:
    """Bagian 'Sudah berlangsung'. Kosong bila tidak ada pertemuan, agar halaman tanpa isi tetap sama."""
    if not berlangsung:
        return ""
    baris = "".join(_baris_berlangsung(p) for p in berlangsung)
    return ('<section class="jadwal-kartu-st" aria-label="Sudah berlangsung">'
            f"<h2>{COPY_BERLANGSUNG}</h2>"
            f'<p class="jadwal-meta-st">{_e(COPY_KETERANGAN_BERLANGSUNG)}</p>'
            f'<ol class="jadwal-daftar-st">{baris}</ol></section>')


def _baris_sesi(sesi: dict) -> str:
    keterangan = _e(_keterangan_sesi(sesi))
    aksi = sesi.get("aksi")
    if aksi is None:
        return f"<li>{keterangan}</li>"
    return f"<li>{keterangan} · {_status_dan_tautan(aksi['id_pertemuan'], aksi['tercatat'])}</li>"


def _baris_anak(anak: dict) -> str:
    """Nama anak (di-escape); bila masa akses habis, ditambah teks `COPY_AKSES_HABIS` (bukan hanya warna)."""
    tanda = (" · " + COPY_AKSES_HABIS) if anak["akses_habis"] else ""
    return f"<li>{_e(anak['nama'])}{tanda}</li>"


def _daftar_anak(anak: Sequence[dict]) -> str:
    if not anak:
        return _p(COPY_KOSONG_ANAK, "jadwal-meta-st")
    return '<ul class="jadwal-daftar-st">' + "".join(_baris_anak(a) for a in anak) + "</ul>"


def _tautan_tugas(tugas_aktif: bool) -> str:
    """Satu tautan 'Tugas untuk anak' hanya bila gerbang tugas guru menyala; selain itu tidak ada byte tambahan."""
    if not tugas_aktif:
        return ""
    return f'<p><a class="jadwal-tautan-st" href="{RUTE_TUGAS}">{COPY_TUGAS_ANAK}</a></p>'


def halaman_jadwal(ident, pertemuan: Sequence[dict], berlangsung: Sequence[dict] = (),
                   *, tugas_aktif: bool = False) -> bytes:
    """Pertemuan mendatang milik guru, dan pertemuan yang sudah berlangsung dalam jendela catat (bila ada).

    `pertemuan` tiap item: `judul`, `ke`, `mulai`, `dibatalkan`, `kelas_id` (atau None).
    `berlangsung` tiap item: `judul`, `ke`, `mulai`, `tercatat` (bool), `id_pertemuan` (int).
    `tugas_aktif` (bawaan False): gerbang tugas guru; False menghasilkan byte yang sama dengan sebelumnya.
    """
    daftar = _daftar_atau_kosong([_baris_pertemuan(p) for p in pertemuan], COPY_KOSONG_JADWAL)
    isi = ('<main aria-labelledby="judul-jadwal" class="jadwal-st">'
           '<header><p class="jadwal-alis-st">RUANG GURU</p>'
           '<h1 id="judul-jadwal">Jadwal saya</h1>'
           "<p>Pertemuan mendatang untuk kelas dan anak yang Anda ajar. Jadwal diatur tim; "
           "halaman ini hanya menampilkan.</p></header>"
           f"{_bagian_berlangsung(berlangsung)}"
           '<section class="jadwal-kartu-st" aria-label="Pertemuan mendatang">'
           f"<h2>Pertemuan mendatang</h2>{daftar}</section>"
           f"{_tautan_tugas(tugas_aktif)}"
           '<p><a class="jadwal-tautan-st" href="/guru">Kembali ke ruang guru</a></p></main>')
    return _halaman_stitch("Jadwal saya", GAYA + isi, ident=ident,
                           kelas_bungkus=KELAS_BUNGKUS_JADWAL, privat=True)


def halaman_kelas(ident, kelas: Sequence[dict]) -> bytes:
    """Kelompok Mini Class milik guru. Tiap item: `id` (untuk href), `nama`, `kuota`, `terisi`, `berikut` (atau None)."""
    daftar = _daftar_atau_kosong([_baris_kelas(k) for k in kelas], COPY_KOSONG_KELAS)
    isi = ('<main aria-labelledby="judul-kelas" class="jadwal-st">'
           '<header><p class="jadwal-alis-st">RUANG GURU</p>'
           '<h1 id="judul-kelas">Kelas saya</h1>'
           "<p>Mini Class yang Anda ajar. Daftar anak dan pertemuan ada di tiap kelas.</p></header>"
           '<section class="jadwal-kartu-st" aria-label="Daftar kelas">'
           f"<h2>Mini Class</h2>{daftar}</section>"
           '<p><a class="jadwal-tautan-st" href="/guru">Kembali ke ruang guru</a></p></main>')
    return _halaman_stitch("Kelas saya", GAYA + isi, ident=ident,
                           kelas_bungkus=KELAS_BUNGKUS_KELAS, privat=True)


def halaman_detail(ident, kelas: dict, tautan: str = "") -> bytes:
    """Satu kelompok: `nama`, `lokasi`, `kuota`, `terisi`, `anggota` (`nama` dan `akses_habis`), `sesi` (8 pertemuan).

    `tautan` berisi HTML bagian 'Tambah anak dengan kode' dari `guru_tautan_pages` (kosong = tanpa bagian itu).
    """
    sesi = _daftar_atau_kosong([_baris_sesi(s) for s in kelas["sesi"]], COPY_KOSONG_JADWAL)
    isi = ('<main aria-labelledby="judul-kelas" class="jadwal-st">'
           '<header><p class="jadwal-alis-st">MINI CLASS</p>'
           f'<h1 id="judul-kelas">{_e(kelas["nama"])}</h1></header>'
           '<section class="jadwal-kartu-st" aria-label="Ringkasan kelas"><h2>Ringkasan</h2>'
           f'<p class="jadwal-meta-st">Terisi {int(kelas["terisi"])} dari {int(kelas["kuota"])} anak.</p>'
           f"{_baris_lokasi(kelas['lokasi'])}</section>"
           '<section class="jadwal-kartu-st" aria-label="Anak di kelas"><h2>Anak</h2>'
           f"{_daftar_anak(kelas['anggota'])}</section>"
           '<section class="jadwal-kartu-st" aria-label="Pertemuan"><h2>Pertemuan</h2>'
           f"{sesi}</section>"
           f"{tautan}"
           f'<p><a class="jadwal-tautan-st" href="{RUTE_KELAS}">Kembali ke Kelas saya</a></p></main>')
    return _halaman_stitch("Kelas saya", GAYA + isi, ident=ident,
                           kelas_bungkus=KELAS_BUNGKUS_DETAIL, privat=True)
