"""Off-site dari VPS ke R2: enkripsi hibrida kunci publik, retensi, penanda, kredensial."""
import gzip
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import time

import pytest

from offsite_kit import (ENV_AKSES, ENV_RAHASIA, PENANDA, SCRIPTS, buat_bundle,
                         buat_pasangan_kunci, tulis_env)
from s3_tiruan_kit import BUCKET_UJI, S3Tiruan

import backup_offsite_vps as vps  # noqa: E402
import offsite_kripto  # noqa: E402

HARI = 86400


@pytest.fixture(autouse=True)
def _tanpa_jeda_ulang(monkeypatch):
    monkeypatch.setattr(vps.r2_s3, "JEDA_ULANG_DETIK", (0.0, 0.0))


@pytest.fixture(scope="module")
def kunci(tmp_path_factory):
    return buat_pasangan_kunci(tmp_path_factory.mktemp("kunci"))


@pytest.fixture()
def s3():
    with S3Tiruan(akses=ENV_AKSES, rahasia=ENV_RAHASIA) as server:
        yield server


@pytest.fixture()
def lingkungan(tmp_path, s3, kunci):
    bundle = buat_bundle(tmp_path)
    penanda = tmp_path / "log" / "offsite.last-ok"
    penanda.parent.mkdir()
    penanda.write_text("lama 00000000-000000\n")
    return {"tmp": tmp_path, "s3": s3, "bundle": bundle, "penanda": penanda,
            "env": tulis_env(tmp_path / "r2.env"), "publik": kunci[1], "privat": kunci[0]}


def _jalankan(env, capsys, *tambahan, bundle_dir=None):
    argv = ["--env", str(env["env"]), "--kunci-publik", str(env["publik"]),
            "--bundle-dir", str(bundle_dir or env["bundle"].parent),
            "--penanda", str(env["penanda"]), "--endpoint", env["s3"].url,
            "--uji-lewati-pemilik-env", *tambahan]
    kode = vps.main(argv)
    keluar = capsys.readouterr()
    return kode, keluar.out, keluar.err


def _puts(s3):
    return [k for m, k in s3.permintaan if m == "PUT"]


def test_unggah_membuat_tiga_objek_meta_bersih_dan_penanda(lingkungan, capsys):
    kode, out, err = _jalankan(lingkungan, capsys)

    s3, id_bundle = lingkungan["s3"], lingkungan["bundle"].name
    assert kode == 0 and err == ""
    assert sorted(s3.objek) == [f"vps/{id_bundle}/{n}" for n in ("data.enc", "kunci.enc", "meta.json")]
    meta = json.loads(s3.objek[f"vps/{id_bundle}/meta.json"][0])
    assert meta["id"] == id_bundle and meta["format"] == 1
    assert meta["ukuran"] == len(s3.objek[f"vps/{id_bundle}/data.enc"][0])
    assert set(meta["alg"]) == {"cipher", "kdf", "iter", "md", "wrap", "mac"} and meta["alg"]["iter"] == 200000
    teks_meta = json.dumps(meta)
    assert "latihan" not in teks_meta and "sandi" not in teks_meta and PENANDA not in teks_meta
    ringkas = json.loads(out)
    assert ringkas["ok"] is True and ringkas["id"] == id_bundle and ringkas["terhapus"] == 0
    assert ringkas["ukuran"] == meta["ukuran"]
    stempel, ident = lingkungan["penanda"].read_text().split()
    assert ident == id_bundle and re.fullmatch(r"\d{8}-\d{6}", stempel)


def _mengandung_plaintext(payload: bytes) -> bool:
    kandidat = [payload]
    try:
        kandidat.append(gzip.decompress(payload))
    except (OSError, EOFError):
        pass
    for isi in list(kandidat):
        try:
            with tarfile.open(fileobj=io.BytesIO(isi)) as tar:
                kandidat.extend(tar.extractfile(m).read() for m in tar.getmembers() if m.isfile())
        except (tarfile.TarError, OSError, EOFError):
            continue
    return any(PENANDA.encode() in isi for isi in kandidat)


def test_data_terunggah_tidak_pernah_plaintext(lingkungan, capsys):
    kode, _, _ = _jalankan(lingkungan, capsys)

    s3 = lingkungan["s3"]
    assert kode == 0 and s3.payload_diterima
    assert not any(_mengandung_plaintext(p) for p in s3.payload_diterima)
    data = s3.objek[f"vps/{lingkungan['bundle'].name}/data.enc"][0]
    assert data.startswith(b"Salted__") and not data.startswith(b"\x1f\x8b")


