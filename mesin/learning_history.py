"""Catatan konteks untuk histori belajar pada level berbeda."""
from __future__ import annotations

from typing import Tuple

from learning_cycle import BuktiSiklus
from question_context import label_profil_parameter as label_kelas


def _gabung_label(label: Tuple[str, ...]) -> str:
    if len(label) == 1:
        return label[0]
    return ", ".join(label[:-1]) + " dan " + label[-1]


def catatan_histori_beda_level(
    bukti: BuktiSiklus,
    *,
    mulai_dari_awal: bool,
) -> Tuple[str, ...]:
    """Jelaskan histori beda level tanpa menjadikannya bukti level aktif."""
    level_lama = tuple(
        sorted(
            {
                sesi.level
                for sesi in bukti.sesi
                if sesi.siswa_id == bukti.siswa_id
                and sesi.level != bukti.level_aktif
            },
            key=label_kelas,
        )
    )
    if not level_lama:
        return ()

    kelas_lama = _gabung_label(tuple(label_kelas(level) for level in level_lama))
    kelas_aktif = label_kelas(bukti.level_aktif)
    hasil = (
        f"Riwayat {kelas_lama} tetap tersimpan sebagai catatan; "
        f"tidak dihitung dalam pemetaan {kelas_aktif}.",
    )
    if mulai_dari_awal:
        hasil += (f"Mulai pemetaan {kelas_aktif} dari awal.",)
    return hasil
