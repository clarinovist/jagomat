"""Pemulihan off-site (Mac): verifikasi MAC sebelum dekripsi, ekstraksi aman, roundtrip."""
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

import pytest

from offsite_kit import (ENV_AKSES, ENV_RAHASIA, buat_bundle, buat_pasangan_kunci,
                         hash_pohon, tulis_env)
from offsite_lingkungan import (_lingkungan_uji, kunci, kunci_lain, paket, pulihkan,  # noqa: F401
                                s3, simpan_objek, unggah)

import backup_offsite_vps as vps  # noqa: E402
import offsite_kripto  # noqa: E402
import pulihkan_offsite as pulih  # noqa: E402

CANDIDATE_OPENSSL = ("/usr/bin/openssl", "/opt/homebrew/bin/openssl")

_pulihkan = pulihkan
_simpan_objek = simpan_objek


def _unggah(tmp_path, s3, publik, capsys, *tambahan, bundle=None):
    return unggah(tmp_path, s3, publik, capsys, *tambahan, bundle=bundle)[0]


def test_roundtrip_dari_direktori_bundle_identik_byte_per_byte(paket, capsys):
    kode, out, err = _pulihkan(paket, capsys)

    assert kode == 0 and err == ""
    hasil = paket["tujuan"] / paket["id"]
    assert hash_pohon(hasil) == hash_pohon(paket["bundle"])
    assert json.loads(out)["ok"] is True


def test_roundtrip_penuh_lewat_unduhan_s3_tiruan(paket, capsys):
    env = tulis_env(paket["tmp"] / "baca.env")
    argv = ["--id", paket["id"], "--env", str(env), "--endpoint", paket["s3"].url,
            "--kunci-privat", str(paket["privat"]), "--tujuan", str(paket["tujuan"])]

    kode = pulih.main(argv)

    assert kode == 0, capsys.readouterr().err
    assert hash_pohon(paket["tujuan"] / paket["id"]) == hash_pohon(paket["bundle"])
    assert [m for m, _ in paket["s3"].permintaan if m == "DELETE"] == []


def test_kunci_privat_salah_ditolak_tanpa_menulis_tujuan(paket, kunci_lain, capsys):
    kode, _, err = _pulihkan(paket, capsys, privat=kunci_lain[0])

    assert kode == 1 and "kunci" in err
    assert not paket["tujuan"].exists()


def _balik_bit(path: Path, posisi: int = 100) -> None:
    isi = bytearray(path.read_bytes())
    isi[posisi] ^= 0x01
    path.write_bytes(bytes(isi))


def _pasang_mata_mata(monkeypatch):
    dipanggil = []
    asli = pulih.dekripsi_data
    monkeypatch.setattr(pulih, "dekripsi_data", lambda *a, **k: (dipanggil.append(1), asli(*a, **k))[1])
    return dipanggil


def test_bit_data_terbalik_ditolak_sebelum_dekripsi(paket, capsys, monkeypatch):
    dipanggil = _pasang_mata_mata(monkeypatch)
    _balik_bit(paket["dir"] / "data.enc")

    kode, _, err = _pulihkan(paket, capsys)

    assert kode == 1 and not dipanggil and not paket["tujuan"].exists()


def test_penyerang_menulis_ulang_meta_ditolak_oleh_mac_sebelum_dekripsi(paket, capsys, monkeypatch):
    dipanggil = _pasang_mata_mata(monkeypatch)
    data = paket["dir"] / "data.enc"
    _balik_bit(data)
    meta = json.loads((paket["dir"] / "meta.json").read_text())
    meta["sha256"] = offsite_kripto.sha256_berkas(data)  # sha & ukuran dibuat cocok lagi
    (paket["dir"] / "meta.json").write_text(json.dumps(meta))

    kode, _, err = _pulihkan(paket, capsys, harapan=False)  # jalur MAC internal

    assert kode == 1 and "MAC" in err
    assert not dipanggil and not paket["tujuan"].exists()


