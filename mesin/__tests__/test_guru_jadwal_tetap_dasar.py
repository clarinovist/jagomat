"""Penyimpanan jadwal tetap guru: DB terpisah, append-only, usulan dan putusan (data sintetis)."""

import hashlib
import os
import sqlite3
import stat
from contextlib import closing

import pytest

import guru_jadwal_tetap_dasar as D

ID_GURU_A = "akun_" + "a" * 32
ID_GURU_B = "akun_" + "b" * 32
ID_ADMIN = "akun_" + "c" * 32
ID_ADMIN_LAIN = "akun_" + "d" * 32
BLOK_1 = "1@480-600"
BLOK_2 = "3@900-1020"
BLOK_3 = "5@540-600;6@540-600"
WAKTU_1 = "2026-12-01T09:00:00"
WAKTU_2 = "2026-12-01T09:30:00"
WAKTU_3 = "2026-12-01T10:00:00"
PESAN_TOLAK_UBAH = "hanya boleh ditambah"
VERSI_ASING = 7


def _blok_ke(indeks):
    """Blok yang berbeda untuk setiap indeks (selalu berbeda dari blok tetangganya)."""
    return f"1@{480 + 30 * indeks}-{540 + 30 * indeks}"


@pytest.fixture(autouse=True)
def env_ke_berkas_sintetis(tmp_path, monkeypatch):
    """Tidak ada tes yang boleh menyentuh DB sungguhan: env diarahkan ke berkas sementara."""
    monkeypatch.setenv(D.ENV_DB, str(tmp_path / "env-sintetis.db"))


@pytest.fixture
def berkas(tmp_path):
    return tmp_path / "guru-jadwal-tetap.db"


def _usul(path, **ubah):
    data = {"guru_akun": ID_GURU_A, "blok": BLOK_1, "dibuat": WAKTU_1, "path": path}
    return D.usul(**{**data, **ubah})


def _tetapkan(path, **ubah):
    data = {"guru_akun": ID_GURU_A, "blok": BLOK_2, "admin_akun": ID_ADMIN, "dibuat": WAKTU_2, "path": path}
    return D.tetapkan_admin(**{**data, **ubah})


def _putus(path, usulan_id, putusan="setuju", dibuat=WAKTU_3):
    return D.putus(usulan_id=usulan_id, putusan=putusan, admin_akun=ID_ADMIN, dibuat=dibuat, path=path)


def _id_menunggu(path, guru=ID_GURU_A):
    return D.menunggu(guru, path=path)["usulan_id"]


def _baca(path, sql, parameter=()):
    """Baca lewat mode=ro; berkas harus sudah ada (tes ini tidak boleh membuatnya)."""
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as kon:
        return kon.execute(sql, parameter).fetchall()


def _jumlah(path, tabel):
    return _baca(path, f"SELECT COUNT(*) FROM {tabel}")[0][0]


def _versi(path):
    return _baca(path, "PRAGMA user_version")[0][0]


def _tabel(path):
    sql = "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    return {baris[0] for baris in _baca(path, sql)}


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _coba_mulai_tulis(path):
    """Penulis lain mencoba memulai transaksi tulis tanpa menunggu; mengembalikan galatnya, None bila berhasil."""
    with closing(sqlite3.connect(str(path), timeout=0)) as kon:
        try:
            kon.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as err:
            return err
        kon.execute("ROLLBACK")
        return None


# --- berkas, skema, dan baca -------------------------------------------------------------

def test_berkas_dibuat_0600_pada_tulis_pertama(berkas):
    # Arrange
    assert not berkas.exists()

    # Act
    _usul(berkas)

    # Assert
    assert stat.S_IMODE(os.stat(berkas).st_mode) == 0o600


def test_skema_baru_memakai_versi_skema_dan_dua_tabel(berkas):
    # Act
    _usul(berkas)

    # Assert
    assert _versi(berkas) == D.VERSI_SKEMA == 1
    assert {"tetap_usulan", "tetap_putusan"} <= _tabel(berkas)


