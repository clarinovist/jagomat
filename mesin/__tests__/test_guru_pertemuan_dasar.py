"""Penyimpanan catatan pertemuan guru: DB terpisah, append-only, snapshot mulai, atomik (data sintetis)."""

import os
import sqlite3
import stat
from contextlib import closing

import pytest

import guru_pertemuan_dasar as D

ID_GURU = "akun_" + "a" * 32
ID_ADMIN = "akun_" + "b" * 32
KUNCI = "klp_" + "c" * 32 + ":1"
KUNCI_LAIN = "kor_" + "d" * 32 + ":2"
MULAI = "2026-11-10T10:00:00"
MULAI_LAIN = "2026-11-12T10:00:00"
PADA = "2026-11-10T10:30:00"
PADA_LAIN = "2026-11-10T10:45:00"
TOPIK = "pola-bilangan"
TOPIK_LAIN = "kombinatorik"
ORDER_A = "kor_" + "1" * 32
ORDER_B = "kor_" + "2" * 32
HADIR_AWAL = {ORDER_A: "hadir"}
JUMLAH_PASANGAN_UJI = 450
PESAN_TOLAK_UBAH = "hanya boleh ditambah"


@pytest.fixture(autouse=True)
def env_ke_berkas_sintetis(tmp_path, monkeypatch):
    """Tidak ada tes yang boleh menyentuh DB sungguhan: env diarahkan ke berkas sementara."""
    monkeypatch.setenv(D.ENV_DB, str(tmp_path / "env-sintetis.db"))


@pytest.fixture
def berkas(tmp_path):
    return tmp_path / "guru-pertemuan.db"


def _data(path, **ubah):
    data = {
        "kunci": KUNCI,
        "pertemuan_id": 1,
        "mulai": MULAI,
        "topik": TOPIK,
        "hadir": HADIR_AWAL,
        "oleh": ID_GURU,
        "peran": "guru",
        "pada": PADA,
        "path": path,
    }
    return {**data, **ubah}


def _catat(path, **ubah):
    return D.catat(**_data(path, **ubah))


def _baca(path, sql, parameter=()):
    """Baca lewat mode=ro; berkas harus sudah ada (tes ini tidak boleh membuatnya)."""
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as kon:
        return kon.execute(sql, parameter).fetchall()


def _jumlah(path, tabel):
    return _baca(path, "SELECT COUNT(*) FROM " + tabel)[0][0]


def _versi(path):
    return _baca(path, "PRAGMA user_version")[0][0]


def _tabel(path):
    sql = "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    return {baris[0] for baris in _baca(path, sql)}


# --- berkas, skema, dan baca -------------------------------------------------------------

def test_berkas_belum_ada_sebelum_tulis_pertama_lalu_dibuat_0600(berkas):
    # Arrange
    assert not berkas.exists()

    # Act
    _catat(berkas)

    # Assert
    assert stat.S_IMODE(os.stat(berkas).st_mode) == 0o600


def test_terkini_dan_punya_jurnal_tidak_membuat_berkas(berkas):
    # Arrange / Act
    keadaan = D.terkini(KUNCI, MULAI, path=berkas)
    sudah = D.punya_jurnal([(KUNCI, MULAI)], path=berkas)

    # Assert
    assert keadaan == {"topik": None, "hadir": {}}
    assert sudah == set()
    assert not berkas.exists()


def test_skema_baru_memakai_versi_satu_dengan_kedua_tabel(berkas):
    # Arrange / Act
    _catat(berkas)

    # Assert
    assert _versi(berkas) == D.VERSI_SKEMA == 1
    assert set(D.TABEL_SKEMA) <= _tabel(berkas)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE pertemuan_jurnal SET topik = 'kombinatorik'",
        "DELETE FROM pertemuan_jurnal",
        "UPDATE pertemuan_hadir SET status = 'izin'",
        "DELETE FROM pertemuan_hadir",
    ],
)
def test_trigger_menolak_ubah_dan_hapus_pada_kedua_tabel(berkas, sql):
    # Arrange
    _catat(berkas)

    # Act / Assert
    with closing(sqlite3.connect(str(berkas))) as kon:
        with pytest.raises(sqlite3.IntegrityError, match=PESAN_TOLAK_UBAH):
            kon.execute(sql)
    assert _jumlah(berkas, "pertemuan_jurnal") == 1
    assert _jumlah(berkas, "pertemuan_hadir") == 1


