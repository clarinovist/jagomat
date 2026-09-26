"""Rekonsiliasi langganan terjadwal: satu putaran bounded, lease, tanpa rahasia di output.

Entry kanonis yang IKUT IMAGE (COPY *.py) sehingga dapat dijalankan di container:

  docker exec osn-mesin python rekonsiliasi_langganan.py \
    --admin-db /data/admin-control.db --auth /data/sandi.json --belajar /data/latihan.db \
    --rahasia /run/secrets/midtrans/produksi-rahasia \
    --lease /data/langganan-rekonsiliasi.lock

Untuk dev/test lokal, `scripts/rekonsiliasi_langganan.py` membungkus modul ini.

Hanya invoice ber-intent yang diperiksa; tidak ada invoice, enrollment, receipt, atau
grant baru di luar hasil query provider. Output satu baris JSON agregat ke stdout —
tanpa identitas anak, tanpa id invoice, tanpa kredensial. Exit: 0 sukses, 2 konfigurasi
produksi tidak sah, 3 lease dipegang proses lain, 4 sakelar/state belum siap, 1 galat lain.
"""

import argparse
import json
from pathlib import Path
import sys
import time

import admin_store
import auth
import database
import subscription_produksi as prod
import subscription_worker as worker


def _argumen(argv=None):
    p = argparse.ArgumentParser(description="Rekonsiliasi langganan (satu putaran bounded).")
    p.add_argument("--admin-db", default=str(admin_store.BAWAAN))
    p.add_argument("--auth", default=str(auth.BERKAS_SANDI))
    p.add_argument("--belajar", default=str(database.BAWAAN))
    p.add_argument("--rahasia", default=str(prod.BERKAS_RAHASIA_BAWAAN))
    p.add_argument("--recovery", default=str(prod.BERKAS_RECOVERY_BAWAAN))
    p.add_argument("--lease", default="")
    p.add_argument("--batas", type=int, default=worker.BATAS_BAWAAN)
    p.add_argument("--jeda", type=int, default=worker.JEDA_BAWAAN)
    p.add_argument("--horizon-hari", type=int, default=worker.HORIZON_BAWAAN // 86400)
    p.add_argument("--sekarang", type=int, default=0,
                   help="jam eksplisit untuk pemulihan (default: jam sistem)")
    return p.parse_args(argv)


def main(argv=None, *, transport=None, clock=None):
    arg = _argumen(argv)
    # Jam dikoersi int: time.time() mengembalikan float, sedangkan validasi
    # waktu langganan (`subscription.waktu`) hanya menerima int — jalur cron
    # produksi tidak pernah memakai `--sekarang`.
    sekarang = int(arg.sekarang or (clock or time.time)())
    lease = arg.lease or str(Path(arg.admin_db).resolve().parent / "langganan-rekonsiliasi.lock")
    try:
        config, bawaan = prod.konfigurasi_dan_transport(path_rahasia=arg.rahasia)
    except (Exception, KeyboardInterrupt):
        print("konfigurasi produksi tidak sah", file=sys.stderr)
        return 2
    try:
        kesiapan = prod.kesiapan_produksi(path_recovery=arg.recovery)
        sakelar = prod.sakelar_efektif(arg.admin_db, kesiapan)
    except (Exception, KeyboardInterrupt):
        print("state langganan belum siap", file=sys.stderr)
        return 4
    if not sakelar.rekonsiliasi:
        print("sakelar rekonsiliasi belum siap", file=sys.stderr)
        return 4
    try:
        with worker.lease(lease) as didapat:
            if not didapat:
                print("lease dipegang proses lain", file=sys.stderr)
                return 3
            ringkas = worker.jalankan(arg.admin_db, arg.auth, arg.belajar, config=config,
                                      transport=bawaan if transport is None else transport,
                                      sekarang=sekarang, sakelar=sakelar, batas=arg.batas,
                                      jeda=arg.jeda, horizon=max(0, arg.horizon_hari) * 86400)
    except (Exception, KeyboardInterrupt) as galat:
        # Nama tipe saja: pesan exception bisa memuat path/nilai internal.
        print("putaran rekonsiliasi gagal (%s)" % type(galat).__name__, file=sys.stderr)
        return 1
    print(json.dumps(dict(ringkas, kesiapan=kesiapan), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
