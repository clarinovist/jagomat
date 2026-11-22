"""Kartu Latihan Lomba di beranda murid (hanya dipanggil bila sakelar Lomba hidup).

`kartu_beranda` murni: menerima `contest_anak.RingkasAnak` yang sudah dihitung. `kartu_untuk_siswa` membaca
datanya dari DB (dibatasi ke satu siswa) lalu merendernya. Versi BESAR menggantikan blok "Siap untuk latihan
pertama?" saat anak belum punya sesi dari Guru; versi kecil duduk di daftar latihan. CSS: `contest_style.GAYA_BERANDA`.
"""
from __future__ import annotations

import html
from typing import TYPE_CHECKING

import contest_anak
import contest_komponen as KP
import contest_paket as PK
import contest_pages as P
from murid_shell import ikon_murid

if TYPE_CHECKING:
    from contest_anak import RingkasAnak

CATATAN_TANPA_GURU = "Belum ada latihan dari gurumu."
EYEBROW = "Latihan tambahan"


def _isi_berjalan(ringkas: "RingkasAnak") -> str:
    sesi = ringkas.berjalan
    siapa = PK.LABEL_BERJALAN.get(sesi.mode, PK.LABEL_BERJALAN[PK.MODE_LATIHAN])
    return (f'<p class="lb-status">{siapa} masih berjalan</p>'
            f'<p class="lb-meta">Sisa waktu {P.mmss(ringkas.sisa_detik)} &middot; '
            f'{len(ringkas.terisi)} dari {int(sesi.jumlah_soal)} soal terisi</p>'
            f'<a class="lb-tombol" href="{P.alamat_sesi(sesi.id, ringkas.nomor_lanjut)}">Lanjutkan</a>')


def _isi_belum_jalan(ringkas: "RingkasAnak") -> str:
    terakhir = ""
    if ringkas.nilai_terakhir is not None:
        jumlah = ringkas.jumlah_terakhir or ringkas.paket.jumlah_soal
        terakhir = f'<p class="lb-meta">Nilai terakhir: {int(ringkas.nilai_terakhir)}/{int(jumlah)}</p>'
    return terakhir + f'<a class="lb-tombol" href="{P.ALAMAT_AWAL}">Mulai latihan</a>'


def kartu_beranda(ringkas: "RingkasAnak", besar: bool = False) -> str:
    """Satu kartu: nama paket, sesi berjalan (Lanjutkan) atau Mulai latihan, hitung mundur, dan target hari ini."""
    kelas = "lomba-beranda besar" if besar else "lomba-beranda"
    maskot = KP.maskot_kartu("menunjuk") if besar else ""
    aksi = _isi_berjalan(ringkas) if ringkas.berjalan is not None else _isi_belum_jalan(ringkas)
    kemajuan = KP.blok_hitung_mundur(ringkas.hitung_mundur) + KP.blok_target(
        ringkas.selesai_hari_ini, ringkas.paket.target_harian)
    catatan = f'<p class="lb-catatan">{CATATAN_TANPA_GURU}</p>' if besar else ""
    kepala = (f'<div class="lb-kepala"><span class="murid-ikon-topik-st">{ikon_murid("piala")}</span>'
              f'<div><span class="murid-tahap-st">{EYEBROW}</span>'
              f'<h2 id="judul-lomba">{PK.JUDUL_ANAK}</h2></div></div>')
    return (f'<section class="{kelas}" aria-labelledby="judul-lomba">{maskot}{kepala}'
            f'{aksi}{kemajuan}</section>{catatan}')


def kartu_untuk_siswa(kon, siswa_id: int, sekarang: int, besar: bool = False) -> str:
    """Muat data anak lalu render kartu beranda."""
    return kartu_beranda(contest_anak.muat_ringkas(kon, siswa_id, sekarang), besar)
