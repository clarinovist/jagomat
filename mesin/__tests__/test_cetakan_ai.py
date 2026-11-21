"""Klien AI draf cetakan (`cetakan_ai`): muatan privat, batas ukuran/waktu, galat ramah, parser, terpisah dari llm.

Tanpa jaringan nyata: `cetakan_ai.urllib.request.urlopen` dipalsukan. Kunci API sintetis.
"""
from __future__ import annotations

import ast
import http.client
import inspect
import json
import logging
import socket
import sys
from pathlib import Path
import urllib.error

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cetakan_ai  # noqa: E402
import cetakan_pola as pola  # noqa: E402
import kurikulum_kelas_hitung as hitung  # noqa: E402
from cetakan_ai_kit import (  # noqa: E402
    BAB, KELAS, KUNCI_SINTETIS, MESIN, badan_chat, impor_berkas, isi_balasan, kandidat_sah,
    modul_mesin_terimpor, pasang_api, siapkan_env,
)

BAB_UJI = hitung.cari_bab(KELAS, BAB)[1]
ALAMAT = "https://api.deepseek.com/chat/completions"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    siapkan_env(monkeypatch)


def _badan_dengan_panjang(n: int) -> bytes:
    """Badan balasan sah JSON berukuran PERSIS n byte (isi berupa padding ASCII di dalam content)."""
    dasar = len(isi_balasan([kandidat_sah()], tambahan={"p": ""}))
    isi = isi_balasan([kandidat_sah()], tambahan={"p": "x" * (n - dasar)})
    assert len(isi) == n
    return isi


# --- konfigurasi ---------------------------------------------------------------------------

def test_konfigurasi_bawaan_dan_env_dibaca_saat_dipanggil(monkeypatch):
    assert cetakan_ai.konfigurasi() == {
        "base_url": "https://api.deepseek.com", "api_key": KUNCI_SINTETIS, "model": cetakan_ai.MODEL_BAWAAN}
    monkeypatch.setenv(cetakan_ai.ENV_BASE_URL, "https://contoh.invalid/")
    monkeypatch.setenv(cetakan_ai.ENV_MODEL, "model-uji")
    monkeypatch.setenv(cetakan_ai.ENV_API_KEY, "  kunci-lain  ")
    assert cetakan_ai.konfigurasi() == {"base_url": "https://contoh.invalid", "api_key": "kunci-lain", "model": "model-uji"}


def test_nilai_bawaan_sama_dengan_llm_agar_tidak_menyimpang():
    import llm
    assert cetakan_ai.BASE_URL_BAWAAN == llm.BASE_URL_BAWAAN and cetakan_ai.MODEL_BAWAAN == llm.MODEL_BAWAAN
    assert (cetakan_ai.ENV_API_KEY, cetakan_ai.ENV_BASE_URL, cetakan_ai.ENV_MODEL) == (
        llm.ENV_API_KEY, llm.ENV_BASE_URL, llm.ENV_MODEL)


@pytest.mark.parametrize("kunci,hasil", [("", False), ("   ", False), (KUNCI_SINTETIS, True)])
def test_aktif_hanya_bila_kunci_ada(monkeypatch, kunci, hasil):
    monkeypatch.setenv(cetakan_ai.ENV_API_KEY, kunci)
    assert cetakan_ai.aktif() is hasil


def test_aktif_tanpa_env_sama_sekali_false(monkeypatch):
    monkeypatch.delenv(cetakan_ai.ENV_API_KEY)
    assert cetakan_ai.aktif() is False


# --- muatan privat -------------------------------------------------------------------------

def test_muatan_hanya_menerima_kelas_dan_bab():
    assert list(inspect.signature(cetakan_ai.muatan).parameters) == ["kelas", "bab"]
    assert list(inspect.signature(cetakan_ai.pesan_pengguna).parameters) == ["kelas", "bab"]


