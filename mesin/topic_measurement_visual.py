"""Proyeksi waktu diketahui; waktu yang dicari tidak masuk descriptor."""
from __future__ import annotations

from measurement_combinatorics_visual_data import (
    FIELD_WAKTU, bulat, field_tepat, validasi_waktu,
)
from visual_contract import DescriptorVisual


def proyeksi_pengukuran(template_id, parameter):
    if template_id == "skala_peta":
        from measurement_scale_visual import proyeksi_skala
        from catalog_versions import parameter_visual
        return proyeksi_skala(parameter_visual(template_id, parameter, {"skala_peta"}))
    if template_id != "jam_selesai":
        return None
    field_tepat(parameter, {"varian", "jam", "menit", "durasi_jam", "durasi_menit"})
    varian = parameter["varian"]
    if not isinstance(varian, str) or varian not in FIELD_WAKTU:
        raise ValueError("varian jam tidak didukung")
    jam = bulat(parameter["jam"], "jam", 0, 23)
    menit = bulat(parameter["menit"], "menit", 0, 59)
    durasi_jam = bulat(parameter["durasi_jam"], "durasi jam", 0, 23)
    durasi_menit = bulat(parameter["durasi_menit"], "durasi menit", 0, 59)
    mulai = jam * 60 + menit
    durasi = durasi_jam * 60 + durasi_menit
    # Semua nilai di sini tetap server-side; hanya field diberikan diproyeksikan.
    fakta = {"varian": varian, "mulai": mulai, "selesai": mulai + durasi, "durasi": durasi}
    data = {nama: fakta[nama] for nama in sorted(FIELD_WAKTU[varian])}
    validasi_waktu(data)
    pertanyaan = {
        "cari_mulai": "Pukul berapa kegiatan itu mulai?",
        "cari_selesai": "Pukul berapa kegiatan itu selesai?",
        "cari_durasi": "Berapa lama kegiatan itu berlangsung?",
    }[varian]
    return ("Perhatikan waktu kegiatan pada diagram (format 24 jam).\n" + pertanyaan,
            DescriptorVisual("linimasa_jam", 1, data))
