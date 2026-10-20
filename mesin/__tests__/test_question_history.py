"""Riwayat sintetis tetap memakai kunci/malrule bank, bukan versi template terbaru."""
from __future__ import annotations

from dataclasses import replace

import pytest

import database
import question_views
import teacher_print_pages
import teacher_review_service
import topic_number_theory
import topic_statistics
import worksheets
from generator import Lembar
from screen_style import GAYA_LAYAR
from templates import Malrule, Soal
from topics import ambil


# Fixture keluaran lama sintetis; tidak dibuat lewat template yang akan diubah.
LAMA_BILANGAN = Soal(
    "keterbagian", {"d": 3, "a": 24, "b": 25, "c": 10, "jawab": 0},
    "Manakah dari bilangan 24, 25, dan 10 yang habis dibagi 3?", "24",
    (
        Malrule("keterbagian.pilih_tak_habis", "25", "B", "memilih bilangan yang tidak habis dibagi 3"),
        Malrule("keterbagian.trap_divisor", "10", "K", "memilih bilangan yang hanya habis dibagi 2 — aturan pembagian 3 tidak dipakai dengan benar"),
        Malrule("keterbagian.kurang_satu", "23", "H", "menentukan bilangan yang benar, lalu menguranginya satu"),
    ),
    minta_restatement=True, bagian="A", level="P4",
    pembahasan="Langkah: bilangan habis dibagi 3 kalau memenuhi ciri pembagi 3. Yang memenuhi = 24.",
)
LAMA_MODUS = Soal(
    "median_modus", {"varian": "modus", "data": [5, 5, 3]},
    "Data: 5, 5, 3. Berapa modusnya (nilai yang paling sering muncul)?", "5",
    (
        Malrule("modus.pertama", "6", "K", "menjawab data pertama, bukan yang paling sering muncul"),
        Malrule("modus.kedua", "3", "K", "menjawab nilai yang bukan paling sering muncul"),
        Malrule("modus.kurang_satu", "4", "H", "perhitungan benar, hasilnya meleset satu"),
    ),
    bagian="B", level="P4",
    pembahasan="Langkah: Kemunculan data (5:2x, 3:1x). Modus (paling sering muncul) = 5.",
)


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "riwayat-sintetis.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        yield kon


def _simpan_sesi_lama(db, monkeypatch, topik, soal):
    siswa = database.tambah_siswa(db, "Fixture Riwayat", "P4", pemilik="guru")
    with monkeypatch.context() as patch:
        patch.setattr(database, "buat_lembar", lambda *a, **kw: Lembar(42, (soal,), "P4"))
        sesi = database.buat_sesi(db, siswa, 42, topik=topik, level="P4", tanggal="2026-10-20")
    return sesi


def _bank(db):
    return tuple(
        tuple(tuple(r) for r in db.execute(query))
        for query in ("SELECT * FROM soal ORDER BY id", "SELECT * FROM malrule ORDER BY id")
    )


def test_parameter_lama_keterbagian_identik():
    assert replace(topic_number_theory.keterbagian(**LAMA_BILANGAN.parameter), level="P4") == LAMA_BILANGAN


