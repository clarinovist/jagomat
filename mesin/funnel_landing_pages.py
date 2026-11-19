"""Markup landing `/cek-kemampuan` gaya playful (v4, 19 Nov 2026).

Dipanggil `funnel_pages.halaman_cek_kemampuan`. Renderer murni: tanpa data
keluarga/anak, tanpa form, tanpa atribut `style`; semua tampilan lewat kelas
`cek-...-st` (CSS di `funnel_landing_style`). Satu tombol utama (CTA koral di
hero); bagian lain memakai tautan ke `#mulai`.

Interaksi (chip gejala, tebak langkah, kartu hero) adalah enhancement: skrip
`funnel_landing_browser.SKRIP_LANDING_CEK`. Tanpa JS, semua jawaban gejala
tampil sebagai `<details>` dan penjelasan demo ada di `<details>` juga.
Semua contoh bersifat ilustrasi dan berlabel contoh (nama sintetis).
"""
from __future__ import annotations

import funnel_pages as P
from funnel_landing_browser import SKRIP_LANDING_CEK

MASKOT_MERAYAKAN = "/aset/maskot-merayakan-v3-240.png"
JALUR_MULAI = "#mulai"

COPY_GELEMBUNG = "Halo! Aku bantu cari salahnya di langkah mana."
COPY_FAKTA = ("Kelas 1–6 SD", "Soal sesuai kelas", "Laporan lengkap dibaca Guru")
COPY_ARIA_PANGGUNG = "Contoh hasil, data sintetis"

# Kartu contoh di hero: data sintetis, label contoh selalu tampil.
COPY_CONTOH_NAMA = "Aisyah · kelas 4"
COPY_CONTOH_RINGKAS = "Hitung dasar kuat. Soal cerita perlu diperkuat."
COPY_CONTOH_POSISI = ("Lebih tinggi dari ", "64%", " anak kelas 4 yang ikut Cek Jagomat")
COPY_CONTOH_MATERI = (
    ("tambah", "teal", "Tambah-kurang", 83, "kuat"),
    ("kali", "koral", "Perkalian", 55, "perlu diperkuat"),
    ("cerita", "mint", "Soal cerita", 35, "perlu dibantu"),
)

COPY_GEJALA_ALIS = "Kedengarannya akrab?"
COPY_GEJALA_JUDUL = "Pilih yang paling sering Anda alami."
COPY_GEJALA_SUB = "Salah yang berulang biasanya punya pola. Ketuk salah satu."
# (ikon, warna, label chip, kutipan, penjelasan, langkah malam ini)
COPY_GEJALA = (
    ("rumah", "teal", "Di rumah bisa, pas ujian salah lagi",
     "Di rumah sudah bisa, pas ujian kok salah lagi?",
     "Bisa jadi yang kurang bukan latihan, tapi bagian mana yang belum benar-benar nempel.",
     "minta anak mengerjakan soal serupa dengan angka berbeda, lalu lihat langkah mana yang berubah."),
    ("layar", "koral", "Sudah dileskan, tapi tetap kesulitan",
     "Sudah dileskan, tapi anak tetap kesulitan?",
     "Sebelum menambah les, lihat dulu salahnya di mana. Kadang yang tertinggal hanya satu langkah kecil.",
     "minta anak menjelaskan caranya dengan kata-katanya sendiri, bukan hanya jawabannya."),
    ("jam", "amber", "Pas les bisa, seminggu kemudian lupa",
     "Pas les bisa, seminggu kemudian lupa?",
     "Anak mungkin mengikuti caranya, tapi belum paham kenapa caranya begitu.",
     'tanya "kenapa langkahnya begini?" di satu soal saja. Dua menit cukup.'),
    ("pensil", "navy", "Sering dibilang ceroboh",
     "Sering salah dan dibilang ceroboh?",
     '"Ceroboh" belum tentu ceroboh. Salah yang berulang bisa jadi satu langkah konsep yang tertinggal.',
     "lingkari langkah pertama yang salah di tiga soal terakhir. Apakah langkahnya sama?"),
)
COPY_COBA_MALAM = "Coba malam ini:"

