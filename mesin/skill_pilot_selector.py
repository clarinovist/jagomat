"""Selector pilot deterministik; tidak menulis sesi atau mengganti generator lama."""
from dataclasses import dataclass
from typing import Optional

import generator
import topics
from generator_version import versi_generator_baru
from skill_pilot import (
    KonteksPilot, KunciFokus, tuntutan, sidik_variasi, validasi_fokus,
)
from templates import Soal


@dataclass(frozen=True)
class ProbePilot:
    soal: Soal
    konteks: KonteksPilot
    seed_sumber: int
    versi_generator: int
    sidik_variasi: str
    target_fokus: Optional[KunciFokus] = None


def pilih_probe(konteks, seed, jumlah, *, sidik_terpakai=(), fokus=None, batas=4000):
    """Tolak kuota tak terpenuhi seluruhnya; tidak fallback ke varian lain.

    Batas pencarian melindungi sumber terbatas. Nilai sidik lama berasal dari
    adapter tervalidasi, bukan cookie/LLM atau profil anak terkini.
    """
    if type(konteks) is not KonteksPilot:
        raise ValueError("konteks pilot tidak sah")
    if type(seed) is not int or seed < 0 or type(jumlah) is not int or not 1 <= jumlah <= 15:
        raise ValueError("seed atau jumlah probe tidak sah")
    if type(batas) is not int or not 1 <= batas <= 20000:
        raise ValueError("batas pencarian probe tidak sah")
    if (type(sidik_terpakai) is not tuple
            or any(type(s) is not str or len(s) != 64 or any(c not in "0123456789abcdef" for c in s)
                   for s in sidik_terpakai)):
        raise ValueError("sidik sumber tidak sah")
    if fokus is not None:
        validasi_fokus(konteks, fokus)
    item = tuntutan(konteks.tuntutan_id)
    topik = topics.pemilik_template(item.template_id)
    terpakai = set(sidik_terpakai)
    hasil = []
    for calon in range(seed, seed + batas):
        soal = generator.buat_soal(item.template_id, calon, konteks.profil_parameter, topik)
        if item.varian is not None and soal.parameter.get("varian") != item.varian:
            continue
        if fokus is not None and fokus[2] is not None and not any(
            m.id == fokus[2] and m.kode == fokus[1] for m in soal.malrule
        ):
            continue
        sidik = sidik_variasi(konteks, soal.template_id, soal.parameter)
        if sidik in terpakai:
            continue
        terpakai.add(sidik)
        hasil.append(ProbePilot(soal, konteks, calon, versi_generator_baru(), sidik, fokus))
        if len(hasil) == jumlah:
            return tuple(hasil)
    raise ValueError("Probe baru yang cocok belum cukup; tidak ada sesi yang dibuat.")