def test_baca_tidak_membuat_berkas(berkas):
    # Act / Assert
    assert D.aktif(ID_GURU_A, path=berkas) is None
    assert D.menunggu(ID_GURU_A, path=berkas) is None
    assert D.ditolak_terakhir(ID_GURU_A, path=berkas) is None
    assert D.riwayat(ID_GURU_A, path=berkas) == []
    assert D.aktif_semua(path=berkas) == {}
    assert D.menunggu_semua(path=berkas) == {}
    assert not berkas.exists()


def test_berkas_versi_nol_dibaca_sebagai_kosong_tanpa_diubah(berkas):
    # Arrange
    berkas.touch(mode=0o600)

    # Act
    hasil = D.aktif(ID_GURU_A, path=berkas)

    # Assert
    assert hasil is None
    assert berkas.stat().st_size == 0


def test_versi_asing_ditolak_pada_tulis_dan_baca_tanpa_mengubah_berkas(berkas):
    # Arrange
    with closing(sqlite3.connect(str(berkas))) as kon, kon:
        kon.execute(f"PRAGMA user_version = {VERSI_ASING}")
    hash_sebelum = _hash(berkas)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat_tulis:
        _usul(berkas)
    assert galat_tulis.value.kind == "umum"
    with pytest.raises(D.GalatTetap) as galat_baca:
        D.aktif(ID_GURU_A, path=berkas)
    assert galat_baca.value.kind == "umum"
    assert _versi(berkas) == VERSI_ASING
    assert _hash(berkas) == hash_sebelum


def test_path_env_dipakai_bila_argumen_path_tidak_diberikan(tmp_path, monkeypatch):
    # Arrange
    tujuan = tmp_path / "dari-env.db"
    monkeypatch.setenv(D.ENV_DB, str(tujuan))

    # Act
    D.usul(guru_akun=ID_GURU_A, blok=BLOK_1, dibuat=WAKTU_1)

    # Assert
    assert tujuan.exists()


def test_path_bawaan_berada_di_data_dengan_nama_berkas_resmi():
    # Act / Assert
    assert D.BERKAS_BAWAAN == "/data/guru-jadwal-tetap.db"
    assert D.ENV_DB == "GURU_JADWAL_TETAP_DB"


# --- symlink ----------------------------------------------------------------------------

def test_symlink_menggantung_ditolak_tulis_dan_tidak_membuat_sasaran(tmp_path):
    # Arrange
    sasaran = tmp_path / "sasaran.db"
    tautan = tmp_path / "tautan.db"
    tautan.symlink_to(sasaran)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        _usul(tautan)
    assert galat.value.kind == "umum"
    assert not sasaran.exists()
    assert tautan.is_symlink()


def test_symlink_ke_berkas_ada_ditolak_tulis_dan_sasaran_tidak_berubah(tmp_path):
    # Arrange
    sasaran = tmp_path / "sasaran.db"
    _usul(sasaran)
    tautan = tmp_path / "tautan.db"
    tautan.symlink_to(sasaran)
    hash_sebelum = _hash(sasaran)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        _usul(tautan, blok=BLOK_2, dibuat=WAKTU_2)
    assert galat.value.kind == "umum"
    assert _hash(sasaran) == hash_sebelum


def test_symlink_ditolak_pada_baca(tmp_path):
    # Arrange
    sasaran = tmp_path / "sasaran.db"
    _usul(sasaran)
    tautan = tmp_path / "tautan.db"
    tautan.symlink_to(sasaran)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        D.aktif(ID_GURU_A, path=tautan)
    assert galat.value.kind == "umum"


# --- append-only ------------------------------------------------------------------------

@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE tetap_usulan SET blok = '1@480-540'",
        "DELETE FROM tetap_usulan",
        "UPDATE tetap_putusan SET putusan = 'tolak'",
        "DELETE FROM tetap_putusan",
    ],
)
def test_trigger_menolak_ubah_dan_hapus_pada_kedua_tabel(berkas, sql):
    # Arrange
    _usul(berkas)
    _putus(berkas, usulan_id=1)

    # Act / Assert
    with closing(sqlite3.connect(str(berkas))) as kon:
        with pytest.raises(sqlite3.IntegrityError, match=PESAN_TOLAK_UBAH):
            kon.execute(sql)
    assert _jumlah(berkas, "tetap_usulan") == 1
    assert _jumlah(berkas, "tetap_putusan") == 1


# --- validasi sebelum berkas disentuh ---------------------------------------------------