COPY_DEMO_ALIS = "Coba sebentar"
COPY_DEMO_JUDUL = "Tebak: di langkah mana salahnya?"
COPY_DEMO_SUB = "Begini cara Guru Jagomat membaca jawaban anak. Contoh sintetis."
COPY_DEMO_SOAL = "47 × 6 = …"
COPY_DEMO_JAWABAN = ("Jawaban anak ", "242", ". Seharusnya ", "282", ".")
# (teks langkah, apakah di sini salahnya)
COPY_DEMO_LANGKAH = (
    ("7 × 6 = 42, tulis 2, simpan 4", False),
    ("4 × 6 = 24, langsung ditulis 24", True),
    ("Hasil ditulis 242", False),
)
COPY_DEMO_AWAL = "Ketuk langkah yang menurut Anda salah."
COPY_DEMO_SALAH = "Langkah ini sudah benar. Coba yang lain."
COPY_DEMO_TEPAT = (
    "Tepat! Simpanan 4 belum ditambahkan: 24 + 4 = 28. Perkaliannya sudah benar, "
    "yang tertinggal hanya satu langkah kecil."
)
COPY_DEMO_LIHAT = "Lihat jawabannya"
COPY_DEMO_BAWAH = (
    "Di Peta Kemampuan, setiap materi yang perlu diperkuat dibahas seperti ini, "
    "lengkap dengan latihan 10 menit."
)
COPY_TAUTAN_MULAI = "Mulai cek gratis ↑"

COPY_CARA_ALIS = "Cara kerjanya"
COPY_CARA_JUDUL = "Tiga langkah, tanpa ribet."

COPY_PETA_ALIS = "Mulai gratis, lanjut kalau perlu"
COPY_PETA_JUDUL = "Dari skor ke satu langkah berikutnya."
COPY_GRATIS_NAMA = "Cek Kemampuan"
COPY_GRATIS_HARGA = ("Gratis", "dengan akun")
COPY_GRATIS_ISI = (
    "Skor dan kategori kemampuan",
    "Ringkasan awal: bagian yang kuat dan yang perlu dibantu",
    "Hasil otomatis, keluar begitu anak selesai",
)
COPY_GRATIS_CATATAN = 'Hasil gratis berlabel "belum ditinjau Guru".'
COPY_TIKET_ALIS = "Langkah setelah cek gratis"
COPY_TIKET_HARGA = ("Rp49.000", "sekali bayar")
# (ikon, warna, teks)
COPY_PETA_ISI = (
    ("peta", "teal",
     "Laporan lengkap dibaca Guru: per materi, pola salah dengan contoh langkah, dan misi belajar"),
    ("lembar", "amber", "Lembar ringkasan 1 halaman, siap dicetak atau dikirim"),
    ("posisi", "koral", "Posisi anak di antara teman sekelas yang sudah ikut Cek Jagomat"),
    ("obrol", "mint", "Ngobrol 20 menit dengan Guru soal cara berpikir anak"),
    ("kalender", "navy", "Latihan 30 hari, langsung bisa dipakai di rumah"),
)
COPY_TIKET_CATATAN = (
    "Bukan langganan. "
    f"{P.COPY_TIDAK_KEMBALI} Tidak wajib ikut kelas. {P.COPY_PAKET_DARI_HASIL}"
)
COPY_TAUTAN_ISI = "Lihat isi Peta Kemampuan"

