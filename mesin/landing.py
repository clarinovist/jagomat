"""Halaman landing publik — permukaan pertama pengunjung yang belum masuk.

Dibuka tanpa kredensial (200). Guru/murid yang sudah punya sesi diarahkan
ke /masuk. Konten marketing: apa yang dilakukan produk, untuk siapa, dan
rujukan kompetisi (OSN/SASMO). Data anak TIDAK pernah muncul di sini —
halaman ini statis, tidak membaca basis data sama sekali.

Brand dari design_tokens (sumber tunggal) — jangan hardcode nama di sini.

Sejak S8-S11 (1 Sep 2026): semua halaman publik diadopsi ke Stitch.
_halaman_publik lama dihapus (cleanup). Kontrak markup test dipertahankan.
"""
from __future__ import annotations

import html

import brand
import design_tokens as T
from teacher_style import SKRIP_MATA_SANDI, SKRIP_CEGAH_KIRIM_GANDA


def _font_link() -> str:
    """<link> Google Fonts CDN — dipakai semua halaman publik Stitch."""
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700'
        '&family=Plus+Jakarta+Sans:wght@400;600;700;800'
        '&family=Material+Symbols+Outlined&display=swap" rel="stylesheet">'
    )


def _halaman_publik_stitch(
    judul: str, isi: str, og: dict[str, str] | None = None,
    *, kelas_badan: str = "publik-badan-st",
) -> bytes:
    """Kerangka halaman publik versi Stitch — GAYA_STITCH, body.st.

    Dipakai oleh halaman_daftar, halaman_kebijakan, halaman_lupa_sandi
    (S8-S10). Kontrak markup yang diuji test (a.brand href=/, tombol-putih
    href=/masuk, href=/masuk tepat 1) dipertahankan di markup isi.

    og = metadata share (WhatsApp/Facebook) untuk halaman yang memang
    dibagikan; None berarti favicon + manifest saja.
    kelas_badan memisahkan kanvas landing dari padding halaman form.
    """
    from style_stitch import gaya_stitch

    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala(og)}
{_font_link()}
<style>{gaya_stitch()}</style></head>
<body class="st"><div class="{html.escape(kelas_badan, quote=True)}">{isi}</div>
<script>{SKRIP_MATA_SANDI}</script><script>{SKRIP_CEGAH_KIRIM_GANDA}</script></body></html>""".encode()


def _topbar_publik_st() -> str:
    """Topbar publik Stitch: brand owl + nama (link /), tombol Masuk."""
    n = html.escape(T.NAMA_PRODUK)
    return (
        '<div class="publik-topbar-st">'
        f'<a class="brand" href="/">'
        f'{brand.mark("topbar")}'
        f'<span>{n}</span></a>'
        '<nav class="topbar-navigasi">'
        f'<a class="tombol-putih" href="/masuk">Masuk</a></nav></div>'
    )


def halaman_daftar(
    pesan: str = "", galat: bool = False, nama: str = "", *,
    pendaftaran_dibuka: bool = True, token_form: str = "", belum_tersedia: bool = False,
    analitik: str = "",
) -> bytes:
    """Form pendaftaran mandiri pendamping (orang tua / guru / les).

    pesan = teks feedback; galat=True membuatnya dirender sebagai galat.
    nama = nama yang diketik pengguna (dikembalikan supaya tidak mengetik ulang).
    """
    kotak = ""
    if pesan:
        kelas = "masuk-galat-st" if galat else "pesan-st"
        peran = "alert" if galat else "status"
        judul_pesan = "Periksa kembali" if galat else "Catatan untukmu"
        kotak = (
            f'<div class="{kelas}" id="pesan-daftar" role="{peran}" aria-atomic="true">'
            f'<b>{judul_pesan}</b><p>{html.escape(pesan)}</p></div>'
        )
    deskripsi = ' aria-describedby="pesan-daftar"' if pesan else ""
    if not pendaftaran_dibuka:
        judul_status = 'Pendaftaran sementara belum tersedia' if belum_tersedia else 'Pendaftaran baru sedang ditutup'
        isi = f"""
