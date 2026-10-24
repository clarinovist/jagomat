#!/bin/bash
# Tarik bundle operasional lengkap yang sudah dibuat saat maintenance terkontrol.
# Tidak menghentikan produksi, membuat snapshot live parsial, atau memangkas retensi.
set -euo pipefail
umask 077
DIREKTORI_SKRIP="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [ "$#" -ne 1 ]; then
  echo "Pakai: $0 <id-bundle-operasional>" >&2
  echo "Buat bundle lengkap lewat runbook docs/operational-backup.md terlebih dahulu; backup tiga DB lama tidak lagi dijalankan." >&2
  exit 2
fi
PYTHON="$DIREKTORI_SKRIP/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Interpreter proyek tidak tersedia." >&2
  exit 2
fi
exec "$PYTHON" -B "$DIREKTORI_SKRIP/../scripts/operational_backup.py" fetch \
  --id "$1" --host "${OSN_HOST_VPS:-biznet-sekolahdesain}" \
  --destination "$DIREKTORI_SKRIP/cadangan/operasional"