COPY_FAQ_ALIS = "Tanya jawab"
COPY_FAQ_JUDUL = "Biar Anda tenang sebelum mulai."
COPY_FAQ_BAYAR = (
    "Cek Kemampuan gratis. Pembayaran hanya bila Anda membuka Peta Kemampuan "
    "(Rp49.000 sekali bayar) dari halaman hasil. Peta Kemampuan tidak dapat "
    "dikembalikan dan menjadi voucher program belajar bila Anda lanjut. Bila laporan "
    "terlambat lebih dari 3×24 jam dari jam yang dikabarkan, Anda memilih menunggu "
    "atau uang kembali penuh."
)
# (ikon, warna, pertanyaan, jawaban teks, atau None bila jawabannya daftar batas hasil)
COPY_FAQ = (
    ("hp", "teal", "Berapa lama, dan perlu ditemani?",
     "15 soal sesuai kelas, dikerjakan sendiri di HP. Anda tidak perlu duduk menemani. "
     "Jawaban tersimpan tiap soal, jadi kalau sinyal putus, cek bisa dilanjutkan."),
    ("kalender", "amber", "Untuk kelas berapa?",
     "Kelas 1–6 SD. Soal mengikuti kelas yang Anda pilih saat daftar."),
    ("kunci", "navy", "Bagaimana dengan data anak?",
     "Kami hanya menyimpan data yang Anda isi sendiri saat daftar, ditambah jawaban "
     "cek anak. Hasil anak hanya terlihat di akun Anda dan oleh Guru peninjau."),
    ("uang", "koral", "Kapan saya harus membayar?", COPY_FAQ_BAYAR),
    ("target", "mint", "Biar harapannya pas: batas hasil", None),
)

COPY_TUTUP_JUDUL = "Satu cek kecil, satu langkah yang jelas."
COPY_TUTUP_SUB = "Gratis, sekitar sekali duduk, dan Anda langsung tahu harus mulai dari mana."

_D = {
    "topi": '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c3 2.5 9 2.5 12 0v-5"/>',
    "kali": '<path d="M7 7l10 10M17 7 7 17"/>',
    "centang": '<path d="M20 6 9 17l-5-5"/>',
    "tambah": '<path d="M8 4.5v8M4 8.5h8"/><path d="M13 17.5h7"/>',
    "cerita": (
        '<path d="M3 5.5h5.5A3.5 3.5 0 0 1 12 9v11a2.5 2.5 0 0 0-2.5-2.5H3z"/>'
        '<path d="M21 5.5h-5.5A3.5 3.5 0 0 0 12 9v11a2.5 2.5 0 0 1 2.5-2.5H21z"/>'
    ),
    "rumah": '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
    "layar": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "jam": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/>',
    "pensil": '<path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19z"/><path d="M14.5 6.5l3 3"/>',
    "wa": (
        '<path d="M4 20l1.3-4A8 8 0 1 1 8 18.7z"/>'
        '<path d="M9 9.5c.5 2 2 3.5 4 4.5l1.2-1.2 2 1-.6 1.8c-3.5-.2-7-3.5-7.4-7.2l1.8-.6 1 2z"/>'
    ),
    "hp": '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18h2"/>',
    "grafik": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "peta": '<path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6z"/><path d="M9 4v14M15 6v14"/>',
    "lembar": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
    "posisi": '<path d="M4 20h4v-6H4zM10 20h4V8h-4zM16 20h4v-9h-4z"/>',
    "obrol": '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
    "kalender": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "kunci": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "uang": '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/>',
    "target": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
}
_UBIN_DOODLE = ("+", "×", "÷", "½", "7", "=", "3", "−")


def _ikon(nama: str, ukuran: int = 18, tebal: str = "2.4") -> str:
    return P._ikon(_D[nama], ukuran, tebal)


def _ubin(nama: str, warna: str, ukuran: int) -> str:
    return (
        f'<span class="cek-ubin-st cek-ubin-{warna}-st cek-ubin-{ukuran}-st">'
        f"{_ikon(nama, round(ukuran * .55))}</span>"
    )


def _kepala(alis: str, judul: str, id_judul: str, sub: str = "", tengah: bool = False) -> str:
    kelas = "cek-kepala-st cek-tengah-st" if tengah else "cek-kepala-st"
    sub_html = f'\n    <p class="cek-sub-b-st">{P._e(sub)}</p>' if sub else ""
    return (
        f'<div class="{kelas}">\n    <span class="cek-alis-st">{P._e(alis)}</span>\n'
        f'    <h2 class="cek-judul-b-st" id="{id_judul}">{P._e(judul)}</h2>{sub_html}\n  </div>'
    )


