"""Cek kemampuan dari sesi anak (F2b): gerbang, persetujuan, mulai, status kartu beranda.

Akun anak hasil pendaftaran mode anak (F2a) mengerjakan cek gratis dari akunnya sendiri. Modul ini murni domain
(tanpa HTTP) dan memakai ulang mesin yang ada: `cek_gratis.mulai` (sesi + baris cek) dan, lewat
`cek_murid_http`, tautan anak `share_links` + layar `/mulai/<token>` (`cek_anak_http`). Tidak ada soal,
kunci, atau penilaian baru di sini.

Invarian:
- `id_akun` = akun MURID dan `siswa_id` = anak akun itu; keduanya dari sesi server (pemanggil), tidak pernah
  dari URL/form. `pemilik` dibaca dari baris `siswa` itu sendiri (koordinator lembaga atau guru mana pun).
- Tanpa baris `persetujuan_daftar_anak` dengan `versi_notice` yang sama dengan notice cek saat ini, mulai
  ditolak SEBELUM menulis apa pun (anak hasil daftar lama/buatan guru tidak bisa memulai dari sini).
- Cek anak yang dibuat `id_akun` lain (alur guru lama) tidak diambil alih dan tidak ditampilkan kartunya.
- Gerbang = sakelar `DAFTAR_AKUN_ANAK` DAN sakelar funnel: layar cek anak (`/mulai/<token>`) hanya dilayani
  `share_http` bila funnel hidup; tanpa itu token membuka halaman kerja biasa yang bukan layar "Hore".
"""
from __future__ import annotations

import html
from typing import Optional

import cek_gratis
import daftar_anak_gate
import daftar_anak_store
import funnel_flag
from cek_gratis_skor import JUMLAH_SOAL, VERSI_NOTICE, periksa_id_akun

RUTE_MULAI = "/murid/cek/mulai"
BELUM = "belum"
BERJALAN = "berjalan"
SELESAI = "selesai"
PENANDA_AWAL = "<!--cek-murid-->"
PENANDA_AKHIR = "<!--/cek-murid-->"
SEMBUNYI_KOSONG = frozenset()


def gerbang_aktif() -> bool:
    """Sakelar akun anak DAN funnel hidup (lihat docstring modul)."""
    return daftar_anak_gate.aktif() and funnel_flag.funnel_aktif()


def _pemilik_siswa(kon, siswa_id) -> Optional[str]:
    if type(siswa_id) is not int or siswa_id < 1:
        return None
    baris = kon.execute("SELECT pemilik FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
    return None if baris is None else baris["pemilik"]


def persetujuan_sah(kon, siswa_id) -> bool:
    """Baris persetujuan pendaftaran anak ini ada dan bernotice sama dengan notice cek saat ini."""
    ada = daftar_anak_store.ambil_persetujuan(kon, siswa_id)
    return ada is not None and ada[0] == VERSI_NOTICE


def mulai(kon, id_akun, siswa_id, sekarang: str) -> dict:
    """Mulai (atau lanjutkan) cek anak ini; `{"sesi_id", "baru"}`. Idempoten per anak.

    Urutan guard, semuanya sebelum menulis: id_akun sah, anak ada (`CekTidakDitemukan`), persetujuan daftar
    anak sah (`CekPersetujuanDiperlukan`); lalu `cek_gratis.mulai` yang masih menegakkan kepemilikan,
    cek-ada-milik-akun-lain (`CekTidakDitemukan`), dan ketersediaan kelas (`CekBelumTersedia`).
    Di transaksi pemanggil, tanpa commit.
    """
    periksa_id_akun(id_akun)
    pemilik = _pemilik_siswa(kon, siswa_id)
    if pemilik is None:
        raise cek_gratis.CekTidakDitemukan("Cek tidak ditemukan.")
    if not persetujuan_sah(kon, siswa_id):
        raise cek_gratis.CekPersetujuanDiperlukan("Persetujuan data diperlukan untuk memulai cek.")
    return cek_gratis.mulai(kon, id_akun, siswa_id, pemilik, True, sekarang)


def status(kon, id_akun, siswa_id) -> Optional[str]:
    """`BELUM`/`BERJALAN`/`SELESAI` untuk kartu beranda; None bila kartu tidak boleh tampil. Hanya membaca.

    `SELESAI` bila sesi cek sudah dikumpulkan, dibatalkan, atau hilang (bukan menunggu skor: penilaian dilakukan
    pembaca hasil lewat `cek_gratis.selesaikan_jika_siap`). None bila anak tanpa persetujuan sah atau cek-nya
    milik akun lain.
    """
    if not persetujuan_sah(kon, siswa_id):
        return None
    baris = kon.execute(
        """SELECT c.id_akun, c.skor, s.id AS sesi_ada, s.selesai, s.dibatalkan
           FROM cek_gratis c LEFT JOIN sesi s ON s.id = c.sesi_id WHERE c.siswa_id = ?""",
        (siswa_id,),
    ).fetchone()
    if baris is None:
        return BELUM
    if baris["id_akun"] != id_akun:
        return None
    if baris["skor"] is not None or baris["sesi_ada"] is None or baris["selesai"] is not None \
            or baris["dibatalkan"] is not None:
        return SELESAI
    return BERJALAN


def kartu_html(keadaan: Optional[str]) -> str:
    """Kartu beranda; kosong bila cek sudah selesai atau kartu tidak berlaku. Tanpa tautan, skrip, atau skor."""
    if keadaan not in (BELUM, BERJALAN):
        return ""
    lanjut = keadaan == BERJALAN
    label = "Lanjutkan cek kemampuan" if lanjut else "Mulai cek kemampuan"
    teks = "Lanjutkan dari soal yang tadi, ya." if lanjut else f"{JUMLAH_SOAL} soal pilihan ganda. Santai saja, jawab sebisamu."
    return (
        f'{PENANDA_AWAL}<section class="murid-latihan-lain-st" aria-labelledby="judul-cek-murid" '
        'style="margin-block-end: 1rem">'
        '<div class="murid-kepala-bagian-st"><h2 id="judul-cek-murid">Cek kemampuan</h2></div>'
        f'<div class="st-kartu"><p>{html.escape(teks)}</p>'
        f'<form method="post" action="{RUTE_MULAI}">'
        f'<button type="submit" class="st-tombol-coral">{html.escape(label)}</button></form></div>'
        f'</section>{PENANDA_AKHIR}'
    )


def untuk_beranda(kon, id_akun, siswa_id):
    """(html kartu, id sesi cek yang disembunyikan dari daftar latihan) untuk beranda murid.

    Gerbang mati, id_akun tak sah, atau kartu tidak berlaku -> ("", kosong): keluaran beranda tidak berubah.
    Sesi cek milik akun ini disembunyikan dari daftar latihan biasa supaya tidak ada jalur kedua yang
    melewati layar cek anak.
    """
    if not gerbang_aktif():
        return "", SEMBUNYI_KOSONG
    try:
        periksa_id_akun(id_akun)
    except ValueError:
        return "", SEMBUNYI_KOSONG
    keadaan = status(kon, id_akun, siswa_id)
    if keadaan is None:
        return "", SEMBUNYI_KOSONG
    sesi = kon.execute("SELECT sesi_id FROM cek_gratis WHERE siswa_id = ?", (siswa_id,)).fetchone()
    sembunyi = SEMBUNYI_KOSONG if sesi is None or sesi["sesi_id"] is None else frozenset({sesi["sesi_id"]})
    return kartu_html(keadaan), sembunyi
