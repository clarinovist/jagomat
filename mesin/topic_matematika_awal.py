"""Matematika Awal (P1 sampai P6, khusus Latihan manual dan lembar cetak).

Topik lintas bab Kurikulum Merdeka SD yang belum punya soal (bentuk, ukuran,
diagram, pola, pecahan sederhana, waktu, peluang). Semua soal teks, tanpa gambar.
Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis
pasti dari satu jawaban. Tiap jenis ada di modul `awal_<jenis>.py`-nya sendiri
dan berhenti pada kunci dihitung dari parameter + solver terpisah di tes.

CARA MENAMBAH SATU JENIS: tulis modul `awal_<jenis>.py` (fungsi soal, `LEVEL`,
`domain_parameter(level)`, `parameter(rng, level)`), lalu tambahkan SATU entri
`Jenis(...)` di `JENIS` di bawah. Komposisi, registri template, sampler,
enumerator domain, dan judul bagian dibangun dari `JENIS`. Titik sentuh lain
(sakelar, label, kartu rumus, inventaris visual, PG, pancingan) ada di
checklist laporan tahap 2; `test_matematika_awal_*` mengunci yang bisa dikunci.

Palang: topik ini `hanya_manual`, jadi tidak ikut Campuran, siklus terpandu,
mastery, atau Pendamping karena belum punya grup mastery, kartu intervensi, dan
playbook. Pembuatan soal di balik `OSN_MATEMATIKA_AWAL` (bawaan 1, lihat
`matematika_awal_versions`); pembaca histori selalu mengenal topik dan jenisnya.
Kunci dan malrule dihitung dari parameter; kunci dicek solver terpisah yang
hanya membaca teks (test_matematika_awal_domain).
"""
from __future__ import annotations

import random
from typing import Callable, NamedTuple

import awal_baca_diagram_gambar as baca_diagram_gambar
import awal_bandingkan_ciri_bangun as bandingkan_ciri_bangun
import awal_bilang_benda_awal as bilang_benda_awal
import awal_ciri_komposisi_bangun as ciri_komposisi_bangun
import awal_keliling_gabungan as keliling_gabungan
import awal_kenali_bentuk as kenali_bentuk
import awal_luas_petak_volume_kubus as luas_petak_volume_kubus
import awal_pecahan_bilangan_asli_desimal as pecahan_bilangan_asli_desimal
import awal_pecahan_senilai_desimal as pecahan_senilai_desimal
import awal_pecahan_setengah as pecahan_setengah
import awal_peluang_dasar as peluang_dasar
import awal_pola_posisi as pola_posisi
import awal_tambah_kurang_100 as tambah_kurang_100
import awal_tambah_kurang_20 as tambah_kurang_20
import awal_turus_gambar_awal as turus_gambar_awal
import awal_ukur_konversi_awal as ukur_konversi_awal
import awal_ukur_satuan_tak_baku as ukur_satuan_tak_baku
import awal_unsur_bangun_datar as unsur_bangun_datar
import awal_waktu_berat_awal as waktu_berat_awal
from templates import Soal
from topics import Topik, daftarkan

TOPIK_ID = "matematika-awal"
# Panjang satu lembar; jenis level itu diulang bergiliran sampai penuh.
JUMLAH_SOAL_LEMBAR = 10
BAGIAN = "A"


class Jenis(NamedTuple):
    """Satu jenis soal: template, sampler, level pemakai, dan enumerator domain sahnya."""

    template_id: str
    fungsi: Callable[..., Soal]
    sampler: Callable[[random.Random, str], dict]  # (rng, level) -> parameter
    level: tuple
    domain_parameter: Callable[[str], tuple]  # level -> parameter sah (tuple of dict)


