# Lembar ulasan manusia — 15 draf P3

**Belum direview manusia. Tidak ada entri disahkan.** Ini antrean ulasan, bukan
sertifikasi atau hasil observasi guru. [Prosedur dan tujuh pertanyaan](playbook-guru.md#ulasan-manusia-belum-dilakukan)
berlaku pada setiap baris. Konten: `mesin/konten/playbook_p3.json` versi entri 1;
katalog writer2, profil internal P3. Masing-masing satu malrule K per pola, bukan
cakupan seluruh malrule/B/H/E/N/T. Data/identitas contoh sintetis.

Pemilik memilih B pada 2026-10-22: draf boleh tampil kepada semua guru dengan
peringatan permanen sebelum review. Ini pengecualian gerbang tampil, **bukan**
pengesahan matematika; kolom keputusan manusia di bawah tetap belum diisi.

Pemilihan 15 pola disetujui pemilik berdasarkan pemetaan awal tanpa fokus.
Seed 0–24 menghasilkan 375 soal, masing-masing pola 25 kali; bukan statistik
kesalahan atau bukti pola paling dibutuhkan guru. Satu entri tidak otomatis cocok
seluruh variasi; reviewer harus memeriksa batas varian yang tertulis.

| Pola | Malrule | Perhatian ulasan | Keputusan manusia |
|---|---|---|---|
| luas_kotak_satuan | datar.hanya_satu_baris | Daerah pengisi, satuan persegi vs panjang | Belum diisi |
| benar_salah_pengandaian | pengandaian.bekal_1 | Pasti vs mungkin; bukan semua varian | Belum diisi |
| deret_aritmetika | aritmetika.beda_dikira_satu | Beda tetap; tidak mengklaim pola tunggal | Belum diisi |
| jangkauan_data | jangkau.arah_salah | P3 terbesar/terkecil, bukan otomatis rumus jangkauan | Belum diisi |
| simetri_bangun | simetri.hitung_sisi | Bentuk kertas tepat; garis lipat bukan jumlah sisi | Belum diisi |
| tabel_penalaran | tabel.terendah | Arah dua perbandingan; tertinggi vs terendah | Belum diisi |
| deret_aritmetika_turun | aritmetika_turun.arah_dibalik | Pengurangan tetap, bukan pembagian | Belum diisi |
| median_modus | modus.kedua | P3 modus, bukan median; satu modus pada contoh | Belum diisi |
| keliling_luas_datar | datar.tukar_luas | Apakah contoh pertama angka luas/keliling sama membingungkan? | Belum diisi |
| soal_uang | uang.salah_bagi_uang_besar | k+1 bagian; uang contoh bukan harga nyata | Belum diisi |
| deret_geometri | geometri.pola_tambah_dipaksakan | Perkalian tetap vs selisih terakhir | Belum diisi |
| tabel_turus | turus.terkecil | Varian terbanyak; kategori vs frekuensi | Belum diisi |
| soal_umur | umur.selisih_umur_n_tahun | Dua orang katalog2; waktu bersama, bukan ayah-anak | Belum diisi |
| deret_bertingkat | bertingkat.selisih_terakhir_diulang | Selisih kedua tidak selalu satu | Belum diisi |
| diagram_batang_garis | batang.terbesar | Varian jumlah; skala jelas, bukan hanya tertinggi | Belum diisi |

## Salin dan isi bagian ini untuk setiap entri

- Identitas lengkap (template, profil, kode, malrule): **belum diisi manusia**
- Versi dan SHA-256 isi yang diperiksa: **belum diisi manusia**
- Penulis/penyunting manusia: **belum ditetapkan**
- Reviewer matematika manusia: **belum ditetapkan**
- Tanggal review: **belum diisi manusia**
- Keputusan **setuju / ubah / tolak**: **belum diisi manusia**
- Jawaban pertanyaan 1–7 pada prosedur: **belum diisi manusia**
- Koreksi angka/satuan/bahasa/batas varian/sumber: **belum diisi manusia**
- Catatan uji coba mengajar (jika benar-benar dilakukan, pisahkan dari review): **belum ada**

Tampilan draf bukan persetujuan manusia. Pengesahan JSON merupakan tindakan manusia
setelah review exact; agent tidak boleh mengisi reviewer, tanggal atau status
`disahkan`. Jika belum ada reviewer, pertahankan `draf` dan metadata `null`.
