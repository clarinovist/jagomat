"""Sakelar kelima OSN_LOMBA: memperlebar DB sakelar lama (4 nama) tanpa menaikkan versi dan tanpa mengubah yang ada."""
import sqlite3
from contextlib import closing

import pytest

import feature_switch as F

NAMA_LAMA = ("FUNNEL_AKTIF", "PESANAN_TRANSFER_AKTIF", "OSN_CETAK_RINGKAS", "OSN_BANK_KALIMAT")
NAMA_BARU = "OSN_LOMBA"
DDL_SAKELAR_LAMA = (
    "CREATE TABLE sakelar (nama TEXT PRIMARY KEY CHECK (nama IN "
    "('FUNNEL_AKTIF','PESANAN_TRANSFER_AKTIF','OSN_CETAK_RINGKAS','OSN_BANK_KALIMAT')), "
    "aktif INTEGER NOT NULL CHECK (aktif IN (0, 1)), revisi INTEGER NOT NULL CHECK (revisi >= 1), "
    "diperbarui TEXT NOT NULL)")
DDL_AUDIT_LAMA = (
    "CREATE TABLE audit_sakelar (id INTEGER PRIMARY KEY AUTOINCREMENT, nama TEXT NOT NULL, lama INTEGER, "
    "baru INTEGER NOT NULL, revisi INTEGER NOT NULL, actor_id TEXT NOT NULL, dibuat TEXT NOT NULL)")
NAMA_TERBARU = ("DAFTAR_AKUN_ANAK", "LATIHAN_HARIAN", "PAKET_BELAJAR", "DAFTAR_GURU")  # sakelar keenam sampai kesembilan; pelebaran dari 4 nama ke atas tetap sama
SEED = {nama: False for nama in NAMA_LAMA + (NAMA_BARU,) + NAMA_TERBARU}
# keadaan produksi yang masuk akal: funnel hidup (revisi 3), transfer hidup (revisi 2), sisanya mati
KEADAAN_LAMA = {"FUNNEL_AKTIF": (1, 3), "PESANAN_TRANSFER_AKTIF": (1, 2),
                "OSN_CETAK_RINGKAS": (0, 1), "OSN_BANK_KALIMAT": (0, 1)}


@pytest.fixture(autouse=True)
def _bersih():
    F.bersihkan_cache()
    yield
    F.bersihkan_cache()


@pytest.fixture
def db_lama(tmp_path):
    """DB sakelar persis seperti versi lama: CHECK 4 nama, user_version 1, riwayat audit."""
    path = tmp_path / "sakelar.db"
    with closing(sqlite3.connect(path)) as kon, kon:
        kon.execute(DDL_SAKELAR_LAMA)
        kon.execute(DDL_AUDIT_LAMA)
        for nama, (aktif, revisi) in KEADAAN_LAMA.items():
            kon.execute("INSERT INTO sakelar VALUES (?,?,?,?)", (nama, aktif, revisi, "2026-11-01T00:00:00+00:00"))
        kon.execute("INSERT INTO audit_sakelar(nama,lama,baru,revisi,actor_id,dibuat) VALUES "
                    "('FUNNEL_AKTIF',0,1,3,'pemilik','2026-11-01T00:00:00+00:00')")
        kon.execute("PRAGMA user_version = 1")
    return path


def _baca(path, sql, parameter=()):
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as kon:
        return kon.execute(sql, parameter).fetchall()


def _ubah(path, nama=NAMA_BARU, aktif=True, revisi=1):
    return F.ubah(nama, aktif, actor_id="uji", revisi_diharapkan=revisi, seed=SEED, path=path)


# --- daftar nama --------------------------------------------------------------------------

def test_osn_lomba_ada_di_daftar_nama_sakelar_setelah_empat_yang_lama():
    assert F.NAMA_SAKELAR == NAMA_LAMA + (NAMA_BARU,) + NAMA_TERBARU


def test_versi_skema_tidak_dinaikkan_agar_kode_lama_tetap_bisa_membaca():
    assert F.VERSI_SKEMA == 1


def test_seed_tanpa_nama_baru_ditolak():
    with pytest.raises(ValueError):
        F.daftar(seed={nama: False for nama in NAMA_LAMA}, path="/tidak/ada.db")


# --- membaca DB lama (tanpa migrasi saat membaca) -----------------------------------------------

def test_membaca_db_lama_tidak_mengubah_nilai_empat_sakelar_yang_hidup(db_lama):
    for nama, (aktif, _) in KEADAAN_LAMA.items():
        assert F.aktif(nama, lambda: not aktif, path=db_lama) is bool(aktif)


