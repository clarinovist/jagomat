"""Jawaban beruntun Latihan Harian: dihitung per sesi, hanya setelah terjawab, dan memilih pose maskot."""
import pytest

import harian_beruntun
import harian_latihan_store as hs
from test_harian_latihan_store import (  # noqa: F401  (fixture dan pembantu dipakai bersama)
    T0, _anak, _jawab, _kunci_huruf, _mulai, jalur, kon, lingkungan,
)


def _jawab_pola(kon, siswa, sesi, pola):
    """pola: string 'B'/'S' per soal berurutan (benar/salah) dari soal 1."""
    for n, p in enumerate(pola, 1):
        kunci = _kunci_huruf(kon, sesi, n)
        huruf = kunci if p == "B" else next(h for h in "ABCD" if h != kunci)
        _jawab(kon, siswa, sesi, n, huruf)


@pytest.mark.parametrize("pola,nomor,benar,beruntun", [
    ("B", 1, True, 1), ("BBB", 3, True, 3), ("SBB", 3, True, 2), ("BBS", 3, False, 1),
    ("BSS", 3, False, 2), ("BBBBS", 4, True, 4), ("SSS", 2, False, 2),
])
def test_hitung_beruntun_dalam_sesi_ini(kon, pola, nomor, benar, beruntun):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak)
    _jawab_pola(kon, anak, sesi.id, pola)
    _, umpan = hs.muat_soal(kon, anak, sesi.id, nomor)
    assert umpan.benar is benar
    assert harian_beruntun.hitung(kon, sesi.id, nomor, umpan.benar) == beruntun


def test_beruntun_tidak_menyeberang_sesi_lain(kon):
    anak = _anak(kon)
    pertama, _ = _mulai(kon, anak)
    _jawab_pola(kon, anak, pertama.id, "BBBBBBBBBB")
    kedua, _ = _mulai(kon, anak, sekarang=T0 + 2 * 86400)
    _jawab_pola(kon, anak, kedua.id, "B")
    assert harian_beruntun.hitung(kon, kedua.id, 1, True) == 1


def test_modul_beruntun_bukan_berkas_kontrak_rilis():
    """Stem berisi schema/migrat/database/store masuk sidik kontrak rilis; pose maskot tidak boleh menggesernya."""
    stem = harian_beruntun.__name__
    assert not any(k in stem for k in ("schema", "migrat", "database", "store"))
