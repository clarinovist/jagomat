"""Kontrak opsi publik immutable; pembaca tidak membutuhkan kunci atau diagnosis.

Snapshot mengikat opsi ke butir dan penyajian tertentu. Sidik adalah pemeriksaan
integritas/replay, bukan tanda tangan otorisasi; kepemilikan diperiksa oleh store.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

JUMLAH_OPSI = {"tiga-v1": 3, "empat-v1": 4, "tertanam-lima-v1": 5}
BATAS_JSON = 32_000
_SIDIK = re.compile(r"[0-9a-f]{64}")


def _teks(nilai: str, batas: int) -> bool:
    return (isinstance(nilai, str) and 0 < len(nilai) <= batas
            and nilai == nilai.strip()
            and not any(ord(c) < 32 and c != "\n" or ord(c) == 127 for c in nilai))


@dataclass(frozen=True)
class OpsiJawaban:
    """Identitas netral dan teks biasa; bukan HTML atau penanda jawaban benar."""

    id: str
    label: str
    nilai: str
    teks: str


@dataclass(frozen=True)
class PilihanButir:
    """Snapshot publik lengkap yang jumlahnya ditentukan kebijakan server."""

    sesi_soal_id: int
    fingerprint_pertanyaan: str
    kebijakan: str
    opsi: tuple[OpsiJawaban, ...]
    versi: int = 1

    def __post_init__(self):
        if type(self.versi) is not int or self.versi != 1:
            raise ValueError("Versi pilihan tidak didukung.")
        if type(self.sesi_soal_id) is not int or self.sesi_soal_id <= 0:
            raise ValueError("Identitas butir pilihan tidak sah.")
        if not isinstance(self.fingerprint_pertanyaan, str) or not _SIDIK.fullmatch(self.fingerprint_pertanyaan):
            raise ValueError("Sidik pertanyaan tidak sah.")
        if not isinstance(self.kebijakan, str) or self.kebijakan not in JUMLAH_OPSI:
            raise ValueError("Kebijakan pilihan tidak dikenal.")
        if type(self.opsi) is not tuple or len(self.opsi) != JUMLAH_OPSI[self.kebijakan]:
            raise ValueError("Jumlah opsi tidak sesuai kebijakan.")
        for i, opsi in enumerate(self.opsi):
            if type(opsi) is not OpsiJawaban:
                raise ValueError("Struktur opsi tidak sah.")
            if opsi.id != f"opsi_{i + 1}" or opsi.label != "ABCDE"[i]:
                raise ValueError("Identitas atau urutan opsi tidak sah.")
            if not _teks(opsi.nilai, 1000) or not _teks(opsi.teks, 4000):
                raise ValueError("Nilai atau teks opsi tidak sah.")
        if len({o.nilai for o in self.opsi}) != len(self.opsi):
            raise ValueError("Nilai opsi duplikat.")
        if len({o.teks for o in self.opsi}) != len(self.opsi):
            raise ValueError("Teks opsi duplikat.")
        if self.kebijakan == "tertanam-lima-v1" and tuple(o.nilai for o in self.opsi) != tuple("ABCDE"):
            raise ValueError("Opsi tertanam wajib mempertahankan label asal.")

    def nilai_untuk(self, pilihan_id: str) -> str:
        """Kosong eksplisit menghapus pilihan; ID asing tidak menjadi jawaban."""
        if pilihan_id == "":
            return ""
        for opsi in self.opsi:
            if opsi.id == pilihan_id:
                return opsi.nilai
        raise ValueError("Pilihan bukan milik butir ini.")


def serialisasi(pilihan: PilihanButir) -> str:
    """Serialisasi daftar putih, tanpa mengambil atribut tambahan objek."""
    isi = {
        "versi": pilihan.versi,
        "sesi_soal_id": pilihan.sesi_soal_id,
        "fingerprint_pertanyaan": pilihan.fingerprint_pertanyaan,
        "kebijakan": pilihan.kebijakan,
        "opsi": [{"id": o.id, "label": o.label, "nilai": o.nilai, "teks": o.teks}
                 for o in pilihan.opsi],
    }
    return json.dumps(isi, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(pilihan: PilihanButir) -> str:
    """Sidik hanya atas snapshot publik, tidak memuat kebenaran jawaban."""
    return hashlib.sha256(serialisasi(pilihan).encode("utf-8")).hexdigest()


def _objek(pasangan):
    hasil = {}
    for nama, nilai in pasangan:
        if nama in hasil:
            raise ValueError("Field pilihan duplikat.")
        hasil[nama] = nilai
    return hasil


def _konstanta(_nilai):
    raise ValueError("Konstanta JSON pilihan tidak sah.")


def deserialisasi(teks: str, sidik: str, *, sesi_soal_id: int,
                  fingerprint_pertanyaan: str) -> PilihanButir:
    """Baca versi ketat dan tolak snapshot salah butir, berubah, atau parsial."""
    if not isinstance(teks, str) or len(teks) > BATAS_JSON:
        raise ValueError("Snapshot pilihan terlalu besar atau tidak sah.")
    if not isinstance(sidik, str) or not _SIDIK.fullmatch(sidik):
        raise ValueError("Sidik pilihan tidak sah.")
    try:
        data = json.loads(teks, object_pairs_hook=_objek, parse_constant=_konstanta)
    except (ValueError, RecursionError) as galat:
        raise ValueError("JSON pilihan tidak sah.") from galat
    kolom = {"versi", "sesi_soal_id", "fingerprint_pertanyaan", "kebijakan", "opsi"}
    if type(data) is not dict or set(data) != kolom or type(data["opsi"]) is not list:
        raise ValueError("Field snapshot pilihan tidak sah.")
    opsi = []
    for item in data["opsi"]:
        if type(item) is not dict or set(item) != {"id", "label", "nilai", "teks"}:
            raise ValueError("Field opsi tidak sah.")
        opsi.append(OpsiJawaban(**item))
    pilihan = PilihanButir(data["sesi_soal_id"], data["fingerprint_pertanyaan"],
                          data["kebijakan"], tuple(opsi), data["versi"])
    if (type(sesi_soal_id) is not int or pilihan.sesi_soal_id != sesi_soal_id
            or pilihan.fingerprint_pertanyaan != fingerprint_pertanyaan):
        raise ValueError("Snapshot pilihan tidak cocok dengan pertanyaan.")
    if serialisasi(pilihan) != teks or fingerprint(pilihan) != sidik:
        raise ValueError("Snapshot pilihan berubah atau tidak kanonis.")
    return pilihan