def _fakta() -> str:
    ikon = ("topi", "kali", "centang")
    chip = "".join(
        f"<span>{_ikon(i, 18)}{P._e(t)}</span>" for i, t in zip(ikon, COPY_FAKTA)
    )
    return f'<div class="cek-fakta-st">{chip}</div>'


def _kartu_materi() -> str:
    baris = "".join(
        f'<li>{_ubin(i, w, 30)}<span class="cek-materi-nama-st"><span>{P._e(n)}</span>'
        f'<b>{p}% · {P._e(s)}</b></span>'
        f'<span class="cek-bar-st cek-bar-{p}-st{"" if s == "kuat" else " cek-bar-lemah-st"}"><i></i></span></li>'
        for i, w, n, p, s in COPY_CONTOH_MATERI
    )
    return (
        '<div class="cek-kt-st cek-kt-materi-st" tabindex="0">'
        '<div class="cek-lbl-st">Per materi<span>Peta Kemampuan</span></div>'
        f'<ul class="cek-mini-materi-st">{baris}</ul></div>'
    )


def _kartu_lencana() -> str:
    return (
        '<div class="cek-kt-st cek-kt-lencana-st" tabindex="0">'
        f'<div class="cek-medali-st">{_ikon("tambah", 34)}</div>'
        "<b>Jago Tambah-Kurang</b><small>Lencana di laporan</small></div>"
    )


def _kartu_skor() -> str:
    a, b, c = COPY_CONTOH_POSISI
    return (
        '<div class="cek-kt-st cek-kt-skor-st" tabindex="0">'
        '<div class="cek-lbl-st">Hasil gratis<span>Contoh hasil</span></div>'
        f'<p class="cek-nama-contoh-st">{P._e(COPY_CONTOH_NAMA)}</p>'
        '<div class="cek-skor-baris-st">'
        '<div class="cek-cincin-st" role="img" aria-label="Skor 72 dari 100">'
        '<svg viewBox="0 0 120 120" aria-hidden="true">'
        '<circle class="cek-cincin-jalur-st" cx="60" cy="60" r="50" fill="none" stroke-width="14"/>'
        '<circle class="cek-cincin-isi-st" cx="60" cy="60" r="50" fill="none" stroke-width="14" '
        'stroke-linecap="round" stroke-dasharray="226.2 314.2"/></svg>'
        '<div class="cek-cincin-angka-st" aria-hidden="true"><b>72</b><small>dari 100</small></div></div>'
        f'<div><span class="cek-pita-st">Cukup baik</span>'
        f'<p class="cek-ringkas-st">{P._e(COPY_CONTOH_RINGKAS)}</p></div></div>'
        f'<p class="cek-posisi-st">{P._e(a)}<b>{P._e(b)}</b>{P._e(c)}</p></div>'
    )


def _panggung() -> str:
    return (
        f'<div class="cek-panggung-st" id="contoh-hasil" aria-label="{P._e(COPY_ARIA_PANGGUNG)}">\n'
        f"      {_kartu_lencana()}\n      {_kartu_materi()}\n      {_kartu_skor()}\n"
        f'      <p class="cek-gelembung-st" aria-hidden="true">{P._e(COPY_GELEMBUNG)}</p>\n'
        f'      <img class="cek-maskot-st" src="{P.MASKOT_MENYAPA}" alt="" width="150" height="150">\n'
        f'      <p class="cek-ket-contoh-st">{P._e(P.COPY_LABEL_CONTOH)}</p>\n    </div>'
    )


def _hero() -> str:
    doodle = "".join(f"<span>{d}</span>" for d in _UBIN_DOODLE)
    return f"""<section class="cek-hero-st" id="mulai" aria-labelledby="judul-cek">
  <div class="cek-doodle-st" aria-hidden="true">{doodle}</div>
  <div class="cek-w-st cek-hero-isi-st">
    <div class="cek-hero-kiri-st">
      <p class="cek-tanya-st">{P._e(P.COPY_PERTANYAAN)}</p>
      <h1 id="judul-cek">Kelihatan di langkah mana <em>anak mulai bingung.</em></h1>
      <p class="cek-sub-st">{P._e(P.COPY_SUB_HERO)}</p>
      {P._cta_utama(P.COPY_CTA)}
      <p class="cek-kecil-st">{P._e(P.COPY_CATATAN_HERO)}</p>
      {_fakta()}
    </div>
    {_panggung()}
  </div>
</section>"""