def test_mac_dirusak_satu_bit_ditolak(paket, capsys, monkeypatch):
    dipanggil = _pasang_mata_mata(monkeypatch)
    meta = json.loads((paket["dir"] / "meta.json").read_text())
    meta["mac"] = ("0" if meta["mac"][0] != "0" else "1") + meta["mac"][1:]
    (paket["dir"] / "meta.json").write_text(json.dumps(meta))

    kode, _, err = _pulihkan(paket, capsys, harapan=False)  # jalur MAC internal

    assert kode == 1 and "MAC" in err and not dipanggil and not paket["tujuan"].exists()


def test_kunci_enc_dirusak_ditolak_sebelum_dekripsi_data(paket, capsys, monkeypatch):
    dipanggil = _pasang_mata_mata(monkeypatch)
    _balik_bit(paket["dir"] / "kunci.enc", 10)

    kode, _, _ = _pulihkan(paket, capsys)

    assert kode == 1 and not dipanggil and not paket["tujuan"].exists()


@pytest.mark.parametrize("ubah", [
    lambda m: m.update(id="20200101-000000"),
    lambda m: m["alg"].update(iter=1),
    lambda m: m["alg"].update(cipher="aes-128-ecb"),
    lambda m: m.update(format=2),
    lambda m: m.update(tambahan="x"),
    lambda m: m.pop("mac"),
], ids=["id", "iter", "cipher", "format", "kolom-asing", "tanpa-mac"])
def test_meta_tidak_sah_ditolak(paket, capsys, monkeypatch, ubah):
    dipanggil = _pasang_mata_mata(monkeypatch)
    meta = json.loads((paket["dir"] / "meta.json").read_text())
    ubah(meta)
    (paket["dir"] / "meta.json").write_text(json.dumps(meta))

    kode, _, _ = _pulihkan(paket, capsys)

    assert kode == 1 and not dipanggil and not paket["tujuan"].exists()


def test_tujuan_tak_kosong_ditolak_dan_isinya_tidak_berubah(paket, capsys, monkeypatch):
    dipanggil = _pasang_mata_mata(monkeypatch)
    paket["tujuan"].mkdir()
    (paket["tujuan"] / "milik-lain.txt").write_text("jangan disentuh")

    kode, _, err = _pulihkan(paket, capsys)

    assert kode == 1 and "kosong" in err and not dipanggil
    assert [p.name for p in paket["tujuan"].iterdir()] == ["milik-lain.txt"]
    assert (paket["tujuan"] / "milik-lain.txt").read_text() == "jangan disentuh"


def test_tujuan_direktori_kosong_diterima(paket, capsys):
    paket["tujuan"].mkdir()

    kode, _, _ = _pulihkan(paket, capsys)

    assert kode == 0 and (paket["tujuan"] / paket["id"] / "manifest.json").is_file()


def test_objek_hilang_ditolak(paket, capsys):
    (paket["dir"] / "kunci.enc").unlink()

    kode, _, err = _pulihkan(paket, capsys)

    assert kode == 1 and "kunci.enc" in err


def test_kunci_privat_hanya_sebagai_path_dan_sandi_tidak_di_argv(paket, capsys, monkeypatch):
    dipanggil = []
    asli = subprocess.run

    def mata_mata(argumen, **kw):
        dipanggil.append((list(argumen), kw.get("env")))
        return asli(argumen, **kw)

    monkeypatch.setattr(offsite_kripto.subprocess, "run", mata_mata)
    isi_privat = paket["privat"].read_text()

    kode, _, _ = _pulihkan(paket, capsys)

    assert kode == 0
    argv_semua = [str(a) for argumen, _ in dipanggil for a in argumen]
    assert str(paket["privat"]) in argv_semua
    assert not any("PRIVATE KEY" in a or isi_privat.strip()[40:80] in a for a in argv_semua)
    assert not any(len(a) == 64 and all(c in "0123456789abcdef" for c in a) for a in argv_semua)