<main class="daftar-editorial-st" aria-labelledby="judul-daftar">
{_topbar_publik_st()}<div class="daftar-panel-st">
<section class="publik-kartu-st daftar-kartu-st" aria-labelledby="judul-daftar">
<p class="daftar-alis-st">PENDAFTARAN</p><h1 id="judul-daftar">{judul_status}</h1>
<p class="publik-sub-st">Akun yang sudah terdaftar tetap bisa masuk.</p>{kotak}
<p><a class="masuk-tombol-st" href="/masuk">Masuk ke akun</a></p>
</section></div></main>"""
        return _halaman_publik_stitch(f"Daftar — {T.NAMA_PRODUK}", isi)

    token = (
        f'<input type="hidden" name="token_form" value="{html.escape(token_form, quote=True)}">'
        if token_form else ""
    )
    isi = f"""
<main class="daftar-editorial-st" aria-labelledby="judul-daftar">
{_topbar_publik_st()}
<div class="daftar-panel-st">
<aside class="daftar-catatan-st" aria-labelledby="judul-pendamping">
<p class="daftar-alis-st">MULAI DARI MENEMANI</p>
<h2 id="judul-pendamping">Belajar anak,<br><span>didampingi kamu.</span></h2>
<p class="daftar-pengantar-st">Bukan hanya mengumpulkan jawaban benar.<br>Temani anak memahami caranya.</p>
<div class="daftar-buku-st" aria-hidden="true">
<img class="daftar-maskot-st" src="/aset/maskot-menyapa-v3-240.png" width="240" height="240" alt="">
<span>Satu langkah, bersama.</span>
</div>
<ol class="daftar-langkah-st">
<li><span>01</span><div><b>Buat akunmu</b><p>Akun untuk orang tua, guru, atau pendamping les.</p></div></li>
<li><span>02</span><div><b>Siapkan profil anak</b><p>Akun anak dibuat dari dalam aplikasi.</p></div></li>
<li><span>03</span><div><b>Mulai mendampingi</b><p>Siapkan latihan, lalu tinjau cara anak menjawab.</p></div></li>
</ol>
</aside>
<section class="publik-kartu-st daftar-kartu-st" aria-labelledby="judul-daftar">
<div class="daftar-sapaan-st">
<p class="daftar-alis-st">AKUN PENDAMPING</p>
<h1 class="publik-judul-st" id="judul-daftar">Buat akun orang tua</h1>
<p class="publik-sub-st">Untuk orang tua, guru, atau pendamping les.
Akun anak dibuat setelah ini, dari dalam aplikasi.</p>
</div>
{kotak}
<form class="masuk-form-st" method="post" action="/daftar"{deskripsi}>
  {token}
  <div class="masuk-field-st">
    <label for="nama">Nama pengguna</label>
    <input type="text" id="nama" name="nama" autocomplete="username" required
     aria-describedby="petunjuk-nama-daftar" value="{html.escape(nama)}">
    <p class="daftar-petunjuk-st" id="petunjuk-nama-daftar">Pilih nama pengguna yang mudah diingat. Tidak perlu email atau nomor telepon.</p>
  </div>
  <div class="masuk-field-st">
    <label for="sandi">Kata sandi</label>
    <input type="password" id="sandi" name="sandi" autocomplete="new-password" required minlength="8"
     aria-describedby="petunjuk-sandi-daftar">
    <p class="daftar-petunjuk-st" id="petunjuk-sandi-daftar">Minimal 8 karakter. Simpan nama pengguna dan sandimu di tempat aman.</p>
  </div>
  <div class="daftar-persetujuan-st">
   <label class="koreksi-centang-st" for="setuju">
    <input type="checkbox" id="setuju" name="setuju" value="1" required>
    <span>Saya orang tua/wali atau pendidik yang bertanggung jawab, dan saya
    menyetujui <a href="/kebijakan-privasi">Kebijakan Privasi</a>.</span>
   </label>
  </div>
  {analitik}
  <button class="masuk-tombol-st" type="submit">Buat akun <span aria-hidden="true">→</span></button>
