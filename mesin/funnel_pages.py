"""Markup publik funnel Cek Kemampuan (Fase 1): `/cek-kemampuan`, `/paket-coba`.

Renderer murni: tidak membaca data keluarga/anak, tidak ada form. Satu aksi
satu pintu: CTA utama "Mulai cek gratis" ke `/daftar?jalur=cek`. Semua contoh
hasil bersifat ilustrasi (nama sintetis). Kerangka, topbar, dan footer
mengikuti landing; sakelar `FUNNEL_AKTIF` diputuskan pemanggil (`funnel_http`).
"""
from __future__ import annotations

import html

import brand
import design_tokens as T
import landing

JALUR_DAFTAR_CEK = "/daftar?jalur=cek"

# Kalimat disetujui Pemilik (plan funnel §7), dipakai harfiah.
COPY_HARGA = (
    "Paket Coba Rp49.000, sekali bayar. "
    "Bukan langganan, jadi bulan depan tidak ada tagihan lagi."
)
COPY_PEMBATALAN = (
    "Kalau kamu berubah pikiran sebelum jadwal cek dibuat, bilang saja lewat "
    "WhatsApp. Uangmu kami kembalikan penuh, tanpa ditanya alasan. Setelah jadwal "
    "cek dibuat dan anak mulai mengerjakan, uang tidak bisa dikembalikan karena "
    "laporannya sudah mulai dikerjakan. Kalau ternyata kamu tidak bisa hadir di "
    "jadwal yang sudah dibuat, kabari kami; kita cari waktu lain, tidak hangus."
)
COPY_KONSULTASI = (
    "Setelah kamu bayar, kami hubungi kamu lewat WhatsApp untuk mencari waktu "
    "ngobrol 20 menit dengan guru. Pagi, malam, atau akhir pekan, kita cari yang cocok."
)
COPY_DEPOSIT = (
    "Biaya ini menjadi deposit: Anda mendapat voucher Rp49.000 untuk program "
    "belajar di Jagomat bila Anda melanjutkan. Voucher dikirim lewat WhatsApp "
    "setelah pembayaran dan dicatat oleh tim."
)

COPY_LABEL_CONTOH = "Contoh ilustrasi, bukan hasil anak sungguhan"
COPY_PAKET_DARI_HASIL = (
    "Paket Coba dibuka dari halaman hasil, setelah cek gratis selesai."
)

