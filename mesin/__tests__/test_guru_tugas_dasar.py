"""Penyimpanan tugas guru: DB terpisah, append-only, baca tanpa membuat berkas (data sintetis)."""

import os
import sqlite3
import stat
from contextlib import closing

import pytest

import guru_tugas_dasar as D

ID_GURU_A = "akun_" + "a" * 32
ID_GURU_B = "akun_" + "b" * 32
SISWA_A = 11
SISWA_B = 22
SESI_1 = 101
SESI_2 = 102
SESI_3 = 103
TOPIK = "pola-bilangan"
TOPIK_LAIN = "kombinatorik"
TENGGAT = "2026-12-05"
DIBUAT = "2026-12-01T09:00:00"
DIBUAT_LAIN = "2026-12-01T09:30:00"
PESAN_TOLAK_UBAH = "hanya boleh ditambah"
VERSI_ASING = 7


@pytest.fixture(autouse=True)
def env_ke_berkas_sintetis(tmp_path, monkeypatch):
    """Tidak ada tes yang boleh menyentuh DB sungguhan: env diarahkan ke berkas sementara."""
    monkeypatch.setenv(D.ENV_DB, str(tmp_path / "env-sintetis.db"))


@pytest.fixture
def berkas(tmp_path):
    return tmp_path / "guru-tugas.db"


def _catat(path, **ubah):
    data = {
        "sesi_id": SESI_1,
        "siswa_id": SISWA_A,
        "guru_akun": ID_GURU_A,
        "topik": TOPIK,
        "tenggat": TENGGAT,
        "dibuat": DIBUAT,
        "path": path,
    }
    return D.catat(**{**data, **ubah})


def _baca(path, sql, parameter=()):
    """Baca lewat mode=ro; berkas harus sudah ada (tes ini tidak boleh membuatnya)."""
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as kon:
        return kon.execute(sql, parameter).fetchall()


def _jumlah(path):
    return _baca(path, "SELECT COUNT(*) FROM tugas_guru")[0][0]


def _versi(path):
    return _baca(path, "PRAGMA user_version")[0][0]


def _tabel(path):
    sql = "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    return {baris[0] for baris in _baca(path, sql)}


def _insert_mentah(path, baris):
    kolom = tuple(baris)
    tanda_tanya = ", ".join(["?"] * len(kolom))
    sql = "INSERT INTO tugas_guru (" + ", ".join(kolom) + ") VALUES (" + tanda_tanya + ")"
    with closing(sqlite3.connect(str(path))) as kon, kon:
        kon.execute(sql, [baris[k] for k in kolom])


# --- berkas, skema, dan baca -------------------------------------------------------------

def test_berkas_dibuat_0600_pada_tulis_pertama(berkas):
    # Arrange
    assert not berkas.exists()

    # Act
    _catat(berkas)

    # Assert
    assert stat.S_IMODE(os.stat(berkas).st_mode) == 0o600


def test_catat_mengembalikan_id_baris_yang_ditulis(berkas):
    # Act
    id_baru = _catat(berkas)

    # Assert
    assert type(id_baru) is int and id_baru == 1


def test_skema_baru_memakai_versi_skema_dan_tabel_tugas(berkas):
    # Act
    _catat(berkas)

    # Assert
    assert _versi(berkas) == D.VERSI_SKEMA == 1
    assert set(D.TABEL_SKEMA) <= _tabel(berkas)


def test_daftar_siswa_dan_daftar_guru_tidak_membuat_berkas(berkas):
    # Act
    siswa = D.daftar_siswa(SISWA_A, path=berkas)
    guru = D.daftar_guru(ID_GURU_A, path=berkas)

    # Assert
    assert siswa == []
    assert guru == []
    assert not berkas.exists()


def test_daftar_pada_berkas_kosong_versi_nol_tidak_mengubah_berkas(berkas):
    # Arrange
    berkas.touch(mode=0o600)

    # Act
    hasil = D.daftar_siswa(SISWA_A, path=berkas)

    # Assert
    assert hasil == []
    assert berkas.stat().st_size == 0


