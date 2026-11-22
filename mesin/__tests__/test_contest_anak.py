"""Ringkasan anak Latihan Lomba: soal kosong siklis, banding, target harian, nilai terbaik, dan sesi asal kumpul."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import contest_anak as A  # noqa: E402
import contest_assignment_store as AS  # noqa: E402
import contest_core as C  # noqa: E402
import contest_paket as PK  # noqa: E402
import contest_store as K  # noqa: E402
import database  # noqa: E402

SEKARANG = 1_795_000_000            # 18 Nov 2026, 18.06 WIB
AWAL_HARI = PK.awal_hari_wib(SEKARANG)
KEMARIN_MALAM = AWAL_HARI - 3600    # 23.00 WIB kemarin
LAMA_WAJAR = 400


@pytest.fixture
def kon(tmp_path):
    jalur = tmp_path / "anak.db"
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        yield k


@pytest.fixture
def anak(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Satu", pemilik="guru")


@pytest.fixture
def anak_lain(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Dua", pemilik="guru")


def _jawaban(kon, sesi_id, nomor, benar):
    baris = kon.execute("SELECT jenis, kunci, pilihan_json FROM lomba_soal WHERE sesi_id=? AND nomor=?",
                        (sesi_id, nomor)).fetchone()
    if baris["jenis"] == "isian":
        return baris["kunci"] if benar else str(int(baris["kunci"]) + 1)
    huruf = C.HURUF[json.loads(baris["pilihan_json"]).index(baris["kunci"])]
    return huruf if benar else next(h for h in C.HURUF if h != huruf)


def _sesi_selesai(kon, siswa, mulai, lama, benar_sampai=10, terisi=10):
    """Satu sesi: nomor 1..terisi dijawab (benar bila nomor <= benar_sampai), dikumpulkan `lama` detik kemudian."""
    sesi = K.mulai_atau_lanjut(kon, siswa, mulai, seed=mulai % 10_007)
    for nomor in range(1, terisi + 1):
        K.simpan_jawaban(kon, siswa, sesi.id, nomor, _jawaban(kon, sesi.id, nomor, nomor <= benar_sampai), mulai + 1)
    K.kumpulkan(kon, siswa, sesi.id, mulai + lama)
    return sesi.id


# --- soal kosong siklis ------------------------------------------------------------------------------

def test_kosong_pertama_adalah_nomor_terkecil_yang_belum_terisi_dan_satu_bila_semua_terisi():
    assert A.nomor_kosong_pertama(frozenset()) == 1
    assert A.nomor_kosong_pertama(frozenset({1, 2, 4})) == 3
    assert A.nomor_kosong_pertama(frozenset(range(2, 11))) == 1
    assert A.nomor_kosong_pertama(frozenset(range(1, 11))) == 1


@pytest.mark.parametrize("terisi,nomor,harapan", [
    (set(), 3, 4),
    ({3, 4}, 3, 5),
    ({3, 4, 5, 6, 7, 8, 9, 10}, 3, 1),          # 4..10 terisi, memutar ke 1
    ({1, 2, 3, 4, 5, 6, 7, 8, 9, 10}, 3, None),  # semua terisi
    ({3, 4, 5, 6, 7, 8, 9, 10, 1}, 3, 2),
    ({1, 2, 4, 5, 6, 7, 8, 9, 10, 3}, 10, None),
    (set(), 10, 1),
    ({1}, 10, 2),
    ({10}, 10, 1),
    ({1, 2, 3, 4, 5, 6, 7, 8, 9}, 10, None),
])
def test_kosong_berikutnya_setelah_nomor_ini_secara_siklis(terisi, nomor, harapan):
    assert A.nomor_kosong_berikutnya(frozenset(terisi | {nomor}), nomor) == harapan


def test_kosong_berikutnya_tidak_pernah_mengembalikan_nomor_itu_sendiri():
    assert A.nomor_kosong_berikutnya(frozenset(), 5) == 6
    assert A.nomor_kosong_berikutnya(frozenset(set(range(1, 11)) - {5}), 5) is None


# --- kalimat banding ------------------------------------------------------------------------------------

@pytest.mark.parametrize("nilai,sebelumnya,kalimat", [
    (7, 5, "Naik 2 dari latihan sebelumnya"), (5, 7, "Turun 2 dari latihan sebelumnya"),
    (6, 6, "Sama dengan latihan sebelumnya"), (0, 0, "Sama dengan latihan sebelumnya"),
    (7, None, ""), (1, 0, "Naik 1 dari latihan sebelumnya"),
])
def test_kalimat_banding(nilai, sebelumnya, kalimat):
    assert A.kalimat_banding(nilai, sebelumnya) == kalimat


# --- ringkasan dari DB --------------------------------------------------------------------------------------

def test_anak_baru_tanpa_sesi_punya_ringkasan_kosong(kon, anak):
    r = A.muat_ringkas(kon, anak, SEKARANG)

    assert r.berjalan is None and r.sisa_detik == 0 and r.terisi == frozenset() and r.nomor_lanjut == 1
    assert r.riwayat == () and r.nilai_terbaik is None and r.nilai_terakhir is None and r.selesai_hari_ini == 0
    assert r.hitung_mundur == "Lomba tinggal 24 hari lagi" and r.paket is PK.PAKET_AKTIF
    assert r.sekarang == SEKARANG


def _tugaskan(kon, siswa, **nilai):
    dasar = dict(aktif=True, target_harian=None, tampil_hitung_mundur=None, durasi_latihan_detik=None, durasi_simulasi_detik=None, sekarang=SEKARANG, oleh="guru-uji")
    dasar.update(nilai)
    AS.atur(kon, siswa, **dasar)


def test_penugasan_tanpa_nilai_khusus_mengikuti_paket_persis(kon, anak):
    _tugaskan(kon, anak)

    r = A.muat_ringkas(kon, anak, SEKARANG)

    assert r.paket is PK.PAKET_AKTIF and r.hitung_mundur == "Lomba tinggal 24 hari lagi"


def test_penugasan_menimpa_target_harian_paket_termasuk_nol(kon, anak):
    _tugaskan(kon, anak, target_harian=3)
    assert A.muat_ringkas(kon, anak, SEKARANG).paket.target_harian == 3

    _tugaskan(kon, anak, target_harian=0)
    r = A.muat_ringkas(kon, anak, SEKARANG)

    assert r.paket.target_harian == 0
    assert PK.PAKET_AKTIF.target_harian == 2      # paket asli tidak dimutasi


def test_penugasan_mematikan_hitung_mundur_tanpa_mengubah_paket(kon, anak):
    _tugaskan(kon, anak, tampil_hitung_mundur=False)

    r = A.muat_ringkas(kon, anak, SEKARANG)

    assert r.hitung_mundur == "" and r.paket.tampil_hitung_mundur is False
    assert PK.PAKET_AKTIF.tampil_hitung_mundur is True


def test_penugasan_satu_anak_tidak_memengaruhi_ringkasan_anak_lain(kon, anak, anak_lain):
    _tugaskan(kon, anak, target_harian=5, tampil_hitung_mundur=False)

    r = A.muat_ringkas(kon, anak_lain, SEKARANG)

    assert r.paket is PK.PAKET_AKTIF and r.hitung_mundur == "Lomba tinggal 24 hari lagi"


def test_sesi_berjalan_membawa_sisa_waktu_terisi_dan_soal_kosong_pertama(kon, anak):
    sesi = K.mulai_atau_lanjut(kon, anak, SEKARANG - 100, seed=1)
    for nomor in (1, 2, 4):
        K.simpan_jawaban(kon, anak, sesi.id, nomor, _jawaban(kon, sesi.id, nomor, True), SEKARANG - 50)

    r = A.muat_ringkas(kon, anak, SEKARANG)

    assert r.berjalan.id == sesi.id and r.sisa_detik == 800 and r.terisi == frozenset({1, 2, 4}) and r.nomor_lanjut == 3


def test_semua_terisi_membuat_lanjutkan_ke_soal_satu(kon, anak):
    sesi = K.mulai_atau_lanjut(kon, anak, SEKARANG - 100, seed=1)
    for nomor in range(1, 11):
        K.simpan_jawaban(kon, anak, sesi.id, nomor, _jawaban(kon, sesi.id, nomor, True), SEKARANG - 50)

    assert A.muat_ringkas(kon, anak, SEKARANG).nomor_lanjut == 1


def test_nilai_terbaik_dan_terakhir_mengabaikan_sesi_asal_kumpul(kon, anak):
    _sesi_selesai(kon, anak, SEKARANG - 4000, LAMA_WAJAR, benar_sampai=6)           # sah, 6
    _sesi_selesai(kon, anak, SEKARANG - 3000, 60, benar_sampai=10)                   # asal kumpul (60 detik)
    _sesi_selesai(kon, anak, SEKARANG - 2000, LAMA_WAJAR, benar_sampai=10, terisi=2)  # asal kumpul (2 terisi)

    r = A.muat_ringkas(kon, anak, SEKARANG)

    assert r.nilai_terbaik == 6 and r.nilai_terakhir == 6
    assert len(r.riwayat) == 3 and [s.nilai for s in r.riwayat][-1] == 6           # terbaru dulu; yang tertua terakhir


def test_riwayat_menyertakan_asal_kumpul_terbaru_dulu_maksimal_lima(kon, anak):
    for i in range(7):
        _sesi_selesai(kon, anak, SEKARANG - 10_000 + i * 1000, LAMA_WAJAR, benar_sampai=i)

    r = A.muat_ringkas(kon, anak, SEKARANG)

    assert [s.nilai for s in r.riwayat] == [6, 5, 4, 3, 2]


def test_target_harian_menghitung_sesi_sah_yang_dimulai_hari_ini_wib(kon, anak):
    _sesi_selesai(kon, anak, KEMARIN_MALAM, LAMA_WAJAR)                              # kemarin: tidak dihitung
    _sesi_selesai(kon, anak, AWAL_HARI, LAMA_WAJAR)                                  # tepat 00.00 WIB: dihitung
    _sesi_selesai(kon, anak, AWAL_HARI + 1000, 30)                                    # asal kumpul: tidak dihitung
    _sesi_selesai(kon, anak, AWAL_HARI + 2000, LAMA_WAJAR, benar_sampai=3)

    assert A.muat_ringkas(kon, anak, SEKARANG).selesai_hari_ini == 2


def test_target_harian_berganti_hari_tepat_pada_tengah_malam_wib(kon, anak):
    _sesi_selesai(kon, anak, AWAL_HARI + 100, LAMA_WAJAR)

    assert A.muat_ringkas(kon, anak, AWAL_HARI + 200).selesai_hari_ini == 1
    assert A.muat_ringkas(kon, anak, AWAL_HARI + 86_400).selesai_hari_ini == 0


def test_sesi_berjalan_tidak_dihitung_sebagai_selesai_hari_ini(kon, anak):
    K.mulai_atau_lanjut(kon, anak, SEKARANG - 10, seed=1)

    assert A.muat_ringkas(kon, anak, SEKARANG).selesai_hari_ini == 0


def test_ringkasan_hanya_milik_anak_itu(kon, anak, anak_lain):
    _sesi_selesai(kon, anak_lain, SEKARANG - 4000, LAMA_WAJAR)

    r = A.muat_ringkas(kon, anak, SEKARANG)

    assert r.riwayat == () and r.nilai_terbaik is None and r.selesai_hari_ini == 0


def test_sesi_yang_waktunya_habis_ikut_riwayat_dan_bukan_lagi_berjalan(kon, anak):
    K.mulai_atau_lanjut(kon, anak, SEKARANG - 1000, seed=1)

    r = A.muat_ringkas(kon, anak, SEKARANG)

    assert r.berjalan is None and len(r.riwayat) == 1 and r.riwayat[0].status == K.WAKTU_HABIS


# --- perbandingan dengan latihan sebelumnya ------------------------------------------------------------------

def test_nilai_sebelumnya_memakai_sesi_sah_terdekat_sebelum_sesi_ini(kon, anak):
    pertama = _sesi_selesai(kon, anak, SEKARANG - 5000, LAMA_WAJAR, benar_sampai=4)
    _sesi_selesai(kon, anak, SEKARANG - 4000, 30, benar_sampai=10)                   # asal kumpul: dilewati
    ketiga = _sesi_selesai(kon, anak, SEKARANG - 3000, LAMA_WAJAR, benar_sampai=9)

    assert A.nilai_sebelumnya(kon, anak, ketiga, SEKARANG) == 4
    assert A.nilai_sebelumnya(kon, anak, pertama, SEKARANG) is None


def test_sesi_asal_kumpul_tidak_dibandingkan_sama_sekali(kon, anak):
    _sesi_selesai(kon, anak, SEKARANG - 5000, LAMA_WAJAR, benar_sampai=4)
    cepat = _sesi_selesai(kon, anak, SEKARANG - 4000, 30, benar_sampai=10)

    assert A.nilai_sebelumnya(kon, anak, cepat, SEKARANG) is None


def test_nilai_sebelumnya_tidak_menyentuh_sesi_anak_lain(kon, anak, anak_lain):
    _sesi_selesai(kon, anak_lain, SEKARANG - 5000, LAMA_WAJAR, benar_sampai=4)
    milik = _sesi_selesai(kon, anak, SEKARANG - 3000, LAMA_WAJAR, benar_sampai=9)

    assert A.nilai_sebelumnya(kon, anak, milik, SEKARANG) is None