# DRAF: teks final menunggu persetujuan Pemilik (keputusan terbuka plan §10:
# skor/kategori, ringkasan awal, level per materi, peringkat).
COPY_SKOR_CONTOH = "Skor keseluruhan 72 dari 100 · kategori: Cukup baik"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_RINGKASAN_AWAL_CONTOH = ("Hitung dasar kuat", "Soal cerita perlu diperkuat")
# DRAF: teks final menunggu persetujuan Pemilik
COPY_GRATIS_ISI = (
    "<b>Skor keseluruhan dan kategori kemampuan.</b> Jadi Anda tahu gambaran umumnya.",
    "<b>Ringkasan awal.</b> Satu paragraf tentang bagian yang sudah kuat dan yang perlu diperkuat.",
    "<b>Catatan penting:</b> hasil dibuat otomatis dan <b>belum diperiksa guru</b>. "
    "Detail per materi, analisis kesalahan, dan urutan belajar ada di laporan lengkap.",
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_LAPORAN_LENGKAP = (
    "laporan lengkap yang diperiksa guru: penguasaan per materi, "
    "analisis kesalahan, dan urutan belajar prioritas 1, 2, 3"
)
COPY_PAKET_ISI = (
    COPY_LAPORAN_LENGKAP,
    "konsultasi 20 menit dengan guru tentang cara berpikir anak dan hal yang bisa dilatih",
    "akses latihan 30 hari untuk satu anak",
    "deposit Rp49.000 berupa voucher untuk program belajar jika nanti Anda ingin melanjutkan",
)
COPY_BATAS_HASIL = (
    "hasil menunjukkan pola pada soal yang dikerjakan, bukan pemeriksaan menyeluruh",
    "hasil tidak menjamin nilai anak akan naik",
    "materi di luar soal yang dikerjakan belum diperiksa",
)


def _e(teks: str) -> str:
    return html.escape(teks)


def _topbar(*, tautan_funnel: bool) -> str:
    n = _e(T.NAMA_PRODUK)
    nav = ""
    if tautan_funnel:
        nav = (
            '<a class="landing-nav-st" href="/cek-kemampuan">Cek kemampuan</a>\n'
            '<a class="landing-nav-st" href="/paket-coba">Paket Coba</a>\n'
        )
    return f"""
<a class="landing-lewati-st" href="#konten">Lewati ke konten</a>
<header class="landing-topbar-st"><div class="landing-topbar-isi-st">
<a class="brand" href="/">{brand.mark("topbar")}<span>{n}</span></a>
<nav class="topbar-navigasi" aria-label="Navigasi utama">
{nav}<a class="tombol-putih" href="/masuk">Masuk</a></nav>
</div></header>"""


def _footer(dukungan) -> str:
    n = _e(T.NAMA_PRODUK)
    tag = _e(T.TAGLINE)
    kontak = landing._kontak_dukungan(dukungan, konteks="umum")
    return f"""
<footer class="landing-footer-st"><div class="landing-footer-isi-st">
  <div><a href="/syarat-penggunaan">Syarat Penggunaan</a> · <a href="/kebijakan-privasi">Kebijakan Privasi</a>
  {kontak}</div>
  <div>{n} — {tag}</div>
</div></footer>"""


def _daftar_li(butir) -> str:
    return "".join(f"<li>{_e(b)}</li>" for b in butir)


def _cta_utama() -> str:
    return (
        '<p class="landing-cta-baris-st">'
        f'<a class="tombol-coral" href="{JALUR_DAFTAR_CEK}">Mulai cek gratis '
        '<span aria-hidden="true">↗</span></a></p>'
    )


def _kartu_batas() -> str:
    return f"""
  <section class="landing-kartu-st funnel-kartu-batas-st">
    <h3 class="landing-kartu-judul-st">Batas hasil pemeriksaan</h3>
    <div class="landing-kartu-isi-st">
      <p>Hal yang perlu Anda ketahui sebelum membayar:</p>
      <ul>{_daftar_li(COPY_BATAS_HASIL)}</ul>
    </div>
  </section>"""


def _bungkus(judul: str, isi: str) -> bytes:
    return landing._halaman_publik_stitch(
        judul, isi, kelas_badan="landing-halaman-st"
    )


def halaman_belum_dibuka(dukungan=None) -> bytes:
    """Status saat sakelar mati: tanpa form dan tanpa CTA ke jalur cek."""
    isi = f"""{_topbar(tautan_funnel=False)}
<main class="landing-bungkus-st" id="konten" tabindex="-1">
<section class="landing-kenali-st" aria-labelledby="judul-belum">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">CEK KEMAMPUAN</p>
  <h1 id="judul-belum">Halaman ini belum dibuka.</h1>
  <p>Cek kemampuan belum tersedia. Kami akan membukanya setelah siap.</p>
  <p><a class="landing-nav-st" href="/">Kembali ke beranda</a>
  <a class="landing-nav-st" href="/masuk">Masuk</a></p>
</div>
</section>
</main>
{_footer(dukungan)}"""
    return _bungkus("Belum dibuka", isi)


def halaman_cek_kemampuan(dukungan=None) -> bytes:
    """Halaman cek gratis: satu CTA, contoh hasil ilustrasi, ringkasan paket."""
    kode = "".join(
        f'<span class="landing-kode-st{" aktif" if i == 0 else ""}">{_e(t)}</span>'
        for i, t in enumerate(COPY_RINGKASAN_AWAL_CONTOH)
    )
    gratis = "".join(f"<p>{b}</p>" for b in COPY_GRATIS_ISI)
    isi = f"""{_topbar(tautan_funnel=True)}
<main class="landing-bungkus-st funnel-halaman-st" id="konten" tabindex="-1">
<section class="landing-hero-st" aria-labelledby="judul-cek">
<div class="landing-hero-teks-st">
  <p class="landing-alis-st"><span aria-hidden="true">✳</span> <span>Cek kemampuan gratis · <span class="landing-jenjang-st">Kelas 1–6 SD</span></span></p>
  <h1 class="landing-judul-st" id="judul-cek">Kelihatan di langkah mana
  <span>anak mulai bingung.</span></h1>
  <p class="landing-tagline-st">Sekitar 25 menit. Akun gratis, dibuat di awal.</p>
  <p class="landing-sub-st">Anak mengerjakan soal sesuai kelasnya. Setelah selesai, Anda langsung
  mendapat skor keseluruhan, kategori kemampuan, dan ringkasan awal. Detail per materi ada di
  laporan lengkap.</p>
  {_cta_utama()}
  <p class="landing-penawaran-st"><b>Gratis · tanpa kartu pembayaran.</b><br>
  Buat akun gratis dengan nomor WhatsApp Anda, lalu isi nama panggilan anak, kelas, dan persetujuan orang tua atau wali.</p>
  <p class="funnel-tautan-baris-st"><a class="funnel-tautan-st" href="#contoh-hasil">Lihat contoh hasil</a>
  <a class="funnel-tautan-st" href="/paket-coba">Tentang Paket Coba</a></p>
</div>

<div class="landing-panggung-st" id="contoh-hasil">
<div class="landing-demo-st">
  <div class="landing-demo-kepala-st"><span>Hasil gratis</span><span>Contoh</span></div>
  <p class="landing-demo-soal-st">Aisyah · kelas 4</p>
  <p class="funnel-catatan-st">{_e(COPY_SKOR_CONTOH)}</p>
  <div class="landing-demo-hasil-st">
    <p class="landing-demo-label-st">Ringkasan awal · contoh ilustrasi</p>
    <div class="landing-kode-grup-st">{kode}</div>
    <p class="landing-demo-catatan-st"><b>Detail per materi, analisis kesalahan, dan urutan belajar</b>
    ada di laporan lengkap.</p>
  </div>
</div>
  <p class="landing-demo-keterangan-st">{_e(COPY_LABEL_CONTOH)}</p>
</div>
</section>

<section class="landing-kenali-st" aria-labelledby="judul-langkah">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">CARA KERJANYA</p>
  <h2 id="judul-langkah">Tiga langkah, selesai di rumah.</h2>
  <p>Dikerjakan dari rumah dan tidak perlu panggilan video.</p>
</div>
<div class="landing-grid-st">
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st"><span class="landing-nomor-st" aria-hidden="true">01</span>Buat akun gratis</h3>
    <div class="landing-kartu-isi-st"><p>Buat akun dengan nomor WhatsApp Anda, isi nama panggilan anak dan kelasnya, lalu berikan
    persetujuan sebagai orang tua atau wali.</p></div>
  </section>
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st"><span class="landing-nomor-st" aria-hidden="true">02</span>Anak mengerjakan 25 menit</h3>
    <div class="landing-kartu-isi-st"><p>Soal menyesuaikan kelas. Anak mengerjakan sendiri;
    Anda tidak perlu terus mendampingi.</p></div>
  </section>
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st"><span class="landing-nomor-st" aria-hidden="true">03</span>Baca hasilnya</h3>
    <div class="landing-kartu-isi-st"><p>Anda langsung melihat skor keseluruhan, kategori kemampuan,
    dan ringkasan awal.</p></div>
  </section>
  <section class="landing-kartu-st">
    <h3 class="landing-kartu-judul-st">Yang Anda dapat secara gratis</h3>
    <div class="landing-kartu-isi-st">{gratis}</div>
  </section>
</div>
</section>

<section class="landing-harga-st landing-kenali-st" aria-labelledby="judul-paket">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">KALAU MAU LEBIH LENGKAP</p>
  <h2 id="judul-paket">Paket Coba</h2>
  <p>{_e(COPY_HARGA)}</p>
  <p class="funnel-tautan-baris-st"><a class="funnel-tautan-st" href="/paket-coba">Lihat isi Paket Coba</a></p>
</div>
<div class="landing-grid-st">{_kartu_batas()}
</div>
</section>
</main>
{_footer(dukungan)}"""
    return _bungkus("Cek kemampuan gratis", isi)


def halaman_paket_coba(dukungan=None) -> bytes:
    """Halaman harga Paket Coba (Fase 1): tanpa form pesanan."""
    faq = (
        ("Kapan konsultasinya?", COPY_KONSULTASI),
        ("Bagaimana jika berubah pikiran?", COPY_PEMBATALAN),
        ("Bagaimana deposit Rp49.000?", COPY_DEPOSIT),
    )
    kartu_faq = "".join(
        f'\n  <section class="landing-kartu-st"><h3 class="landing-kartu-judul-st">{_e(q)}</h3>'
        f'<div class="landing-kartu-isi-st"><p>{_e(a)}</p></div></section>'
        for q, a in faq
    )
    isi = f"""{_topbar(tautan_funnel=True)}
<main class="landing-bungkus-st funnel-halaman-st" id="konten" tabindex="-1">
<section class="landing-kenali-st" aria-labelledby="judul-paket">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">PAKET COBA</p>
  <h1 id="judul-paket">Laporan lengkap, diperiksa guru.</h1>
  <p>{_e(COPY_HARGA)}</p>
</div>

<div class="funnel-dua-kolom-st">
  <section class="landing-kartu-st">
    <div class="landing-kartu-isi-st">
      <p class="funnel-harga-st"><span class="funnel-harga-angka-st">Rp49.000</span>
      <span class="funnel-harga-satuan-st">sekali bayar</span></p>
      <p class="funnel-pil-baris-st"><span class="funnel-pil-st">Bukan langganan</span>
      <span class="funnel-pil-st funnel-pil-jujur-st">Tidak diperpanjang otomatis</span></p>
      <p>Yang Anda dapat:</p>
      <ul>{_daftar_li(COPY_PAKET_ISI)}</ul>
      <p class="funnel-catatan-st">Mengambil kelas tidak wajib. Anda tetap dapat memakai laporan
      untuk berlatih di rumah. Jika memerlukan pendampingan, guru akan menjelaskan pilihan kelas yang tersedia.</p>
    </div>
  </section>
{_kartu_batas()}
</div>

<div class="funnel-aksi-st">
  <p>{_e(COPY_PAKET_DARI_HASIL)}</p>
  {_cta_utama()}
</div>
</section>

<section class="landing-kenali-st" aria-labelledby="judul-jelas">
<div class="landing-bagian-kepala-st">
  <p class="landing-alis-st">SEBELUM MEMBAYAR</p>
  <h2 id="judul-jelas">Tiga hal yang perlu Anda ketahui</h2>
</div>
<div class="landing-grid-st">{kartu_faq}
</div>
</section>
</main>
{_footer(dukungan)}"""
    return _bungkus("Paket Coba", isi)
