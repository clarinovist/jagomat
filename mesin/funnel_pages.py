"""Markup publik funnel Cek Kemampuan: `/cek-kemampuan`, `/paket-coba` (tampil: "Peta Kemampuan").

Renderer murni: tidak membaca data keluarga/anak, tidak ada form, tanpa JS
(`<details>` native). Satu aksi satu pintu: CTA utama "Cek anak saya, gratis"
ke `/daftar?jalur=cek`. Semua contoh hasil bersifat ilustrasi (nama sintetis).
Kerangka, topbar, dan footer mengikuti landing; sakelar `FUNNEL_AKTIF`
diputuskan pemanggil (`funnel_http`). Rute `/paket-coba` tidak berubah.
"""
from __future__ import annotations

import html

import brand
import design_tokens as T
import landing

JALUR_DAFTAR_CEK = "/daftar?jalur=cek"
MASKOT_MENYAPA = "/aset/maskot-menyapa-v3-240.png"

NAMA_PAKET = "Peta Kemampuan"

# Kalimat disetujui Pemilik, dipakai harfiah.
COPY_BUKAN_LANGGANAN = "Bukan langganan, jadi bulan depan tidak ada tagihan lagi."
COPY_HARGA = f"{NAMA_PAKET} Rp49.000, sekali bayar. {COPY_BUKAN_LANGGANAN}"

# DRAF: Keputusan 18 (tim/founder/keputusan-pemilik.md): tidak dapat dikembalikan, jadi voucher; menunggu persetujuan Pemilik.
COPY_TIDAK_KEMBALI = (
    "Peta Kemampuan tidak dapat dikembalikan, jadi Rp49.000 menjadi voucher "
    "program belajar bila Anda lanjut."
)
# DRAF: ketentuan laporan terlambat dan program kelas menunggu persetujuan Pemilik.
COPY_PEMBATALAN_BUTIR = (
    ("Peta Kemampuan tidak dapat dikembalikan,",
     " karena guru langsung mengerjakan laporannya. Sebagai gantinya, Rp49.000 "
     "menjadi voucher program belajar bila Anda lanjut."),
    ("Program belajar (kelas)", " punya ketentuan pengembalian tersendiri."),
    ("Laporan terlambat lebih dari 3×24 jam",
     " dari jam terbit yang kami kabari: Anda memilih tetap menunggu atau uang kembali penuh."),
    ("Tidak bisa hadir di jadwal konsultasi:",
     " kabari kami, kita cari waktu lain, tidak hangus."),
)
COPY_PEMBATALAN = " ".join(a + b for a, b in COPY_PEMBATALAN_BUTIR)
COPY_KONSULTASI = (
    "Setelah Anda bayar, kami hubungi lewat WhatsApp untuk mencari waktu "
    "ngobrol 20 menit dengan guru. Pagi, malam, atau akhir pekan, kita cari yang cocok."
)
COPY_DEPOSIT = (
    "Voucher dikirim lewat WhatsApp setelah pembayaran dan dicatat oleh tim. "
    "Nilainya Rp49.000 untuk program belajar di Jagomat bila Anda lanjut."
)
# Peluncuran awal; HAPUS konstanta ini (dan pemakaiannya) saat kuota 20 keluarga habis.
COPY_KUOTA_AWAL = "Peluncuran awal: 20 keluarga pertama"

COPY_LABEL_CONTOH = "Contoh ilustrasi, bukan hasil anak sungguhan"
COPY_PAKET_DARI_HASIL = (
    f"{NAMA_PAKET} dibuka dari halaman hasil, setelah cek gratis selesai."
)

