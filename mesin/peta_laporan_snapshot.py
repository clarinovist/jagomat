"""Snapshot isi laporan Peta Kemampuan untuk orang tua (D1-1): pembangun MURNI dan pemeriksa isi.

`bangun` mengubah hasil pembaca allowlist `cek_ringkasan_admin.ringkasan_untuk_order` (dipakai ulang, bukan
diduplikasi) menjadi isi laporan versi 1. Dengan `proses` (pembaca `cek_ringkasan_proses`) hasilnya versi 2: tambahan
grid benar/salah per nomor, jumlah dilewati, dan perkiraan waktu. Bila proses memuat detik jawaban (cek baru), hasilnya
versi 3: tambahan daftar `soal` per nomor (benar, detik, jumlah ganti, materi), rata-rata detik soal, dan jumlah jawaban
salah yang terlalu cepat. Hanya bahan `ada` dengan data per materi yang diterima; selain itu ValueError (tidak ada
penebakan). Isi TANPA nama anak, kontak, teks soal, jawaban, kunci, kode diagnosis/malrule/alasan, id sesi/soal/
sesi soal, nama Guru, peringkat, Tantangan/Resep/Lencana, status/bahan/hari_tersisa, atau jam selesai.

`periksa_isi` adalah gerbang tunggal bentuk isi: dipakai store saat menulis dan saat membaca, dan oleh renderer
halaman orang tua kelak. Kunci harus PERSIS `KUNCI_ISI` per versi; tipe dan batas panjang ditegakkan; hasilnya salinan
baru. Isi versi 3 juga harus muat di kolom `peta_laporan.isi` (lihat `MAKS_KARAKTER_ISI`).
"""
from __future__ import annotations

import json
from datetime import date
from fractions import Fraction
from typing import Optional

import cek_waktu_soal
import topik_awam
from cek_gratis_skor import RETENSI_BELUM_SELESAI_HARI, waktu_baku
from cek_ringkasan_admin import BAHAN_ADA, KUNCI_HASIL
from cek_ringkasan_proses import KUNCI_PROSES, KUNCI_SOAL, KUNCI_SOAL_DASAR

VERSI_ISI_V1 = 1
VERSI_ISI_V2 = 2
VERSI_ISI_V3 = 3
MAKS_DILATIH = 3
MAKS_MATERI = 40
MAKS_NAMA = 80
MAKS_SOAL = 200
KELAS_MIN, KELAS_MAKS = 1, 12
KUNCI_V1 = (
    "versi", "kelas", "tanggal_cek", "skor", "kategori", "jumlah_soal", "per_materi", "kuat",
    "perlu_dilatih", "ringkasan_perlu",
)
KUNCI_V2 = KUNCI_V1 + ("grid", "dilewati", "menit_total", "rata_detik")
KUNCI_V3 = KUNCI_V2 + ("soal", "rata_detik_soal", "jumlah_cepat")
KUNCI_ISI = {VERSI_ISI_V1: KUNCI_V1, VERSI_ISI_V2: KUNCI_V2, VERSI_ISI_V3: KUNCI_V3}
KUNCI_MATERI = ("materi", "benar", "total")
GRID_SALAH, GRID_BENAR, GRID_DILEWATI = 0, 1, 2
NILAI_GRID = (GRID_SALAH, GRID_BENAR, GRID_DILEWATI)
DETIK_PER_MENIT = 60
# Batas wajar satu cek: sesi belum selesai disapu setelah RETENSI_BELUM_SELESAI_HARI; durasi di atasnya tak diperkirakan.
MAKS_MENIT_TOTAL = 60 * 24 * RETENSI_BELUM_SELESAI_HARI
# Jawaban salah yang diisi kurang dari ambang ini dihitung sebagai "terlalu cepat" (tanpa menilai anak).
AMBANG_CEPAT_DETIK = 10
# Jumlah ganti di atas batas ini dijepit (bukan ditolak) agar laporan tetap terbit.
MAKS_GANTI = 99
# Sama dengan CHECK `length(isi) BETWEEN 2 AND 8000` di `schema_peta_laporan.py` (dibaca karakter JSON yang disimpan).
MAKS_KARAKTER_ISI = 8000
_PESAN_BAHAN = "bahan tidak tersedia"


