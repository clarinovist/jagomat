#!/usr/bin/env python3
"""Paket tantangan cetak mandiri, tanpa Soal/registry/akun/DB atau provider runtime."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import html
import json
from pathlib import Path

VERSI = "tantangan-kelas5-2026-10-v1"


@dataclass(frozen=True)
class Tantangan:
    id: str
    judul: str
    teks: str
    jawaban: str
    langkah: tuple[str, ...]


PAKET = (
    Tantangan("kpk-ketiga", "Lampu bersama lagi",
        "Lampu merah berkedip setiap 6 menit dan lampu biru setiap 8 menit. Keduanya berkedip bersamaan pukul 08.00. "
        "Pukul berapa keduanya berkedip bersamaan untuk ketiga kalinya SETELAH pukul 08.00? Kejadian pukul 08.00 tidak dihitung.",
        "09.12", ("KPK dari 6 dan 8 adalah 24: kedua lampu berkedip bersama setiap 24 menit.",
                   "Kejadian ketiga setelah awal terjadi 3 × 24 = 72 menit kemudian. Pukul 08.00 + 1 jam 12 menit = 09.12.")),
    Tantangan("kpk-rentang", "Keberangkatan bersama",
        "Bus A berangkat setiap 12 menit dan bus B setiap 18 menit. Keduanya berangkat bersamaan pukul 09.00. "
        "Berapa kali keduanya berangkat bersamaan setelah pukul 09.00 sampai pukul 12.00? Jangan hitung keberangkatan pukul 09.00; hitung pukul 12.00 jika keduanya berangkat bersama.",
        "5 kali", ("KPK dari 12 dan 18 adalah 36 menit. Dari 09.00 sampai 12.00 ada 180 menit.",
                   "Waktu bersama: 09.36, 10.12, 10.48, 11.24, dan 12.00. Ada 180 ÷ 36 = 5 kejadian setelah awal.")),
    Tantangan("kpk-durasi", "Mulai setelah alarm",
        "Alarm A berbunyi setiap 8 menit dan alarm B setiap 12 menit. Keduanya berbunyi bersama pukul 10.00. "
        "Sebuah kegiatan dimulai saat kedua alarm pertama kali berbunyi bersama lagi setelah 10.00. Kegiatan berlangsung 35 menit. Pukul berapa kegiatan selesai?",
        "10.59", ("KPK dari 8 dan 12 adalah 24. Kegiatan mulai pukul 10.24.",
                   "Tambahkan 35 menit: 24 + 35 = 59. Jadi kegiatan selesai pukul 10.59.")),
    Tantangan("cacah-larangan", "Kartu dan amplop",
        "Ada 4 motif kartu: bunga, daun, bintang, dan bulan. Ada 3 warna amplop: merah, biru, dan putih. "
        "Satu paket berisi satu motif kartu dan satu warna amplop. Semua pasangan boleh dipilih, kecuali kartu bunga atau daun tidak boleh memakai amplop merah. Berapa banyak paket berbeda yang boleh dibuat?",
        "10 paket", ("Tanpa larangan, banyak paket = 4 × 3 = 12.",
                      "Dua pasangan dilarang: bunga–merah dan daun–merah. Jadi 12 − 2 = 10 paket.")),
    Tantangan("cacah-peserta", "Dua peserta datang",
        "Enam orang sudah berjabat tangan dengan setiap orang lain dalam kelompok itu, tepat sekali untuk tiap pasangan. "
        "Kemudian 2 orang baru datang. Setiap orang baru berjabat tangan dengan keenam orang lama, dan kedua orang baru juga saling berjabat tangan sekali. "
        "Orang lama tidak mengulang jabat tangan mereka. Berapa jabat tangan TAMBAHAN yang terjadi?",
        "13 jabat tangan", ("Setiap orang baru berjabat tangan dengan 6 orang lama: 2 × 6 = 12 jabat tangan.",
                            "Kedua orang baru saling berjabat tangan sekali. Tambahannya 12 + 1 = 13, bukan seluruh jabat tangan sejak awal.")),
    Tantangan("cacah-jalur", "Satu jalan ditutup",
        "Dari A ke B tersedia 3 jalan berbeda, dari B ke C tersedia 4 jalan berbeda, dan dari C ke D tersedia 2 jalan berbeda. "
        "Perjalanan selalu mengikuti A → B → C → D, memilih satu jalan pada setiap tahap. Semua gabungan pilihan dapat dilalui. "
        "Jika tepat satu jalan B ke C ditutup, berapa banyak rute A ke D yang masih dapat dilalui?",
        "18 rute", ("Setelah penutupan, pilihan B ke C tersisa 4 − 1 = 3 jalan.",
                    "Banyak rute = 3 × 3 × 2 = 18. Bisa juga 24 rute semula dikurangi 6 rute yang memakai jalan tertutup.")),
)

GAYA = """
@page { size: A4; margin: 16mm; }
* { box-sizing: border-box; }
body { font: 16px/1.55 Georgia, serif; color: black; background: white; max-width: 180mm; margin: 24px auto; padding: 0 16px; }
h1 { font-size: 26px; line-height: 1.2; } h2 { font-size: 20px; }
header { border-bottom: 2px solid; padding-bottom: 12px; }
article { break-inside: avoid; page-break-inside: avoid; padding: 14px 0; }
.meta { font: 13px/1.4 sans-serif; } .ruang { border: 1px solid; min-height: 50mm; margin-top: 10px; padding: 8px; }
@media print { body { margin: 0; padding: 0; max-width: none; } .lembar { break-after: page; } .lembar:last-child { break-after: auto; } }
"""


def render(solusi=False):
    """Dua dokumen berbeda; HTML soal tidak menyembunyikan solusi di markup."""
    judul = "Panduan solusi — untuk pendamping" if solusi else "Enam tantangan — KPK & pencacahan"
    halaman = []
    for awal in range(0, len(PAKET), 2):
        kartu = []
        for i, s in enumerate(PAKET[awal:awal + 2], awal + 1):
            isi = '<p>' + html.escape(s.teks) + '</p>'
            if solusi:
                isi += '<p><strong>Jawaban: ' + html.escape(s.jawaban) + '</strong></p><ol>'
                isi += ''.join('<li>' + html.escape(l) + '</li>' for l in s.langkah) + '</ol>'
            else:
                isi += '<div class="ruang">Tuliskan langkah dan alasanmu:</div>'
            kartu.append('<article><h2>' + str(i) + '. ' + html.escape(s.judul) + '</h2>' + isi + '</article>')
        halaman.append('<section class="lembar"><header><p class="meta">JAGOMAT · LATIHAN TAMBAHAN KELAS 5</p>'
                       '<h1>' + judul + '</h1><p class="meta">Paket cetak terpisah. Tidak masuk diagnosis atau bukti penguasaan aplikasi. '
                       'Kerjakan dengan tenang; jelaskan caramu.</p></header>' + ''.join(kartu) + '</section>')
    return '<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + judul + '</title><style>' + GAYA + '</style></head><body>' + ''.join(halaman) + '</body></html>'


def ekspor(tujuan: Path):
    """Tulis hanya direktori baru; tidak menerima nama atau jawaban anak."""
    tujuan.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for nama, solusi in (("soal.html", False), ("solusi.html", True)):
        isi = render(solusi).encode()
        (tujuan / nama).write_bytes(isi)
        hashes[nama] = hashlib.sha256(isi).hexdigest()
    manifest = {"versi": VERSI, "jumlah": len(PAKET), "sasaran": "kelas 5",
                "status": "menunggu_tinjauan_manusia", "berkas_sha256": hashes,
                "diagnosis_otomatis": False, "bukti_penguasaan": False}
    (tujuan / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(ekspor(args.output), ensure_ascii=False))