def test_versi_skema_asing_ditolak_dan_tidak_mengubah_berkas(berkas):
    # Arrange
    with closing(sqlite3.connect(str(berkas))) as kon, kon:
        kon.execute(f"PRAGMA user_version = {VERSI_ASING}")

    # Act / Assert
    with pytest.raises(D.GalatTugas):
        _catat(berkas)
    with pytest.raises(D.GalatTugas):
        D.daftar_siswa(SISWA_A, path=berkas)
    with pytest.raises(D.GalatTugas):
        D.daftar_guru(ID_GURU_A, path=berkas)
    assert _versi(berkas) == VERSI_ASING
    assert _tabel(berkas) == set()


def test_versi_asing_ditolak_saat_baca_walau_tabel_sudah_ada(berkas):
    """Tanpa cek versi, SELECT pada tabel yang ada akan berhasil; hanya cek versi yang boleh menolaknya."""
    # Arrange
    _catat(berkas)
    with closing(sqlite3.connect(str(berkas))) as kon, kon:
        kon.execute(f"PRAGMA user_version = {VERSI_ASING}")

    # Act / Assert
    with pytest.raises(D.GalatTugas):
        D.daftar_siswa(SISWA_A, path=berkas)
    with pytest.raises(D.GalatTugas):
        D.daftar_guru(ID_GURU_A, path=berkas)
    assert _jumlah(berkas) == 1


def test_path_env_dipakai_bila_argumen_path_tidak_diberikan(tmp_path, monkeypatch):
    # Arrange
    tujuan = tmp_path / "dari-env.db"
    monkeypatch.setenv(D.ENV_DB, str(tujuan))

    # Act
    D.catat(sesi_id=SESI_1, siswa_id=SISWA_A, guru_akun=ID_GURU_A, topik=TOPIK,
            tenggat=TENGGAT, dibuat=DIBUAT)

    # Assert
    assert tujuan.exists()


def test_path_bawaan_berada_di_data_dengan_nama_berkas_resmi():
    # Act / Assert
    assert D.BERKAS_BAWAAN == "/data/guru-tugas.db"
    assert D.ENV_DB == "GURU_TUGAS_DB"


# --- catat dan baca ---------------------------------------------------------------------

def test_daftar_siswa_hanya_memuat_tugas_milik_siswa_itu_urut_terbaru(berkas):
    # Arrange
    _catat(berkas, sesi_id=SESI_1, siswa_id=SISWA_A)
    _catat(berkas, sesi_id=SESI_2, siswa_id=SISWA_B)
    _catat(berkas, sesi_id=SESI_3, siswa_id=SISWA_A, topik=TOPIK_LAIN)

    # Act
    hasil = D.daftar_siswa(SISWA_A, path=berkas)

    # Assert
    assert [baris["sesi_id"] for baris in hasil] == [SESI_3, SESI_1]
    assert all(baris["siswa_id"] == SISWA_A for baris in hasil)


def test_daftar_guru_hanya_memuat_tugas_milik_guru_itu_urut_terbaru(berkas):
    # Arrange
    _catat(berkas, sesi_id=SESI_1, guru_akun=ID_GURU_A)
    _catat(berkas, sesi_id=SESI_2, guru_akun=ID_GURU_B, siswa_id=SISWA_B)
    _catat(berkas, sesi_id=SESI_3, guru_akun=ID_GURU_A, siswa_id=SISWA_B)

    # Act
    hasil = D.daftar_guru(ID_GURU_A, path=berkas)

    # Assert
    assert [baris["sesi_id"] for baris in hasil] == [SESI_3, SESI_1]
    assert all(baris["guru_akun"] == ID_GURU_A for baris in hasil)


def test_baris_baca_memuat_kunci_tepat_tujuh_tanpa_data_lain(berkas):
    # Arrange
    _catat(berkas)

    # Act
    baris = D.daftar_siswa(SISWA_A, path=berkas)[0]

    # Assert
    assert set(baris) == {"id", "sesi_id", "siswa_id", "guru_akun", "topik", "tenggat", "dibuat"}
    assert baris == {
        "id": 1,
        "sesi_id": SESI_1,
        "siswa_id": SISWA_A,
        "guru_akun": ID_GURU_A,
        "topik": TOPIK,
        "tenggat": TENGGAT,
        "dibuat": DIBUAT,
    }


def test_tenggat_none_disimpan_dan_dibaca_sebagai_none(berkas):
    # Arrange
    _catat(berkas, tenggat=None)

    # Act / Assert
    assert D.daftar_siswa(SISWA_A, path=berkas)[0]["tenggat"] is None


