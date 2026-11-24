"""Snapshot laporan Peta (D1-1): pembangun murni dari pembaca allowlist dan pemeriksa isi.

Data sintetis. Tes di sini menjadi sasaran mutation di `test_peta_laporan_mutation.py`.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis  # noqa: E402
import cek_ringkasan_admin as cra  # noqa: E402
import database  # noqa: E402
import peta_laporan_snapshot as snap  # noqa: E402
import topik_awam  # noqa: E402
from cek_gratis_kit import ID_A, SEKARANG, SELESAI_SESI, jawab, mulai_cek, tambah_anak, tandai_selesai  # noqa: E402

KUNCI_PERSIS = {
    "versi", "kelas", "tanggal_cek", "skor", "kategori", "jumlah_soal", "per_materi", "kuat",
    "perlu_dilatih", "ringkasan_perlu",
}
NAMA_ANAK = "Anak Sintetis Rahasia"
KATA_TERLARANG = (
    "kunci", "jawaban", "malrule", "diagnos", "alasan", "sesi_id", "soal_id", "guru", "peringkat",
    "tantangan", "resep", "lencana", "status", "bahan", "hari_tersisa", "selesai_pada", "kontak",
)


def _ringkasan(**ubah) -> dict:
    dasar = {
        "status": "selesai", "kelas": 4, "skor": 47, "kategori": "Perlu penguatan", "jumlah_soal": 15,
        "selesai_pada": "2026-11-18 09:00:00", "ringkasan_kuat": ["Berhitung"],
        "ringkasan_perlu": ["Geometri datar"],
        "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                       {"materi": "Pengukuran", "benar": 2, "total": 5},
                       {"materi": "Geometri datar", "benar": 0, "total": 5}],
        "bahan": "ada", "hari_tersisa": 20,
    }
    assert set(dasar) == set(cra.KUNCI_HASIL)
    return {**dasar, **ubah}


def _materi(*butir):
    return [{"materi": n, "benar": b, "total": t} for n, b, t in butir]


# --- bangun ------------------------------------------------------------------------------

def test_kunci_isi_persis_dan_versi_satu():
    isi = snap.bangun(_ringkasan())
    assert set(isi) == KUNCI_PERSIS
    assert isi["versi"] == 1
    assert set(snap.KUNCI_ISI) == KUNCI_PERSIS


def test_isi_menyalin_nilai_yang_diizinkan_saja():
    isi = snap.bangun(_ringkasan())
    assert isi["kelas"] == 4 and isi["skor"] == 47 and isi["kategori"] == "Perlu penguatan"
    assert isi["jumlah_soal"] == 15
    assert isi["tanggal_cek"] == "2026-11-18"
    assert isi["per_materi"] == _materi(("Berhitung", 5, 5), ("Pengukuran", 2, 5), ("Geometri datar", 0, 5))
    assert isi["kuat"] == ["Berhitung"]
    assert isi["ringkasan_perlu"] == ["Geometri datar"]


def test_tanggal_cek_dari_selesai_pada_berformat_iso_t():
    assert snap.bangun(_ringkasan(selesai_pada="2026-12-01T23:59:59"))["tanggal_cek"] == "2026-12-01"


def test_kelas_kosong_diizinkan_dan_ringkasan_perlu_kosong_tetap_ada_sebagai_daftar():
    isi = snap.bangun(_ringkasan(kelas=None, ringkasan_perlu=[]))
    assert isi["kelas"] is None
    assert isi["ringkasan_perlu"] == []


@pytest.mark.parametrize("bahan", ["dihapus", "belum_dinilai"])
def test_bahan_selain_ada_ditolak(bahan):
    with pytest.raises(ValueError, match="bahan tidak tersedia"):
        snap.bangun(_ringkasan(bahan=bahan))


def test_bahan_ada_tapi_per_materi_kosong_ditolak():
    with pytest.raises(ValueError, match="bahan tidak tersedia"):
        snap.bangun(_ringkasan(per_materi=[]))


def test_cek_belum_selesai_tanpa_skor_ditolak():
    with pytest.raises(ValueError, match="bahan tidak tersedia"):
        snap.bangun(_ringkasan(skor=None, status="belum_selesai"))


@pytest.mark.parametrize("ringkasan", [None, [], "ada"])
def test_ringkasan_bukan_dict_ditolak(ringkasan):
    with pytest.raises(ValueError, match="bahan tidak tersedia"):
        snap.bangun(ringkasan)


def test_ringkasan_dengan_kunci_asing_atau_kurang_ditolak():
    asing = {**_ringkasan(), "sesi_id": 7}
    kurang = {k: v for k, v in _ringkasan().items() if k != "hari_tersisa"}
    for salah in (asing, kurang):
        with pytest.raises(ValueError, match="bahan tidak tersedia"):
            snap.bangun(salah)


def test_perlu_dilatih_urut_rasio_terendah_lalu_nama_maksimal_tiga():
    per = _materi(("Penuh", 5, 5), ("Sedang E", 2, 5), ("Nol", 0, 5), ("Sedang B", 2, 5),
                  ("Satu", 1, 5), ("Alfa", 3, 5))
    isi = snap.bangun(_ringkasan(per_materi=per))
    assert isi["perlu_dilatih"] == ["Nol", "Satu", "Sedang B"]


def test_perlu_dilatih_rasio_sama_beda_total_diurut_nama():
    per = _materi(("Zeta", 1, 2), ("Alfa", 2, 4), ("Tuntas", 3, 3))
    assert snap.bangun(_ringkasan(per_materi=per))["perlu_dilatih"] == ["Alfa", "Zeta"]


def test_perlu_dilatih_kosong_bila_semua_materi_benar_semua():
    per = _materi(("A", 3, 3), ("B", 5, 5))
    assert snap.bangun(_ringkasan(per_materi=per))["perlu_dilatih"] == []


def test_perlu_dilatih_tidak_mengubah_urutan_per_materi():
    per = _materi(("Zeta", 0, 5), ("Alfa", 4, 5))
    isi = snap.bangun(_ringkasan(per_materi=per))
    assert [m["materi"] for m in isi["per_materi"]] == ["Zeta", "Alfa"]


def test_nama_resmi_lama_di_kuat_dan_perlu_dipetakan_ke_label_awam():
    awam = topik_awam.nama("pola-bilangan")
    resmi = "Pola Bilangan"
    assert awam != resmi and topik_awam.dari_nama_lama(resmi) == awam
    isi = snap.bangun(_ringkasan(ringkasan_kuat=[resmi], ringkasan_perlu=[resmi]))
    assert isi["kuat"] == [awam] and isi["ringkasan_perlu"] == [awam]


def test_bangun_deterministik_dan_tidak_mengubah_masukan():
    ringkasan = _ringkasan()
    asli = copy.deepcopy(ringkasan)
    pertama, kedua = snap.bangun(ringkasan), snap.bangun(ringkasan)
    assert pertama == kedua and pertama is not kedua
    assert ringkasan == asli
    pertama["per_materi"][0]["benar"] = 0
    pertama["kuat"].append("x")
    assert ringkasan == asli and snap.bangun(ringkasan) == kedua


def test_isi_dari_pembaca_nyata_tanpa_nama_anak_dan_kata_terlarang(tmp_path, monkeypatch):
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)
    jalur = tmp_path / "snap.db"
    database.siapkan(jalur)
    with database.buka(jalur) as kon:
        anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
        sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
        jawab(kon, sesi_id, {"berhitung-sekolah": 5, "pengukuran": 2, "geometri-datar": 0})
        tandai_selesai(kon, sesi_id, SELESAI_SESI)
        assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True
        cek_id = kon.execute("SELECT id FROM cek_gratis WHERE siswa_id = ?", (anak,)).fetchone()[0]
        ringkasan = cra.ringkasan_untuk_order(kon, anak, cek_id, ID_A, SEKARANG)
    isi = snap.bangun(ringkasan)
    teks = json.dumps(isi, ensure_ascii=False).lower()
    assert set(isi) == KUNCI_PERSIS
    assert NAMA_ANAK.lower() not in teks and "rahasia" not in teks
    for kata in KATA_TERLARANG:
        assert kata not in teks, kata
    assert snap.periksa_isi(isi) == isi
    assert isi["skor"] == 47 and isi["tanggal_cek"] == "2026-11-18"


# --- periksa_isi -------------------------------------------------------------------------

def test_periksa_isi_menerima_isi_sah_dan_mengembalikan_salinan():
    isi = snap.bangun(_ringkasan())
    bersih = snap.periksa_isi(isi)
    assert bersih == isi and bersih is not isi
    assert bersih["per_materi"] is not isi["per_materi"]


@pytest.mark.parametrize("ubah", [
    {"sesi_id": 1}, {"guru": "x"}, {"nama": "Anak"}, {"status": "selesai"},
])
def test_periksa_isi_menolak_kunci_asing(ubah):
    with pytest.raises(ValueError):
        snap.periksa_isi({**snap.bangun(_ringkasan()), **ubah})


@pytest.mark.parametrize("kunci", sorted(KUNCI_PERSIS))
def test_periksa_isi_menolak_kunci_kurang(kunci):
    isi = snap.bangun(_ringkasan())
    del isi[kunci]
    with pytest.raises(ValueError):
        snap.periksa_isi(isi)


@pytest.mark.parametrize("ubah", [
    {"versi": 2}, {"versi": True}, {"skor": "47"}, {"skor": True}, {"skor": 101}, {"skor": -1},
    {"jumlah_soal": 0}, {"jumlah_soal": 15.0}, {"kelas": 0}, {"kelas": 13}, {"kelas": "4"},
    {"tanggal_cek": "2026-13-01"}, {"tanggal_cek": "18-11-2026"}, {"tanggal_cek": None},
    {"kategori": ""}, {"kategori": 5}, {"kategori": "a" * 81}, {"kategori": "baris\nbaru"},
    {"per_materi": []}, {"per_materi": "x"}, {"per_materi": [{"materi": "A", "benar": 1, "total": 1}] * 41},
    {"kuat": "Berhitung"}, {"kuat": [5]}, {"kuat": [""]}, {"kuat": ["a"] * 41},
    {"perlu_dilatih": ["a", "b", "c", "d"]}, {"perlu_dilatih": None},
    {"ringkasan_perlu": [None]},
])
def test_periksa_isi_menolak_tipe_dan_batas_salah(ubah):
    with pytest.raises(ValueError):
        snap.periksa_isi({**snap.bangun(_ringkasan()), **ubah})


@pytest.mark.parametrize("butir", [
    {"materi": "A", "benar": 6, "total": 5},
    {"materi": "A", "benar": 0, "total": 0},
    {"materi": "A", "benar": -1, "total": 5},
    {"materi": "A", "benar": "1", "total": 5},
    {"materi": "A", "benar": True, "total": 5},
    {"materi": "", "benar": 1, "total": 5},
    {"materi": "A", "benar": 1, "total": 5, "jawaban": "x"},
    {"materi": "A", "benar": 1},
    "A",
])
def test_periksa_isi_menolak_butir_per_materi_salah(butir):
    with pytest.raises(ValueError):
        snap.periksa_isi({**snap.bangun(_ringkasan()), "per_materi": [butir]})


def test_periksa_isi_bukan_dict_ditolak():
    for salah in (None, [], "isi", 5):
        with pytest.raises(ValueError):
            snap.periksa_isi(salah)