def _nama_awam(daftar) -> list:
    """Nama topik tersimpan (bisa nama resmi lama) menjadi label awam efektif; salinan baru."""
    return [topik_awam.dari_nama_lama(nama) for nama in daftar]


def _perlu_dilatih(per_materi) -> list:
    """Maks `MAKS_DILATIH` nama materi: rasio benar terendah dulu, lalu nama; hanya yang belum penuh benar."""
    kandidat = [m for m in per_materi if m["total"] >= 1 and m["benar"] < m["total"]]
    urut = sorted(kandidat, key=lambda m: (Fraction(m["benar"], m["total"]), m["materi"]))
    return [m["materi"] for m in urut[:MAKS_DILATIH]]


def _isi_dari_ringkasan(ringkasan) -> dict:
    """Isi versi 1 mentah dari hasil `ringkasan_untuk_order`; ValueError("bahan tidak tersedia") bila belum layak."""
    if not isinstance(ringkasan, dict) or set(ringkasan) != set(KUNCI_HASIL):
        raise ValueError(_PESAN_BAHAN)
    if ringkasan["bahan"] != BAHAN_ADA or not ringkasan["per_materi"] or ringkasan["skor"] is None:
        raise ValueError(_PESAN_BAHAN)
    per_materi = [{"materi": m["materi"], "benar": m["benar"], "total": m["total"]}
                  for m in ringkasan["per_materi"]]
    return {
        "versi": VERSI_ISI_V1,
        "kelas": ringkasan["kelas"],
        "tanggal_cek": waktu_baku(ringkasan["selesai_pada"]).date().isoformat(),
        "skor": ringkasan["skor"],
        "kategori": ringkasan["kategori"],
        "jumlah_soal": ringkasan["jumlah_soal"],
        "per_materi": per_materi,
        "kuat": _nama_awam(ringkasan["ringkasan_kuat"]),
        "perlu_dilatih": _perlu_dilatih(per_materi),
        "ringkasan_perlu": _nama_awam(ringkasan["ringkasan_perlu"]),
    }


def bangun(ringkasan, proses=None) -> dict:
    """Isi laporan dari `ringkasan_untuk_order`: versi 1 bila `proses` None; versi 2 atau 3 bila ada (pembaca proses).

    ValueError("bahan tidak tersedia") bila bahan belum layak, atau bila untuk versi 2/3 grid tidak bisa dibentuk.
    """
    isi = _isi_dari_ringkasan(ringkasan)
    if proses is not None:
        isi = {**isi, **_bagian_proses(proses, isi["jumlah_soal"])}
    return periksa_isi(isi)


def _bagian_proses(proses, jumlah) -> dict:
    """Versi 2 (grid, dilewati, waktu) atau versi 3 bila ada detik soal; ValueError bila tak lengkap."""
    if type(proses) is not dict or set(proses) != set(KUNCI_PROSES):
        raise ValueError(_PESAN_BAHAN)
    if type(jumlah) is not int or jumlah < 1:
        raise ValueError(_PESAN_BAHAN)
    grid = _grid_dari_soal(proses["soal"], jumlah)
    menit, rata = _waktu_dari_durasi(proses["durasi_detik"], jumlah)
    dasar = {"versi": VERSI_ISI_V2, "grid": grid, "dilewati": grid.count(GRID_DILEWATI),
             "menit_total": menit, "rata_detik": rata}
    if not _ada_detik(proses["soal"]):
        return dasar
    return {**dasar, "versi": VERSI_ISI_V3, **_bagian_perilaku(proses["soal"], jumlah)}


def _ada_detik(soal) -> bool:
    """True bila ada butir berbentuk lengkap (`KUNCI_SOAL`) dengan detik terisi; cek lama tanpa detik tetap versi 2."""
    return any(type(b) is dict and set(b) == set(KUNCI_SOAL) and b["detik"] is not None for b in soal)