def test_sesi_id_ganda_ditolak_dan_baris_pertama_tetap(berkas):
    # Arrange
    _catat(berkas)

    # Act / Assert
    with pytest.raises(D.GalatTugas) as galat:
        _catat(berkas, topik=TOPIK_LAIN, dibuat=DIBUAT_LAIN)
    assert isinstance(galat.value.__cause__, sqlite3.IntegrityError)
    assert _jumlah(berkas) == 1
    assert D.daftar_siswa(SISWA_A, path=berkas)[0]["topik"] == TOPIK


def test_galat_tulis_tidak_membocorkan_path_di_pesan(berkas):
    # Arrange
    _catat(berkas)

    # Act / Assert
    with pytest.raises(D.GalatTugas) as galat:
        _catat(berkas, sesi_id=SESI_1, topik=TOPIK_LAIN)
    assert str(berkas) not in str(galat.value)


# --- append-only ------------------------------------------------------------------------

@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE tugas_guru SET topik = 'kombinatorik'",
        "DELETE FROM tugas_guru",
    ],
)
def test_trigger_menolak_ubah_dan_hapus(berkas, sql):
    # Arrange
    _catat(berkas)

    # Act / Assert
    with closing(sqlite3.connect(str(berkas))) as kon:
        with pytest.raises(sqlite3.IntegrityError, match=PESAN_TOLAK_UBAH):
            kon.execute(sql)
    assert _jumlah(berkas) == 1


# --- validasi sebelum berkas disentuh ---------------------------------------------------

@pytest.mark.parametrize(
    "ubah",
    [
        pytest.param({"sesi_id": 0}, id="sesi-id-nol"),
        pytest.param({"sesi_id": True}, id="sesi-id-bool"),
        pytest.param({"sesi_id": "101"}, id="sesi-id-teks"),
        pytest.param({"siswa_id": 0}, id="siswa-id-nol"),
        pytest.param({"siswa_id": False}, id="siswa-id-bool"),
        pytest.param({"guru_akun": "akun_" + "A" * 32}, id="guru-huruf-besar"),
        pytest.param({"guru_akun": "akun_" + "a" * 31}, id="guru-pendek"),
        pytest.param({"guru_akun": "kor_" + "a" * 32}, id="guru-prefiks-salah"),
        pytest.param({"guru_akun": None}, id="guru-none"),
        pytest.param({"topik": "campuran"}, id="topik-campuran"),
        pytest.param({"topik": "topik-acak-xyz"}, id="topik-tidak-dikenal"),
        pytest.param({"topik": ""}, id="topik-kosong"),
        pytest.param({"topik": 7}, id="topik-bukan-teks"),
        pytest.param({"tenggat": "2026-2-3"}, id="tenggat-tidak-padat"),
        pytest.param({"tenggat": "2026-02-30"}, id="tenggat-tidak-ada"),
        pytest.param({"dibuat": "2026-12-01 09:00:00"}, id="dibuat-pakai-spasi"),
        pytest.param({"dibuat": "2026-12-01"}, id="dibuat-tanpa-jam"),
    ],
)
def test_argumen_tidak_sah_ditolak_sebelum_berkas_dibuat(berkas, ubah):
    # Act / Assert
    with pytest.raises(ValueError):
        _catat(berkas, **ubah)
    assert not berkas.exists()


# --- galat tulis pertama dan berkas kosong ----------------------------------------------

def test_gagal_pada_tulis_pertama_tidak_meninggalkan_berkas_kosong(berkas, monkeypatch, tmp_path):
    """Berkas 0 byte tidak punya header SQLite: backup operasional akan menolaknya."""
    # Arrange
    def gagal_sisipkan(kon, catatan):
        raise sqlite3.OperationalError("gangguan uji")

    monkeypatch.setattr(D, "_sisipkan_tugas", gagal_sisipkan)

    # Act / Assert
    with pytest.raises(D.GalatTugas):
        _catat(berkas)
    assert list(tmp_path.iterdir()) == []


def test_gagal_pada_berkas_yang_sudah_ada_tidak_menghapusnya(berkas, monkeypatch):
    # Arrange
    _catat(berkas)
    ukuran = berkas.stat().st_size

    def gagal_sisipkan(kon, catatan):
        raise sqlite3.OperationalError("gangguan uji")

    monkeypatch.setattr(D, "_sisipkan_tugas", gagal_sisipkan)

    # Act / Assert
    with pytest.raises(D.GalatTugas):
        _catat(berkas, sesi_id=SESI_2)
    assert berkas.exists() and berkas.stat().st_size == ukuran


