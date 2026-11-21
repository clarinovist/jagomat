"""Validator ketat sub-adegan `jam_analog` dari descriptor `adegan_awal` v1 (Matematika Awal).

Descriptor menggambar muka jam dinding berjarum buatan kode (SVG, bukan raster):
`{"adegan": "jam_analog", "jam": 1..12, "menit": 0 | 30}`. Hanya jam penuh dan setengah jam
(P2). Field tambahan ditolak. Waktu pada descriptor adalah FAKTA GAMBAR (jarum menunjuk ke
sana), bukan kunci: pada soal baca jam, jawaban memang terbaca dari letak jarum, sedangkan
teks proyeksi tidak pernah memuat jam itu.

Dipanggil lewat `adegan_awal_data.validasi_adegan_awal` (impor malas agar tidak melingkar).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from adegan_awal_data import _field_tepat

JAM_MIN, JAM_MAKS = 1, 12
MENIT_DIDUKUNG = (0, 30)
_FIELD = {"adegan", "jam", "menit"}


def validasi_jam_analog(data: Mapping[str, Any]) -> None:
    """Validasi allow-list descriptor `jam_analog`; gagal tertutup (bool tidak lolos sebagai int)."""
    _field_tepat(data, _FIELD, "adegan_awal/jam_analog")
    jam, menit = data["jam"], data["menit"]
    if type(jam) is not int or not JAM_MIN <= jam <= JAM_MAKS:
        raise ValueError(f"jam jam_analog wajib bilangan bulat {JAM_MIN}..{JAM_MAKS}: {jam!r}")
    if type(menit) is not int or menit not in MENIT_DIDUKUNG:
        raise ValueError(f"menit jam_analog hanya boleh {MENIT_DIDUKUNG}: {menit!r}")
