"""Façade kompatibel halaman guru: workspace, sesi, review, dan lembar.

Router HTTP tetap di web.py. Bingkai/topbar dimiliki ``teacher_shell.py``
dan di-re-export di sini agar caller lama tetap bekerja. Aturan lama tetap:
modul ini tidak boleh mengimpor students di atas file (impor terlambat di
fungsi yang membutuhkannya).
"""

from __future__ import annotations

import random
import database
import question_views
import guru_beranda_pages
import worksheets
from generator import LEVEL_BAWAAN
from topics import TOPIK_BAWAAN, ambil
from template_labels import nama_tipe_soal as _nama_template
from templates import Soal
from teacher_corrections import KODE_PILIHAN
from teacher_shell import (
    _halaman,
    _halaman_stitch,
    _topbar,
    _topbar_stitch,
)
from teacher_print_pages import (
    _pil_sesi,
    _tombol_cerita,
    halaman_bagikan_sesi,
    halaman_konfirmasi_hapus,
    halaman_sesi_cetak,
    halaman_sesi_lampiran,
    halaman_lembar as _halaman_lembar_impl,
)
from teacher_review_service import simpan_sesi as _simpan_sesi_impl
from teacher_session_pages import (
    _badge_mode,
    _blok_latihan_serupa,
    _label_tahap_sesi,
    _pil_sesi_stitch,
    halaman_sesi_stitch as _halaman_sesi_stitch_impl,
)
from teacher_workspace import (
    INFO_LATIHAN_BEBAS,
    LABEL_KODE_REMEDIAL,
    _ambil,
    _badge_review_status,
    _kelas_sekolah_profil,
    _kontrol_mode_sesi,
    _kontrol_profil_parameter,
    _fmt_durasi,
    _form_remedial,
    _mode_sesi,
    _nama_topik_sesi,
    _ringkasan_angka_sesi,
    _tanggal_ringkas,
    _topik_untuk_level,
    halaman_anak,
)


def _soal_dari_baris(baris) -> Soal:
    """Wrapper kompatibilitas menuju adapter pembaca penyajian sesi."""
    return question_views.soal_dari_baris(baris)




def halaman_utama_stitch(
    kon,
    pesan: str = "",
    pemilik: str | None = None,
    peran: str = "guru",
    sorot: int | None = None,
    cari: str = '',
    kelompok: str = 'semua',
) -> bytes:
    """Beranda pendamping: satu pintu per anak, tanpa keputusan belajar baru.

    Anak dikelompokkan menurut langkah berikutnya dari reducer yang sama dengan
    profil anak (``teacher_home_priority``); status kirim/review hanya ringkasan
    aktivitas, bukan bukti penguasaan. Render ada di ``guru_beranda_pages``.
    """
    return guru_beranda_pages.halaman(kon, pesan, pemilik, peran, cari, kelompok)


def halaman_lembar(kon, sesi_id: int, untuk_guru: bool = False) -> bytes | None:
    """Façade lembar dengan lookup renderer dan adapter soal tetap runtime."""
    return _halaman_lembar_impl(
        kon, sesi_id, untuk_guru, soal_dari_baris=_soal_dari_baris,
        worksheets_module=worksheets,
    )


def halaman_sesi_stitch(
    kon, sesi_id: int, pesan: str = "", peran: str = "guru",
    pengguna: str = "", bantuan: str = "", bantuan_nomor: int | None = None,
    draf_koreksi=None,
    privat: bool = False,
    masalah_konfirmasi=(),
) -> bytes:
    """Façade renderer sesi dengan lookup adapter soal tetap runtime."""
    return _halaman_sesi_stitch_impl(
        kon, sesi_id, pesan=pesan, peran=peran, pengguna=pengguna,
        bantuan=bantuan, bantuan_nomor=bantuan_nomor,
        draf_koreksi=draf_koreksi, privat=privat,
        masalah_konfirmasi=masalah_konfirmasi,
        soal_dari_baris=_soal_dari_baris,
    )



def simpan_sesi(
    kon, sesi_id: int, data: dict, *, tinjauan_disimpan: bool = False,
    guru: str = 'guru',
) -> str:
    """Façade layanan koreksi dengan lookup adapter soal tetap runtime."""
    return _simpan_sesi_impl(
        kon, sesi_id, data, tinjauan_disimpan=tinjauan_disimpan, guru=guru,
        soal_dari_baris=_soal_dari_baris,
    )


def buat_sesi_seed_baru(
    kon,
    siswa_id: int,
    level: str | None = None,
    topik: str | None = None,
    mode: str = "diagnostik",
    timer_mode: str = "tanpa",
    durasi_menit: int = 15,
    timer_auto: int = 0,
    jumlah_soal: int | None = None,
    format_jawaban: str = 'isian',
) -> int:
    """Sesi baru dengan seed yang belum pernah dipakai siswa ini."""
    if level is None:
        baris = kon.execute(
            "SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()
        level = baris["tingkat"] if baris else LEVEL_BAWAAN
    if topik is None:
        topik = TOPIK_BAWAAN
    else:
        ambil(topik)  # validasi awal: gagal cepat sebelum menyentuh basis data

    dipakai = {
        r["seed"]
        for r in kon.execute(
            "SELECT seed FROM sesi WHERE siswa_id = ?", (siswa_id,)
        ).fetchall()
    }
    for _ in range(500):
        seed = random.randint(1, 9_999_999)
        if seed not in dipakai:
            return database.buat_sesi(
                kon, siswa_id, seed, level=level, topik=topik, mode=mode,
                timer_mode=timer_mode, durasi_menit=durasi_menit,
                timer_auto=timer_auto, jumlah_soal=jumlah_soal, format_jawaban=format_jawaban,
            )
    raise RuntimeError("gagal menemukan seed baru")
