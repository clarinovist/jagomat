"""Markup publik funnel Cek Kemampuan: `/cek-kemampuan`, `/paket-coba` (tampil: "Peta Kemampuan").

Renderer murni: tidak membaca data keluarga/anak, tidak ada form. Satu aksi satu
pintu: CTA utama "Cek anak saya, gratis" ke `/daftar?jalur=cek`. `/paket-coba`
tanpa JS (`<details>` native); landing `/cek-kemampuan` memakai enhancement JS
berhash CSP (`funnel_landing_browser`) dengan fallback native utuh. Semua contoh
hasil bersifat ilustrasi (nama sintetis).
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
    "Anak mengerjakan sendiri di HP. Anda melihat bagian mana yang sudah "
    "kuat dan mana yang perlu dibantu, supaya latihan di rumah tepat sasaran dan "
    "nilai matematikanya bisa naik. Gratis."
)
COPY_CTA = "Cek anak saya, gratis"
COPY_CATATAN_HERO = "Tanpa kartu pembayaran. Daftar dengan nomor WhatsApp Anda."
COPY_LANGKAH = (
    ("Daftar dengan WhatsApp",
     "Cukup nomor WhatsApp dan kelas anak, lalu setujui sebagai orang tua atau wali."),
    ("Anak mengerjakan", "15 soal di HP, sendiri. Anda tidak perlu duduk menemani."),
    ("Langsung tahu",
     "Skor, kategori, dan bagian yang perlu dibantu muncul begitu anak selesai."),
)
COPY_PAKET_SUB = (
    "Latihan yang tepat sasaran membantu nilai matematika anak naik. "
    "Mulai dari satu langkah yang jelas minggu ini."
)
COPY_PIL_VOUCHER = "Jadi voucher Rp49.000 bila lanjut belajar"
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

# Kerangka kartu profil guru. KOSONG secara bawaan: Pemilik mengisi data NYATA
# (nama, latar pendidikan, lama mengajar) setelah disetujui. Dilarang mengisi data
# karangan; selama kosong, kartu tidak dirender sama sekali (tanpa penanda/placeholder).
# Bentuk tiap butir: {"nama": ..., "latar": ..., "lama_mengajar": ...}.
PROFIL_GURU: tuple = ()
COPY_JUDUL_PROFIL_GURU = "Guru yang membaca laporan Anda"  # DRAF: teks final menunggu persetujuan Pemilik

COPY_TAUTAN_CONTOH = "Lihat contoh Peta Kemampuan"  # DRAF: teks final menunggu persetujuan Pemilik
JALUR_CONTOH = "/contoh-peta-kemampuan"

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


def kartu_profil_guru(profil=None) -> str:
    """Kartu profil guru; string kosong (nol byte) bila `PROFIL_GURU` kosong."""
    profil = PROFIL_GURU if profil is None else profil
    if not profil:
        return ""
    baris = "".join(
        f'<li><b>{_e(str(g.get("nama", "")))}</b>'
        f'<span>{_e(str(g.get("latar", "")))}</span>'
        f'<span>{_e(str(g.get("lama_mengajar", "")))}</span></li>'
        for g in profil
    )
    return (
        '\n  <aside class="funnel-guru-st" aria-labelledby="judul-guru">'
        f'<h2 id="judul-guru">{_e(COPY_JUDUL_PROFIL_GURU)}</h2><ul>{baris}</ul></aside>'
    )


def _tautan_contoh(kelas: str) -> str:
    return f'<a class="{kelas}" href="{JALUR_CONTOH}">{_e(COPY_TAUTAN_CONTOH)}</a>'


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














def halaman_cek_kemampuan(dukungan=None) -> bytes:
    """Halaman cek gratis gaya playful: satu CTA, contoh hasil ilustrasi, ringkasan Peta Kemampuan."""
    import funnel_landing_pages  # lazy: modul landing mengimpor funnel_pages

    return _bungkus("Cek kemampuan gratis", funnel_landing_pages.isi_cek_kemampuan(dukungan))


def _faq_pembatalan() -> str:
    butir = "".join(f"<li><b>{_e(a)}</b>{_e(b)}</li>" for a, b in COPY_PEMBATALAN_BUTIR)
    return f'<ul>{butir}</ul>'


def _kartu_harga() -> str:
    return f"""
    <div class="funnel-harga-kartu-st">
      <p class="funnel-harga-baris-st"><strong>Rp49.000</strong><span>sekali bayar</span></p>
      <span class="funnel-pil-hijau-st">Sekali bayar, bukan langganan</span>
      <span class="funnel-pil-hijau-st funnel-pil-kuning-st">Jadi voucher program belajar</span>
      <p class="funnel-contoh-tautan-st">{_tautan_contoh("funnel-tautan-sekunder-st")}</p>
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
  </div>{kartu_profil_guru()}
  <div class="funnel-aksi-st">
    <p>{_e(COPY_PAKET_DARI_HASIL)}</p>
    {_cta_utama("Mulai dari cek gratis")}
  </div>
</section>
{_faq()}
</main>
{_footer(dukungan)}"""
    return _bungkus(NAMA_PAKET, isi)
