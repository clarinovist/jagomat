"""Off-site VPS pasca-tinjauan: tar dari manifest tanpa TOCTOU, sapuan sisa, flag uji, isolasi -I."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

import pytest

from offsite_kit import ENV_RAHASIA, SCRIPTS
from offsite_lingkungan import (_lingkungan_uji, jalankan, kunci, lingkungan, s3)  # noqa: F401

import backup_offsite_vps as vps  # noqa: E402

HARI = 86400
RAHASIA_LUAR = "ISI-RAHASIA-DI-LUAR-BUNDLE-91c2"


def _nama_tar(path: Path) -> list:
    with tarfile.open(str(path), "r:gz") as tar:
        return sorted(m.name for m in tar.getmembers())


# --- L7: tar hanya dari manifest, dibuka O_NOFOLLOW ---

def test_tar_hanya_memuat_berkas_manifest_dan_direktori_bundle(lingkungan, tmp_path):
    bundle = lingkungan["bundle"]
    (bundle / "liar.txt").write_text("bukan bagian manifest")
    tujuan = tmp_path / "b.tar.gz"

    vps.buat_tar(bundle, tujuan)

    nama = _nama_tar(tujuan)
    assert f"{bundle.name}/liar.txt" not in nama
    assert nama == sorted([bundle.name, f"{bundle.name}/manifest.json",
                           f"{bundle.name}/latihan.db", f"{bundle.name}/sandi.json"])


def test_tar_menolak_berkas_manifest_yang_symlink_walau_lolos_validasi(lingkungan, capsys):
    bundle = lingkungan["bundle"]
    salinan = bundle / "latihan.db.asli"
    os.replace(bundle / "latihan.db", salinan)
    (bundle / "latihan.db").symlink_to(salinan)  # is_file() True dan hash sama: validasi lolos

    kode, out, err = jalankan(lingkungan, capsys)

    assert kode == 1 and out == "" and "bukan berkas biasa" in err
    assert lingkungan["s3"].payload_diterima == []


def test_berkas_diganti_symlink_setelah_validasi_tidak_terunggah(lingkungan, capsys, monkeypatch, tmp_path):
    luar = tmp_path / "luar.txt"
    luar.write_text(RAHASIA_LUAR)
    asli = vps.validasi_bundle

    def validasi_lalu_tukar(bundle):
        asli(bundle)
        (bundle / "sandi.json").unlink()
        (bundle / "sandi.json").symlink_to(luar)  # jendela TOCTOU

    monkeypatch.setattr(vps, "validasi_bundle", validasi_lalu_tukar)

    kode, _, err = jalankan(lingkungan, capsys)

    assert kode == 1 and "bukan berkas biasa" in err
    assert lingkungan["s3"].payload_diterima == []
    assert [m for m, _ in lingkungan["s3"].permintaan if m == "PUT"] == []


def test_tar_menolak_nama_manifest_tidak_polos(lingkungan, tmp_path):
    bundle = lingkungan["bundle"]
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["berkas"][0]["nama"] = "../keluar.db"
    (bundle / "manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(vps.GalatOffsite):
        vps.buat_tar(bundle, tmp_path / "b.tar.gz")


# --- L8: rmtree tidak diam-diam, sapuan sisa plaintext ---

def test_kegagalan_rmtree_dicatat_ke_stderr_tanpa_rahasia(lingkungan, capsys, monkeypatch):
    def gagal(*_a, **_k):
        raise PermissionError(f"/tmp/offsite-x/{ENV_RAHASIA}")

    import offsite_kerja
    from types import SimpleNamespace
    monkeypatch.setattr(offsite_kerja, "shutil", SimpleNamespace(rmtree=gagal))

    kode, _, err = jalankan(lingkungan, capsys)

    assert kode == 0 and "tidak terhapus" in err and "PermissionError" in err
    assert ENV_RAHASIA not in err


def _sisa(induk: Path, nama: str, *, umur_hari: float = 2, mode: int = 0o700) -> Path:
    path = induk / nama
    path.mkdir()
    (path / "sandi.sesi").write_text("sisa")
    os.chmod(path, mode)
    lampau = time.time() - umur_hari * HARI
    os.utime(path, (lampau, lampau))
    return path


def test_sapu_hanya_menghapus_direktori_offsite_milik_uid_mode_0700_dan_tua(tmp_path):
    import offsite_kerja
    induk = tmp_path / "tmp"
    induk.mkdir()
    tua = _sisa(induk, "offsite-ab12cd_9")
    baru = _sisa(induk, "offsite-ab12cd98", umur_hari=0.5)
    longgar = _sisa(induk, "offsite-zz99yy88", mode=0o755)
    pola_lain = _sisa(induk, "offsite-ab12cd98-lain")
    bukan_offsite = _sisa(induk, "lain-ab12cd98")
    sasaran = _sisa(induk, "sasaran-asli")
    tautan = induk / "offsite-tautan12"
    tautan.symlink_to(sasaran, target_is_directory=True)
    berkas = induk / "offsite-berkas12"
    berkas.write_text("x")
    os.utime(berkas, (time.time() - 5 * HARI,) * 2)

    jumlah = offsite_kerja.sapu_sisa(induk, time.time(), uid=os.geteuid())

    assert jumlah == 1 and not tua.exists()
    for aman in (baru, longgar, pola_lain, bukan_offsite, sasaran, tautan, berkas):
        assert aman.exists() or aman.is_symlink()
    assert (sasaran / "sandi.sesi").read_text() == "sisa"


def test_sapu_tidak_menghapus_milik_uid_lain(tmp_path):
    import offsite_kerja
    tua = _sisa(tmp_path, "offsite-ab12cd98")

    jumlah = offsite_kerja.sapu_sisa(tmp_path, time.time(), uid=os.geteuid() + 1)

    assert jumlah == 0 and tua.exists()


def test_sapu_induk_tidak_ada_tidak_gagal(tmp_path):
    import offsite_kerja

    assert offsite_kerja.sapu_sisa(tmp_path / "tidak-ada", time.time(), uid=os.geteuid()) == 0


def test_run_menyapu_sisa_lama_di_tmp_dir_dan_melaporkannya(lingkungan, capsys, tmp_path):
    pakai = tmp_path / "sementara"
    pakai.mkdir()
    sisa = _sisa(pakai, "offsite-ab12cd98")

    kode, _, err = jalankan(lingkungan, capsys, "--tmp-dir", str(pakai))

    assert kode == 0 and not sisa.exists() and "1" in err and "sisa" in err


# --- L12: flag uji hanya bersama env uji ---

@pytest.mark.parametrize("nilai", [None, "0", ""])
def test_flag_uji_pemilik_env_ditolak_tanpa_env_uji(lingkungan, capsys, monkeypatch, nilai):
    if nilai is None:
        monkeypatch.delenv("OSN_OFFSITE_UJI", raising=False)
    else:
        monkeypatch.setenv("OSN_OFFSITE_UJI", nilai)

    kode, out, err = jalankan(lingkungan, capsys)

    assert kode == 1 and out == "" and "OSN_OFFSITE_UJI" in err
    assert lingkungan["s3"].permintaan == []


# --- INFO: python3 -I (mode terisolasi) tetap dapat mengimpor modul pendamping ---

@pytest.mark.parametrize("skrip", ["backup_offsite_vps.py", "pulihkan_offsite.py"])
def test_skrip_berjalan_di_mode_terisolasi_python_i(skrip):
    hasil = subprocess.run([sys.executable, "-I", str(SCRIPTS / skrip), "--help"],
                           capture_output=True, text=True, timeout=60, cwd="/")

    assert hasil.returncode == 0 and "usage" in hasil.stdout.lower(), hasil.stderr
