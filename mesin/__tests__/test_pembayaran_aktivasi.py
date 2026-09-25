"""Aktivasi pembayaran: wiring runtime di dispatch web dan entry worker di image.

Semua state sintetis (DB tmp, berkas rahasia tmp); tanpa socket keluar, tanpa
kredensial nyata, dan tanpa menyentuh path produksi /run/secrets.
"""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import admin_subscription
import subscription_produksi as prod
from http_test_kit import ServerUji

AKAR = Path(__file__).resolve().parents[1]
SHIM = AKAR.parent / "scripts" / "rekonsiliasi_langganan.py"

ARTEFAK = {"versi": 1, "revisi": "a" * 40, "digest": "sha256:" + "b" * 64,
           "kontrak": "c" * 64, "pasangan_terverifikasi": True, "kompatibel": True,
           "mode": "migrasi"}


@pytest.fixture
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def tulis_privat(path, isi):
    path.write_text(isi)
    os.chmod(path, 0o600)
    return path


def test_dispatch_gagal_pasang_tetap_fail_closed_dan_situs_normal(server, tmp_path, monkeypatch):
    """Tanpa secret/artefak sah: percobaan sekali, runtime tetap OFF, situs hidup."""
    monkeypatch.setattr(prod, "BERKAS_RAHASIA_BAWAAN", str(tmp_path / "tidak-ada.conf"))
    monkeypatch.setattr(prod, "BERKAS_RECOVERY_BAWAAN", str(tmp_path / "tidak-ada.json"))
    kode, _, _ = server.minta("/")
    assert kode == 200
    assert getattr(server.server, "pembayaran_runtime", None) is None
    assert getattr(server.server, "_pembayaran_dicoba", False) is True
    kode2, _, _ = server.minta("/masuk")
    assert kode2 == 200


def test_dispatch_memasang_runtime_saat_secret_dan_artefak_sah(server, tmp_path, monkeypatch):
    rahasia = tulis_privat(tmp_path / "rahasia.conf",
                           "merchant=M_SINTETIS\nserver_key=Mid-server-SINTETIS\n")
    recovery = tulis_privat(tmp_path / "recovery.json", json.dumps(ARTEFAK))
    monkeypatch.setattr(prod, "BERKAS_RAHASIA_BAWAAN", str(rahasia))
    monkeypatch.setattr(prod, "BERKAS_RECOVERY_BAWAAN", str(recovery))
    kode, _, _ = server.minta("/")
    assert kode == 200
    runtime = getattr(server.server, "pembayaran_runtime", None)
    assert isinstance(runtime, admin_subscription.RuntimePembayaran)
    assert runtime.config.lingkungan == "production" and runtime.config.merchant == "M_SINTETIS"
    assert runtime.kesiapan == {"provider_produksi": True, "callback": True,
                                "recovery": True, "kebijakan": True}
    assert "Mid-server" not in repr(runtime)


def test_cli_kanonis_dapat_dijalankan_dari_direktori_mesin():
    """Simulasi invokasi container: `python rekonsiliasi_langganan.py --help`."""
    hasil = subprocess.run([sys.executable, "-B", "rekonsiliasi_langganan.py", "--help"],
                           cwd=AKAR, capture_output=True, text=True, timeout=60,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert hasil.returncode == 0, hasil.stderr
    assert "--admin-db" in hasil.stdout and "--rahasia" in hasil.stdout
    assert "--lease" in hasil.stdout


def test_shim_scripts_meneruskan_ke_modul_kanonis():
    spec = importlib.util.spec_from_file_location("rekonsiliasi_shim", SHIM)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    import rekonsiliasi_langganan as kanonis
    assert modul.main is kanonis.main
    assert modul.prod is prod
