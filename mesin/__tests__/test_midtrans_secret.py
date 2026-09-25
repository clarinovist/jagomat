"""Loader rahasia produksi dengan berkas sintetis; tidak ada kredensial nyata."""

import os
from pathlib import Path

import pytest
import midtrans_contract as m
import midtrans_secret as r

KUNCI = "Mid-server-SINTETIS-bukan-credential"
MERCHANT = "M_SINTETIS"


def tulis(tmp_path, isi, *, mode=0o600, nama="rahasia.conf"):
    p = tmp_path / nama
    p.write_bytes(isi)
    os.chmod(p, mode)
    return p


def isi(*, merchant=MERCHANT, kunci=KUNCI, akhir="\n"):
    return ("merchant=%s\nserver_key=%s%s" % (merchant, kunci, akhir)).encode()


def test_berkas_sah_dibaca_dan_konfigurasi_produksi(tmp_path):
    p = tulis(tmp_path, isi())
    assert r.baca_berkas(p) == (MERCHANT, KUNCI)
    assert r.baca_berkas(str(p)) == (MERCHANT, KUNCI)
    cfg = r.konfigurasi(p)
    assert cfg.lingkungan == "production" and cfg.merchant == MERCHANT
    assert KUNCI not in repr(cfg) and KUNCI not in cfg.authorization()


def test_urutan_baris_bebas_tanpa_duplikat(tmp_path):
    p = tulis(tmp_path, ("server_key=%s\nmerchant=%s\n" % (KUNCI, MERCHANT)).encode())
    assert r.baca_berkas(p) == (MERCHANT, KUNCI)


def test_symlink_dan_bukan_file_biasa_ditolak(tmp_path):
    asli = tulis(tmp_path, isi())
    tautan = tmp_path / "tautan.conf"
    tautan.symlink_to(asli)
    assert tautan.is_symlink()
    with pytest.raises(r.RahasiaTidakSah):
        r.baca_berkas(tautan)
    with pytest.raises(r.RahasiaTidakSah):
        r.baca_berkas(tmp_path)
    with pytest.raises(r.RahasiaTidakSah):
        r.baca_berkas(tmp_path / "tidak-ada.conf")


@pytest.mark.parametrize("mode,diterima", [
    (0o600, True), (0o400, True), (0o644, False), (0o640, False), (0o604, False),
    (0o606, False), (0o444, False), (0o666, False), (0o4600, False)])
def test_izin_ketat(tmp_path, mode, diterima):
    p = tulis(tmp_path, isi(), mode=0o600)
    os.chmod(p, mode)
    if diterima:
        assert r.baca_berkas(p) == (MERCHANT, KUNCI)
    else:
        with pytest.raises(r.RahasiaTidakSah):
            r.baca_berkas(p)


def test_owner_bukan_pemakai_proses_ditolak(tmp_path, monkeypatch):
    p = tulis(tmp_path, isi())
    asli = os.geteuid()
    monkeypatch.setattr(r.os, "geteuid", lambda: asli + 1)
    with pytest.raises(r.RahasiaTidakSah):
        r.baca_berkas(p)


@pytest.mark.parametrize("buruk", [
    b"", b"merchant=" + MERCHANT.encode() + b"\n", b"merchant=M\nserver_key=\n",
    b"merchant=M\nserver_key=K\nextra=1\n", b"merchant=M\nmerchant=M2\nserver_key=K\n",
    b"merchant=M\nserver_key=S B\n", b"merchant=M\nserver_key=K:1\n",
    b"merchant=M.D\nserver_key=K\n", b"merchant=M\nserver_key=K\x00\n",
    b"merchant=M\nserver_key=K\n\n", b"merchant =M\nserver_key=K\n",
    b"merchant=M\nserver_key=K=c\n", "merchant=M\nserver_key=K\n".encode("utf-16"),
    b"merchant=" + b"M" * 65 + b"\nserver_key=K\n",
    b"merchant=M\nserver_key=" + b"K" * 257 + b"\n",
])
def test_isi_tidak_sesuai_kontrak_ditolak(tmp_path, buruk):
    p = tulis(tmp_path, buruk)
    with pytest.raises(r.RahasiaTidakSah):
        r.baca_berkas(p)


def test_berkas_terlalu_besar_ditolak(tmp_path):
    p = tulis(tmp_path, b"merchant=M\nserver_key=K\n" + b"#" * r.BATAS_BERKAS)
    with pytest.raises(r.RahasiaTidakSah):
        r.baca_berkas(p)


def test_pesan_galat_tidak_membocorkan_nilai(tmp_path):
    rahasia = "Mid-server-RAHASIA-JANGAN-BOCOR"
    p = tulis(tmp_path, ("merchant=M\nserver_key=%s x\n" % rahasia).encode())
    with pytest.raises(r.RahasiaTidakSah) as galat:
        r.baca_berkas(p)
    assert rahasia not in str(galat.value) + repr(galat.value)


def test_kunci_sandbox_tidak_boleh_untuk_produksi(tmp_path):
    p = tulis(tmp_path, isi(kunci="SB-Mid-server-SINTETIS"))
    assert r.baca_berkas(p) == (MERCHANT, "SB-Mid-server-SINTETIS")
    with pytest.raises(r.RahasiaTidakSah):
        r.konfigurasi(p)


def test_tidak_ada_beberapa_kunci_terbuka(tmp_path):
    p = tulis(tmp_path, isi())
    sebelum = len(os.listdir("/dev/fd"))
    for _ in range(25):
        r.baca_berkas(p)
        with pytest.raises(r.RahasiaTidakSah):
            r.baca_berkas(tmp_path / "tidak-ada.conf")
    assert len(os.listdir("/dev/fd")) <= sebelum + 1
