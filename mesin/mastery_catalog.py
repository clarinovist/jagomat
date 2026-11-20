"""Target keterampilan Jagomat v1; bukan silabus sekolah atau bobot soal.

Grup menyatukan variasi satu keterampilan, bukan sekadar kartu rumus bersama.
Semua pola dalam grup yang tersedia di kelas anak wajib memiliki bukti. Satu
pola hanya berada pada satu target dan satu topik; jumlah soal tidak memberi bobot.
"""
from dataclasses import dataclass
from typing import Tuple

import kurikulum_katalog
import topics
from templates import LEVEL_TINGKAT

VERSI_KATALOG = "jagomat-2026-10-v2"


@dataclass(frozen=True)
class TargetMateri:
    id: str
    nama: str
    topik_id: str
    topik: str
    pola: Tuple[str, ...]


# Pemetaan eksplisit: FPB tidak dianggap KPK; luas segiempat tidak mewakili
# arsiran; rata-rata sederhana belum membuktikan rata-rata gabungan. Varian
# yang memang berbagi keterampilan tetap diuji semuanya, bukan salah satunya.
# Data dari `kurikulum_katalog` (satu sumber peta kurikulum). Grup `bilangan-dasar` dan
# `bilangan-sekolah` hanya audit latihan manual (palang `Topik.hanya_manual` bagi yang
# kedua); `katalog_target` melewati topik manual-saja walau grupnya ada.
KELOMPOK = kurikulum_katalog.kelompok_mastery()


def katalog_target(level: str) -> Tuple[TargetMateri, ...]:
    """Kelas tidak dikenal tidak diam-diam diberi target kelas lain."""
    if level not in LEVEL_TINGKAT:
        return ()
    hasil = []
    # Topik manual-saja tidak pernah menjadi target mastery, walau kelak ada di KELOMPOK.
    for topik_id in topics.daftar_topik_siklus():
        paket = topics.ambil(topik_id)
        pola_kelas = set(paket.komposisi.get(level, ()))
        for kode, nama, pola in KELOMPOK.get(topik_id, ()):
            tersedia = tuple(t for t in pola if t in pola_kelas)
            if tersedia:
                hasil.append(TargetMateri(topik_id + "." + kode, nama, topik_id, paket.nama, tersedia))
    return tuple(hasil)