</form>
<p class="daftar-bawah-st">Setelah mendaftar, kamu langsung masuk ke ruang pendamping.</p>
</section>
</div>
<p class="daftar-kaki-st">{html.escape(T.TAGLINE)}</p>
</main>
"""
    return _halaman_publik_stitch(f"Daftar — {T.NAMA_PRODUK}", isi)


def halaman_kebijakan() -> bytes:
    """Kebijakan privasi publik — tujuan tiga tautan persetujuan
    (footer landing, checkbox /daftar, checkbox anak-baru di web.py).

    Statis: tidak membaca basis data sama sekali, identik untuk semua
    pengunjung. Isinya mengikuti perilaku aplikasi yang SEBENARNYA —
    termasuk pengiriman foto lembar ke layanan AI — bukan janji yang
    belum diimplementasi.
    """
    isi = f"""
<main class="dukungan-editorial-st privasi-editorial-st" aria-labelledby="judul-privasi">
{_topbar_publik_st()}
<div class="publik-bungkus-st">
<section class="publik-kartu-st lebar">
<p class="dukungan-alis-st">CATATAN TENTANG DATAMU</p>
<div id="judul-privasi"><h1>Kebijakan Privasi</h1></div>
<p class="publik-sub-st">Ringkas dan jujur, tanpa bahasa hukum.
Terakhir diperbarui 6 September 2026.</p>

<div class="publik-isi-st">
<h2>Data yang dikumpulkan</h2>
<ul>
<li>Nama akun orang tua/guru dan kata sandinya (disimpan sebagai hash).</li>
<li>Nama panggilan anak dan kelas sekolahnya (kelas 3–6).</li>
<li>Hasil latihan: jawaban anak, kode diagnosis kesalahan
(K/B/H/E/T/N), dan catatan guru.</li>
<li>Foto lembar jawaban — hanya jika kamu mengunggahnya sebagai
lampiran.</li>
</ul>

<h2>Data anak</h2>
<p>Akun anak hanya bisa dibuat oleh orang tua/guru atau pengelola dari dalam
aplikasi — anak tidak pernah mendaftar sendiri. Anak hanya melihat sesi latihannya
sendiri di halaman murid; tidak ada obrolan atau kontak antar-anak.</p>

<h2>Layanan AI pihak ketiga</h2>
<p>Fitur <b>variasi cerita</b> mengirim kalimat soal (tanpa nama anak,
tanpa kunci jawaban) ke layanan AI untuk ditulis ulang menjadi soal
bercerita. Fitur <b>lampiran foto</b> mengirim foto lembar yang sudah
diisi anak ke layanan AI agar jawabannya bisa dibaca otomatis — foto itu
bisa memuat tulisan tangan anak. Pengiriman terjadi saat guru atau anak
sengaja mengunggah foto. Pastikan izin orang tua/wali sudah ada sebelum
memakai fitur ini; aplikasi belum memiliki gerbang persetujuan khusus pada
setiap upload. Hasil AI hanya berupa usulan dan harus diperiksa guru.</p>
<p>Fitur <b>Pendamping</b>, bila diaktifkan dan setelah persetujuan terpisah,
mengirim isi chat ke DeepSeek. Jangan menulis email, nomor telepon, sandi,
token, atau data pribadi anak. Bantuan kontekstual hanya memakai sumber belajar
minimum yang dipilih dan disetujui; jawaban/cara anak tidak dikirim otomatis. Riwayat chat
disimpan sampai 180 hari sejak aktivitas terakhir; operasi gagal disimpan paling
lama 7 hari. Penghapusan data aktif dilakukan segera, sedangkan salinan cadangan
dapat bertahan paling lama 30 hari. Admin tidak dapat membuka isi chat atau
memori keluarga.</p>
<p>Selain penyedia AI untuk fitur tersebut dan penyedia font tampilan,
tidak ada pihak ketiga untuk iklan, pelacakan, atau analitik.</p>