# Urutan = urutan kemunculan di lembar sebelum dikocok. TAMBAH JENIS BARU DI SINI.
JENIS = (
    Jenis(kenali_bentuk.TEMPLATE_ID, kenali_bentuk.kenali_bentuk, kenali_bentuk.parameter,
          kenali_bentuk.LEVEL, kenali_bentuk.domain_parameter),
    Jenis(ukur_satuan_tak_baku.TEMPLATE_ID, ukur_satuan_tak_baku.ukur_satuan_tak_baku,
          ukur_satuan_tak_baku.parameter, ukur_satuan_tak_baku.LEVEL,
          ukur_satuan_tak_baku.domain_parameter),
    Jenis(baca_diagram_gambar.TEMPLATE_ID, baca_diagram_gambar.baca_diagram_gambar,
          baca_diagram_gambar.parameter, baca_diagram_gambar.LEVEL,
          baca_diagram_gambar.domain_parameter),
    Jenis(pola_posisi.TEMPLATE_ID, pola_posisi.pola_posisi, pola_posisi.parameter,
          pola_posisi.LEVEL, pola_posisi.domain_parameter),
    Jenis(pecahan_setengah.TEMPLATE_ID, pecahan_setengah.pecahan_setengah,
          pecahan_setengah.parameter, pecahan_setengah.LEVEL, pecahan_setengah.domain_parameter),
    Jenis(waktu_berat_awal.TEMPLATE_ID, waktu_berat_awal.waktu_berat_awal,
          waktu_berat_awal.parameter, waktu_berat_awal.LEVEL, waktu_berat_awal.domain_parameter),
    Jenis(turus_gambar_awal.TEMPLATE_ID, turus_gambar_awal.turus_gambar_awal,
          turus_gambar_awal.parameter, turus_gambar_awal.LEVEL, turus_gambar_awal.domain_parameter),
    Jenis(ukur_konversi_awal.TEMPLATE_ID, ukur_konversi_awal.ukur_konversi_awal,
          ukur_konversi_awal.parameter, ukur_konversi_awal.LEVEL,
          ukur_konversi_awal.domain_parameter),
    Jenis(bandingkan_ciri_bangun.TEMPLATE_ID, bandingkan_ciri_bangun.bandingkan_ciri_bangun,
          bandingkan_ciri_bangun.parameter, bandingkan_ciri_bangun.LEVEL,
          bandingkan_ciri_bangun.domain_parameter),
    Jenis(peluang_dasar.TEMPLATE_ID, peluang_dasar.peluang_dasar, peluang_dasar.parameter,
          peluang_dasar.LEVEL, peluang_dasar.domain_parameter),
    Jenis(bilang_benda_awal.TEMPLATE_ID, bilang_benda_awal.bilang_benda_awal,
          bilang_benda_awal.parameter, bilang_benda_awal.LEVEL,
          bilang_benda_awal.domain_parameter),
    Jenis(tambah_kurang_20.TEMPLATE_ID, tambah_kurang_20.tambah_kurang_20,
          tambah_kurang_20.parameter, tambah_kurang_20.LEVEL,
          tambah_kurang_20.domain_parameter),
    Jenis(tambah_kurang_100.TEMPLATE_ID, tambah_kurang_100.tambah_kurang_100,
          tambah_kurang_100.parameter, tambah_kurang_100.LEVEL,
          tambah_kurang_100.domain_parameter),
    Jenis(unsur_bangun_datar.TEMPLATE_ID, unsur_bangun_datar.unsur_bangun_datar,
          unsur_bangun_datar.parameter, unsur_bangun_datar.LEVEL,
          unsur_bangun_datar.domain_parameter),
    Jenis(pecahan_senilai_desimal.TEMPLATE_ID, pecahan_senilai_desimal.pecahan_senilai_desimal,
          pecahan_senilai_desimal.parameter, pecahan_senilai_desimal.LEVEL,
          pecahan_senilai_desimal.domain_parameter),
    Jenis(luas_petak_volume_kubus.TEMPLATE_ID, luas_petak_volume_kubus.luas_petak_volume_kubus,
          luas_petak_volume_kubus.parameter, luas_petak_volume_kubus.LEVEL,
          luas_petak_volume_kubus.domain_parameter),
    Jenis(ciri_komposisi_bangun.TEMPLATE_ID, ciri_komposisi_bangun.ciri_komposisi_bangun,
          ciri_komposisi_bangun.parameter, ciri_komposisi_bangun.LEVEL,
          ciri_komposisi_bangun.domain_parameter),
    Jenis(keliling_gabungan.TEMPLATE_ID, keliling_gabungan.keliling_gabungan,
          keliling_gabungan.parameter, keliling_gabungan.LEVEL,
          keliling_gabungan.domain_parameter),
    Jenis(pecahan_bilangan_asli_desimal.TEMPLATE_ID, pecahan_bilangan_asli_desimal.pecahan_bilangan_asli_desimal,
          pecahan_bilangan_asli_desimal.parameter, pecahan_bilangan_asli_desimal.LEVEL,
          pecahan_bilangan_asli_desimal.domain_parameter),
)
_PER_ID = {j.template_id: j for j in JENIS}
if len(_PER_ID) != len(JENIS):
    raise RuntimeError("template_id jenis Matematika Awal tidak unik")
LEVEL_TOPIK = tuple(sorted({lv for j in JENIS for lv in j.level}))
PROFIL_LEVEL = {level: {} for level in LEVEL_TOPIK}


def _komposisi(level: str) -> tuple:
    """Jenis level itu, diulang bergiliran sampai JUMLAH_SOAL_LEMBAR."""
    jenis = [j.template_id for j in JENIS if level in j.level]
    return tuple(jenis[i % len(jenis)] for i in range(JUMLAH_SOAL_LEMBAR))


KOMPOSISI = {level: _komposisi(level) for level in LEVEL_TOPIK}


def _jenis(template_id: str, level: str) -> Jenis:
    if template_id not in _PER_ID:
        raise KeyError(template_id)
    jenis = _PER_ID[template_id]
    if level not in jenis.level:
        raise ValueError(f"jenis {template_id} tidak tersedia untuk level {level!r}")
    return jenis


def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    return _jenis(template_id, level).sampler(rng, level)


def domain_parameter(template_id: str, level: str) -> tuple:
    """Seluruh parameter sah satu jenis di satu level; dict baru setiap panggilan."""
    return _jenis(template_id, level).domain_parameter(level)


daftarkan(Topik(
    id=TOPIK_ID,
    nama="Matematika Awal",
    judul_lembar="Latihan Matematika Awal",
    judul_penilaian="Penilaian — Matematika Awal",
    templates={j.template_id: j.fungsi for j in JENIS},
    komposisi=KOMPOSISI,
    profil=PROFIL_LEVEL,
    judul_bagian={BAGIAN: "Matematika Awal"},
    parameter_untuk=_parameter,
    unik_per_lembar=True,
    domain_parameter=domain_parameter,
    hanya_manual=True,
))