def test_berkas_kosong_yang_dipegang_penulis_lain_tidak_dibuang(berkas, monkeypatch):
    """Penulis lain sudah BEGIN IMMEDIATE pada berkas 0 byte yang baru dibuat catat(): pembersihan harus melewatinya."""
    penulis = []
    siapkan_asli = D._siapkan_berkas

    def siapkan_lalu_tahan(tujuan):
        dibuat = siapkan_asli(tujuan)
        kon = sqlite3.connect(str(tujuan), timeout=0)
        kon.execute("BEGIN IMMEDIATE")
        penulis.append(kon)
        return dibuat

    def gagal_sisipkan(kon, tugas):
        raise sqlite3.OperationalError("gangguan uji")

    monkeypatch.setattr(D, "_siapkan_berkas", siapkan_lalu_tahan)
    monkeypatch.setattr(D, "_sisipkan_tugas", gagal_sisipkan)
    monkeypatch.setattr(D, "TIMEOUT_DETIK", 0.0)
    try:
        with pytest.raises(D.GalatTugas):
            _catat(berkas)
        assert berkas.exists()
    finally:
        penulis[0].close()


# --- validasi baca ----------------------------------------------------------------------

@pytest.mark.parametrize(
    ("fungsi", "argumen"),
    [
        pytest.param(D.daftar_siswa, 0, id="siswa-id-nol"),
        pytest.param(D.daftar_siswa, True, id="siswa-id-bool"),
        pytest.param(D.daftar_guru, "akun_" + "A" * 32, id="guru-huruf-besar"),
        pytest.param(D.daftar_guru, None, id="guru-none"),
    ],
)
def test_daftar_menolak_argumen_tidak_sah_tanpa_membuat_berkas(berkas, fungsi, argumen):
    # Act / Assert
    with pytest.raises(ValueError):
        fungsi(argumen, path=berkas)
    assert not berkas.exists()


# --- CHECK skema di sisi DB (INSERT mentah, melewati validasi Python) -------------------

_BARIS_SAH = {
    "sesi_id": SESI_2,
    "siswa_id": SISWA_A,
    "guru_akun": ID_GURU_A,
    "topik": TOPIK,
    "tenggat": TENGGAT,
    "dibuat": DIBUAT,
}


def test_baris_mentah_yang_sah_diterima_oleh_check_skema(berkas):
    # Arrange
    _catat(berkas)

    # Act
    _insert_mentah(berkas, _BARIS_SAH)

    # Assert
    assert _jumlah(berkas) == 2


@pytest.mark.parametrize(
    "ubah",
    [
        pytest.param({"sesi_id": SESI_1}, id="sesi-ganda"),
        pytest.param({"sesi_id": 0}, id="sesi-id-nol"),
        pytest.param({"siswa_id": 0}, id="siswa-id-nol"),
        pytest.param({"guru_akun": "akun_" + "A" * 32}, id="guru-huruf-besar"),
        pytest.param({"guru_akun": "kor_" + "a" * 32}, id="guru-prefiks-salah"),
        pytest.param({"topik": ""}, id="topik-kosong"),
        pytest.param({"topik": "t" * 65}, id="topik-65-karakter"),
        pytest.param({"tenggat": "2026-2-3"}, id="tenggat-tidak-padat"),
        pytest.param({"tenggat": "2026-AA-01"}, id="tenggat-huruf"),
        pytest.param({"dibuat": "2026-12-01 09:00:00"}, id="dibuat-pakai-spasi"),
        pytest.param({"dibuat": "2026-12-01T9:00:00"}, id="dibuat-jam-tidak-padat"),
    ],
)
def test_check_skema_menolak_baris_mentah_yang_tidak_sah(berkas, ubah):
    # Arrange
    _catat(berkas)
    baris = {**_BARIS_SAH, **ubah}

    # Act / Assert
    with pytest.raises(sqlite3.IntegrityError):
        _insert_mentah(berkas, baris)
    assert _jumlah(berkas) == 1


def test_tenggat_null_diterima_oleh_check_skema(berkas):
    # Arrange
    _catat(berkas)

    # Act
    _insert_mentah(berkas, {**_BARIS_SAH, "tenggat": None})

    # Assert
    assert _jumlah(berkas) == 2
