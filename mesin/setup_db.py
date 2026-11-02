"""Siapkan basis data: buat tabel, daftarkan siswa, siapkan sesi pertama.

Jalankan sekali per mesin:
    ./.venv/bin/python setup_db.py

Aman dijalankan ulang — siswa tidak terduplikasi, dan bank soal memakai
tanda_tangan sebagai penjaga. Yang TIDAK aman diulang: pembuatan sesi,
karena tiap panggilan membuat sesi baru. Karena itu sesi hanya dibuat
kalau siswa belum punya satu pun.
"""

from __future__ import annotations

import sys

import database

SISWA = ["Andi", "Bila"]


def main() -> int:
    database.siapkan()
    print(f"basis data siap: {database.BAWAAN}")

    with database.buka() as kon:
        for nama in SISWA:
            sid = database.tambah_siswa(kon, nama)
            print(f"  siswa id={sid} ditambahkan")

        print()
        for baris in database.daftar_siswa(kon):
            sudah = kon.execute(
                "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (baris["id"],)
            ).fetchone()["n"]
            if sudah:
                print(f"  siswa id={baris['id']}: sudah punya {sudah} sesi — dilewati")
                continue
            # Seed diambil dari id siswa + tanggal supaya dua anak dapat
            # lembar BERBEDA di hari yang sama. Kalau seed-nya sama, satu
            # anak bisa menyalin jawaban yang lain.
            seed = 1000 + baris["id"]
            sesi_id = database.buat_sesi(kon, baris["id"], seed)
            print(f"  siswa id={baris['id']}: sesi #{sesi_id} dibuat (seed {seed})")

        print()
        print("bank soal terisi:")
        total = 0
        for s in database.statistik_bank(kon):
            print(f"  {s['template_id']:30s} {s['jumlah']:3d}")
            total += s["jumlah"]
        print(f"  {'TOTAL':30s} {total:3d}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
