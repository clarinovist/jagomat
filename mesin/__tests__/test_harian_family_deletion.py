"""Penghapusan keluarga menghapus data Latihan Harian anak target saja (siswa hanya dianonimkan, cascade tak berlaku)."""
import pytest

import database
import family_deletion as hapus


@pytest.fixture
def kon(tmp_path):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        yield k


def _isi(kon, siswa_id):
    sesi = kon.execute("INSERT INTO harian_sesi(siswa_id,tingkat,seed,jumlah_soal,mulai_epoch,status) VALUES (?,'t1',5,1,10,'berjalan')",
                       (siswa_id,)).lastrowid
    kon.execute("INSERT INTO harian_soal VALUES (?,1,'tambah_dasar','bilangan-dasar','P1','1. Bab','0','tt','{}','[\"1\",\"2\",\"3\",\"4\"]',0,'cara')", (sesi,))
    kon.execute("INSERT INTO harian_jawaban VALUES (?,1,0,1,11)", (sesi,))


def _hitung(kon, siswa_ids):
    q = ",".join("?" * len(siswa_ids))
    return tuple(kon.execute(sql % q, tuple(siswa_ids)).fetchone()[0] for sql in (
        "SELECT COUNT(*) FROM harian_sesi WHERE siswa_id IN (%s)",
        "SELECT COUNT(*) FROM harian_soal WHERE sesi_id IN (SELECT id FROM harian_sesi WHERE siswa_id IN (%s))",
        "SELECT COUNT(*) FROM harian_jawaban WHERE sesi_id IN (SELECT id FROM harian_sesi WHERE siswa_id IN (%s))"))


def test_hapus_harian_menghapus_anak_target_dan_tidak_menyentuh_lain(kon):
    target = kon.execute("INSERT INTO siswa(nama,tingkat,pemilik) VALUES ('Target','P1','keluarga-a')").lastrowid
    lain = kon.execute("INSERT INTO siswa(nama,tingkat,pemilik) VALUES ('Lain','P1','keluarga-b')").lastrowid
    _isi(kon, target)
    _isi(kon, lain)

    hapus._hapus_harian(kon, (target,))

    assert _hitung(kon, [target]) == (0, 0, 0)
    assert _hitung(kon, [lain]) == (1, 1, 1)


def test_hapus_harian_tanpa_siswa_atau_tanpa_tabel_tidak_error(kon):
    hapus._hapus_harian(kon, ())
    for tabel in ("harian_jawaban", "harian_soal", "harian_sesi"):
        kon.execute("DROP TABLE %s" % tabel)

    hapus._hapus_harian(kon, (1,))
