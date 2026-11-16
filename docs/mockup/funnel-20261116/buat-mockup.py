"""Generator mockup statis funnel Cek Kemampuan.

Bukan halaman produksi: tidak ada rute, tidak menyentuh DB, tidak mengirim
data apa pun. Tujuannya hanya memperlihatkan bentuk layar memakai kerangka
dan kelas CSS yang sudah ada (`landing._halaman_publik_stitch`,
`style_stitch.gaya_stitch()`) supaya yang dilihat sama dengan tampilan asli.

Jalankan: mesin/.venv/bin/python docs/mockup/funnel-20261116/buat-mockup.py
Keluaran: A-cek-kemampuan.html, B-paket-coba.html, C-hasil.html,
D-pesanan.html, index.html (galeri 390px + 1180px).
"""
from __future__ import annotations

import pathlib
import sys

AKAR = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(AKAR / "mesin"))

import design_tokens as T  # noqa: E402
import landing  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent

# CSS tambahan khusus mockup. Nilainya diambil dari design_tokens supaya tidak
# mengarang warna baru; di produksi ini harus lewat style_stitch/GAYA, bukan file ini.
EKSTRA = f"""
.mockup-harga-st{{display:flex;align-items:baseline;gap:.5rem;flex-wrap:wrap;margin:.25rem 0 .5rem}}
.mockup-harga-angka-st{{font-size:2.6rem;font-weight:800;letter-spacing:-.02em;color:{T.TEKS_JUDUL}}}
.mockup-harga-satuan-st{{font-size:1rem;color:{T.TEKS_SUBTLE}}}
.mockup-pil-st{{display:inline-block;padding:.3rem .7rem;border-radius:999px;font-size:.8rem;font-weight:600;
  background:{T.LATAR_CATATAN};border:1px solid {T.BORDER_CATATAN};color:{T.TEKS_JUDUL}}}
.mockup-pil-jujur-st{{background:{T.LATAR_KARTU_SEKUNDER};border-color:{T.BORDER_INTERAKTIF}}}
.mockup-qris-st{{width:11rem;height:11rem;border:1px solid {T.BORDER_HALUS};border-radius:.75rem;
  display:grid;place-items:center;color:{T.TEKS_SUBTLE};font-size:.85rem;background:
  repeating-conic-gradient({T.BORDER_HALUS} 0% 25%, #fff 0% 50%) 50%/1.1rem 1.1rem;margin:.75rem auto}}
.mockup-qris-st span{{background:#fff;padding:.35rem .5rem;border-radius:.4rem;border:1px solid {T.BORDER_HALUS}}}
.mockup-form-st label{{display:block;font-weight:600;margin:.9rem 0 .3rem;color:{T.TEKS_UTAMA}}}
.mockup-form-st input,.mockup-form-st select{{width:100%;min-height:{T.TINGGI_KONTROL};padding:.7rem .8rem;font-size:1rem;
  border:1px solid {T.BORDER_KONTROL};border-radius:{T.RADIUS_KECIL};background:#fff;color:{T.TEKS_UTAMA}}}
.mockup-form-st input:focus,.mockup-form-st select:focus{{outline:3px solid {T.AKSEN_AMBER_TUA};outline-offset:2px}}
.mockup-form-st button{{width:100%;justify-content:center}}
.mockup-wajib-st{{font-size:.9rem;color:{T.TEKS_SUBTLE};margin:.25rem 0 1rem}}
.mockup-catatan-st{{font-size:.9rem;color:{T.TEKS_SUBTLE};margin-top:.75rem}}
.mockup-dua-kolom-st{{display:grid;gap:1.5rem;grid-template-columns:minmax(0,1.05fr) minmax(0,.95fr);align-items:start}}
.mockup-dua-kolom-st>.landing-kartu-st{{height:100%}}
.mockup-kartu-batas-st{{background:{T.LATAR_CATATAN};border-color:{T.BORDER_CATATAN}}}
/* Galeri harus tetap utuh ketika screenshot full-page diambil. Scroll-driven animation
   produksi dinonaktifkan hanya di mockup agar kartu di luar viewport tidak transparan. */
.landing-kartu-st,.landing-demo-st,.landing-hero-teks-st>*{{animation:none!important;opacity:1!important;transform:none!important}}
.mockup-ringkasan-st{{margin:0 0 1.25rem;padding:.85rem 1rem;border-left:4px solid {T.AKSEN_TEAL_TUA};
  border-radius:0 {T.RADIUS_KECIL} {T.RADIUS_KECIL} 0;background:{T.LATAR_KARTU_SEKUNDER}}}
.mockup-ringkasan-st p{{margin:.2rem 0}}
.mockup-status-st{{display:flex;align-items:center;gap:.6rem;margin:1rem 0;padding:.75rem 1rem;
  border-radius:{T.RADIUS_KECIL};background:{T.LATAR_CATATAN};color:{T.TEKS_JUDUL};font-weight:700}}
.mockup-status-titik-st{{width:.65rem;height:.65rem;border-radius:50%;background:{T.AKSEN_AMBER_TUA};flex:0 0 auto}}
.mockup-tombol-sekunder-st{{display:inline-flex;align-items:center;justify-content:center;min-height:{T.TINGGI_KONTROL};
  padding:0 {T.SP_5};border:2px solid {T.TEKS_JUDUL};border-radius:{T.RADIUS_SEDANG};background:transparent;
  color:{T.TEKS_JUDUL};font:inherit;font-weight:700}}
.mockup-tombol-sekunder-st:disabled{{opacity:.55;cursor:not-allowed;background:{T.LATAR_NONAKTIF}}}
.mockup-catatan-utama-st{{margin:.75rem 0 0;padding:.8rem 1rem;border-radius:{T.RADIUS_KECIL};
  background:{T.LATAR_KARTU_SEKUNDER};color:{T.TEKS_JUDUL}}}
@media (max-width:820px){{.mockup-dua-kolom-st{{grid-template-columns:1fr}}}}
.mockup-galeri-st{{max-width:1180px;margin:0 auto;padding:2rem 1rem 4rem;font-family:system-ui,sans-serif}}
.mockup-galeri-st h1{{color:{T.TEKS_JUDUL}}}
.mockup-galeri-st figure{{margin:0 0 2.5rem}}
.mockup-galeri-st figcaption{{font-weight:700;margin:.75rem 0;color:{T.TEKS_JUDUL}}}
.mockup-bingkai-st{{display:flex;gap:1.5rem;flex-wrap:wrap;align-items:flex-start}}
.mockup-bingkai-st iframe{{border:1px solid {T.BORDER_HALUS};border-radius:.75rem;background:#fff}}
.mockup-daftar-st{{font:inherit;white-space:pre-line;line-height:1.7;margin:0;color:{T.TEKS_UTAMA}}}
.mockup-tautan-st{{display:inline-flex;align-items:center;min-height:44px;color:{T.TEKS_JUDUL};text-decoration:underline;
  text-underline-offset:3px;font-weight:600}}
.mockup-lebar-st{{grid-column:1/-1}}
.mockup-cta-st{{display:inline-flex;align-items:center;justify-content:center;gap:.5rem;min-height:{T.TINGGI_CTA};
  padding:.75rem {T.SP_5};border-radius:{T.RADIUS_SEDANG};background:{T.AKSEN_KORAL_TUA};color:{T.TEKS_PUTIH};
  font-weight:700;text-align:center;text-decoration:none}}
@media (min-width:821px){{
  .landing-hero-st{{grid-template-columns:minmax(0,.95fr) minmax(0,1.05fr);gap:2.25rem;padding-top:3.25rem}}
  .landing-judul-st{{font-size:clamp(3rem,4.35vw,3.65rem);line-height:1.08}}
  .landing-panggung-st{{padding-top:3rem}}
}}
@media (max-width:560px){{
  .mockup-cta-baris-st{{flex-direction:column;align-items:flex-start;gap:.6rem}}
  .mockup-cta-st,.mockup-tombol-sekunder-st{{width:100%}}
  .mockup-harga-angka-st{{font-size:2.25rem}}
}}
"""