def _isi_gejala(kutip: str, isi: str, coba: str) -> str:
    return (
        f'<p class="cek-kutip-st">{P._e(kutip)}</p>'
        f'<p class="cek-isi-st">{P._e(isi)}</p>'
        f'<p class="cek-coba-st"><b>{P._e(COPY_COBA_MALAM)}</b> {P._e(coba)}</p>'
    )


def _chip_gejala() -> str:
    tombol = "".join(
        f'<button type="button" class="cek-chip-tombol-st" aria-pressed="{"true" if n == 0 else "false"}">'
        f'{_ubin(i, w, 44)}<span>{P._e(label)}</span><span class="cek-panah-st" aria-hidden="true">→</span></button>'
        for n, (i, w, label, _k, _s, _c) in enumerate(COPY_GEJALA)
    )
    return (
        '<div class="cek-chip-st" role="group" aria-label="Pilih gejala" hidden data-cek-chip>'
        f"{tombol}</div>"
    )


def _daftar_gejala() -> str:
    panel = "".join(
        f'\n      <details class="cek-jawab-st" data-cek-panel{" open" if n == 0 else ""}>'
        f"<summary>{_ubin(i, w, 44)}<span>{P._e(label)}</span></summary>"
        f'<div class="cek-jawab-isi-st">{_isi_gejala(k, s, c)}</div></details>'
        for n, (i, w, label, k, s, c) in enumerate(COPY_GEJALA)
    )
    return f'<div class="cek-daftar-st" data-cek-daftar>{panel}\n    </div>'


def _gejala() -> str:
    return f"""<section class="cek-blok-st" aria-labelledby="judul-gejala"><div class="cek-w-st">
  {_kepala(COPY_GEJALA_ALIS, COPY_GEJALA_JUDUL, "judul-gejala", COPY_GEJALA_SUB)}
  <div class="cek-gejala-st" data-cek-gejala>
    {_chip_gejala()}
    {_daftar_gejala()}
  </div>
</div></section>"""


# Susunan perkalian bersusun 4 kolom x 4 baris: (kelas tambahan, isi).
# `x` menandai digit hasil yang salah (dicoret skrip setelah tebakan tepat).
_SEL_SUSUN = (
    ("", ""), ("", ""), ("bawa", "4"), ("", ""),
    ("", ""), ("", ""), ("", "4"), ("", "7"),
    ("", "×"), ("", ""), ("", ""), ("", "6"),
    ("gr", ""), ("gr", "2"), ("gr", "4"), ("gr", "2"),
)
_SEL_SALAH = 14


def _sel_susun(n: int, kelas: str, isi: str) -> str:
    atribut = ""
    if kelas:
        atribut += f' class="cek-{kelas}-st"'
    if n == _SEL_SALAH:
        atribut += " data-cek-digit"
    return f"<span{atribut}>{isi}</span>"


def _soal_susun() -> str:
    isi = "".join(_sel_susun(n, k, t) for n, (k, t) in enumerate(_SEL_SUSUN))
    return f'<div class="cek-susun-st" role="img" aria-label="Jawaban anak 242">{isi}</div>'


def _kartu_soal() -> str:
    a, b, c, d, e = COPY_DEMO_JAWABAN
    return (
        '<div class="cek-soal-k-st"><span class="cek-label-st">Soal</span>'
        f'<p class="cek-soal-teks-st">{P._e(COPY_DEMO_SOAL)}</p>{_soal_susun()}'
        f'<p class="cek-jwb-st">{P._e(a)}<b>{P._e(b)}</b>{P._e(c)}<b>{P._e(d)}</b>{P._e(e)}</p></div>'
    )


