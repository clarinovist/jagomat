# Runbook rilis pusat kendali admin

Status: **readiness source lokal; bukan bukti produksi siap atau izin operasi**.
Dokumen ini melengkapi [`production-release.md`](production-release.md), bukan
menggantikan policy/deployer/approval di sana.

## Kontrak persistensi kandidat

| State | Target | Sifat |
| --- | ---: | --- |
| DB belajar `/data/latihan.db` | skema aplikasi + `operasi_admin_siswa` | durable; data anak, provenance, dan receipt mutasi siswa |
| Auth `/data/sandi.json` | setiap akun punya `id_akun` + `revisi_auth`; receipt akun ada di envelope | durable dan privat; memuat hash credential, bukan sandi teks |
| Admin `/data/admin-control.db` | schema **4** | durable; config pendaftaran, journal, audit, anchor receipt, metadata batch/item/group/penyerahan tanpa alias |
| AI `/data/ai-control.db` | schema **2** pada candidate coordinator | durable; config/ledger/audit AI tanpa prompt/foto/credential |
| Pendamping `/data/pendamping.db` | schema **4** | durable; riwayat privat terpisah |
| Sesi `/data/sesi.json` | tidak dibackup untuk restore auth | ephemeral; harus dianggap invalid setelah restore |
| Draft `/data/transient/admin-drafts.db` | schema **2** | transient TTL 900 detik; wajib dikecualikan dari backup |
| Lembar/cache turunan | bukan bagian bundle authoritative | jangan dipakai sebagai sumber restore |

Upgrade harus eksplisit dan idempoten. Admin mendukung v1/v2/v3→v4 dan menolak
versi lebih baru. Receipt siswa dibuat eksplisit oleh
`admin_students.siapkan(path_db)`. Draft transient dibuat ulang eksplisit oleh
`admin_bulk.siapkan_transient(path)`; GET tidak boleh membuatnya. Candidate AI2
dan migratornya merupakan artefak coordinator. **Tidak pernah downgrade
`user_version`, menghapus kolom/receipt, atau menjalankan binary lama terhadap DB
yang lebih baru.**

## Batas helper lokal

`mesin/admin_backup.py` tidak mengambil snapshot produksi dan tidak memiliki cara
membuktikan semua writer aplikasi/cron/maintenance sudah berhenti. Karena itu:

- tidak ada parameter boolean `writes_held` yang diperlakukan sebagai bukti;
- helper hanya memvalidasi bundle yang telah dibuat saat quiescent dan menjalankan
  rehearsal pada turunan temp;
- snapshot coherent lintas SQLite+JSON tetap memerlukan maintenance/drain nyata
  serta verifikasi operator di jalur `deploy-v2`;
- jangan menjalankan `mesin/cadangkan.sh` lama sebagai bukti bundle ini: script
  itu memakai temp tetap, mengambil file terpisah, belum mencakup admin/auth, dan
  melakukan prune otomatis.

Ini sengaja membatasi klaim: source validator tersedia, tetapi backup produksi
belum ada sampai operator benar-benar membuat serta memvalidasi bundle exact.

## Prosedur backup coherent (produksi, hanya setelah approval exact)

1. Catat candidate digest, recovery digest kompatibel, revision, hash deployer,
   jendela waktu+timezone, RPO, dan `bundle_id` unik. Izin push bukan approval
   migrasi/backup/restore.
2. Aktifkan maintenance dan tahan **semua** writer: ingress POST, worker,
   scheduler/cron, dan container lain pada volume. Drain request in-flight.
   Socket count nol atau field `writes_held:true` saja bukan bukti.
3. Dengan urutan canonical **DB belajar → auth → admin SQLite → AI SQLite →
   Pendamping SQLite**, ambil salinan:
   - pegang `BEGIN IMMEDIATE` DB belajar;
   - pegang sidecar lock auth yang sama dengan `transaksi_json`;
   - gunakan SQLite backup API untuk `latihan.db`, `admin-control.db`,
     `ai-control.db`, dan `pendamping.db` ke nama temp unik;
   - salin `sandi.json` saat lock auth masih dipegang;
   - lepaskan lock setelah seluruh salinan dan fsync selesai.
4. Tempat tujuan harus direktori 0700; file dan manifest 0600, regular file,
   satu hardlink, tanpa symlink. Transfer terenkripsi ke storage lokal ignored.
5. Jangan sertakan `sesi.json`, DB draft transient, lembar, cache, atau log.
   Jangan mencetak username/hash/record pada stdout. Jangan prune selama migrasi.
6. Buat manifest atomik `admin_backup.buat_manifest(...)`, lalu jalankan
   `validasi_bundle(...)`. Validasi awal menerima backup DB belajar lama sebelum
   tabel receipt ada; rehearsal candidate wajib membuat `operasi_admin_siswa`.
   Hash, ukuran, schema, integrity/FK, dan metadata revisi auth diperiksa tanpa
   mengeluarkan isi akun.
