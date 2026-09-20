#!/bin/bash
# Cadangkan basis data mesin latihan dari VPS ke Mac ini.
#
# Alasan menariknya KE Mac, bukan menyimpan di VPS: VPS itu pernah
# di-null-route dan pernah jadi relay spam. Cadangan yang tinggal di mesin
# yang sama tidak melindungi dari hilangnya mesin itu.
#
# Memakai sqlite3 .backup, bukan cp: menyalin berkas SQLite yang sedang
# ditulis bisa menghasilkan salinan rusak yang baru ketahuan saat dipulihkan.
set -euo pipefail

INANG="${OSN_HOST_VPS:-vps-osn}"   # setel lewat lingkungan
# Ikuti checkout, termasuk saat folder induk diakses melalui alias kompatibilitas.
DIREKTORI_SKRIP="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
TUJUAN="$DIREKTORI_SKRIP/cadangan"
SIMPAN_HARI=30

mkdir -p "$TUJUAN"
CAP="$(date +%Y%m%d-%H%M%S)"

# Salinan konsisten dibuat di dalam container, lalu ditarik.
ssh -o ConnectTimeout=10 "$INANG" \
  "sudo -n docker exec osn-mesin python -c \"
import sqlite3
sumber = sqlite3.connect('/data/latihan.db')
tujuan = sqlite3.connect('/data/cadangan-sementara.db')
sumber.backup(tujuan)
tujuan.close(); sumber.close()
print('salinan konsisten dibuat')
\"" >/dev/null

ssh -o ConnectTimeout=10 "$INANG" \
  "sudo -n cat /opt/osn/data/cadangan-sementara.db" > "$TUJUAN/latihan-$CAP.db"

ssh -o ConnectTimeout=10 "$INANG" \
  "sudo -n rm -f /opt/osn/data/cadangan-sementara.db"

# Riwayat Pendamping terpisah dari data belajar. Jika DB-nya sudah terbentuk,
# tarik salinan konsisten tersendiri agar retensi/recovery tidak tercampur.
PENDAMPING_ADA="$(ssh -o ConnectTimeout=10 "$INANG" \
  "sudo -n test -f /opt/osn/data/pendamping.db && echo 1 || echo 0")"
if [ "$PENDAMPING_ADA" = "1" ]; then
  ssh -o ConnectTimeout=10 "$INANG" \
    "sudo -n docker exec osn-mesin python -c \"
import sqlite3
sumber = sqlite3.connect('/data/pendamping.db')
tujuan = sqlite3.connect('/data/cadangan-pendamping-sementara.db')
sumber.backup(tujuan)
tujuan.close(); sumber.close()
print('salinan Pendamping konsisten dibuat')
\"" >/dev/null
  ssh -o ConnectTimeout=10 "$INANG" \
    "sudo -n cat /opt/osn/data/cadangan-pendamping-sementara.db" \
    > "$TUJUAN/pendamping-$CAP.db"
  ssh -o ConnectTimeout=10 "$INANG" \
    "sudo -n rm -f /opt/osn/data/cadangan-pendamping-sementara.db"
  if ! sqlite3 "$TUJUAN/pendamping-$CAP.db" "PRAGMA integrity_check;" \
      | grep -q "^ok$"; then
    echo "GAGAL: cadangan Pendamping rusak, dihapus" >&2
    rm -f "$TUJUAN/pendamping-$CAP.db"
    exit 1
  fi
  echo "pendamping: $TUJUAN/pendamping-$CAP.db — integritas ok"
fi

# Ledger/pengaturan AI ikut dicadangkan terpisah. Isinya metadata agregat,
# tanpa prompt, respons, foto, atau credential.
AI_ADA="$(ssh -o ConnectTimeout=10 "$INANG" \
  "sudo -n test -f /opt/osn/data/ai-control.db && echo 1 || echo 0")"
if [ "$AI_ADA" = "1" ]; then
  ssh -o ConnectTimeout=10 "$INANG" \
    "sudo -n docker exec osn-mesin python -c \"
import sqlite3
sumber = sqlite3.connect('/data/ai-control.db')
tujuan = sqlite3.connect('/data/cadangan-ai-sementara.db')
sumber.backup(tujuan)
tujuan.close(); sumber.close()
\"" >/dev/null
  ssh -o ConnectTimeout=10 "$INANG" \
    "sudo -n cat /opt/osn/data/cadangan-ai-sementara.db" \
    > "$TUJUAN/ai-control-$CAP.db"
  ssh -o ConnectTimeout=10 "$INANG" \
    "sudo -n rm -f /opt/osn/data/cadangan-ai-sementara.db"
  if ! sqlite3 "$TUJUAN/ai-control-$CAP.db" "PRAGMA integrity_check;" \
      | grep -q "^ok$"; then
    echo "GAGAL: cadangan pengaturan AI rusak, dihapus" >&2
    rm -f "$TUJUAN/ai-control-$CAP.db"
    exit 1
  fi
  echo "pengaturan AI: $TUJUAN/ai-control-$CAP.db — integritas ok"
fi

# Cadangan yang tidak bisa dibuka bukan cadangan. Diperiksa tiap kali,
# bukan hanya saat dibutuhkan — saat dibutuhkan sudah terlambat.
if ! sqlite3 "$TUJUAN/latihan-$CAP.db" "PRAGMA integrity_check;" | grep -q "^ok$"; then
  echo "GAGAL: cadangan rusak, dihapus" >&2
  rm -f "$TUJUAN/latihan-$CAP.db"
  exit 1
fi

SISWA=$(sqlite3 "$TUJUAN/latihan-$CAP.db" "SELECT COUNT(*) FROM siswa;")
SESI=$(sqlite3 "$TUJUAN/latihan-$CAP.db" "SELECT COUNT(*) FROM sesi;")
JWB=$(sqlite3 "$TUJUAN/latihan-$CAP.db" "SELECT COUNT(*) FROM jawaban;")
UKURAN=$(du -h "$TUJUAN/latihan-$CAP.db" | cut -f1)

echo "cadangan: $TUJUAN/latihan-$CAP.db ($UKURAN)"
echo "isi     : $SISWA siswa, $SESI sesi, $JWB jawaban — integritas ok"

find "$TUJUAN" \( -name "latihan-*.db" -o -name "pendamping-*.db" -o -name "ai-control-*.db" \) \
  -mtime "+$SIMPAN_HARI" -delete 2>/dev/null || true
echo "tersimpan: $(find "$TUJUAN" -name 'latihan-*.db' | wc -l | tr -d ' ') cadangan latihan, $(find "$TUJUAN" -name 'pendamping-*.db' | wc -l | tr -d ' ') cadangan Pendamping, $(find "$TUJUAN" -name 'ai-control-*.db' | wc -l | tr -d ' ') cadangan pengaturan AI"
