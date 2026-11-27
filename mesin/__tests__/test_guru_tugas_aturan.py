"""Aturan murni tugas guru: gerbang rilis, validasi tenggat, dan daftar topik yang boleh ditugaskan (data sintetis)."""

from datetime import date, datetime

import pytest

import guru_pertemuan_aturan as pertemuan
import guru_tugas_aturan as A
import school_numbers_versions

HARI_INI = date(2026, 12, 1)
TOPIK_BIASA = "pola-bilangan"
TOPIK_DASAR = "bilangan-dasar"
TOPIK_MANUAL = "matematika-awal"


@pytest.fixture(autouse=True)
def env_materi_bawaan(monkeypatch):
    """Nilai bawaan: materi dasar tertutup. Tes yang butuh keadaan lain menyetelnya sendiri."""
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)


# --- gerbang rilis ----------------------------------------------------------------------

def test_gerbang_rilis_mati_secara_bawaan():
    # Act / Assert
    assert A.GURU_TUGAS_AKTIF is False
    assert A.guru_tugas_aktif() is False


def test_gerbang_dibaca_saat_dipanggil_bukan_saat_impor(monkeypatch):
    # Arrange
    monkeypatch.setattr(A, "GURU_TUGAS_AKTIF", True)

    # Act / Assert
    assert A.guru_tugas_aktif() is True


@pytest.mark.parametrize("nilai", [1, "True", None])
def test_gerbang_hanya_menerima_bool_true_sebagai_aktif(monkeypatch, nilai):
    # Arrange
    monkeypatch.setattr(A, "GURU_TUGAS_AKTIF", nilai)

    # Act / Assert
    assert A.guru_tugas_aktif() is False


# --- baca_tenggat -----------------------------------------------------------------------

@pytest.mark.parametrize("kosong", [None, "", "   ", "\t"])
def test_tenggat_kosong_atau_spasi_menjadi_none(kosong):
    # Act / Assert
    assert A.baca_tenggat(kosong, HARI_INI) is None


def test_tenggat_hari_ini_diterima():
    # Act / Assert
    assert A.baca_tenggat("2026-12-01", HARI_INI) == "2026-12-01"


def test_tenggat_tepat_enam_puluh_hari_ke_depan_diterima():
    # Arrange: 1 Des 2026 + 60 hari = 30 Jan 2027
    # Act / Assert
    assert A.baca_tenggat("2027-01-30", HARI_INI) == "2027-01-30"


def test_tenggat_kemarin_ditolak():
    # Act / Assert
    with pytest.raises(ValueError):
        A.baca_tenggat("2026-11-30", HARI_INI)


def test_tenggat_enam_puluh_satu_hari_ke_depan_ditolak():
    # Arrange: 1 Des 2026 + 61 hari = 31 Jan 2027
    # Act / Assert
    with pytest.raises(ValueError):
        A.baca_tenggat("2027-01-31", HARI_INI)


@pytest.mark.parametrize(
    "teks",
    [
        pytest.param("2026-2-3", id="bulan-hari-tidak-padat"),
        pytest.param("2026-12-1", id="hari-tidak-padat"),
        pytest.param("20261201", id="bentuk-dasar-iso-tanpa-pemisah"),
        pytest.param("2026-W49-2", id="bentuk-minggu-iso"),
        pytest.param("2026-12-01\n", id="ada-newline"),
        pytest.param(" 2026-12-01", id="ada-spasi-depan"),
        pytest.param("2026/12/01", id="pemisah-garis-miring"),
        pytest.param("01-12-2026", id="urutan-hari-dulu"),
        pytest.param("２０２６-１２-０１", id="digit-lebar-penuh"),
        pytest.param("٢٠٢٦-١٢-٠١", id="digit-arab-timur"),
        pytest.param("2026-12-32", id="hari-tidak-ada"),
        pytest.param("2026-02-30", id="tanggal-februari-tidak-ada"),
        pytest.param("2026-13-01", id="bulan-tiga-belas"),
        pytest.param(20261201, id="bukan-teks"),
    ],
)
def test_format_tenggat_yang_tidak_tepat_ditolak(teks):
    # Act / Assert
    with pytest.raises(ValueError):
        A.baca_tenggat(teks, HARI_INI)


def test_hari_ini_harus_date_bukan_datetime():
    # Act / Assert
    with pytest.raises(ValueError):
        A.baca_tenggat("2026-12-01", datetime(2026, 12, 1))


# --- daftar topik tugas -----------------------------------------------------------------

def test_daftar_topik_tugas_berisi_pasangan_id_dan_label_resmi():
    # Act
    daftar = A.daftar_topik_tugas()

    # Assert
    assert all(type(id_topik) is str and type(label) is str for id_topik, label in daftar)
    assert (TOPIK_BIASA, pertemuan.label_topik(TOPIK_BIASA)) in daftar


