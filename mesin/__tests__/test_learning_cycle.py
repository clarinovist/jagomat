"""Kontrak data Fase 0 siklus belajar terpandu.

Status pedagogis belum direduksi di fase ini. Test mengunci bukti immutable,
provenance putaran, serta data yang dibutuhkan reducer Fase 1 untuk menolak
sesi stale, beda level, belum lengkap, belum dikonfirmasi, atau dibatalkan.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from learning_cycle import (  # noqa: E402
    BuktiSiklus,
    KejadianSiklus,
    OutcomeSiklus,
    PutaranSiklus,
    SesiSiklus,
    intervensi_untuk,
    rencana_berikutnya,
)


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "siklus.db"
    database.siapkan(path)
    return path


def _sesi_satu_butir(kon, *, nama="Anak", level="P3", tujuan="bebas"):
    siswa_id = database.tambah_siswa(kon, nama, tingkat=level)
    sesi_id = database.buat_sesi(
        kon, siswa_id, seed=7, level=level, jumlah_soal=1
    )
    kon.execute("UPDATE sesi SET tujuan = ? WHERE id = ?", (tujuan, sesi_id))
    butir = database.isi_sesi(kon, sesi_id)[0]
    return siswa_id, sesi_id, butir


def _isi_dan_selesaikan(
    kon, sesi_id, butir, *, kode="K", malrule_id: str | None = "m-1"
):
    jawaban_id = database.simpan_jawaban(
        kon, butir["sesi_soal_id"], jawaban="0", cara="menghitung"
    )
    database.simpan_diagnosis(
        kon,
        jawaban_id,
        benar=False,
        kode_usulan=kode,
        kode_final=kode,
        malrule_id=malrule_id,
        alasan="cara lama",
    )
    database.tandai_selesai(kon, sesi_id)
    return jawaban_id


def test_sesi_manual_baru_tetap_bebas_tanpa_metadata_siklus_rekaan(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Manual")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=11, jumlah_soal=1)
        sesi = kon.execute(
            """SELECT tujuan, dikonfirmasi_guru, fingerprint_konfirmasi,
                      putaran_id, bagian_checkpoint, dibatalkan
               FROM sesi WHERE id = ?""",
            (sesi_id,),
        ).fetchone()

    assert dict(sesi) == {
        "tujuan": "bebas",
        "dikonfirmasi_guru": None,
        "fingerprint_konfirmasi": None,
        "putaran_id": None,
        "bagian_checkpoint": None,
        "dibatalkan": None,
    }


def test_buat_putaran_dan_tautkan_sesi_tidak_menyisakan_mutasi_parsial(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Atomis", tingkat="P3")
        valid_1 = database.buat_sesi(kon, siswa_id, 1, level="P3", jumlah_soal=1)
        valid_2 = database.buat_sesi(kon, siswa_id, 2, level="P3", jumlah_soal=1)
        beda_level = database.buat_sesi(
            kon, siswa_id, 3, level="P4", jumlah_soal=1
        )

        with pytest.raises(ValueError, match="level sesi berbeda"):
            database.buat_putaran_fokus(
                kon, siswa_id, "P3", sesi_ids=[valid_1, beda_level]
            )
        assert kon.execute("SELECT COUNT(*) FROM putaran_fokus").fetchone()[0] == 0
        assert kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE putaran_id IS NOT NULL"
        ).fetchone()[0] == 0

        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        with pytest.raises(ValueError, match="level sesi berbeda"):
            database.tautkan_sesi_putaran(
                kon, putaran_id, [valid_1, valid_1, beda_level]
            )
        assert kon.execute(
            "SELECT putaran_id FROM sesi WHERE id = ?", (valid_1,)
        ).fetchone()[0] is None

        database.tautkan_sesi_putaran(
            kon, putaran_id, [valid_1, valid_1, valid_2]
        )
        tertaut = kon.execute(
            "SELECT id FROM sesi WHERE putaran_id = ? ORDER BY id", (putaran_id,)
        ).fetchall()

    assert [baris["id"] for baris in tertaut] == [valid_1, valid_2]


def test_putaran_maksimal_dua_fokus_kanonis_dengan_provenance_multi_sesi(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Fokus")
        siswa_lain = database.tambah_siswa(kon, "Fokus Lain")
        sesi_1 = database.buat_sesi(kon, siswa_id, 1, jumlah_soal=1)
        sesi_2 = database.buat_sesi(kon, siswa_id, 2, jumlah_soal=1)
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        with pytest.raises(ValueError, match="bukan milik siswa"):
            database.buat_putaran_fokus(kon, siswa_lain, "P3", sesi_ids=[sesi_1])
        database.tautkan_sesi_putaran(kon, putaran_id, [sesi_1, sesi_2])

        fokus_1 = database.tambah_anggota_fokus(
            kon, putaran_id, "deret", "K", "salah-rasio", [sesi_1, sesi_2]
        )
        fokus_2 = database.tambah_anggota_fokus(
            kon, putaran_id, "umur", "H", None, [sesi_2]
        )

        with pytest.raises(ValueError, match="maksimal dua"):
            database.tambah_anggota_fokus(
                kon, putaran_id, "uang", "K", "salah-satuan", [sesi_1]
            )
        with pytest.raises(sqlite3.IntegrityError):
            database.tambah_anggota_fokus(
                kon, putaran_id, "deret", "K", "salah-rasio", [sesi_1]
            )

        sumber = kon.execute(
            """SELECT anggota_fokus_id, sesi_id FROM bukti_fokus
               ORDER BY anggota_fokus_id, sesi_id"""
        ).fetchall()

    assert [(r["anggota_fokus_id"], r["sesi_id"]) for r in sumber] == [
        (fokus_1, sesi_1),
        (fokus_1, sesi_2),
        (fokus_2, sesi_2),
    ]


def test_provenance_fokus_harus_berasal_dari_putaran_dan_siswa_yang_sama(db):
    with database.buka(db) as kon:
        siswa_1 = database.tambah_siswa(kon, "Satu")
        siswa_2 = database.tambah_siswa(kon, "Dua")
        putaran_id = database.buat_putaran_fokus(kon, siswa_1, "P3")
        sesi_tanpa_putaran = database.buat_sesi(kon, siswa_1, 3, jumlah_soal=1)
        sesi_siswa_lain = database.buat_sesi(kon, siswa_2, 4, jumlah_soal=1)
        database.tautkan_sesi_putaran(kon, putaran_id, [])

        with pytest.raises(ValueError, match="siswa dan putaran"):
            database.tambah_anggota_fokus(
                kon, putaran_id, "deret", "K", "m-1", [sesi_tanpa_putaran]
            )
        with pytest.raises(ValueError, match="siswa dan putaran"):
            database.tambah_anggota_fokus(
                kon, putaran_id, "deret", "K", "m-1", [sesi_siswa_lain]
            )


def test_konfirmasi_snapshot_mereproduksi_outcome_lama_setelah_koreksi(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        jawaban_id = _isi_dan_selesaikan(kon, sesi_id, butir)

        konfirmasi_1 = database.konfirmasi_hasil(
            kon,
            sesi_id,
            guru="guru",
            cek_pemahaman={butir["sesi_soal_id"]: "ragu"},
        )
        snapshot_lama = kon.execute(
            """SELECT nomor, template_id, jawaban, benar, kode_final,
                      malrule_id, dilewati, level_efektif, cek_pemahaman
               FROM snapshot_outcome WHERE konfirmasi_id = ?""",
            (konfirmasi_1,),
        ).fetchone()

        database.simpan_diagnosis(
            kon,
            jawaban_id,
            benar=True,
            kode_usulan="K",
            kode_final=None,
            malrule_id=None,
            alasan="dikoreksi guru",
            manual=True,
        )
        snapshot_setelah_koreksi = kon.execute(
            """SELECT nomor, template_id, jawaban, benar, kode_final,
                      malrule_id, dilewati, level_efektif, cek_pemahaman
               FROM snapshot_outcome WHERE konfirmasi_id = ?""",
            (konfirmasi_1,),
        ).fetchone()

    assert dict(snapshot_lama) == dict(snapshot_setelah_koreksi)
    assert snapshot_lama["kode_final"] == "K"
    assert snapshot_lama["malrule_id"] == "m-1"
    assert snapshot_lama["level_efektif"] == "P3"
    assert snapshot_lama["cek_pemahaman"] == "ragu"


def test_koreksi_diagnosis_menginvalidasi_cache_dan_nomor_konfirmasi_monoton(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        jawaban_id = _isi_dan_selesaikan(kon, sesi_id, butir)
        pertama = database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        cache_sebelum = kon.execute(
            "SELECT dikonfirmasi_guru, fingerprint_konfirmasi FROM sesi WHERE id = ?",
            (sesi_id,),
        ).fetchone()

        database.simpan_diagnosis(
            kon, jawaban_id, True, "K", None, None, "hasil koreksi", True
        )
        cache_sesudah = kon.execute(
            "SELECT dikonfirmasi_guru, fingerprint_konfirmasi FROM sesi WHERE id = ?",
            (sesi_id,),
        ).fetchone()
        invalidasi = kon.execute(
            """SELECT jenis, konfirmasi_id FROM kejadian_belajar
               WHERE sesi_id = ? AND jenis = 'konfirmasi_dibatalkan'""",
            (sesi_id,),
        ).fetchall()

        kedua = database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        urutan = kon.execute(
            """SELECT id, nomor_urut FROM konfirmasi_hasil
               WHERE sesi_id = ? ORDER BY nomor_urut""",
            (sesi_id,),
        ).fetchall()

    assert cache_sebelum["dikonfirmasi_guru"] is not None
    assert cache_sebelum["fingerprint_konfirmasi"]
    assert dict(cache_sesudah) == {
        "dikonfirmasi_guru": None,
        "fingerprint_konfirmasi": None,
    }
    assert len(invalidasi) == 1
    assert invalidasi[0]["konfirmasi_id"] == pertama
    assert [(r["id"], r["nomor_urut"]) for r in urutan] == [
        (pertama, 1),
        (kedua, 2),
    ]


def test_koreksi_jawaban_juga_menginvalidasi_konfirmasi(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        _isi_dan_selesaikan(kon, sesi_id, butir)
        konfirmasi_id = database.konfirmasi_hasil(kon, sesi_id, guru="guru")

        database.simpan_jawaban(
            kon, butir["sesi_soal_id"], jawaban="jawaban diperbaiki"
        )
        sesi = kon.execute(
            "SELECT dikonfirmasi_guru, fingerprint_konfirmasi FROM sesi WHERE id = ?",
            (sesi_id,),
        ).fetchone()
        invalidasi = kon.execute(
            """SELECT konfirmasi_id FROM kejadian_belajar
               WHERE sesi_id = ? AND jenis = 'konfirmasi_dibatalkan'""",
            (sesi_id,),
        ).fetchall()

    assert dict(sesi) == {
        "dikonfirmasi_guru": None,
        "fingerprint_konfirmasi": None,
    }
    assert [r["konfirmasi_id"] for r in invalidasi] == [konfirmasi_id]


def test_hanya_hasil_selesai_lengkap_dan_eksplisit_yang_bisa_dikonfirmasi(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        jawaban_id = database.simpan_jawaban(
            kon, butir["sesi_soal_id"], jawaban="0"
        )
        database.simpan_diagnosis(kon, jawaban_id, False, "K", "K", "m-1")

        # kode_final dan direview bukan bukti, dan sesi belum selesai.
        kon.execute(
            "UPDATE sesi SET direview = datetime('now') WHERE id = ?", (sesi_id,)
        )
        with pytest.raises(ValueError, match="belum selesai"):
            database.konfirmasi_hasil(kon, sesi_id, guru="guru")

        database.tandai_selesai(kon, sesi_id)
        kon.execute("DELETE FROM diagnosis WHERE jawaban_id = ?", (jawaban_id,))
        with pytest.raises(ValueError, match="outcome belum lengkap"):
            database.konfirmasi_hasil(kon, sesi_id, guru="guru")

        konfirmasi_id = database.konfirmasi_hasil(
            kon,
            sesi_id,
            guru="guru",
            dilewati={butir["sesi_soal_id"]},
        )
        snapshot = kon.execute(
            "SELECT dilewati, kode_final FROM snapshot_outcome WHERE konfirmasi_id = ?",
            (konfirmasi_id,),
        ).fetchone()

    assert snapshot["dilewati"] == 1
    assert snapshot["kode_final"] is None


@pytest.mark.parametrize(
    ("benar", "kode_final", "malrule_id"),
    [
        (False, None, None),
        (True, "K", None),
        (True, None, "m-1"),
    ],
)
def test_konfirmasi_menolak_outcome_non_dilewati_yang_kontradiktif(
    db, benar, kode_final, malrule_id
):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        jawaban_id = database.simpan_jawaban(
            kon, butir["sesi_soal_id"], jawaban="0"
        )
        database.simpan_diagnosis(
            kon,
            jawaban_id,
            benar=benar,
            kode_usulan="K",
            kode_final=kode_final,
            malrule_id=malrule_id,
        )
        database.tandai_selesai(kon, sesi_id)

        with pytest.raises(ValueError, match="outcome belum lengkap"):
            database.konfirmasi_hasil(kon, sesi_id, guru="guru")

        assert kon.execute("SELECT COUNT(*) FROM konfirmasi_hasil").fetchone()[0] == 0


@pytest.mark.parametrize("kode_final", ["N", "T"])
def test_konfirmasi_dan_snapshot_raw_sql_menerima_n_t_sebagai_salah_berkode(
    db, kode_final
):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        _isi_dan_selesaikan(
            kon, sesi_id, butir, kode=kode_final, malrule_id=None
        )
        if kode_final == 'T':
            jid = database.isi_sesi(kon, sesi_id)[0]['jawaban_id']
            database.simpan_diagnosis(kon, jid, False, None, 'T', manual=True, alasan='Guru memastikan kebutuhan pengenalan')
        konfirmasi_service = database.konfirmasi_hasil(
            kon, sesi_id, guru="guru"
        )
        snapshot_service = kon.execute(
            """SELECT benar, kode_final FROM snapshot_outcome
               WHERE konfirmasi_id = ?""",
            (konfirmasi_service,),
        ).fetchone()

        sesi_raw = database.buat_sesi(
            kon,
            kon.execute("SELECT siswa_id FROM sesi WHERE id = ?", (sesi_id,)).fetchone()[0],
            seed=17,
            jumlah_soal=1,
        )
        butir_raw = database.isi_sesi(kon, sesi_raw)[0]
        konfirmasi_id = kon.execute(
            """INSERT INTO konfirmasi_hasil
                   (sesi_id, nomor_urut, guru, fingerprint)
               VALUES (?, 1, 'guru', ?)""",
            (sesi_raw, kode_final),
        ).lastrowid
        kon.execute(
            """INSERT INTO snapshot_outcome
                   (konfirmasi_id, sesi_soal_id, nomor, template_id, jawaban,
                    benar, kode_final, dilewati, level_efektif)
               VALUES (?, ?, 1, ?, '', 0, ?, 0, 'P3')""",
            (
                konfirmasi_id,
                butir_raw["sesi_soal_id"],
                butir_raw["template_id"],
                kode_final,
            ),
        )

    assert dict(snapshot_service) == {"benar": 0, "kode_final": kode_final}
    assert konfirmasi_id is not None


def test_snapshot_raw_sql_menolak_outcome_kontradiktif(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        konfirmasi_id = kon.execute(
            """INSERT INTO konfirmasi_hasil
                   (sesi_id, nomor_urut, guru, fingerprint)
               VALUES (?, 1, 'guru', 'raw')""",
            (sesi_id,),
        ).lastrowid
        sql = """INSERT INTO snapshot_outcome
                    (konfirmasi_id, sesi_soal_id, nomor, template_id, jawaban,
                     benar, kode_final, malrule_id, dilewati, level_efektif)
                 VALUES (?, ?, ?, ?, '', ?, ?, ?, 0, 'P3')"""
        kasus = [
            (1, 0, None, None),
            (2, 1, "K", None),
            (3, 1, None, "m-1"),
        ]
        for nomor, benar, kode_final, malrule_id in kasus:
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute(
                    sql,
                    (
                        konfirmasi_id,
                        butir["sesi_soal_id"] + nomor,
                        nomor,
                        butir["template_id"],
                        benar,
                        kode_final,
                        malrule_id,
                    ),
                )


def test_konfirmasi_identik_aktif_idempoten_tanpa_bukti_duplikat(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        _isi_dan_selesaikan(kon, sesi_id, butir)

        pertama = database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        kedua = database.konfirmasi_hasil(kon, sesi_id, guru="guru-lain")
        jumlah = {
            "konfirmasi": kon.execute(
                "SELECT COUNT(*) FROM konfirmasi_hasil WHERE sesi_id = ?", (sesi_id,)
            ).fetchone()[0],
            "snapshot": kon.execute(
                """SELECT COUNT(*) FROM snapshot_outcome so
                   JOIN konfirmasi_hasil kh ON kh.id = so.konfirmasi_id
                   WHERE kh.sesi_id = ?""",
                (sesi_id,),
            ).fetchone()[0],
            "event": kon.execute(
                """SELECT COUNT(*) FROM kejadian_belajar
                   WHERE sesi_id = ? AND jenis = 'hasil_dikonfirmasi'""",
                (sesi_id,),
            ).fetchone()[0],
        }

    assert kedua == pertama
    assert jumlah == {"konfirmasi": 1, "snapshot": 1, "event": 1}


def test_invalidasi_memilih_konfirmasi_aktif_terbaru_dan_urutan_tetap_monoton(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        jawaban_id = _isi_dan_selesaikan(kon, sesi_id, butir)
        pertama = database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        fingerprint = kon.execute(
            "SELECT fingerprint_konfirmasi FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()[0]
        terbaru = kon.execute(
            """INSERT INTO konfirmasi_hasil
                   (sesi_id, nomor_urut, guru, fingerprint)
               VALUES (?, 2, 'guru', ?)""",
            (sesi_id, fingerprint),
        ).lastrowid

        database.simpan_diagnosis(
            kon, jawaban_id, True, "K", None, None, "hasil koreksi", True
        )
        invalidasi = kon.execute(
            """SELECT konfirmasi_id FROM kejadian_belajar
               WHERE sesi_id = ? AND jenis = 'konfirmasi_dibatalkan'
               ORDER BY id DESC LIMIT 1""",
            (sesi_id,),
        ).fetchone()[0]
        ketiga = database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        nomor_ketiga = kon.execute(
            "SELECT nomor_urut FROM konfirmasi_hasil WHERE id = ?", (ketiga,)
        ).fetchone()[0]

    assert terbaru != pertama
    assert invalidasi == terbaru
    assert nomor_ketiga == 3


def test_sesi_dibatalkan_tidak_bisa_dikonfirmasi_dan_snapshot_lama_bertahan(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="evaluasi")
        _isi_dan_selesaikan(kon, sesi_id, butir)
        konfirmasi_id = database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        database.batalkan_sesi(kon, sesi_id, alasan="lembar rusak")

        with pytest.raises(ValueError, match="dibatalkan"):
            database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        jumlah_snapshot = kon.execute(
            "SELECT COUNT(*) FROM snapshot_outcome WHERE konfirmasi_id = ?",
            (konfirmasi_id,),
        ).fetchone()[0]
        batal = kon.execute(
            "SELECT dibatalkan FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()[0]

    assert batal is not None
    assert jumlah_snapshot == 1


def test_sesi_berbukti_tidak_bisa_hard_delete_tapi_sesi_biasa_tetap_bisa(db):
    with database.buka(db) as kon:
        siswa_id, sesi_bukti, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        _isi_dan_selesaikan(kon, sesi_bukti, butir)
        database.konfirmasi_hasil(kon, sesi_bukti, guru="guru")

        with pytest.raises(sqlite3.IntegrityError):
            database.hapus_sesi(kon, sesi_bukti)
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("DELETE FROM sesi WHERE id = ?", (sesi_bukti,))
        assert kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE id = ?", (sesi_bukti,)
        ).fetchone()[0] == 1

        sesi_biasa = database.buat_sesi(kon, siswa_id, 99, jumlah_soal=1)
        assert database.hapus_sesi(kon, sesi_biasa) is True


def test_data_membedakan_bukti_level_aktif_dan_kondisi_yang_harus_ditolak_reducer(db):
    with database.buka(db) as kon:
        siswa_id, sesi_id, butir = _sesi_satu_butir(
            kon, nama="Naik", level="P3", tujuan="pemetaan"
        )
        _isi_dan_selesaikan(kon, sesi_id, butir)
        konfirmasi_id = database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        database.ganti_level(kon, siswa_id, "P4")

        data = kon.execute(
            """SELECT s.level AS level_sesi, w.tingkat AS level_aktif,
                      s.selesai, s.dikonfirmasi_guru, s.dibatalkan,
                      COUNT(so.id) AS jumlah_snapshot
               FROM sesi s
               JOIN siswa w ON w.id = s.siswa_id
               LEFT JOIN konfirmasi_hasil kh ON kh.sesi_id = s.id
               LEFT JOIN snapshot_outcome so ON so.konfirmasi_id = kh.id
               WHERE s.id = ? GROUP BY s.id""",
            (sesi_id,),
        ).fetchone()
        perubahan = kon.execute(
            """SELECT jenis, data FROM kejadian_belajar
               WHERE siswa_id = ? AND jenis = 'diganti_level'""",
            (siswa_id,),
        ).fetchone()
        snapshot_level = kon.execute(
            "SELECT level_efektif FROM snapshot_outcome WHERE konfirmasi_id = ?",
            (konfirmasi_id,),
        ).fetchone()[0]

    assert data["level_sesi"] == snapshot_level == "P3"
    assert data["level_aktif"] == "P4"
    assert data["selesai"] is not None
    assert data["dikonfirmasi_guru"] is not None
    assert data["dibatalkan"] is None
    assert data["jumlah_snapshot"] == 1
    assert perubahan["jenis"] == "diganti_level"
    assert '"level_lama": "P3"' in perubahan["data"]
    assert '"level_baru": "P4"' in perubahan["data"]


def test_kejadian_diganti_level_dapat_merujuk_putaran_lama(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Putaran lama", tingkat="P3")
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")

        database.ganti_level(kon, siswa_id, "P4")
        kejadian = kon.execute(
            """SELECT putaran_id, jenis FROM kejadian_belajar
               WHERE siswa_id = ? AND jenis = 'diganti_level'""",
            (siswa_id,),
        ).fetchone()

    assert kejadian["putaran_id"] == putaran_id
    assert kejadian["jenis"] == "diganti_level"


def test_tabel_bukti_append_only(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_satu_butir(kon, tujuan="pemetaan")
        _isi_dan_selesaikan(kon, sesi_id, butir)
        konfirmasi_id = database.konfirmasi_hasil(kon, sesi_id, guru="guru")

        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            kon.execute(
                "UPDATE konfirmasi_hasil SET nomor_urut = 9 WHERE id = ?",
                (konfirmasi_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            kon.execute(
                "DELETE FROM snapshot_outcome WHERE konfirmasi_id = ?",
                (konfirmasi_id,),
            )


# ── Fase 1: reducer murni ──────────────────────────────────────────────


def _outcome(template, kode=None, malrule=None, benar=False, paham=None):
    return OutcomeSiklus(template, benar, kode, malrule, False, paham)


_WAKTU_OTOMATIS = object()


def _sesi_domain(
    identitas,
    tanggal,
    *,
    tujuan="pemetaan",
    level="P3",
    putaran=1,
    selesai=_WAKTU_OTOMATIS,
    dikonfirmasi=_WAKTU_OTOMATIS,
    direview=None,
    batal=None,
    outcomes=(),
    bagian=None,
    target_fokus=None,
    occurrence=None,
    konfirmasi_id=None,
):
    if selesai is _WAKTU_OTOMATIS:
        selesai = f"{tanggal} 09:00:00"
    if dikonfirmasi is _WAKTU_OTOMATIS:
        dikonfirmasi = f"{tanggal} 10:00:00"
    if target_fokus is None and tujuan in {
        "latihan_terbimbing",
        "penguatan",
        "evaluasi",
        "checkpoint",
    }:
        target_fokus = (("deret", "K", "m"),)
    if target_fokus is None:
        target_fokus = ()
    if occurrence is None and tujuan == "checkpoint":
        occurrence = 1
    assert selesai is None or isinstance(selesai, str)
    assert dikonfirmasi is None or isinstance(dikonfirmasi, str)
    sesi = SesiSiklus(
        identitas,
        1,
        level,
        tujuan,
        date.fromisoformat(tanggal),
        dibuat=f"{tanggal} 08:00:00",
        selesai=selesai,
        direview=direview,
        dikonfirmasi=dikonfirmasi,
        putaran_id=putaran,
        bagian_checkpoint=bagian,
        dibatalkan=batal,
        outcomes=tuple(outcomes),
        target_fokus=tuple(target_fokus),
        occurrence=occurrence,
        konfirmasi_id=konfirmasi_id,
        selesai_pada=(
            date.fromisoformat(selesai[:10]) if selesai is not None else None
        ),
        dikonfirmasi_pada=(
            date.fromisoformat(dikonfirmasi[:10])
            if dikonfirmasi is not None
            else None
        ),
    )
    return sesi


def _event(
    identitas,
    jenis,
    tanggal,
    *,
    putaran=1,
    sesi=None,
    konfirmasi_id=None,
    **data,
):
    return KejadianSiklus(
        identitas,
        jenis,
        date.fromisoformat(tanggal),
        putaran,
        sesi,
        konfirmasi_id,
        data=tuple(sorted(data.items())),
    )


def _bukti(*sesi, level="P3", putaran=None, kejadian=(), pendekatan=()):
    if putaran is None:
        putaran = (PutaranSiklus(1, 1, level, date(2026, 9, 1)),)
    return BuktiSiklus(1, level, tuple(sesi), tuple(putaran), tuple(kejadian), tuple(pendekatan))


def test_sesi_selesai_yang_sudah_direview_tetap_menunggu_konfirmasi():
    sesi = _sesi_domain(
        1, "2026-09-01", selesai="2026-09-01 09:00:00", direview="sudah dilihat", dikonfirmasi=None
    )

    rencana = rencana_berikutnya(_bukti(sesi), 1, date(2026, 9, 2))

    assert rencana.tindakan == "konfirmasi_hasil"
    assert rencana.sesi_id == 1


def test_sesi_pemblokir_memilih_yang_belum_selesai_paling_tua():
    baru = _sesi_domain(2, "2026-09-02", selesai=None, dikonfirmasi=None)
    lama = _sesi_domain(1, "2026-09-01", selesai=None, dikonfirmasi=None)

    rencana = rencana_berikutnya(_bukti(baru, lama), 1, date(2026, 9, 3))

    assert rencana.tindakan == "lanjutkan_sesi"
    assert rencana.sesi_id == 1


def test_sesi_manual_stale_dibatalkan_dan_beda_level_tidak_memblokir():
    manual = _sesi_domain(1, "2026-09-01", tujuan="bebas", putaran=None, selesai=None)
    stale = _sesi_domain(2, "2026-09-01", putaran=99, selesai=None)
    beda_level = _sesi_domain(3, "2026-09-01", level="P4", selesai=None)
    batal = _sesi_domain(4, "2026-09-01", selesai=None, batal="batal")

    rencana = rencana_berikutnya(
        _bukti(manual, stale, beda_level, batal), 1, date(2026, 9, 2)
    )

    assert rencana.tindakan == "pemetaan"


def test_pemetaan_harus_tiga_tanggal_berbeda_dan_level_aktif():
    sesi = (
        _sesi_domain(1, "2026-09-01"),
        _sesi_domain(2, "2026-09-01"),
        _sesi_domain(3, "2026-09-02"),
        _sesi_domain(4, "2026-09-03", level="P4"),
    )

    rencana = rencana_berikutnya(_bukti(*sesi), 1, date(2026, 9, 2))

    assert rencana.tindakan == "tunggu_pemetaan"
    assert rencana.tersedia_pada == date(2026, 9, 3)


def test_kunci_k_sama_baru_menjadi_fokus_setelah_dua_sesi():
    satu = _sesi_domain(1, "2026-09-01", outcomes=(_outcome("deret", "K", "m1"),))
    rencana_satu = rencana_berikutnya(_bukti(satu), 1, date(2026, 9, 2))
    dua = _sesi_domain(2, "2026-09-02", outcomes=(_outcome("deret", "K", "m1"),))
    tiga = _sesi_domain(3, "2026-09-03")

    rencana_dua_tanggal = rencana_berikutnya(
        _bukti(satu, dua), 1, date(2026, 9, 3)
    )
    rencana_dua = rencana_berikutnya(_bukti(satu, dua, tiga), 1, date(2026, 9, 4))

    assert rencana_satu.tindakan in {"tunggu_pemetaan", "pemetaan"}
    assert rencana_satu.putaran is None or not rencana_satu.putaran.fokus
    assert rencana_dua_tanggal.tindakan == "pemetaan"
    assert rencana_dua.putaran.fokus[0].kunci == ("deret", "K", "m1")


def test_satu_k_dan_satu_h_tidak_digabung_menjadi_fokus():
    sesi = (
        _sesi_domain(1, "2026-09-01", outcomes=(_outcome("deret", "K", "m1"),)),
        _sesi_domain(2, "2026-09-02", outcomes=(_outcome("deret", "H", "m1"),)),
        _sesi_domain(3, "2026-09-03"),
    )

    rencana = rencana_berikutnya(_bukti(*sesi), 1, date(2026, 9, 4))

    assert rencana.tindakan == "probe_diagnostik"
    assert not rencana.putaran.fokus


def test_ranking_fokus_maksimal_dua_mendahulukan_jumlah_lalu_k_dan_terbaru():
    sesi = (
        _sesi_domain(1, "2026-09-01", outcomes=(
            _outcome("a", "H"), _outcome("b", "K", "b")
        )),
        _sesi_domain(2, "2026-09-02", outcomes=(
            _outcome("a", "H"), _outcome("b", "K", "b"), _outcome("c", "K", "c")
        )),
        _sesi_domain(3, "2026-09-03", outcomes=(
            _outcome("a", "H"), _outcome("c", "K", "c")
        )),
    )

    fokus = rencana_berikutnya(_bukti(*sesi), 1, date(2026, 9, 4)).putaran.fokus

    assert [f.kunci for f in fokus] == [("a", "H", None), ("c", "K", "c")]


def test_anchor_maksimal_lima_k_ke_h_lalu_terbaru_dan_sisanya_dibawa():
    outcomes = tuple(_outcome(f"k{i}", "K", f"m{i}") for i in range(4)) + tuple(
        _outcome(f"h{i}", "H") for i in range(4)
    )
    sesi = _sesi_domain(1, "2026-09-01", outcomes=outcomes)

    rencana = rencana_berikutnya(_bukti(sesi), 1, date(2026, 9, 2))

    assert rencana.tindakan == "pemetaan"
    assert len(rencana.kandidat) == 5
    assert [k[1] for k in rencana.kandidat] == ["K", "K", "K", "K", "H"]


def test_kandidat_baru_di_pemetaan_ketiga_memicu_probe_lanjutan():
    sesi = (
        _sesi_domain(1, "2026-09-01"),
        _sesi_domain(2, "2026-09-02"),
        _sesi_domain(3, "2026-09-03", outcomes=(_outcome("baru", "K", "m"),)),
    )

    rencana = rencana_berikutnya(_bukti(*sesi), 1, date(2026, 9, 4))

    assert rencana.tindakan == "probe_diagnostik"
    assert rencana.kandidat == (("baru", "K", "m"),)


@pytest.mark.parametrize("kode", list("BKHENT"))
def test_setiap_kode_memiliki_tindakan_berbeda(kode):
    semua = {k: intervensi_untuk(k).tindakan for k in "BKHENT"}

    assert len(set(semua.values())) == 6
    assert intervensi_untuk(kode).kode == kode


def test_n_ragu_menjadi_kandidat_k_derived_tanpa_mengubah_outcome_historis():
    n1 = _outcome("rasio", "N", None, paham="ragu")
    n2 = _outcome("rasio", "N", None, paham="menghafal")
    sesi = (
        _sesi_domain(1, "2026-09-01", outcomes=(n1,)),
        _sesi_domain(2, "2026-09-02", outcomes=(n2,)),
        _sesi_domain(3, "2026-09-03"),
    )

    fokus = rencana_berikutnya(_bukti(*sesi), 1, date(2026, 9, 4)).putaran.fokus

    assert fokus[0].kunci == ("rasio", "K", None)
    assert n1.kode_final == n2.kode_final == "N"


def test_penguat_dan_latihan_terbimbing_tidak_menambah_bukti_kelemahan():
    pemetaan = _sesi_domain(1, "2026-09-01", outcomes=(_outcome("deret", "K", "m"),))
    terbimbing = _sesi_domain(
        2, "2026-09-02", tujuan="latihan_terbimbing", outcomes=(_outcome("deret", "K", "m"),)
    )
    penguatan = _sesi_domain(
        3, "2026-09-03", tujuan="penguatan", outcomes=(_outcome("deret", "K", "m"),)
    )

    rencana = rencana_berikutnya(_bukti(pemetaan, terbimbing, penguatan), 1, date(2026, 9, 4))

    assert rencana.putaran is None or not rencana.putaran.fokus


def test_sesi_bebas_hanya_masuk_pemetaan_dengan_opt_in_event():
    bebas = _sesi_domain(
        1,
        "2026-09-01",
        tujuan="bebas",
        putaran=None,
        konfirmasi_id=11,
        outcomes=(_outcome("deret", "K", "m"),),
    )
    pemetaan = _sesi_domain(2, "2026-09-02", outcomes=(_outcome("deret", "K", "m"),))
    ketiga = _sesi_domain(3, "2026-09-03")
    tanpa = rencana_berikutnya(_bukti(bebas, pemetaan, ketiga), 1, date(2026, 9, 4))
    opt_in = _event(
        1,
        "sertakan_pemetaan",
        "2026-09-01",
        putaran=None,
        sesi=1,
        konfirmasi_id=11,
    )

    dengan = rencana_berikutnya(
        _bukti(bebas, pemetaan, ketiga, kejadian=(opt_in,)), 1, date(2026, 9, 4)
    )

    assert tanpa.putaran is None or not tanpa.putaran.fokus
    assert dengan.putaran.fokus[0].kunci == ("deret", "K", "m")


def _fokus_deret():
    return ("deret", "K", "m")


def _putaran_fokus_deret():
    return (PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (_fokus_deret(),)),)


def test_penguatan_terkonfirmasi_memulai_jeda_evaluasi_tiga_hari():
    penguatan = _sesi_domain(
        1,
        "2026-09-05",
        tujuan="penguatan",
        target_fokus=(_fokus_deret(),),
        outcomes=(_outcome("deret", benar=True),),
    )
    terbimbing = _sesi_domain(
        2,
        "2026-09-04",
        tujuan="latihan_terbimbing",
        target_fokus=(_fokus_deret(),),
        outcomes=(_outcome("deret", benar=True),),
    )
    events = (
        _event(1, "intervensi_selesai", "2026-09-03", fokus=_fokus_deret(), pendekatan_id="visual-1"),
    )

    sebelum = rencana_berikutnya(
        _bukti(terbimbing, penguatan, putaran=_putaran_fokus_deret(), kejadian=events),
        1,
        date(2026, 9, 7),
    )
    jatuh_tempo = rencana_berikutnya(
        _bukti(terbimbing, penguatan, putaran=_putaran_fokus_deret(), kejadian=events),
        1,
        date(2026, 9, 8),
    )

    assert sebelum.tindakan == "tunggu_evaluasi"
    assert sebelum.tersedia_pada == date(2026, 9, 8)
    assert jatuh_tempo.tindakan == "evaluasi"
    assert jatuh_tempo.jumlah_probe_minimum == 4


def test_penguatan_belum_dikonfirmasi_tidak_memulai_jeda():
    penguatan = _sesi_domain(
        1, "2026-09-05", tujuan="penguatan", dikonfirmasi=None,
        outcomes=(_outcome("deret", benar=True),)
    )

    rencana = rencana_berikutnya(
        _bukti(penguatan, putaran=_putaran_fokus_deret()), 1, date(2026, 9, 20)
    )

    assert rencana.tindakan == "konfirmasi_hasil"


def _evaluasi(identitas, tanggal, benar, *, paham="bisa_menjelaskan", kode=None):
    outcomes = tuple(
        _outcome("deret", kode if i == 0 else None, "m" if kode and i == 0 else None,
                 benar=benar if not kode or i else True, paham=paham)
        for i in range(4)
    )
    return _sesi_domain(
        identitas,
        tanggal,
        tujuan="evaluasi",
        target_fokus=(_fokus_deret(),),
        outcomes=outcomes,
    )


def test_evaluasi_lulus_dengan_75_persen_nol_k_dan_bisa_menjelaskan():
    evaluasi = _sesi_domain(
        1,
        "2026-09-08",
        tujuan="evaluasi",
        target_fokus=(_fokus_deret(),),
        outcomes=(
            _outcome("deret", benar=True, paham="bisa_menjelaskan"),
            _outcome("deret", benar=True, paham="bisa_menjelaskan"),
            _outcome("deret", benar=True, paham="bisa_menjelaskan"),
            _outcome("deret", "H", benar=False, paham="bisa_menjelaskan"),
        ),
    )

    rencana = rencana_berikutnya(
        _bukti(evaluasi, putaran=_putaran_fokus_deret()), 1, date(2026, 9, 9)
    )

    assert rencana.putaran.fokus[0].status == "mulai_membaik"
    assert rencana.tindakan == "tunggu_checkpoint"
    assert rencana.tersedia_pada == date(2026, 10, 6)


@pytest.mark.parametrize("paham", ["ragu", "menghafal"])
def test_evaluasi_benar_tetapi_pemahaman_gagal_tidak_lulus(paham):
    evaluasi = _evaluasi(1, "2026-09-08", True, paham=paham)
    pendekatan = ((_fokus_deret(), ("visual-1", "visual-2")),)
    events = (
        _event(1, "intervensi_selesai", "2026-09-03", fokus=_fokus_deret(), pendekatan_id="visual-1"),
    )

    rencana = rencana_berikutnya(
        _bukti(
            evaluasi,
            putaran=_putaran_fokus_deret(),
            kejadian=events,
            pendekatan=pendekatan,
        ),
        1,
        date(2026, 9, 9),
    )

    assert rencana.tindakan == "intervensi"
    assert rencana.putaran.fokus[0].status == "perlu_diperkuat"
    assert rencana.putaran.fokus[0].pendekatan_berikutnya == "visual-2"


def test_evaluasi_gagal_pertama_tanpa_alternatif_langsung_eskalasi():
    evaluasi = _evaluasi(1, "2026-09-08", False)
    events = (
        _event(1, "intervensi_selesai", "2026-09-03", fokus=_fokus_deret(), pendekatan_id="satu-satunya"),
    )

    rencana = rencana_berikutnya(
        _bukti(evaluasi, putaran=_putaran_fokus_deret(), kejadian=events),
        1,
        date(2026, 9, 9),
    )

    assert rencana.tindakan == "eskalasi"


def test_evaluasi_gagal_kedua_berturut_turut_memicu_eskalasi():
    sesi = (_evaluasi(1, "2026-09-08", False), _evaluasi(2, "2026-09-15", False))
    pendekatan = ((_fokus_deret(), ("visual-1", "visual-2", "visual-3")),)

    rencana = rencana_berikutnya(
        _bukti(*sesi, putaran=_putaran_fokus_deret(), pendekatan=pendekatan),
        1,
        date(2026, 9, 16),
    )

    assert rencana.tindakan == "eskalasi"


def test_checkpoint_jatuh_tempo_28_hari_per_fokus_dan_membawa_minimum_probe():
    evaluasi = _evaluasi(1, "2026-09-08", True)

    rencana = rencana_berikutnya(
        _bukti(evaluasi, putaran=_putaran_fokus_deret()), 1, date(2026, 10, 6)
    )

    assert rencana.tindakan == "checkpoint"
    assert rencana.bagian_checkpoint == 1
    assert rencana.jumlah_probe_minimum == 3


def test_checkpoint_belum_mengubah_status_sebelum_dua_bagian_terkonfirmasi():
    evaluasi = _evaluasi(1, "2026-09-08", True)
    bagian_1 = _sesi_domain(
     2,
     "2026-10-06",
     tujuan="checkpoint",
     bagian=1,
     occurrence=1,
     target_fokus=(_fokus_deret(),),
     outcomes=tuple(
         _outcome("deret", benar=True, paham="bisa_menjelaskan")
         for _ in range(3)
     ),
 )

    rencana = rencana_berikutnya(
        _bukti(evaluasi, bagian_1, putaran=_putaran_fokus_deret()),
        1,
        date(2026, 10, 6),
    )

    assert rencana.tindakan == "checkpoint"
    assert rencana.bagian_checkpoint == 2
    assert rencana.putaran.fokus[0].status == "mulai_membaik"


def test_checkpoint_sukses_menjadi_bertahan_dan_berulang_28_hari():
    evaluasi = _evaluasi(1, "2026-09-08", True)
    checkpoint = tuple(
        _sesi_domain(
            i + 2, f"2026-10-{6 + i:02d}", tujuan="checkpoint", bagian=i + 1,
            outcomes=tuple(_outcome("deret", benar=True, paham="bisa_menjelaskan") for _ in range(2)),
        )
        for i in range(2)
    )

    sebelum = rencana_berikutnya(
        _bukti(evaluasi, *checkpoint, putaran=_putaran_fokus_deret()),
        1,
        date(2026, 11, 3),
    )
    ulang = rencana_berikutnya(
        _bukti(evaluasi, *checkpoint, putaran=_putaran_fokus_deret()),
        1,
        date(2026, 11, 4),
    )

    assert sebelum.putaran.fokus[0].status == "bertahan"
    assert sebelum.tindakan == "tunggu_checkpoint"
    assert ulang.tindakan == "checkpoint"


def test_k_baru_pada_fokus_bertahan_membuka_putaran_baru_tanpa_menghapus_histori():
    evaluasi = _evaluasi(1, "2026-09-08", True)
    checkpoint = tuple(
        _sesi_domain(
            i + 2, "2026-10-06", tujuan="checkpoint", bagian=i + 1,
            outcomes=tuple(_outcome("deret", benar=True, paham="bisa_menjelaskan") for _ in range(2)),
        )
        for i in range(2)
    )
    kambuh = _sesi_domain(
        4, "2026-10-10", tujuan="pemetaan", outcomes=(_outcome("deret", "K", "m"),)
    )

    rencana = rencana_berikutnya(
        _bukti(evaluasi, *checkpoint, kambuh, putaran=_putaran_fokus_deret()),
        1,
        date(2026, 10, 11),
    )

    assert rencana.tindakan == "putaran_baru"
    assert rencana.putaran.id is None
    assert rencana.putaran.fokus[0].kunci == _fokus_deret()


def test_pengenalan_t_diikuti_probe_sampai_hasil_terkonfirmasi():
    sesi = (
        _sesi_domain(1, "2026-09-01", outcomes=(_outcome("pecahan", "T"),)),
        _sesi_domain(2, "2026-09-02"),
        _sesi_domain(3, "2026-09-03"),
    )
    selesai = _event(
        1,
        "pengenalan_selesai",
        "2026-09-03",
        fokus=("pecahan", "T", None),
    )

    rencana = rencana_berikutnya(
        _bukti(*sesi, kejadian=(selesai,)), 1, date(2026, 9, 4)
    )

    assert rencana.tindakan == "probe_setelah_pengenalan"
    assert rencana.kandidat == (("pecahan", "T", None),)


def test_pemetaan_didahulukan_dari_probe_setelah_pengenalan():
    pemetaan_t = _sesi_domain(1, "2026-09-01", outcomes=(_outcome("pecahan", "T"),))
    selesai = _event(
        1,
        "pengenalan_selesai",
        "2026-09-01",
        fokus=("pecahan", "T", None),
    )

    rencana = rencana_berikutnya(
        _bukti(pemetaan_t, kejadian=(selesai,)), 1, date(2026, 9, 2)
    )

    assert rencana.tindakan == "pemetaan"


def test_t_tanpa_pengenalan_merekomendasikan_pengenalan_bukan_maintenance():
    sesi = (
        _sesi_domain(1, "2026-09-01"),
        _sesi_domain(2, "2026-09-02"),
        _sesi_domain(3, "2026-09-03", outcomes=(_outcome("pecahan", "T"),)),
    )

    rencana = rencana_berikutnya(_bukti(*sesi), 1, date(2026, 9, 4))

    assert rencana.tindakan == "pengenalan"
    assert rencana.kandidat == (("pecahan", "T", None),)


def test_override_sebelum_intervensi_mengganti_fokus():
    lama = _fokus_deret()
    baru = ("uang", "H", None)
    override = _event(1, "fokus_diubah", "2026-09-02", fokus=(baru,))

    rencana = rencana_berikutnya(
        _bukti(putaran=_putaran_fokus_deret(), kejadian=(override,)),
        1,
        date(2026, 9, 3),
    )

    assert rencana.putaran.fokus[0].kunci == baru
    assert rencana.putaran.fokus[0].kunci != lama


def test_override_terlambat_mengikuti_putaran_baru_dan_sesi_lama_nonblocking():
    lama = PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (_fokus_deret(),))
    baru = PutaranSiklus(2, 1, "P3", date(2026, 9, 5), (("uang", "H", None),))
    sesi_lama = _sesi_domain(1, "2026-09-03", putaran=1, selesai=None, dikonfirmasi=None)
    events = (
        _event(1, "intervensi_selesai", "2026-09-02", putaran=1, fokus=_fokus_deret(), pendekatan_id="v1"),
        _event(2, "override_ditutup", "2026-09-05", putaran=1),
    )

    rencana = rencana_berikutnya(
        _bukti(sesi_lama, putaran=(lama, baru), kejadian=events), 1, date(2026, 9, 6)
    )

    assert rencana.sesi_id is None
    assert rencana.putaran.id == 2
    assert rencana.putaran.fokus[0].kunci == ("uang", "H", None)


def test_intervensi_selesai_dilanjutkan_latihan_terbimbing_lalu_penguatan():
    selesai = _event(
        1, "intervensi_selesai", "2026-09-02", fokus=_fokus_deret(), pendekatan_id="v1"
    )
    tanpa_latihan = rencana_berikutnya(
        _bukti(putaran=_putaran_fokus_deret(), kejadian=(selesai,)),
        1,
        date(2026, 9, 3),
    )
    terbimbing = _sesi_domain(
        1, "2026-09-03", tujuan="latihan_terbimbing", outcomes=(_outcome("deret", benar=True),)
    )

    sesudah_latihan = rencana_berikutnya(
        _bukti(terbimbing, putaran=_putaran_fokus_deret(), kejadian=(selesai,)),
        1,
        date(2026, 9, 4),
    )

    assert tanpa_latihan.tindakan == "latihan_terbimbing"
    assert sesudah_latihan.tindakan == "penguatan"


def test_dua_sesi_gagal_baru_setelah_bertahan_membuka_putaran_baru():
    evaluasi = _evaluasi(1, "2026-09-08", True)
    checkpoint = tuple(
        _sesi_domain(
            i + 2,
            "2026-10-06",
            tujuan="checkpoint",
            bagian=i + 1,
            outcomes=tuple(
                _outcome("deret", benar=True, paham="bisa_menjelaskan") for _ in range(2)
            ),
        )
        for i in range(2)
    )
    gagal_1 = _sesi_domain(
        4,
        "2026-10-10",
        target_fokus=(_fokus_deret(),),
        outcomes=(_outcome("deret", "H", benar=False),),
    )
    gagal_2 = _sesi_domain(
        5,
        "2026-10-11",
        target_fokus=(_fokus_deret(),),
        outcomes=(_outcome("deret", "H", benar=False),),
    )

    rencana = rencana_berikutnya(
        _bukti(
            evaluasi,
            *checkpoint,
            gagal_1,
            gagal_2,
            putaran=_putaran_fokus_deret(),
        ),
        1,
        date(2026, 10, 12),
    )

    assert rencana.tindakan == "putaran_baru"


def test_loader_database_menghasilkan_input_immutable_dari_snapshot_aktif(db):
    with database.buka(db) as kon:
        siswa_id, sesi_id, butir = _sesi_satu_butir(
            kon, nama="Loader", level="P3", tujuan="pemetaan"
        )
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        database.tautkan_sesi_putaran(kon, putaran_id, [sesi_id])
        _isi_dan_selesaikan(kon, sesi_id, butir)
        database.konfirmasi_hasil(kon, sesi_id, guru="guru")

        bukti = database.muat_bukti_siklus(kon, siswa_id)

    assert isinstance(bukti, BuktiSiklus)
    assert bukti.putaran[0].id == putaran_id
    assert bukti.sesi[0].outcomes[0].kode_final == "K"
    with pytest.raises(Exception):
        bukti.sesi[0].tujuan = "bebas"


# ── Regresi review Fase 1 ───────────────────────────────────────────────


def _target(*kunci):
    return tuple(kunci)


def _putaran_dua_fokus():
    return (
        PutaranSiklus(
            1,
            1,
            "P3",
            date(2026, 9, 1),
            ((_fokus_deret()), ("deret", "K", "malrule-b")),
        ),
    )


def test_evaluasi_memisahkan_dua_malrule_pada_template_yang_sama():
    fokus_a = _fokus_deret()
    fokus_b = ("deret", "K", "malrule-b")
    evaluasi_a = _sesi_domain(
        10,
        "2026-09-08",
        tujuan="evaluasi",
        target_fokus=_target(fokus_a),
        outcomes=tuple(
            _outcome("deret", benar=True, paham="bisa_menjelaskan") for _ in range(4)
        ),
    )

    rencana = rencana_berikutnya(
        _bukti(evaluasi_a, putaran=_putaran_dua_fokus()), 1, date(2026, 9, 9)
    )

    status = {item.kunci: item.status for item in rencana.putaran.fokus}
    assert status[fokus_a] == "mulai_membaik"
    assert status[fokus_b] == "perlu_dipelajari"


def test_progres_intervensi_dan_latihan_dihitung_per_fokus():
    fokus_a = _fokus_deret()
    fokus_b = ("deret", "K", "malrule-b")
    intervensi_a = _event(
        1,
        "intervensi_selesai",
        "2026-09-02",
        fokus=fokus_a,
        pendekatan_id="visual-a",
    )
    terbimbing_a = _sesi_domain(
        2,
        "2026-09-03",
        tujuan="latihan_terbimbing",
        target_fokus=_target(fokus_a),
        outcomes=(_outcome("deret", benar=True),),
    )

    rencana = rencana_berikutnya(
        _bukti(
            terbimbing_a,
            putaran=_putaran_dua_fokus(),
            kejadian=(intervensi_a,),
        ),
        1,
        date(2026, 9, 4),
    )

    assert rencana.tindakan == "intervensi"
    assert rencana.kandidat == (fokus_b,)


def test_checkpoint_tidak_memasangkan_bagian_lintas_occurrence():
    fokus = _fokus_deret()
    evaluasi = _evaluasi(1, "2026-09-08", True)
    bagian_lama = _sesi_domain(
        2,
        "2026-10-06",
        tujuan="checkpoint",
        bagian=1,
        occurrence=1,
        target_fokus=_target(fokus),
        outcomes=tuple(
            _outcome("deret", benar=True, paham="bisa_menjelaskan") for _ in range(2)
        ),
    )
    bagian_baru = _sesi_domain(
        3,
        "2026-11-03",
        tujuan="checkpoint",
        bagian=2,
        occurrence=2,
        target_fokus=_target(fokus),
        outcomes=tuple(
            _outcome("deret", benar=True, paham="bisa_menjelaskan") for _ in range(2)
        ),
    )

    rencana = rencana_berikutnya(
        _bukti(evaluasi, bagian_lama, bagian_baru, putaran=_putaran_fokus_deret()),
        1,
        date(2026, 11, 4),
    )

    assert rencana.putaran.fokus[0].status == "mulai_membaik"
    assert rencana.tindakan == "checkpoint"
    assert rencana.bagian_checkpoint == 1


def test_intervensi_fokus_lain_mengalahkan_tunggu_checkpoint():
    fokus_a = _fokus_deret()
    fokus_b = ("deret", "K", "malrule-b")
    evaluasi_a = _sesi_domain(
        1,
        "2026-09-08",
        tujuan="evaluasi",
        target_fokus=_target(fokus_a),
        outcomes=tuple(
            _outcome("deret", benar=True, paham="bisa_menjelaskan") for _ in range(4)
        ),
    )

    rencana = rencana_berikutnya(
        _bukti(evaluasi_a, putaran=_putaran_dua_fokus()), 1, date(2026, 9, 9)
    )

    assert rencana.tindakan == "intervensi"
    assert rencana.kandidat == (fokus_b,)


def test_pengenalan_t_stale_tidak_menghapus_antrean_dan_probe_harus_eksplisit():
    materi = ("pecahan", "T", None)
    sesi_t = (
        _sesi_domain(1, "2026-09-01", outcomes=(_outcome("pecahan", "T"),)),
        _sesi_domain(2, "2026-09-02"),
        _sesi_domain(3, "2026-09-03"),
    )
    stale = _event(
        1,
        "pengenalan_selesai",
        "2026-08-31",
        putaran=99,
        fokus=materi,
    )
    outcome_asal = _sesi_domain(
        4,
        "2026-09-04",
        tujuan="pemetaan",
        outcomes=(_outcome("pecahan", benar=True),),
    )

    rencana = rencana_berikutnya(
        _bukti(*sesi_t, outcome_asal, kejadian=(stale,)), 1, date(2026, 9, 5)
    )

    assert rencana.tindakan == "pengenalan"
    assert rencana.kandidat == (materi,)


def test_opt_in_sesi_bebas_harus_merujuk_konfirmasi_aktif():
    bebas = _sesi_domain(
        1,
        "2026-09-01",
        tujuan="bebas",
        putaran=None,
        konfirmasi_id=22,
        outcomes=(_outcome("deret", "K", "m"),),
    )
    pemetaan = _sesi_domain(2, "2026-09-02", outcomes=(_outcome("deret", "K", "m"),))
    ketiga = _sesi_domain(3, "2026-09-03")
    opt_in_lama = KejadianSiklus(
        1,
        "sertakan_pemetaan",
        date(2026, 9, 1),
        None,
        1,
        21,
    )

    rencana = rencana_berikutnya(
        _bukti(bebas, pemetaan, ketiga, kejadian=(opt_in_lama,)),
        1,
        date(2026, 9, 4),
    )

    assert not rencana.putaran.fokus


def test_tanggal_sesi_bebas_opt_in_ikut_menyelesaikan_tiga_tanggal_pemetaan():
    bebas = _sesi_domain(
        1, "2026-09-01", tujuan="bebas", putaran=None, konfirmasi_id=11
    )
    pemetaan_2 = _sesi_domain(2, "2026-09-02")
    pemetaan_3 = _sesi_domain(3, "2026-09-03")
    opt_in = KejadianSiklus(
        1, "sertakan_pemetaan", date(2026, 9, 1), None, 1, 11
    )

    rencana = rencana_berikutnya(
        _bukti(bebas, pemetaan_2, pemetaan_3, kejadian=(opt_in,)),
        1,
        date(2026, 9, 4),
    )

    assert rencana.tindakan == "mixed_maintenance"
    assert rencana.putaran.tanggal_pemetaan == (
        date(2026, 9, 1),
        date(2026, 9, 2),
        date(2026, 9, 3),
    )


def test_jeda_evaluasi_mulai_dari_waktu_terakhir_selesai_dan_dikonfirmasi():
    fokus = _fokus_deret()
    penguatan = _sesi_domain(
        1,
        "2026-09-01",
        tujuan="penguatan",
        selesai="2026-09-05 23:55:00",
        dikonfirmasi="2026-09-06 00:05:00",
        target_fokus=_target(fokus),
        outcomes=(_outcome("deret", benar=True),),
    )
    terbimbing = _sesi_domain(
        2,
        "2026-09-04",
        tujuan="latihan_terbimbing",
        target_fokus=_target(fokus),
        outcomes=(_outcome("deret", benar=True),),
    )
    selesai = _event(
        1,
        "intervensi_selesai",
        "2026-09-02",
        fokus=fokus,
        pendekatan_id="visual-1",
    )

    rencana = rencana_berikutnya(
        _bukti(terbimbing, penguatan, putaran=_putaran_fokus_deret(), kejadian=(selesai,)),
        1,
        date(2026, 9, 8),
    )

    assert rencana.tindakan == "tunggu_evaluasi"
    assert rencana.tersedia_pada == date(2026, 9, 9)


def test_loader_membaca_target_occurrence_konfirmasi_dan_waktu_domain(db):
    fokus = ("deret", "K", "m-1")
    with database.buka(db) as kon:
        siswa_id, sesi_id, butir = _sesi_satu_butir(
            kon, nama="Metadata", level="P3", tujuan="evaluasi"
        )
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        database.tautkan_sesi_putaran(kon, putaran_id, [sesi_id])
        _isi_dan_selesaikan(kon, sesi_id, butir)
        konfirmasi_id = database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        kon.execute(
            """INSERT INTO kejadian_belajar
                   (siswa_id, putaran_id, sesi_id, konfirmasi_id, jenis, data, dibuat)
               VALUES (?, ?, ?, ?, 'sesi_dibuat', ?, '2026-09-07 08:00:00')""",
            (
                siswa_id,
                putaran_id,
                sesi_id,
                konfirmasi_id,
                '{"fokus":[["deret","K","m-1"]],"occurrence":3}',
            ),
        )

        bukti = database.muat_bukti_siklus(kon, siswa_id)

    sesi = bukti.sesi[0]
    assert sesi.target_fokus == (fokus,)
    assert sesi.occurrence == 3
    assert sesi.konfirmasi_id == konfirmasi_id
    assert sesi.selesai_pada is not None
    assert sesi.dikonfirmasi_pada is not None
