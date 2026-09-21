"""Audit repeatable lengkap pada komposisi, tanpa menyulap sampel jadi kurikulum."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from question_context import daftar_konteks

AKAR = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("audit_skill_demands", AKAR / "scripts/audit_skill_demands.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_audit_semua_pasangan_dan_pilot_bukan_penyebut():
    hasil = audit.audit(3)
    baris = hasil["konteks"]
    assert {b["konteks_id"] for b in baris} == {k.id for k in daftar_konteks()}
    assert hasil["jumlah_soal"] == hasil["jumlah_pasangan"] * 3
    assert hasil["jumlah_pola"] == len({k.template_id for k in daftar_konteks()})
    for b in baris:
        assert b["prasyarat_terverifikasi"] is None
        assert b["kecocokan_intervensi_per_varian"] == "belum disahkan"
        assert b["signature_sha256"] and b["render_sha256"]
        assert b["kartu_rumus"] and b["sumber_template"]["sha256"]
    pilot = [b for b in baris if b["template_id"] == "keliling_luas_datar"]
    assert len(pilot) == 4
    assert all(b["tuntutan_draft"] for b in pilot)
    assert all("geometri_datar-v1" in b["representasi_tersedia_sampel"] for b in pilot)
    assert all(b["rentang_angka_sampel"] and b["intervensi_k_tersedia"] for b in pilot)
    assert all("varian" in b["kategori_parameter_sampel"] for b in pilot)
    assert "penyebut" not in hasil
    assert any("penyebut" in batas for batas in hasil["batas"])


def test_determinisme_cli_antarproses_dengan_hashseed_berbeda():
    keluaran = []
    for seed in ("1", "731"):
        env = dict(os.environ, PYTHONHASHSEED=seed, OSN_MATEMATIKA_VERSI="2")
        keluaran.append(subprocess.check_output(
            [sys.executable, "-B", str(AKAR / "scripts/audit_skill_demands.py"), "--jumlah-seed", "1"],
            cwd=str(AKAR), env=env,
        ))
    assert keluaran[0] == keluaran[1]
    assert json.loads(keluaran[0])["versi_generator"] == 2


@pytest.mark.parametrize("jumlah", (0, 501, True, 2.5))
def test_jumlah_seed_invalid_gagal_terlihat(jumlah):
    with pytest.raises(ValueError):
        audit.audit(jumlah)
