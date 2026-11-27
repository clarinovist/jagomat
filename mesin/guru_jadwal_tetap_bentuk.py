"""Bentuk DB jadwal tetap guru (`guru-jadwal-tetap.db`): konstanta saja, TANPA impor.

Dipisah dari `guru_jadwal_tetap_dasar` supaya validator skema backup operasional (yang jalan di host dengan subset
modul `mesin/`) cukup membawa berkas kecil ini, tanpa menarik modul aplikasi lain.
"""
NAMA_BERKAS = "guru-jadwal-tetap.db"
VERSI_SKEMA = 1
TABEL_SKEMA = ("tetap_usulan", "tetap_putusan")