def test_versi_skema_asing_ditolak_saat_catat_terkini_dan_punya_jurnal(berkas):
    # Arrange
    with closing(sqlite3.connect(str(berkas))) as kon, kon:
        kon.execute("PRAGMA user_version = 7")

    # Act / Assert
    with pytest.raises(D.GalatCatatan):
        _catat(berkas)
    with pytest.raises(D.GalatCatatan):
        D.terkini(KUNCI, MULAI, path=berkas)
    with pytest.raises(D.GalatCatatan):
        D.punya_jurnal([(KUNCI, MULAI)], path=berkas)
    assert _versi(berkas) == 7
    assert _tabel(berkas) == set()


def test_path_env_dipakai_bila_argumen_path_tidak_diberikan(tmp_path, monkeypatch):
    # Arrange
    tujuan = tmp_path / "dari-env.db"
    monkeypatch.setenv(D.ENV_DB, str(tujuan))

    # Act
    D.catat(kunci=KUNCI, pertemuan_id=1, mulai=MULAI, topik=TOPIK, hadir=HADIR_AWAL,
            oleh=ID_GURU, peran="guru", pada=PADA)

    # Assert
    assert tujuan.exists()


# --- catat: tulis selisih dan idempoten -------------------------------------------------

def test_catat_menulis_satu_jurnal_dan_satu_baris_per_status(berkas):
    # Arrange
    hadir = {ORDER_A: "hadir", ORDER_B: "izin"}

    # Act
    baru = _catat(berkas, hadir=hadir)

    # Assert
    assert baru == 3
    assert _jumlah(berkas, "pertemuan_jurnal") == 1
    assert _jumlah(berkas, "pertemuan_hadir") == 2


def test_kirim_ulang_identik_tidak_menulis_baris(berkas):
    # Arrange
    hadir = {ORDER_A: "hadir", ORDER_B: "izin"}
    _catat(berkas, hadir=hadir)

    # Act
    baru = _catat(berkas, hadir=hadir, pada=PADA_LAIN)

    # Assert
    assert baru == 0
    assert _jumlah(berkas, "pertemuan_jurnal") == 1
    assert _jumlah(berkas, "pertemuan_hadir") == 2


def test_ubah_satu_status_menulis_tepat_satu_baris_dan_riwayat_tetap(berkas):
    # Arrange
    _catat(berkas, hadir={ORDER_A: "hadir", ORDER_B: "izin"})

    # Act
    baru = _catat(berkas, hadir={ORDER_A: "hadir", ORDER_B: "hadir"}, pada=PADA_LAIN)

    # Assert
    assert baru == 1
    assert _jumlah(berkas, "pertemuan_hadir") == 3
    assert D.terkini(KUNCI, MULAI, path=berkas)["hadir"] == {ORDER_A: "hadir", ORDER_B: "hadir"}
    riwayat_b = _baca(berkas, "SELECT status FROM pertemuan_hadir WHERE order_id = ? ORDER BY id", (ORDER_B,))
    assert [baris[0] for baris in riwayat_b] == ["izin", "hadir"]


def test_ubah_topik_menulis_satu_baris_jurnal_dan_terkini_memakai_yang_baru(berkas):
    # Arrange
    _catat(berkas)

    # Act
    baru = _catat(berkas, topik=TOPIK_LAIN, pada=PADA_LAIN)

    # Assert
    assert baru == 1
    assert _jumlah(berkas, "pertemuan_jurnal") == 2
    assert D.terkini(KUNCI, MULAI, path=berkas)["topik"] == TOPIK_LAIN


def test_status_kembali_ke_awal_menambah_baris_dan_terkini_memakai_id_terbesar(berkas):
    # Arrange / Act / Assert
    assert _catat(berkas, hadir={ORDER_A: "hadir"}) == 2
    assert _catat(berkas, hadir={ORDER_A: "izin"}, pada=PADA_LAIN) == 1
    assert _catat(berkas, hadir={ORDER_A: "hadir"}, pada=PADA_LAIN) == 1
    assert _jumlah(berkas, "pertemuan_hadir") == 3
    assert D.terkini(KUNCI, MULAI, path=berkas)["hadir"] == {ORDER_A: "hadir"}


# --- snapshot mulai ---------------------------------------------------------------------

def test_pertemuan_yang_digeser_tidak_mewarisi_catatan_lama(berkas):
    # Arrange
    _catat(berkas)

    # Act / Assert
    assert D.terkini(KUNCI, MULAI_LAIN, path=berkas) == {"topik": None, "hadir": {}}
    assert D.punya_jurnal([(KUNCI, MULAI_LAIN), (KUNCI, MULAI)], path=berkas) == {(KUNCI, MULAI)}


