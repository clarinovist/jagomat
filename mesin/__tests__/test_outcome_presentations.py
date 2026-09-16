"""Provenance representasi outcome: metadata immutable, bukan bukti baru."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database
import question_views
import schema
import topic_solid_geometry


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.delenv("OSN_VISUAL_KELUARGA", raising=False)
    path = tmp_path / "outcome.db"
    database.siapkan(path)
    return path


def _sesi(kon, *, warisan=False, jumlah=2):
    siswa = database.tambah_siswa(kon, "Fixture provenance", "P6", pemilik="guru")
    soal = replace(topic_solid_geometry.volume_kubus_balok(
        "kubus_cari_s", s=4, V=64), level="P6")
    sesi = database.buat_sesi_dari_urutan(
        kon, siswa, seed=41, urutan=(soal.template_id,) * jumlah,
        topik="geometri-ruang", level="P6", soal_terpilih=(soal,) * jumlah)
    if warisan:
        kolom = ", ".join(n + " = NULL" for n in question_views.KOLOM_SNAPSHOT)
        kon.execute(f"UPDATE sesi_soal SET {kolom} WHERE sesi_id = ?", (sesi,))
    return siswa, sesi


def _selesaikan(kon, sesi):
    for butir in kon.execute("SELECT id AS sesi_soal_id FROM sesi_soal WHERE sesi_id = ?", (sesi,)):
        jawaban = database.simpan_jawaban(kon, butir["sesi_soal_id"], "0")
        database.simpan_diagnosis(kon, jawaban, False, "K", "K", "uji", "fixture")
    database.tandai_selesai(kon, sesi)


def _tabel(kon, nama):
    return tuple(tuple(b) for b in kon.execute(f"SELECT * FROM {nama} ORDER BY 1"))


def _riwayat(kon):
    return tuple(_tabel(kon, t) for t in (
        "konfirmasi_hasil", "snapshot_outcome", "kejadian_belajar", "sesi"))


def _konfirmasi_lama(kon, sesi, *, hubungan=None):
    """Fixture writer sebelum sidecar: hash kanonis lama tetap byte-identik."""
    butir = kon.execute("""SELECT ss.id AS sesi_soal_id, ss.nomor, s.template_id
        FROM sesi_soal ss JOIN soal s ON s.id = ss.soal_id
        WHERE ss.sesi_id = ? ORDER BY ss.nomor""", (sesi,)).fetchall()
    kanonis = tuple(dict(
        nomor=b["nomor"], template_id=b["template_id"], jawaban="0", benar=0,
        kode_final="K", malrule_id="uji", dilewati=0, level_efektif="P6",
        cek_pemahaman=None, target_template_id=None,
        target_kode_intervensi=None, target_malrule_id=None) for b in butir)
    serial = json.dumps(kanonis, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sidik = hashlib.sha256(serial.encode()).hexdigest()
    kid = kon.execute("""INSERT INTO konfirmasi_hasil
        (sesi_id, nomor_urut, guru, fingerprint) VALUES (?, 1, 'guru', ?)""",
        (sesi, sidik)).lastrowid
    for b, isi in zip(butir, kanonis):
        data = dict(isi, konfirmasi_id=kid,
                    sesi_soal_id=b["sesi_soal_id"] if hubungan is None else hubungan)
        nama = ", ".join(data)
        tempat = ", ".join("?" for _ in data)
        kon.execute(f"INSERT INTO snapshot_outcome ({nama}) VALUES ({tempat})",
                    tuple(data.values()))
    kon.execute("""UPDATE sesi SET dikonfirmasi_guru = datetime('now'),
        fingerprint_konfirmasi = ? WHERE id = ?""", (sidik, sesi))
    return kid


@pytest.mark.parametrize("warisan,visual", [(False, False), (False, True), (True, False)])
def test_konfirmasi_menyimpan_snapshot_persis_dan_hash_tetap(db, monkeypatch, warisan, visual):
    if visual:
        monkeypatch.setenv("OSN_VISUAL_KELUARGA", "geometri-ruang")
    with database.buka(db) as kon:
        _, sesi = _sesi(kon, warisan=warisan)
        _selesaikan(kon, sesi)
        kid = database.konfirmasi_hasil(kon, sesi, "guru")
        sebelum = _riwayat(kon)
        assert database.konfirmasi_hasil(kon, sesi, "guru-lain") == kid
        assert _riwayat(kon) == sebelum
        sumber = database.isi_sesi(kon, sesi)
        aktual = kon.execute("""SELECT po.* FROM penyajian_outcome po
            JOIN snapshot_outcome so ON so.id = po.snapshot_outcome_id
            WHERE so.konfirmasi_id = ? ORDER BY so.nomor""", (kid,)).fetchall()
        assert len(aktual) == len(sumber) == 2
        for a, b in zip(aktual, sumber):
            assert a["mode_representasi"] == ("teks-v1" if warisan else b["mode_representasi"])
            assert a["fingerprint_penyajian"] == b["fingerprint_penyajian"]


def test_konfirmasi_historis_melengkapi_metadata_tanpa_versi_baru(db):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon)
        _selesaikan(kon, sesi)
        kid = _konfirmasi_lama(kon, sesi)
        sebelum = _riwayat(kon)
        assert database.konfirmasi_hasil(kon, sesi, "guru") == kid
        assert _riwayat(kon) == sebelum
        assert len(_tabel(kon, "penyajian_outcome")) == 2


def test_sidecar_tidak_bisa_diganti_insert_or_replace(db):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon)
        _selesaikan(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, "guru")
        sebelum = _tabel(kon, "penyajian_outcome")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            kon.execute("INSERT OR REPLACE INTO penyajian_outcome VALUES (?, ?, ?)", sebelum[0])
        assert _tabel(kon, "penyajian_outcome") == sebelum


@pytest.mark.parametrize("warisan,visual", [(False, False), (False, True), (True, False)])
def test_reader_memakai_sidecar_setelah_flag_off_bukan_diagnosis_mutable(db, monkeypatch, warisan, visual):
    if visual:
        monkeypatch.setenv("OSN_VISUAL_KELUARGA", "geometri-ruang")
    with database.buka(db) as kon:
        siswa, sesi = _sesi(kon, warisan=warisan)
        _selesaikan(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, "guru")
        harapan = tuple(("teks-v1" if warisan else b["mode_representasi"],
                         b["fingerprint_penyajian"]) for b in database.isi_sesi(kon, sesi))
    monkeypatch.delenv("OSN_VISUAL_KELUARGA", raising=False)
    with database.buka(db) as kon:
        kon.execute("UPDATE diagnosis SET kode_final = 'H'")
        sebelum = _riwayat(kon)
        bukti = database.muat_bukti_siklus(kon, siswa)
        outcomes = bukti.sesi[0].outcomes
        assert tuple((o.mode_representasi, o.fingerprint_penyajian) for o in outcomes) == harapan
        assert all(o.kode_final == "K" for o in outcomes)
        assert _riwayat(kon) == sebelum


def test_reader_tidak_menebak_teks_atau_menulis_saat_metadata_hilang(db):
    with database.buka(db) as kon:
        siswa, sesi = _sesi(kon)
        _selesaikan(kon, sesi)
        _konfirmasi_lama(kon, sesi)
        sebelum = _riwayat(kon)
        with pytest.raises(ValueError, match="provenance.*hilang"):
            database.muat_bukti_siklus(kon, siswa)
        assert _riwayat(kon) == sebelum
        assert _tabel(kon, "penyajian_outcome") == ()


def _skema_tanpa_sidecar(kon, *, pra_snapshot):
    """Pasang skema pra-fase 8, tanpa menurunkan guard tabel outcome lama."""
    if pra_snapshot:
        kon.execute("""CREATE TABLE sesi_soal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesi_id INTEGER NOT NULL REFERENCES sesi(id) ON DELETE CASCADE,
            soal_id INTEGER NOT NULL REFERENCES soal(id), nomor INTEGER NOT NULL,
            UNIQUE (sesi_id, nomor))""")
    bagian = ""
    for baris in schema.SKEMA.splitlines(keepends=True):
        bagian += baris
        if not sqlite3.complete_statement(bagian):
            continue
        # Fixture pra-PG tidak memasang trigger baru yang membutuhkan snapshot.
        if 'penyajian_outcome' not in bagian and not ('CREATE TRIGGER' in bagian and 'pilihan_' in bagian) and not (
                pra_snapshot and "sesi_soal_snapshot" in bagian):
            kon.execute(bagian)
        bagian = ""


@pytest.mark.parametrize("pra_snapshot", [True, False])
def test_upgrade_skema_lama_sebelum_backfill(tmp_path, monkeypatch, pra_snapshot):
    path = tmp_path / "pra-fase8.db"
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "geometri-ruang")
    with database.buka(path) as kon:
        _skema_tanpa_sidecar(kon, pra_snapshot=pra_snapshot)
        if pra_snapshot:
            siswa = database.tambah_siswa(kon, "Fixture lama", "P6", pemilik="guru")
            soal = replace(topic_solid_geometry.volume_kubus_balok(
                "kubus_cari_s", s=4, V=64), level="P6")
            soal_id = database.simpan_soal(kon, soal)
            sesi = kon.execute("INSERT INTO sesi (siswa_id, seed, level) VALUES (?, 41, 'P6')",
                               (siswa,)).lastrowid
            assert sesi is not None
            kon.execute("INSERT INTO sesi_soal (sesi_id, soal_id, nomor) VALUES (?, ?, 1)",
                        (sesi, soal_id))
            harapan = (("teks-v1", None),)
        else:
            _, sesi = _sesi(kon)
            harapan = tuple((b["mode_representasi"], b["fingerprint_penyajian"])
                            for b in database.isi_sesi(kon, sesi))
        _selesaikan(kon, sesi)
        kid = _konfirmasi_lama(kon, sesi)
        sebelum = _riwayat(kon)
        assert not kon.execute("SELECT 1 FROM sqlite_master WHERE name = 'penyajian_outcome'").fetchall()
    monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    for _ in range(2):
        database.siapkan(path)
        with database.buka(path) as kon:
            assert _riwayat(kon) == sebelum
            assert tuple(b[1:] for b in _tabel(kon, "penyajian_outcome")) == harapan
            assert database.konfirmasi_hasil(kon, sesi, "guru") == kid
            assert _riwayat(kon) == sebelum
            assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
            assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_konfirmasi_tidak_menghilangkan_butir_yang_sumbernya_putus(db):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon)
        kon.commit()
        kon.execute("PRAGMA foreign_keys = OFF")
        kon.execute("UPDATE sesi_soal SET soal_id = 99999 WHERE nomor = 2")
        _selesaikan(kon, sesi)
        sebelum = _riwayat(kon)
        with pytest.raises(ValueError, match="hubungan|snapshot"):
            database.konfirmasi_hasil(kon, sesi, "guru")
        assert _riwayat(kon) == sebelum
        assert _tabel(kon, "penyajian_outcome") == ()


def test_konfirmasi_menunggu_commit_dan_rollback_pemanggil(db):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon)
        _selesaikan(kon, sesi)
    with database.buka(db) as kon:
        database.konfirmasi_hasil(kon, sesi, "guru")
        with database.buka(db) as pembaca:
            assert _tabel(pembaca, "snapshot_outcome") == ()
            assert _tabel(pembaca, "penyajian_outcome") == ()
        kon.rollback()
        assert _tabel(kon, "snapshot_outcome") == ()
        assert _tabel(kon, "penyajian_outcome") == ()
        assert kon.execute("SELECT dikonfirmasi_guru FROM sesi WHERE id = ?", (sesi,)).fetchone()[0] is None


@pytest.mark.parametrize("kerusakan", ["parsial", "json", "mode", "parameter"])
def test_upgrade_rusak_rollback_skema_dan_backfill(tmp_path, kerusakan):
    path = tmp_path / "rusak.db"
    with database.buka(path) as kon:
        _skema_tanpa_sidecar(kon, pra_snapshot=True)
        database.migrasi(kon)
        _, sesi = _sesi(kon)
        if kerusakan == "parameter":
            kon.execute("UPDATE soal SET parameter = '[]'")
        else:
            kolom, nilai = {"parsial": ("penyajian_json", None),
                            "json": ("penyajian_json", "{}"),
                            "mode": ("mode_representasi", "palsu-v1")}[kerusakan]
            kon.execute(f"UPDATE sesi_soal SET {kolom} = ? WHERE nomor = 2", (nilai,))
        _selesaikan(kon, sesi)
        _konfirmasi_lama(kon, sesi)
        sebelum = _riwayat(kon)
        skema_sebelum = tuple(kon.execute("SELECT name, sql FROM sqlite_master ORDER BY name"))
    with pytest.raises(ValueError, match="snapshot"):
        database.siapkan(path)
    with database.buka(path) as kon:
        assert _riwayat(kon) == sebelum
        assert tuple(kon.execute("SELECT name, sql FROM sqlite_master ORDER BY name")) == skema_sebelum
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("kerusakan", ["json", "mode", "sidik"])
def test_trigger_memvalidasi_snapshot_bukan_menyalin_raw_fields(db, kerusakan):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon, jumlah=1)
        kolom, nilai = {"json": ("penyajian_json", "{}"),
                        "mode": ("mode_representasi", "palsu-v1"),
                        "sidik": ("fingerprint_penyajian", "0" * 64)}[kerusakan]
        kon.execute(f"UPDATE sesi_soal SET {kolom} = ?", (nilai,))
        _selesaikan(kon, sesi)
        _konfirmasi_lama(kon, sesi)
        b = database.isi_sesi(kon, sesi)[0]
        oid = kon.execute("SELECT id FROM snapshot_outcome").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError, match="provenance"):
            kon.execute("INSERT INTO penyajian_outcome VALUES (?, ?, ?)",
                        (oid, b["mode_representasi"], b["fingerprint_penyajian"]))
        assert _tabel(kon, "penyajian_outcome") == ()


@pytest.mark.parametrize("warisan", [True, False])
def test_insert_raw_sah_dan_fk_tidak_bisa_dipalsukan(db, warisan):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon, warisan=warisan, jumlah=1)
        _selesaikan(kon, sesi)
        _konfirmasi_lama(kon, sesi)
        b = database.isi_sesi(kon, sesi)[0]
        oid = kon.execute("SELECT id FROM snapshot_outcome").fetchone()[0]
        data = (oid, "teks-v1", b["fingerprint_penyajian"])
        kon.execute("INSERT INTO penyajian_outcome VALUES (?, ?, ?)", data)
        with pytest.raises(sqlite3.IntegrityError, match="provenance"):
            kon.execute("INSERT INTO penyajian_outcome VALUES (?, ?, ?)", (99999, *data[1:]))
        assert _tabel(kon, "penyajian_outcome") == (data,)


def test_raw_sql_tanpa_adapter_gagal_tertutup(db):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon, jumlah=1)
        _selesaikan(kon, sesi)
        _konfirmasi_lama(kon, sesi)
        b = database.isi_sesi(kon, sesi)[0]
        oid = kon.execute("SELECT id FROM snapshot_outcome").fetchone()[0]
    with sqlite3.connect(str(db)) as kon:
        with pytest.raises(sqlite3.OperationalError, match="no such function"):
            kon.execute("INSERT INTO penyajian_outcome VALUES (?, ?, ?)",
                        (oid, b["mode_representasi"], b["fingerprint_penyajian"]))
        assert _tabel(kon, "penyajian_outcome") == ()


def test_permukaan_murid_tidak_membaca_sidecar_atau_bukti(db):
    import students
    with database.buka(db) as kon:
        siswa, sesi = _sesi(kon)
        _selesaikan(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, "guru")

        def palang(aksi, tabel, kolom, *_):
            if aksi == sqlite3.SQLITE_READ and (
                tabel in {"snapshot_outcome", "penyajian_outcome", "diagnosis"}
                or kolom in {"kunci", "malrule_id", "kode_final", "kode_usulan", "alasan"}
            ):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        kon.set_authorizer(palang)
        try:
            assert len(students.soal_murid(kon, sesi, siswa)) == 2
            with pytest.raises(sqlite3.DatabaseError):
                kon.execute("SELECT * FROM penyajian_outcome").fetchall()
        finally:
            kon.set_authorizer(lambda *_: sqlite3.SQLITE_OK)


def test_snapshot_sesi_tetap_terkunci_setelah_konfirmasi(db):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon)
        _selesaikan(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, "guru")
        sebelum = _tabel(kon, "sesi_soal")
        with pytest.raises(sqlite3.IntegrityError, match="terkunci"):
            kon.execute("UPDATE sesi_soal SET mode_representasi = 'palsu-v1'")
        assert _tabel(kon, "sesi_soal") == sebelum


def test_hubungan_lintas_sesi_ditolak_trigger_dan_backfill(db):
    import outcome_presentations
    with database.buka(db) as kon:
        siswa, sesi = _sesi(kon, jumlah=1)
        butir = database.isi_sesi(kon, sesi)[0]
        sesi_lain = kon.execute("INSERT INTO sesi (siswa_id, seed) VALUES (?, 99)",
                                (siswa,)).lastrowid
        kid = kon.execute("""INSERT INTO konfirmasi_hasil
            (sesi_id, nomor_urut, guru, fingerprint) VALUES (?, 1, 'guru', 'fixture')""",
            (sesi_lain,)).lastrowid
        oid = kon.execute("""INSERT INTO snapshot_outcome
            (konfirmasi_id, sesi_soal_id, nomor, template_id, benar, level_efektif)
            VALUES (?, ?, 1, ?, 1, 'P6')""",
            (kid, butir["sesi_soal_id"], butir["template_id"])).lastrowid
        sebelum = _riwayat(kon)
        with pytest.raises(sqlite3.IntegrityError, match="provenance"):
            kon.execute("INSERT INTO penyajian_outcome VALUES (?, ?, ?)",
                        (oid, butir["mode_representasi"], butir["fingerprint_penyajian"]))
        with pytest.raises(ValueError, match="hubungan"):
            outcome_presentations.lengkapi(kon)
        assert _riwayat(kon) == sebelum
        assert _tabel(kon, "penyajian_outcome") == ()


def test_sidecar_fk_menjaga_snapshot_dari_replace(db):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon, jumlah=1)
        _selesaikan(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, "guru")
        sebelum = _riwayat(kon)
        metadata = _tabel(kon, "penyajian_outcome")
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT OR REPLACE INTO snapshot_outcome SELECT * FROM snapshot_outcome")
        assert _riwayat(kon) == sebelum
        assert _tabel(kon, "penyajian_outcome") == metadata


def test_migrasi_menambah_hanya_sidecar_idempoten_dan_integritas(db):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon, warisan=True)
        _selesaikan(kon, sesi)
        _konfirmasi_lama(kon, sesi)
        sebelum = _riwayat(kon)
        guard = tuple(kon.execute("""SELECT name, sql FROM sqlite_master
            WHERE type = 'trigger' AND name LIKE 'snapshot_outcome_%' ORDER BY name"""))
    for _ in range(2):
        database.siapkan(db)
        with database.buka(db) as kon:
            assert _riwayat(kon) == sebelum
            assert tuple(kon.execute("""SELECT name, sql FROM sqlite_master
                WHERE type = 'trigger' AND name LIKE 'snapshot_outcome_%' ORDER BY name""")) == guard
            assert len(_tabel(kon, "penyajian_outcome")) == 2
            assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
            assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            fk = kon.execute("PRAGMA foreign_key_list(penyajian_outcome)").fetchone()
            assert fk["table"] == "snapshot_outcome" and fk["on_delete"] == "RESTRICT"


@pytest.mark.parametrize("tabel", ["snapshot_outcome", "penyajian_outcome"])
@pytest.mark.parametrize("aksi", ["UPDATE", "DELETE"])
def test_snapshot_dan_sidecar_append_only(db, tabel, aksi):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon)
        _selesaikan(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, "guru")
        sebelum = _tabel(kon, tabel)
        kolom = "nomor" if tabel == "snapshot_outcome" else "mode_representasi"
        sql = f"UPDATE {tabel} SET {kolom} = {kolom}" if aksi == "UPDATE" else f"DELETE FROM {tabel}"
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            kon.execute(sql)
        assert _tabel(kon, tabel) == sebelum


@pytest.mark.parametrize("mode,sidik", [
    ("palsu-v1", "0" * 64), ("teks-v1", None), ("", "0" * 64),
    (None, "0" * 64), ("teks-v1", "g" * 64), ("teks-v1", "a" * 63),
])
def test_insert_raw_menolak_provenance_palsu(db, mode, sidik):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon, jumlah=1)
        _selesaikan(kon, sesi)
        _konfirmasi_lama(kon, sesi)
        oid = kon.execute("SELECT id FROM snapshot_outcome").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO penyajian_outcome VALUES (?, ?, ?)", (oid, mode, sidik))
        assert _tabel(kon, "penyajian_outcome") == ()


@pytest.mark.parametrize("kolom,nilai", [
    ("penyajian_json", "{}"), ("mode_representasi", "palsu-v1"),
    ("fingerprint_penyajian", "0" * 64),
])
def test_snapshot_raw_rusak_menggagalkan_konfirmasi_atomik(db, kolom, nilai):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon)
        kon.execute(f"UPDATE sesi_soal SET {kolom} = ? WHERE nomor = 2", (nilai,))
        _selesaikan(kon, sesi)
        sebelum = _riwayat(kon)
        with pytest.raises(ValueError, match="snapshot|penyajian"):
            database.konfirmasi_hasil(kon, sesi, "guru")
        assert _riwayat(kon) == sebelum
        assert _tabel(kon, "penyajian_outcome") == ()


def test_sidecar_gagal_di_butir_kedua_menggulung_seluruh_konfirmasi(db):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon)
        _selesaikan(kon, sesi)
        kon.execute("""CREATE TRIGGER simulasi_gagal_sidecar
            BEFORE INSERT ON penyajian_outcome
            WHEN (SELECT nomor FROM snapshot_outcome WHERE id = NEW.snapshot_outcome_id) = 2
            BEGIN SELECT RAISE(ABORT, 'simulasi gagal sidecar'); END""")
        sebelum = _riwayat(kon)
        with pytest.raises(sqlite3.IntegrityError, match="simulasi gagal"):
            database.konfirmasi_hasil(kon, sesi, "guru")
        assert _riwayat(kon) == sebelum
        assert _tabel(kon, "penyajian_outcome") == ()


@pytest.mark.parametrize("hubungan", [99999, 2])
def test_migrasi_menolak_hubungan_hilang_atau_nomor_salah(db, hubungan):
    with database.buka(db) as kon:
        _, sesi = _sesi(kon)
        _selesaikan(kon, sesi)
        # Satu snapshot saja agar FK logis yang buruk tidak tertutup UNIQUE.
        b = database.isi_sesi(kon, sesi)[0]
        kid = kon.execute("""INSERT INTO konfirmasi_hasil
            (sesi_id, nomor_urut, guru, fingerprint) VALUES (?, 1, 'guru', 'fixture')""", (sesi,)).lastrowid
        kon.execute("""INSERT INTO snapshot_outcome
            (konfirmasi_id, sesi_soal_id, nomor, template_id, benar, level_efektif)
            VALUES (?, ?, 1, ?, 1, 'P6')""", (kid, hubungan, b["template_id"]))
        sebelum = _riwayat(kon)
    with pytest.raises(ValueError, match="hubungan|snapshot"):
        database.siapkan(db)
    with database.buka(db) as kon:
        assert _riwayat(kon) == sebelum
        assert _tabel(kon, "penyajian_outcome") == ()