@pytest.mark.parametrize(
    "ubah",
    [
        pytest.param({"guru_akun": "akun_" + "A" * 32}, id="guru-huruf-besar"),
        pytest.param({"guru_akun": "akun_" + "a" * 31}, id="guru-pendek"),
        pytest.param({"guru_akun": "kor_" + "a" * 32}, id="guru-prefiks-salah"),
        pytest.param({"guru_akun": None}, id="guru-none"),
        pytest.param({"blok": 7}, id="blok-bukan-teks"),
        pytest.param({"blok": "1@480-600 "}, id="blok-spasi"),
        pytest.param({"blok": "1@480:600"}, id="blok-karakter-asing"),
        pytest.param({"blok": "x@480-600"}, id="blok-huruf"),
        pytest.param({"blok": "1@" + "9" * 199}, id="blok-201-karakter"),
        pytest.param({"dibuat": "2026-12-01 09:00:00"}, id="dibuat-pakai-spasi"),
        pytest.param({"dibuat": "2026-12-01"}, id="dibuat-tanpa-jam"),
    ],
)
def test_argumen_usul_tidak_sah_ditolak_sebelum_berkas_dibuat(berkas, ubah):
    # Act / Assert
    with pytest.raises(ValueError):
        _usul(berkas, **ubah)
    assert not berkas.exists()


@pytest.mark.parametrize(
    "panggil",
    [
        pytest.param(
            lambda p: D.tetapkan_admin(guru_akun=ID_GURU_A, blok=BLOK_1, admin_akun="akun_X",
                                       dibuat=WAKTU_1, path=p),
            id="tetapkan-admin-tidak-sah",
        ),
        pytest.param(
            lambda p: D.putus(usulan_id=True, putusan="setuju", admin_akun=ID_ADMIN, dibuat=WAKTU_1, path=p),
            id="putus-id-bool",
        ),
        pytest.param(
            lambda p: D.putus(usulan_id=1, putusan="setuju", admin_akun="bukan-akun", dibuat=WAKTU_1, path=p),
            id="putus-admin-tidak-sah",
        ),
        pytest.param(
            lambda p: D.putus(usulan_id=1, putusan="batal", admin_akun=ID_ADMIN, dibuat=WAKTU_1, path=p),
            id="putus-putusan-asing",
        ),
        pytest.param(lambda p: D.aktif("bukan-akun", path=p), id="aktif-guru-tidak-sah"),
        pytest.param(lambda p: D.riwayat(ID_GURU_A, batas=0, path=p), id="riwayat-batas-nol"),
    ],
)
def test_argumen_tidak_sah_ditolak_tanpa_membuat_berkas(berkas, panggil):
    # Act / Assert
    with pytest.raises(ValueError):
        panggil(berkas)
    assert not berkas.exists()


def test_gagal_pada_tulis_pertama_tidak_meninggalkan_berkas_kosong(berkas, monkeypatch, tmp_path):
    """Berkas 0 byte tidak punya header SQLite: backup operasional akan menolaknya."""
    # Arrange
    def gagal_sisipkan(kon, *args):
        raise sqlite3.OperationalError("gangguan uji")

    monkeypatch.setattr(D, "_sisipkan_usulan", gagal_sisipkan)

    # Act / Assert
    with pytest.raises(D.GalatTetap):
        _usul(berkas)
    assert list(tmp_path.iterdir()) == []


# --- usul -------------------------------------------------------------------------------

def test_usul_pertama_menulis_dan_menjadi_menunggu(berkas):
    # Act
    hasil = _usul(berkas)

    # Assert
    assert hasil is True
    assert D.menunggu(ID_GURU_A, path=berkas)["blok"] == BLOK_1
    assert D.aktif(ID_GURU_A, path=berkas) is None


def test_usul_identik_dengan_menunggu_tidak_menulis(berkas):
    # Arrange
    _usul(berkas)
    hash_sebelum = _hash(berkas)

    # Act
    hasil = _usul(berkas, dibuat=WAKTU_2)

    # Assert
    assert hasil is False
    assert _hash(berkas) == hash_sebelum


