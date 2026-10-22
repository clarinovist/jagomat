# Jagomat — Mesin Latihan

Aplikasi matematika SD: **siapkan latihan → anak mengerjakan → guru meninjau dan
mengonfirmasi → ikuti langkah berikutnya**. Fokus sekarang guru les in-house;
peran guru tetap mencakup orang tua. [Spesifikasi](../docs/spec.md) ·
[Status dan pekerjaan tersisa](../docs/status-proyek.md) · [Arsitektur](../docs/context.md).

## Menggunakan website

Situs kanonis **https://jagomat.id**. Masuk melalui `/masuk`; guru menuju `/guru`,
murid ke ruang latihan, admin ke panel pengelola. Akses awal nonkomersial; keberadaan
kode langganan bukan penawaran berbayar aktif.

1. **Beranda guru:** cari anak milik Anda atau filter kelompok langkah berikutnya.
   Yang terlama menunggu konfirmasi diprioritaskan. Kelompok bukan peringkat kemampuan.
2. **Profil anak:** empat tab **Beranda, Latihan, Riwayat, Perkembangan**. Beranda
   menunjukkan satu CTA dari siklus; latihan manual tetap tersedia. Kelas sekolah
   opsional, berbeda dari konfigurasi internal P3–P6.
3. **Kerjakan:** gunakan halaman murid/tautan satu sesi atau cetak lembar dari
   halaman sesi. Kunci dan pembahasan hanya untuk guru, bukan untuk dibagikan ke anak.
   Seed deterministik membantu reproduksi, **bukan jaminan soal tidak pernah berulang**.
4. **Dari kertas:** unggah foto sebagai bukti. Jika vision tidak dikonfigurasi,
   halaman **Isi dari lembar** meminta transkripsi guru tanpa menyebutnya bacaan AI.
   Terapkan tidak menggantikan tinjauan dan konfirmasi hasil.
5. **Tinjau:** periksa jawaban, cara dan pemahaman; usulan diagnosis bukan keputusan
   final. Simpan draf bila perlu, lalu **Konfirmasi hasil sesi** secara eksplisit.
6. **Perkembangan:** Ringkasan/Per materi memproyeksikan bukti yang sama dengan
   Beranda. Angka aktivitas bukan skor kemampuan; belum dinilai bukan tidak mampu.

Cetak lewat browser pada ukuran kertas/skala yang sesuai preview. Untuk cetak ulang,
buka **sesi tersimpan**: snapshot/bank historis menjadi acuan; jangan membuat sesi baru
hanya dari seed dan menganggap hasilnya selalu byte-identik setelah perubahan versi.

## Membaca diagnosis

| Kode | Dugaan yang perlu diperiksa | Arah tindakan |
| --- | --- | --- |
| B | Baca/makna soal | Minta anak menjelaskan yang diketahui dan ditanyakan |
| K | Konsep | Gunakan pengenalan/contoh atau intervensi yang cocok |
| H | Hitung | Periksa langkah perhitungan, bukan langsung menambah drill |
| E | Penulisan akhir | Cocokkan hasil cara dengan jawaban akhir |
| N | Menebak | Periksa alasan/pemahaman; benar saja belum cukup |
| T | Belum mengenal | Pengenalan lalu probe, bukan label kelemahan |

Tidak ada aturan “K≥3 turunkan level” atau “H banyak pasti sudah paham”. Sumber
status/rekomendasi adalah [siklus belajar](../docs/siklus-belajar-terpandu.md),
dengan konteks, bukti terkonfirmasi, jeda dan pemeriksaan penjelasan. Malrule adalah
hipotesis prosedur, belum bukti bahwa anak sungguhan memakai prosedur tersebut.

## Akun dan batas akses

- `/akun` menyediakan pengaturan akun, kartu daftar anak/Kelola, dan akun latihan
  melalui `?section=`. Anak ber-riwayat/bukti terkait tidak bisa dihapus sembarangan.
- Nama tampilan anak dan login berbeda; nama anak dapat sama antar keluarga, login
  harus unik. Menghapus login bukan menghapus profil atau seluruh data keluarga.
- Guru hanya mengakses datanya sendiri; resource asing → **404 identik**, tanpa
  efek samping. Murid tidak melihat kunci/malrule/diagnosis/laporan.
- Admin dapat mengelola data murid lintas keluarga melalui permukaan pengelola,
  tetapi tidak mengubah akun/sandi admin lain. Jangan mengedit DB/auth manual.
  Bootstrap `serve.py` dapat mempromosikan guru pertama bila admin belum ada dan
  memberi pemilik pada data warisan; bukan perintah menjalankannya terhadap data
  produksi/preview tanpa memahami efek startup.
- Keluar memakai POST dan mencabut sesi. Reset/hapus keluarga memerlukan verifikasi
  independen dan [prosedur dukungan](../docs/support-operations.md).

## Bantuan dan AI

Bantuan statis tersedia tanpa AI. Playbook berisi **15 draf P3**, tampil dengan
peringatan permanen; belum disahkan manusia. [Prosedur review](../docs/playbook-guru.md).

**Pendamping** adalah fitur AI, bukan sebutan orang dewasa. Konteks dan pengiriman
ke provider memerlukan izin sesuai produk. Usulan tidak mengubah diagnosis/bukti
secara otomatis. Kelola data dari Akun: hapus satu chat atau cabut izin, termasuk
ketika provider mati. Hapus akses aktif tidak menjanjikan penghapusan fisik semua
salinan seketika. [Kontrak runtime/retensi](../docs/pendamping-runtime.md).