def test_osn_lomba_pada_db_lama_jatuh_ke_fallback_env(db_lama):
    assert F.aktif(NAMA_BARU, lambda: False, path=db_lama) is False
    F.bersihkan_cache()
    assert F.aktif(NAMA_BARU, lambda: True, path=db_lama) is True


def test_membaca_tidak_memigrasi_db_lama(db_lama):
    F.aktif(NAMA_BARU, lambda: False, path=db_lama)
    F.daftar(seed=SEED, path=db_lama)
    sql = _baca(db_lama, "SELECT sql FROM sqlite_master WHERE name='sakelar'")[0][0]
    assert "OSN_LOMBA" not in sql


def test_daftar_pada_db_lama_menampilkan_lima_sakelar_dengan_nilai_lama_utuh(db_lama):
    hasil = F.daftar(seed=SEED, path=db_lama)
    assert [s.nama for s in hasil] == list(F.NAMA_SAKELAR)
    funnel, transfer = hasil[0], hasil[1]
    assert (funnel.aktif, funnel.revisi, funnel.sumber) == (True, 3, "db")
    assert (transfer.aktif, transfer.revisi) == (True, 2)
    assert (hasil[4].nama, hasil[4].aktif, hasil[4].revisi, hasil[4].sumber) == (NAMA_BARU, False, 0, "env")


# --- memperlebar saat ubah() ------------------------------------------------------------------

def test_ubah_osn_lomba_pada_db_lama_memperlebar_tanpa_menaikkan_versi(db_lama):
    hasil = _ubah(db_lama)
    assert (hasil.nama, hasil.aktif, hasil.revisi, hasil.sumber) == (NAMA_BARU, True, 2, "db")
    assert _baca(db_lama, "PRAGMA user_version")[0][0] == 1
    sql = _baca(db_lama, "SELECT sql FROM sqlite_master WHERE name='sakelar'")[0][0]
    assert all(f"'{nama}'" in sql for nama in F.NAMA_SAKELAR)


def test_perluasan_menyimpan_nilai_revisi_dan_riwayat_empat_sakelar_lama(db_lama):
    _ubah(db_lama)
    for nama, (aktif, revisi) in KEADAAN_LAMA.items():
        baris = _baca(db_lama, "SELECT aktif, revisi FROM sakelar WHERE nama=?", (nama,))[0]
        assert tuple(baris) == (aktif, revisi), nama
    audit = _baca(db_lama, "SELECT nama, lama, baru, revisi, actor_id FROM audit_sakelar WHERE actor_id='pemilik'")
    assert [tuple(a) for a in audit] == [("FUNNEL_AKTIF", 0, 1, 3, "pemilik")]


def test_mengubah_sakelar_lama_pada_db_lama_juga_memperlebar_dan_menyemai_osn_lomba_mati(db_lama):
    F.ubah("OSN_CETAK_RINGKAS", True, actor_id="uji", revisi_diharapkan=1, seed=SEED, path=db_lama)
    assert F.aktif(NAMA_BARU, lambda: True, path=db_lama) is False       # baris disemai dari SEED (mati)
    assert F.aktif("OSN_CETAK_RINGKAS", lambda: False, path=db_lama) is True
    assert F.aktif("FUNNEL_AKTIF", lambda: False, path=db_lama) is True


def test_perluasan_idempoten_dan_tidak_membangun_ulang_tabel_yang_sudah_lebar(db_lama):
    _ubah(db_lama)
    rowid_sebelum = _baca(db_lama, "SELECT rootpage FROM sqlite_master WHERE name='sakelar'")[0][0]
    _ubah(db_lama, aktif=False, revisi=2)
    assert _baca(db_lama, "SELECT rootpage FROM sqlite_master WHERE name='sakelar'")[0][0] == rowid_sebelum
    assert _baca(db_lama, "SELECT COUNT(*) FROM sakelar")[0][0] == 9


def test_perluasan_gagal_di_tengah_membatalkan_semuanya_dan_db_lama_utuh(db_lama, monkeypatch):
    asli = F._perluas_nama

    def gagal_setelah_menyalin(kon):
        asli(kon)
        raise sqlite3.OperationalError("uji: gagal setelah menyalin")

    monkeypatch.setattr(F, "_perluas_nama", gagal_setelah_menyalin)
    with pytest.raises(F.GalatSakelar):
        _ubah(db_lama)
    sql = _baca(db_lama, "SELECT sql FROM sqlite_master WHERE name='sakelar'")[0][0]
    assert "OSN_LOMBA" not in sql
    assert _baca(db_lama, "SELECT COUNT(*) FROM sakelar")[0][0] == 4
    assert _baca(db_lama, "PRAGMA user_version")[0][0] == 1
    assert _baca(db_lama, "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'sakelar%'")[0][0] == 1