def test_muatan_dua_pesan_dengan_struktur_dan_isi_yang_diharapkan():
    pesan = cetakan_ai.muatan(KELAS, BAB_UJI)
    assert [p["role"] for p in pesan] == ["system", "user"] and all(set(p) == {"role", "content"} for p in pesan)
    pengguna = pesan[1]["content"]
    sub = "\n".join("- %s" % s for s in BAB_UJI.sub_materi)
    assert pengguna.startswith("Kelas: %d\nBab %d: %s\nSub-materi bab:\n%s\n\n" % (KELAS, BAB, BAB_UJI.judul, sub))
    contoh = json.loads(pengguna.rsplit("\n", 1)[1])
    assert contoh["kelas"] == KELAS and contoh["bab"] == BAB
    pola.validasi(contoh)  # contoh format di muatan sendiri adalah cetakan sah


def test_muatan_memuat_aturan_dari_konstanta_pola_dan_kata_json():
    sistem = cetakan_ai.muatan(KELAS, BAB_UJI)[0]["content"]
    assert "JSON" in sistem
    for angka in (pola.MAKS_VARIABEL, pola.BATAS_KONSTANTA, pola.MAKS_SYARAT, pola.MAKS_TEKS, pola.MAKS_PEMBAHASAN,
                  pola.MAKS_JUDUL, pola.MAKS_EKSPRESI, pola.MIN_UNIK):
        assert str(angka) in sistem
    for kata in ("+ - * // %", "a % b == 0", "{nama}", "{kunci}", "bilangan bulat >= 0", "{\"cetakan\": [ ... ]}"):
        assert kata in sistem


def test_muatan_murni_deterministik_dan_tak_dipengaruhi_env(monkeypatch):
    awal = cetakan_ai.muatan(KELAS, BAB_UJI)
    monkeypatch.setenv("USER", "admin-rahasia")
    monkeypatch.setenv(cetakan_ai.ENV_API_KEY, "kunci-lain")
    assert cetakan_ai.muatan(KELAS, BAB_UJI) == awal


def test_muatan_tak_memuat_kata_akun_sesi_atau_anak_dan_kunci_api():
    teks = json.dumps(cetakan_ai.muatan(KELAS, BAB_UJI), ensure_ascii=False).lower()
    for kata in ("actor", "akun_", "email", "cookie", "sesi", "csrf", "password", "sandi", KUNCI_SINTETIS):
        assert kata not in teks


def test_sistem_hanya_memakai_nama_sintetis_bukan_nama_anak():
    sistem = cetakan_ai.muatan(KELAS, BAB_UJI)[0]["content"]
    assert not any(nama in sistem for nama in pola.NAMA_SINTETIS)  # nama diisi mesin, tak dikirim


# --- permintaan ----------------------------------------------------------------------------

def test_permintaan_post_ke_chat_completions_dengan_header_badan_dan_timeout(monkeypatch):
    api = pasang_api(monkeypatch)
    cetakan_ai.minta_kandidat(KELAS, BAB_UJI)
    req, timeout = api.panggilan[0]
    assert len(api.panggilan) == 1 and req.full_url == ALAMAT and req.get_method() == "POST"
    assert timeout == 30 == cetakan_ai.BATAS_WAKTU_DETIK
    assert req.get_header("Authorization") == "Bearer " + KUNCI_SINTETIS
    assert req.get_header("Content-type") == "application/json"
    badan = api.badan()
    assert set(badan) == {"model", "messages", "temperature", "max_tokens", "response_format", "thinking"}
    assert badan["thinking"] == {"type": "disabled"}
    assert badan["model"] == cetakan_ai.MODEL_BAWAAN and badan["response_format"] == {"type": "json_object"}
    assert badan["messages"] == cetakan_ai.muatan(KELAS, BAB_UJI)
    assert 0 <= badan["temperature"] <= 0.5 and 0 < badan["max_tokens"] <= 2000
    assert KUNCI_SINTETIS not in req.data.decode("utf-8")


def test_alamat_dan_model_dari_env_dipakai(monkeypatch):
    monkeypatch.setenv(cetakan_ai.ENV_BASE_URL, "https://contoh.invalid/v1/")
    monkeypatch.setenv(cetakan_ai.ENV_MODEL, "model-uji")
    api = pasang_api(monkeypatch)
    cetakan_ai.minta_kandidat(KELAS, BAB_UJI)
    assert api.panggilan[0][0].full_url == "https://contoh.invalid/v1/chat/completions"
    assert api.badan()["model"] == "model-uji"