def _langkah_demo() -> str:
    item = "".join(
        f'<li data-cek-langkah{" data-cek-tepat" if salah else ""}>'
        f'<span class="cek-langkah-isi-st"><span class="cek-no-st">{n}</span><span>{P._e(teks)}</span></span></li>'
        for n, (teks, salah) in enumerate(COPY_DEMO_LANGKAH, start=1)
    )
    return f'<ol class="cek-langkah-d-st">{item}</ol>'


def _demo() -> str:
    return f"""<section class="cek-blok-st cek-rapat-st" aria-labelledby="judul-demo"><div class="cek-w-st">
  {_kepala(COPY_DEMO_ALIS, COPY_DEMO_JUDUL, "judul-demo", COPY_DEMO_SUB, tengah=True)}
  <div class="cek-demo-w-st">
    <div class="cek-demo-st" data-cek-demo data-umpan-salah="{P._e(COPY_DEMO_SALAH)}" data-umpan-tepat="{P._e(COPY_DEMO_TEPAT)}">
      {_kartu_soal()}
      <div>
        {_langkah_demo()}
        <details class="cek-kunci-d-st" data-cek-kunci><summary>{P._e(COPY_DEMO_LIHAT)}</summary><p>{P._e(COPY_DEMO_TEPAT)}</p></details>
        <p class="cek-umpan-st" data-cek-umpan aria-live="polite" hidden>{P._e(COPY_DEMO_AWAL)}</p>
        <p class="cek-demo-bawah-st">{P._e(COPY_DEMO_BAWAH)} <a href="{JALUR_MULAI}">{P._e(COPY_TAUTAN_MULAI)}</a></p>
      </div>
    </div>
  </div>
</div></section>"""


def _cara() -> str:
    batu = ("wa", "hp", "grafik")
    langkah = "".join(
        f'\n    <li><span class="cek-batu-st">{_ikon(i, 36, "2.2")}<span class="cek-no-batu-st">{n}</span></span>'
        f"<h3>{P._e(j)}</h3><p>{P._e(t)}</p></li>"
        for n, (i, (j, t)) in enumerate(zip(batu, P.COPY_LANGKAH), start=1)
    )
    return f"""<section class="cek-blok-st cek-rapat-st" id="cara" aria-labelledby="judul-langkah"><div class="cek-w-st">
  {_kepala(COPY_CARA_ALIS, COPY_CARA_JUDUL, "judul-langkah", tengah=True)}
  <ol class="cek-jalur-st">{langkah}
  </ol>
</div></section>"""


def _centang_li(butir) -> str:
    return "".join(
        f"<li>{_ubin(i, w, 30)}<span>{P._e(t)}</span></li>" for i, w, t in butir
    )


def _kartu_gratis() -> str:
    butir = tuple(("centang", "teal", t) for t in COPY_GRATIS_ISI)
    harga, satuan = COPY_GRATIS_HARGA
    return f"""<div class="cek-kartu-g-st">
      <span class="cek-alis-st">{P._e(COPY_GRATIS_NAMA)}</span>
      <p class="cek-harga-st">{P._e(harga)}<small>{P._e(satuan)}</small></p>
      <ul class="cek-cek-st">{_centang_li(butir)}</ul>
      <p class="cek-kartu-catatan-st">{P._e(COPY_GRATIS_CATATAN)}</p>
    </div>"""


_CAP = (
    '<svg class="cek-cap-st" viewBox="0 0 100 100" aria-hidden="true"><defs>'
    '<path id="cek-cap-lingkar" d="M50 50 m-36 0 a36 36 0 1 1 72 0 a36 36 0 1 1 -72 0"/></defs>'
    '<circle class="cek-cap-garis-st" cx="50" cy="50" r="46" fill="none" stroke-width="3"/>'
    '<circle class="cek-cap-garis-st" cx="50" cy="50" r="28" fill="none" stroke-width="1.5"/>'
    '<text class="cek-cap-teks-st" font-size="8.8"><textPath href="#cek-cap-lingkar">KEPALA SEKOLAH ★ JAGOMAT ★</textPath></text>'
    '<text class="cek-cap-jago-st" font-size="15" x="50" y="55" text-anchor="middle">JAGO</text></svg>'
)