def test_catat_pada_mulai_baru_menulis_dan_mulai_lama_tetap_terlihat(berkas):
    # Arrange
    _catat(berkas)

    # Act
    baru = _catat(berkas, mulai=MULAI_LAIN)

    # Assert
    assert baru == 2
    assert D.terkini(KUNCI, MULAI, path=berkas)["topik"] == TOPIK
    assert D.terkini(KUNCI, MULAI_LAIN, path=berkas)["topik"] == TOPIK
    assert _catat(berkas, mulai=MULAI) == 0


def test_punya_jurnal_hanya_mencocokkan_pasangan_kunci_dan_mulai_yang_sama(berkas):
    # Arrange
    _catat(berkas, kunci=KUNCI, mulai=MULAI)
    _catat(berkas, kunci=KUNCI_LAIN, mulai=MULAI_LAIN)

    # Act
    silang = D.punya_jurnal([(KUNCI, MULAI_LAIN), (KUNCI_LAIN, MULAI)], path=berkas)
    cocok = D.punya_jurnal([(KUNCI_LAIN, MULAI_LAIN)], path=berkas)

    # Assert
    assert silang == set()
    assert cocok == {(KUNCI_LAIN, MULAI_LAIN)}


# --- atomik -----------------------------------------------------------------------------

def test_gagal_di_tengah_tulis_membatalkan_seluruh_transaksi(berkas, monkeypatch):
    # Arrange
    _catat(berkas)
    sisipkan_asli = D._sisipkan_hadir
    panggilan = []

    def gagal_pada_panggilan_kedua(kon, catatan, order_id, status):
        panggilan.append(order_id)
        if len(panggilan) == 2:
            raise sqlite3.OperationalError("gangguan uji")
        return sisipkan_asli(kon, catatan, order_id, status)

    monkeypatch.setattr(D, "_sisipkan_hadir", gagal_pada_panggilan_kedua)

    # Act / Assert
    with pytest.raises(D.GalatCatatan):
        _catat(berkas, topik=TOPIK_LAIN, hadir={ORDER_A: "izin", ORDER_B: "izin"}, pada=PADA_LAIN)
    assert len(panggilan) == 2
    assert _jumlah(berkas, "pertemuan_jurnal") == 1
    assert _jumlah(berkas, "pertemuan_hadir") == 1
    assert D.terkini(KUNCI, MULAI, path=berkas) == {"topik": TOPIK, "hadir": {ORDER_A: "hadir"}}


def test_gagal_pada_tulis_pertama_tidak_meninggalkan_berkas_kosong(berkas, monkeypatch):
    """Berkas 0 byte tidak punya header SQLite: `sqlite_copy` backup operasional menolaknya dan seluruh backup gagal."""
    # Arrange
    def gagal_sisipkan_jurnal(kon, catatan):
        raise sqlite3.OperationalError("gangguan uji")

    monkeypatch.setattr(D, "_sisipkan_jurnal", gagal_sisipkan_jurnal)

    # Act / Assert
    with pytest.raises(D.GalatCatatan):
        _catat(berkas)
    assert not berkas.exists()
    assert D.terkini(KUNCI, MULAI, path=berkas) == {"topik": None, "hadir": {}}


def test_gagal_pada_berkas_yang_sudah_ada_tidak_menghapusnya(berkas, monkeypatch):
    # Arrange: berkas sah sudah ada, lalu penulisan berikutnya gagal
    _catat(berkas)
    ukuran = berkas.stat().st_size

    def gagal_sisipkan_jurnal(kon, catatan):
        raise sqlite3.OperationalError("gangguan uji")

    monkeypatch.setattr(D, "_sisipkan_jurnal", gagal_sisipkan_jurnal)

    # Act / Assert
    with pytest.raises(D.GalatCatatan):
        _catat(berkas, topik=TOPIK_LAIN, pada=PADA_LAIN)
    assert berkas.exists() and berkas.stat().st_size == ukuran


def test_berkas_kosong_buatan_pihak_lain_tidak_dihapus_saat_gagal(berkas, monkeypatch):
    """Hanya berkas yang dibuat oleh catat() sendiri yang boleh dibersihkan."""
    berkas.touch(mode=0o600)

    def gagal_sisipkan_jurnal(kon, catatan):
        raise sqlite3.OperationalError("gangguan uji")

    monkeypatch.setattr(D, "_sisipkan_jurnal", gagal_sisipkan_jurnal)

    with pytest.raises(D.GalatCatatan):
        _catat(berkas)
    assert berkas.exists()


