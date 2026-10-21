# Playbook guru — kontrak kerangka dan ulasan

## Status dan batas

Prioritas Fase 2 berdasarkan analisis kode; observasi guru sengaja dilewati atas
keputusan pemilik, bukan bukti kebutuhan tervalidasi. Pilot/pengembangan hanya
memakai data sintetis. **Reviewer matematika manusia belum ditetapkan.**
Agent hanya menyusun draf. Pengesahan final wajib penulisan/penyuntingan dan review
manusia; tidak ada LLM runtime yang menentukan isi, diagnosis, atau rekomendasi.

**Pengecualian eksplisit pemilik 2026-10-22 (pilihan B): draf boleh tampil ke semua
akun guru sebelum review manusia.** Ini melonggarkan gerbang tampil sebelumnya,
bukan pengesahan isi atau bukti bahwa isinya benar. Risiko isi ajar yang belum
diperiksa manusia tetap ada. Guru harus memeriksanya, bukan menganggapnya panduan final.

Konten di `mesin/konten/playbook_p3.json` tetap `draf` dengan
reviewer/tanggal/versi_review/sha256_review `null`. Peringatan “DRAF — belum direview
manusia; jangan dianggap panduan ajar final” terlihat di summary slot, saat tertutup
maupun terbuka. Kecocokan fokus/profil/pendekatan tetap wajib; semua guru hanya
mengakses resource miliknya. JSON bukan aset publik atau rute unduh. Materi existing
tidak diganti atau diklaim telah direview melalui playbook.

## Kontrak teknis

Envelope `versi_format: 1`, `entri: [...]`. Identitas unik:
`(template_id, profil, kode_intervensi, malrule_id)`. Profil memakai keanggotaan
komposisi eksplisit; P3 internal bukan kelas sekolah. `malrule_id: null` berarti
fokus tanpa malrule, **bukan wildcard**. Entri tidak diwariskan ke profil lain.

Isi plain text: `miskonsepsi`, `batas`, `urutan` (benda/gambar/simbol), 2–3
`pertanyaan`, `pendekatan` (ID existing dan contoh berbeda), `tanda_paham`, `sumber`,
`versi`, `saksi_seed`. Saksi generator membuktikan ID/kode tersedia pada konteks
tersebut, bukan seluruh variasi atau kebenaran pedagogis. Batas varian harus
diperiksa manusia; entri tidak boleh disahkan bila petunjuk hanya cocok sebagian
varian tanpa penjelasan batas yang memadai.

Metadata review: `status`, `reviewer`, `tanggal_review` (YYYY-MM-DD), `versi_review`,
`sha256_review`. Sidik SHA-256 berasal dari JSON seluruh field selain lima metadata
review, UTF-8, kunci terurut, pemisah `,` dan `:`, tanpa ASCII escaping.
`teaching_playbook.sidik_isi()` menyediakan hitungan deterministik.
Hash mengikat isi dan versi, **bukan bukti bahwa reviewer manusia benar-benar ada**;
proses review manusia dan riwayat Git tetap diperlukan. Agent tidak mengisi status
`disahkan`, identitas reviewer, tanggal, atau hash pengesahan konten runtime.

Loader membaca path paket tetap hanya ketika dipanggil; tanpa I/O saat impor,
DB/network, atau cache yang mempertahankan isi dicabut. Entri rusak, identitas
ambigu, metadata draf tidak seluruhnya null, atau hash/versi ulasan disahkan tidak
cocok → fragmen kosong, bukan error halaman atau pengganti materi/CTA. Draf valid
boleh tampil dengan peringatan sesuai pengecualian pemilik; valid secara teknis
**bukan** pengesahan pedagogis. Disahkan rusak tidak boleh fallback ke draf.
Penghapusan/pengubahan konten berlaku pada pembacaan berikutnya. Test pengesahan
positif memakai fixture sintetis terpisah, tidak mengesahkan konten nyata. JSON dibawa image melalui COPY internal, bukan folder aset/publik.

## Ulasan manusia (belum dilakukan)

Tersedia **15 draf, 0 disahkan**, satu malrule K per pola P3, dengan dua contoh
berbeda per entri. Bukan cakupan semua malrule atau lima kode lainnya. Antrean dan
lembar isian reviewer: [ulasan P3](playbook-ulasan-p3.md). Validasi memakai katalog2;
recovery katalog1 tidak dipaksa menerima identitas baru.

Untuk setiap entri, reviewer perlu menjawab dan menyimpan catatan Markdown:

1. Apakah dugaan miskonsepsi cocok dengan malrule dan **seluruh varian P3 yang dicakup**?
   Apakah bahasa menyatakan dugaan yang diperiksa, bukan diagnosis baru?
2. Apakah semua hitungan, satuan, diagram yang dijelaskan, dan contoh benar?
3. Apakah benda → gambar → simbol dapat dilakukan tanpa melompati konsep?
4. Apakah pertanyaan memancing penjelasan, bukan membocorkan jawaban latihan anak?
5. Apakah contoh tiap pendekatan berbeda dan sesuai `pendekatan_id` existing?
6. Apakah indikator pemahaman tidak menyamakan hafalan/jawaban benar dengan kelulusan?
7. Apakah sumber dapat diperiksa dan batas bantuan/varian cukup jelas?

Format catatan: identitas entri, versi dan sidik isi yang diperiksa; keputusan
**setuju / ubah / tolak**; jawaban tujuh pertanyaan; koreksi; identitas reviewer dan
tanggal ditulis manusia. Tampilan draf tidak menandakan keputusan setuju.

- **Ubah:** manusia menyunting isi, menaikkan versi, mengosongkan metadata pengesahan,
  tetap draf, lalu mengulang review exact.
- **Tolak:** keluarkan entri dari bundle runtime agar tidak tampil sebagai draf;
  pertahankan catatan penolakan dan sejarah Git. Tulis sebab dan batas perbaikan.
- **Setuju:** hanya setelah penulisan/penyuntingan serta review manusia selesai,
  manusia sendiri mencatat reviewer, tanggal, versi_review, sidik isi dan `disahkan`.
  Jalankan validasi/test; perubahan konten setelah itu membatalkan sidik ulasan.

Tidak ada antarmuka admin atau migrasi DB dalam fase ini. Izin tampil draf tidak
mengizinkan agent mengisi pengesahan atau menghapus label draf. Playbook tidak menentukan status belajar; sumber
keputusan tetap `learning_cycle.py`. Rute murid, tautan sesi, dan resource guru
asing tidak boleh membaca loader atau menerima fragmennya.
