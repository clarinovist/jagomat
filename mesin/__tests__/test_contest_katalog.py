"""Kelengkapan katalog Latihan Lomba: cukup template, tersebar di topik, jenis, dan tingkat."""
from collections import Counter
import random

import contest_core as C
import contest_session as S
import contest_templates

KATALOG = contest_templates.katalog()
TOTAL_MIN, TOTAL_MAKS = 30, 40
PER_TOPIK_MIN = 7
ISIAN_MIN = 5
TOPIK_BERISIAN_MIN = 3
PER_TINGKAT_MIN = 6
INGGRIS_MIN, INGGRIS_MAKS = 1, 3


def test_jumlah_template_di_rentang_rencana():
    assert TOTAL_MIN <= len(KATALOG) <= TOTAL_MAKS, len(KATALOG)


def test_setiap_topik_punya_cukup_template():
    hitung = Counter(t.topik for t in KATALOG)
    for topik in C.TOPIK:
        assert hitung[topik] >= PER_TOPIK_MIN, (topik, hitung[topik])


def test_cukup_template_isian_dan_tersebar_di_beberapa_topik():
    isian = [t for t in KATALOG if t.jenis == C.JENIS_ISIAN]
    assert len(isian) >= ISIAN_MIN
    assert len({t.topik for t in isian}) >= TOPIK_BERISIAN_MIN


def test_empat_puluh_sesi_berturut_cukup_soal_tanpa_mengulang_lima_sesi_terakhir():
    riwayat = []
    for seed in range(40):
        terlarang = frozenset().union(*riwayat[-S.RIWAYAT_SESI:]) if riwayat else frozenset()
        sesi = S.rakit_sesi(seed, KATALOG, terlarang)
        tanda = frozenset(C.tanda_tangan(b.soal) for b in sesi.butir)
        assert not tanda & terlarang
        riwayat.append(tanda)


def test_template_berbahasa_inggris_sedikit_seperti_di_lomba():
    inggris = [t for t in KATALOG if C.buat_soal(t, random.Random(1)).inggris]
    assert INGGRIS_MIN <= len(inggris) <= INGGRIS_MAKS, [t.id for t in inggris]


def test_setiap_tingkat_kesulitan_terwakili_cukup():
    hitung = Counter(t.tingkat for t in KATALOG)
    for tingkat in C.TINGKAT:
        assert hitung[tingkat] >= PER_TINGKAT_MIN, (tingkat, hitung[tingkat])


KELUARGA_DIHARAPKAN = {
    "ops_fam_dua_langkah": {"ops_cerita_dua_langkah", "ops_inggris_dua_langkah"},
    "ops_fam_jumlah_selisih": {"ops_jumlah_selisih", "ops_inggris_jumlah_selisih"},
    "ukur_fam_selisih_jam": {"ukur_lama_kegiatan", "ukur_lama_menit"},
    "ukur_fam_kalender": {"ukur_kalender_hari", "ukur_kalender_n_hari_lagi"},
}


def test_template_sejenis_dikelompokkan_dalam_keluarga():
    ditemukan = {}
    for template in KATALOG:
        if template.keluarga:
            ditemukan.setdefault(template.keluarga, set()).add(template.id)
    for nama, anggota in KELUARGA_DIHARAPKAN.items():
        assert ditemukan.get(nama) == anggota, (nama, ditemukan.get(nama))


TUMPANG_TINDIH_MAKS_RATA2 = 0.5


def test_rotasi_membuat_sesi_berurutan_jarang_memakai_jenis_soal_yang_sama():
    riwayat_tanda, riwayat_template, tumpang = [], [], []
    for seed in range(40):
        terlarang = frozenset().union(*riwayat_tanda[-S.RIWAYAT_SESI:]) if riwayat_tanda else frozenset()
        hindari = frozenset().union(*riwayat_template[-S.ROTASI_SESI:]) if riwayat_template else frozenset()
        sesi = S.rakit_sesi(seed, KATALOG, terlarang, template_dihindari=hindari)
        template = frozenset(b.soal.template_id for b in sesi.butir)
        if riwayat_template:
            tumpang.append(len(template & riwayat_template[-1]))
        riwayat_tanda.append(frozenset(C.tanda_tangan(b.soal) for b in sesi.butir))
        riwayat_template.append(template)
    assert sum(tumpang) / len(tumpang) <= TUMPANG_TINDIH_MAKS_RATA2, tumpang