def test_hanya_kunci_publik_dipakai_dan_sandi_sesi_tidak_di_argv_atau_env(lingkungan, capsys, monkeypatch):
    lingkungan["privat"].chmod(0)  # bila skrip membacanya, tes ini gagal
    tetap = bytes(range(32))
    sandi_hex = tetap.hex().encode()
    monkeypatch.setattr(offsite_kripto, "bangkitkan_sandi", lambda: tetap.hex())
    dipanggil, berkas_sandi_terlihat = [], []
    asli = subprocess.run

    def mata_mata(argumen, **kw):
        dipanggil.append((list(argumen), kw.get("env")))
        for item in argumen:
            if str(item).startswith("file:"):
                berkas = Path(str(item)[5:])
                assert os.stat(berkas).st_mode & 0o777 == 0o600
                assert os.stat(berkas.parent).st_mode & 0o777 == 0o700
                berkas_sandi_terlihat.append(berkas)
        return asli(argumen, **kw)

    monkeypatch.setattr(offsite_kripto.subprocess, "run", mata_mata)

    try:
        kode, _, _ = _jalankan(lingkungan, capsys)
    finally:
        lingkungan["privat"].chmod(0o600)

    assert kode == 0 and dipanggil and berkas_sandi_terlihat
    for argumen, env in dipanggil:
        assert not any(sandi_hex.decode() in str(a) for a in argumen)
        assert not any(sandi_hex.decode() in str(v) for v in (env or {}).values())
        assert "-decrypt" not in argumen and "-d" not in argumen
        assert str(lingkungan["privat"]) not in argumen


def test_skrip_vps_tidak_punya_kode_atau_argumen_dekripsi():
    sumber = "\n".join((SCRIPTS / n).read_text() for n in
                       ("backup_offsite_vps.py", "r2_s3.py", "offsite_kripto.py"))
    parser = vps.buat_parser()
    opsi = [o for a in parser._actions for o in a.option_strings]

    assert not any("privat" in o for o in opsi)
    assert not re.search(r"-decrypt|-passin|\"-d\"|'-d'|BEGIN (RSA |ENCRYPTED )?PRIVATE", sumber)


def test_kunci_privat_sebagai_kunci_publik_ditolak(lingkungan, capsys):
    lingkungan["publik"] = lingkungan["privat"]

    kode, out, err = _jalankan(lingkungan, capsys)

    assert kode == 1 and out == "" and "publik" in err
    assert lingkungan["s3"].permintaan == []


def test_bundle_basi_gagal_tanpa_unggahan_dan_penanda_tetap(tmp_path, s3, kunci, capsys):
    bundle = buat_bundle(tmp_path, umur_jam=27)
    env = {"tmp": tmp_path, "s3": s3, "bundle": bundle, "env": tulis_env(tmp_path / "r2.env"),
           "publik": kunci[1], "penanda": tmp_path / "ok"}
    env["penanda"].write_text("lama\n")

    kode, out, err = _jalankan(env, capsys)

    assert kode == 1 and out == "" and "lebih tua" in err
    assert s3.permintaan == [] and env["penanda"].read_text() == "lama\n"


def test_umur_maks_jam_dapat_diatur(lingkungan, capsys):
    kode, _, _ = _jalankan(lingkungan, capsys, "--umur-maks-jam", "0.5")

    assert kode == 1 and lingkungan["s3"].permintaan == []


def test_bundle_tak_lolos_validasi_gagal(lingkungan, capsys):
    (lingkungan["bundle"] / "latihan.db").write_bytes(b"rusak")

    kode, out, err = _jalankan(lingkungan, capsys)

    assert kode == 1 and out == "" and "validasi" in err
    assert lingkungan["s3"].permintaan == []
    assert lingkungan["penanda"].read_text() == "lama 00000000-000000\n"


def test_id_manifest_beda_dari_nama_direktori_ditolak(lingkungan, capsys):
    bundle = lingkungan["bundle"]
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["id"] = "20200101-000000"
    (bundle / "manifest.json").write_text(json.dumps(manifest))

    kode, _, err = _jalankan(lingkungan, capsys)

    assert kode == 1 and lingkungan["s3"].permintaan == []