<h2>Siapa yang bisa melihat</h2>
<ul>
<li>Selain akses pengelola untuk dukungan operasional di bawah, data satu
keluarga tidak terlihat oleh akun keluarga lain.</li>
<li>Akun pengelola server dapat melihat dan mengelola data murid semua
keluarga untuk dukungan operasional, termasuk sesi, jawaban, koreksi,
lampiran, dan akun login murid. Pengelola tidak dapat mengubah akun atau
sandi sesama pengelola.</li>
<li>Tidak ada pihak ketiga lain yang dapat melihat data anak untuk iklan,
pelacakan, atau analitik.</li>
</ul>

<h2>Data yang tidak dikumpulkan</h2>
<ul>
<li>Tidak ada email, nomor telepon, atau alamat.</li>
<li>Tidak ada cookie pelacak atau analitik pihak ketiga.</li>
<li>Cukup tulis nama panggilan anak — jangan nama lengkap atau data
pribadi lainnya.</li>
</ul>

<h2>Analitik opsional</h2>
<p>Jika eksperimen evaluasi diaktifkan, orang tua dapat memilih persetujuan terpisah.
Jagomat mencatat keberadaan aktivitas latihan harian, sumber informasi berkategori,
dan survei singkat—bukan jawaban, nilai, diagnosis, foto, chat, atau kontak.
Menolak atau mencabut tidak mengurangi hak akses. Data terkait akun dihapus paling
lama 90 hari sejak pendaftaran; agregat kelompok tanpa mapping disimpan paling lama
12 bulan setelah rekrutmen. Cabut dan hapus analitik aktif melalui pengaturan akun.
Setelah restart atau pemulihan, pengiriman aktivitas memerlukan persetujuan ulang;
data lama tidak otomatis menjadi izin baru.</p>
<h2>Penyimpanan &amp; penghapusan data</h2>
<p>Semua data tersimpan dalam satu basis data di server pengelola —
bukan layanan cloud pihak ketiga. Dari aplikasi, kamu bisa menghapus
sesi latihan dan akun login anak kapan saja. Untuk penghapusan yang
lebih besar (seluruh data keluarga), hubungi pengelola server lewat WA
{html.escape(T.WA_SUPPORT)} — sebutkan nama akunmu.</p>
</div>
</section>
</div>
</main>
"""
    return _halaman_publik_stitch(f"Kebijakan Privasi — {T.NAMA_PRODUK}", isi)


def halaman_lupa_sandi() -> bytes:
    """Panduan publik "Lupa sandi?" — murni teks, tanpa form apa pun.

    Aplikasi ini SENGAJA tidak menyimpan email/telepon, jadi reset mandiri
    via email mustahil: tidak ada jalur kirim-ulang sandi otomatis dan tidak
    boleh diarang seolah ada. Sandi hanya bisa disetel ulang oleh manusia
    yang tepat — guru/orang tua untuk murid, pengelola untuk orang tua.
    Halaman ini menunjukkan jalurnya supaya yang terkunci tidak buntu di
    halaman masuk.
    """
    n = html.escape(T.NAMA_PRODUK)
    isi = f"""
