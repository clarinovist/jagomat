"""Urutan finalisasi sesi lewat tautan: dipakai jalur lama dan jalur cek anak.

Dipindah apa adanya dari ``share_http`` (bukan diubah). Dibagi dua karena
``sensor_http``/analitik membaca status yang sudah ter-commit lewat koneksi
sendiri: bagian pertama berjalan DI DALAM transaksi pemanggil, bagian kedua
HANYA setelah commit.
"""
from __future__ import annotations

import database


def finalkan_kiriman_tautan(kon, sesi_id: int) -> bool:
    """Arsipkan, diagnosa, lalu tandai selesai; True bila ini kiriman pertama.

    Dipanggil di transaksi pemanggil; tidak commit sendiri.
    """
    import student_submissions as kiriman
    from reports import diagnosa_murid

    kiriman_baru = not kon.execute(
        "SELECT 1 FROM pengiriman_sesi WHERE sesi_id=?", (sesi_id,)
    ).fetchone()
    kiriman.arsipkan(kon, sesi_id, "tautan")
    diagnosa_murid(kon, sesi_id)
    database.tandai_mulai(kon, sesi_id)
    database.tandai_selesai(kon, sesi_id)
    return kiriman_baru


def catat_kiriman_tautan(sesi_id: int, kiriman_baru: bool) -> None:
    """Sensor dan analitik 'dikirim'; panggil hanya SETELAH commit."""
    import product_analytics_http as analitik
    import sensor_http

    sensor_http.sesi(sesi_id, 'dikirim')
    analitik.aktivitas_sesi(sesi_id, "latihan_dikirim", baru=kiriman_baru)
