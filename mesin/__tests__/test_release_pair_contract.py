"""Kontrak bentuk modul pasangan rilis: cegah drift 15 berkas kembar.

Yang diuji adalah bentuk (konstanta wajib, string tidak kosong, penanda unik),
bukan isi probe — tiap paket sengaja punya invarian berbeda.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

AKAR = Path(__file__).resolve().parents[2]
SCRIPTS = AKAR / "scripts"
sys.path.insert(0, str(SCRIPTS))

from release_pair_common import (  # noqa: E402
    KontrakPairTidakSah,
    daftar_modul,
    pastikan_penanda_unik,
    validasi_modul,
)


def _modul(tulis: str = "print('OSN_A_WRITER_OK')", baca: str = "print('OSN_A_RECOVERY_OK')", **lain):
    return SimpleNamespace(SUMBER_TULIS=tulis, SUMBER_BACA=baca, **lain)


def test_semua_modul_pasangan_memakai_kontrak_yang_sama():
    modul = daftar_modul(SCRIPTS.glob("release_*_pair.py"))
    assert len(modul) >= 13, "modul pasangan hilang atau berpindah nama"
    penanda: dict[str, tuple[str, ...]] = {}
    for nama, isi in modul:
        penanda[nama] = validasi_modul(isi, nama=nama)
    pastikan_penanda_unik(penanda)
    semua = [p for daftar in penanda.values() for p in daftar]
    assert len(semua) == len(set(semua))


@pytest.mark.parametrize(
    "hilang",
    ["SUMBER_TULIS", "SUMBER_BACA"],
)
def test_konstanta_wajib_hilang_ditolak(hilang):
    modul = _modul()
    delattr(modul, hilang)
    with pytest.raises(KontrakPairTidakSah, match=hilang):
        validasi_modul(modul, nama="contoh_pair")


@pytest.mark.parametrize("nilai", ["", "   ", None, 42])
def test_sumber_kosong_atau_bukan_string_ditolak(nilai):
    with pytest.raises(KontrakPairTidakSah):
        validasi_modul(_modul(tulis=nilai), nama="contoh_pair")


def test_sumber_kembali_opsional_tetapi_tidak_boleh_kosong():
    assert validasi_modul(_modul(), nama="contoh_pair") == (
        "OSN_A_WRITER_OK",
        "OSN_A_RECOVERY_OK",
    )
    with pytest.raises(KontrakPairTidakSah, match="SUMBER_KEMBALI"):
        validasi_modul(_modul(SUMBER_KEMBALI="  "), nama="contoh_pair")


def test_penanda_ganda_dalam_satu_modul_ditolak():
    with pytest.raises(KontrakPairTidakSah, match="ganda"):
        validasi_modul(
            _modul(baca="print('OSN_A_WRITER_OK')"), nama="contoh_pair"
        )


def test_penanda_sama_antar_modul_ditolak():
    with pytest.raises(KontrakPairTidakSah, match="OSN_A_WRITER_OK"):
        pastikan_penanda_unik(
            {
                "satu_pair": ("OSN_A_WRITER_OK",),
                "dua_pair": ("OSN_A_WRITER_OK",),
            }
        )


def test_modul_non_pair_diabaikan():
    nama = {n for n, _ in daftar_modul(SCRIPTS.glob("release_*"))}
    assert "release_pair_common" not in nama
    assert all(n.endswith("_pair") for n in nama)