<main class="dukungan-editorial-st lupa-editorial-st" aria-labelledby="judul-lupa">
<div class="dukungan-topbar-st">
<a class="brand" href="/">{brand.mark("topbar")}<span>{n}</span></a>
<span class="dukungan-topbar-catatan-st">Ruang bantuan</span>
</div>
<div class="publik-bungkus-st">
<section class="publik-kartu-st">
<p class="dukungan-alis-st">KITA CARI JALANNYA</p>
<h1 class="publik-judul-st" id="judul-lupa">Lupa sandi?</h1>
<p class="publik-sub-st">Tidak apa-apa — sandimu bisa disetel ulang, hanya saja tidak
lewat email.</p>
<div class="publik-isi-st">
<p>Aplikasi ini tidak menyimpan email, jadi sandi tidak bisa dikirim
otomatis. Yang menyetel ulang adalah manusia yang tepat:</p>
<ul>
<li><b>Kamu murid?</b> Mintalah gurumu atau orang tuamu menyetel sandi
baru — dari halaman Akun, kartu "Akun latihan", tombol
"Setel sandi baru".</li>
<li><b>Kamu orang tua yang daftar sendiri di /daftar?</b> Hubungi WA
{html.escape(T.WA_SUPPORT)} — sebutkan nama akunmu — untuk disetel
ulang oleh pengelola.</li>
<li><b>Akunmu dibuatkan les/guru?</b> Minta ke mereka yang menyetel
ulang — sandimu terikat ke keluarga mereka.</li>
</ul>
<p class="dukungan-kembali-st"><a href="/masuk">Kembali ke halaman masuk <span aria-hidden="true">→</span></a></p>
</div>
</section>
</div>
</main>
"""
    return _halaman_publik_stitch(f"Lupa sandi? — {T.NAMA_PRODUK}", isi)


def halaman_landing() -> bytes:
    """Landing editorial bertema buku latihan, tanpa membaca data anak.

    Kanvas lebar terpisah dari form publik. Contoh tetap statis, maskot
    hanya dekorasi, dan setiap aksi punya satu pintu. Narasi mengikuti
    siklus belajar; tidak mengaktifkan langganan atau layanan AI.
    """
    n = html.escape(T.NAMA_PRODUK)
    tag = html.escape(T.TAGLINE)
    mark_topbar = brand.mark("topbar")
    isi = f"""
<a class="landing-lewati-st" href="#konten">Lewati ke konten</a>
<header class="landing-topbar-st"><div class="landing-topbar-isi-st">
<a class="brand" href="/">{mark_topbar}<span>{n}</span></a>
<nav class="topbar-navigasi" aria-label="Navigasi utama">
<a class="landing-nav-st" href="#cara-kerja">Kenali {n}</a>
<a class="landing-nav-st" href="#contoh">Contoh latihan</a>
<a class="tombol-putih" href="/masuk">Masuk</a></nav>
</div></header>

<main class="landing-bungkus-st" id="konten" tabindex="-1">
<section class="landing-hero-st" aria-labelledby="judul-landing">
<div class="landing-hero-teks-st">
  <p class="landing-alis-st"><span aria-hidden="true">✳</span> Matematika SD · OSN &amp; SASMO</p>
  <h1 class="landing-judul-st" id="judul-landing">Bukan sekadar<br>benar.
  <span>Paham caranya.</span></h1>
  <p class="landing-tagline-st">{tag}</p>
  <p class="landing-sub-st">Bantu anak memahami matematika lewat latihan,
  <b>tinjauan cara berpikir</b>, dan rencana belajar terpandu. Bukan hanya
  tahu letak salahnya — orang tua dan guru tahu langkah berikutnya.</p>
  <p class="landing-cta-baris-st"><a class="tombol-coral" href="/daftar">
  Mulai — daftar sekarang <span aria-hidden="true">↗</span></a></p>
  <p class="landing-catatan-cta-st">Untuk orang tua, guru, dan les privat · Kelas 3–6 SD</p>
</div>

<div class="landing-panggung-st">
  <span class="landing-coret-st" aria-hidden="true">✳</span>
  <p class="landing-catatan-kertas-st">Di balik jawaban,<br><b>ada cara berpikir.</b></p>