def halaman(judul: str, isi: str, *, kelas: str = "landing-halaman-st") -> str:
    html = landing._halaman_publik_stitch(judul, isi, kelas_badan=kelas).decode("utf-8")
    return html.replace("</head>", f"<style>{EKSTRA}</style></head>", 1)


def topbar(aktif: str = "") -> str:
    n = T.NAMA_PRODUK
    return f"""
<a class="landing-lewati-st" href="#konten">Lewati ke konten</a>
<header class="landing-topbar-st"><div class="landing-topbar-isi-st">
<a class="brand" href="/">{n}</a>
<nav class="topbar-navigasi" aria-label="Navigasi utama">
<a class="landing-nav-st" href="#">Cek kemampuan</a>
<a class="landing-nav-st" href="#">Paket Coba</a>
<a class="tombol-putih" href="#">Masuk</a></nav>
</div></header>"""


FOOTER = """
<footer class="landing-footer-st"><div class="landing-footer-isi-st">
<p><b>Jagomat</b> · pendampingan matematika kelas 1–6 SD.</p>
<p class="landing-demo-keterangan-st">Halaman contoh (mockup). Semua nama dan angka hanya ilustrasi, bukan data anak sungguhan.</p>
</div></footer>"""


# ---------------------------------------------------------------- A. Cek kemampuan
A_ISI = f"""{topbar()}
<main class="landing-bungkus-st" id="konten" tabindex="-1">
<section class="landing-hero-st" aria-labelledby="judul-cek">
<div class="landing-hero-teks-st">
  <p class="landing-alis-st"><span aria-hidden="true">✳</span> <span>Cek kemampuan gratis · <span class="landing-jenjang-st">Kelas 1–6 SD</span></span></p>
  <h1 class="landing-judul-st" id="judul-cek">Kelihatan di langkah mana
  <span>anak mulai bingung.</span></h1>
  <p class="landing-tagline-st">Sekitar 25 menit. Satu halaman. Tanpa membuat akun.</p>
  <p class="landing-sub-st">Anak mengerjakan soal sesuai kelasnya. Setelah selesai, Anda langsung
  mendapat ringkasan: bagian yang sudah kuat, bagian yang perlu dipahami lagi, dan satu kegiatan
  yang bisa dicoba di rumah.</p>
  <p class="landing-cta-baris-st">
    <a class="tombol-coral" href="#">Mulai cek gratis <span aria-hidden="true">↗</span></a>
  </p>
  <p class="landing-penawaran-st"><b>Gratis · tanpa kartu pembayaran.</b><br>
  Cukup isi nama panggilan, kelas, dan persetujuan orang tua atau wali.</p>
  <p><a class="mockup-tautan-st" href="#">Lihat contoh hasil</a></p>
</div>

<div class="landing-panggung-st">
  <span class="landing-coret-st" aria-hidden="true">✳</span>
  <p class="landing-catatan-kertas-st">Bukan cuma nilai.<br><b>Ada langkahnya.</b></p>
<div class="landing-demo-st">
  <div class="landing-demo-kepala-st"><span>Ringkasan 1 halaman</span><span>Contoh</span></div>
  <p class="landing-demo-soal-st">Aisyah · kelas 4</p>
  <p class="mockup-daftar-st">Sudah kuat
· penjumlahan bersusun
· perkalian sampai 2 angka
· membaca soal cerita</p>
  <div class="landing-demo-hasil-st">
    <p class="landing-demo-label-st">Perlu dipahami lagi · contoh ilustrasi</p>
    <div class="landing-kode-grup-st">
      <span class="landing-kode-st aktif">Pecahan senilai</span>
      <span class="landing-kode-st">Langkah hitung</span>
    </div>
    <p class="landing-demo-catatan-st"><b>Satu langkah minggu ini:</b> minta anak menjelaskan
    kenapa 1/2 dan 2/4 dianggap sama, pakai satu kertas yang dilipat.</p>
  </div>
</div>
  <p class="landing-demo-keterangan-st">Contoh ilustrasi · bukan hasil anak sungguhan</p>
</div>
</section>

<section class="landing-kenali-st" aria-labelledby="judul-langkah">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">CARA KERJANYA</p>
  <h2 id="judul-langkah">Tiga langkah, selesai di rumah.</h2>
  <p>Dikerjakan dari rumah dan tidak perlu panggilan video.</p>
</div>
<div class="landing-grid-st landing-info-st">
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st"><span class="landing-nomor-st" aria-hidden="true">01</span>Isi data singkat</h3>
    <div class="landing-kartu-isi-st"><p>Isi nama panggilan anak dan kelasnya, lalu berikan
    persetujuan sebagai orang tua atau wali. Kurang dari satu menit.</p></div>
  </section>
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st"><span class="landing-nomor-st" aria-hidden="true">02</span>Anak mengerjakan 25 menit</h3>
    <div class="landing-kartu-isi-st"><p>Soal menyesuaikan kelas. Anak mengerjakan sendiri;
    Anda tidak perlu terus mendampingi.</p></div>
  </section>
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st"><span class="landing-nomor-st" aria-hidden="true">03</span>Baca ringkasannya</h3>
    <div class="landing-kartu-isi-st"><p>Satu halaman berisi hal yang sudah kuat,
    bagian yang perlu dipahami lagi, dan satu kegiatan untuk minggu ini.</p></div>
  </section>
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st">Yang Anda dapat secara gratis</h3>
    <div class="landing-kartu-isi-st">
      <p><b>Tiga hal yang sudah kuat.</b> Jadi Anda tahu bagian yang tidak perlu diulang.</p>
      <p><b>Satu bagian yang perlu dipahami lagi.</b> Bukan daftar panjang yang membingungkan.</p>
      <p><b>Catatan penting:</b> ringkasan dibuat otomatis dan <b>belum diperiksa guru</b>.
      Paket Coba mencakup pemeriksaan guru dan konsultasi 20 menit.</p>
    </div>
  </section>
</div>
</section>

<section class="landing-harga-st" id="paket-coba" aria-labelledby="judul-paket">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">KALAU MAU LEBIH LENGKAP</p>
  <h2 id="judul-paket">Paket Coba Rp49.000, sekali bayar.</h2>
  <p>Bukan langganan. Tidak ada perpanjangan atau tagihan otomatis.</p>
</div>
<div class="landing-grid-st">
  <section class="landing-kartu-st">
    <div class="landing-kartu-isi-st">
      <p class="mockup-harga-st"><span class="mockup-harga-angka-st">Rp49.000</span>
      <span class="mockup-harga-satuan-st">sekali bayar · bukan langganan</span></p>
      <p>Yang termasuk:</p>
      <ul>
        <li>laporan lengkap 5–6 halaman yang diperiksa guru dan ditulis untuk orang tua;</li>
        <li>konsultasi video 20 menit dengan guru tentang cara berpikir anak dan hal yang bisa dilatih;</li>
        <li>akses latihan 30 hari untuk satu anak;</li>
        <li>potongan Rp49.000 untuk kelas pertama jika nanti Anda ingin melanjutkan.</li>
      </ul>
      <p><a class="tombol-coral" href="#">Lihat rincian Paket Coba <span aria-hidden="true">↗</span></a></p>
      <p class="landing-harga-syarat-st">Mengambil kelas tidak wajib. Anda tetap dapat memakai laporan
      untuk berlatih di rumah. Jika memerlukan pendampingan, guru akan menjelaskan pilihan kelas yang tersedia.</p>
    </div>
  </section>

  <section class="landing-kartu-st mockup-kartu-batas-st">
    <h3 class="landing-kartu-judul-st">Batas hasil pemeriksaan</h3>
    <div class="landing-kartu-isi-st">
      <p>Hal yang perlu Anda ketahui sebelum membayar:</p>
      <ul>
        <li>hasil menunjukkan pola pada soal yang dikerjakan, bukan pemeriksaan menyeluruh;</li>
        <li>hasil tidak menjamin nilai anak akan naik;</li>
        <li>materi di luar soal yang dikerjakan belum diperiksa.</li>
      </ul>
      <p class="mockup-catatan-st">Anda tetap mendapat laporan yang diperiksa guru dan satu kegiatan
      yang bisa dicoba di rumah.</p>
    </div>
  </section>
</div>
</section>
{FOOTER}
</main>"""

