"""Skrip off-site Mac: tidak mengunggah bundle basi dan selalu memberi alert saat gagal.

ssh/rclone/openssl diganti perintah tiruan; tidak ada jaringan, R2, atau VPS sungguhan.
"""
import datetime as dt
import os
from pathlib import Path
import subprocess

import pytest

SKRIP = Path(__file__).resolve().parents[2] / "scripts" / "backup_offsite_mac.sh"
WIB = dt.timezone(dt.timedelta(hours=7))


def _perintah(path: Path, isi: str) -> None:
    path.write_text("#!/bin/bash\n" + isi, encoding="utf-8")
    path.chmod(0o755)


def _jalankan(tmp_path, *, id_backup, kunci=True):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # ssh pertama (cari ID) mencetak ID tiruan; panggilan lain tidak pernah tercapai di tes ini.
    _perintah(bin_dir / "ssh", f'echo "{id_backup}"\n')
    _perintah(bin_dir / "rclone", f'echo "$@" >> "{tmp_path}/rclone.log"\n')
    _perintah(bin_dir / "openssl", f'echo "$@" >> "{tmp_path}/openssl.log"\n')
    alert = tmp_path / "alert"
    _perintah(alert, f'echo "$1" >> "{tmp_path}/alert.log"\n')
    berkas_kunci = tmp_path / "offsite.key"
    if kunci:
        berkas_kunci.write_text("kunci-tes\n", encoding="utf-8")
    env = {
        "HOME": str(tmp_path),
        "PATH": os.environ["PATH"],
        "OSN_OFFSITE_PATH_AWAL": str(bin_dir),
        "OSN_OFFSITE_KUNCI": str(berkas_kunci),
        "OSN_OFFSITE_TMP": str(tmp_path / "scratch"),
        "OSN_ALERT": str(alert),
    }
    hasil = subprocess.run(
        ["bash", str(SKRIP)], env=env, capture_output=True, text=True, timeout=30)
    return hasil


def _id(jam_lalu: float) -> str:
    return (dt.datetime.now(WIB) - dt.timedelta(hours=jam_lalu)).strftime("%Y%m%d-%H%M%S")


def _dibaca(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_menolak_dan_mengalert_bundle_terbaru_yang_basi(tmp_path):
    hasil = _jalankan(tmp_path, id_backup=_id(jam_lalu=48))

    assert hasil.returncode == 1
    assert "terlalu lama" in hasil.stderr
    assert "GAGAL" in _dibaca(tmp_path / "alert.log")
    assert _dibaca(tmp_path / "rclone.log") == ""
    assert _dibaca(tmp_path / "openssl.log") == ""


def test_id_tidak_sah_gagal_dan_mengalert(tmp_path):
    hasil = _jalankan(tmp_path, id_backup="bukan-id")

    assert hasil.returncode == 1
    assert "ID backup tidak sah" in hasil.stderr
    assert "GAGAL" in _dibaca(tmp_path / "alert.log")
    assert _dibaca(tmp_path / "rclone.log") == ""


def test_kunci_hilang_gagal_dan_mengalert(tmp_path):
    hasil = _jalankan(tmp_path, id_backup=_id(jam_lalu=1), kunci=False)

    assert hasil.returncode == 1
    assert "kunci enkripsi tidak ada" in hasil.stderr
    assert "GAGAL" in _dibaca(tmp_path / "alert.log")


def test_bundle_segar_lolos_pemeriksaan_umur(tmp_path):
    # ssh tiruan hanya mencetak ID, jadi langkah validasi/tar menghasilkan tar kosong dan
    # skrip gagal SESUDAH pemeriksaan umur; yang dibuktikan di sini: pesan basi tidak muncul.
    hasil = _jalankan(tmp_path, id_backup=_id(jam_lalu=1))

    assert "terlalu lama" not in hasil.stderr
    assert "ID backup tidak sah" not in hasil.stderr


def test_skrip_valid_dan_tanpa_rahasia():
    teks = SKRIP.read_text(encoding="utf-8")
    assert subprocess.run(["bash", "-n", str(SKRIP)]).returncode == 0
    for terlarang in ("BEGIN PRIVATE KEY", "AKIA", "access_key_id", "secret_access_key", "bot_token"):
        assert terlarang not in teks
    assert os.access(SKRIP, os.X_OK)