<div class="landing-demo-st">
  <div class="landing-demo-kepala-st"><span>Soal 4/10</span><span>Contoh</span></div>
  <p class="landing-demo-soal-st">Berapa hasil dari 345 + 128?</p>
  <div class="landing-demo-cara-st">  345
+ 128
─────
  463</div>
  <div class="landing-demo-hasil-st">
    <p class="landing-demo-label-st">Dugaan awal · perlu ditinjau</p>
    <div class="landing-kode-grup-st">
      <span class="landing-kode-st aktif">H · Salah hitung</span>
      <span class="landing-kode-st">K · Salah konsep</span>
      <span class="landing-kode-st">B · Salah baca</span>
    </div>
    <p class="landing-demo-catatan-st"><b>Ajak anak menjelaskan langkahnya.</b>
    Hasil yang tepat 473, bukan 463. Periksa bersama: 5 + 8 = 13,
    tulis 3 dan simpan 1 ke puluhan. Pastikan penyebabnya dari cara anak
    mengerjakan, bukan diagnosis dari jawaban akhir saja.</p>
  </div>
</div>
  <img class="landing-maskot-st" src="/aset/maskot-menunjuk-v3-240.png"
       width="240" height="240" alt="" aria-hidden="true">
  <p class="landing-demo-keterangan-st">Ilustrasi latihan · bukan data anak</p>
</div>
</section>

<section class="landing-manfaat-st" aria-labelledby="judul-manfaat">
  <h2 id="judul-manfaat">Kenali kebutuhan. Dampingi latihan. Cek pemahaman.</h2>
  <div class="landing-pill-baris-st">
    <span class="landing-pill-st"><span aria-hidden="true">01 /</span> Rencana belajar</span>
    <span class="landing-pill-st"><span aria-hidden="true">02 /</span> Peta penguasaan</span>
    <span class="landing-pill-st"><span aria-hidden="true">03 /</span> Latihan fleksibel</span>
  </div>
</section>

<section class="landing-kenali-st" id="cara-kerja" aria-labelledby="judul-kenali">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">BELAJAR DENGAN ARAH</p>
  <h2 id="judul-kenali">Tidak berhenti di nilai.<br>Ada langkah berikutnya.</h2>
  <p>Untuk orang tua, guru, dan pendamping les yang ingin menemani anak memahami caranya.</p>
</div>
<div class="landing-grid-st landing-info-st">
<section class="landing-kartu-st landing-untuk-st">
  <h3 class="landing-kartu-judul-st">
  <span class="landing-nomor-st" aria-hidden="true">01</span>Rencana belajar terpandu</h3>
  <div class="landing-kartu-isi-st">
  <p>Mulai dari <b>pemetaan</b>, pilih fokus, lalu pelajari contoh dan
  latihan terbimbing sebelum penguatan mandiri.</p>
  <p>Lanjutkan dengan <b>cek berjeda dan cek berkala</b>. Hasil yang
  dikonfirmasi membantu menentukan: lanjut, coba pendekatan lain,
  atau periksa kebutuhan bantuan lebih lanjut.</p>
  </div>
</section>

<section class="landing-kartu-st landing-cara-st">
  <h3 class="landing-kartu-judul-st">
  <span class="landing-nomor-st" aria-hidden="true">↗</span>Cara kerja</h3>
  <div class="landing-kartu-isi-st">
  <ol>
    <li>Buat profil anak, lalu pilih variasi latihan.</li>
    <li>Anak mengerjakan dan menunjukkan caranya, di HP atau kertas.</li>
    <li>Tinjau dan konfirmasi hasilnya. Untuk rencana terpandu,
    ikuti langkah belajar berikutnya.</li>
  </ol>
  </div>
</section>

