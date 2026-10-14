"""Instrumen immutable untuk wawancara riset konsumen.

Kategori membantu coding setelah jawaban terbuka; bukan naskah yang wajib
 dibacakan kepada responden. Snapshot disimpan bersama setiap versi instrumen agar
arti data lama tidak mengikuti perubahan kode aplikasi.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping, Sequence


KODE_VERSI_AKTIF = "b2c-masalah-v1"
SLUG_STUDI_AKTIF = "validasi-masalah-b2c-orang-tua"

PERTANYAAN = (
    {
        "kode": "Q1",
        "judul": "Kejadian terakhir",
        "pertanyaan": "Terakhir kali mendampingi matematika, kapan dan sedang belajar apa?",
        "bantuan": "Mulai dari cerita responden. Kode konteks dipilih interviewer setelah mendengar jawaban.",
        "pilihan": (
            ("konteks_sekolah", "Materi atau PR sekolah", "Konteks"),
            ("konteks_ujian", "Persiapan ujian sekolah", "Konteks"),
            ("konteks_osn", "OSN atau pengayaan", "Konteks"),
            ("konteks_tambahan", "Latihan tambahan", "Konteks"),
            ("konteks_lain", "Konteks lain", "Konteks"),
        ),
    },
    {
        "kode": "Q2",
        "judul": "Masalah yang terjadi",
        "pertanyaan": "Apa yang terjadi sampai anak membutuhkan bantuan?",
        "bantuan": "Catat kejadian yang diceritakan, bukan dugaan yang belum dikatakan responden.",
        "pilihan": (
            ("masalah_belum_paham", "Belum memahami materi", "Masalah"),
            ("masalah_tidak_mulai", "Tidak tahu mulai dari mana", "Masalah"),
            ("masalah_salah_makna", "Salah memahami soal", "Masalah"),
            ("masalah_hitung", "Salah hitung atau kurang teliti", "Masalah"),
            ("masalah_fokus", "Tidak fokus", "Masalah"),
            ("masalah_lain", "Masalah lain", "Masalah"),
        ),
    },
    {
        "kode": "Q3",
        "judul": "Bagian tersulit",
        "pertanyaan": "Dari kejadian itu, bagian yang paling sulit bagi Anda apa?",
        "bantuan": "Pilih satu kode utama bila responden menetapkan prioritas. Jawaban tambahan tidak perlu dipaksa.",
        "pilihan": (
            ("sulit_memahami", "Memahami materi terlebih dahulu", "Kesulitan"),
            ("sulit_menjelaskan", "Menjelaskan kepada anak", "Kesulitan"),
            ("sulit_latihan", "Memilih latihan", "Kesulitan"),
            ("sulit_menilai", "Menilai apakah anak sudah paham", "Kesulitan"),
            ("sulit_waktu_fokus", "Menyediakan waktu atau menjaga fokus", "Kesulitan"),
            ("sulit_tidak_ada", "Tidak merasa kesulitan", "Kesulitan"),
            ("sulit_lain", "Kesulitan lain", "Kesulitan"),
        ),
    },
    {
        "kode": "Q4",
        "judul": "Yang dilakukan",
        "pertanyaan": "Waktu itu Anda melakukan apa?",
        "bantuan": "Boleh ada beberapa tindakan. Kode utama adalah tindakan yang paling berperan menurut responden.",
        "pilihan": (
            ("cara_jelaskan", "Menjelaskan sendiri", "Tindakan"),
            ("cara_ai", "Menggunakan AI", "Tindakan"),
            ("cara_internet", "Mencari internet atau video", "Tindakan"),
            ("cara_buku", "Menggunakan buku", "Tindakan"),
            ("cara_guru", "Bertanya kepada guru atau tutor", "Tindakan"),
            ("cara_tunda", "Menunda", "Tindakan"),
            ("cara_lain", "Tindakan lain", "Tindakan"),
        ),
    },
    {
        "kode": "Q5",
        "judul": "Alasan dan fungsi bantuan",
        "pertanyaan": "Mengapa memilih cara itu, dan bantuan tersebut paling berguna untuk apa?",
        "bantuan": "Kode alasan dan fungsi secara terpisah bila keduanya muncul. Tidak perlu mengejar keduanya bila responden hanya menyebut satu.",
        "pilihan": (
            ("alasan_cepat", "Paling cepat", "Alasan memilih"),
            ("alasan_mudah", "Paling mudah", "Alasan memilih"),
            ("alasan_terbiasa", "Sudah terbiasa", "Alasan memilih"),
            ("alasan_tanpa_alternatif", "Tidak tahu alternatif lain", "Alasan memilih"),
            ("alasan_cocok", "Hasil dianggap paling cocok", "Alasan memilih"),
            ("fungsi_paham_ortu", "Membantu orang tua memahami materi", "Fungsi bantuan"),
            ("fungsi_jawaban", "Mendapatkan jawaban", "Fungsi bantuan"),
            ("fungsi_menjelaskan", "Mendapatkan cara menjelaskan", "Fungsi bantuan"),
            ("fungsi_latihan", "Membuat latihan", "Fungsi bantuan"),
            ("fungsi_periksa", "Memeriksa jawaban", "Fungsi bantuan"),
            ("fungsi_lain", "Fungsi lain", "Fungsi bantuan"),
        ),
    },
    {
        "kode": "Q6",
        "judul": "Hasil kejadian",
        "pertanyaan": "Setelah menggunakan cara itu, hasilnya bagaimana?",
        "bantuan": "Terima hasil yang memang diketahui responden. Jangan memaksa bukti tahap pilot pada wawancara masalah.",
        "pilihan": (
            ("hasil_selesai", "Anak dapat menyelesaikan soal", "Hasil"),
            ("hasil_banyak_bantuan", "Masih membutuhkan banyak bantuan", "Hasil"),
            ("hasil_belum", "Belum dapat menyelesaikan", "Hasil"),
            ("hasil_tunda", "Pendampingan ditunda", "Hasil"),
            ("hasil_tidak_tahu", "Responden tidak tahu hasilnya", "Hasil"),
            ("hasil_lain", "Hasil lain", "Hasil"),
        ),
    },
    {
        "kode": "Q7",
        "judul": "Yang masih menyulitkan",
        "pertanyaan": "Setelah itu, apa yang masih menyulitkan dan seberapa mengganggu bagi Anda?",
        "bantuan": "Kode masalah tersisa dan intensitas hanya bila disebut atau dikonfirmasi responden.",
        "pilihan": (
            ("sisa_memahami", "Memahami materi", "Masalah tersisa"),
            ("sisa_menjelaskan", "Menjelaskan kepada anak", "Masalah tersisa"),
            ("sisa_latihan", "Menemukan latihan yang sesuai", "Masalah tersisa"),
            ("sisa_menilai", "Menilai apakah anak sudah paham", "Masalah tersisa"),
            ("sisa_waktu_fokus", "Waktu atau fokus", "Masalah tersisa"),
            ("sisa_selesai", "Sudah cukup terselesaikan", "Masalah tersisa"),
            ("intensitas_1", "1 — Tidak mengganggu", "Intensitas"),
            ("intensitas_2", "2 — Sedikit mengganggu", "Intensitas"),
            ("intensitas_3", "3 — Cukup mengganggu", "Intensitas"),
            ("intensitas_4", "4 — Sangat mengganggu", "Intensitas"),
            ("sisa_lain", "Masalah lain", "Masalah tersisa"),
        ),
    },
    {
        "kode": "Q8",
        "judul": "Frekuensi",
        "pertanyaan": "Dalam 30 hari terakhir, kira-kira berapa kali situasi serupa terjadi?",
        "bantuan": "Angka dalam jawaban bebas boleh lebih spesifik daripada kategori coding.",
        "pilihan": (
            ("frekuensi_pertama", "Baru pertama kali", "Frekuensi"),
            ("frekuensi_1", "1 kali", "Frekuensi"),
            ("frekuensi_2_3", "2–3 kali", "Frekuensi"),
            ("frekuensi_4_6", "4–6 kali", "Frekuensi"),
            ("frekuensi_7_plus", "Lebih dari 6 kali", "Frekuensi"),
            ("frekuensi_tidak_ingat", "Tidak ingat", "Frekuensi"),
        ),
    },
    {
        "kode": "Q9",
        "judul": "Bantuan yang biasa digunakan",
        "pertanyaan": "Saat mendampingi matematika, bantuan apa yang paling sering Anda gunakan?",
        "bantuan": "Bedakan yang biasa digunakan dari solusi yang hanya pernah dicoba sekali.",
        "pilihan": (
            ("bantuan_ai", "AI", "Bantuan"),
            ("bantuan_internet", "Internet atau video", "Bantuan"),
            ("bantuan_buku", "Buku", "Bantuan"),
            ("bantuan_guru", "Guru atau tutor", "Bantuan"),
            ("bantuan_keluarga", "Anggota keluarga", "Bantuan"),
            ("bantuan_tidak_ada", "Tidak menggunakan bantuan", "Bantuan"),
            ("bantuan_lain", "Bantuan lain", "Bantuan"),
        ),
    },
)


def snapshot() -> dict:
    """Bangun representasi JSON stabil tanpa tuple Python."""
    return {
        "versi": 1,
        "kode": KODE_VERSI_AKTIF,
        "studi": SLUG_STUDI_AKTIF,
        "pertanyaan": [
            {
                "kode": item["kode"],
                "judul": item["judul"],
                "pertanyaan": item["pertanyaan"],
                "bantuan": item["bantuan"],
                "pilihan": [
                    {"kode": kode, "label": label, "kelompok": kelompok}
                    for kode, label, kelompok in item["pilihan"]
                ],
            }
            for item in PERTANYAAN
        ],
    }


def json_kanonis(data: Mapping) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sidik(data: Mapping) -> str:
    return hashlib.sha256(json_kanonis(data).encode("utf-8")).hexdigest()


def validasi_snapshot(data) -> dict:
    """Tolak snapshot rusak/ambigu; versi historis tetap dibaca dari DB."""
    if not isinstance(data, dict) or set(data) != {"versi", "kode", "studi", "pertanyaan"}:
        raise ValueError("snapshot instrumen tidak sah")
    if data["versi"] != 1 or not isinstance(data["kode"], str) or not isinstance(data["studi"], str):
        raise ValueError("snapshot instrumen tidak sah")
    if not isinstance(data["pertanyaan"], list) or not data["pertanyaan"]:
        raise ValueError("snapshot instrumen tidak sah")
    pertanyaan_terlihat = set()
    kode_terlihat = set()
    for item in data["pertanyaan"]:
        if not isinstance(item, dict) or set(item) != {"kode", "judul", "pertanyaan", "bantuan", "pilihan"}:
            raise ValueError("snapshot instrumen tidak sah")
        kode_q = item["kode"]
        if not isinstance(kode_q, str) or not re.fullmatch(r"Q[1-9][0-9]?", kode_q) or kode_q in pertanyaan_terlihat:
            raise ValueError("snapshot instrumen tidak sah")
        pertanyaan_terlihat.add(kode_q)
        if any(not isinstance(item[k], str) or not item[k].strip() for k in ("judul", "pertanyaan", "bantuan")):
            raise ValueError("snapshot instrumen tidak sah")
        if not isinstance(item["pilihan"], list) or not item["pilihan"]:
            raise ValueError("snapshot instrumen tidak sah")
        for opsi in item["pilihan"]:
            if not isinstance(opsi, dict) or set(opsi) != {"kode", "label", "kelompok"}:
                raise ValueError("snapshot instrumen tidak sah")
            kode = opsi["kode"]
            if (not isinstance(kode, str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", kode)
                    or kode in kode_terlihat
                    or any(not isinstance(opsi[k], str) or not opsi[k].strip() for k in ("label", "kelompok"))):
                raise ValueError("snapshot instrumen tidak sah")
            kode_terlihat.add(kode)
    return data


def muat_json(teks: str) -> dict:
    try:
        data = json.loads(teks)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("snapshot instrumen tidak sah") from None
    return validasi_snapshot(data)


def pertanyaan(data: Mapping, kode: str) -> dict:
    cocok = [item for item in data["pertanyaan"] if item["kode"] == kode]
    if len(cocok) != 1:
        raise LookupError("pertanyaan tidak tersedia")
    return cocok[0]


def kode_diizinkan(item: Mapping) -> frozenset:
    return frozenset(opsi["kode"] for opsi in item["pilihan"])


def label_kode(data: Mapping) -> dict:
    return {
        opsi["kode"]: opsi["label"]
        for item in data["pertanyaan"]
        for opsi in item["pilihan"]
    }


def kelompok_pilihan(item: Mapping) -> Sequence[tuple]:
    urutan = []
    hasil = {}
    for opsi in item["pilihan"]:
        kelompok = opsi["kelompok"]
        if kelompok not in hasil:
            urutan.append(kelompok)
            hasil[kelompok] = []
        hasil[kelompok].append(opsi)
    return tuple((kelompok, tuple(hasil[kelompok])) for kelompok in urutan)