def test_usul_identik_dengan_aktif_no_op_hanya_bila_tanpa_menunggu(berkas):
    # Arrange
    _usul(berkas)
    _putus(berkas, usulan_id=1)
    hash_sebelum = _hash(berkas)

    # Act / Assert
    assert _usul(berkas, dibuat=WAKTU_2) is False
    assert _hash(berkas) == hash_sebelum
    assert _usul(berkas, blok=BLOK_2, dibuat=WAKTU_2) is True
    assert _usul(berkas, blok=BLOK_1, dibuat=WAKTU_3) is True


def test_kirim_ulang_aktif_saat_menunggu_berbeda_menggantikan_menunggu(berkas):
    # Arrange
    _usul(berkas, blok=BLOK_1)
    _putus(berkas, usulan_id=1)
    _usul(berkas, blok=BLOK_2, dibuat=WAKTU_2)

    # Act
    hasil = _usul(berkas, blok=BLOK_1, dibuat=WAKTU_3)

    # Assert
    assert hasil is True
    assert D.menunggu(ID_GURU_A, path=berkas)["blok"] == BLOK_1
    assert D.menunggu(ID_GURU_A, path=berkas)["usulan_id"] == 3


def test_batas_sepuluh_usulan_dalam_24_jam_lalu_ditolak_tanpa_tulis(berkas):
    # Arrange
    assert D.BATAS_USULAN_PER_HARI == 10
    for indeks in range(10):
        assert _usul(berkas, blok=_blok_ke(indeks)) is True
    hash_sebelum = _hash(berkas)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        _usul(berkas, blok=_blok_ke(10))
    assert galat.value.kind == "batas"
    assert _hash(berkas) == hash_sebelum


def test_usulan_tepat_24_jam_lalu_tidak_dihitung_dan_satu_detik_sebelumnya_dihitung(berkas):
    # Arrange
    for indeks in range(10):
        _usul(berkas, blok=_blok_ke(indeks), dibuat=WAKTU_1)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        _usul(berkas, blok=_blok_ke(10), dibuat="2026-12-02T08:59:59")
    assert galat.value.kind == "batas"
    assert _usul(berkas, blok=_blok_ke(10), dibuat="2026-12-02T09:00:00") is True


def test_batas_tidak_menghitung_ketetapan_admin_dan_guru_lain(berkas):
    # Arrange
    for indeks in range(10):
        _tetapkan(berkas, blok=_blok_ke(indeks), dibuat=WAKTU_1)
        _usul(berkas, guru_akun=ID_GURU_B, blok=_blok_ke(indeks), dibuat=WAKTU_1)

    # Act / Assert
    assert _usul(berkas, blok=BLOK_1, dibuat=WAKTU_2) is True
    with pytest.raises(D.GalatTetap) as galat:
        _usul(berkas, guru_akun=ID_GURU_B, blok=_blok_ke(10), dibuat=WAKTU_2)
    assert galat.value.kind == "batas"


def test_usul_dengan_waktu_awal_tahun_satu_tidak_meledak(berkas):
    # Act / Assert
    assert _usul(berkas, dibuat="0001-01-01T00:00:00") is True


# --- putus ------------------------------------------------------------------------------

def test_putus_setuju_menjadikan_aktif_dan_mengosongkan_menunggu(berkas):
    # Arrange
    _usul(berkas)

    # Act
    _putus(berkas, usulan_id=1, putusan="setuju")

    # Assert
    aktif = D.aktif(ID_GURU_A, path=berkas)
    assert aktif == {
        "usulan_id": 1,
        "blok": BLOK_1,
        "asal": "guru",
        "oleh": ID_GURU_A,
        "dibuat": WAKTU_1,
        "diputus": WAKTU_3,
    }
    assert D.menunggu(ID_GURU_A, path=berkas) is None


def test_putus_tolak_mengisi_ditolak_terakhir(berkas):
    # Arrange
    _usul(berkas)

    # Act
    _putus(berkas, usulan_id=1, putusan="tolak")

    # Assert
    assert D.aktif(ID_GURU_A, path=berkas) is None
    assert D.menunggu(ID_GURU_A, path=berkas) is None
    assert D.ditolak_terakhir(ID_GURU_A, path=berkas) == {
        "usulan_id": 1,
        "blok": BLOK_1,
        "diputus": WAKTU_3,
    }


