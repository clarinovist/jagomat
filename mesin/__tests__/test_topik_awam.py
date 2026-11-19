"""Label topik awam: satu sumber untuk layar anak dan ringkasan orang tua."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis_skor  # noqa: E402
import cek_pages  # noqa: E402
import topik_awam  # noqa: E402
import topics  # noqa: E402


def test_label_awam_mencakup_semua_topik_cek_dan_unik():
    ids = cek_gratis_skor.semua_topik_cek()
    assert set(ids) == set(topik_awam.NAMA_AWAM)
    assert len(set(topik_awam.NAMA_AWAM.values())) == len(ids)


@pytest.mark.parametrize("topik_id", cek_gratis_skor.semua_topik_cek())
def test_nama_resmi_lama_dipetakan_ke_label_awam(topik_id):
    assert topik_awam.dari_nama_lama(topics.ambil(topik_id).nama) == topik_awam.nama(topik_id)


def test_label_asing_dibiarkan_apa_adanya():
    assert topik_awam.dari_nama_lama("Topik Warisan") == "Topik Warisan"


def test_blok_ringkasan_memetakan_nama_tersimpan_lama():
    """Hasil lama di DB menyimpan nama resmi; render wajib memakai nama baru."""
    html = cek_pages._blok_ringkasan({
        "kuat": ["Aritmatika Lanjut"],
        "perlu": ["Berhitung Dasar Sekolah"],
    })
    assert "Aritmetika lanjut" in html and "Berhitung" in html
    assert "Aritmatika Lanjut" not in html
    assert "Berhitung Dasar Sekolah" not in html
