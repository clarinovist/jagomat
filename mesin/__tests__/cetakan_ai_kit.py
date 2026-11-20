"""Pembantu tes draf AI cetakan (C3): urlopen palsu, balasan chat sintetis, kandidat sah, kirim POST draf AI.

Semua data SINTETIS, tanpa jaringan nyata. Kunci API selalu `KUNCI_SINTETIS`. Dipakai tes klien, kuota, dan HTTP.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cetakan_ai  # noqa: E402

MESIN = Path(__file__).resolve().parent.parent
KUNCI_SINTETIS = "sk-uji-sintetis"
KELAS, BAB = 3, 1  # bab sah di kurikulum; dipakai sebagai target bawaan


def kandidat_sah(**ganti) -> dict:
    """Satu kandidat cetakan sah (kelas/bab sengaja kelas 2 bab 2: pemanggil memaksa nilai dari tinjauan)."""
    isi = {
        "kelas": 2, "bab": 2, "judul": "Penjumlahan dua angka dalam soal cerita",
        "teks": "{nama} punya {a} kelereng. Ia diberi {b} kelereng lagi. Berapa kelereng {nama} sekarang?",
        "variabel": {"a": [10, 50], "b": [1, 40]}, "nama": True, "syarat": ["a + b <= 99"],
        "kunci": "a + b", "pembahasan": "{a} + {b} = {kunci}",
    }
    isi.update(ganti)
    return isi


def kandidat_tak_layak(**ganti) -> dict:
    """Sah secara bentuk tetapi hanya 25 kombinasi (< 30 unik): gagal uji kelayakan."""
    return kandidat_sah(variabel={"a": [1, 5], "b": [1, 5]}, syarat=[], **ganti)


def isi_balasan(kandidat, *, tambahan: dict = None) -> bytes:
    """Badan balasan /chat/completions yang content-nya `{"cetakan": kandidat}` (+ kunci tambahan)."""
    content = json.dumps({"cetakan": list(kandidat), **(tambahan or {})})
    return badan_chat(content)


def badan_chat(content) -> bytes:
    return json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode("utf-8")


class ResponsPalsu:
    """Pengganti hasil urlopen: context manager + `read(n)` yang menghormati batas n; mencatat n."""

    def __init__(self, byte: bytes):
        self._byte = byte
        self.permintaan_baca = []

    def read(self, n=None):
        self.permintaan_baca.append(n)
        return self._byte if n is None else self._byte[:n]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ApiPalsu:
    """urlopen palsu: mencatat (request, timeout) tiap panggilan; mengembalikan `respons` atau melempar `galat`."""

    def __init__(self, respons: bytes = None, galat: BaseException = None):
        self.respons = respons if respons is not None else isi_balasan([kandidat_sah()])
        self.galat = galat
        self.panggilan = []
        self.respons_terakhir = None

    def __call__(self, req, timeout=None, **kwargs):
        self.panggilan.append((req, timeout))
        if self.galat is not None:
            raise self.galat
        self.respons_terakhir = ResponsPalsu(self.respons)
        return self.respons_terakhir

    def badan(self, indeks: int = 0) -> dict:
        return json.loads(self.panggilan[indeks][0].data.decode("utf-8"))


def pasang_api(monkeypatch, respons: bytes = None, galat: BaseException = None) -> ApiPalsu:
    api = ApiPalsu(respons, galat)
    monkeypatch.setattr(cetakan_ai.urllib.request, "urlopen", api, raising=True)
    return api


def siapkan_env(monkeypatch, *, kunci: str = KUNCI_SINTETIS) -> None:
    """Kunci sintetis terpasang (atau dicabut bila kosong); alamat dan model kembali ke bawaan."""
    monkeypatch.delenv(cetakan_ai.ENV_BASE_URL, raising=False)
    monkeypatch.delenv(cetakan_ai.ENV_MODEL, raising=False)
    if kunci:
        monkeypatch.setenv(cetakan_ai.ENV_API_KEY, kunci)
    else:
        monkeypatch.delenv(cetakan_ai.ENV_API_KEY, raising=False)


def modul_mesin_terimpor(impor: str) -> set:
    """Modul mesin yang ikut termuat setelah menjalankan `impor` di interpreter bersih."""
    kode = (
        "import sys; sys.path.insert(0, %r); %s; "
        "print(sorted(n for n, m in sys.modules.items() "
        "if getattr(m, '__file__', None) and m.__file__.startswith(%r)))"
        % (str(MESIN), impor, str(MESIN) + "/"))
    keluar = subprocess.run([sys.executable, "-c", kode], capture_output=True, text=True, check=True).stdout
    return set(ast.literal_eval(keluar.strip()))


def impor_berkas(nama: str) -> set:
    """Nama modul tingkat atas yang diimpor berkas mesin `nama` (AST, hanya import tingkat modul)."""
    pohon = ast.parse((MESIN / nama).read_text(encoding="utf-8"))
    modul = set()
    for node in pohon.body:
        if isinstance(node, ast.Import):
            modul.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modul.add(node.module)
    return modul