# --- validasi sebelum berkas disentuh ---------------------------------------------------

@pytest.mark.parametrize(
    "ubah",
    [
        pytest.param({"kunci": "KLP_" + "C" * 32 + ":1"}, id="kunci-huruf-besar"),
        pytest.param({"kunci": KUNCI[:-1] + "9"}, id="kunci-ke-sembilan"),
        pytest.param({"kunci": KUNCI + "\n"}, id="kunci-ada-newline"),
        pytest.param({"pertemuan_id": 0}, id="pertemuan-id-nol"),
        pytest.param({"pertemuan_id": True}, id="pertemuan-id-bool"),
        pytest.param({"mulai": "2026-1-5T10:00:00"}, id="mulai-tidak-padat"),
        pytest.param({"mulai": "2026-13-01T10:00:00"}, id="mulai-bulan-tiga-belas"),
        pytest.param({"pada": "2026-11-10 10:30:00"}, id="pada-pakai-spasi"),
        pytest.param({"topik": "campuran"}, id="topik-campuran"),
        pytest.param({"topik": "topik-asing"}, id="topik-tidak-dikenal"),
        pytest.param({"topik": 7}, id="topik-bukan-teks"),
        pytest.param({"oleh": "akun_" + "A" * 32}, id="oleh-huruf-besar"),
        pytest.param({"oleh": KUNCI_LAIN}, id="oleh-prefiks-salah"),
        pytest.param({"peran": "orang_tua"}, id="peran-tidak-dikenal"),
        pytest.param({"peran": "Guru"}, id="peran-huruf-besar"),
        pytest.param({"hadir": [ORDER_A]}, id="hadir-bukan-pemetaan"),
        pytest.param({"hadir": {"akun_" + "1" * 32: "hadir"}}, id="order-berprefiks-akun"),
        pytest.param({"hadir": {ORDER_A.upper(): "hadir"}}, id="order-huruf-besar"),
        pytest.param({"hadir": {ORDER_A: "sakit"}}, id="status-tidak-dikenal"),
    ],
)
def test_argumen_tidak_sah_ditolak_sebelum_berkas_dibuat(berkas, ubah):
    # Act / Assert
    with pytest.raises(ValueError):
        _catat(berkas, **ubah)
    assert not berkas.exists()


def test_punya_jurnal_menolak_pasangan_tidak_sah_tanpa_membuat_berkas(berkas):
    # Act / Assert
    with pytest.raises(ValueError):
        D.punya_jurnal([(KUNCI, "2026-1-5T10:00:00")], path=berkas)
    assert not berkas.exists()


def test_peran_admin_diterima_dan_tersimpan(berkas):
    # Act
    _catat(berkas, peran="admin", oleh=ID_ADMIN)

    # Assert
    assert _baca(berkas, "SELECT peran, oleh FROM pertemuan_jurnal") == [("admin", ID_ADMIN)]


# --- punya_jurnal untuk banyak pasangan -------------------------------------------------

def _pasangan_uji(jumlah):
    return [("klp_" + format(i, "032x") + ":1", MULAI) for i in range(jumlah)]


def _sisipkan_jurnal_mentah(path, pasangan):
    baris = [(kunci, 1, mulai, TOPIK, ID_GURU, "guru", PADA) for kunci, mulai in pasangan]
    with closing(sqlite3.connect(str(path))) as kon, kon:
        kon.executemany(
            "INSERT INTO pertemuan_jurnal (kunci, pertemuan_id, mulai, topik, oleh, peran, pada) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            baris,
        )


def test_punya_jurnal_benar_melintasi_batas_potongan_default(berkas):
    # Arrange
    _catat(berkas)
    pasangan = _pasangan_uji(JUMLAH_PASANGAN_UJI)
    berjurnal = pasangan[::2]
    _sisipkan_jurnal_mentah(berkas, berjurnal)

    # Act
    hasil = D.punya_jurnal(pasangan, path=berkas)

    # Assert
    assert hasil == set(berjurnal)
    assert pasangan[D.PANJANG_POTONGAN_PASANGAN] in hasil
    assert pasangan[D.PANJANG_POTONGAN_PASANGAN - 1] not in hasil