<section class="landing-kartu-st landing-topik-st">
  <h3 class="landing-kartu-judul-st">
  <span class="landing-nomor-st" aria-hidden="true">02</span>Peta penguasaan materi</h3>
  <div class="landing-kartu-isi-st">
  <p>Lihat materi yang menunjukkan pemahaman, masih dipelajari, belum
  dinilai, atau perlu dicek kembali. Jawaban benar saja belum cukup:
  anak juga perlu <b>bisa menjelaskan</b>.</p>
  <p>Peta mengikuti target materi {n} pada variasi latihan yang dipilih —
  bukan nilai rapor atau ukuran seluruh kurikulum.</p>
  </div>
</section>

<section class="landing-kartu-st landing-kompetisi-st">
  <h3 class="landing-kartu-judul-st">
  <span class="landing-nomor-st" aria-hidden="true">03</span>Latihan yang fleksibel</h3>
  <div class="landing-kartu-isi-st">
  <p><b>Latihan manual</b> tetap bisa dipilih tanpa menuntaskan pemetaan.
  Pilih materi dan variasi soal, kerjakan di halaman murid atau cetak
  lembar latihan.</p>
  <p>Dari bilangan dan aritmetika hingga geometri, statistika,
  pengukuran, dan kombinatorik — untuk membangun fondasi dan berlatih
  pola soal bergaya OSN/SASMO.</p>
  </div>
</section>
</div>
</section>

<section class="landing-contoh-st" id="contoh" aria-labelledby="judul-contoh">
<div class="landing-bagian-kepala-st">
<p class="landing-alis-st">LEBIH DARI BENAR ATAU SALAH</p>
<h2 class="landing-contoh-judul-st" id="judul-contoh">Salahnya berbeda. Bantuannya juga.</h2>
<p class="landing-contoh-sub-st">Contoh tertulis — bukan data anak mana pun.
Penyebab diperiksa bersama anak sebelum menentukan bantuan.</p>
</div>
<div class="landing-grid-st">
<section class="landing-kartu-st">
  <div class="landing-contoh-kode-st">
  <span class="landing-contoh-dot-st" style="background:{T.STATUS_SALAH}"></span>
  K · Salah konsep</div>
  <div class="landing-kartu-isi-st">
  <p>2/3 + 3/4 dijawab <b>5/7</b>. Jika penjelasan anak menunjukkan
  pembilang dan penyebut dijumlahkan sendiri-sendiri, periksa konsep
  pecahannya.</p>
  <div class="landing-resep-st"><b>Dampingi:</b> gunakan gambar bagian
  yang sama besar, lanjutkan dengan contoh terbimbing, lalu cek
  pemahaman lewat soal berbeda.</div>
  </div>
</section>

<section class="landing-kartu-st">
  <div class="landing-contoh-kode-st">
  <span class="landing-contoh-dot-st" style="background:{T.STATUS_LEMAH}"></span>
  B · Salah baca soal</div>
  <div class="landing-kartu-isi-st">
  <p>Anak menghitung hal lain dari yang ditanyakan. Ajak ia
  menceritakan ulang soal untuk memeriksa pemahamannya.</p>
  <div class="landing-resep-st"><b>Dampingi:</b> tandai informasi
  penting dan yang ditanya. Minta anak mengucapkannya kembali
  sebelum memilih perhitungan.</div>
  </div>
</section>

<section class="landing-kartu-st">
  <div class="landing-contoh-kode-st">
  <span class="landing-contoh-dot-st" style="background:{T.STATUS_KUAT}"></span>
  H · Salah hitung</div>
  <div class="landing-kartu-isi-st">
  <p>Jika anak bisa menjelaskan konsep dan langkahnya, tetapi
  perhitungannya meleset, bantu periksa langkah yang keliru.</p>
  <div class="landing-resep-st"><b>Dampingi:</b> tulis langkah satu
  per satu, periksa ulang hasilnya, lalu coba mandiri. Tidak semua
  kesalahan hitung memerlukan materi baru.</div>
  </div>
