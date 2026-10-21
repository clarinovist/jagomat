"""Bantuan pra-tulis untuk permukaan orang tua, tanpa data anak atau layanan AI."""
from html import escape

import design_tokens as T

KARTU = (
    ('Anak bingung mulai dari mana',
     'Kita coba satu langkah kecil dulu.',
     'Bagian mana dari soal yang sudah kamu pahami?',
     'Ajak anak menunjuk satu informasi yang diketahui sebelum menghitung.'),
    ('Anak menolak dibantu',
     'Aku tidak akan mengambil alih.',
     'Kamu ingin aku mendengarkan dulu atau kita jeda sebentar?',
     'Ikuti pilihannya. Tunggu sampai ia bersedia sebelum melanjutkan satu langkah.'),
    ('Pendamping mulai kesal',
     'Kita jeda dulu; nanti kita coba satu bagian kecil bersama.',
     'Mau istirahat sebentar?',
     'Ambil jeda untuk menenangkan diri. Jangan memaksa melanjutkan ketika masih kesal.'),
)
FAQ = {
    'rencana': ('Mulai dari mana?',
                'Ikuti satu langkah yang tersedia di Beranda ini. Jika ada hasil menunggu tinjauan, '
                'buka sesi yang ditunjuk lalu dengarkan cara anak sebelum mengonfirmasi hasil. '
                'Latihan tambahan tidak menggantikan tugas di Beranda.'),
    'latihan': ('Bagaimana membuat latihan dari hasil terbaru?',
                'Pilih mode Dari hasil terbaru pada form di atas. Tinjau tipe soal yang disarankan, '
                'sesuaikan pilihan dan jumlahnya, lalu tekan Buat latihan. '
                'Jika belum ada bagian yang disarankan, pilih satu topik untuk latihan tambahan. '
                'Latihan ini tercatat di Riwayat, bukan bukti penguasaan atau pengganti tugas di Beranda.'),
    'perkembangan': ('Apa arti sedang dipelajari dan menunjukkan pemahaman?',
                     'Sedang dipelajari berarti target sedang dipelajari, bukan otomatis sudah dipahami. '
                     'Menunjukkan pemahaman berarti ada bukti yang memenuhi kriteria target yang tersedia, '
                     'bukan penguasaan seluruh matematika atau kelulusan permanen. '
                     'Belum dinilai bukan berarti tidak mampu. Lihat rincian bukti dan kriteria pada Perkembangan ini.'),
}


def kartu_pendampingan():
    """Pilihan situasi generik, bukan diagnosis atau intervensi individual."""
    isi = ''.join(
        '<details class="bantuan-statis-kartu"><summary>' + escape(judul) + '</summary>'
        '<div class="bantuan-statis-isi"><p><b>Mulai dengan:</b> “' + escape(pembuka) + '”</p>'
        '<p><b>Tanyakan:</b> “' + escape(tanya) + '”</p>'
        '<p><b>Langkah kecil:</b> ' + escape(langkah) + '</p></div></details>'
        for judul, pembuka, tanya, langkah in KARTU
    )
    return (
        '<section class="bantuan-statis-st" aria-labelledby="judul-bantuan-pendampingan">'
        '<h2 class="st" id="judul-bantuan-pendampingan">Saat mendampingi terasa sulit</h2>'
        '<p class="bantuan-statis-pengantar">Pilih situasi yang sesuai. Ini panduan umum tanpa AI, '
        'bukan penilaian kemampuan anak.</p><div class="bantuan-statis-daftar">'
        + isi + '</div></section>'
    )


def faq(konteks):
    """FAQ sesuai permukaan; tanpa CTA, pengiriman form, atau tautan dari model."""
    judul, isi = FAQ[konteks]
    return ('<details class="bantuan-statis-faq" data-faq-lokal="' + konteks + '">'
            '<summary>' + escape(judul) + '</summary><p>' + escape(isi) + '</p></details>')


GAYA = f'''
.bantuan-statis-st {{ margin-block: {T.SP_5}; color: {T.TEKS_UTAMA}; }}
.bantuan-statis-st h2 {{ margin: 0 0 {T.SP_2}; font-size: 1.1rem; }}
.bantuan-statis-pengantar {{ margin: 0 0 {T.SP_3}; line-height: 1.6; }}
.bantuan-statis-daftar {{ display: grid; gap: {T.SP_2}; }}
.bantuan-statis-kartu, .bantuan-statis-faq {{
  min-width: 0; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_KARTU};
  color: {T.TEKS_UTAMA}; overflow-wrap: anywhere;
}}
.bantuan-statis-faq {{ margin-block: {T.SP_4}; }}
.bantuan-statis-kartu > summary, .bantuan-statis-faq > summary {{
  cursor: pointer; box-sizing: border-box; min-height: {T.TARGET_SENTUH};
  padding: {T.SP_3} {T.SP_4}; font-size: 1rem; line-height: 1.5;
  color: {T.AKSEN_TEAL_TUA}; font-weight: 600;
}}
.bantuan-statis-kartu > summary:focus-visible, .bantuan-statis-faq > summary:focus-visible {{
  outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px;
}}
.bantuan-statis-isi {{ padding: 0 {T.SP_4} {T.SP_3}; }}
.bantuan-statis-isi p, .bantuan-statis-faq > p {{ line-height: 1.6; margin: {T.SP_2} 0; }}
.bantuan-statis-faq > p {{ padding: 0 {T.SP_4} {T.SP_3}; }}
'''