def _paket_tar_jahat(tmp_path, s3, publik, capsys, monkeypatch, pembuat):
    """Bangun paket yang MAC-nya sah tetapi tar-nya berbahaya, lewat jalur enkripsi sungguhan."""
    def tar_jahat(bundle, tujuan):
        with tarfile.open(str(tujuan), "w:gz") as tar:
            pembuat(tar, bundle.name)
    with monkeypatch.context() as lokal:
        lokal.setattr(vps, "buat_tar", tar_jahat)
        return _unggah(tmp_path, s3, publik, capsys)


def _entri(tar, nama, isi=b"x", tipe=tarfile.REGTYPE, tautan=""):
    info = tarfile.TarInfo(nama)
    info.type, info.linkname, info.size = tipe, tautan, len(isi) if tipe == tarfile.REGTYPE else 0
    tar.addfile(info, io.BytesIO(isi) if tipe == tarfile.REGTYPE else None)


JAHAT = {
    "traversal": lambda t, i: _entri(t, f"{i}/../../evil"),
    "absolut": lambda t, i: _entri(t, "/tmp/evil-absolut"),
    "symlink": lambda t, i: _entri(t, f"{i}/tautan", tipe=tarfile.SYMTYPE, tautan="/etc/passwd"),
    "hardlink": lambda t, i: _entri(t, f"{i}/keras", tipe=tarfile.LNKTYPE, tautan=f"{i}/x"),
    "akar-lain": lambda t, i: _entri(t, "bukan-id/x"),
    "duplikat": lambda t, i: (_entri(t, f"{i}/a"), _entri(t, f"{i}/a")),
    "perangkat": lambda t, i: _entri(t, f"{i}/dev", tipe=tarfile.CHRTYPE),
}


@pytest.mark.parametrize("nama", sorted(JAHAT))
def test_tar_berbahaya_ditolak_dan_tidak_menulis_di_luar_tujuan(tmp_path, s3, kunci, capsys, monkeypatch, nama):
    bundle = _paket_tar_jahat(tmp_path, s3, kunci[1], capsys, monkeypatch, JAHAT[nama])
    p = {"id": bundle.name, "dir": _simpan_objek(s3, bundle.name, tmp_path / "u"),
         "privat": kunci[0], "tujuan": tmp_path / "pulih"}

    kode, _, err = _pulihkan(p, capsys)

    assert kode == 1 and "tar" in err
    assert not p["tujuan"].exists()
    assert not (tmp_path / "evil").exists() and not Path("/tmp/evil-absolut").exists()
    assert not [x for x in tmp_path.iterdir() if x.name.startswith(".pulihkan")]


def test_argumen_wajib_hilang_gagal_bersih(capsys):
    with pytest.raises(SystemExit) as info:
        pulih.main(["--id", "20260101-000000"])

    assert info.value.code != 0


def _openssl_berbeda():
    unik = {}
    for kandidat in CANDIDATE_OPENSSL:
        if os.path.exists(kandidat):
            unik.setdefault(os.path.realpath(kandidat), kandidat)
    return list(unik.values())


@pytest.mark.skipif(len(_openssl_berbeda()) < 2, reason="hanya satu biner openssl")
@pytest.mark.parametrize("arah", [0, 1])
def test_interop_antar_biner_openssl(tmp_path, s3, kunci, capsys, arah):
    pembungkus, pembuka = _openssl_berbeda()[arah], _openssl_berbeda()[1 - arah]
    bundle = _unggah(tmp_path, s3, kunci[1], capsys, "--openssl", pembungkus)
    p = {"id": bundle.name, "dir": _simpan_objek(s3, bundle.name, tmp_path / "u"),
         "privat": kunci[0], "tujuan": tmp_path / "pulih"}

    kode, _, err = _pulihkan(p, capsys, "--openssl", pembuka)

    assert kode == 0, err
    assert hash_pohon(p["tujuan"] / bundle.name) == hash_pohon(bundle)