# DRAF: teks final menunggu persetujuan Pemilik (copy landing dan halaman Peta Kemampuan).
COPY_PERTANYAAN = "Latihan sudah ditambah, tapi salahnya itu-itu lagi?"
COPY_SUB_HERO = (
    "Anak mengerjakan sendiri, 25 menit di HP. Anda melihat bagian mana yang sudah "
    "kuat dan mana yang perlu dibantu, supaya latihan di rumah tepat sasaran dan "
    "nilai matematikanya bisa naik. Gratis."
)
COPY_CTA = "Cek anak saya, gratis"
COPY_CATATAN_HERO = "Tanpa kartu pembayaran. Daftar dengan nomor WhatsApp Anda."
COPY_FAKTA = "Kelas 1–6 SD · Soal sesuai kelas · Laporan lengkap dibaca guru"
COPY_OTOMATIS = ("Hasil otomatis dari sistem. ", "Guru membacanya", " di laporan lengkap.")
COPY_RINGKASAN_AWAL_CONTOH = ("Hitung dasar kuat", "Soal cerita perlu diperkuat")
COPY_KUNCI_CONTOH = "Detail per materi: dibuka di Peta Kemampuan"
COPY_LANGKAH = (
    ("Daftar dengan WhatsApp",
     "Cukup nomor WhatsApp dan kelas anak, lalu setujui sebagai orang tua atau wali."),
    ("Anak mengerjakan", "25 menit di HP, sendiri. Anda tidak perlu duduk menemani."),
    ("Langsung tahu",
     "Skor, kategori, dan bagian yang perlu dibantu muncul begitu anak selesai."),
)
COPY_PAKET_SUB = (
    "Latihan yang tepat sasaran membantu nilai matematika anak naik. "
    "Mulai dari satu langkah yang jelas minggu ini."
)
COPY_PIL_VOUCHER = "Jadi voucher Rp49.000 bila lanjut belajar"
COPY_PAKET_RINGKAS = (
    "Laporan lengkap yang dibaca guru: bagian yang kuat, pola salah yang paling sering, dan urutan langkah belajar",
    "Ngobrol 20 menit dengan guru soal cara berpikir anak",
    "Latihan 30 hari, langsung bisa dipakai di rumah",
)
COPY_JUDUL_PAKET_HALAMAN = "Lihat pola salahnya. Tahu satu langkah berikutnya."
COPY_PENGANTAR_PAKET = (
    "Laporan lengkap yang dibaca guru, plus obrolan 20 menit untuk mengubahnya jadi "
    "langkah nyata di rumah, supaya anak makin jago berhitung. Di peluncuran awal, "
    "20 keluarga pertama dibaca langsung oleh guru kami."
)
COPY_PAKET_ISI = (
    "Laporan lengkap yang dibaca guru: penguasaan per materi, pola kesalahan, dan urutan belajar yang paling perlu dulu",
    "Ngobrol 20 menit dengan guru tentang cara berpikir anak dan apa yang bisa dilatih",
    "Latihan 30 hari untuk satu anak, siap dipakai di rumah",
    "Rp49.000 jadi voucher program belajar bila Anda lanjut",
)
COPY_TIDAK_WAJIB_KELAS = (
    "Tidak wajib ikut kelas. Laporan tetap bisa Anda pakai untuk berlatih sendiri di rumah."
)
COPY_BATAS_JUDUL = "Biar harapannya pas"
COPY_BATAS_HASIL = (
    "Hasil membaca pola dari soal yang dikerjakan, bukan ujian menyeluruh.",
    "Ini alat bantu memahami anak, bukan jaminan nilai naik.",
    "Materi di luar soal yang dikerjakan belum terbaca.",
)

_SVG = (
    '<svg width="{u}" height="{u}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>'
)


def _ikon(d: str, ukuran: int = 20, tebal: str = "2.4") -> str:
    return _SVG.format(u=ukuran, w=tebal, d=d)


_D_CENTANG = '<path d="M5 12.5l4.5 4.5L19 7.5"/>'
_D_PANAH = '<path d="M5 12h14M13 6l6 6-6 6"/>'
_D_INFO = '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5h.01"/>'
_D_SERU = '<path d="M12 7v6M12 17h.01"/>'
_D_GEMBOK = '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>'
_D_ORANG = '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-3.6 3.5-5.5 7-5.5s6.2 1.9 7 5.5"/>'
_D_HP = '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>'
_D_GRAFIK = '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'


def _e(teks: str) -> str:
    return html.escape(teks)