Kunci provider disimpan privat di host, tidak di repo/image/log. Konfigurasi
`DEEPSEEK_MODEL` dan `DEEPSEEK_VISION_MODEL` mengikuti deployer teruji; jangan
menyalin secret dari sumber yang ditebak. Fitur AI dapat nonaktif ketika konfigurasi
hilang; kesehatan halaman publik tidak membuktikan provider bekerja.

## Pengembangan lokal

Repo Git benar berada **satu tingkat di atas folder ini**. Semua Git memakai
`git -C /Users/nugroho/Documents/jagomat …`, bukan repo basi `mesin/.git`.
Interpreter existing: `mesin/.venv/bin/python` (lokal3.9.6); CI/container3.12.
Runtime hanya stdlib; dev dependency pytest/pytest-xdist. Jangan membuat ulang
venv atau menjalankan `setup_db.py` hanya untuk membaca/menguji kode.

```bash
cd /Users/nugroho/Documents/jagomat
# Contoh scoped test; sesuaikan dengan perubahan.
mesin/.venv/bin/python -m pytest mesin/__tests__/test_generator.py -q -W error -p no:cacheprovider
# Sesudah stage scope yang direview; membaca index Git.
mesin/.venv/bin/python scripts/check_repo.py
```

Full suite sebelum rilis memakai CI empat shard, bukan `-n auto` lokal karena test
HTTP berbagi socket. Preview harus memakai DB/sandi/session temp dan fixture
sintetis; **jangan menjalankan `serve.py` dengan default data nyata untuk preview**.
Panduan lengkap: [workflow](../CLAUDE.md), [preview/verifikasi](../docs/workflow-reference.md).
CLI `generate_worksheet.py` tetap alat latihan manual; gunakan `--help` dan path
keluaran terisolasi, bukan asumsi CLI mengorkestrasi siklus terpandu.

## Struktur kode

| Area | Modul |
| --- | --- |
| Topik/soal | `topics.py`, `topic_*.py`, `templates.py`, `generator.py` |
| Snapshot/lembar | `question_views.py`, `render.py`, `worksheets.py` |
| Data/identitas | `database.py`, `*_store.py`, `*_schema.py`, `auth.py`, `sessions.py`, `students.py` |
| Belajar/laporan | `diagnosis.py`, `learning_cycle.py`, `learning_cycle_service.py`, `reports.py`, `mastery_*` |
| Halaman/HTTP | `web.py`, `*_http.py`, `*_pages.py`, `teacher_shell.py`, `child_*` |
| Layanan | `assistant_*`, `ai_*`, `subscription_*`, `midtrans_*`, `admin_*`, `research_*` |
| Gaya | `design_tokens.py`, `style_stitch.py`, `teacher_style.py`, `admin_style.py`, `child_*_style.py` |

Peta façade dan alasan boundary: [referensi arsitektur](../docs/architecture-reference.md).
`konten/` internal guru, `publik/` aset publik; jangan mencampurkan keduanya.

## Produksi, CI dan backup

- Domain `https://jagomat.id`, SSH `biznet-sekolahdesain`, container `osn-mesin`,
  data `/opt/osn/data`, image `ghcr.io/clarinovist/osn-mesin-latihan`.
- **Push bukan deploy.** CI push menjalankan palang/tes cepat; dispatch menjalankan
  full kandidat+recovery, build/probe/pair. Job `pasang` tetap literal false.
- Pemasangan memakai pasangan **digest exact** yang lolos CI, bukan `latest` atau
  sekadar SHA/tag. Preflight live sebelum maintenance, backup/rehearsal, approval
  sekali pakai, swap/health dan pemulihan akses mengikuti [runbook](../docs/production-release.md).
- Recovery adalah image pinned kompatibel, **bukan selalu image sebelumnya**.
  Recovery sehat setelah kegagalan kandidat tetap kegagalan rilis; tidak auto-restore DB.
- Smoke anonim: `/`200, `/akun`401, `/murid/`303 ke `/masuk`. Jangan memakai akun
  atau data anak untuk smoke dan jangan membuang log privat ke chat.
- `cadangkan.sh` adalah helper lama dua DB dengan retensi; **bukan** backup lengkap
  rilis saat ini. Bundle inti: empat DB+auth; riset terpisah. Jadwal/off-site/restore
  berkala perlu bukti operasional sendiri. Jangan menjalankan prune atau restore
  hanya demi perapian. Tidak build di VPS atau menyalakan Docker lokal otomatis.

```bash
gh run list --repo clarinovist/jagomat --branch main
gh run watch <id-run> --repo clarinovist/jagomat --exit-status
```

## Batas dan sejarah

- Katalog Batch A–C/bank kalimat aktif tidak mengesahkan semua97 template. Audit
  lanjutan dan review manusia tetap dibedakan dari kelolosan tes mesin.
- Revisi penilaian baru default0; pilot bank90 item offline, belum serving authored.
  [Katalog](../docs/catalog-corrections.md) · [Pilot](../docs/catalog-pilot.md).
- Penerimaan perangkat nyata, efektivitas mengajar, dan kecepatan transkripsi belum
  boleh disimpulkan dari screenshot/CI. Pembatalan/penundaan tetap dihormati.
- Riwayat eksperimen variasi dan metrik sampel lama dipindahkan ke
  [riwayat kualitas soal](../docs/question-quality-history.md); bukan backlog otomatis.
- Data anak, sesi, credential, riset privat, cache dan backup tetap ignored;
  jangan `git add -f` atau mengirimnya ke layanan evaluasi eksternal.
