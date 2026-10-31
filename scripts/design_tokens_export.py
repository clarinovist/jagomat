#!/usr/bin/env python3
"""Ekspor token desain Jagomat ke tokens.json (gaya DTCG) dan tokens.css untuk alat desain.

Sumber tetap mesin/design_tokens.py dan peta peran mesin/design_roles.py. Hasil
ekspor adalah salinan baca: jangan diedit manual, jangan di-commit; ekspor ulang
bila token berubah. Tanpa DB, jaringan, atau import aplikasi selain dua modul itu.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "mesin"))
import design_roles as R  # noqa: E402
import design_tokens as T  # noqa: E402

# Teks merek, bukan nilai CSS; dicatat di $extensions.
TEKS_MEREK = ("NAMA_PRODUK", "TAGLINE")
# Geometri SVG soal (satuan viewBox), bukan token UI — lihat docstring design_tokens.
AWALAN_GEOMETRI = ("POLA_", "STAT_", "GEO_", "RUANG_", "JAM_", "VENN_", "PETA_", "PETAK_",
                   "OBJEK_", "SLOT_", "TIM_", "SUSUNAN_", "FASE6_")
POLA_WARNA = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})")
POLA_DIMENSI = re.compile(r"-?\d*\.?\d+(?:px|rem|pt|%)")
POLA_DURASI = re.compile(r"\d*\.?\d+s")
POLA_ANGKA = re.compile(r"\d*\.?\d+")
# Ukuran ikon/info bukan skala tipografi meski bernama UKURAN_.
UKURAN_BUKAN_TIPE = ("UKURAN_INFO", "UKURAN_IKON")
# (awalan, grup) — dicek berurutan; yang pertama cocok menang.
GRUP_DIMENSI = (
    ("ANAK_BATAS_", "breakpoint"), ("BATAS_", "breakpoint"), ("MULAI_", "breakpoint"),
    ("SP_", "jarak"), ("RADIUS_", "radius"), ("LOGO_", "logo"),
)


def _grup_warna(nama: str) -> str:
    if nama.startswith("ANAK_"):
        return "profil"
    if nama.startswith("ADMIN_"):
        return "admin-gelap" if nama.endswith("_GELAP") else "admin-terang"
    if nama.startswith("KODE_"):
        return "kode-diagnosis"
    if nama.startswith(("CETAK_", "LEMBAR_")):
        return "cetak-lembar"
    return "dasar"


def _grup_dimensi(nama: str) -> str:
    if nama.startswith("UKURAN_") and nama not in UKURAN_BUKAN_TIPE:
        return "tipe"
    for awalan, grup in GRUP_DIMENSI:
        if nama.startswith(awalan):
            return grup
    return "tata-letak"


def _jenis(nama: str, nilai: str):
    """(kategori, grup, $type) atau None bila nilai tidak bisa diwakili satu token jujur."""
    if POLA_WARNA.fullmatch(nilai):
        return "warna", _grup_warna(nama), "color"
    if nama.startswith("FONT_"):
        return "font", "keluarga", "fontFamily"
    if POLA_DIMENSI.fullmatch(nilai):
        return "ukuran", _grup_dimensi(nama), "dimension"
    if POLA_DURASI.fullmatch(nilai):
        return "gerak", "durasi", "duration"
    if POLA_ANGKA.fullmatch(nilai):
        return "ukuran", "tipe", "number"
    return None


def kumpulkan():
    """Token string non-adapter, urut sesuai definisi di design_tokens.py."""
    return [(k, v) for k, v in vars(T).items()
            if k.isupper() and isinstance(v, str) and not v.startswith("var(")
            and k not in TEKS_MEREK and not k.startswith(AWALAN_GEOMETRI)]


def _sumber() -> str:
    berkas = ["mesin/design_tokens.py", "mesin/design_roles.py"]
    try:
        sha = subprocess.run(["git", "-C", str(AKAR), "rev-parse", "HEAD"], capture_output=True,
                             text=True, check=True, timeout=30).stdout.strip()
        kotor = subprocess.run(["git", "-C", str(AKAR), "status", "--porcelain", "--", *berkas],
                               capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "sumber Git tidak diketahui"
    return f"commit {sha}" + (" + perubahan token belum di-commit" if kotor else "")


def _peran(lokasi: dict) -> dict:
    peran = {}
    for permukaan in R.PERMUKAAN:
        peta = {}
        for nama_peran, token in R.peta_peran(permukaan).items():
            if token not in lokasi:
                raise ValueError(f"peran {permukaan}.{nama_peran} menunjuk token tak terekspor {token}")
            peta[nama_peran] = {"$type": "color", "$value": "{" + lokasi[token] + "}"}
        peran[permukaan] = peta
    return peran


def bangun_json() -> dict:
    data, lokasi, hanya_css = {}, {}, []
    for nama, nilai in kumpulkan():
        jenis = _jenis(nama, nilai)
        if jenis is None:
            hanya_css.append(nama)
            continue
        kategori, grup, tipe = jenis
        data.setdefault(kategori, {}).setdefault(grup, {})[nama] = {"$type": tipe, "$value": nilai}
        lokasi[nama] = f"{kategori}.{grup}.{nama}"
    data["peran"] = _peran(lokasi)
    data["$description"] = ("Token desain Jagomat, diekspor dari mesin/design_tokens.py. "
                            "Salinan baca: ubah sumbernya, lalu ekspor ulang.")
    data["$extensions"] = {"jagomat": {
        "nama_produk": T.NAMA_PRODUK, "tagline": T.TAGLINE, "sumber": _sumber(),
        "hanya_css": hanya_css,
        "catatan": ("Token di hanya_css (clamp, bayangan) tersedia utuh di tokens.css. "
                    "Peran = token yang dipakai aturan CSS nyata per permukaan (design_roles.py)."),
    }}
    return data


def bangun_css() -> str:
    baris = [f"  --{nama.lower().replace('_', '-')}: {nilai};" for nama, nilai in kumpulkan()]
    return (f"/* Token desain Jagomat — diekspor dari mesin/design_tokens.py ({_sumber()}).\n"
            "   Salinan baca: ubah sumbernya, lalu ekspor ulang. */\n"
            ":root {\n" + "\n".join(baris) + "\n}\n")


def ekspor(tujuan: Path):
    tujuan.mkdir(parents=True, exist_ok=False)
    json_path, css_path = tujuan / "tokens.json", tujuan / "tokens.css"
    json_path.write_text(json.dumps(bangun_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    css_path.write_text(bangun_css(), encoding="utf-8")
    return json_path, css_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="folder baru untuk tokens.json dan tokens.css")
    for berkas in ekspor(parser.parse_args().output):
        print(berkas.resolve())


if __name__ == "__main__":
    main()