def test_daftar_topik_tugas_tanpa_paket_sintetis_campuran():
    # Act
    ids = [id_topik for id_topik, _ in A.daftar_topik_tugas()]

    # Assert
    assert pertemuan.TOPIK_SINTETIS not in ids
    assert "campuran" not in ids


def test_materi_dasar_tertutup_saat_env_bawaan():
    # Act
    ids = [id_topik for id_topik, _ in A.daftar_topik_tugas()]

    # Assert
    assert TOPIK_DASAR not in ids


def test_materi_dasar_masuk_saat_env_menyalakan_materi(monkeypatch):
    # Arrange
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")

    # Act
    ids = [id_topik for id_topik, _ in A.daftar_topik_tugas()]

    # Assert
    assert TOPIK_DASAR in ids


def test_env_materi_tidak_sah_melempar_galat_bukan_daftar_kosong(monkeypatch):
    """Sama seperti daftar_topik_latihan: env salah harus terlihat, tidak menyembunyikan semua topik diam-diam."""
    # Arrange
    monkeypatch.setenv("OSN_MATERI_DASAR", "2")

    # Act / Assert
    with pytest.raises(ValueError):
        A.daftar_topik_tugas()
    with pytest.raises(ValueError):
        A.topik_tugas_sah(TOPIK_BIASA)


def test_topik_yang_ditolak_palang_buka_tidak_masuk_daftar(monkeypatch):
    # Arrange
    monkeypatch.setattr(school_numbers_versions, "topik_dibuka", lambda id_topik: id_topik != TOPIK_BIASA)

    # Act
    ids = [id_topik for id_topik, _ in A.daftar_topik_tugas()]

    # Assert
    assert TOPIK_BIASA not in ids


def test_topik_manual_saja_tetap_boleh_ditugaskan():
    """Keputusan rancangan: topik hanya_manual dipilih guru sendiri, jadi tidak disaring di sini."""
    # Act
    ids = [id_topik for id_topik, _ in A.daftar_topik_tugas()]

    # Assert
    assert TOPIK_MANUAL in ids


def test_daftar_topik_tugas_selalu_salinan_baru():
    # Arrange
    pertama = A.daftar_topik_tugas()

    # Act
    pertama.clear()

    # Assert
    assert A.daftar_topik_tugas() != []


@pytest.mark.parametrize(
    ("nilai", "sah"),
    [
        pytest.param(TOPIK_BIASA, True, id="topik-biasa"),
        pytest.param(TOPIK_MANUAL, True, id="topik-manual-saja"),
        pytest.param("campuran", False, id="paket-sintetis"),
        pytest.param(TOPIK_DASAR, False, id="materi-dasar-tertutup"),
        pytest.param("topik-acak-xyz", False, id="id-tidak-dikenal"),
        pytest.param("", False, id="kosong"),
        pytest.param(None, False, id="none"),
        pytest.param(7, False, id="bukan-teks"),
    ],
)
def test_topik_tugas_sah_hanya_untuk_id_dalam_daftar(nilai, sah):
    # Act / Assert
    assert A.topik_tugas_sah(nilai) is sah


# --- status tenggat (label saja, keputusan Pemilik T4) ----------------------------------

def test_status_tenggat_tanpa_tenggat():
    # Act / Assert
    assert A.status_tenggat(None, HARI_INI) == A.TENGGAT_TANPA


def test_status_tenggat_hari_tenggat_masih_berjalan():
    # Arrange
    tenggat = HARI_INI.isoformat()

    # Act / Assert
    assert A.status_tenggat(tenggat, HARI_INI) == A.TENGGAT_BERJALAN


def test_status_tenggat_masa_depan_berjalan():
    # Act / Assert
    assert A.status_tenggat("2026-12-02", HARI_INI) == A.TENGGAT_BERJALAN


def test_status_tenggat_kemarin_lewat():
    # Act / Assert
    assert A.status_tenggat("2026-11-30", HARI_INI) == A.TENGGAT_LEWAT


@pytest.mark.parametrize("rusak", ["", "2026-2-3", "20261201", 20261201, b"2026-12-01"])
def test_status_tenggat_bentuk_rusak_ditolak(rusak):
    # Act / Assert
    with pytest.raises(ValueError):
        A.status_tenggat(rusak, HARI_INI)


def test_status_tenggat_hari_ini_harus_date_murni():
    # Act / Assert
    with pytest.raises(ValueError):
        A.status_tenggat("2026-12-01", datetime(2026, 12, 1, 8, 0, 0))
