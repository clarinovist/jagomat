# Backup operasional Jagomat

## Status audit25 Oktober2026

- Backup rilis lengkap tersedia; itu berbeda dari jadwal backup rutin.
- Inventaris lokal tidak menemukan LaunchAgent/cron Jagomat. Di VPS, cron yang
  ditemukan untuk backup adalah milik PolyFlow dan skripnya tidak mencakup Jagomat.
  Belum ada bukti scheduler Jagomat otomatis; audit ini **tidak memasang cron baru**.
- Skrip lama hanya menyalin tiga DB terpisah, tidak menyertakan auth/admin/riset/
  lampiran, memakai nama temp tetap, dan memangkas30hari. Jalur lama diganti
  entrypoint **fetch paket lengkap existing**; tidak lagi mengklaim backup parsial
  sebagai pemulihan aplikasi utuh. Tidak ada backup lama yang dihapus atau retensi
  existing yang diubah. Kebijakan retensi tetap berlaku dan perlu operator;
  tooling ini tidak melakukan prune otomatis.

## Cakupan paket

`operasional/<id>/` privat:

- `bundle/`: empat DB durable dan `sandi.json`, dengan manifest/validator
  `admin_backup` existing;
- `riset-separate.db`: salinan terpisah dengan validasi schema+instrumen kanonis
  `research_store.buka_baca`; retensi riset tetap terpisah;
- `lampiran/`: seluruh berkas foto; setiap referensi metadata harus menunjuk file
  aman yang ada. Direktori sumber belum terbentuk sah hanya bila tanpa referensi;
- `operational-manifest.json`: revision/digest aplikasi, cutoff, daftar/hash/ukuran
  file dan direktori. Tidak berisi isi jawaban, nama anak, atau credential.
  Path lampiran tetap privat, bukan untuk log/prompt.

Tidak menyertakan sesi/transient, lembar/cache generated, arsip backup lain,
provider credential atau konfigurasi host. **Ini paket data aplikasi, bukan backup
seluruh VPS.** Pemulihan host juga membutuhkan image exact, config/secret existing
melalui inventaris privat, dan rotasi/rekonsiliasi sesuai runbook. Jangan memulihkan
sesi login lama atau consent epoch tanpa prosedur domain.

## Capture terkontrol, bukan backup hot lintas-DB

Tool `scripts/operational_backup.py` tidak menghentikan server atau memasang hold.
Operator memakai maintenance/drain existing dari [runbook rilis](production-release.md),
setelah preflight current/image/schema sehat. Semua writer (HTTP, cron, worker,
proses file lain) harus ditahan. Jangan memakai produksi sebagai test.

Capture memverifikasi app `exited`, maintenance terpasang, dua cron writer
terkomentar, tidak ada container lain me-mount data/ancestor/subtree dan fuser
hanya melihat collector sendiri. Lock deploy mencegah persaingan deployment;
DB/auth diambil berurutan belajar→auth→admin→AI→Pendamping→riset. Caller wajib
mempertahankan hold selama capture; pemeriksaan sesaat bukan penghalang proses
root nakal. Tidak menjalankan callback DB/provider atau migrasi saat capture.

Sesudah gate CI exact dan pemasangan tooling privat terverifikasi, operator root:

```text
python3 -B /opt/osn/backup-tool/scripts/operational_backup.py capture --id <id-baru> --revision <SHA-current> --image sha256:<digest-current>
```

Target tetap `/opt/osn/data`, output `/opt/osn/cadangan/operasional/<id>`. ID hanya
huruf kecil/angka/tanda-hubung,2–80 karakter; tidak ada path bebas di capture.
Tidak menimpa. Salinan memakai SQLite backup API, auth lock dan copy foto. Mode
journal salinan dinormalkan ke DELETE; header dan WAL kosong diperiksa sebelum
sidecar salinan milik collector dibersihkan. Mode/sidecar DB live tidak diubah. Output
stage privat baru dipublikasikan setelah validator/hash/fsync lulus. Failure
meninggalkan `.partial-*` privat, bukan marker sukses. Jangan menghapusnya sebelum
penyebab diketahui. Setelah capture dan kondisi data sehat, pulihkan akses segera;
transfer dan rehearsal tidak perlu memperpanjang downtime.

## Transfer off-site ke Mac existing

Dari akar repo:

```bash
bash mesin/cadangkan.sh <id-bundle-operasional>
```

Script memakai interpreter proyek, alias `biznet-sekolahdesain` (override
`OSN_HOST_VPS` hanya target yang telah diverifikasi), SSH batch existing. Destination
mengikuti lokasi repo/alias, bukan cwd/home lama:
`mesin/cadangan/operasional/<id>`. File privat tidak masuk log/chat atau Git.

Export memvalidasi paket sebelum stream. Transfer gagal tetap `.transfer-*` privat;
extractor menolak path traversal, symlink/hardlink/perangkat, duplikat, >100.000
entri atau total>2GiB. Tidak memakai `extractall`. Setelah hash/schema/linkage/ID
lulus dan direktori tersinkron, staging di-rename atomik. Output sebelumnya tidak
ditimpa. Backup2GiB+ perlu rencana ukuran terpisah, bukan melemahkan batas diam-diam.

`validate <path>` read-only; tidak memperbaiki backup rusak. Manifest dan hash
mendeteksi perubahan, **bukan autentikasi atau bukti quiesce**; kepercayaan asal
berasal SSH terverifikasi dan prosedur operator. Mac tetap perlu perlindungan disk,
akses dan kebijakan retensi. Lokasi Mac tidak tersedia saat laptop mati; tidak
mengklaim off-site otomatis24/7.

## Pemulihan dan verifikasi

Uji hanya pada turunan privat/sintetis, tidak restore live. Validator memastikan
core/hash/schema/FK/auth/linkage foto/riset. Rehearsal startup memakai artifact exact
teruji dan salinan terisolasi, tanpa network; periksa idempotensi, preservasi dan
kebutuhan rekonsiliasi. Restore live merupakan operasi terpisah: sesi diinvalidasi,
izin/sensor dan billing direkonsiliasi sesuai kontrak, backup sebelum cutover,
operator memverifikasi target dan recovery. Jangan menimpa seluruh data dengan
`cp` atau menghapus histori untuk membuat startup hijau.

Tes: `test_operational_backup*`, `test_backup_location`, validator core/riset existing.
Mutation menghapus guard hash/linkage/schema/writer/traversal untuk membuktikan
kegagalan ditangkap; data sintetis saja. Status live/hasil satu eksekusi dicatat
terpisah di plan/runbook, bukan disimpulkan dari keberadaan skrip.

## Yang tetap terbuka

1. Frekuensi/jam backup dan toleransi downtime berulang belum diputuskan.
2. Off-site otomatis independen dari laptop belum dipilih/diotorisasi.
3. Retensi per domain, bukti penghapusan, alert kegagalan dan restore berkala perlu
   dioperasionalkan bersama keputusan scheduler; tidak dianggap selesai oleh satu
   backup manual yang lulus.
