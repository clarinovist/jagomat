"""Pertanyaan pancingan untuk guru saat Jagomat tidak punya dugaan ("Belum yakin").

Dipakai halaman tinjauan guru hanya untuk jawaban salah yang tidak cocok pola
kesalahan mana pun (``diagnosis.diagnosa`` kasus 5) atau yang mesin minta
guru membaca kotak "mintanya apa". Isinya pertanyaan umum per topik, bukan
panduan mengajar tersahkan: tidak menyebut kunci, tidak mengubah diagnosis,
reducer, atau bukti, dan tidak pernah dirender di permukaan murid.
"""
from __future__ import annotations

from html import escape

import design_tokens as T
import topics

PERTANYAAN_UMUM = (
    "Minta anak menunjukkan caranya di kertas, pelan-pelan, sambil bersuara.",
    "Tanya: angka atau kata mana di soal yang kamu pakai dulu? Kenapa itu?",
    "Tanya: coba ulangi, soal ini sebenarnya minta apa?",
)

PERTANYAAN_TOPIK = {
    "pola-bilangan": (
        "Tanya: dari satu angka ke angka berikutnya, apa yang berubah? Tunjuk di lembar.",
        "Minta anak melanjutkan polanya dua langkah lagi sambil bersuara.",
        "Tanya: apakah perubahannya selalu sama? Cek dua pasang angka.",
    ),
    "aritmetika-dasar": (
        "Minta anak menghitung ulang sambil bersuara, mulai dari langkah pertama.",
        "Tanya: angka mana yang dijumlah atau dikurang dulu? Kenapa?",
        "Minta anak memeriksa dengan cara lain, misalnya dari belakang atau pakai benda.",
    ),
    "aritmatika-lanjut": (
        "Tanya: operasi mana yang kamu kerjakan dulu? Tunjukkan urutannya.",
        "Minta anak menulis tiap langkah di baris terpisah, lalu periksa satu per satu.",
        "Tanya: hasilnya masuk akal? Coba taksir kasar dulu.",
    ),
    "bilangan-dasar": (
        "Minta anak menghitung dengan benda atau jari sambil bersuara.",
        "Tanya: berapa lagi supaya pas sepuluh? Tunjukkan.",
        "Minta anak mengulang soalnya dengan kata-katanya sendiri.",
    ),
    "campuran": PERTANYAAN_UMUM,
    "geometri-datar": (
        "Minta anak menunjuk bagian bangun yang dimaksud soal: sisi, keliling, atau luas.",
        "Tanya: ukuran mana yang kamu pakai? Dari mana angkanya?",
        "Minta anak menggambar ulang bangunnya dengan ukuran yang tertulis.",
    ),
    "geometri-ruang": (
        "Minta anak menyebut bagian bangun ruang yang ditanya: sisi, rusuk, atau isi.",
        "Tanya: ukuran mana yang kamu pakai, dan untuk apa?",
        "Minta anak membayangkan bangunnya lewat benda nyata di sekitar.",
    ),
    "kombinatorik": (
        "Minta anak menuliskan beberapa kemungkinan satu per satu.",
        "Tanya: ada kemungkinan yang terhitung dua kali, atau yang terlewat?",
        "Tanya: bagaimana caramu memastikan semuanya sudah terhitung?",
    ),
    "logika": (
        "Minta anak menceritakan ulang petunjuk soal dengan kata sendiri.",
        "Tanya: petunjuk mana yang kamu pakai pertama? Kenapa?",
        "Minta anak mengecek jawabannya terhadap tiap petunjuk satu per satu.",
    ),
    "pengukuran": (
        "Tanya: satuannya apa, dan apakah soal minta satuan yang sama?",
        "Minta anak menunjukkan cara mengubah satuan, langkah demi langkah.",
        "Tanya: hasilnya masuk akal untuk benda sebesar itu?",
    ),
    "statistika": (
        "Minta anak membaca ulang datanya sambil menunjuk tabel atau diagram.",
        "Tanya: angka mana yang dipakai, dan berapa banyak datanya?",
        "Tanya: soal minta jumlah, rata-rata, atau yang paling sering? Tunjuk di soal.",
    ),
    "teori-bilangan": (
        "Minta anak menuliskan faktor atau kelipatan yang dipakai.",
        "Tanya: bagaimana kamu tahu bilangan ini habis dibagi?",
        "Minta anak mengecek jawabannya dengan membagi atau mengalikan balik.",
    ),
}

LABEL = "Belum ada dugaan. Tanyakan ini ke anak"
CATATAN_DRAF = "Draf: pertanyaan umum per topik, bukan panduan tersahkan. Dengarkan dulu, jangan memberi petunjuk."


def pertanyaan_untuk(template_id: str, topik_sesi: str) -> tuple[str, ...]:
    """Topik pemilik template lebih dipercaya daripada topik sesi (sesi campuran)."""
    topik = topics.pemilik_template(template_id or "") or (topik_sesi or "")
    return tuple(PERTANYAAN_TOPIK.get(topik, PERTANYAAN_UMUM))


def render(template_id: str, topik_sesi: str, *, peran: str) -> str:
    """Hanya guru; permukaan lain selalu kosong."""
    if peran != "guru":
        return ""
    butir = "".join("<li>" + escape(t) + "</li>" for t in pertanyaan_untuk(template_id, topik_sesi))
    return (
        '<div class="pancingan-st" data-pancingan-guru>'
        "<p class=\"pancingan-judul-st\"><b>" + escape(LABEL) + "</b></p>"
        "<ol>" + butir + "</ol>"
        "<p class=\"pancingan-catatan-st\">" + escape(CATATAN_DRAF) + "</p></div>"
    )


GAYA = f'''
.pancingan-st {{ margin-block: {T.SP_3}; padding: {T.SP_3} {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_KARTU}; color: {T.TEKS_UTAMA};
  min-width: 0; overflow-wrap: anywhere; line-height: 1.6; }}
.pancingan-st ol {{ margin: {T.SP_2} 0; padding-left: 1.4rem; }}
.pancingan-judul-st {{ margin: 0; }}
.pancingan-catatan-st {{ margin: 0; color: {T.TEKS_SUBTLE}; }}
'''