def _topbar(*, tautan_funnel: bool) -> str:
    n = _e(T.NAMA_PRODUK)
    nav = ""
    if tautan_funnel:
        nav = (
            '<a class="landing-nav-st" href="/cek-kemampuan">Cek kemampuan</a>\n'
            f'<a class="landing-nav-st" href="/paket-coba">{_e(NAMA_PAKET)}</a>\n'
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


def _cta_utama(teks: str) -> str:
    return (
        '<p class="landing-cta-baris-st">'
        f'<a class="tombol-coral" href="{JALUR_DAFTAR_CEK}">{_e(teks)} '
        f'<span aria-hidden="true">{_ikon(_D_PANAH, 18, "2.6")}</span></a></p>'
    )


def _centang(butir) -> str:
    return "".join(f"<li>{_ikon(_D_CENTANG, 20, '2.8')}<span>{_e(b)}</span></li>" for b in butir)


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


def _kartu_contoh() -> str:
    kuat, lemah = COPY_RINGKASAN_AWAL_CONTOH
    a, b, c = COPY_OTOMATIS
    return f"""
<div class="funnel-panggung-st" id="contoh-hasil">
<div class="funnel-lengkung-st" aria-hidden="true"></div>
<div class="funnel-contoh-st">
  <div class="funnel-kartu-contoh-st">
    <div class="funnel-kepala-st"><span>Hasil gratis</span><span class="funnel-lencana-st">Contoh hasil</span></div>
    <p class="funnel-anak-st">Aisyah · kelas 4</p>
    <div class="funnel-skor-baris-st">
      <div class="funnel-cincin-st" role="img" aria-label="Skor 72 dari 100"><span class="funnel-cincin-dalam-st"><b>72<small>dari 100</small></b></span></div>
      <div class="funnel-kategori-st">Cukup baik<small>Kategori kemampuan</small></div>
    </div>
    <div class="funnel-chip-baris-st">
      <div class="funnel-chip-st funnel-chip-kuat-st">{_ikon(_D_CENTANG, 20, "2.6")}{_e(kuat)}</div>
      <div class="funnel-chip-st funnel-chip-lemah-st">{_ikon(_D_SERU)}{_e(lemah)}</div>
      <div class="funnel-chip-st funnel-chip-kunci-st">{_ikon(_D_GEMBOK, 20, "2.2")}{_e(COPY_KUNCI_CONTOH)}</div>
    </div>
    <p class="funnel-otomatis-st">{_e(a)}<b>{_e(b)}</b>{_e(c)}</p>
  </div>
  <img class="funnel-maskot-st" src="{MASKOT_MENYAPA}" width="240" height="240" alt="">
  <p class="funnel-ket-contoh-st">{_e(COPY_LABEL_CONTOH)}</p>
</div>
</div>"""


def _langkah() -> str:
    ikon = (_D_ORANG, _D_HP, _D_GRAFIK)
    kartu = "".join(
        f'\n  <article><div class="funnel-ikon-st">{_ikon(d, 26, "2.2")}</div>'
        f"<h3>{_e(j)}</h3><p>{_e(t)}</p></article>"
        for d, (j, t) in zip(ikon, COPY_LANGKAH)
    )
    return f"""
<section class="funnel-bagian-st" aria-labelledby="judul-langkah">
  <p class="funnel-alis-st">Cara kerjanya</p>
  <h2 class="funnel-judul-bagian-st" id="judul-langkah">Tiga langkah, tanpa ribet.</h2>
  <div class="funnel-langkah-st">{kartu}
  </div>
</section>"""


def _akordeon_batas() -> str:
    return f"""
  <details class="funnel-akordeon-st">
    <summary>Biar harapannya pas: batas hasil</summary>
    <ul>{_daftar_li(COPY_BATAS_HASIL)}</ul>
  </details>"""


def _blok_paket() -> str:
    return f"""
<section class="funnel-bagian-st" aria-labelledby="judul-paket">
  <div class="funnel-paket-st">
    <div>
      <p class="funnel-alis-st">Langkah setelah cek gratis</p>
      <h2 id="judul-paket">{_e(NAMA_PAKET)}</h2>
      <p class="funnel-paket-sub-st">{_e(COPY_PAKET_SUB)}</p>
      <p class="funnel-harga-baris-st"><strong>Rp49.000</strong><span>sekali bayar</span></p>
      <p class="funnel-bukan-st">{_e(COPY_BUKAN_LANGGANAN)}</p>
      <span class="funnel-pil-terang-st funnel-pil-kuota-st">{_e(COPY_KUOTA_AWAL)}</span>
      <span class="funnel-pil-terang-st">{_e(COPY_PIL_VOUCHER)}</span>
    </div>
    <div>
      <ul class="funnel-centang-st">{_centang(COPY_PAKET_RINGKAS)}</ul>
      <a class="funnel-tautan-terang-st" href="/paket-coba">Lihat isi {_e(NAMA_PAKET)}</a>
    </div>
  </div>{_akordeon_batas()}
</section>"""


def halaman_cek_kemampuan(dukungan=None) -> bytes:
    """Halaman cek gratis: satu CTA, contoh hasil ilustrasi, ringkasan Peta Kemampuan."""
    isi = f"""{_topbar(tautan_funnel=True)}
<main class="landing-bungkus-st funnel-halaman-st" id="konten" tabindex="-1">
<section class="funnel-hero-st" aria-labelledby="judul-cek">
<div>
  <p class="funnel-tanya-st">{_e(COPY_PERTANYAAN)}</p>
  <h1 class="funnel-judul-hero-st" id="judul-cek">Kelihatan di langkah mana <em>anak mulai bingung.</em></h1>
  <p class="funnel-sub-st">{_e(COPY_SUB_HERO)}</p>
  {_cta_utama(COPY_CTA)}
  <p class="funnel-kecil-st">{_e(COPY_CATATAN_HERO)}</p>
  <p class="funnel-fakta-st">{_e(COPY_FAKTA)}</p>
</div>{_kartu_contoh()}
</section>
{_langkah()}
{_blok_paket()}
</main>
{_footer(dukungan)}"""
    return _bungkus("Cek kemampuan gratis", isi)


def _faq_pembatalan() -> str:
    butir = "".join(f"<li><b>{_e(a)}</b>{_e(b)}</li>" for a, b in COPY_PEMBATALAN_BUTIR)
    return f'<ul>{butir}</ul>'


def _kartu_harga() -> str:
    return f"""
    <div class="funnel-harga-kartu-st">
      <p class="funnel-harga-baris-st"><strong>Rp49.000</strong><span>sekali bayar</span></p>
      <span class="funnel-pil-hijau-st">Sekali bayar, bukan langganan</span>
      <span class="funnel-pil-hijau-st funnel-pil-kuning-st">Jadi voucher program belajar</span>
      <p class="funnel-catatan-kelas-st">{_e(COPY_HARGA)}</p>
      <ul class="funnel-centang-st">{_centang(COPY_PAKET_ISI)}</ul>
      <p class="funnel-tegas-st">{_e(COPY_TIDAK_KEMBALI)}</p>
      <p class="funnel-catatan-kelas-st">{_e(COPY_TIDAK_WAJIB_KELAS)}</p>
    </div>"""


def _kartu_batas() -> str:
    butir = "".join(f"<li>{_ikon(_D_INFO)}<span>{_e(b)}</span></li>" for b in COPY_BATAS_HASIL)
    return f"""
    <aside class="funnel-batas-kartu-st" aria-labelledby="judul-batas">
      <h2 id="judul-batas">{_e(COPY_BATAS_JUDUL)}</h2>
      <ul>{butir}</ul>
    </aside>"""


def _faq() -> str:
    return f"""
<section class="funnel-bagian-st" aria-labelledby="judul-jelas">
  <p class="funnel-alis-st">Pertanyaan yang sering muncul</p>
  <h2 class="funnel-judul-bagian-st" id="judul-jelas">Biar Anda tenang sebelum membayar.</h2>
  <div class="funnel-faq-st">
    <details><summary>Kapan ngobrol dengan gurunya?</summary>
      <div class="funnel-jawab-st">{_e(COPY_KONSULTASI)}</div></details>
    <details open><summary>Apakah uangnya bisa kembali?</summary>
      <div class="funnel-jawab-st">{_faq_pembatalan()}</div></details>
    <details><summary>Bagaimana cara memakai voucher Rp49.000?</summary>
      <div class="funnel-jawab-st">{_e(COPY_DEPOSIT)}</div></details>
  </div>
</section>"""


def halaman_paket_coba(dukungan=None) -> bytes:
    """Halaman harga Peta Kemampuan (rute tetap `/paket-coba`): tanpa form pesanan."""
    isi = f"""{_topbar(tautan_funnel=True)}
<main class="landing-bungkus-st funnel-halaman-st" id="konten" tabindex="-1">
<section class="funnel-bagian-st" aria-labelledby="judul-paket">
  <p class="funnel-alis-st">{_e(NAMA_PAKET)}</p>
  <h1 class="funnel-judul-halaman-st" id="judul-paket">{_e(COPY_JUDUL_PAKET_HALAMAN)}</h1>
  <p class="funnel-pengantar-st">{_e(COPY_PENGANTAR_PAKET)}</p>
  <div class="funnel-dua-st">{_kartu_harga()}{_kartu_batas()}
  </div>
  <div class="funnel-aksi-st">
    <p>{_e(COPY_PAKET_DARI_HASIL)}</p>
    {_cta_utama("Mulai dari cek gratis")}
  </div>
</section>
{_faq()}
</main>
{_footer(dukungan)}"""
    return _bungkus(NAMA_PAKET, isi)