# ---------------------------------------------------------------- B. Paket coba
B_ISI = f"""{topbar()}
<main class="landing-bungkus-st" id="konten" tabindex="-1">
<section class="landing-kenali-st" aria-labelledby="judul-paket">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">PAKET COBA</p>
  <h1 id="judul-paket">Laporan lengkap, diperiksa guru.</h1>
  <p>Sekali bayar Rp49.000. Bukan langganan dan tidak diperpanjang otomatis.</p>
</div>

<div class="mockup-dua-kolom-st">
  <section class="landing-kartu-st">
    <div class="landing-kartu-isi-st">
      <p class="mockup-harga-st"><span class="mockup-harga-angka-st">Rp49.000</span>
      <span class="mockup-harga-satuan-st">sekali bayar</span></p>
      <p><span class="mockup-pil-st">Bukan langganan</span>
         <span class="mockup-pil-st mockup-pil-jujur-st">Tidak diperpanjang otomatis</span></p>
      <p>Yang Anda dapat:</p>
      <ul>
        <li><b>Laporan 5–6 halaman</b> yang diperiksa guru dan ditulis untuk orang tua.</li>
        <li><b>Konsultasi video 20 menit</b> untuk membahas cara berpikir anak dan hal yang bisa dilatih.</li>
        <li><b>Latihan 30 hari</b> untuk satu anak, diarahkan dari hasil cek.</li>
        <li><b>Potongan Rp49.000</b> untuk kelas pertama jika nanti Anda ingin melanjutkan.</li>
      </ul>
      <p class="mockup-catatan-st">Pembayaran melalui QRIS. Data anak hanya dipakai untuk pemeriksaan ini.</p>
    </div>
  </section>

  <section class="landing-kartu-st">
    <div class="landing-kartu-isi-st">
      <h2 class="landing-kartu-judul-st">Isi data untuk melanjutkan pembayaran</h2>
      <p class="mockup-wajib-st">Semua kolom wajib diisi.</p>
      <form class="mockup-form-st" action="#" method="post">
        <label for="m-nama">Nama Anda</label>
        <input id="m-nama" name="nama" type="text" placeholder="Contoh: Rina" autocomplete="name" required>
        <label for="m-wa">Nomor WhatsApp aktif</label>
        <input id="m-wa" name="whatsapp" type="tel" placeholder="Contoh: 0812 3456 7890"
          autocomplete="tel" inputmode="tel" aria-describedby="bantuan-wa" required>
        <p class="mockup-catatan-st" id="bantuan-wa">Kami hanya memakai nomor ini untuk mengatur jadwal
        bersama guru dan membantu pesanan Anda.</p>
        <label for="m-anak">Nama panggilan atau inisial anak</label>
        <input id="m-anak" name="nama_anak" type="text" placeholder="Contoh: Aya" autocomplete="off" required>
        <label for="m-kelas">Kelas anak</label>
        <select id="m-kelas" name="kelas" required><option value="">Pilih kelas</option><option>Kelas 1</option>
        <option>Kelas 2</option><option>Kelas 3</option><option>Kelas 4</option><option>Kelas 5</option>
        <option>Kelas 6</option></select>
        <p style="margin-top:1.25rem"><button class="st-tombol-coral" type="submit">Lanjut ke pembayaran · Rp49.000</button></p>
        <p class="mockup-catatan-st">Setelah pembayaran berhasil, Anda membuat sandi untuk membuka laporan dan latihan 30 hari.</p>
      </form>
    </div>
  </section>
</div>
</section>

<section class="landing-kenali-st" aria-labelledby="judul-jelas">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">SEBELUM MEMBAYAR</p>
  <h2 id="judul-jelas">Tiga hal yang perlu Anda ketahui</h2>
</div>
<div class="landing-grid-st landing-info-st">
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st">Kapan konsultasinya?</h3>
    <div class="landing-kartu-isi-st"><p>Setelah pembayaran berhasil, kami menghubungi Anda lewat WhatsApp.
    Kami akan membantu mencari jadwal konsultasi 20 menit yang cocok.</p></div>
  </section>
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st">Bagaimana jika berubah pikiran?</h3>
    <div class="landing-kartu-isi-st"><p>Anda bisa meminta pengembalian dana penuh lewat WhatsApp
    hingga sebelum jadwal pemeriksaan dibuat. Setelah jadwal dibuat, Anda tetap dapat meminta
    penjadwalan ulang jika waktunya berubah.</p></div>
  </section>
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st">Bagaimana potongan kelasnya?</h3>
    <div class="landing-kartu-isi-st"><p>Jika nanti Anda mengikuti kelas, kami memberikan potongan
    Rp49.000 untuk pembayaran kelas pertama. Potongan tercatat atas nama Anda.</p></div>
  </section>
</div>
</section>
{FOOTER}
</main>"""

