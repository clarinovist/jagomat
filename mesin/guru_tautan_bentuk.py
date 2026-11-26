"""Bentuk DB ledger tautan kode anak guru (`guru-tautan.db`): konstanta saja, TANPA impor.

Dipisah dari `guru_tautan_dasar` supaya validator skema backup operasional (yang jalan di host dengan subset modul
`mesin/`) cukup membawa berkas kecil ini, tanpa menarik `auth` atau modul aplikasi lain.
"""
NAMA_BERKAS = "guru-tautan.db"
VERSI_SKEMA = 1
TABEL_SKEMA = ("kode_anak", "kode_cabut", "permintaan", "putusan", "percobaan_gagal")
