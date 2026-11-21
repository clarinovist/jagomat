"""Fixture dan pembantu bersama tes off-site (sisi VPS dan sisi pemulihan).

Diimpor ke modul tes agar fixture-nya ikut terdaftar; hanya data sintetis.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from offsite_kit import (ENV_AKSES, ENV_RAHASIA, buat_bundle, buat_pasangan_kunci,
                         tulis_env)
from s3_tiruan_kit import S3Tiruan

import backup_offsite_vps as vps  # noqa: E402
import offsite_kripto  # noqa: E402
import pulihkan_offsite as pulih  # noqa: E402


@pytest.fixture(autouse=True)
def _lingkungan_uji(monkeypatch):
    """Tanpa jeda ulang nyata; flag uji pemilik-env hanya aktif bila env uji ada."""
    monkeypatch.setattr(vps.r2_s3, "JEDA_ULANG_DETIK", (0.0, 0.0))
    monkeypatch.setenv("OSN_OFFSITE_UJI", "1")


@pytest.fixture(scope="module")
def kunci(tmp_path_factory):
    return buat_pasangan_kunci(tmp_path_factory.mktemp("kunci"))


@pytest.fixture(scope="module")
def kunci_lain(tmp_path_factory):
    return buat_pasangan_kunci(tmp_path_factory.mktemp("kunci-lain"))


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


def argv_vps(env, *tambahan, bundle_dir=None):
    return ["--env", str(env["env"]), "--kunci-publik", str(env["publik"]),
            "--bundle-dir", str(bundle_dir or env["bundle"].parent),
            "--penanda", str(env["penanda"]), "--endpoint", env["s3"].url,
            "--uji-lewati-pemilik-env", *tambahan]


def jalankan(env, capsys, *tambahan, bundle_dir=None):
    kode = vps.main(argv_vps(env, *tambahan, bundle_dir=bundle_dir))
    keluar = capsys.readouterr()
    return kode, keluar.out, keluar.err


def baca_penanda(path) -> dict:
    """Urai penanda: `<stempel> <id> kunci=nilai ...` jadi dict."""
    bagian = Path(path).read_text().split()
    hasil = {"stempel": bagian[0], "id": bagian[1]}
    hasil.update(item.partition("=")[::2] for item in bagian[2:])
    return hasil


def unggah(tmp_path, s3, publik, capsys, *tambahan, bundle=None):
    """Jalankan skrip VPS sungguhan ke S3 tiruan; kembalikan (bundle, ringkasan JSON)."""
    bundle = bundle or buat_bundle(tmp_path)
    argv = ["--env", str(tulis_env(tmp_path / "r2.env")), "--kunci-publik", str(publik),
            "--bundle-dir", str(bundle.parent), "--penanda", str(tmp_path / "ok"),
            "--endpoint", s3.url, "--uji-lewati-pemilik-env", *tambahan]
    assert vps.main(argv) == 0, capsys.readouterr().err
    ringkas = json.loads(capsys.readouterr().out)
    return bundle, ringkas


def simpan_objek(s3, id_bundle, tujuan: Path) -> Path:
    tujuan.mkdir(parents=True, exist_ok=True)
    for nama in offsite_kripto.NAMA_OBJEK:
        (tujuan / nama).write_bytes(s3.objek[f"vps/{id_bundle}/{nama}"][0])
    return tujuan


@pytest.fixture()
def paket(tmp_path, s3, kunci, capsys):
    bundle, ringkas = unggah(tmp_path, s3, kunci[1], capsys)
    return {"bundle": bundle, "id": bundle.name, "tujuan": tmp_path / "pulih",
            "dir": simpan_objek(s3, bundle.name, tmp_path / "unduhan"),
            "privat": kunci[0], "tmp": tmp_path, "s3": s3, "ringkas": ringkas}


def pulihkan(p, capsys, *tambahan, privat=None, tujuan=None, harapan=True):
    """Jalankan pemulihan; `harapan` menyertakan mac/sha256 tepercaya dari ringkasan VPS."""
    argv = ["--id", p["id"], "--dari-direktori", str(p["dir"]),
            "--kunci-privat", str(privat or p["privat"]), "--tujuan", str(tujuan or p["tujuan"])]
    if harapan and "ringkas" in p:
        argv += ["--mac-harapan", p["ringkas"]["mac"], "--sha256-harapan", p["ringkas"]["sha256"]]
    kode = pulih.main(argv + list(tambahan))
    keluar = capsys.readouterr()
    return kode, keluar.out, keluar.err