# ---------------------------------------------------------------- C. Hasil gratis
C_ISI = f"""{topbar()}
<main class="landing-bungkus-st" id="konten" tabindex="-1">
<section class="landing-kenali-st" aria-labelledby="judul-hasil">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">RINGKASAN HASIL · GRATIS</p>
  <h1 id="judul-hasil">Ringkasan hasil Aisyah</h1>
  <p>Kelas 4 · 15 soal selesai</p>
  <p><span class="mockup-pil-st mockup-pil-jujur-st">Ringkasan otomatis · belum diperiksa guru</span></p>
</div>

<div class="landing-grid-st landing-info-st">
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st"><span class="landing-nomor-st" aria-hidden="true">01</span>Sudah kuat</h3>
    <div class="landing-kartu-isi-st">
      <ul><li>penjumlahan dan pengurangan bersusun</li>
      <li>perkalian sampai dua angka</li>
      <li>membaca soal cerita sederhana</li></ul>
    </div>
  </section>
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st"><span class="landing-nomor-st" aria-hidden="true">02</span>Perlu dipahami lagi</h3>
    <div class="landing-kartu-isi-st">
      <ul><li><b>Pecahan senilai.</b> Anak menulis 1/2 = 2/3; kemungkinan melihat angka atas dan
      bawah terpisah, bukan sebagai satu nilai.</li>
      <li><b>Langkah hitung.</b> Ada satu soal di mana anak melewati langkah penyimpanan puluhan.</li></ul>
    </div>
  </section>
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st"><span class="landing-nomor-st" aria-hidden="true">03</span>Satu langkah minggu ini</h3>
    <div class="landing-kartu-isi-st">
      <p>Lipat satu kertas jadi dua, lalu jadi empat. Minta anak menunjukkan kenapa bagian yang
      dilipat dua kali tetap sama besar. Cukup 10 menit, dua kali minggu ini.</p>
    </div>
  </section>
</div>

<div class="landing-grid-st">
  <section class="landing-kartu-st">
    <div class="landing-kartu-isi-st">
      <p><b>Batas ringkasan ini:</b> hasil dibuat dari 15 soal yang dikerjakan Aisyah.
      Ringkasan ini bukan pemeriksaan menyeluruh dan tidak memperkirakan nilai. Materi di luar soal
      yang dikerjakan belum diperiksa.</p>
      <p><a class="mockup-cta-st" href="#">Dapatkan laporan lengkap · Rp49.000</a></p>
      <p class="mockup-lebar-st mockup-catatan-st">Termasuk pemeriksaan guru, konsultasi 20 menit,
      latihan 30 hari, dan potongan Rp49.000 untuk kelas pertama. Sekali bayar, bukan langganan.</p>
    </div>
  </section>
</div>
</section>
{FOOTER}
</main>"""

