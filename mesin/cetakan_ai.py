"""Klien AI khusus draf cetakan soal berpola (C3): satu permintaan DeepSeek -> 1-3 kandidat cetakan (dict).

SENGAJA terpisah dari `llm.py` dan `ai_service`/`ai_store`: sakelar "Hentikan" dan batas fitur di /admin/ai
mengatur fitur AI lama (parafrase, Pendamping, lampiran) dan akan dimatikan pemilik, sedangkan draf cetakan harus
tetap hidup. Karena itu modul ini TIDAK mengecek `AI_NONAKTIF` dan tidak tercatat di ledger /admin/ai; batasnya
ada di `cetakan_ai_store` (kuota harian) dan timeout/ukuran di sini.

Garis yang tidak boleh dilanggar:
- Muatan privat by construction: `muatan(kelas, bab)` murni dan hanya menerima kelas + `Bab` kurikulum (data beku).
  Isinya kelas, judul bab, sub-materi, aturan cetakan, dan satu contoh format. Tak pernah menerima akun, sesi,
  permintaan HTTP, atau data anak.
- AI hanya menulis DATA kandidat. Pemanggil memaksa kelas/bab, memvalidasi lewat `cetakan_pola`, dan kunci
  selalu dihitung mesin; modul ini tidak memvalidasi isi kandidat.
- Galat dipetakan ke `GalatAI` dengan alasan ramah yang tidak memuat kunci API, alamat lengkap, atau isi balasan.

Konfigurasi dibaca dari env SAAT DIPANGGIL (bukan saat impor), seperti `llm.konfigurasi`. Konstanta bawaan
URL/model diduplikasi dari `llm.py` karena mengimpor `llm` menarik `ai_service` (kebalikan dari tujuan di atas).
Hanya stdlib + `cetakan_pola` + `kurikulum_kelas`.
"""
from __future__ import annotations

import http.client
import json
import logging
import os
from typing import Dict, List, Tuple
import urllib.error
import urllib.request

import cetakan_pola as pola
import kurikulum_kelas as kk

ENV_BASE_URL = "DEEPSEEK_BASE_URL"
ENV_API_KEY = "DEEPSEEK_API_KEY"
ENV_MODEL = "DEEPSEEK_MODEL"
# Salinan `llm.BASE_URL_BAWAAN` dan `llm.MODEL_BAWAAN` (lihat docstring modul); tes menjaga keduanya sama.
BASE_URL_BAWAAN = "https://api.deepseek.com"
MODEL_BAWAAN = "deepseek-flash"

BATAS_WAKTU_DETIK = 30
BATAS_RESPONS_BYTE = 8192
TEMPERATUR = 0.4
MAKS_TOKEN = 1500
MIN_KANDIDAT = 1
MAKS_KANDIDAT = 3
SKEMA_URL_SAH = ("https://", "http://")

_log = logging.getLogger(__name__)

COPY_TANPA_KUNCI = "Kunci layanan AI belum dipasang di server ini."
COPY_TIDAK_TERHUBUNG = "Layanan AI tidak dapat dihubungi (jaringan atau waktu habis)."
COPY_DITOLAK = "Layanan AI menolak permintaan (kode %d)."
COPY_ALAMAT = "Alamat layanan AI di pengaturan server tidak sah."
COPY_TERLALU_PANJANG = "Jawaban AI terlalu panjang, jadi ditolak."
COPY_BUKAN_JSON = "Jawaban AI bukan JSON yang bisa dibaca."
COPY_BENTUK = "Jawaban AI tidak berisi daftar cetakan yang dikenali."


class GalatAI(Exception):
    """Permintaan ke AI gagal; `str(galat)` aman ditampilkan ke admin (tanpa rahasia)."""


def konfigurasi() -> Dict[str, str]:
    """Env dibaca saat dipanggil supaya bisa diuji."""
    return {
        "base_url": os.environ.get(ENV_BASE_URL, BASE_URL_BAWAAN).rstrip("/"),
        "api_key": os.environ.get(ENV_API_KEY, "").strip(),
        "model": os.environ.get(ENV_MODEL, MODEL_BAWAAN),
    }


def aktif() -> bool:
    """True hanya bila kunci API ada. Tanpa panggilan jaringan."""
    return bool(konfigurasi()["api_key"])


# --- muatan (murni) -----------------------------------------------------------

def _aturan() -> str:
    return (
        "Kamu membantu menulis CETAKAN soal matematika SD dalam bentuk data JSON, bukan kode. "
        "Mesin kami yang memvalidasi dan menghitung kunci jawaban, jadi kamu hanya menulis cetakannya.\n"
        "Aturan cetakan:\n"
        "- Variabel: 1 sampai %d, masing-masing satu huruf kecil (a-z). Rentang tiap variabel adalah "
        "[min, max] bilangan bulat dengan 0 <= min <= max <= %d.\n"
        "- \"kunci\" adalah rumus aritmetika dari variabel; hasilnya harus bilangan bulat >= 0. "
        "Operator yang boleh hanya + - * // %% dan kurung, tanpa fungsi, pangkat, desimal, atau teks.\n"
        "- \"syarat\" (opsional, maksimal %d) adalah perbandingan seperti a + b <= 99, boleh digabung and/or. "
        "Untuk pembagian pakai syarat a %% b == 0 supaya hasilnya habis dibagi.\n"
        "- \"teks\" (maksimal %d karakter, tanpa HTML atau tanda < >) memakai placeholder seperti {a}; "
        "setiap variabel harus muncul sebagai placeholder. Placeholder {nama} hanya bila \"nama\" bernilai true "
        "(nama anak sintetis diisi mesin).\n"
        "- \"pembahasan\" (opsional, maksimal %d karakter) boleh memakai placeholder variabel, {nama}, dan {kunci}.\n"
        "- \"judul\" maksimal %d karakter. \"nama\" bernilai true atau false.\n"
        "- Rumus dan syarat maksimal %d karakter.\n"
        "- Soal harus hanya teks dan angka (tanpa gambar atau diagram) dan menghasilkan sedikitnya %d soal berbeda.\n"
        "Jawab HANYA dengan satu objek JSON berbentuk {\"cetakan\": [ ... ]} berisi %d sampai %d cetakan."
    ) % (pola.MAKS_VARIABEL, pola.BATAS_KONSTANTA, pola.MAKS_SYARAT, pola.MAKS_TEKS, pola.MAKS_PEMBAHASAN,
         pola.MAKS_JUDUL, pola.MAKS_EKSPRESI, pola.MIN_UNIK, MIN_KANDIDAT, MAKS_KANDIDAT)


