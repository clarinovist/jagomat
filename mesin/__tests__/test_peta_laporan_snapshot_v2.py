"""Snapshot laporan Peta versi 2 (F3): grid benar/salah per nomor, jumlah dilewati, dan perkiraan waktu.

Data sintetis di basis sementara. Pembaca proses (`cek_ringkasan_proses`) dan jalur otomatis (`peta_otomatis`) diuji
dengan cek nyata; satu guard baru (tipe grid di `periksa_isi`) dimutasi lewat `harian_mutasi_kit.uji_mutasi` pada salinan.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis  # noqa: E402
import cek_ringkasan_admin as cra  # noqa: E402
import cek_ringkasan_proses as crp  # noqa: E402
import database  # noqa: E402
import peta_laporan_ortu_pages as halaman  # noqa: E402
import peta_laporan_snapshot as snap  # noqa: E402
import peta_laporan_store as toko  # noqa: E402
import peta_otomatis  # noqa: E402
from cek_gratis_kit import ID_A, ID_B, SEKARANG, SELESAI_SESI, mulai_cek, tambah_anak, tandai_selesai  # noqa: E402
from harian_mutasi_kit import uji_mutasi  # noqa: E402

TES_V2 = "test_peta_laporan_snapshot_v2.py"
SALIN_TES = ("cek_gratis_kit.py", "harian_mutasi_kit.py", TES_V2)
GURU = "guru-a"
NAMA_ANAK = "Anak Sintetis Rahasia"
CATATAN = "Catatan sintetis untuk uji laporan versi satu dan dua."
MULAI_SESI = "2026-11-18 08:45:00"  # 15 menit sebelum SELESAI_SESI
EPOCH = 1763000000
DURASI_DETIK = 900
# B = benar (jawaban kunci), S = salah (jawaban kosong), - = dilewati (tanpa baris jawaban).
POLA = "BBSBB-BSSBBBB-S"
GRID_POLA = [1, 1, 0, 1, 1, 2, 1, 0, 0, 1, 1, 1, 1, 2, 0]
KUNCI_V1 = set(snap.KUNCI_ISI[snap.VERSI_ISI_V1])
KUNCI_V2 = set(snap.KUNCI_ISI[snap.VERSI_ISI_V2])
KATA_TERLARANG = (
    "kunci", "jawaban", "malrule", "diagnos", "alasan", "sesi_id", "soal_id", "guru", "peringkat",
    "tantangan", "resep", "lencana", "status", "bahan", "hari_tersisa", "selesai_pada", "kontak",
)


def _ringkasan() -> dict:
    """Ringkasan sintetis (bentuk `KUNCI_HASIL`) untuk 15 soal."""
    return {
        "status": "selesai", "kelas": 4, "skor": 60, "kategori": "Cukup baik", "jumlah_soal": 15,
        "selesai_pada": "2026-11-18 09:00:00", "ringkasan_kuat": ["Berhitung"],
        "ringkasan_perlu": ["Geometri datar"],
        "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                       {"materi": "Pengukuran", "benar": 2, "total": 5},
                       {"materi": "Geometri datar", "benar": 2, "total": 5}],
        "bahan": "ada", "hari_tersisa": 20,
    }


def _butir(nomor: int, simbol: str) -> dict:
    if simbol == "-":
        return {"nomor": nomor, "dijawab": False, "benar": None}
    return {"nomor": nomor, "dijawab": True, "benar": 1 if simbol == "B" else 0}


def _proses(pola: str = POLA, durasi_detik=DURASI_DETIK) -> dict:
    return {"soal": [_butir(nomor, simbol) for nomor, simbol in enumerate(pola, start=1)],
            "durasi_detik": durasi_detik}


def _ubah_butir(proses: dict, indeks: int, **ubah) -> dict:
    return {**proses, "soal": [{**b, **ubah} if i == indeks else b for i, b in enumerate(proses["soal"])]}


def _isi_v2() -> dict:
    return snap.bangun(_ringkasan(), proses=_proses())


# --- bangun versi 2 (murni) --------------------------------------------------------------------

def test_v2_kunci_persis_grid_dan_perkiraan_waktu():
    isi = _isi_v2()
    assert set(isi) == KUNCI_V2
    assert isi["versi"] == snap.VERSI_ISI_V2
    assert isi["grid"] == GRID_POLA
    assert isi["dilewati"] == 2
    assert isi["menit_total"] == 15 and isi["rata_detik"] == 60


def test_v1_tanpa_proses_tetap_versi_satu_tanpa_grid():
    isi = snap.bangun(_ringkasan())
    assert set(isi) == KUNCI_V1 and isi["versi"] == snap.VERSI_ISI_V1


def test_bagian_v1_pada_v2_sama_dengan_isi_v1_untuk_masukan_yang_sama():
    v1 = snap.bangun(_ringkasan())
    v2 = _isi_v2()
    sama = KUNCI_V1 - {"versi"}
    assert {k: v2[k] for k in sama} == {k: v1[k] for k in sama}


def test_menit_dibulatkan_ke_atas_dan_rata_ke_bawah():
    isi = snap.bangun(_ringkasan(), proses=_proses(durasi_detik=61))
    assert isi["menit_total"] == 2 and isi["rata_detik"] == 4  # 61 // 15


def test_durasi_nol_menghasilkan_waktu_nol():
    isi = snap.bangun(_ringkasan(), proses=_proses(durasi_detik=0))
    assert isi["menit_total"] == 0 and isi["rata_detik"] == 0


@pytest.mark.parametrize("durasi", [None, snap.MAKS_MENIT_TOTAL * snap.DETIK_PER_MENIT + 1])
def test_durasi_kosong_atau_terlalu_panjang_tanpa_perkiraan_tidak_menghalangi(durasi):
    isi = snap.bangun(_ringkasan(), proses=_proses(durasi_detik=durasi))
    assert isi["menit_total"] is None and isi["rata_detik"] is None
    assert isi["grid"] == GRID_POLA


def test_tanpa_dilewati_bila_semua_soal_dijawab():
    isi = snap.bangun(_ringkasan(), proses=_proses("BBSBBSBBSBBSBBS"))
    assert isi["dilewati"] == 0 and 2 not in isi["grid"]


@pytest.mark.parametrize("proses", [
    {"soal": _proses()["soal"][:-1], "durasi_detik": DURASI_DETIK},
    {"soal": _proses()["soal"] + [_butir(16, "B")], "durasi_detik": DURASI_DETIK},
    _ubah_butir(_proses(), 2, nomor=4),
    _ubah_butir(_proses(), 0, benar=None),
    _ubah_butir(_proses(), 5, benar=1),
    _ubah_butir(_proses(), 0, dijawab=False),
    _ubah_butir(_proses(), 1, benar=True),
    {**_proses(), "durasi_detik": -1},
    {**_proses(), "durasi_detik": "900"},
    {**_proses(), "sesi_id": 7},
    {"soal": _proses()["soal"]},
])
def test_proses_tak_lengkap_menjadi_bahan_tidak_tersedia(proses):
    with pytest.raises(ValueError, match="bahan tidak tersedia"):
        snap.bangun(_ringkasan(), proses=proses)


def test_jumlah_soal_ringkasan_harus_cocok_dengan_panjang_soal():
    with pytest.raises(ValueError, match="bahan tidak tersedia"):
        snap.bangun({**_ringkasan(), "jumlah_soal": 14}, proses=_proses())


def test_isi_v2_tanpa_teks_terlarang_dan_tanpa_nama_anak():
    teks = json.dumps(_isi_v2(), ensure_ascii=False).lower()
    assert "rahasia" not in teks
    for kata in KATA_TERLARANG:
        assert kata not in teks, kata


# --- periksa_isi versi 2 -----------------------------------------------------------------------

def test_periksa_isi_v2_menerima_salinan_baru():
    isi = _isi_v2()
    bersih = snap.periksa_isi(isi)
    assert bersih == isi and bersih is not isi and bersih["grid"] is not isi["grid"]


def test_periksa_isi_v2_menerima_waktu_nol():
    assert snap.periksa_isi({**_isi_v2(), "menit_total": 0, "rata_detik": 0})["menit_total"] == 0


@pytest.mark.parametrize("ubah", [
    {"grid": GRID_POLA + [1]},
    {"grid": GRID_POLA[:-1]},
    {"grid": "1" * 15},
    {"grid": None},
    {"grid": [3] + GRID_POLA[1:]},
    {"grid": [-1] + GRID_POLA[1:]},
    {"grid": [1.0] + GRID_POLA[1:]},
    {"grid": GRID_POLA[:5] + [0] + GRID_POLA[6:]},
    {"dilewati": 1}, {"dilewati": 3}, {"dilewati": -1}, {"dilewati": True}, {"dilewati": "2"},
    {"menit_total": -1}, {"menit_total": "15"}, {"menit_total": None},
    {"rata_detik": None}, {"rata_detik": -1}, {"rata_detik": 61 * 15},
    {"menit_total": 0, "rata_detik": 1},
])
def test_periksa_isi_v2_menolak_grid_dan_waktu_tidak_sah(ubah):
    with pytest.raises(ValueError):
        snap.periksa_isi({**_isi_v2(), **ubah})


@pytest.mark.parametrize("ubah", [{"versi": 3}, {"versi": 0}, {"versi": True}, {"versi": "2"}, {"versi": None}])
def test_periksa_isi_menolak_versi_tak_dikenal(ubah):
    with pytest.raises(ValueError):
        snap.periksa_isi({**_isi_v2(), **ubah})


@pytest.mark.parametrize("kunci", sorted(KUNCI_V2))
def test_periksa_isi_v2_menolak_kunci_kurang(kunci):
    isi = _isi_v2()
    del isi[kunci]
    with pytest.raises(ValueError):
        snap.periksa_isi(isi)


@pytest.mark.parametrize("asing", ["sesi_id", "nama", "soal", "teks_soal", "akun_id"])
def test_periksa_isi_v2_menolak_kunci_asing(asing):
    with pytest.raises(ValueError):
        snap.periksa_isi({**_isi_v2(), asing: 1})


# --- pembaca proses dan basis sementara --------------------------------------------------------

@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "v2.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


def _jawab_pola(kon, sesi_id: int, pola: str) -> None:
    """Jawaban per nomor: B = jawaban kunci, S = jawaban kosong, - = tanpa baris jawaban (dilewati)."""
    for baris, simbol in zip(database.isi_sesi(kon, sesi_id), pola):
        if simbol != "-":
            database.simpan_jawaban(kon, baris["sesi_soal_id"], jawaban=baris["kunci"] if simbol == "B" else "")


def _cek_selesai(kon, anak: int, mulai=MULAI_SESI) -> int:
    """Cek sintetis selesai dengan pola `POLA`; mengembalikan id cek. Transaksi ditutup (commit)."""
    sesi_id = mulai_cek(kon, ID_A, anak, GURU)
    _jawab_pola(kon, sesi_id, POLA)
    kon.execute("UPDATE sesi SET mulai = ? WHERE id = ?", (mulai, sesi_id))
    tandai_selesai(kon, sesi_id, SELESAI_SESI)
    assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True
    kon.commit()
    return kon.execute("SELECT id FROM cek_gratis WHERE siswa_id = ?", (anak,)).fetchone()[0]


def _izin(anak: int, cek_id: int) -> dict:
    return {"order_id": 1, "siswa_id": anak, "cek_id": cek_id, "akun_id": ID_A, "terbit": None}


def test_v2_dari_pembaca_nyata_tanpa_nama_anak_dan_kata_terlarang(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    cek_id = _cek_selesai(kon, anak)
    ringkasan = cra.ringkasan_untuk_order(kon, anak, cek_id, ID_A, SEKARANG)
    proses = crp.proses_untuk_order(kon, anak, cek_id, ID_A)
    isi = snap.bangun(ringkasan, proses=proses)
    teks = json.dumps(isi, ensure_ascii=False).lower()
    assert set(isi) == KUNCI_V2 and isi["grid"] == GRID_POLA
    assert isi["dilewati"] == 2 and isi["menit_total"] == 15 and isi["rata_detik"] == 60
    assert NAMA_ANAK.lower() not in teks and "rahasia" not in teks
    for kata in KATA_TERLARANG:
        assert kata not in teks, kata
    assert snap.periksa_isi(isi) == isi


def test_pembaca_proses_hanya_allowlist_dan_menolak_akun_atau_anak_lain(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    lain = tambah_anak(kon, "Anak Sintetis Dua", GURU, 4)
    cek_id = _cek_selesai(kon, anak)
    proses = crp.proses_untuk_order(kon, anak, cek_id, ID_A)
    assert set(proses) == set(crp.KUNCI_PROSES) and proses["durasi_detik"] == DURASI_DETIK
    assert all(set(butir) == set(crp.KUNCI_SOAL) for butir in proses["soal"])
    assert crp.proses_untuk_order(kon, anak, cek_id, ID_B) is None
    assert crp.proses_untuk_order(kon, lain, cek_id, ID_A) is None
    assert crp.proses_untuk_order(kon, anak, cek_id + 1000, ID_A) is None
    with pytest.raises(ValueError):
        crp.proses_untuk_order(kon, anak, cek_id, "bukan-akun")


@pytest.mark.parametrize("sql", [crp._SQL_CEK, crp._SQL_WAKTU, crp._SQL_SOAL])
def test_sql_pembaca_proses_tanpa_kolom_terlarang(sql):
    kolom = re.search(r"SELECT(.*?)FROM", sql, re.S | re.I).group(1).lower()
    for kata in ("teks", "penyajian", "kunci", "jawaban", "restatement", "cara", "alasan", "kode",
                 "malrule", "soal_id", "nama", "kontak", "skor", "catatan"):
        assert kata not in kolom, kata


def test_snapshot_v1_tersimpan_tetap_terbaca_dan_v2_bolak_balik(kon):
    anak_v1 = tambah_anak(kon, "Anak Satu", GURU, 4)
    anak_v2 = tambah_anak(kon, "Anak Dua", GURU, 4)
    for anak, isi in ((anak_v1, snap.bangun(_ringkasan())), (anak_v2, _isi_v2())):
        toko.buat_draf(kon, anak, GURU, isi, EPOCH)
        toko.simpan_catatan(kon, anak, CATATAN)
        toko.terbitkan(kon, anak, GURU, EPOCH + 60)
        assert toko.ambil(kon, anak)["isi"] == isi
        assert toko.terbit_terakhir(kon, anak)["isi"] == isi


def test_jalur_otomatis_menerbitkan_laporan_versi_dua(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    cek_id = _cek_selesai(kon, anak)
    assert peta_otomatis.terbitkan_bila_siap(kon, _izin(anak, cek_id), SEKARANG) == peta_otomatis.TERBIT
    isi = toko.ambil(kon, anak)["isi"]
    assert isi["versi"] == snap.VERSI_ISI_V2
    assert len(isi["grid"]) == isi["jumlah_soal"] == 15
    assert isi["grid"] == GRID_POLA


def test_laporan_v2_tampil_di_blok_peta_tanpa_grid_mentah():
    """Renderer orang tua (versi 1) hanya membaca kunci yang dikenalnya; grid dan waktu tak tercetak mentah."""
    html = halaman.blok_peta({"isi": _isi_v2(), "catatan": CATATAN, "diterbitkan": "2026-11-24 15:00:00"})
    assert str(_isi_v2()["skor"]) in html
    assert str(GRID_POLA) not in html
    assert "menit_total" not in html and "grid" not in html.lower()


def test_jalur_otomatis_tanpa_waktu_mulai_tetap_terbit_tanpa_perkiraan(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    cek_id = _cek_selesai(kon, anak, mulai=None)
    assert peta_otomatis.terbitkan_bila_siap(kon, _izin(anak, cek_id), SEKARANG) == peta_otomatis.TERBIT
    isi = toko.ambil(kon, anak)["isi"]
    assert isi["menit_total"] is None and isi["rata_detik"] is None and isi["grid"] == GRID_POLA


@pytest.mark.parametrize("proses_palsu", [None, {"soal": [], "durasi_detik": DURASI_DETIK}])
def test_proses_tak_terbaca_membuat_laporan_belum_terbit(kon, monkeypatch, proses_palsu):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    cek_id = _cek_selesai(kon, anak)
    monkeypatch.setattr(crp, "proses_untuk_order", lambda *a, **k: proses_palsu)
    assert peta_otomatis.terbitkan_bila_siap(kon, _izin(anak, cek_id), SEKARANG) == peta_otomatis.BAHAN_BELUM
    assert toko.ambil(kon, anak) is None


# --- mutasi satu guard baru (tipe grid) --------------------------------------------------------

@pytest.mark.parametrize("nilai", [True, 1.0])
def test_grid_berisi_bukan_bilangan_bulat_ditolak(nilai):
    with pytest.raises(ValueError):
        snap.periksa_isi({**_isi_v2(), "grid": [nilai] + GRID_POLA[1:]})


def test_mutasi_guard_tipe_grid_tertangkap(tmp_path):
    uji_mutasi(tmp_path, "peta_laporan_snapshot.py",
               [("type(g) is not int or g not in NILAI_GRID", "g not in NILAI_GRID")],
               TES_V2, "test_grid_berisi_bukan_bilangan_bulat_ditolak", SALIN_TES)
