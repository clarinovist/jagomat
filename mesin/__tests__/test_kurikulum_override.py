"""Tes store override kurikulum (3b): DB terpisah, fail ke bawaan, revisi, audit, cache.

Semua DB uji di tmp_path dengan data sintetis; kasus "tangan" (baris rusak,
user_version asing) ditanam lewat sqlite3 langsung, bukan lewat API tulis.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import sqlite3
import stat
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kurikulum_cp  # noqa: E402
import kurikulum_katalog  # noqa: E402
import kurikulum_override as ko  # noqa: E402

KUNCI = ("pengukuran", "jam")
BAWAAN_CP = kurikulum_cp.CP_PER_GRUP[KUNCI]
KUNCI_LAIN = ("pengukuran", "waktu")
LABEL_BAWAAN = kurikulum_katalog.label_awam()
TOPIK = "pengukuran"
TOPIK_LAIN = "statistika"
TANPA_LABEL = "kombinatorik"
BARU = (("C.pengukuran.2", "sebagian"), ("A.pengukuran.1", "prasyarat"))
BARU_NORMAL = (("A.pengukuran.1", "prasyarat"), ("C.pengukuran.2", "sebagian"))


@pytest.fixture(autouse=True)
def _cache_kosong_dan_jam_pulih():
    ko.bersihkan_cache()
    jam_asli = ko._jam
    yield
    ko._jam = jam_asli
    ko.bersihkan_cache()


@pytest.fixture
def db(tmp_path):
    return tmp_path / "kurikulum.db"


def _ubah_cp(db, isi=BARU, *, kunci=KUNCI, revisi=0, actor="admin"):
    return ko.ubah_cp(kunci[0], kunci[1], isi, actor_id=actor,
                      revisi_diharapkan=revisi, path=db)


def _ubah_label(db, label="Ukur-ukur", *, topik=TOPIK, revisi=0, actor="admin"):
    return ko.ubah_label(topik, label, actor_id=actor,
                         revisi_diharapkan=revisi, path=db)


def _baris(db, sql, parameter=()):
    with sqlite3.connect(db) as kon:
        kon.row_factory = sqlite3.Row
        hasil = [dict(b) for b in kon.execute(sql, parameter)]
    kon.close()
    return hasil


def _db_tangan(db, *, versi=1, baris_cp=(), baris_label=()):
    """DB v1 tangan TANPA CHECK agar baris rusak bisa ditanam."""
    with sqlite3.connect(db) as kon:
        kon.execute("CREATE TABLE cp_grup (topik_id TEXT, grup_kode TEXT, isi_json TEXT,"
                    " revisi INTEGER, diperbarui TEXT, PRIMARY KEY (topik_id, grup_kode))")
        kon.execute("CREATE TABLE label_awam (topik_id TEXT PRIMARY KEY, label TEXT,"
                    " revisi INTEGER, diperbarui TEXT)")
        kon.execute("CREATE TABLE audit_kurikulum (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " jenis TEXT, kunci TEXT, lama TEXT, baru TEXT, revisi INTEGER,"
                    " actor_id TEXT, dibuat TEXT)")
        kon.executemany("INSERT INTO cp_grup VALUES (?, ?, ?, ?, '2026-01-01')", baris_cp)
        kon.executemany("INSERT INTO label_awam VALUES (?, ?, ?, '2026-01-01')", baris_label)
        kon.execute(f"PRAGMA user_version = {versi}")
    kon.close()


# --- berkas tidak ada ---------------------------------------------------------

def test_berkas_tidak_ada_efektif_sama_dengan_bawaan_dan_tidak_membuat_berkas(db):
    # Act
    cp = ko.cp_efektif(path=db)
    label = ko.label_efektif(path=db)
    daftar = ko.daftar_cp(path=db) + ko.daftar_label(path=db)

    # Assert
    assert cp == {k: tuple(v) for k, v in kurikulum_cp.CP_PER_GRUP.items()}
    assert list(cp) == list(kurikulum_cp.CP_PER_GRUP)
    assert label == LABEL_BAWAAN and list(label) == list(LABEL_BAWAAN)
    assert all(i.sumber == "bawaan" and i.revisi == 0 and i.diperbarui is None
               and i.efektif == i.bawaan for i in daftar)
    assert not db.exists()


def test_path_dari_env_lalu_bawaan(tmp_path, monkeypatch):
    berkas = tmp_path / "dari-env.db"
    monkeypatch.setenv(ko.ENV_BERKAS_DB, str(berkas))
    ko.ubah_cp(*KUNCI, BARU, actor_id="admin", revisi_diharapkan=0)
    assert berkas.exists()
    assert ko.cp_efektif()[KUNCI] == BARU_NORMAL


# --- tulis dasar --------------------------------------------------------------

def test_ubah_cp_efektif_berubah_dinormalkan_dan_diaudit(db):
    # Act
    hasil = _ubah_cp(db)

    # Assert
    assert hasil.efektif == BARU_NORMAL and hasil.sumber == "admin" and hasil.revisi == 1
    item = next(i for i in ko.daftar_cp(path=db) if (i.topik_id, i.grup_kode) == KUNCI)
    assert (item.efektif, item.bawaan, item.sumber, item.revisi) == (
        BARU_NORMAL, BAWAAN_CP, "admin", 1)
    assert item.diperbarui is not None
    audit = _baris(db, "SELECT * FROM audit_kurikulum")
    assert len(audit) == 1
    assert (audit[0]["jenis"], audit[0]["kunci"], audit[0]["revisi"], audit[0]["actor_id"]) == (
        "cp", "pengukuran/jam", 1, "admin")
    assert audit[0]["lama"] == '[["C.pengukuran.2", "penuh"]]'
    assert audit[0]["baru"] == '[["A.pengukuran.1", "prasyarat"], ["C.pengukuran.2", "sebagian"]]'
    assert stat.S_IMODE(os.stat(db).st_mode) == 0o600
    assert _baris(db, "PRAGMA user_version") == [{"user_version": ko.VERSI_SKEMA}]


def test_ubah_cp_tuple_kosong_sah_artinya_di_luar_cp(db):
    hasil = _ubah_cp(db, ())
    assert hasil.efektif == () and hasil.sumber == "admin"
    assert ko.cp_efektif(path=db)[KUNCI] == ()


def test_ubah_label_efektif_berubah_dan_diaudit(db):
    hasil = _ubah_label(db, "  Ukur-ukur ")

    assert hasil.efektif == "Ukur-ukur" and hasil.sumber == "admin" and hasil.revisi == 1
    assert ko.label_efektif(path=db)[TOPIK] == "Ukur-ukur"
    assert ko.label_efektif(path=db)[TOPIK_LAIN] == LABEL_BAWAAN[TOPIK_LAIN]
    audit = _baris(db, "SELECT * FROM audit_kurikulum")
    assert len(audit) == 1
    assert (audit[0]["jenis"], audit[0]["kunci"], audit[0]["revisi"]) == ("label", TOPIK, 1)
    assert audit[0]["lama"] == '"Pengukuran"' and audit[0]["baru"] == '"Ukur-ukur"'
    assert stat.S_IMODE(os.stat(db).st_mode) == 0o600


def test_urutan_kunci_efektif_tetap_urutan_bawaan_setelah_ubah(db):
    _ubah_cp(db)
    _ubah_label(db)
    assert list(ko.cp_efektif(path=db)) == list(kurikulum_cp.CP_PER_GRUP)
    assert list(ko.label_efektif(path=db)) == list(LABEL_BAWAAN)


# --- kembalikan, revisi, ABA --------------------------------------------------

def test_kembalikan_cp_ke_bawaan_revisi_naik_dan_aba_tertutup(db):
    _ubah_cp(db)

    hasil = ko.kembalikan_cp(*KUNCI, actor_id="admin", revisi_diharapkan=1, path=db)

    assert hasil.efektif == BAWAAN_CP and hasil.sumber == "bawaan" and hasil.revisi == 2
    assert ko.cp_efektif(path=db)[KUNCI] == BAWAAN_CP
    audit = _baris(db, "SELECT revisi, lama, baru FROM audit_kurikulum ORDER BY id")
    assert [a["revisi"] for a in audit] == [1, 2]
    assert audit[1]["lama"] == audit[0]["baru"]
    baris = _baris(db, "SELECT isi_json, revisi FROM cp_grup")
    assert baris == [{"isi_json": None, "revisi": 2}]  # baris tidak dihapus
    with pytest.raises(ko.KonflikRevisi):
        _ubah_cp(db, revisi=0)  # klien basi yang melihat keadaan awal tidak boleh menimpa
    assert ko.cp_efektif(path=db)[KUNCI] == BAWAAN_CP


def test_kembalikan_label_ke_bawaan(db):
    _ubah_label(db)

    hasil = ko.kembalikan_label(TOPIK, actor_id="admin", revisi_diharapkan=1, path=db)

    assert hasil.efektif == LABEL_BAWAAN[TOPIK] and hasil.sumber == "bawaan" and hasil.revisi == 2
    assert ko.label_efektif(path=db) == LABEL_BAWAAN
    assert len(_baris(db, "SELECT * FROM audit_kurikulum")) == 2
    with pytest.raises(ko.KonflikRevisi):
        _ubah_label(db, "Lain lagi", revisi=0)


def test_konflik_revisi_digulung_balik_tanpa_audit_atau_perubahan(db):
    _ubah_cp(db)
    sebelum = _baris(db, "SELECT * FROM cp_grup")

    with pytest.raises(ko.KonflikRevisi):
        _ubah_cp(db, (("A.bilangan.1", "penuh"),), revisi=7)

    assert _baris(db, "SELECT * FROM cp_grup") == sebelum
    assert len(_baris(db, "SELECT * FROM audit_kurikulum")) == 1
    assert ko.cp_efektif(path=db)[KUNCI] == BARU_NORMAL


def test_konflik_pada_berkas_baru_tidak_meninggalkan_berkas(db):
    with pytest.raises(ko.KonflikRevisi):
        _ubah_cp(db, revisi=3)
    assert not db.exists()


def test_nilai_sama_adalah_noop_tanpa_revisi_atau_audit(db):
    _ubah_cp(db)
    _ubah_label(db)

    cp = _ubah_cp(db, BARU_NORMAL, revisi=1)
    label = _ubah_label(db, "Ukur-ukur", revisi=1)

    assert cp.revisi == 1 and label.revisi == 1
    assert len(_baris(db, "SELECT * FROM audit_kurikulum")) == 2
    assert [b["revisi"] for b in _baris(db, "SELECT revisi FROM cp_grup")] == [1]


def test_ubah_ke_nilai_bawaan_pada_kunci_belum_diubah_adalah_noop(db):
    hasil = _ubah_cp(db, BAWAAN_CP)
    assert hasil.revisi == 0 and hasil.sumber == "bawaan"
    kembali = ko.kembalikan_label(TOPIK, actor_id="admin", revisi_diharapkan=0, path=db)
    assert kembali.revisi == 0
    assert not db.exists()  # tak ada yang berubah, jadi berkas tidak dibuat


def test_ubah_ke_nilai_bawaan_pada_kunci_yang_diubah_disimpan_sebagai_null(db):
    _ubah_cp(db)
    hasil = _ubah_cp(db, BAWAAN_CP, revisi=1)
    assert hasil.sumber == "bawaan" and hasil.revisi == 2
    assert _baris(db, "SELECT isi_json FROM cp_grup") == [{"isi_json": None}]


def test_revisi_independen_per_kunci(db):
    _ubah_cp(db)
    hasil = _ubah_cp(db, (), kunci=KUNCI_LAIN, revisi=0)
    assert hasil.revisi == 1


# --- validasi tulis -----------------------------------------------------------

@pytest.mark.parametrize("kunci", [("asing", "jam"), ("pengukuran", "asing"), ("jam", "pengukuran")])
def test_validasi_tolak_kunci_cp_asing(db, kunci):
    with pytest.raises(ValueError, match="Grup katalog"):
        _ubah_cp(db, kunci=kunci)
    assert not db.exists()


@pytest.mark.parametrize("isi, pesan", [
    ((("Z.asing.1", "penuh"),), "capaian tidak dikenal"),
    ((("C.pengukuran.2", "asing"),), "kecocokan tidak dikenal"),
    ((("C.pengukuran.2", "penuh"), ("C.pengukuran.2", "sebagian")), "ganda"),
    (tuple((b.id, "penuh") for b in kurikulum_cp.CAPAIAN[:13]), "maksimal"),
    ("C.pengukuran.2", "daftar pasangan"),
    ((("C.pengukuran.2",),), "pasangan"),
    (((1, "penuh"),), "pasangan"),
    (None, "daftar pasangan"),
])
def test_validasi_tolak_isi_cp_tak_sah(db, isi, pesan):
    with pytest.raises(ValueError, match=pesan):
        _ubah_cp(db, isi)
    assert not db.exists()


def test_validasi_terima_tepat_dua_belas_pasangan(db):
    isi = tuple((b.id, "penuh") for b in kurikulum_cp.CAPAIAN[:12])
    assert _ubah_cp(db, isi).efektif == isi


@pytest.mark.parametrize("label", ["", "   ", "x" * 41, "Ukur\x00an", "Ukur\nan", "Ukur​an", 7, None])
def test_validasi_tolak_label_tak_sah(db, label):
    with pytest.raises(ValueError):
        _ubah_label(db, label)
    assert not db.exists()


def test_validasi_terima_label_empat_puluh_karakter(db):
    assert _ubah_label(db, "x" * 40).efektif == "x" * 40


def test_validasi_tolak_label_duplikat_casefold_terhadap_bawaan_topik_lain(db):
    with pytest.raises(ValueError, match="sudah dipakai"):
        _ubah_label(db, LABEL_BAWAAN[TOPIK_LAIN].upper())
    assert not db.exists()  # transaksi digulung balik, berkas baru tak tersisa


def test_validasi_tolak_label_duplikat_terhadap_override_topik_lain(db):
    _ubah_label(db, "Nama Baru", topik=TOPIK_LAIN)
    with pytest.raises(ValueError, match="sudah dipakai"):
        _ubah_label(db, "nama baru")


def test_label_sama_dengan_bawaan_sendiri_beda_huruf_boleh(db):
    assert _ubah_label(db, LABEL_BAWAAN[TOPIK].upper()).sumber == "admin"


def test_kembalikan_label_ditolak_bila_bawaan_bentrok_dengan_override_lain(db):
    _ubah_label(db, "Nama Baru", topik=TOPIK_LAIN)
    _ubah_label(db, LABEL_BAWAAN[TOPIK_LAIN], topik=TOPIK)  # bawaan lama milik topik lain, kini bebas
    with pytest.raises(ValueError, match="sudah dipakai"):
        ko.kembalikan_label(TOPIK_LAIN, actor_id="admin", revisi_diharapkan=1, path=db)


def test_validasi_tolak_label_topik_tanpa_label_bawaan(db):
    with pytest.raises(ValueError, match="label awam bawaan"):
        _ubah_label(db, "Apa saja", topik=TANPA_LABEL)
    with pytest.raises(ValueError, match="label awam bawaan"):
        ko.kembalikan_label("tidak-ada", actor_id="admin", revisi_diharapkan=0, path=db)
    assert not db.exists()


@pytest.mark.parametrize("actor", ["", "   ", None, 5, "a" * 101])
def test_validasi_tolak_actor_id_tak_sah(db, actor):
    with pytest.raises(ValueError, match="pelaku"):
        _ubah_cp(db, actor=actor)
    with pytest.raises(ValueError, match="pelaku"):
        _ubah_label(db, actor=actor)
    assert not db.exists()


@pytest.mark.parametrize("revisi", [-1, "0", None, True, 1.0])
def test_validasi_tolak_revisi_diharapkan_tak_sah(db, revisi):
    with pytest.raises(ValueError, match="Revisi"):
        _ubah_cp(db, revisi=revisi)


# --- baca: fail ke bawaan -----------------------------------------------------

def test_baca_db_bytes_acak_memakai_bawaan_dan_mencatat_log(db, caplog):
    db.write_bytes(bytes(range(256)) * 64)
    with caplog.at_level(logging.WARNING, logger=ko.__name__):
        efektif = ko.cp_efektif(path=db)
    assert efektif == {k: tuple(v) for k, v in kurikulum_cp.CP_PER_GRUP.items()}
    assert ko.label_efektif(path=db) == LABEL_BAWAAN
    assert "memakai bawaan" in caplog.text


def test_baca_user_version_asing_memakai_bawaan(db):
    _db_tangan(db, versi=2, baris_cp=[(*KUNCI, '[["A.bilangan.1", "penuh"]]', 1)])
    assert ko.cp_efektif(path=db)[KUNCI] == BAWAAN_CP


def test_baca_tabel_hilang_memakai_bawaan(db):
    with sqlite3.connect(db) as kon:
        kon.execute("CREATE TABLE lain (x INTEGER)")
        kon.execute(f"PRAGMA user_version = {ko.VERSI_SKEMA}")
    kon.close()
    assert ko.label_efektif(path=db) == LABEL_BAWAAN


def test_baca_baris_rusak_memakai_bawaan_sedang_baris_lain_tetap_override(db, caplog):
    _db_tangan(db, baris_cp=[
        (*KUNCI, "{bukan json", 4),
        ("pengukuran", "waktu", '[["Z.asing.9", "penuh"]]', 2),
        ("pengukuran", "skala", '[["C.aljabar.3", "asing"]]', 3),
        ("pengukuran", "konversi", '[["B.pengukuran.2", "penuh"], ["B.pengukuran.2", "penuh"]]', 1),
        ("asing", "kunci", "[]", 1),
        ("pengukuran", "luas_volume", '[["A.pengukuran.1", "penuh"]]', 5),
    ], baris_label=[
        (TOPIK, "x" * 41, 2),
        (TOPIK_LAIN, "Statistik Ria", 3),
        (TANPA_LABEL, "Tak boleh", 1),
    ])

    with caplog.at_level(logging.WARNING, logger=ko.__name__):
        cp = ko.cp_efektif(path=db)
        label = ko.label_efektif(path=db)

    bawaan = kurikulum_cp.CP_PER_GRUP
    for kunci in (KUNCI, ("pengukuran", "waktu"), ("pengukuran", "skala"), ("pengukuran", "konversi")):
        assert cp[kunci] == bawaan[kunci]
    assert cp[("pengukuran", "luas_volume")] == (("A.pengukuran.1", "penuh"),)
    assert ("asing", "kunci") not in cp
    assert label[TOPIK] == LABEL_BAWAAN[TOPIK]
    assert label[TOPIK_LAIN] == "Statistik Ria"
    assert TANPA_LABEL not in label
    item = next(i for i in ko.daftar_cp(path=db) if (i.topik_id, i.grup_kode) == KUNCI)
    assert item.sumber == "bawaan" and item.revisi == 4  # revisi asli tetap, agar admin bisa menimpa
    assert "{bukan json" not in caplog.text  # log tanpa isi
    assert "Tak boleh" not in caplog.text
    assert f"topik tak dikenal {TANPA_LABEL}" in caplog.text


def test_baca_override_label_bentrok_dibuang_sedang_yang_lain_tetap(db):
    _db_tangan(db, baris_label=[
        (TOPIK, LABEL_BAWAAN[TOPIK_LAIN].lower(), 1),
        ("geometri-datar", "Bentuk", 1),
    ])
    label = ko.label_efektif(path=db)
    assert label[TOPIK] == LABEL_BAWAAN[TOPIK]
    assert label["geometri-datar"] == "Bentuk"
    assert len({v.casefold() for v in label.values()}) == len(label)


def test_baca_kolom_nilai_null_dan_revisi_tak_sah(db):
    _db_tangan(db, baris_cp=[(*KUNCI, None, 3), (*KUNCI_LAIN, '[["A.bilangan.1", "penuh"]]', "x")])
    cp = ko.cp_efektif(path=db)
    assert cp[KUNCI] == BAWAAN_CP and cp[KUNCI_LAIN] == kurikulum_cp.CP_PER_GRUP[KUNCI_LAIN]


# --- tulis ke DB asing --------------------------------------------------------

def test_tulis_ke_user_version_asing_galat_dan_berkas_tak_berubah(db):
    _db_tangan(db, versi=2)
    sebelum = db.read_bytes()
    with pytest.raises(ko.GalatKurikulum):
        _ubah_cp(db)
    with pytest.raises(ko.GalatKurikulum):
        _ubah_label(db)
    assert db.read_bytes() == sebelum


def test_tulis_ke_db_v0_berisi_tabel_asing_galat_dan_tak_berubah(db):
    with sqlite3.connect(db) as kon:
        kon.execute("CREATE TABLE milik_orang (x INTEGER)")
    kon.close()
    sebelum = db.read_bytes()
    with pytest.raises(ko.GalatKurikulum):
        _ubah_cp(db)
    assert db.read_bytes() == sebelum


def test_tulis_ke_berkas_bukan_sqlite_galat(db):
    db.write_bytes(bytes(range(256)) * 64)
    with pytest.raises(ko.GalatKurikulum):
        _ubah_cp(db)


def test_tulis_ke_direktori_tak_ada_galat(tmp_path):
    with pytest.raises(ko.GalatKurikulum):
        _ubah_cp(tmp_path / "tidak-ada" / "kurikulum.db")


# --- cache --------------------------------------------------------------------

def test_cache_setelah_ubah_baca_langsung_melihat_nilai_baru(db):
    assert ko.cp_efektif(path=db)[KUNCI] == BAWAAN_CP
    _ubah_cp(db)
    assert ko.cp_efektif(path=db)[KUNCI] == BARU_NORMAL
    assert ko.label_efektif(path=db)[TOPIK] == LABEL_BAWAAN[TOPIK]
    _ubah_label(db)
    assert ko.label_efektif(path=db)[TOPIK] == "Ukur-ukur"


def test_cache_hasil_baca_dipakai_dalam_ttl_dan_kedaluwarsa_sesudahnya(db):
    waktu = {"t": 1000.0}
    ko._jam = lambda: waktu["t"]
    _ubah_cp(db)
    assert ko.cp_efektif(path=db)[KUNCI] == BARU_NORMAL
    with sqlite3.connect(db) as kon:  # perubahan di luar API tidak membersihkan cache
        kon.execute("UPDATE cp_grup SET isi_json = '[]'")
    kon.close()

    waktu["t"] += ko.TTL_DETIK - 1
    assert ko.cp_efektif(path=db)[KUNCI] == BARU_NORMAL
    waktu["t"] += 2
    assert ko.cp_efektif(path=db)[KUNCI] == ()


def test_hasil_baca_adalah_salinan_yang_aman_diubah_pemanggil(db):
    pertama = ko.cp_efektif(path=db)
    pertama[KUNCI] = ()
    del pertama[KUNCI_LAIN]
    kedua = ko.cp_efektif(path=db)
    assert kedua[KUNCI] == BAWAAN_CP and KUNCI_LAIN in kedua


# --- batas modul --------------------------------------------------------------

def test_modul_hanya_mengimpor_stdlib_dan_dua_modul_kurikulum():
    import ast

    sumber = Path(ko.__file__).read_text()
    diimpor = set()
    for simpul in ast.walk(ast.parse(sumber)):
        if isinstance(simpul, ast.Import):
            diimpor.update(a.name.split(".")[0] for a in simpul.names)
        elif isinstance(simpul, ast.ImportFrom) and simpul.module:
            diimpor.add(simpul.module.split(".")[0])
    lokal = {n for n in diimpor if n not in sys.stdlib_module_names} if hasattr(
        sys, "stdlib_module_names") else diimpor & {"web", "database", "topics", "generator"}
    assert lokal <= {"kurikulum_cp", "kurikulum_katalog"}
