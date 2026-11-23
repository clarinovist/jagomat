"""Soal pilihan ganda 4 opsi untuk Latihan Harian, dibuat murni dari satu template, level, dan seed.

Tanpa DB dan tanpa sesi: tidak memakai `sesi_soal_id` DB. Memakai pembangkit yang ada (`generator.buat_soal`,
`choice_generation.kandidat`, `multiple_choice.buat_pilihan`) dan hasilnya wajib lolos validasi semantik
`multiple_choice.validasi_kebenaran`: empat opsi berbeda secara matematis dan TEPAT SATU benar. Kekurangan
pengecoh selalu ditolak (`SoalTidakLayak`), tidak pernah ditambal angka rekaan.

Jenis soal dikeluarkan dari Latihan Harian bila tidak bisa dibuat PG 4 opsi sah: pembahasan kosong, kebijakan
lima opsi tertanam (jaring-jaring, benar/salah), atau pengecoh terkurasi kurang dari tiga (mis. hanya tiga
simbol perbandingan). `audit_template` mengukur ini deterministik dari sampel seed tetap.

Acak hanya dari `random.Random` berbasis seed/string; tidak memakai `hash()`.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Dict, Tuple

import choice_generation
import generator
import multiple_choice
import question_views
import visual_contract

KEBIJAKAN_EMPAT = "empat-v1"
KEBIJAKAN_TERTANAM = "tertanam-lima-v1"
JUMLAH_OPSI = 4
JUMLAH_PENGECOH = JUMLAH_OPSI - 1
SAMPEL_AUDIT = 40
SEED_AUDIT_AWAL = 7001
AMBANG_LOLOS = 0.2  # jenis soal dipakai bila minimal seperlima sampel menghasilkan PG 4 opsi sah
_SIDIK = re.compile(r"[0-9a-f]{64}")

ALASAN_TANPA_PEMBAHASAN = "tanpa_pembahasan"
ALASAN_LIMA_OPSI = "lima_opsi_tertanam"
ALASAN_PENGECOH_KURANG = "pengecoh_kurang"
ALASAN_GAGAL_BUAT = "gagal_buat"


class SoalTidakLayak(ValueError):
    """Satu seed tidak menghasilkan PG 4 opsi sah; `alasan` salah satu konstanta ALASAN_*."""

    def __init__(self, alasan: str):
        super().__init__(alasan)
        self.alasan = alasan


@dataclass(frozen=True)
class SoalPg:
    """Snapshot satu soal PG 4 opsi. `kunci_indeks` dan `pembahasan` hanya untuk server (bukan untuk halaman soal)."""

    template_id: str
    topik_id: str
    level: str
    tanda_tangan: str
    penyajian_json: str
    opsi: Tuple[str, ...]
    kunci_indeks: int
    pembahasan: str


def buat_soal_pg(topik_id: str, template_id: str, level: str, seed: int) -> SoalPg:
    """PG 4 opsi sah dari (topik, template, level, seed), atau `SoalTidakLayak`. Deterministik."""
    try:
        soal = generator.buat_soal(template_id, seed, level, topik_id)
    except ValueError as galat:
        raise SoalTidakLayak(ALASAN_GAGAL_BUAT) from galat
    if not soal.pembahasan.strip():
        raise SoalTidakLayak(ALASAN_TANPA_PEMBAHASAN)
    kebijakan, jenis = choice_generation.kebijakan_soal(soal)
    if kebijakan == KEBIJAKAN_TERTANAM:
        raise SoalTidakLayak(ALASAN_LIMA_OPSI)
    try:
        _k, _j, pengecoh = choice_generation.kandidat(soal, JUMLAH_PENGECOH)
    except ValueError as galat:
        raise SoalTidakLayak(ALASAN_PENGECOH_KURANG) from galat
    penyajian = question_views.penyajian_dari_soal(soal)
    if not _SIDIK.fullmatch(penyajian.fingerprint_penyajian):
        raise SoalTidakLayak(ALASAN_GAGAL_BUAT)
    try:
        pilihan = multiple_choice.buat_pilihan(
            sesi_soal_id=1, fingerprint_pertanyaan=penyajian.fingerprint_penyajian,
            kebijakan=KEBIJAKAN_EMPAT, jenis=jenis, kunci=soal.kunci, pengecoh=tuple(pengecoh),
            seed=seed, identitas=soal.tanda_tangan)
    except ValueError as galat:
        raise SoalTidakLayak(ALASAN_PENGECOH_KURANG) from galat
    teks = tuple(o.teks for o in pilihan.opsi)
    benar = [i for i, o in enumerate(pilihan.opsi) if o.nilai == soal.kunci]
    if len(teks) != JUMLAH_OPSI or len(benar) != 1:
        raise SoalTidakLayak(ALASAN_PENGECOH_KURANG)
    return SoalPg(
        template_id=template_id, topik_id=topik_id, level=level, tanda_tangan=soal.tanda_tangan,
        penyajian_json=visual_contract.serialisasi_penyajian(penyajian), opsi=teks,
        kunci_indeks=benar[0], pembahasan=soal.pembahasan.strip())


@dataclass(frozen=True)
class LaporanTemplate:
    jumlah: int
    lolos: int
    alasan: Tuple[Tuple[str, int], ...]  # (alasan, banyak) untuk sampel yang gagal, urut alasan

    @property
    def layak(self) -> bool:
        return self.jumlah > 0 and self.lolos / self.jumlah >= AMBANG_LOLOS


@lru_cache(maxsize=None)
def audit_template(topik_id: str, template_id: str, level: str) -> LaporanTemplate:
    """Ukur berapa dari `SAMPEL_AUDIT` seed tetap yang jadi PG 4 opsi sah. Murni per argumen, di-cache per proses."""
    lolos = 0
    gagal: Dict[str, int] = {}
    for seed in range(SEED_AUDIT_AWAL, SEED_AUDIT_AWAL + SAMPEL_AUDIT):
        try:
            buat_soal_pg(topik_id, template_id, level, seed)
            lolos += 1
        except SoalTidakLayak as galat:
            gagal[galat.alasan] = gagal.get(galat.alasan, 0) + 1
    return LaporanTemplate(SAMPEL_AUDIT, lolos, tuple(sorted(gagal.items())))