# ---------------------------------------------------------------- D. Status pesanan
D_ISI = f"""{topbar()}
<main class="landing-bungkus-st" id="konten" tabindex="-1">
<section class="landing-kenali-st" aria-labelledby="judul-pesanan">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">PESANAN · INV-8F2A</p>
  <h1 id="judul-pesanan">Selesaikan pembayaran</h1>
  <p>Paket Coba untuk Aisyah · Rp49.000 sekali bayar</p>
  <div class="mockup-status-st" role="status" aria-live="polite"><span class="mockup-status-titik-st" aria-hidden="true"></span>
  Menunggu pembayaran · tersisa 14:32</div>
</div>

<div class="mockup-dua-kolom-st">
  <section class="landing-kartu-st">
    <div class="landing-kartu-isi-st">
      <h2 class="landing-kartu-judul-st">Bayar melalui QRIS</h2>
      <p>Buka aplikasi bank atau dompet digital, pilih QRIS, lalu pindai kode ini.</p>
      <div class="mockup-qris-st" role="img" aria-label="Kode QRIS contoh"><span>QRIS contoh</span></div>
      <p class="mockup-catatan-utama-st"><b>Kode aktif selama 15 menit.</b><br>
      Setelah membayar, tunggu sebentar. Status akan diperbarui otomatis.</p>
      <p><button class="mockup-tombol-sekunder-st" type="button" disabled>Buat QR baru setelah kedaluwarsa</button></p>
    </div>
  </section>

  <section class="landing-kartu-st">
    <div class="landing-kartu-isi-st">
      <h2 class="landing-kartu-judul-st">Setelah pembayaran berhasil</h2>
      <ol>
        <li>Status berubah menjadi <b>Pembayaran berhasil</b>.</li>
        <li>Anda membuat sandi untuk membuka laporan dan latihan 30 hari.</li>
        <li>Kami menghubungi Anda lewat WhatsApp untuk mengatur konsultasi 20 menit.</li>
      </ol>
      <p class="mockup-catatan-st">Pembayaran belum berubah setelah beberapa menit?
      <a class="mockup-tautan-st" href="#">Hubungi kami</a></p>
      <p class="mockup-catatan-st">Pengembalian dana penuh tersedia sebelum jadwal pemeriksaan dibuat.</p>
    </div>
  </section>
</div>
</section>
{FOOTER}
</main>"""