</section>
</div>
</section>

<section class="landing-pilot-st" aria-labelledby="judul-pendamping-landing">
<div>
<p class="landing-alis-st">PENDAMPING AI</p>
<h2 class="landing-contoh-judul-st" id="judul-pendamping-landing">Teman belajar.</h2>
</div>
<p class="landing-contoh-sub-st">Butuh bantuan memahami materi atau
menyiapkan latihan? Pendamping membantu lewat percakapan, bila fitur
aktif dan kamu menyetujui penggunaan AI. Bukan penentu diagnosis atau
pengganti tinjauanmu; kamu tetap memilih dan memeriksa bantuannya.</p>
</section>

<section class="landing-faq-st" aria-labelledby="judul-faq">
<div class="landing-bagian-kepala-st">
<p class="landing-alis-st">SEBELUM MULAI</p>
<h2 class="landing-contoh-judul-st" id="judul-faq">Sering ditanya</h2>
</div>
<div class="landing-faq-daftar-st">
<details><summary>Untuk kelas berapa?</summary>
<p>Kelas 3–6 SD. Variasi latihan dipilih terpisah dari kelas sekolah;
lihat contoh soalnya untuk memilih titik awal.</p></details>
<details><summary>Anak mengerjakan di HP atau kertas?</summary>
<p>Keduanya bisa. Gunakan halaman murid, atau cetak lembar untuk dikerjakan
di kertas. Hasil kertas dapat dicatat oleh orang tua/guru. Jika pembacaan
foto dengan AI tersedia, hasil baca tetap perlu diperiksa.</p></details>
<details><summary>Apakah ini khusus olimpiade?</summary>
<p>Tidak. {n} membantu membangun fondasi matematika dan berlatih pola soal
bergaya OSN/SASMO. Bukan pengganti seluruh pelajaran sekolah atau jaminan
prestasi olimpiade.</p></details>
<details><summary>Bagaimana dengan biaya?</summary>
<p>Paket dan pembayaran publik sedang disiapkan. Pendaftaran akun tidak
memicu pembayaran.</p></details>
<details><summary>Data anak disimpan di mana?</summary>
<p>Data belajar disimpan di server pengelola. Tidak ada iklan atau
pelacak pihak ketiga; pendaftaran tidak meminta email atau nomor telepon.
Fitur AI memakai layanan AI pihak ketiga: foto lembar dikirim untuk
pembacaan jawaban saat fitur digunakan, jadi pastikan izin orang tua/wali.
Pendamping memerlukan persetujuan terpisah. Rinciannya ada di
<a href="/kebijakan-privasi">Kebijakan Privasi</a>.</p></details>
<details><summary>Lupa sandi bagaimana?</summary>
<p>Tidak ada reset via email. Anak minta ke orang tua/gurunya; orang tua
yang daftar sendiri hubungi WA {html.escape(T.WA_SUPPORT)}
(sebutkan nama akunmu). Detailnya ada di halaman
<a href="/lupa-sandi">Lupa sandi</a>.</p></details>
</div>
</section>
</main>

<footer class="landing-footer-st"><div class="landing-footer-isi-st">
  <div><a href="/kebijakan-privasi">Kebijakan Privasi</a> ·
  <span>Butuh bantuan? WA {html.escape(T.WA_SUPPORT)}</span></div>
  <div>{n} — {tag}</div>
</div></footer>
"""
    return _halaman_publik_stitch(
        T.NAMA_PRODUK,
        isi,
        og={
            "judul": f"{T.NAMA_PRODUK} — {T.TAGLINE}",
            "deskripsi": (
                "Latihan matematika SD bergaya OSN/SASMO dengan rencana belajar "
                "terpandu dan peta penguasaan. Dampingi cara berpikir anak dan "
                "ikuti langkah belajar berikutnya."
            ),
            "jalur": "/",
        },
        kelas_badan="landing-halaman-st",
    )
