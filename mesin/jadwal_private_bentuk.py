"""Bentuk DB jadwal private (`jadwal-private.db`): konstanta saja, TANPA impor.

Dipisah dari `jadwal_private_dasar` supaya validator skema backup operasional (yang jalan di host dengan subset modul
`mesin/`) cukup membawa berkas kecil ini, tanpa menarik `jadwal_dasar`, `kelas_dasar`, atau modul aplikasi lain.
Tabel tambahan (`private_pola_pengajuan`, `tunggu_mini`) sengaja TIDAK masuk `TABEL_SKEMA`: dibuat lazy lewat
`DDL_TAMBAHAN`, sehingga berkas v1 lama yang belum punya tabel itu tetap sah.
"""
NAMA_BERKAS = "jadwal-private.db"
VERSI_SKEMA = 1
TABEL_SKEMA = ("private_slot", "private_pengajuan")
