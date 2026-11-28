"""Snapshot laporan Peta versi 3 (F5): data perilaku per nomor soal (benar, detik, jumlah ganti, materi).

Versi 3 hanya terbit bila ada detik jawaban (cek baru); cek lama tetap versi 2 dan tidak berubah. Pembaca nyata
(`cek_ringkasan_proses`) dan jalur otomatis (`peta_otomatis`) diuji dengan cek sintetis di DB sementara. Guard
privasi dan rentang baru dimutasi lewat `harian_mutasi_kit.uji_mutasi` pada salinan, tidak pada berkas asli.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis  # noqa: E402
import cek_perilaku  # noqa: E402
import cek_ringkasan_admin as cra  # noqa: E402
import cek_ringkasan_proses as crp  # noqa: E402
import database  # noqa: E402
import peta_laporan_ortu_pages as halaman  # noqa: E402
import peta_laporan_snapshot as snap  # noqa: E402
import peta_laporan_store as toko  # noqa: E402
import peta_otomatis  # noqa: E402
from cek_gratis_kit import ID_A, ID_B, SEKARANG, SELESAI_SESI, mulai_cek, tambah_anak, tandai_selesai  # noqa: E402
from harian_mutasi_kit import uji_mutasi  # noqa: E402

TES_V3 = "test_peta_laporan_snapshot_v3.py"
SALIN_TES = ("cek_gratis_kit.py", "harian_mutasi_kit.py", TES_V3)
GURU = "guru-a"
NAMA_ANAK = "Anak Sintetis Rahasia"
CATATAN = "Catatan sintetis untuk uji laporan versi tiga."
MULAI_SESI = "2026-11-18 08:45:00"  # 15 menit sebelum SELESAI_SESI
EPOCH = 1763000000
DURASI_DETIK = 900
# B = benar, S = salah, - = dilewati (tanpa baris jawaban). Sama dengan pola uji versi 2.
POLA = "BBSBB-BSSBBBB-S"
GRID_POLA = [1, 1, 0, 1, 1, 2, 1, 0, 0, 1, 1, 1, 1, 2, 0]
# Detik per nomor (None untuk yang dilewati) dan jumlah ganti per nomor (nomor 1 sekali, nomor 8 tiga kali).
DETIK = (12, 45, 3, 30, 9, None, 5, 60, 8, 25, 40, 90, 15, None, 4)
GANTI = (1, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0)
MATERI = ("Berhitung", "Pengukuran", "Geometri datar")
MATERI_PANJANG = "Materi " + "x" * 73  # tepat 80 karakter (batas `MAKS_NAMA`)
KUNCI_V3 = set(snap.KUNCI_ISI[snap.VERSI_ISI_V3])
KUNCI_V2 = set(snap.KUNCI_ISI[snap.VERSI_ISI_V2])
KUNCI_BUTIR = set(crp.KUNCI_SOAL)
KATA_TERLARANG = (
    "kunci", "jawaban", "malrule", "diagnos", "alasan", "sesi_id", "soal_id", "guru", "peringkat",
    "tantangan", "resep", "lencana", "status", "bahan", "hari_tersisa", "selesai_pada", "kontak",
    "belum_pernah", "dicatat",
)


def _ringkasan(jumlah: int = 15) -> dict:
    """Ringkasan sintetis (bentuk `KUNCI_HASIL`) untuk `jumlah` soal."""
    return {
        "status": "selesai", "kelas": 4, "skor": 60, "kategori": "Cukup baik", "jumlah_soal": jumlah,
        "selesai_pada": "2026-11-18 09:00:00", "ringkasan_kuat": ["Berhitung"],
        "ringkasan_perlu": ["Geometri datar"],
        "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                       {"materi": "Pengukuran", "benar": 2, "total": 5},
                       {"materi": "Geometri datar", "benar": 2, "total": 5}],
        "bahan": "ada", "hari_tersisa": 20,
    }


def _butir_v3(nomor: int, simbol: str, detik, ganti: int, materi: str) -> dict:
    """Butir berkunci lengkap (`KUNCI_SOAL`) seperti keluaran pembaca proses."""
    dijawab = simbol != "-"
    return {"nomor": nomor, "dijawab": dijawab, "benar": int(simbol == "B") if dijawab else None,
            "detik": detik, "ganti": ganti, "materi": materi}


def _proses_v3(pola: str = POLA, detik=DETIK, ganti=GANTI, durasi=DURASI_DETIK) -> dict:
    soal = [_butir_v3(nomor, simbol, d, g, MATERI[(nomor - 1) % len(MATERI)])
            for nomor, (simbol, d, g) in enumerate(zip(pola, detik, ganti), start=1)]
    return {"soal": soal, "durasi_detik": durasi}


def _isi_v3(**kunci) -> dict:
    return snap.bangun(_ringkasan(), proses=_proses_v3(**kunci))


def _ubah_butir(isi: dict, indeks: int, **ubah) -> dict:
    return {**isi, "soal": [{**b, **ubah} if i == indeks else b for i, b in enumerate(isi["soal"])]}


def _proses_panjang(jumlah: int) -> dict:
    """Worst case untuk ukuran: detik 600, ganti 99, dan materi 80 karakter pada setiap soal."""
    pola = (POLA * (jumlah // len(POLA) + 1))[:jumlah]
    soal = [_butir_v3(nomor, simbol, None if simbol == "-" else 600, 0 if simbol == "-" else 99, MATERI_PANJANG)
            for nomor, simbol in enumerate(pola, start=1)]
    return {"soal": soal, "durasi_detik": DURASI_DETIK}


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "v3.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


def _jawab_pola(kon, sesi_id: int) -> None:
    """Jawaban, detik, dan jumlah ganti sesuai pola sintetis; `-` tidak punya baris jawaban."""
    for baris, simbol, detik, ganti in zip(database.isi_sesi(kon, sesi_id), POLA, DETIK, GANTI):
        if simbol == "-":
            continue
        database.simpan_jawaban(kon, baris["sesi_soal_id"],
                                jawaban=baris["kunci"] if simbol == "B" else "", detik=detik)
        for _ in range(ganti):
            cek_perilaku.catat_ganti(kon, baris["sesi_soal_id"], "lama", "baru")


def _cek_selesai(kon, anak: int) -> int:
    """Cek sintetis selesai dengan detik dan ganti; transaksi ditutup (commit). Mengembalikan id cek."""
    sesi_id = mulai_cek(kon, ID_A, anak, GURU)
    _jawab_pola(kon, sesi_id)
    kon.execute("UPDATE sesi SET mulai = ? WHERE id = ?", (MULAI_SESI, sesi_id))
    tandai_selesai(kon, sesi_id, SELESAI_SESI)
    assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True
    kon.commit()
    return kon.execute("SELECT id FROM cek_gratis WHERE siswa_id = ?", (anak,)).fetchone()[0]


def _izin(anak: int, cek_id: int) -> dict:
    return {"order_id": 1, "siswa_id": anak, "cek_id": cek_id, "akun_id": ID_A, "terbit": None}


# --- bangun versi 3 (murni) --------------------------------------------------------------------

def test_v3_kunci_persis_dan_butir_soal_lengkap():
    isi = _isi_v3()
    assert set(isi) == KUNCI_V3 and isi["versi"] == snap.VERSI_ISI_V3
    assert set(snap.KUNCI_ISI[snap.VERSI_ISI_V3]) == KUNCI_V3
    assert len(isi["soal"]) == isi["jumlah_soal"] == 15
    assert all(set(butir) == KUNCI_BUTIR for butir in isi["soal"])
    assert isi["grid"] == GRID_POLA


def test_v3_nilai_per_nomor_dan_ringkasan_perilaku():
    isi = _isi_v3()
    assert isi["soal"][0] == {"nomor": 1, "dijawab": True, "benar": 1, "detik": 12, "ganti": 1,
                              "materi": MATERI[0]}
    assert isi["soal"][5] == {"nomor": 6, "dijawab": False, "benar": None, "detik": None, "ganti": 0,
                              "materi": MATERI[2]}
    assert isi["soal"][7]["ganti"] == 3 and isi["soal"][7]["benar"] == 0
    # 13 soal punya detik (346 detik): rata 26; jawaban salah cepat (<10 detik) = nomor 3, 9, dan 15.
    assert isi["rata_detik_soal"] == 26
    assert isi["jumlah_cepat"] == 3
    assert isi["menit_total"] == 15 and isi["rata_detik"] == 60


def test_tanpa_detik_dan_tanpa_ganti_tetap_versi_dua_dan_sama_byte():
    dasar = snap.bangun(_ringkasan(), proses={"soal": [
        {"nomor": n, "dijawab": s != "-", "benar": (int(s == "B") if s != "-" else None)}
        for n, s in enumerate(POLA, start=1)], "durasi_detik": DURASI_DETIK})
    tanpa_detik = snap.bangun(_ringkasan(), proses=_proses_v3(detik=(None,) * 15, ganti=(0,) * 15))
    assert tanpa_detik["versi"] == snap.VERSI_ISI_V2 and set(tanpa_detik) == KUNCI_V2
    assert json.dumps(tanpa_detik, sort_keys=True) == json.dumps(dasar, sort_keys=True)


def test_detik_sebagian_tetap_versi_tiga_dengan_rata_kosong():
    sebagian = tuple(60 if i in (0, 1, 2, 3, 4, 6, 7) else None for i in range(15))  # 7 dari 15 soal
    isi = _isi_v3(detik=sebagian)
    assert isi["versi"] == snap.VERSI_ISI_V3 and isi["rata_detik_soal"] is None


def test_rata_detik_soal_tepat_separuh_dihitung():
    separuh = tuple(60 if i in (0, 1, 2, 3, 4, 6, 7, 8) else None for i in range(15))  # 8 dari 15 soal
    assert _isi_v3(detik=separuh)["rata_detik_soal"] == 60


def test_jumlah_cepat_hanya_salah_dengan_detik_di_bawah_ambang():
    pola = "SSBSS" + "B" * 10
    detik = (9, 10, 1, None, 0) + (None,) * 10  # salah<10 (9) ✓, salah=10 ✗, benar<10 ✗, tanpa detik ✗, salah 0 ✓
    ganti = (0,) * 15
    isi = snap.bangun(_ringkasan(), proses=_proses_v3(pola=pola, detik=detik, ganti=ganti))
    assert isi["jumlah_cepat"] == 2


def test_jumlah_ganti_di_atas_batas_dijepit_ke_sembilan_puluh_sembilan():
    isi = _isi_v3(ganti=(150,) + GANTI[1:])
    assert isi["soal"][0]["ganti"] == snap.MAKS_GANTI == 99


def test_isi_v3_tanpa_teks_terlarang_dan_tanpa_nama_anak():
    teks = json.dumps(_isi_v3(), ensure_ascii=False).lower()
    assert "rahasia" not in teks
    for kata in KATA_TERLARANG:
        assert kata not in teks, kata


def test_v1_dan_v2_lama_tetap_sah_di_periksa_isi():
    v1 = snap.bangun(_ringkasan())
    v2 = snap.bangun(_ringkasan(), proses=_proses_v3(detik=(None,) * 15, ganti=(0,) * 15))
    assert snap.periksa_isi(v1) == v1 and snap.periksa_isi(v2) == v2


# --- periksa_isi versi 3 -----------------------------------------------------------------------

def test_periksa_isi_v3_menerima_salinan_baru():
    isi = _isi_v3()
    bersih = snap.periksa_isi(isi)
    assert bersih == isi and bersih is not isi and bersih["soal"] is not isi["soal"]


@pytest.mark.parametrize("asing", ["jawaban", "teks_soal", "sesi_soal_id", "nama"])
def test_periksa_isi_v3_menolak_kunci_asing(asing):
    with pytest.raises(ValueError):
        snap.periksa_isi({**_isi_v3(), asing: 1})


@pytest.mark.parametrize("kunci", sorted(KUNCI_V3))
def test_periksa_isi_v3_menolak_kunci_kurang(kunci):
    isi = _isi_v3()
    del isi[kunci]
    with pytest.raises(ValueError):
        snap.periksa_isi(isi)


@pytest.mark.parametrize("ubah", [
    {"detik": 601}, {"detik": -1}, {"detik": True}, {"detik": "5"}, {"detik": 5.0},
    {"ganti": -1}, {"ganti": 100}, {"ganti": True}, {"ganti": "1"},
    {"dijawab": 1}, {"dijawab": None}, {"benar": True}, {"benar": 2}, {"benar": None},
    {"materi": ""}, {"materi": "x" * 81}, {"materi": 5},
    {"nomor": 2}, {"jawaban": "x"},
])
def test_periksa_isi_v3_menolak_butir_salah(ubah):
    with pytest.raises(ValueError):
        snap.periksa_isi(_ubah_butir(_isi_v3(), 0, **ubah))


@pytest.mark.parametrize("ubah", [{"detik": 5}, {"benar": 1}])
def test_periksa_isi_v3_menolak_data_pada_soal_dilewati(ubah):
    with pytest.raises(ValueError):
        snap.periksa_isi(_ubah_butir(_isi_v3(), 5, **ubah))


@pytest.mark.parametrize("ubah", [
    {"grid": [0] + GRID_POLA[1:]},
    {"rata_detik_soal": 27},
    {"jumlah_cepat": 4},
    {"soal": _isi_v3()["soal"][:-1]},
    {"soal": list(reversed(_isi_v3()["soal"]))},
])
def test_periksa_isi_v3_menolak_turunan_tidak_konsisten(ubah):
    with pytest.raises(ValueError):
        snap.periksa_isi({**_isi_v3(), **ubah})


@pytest.mark.parametrize("detik", [601, 10 ** 6, -1])
def test_periksa_isi_v3_menolak_rentang_detik(detik):
    """Isi dengan detik sparse (rata kosong, jumlah cepat tetap): hanya batas rentang yang boleh menolak."""
    sebagian = tuple(60 if i in (0, 1, 2, 3, 4, 6, 7) else None for i in range(15))
    with pytest.raises(ValueError):
        snap.periksa_isi(_ubah_butir(_isi_v3(detik=sebagian), 0, detik=detik))


@pytest.mark.parametrize("ubah", [{"versi": 0}, {"versi": 4}, {"versi": True}, {"versi": "3"}, {"versi": None}])
def test_periksa_isi_menolak_versi_tak_dikenal_setelah_v3(ubah):
    with pytest.raises(ValueError):
        snap.periksa_isi({**_isi_v3(), **ubah})


def test_periksa_isi_menolak_isi_v2_yang_diberi_versi_tiga():
    v2 = snap.bangun(_ringkasan(), proses=_proses_v3(detik=(None,) * 15, ganti=(0,) * 15))
    with pytest.raises(ValueError):
        snap.periksa_isi({**v2, "versi": 3})


# --- ukuran di kolom store ---------------------------------------------------------------------

def test_isi_v3_15_dan_25_soal_di_bawah_batas_karakter():
    for jumlah in (15, 25):
        isi = snap.bangun(_ringkasan(jumlah), proses=_proses_panjang(jumlah))
        assert len(json.dumps(isi, ensure_ascii=False, sort_keys=True)) < snap.MAKS_KARAKTER_ISI


def test_isi_v3_200_soal_ditolak_karena_melebihi_kolom_store():
    with pytest.raises(ValueError, match="terlalu panjang"):
        snap.bangun(_ringkasan(200), proses=_proses_panjang(200))


def test_isi_v3_25_soal_muat_dan_terbaca_kembali_dari_toko(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    isi = snap.bangun(_ringkasan(25), proses=_proses_panjang(25))
    toko.buat_draf(kon, anak, GURU, isi, EPOCH)
    toko.simpan_catatan(kon, anak, CATATAN)
    toko.terbitkan(kon, anak, GURU, EPOCH + 60)
    assert toko.ambil(kon, anak)["isi"] == isi


# --- pembaca proses nyata ----------------------------------------------------------------------

def test_pembaca_proses_v3_nilai_per_nomor_dari_cek_nyata(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    cek_id = _cek_selesai(kon, anak)
    proses = crp.proses_untuk_order(kon, anak, cek_id, ID_A)
    assert set(proses) == set(crp.KUNCI_PROSES) and proses["durasi_detik"] == DURASI_DETIK
    assert all(set(butir) == KUNCI_BUTIR for butir in proses["soal"])
    assert [b["detik"] for b in proses["soal"]] == list(DETIK)
    assert [b["ganti"] for b in proses["soal"]] == list(GANTI)
    assert all(b["materi"] for b in proses["soal"] if b["dijawab"])


def test_v3_dari_pembaca_nyata_sama_dengan_nilai_yang_diharapkan(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    cek_id = _cek_selesai(kon, anak)
    ringkasan = cra.ringkasan_untuk_order(kon, anak, cek_id, ID_A, SEKARANG)
    proses = crp.proses_untuk_order(kon, anak, cek_id, ID_A)
    isi = snap.bangun(ringkasan, proses=proses)
    assert isi["versi"] == snap.VERSI_ISI_V3 and set(isi) == KUNCI_V3
    assert isi["grid"] == GRID_POLA and isi["dilewati"] == 2
    assert isi["rata_detik_soal"] == 26 and isi["jumlah_cepat"] == 3
    assert isi["menit_total"] == 15 and isi["rata_detik"] == 60
    assert isi["soal"][0]["ganti"] == 1 and isi["soal"][7]["ganti"] == 3
    materi_soal = {b["materi"] for b in isi["soal"] if b["materi"] is not None}
    assert materi_soal == {m["materi"] for m in isi["per_materi"]}


def test_v3_dari_pembaca_nyata_tanpa_nama_anak_dan_kata_terlarang(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    cek_id = _cek_selesai(kon, anak)
    ringkasan = cra.ringkasan_untuk_order(kon, anak, cek_id, ID_A, SEKARANG)
    isi = snap.bangun(ringkasan, proses=crp.proses_untuk_order(kon, anak, cek_id, ID_A))
    teks = json.dumps(isi, ensure_ascii=False).lower()
    assert NAMA_ANAK.lower() not in teks and "rahasia" not in teks
    for kata in KATA_TERLARANG:
        assert kata not in teks, kata
    assert snap.periksa_isi(isi) == isi


def test_pembaca_proses_v3_menolak_akun_atau_anak_lain(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    lain = tambah_anak(kon, "Anak Sintetis Dua", GURU, 4)
    cek_id = _cek_selesai(kon, anak)
    assert crp.proses_untuk_order(kon, anak, cek_id, ID_B) is None
    assert crp.proses_untuk_order(kon, lain, cek_id, ID_A) is None


def test_pembaca_proses_v3_menolak_detik_di_luar_rentang(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    cek_id = _cek_selesai(kon, anak)
    kon.execute("UPDATE jawaban SET detik = 601 WHERE id = (SELECT MIN(id) FROM jawaban)")
    with pytest.raises(ValueError):
        crp.proses_untuk_order(kon, anak, cek_id, ID_A)


@pytest.mark.parametrize("sql", [crp._SQL_CEK, crp._SQL_WAKTU, crp._SQL_SOAL])
def test_sql_pembaca_proses_v3_tanpa_kolom_terlarang(sql):
    kolom = re.search(r"SELECT(.*?)FROM", sql, re.S | re.I).group(1).lower()
    for kata in ("teks", "penyajian", "kunci", "jawaban", "restatement", "cara", "alasan", "kode",
                 "malrule", "soal_id", "nama", "kontak", "skor", "catatan", "belum_pernah", "dicatat"):
        assert kata not in kolom, kata


def test_jalur_otomatis_menerbitkan_laporan_versi_tiga(kon):
    anak = tambah_anak(kon, NAMA_ANAK, GURU, 4)
    cek_id = _cek_selesai(kon, anak)
    assert peta_otomatis.terbitkan_bila_siap(kon, _izin(anak, cek_id), SEKARANG) == peta_otomatis.TERBIT
    isi = toko.ambil(kon, anak)["isi"]
    assert isi["versi"] == snap.VERSI_ISI_V3 and len(isi["soal"]) == isi["jumlah_soal"] == 15


# --- renderer: v3 tampil lewat renderer v2 tanpa kunci baru -----------------------------------

def test_renderer_v3_sama_dengan_proyeksi_v2_dan_tanpa_kunci_baru():
    isi = _isi_v3()
    proyeksi = {kunci: isi[kunci] for kunci in snap.KUNCI_ISI[snap.VERSI_ISI_V2]}
    proyeksi["versi"] = snap.VERSI_ISI_V2
    peta = {"catatan": CATATAN, "diterbitkan": "2026-11-24 15:00:00"}
    html_v3 = halaman.blok_peta({**peta, "isi": isi})
    assert html_v3 == halaman.blok_peta({**peta, "isi": proyeksi})
    assert "rata_detik_soal" not in html_v3 and "jumlah_cepat" not in html_v3


# --- mutasi guard baru -------------------------------------------------------------------------

def test_mutasi_kunci_butir_tertangkap(tmp_path):
    uji_mutasi(tmp_path, "peta_laporan_snapshot.py",
               [("if type(butir) is not dict or set(butir) != set(KUNCI_SOAL):",
                 "if type(butir) is not dict:")],
               TES_V3, "test_periksa_isi_v3_menolak_butir_salah", SALIN_TES)


def test_mutasi_rentang_detik_tertangkap(tmp_path):
    uji_mutasi(tmp_path, "peta_laporan_snapshot.py",
               [('    return _opsional_int(detik, cek_waktu_soal.BATAS_DETIK_SOAL, "detik")',
                 '    return _opsional_int(detik, 10 ** 9, "detik")')],
               TES_V3, "test_periksa_isi_v3_menolak_rentang_detik", SALIN_TES)


def test_mutasi_allowlist_sql_pembaca_tertangkap(tmp_path):
    uji_mutasi(tmp_path, "cek_ringkasan_proses.py",
               [("j.detik AS detik, s.template_id AS template_id",
                 "j.detik AS detik, s.template_id AS template_id, j.jawaban AS jawaban")],
               TES_V3, "test_sql_pembaca_proses_v3_tanpa_kolom_terlarang", SALIN_TES)
