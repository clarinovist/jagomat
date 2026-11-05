"""Pertanyaan pancingan untuk guru saat Jagomat tidak punya dugaan ("Belum yakin").

Dipakai halaman tinjauan guru hanya untuk jawaban salah yang tidak cocok pola
kesalahan mana pun (``diagnosis.diagnosa`` kasus 5) atau yang mesin minta
guru membaca kotak "mintanya apa". Isinya draf per jenis soal dari
``konten/pancingan/<topik>.json`` (3 pertanyaan + 1 tindak lanjut), dengan
cadangan pertanyaan umum per topik; bukan panduan mengajar tersahkan: tidak menyebut kunci, tidak mengubah diagnosis,
reducer, atau bukti, dan tidak pernah dirender di permukaan murid.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from html import escape
from pathlib import Path

import design_tokens as T
import topics

DIREKTORI = Path(__file__).resolve().parent / "konten" / "pancingan"
VERSI_FORMAT = 1
STATUS_DIIZINKAN = ("draf",)
JUMLAH_PERTANYAAN = 3
MAKS_PANJANG_PERTANYAAN = 120
MAKS_PANJANG_TINDAK_LANJUT = 200
KATA_TERLARANG = re.compile(
    r"\b(?:malrule|diagnosis|kode|template|kunci|pola kesalahan|ceroboh|malas|bodoh)\b", re.IGNORECASE
)

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

def _teks_valid(nilai, batas: int, nama: str) -> list[str]:
    if not isinstance(nilai, str) or not nilai.strip():
        return [nama + ": harus teks tidak kosong"]
    galat = []
    if len(nilai) > batas:
        galat.append(nama + ": melebihi " + str(batas) + " karakter")
    if KATA_TERLARANG.search(nilai):
        galat.append(nama + ": memuat istilah internal terlarang")
    return galat


def _entri_valid(tid: str, entri, topik: str) -> list[str]:
    if topics.pemilik_template(tid) != topik:
        return [tid + ": bukan template milik topik " + topik]
    if not isinstance(entri, dict):
        return [tid + ": entri harus objek"]
    daftar = entri.get("pertanyaan")
    if not isinstance(daftar, list) or len(daftar) != JUMLAH_PERTANYAAN:
        return [tid + ": harus tepat " + str(JUMLAH_PERTANYAAN) + " pertanyaan"]
    galat = []
    for i, q in enumerate(daftar):
        galat += _teks_valid(q, MAKS_PANJANG_PERTANYAAN, tid + " pertanyaan " + str(i + 1))
    galat += _teks_valid(entri.get("tindak_lanjut"), MAKS_PANJANG_TINDAK_LANJUT, tid + " tindak_lanjut")
    return galat


def validasi_berkas(data, nama_dasar: str) -> list[str]:
    """Daftar galat berkas pancingan; kosong berarti sah (gagal tertutup)."""
    if not isinstance(data, dict):
        return ["isi berkas harus objek"]
    galat = []
    if data.get("versi_format") != VERSI_FORMAT:
        galat.append("versi_format harus " + str(VERSI_FORMAT))
    if data.get("status") not in STATUS_DIIZINKAN:
        galat.append("status tidak diizinkan")
    topik = data.get("topik")
    if topik != nama_dasar or topik not in topics.daftar_topik():
        galat.append("topik harus sama dengan nama berkas dan dikenal")
    peta = data.get("template")
    if not isinstance(peta, dict) or not peta:
        return galat + ["template harus objek tidak kosong"]
    if galat:
        return galat
    for tid, entri in peta.items():
        galat += _entri_valid(tid, entri, topik)
    return galat


def galat_berkas() -> dict[str, list[str]]:
    """Nama berkas -> galat, hanya untuk berkas yang tidak sah (dipakai uji CI)."""
    hasil = {}
    for berkas in sorted(DIREKTORI.glob("*.json")):
        try:
            data = json.loads(berkas.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            hasil[berkas.name] = ["tidak terbaca: " + type(e).__name__]
            continue
        galat = validasi_berkas(data, berkas.stem)
        if galat:
            hasil[berkas.name] = galat
    return hasil


@lru_cache(maxsize=1)
def _muat() -> dict:
    """tid -> (pertanyaan, tindak_lanjut) dari berkas sah; berkas rusak dilewati."""
    entri = {}
    for berkas in sorted(DIREKTORI.glob("*.json")):
        try:
            data = json.loads(berkas.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if validasi_berkas(data, berkas.stem):
            continue
        for tid, e in data["template"].items():
            entri[tid] = (tuple(e["pertanyaan"]), e["tindak_lanjut"].strip())
    return entri


LABEL = "Belum ada dugaan. Tanyakan ini ke anak"
CATATAN_DRAF = "Draf: pertanyaan umum per topik, bukan panduan tersahkan. Dengarkan dulu, jangan memberi petunjuk."
CATATAN_DRAF_TEMPLATE = (
    "Draf: pertanyaan untuk soal jenis ini, belum ditinjau reviewer. "
    "Dengarkan dulu, jangan memberi petunjuk."
)
AWALAN_TINDAK_LANJUT = "Bila masih belum jelas: "


def pertanyaan_untuk(template_id: str, topik_sesi: str) -> tuple[str, ...]:
    """Entri template dulu, lalu topik pemilik template, topik sesi, umum."""
    entri = _muat().get(template_id or "")
    if entri:
        return entri[0]
    topik = topics.pemilik_template(template_id or "") or (topik_sesi or "")
    return tuple(PERTANYAAN_TOPIK.get(topik, PERTANYAAN_UMUM))


def tindak_lanjut_untuk(template_id: str) -> str | None:
    """Satu kalimat tindak lanjut khusus template, atau None bila tak ada."""
    entri = _muat().get(template_id or "")
    return entri[1] if entri else None


def render(template_id: str, topik_sesi: str, *, peran: str) -> str:
    """Hanya guru; permukaan lain selalu kosong."""
    if peran != "guru":
        return ""
    butir = "".join("<li>" + escape(t) + "</li>" for t in pertanyaan_untuk(template_id, topik_sesi))
    lanjut = tindak_lanjut_untuk(template_id)
    baris_lanjut = (
        '<p class="pancingan-lanjut-st">' + escape(AWALAN_TINDAK_LANJUT + lanjut) + "</p>"
        if lanjut else ""
    )
    catatan = CATATAN_DRAF_TEMPLATE if lanjut else CATATAN_DRAF
    return (
        '<div class="pancingan-st" data-pancingan-guru>'
        "<p class=\"pancingan-judul-st\"><b>" + escape(LABEL) + "</b></p>"
        "<ol>" + butir + "</ol>" + baris_lanjut +
        "<p class=\"pancingan-catatan-st\">" + escape(catatan) + "</p></div>"
    )


GAYA = f'''
.pancingan-st {{ margin-block: {T.SP_3}; padding: {T.SP_3} {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_KARTU}; color: {T.TEKS_UTAMA};
  min-width: 0; overflow-wrap: anywhere; line-height: 1.6; }}
.pancingan-st ol {{ margin: {T.SP_2} 0; padding-left: 1.4rem; }}
.pancingan-judul-st {{ margin: 0; }}
.pancingan-lanjut-st {{ margin: {T.SP_2} 0; }}
.pancingan-catatan-st {{ margin: 0; color: {T.TEKS_SUBTLE}; }}
'''