def test_memilih_bundle_terbaru_dan_mengabaikan_partial(lingkungan, capsys):
    akar = lingkungan["bundle"].parent
    lama = buat_bundle(lingkungan["tmp"] / "lain", umur_jam=5)
    os.replace(lama, akar / lama.name)
    (akar / ".partial-29990101-000000-1").mkdir()

    kode, out, _ = _jalankan(lingkungan, capsys)

    assert kode == 0 and json.loads(out)["id"] == lingkungan["bundle"].name


def test_bundle_tidak_ada_gagal(lingkungan, capsys, tmp_path):
    kosong = tmp_path / "kosong"
    kosong.mkdir()

    kode, _, err = _jalankan(lingkungan, capsys, bundle_dir=kosong)

    assert kode == 1 and "bundle" in err


def test_unggahan_gagal_di_tengah_keluar_nonnol_penanda_tetap_dan_tanpa_retensi(lingkungan, capsys):
    s3, id_bundle = lingkungan["s3"], lingkungan["bundle"].name
    s3.taruh("vps/20200101-000000/data.enc", b"x", diubah=time.time() - 90 * HARI)
    s3.gagal[("PUT", f"vps/{id_bundle}/kunci.enc")] = 500

    kode, out, err = _jalankan(lingkungan, capsys)

    assert kode == 1 and out == "" and "500" in err
    assert lingkungan["penanda"].read_text() == "lama 00000000-000000\n"
    assert not [p for p in s3.permintaan if p[0] == "DELETE"]
    assert "vps/20200101-000000/data.enc" in s3.objek


def test_retensi_hanya_menghapus_vps_lebih_tua_dari_batas(lingkungan, capsys):
    s3 = lingkungan["s3"]
    lama, baru = time.time() - 40 * HARI, time.time() - 5 * HARI
    for nama in ("data.enc", "kunci.enc", "meta.json"):
        s3.taruh(f"vps/20200101-000000/{nama}", b"x", diubah=lama)
        s3.taruh(f"vps/20260101-000000/{nama}", b"x", diubah=baru)
    s3.taruh("harian/20200101-000000.tar.gz.enc", b"x", diubah=time.time() - 400 * HARI)
    s3.taruh("harian/baru.tar.gz.enc", b"x", diubah=baru)
    s3.taruh("vps/catatan-asing.txt", b"x", diubah=lama)

    kode, out, _ = _jalankan(lingkungan, capsys)

    assert kode == 0 and json.loads(out)["terhapus"] == 3
    ada = s3.kunci_ada()
    assert not [k for k in ada if k.startswith("vps/20200101")]
    assert "harian/20200101-000000.tar.gz.enc" in ada and "harian/baru.tar.gz.enc" in ada
    assert "vps/catatan-asing.txt" in ada
    assert all(f"vps/20260101-000000/{n}" in ada for n in ("data.enc", "kunci.enc", "meta.json"))
    hapus = [k for m, k in s3.permintaan if m == "DELETE"]
    assert hapus and all(k.startswith("vps/") for k in hapus)


def test_retensi_hari_dapat_diatur_dan_minimal_satu(lingkungan, capsys):
    s3 = lingkungan["s3"]
    s3.taruh("vps/20260101-000000/data.enc", b"x", diubah=time.time() - 3 * HARI)

    kode, out, _ = _jalankan(lingkungan, capsys, "--retensi-hari", "2")
    assert kode == 0 and json.loads(out)["terhapus"] == 1

    kode, _, err = _jalankan(lingkungan, capsys, "--retensi-hari", "0")
    assert kode == 1 and "retensi" in err


def test_retensi_gagal_keluar_kode_3_dan_penanda_lama_tidak_berubah(lingkungan, capsys):
    s3 = lingkungan["s3"]
    s3.taruh("vps/20200101-000000/data.enc", b"x", diubah=time.time() - 90 * HARI)
    s3.gagal[("DELETE", "vps/20200101-000000/data.enc")] = 500

    kode, out, err = _jalankan(lingkungan, capsys)

    assert kode == 3 and out == "" and "retensi gagal" in err and "terunggah" in err
    assert lingkungan["penanda"].read_text() == "lama 00000000-000000\n"


