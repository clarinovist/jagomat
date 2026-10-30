"""Kontrak katalog offline untuk Pendamping Jagomat.

Katalog ini hanya menjelaskan kemampuan source. Ia tidak membuka basis data,
menghasilkan soal, atau membawa kunci dan diagnosis ke payload agent.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_catalog  # noqa: E402
import rumus  # noqa: E402
import topics  # noqa: E402


def _topik_asli():
    return tuple(
        topics.ambil(topik_id)
        for topik_id in topics.daftar_topik()
        if topik_id != "campuran"
    )


def test_katalog_mencakup_registry_dengan_satu_pemilik_asli(monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '1')
    katalog = assistant_catalog.buat_katalog()
    registry = topics.registri()

    assert {item.id for item in katalog.template} == set(registry)
    assert {item.id for item in katalog.topik} == {item.id for item in _topik_asli()}
    assert all(item.topik_id != "campuran" for item in katalog.template)

    jumlah_pemilik = {
        template_id: sum(template_id in topik.templates for topik in _topik_asli())
        for template_id in registry
    }
    assert set(jumlah_pemilik.values()) == {1}


def test_level_template_hanya_berasal_dari_komposisi_aktual():
    katalog = assistant_catalog.buat_katalog()
    sumber = {topik.id: topik for topik in _topik_asli()}

    for item in katalog.template:
        topik = sumber[item.topik_id]
        aktual = tuple(
            sorted(
                level
                for level, komposisi in topik.komposisi.items()
                if item.id in komposisi
            )
        )
        assert item.level == aktual
        assert item.level


def test_kartu_konsep_berasal_dari_kartu_resmi():
    katalog = assistant_catalog.buat_katalog()

    for item in katalog.template:
        kartu = rumus.kartu_untuk(item.id)
        assert kartu is not None
        assert item.kartu is not None
        assert item.kartu.judul == kartu.judul
        assert item.kartu.inti == kartu.inti
        assert item.kartu.contoh == kartu.contoh
        bantuan = kartu.bantuan
        assert item.kartu.bantuan_jenis == (bantuan.jenis if bantuan else None)
        assert item.kartu.bantuan_versi == (bantuan.versi if bantuan else None)


def test_metadata_yang_belum_punya_sumber_tidak_ditebak():
    katalog = assistant_catalog.buat_katalog()

    assert {item.status_nama_ramah for item in katalog.template} == {
        "belum_dideskripsikan"
    }
    assert {item.status_variasi for item in katalog.template} == {
        "belum_dideskripsikan"
    }
    assert all(item.nama_ramah is None for item in katalog.template)
    assert all(item.variasi == () for item in katalog.template)


def test_snapshot_immutable_dan_tidak_memutasi_source():
    sebelum = {
        topik.id: (
            tuple(topik.templates),
            tuple((level, tuple(komposisi)) for level, komposisi in topik.komposisi.items()),
        )
        for topik in _topik_asli()
    }
    katalog = assistant_catalog.buat_katalog()

    with pytest.raises(FrozenInstanceError):
        katalog.versi = 2
    with pytest.raises(FrozenInstanceError):
        katalog.template[0].topik_id = "campuran"
    with pytest.raises(TypeError):
        katalog.template[0].level[0] = "P0"

    sesudah = {
        topik.id: (
            tuple(topik.templates),
            tuple((level, tuple(komposisi)) for level, komposisi in topik.komposisi.items()),
        )
        for topik in _topik_asli()
    }
    assert sesudah == sebelum


def test_serialisasi_ringkas_stabil_dan_tanpa_data_terlarang():
    pertama = assistant_catalog.serialisasi_ringkas(assistant_catalog.buat_katalog())
    kedua = assistant_catalog.serialisasi_ringkas(assistant_catalog.buat_katalog())
    isi = json.loads(pertama)

    assert pertama == kedua
    assert len(pertama) == assistant_catalog.ukur_katalog(
        assistant_catalog.buat_katalog()
    ).karakter
    assert len(pertama.encode("utf-8")) == assistant_catalog.ukur_katalog(
        assistant_catalog.buat_katalog()
    ).byte
    assert set(isi) == {"versi", "topik", "template"}
    assert all(
        kata not in pertama.lower()
        for kata in ("kunci", "malrule", "diagnosis", "siswa_id", "nama_anak")
    )


def test_serialisasi_stabil_antarproses():
    akar = Path(__file__).resolve().parent.parent
    skrip = (
        "import assistant_catalog; "
        "print(assistant_catalog.serialisasi_ringkas("
        "assistant_catalog.buat_katalog()))"
    )
    hasil = [
        subprocess.run(
            [sys.executable, "-c", skrip],
            cwd=str(akar),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        for _ in range(2)
    ]
    assert hasil[0] == hasil[1]