def _bagian_perilaku(soal, jumlah: int) -> dict:
    """Butir soal versi 3 dan ringkasan perilakunya; jumlah ganti di atas `MAKS_GANTI` dijepit ke batas."""
    butir = _soal_periksa([_jepit_ganti(b) for b in soal], jumlah)
    return {"soal": butir, "rata_detik_soal": _rata_detik_soal(butir, jumlah),
            "jumlah_cepat": _jumlah_cepat(butir)}


def _jepit_ganti(butir):
    """Butir dengan `ganti` di atas batas dijepit ke `MAKS_GANTI`; bentuk lain dibiarkan untuk diperiksa."""
    if type(butir) is not dict or type(butir.get("ganti")) is not int:
        return butir
    return {**butir, "ganti": min(butir["ganti"], MAKS_GANTI)}


def _grid_dari_soal(soal, jumlah: int) -> list:
    """Satu nilai per nomor 1..jumlah; urut nomor dan jumlah wajib cocok (tanpa lubang atau kelebihan)."""
    if type(soal) is not list or len(soal) != jumlah:
        raise ValueError(_PESAN_BAHAN)
    return [_nilai_grid(butir, nomor) for nomor, butir in enumerate(soal, start=1)]


def _nilai_grid(butir, nomor: int) -> int:
    """GRID_DILEWATI bila tak ada jawaban; selain itu benar/salah dari diagnosis (belum dinilai = galat)."""
    if type(butir) is not dict or set(butir) not in (set(KUNCI_SOAL_DASAR), set(KUNCI_SOAL)):
        raise ValueError(_PESAN_BAHAN)
    if type(butir["nomor"]) is not int or butir["nomor"] != nomor or type(butir["dijawab"]) is not bool:
        raise ValueError(_PESAN_BAHAN)
    if not butir["dijawab"]:
        if butir["benar"] is not None:
            raise ValueError(_PESAN_BAHAN)
        return GRID_DILEWATI
    if type(butir["benar"]) is not int or butir["benar"] not in (0, 1):
        raise ValueError(_PESAN_BAHAN)
    return GRID_BENAR if butir["benar"] == 1 else GRID_SALAH


def _waktu_dari_durasi(durasi, jumlah: int):
    """(menit_total, rata_detik): menit dibulatkan ke atas, rata per soal dibulatkan ke bawah (perkiraan).

    None,None bila durasi tak ada atau melewati `MAKS_MENIT_TOTAL` (tanpa perkiraan; tidak menghalangi terbit).
    """
    if durasi is None:
        return None, None
    if type(durasi) is not int or durasi < 0:
        raise ValueError(_PESAN_BAHAN)
    if durasi > MAKS_MENIT_TOTAL * DETIK_PER_MENIT:
        return None, None
    return (durasi + DETIK_PER_MENIT - 1) // DETIK_PER_MENIT, durasi // jumlah


def _rata_detik_soal(butir, jumlah: int) -> Optional[int]:
    """Rata-rata detik soal yang punya detik (dibulatkan ke bawah); None bila kurang dari separuh soal punya detik."""
    detik = [b["detik"] for b in butir if b["detik"] is not None]
    if 2 * len(detik) < jumlah:
        return None
    return sum(detik) // len(detik)


def _jumlah_cepat(butir) -> int:
    """Jawaban SALAH yang diisi kurang dari `AMBANG_CEPAT_DETIK` detik; hanya dihitung bila detik ada."""
    return sum(1 for b in butir
               if b["dijawab"] and b["benar"] == 0 and b["detik"] is not None and b["detik"] < AMBANG_CEPAT_DETIK)


def _grid_dari_butir(butir) -> list:
    """Grid yang seharusnya dari butir versi 3 (dilewati / benar / salah)."""
    return [GRID_DILEWATI if not b["dijawab"] else (GRID_BENAR if b["benar"] == 1 else GRID_SALAH) for b in butir]


def _int(nilai, kecil: int, besar: int, nama: str) -> int:
    if type(nilai) is not int or not kecil <= nilai <= besar:
        raise ValueError("%s tidak sah" % nama)
    return nilai


def _teks(nilai, nama: str) -> str:
    if type(nilai) is not str or not 1 <= len(nilai) <= MAKS_NAMA or not nilai.isprintable():
        raise ValueError("%s tidak sah" % nama)
    return nilai