def test_usulan_tergantikan_tidak_bisa_diputus(berkas):
    # Arrange
    _usul(berkas, blok=BLOK_1)
    _usul(berkas, blok=BLOK_2, dibuat=WAKTU_2)
    hash_sebelum = _hash(berkas)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        _putus(berkas, usulan_id=1)
    assert galat.value.kind == "konflik"
    assert _hash(berkas) == hash_sebelum
    assert _id_menunggu(berkas) == 2


def test_usulan_tergantikan_tidak_muncul_lagi_setelah_penggantinya_ditolak(berkas):
    # Arrange
    _usul(berkas, blok=BLOK_1)
    _usul(berkas, blok=BLOK_2, dibuat=WAKTU_2)
    _putus(berkas, usulan_id=2, putusan="tolak")
    hash_sebelum = _hash(berkas)

    # Act / Assert
    assert D.menunggu(ID_GURU_A, path=berkas) is None
    assert D.ditolak_terakhir(ID_GURU_A, path=berkas)["usulan_id"] == 2
    with pytest.raises(D.GalatTetap) as galat:
        _putus(berkas, usulan_id=1)
    assert galat.value.kind == "konflik"
    assert _hash(berkas) == hash_sebelum


def test_putus_ganda_ditolak_sebagai_konflik(berkas):
    # Arrange
    _usul(berkas)
    _putus(berkas, usulan_id=1, putusan="setuju")
    hash_sebelum = _hash(berkas)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        _putus(berkas, usulan_id=1, putusan="tolak")
    assert galat.value.kind == "konflik"
    assert _hash(berkas) == hash_sebelum


def test_putus_usulan_asal_admin_ditolak_sebagai_konflik(berkas):
    # Arrange
    _tetapkan(berkas)
    hash_sebelum = _hash(berkas)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        _putus(berkas, usulan_id=1, putusan="tolak")
    assert galat.value.kind == "konflik"
    assert _hash(berkas) == hash_sebelum


def test_putus_usulan_tidak_ada_konflik_dan_tidak_membuat_berkas(berkas):
    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        _putus(berkas, usulan_id=5)
    assert galat.value.kind == "konflik"
    assert not berkas.exists()


def test_putus_usulan_tidak_ada_di_berkas_ada_konflik_tanpa_mengubah(berkas):
    # Arrange
    _usul(berkas)
    hash_sebelum = _hash(berkas)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        _putus(berkas, usulan_id=5)
    assert galat.value.kind == "konflik"
    assert _hash(berkas) == hash_sebelum


def test_cek_menunggu_dan_tulis_putusan_berjalan_dalam_satu_transaksi(berkas, monkeypatch):
    """Penulis lain tidak boleh masuk di antara cek 'masih menunggu' dan INSERT putusan."""
    # Arrange
    _usul(berkas)
    terkunci = []
    cek_asli = D._menunggu_kon

    def cek_lalu_coba_tulis_lain(kon, guru_akun, aktif):
        hasil = cek_asli(kon, guru_akun, aktif)
        terkunci.append(_coba_mulai_tulis(berkas))
        return hasil

    monkeypatch.setattr(D, "_menunggu_kon", cek_lalu_coba_tulis_lain)

    # Act
    _putus(berkas, usulan_id=1, putusan="setuju")

    # Assert
    assert len(terkunci) == 1
    assert isinstance(terkunci[0], sqlite3.OperationalError)
    assert D.aktif(ID_GURU_A, path=berkas)["usulan_id"] == 1


# --- tetapkan_admin ---------------------------------------------------------------------

def test_tetapkan_admin_tanpa_riwayat_menjadikan_aktif(berkas):
    # Act
    hasil = _tetapkan(berkas)

    # Assert
    assert hasil is True
    aktif = D.aktif(ID_GURU_A, path=berkas)
    assert aktif["asal"] == "admin"
    assert aktif["oleh"] == ID_ADMIN
    assert aktif["blok"] == BLOK_2
    assert D.menunggu(ID_GURU_A, path=berkas) is None


def test_tetapkan_admin_menggantikan_menunggu_dan_menunggu_lama_konflik(berkas):
    # Arrange
    _usul(berkas, blok=BLOK_1)

    # Act
    _tetapkan(berkas, blok=BLOK_2)

    # Assert
    assert D.menunggu(ID_GURU_A, path=berkas) is None
    with pytest.raises(D.GalatTetap) as galat:
        _putus(berkas, usulan_id=1)
    assert galat.value.kind == "konflik"


