"""Tahap 1-dari-6 hanya ditampilkan bila reducer memang berada di tahap itu; pemulihan sumber tidak berpura-pura tahap 1."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import learning_cycle_ui as UI
import profile_home
from learning_cycle import BuktiSiklus, RencanaBelajar

BUKTI = BuktiSiklus(9, "P3")


def _rencana(tindakan):
    return RencanaBelajar(tindakan, "uji")


def test_pulihkan_sumber_tidak_menunjuk_tahap_apa_pun():
    posisi = profile_home.posisi(_rencana("pulihkan_sumber"), BUKTI, "Anak")
    assert "dari 6" not in posisi and 'aria-current="step"' not in posisi
    assert "Posisi Anak" in posisi and "belum bisa ditunjukkan" in posisi
    alur = UI._alur_rencana(_rencana("pulihkan_sumber"), BUKTI)
    assert "Tahap sekarang" not in alur and 'aria-current="step"' not in alur
    assert UI._kalimat_tahap(_rencana("pulihkan_sumber"), BUKTI) == (
        "Tahap belum bisa ditunjukkan sampai sumber fokus dipulihkan. ")


@pytest.mark.parametrize("tindakan,nomor", [
    ("pemetaan", 1), ("pilih_variasi", 1), ("intervensi", 2), ("penguatan", 3),
    ("evaluasi", 4), ("checkpoint", 5), ("mixed_maintenance", 6), ("eskalasi", 6),
])
def test_tindakan_bertahap_tetap_sama(tindakan, nomor):
    posisi = profile_home.posisi(_rencana(tindakan), BUKTI, "Anak")
    assert f"tahap {nomor} dari 6" in posisi
    assert posisi.count('aria-current="step"') == 1
    assert UI._kalimat_tahap(_rencana(tindakan), BUKTI) == (
        f"Tahap sekarang: {UI._LABEL_TAHAP[nomor - 1]} ({nomor} dari 6). ")
