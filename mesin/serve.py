"""Jalankan halaman guru.

    ./.venv/bin/python serve.py            # hanya dari Mac ini
    ./.venv/bin/python serve.py --jaringan # bisa diakses dari HP di WiFi

Bawaannya localhost saja. Halaman ini memuat jawaban dan diagnosis anak,
jadi membukanya ke jaringan adalah keputusan sadar, bukan bawaan — dan
alamat WiFi berubah tiap ganti jaringan, sehingga dicetak saat dijalankan.
"""

from __future__ import annotations

import argparse
import socket
import sys
from http.server import ThreadingHTTPServer

import ai_store
import database
import auth
import sessions
from web import Penangan

PORT = 8724


def alamat_wifi() -> str:
    """IP di jaringan lokal, tanpa benar-benar mengirim paket."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def siapkan_admin_dan_pemilik() -> str | None:
    """Naikkan pemasangan lama ke model multi-keluarga. Idempoten.

    Kalau belum ada akun admin, akun guru PERTAMA dipromosikan (bootstrap
    deterministik — pemilik produk tidak perlu menyunting sandi.json lewat
    tangan), lalu seluruh siswa warisan yang ber-pemilik kosong dibackfill
    ke nama admin itu: data lama adalah keluarga si pengelola. Akun lama juga
    mendapat ID generasi stabil sebelum sesi baru dibuat. Tanpa berkas sandi
    (mode lokal) tidak ada yang diubah.
    """
    auth.pastikan_id_akun()
    admin = auth.pastikan_admin()
    if admin is None:
        return None
    with database.buka() as kon:
        kon.execute("UPDATE siswa SET pemilik = ? WHERE pemilik = ''", (admin,))
    return admin


def main() -> int:
    p = argparse.ArgumentParser(description="Sajikan halaman guru")
    p.add_argument("--jaringan", action="store_true",
                   help="izinkan akses dari perangkat lain di WiFi")
    p.add_argument("--port", type=int, default=PORT)
    p.add_argument("--setel-sandi", metavar="SANDI",
                   help="setel sandi guru lalu keluar")
    p.add_argument("--pengguna", default="guru",
                   help="nama pengguna untuk --setel-sandi (bawaan: guru)")
    arg = p.parse_args()

    if arg.setel_sandi:
        berkas = auth.simpan_sandi(arg.setel_sandi, arg.pengguna)
        print(f"sandi tersimpan: {berkas}")
        print(f"pengguna       : {arg.pengguna}")
        print("hash PBKDF2, izin berkas 600. Sandi tidak disimpan sebagai teks.")
        return 0

    database.siapkan()
    # Storage AI di-bootstrap eksplisit saat startup. Kehilangan berkas saat
    # proses sudah berjalan tetap fail-closed di guard; bukan dibuat ulang per call.
    ai_store.siapkan()
    ai_store.purge()
    # Token kedaluwarsa yang menumpuk di sesi.json ikut terbuang tiap kali
    # server dinyalakan (tanda lapangan: belasan token dari masuk-ulang).
    sessions.bersihkan()
    admin = siapkan_admin_dan_pemilik()
    inang = "0.0.0.0" if arg.jaringan else "127.0.0.1"

    # Palang kedua. Palang pertama ada di web.py (memeriksa tiap permintaan);
    # yang ini mencegah kelalaian yang lebih berbahaya — menjalankan server
    # terbuka ke jaringan padahal sandinya belum pernah disetel. Tanpa ini,
    # lupa satu langkah saat deploy berarti data anak terbuka tanpa palang
    # apa pun, dan tidak ada yang memberi tahu.
    if arg.jaringan and not auth.wajib_sandi():
        print("DITOLAK: --jaringan tanpa sandi.", file=sys.stderr)
        print(file=sys.stderr)
        print("Halaman ini memuat jawaban dan diagnosis anak. Setel sandi", file=sys.stderr)
        print("dulu:", file=sys.stderr)
        print(file=sys.stderr)
        print("    ./.venv/bin/python serve.py --setel-sandi 'sandi-anda'",
              file=sys.stderr)
        return 2

    with database.buka() as kon:
        n_siswa = len(database.daftar_siswa(kon))
        n_sesi = kon.execute("SELECT COUNT(*) AS n FROM sesi").fetchone()["n"]

    print(f"basis data : {database.BAWAAN}")
    print(f"isi        : {n_siswa} siswa, {n_sesi} sesi")
    print(f"sandi      : {'aktif' if auth.wajib_sandi() else 'TIDAK aktif (lokal saja)'}")
    if admin:
        print(f"admin      : {admin} (melihat semua keluarga)")
    print()
    print(f"  http://127.0.0.1:{arg.port}")
    if arg.jaringan:
        print(f"  http://{alamat_wifi()}:{arg.port}   (dari HP di WiFi yang sama)")
        print()
        print("  Halaman ini memuat jawaban & diagnosis anak. Jangan dibuka")
        print("  di jaringan publik.")
    print()
    print("Ctrl-C untuk berhenti.")

    server = ThreadingHTTPServer((inang, arg.port), Penangan)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nberhenti.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
