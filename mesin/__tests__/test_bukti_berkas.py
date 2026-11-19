"""Penyimpanan berkas bukti transfer: folder khusus, atomik, nama acak, tanpa path traversal."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import bukti_berkas as bb  # noqa: E402
from bukti_kit import JPEG, PDF, PNG, TEKS_PALSU  # noqa: E402

MESIN = Path(__file__).resolve().parent.parent


def _harus_ditolak(fungsi, nama):
    """Nama tidak sah harus ditolak SEBELUM menyentuh cakram; handle yang lolos ditutup."""
    with pytest.raises(bb.NamaBerkasTidakSah):
        hasil = fungsi(nama)
        if hasattr(hasil, "close"):
            hasil.close()


@pytest.fixture()
def folder(tmp_path, monkeypatch):
    jalur = tmp_path / "bukti"
    monkeypatch.setenv(bb.NAMA_ENV, str(jalur))
    return jalur


def test_simpan_menulis_isi_persis_dengan_nama_acak_32_hex(folder):
    nama = bb.simpan_berkas(JPEG)
    assert bb.POLA_NAMA.fullmatch(nama)
    assert (folder / nama).read_bytes() == JPEG
    assert bb.simpan_berkas(JPEG) != nama


def test_izin_folder_0700_dan_berkas_0600(folder):
    nama = bb.simpan_berkas(PDF)
    assert stat.S_IMODE(os.stat(folder).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(folder / nama).st_mode) == 0o600


def test_folder_longgar_yang_sudah_ada_diperketat(folder):
    folder.mkdir(mode=0o755)
    os.chmod(folder, 0o755)
    bb.simpan_berkas(PNG)
    assert stat.S_IMODE(os.stat(folder).st_mode) == 0o700


def test_tidak_meninggalkan_berkas_sementara(folder):
    bb.simpan_berkas(JPEG)
    assert [p.name for p in folder.iterdir() if p.name.startswith(".")] == []


def test_gagal_tulis_membersihkan_berkas_sementara(folder, monkeypatch):
    def _gagal(*_a, **_k):
        raise OSError("disk penuh")
    monkeypatch.setattr(bb.os, "replace", _gagal)
    with pytest.raises(OSError):
        bb.simpan_berkas(JPEG)
    assert list(folder.iterdir()) == []


def test_folder_default_di_samping_db_admin(tmp_path, monkeypatch):
    monkeypatch.delenv(bb.NAMA_ENV, raising=False)
    monkeypatch.setattr(admin_store, "BAWAAN", tmp_path / "admin-control.db")
    nama = bb.simpan_berkas(JPEG)
    assert (tmp_path / bb.NAMA_FOLDER / nama).read_bytes() == JPEG


def test_env_dibaca_saat_dipanggil_dan_tidak_menyentuh_folder_mesin(folder):
    bb.simpan_berkas(JPEG)
    assert bb.direktori_bukti() == folder
    assert not (MESIN / bb.NAMA_FOLDER).exists()


@pytest.mark.parametrize("nama", [
    "", "../x", "..", "a" * 31, "a" * 33, "A" * 32, "g" * 32, "a" * 32 + "/../b",
    "a" * 32 + ".jpg", "a" * 31 + "\x00", "a" * 32 + "\n", "../" + "a" * 32, None, 12, b"a" * 32,
])
def test_buka_dan_hapus_menolak_nama_tidak_valid(folder, nama):
    _harus_ditolak(bb.buka_berkas, nama)
    _harus_ditolak(bb.hapus_berkas, nama)
    _harus_ditolak(bb.jalur_berkas, nama)


def test_path_absolut_ke_berkas_lain_ditolak_dan_tidak_tersentuh(folder, tmp_path):
    luar = tmp_path / "luar-absolut"
    luar.write_bytes(b"x")
    _harus_ditolak(bb.buka_berkas, str(luar))
    _harus_ditolak(bb.hapus_berkas, str(luar))
    assert luar.read_bytes() == b"x"


def test_buka_berkas_membaca_isi_dan_nama_hilang_filenotfound(folder):
    nama = bb.simpan_berkas(PNG)
    with bb.buka_berkas(nama) as f:
        assert f.read() == PNG
    with pytest.raises(FileNotFoundError):
        bb.buka_berkas("0" * 32)


def test_buka_berkas_menolak_symlink(folder, tmp_path):
    folder.mkdir()
    luar = tmp_path / "rahasia.txt"
    luar.write_bytes(b"jangan dibaca")
    os.symlink(luar, folder / ("c" * 32))
    with pytest.raises(OSError):
        bb.buka_berkas("c" * 32)


def test_hapus_idempoten_dan_tidak_menyentuh_di_luar_folder(folder, tmp_path):
    nama = bb.simpan_berkas(JPEG)
    assert bb.hapus_berkas(nama) is True
    assert bb.hapus_berkas(nama) is False
    assert not (folder / nama).exists()
    luar = tmp_path / "luar"
    luar.write_bytes(b"x")
    with pytest.raises(bb.NamaBerkasTidakSah):
        bb.hapus_berkas("../luar")
    assert luar.exists()


def test_jalur_berkas_berada_di_dalam_folder(folder):
    nama = bb.simpan_berkas(PDF)
    assert bb.jalur_berkas(nama) == folder / nama


@pytest.mark.parametrize("isi,mime", [
    (JPEG, "image/jpeg"), (PNG, "image/png"), (PDF, "application/pdf"),
])
def test_mime_dari_magic_bytes(isi, mime):
    assert bb.mime_dari_isi(isi) == mime


@pytest.mark.parametrize("isi", [
    b"", TEKS_PALSU, b"\x89PNG", b"\x89PNG\r\n\x1a", b"%PDF", b"\xff\xd8", b"GIF89a....",
    b"RIFF\x00\x00\x00\x00WEBP", b"<svg></svg>", b"  %PDF-1.4",
])
def test_mime_ditolak_bila_magic_tidak_lengkap_atau_tipe_lain(isi):
    assert bb.mime_dari_isi(isi) is None


def test_folder_eksplisit_dipakai_tanpa_mengubah_folder_global(folder, tmp_path):
    lain = tmp_path / "folder-lain"
    lain.mkdir()
    nama = bb.simpan_berkas(JPEG)
    (lain / nama).write_bytes(b"salinan")
    assert bb.jalur_berkas(nama, lain) == lain / nama
    assert bb.hapus_berkas(nama, lain) is True
    assert not (lain / nama).exists() and (folder / nama).exists()
    assert bb.direktori_bukti() == folder


def test_folder_eksplisit_tetap_memvalidasi_nama(tmp_path):
    _harus_ditolak(lambda nama: bb.jalur_berkas(nama, tmp_path), "../x")
    _harus_ditolak(lambda nama: bb.hapus_berkas(nama, tmp_path), "a" * 31)


def test_awalan_sementara_dipublikasikan_untuk_retensi():
    assert bb.AWALAN_SEMENTARA == ".tmp-"