def _daftar_teks(nilai, maks: int, nama: str) -> list:
    if type(nilai) is not list or len(nilai) > maks:
        raise ValueError("%s tidak sah" % nama)
    return [_teks(butir, nama) for butir in nilai]


def _materi(butir) -> dict:
    if type(butir) is not dict or set(butir) != set(KUNCI_MATERI):
        raise ValueError("per_materi tidak sah")
    total = _int(butir["total"], 1, MAKS_SOAL, "total")
    return {"materi": _teks(butir["materi"], "materi"),
            "benar": _int(butir["benar"], 0, total, "benar"), "total": total}


def _tanggal(nilai) -> str:
    if type(nilai) is not str or len(nilai) != 10:
        raise ValueError("tanggal_cek tidak sah")
    try:
        return date.fromisoformat(nilai).isoformat()
    except ValueError:
        raise ValueError("tanggal_cek tidak sah") from None


def _kelas(nilai) -> Optional[int]:
    return None if nilai is None else _int(nilai, KELAS_MIN, KELAS_MAKS, "kelas")


def _versi_isi(isi) -> int:
    """Versi yang dikenal (`KUNCI_ISI`) dari isi; selain itu ValueError."""
    if type(isi) is not dict or "versi" not in isi:
        raise ValueError("kunci isi laporan tidak sah")
    versi = isi["versi"]
    if type(versi) is not int or versi not in KUNCI_ISI:
        raise ValueError("versi isi laporan tidak dikenal")
    return versi


def periksa_isi(isi) -> dict:
    """Isi bersih (salinan baru) atau ValueError: versi dikenal, kunci persis sesuai versi, tipe, batas, konsistensi."""
    versi = _versi_isi(isi)
    if set(isi) != set(KUNCI_ISI[versi]):
        raise ValueError("kunci isi laporan tidak sah")
    per_materi = isi["per_materi"]
    if type(per_materi) is not list or not 1 <= len(per_materi) <= MAKS_MATERI:
        raise ValueError("per_materi tidak sah")
    bersih = {
        "versi": versi,
        "kelas": _kelas(isi["kelas"]),
        "tanggal_cek": _tanggal(isi["tanggal_cek"]),
        "skor": _int(isi["skor"], 0, 100, "skor"),
        "kategori": _teks(isi["kategori"], "kategori"),
        "jumlah_soal": _int(isi["jumlah_soal"], 1, MAKS_SOAL, "jumlah_soal"),
        "per_materi": [_materi(butir) for butir in per_materi],
        "kuat": _daftar_teks(isi["kuat"], MAKS_MATERI, "kuat"),
        "perlu_dilatih": _daftar_teks(isi["perlu_dilatih"], MAKS_DILATIH, "perlu_dilatih"),
        "ringkasan_perlu": _daftar_teks(isi["ringkasan_perlu"], MAKS_MATERI, "ringkasan_perlu"),
    }
    if versi in (VERSI_ISI_V2, VERSI_ISI_V3):
        bersih.update(_periksa_v2(isi, bersih["jumlah_soal"]))
    if versi == VERSI_ISI_V3:
        bersih.update(_periksa_v3(isi, bersih["jumlah_soal"], bersih["grid"]))
        _periksa_ukuran(bersih)
    return bersih


def _periksa_v2(isi: dict, jumlah: int) -> dict:
    """Bagian versi 2: grid per nomor, jumlah dilewati (= hitungan 2), dan waktu (None bersama, tidak melebihi total)."""
    grid = _grid_periksa(isi["grid"], jumlah)
    dilewati = _int(isi["dilewati"], 0, jumlah, "dilewati")
    if dilewati != grid.count(GRID_DILEWATI):
        raise ValueError("dilewati tidak konsisten dengan grid")
    menit = _opsional_int(isi["menit_total"], MAKS_MENIT_TOTAL, "menit_total")
    rata = _opsional_int(isi["rata_detik"], MAKS_MENIT_TOTAL * DETIK_PER_MENIT, "rata_detik")
    if (menit is None) != (rata is None):
        raise ValueError("waktu tidak konsisten")
    if menit is not None and rata * jumlah > menit * DETIK_PER_MENIT:
        raise ValueError("waktu tidak konsisten")
    return {"grid": grid, "dilewati": dilewati, "menit_total": menit, "rata_detik": rata}