# --- DB baru dan kompatibilitas kode lama -------------------------------------------------------

def test_db_baru_dibuat_lebar_dengan_versi_satu_dan_menolak_nama_liar(tmp_path):
    path = tmp_path / "baru.db"
    _ubah(path)
    assert _baca(path, "PRAGMA user_version")[0][0] == 1
    with closing(sqlite3.connect(path)) as kon:
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO sakelar VALUES ('NAMA_LIAR',1,1,'x')")


def test_kode_lama_masih_bisa_membaca_dan_menulis_db_yang_sudah_diperlebar(db_lama):
    _ubah(db_lama)
    # kueri persis seperti kode lama: versi harus 1, baca per nama, sisip nama lamanya
    assert _baca(db_lama, "PRAGMA user_version")[0][0] == 1
    assert _baca(db_lama, "SELECT aktif FROM sakelar WHERE nama='FUNNEL_AKTIF'")[0][0] == 1
    with closing(sqlite3.connect(db_lama)) as kon, kon:
        kon.execute("UPDATE sakelar SET aktif=0, revisi=revisi+1 WHERE nama='FUNNEL_AKTIF'")
        kon.execute("INSERT OR IGNORE INTO sakelar VALUES ('OSN_BANK_KALIMAT',1,9,'x')")
    assert _baca(db_lama, "SELECT aktif FROM sakelar WHERE nama='FUNNEL_AKTIF'")[0][0] == 0


def test_versi_lain_selain_nol_dan_satu_tetap_ditolak(tmp_path):
    path = tmp_path / "asing.db"
    with closing(sqlite3.connect(path)) as kon, kon:
        kon.execute("PRAGMA user_version = 7")
    with pytest.raises(F.GalatSakelar):
        _ubah(path)


# --- ketahanan: DB tanpa CHECK nama dan baris rusak ------------------------------------------

def test_db_tanpa_check_nama_tidak_dibangun_ulang(tmp_path):
    path = tmp_path / "tangan.db"
    with closing(sqlite3.connect(path)) as kon, kon:
        kon.execute("CREATE TABLE sakelar (nama TEXT PRIMARY KEY, aktif INTEGER NOT NULL, "
                    "revisi INTEGER NOT NULL, diperbarui TEXT NOT NULL)")
        kon.execute(DDL_AUDIT_LAMA)
        kon.execute("INSERT INTO sakelar VALUES ('FUNNEL_AKTIF', 5, 1, 'x')")
        kon.execute("PRAGMA user_version = 1")
    sql_sebelum = _baca(path, "SELECT sql FROM sqlite_master WHERE name='sakelar'")[0][0]
    _ubah(path, "FUNNEL_AKTIF", True)
    assert _baca(path, "SELECT sql FROM sqlite_master WHERE name='sakelar'")[0][0] == sql_sebelum


def test_perluasan_menyalin_baris_rusak_apa_adanya_sehingga_pemulihan_tetap_mungkin(db_lama):
    with closing(sqlite3.connect(db_lama)) as kon, kon:
        kon.execute("PRAGMA ignore_check_constraints = ON")
        kon.execute("UPDATE sakelar SET aktif = 5 WHERE nama = 'OSN_BANK_KALIMAT'")
    hasil = _ubah(db_lama)                      # memperlebar walau ada baris rusak
    assert hasil.aktif is True
    assert _baca(db_lama, "SELECT aktif FROM sakelar WHERE nama='OSN_BANK_KALIMAT'")[0][0] == 5
    pulih = F.ubah("OSN_BANK_KALIMAT", True, actor_id="uji", revisi_diharapkan=1, seed=SEED, path=db_lama)
    assert (pulih.aktif, pulih.revisi) == (True, 2)
    assert _baca(db_lama, "SELECT aktif FROM sakelar WHERE nama='OSN_BANK_KALIMAT'")[0][0] == 1


def test_perluasan_mengembalikan_penegakan_check_setelah_menyalin(db_lama):
    _ubah(db_lama)
    with closing(sqlite3.connect(db_lama)) as kon:
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO sakelar VALUES ('FUNNEL_AKTIF', 9, 1, 'x')")


def test_koneksi_yang_memperluas_tidak_dibiarkan_mengabaikan_check(db_lama):
    with closing(sqlite3.connect(db_lama)) as kon:
        kon.execute("BEGIN IMMEDIATE")
        F._perluas_nama(kon)
        assert kon.execute("PRAGMA ignore_check_constraints").fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO sakelar VALUES ('OSN_LOMBA', 9, 1, 'x')")
        kon.rollback()