def test_penanda_dibuat_beserta_direktori_induknya(lingkungan, capsys, tmp_path):
    lingkungan["penanda"] = tmp_path / "belum" / "ada" / "ok"

    kode, _, _ = _jalankan(lingkungan, capsys)

    assert kode == 0 and lingkungan["penanda"].read_text().split()[1] == lingkungan["bundle"].name


def test_env_bermode_longgar_ditolak(lingkungan, capsys):
    os.chmod(lingkungan["env"], 0o640)

    kode, out, err = _jalankan(lingkungan, capsys)

    assert kode == 1 and "mode" in err and lingkungan["s3"].permintaan == []


def test_env_bukan_milik_root_ditolak_tanpa_flag_uji(lingkungan, capsys):
    if os.getuid() == 0:
        pytest.skip("dijalankan sebagai root")
    argv = ["--env", str(lingkungan["env"]), "--kunci-publik", str(lingkungan["publik"]),
            "--bundle-dir", str(lingkungan["bundle"].parent), "--penanda", str(lingkungan["penanda"]),
            "--endpoint", lingkungan["s3"].url]

    kode = vps.main(argv)

    assert kode == 1 and "root" in capsys.readouterr().err
    assert lingkungan["s3"].permintaan == []


def test_env_symlink_dan_kunci_hilang_ditolak(lingkungan, capsys, tmp_path):
    tautan = tmp_path / "tautan.env"
    tautan.symlink_to(lingkungan["env"])
    lingkungan["env"] = tautan
    kode, _, err = _jalankan(lingkungan, capsys)
    assert kode == 1

    lingkungan["env"] = tulis_env(tmp_path / "tanpa.env", isi={"R2_BUCKET": ""})
    kode, _, err = _jalankan(lingkungan, capsys)
    assert kode == 1 and "R2_BUCKET" in err


def test_mode_env_tetap_dicek_walau_flag_uji_aktif(lingkungan):
    os.chmod(lingkungan["env"], 0o644)

    with pytest.raises(vps.GalatKonfigurasi):
        vps.muat_env(lingkungan["env"], lewati_pemilik=True)


@pytest.mark.parametrize("skenario", ["sukses", "retensi_gagal", "tanda_salah", "unggah_500", "basi"])
def test_kredensial_tidak_pernah_muncul_di_stdout_stderr(lingkungan, capsys, skenario):
    s3 = lingkungan["s3"]
    if skenario == "tanda_salah":
        s3.rahasia = "rahasia-server-lain"
    if skenario == "unggah_500":
        s3.gagal[("PUT", f"vps/{lingkungan['bundle'].name}/data.enc")] = 500
    if skenario == "retensi_gagal":
        s3.taruh("vps/20200101-000000/data.enc", b"x", diubah=time.time() - 90 * HARI)
        s3.gagal[("DELETE", "vps/20200101-000000/data.enc")] = 500
    if skenario == "basi":
        lingkungan["bundle"] = buat_bundle(lingkungan["tmp"] / "tua", umur_jam=40)

    _, out, err = _jalankan(lingkungan, capsys, bundle_dir=lingkungan["bundle"].parent)

    for rahasia in (ENV_AKSES, ENV_RAHASIA, "a1b2c3d4e5f60718293a4b5c6d7e8f90"):
        assert rahasia not in out + err


def test_galat_tak_terduga_disamarkan_dari_kredensial(lingkungan, capsys, monkeypatch):
    def meledak(*_a, **_k):
        raise RuntimeError(f"gagal dengan {ENV_RAHASIA} dan {ENV_AKSES}")

    monkeypatch.setattr(vps, "unggah_dan_verifikasi", meledak)

    kode, out, err = _jalankan(lingkungan, capsys)

    assert kode == 1 and ENV_RAHASIA not in err + out and ENV_AKSES not in err + out


def test_direktori_sementara_dihapus_saat_keluar_sukses_maupun_gagal(lingkungan, capsys, tmp_path):
    pakai = tmp_path / "sementara"
    pakai.mkdir()

    _jalankan(lingkungan, capsys, "--tmp-dir", str(pakai))
    lingkungan["s3"].gagal[("PUT", f"vps/{lingkungan['bundle'].name}/kunci.enc")] = 500
    _jalankan(lingkungan, capsys, "--tmp-dir", str(pakai))

    assert list(pakai.iterdir()) == []