@pytest.mark.parametrize("topik,lama", (("teori-bilangan", LAMA_BILANGAN), ("statistika", LAMA_MODUS)))
def test_cetak_dan_diagnosis_memakai_bank_historis(db, monkeypatch, topik, lama):
    sesi = _simpan_sesi_lama(db, monkeypatch, topik, lama)
    b = database.isi_sesi(db, sesi)[0]
    awal = _bank(db)
    aturan = lama.malrule[0]
    # Simulasikan renderer versi lain, sementara bank/snapshot tetap versi lama.
    asli = question_views.REGISTRI[lama.template_id]
    monkeypatch.setitem(question_views.REGISTRI, lama.template_id, lambda **p: replace(
        asli(**p), kunci="999", malrule=(Malrule("mutasi", "998", "K", "aturan versi lain"),),
    ))
    for guru in (False, True):
        render = worksheets.lembar_penilaian if guru else worksheets.lembar_soal
        tersaji = replace(lama, penyajian=question_views.penyajian_dari_baris(b))
        args = (tersaji,), "Fixture Riwayat", "2026-10-20"
        if guru:
            args += (42,)
        expected = render(*args, gaya=GAYA_LAYAR, topik_paket=ambil(topik)).encode()
        assert teacher_print_pages.halaman_lembar(db, sesi, untuk_guru=guru) == expected
    form = {f"jwb_{b['sesi_soal_id']}": aturan.jawaban, f"cara_{b['sesi_soal_id']}": "coretan sintetis"}
    teacher_review_service.simpan_sesi(db, sesi, form)
    d = database.isi_sesi(db, sesi)[0]
    assert d["kode_usulan"] == aturan.kode and d["malrule_id"] == aturan.id
    # Diagnosis ulang sungguhan: ubah coretan, bukan jalur no-op simpan.
    form[f"cara_{b['sesi_soal_id']}"] = "coretan sintetis diperiksa ulang"
    teacher_review_service.simpan_sesi(db, sesi, form)
    ulang = database.isi_sesi(db, sesi)[0]
    assert (ulang["benar"], ulang["kode_usulan"], ulang["malrule_id"]) == (d["benar"], d["kode_usulan"], d["malrule_id"])
    assert ulang["penyajian_json"] == b["penyajian_json"]
    assert _bank(db) == awal
    # Simpan objek dengan identitas sama tidak boleh mengganti aturan bank lama.
    baru = replace(asli(**lama.parameter), level=lama.level)
    assert database.simpan_soal(db, baru) == b["soal_id"]
    assert _bank(db) == awal


def test_bank_baru_rollback_template_mempertahankan_reader_bank(db, monkeypatch):
    """Recovery yang didukung: template lama, reader bank TETAP diperbaiki.

    Bukan klaim image recovery pinned sudah memuat reader ini; pasangan image
    harus diverifikasi sebelum rilis. Revert reader ditangkap mutation terpisah.
    """
    baru = replace(topic_statistics.median_modus(**LAMA_MODUS.parameter), level="P4")
    assert "modus.pertama" not in {m.id for m in baru.malrule}
    sesi = _simpan_sesi_lama(db, monkeypatch, "statistika", baru)
    b = database.isi_sesi(db, sesi)[0]
    awal = _bank(db)
    sebelum = teacher_print_pages.halaman_lembar(db, sesi, untuk_guru=True)
    # Output template persis fixture sebelum patch; reader cetak tidak di-revert.
    monkeypatch.setitem(question_views.REGISTRI, "median_modus", lambda **p: replace(LAMA_MODUS, level="P3"))
    assert teacher_print_pages.halaman_lembar(db, sesi, untuk_guru=True) == sebelum
    form = {f"jwb_{b['sesi_soal_id']}": "6", f"cara_{b['sesi_soal_id']}": "coretan sintetis"}
    teacher_review_service.simpan_sesi(db, sesi, form)
    hasil = database.isi_sesi(db, sesi)[0]
    assert hasil["benar"] == 0
    assert hasil["kode_usulan"] is None and hasil["malrule_id"] is None
    assert _bank(db) == awal


def test_identitas_modus_lama_dipakai_ulang_tidak_menimpa_bank(db, monkeypatch):
    sesi = _simpan_sesi_lama(db, monkeypatch, "statistika", LAMA_MODUS)
    lama = database.isi_sesi(db, sesi)[0]
    awal = _bank(db)
    baru = replace(topic_statistics.median_modus(**LAMA_MODUS.parameter), level="P4")
    sesi_baru = _simpan_sesi_lama(db, monkeypatch, "statistika", baru)
    assert database.isi_sesi(db, sesi_baru)[0]["soal_id"] == lama["soal_id"]
    assert _bank(db) == awal
    assert teacher_print_pages.halaman_lembar(db, sesi, untuk_guru=True) == teacher_print_pages.halaman_lembar(db, sesi_baru, untuk_guru=True)
