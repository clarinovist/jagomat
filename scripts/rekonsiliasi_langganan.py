"""Pembungkus dev lokal untuk CLI kanonis `mesin/rekonsiliasi_langganan.py`.

CLI kanonis ikut image (COPY *.py) supaya dapat dijalankan di container, mis.:

  docker exec osn-mesin python rekonsiliasi_langganan.py \
    --admin-db /data/admin-control.db --auth /data/sandi.json --belajar /data/latihan.db \
    --rahasia /run/secrets/midtrans/produksi-rahasia \
    --lease /data/langganan-rekonsiliasi.lock

Berkas ini menjaga perintah dev/test yang lama tetap bekerja:

  mesin/.venv/bin/python scripts/rekonsiliasi_langganan.py ...

Tanpa logika di sini — hanya meneruskan ke modul kanonis.
"""

import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
if str(AKAR / "mesin") not in sys.path:
    sys.path.insert(0, str(AKAR / "mesin"))

import subscription_produksi as prod  # noqa: E402,F401  (dipakai test/alat dev)
from rekonsiliasi_langganan import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
