#!/bin/bash
# Tarik backup harian Jagomat dari VPS, enkripsi, unggah ke R2.
# Dijalankan di Mac Pemilik oleh job Hermes `osn-cadangan-harian` (22:00 WIB); salinan
# kerja yang dipakai job ada di ~/.hermes/scripts/jagomat-backup-offsite.sh.
# Berkas ini sumber yang dilacak Git. Tidak berisi kunci/kredensial: kunci enkripsi
# ada di $KUNCI (0600, tidak pernah masuk VPS/repo) dan kredensial R2 ada di config rclone.
# Data anak tidak pernah disimpan plaintext di laptop: tar hanya di direktori
# sementara dan dihapus saat keluar.
set -euo pipefail
# OSN_OFFSITE_PATH_AWAL hanya untuk tes (menyisipkan perintah tiruan di depan PATH).
export PATH="${OSN_OFFSITE_PATH_AWAL:+$OSN_OFFSITE_PATH_AWAL:}/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

HOST="${OSN_HOST_VPS:-biznet-sekolahdesain}"
REMOTE="/opt/osn/backup-harian"
TUJUAN="${OSN_OFFSITE_TUJUAN:-r2:jagomat-app-cadangan/harian}"
KUNCI="${OSN_OFFSITE_KUNCI:-$HOME/.config/jagomat-backup/offsite.key}"
ALERT="${OSN_ALERT:-$HOME/.hermes/scripts/notify-telegram.py}"
UMUR_MAKS_JAM="${OSN_OFFSITE_UMUR_MAKS_JAM:-26}"
DASAR_TMP="${OSN_OFFSITE_TMP:-$HOME/.hermes/cache/scratch}"
mkdir -p "$DASAR_TMP"
TMP="$(mktemp -d "$DASAR_TMP/jagomat-offsite.XXXXXX")"

# Satu jalur keluar untuk semua kegagalan, termasuk `exit 1` eksplisit
# (trap ERR tidak menangkapnya, jadi alert tidak terkirim).
selesai() {
  local rc=$?
  rm -rf "$TMP"
  if [ "$rc" -ne 0 ] && [ -x "$ALERT" ]; then
    "$ALERT" "Jagomat: backup off-site GAGAL (exit $rc) pada $(date '+%d-%m %H:%M %Z'). Backup lokal VPS tetap jalan; cek ~/.hermes/logs/gateway.log atau jalankan jagomat-backup-offsite.sh manual." || true
  fi
  exit "$rc"
}
trap selesai EXIT

[ -s "$KUNCI" ] || { echo "kunci enkripsi tidak ada: $KUNCI" >&2; exit 1; }
command -v rclone >/dev/null || { echo "rclone tidak ada" >&2; exit 1; }
command -v openssl >/dev/null || { echo "openssl tidak ada" >&2; exit 1; }

ID="$(ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" \
  "sudo -n ls -1 $REMOTE | grep -E '^[0-9]{8}-[0-9]{6}\$' | sort | tail -1")"
case "$ID" in
  [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]) ;;
  *) echo "ID backup tidak sah: ${ID:-kosong}" >&2; exit 1 ;;
esac

# Bundle terbaru yang basi berarti backup 21:45 gagal; jangan unggah ulang bundle lama
# seolah-olah hari ini berhasil. ID memakai WIB (backup_harian._stempel).
UMUR_DETIK="$(python3 -I -c '
import datetime as dt, sys
wib = dt.timezone(dt.timedelta(hours=7))
dibuat = dt.datetime.strptime(sys.argv[1], "%Y%m%d-%H%M%S").replace(tzinfo=wib)
print(int((dt.datetime.now(wib) - dibuat).total_seconds()))
' "$ID")"
if [ "$UMUR_DETIK" -gt $((UMUR_MAKS_JAM * 3600)) ]; then
  echo "backup terbaru terlalu lama ($ID, $((UMUR_DETIK / 3600)) jam > $UMUR_MAKS_JAM jam): backup harian VPS kemungkinan gagal" >&2
  exit 1
fi

ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" \
  "sudo -n /usr/bin/python3 $REMOTE/backup_harian.py --validasi $REMOTE/$ID >/dev/null"
ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" \
  "sudo -n tar -C $REMOTE -czf - $ID" > "$TMP/$ID.tar.gz"

tar -tzf "$TMP/$ID.tar.gz" | grep -qx "$ID/manifest.json"
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
  -in "$TMP/$ID.tar.gz" -out "$TMP/$ID.tar.gz.enc" -pass "file:$KUNCI"
# Bukti kunci cocok: dekripsi harus menghasilkan tar yang bisa dibaca.
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in "$TMP/$ID.tar.gz.enc" -pass "file:$KUNCI" | tar -tzf - >/dev/null

rclone copyto "$TMP/$ID.tar.gz.enc" "$TUJUAN/$ID.tar.gz.enc" --no-traverse
rclone delete "$TUJUAN" --min-age 30d
echo "$(date '+%Y-%m-%dT%H:%M:%S%z') OK $ID $(stat -f%z "$TMP/$ID.tar.gz.enc") bytes terenkripsi"