7. Jika ada journal admin pending/uncertain pada cutoff, hasil validator memberi
   `perlu_rekonsiliasi=True`: **jangan membuka writer atau menyatakan recovery
   siap** sebelum operasi itu direkonsiliasi melalui jalur domain yang teruji.
   Journal sukses tanpa receipt pasangan auth/siswa ditolak validator walaupun
   hash masing-masing file cocok. Validasi linkage ini bukan bukti bahwa cutoff
   seluruh file identik; bukti quiesce operator tetap wajib. Jangan mengubah
   backup dan jangan menganggap `reserved` sebagai gagal aman.
8. Jalankan `rehearsal_bundle(..., migrator_ai=<candidate AI2>)` pada turunan.
   Migrator berjalan dua kali untuk bukti idempoten. Backup induk harus byte-identik.
9. Bila write hold pernah dilepas atau satu file diambil ulang, buang klaim set
   coherent dan ambil **seluruh bundle baru** dengan cutoff/bundle ID baru.

## Validasi dan rehearsal lokal sintetis

Contoh ini hanya untuk fixture sintetis, bukan path `/data` atau backup keluarga:

```python
from pathlib import Path
import admin_backup

bundle = Path("/tmp/bundle-sintetis")  # sudah berisi 5 file durable dengan mode 0600
admin_backup.buat_manifest(bundle, bundle_id="uji-lokal-001", cutoff=1700000000)
ringkas = admin_backup.validasi_bundle(bundle)
ringkas = admin_backup.rehearsal_bundle(bundle, migrator_ai=migrator_ai2_candidate)
```

`RingkasanBackup` hanya mengembalikan bundle ID, cutoff, jenis file, versi admin/
AI, serta rentang revisi auth. Tidak ada nama akun, hash, payload, jawaban, atau
record anak.

## Cutover dan recovery

1. Image candidate/recovery dibangun dan diverifikasi oleh CI dari digest exact.
   Coordinator memiliki `scripts/verify_release_image.py`; jangan mengubah probe
   atau `RECOVERY_SHA` hanya agar candidate lolos.
2. Fingerprint candidate/recovery wajib identik sebelum stop pada **kedua jalur**
   rutin dan `deploy-v2`; approval operator bukan bukti recovery kompatibel.
   Recovery pinned lama masih AI1 dan tidak memenuhi kontrak kandidat admin baru:
   rilis ini **tertahan sebelum swap**, bukan mencoba rollback binary lama setelah
   startup migrasi. Routine juga menuntut current/policy cocok. Jangan mengganti
   pin/hash policy demi lolos. Versi deployer yang ditingkatkan pun belum dipasang
   di VPS; rollout admin membutuhkan prosedur dan approval exact tersendiri.
3. Jalankan migrasi hanya di bawah write hold menggunakan jalur `deploy-v2` dan
   approval sekali pakai exact pair. Jangan membuka writer sebelum schema/readiness
   serta integrity/FK seluruh durable state lolos.
4. Cookie legacy harus login ulang. Setelah restore, hapus/abaikan seluruh
   `sesi.json`; validasi principal tetap bergantung `id_akun` + `revisi_auth`
   mutakhir. Jangan memulihkan cookie dari backup lama.
5. Draft transient tidak direstore; buat file baru eksplisit setelah durable state
   siap. Kehilangan respons credential bulk dipulihkan lewat reset individual
   setelah tinjauan, bukan membaca secret dari backup.
6. Restore produksi memerlukan approval pemulihan data terpisah. Restore adalah
   satu set berdasarkan bundle/cutoff yang sama; jangan mencampur file dari waktu
   berbeda. Setelah restore, reconcile journal/receipt sebelum membuka write.
7. Recovery image harus memahami schema admin4/AI2/receipt siswa/revisi auth.
   Bila tidak, tetap maintenance; jangan downgrade DB.

## Retensi dan privasi

- Backup maksimal **30 hari**, tetapi prune hanya melalui job terpisah setelah
  bundle baru tervalidasi dan tidak selama jendela migrasi/recovery.
- Audit admin disimpan **180 hari**; purge audit tidak menghapus journal/receipt.
- Lifecycle startup dan janitor periodik 60 detik menjalankan purge terbatas.
  Draft melewati TTL 900 detik ditolak akses; pembersihan fisik mengikuti siklus
  maintenance berikutnya (dapat tertunda ketika ada lock/beban/backlog). Metadata
  batch/item/group/penyerahan durable tetap tersedia tanpa alias atau sandi.
- Receipt/journal tidak otomatis ikut purge audit.
- Sesi dan draft transient tidak masuk backup.
- Auth backup memuat hash credential dan tetap data privat: izin 0600, transfer
  terenkripsi, storage ignored, akses terbatas, tanpa log isi.

## Checklist klaim

- **Source tersedia:** file/helper/test ada di source.
- **Source teruji:** scoped test dan rehearsal sintetis hijau.
- **Image terverifikasi:** hanya setelah probe milik coordinator pada digest exact.
- **Backup produksi valid:** hanya setelah bundle exact dibuat saat writer benar-
  benar quiescent dan validator lulus.
- **Terpasang/live/sehat:** hanya setelah deploy approved, inspeksi digest/schema,
  dan smoke publik kanonis.

Jangan menyamakan salah satu tahap di atas dengan tahap berikutnya.