def _tiket() -> str:
    harga, satuan = COPY_TIKET_HARGA
    return f"""<div class="cek-tiket-st">
      {_CAP}
      <span class="cek-alis-st">{P._e(COPY_TIKET_ALIS)}</span>
      <h3>{P._e(P.NAMA_PAKET)}</h3>
      <p class="cek-tiket-sub-st">{P._e(P.COPY_PAKET_SUB)}</p>
      <p class="cek-harga-st">{P._e(harga)}<small>{P._e(satuan)}</small></p>
      <div class="cek-pil-baris-st"><span class="cek-pil-st cek-pil-amber-st">{P._e(P.COPY_KUOTA_AWAL)}</span><span class="cek-pil-st cek-pil-garis-st">{P._e(P.COPY_PIL_VOUCHER)}</span></div>
      <ul class="cek-cek-st">{_centang_li(COPY_PETA_ISI)}</ul>
      <p class="cek-tiket-catat-st">{P._e(COPY_TIKET_CATATAN)}</p>
      <p class="cek-tautan-st"><a href="/paket-coba">{P._e(COPY_TAUTAN_ISI)}</a>{P._tautan_contoh("cek-tautan-contoh-st")}</p>
    </div>"""


def _peta() -> str:
    return f"""<section class="cek-blok-st cek-rapat-st" id="peta" aria-labelledby="judul-peta"><div class="cek-w-st">
  {_kepala(COPY_PETA_ALIS, COPY_PETA_JUDUL, "judul-peta")}
  <div class="cek-dua-st">
    {_kartu_gratis()}
    {_tiket()}
  </div>{P.kartu_profil_guru()}
</div></section>"""


def _faq_isi(jawaban) -> str:
    if jawaban is None:
        return "<ul>" + P._daftar_li(P.COPY_BATAS_HASIL) + "</ul>"
    return P._e(jawaban)


def _faq() -> str:
    butir = "".join(
        f'\n    <details><summary>{_ubin(i, w, 36)}<span>{P._e(tanya)}</span>'
        f'<span class="cek-tanda-st">{_ikon("plus", 20)}</span></summary>'
        f'<div class="cek-isi-f-st">{_faq_isi(jawab)}</div></details>'
        for i, w, tanya, jawab in COPY_FAQ
    )
    return f"""<section class="cek-blok-st cek-rapat-st" id="tanya" aria-labelledby="judul-faq"><div class="cek-w-st">
  {_kepala(COPY_FAQ_ALIS, COPY_FAQ_JUDUL, "judul-faq", tengah=True)}
  <div class="cek-faq-st">{butir}
  </div>
</div></section>"""


def _penutup() -> str:
    return f"""<section class="cek-w-st cek-penutup-bungkus-st" aria-labelledby="judul-tutup">
  <div class="cek-penutup-st">
    <img src="{MASKOT_MERAYAKAN}" alt="" width="140" height="140">
    <div>
      <h2 id="judul-tutup">{P._e(COPY_TUTUP_JUDUL)}</h2>
      <p class="cek-sub-b-st">{P._e(COPY_TUTUP_SUB)}</p>
      <a class="cek-naik-st" href="{JALUR_MULAI}">{P._e(COPY_TAUTAN_MULAI)}</a>
    </div>
  </div>
</section>"""


def isi_cek_kemampuan(dukungan=None) -> str:
    """Isi halaman (topbar, `<main>`, footer, skrip) yang dibungkus `funnel_pages._bungkus`."""
    return f"""{P._topbar(tautan_funnel=True)}
<main class="funnel-halaman-st cek-halaman-st" id="konten" tabindex="-1">
{_hero()}
{_gejala()}
{_demo()}
{_cara()}
{_peta()}
{_faq()}
{_penutup()}
</main>
{P._footer(dukungan)}
<script>{SKRIP_LANDING_CEK}</script>"""