INDEX = f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mockup funnel Cek Kemampuan</title><style>{EKSTRA}</style></head>
<body class="mockup-galeri-st">
<h1>Mockup funnel Cek Kemampuan</h1>
<p>Statis, tanpa server, tanpa data. Dirender dari kerangka dan token asli aplikasi.
Diperiksa pada 390px (HP) dan 1180px (desktop).</p>
<figure><figcaption>A · /cek-kemampuan</figcaption><div class="mockup-bingkai-st">
<iframe src="A-cek-kemampuan.html" width="390" height="844" title="Cek kemampuan HP"></iframe>
<iframe src="A-cek-kemampuan.html" width="1180" height="820" title="Cek kemampuan desktop"></iframe>
</div></figure>
<figure><figcaption>B · /paket-coba</figcaption><div class="mockup-bingkai-st">
<iframe src="B-paket-coba.html" width="390" height="844" title="Paket coba HP"></iframe>
<iframe src="B-paket-coba.html" width="1180" height="820" title="Paket coba desktop"></iframe>
</div></figure>
<figure><figcaption>C · /cek-kemampuan/hasil</figcaption><div class="mockup-bingkai-st">
<iframe src="C-hasil.html" width="390" height="844" title="Hasil HP"></iframe>
<iframe src="C-hasil.html" width="1180" height="820" title="Hasil desktop"></iframe>
</div></figure>
<figure><figcaption>D · /pesanan/&lt;id&gt;</figcaption><div class="mockup-bingkai-st">
<iframe src="D-pesanan.html" width="390" height="844" title="Pesanan HP"></iframe>
<iframe src="D-pesanan.html" width="1180" height="820" title="Pesanan desktop"></iframe>
</div></figure>
</body></html>"""


def main() -> int:
    berkas = {
        "A-cek-kemampuan.html": halaman("Cek kemampuan gratis", A_ISI),
        "B-paket-coba.html": halaman("Paket Coba Rp49.000", B_ISI, kelas="publik-badan-st"),
        "C-hasil.html": halaman("Ringkasan hasil", C_ISI, kelas="publik-badan-st"),
        "D-pesanan.html": halaman("Pesanan", D_ISI, kelas="publik-badan-st"),
        "index.html": INDEX,
    }
    for nama, isi in berkas.items():
        (OUT / nama).write_text(isi, encoding="utf-8")
        print(nama, len(isi), "byte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