def test_tanpa_kunci_galat_tanpa_memanggil_jaringan(monkeypatch):
    siapkan_env(monkeypatch, kunci="")
    api = pasang_api(monkeypatch)
    with pytest.raises(cetakan_ai.GalatAI):
        cetakan_ai.minta_kandidat(KELAS, BAB_UJI)
    assert api.panggilan == []


@pytest.mark.parametrize("alamat", ["file:///etc/passwd", "ftp://contoh.invalid", "contoh-tanpa-skema", "javascript:1"])
def test_alamat_bukan_http_ditolak_tanpa_memanggil_jaringan(monkeypatch, alamat):
    monkeypatch.setenv(cetakan_ai.ENV_BASE_URL, alamat)
    api = pasang_api(monkeypatch)
    with pytest.raises(cetakan_ai.GalatAI, match="Alamat layanan AI"):
        cetakan_ai.minta_kandidat(KELAS, BAB_UJI)
    assert api.panggilan == []


# --- batas ukuran balasan ------------------------------------------------------------------

def test_balasan_8192_byte_diterima_dan_8193_ditolak(monkeypatch):
    pasang_api(monkeypatch, respons=_badan_dengan_panjang(8192))
    assert len(cetakan_ai.minta_kandidat(KELAS, BAB_UJI)) == 1
    pasang_api(monkeypatch, respons=_badan_dengan_panjang(8193))
    with pytest.raises(cetakan_ai.GalatAI, match="terlalu panjang"):
        cetakan_ai.minta_kandidat(KELAS, BAB_UJI)


def test_pembacaan_dibatasi_8193_byte_walau_balasan_sangat_besar(monkeypatch):
    api = pasang_api(monkeypatch, respons=b"x" * 2_000_000)
    with pytest.raises(cetakan_ai.GalatAI, match="terlalu panjang"):
        cetakan_ai.minta_kandidat(KELAS, BAB_UJI)
    assert api.respons_terakhir.permintaan_baca == [cetakan_ai.BATAS_RESPONS_BYTE + 1] == [8193]


# --- galat jaringan -> GalatAI ramah -------------------------------------------------------

GALAT_JARINGAN = [
    urllib.error.HTTPError(ALAMAT, 500, "Server Error", {}, None),
    urllib.error.HTTPError(ALAMAT, 401, "Unauthorized", {}, None),
    urllib.error.URLError("koneksi ditolak"),
    socket.timeout("habis waktu"),
    TimeoutError("habis waktu"),
    ConnectionResetError("putus"),
    http.client.IncompleteRead(b"x"),
    http.client.BadStatusLine("bukan http"),
    OSError("disk"),
    ValueError("url aneh"),
]


@pytest.mark.parametrize("galat", GALAT_JARINGAN, ids=lambda g: type(g).__name__ + str(getattr(g, "code", "")))
def test_galat_jaringan_menjadi_galat_ai_tanpa_rahasia(monkeypatch, caplog, galat):
    pasang_api(monkeypatch, galat=galat)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(cetakan_ai.GalatAI) as info:
            cetakan_ai.minta_kandidat(KELAS, BAB_UJI)
    pesan = str(info.value)
    assert pesan and KUNCI_SINTETIS not in pesan and "deepseek" not in pesan and "http" not in pesan.lower()
    assert KUNCI_SINTETIS not in caplog.text and "Bearer" not in caplog.text and "/chat/completions" not in caplog.text


def test_pesan_galat_http_memuat_kode_saja(monkeypatch):
    pasang_api(monkeypatch, galat=urllib.error.HTTPError(ALAMAT, 429, "Too Many", {}, None))
    with pytest.raises(cetakan_ai.GalatAI, match="kode 429"):
        cetakan_ai.minta_kandidat(KELAS, BAB_UJI)


# --- parser balasan ------------------------------------------------------------------------