@pytest.mark.parametrize("ukuran", [1, 7])
def test_punya_jurnal_hasil_sama_untuk_ukuran_potongan_kecil(berkas, monkeypatch, ukuran):
    # Arrange
    _catat(berkas)
    pasangan = _pasangan_uji(JUMLAH_PASANGAN_UJI)
    berjurnal = pasangan[::2]
    _sisipkan_jurnal_mentah(berkas, berjurnal)
    monkeypatch.setattr(D, "PANJANG_POTONGAN_PASANGAN", ukuran)

    # Act
    hasil = D.punya_jurnal(pasangan, path=berkas)

    # Assert
    assert hasil == set(berjurnal)


def test_punya_jurnal_daftar_kosong_mengembalikan_himpunan_kosong_tanpa_berkas(berkas):
    # Act / Assert
    assert D.punya_jurnal([], path=berkas) == set()
    assert not berkas.exists()


# --- CHECK skema di sisi DB (INSERT mentah, melewati validasi Python) -------------------

_BARIS_SAH = {
    "pertemuan_jurnal": {
        "kunci": KUNCI, "pertemuan_id": 1, "mulai": MULAI, "topik": TOPIK,
        "oleh": ID_GURU, "peran": "guru", "pada": PADA,
    },
    "pertemuan_hadir": {
        "kunci": KUNCI, "pertemuan_id": 1, "mulai": MULAI, "order_id": ORDER_A,
        "status": "hadir", "oleh": ID_GURU, "peran": "guru", "pada": PADA,
    },
}


def _insert_mentah(path, tabel, baris):
    kolom = tuple(baris)
    tanda_tanya = ", ".join(["?"] * len(kolom))
    sql = "INSERT INTO " + tabel + " (" + ", ".join(kolom) + ") VALUES (" + tanda_tanya + ")"
    with closing(sqlite3.connect(str(path))) as kon, kon:
        kon.execute(sql, [baris[k] for k in kolom])


def test_baris_mentah_yang_sah_diterima_oleh_check_skema(berkas):
    # Arrange
    _catat(berkas)

    # Act
    _insert_mentah(berkas, "pertemuan_jurnal", _BARIS_SAH["pertemuan_jurnal"])

    # Assert
    assert _jumlah(berkas, "pertemuan_jurnal") == 2


@pytest.mark.parametrize(
    ("tabel", "ubah"),
    [
        pytest.param("pertemuan_jurnal", {"kunci": "KLP_" + "C" * 32 + ":1"}, id="jurnal-kunci-huruf-besar"),
        pytest.param("pertemuan_jurnal", {"kunci": "klp_" + "c" * 32 + ":9"}, id="jurnal-kunci-ke-sembilan"),
        pytest.param("pertemuan_jurnal", {"pertemuan_id": 0}, id="jurnal-pertemuan-id-nol"),
        pytest.param("pertemuan_jurnal", {"mulai": "2026-1-5T10:00:00"}, id="jurnal-mulai-tidak-padat"),
        pytest.param("pertemuan_jurnal", {"topik": ""}, id="jurnal-topik-kosong"),
        pytest.param("pertemuan_jurnal", {"oleh": "akun_" + "A" * 32}, id="jurnal-oleh-huruf-besar"),
        pytest.param("pertemuan_jurnal", {"peran": "orang_tua"}, id="jurnal-peran-asing"),
        pytest.param("pertemuan_jurnal", {"pada": "2026-11-10 10:30:00"}, id="jurnal-pada-pakai-spasi"),
        pytest.param("pertemuan_hadir", {"order_id": "klp_" + "1" * 32}, id="hadir-order-prefiks-salah"),
        pytest.param("pertemuan_hadir", {"order_id": "kor_" + "G" * 32}, id="hadir-order-bukan-hex"),
        pytest.param("pertemuan_hadir", {"status": "sakit"}, id="hadir-status-asing"),
        pytest.param("pertemuan_hadir", {"mulai": "2026-11-10 10:00:00"}, id="hadir-mulai-pakai-spasi"),
    ],
)
def test_check_skema_menolak_baris_mentah_yang_tidak_sah(berkas, tabel, ubah):
    # Arrange
    _catat(berkas)
    baris = {**_BARIS_SAH[tabel], **ubah}

    # Act / Assert
    with pytest.raises(sqlite3.IntegrityError):
        _insert_mentah(berkas, tabel, baris)
    assert _jumlah(berkas, tabel) == 1
