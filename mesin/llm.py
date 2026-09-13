"""Klien DeepSeek — pembungkus cerita soal waktu-jalan (opsi B2, plan Fase 5).

Peran LLM di mesin ini SANGAT terbatas dan itu disengaja:

  - Python (templates.py) tetap menghitung parameter, kunci, dan malrule.
  - LLM HANYA menulis ulang kalimat soalnya jadi cerita yang berbeda-beda,
    supaya anak tidak menebak pola dari bunyi soal yang selalu sama.
  - Kalimat hasil LLM diverifikasi: setiap angka di dalamnya harus cocok
    dengan angka di parameter/kunci soal asli. Gagal verifikasi -> None,
    pemanggil memakai kalimat bawaan dari template.

Dua garis yang tidak boleh dilanggar modul ini:

  1. Kunci dan malrule TIDAK PERNAH dikirim ke API. Yang keluar hanya
     kalimat soal asli + parameternya, dan prompt melarang model menjawab.
  2. Gagal-diam: tanpa DEEPSEEK_API_KEY semua fungsi langsung pulang
     tanpa network call dan tanpa exception. Fitur mati, aplikasi jalan.

Klien ini stdlib-murni (urllib) dan TERISOLASI: tidak mengubah modul lain.
Pemanggil yang menyambungkannya ke web.py/generator.py — bukan modul ini.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from typing import Any

from templates import Soal
import presentation_lock
import question_views
import ai_service as ai_control
from visual_contract import buat_penyajian

_bucket_ai = ContextVar("bucket_ai_llm", default=None)


@contextmanager
def gunakan_bucket_akun(nilai):
    """Ikat bucket pemilik tanpa mengubah kontrak fungsi publik/fixture lama."""
    token = _bucket_ai.set(nilai)
    try:
        yield
    finally:
        _bucket_ai.reset(token)


# ── Konfigurasi lingkungan ──────────────────────────────────────────────

ENV_BASE_URL = "DEEPSEEK_BASE_URL"
ENV_API_KEY = "DEEPSEEK_API_KEY"
ENV_MODEL = "DEEPSEEK_MODEL"
ENV_VISION_MODEL = "DEEPSEEK_VISION_MODEL"
ENV_SALDO_MIN = "DEEPSEEK_SALDO_MIN"

BASE_URL_BAWAAN = "https://api.deepseek.com"
MODEL_BAWAAN = "deepseek-flash"
VISION_MODEL_BAWAAN = "deepseek-flash"

# Request singkat: soal dibungkus saat lembar disusun, menggantung lebih
# dari ini lebih baik dibuang daripada membuat murid menunggu.
BATAS_WAKTU_DETIK = 20

# max_tokens harus menampung reasoning model: deepseek-flash menulis
# reasoning_content SEBELUM konten (terukur: +-825 reasoning token untuk
# 6 soal). Batas lama 200 membuat konten sering kosong dan fitur gagal
# diam-diam. Cerita 1 kalimat tetap pendek — kelebihan kuota tidak
# berarti teks lebih panjang, dan cache membuat biaya dibayar sekali.
MAX_TOKENS = 2000

# Vision (lampiran foto): deepseek-flash juga reasoning model
# — terukur 718 reasoning token untuk 6 soal.
# Vision membaca lembar utuh: jawaban + caraku untuk sampai puluhan soal.
# 3000 terbukti kurang di lapangan (2 Sep 2026): sesi 50 soal membuat
# balasan terpotong di soal ke-11 dan seluruh hasil terbuang. Prompt kini
# meminta caraku singkat, tapi batasnya tetap dinaikkan supaya lembar
# panjang muat utuh.
MAX_TOKENS_VISION = 8000

# Naikkan versi ini kalau prompt berubah — kunci cache ikut berubah,
# jadi kalimat lama tidak dipakai ulang untuk soal berprompt baru.
#
# v2 (2 Sep 2026): kunci cache kini memuat template_id + latar. Versi lama
# hanya memakai parameter, dan itu membuat dua template BERBEDA berbagi
# entri cache saat parameternya kebetulan sama — terukur 354 tabrakan
# (mis. {"a": 9, "b": 24} dipakai `angka_satuan_pangkat` DAN
# `kerja_bersama`). Cache hit pulang tanpa lewat verifikasi(), jadi soal
# KPK bisa tampil memakai cerita milik soal pangkat.
VERSI_PROMPT = "b2-cerita-v2"

# ── Latar cerita berputar ──────────────────────────────────────────────
#
# Satu soal punya SATU parameter, jadi versi lama hanya bisa punya SATU
# cerita seumur hidup — bank soal tetap terasa monoton meski dibungkus
# LLM. Latar menambah dimensi kedua ke kunci cache: soal yang sama boleh
# punya beberapa penyamaran, dipilih deterministik dari sidik jari soal.
#
# Deterministik itu syarat, bukan kenyamanan: seed yang sama harus
# melahirkan lembar yang sama (kontrak generator.py), dan cache hanya
# berguna kalau soal yang sama selalu meminta latar yang sama. Dipakai
# hash SHA-256, BUKAN hash() bawaan — hash() diacak per proses
# (PYTHONHASHSEED) sehingga latar bisa berubah tiap kali server restart.
LATAR = (
    "pasar pagi",
    "kantin sekolah",
    "kebun belakang rumah",
    "toko kue",
    "lomba 17 Agustus",
    "perpustakaan sekolah",
    "bengkel sepeda",
    "warung sayur",
)


def konfigurasi() -> dict[str, str]:
    """Baca env SAAT DIPANGGIL (bukan saat impor) supaya bisa diuji."""
    return {
        "base_url": os.environ.get(ENV_BASE_URL, BASE_URL_BAWAAN).rstrip("/"),
        "api_key": os.environ.get(ENV_API_KEY, "").strip(),
        "model": os.environ.get(ENV_MODEL, MODEL_BAWAAN),
    }


def aktif() -> bool:
    """True hanya jika API key ada dan tidak kosong. Tanpa network call."""
    return bool(konfigurasi()["api_key"])


# ── Cache ───────────────────────────────────────────────────────────────
#
# Satu soal tidak pernah dibayar dua kali: kalimat hasil LLM disimpan
# berkunci hash(template_id + parameter + latar + versi_prompt + model).
# Tabelnya dibuat oleh PEMANGGIL lewat ensure_table(kon), pola yang sama
# dengan skema di schema.py/database.py — modul ini tidak menyentuh skema
# milik orang lain.


def ensure_table(kon: sqlite3.Connection) -> None:
    """Buat tabel llm_cache bila belum ada. Aman dijalankan berulang."""
    kon.execute(
        """CREATE TABLE IF NOT EXISTS llm_cache (
               kunci_hash TEXT PRIMARY KEY,
               kalimat    TEXT NOT NULL,
               model      TEXT NOT NULL,
               dibuat     TEXT NOT NULL DEFAULT (datetime('now'))
           )"""
    )


def pilih_latar(soal: Soal, putaran: int = 0) -> str:
    """Latar cerita untuk satu soal — deterministik, berputar.

    Dipilih dari sidik jari soal (template_id + parameter), bukan dari
    random module: soal yang sama HARUS selalu meminta latar yang sama,
    kalau tidak cache tidak pernah kena dan tiap generate membayar ulang.

    `putaran` menaikkan indeks: guru yang menekan "variasi cerita" untuk
    kedua kalinya pada soal yang sama mendapat latar berikutnya, bukan
    kalimat yang identik. Nol berarti latar pertama.

    SHA-256, bukan hash() bawaan — hash() diacak per proses lewat
    PYTHONHASHSEED, jadi latar akan berubah tiap server restart dan
    seluruh cache jadi sia-sia.
    """
    sidik = hashlib.sha256(
        f"{soal.template_id}|{soal.tanda_tangan}".encode("utf-8")
    ).hexdigest()
    return LATAR[(int(sidik[:8], 16) + putaran) % len(LATAR)]


def kunci_cache(
    parameter: dict[str, Any],
    model: str | None = None,
    template_id: str = "",
    latar: str = "",
) -> str:
    """Sidik jari cache: template + parameter + latar + versi prompt + model.

    Parameter diurutkan agar {"awal": 2, "beda": 3} dan {"beda": 3,
    "awal": 2} berbagi entri cache — soal yang sama, bayar sekali.

    `template_id` WAJIB ada di sidik jari. Tanpa itu dua template berbeda
    yang kebetulan berparameter sama berbagi entri (terukur 354 tabrakan
    di bank soal, mis. {"a": 9, "b": 24} pada `angka_satuan_pangkat` dan
    `kerja_bersama`), dan karena cache hit pulang TANPA verifikasi(), soal
    yang satu tampil memakai cerita milik soal yang lain. Default ""
    dipertahankan supaya pemanggil lama tidak pecah — tapi seluruh
    pemanggil di modul ini mengisinya.

    `latar` memisahkan beberapa penyamaran untuk soal yang sama, sehingga
    satu soal bisa punya lebih dari satu cerita.
    """
    if model is None:
        model = konfigurasi()["model"]
    butir = json.dumps(
        {
            "template_id": template_id,
            "parameter": parameter,
            "latar": latar,
            "versi_prompt": VERSI_PROMPT,
            "model": model,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(butir.encode("utf-8")).hexdigest()


# ── Verifikasi angka (murni, tanpa network) ────────────────────────────


_POLA_ANGKA = re.compile(r"-?\d+(?:\.\d+)?")


def angka_dalam(teks: str) -> set[float]:
    """Semua angka (int/desimal) di sebuah teks, sebagai himpunan float."""
    return {float(m.group()) for m in _POLA_ANGKA.finditer(teks)}


def sumber_angka(soal: Soal) -> set[float]:
    """Angka yang BOLEH muncul di kalimat hasil LLM.

    Sumbernya dua, keduanya sudah dilihat anak di kalimat asli:

      1. nilai parameter,
      2. angka di kalimat soal asli — penting: banyak template menampilkan
         suku-suku deret yang dihitung dari parameter (mis. 2, 5, 8, 11),
         bukan parameternya sendiri. Menulis ulang cerita pasti memakai
         angka-angka itu lagi.

    Angka KUNCI SENGAJA TIDAK ADA DI SINI.

    Versi pertama memasukkannya (mengikuti kontrak "angka harus cocok
    dengan parameter/kunci") dan itu membuka lubang paling mahal di
    seluruh aplikasi: kalimat "Jawabannya 4193." lolos verifikasi, karena
    4193 memang kunci yang sah. Anak membaca soal beserta jawabannya, dan
    dua kode yang tidak bisa dipulihkan dari data mana pun (N menebak,
    T belum pernah lihat) mati diam-diam — laporan tetap tampak normal.

    Kunci yang kebetulan sama dengan angka yang memang tampil di soal
    (mis. pola siklus) tetap lolos lewat jalur nomor 2, jadi pembatasan
    ini tidak menolak kalimat yang sah.
    """
    diizinkan: set[float] = set()
    for nilai in soal.parameter.values():
        diizinkan |= angka_dalam(str(nilai))
    diizinkan |= angka_dalam(soal.teks)
    return diizinkan


def verifikasi(kalimat: str, soal: Soal) -> bool:
    """Terima kalimat pengganti hanya jika semua angkanya sah.

    Murni dan bisa dites tanpa network. Tiga penolakan, masing-masing
    menutup kerusakan yang berbeda:

      1. kosong / multiline — yang diminta SATU kalimat;
      2. ada angka yang bukan dari soal — model mengarang;
      3. angka soal yang HILANG — subset saja tidak cukup. Himpunan kosong
         adalah subset dari apa pun, jadi "Ada pola bilangan, berapa suku
         berikutnya?" lolos aturan subset padahal soalnya jadi tidak bisa
         dikerjakan sama sekali. Kalimat pengganti wajib membawa kembali
         setiap angka yang tampil di kalimat asli.
    """
    if not kalimat or not kalimat.strip():
        return False
    bersih = kalimat.strip()
    if "\n" in bersih:
        return False

    ada = angka_dalam(bersih)
    if not (ada <= sumber_angka(soal)):
        return False  # mengarang angka

    wajib = angka_dalam(soal.teks)
    if not (wajib <= ada):
        return False  # menghilangkan angka yang dibutuhkan anak

    # Kunci tidak boleh muncul kecuali ia memang bagian dari soal aslinya.
    kunci_angka = angka_dalam(soal.kunci)
    if kunci_angka and not (kunci_angka <= wajib) and (kunci_angka & ada):
        return False

    # Kunci non-angka (huruf siklus, nama hari, pecahan) — periksa teksnya.
    if not kunci_angka and soal.kunci and len(soal.kunci) >= 2:
        if soal.kunci.lower() in bersih.lower() and soal.kunci not in soal.teks:
            return False

    return True


# ── Prompt & respons ───────────────────────────────────────────────────


def _buat_prompt(soal: Soal, latar: str = "") -> list[dict[str, str]]:
    """Pesan untuk /chat/completions. Kunci & malrule sengaja tidak dikirim.

    `latar` disebut eksplisit supaya dua soal sejenis tidak kembali ke
    latar yang sama. Tanpa arahan latar, model punya kecenderungan kuat
    memilih beberapa cerita favorit ("Ani menabung", "Budi membeli
    permen") dan monotonnya cuma bergeser dari template ke LLM.
    """
    sistem = (
        "Kamu penulis soal matematika untuk anak SD Indonesia. "
        "Tugasmu HANYA menulis ulang SATU kalimat soal yang diberikan "
        "menjadi kalimat soal PENGGANTI dengan latar cerita yang berbeda. "
        "Aturan mutlak: jenis pertanyaan dan SEMUA angka harus persis sama; "
        "jangan menjawab soal, memberi petunjuk jawaban, menambah "
        "pertanyaan lain, atau mengubah angka apa pun. Jawab hanya dengan "
        "satu kalimat soal, tanpa penjelasan."
    )
    parameter = ", ".join(f"{k}={soal.parameter[k]}" for k in sorted(soal.parameter))
    tugas = (
        "Tulis satu kalimat soal pengganti, "
        "angkanya sama persis dengan kalimat asli."
    )
    muatan: dict[str, str] = {
        "kalimat_soal_asli": soal.teks,
        "parameter": parameter,
        "tugas": tugas,
    }
    if latar:
        muatan["latar_yang_diminta"] = latar
        muatan["tugas"] = (
            f"{tugas} Gunakan latar cerita '{latar}'. "
            "Jangan menambah angka baru untuk latar itu."
        )
    pengguna = json.dumps(muatan, ensure_ascii=False)
    return [
        {"role": "system", "content": sistem},
        {"role": "user", "content": pengguna},
    ]


def parse_respons(data: bytes | bytearray | str | dict) -> str | None:
    """Ambil isi jawaban dari format OpenAI-compatible.

    Struktur yang diharapkan:
      {"choices": [{"message": {"content": "..."}}]}
    Apa pun yang menyimpang -> None, bukan exception.
    """
    try:
        if isinstance(data, dict):
            muatan = data
        else:
            if isinstance(data, (bytes, bytearray)):
                data = data.decode("utf-8")
            muatan = json.loads(data)
        konten = muatan["choices"][0]["message"]["content"]
        if not isinstance(konten, str):
            return None
        if not konten.strip():
            # Reasoning model (deepseek-flash) yang kehabisan max_tokens di
            # reasoning_content mengirim content kosong. Itu kegagalan
            # permintaan, bukan kalimat sah berupa string kosong.
            return None
        return konten.strip()
    except (KeyError, IndexError, TypeError, ValueError, UnicodeDecodeError):
        return None


# ── Network ────────────────────────────────────────────────────────────


def _panggil(pesan: list[dict[str, str]]) -> str | None:
    """POST cerita melalui guard biaya. Error apa pun -> None."""
    cfg = konfigurasi()
    url = cfg["base_url"] + "/chat/completions"
    tubuh = json.dumps(
        {
            "model": cfg["model"],
            "messages": pesan,
            "temperature": 1.0,
            "max_tokens": MAX_TOKENS,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=tubuh,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
        method="POST",
    )
    try:
        def kirim():
            with urllib.request.urlopen(req, timeout=BATAS_WAKTU_DETIK) as resp:
                return parse_respons(resp.read())
        return ai_control.panggil("cerita", _bucket_ai.get(), kirim)
    except (urllib.error.URLError, OSError, ValueError, ai_control.AIUnavailable):
        # HTTPError turunan URLError; socket.timeout turunan OSError;
        # JSON rusak tertangani parse_respons, ValueError sisa pengaman.
        return None


# ── Vision — baca lembar foto (Fase 2, lampiran) ──────────────────────
#
# Peran vision SANGAT mirip peran cerita: Python tetap pemegang kebenaran.
# AI vision HANYA membaca foto lembar yang sudah diisi anak dan mengusulkan
# {nomor, jawaban, caraku} per soal — guru WAJIB konfirmasi sebelum data
# masuk. Garis yang tidak boleh dilanggar: jawaban yang keluar dari model
# TIDAK pernah langsung jadi data; ia hanya bahan di halaman konfirmasi.


def konfigurasi_vision() -> dict[str, str]:
    """Konfigurasi model vision — key sama, model berbeda dari cerita."""
    cfg = konfigurasi()
    return {
        "base_url": cfg["base_url"],
        "api_key": cfg["api_key"],
        "model": os.environ.get(ENV_VISION_MODEL, VISION_MODEL_BAWAAN),
    }


# Alias kunci: model kadang menjawab dalam bahasa Inggris
# ("number"/"answer"/"work") meski prompt berbahasa Indonesia. Menolak
# balasan seperti itu berarti membuang bacaan yang sebenarnya benar —
# bug lapangan 2 Sep 2026 (lembar Filia: 11 soal terbaca, semuanya
# dibuang). Kunci Indonesia tetap yang utama; alias hanya cadangan.
ALIAS_NOMOR = ("nomor", "number", "no", "soal_ke")
ALIAS_JAWABAN = ("jawaban", "answer", "jawab", "hasil")
ALIAS_CARAKU = ("caraku", "cara", "work", "working", "langkah")


def _ambil_alias(butir: dict, alias: tuple[str, ...]):
    """Nilai pertama yang ada di butir menurut urutan alias (None bila tak ada)."""
    for kunci in alias:
        if kunci in butir and butir[kunci] is not None:
            return butir[kunci]
    return None


def _potong_json_terpotong(bersih: str) -> str | None:
    """Selamatkan JSON yang terpotong di tengah karena batas token.

    Model yang diminta membaca 50 soal bisa kehabisan token di soal ke-11:
    string yang keluar valid sampai objek terakhir lalu berhenti mendadak
    ("caraku": "Pola 'ABCDEB' ada 6 huruf. 139 : 6 = 23 sisa 1, jadi hu).
    Membuang seluruhnya berarti kehilangan 10 soal yang sudah benar terbaca.
    Strategi: potong di objek lengkap TERAKHIR (`}` terakhir yang punya
    pasangan `{`) lalu tutup array + objek luar secara sintaksis.
    Kembalikan None kalau tidak ada satu pun objek utuh.
    """
    # Cari akhir objek butir terakhir yang utuh: telusuri dari belakang.
    for i in range(len(bersih) - 1, -1, -1):
        if bersih[i] != "}":
            continue
        calon = bersih[: i + 1] + "]}"
        try:
            data = json.loads(calon)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("soal"), list):
            return calon
    return None


def parse_ekstraksi(konten: str) -> list[dict] | None:
    """Ubah konten model (mungkin dibungkus ```json) jadi daftar hasil.

    Format yang diterima:
      {"soal": [{"nomor": 1, "jawaban": "10", "caraku": "tambah 2"}, ...]}

    Kunci bahasa Inggris (number/answer/work) diterima sebagai alias —
    lihat ALIAS_*. JSON yang terpotong karena batas token diselamatkan
    sampai objek utuh terakhir (_potong_json_terpotong): bacaan sebagian
    tetap berguna, guru yang mengoreksi.

    Apa pun yang menyimpang -> None, bukan exception. Dua garis kebenaran:
      - nomor wajib bilangan bulat >= 1;
      - jawaban/caraku wajib string (boleh kosong — anak melewati soal).
    """
    bersih = konten.strip()
    # Lepas fence ```json ... ```
    if bersih.startswith("```"):
        baris = bersih.splitlines()
        if baris and baris[0].strip().startswith("```"):
            baris = baris[1:]
        if baris and baris[-1].strip().startswith("```"):
            baris = baris[:-1]
        bersih = "\n".join(baris).strip()
    mulai = bersih.find("{")
    if mulai == -1:
        return None
    akhir = bersih.rfind("}")
    data = None
    if akhir > mulai:
        try:
            data = json.loads(bersih[mulai : akhir + 1])
        except ValueError:
            data = None
    if data is None:
        # Kemungkinan terpotong batas token — selamatkan bagian yang utuh.
        selamat = _potong_json_terpotong(bersih[mulai:])
        if selamat is None:
            return None
        try:
            data = json.loads(selamat)
        except ValueError:
            return None
    if not isinstance(data, dict):
        return None
    daftar = data.get("soal")
    if not isinstance(daftar, list) or not daftar:
        return None
    keluar: list[dict] = []
    for butir in daftar:
        if not isinstance(butir, dict):
            return None
        try:
            nilai_nomor = _ambil_alias(butir, ALIAS_NOMOR)
            if nilai_nomor is None:
                return None
            nomor = int(nilai_nomor)
            jawaban = str(_ambil_alias(butir, ALIAS_JAWABAN) or "").strip()
            caraku = str(_ambil_alias(butir, ALIAS_CARAKU) or "").strip()
        except (TypeError, ValueError):
            return None
        if nomor < 1:
            return None
        keluar.append({"nomor": nomor, "jawaban": jawaban, "caraku": caraku})
    return keluar


def verifikasi_ekstraksi(hasil: list[dict], jumlah_soal: int) -> bool:
    """Hasil sah kalau ada minimal satu nomor yang MASIH di rentang 1..N.

    Dulu syaratnya 1..N LENGKAP. Itu membuang hasil yang benar dalam dua
    kasus nyata (2 Sep 2026): (a) foto memuat sebagian soal saja — anak
    memfoto satu lembar dari sesi 50 soal; (b) balasan model terpotong
    batas token. Sekarang bacaan SEBAGIAN diterima — guru tetap wajib
    konfirmasi di halaman lampiran, jadi tidak ada data yang masuk tanpa
    mata manusia.

    Yang masih ditolak: hasil kosong, dan hasil yang SELURUH nomornya di
    luar rentang (mis. semua nomor 99) — itu tanda model tidak membaca
    lembar ini. Nomor asing dibersihkan oleh saring_ekstraksi, bukan di
    sini. Isi jawaban TIDAK diverifikasi: guru yang menilai.
    """
    if not hasil:
        return False
    nomor = {h["nomor"] for h in hasil}
    return bool(nomor & set(range(1, jumlah_soal + 1)))


def saring_ekstraksi(hasil: list[dict], jumlah_soal: int) -> list[dict]:
    """Buang nomor di luar 1..N dan duplikat (ambil kemunculan pertama).

    Verifikasi memutuskan "layak/tidak"; penyaringan memutuskan "apa yang
    dipakai". Nomor 99 pada sesi 12 soal tidak boleh sampai ke halaman
    konfirmasi — ia tak punya sesi_soal_id dan hanya membingungkan guru.
    """
    sah = set(range(1, jumlah_soal + 1))
    keluar: list[dict] = []
    terlihat: set[int] = set()
    for h in hasil:
        n = h["nomor"]
        if n in sah and n not in terlihat:
            terlihat.add(n)
            keluar.append(h)
    return keluar


def ekstrak_lembar(soal_konteks: list[str], gambar_b64: str) -> list[dict] | None:
    """Baca satu foto lembar -> daftar {nomor, jawaban, caraku} per soal.

    Gagal-diam (pola seluruh modul): tanpa key / network error / parse gagal
    / verifikasi gagal -> None, pemanggil menampilkan pesan "tidak terbaca".

    `soal_konteks` adalah teks tiap soal (berurutan 1..N) — dikirim ke model
    supaya ia memetakan jawaban ke nomor yang benar dan tidak mengarang soal.
    """
    cfg = konfigurasi_vision()
    if not cfg["api_key"]:
        return None

    daftar_soal = "\n".join(
        f"{i + 1}. {teks}" for i, teks in enumerate(soal_konteks)
    )
    prompt = (
        "Berikut daftar soal di lembar ini:\n"
        f"{daftar_soal}\n\n"
        "Baca FOTO lembar yang sudah diisi anak. Untuk SETIAP nomor yang "
        "TERLIHAT di foto:\n"
        "- jawaban: angka/kata yang anak tulis di kotak Jawabanku "
        "(kalau kosong, \"\").\n"
        "- caraku: SALINAN SINGKAT tulisan anak di kotak Caraku, maksimal 15 "
        "kata. Coretan tak terbaca tulis \"?\"; kotak kosong tulis \"\".\n"
        "Nomor yang tidak ada di foto boleh dilewati — jangan mengarang.\n"
        "JANGAN menilai benar/salah dan JANGAN menuliskan cara yang benar; "
        "salin apa adanya yang anak tulis.\n"
        'Keluarkan HANYA JSON: {"soal": [{"nomor": 1, "jawaban": "...", '
        '"caraku": "..."}]} tanpa penjelasan.'
    )
    pesan = [
        {
            "role": "system",
            "content": (
                "Kamu membaca lembar jawaban matematika anak SD dari foto. "
                "Jawab hanya JSON, tanpa penjelasan."
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{gambar_b64}"
                    },
                },
                {"type": "text", "text": prompt},
            ],
        },
    ]
    tubuh = json.dumps(
        {
            "model": cfg["model"],
            "messages": pesan,
            "temperature": 0,
            "max_tokens": MAX_TOKENS_VISION,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        cfg["base_url"] + "/chat/completions",
        data=tubuh,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
        method="POST",
    )
    try:
        def kirim():
            with urllib.request.urlopen(
                req, timeout=BATAS_WAKTU_DETIK * 4
            ) as resp:
                return parse_respons(resp.read())
        konten = ai_control.panggil("lampiran", _bucket_ai.get(), kirim)
    except (urllib.error.URLError, OSError, ValueError, ai_control.AIUnavailable):
        return None
    if konten is None:
        return None
    hasil = parse_ekstraksi(konten)
    if hasil is None or not verifikasi_ekstraksi(hasil, len(soal_konteks)):
        return None
    return saring_ekstraksi(hasil, len(soal_konteks))


# ── Gerbang biaya (opsional) ───────────────────────────────────────────


def cek_saldo(minimal: float | None = None) -> bool:
    """Cek saldo DeepSeek terhadap ambang DEEPSEEK_SALDO_MIN (default 0).

    Mengembalikan False (= fitur dianggap nonaktif) kalau:
      - ambang > 0 tapi API key tidak ada,
      - saldo tak bisa dipastikan (network error, format tak dikenal),
      - saldo terkonfirmasi di bawah ambang.
    Ambang <= 0 / env kosong berarti gerbang biaya dimatikan -> True.
    """
    if minimal is None:
        mentah = os.environ.get(ENV_SALDO_MIN, "").strip()
        if not mentah:
            return True
        try:
            ambang = float(mentah)
        except ValueError:
            return False
    else:
        ambang = float(minimal)
    if ambang <= 0:
        return True
    if not aktif():
        return False

    cfg = konfigurasi()
    req = urllib.request.Request(
        cfg["base_url"] + "/user/balance",
        headers={"Authorization": f"Bearer {cfg['api_key']}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=BATAS_WAKTU_DETIK) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("is_available") is False:
            return False
        total = float(data["balance_infos"][0]["total_balance"])
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError,
            TypeError, AttributeError):
        return False
    return total >= ambang


# ── Pintu masuk utama (B2) ─────────────────────────────────────────────


def bungkus(
    kon: sqlite3.Connection, soal: Soal, putaran: int = 0
) -> str | None:
    """Kalimat soal versi cerita, atau None = pakai kalimat bawaan.

    Urutan keputusannya:
      1. tanpa API key -> None seketika, nol network call (gagal-diam);
      2. cache hit    -> kalimat tersimpan, nol network call;
      3. panggil API  -> verifikasi angka -> simpan cache -> kalimat;
      4. gagal di mana pun -> None.

    `putaran` memutar latar cerita (lihat pilih_latar): 0 = latar pertama,
    1 = latar berikutnya, dan seterusnya. Soal yang sama karena itu bisa
    punya beberapa cerita berbeda tanpa satu pun dibayar dua kali — tiap
    (soal, latar) punya entri cache sendiri.

    Cache hit sengaja TIDAK diverifikasi ulang: yang masuk cache sudah
    lolos verifikasi saat pertama disimpan. Itu aman HANYA karena kunci
    cache memuat template_id — lihat catatan di kunci_cache().
    """
    if not aktif():
        return None

    latar = pilih_latar(soal, putaran)
    hash_kunci = kunci_cache(
        soal.parameter, template_id=soal.template_id, latar=latar
    )
    baris = kon.execute(
        "SELECT kalimat FROM llm_cache WHERE kunci_hash = ?", (hash_kunci,)
    ).fetchone()
    if baris is not None:
        return str(baris[0])

    kalimat = _panggil(_buat_prompt(soal, latar))
    if kalimat is None or not verifikasi(kalimat, soal):
        return None

    kon.execute(
        """INSERT OR REPLACE INTO llm_cache (kunci_hash, kalimat, model)
           VALUES (?, ?, ?)""",
        (hash_kunci, kalimat, konfigurasi()["model"]),
    )
    return kalimat


# Berapa latar yang dicoba untuk satu soal sebelum menyerah ke kalimat
# bawaan. Verifikasi angka sengaja galak (menolak angka karangan, menolak
# angka soal yang hilang), dan sebagian latar memang sulit dipakai tanpa
# menambah angka — "lomba 17 Agustus" menggoda model menulis "17".
# Mencoba latar kedua jauh lebih murah daripada membiarkan soal kembali
# ke kalimat bawaan, dan tetap berbatas supaya biaya tidak lepas kendali.
PERCOBAAN_LATAR = 2


def _sesi_terkunci(kon: sqlite3.Connection, sesi_id: int) -> bool:
    """True bila snapshot sesi tidak boleh lagi berubah."""
    return kon.execute(
        """SELECT EXISTS (
               SELECT 1 FROM sesi se
               WHERE se.id = ?
                 AND (
                     se.penyajian_dibekukan IS NOT NULL
                     OR se.mulai IS NOT NULL OR se.selesai IS NOT NULL
                     OR se.dibatalkan IS NOT NULL
                     OR EXISTS (
                         SELECT 1 FROM sesi_soal ss
                         JOIN jawaban j ON j.sesi_soal_id = ss.id
                         WHERE ss.sesi_id = se.id
                     )
                     OR EXISTS (
                         SELECT 1 FROM konfirmasi_hasil kh
                         WHERE kh.sesi_id = se.id
                     )
                     OR EXISTS (
                         SELECT 1 FROM bukti_fokus bf
                         WHERE bf.sesi_id = se.id
                     )
                 )
           )""",
        (sesi_id,),
    ).fetchone()[0] == 1


def _snapshot_cerita(baris, kalimat: str):
    """Bangun cerita pada snapshot target, termasuk baris warisan all-NULL."""
    lama = question_views.penyajian_dari_baris(baris)
    parameter = json.loads(baris["parameter"])
    warisan = baris["fingerprint_penyajian"] is None
    return buat_penyajian(
        template_id=baris["template_id"],
        level=baris["level"],
        parameter=parameter,
        teks_soal=kalimat,
        bagian_soal=lama.bagian_soal,
        tantangan_soal=lama.tantangan_soal,
        minta_restatement=lama.minta_restatement,
        asal_teks="cerita",
        status_visual="warisan" if warisan else lama.status_visual,
        mode_representasi="teks-v1" if warisan else lama.mode_representasi,
        descriptor=None if warisan else lama.descriptor,
        penyajian_versi=lama.penyajian_versi,
        renderer_versi=lama.renderer_versi,
    )


def bungkus_sesi(kon, sesi_id: int, ambil_soal) -> tuple[int, int, str]:
    """Buat variasi cerita untuk seluruh soal satu sesi.

    Mengembalikan (berhasil, dicoba, catatan).

    `ambil_soal` adalah fungsi yang mengubah satu baris DB jadi objek Soal
    (web._soal_dari_baris) — disuntik dari luar supaya modul ini tetap
    tidak bergantung pada web.py, dan tetap bisa diuji tanpa HTTP.

    Soal yang SUDAH punya cerita dilewati: kalimatnya sudah dibayar, dan
    yang lebih penting anak mungkin sudah mengerjakannya. Mengganti kalimat
    di tengah jalan membuat guru menilai soal yang tidak dikerjakan anak.
    """
    if not aktif():
        return 0, 0, "Fitur cerita tidak aktif (kunci DeepSeek belum dipasang)."
    if _sesi_terkunci(kon, sesi_id):
        return 0, 0, "Variasi cerita ditolak karena sesi sudah terkunci."
    if not cek_saldo():
        return 0, 0, "Saldo DeepSeek di bawah ambang — permintaan ditahan."

    ensure_table(kon)
    pemilik_baris = kon.execute(
        """SELECT w.pemilik FROM sesi se JOIN siswa w ON w.id=se.siswa_id
           WHERE se.id=?""", (sesi_id,),
    ).fetchone()
    bucket_akun = pemilik_baris["pemilik"] if pemilik_baris else None
    target = kon.execute(
        """SELECT ss.id AS sesi_soal_id, ss.nomor,
                  ss.teks_soal, ss.bagian_soal, ss.tantangan_soal,
                  ss.minta_restatement, ss.penyajian_json,
                  ss.penyajian_versi, ss.renderer_versi, ss.asal_teks,
                  ss.status_visual, ss.mode_representasi,
                  ss.fingerprint_matematis, ss.fingerprint_penyajian,
                  s.id, s.template_id, s.parameter, s.kunci, s.level,
                  s.bagian, s.tantangan, s.cerita
           FROM soal s JOIN sesi_soal ss ON ss.soal_id = s.id
           WHERE ss.sesi_id = ? ORDER BY ss.nomor""",
        (sesi_id,),
    ).fetchall()
    hasil = []
    dicoba = 0
    dilewati_visual = 0
    for b in target:
        snapshot_selesai = (
            b["fingerprint_penyajian"] is not None
            and b["asal_teks"] == "cerita"
        )
        if snapshot_selesai:
            continue
        # Visual-esensial harus mempertahankan teks proyektor yang selaras
        # dengan descriptor; parafrase dapat memunculkan kembali data mentah.
        if b["status_visual"] == "siap":
            dilewati_visual += 1
            continue
        dicoba += 1
        soal_ini = ambil_soal(b)
        kalimat = None
        for putaran in range(PERCOBAAN_LATAR):
            with gunakan_bucket_akun(bucket_akun):
                kalimat = bungkus(kon, soal_ini, putaran)
            if kalimat:
                break
        if kalimat:
            hasil.append((b, _snapshot_cerita(b, kalimat)))

    if not hasil:
        tambahan = (
            f" {dilewati_visual} soal visual dilewati."
            if dilewati_visual
            else ""
        )
        if dicoba == 0:
            if dilewati_visual:
                return 0, 0, tambahan.strip()
            return 0, 0, "Semua soal sudah punya versi cerita."
        return 0, dicoba, (
            f"{dicoba} soal dicoba, tidak ada yang lolos verifikasi angka — "
            f"kalimat bawaan tetap dipakai.{tambahan}"
        )

    # Penulisan snapshot atomik per sesi, tetapi transaksi tetap milik pemanggil.
    kon.execute("SAVEPOINT bridge_cerita_sesi")
    try:
        for b, snapshot_baru in hasil:
            if not presentation_lock.perbarui_snapshot(
                kon,
                b["sesi_soal_id"],
                b["fingerprint_penyajian"],
                snapshot_baru,
            ):
                raise RuntimeError("snapshot berubah saat variasi cerita disimpan")
        kon.execute("RELEASE SAVEPOINT bridge_cerita_sesi")
    except (RuntimeError, sqlite3.IntegrityError):
        kon.execute("ROLLBACK TO SAVEPOINT bridge_cerita_sesi")
        kon.execute("RELEASE SAVEPOINT bridge_cerita_sesi")
        return 0, dicoba, "Variasi cerita gagal disimpan karena snapshot berubah."

    berhasil = len(hasil)
    catatan = f"{berhasil} dari {dicoba} soal dapat versi cerita."
    if dilewati_visual:
        catatan += f" {dilewati_visual} soal visual dilewati."
    return berhasil, dicoba, catatan
