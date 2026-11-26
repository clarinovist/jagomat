"""Bentuk DB catatan pertemuan guru (`guru-pertemuan.db`): konstanta saja, TANPA impor.

Dipisah dari `guru_pertemuan_dasar` supaya validator skema backup operasional (yang jalan di host dengan subset modul
`mesin/`) cukup membawa berkas kecil ini, tanpa menarik `auth`, `topics`, atau modul aplikasi lain.
"""
NAMA_BERKAS = "guru-pertemuan.db"
VERSI_SKEMA = 1
TABEL_SKEMA = ("pertemuan_jurnal", "pertemuan_hadir")