BALASAN_RUSAK = {
    "bukan-json": b"<html>gateway</html>",
    "bukan-utf8": b"\xff\xfe\xfa",
    "json-bukan-objek": b"[1, 2]",
    "tanpa-choices": b"{}",
    "choices-kosong": b'{"choices": []}',
    "choices-bukan-daftar": b'{"choices": "x"}',
    "message-hilang": b'{"choices": [{}]}',
    "message-bukan-objek": b'{"choices": [{"message": "x"}]}',
    "content-hilang": b'{"choices": [{"message": {"role": "assistant"}}]}',
    "content-null": b'{"choices": [{"message": {"content": null}}]}',
    "content-angka": b'{"choices": [{"message": {"content": 5}}]}',
    "content-daftar": b'{"choices": [{"message": {"content": ["a"]}}]}',
    "content-bukan-json": badan_chat("Ini bukan JSON"),
    "content-kosong": badan_chat(""),
    "content-daftar-json": badan_chat("[1, 2]"),
    "content-angka-json": badan_chat("5"),
    "tanpa-kunci-cetakan": badan_chat('{"lain": []}'),
    "cetakan-kosong": badan_chat('{"cetakan": []}'),
    "cetakan-bukan-daftar": badan_chat('{"cetakan": "x"}'),
    "cetakan-objek": badan_chat('{"cetakan": {"judul": "x"}}'),
    "bersarang-dalam": badan_chat("[" * 100_000),
}


@pytest.mark.parametrize("nama", sorted(BALASAN_RUSAK))
def test_balasan_rusak_menjadi_galat_ai_bukan_galat_lain(monkeypatch, nama):
    pasang_api(monkeypatch, respons=BALASAN_RUSAK[nama])
    with pytest.raises(cetakan_ai.GalatAI):
        cetakan_ai.minta_kandidat(KELAS, BAB_UJI)


def test_satu_sampai_tiga_kandidat_diterima_apa_adanya(monkeypatch):
    for jumlah in (1, 2, 3):
        daftar = [kandidat_sah(judul="Judul %d" % i) for i in range(jumlah)]
        pasang_api(monkeypatch, respons=isi_balasan(daftar))
        assert cetakan_ai.minta_kandidat(KELAS, BAB_UJI) == tuple(daftar)


def test_lebih_dari_tiga_kandidat_diambil_tiga_pertama(monkeypatch):
    daftar = [kandidat_sah(judul="Judul %d" % i) for i in range(5)]
    pasang_api(monkeypatch, respons=isi_balasan(daftar))
    hasil = cetakan_ai.minta_kandidat(KELAS, BAB_UJI)
    assert hasil == tuple(daftar[:3]) and len(hasil) == cetakan_ai.MAKS_KANDIDAT == 3


def test_kandidat_tak_divalidasi_di_klien_item_aneh_diteruskan(monkeypatch):
    pasang_api(monkeypatch, respons=isi_balasan(["teks", 5, None, {"kunci": "__import__('os')"}]))
    assert cetakan_ai.minta_kandidat(KELAS, BAB_UJI) == ("teks", 5, None)


# --- terpisah dari fitur AI lama -----------------------------------------------------------

def test_klien_tidak_menarik_llm_ai_service_atau_ai_store():
    tertarik = modul_mesin_terimpor("import cetakan_ai")
    assert tertarik == {"cetakan_ai", "cetakan_pola", "kurikulum_kelas"}


def test_klien_hanya_mengimpor_stdlib_dan_modul_data():
    assert impor_berkas("cetakan_ai.py") == {
        "__future__", "http.client", "json", "logging", "os", "typing", "urllib.error", "urllib.request",
        "cetakan_pola", "kurikulum_kelas"}


BERKAS_C3 = ["cetakan_ai.py", "cetakan_ai_store.py", "admin_kurikulum_cetakan_ai_http.py",
             "admin_kurikulum_cetakan_ai_pages.py"]


@pytest.mark.parametrize("berkas", BERKAS_C3)
def test_jalur_cetakan_ai_tak_mengimpor_atau_mengecek_sakelar_ai_lama(berkas):
    assert not impor_berkas(berkas) & {"ai_service", "ai_store", "ai_policy", "llm"}
    pohon = ast.parse((MESIN / berkas).read_text(encoding="utf-8"))
    kode = [n for n in ast.walk(pohon) if isinstance(n, (ast.Name, ast.Attribute, ast.Constant))]
    docstring = ast.get_docstring(pohon, clean=False)
    for node in kode:
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value != docstring:
            assert "AI_NONAKTIF" not in node.value and "dihentikan" not in node.value
        elif isinstance(node, ast.Name):
            assert node.id not in {"ai_service", "ai_store", "ai_policy", "llm", "AI_NONAKTIF"}
