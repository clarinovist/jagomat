"""Bentuk DB tugas guru (`guru-tugas.db`): konstanta saja, TANPA impor.

Dipisah dari `guru_tugas_dasar` supaya validator skema backup operasional (yang jalan di host dengan subset modul
`mesin/`) cukup membawa berkas kecil ini, tanpa menarik `auth`, `topics`, atau modul aplikasi lain.
"""
NAMA_BERKAS = "guru-tugas.db"
VERSI_SKEMA = 1
TABEL_SKEMA = ("tugas_guru",)
