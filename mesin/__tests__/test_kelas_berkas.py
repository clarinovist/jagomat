"""Berkas bukti transfer paket kelas: subfolder `kelas` sendiri di dalam folder bukti (tanpa DB, data sintetis)."""
import pytest

import bukti_berkas
import harian_langganan_berkas
import kelas_berkas


@pytest.fixture
def akar(tmp_path, monkeypatch):
    jalur = tmp_path / "bukti"
    monkeypatch.setenv(bukti_berkas.NAMA_ENV, str(jalur))
    return jalur


def test_subfolder_sendiri_berbeda_dari_harian_dan_dari_folder_bukti_peta(akar):
    assert kelas_berkas.SUBFOLDER == "kelas"
    assert kelas_berkas.folder() == akar / "kelas"
    assert kelas_berkas.folder() != harian_langganan_berkas.folder()
    assert kelas_berkas.folder() != bukti_berkas.direktori_bukti()


def test_simpan_buka_hapus_di_subfolder_kelas_saja(akar):
    nama = kelas_berkas.simpan(b"\x89PNG-sintetis")
    assert (akar / "kelas" / nama).is_file()
    assert not (akar / nama).exists()
    with kelas_berkas.buka(nama) as f:
        assert f.read() == b"\x89PNG-sintetis"
    assert kelas_berkas.hapus(nama) is True
    assert kelas_berkas.hapus(nama) is False
    assert not (akar / "kelas" / nama).exists()


@pytest.mark.parametrize("nama", ["../x", "x" * 32, "A" * 32, "a" * 31, "", None, "a" * 32 + "/../b"])
def test_nama_tidak_sah_ditolak_tanpa_menyentuh_disk(akar, nama):
    with pytest.raises(bukti_berkas.NamaBerkasTidakSah):
        kelas_berkas.buka(nama)
    with pytest.raises(bukti_berkas.NamaBerkasTidakSah):
        kelas_berkas.hapus(nama)


def test_berkas_harian_tidak_terbaca_lewat_kelas_dan_sebaliknya(akar):
    harian = harian_langganan_berkas.simpan(b"harian")
    kelas = kelas_berkas.simpan(b"kelas")
    with pytest.raises(FileNotFoundError):
        kelas_berkas.buka(harian)
    with pytest.raises(FileNotFoundError):
        harian_langganan_berkas.buka(kelas)


def test_isi_bukan_bytes_ditolak(akar):
    with pytest.raises(bukti_berkas.BuktiBerkasError):
        kelas_berkas.simpan("bukan bytes")