def test_tetapkan_admin_identik_aktif_tanpa_menunggu_tidak_menulis(berkas):
    # Arrange
    _tetapkan(berkas, blok=BLOK_1)
    hash_sebelum = _hash(berkas)

    # Act
    hasil = _tetapkan(berkas, blok=BLOK_1)

    # Assert
    assert hasil is False
    assert _hash(berkas) == hash_sebelum


def test_tetapkan_admin_gagal_di_tengah_tidak_menyisakan_usulan_yatim(berkas, monkeypatch):
    # Arrange
    _usul(berkas)

    def gagal_putusan(kon, *args):
        raise sqlite3.OperationalError("gangguan uji")

    monkeypatch.setattr(D, "_sisipkan_putusan", gagal_putusan)

    # Act / Assert
    with pytest.raises(D.GalatTetap) as galat:
        _tetapkan(berkas, blok=BLOK_2)
    assert galat.value.kind == "umum"
    assert _jumlah(berkas, "tetap_usulan") == 1
    assert _jumlah(berkas, "tetap_putusan") == 0
    assert D.aktif(ID_GURU_A, path=berkas) is None


# --- ditolak_terakhir, riwayat, dan daftar ----------------------------------------------

def test_ditolak_terakhir_hilang_setelah_ketetapan_admin_yang_lebih_baru(berkas):
    # Arrange
    _usul(berkas)
    _putus(berkas, usulan_id=1, putusan="tolak")

    # Act
    _tetapkan(berkas, blok=BLOK_2)

    # Assert
    assert D.ditolak_terakhir(ID_GURU_A, path=berkas) is None


def test_riwayat_urut_terbaru_dan_memuat_putusan(berkas):
    # Arrange
    _usul(berkas, blok=BLOK_1, dibuat=WAKTU_1)
    _usul(berkas, blok=BLOK_2, dibuat=WAKTU_2)
    _putus(berkas, usulan_id=2, putusan="setuju", dibuat=WAKTU_3)

    # Act
    hasil = D.riwayat(ID_GURU_A, path=berkas)

    # Assert
    assert hasil == [
        {
            "usulan_id": 2,
            "blok": BLOK_2,
            "asal": "guru",
            "oleh": ID_GURU_A,
            "dibuat": WAKTU_2,
            "putusan": "setuju",
            "diputus_oleh": ID_ADMIN,
            "diputus": WAKTU_3,
        },
        {
            "usulan_id": 1,
            "blok": BLOK_1,
            "asal": "guru",
            "oleh": ID_GURU_A,
            "dibuat": WAKTU_1,
            "putusan": None,
            "diputus_oleh": None,
            "diputus": None,
        },
    ]


def test_riwayat_menghormati_batas(berkas):
    # Arrange
    _usul(berkas, blok=BLOK_1)
    _usul(berkas, blok=BLOK_2, dibuat=WAKTU_2)

    # Act
    hasil = D.riwayat(ID_GURU_A, batas=1, path=berkas)

    # Assert
    assert [baris["usulan_id"] for baris in hasil] == [2]


def test_aktif_semua_dan_menunggu_semua_memuat_guru_yang_relevan(berkas):
    # Arrange
    _usul(berkas, guru_akun=ID_GURU_A)
    _putus(berkas, usulan_id=1, putusan="setuju")
    _usul(berkas, guru_akun=ID_GURU_B, blok=BLOK_2, dibuat=WAKTU_2)

    # Act
    aktif_semua = D.aktif_semua(path=berkas)
    menunggu_semua = D.menunggu_semua(path=berkas)

    # Assert
    assert set(aktif_semua) == {ID_GURU_A}
    assert aktif_semua[ID_GURU_A]["blok"] == BLOK_1
    assert set(menunggu_semua) == {ID_GURU_B}
    assert menunggu_semua[ID_GURU_B]["blok"] == BLOK_2


def test_blok_gabungan_disimpan_apa_adanya(berkas):
    # Arrange
    _tetapkan(berkas, blok=BLOK_3)

    # Act / Assert
    assert D.aktif(ID_GURU_A, path=berkas)["blok"] == BLOK_3
