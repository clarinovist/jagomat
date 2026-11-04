"""Tahap 2 G3: snapshot allowlist (topik, tahap netral, langkah) dari bukti terkonfirmasi."""
import re

import pytest

import database
import parent_report_snapshot as snap


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "snap.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        yield kon, database.tambah_siswa(kon, "Anak Sintetis", pemilik="guru")


def _sesi(kon, anak, topik="pola-bilangan", tanggal="2026-11-10", terkonfirmasi=True, batal=False):
    sesi = database.buat_sesi(kon, anak, 40 + kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0],
                              jumlah_soal=3, topik=topik)
    kon.execute("UPDATE sesi SET tanggal = ? WHERE id = ?", (tanggal, sesi))
    if terkonfirmasi:
        database.tandai_selesai(kon, sesi)
        butir = database.isi_sesi(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, "guru", dilewati={b["sesi_soal_id"] for b in butir})
    if batal:
        kon.execute("UPDATE sesi SET dibatalkan = datetime('now') WHERE id = ?", (sesi,))
    return sesi


def test_tanpa_sesi_terkonfirmasi_topik_kosong(db):
    kon, anak = db
    _sesi(kon, anak, terkonfirmasi=False)
    hasil = snap.bangun(kon, anak, "2026-11-01", "2026-11-30")
    assert hasil["topik"] == []


def test_topik_hanya_dari_sesi_selesai_terkonfirmasi_dalam_periode(db):
    kon, anak = db
    _sesi(kon, anak, "pola-bilangan", "2026-11-10")
    _sesi(kon, anak, "geometri-datar", "2026-11-12")
    _sesi(kon, anak, "pola-bilangan", "2026-11-20")
    _sesi(kon, anak, "statistika", "2026-10-30")            # di luar periode
    _sesi(kon, anak, "logika", "2026-11-15", terkonfirmasi=False)
    hasil = snap.bangun(kon, anak, "2026-11-01", "2026-11-30")
    assert hasil["topik"] == ["Pola Bilangan", "Geometri Datar"]


def test_sesi_batal_dan_anak_lain_tidak_masuk(db):
    kon, anak = db
    lain = database.tambah_siswa(kon, "Anak Lain", pemilik="guru")
    _sesi(kon, lain, "logika", "2026-11-10")
    sesi = _sesi(kon, anak, "logika", "2026-11-11")
    kon.execute("UPDATE sesi SET dibatalkan = datetime('now') WHERE id = ?", (sesi,))
    assert snap.bangun(kon, anak, "2026-11-01", "2026-11-30")["topik"] == []


def test_bentuk_snapshot_tepat_allowlist(db):
    kon, anak = db
    _sesi(kon, anak)
    hasil = snap.bangun(kon, anak, "2026-11-01", "2026-11-30")
    assert set(hasil) == {"versi", "topik", "tahap", "langkah"}
    assert hasil["versi"] == 1
    assert set(hasil["tahap"]) == {"nomor", "label", "uraian"}
    assert 1 <= hasil["tahap"]["nomor"] <= 6
    assert hasil["tahap"]["label"] in snap.LABEL_TAHAP
    assert hasil["langkah"] == snap.LANGKAH[hasil["tahap"]["nomor"] - 1]


def test_tabel_kalimat_enam_tahap_netral():
    assert len(snap.LABEL_TAHAP) == len(snap.URAIAN) == len(snap.LANGKAH) == 6
    teks = " ".join(snap.URAIAN + snap.LANGKAH + snap.LABEL_TAHAP).lower()
    for terlarang in ("malrule", "diagnos", "kunci", "variasi", "p3", "p4", "p5", "p6", "%", "skor",
                      "salah", "benar", "lemah", "kelemahan", "eskalasi", "kode "):
        assert terlarang not in teks, terlarang
    assert not re.search(r"\d", teks)


def test_bangun_tidak_menulis_apa_pun(db):
    kon, anak = db
    _sesi(kon, anak)
    sebelum = tuple(kon.iterdump())
    snap.bangun(kon, anak, "2026-11-01", "2026-11-30")
    assert tuple(kon.iterdump()) == sebelum


def test_tanpa_tahap_tampil_bila_reducer_di_luar_peta(db, monkeypatch):
    kon, anak = db
    import learning_cycle_ui
    monkeypatch.setattr(learning_cycle_ui, "_tahap_tampil", lambda rencana, bukti: None)
    hasil = snap.bangun(kon, anak, "2026-11-01", "2026-11-30")
    assert hasil["tahap"] is None and hasil["langkah"] == snap.LANGKAH_TANPA_TAHAP


def test_label_tahap_sama_dengan_ui_beranda():
    import learning_cycle_ui
    assert snap.LABEL_TAHAP == learning_cycle_ui._LABEL_TAHAP