def _periksa_v3(isi: dict, jumlah: int, grid: list) -> dict:
    """Bagian versi 3: butir soal, rata-rata detik, dan jumlah cepat; konsisten dengan grid dan dihitung ulang."""
    soal = _soal_periksa(isi["soal"], jumlah)
    if grid != _grid_dari_butir(soal):
        raise ValueError("soal tidak konsisten dengan grid")
    rata = _opsional_int(isi["rata_detik_soal"], cek_waktu_soal.BATAS_DETIK_SOAL, "rata_detik_soal")
    if rata != _rata_detik_soal(soal, jumlah):
        raise ValueError("rata_detik_soal tidak konsisten")
    cepat = _int(isi["jumlah_cepat"], 0, jumlah, "jumlah_cepat")
    if cepat != _jumlah_cepat(soal):
        raise ValueError("jumlah_cepat tidak konsisten")
    return {"soal": soal, "rata_detik_soal": rata, "jumlah_cepat": cepat}


def _soal_periksa(nilai, jumlah: int) -> list:
    """Butir per nomor 1..jumlah berkunci `KUNCI_SOAL` persis dan bertipe ketat; ValueError bila tidak sah."""
    if type(nilai) is not list or len(nilai) != jumlah:
        raise ValueError("soal tidak sah")
    return [_butir_periksa(butir, nomor) for nomor, butir in enumerate(nilai, start=1)]


def _butir_periksa(butir, nomor: int) -> dict:
    """Satu butir versi 3: dilewati berarti tanpa benar dan tanpa detik; jawaban berarti benar 0/1 (bool ditolak)."""
    if type(butir) is not dict or set(butir) != set(KUNCI_SOAL):
        raise ValueError("soal tidak sah")
    dijawab = butir["dijawab"]
    if type(dijawab) is not bool or _int(butir["nomor"], nomor, nomor, "nomor") != nomor:
        raise ValueError("soal tidak sah")
    return {
        "nomor": nomor,
        "dijawab": dijawab,
        "benar": _benar_butir(butir["benar"], dijawab),
        "detik": _detik_butir(butir["detik"], dijawab),
        "ganti": _int(butir["ganti"], 0, MAKS_GANTI, "ganti"),
        "materi": _materi_opsional(butir["materi"]),
    }


def _benar_butir(benar, dijawab: bool):
    if not dijawab:
        if benar is not None:
            raise ValueError("soal tidak sah")
        return None
    if type(benar) is not int or benar not in (0, 1):
        raise ValueError("soal tidak sah")
    return benar


def _detik_butir(detik, dijawab: bool) -> Optional[int]:
    if not dijawab:
        if detik is not None:
            raise ValueError("soal tidak sah")
        return None
    return _opsional_int(detik, cek_waktu_soal.BATAS_DETIK_SOAL, "detik")


def _materi_opsional(nilai) -> Optional[str]:
    return None if nilai is None else _teks(nilai, "materi")


def _periksa_ukuran(bersih: dict) -> None:
    """Isi versi 3 harus muat di kolom `peta_laporan.isi`, dihitung dari JSON yang disimpan toko."""
    if len(json.dumps(bersih, ensure_ascii=False, sort_keys=True)) > MAKS_KARAKTER_ISI:
        raise ValueError("isi laporan terlalu panjang")


def _grid_periksa(nilai, jumlah: int) -> list:
    """Grid tepat `jumlah` butir, masing-masing bilangan bulat 0/1/2 (bool tidak diterima)."""
    if type(nilai) is not list or len(nilai) != jumlah:
        raise ValueError("grid tidak sah")
    if any(type(g) is not int or g not in NILAI_GRID for g in nilai):
        raise ValueError("grid tidak sah")
    return list(nilai)


def _opsional_int(nilai, besar: int, nama: str):
    return None if nilai is None else _int(nilai, 0, besar, nama)
