"""Baseline perilaku SEBELUM topik bilangan-sekolah ada (fa03734, flag tak ada).

Nilai beku di bawah direkam dari pohon yang belum diubah dengan skrip yang
mengukur hal yang sama lewat jalur kode yang sama (komposisi Campuran, daftar
Latihan manual, pemilih siklus, katalog Pendamping, katalog target mastery).
Kalau salah satu berubah saat sakelar mati, perilaku aplikasi berubah: cari
penyebabnya, jangan perbarui angkanya.

Cara menurunkan sidik: JSON kanonik (urut kunci, separator rapat, tanpa escape
non-ASCII) lalu 20 hex pertama SHA-256.
"""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

TOPIK = "bilangan-sekolah"
TEMPLATE = "nilai_tempat_besar"

SIDIK_BASELINE = {
    "campuran_komposisi": "c23df069c56127270ca6",
    "campuran_writer": "c23df069c56127270ca6",
    "campuran_templates": "af2e0863f001b153b99a",
    "daftar_topik_latihan": "32b5a5761cb26441d466",
    "katalog_penawaran": "af2e0863f001b153b99a",
    "katalog_target": "ff0d46793b3634a8a29e",
    "lintas_topik": "daa3ca1701bcbeb6abdc",
    "lintas_topik_40": "f1837d6c7e62c8384cfd",
    "override_html": "5b232cdfe19b16616717",
    "pemilih_pemetaan_html": "96c934284b47c4d5c3c0",
}
# Topik yang sah bertambah di daftar Latihan manual hanya saat sakelar hidup.
DAFTAR_LATIHAN_BASELINE = [
    "aritmatika-lanjut", "aritmetika-dasar", "berhitung-sekolah", "campuran",
    "geometri-datar", "geometri-ruang", "kombinatorik", "logika", "pengukuran",
    "pola-bilangan", "statistika", "teori-bilangan",
]


def sidik(nilai) -> str:
    teks = json.dumps(nilai, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()[:20]


def ukur() -> dict:
    """Nilai mentah per kunci baseline, dihitung dari kode yang berjalan."""
    import assistant_catalog
    import learning_cycle_ui
    import learning_sessions
    import mastery_catalog
    import question_context
    import question_variants_ui
    import topics
    from templates import LEVEL, LEVEL_TINGKAT

    campuran = topics.ambil("campuran")
    return {
        "campuran_komposisi": {l: list(v) for l, v in campuran.komposisi.items()},
        "campuran_writer": {l: list(v) for l, v in (campuran.komposisi_writer or {}).items()},
        "campuran_templates": sorted(campuran.templates),
        "daftar_topik_latihan": question_context.daftar_topik_latihan(),
        "katalog_penawaran": [
            t.id for t in assistant_catalog.buat_katalog(untuk_penawaran=True).template],
        "katalog_target": {
            l: [t.id for t in mastery_catalog.katalog_target(l)] for l in LEVEL},
        "lintas_topik": {
            l: learning_sessions._template_lintas_topik(l, 10) for l in LEVEL_TINGKAT},
        "lintas_topik_40": {
            l: learning_sessions._template_lintas_topik(l, 40) for l in LEVEL_TINGKAT},
        "override_html": {
            l: learning_cycle_ui._override(
                SimpleNamespace(tindakan="intervensi", putaran=SimpleNamespace(level=l)), 7)
            for l in LEVEL_TINGKAT},
        "pemilih_pemetaan_html": question_variants_ui.pemilih_pemetaan("uji"),
    }


def sidik_terukur() -> dict:
    return {k: sidik(v) for k, v in ukur().items()}
