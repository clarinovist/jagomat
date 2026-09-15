"""Regresi statistik aktivitas: penyebut, periode, status, dan isolasi anak."""
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database
import report_metrics as metrik
import reports

HARI = date(2026, 9, 15)


@pytest.fixture
def db(tmp_path, monkeypatch):
    import auth
    monkeypatch.setattr(auth, "BERKAS_SANDI", tmp_path / "sandi.json")
    path = tmp_path / "uji.db"
    database.siapkan(path)
    monkeypatch.setattr(metrik, "hari_wib", lambda: HARI)
    monkeypatch.setattr(reports, "hari_wib", lambda: HARI)
    return path


def sesi(kon, sid, jenis=("benar",), tanggal="2026-09-15", selesai=False, **opsi):
    sid_sesi = database.buat_sesi_dari_urutan(
        kon, sid, 401, tuple("deret_aritmetika" for _ in jenis), level=opsi.get("level", "P3")
    )
    kon.execute("UPDATE sesi SET tanggal='2020-01-01', tujuan=?, mode=? WHERE id=?",
                (opsi.get("tujuan", "bebas"), opsi.get("mode", "diagnostik"), sid_sesi))
    for b, j in zip(database.isi_sesi(kon, sid_sesi), jenis):
        if j == "tanpa":
            continue
        jid = database.simpan_jawaban(kon, b["sesi_soal_id"],
                                      "" if j in {"kosong", "T"} else b["kunci"],
                                      "" if j == "kosong" else "cara contoh")
        kon.execute("UPDATE jawaban SET dicatat=? WHERE id=?", (tanggal, jid))
        if j not in {"kosong", "belum"}:
            kode = None if j in {"benar", "unknown"} else j
            database.simpan_diagnosis(kon, jid, j == "benar", kode, kode)
    if selesai:
        database.tandai_selesai(kon, sid_sesi)
    return sid_sesi


def test_regresi_laporan_menghitung_dijawab_bukan_soal_tersedia(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak Uji", pemilik="guru")
        sesi(kon, sid, ("benar",)*3 + ("H", "tanpa"), selesai=True)
        h = reports.halaman_laporan(kon, sid).decode()
    assert "75%" in h
    assert "soal dikerjakan" in h
    assert "Ringkasan untuk orang tua" not in h
    assert "Hasil dan tren per materi" in h


def test_status_tidak_dinilai_bukan_salah_dan_sesi_berjalan_ikut(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Aktivitas")
        sesi(kon, sid, ("benar", "H", "K", "N", "T", "unknown", "belum", "kosong", "tanpa"))
        data = metrik.statistik_laporan(kon, sid, HARI)
    assert data.kini == metrik.Hitungan(7, 1, 2, 3, 1)
    assert data.kini.dinilai == 3
    assert data.kini.persen == pytest.approx(100 / 3)


def test_batas_mingguan_tanggal_jawaban_bukan_sesi(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Batas")
        for tanggal in ["2026-09-01", "2026-09-02", "2026-09-08", "2026-09-09", "2026-09-15", "2026-09-16", "invalid"]:
            sesi(kon, sid, tanggal=tanggal)
        data = metrik.statistik_laporan(kon, sid, HARI)
    assert data.kini.dikerjakan == data.lalu.dikerjakan == 2
    assert data.semua.dikerjakan == 7
    assert data.tanpa_tanggal == 1
    assert data.mulai == date(2026, 9, 9)


def test_koreksi_tidak_menggandakan_aktivitas_dan_read_only(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Koreksi")
        ses = sesi(kon, sid, ("H",), tanggal="2026-09-03")
        b = database.isi_sesi(kon, ses)[0]
        for _ in range(3):
            database.simpan_jawaban(kon, b["sesi_soal_id"], b["kunci"], "cara")
            database.simpan_diagnosis(kon, b["jawaban_id"], True, None, None)
        awal = tuple(kon.iterdump())
        data = metrik.statistik_laporan(kon, sid, HARI)
        assert tuple(kon.iterdump()) == awal
    assert data.semua.dikerjakan == data.lalu.benar == 1
    assert data.kini.dikerjakan == 0


def test_asing_dan_sesi_batal_tidak_masuk(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Milik")
        asing = database.tambah_siswa(kon, "Asing")
        sesi(kon, sid)
        sesi(kon, asing, ("H",)*7)
        batal = sesi(kon, sid, ("H",)*3)
        kon.execute("UPDATE sesi SET dibatalkan='2026-09-15' WHERE id=?", (batal,))
        data = metrik.statistik_laporan(kon, sid, HARI)
        tugas = metrik.tugas_belum_selesai(kon, sid)
    assert data.kini.dikerjakan == data.kini.benar == 1
    assert len(tugas) == 1


def test_snapshot_dilewati_tidak_menjadi_salah_tapi_kerja_tetap_tercatat(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Lewat")
        ses = sesi(kon, sid, ("benar", "H"), selesai=True)
        butir = database.isi_sesi(kon, ses)
        database.konfirmasi_hasil(kon, ses, "guru", dilewati={butir[1]["sesi_soal_id"]})
        data = metrik.statistik_laporan(kon, sid, HARI)
    assert data.kini == metrik.Hitungan(dikerjakan=2, benar=1, dilewati=1, terkonfirmasi=1)


def test_invalidasi_rekonfirmasi_snapshot_tidak_ganda(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Snapshot")
        ses = sesi(kon, sid, ("benar",), selesai=True)
        database.konfirmasi_hasil(kon, ses, "guru")
        b = database.isi_sesi(kon, ses)[0]
        database.simpan_diagnosis(kon, b["jawaban_id"], False, "H", "H")
        belum = metrik.statistik_laporan(kon, sid, HARI)
        database.konfirmasi_hasil(kon, ses, "guru")
        data = metrik.statistik_laporan(kon, sid, HARI)
    assert belum.kini.salah == 1 and belum.kini.terkonfirmasi == 0
    assert data.kini.salah == data.kini.terkonfirmasi == data.kini.dikerjakan == 1


@pytest.mark.parametrize("opsi", [{"level":"P4"}, {"tujuan":"penguatan"}, {"mode":"drill"}])
def test_kelompok_beda_tidak_dibandingkan(db, opsi):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Banding")
        sesi(kon, sid, ("H",)*5, tanggal="2026-09-03")
        sesi(kon, sid, ("benar",)*5, **opsi)
        data = metrik.statistik_laporan(kon, sid, HARI)
    assert len(data.materi) == 2
    assert not data.sebanding


def test_perubahan_hanya_kelompok_sama_dengan_dasar_cukup(db):
    from report_dashboard import _perubahan
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Tren")
        sesi(kon, sid, ("benar",)*3 + ("H",)*2, tanggal="2026-09-03")
        sesi(kon, sid, ("benar",)*4 + ("H",))
        data = metrik.statistik_laporan(kon, sid, HARI)
    assert len(data.sebanding) == 1
    assert _perubahan(data.materi[0]) == "Naik 20 poin persentase"


def test_kosong_bukan_nol_persen(db):
    from report_dashboard import persen
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Kosong")
        sesi(kon, sid, ("tanpa", "kosong", "N", "T"))
        data = metrik.statistik_laporan(kon, sid, HARI)
    assert data.kini.persen is None
    assert persen(data.kini.persen) == "—"
    assert persen(99.5) == "99,5%"