PESAN_SISTEM = _aturan()


def _contoh_format(kelas: int, nomor_bab: int) -> str:
    contoh = {
        "kelas": kelas, "bab": nomor_bab,
        "judul": "Penjumlahan dua angka dalam soal cerita",
        "teks": "{nama} punya {a} kelereng. Ia diberi {b} kelereng lagi. Berapa kelereng {nama} sekarang?",
        "variabel": {"a": [10, 50], "b": [1, 40]},
        "nama": True,
        "syarat": ["a + b <= 99"],
        "kunci": "a + b",
        "pembahasan": "{a} + {b} = {kunci}",
    }
    return json.dumps(contoh, ensure_ascii=False)


def pesan_pengguna(kelas: int, bab: kk.Bab) -> str:
    sub = "\n".join("- %s" % materi for materi in bab.sub_materi)
    return (
        "Kelas: %d\nBab %d: %s\nSub-materi bab:\n%s\n\n"
        "Tulis cetakan soal untuk bab ini. Contoh format satu cetakan (isi dan angkanya ganti sesuai bab):\n%s"
    ) % (kelas, bab.nomor, bab.judul, sub, _contoh_format(kelas, bab.nomor))


def muatan(kelas: int, bab: kk.Bab) -> List[Dict[str, str]]:
    """`messages` untuk permintaan. Murni: hanya kelas dan bab kurikulum; tidak ada akun/sesi/anak."""
    return [{"role": "system", "content": PESAN_SISTEM},
            {"role": "user", "content": pesan_pengguna(kelas, bab)}]


# --- permintaan ---------------------------------------------------------------

def _badan_permintaan(model: str, kelas: int, bab: kk.Bab) -> bytes:
    return json.dumps({
        "model": model, "messages": muatan(kelas, bab), "temperature": TEMPERATUR, "max_tokens": MAKS_TOKEN,
        "response_format": {"type": "json_object"},
    }, ensure_ascii=False).encode("utf-8")


def _kirim(kelas: int, bab: kk.Bab, konf: Dict[str, str]) -> bytes:
    """POST ke `{base}/chat/completions`; kembalikan badan mentah (<= BATAS_RESPONS_BYTE) atau GalatAI."""
    if not konf["api_key"]:
        raise GalatAI(COPY_TANPA_KUNCI)
    if not konf["base_url"].startswith(SKEMA_URL_SAH):
        raise GalatAI(COPY_ALAMAT)
    try:
        req = urllib.request.Request(
            konf["base_url"] + "/chat/completions", data=_badan_permintaan(konf["model"], kelas, bab),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + konf["api_key"]},
            method="POST")
    except ValueError:
        raise GalatAI(COPY_ALAMAT) from None
    try:
        with urllib.request.urlopen(req, timeout=BATAS_WAKTU_DETIK) as resp:
            mentah = resp.read(BATAS_RESPONS_BYTE + 1)
    except urllib.error.HTTPError as err:
        _log.warning("Draf AI cetakan: HTTP %s.", err.code)
        raise GalatAI(COPY_DITOLAK % err.code) from None
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        _log.warning("Draf AI cetakan gagal (%s).", type(err).__name__)
        raise GalatAI(COPY_TIDAK_TERHUBUNG) from None
    if len(mentah) > BATAS_RESPONS_BYTE:
        raise GalatAI(COPY_TERLALU_PANJANG)
    return mentah


def _isi_pesan(mentah: bytes) -> str:
    """`choices[0].message.content` sebagai teks; bentuk apa pun yang menyimpang = GalatAI."""
    try:
        isi = json.loads(mentah.decode("utf-8"))["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError, RecursionError):  # UnicodeDecodeError adalah ValueError
        raise GalatAI(COPY_BUKAN_JSON) from None
    if not isinstance(isi, str):
        raise GalatAI(COPY_BUKAN_JSON)
    return isi


def urai_kandidat(mentah: bytes) -> Tuple[object, ...]:
    """Kandidat cetakan (1..MAKS_KANDIDAT; lebih banyak dipotong ke yang pertama) dari badan balasan mentah."""
    try:
        objek = json.loads(_isi_pesan(mentah))
    except (ValueError, RecursionError):
        raise GalatAI(COPY_BUKAN_JSON) from None
    daftar = objek.get("cetakan") if isinstance(objek, dict) else None
    if not isinstance(daftar, list) or len(daftar) < MIN_KANDIDAT:
        raise GalatAI(COPY_BENTUK)
    return tuple(daftar[:MAKS_KANDIDAT])


def minta_kandidat(kelas: int, bab: kk.Bab) -> Tuple[object, ...]:
    """Satu permintaan ke AI; kandidat BELUM divalidasi (bisa bukan objek sama sekali). Galat = GalatAI."""
    return urai_kandidat(_kirim(kelas, bab, konfigurasi()))
