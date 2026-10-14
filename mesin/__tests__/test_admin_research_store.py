"""Domain storage riset konsumen memakai data sintetis tanpa identitas anak."""
from pathlib import Path
import sqlite3

import pytest

import admin_research_service as layanan
import research_schema as schema
import research_store as store


ACTOR = "akun_" + "a" * 32


def _operasi(nilai):
    if len(nilai) == 32:
        return "op_" + nilai
    return "op_" + ("%032x" % int(nilai, 16))


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "riset.db"
    store.siapkan(path, sekarang=100)
    return path


def _buat(path, *, kode="R01", operasi="b", sekarang=100):
    return store.buat_wawancara(
        path, actor_id=ACTOR, operasi_id=_operasi(operasi),
        kode_responden=kode, sumber="internal", consent_rekaman=False,
        diwawancarai=sekarang, sekarang=sekarang,
    )


def _simpan(path, identitas, q, *, operasi, status="dijawab", jawaban="Jawaban sintetis",
            kutipan="", terpilih=False, catatan="Catatan interviewer sintetis",
            utama=None, tambahan=(), revisi_jawaban=0, sekarang=110):
    detail = store.detail_wawancara(path, identitas)
    store.simpan_jawaban(
        path, actor_id=ACTOR, operasi_id=_operasi(operasi),
        wawancara_id=identitas, pertanyaan_kode=q,
        revisi_wawancara=detail["revisi"], revisi_jawaban=revisi_jawaban,
        status_jawaban=status,
        jawaban_responden=jawaban if status == "dijawab" else "",
        kutipan_responden=kutipan if status == "dijawab" else "",
        kutipan_terpilih=terpilih if status == "dijawab" else False,
        catatan_interviewer=catatan,
        kode_utama=utama if status == "dijawab" else None,
        kode_tambahan=tambahan if status == "dijawab" else (),
        status_klarifikasi="tidak_perlu", sekarang=sekarang,
    )


def test_bootstrap_idempoten_instrumen_immutable_dan_get_tidak_membuat(tmp_path):
    path = tmp_path / "riset.db"
    store.siapkan(path, sekarang=100)
    awal = path.read_bytes()
    store.siapkan(path, sekarang=200)
    assert path.read_bytes() == awal
    with store.buka_baca(path) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM instrumen_riset").fetchone()[0] == 1
    with store._transaksi(path) as kon:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            kon.execute("UPDATE instrumen_riset SET kode_versi='rusak'")
    hilang = tmp_path / "hilang.db"
    with pytest.raises(store.StoreRisetBelumSiap):
        with store.buka_baca(hilang):
            pass
    assert not hilang.exists()


def test_schema_parsial_ditolak_tanpa_perbaikan(tmp_path):
    path = tmp_path / "parsial.db"
    with sqlite3.connect(path) as kon:
        kon.execute("CREATE TABLE studi_riset(slug TEXT)")
        kon.execute("PRAGMA user_version=1")
    sebelum = path.read_bytes()
    with pytest.raises(store.StoreRisetBelumSiap):
        with store.buka_baca(path):
            pass
    assert path.read_bytes() == sebelum


def test_jawaban_responden_catatan_dan_kode_terpisah(db):
    identitas = _buat(db)
    _simpan(
        db, identitas, "Q3", operasi="1", jawaban="Menjelaskan kepada anak",
        kutipan="Menjelaskan itu yang susah", terpilih=True,
        catatan="Responden menetapkan prioritas setelah diminta memilih satu.",
        utama="sulit_menjelaskan", tambahan=("sulit_memahami",),
    )
    detail = store.detail_wawancara(db, identitas)
    jawaban = detail["jawaban"]["Q3"]
    assert jawaban["jawaban_responden"] == "Menjelaskan kepada anak"
    assert jawaban["catatan_interviewer"].startswith("Responden menetapkan")
    assert jawaban["kode_utama"] == "sulit_menjelaskan"
    assert jawaban["kode_tambahan"] == ("sulit_memahami",)
    assert detail["revisi"] == 2


def test_status_tidak_dibahas_sah_tanpa_memaksa_narasi(db):
    identitas = _buat(db)
    _simpan(
        db, identitas, "Q1", operasi="2", status="tidak_dibahas",
        jawaban="", catatan="Tidak sempat dibahas.",
    )
    jawaban = store.detail_wawancara(db, identitas)["jawaban"]["Q1"]
    assert jawaban["status_jawaban"] == "tidak_dibahas"
    assert jawaban["jawaban_responden"] == ""
    assert jawaban["catatan_interviewer"] == "Tidak sempat dibahas."


def test_status_nonnarasi_menolak_membawa_bukti(db):
    identitas = _buat(db)
    with pytest.raises(ValueError, match="nonnarasi"):
        store.simpan_jawaban(
            db, actor_id=ACTOR, operasi_id="op_" + "a" * 32,
            wawancara_id=identitas, pertanyaan_kode="Q1",
            revisi_wawancara=1, revisi_jawaban=0, status_jawaban="tidak_dibahas",
            jawaban_responden="bocor", kutipan_responden="", kutipan_terpilih=False,
            catatan_interviewer="", kode_utama="konteks_osn", kode_tambahan=(),
            status_klarifikasi="tidak_perlu", sekarang=110,
        )
    assert store.detail_wawancara(db, identitas)["jawaban"] == {}


def test_tab_lama_ditolak_setelah_perubahan_lain(db):
    identitas = _buat(db)
    _simpan(db, identitas, "Q1", operasi="1", jawaban="Jawaban Q1")
    revisi_basi = store.detail_wawancara(db, identitas)["revisi"]
    _simpan(db, identitas, "Q2", operasi="2", jawaban="Jawaban Q2", sekarang=120)
    with pytest.raises(store.KonflikRiset, match="berubah"):
        store.simpan_jawaban(
            db, actor_id=ACTOR, operasi_id="op_" + "b" * 32,
            wawancara_id=identitas, pertanyaan_kode="Q3",
            revisi_wawancara=revisi_basi, revisi_jawaban=0, status_jawaban="dijawab",
            jawaban_responden="Tab lama", kutipan_responden="", kutipan_terpilih=False,
            catatan_interviewer="", kode_utama=None, kode_tambahan=(),
            status_klarifikasi="tidak_perlu", sekarang=130,
        )
    assert "Q3" not in store.detail_wawancara(db, identitas)["jawaban"]


def test_kode_asing_konflik_dua_tab_dan_replay_aman(db):
    identitas = _buat(db)
    detail = store.detail_wawancara(db, identitas)
    args = dict(
        path=db, actor_id=ACTOR, operasi_id="op_" + "3" * 32,
        wawancara_id=identitas, pertanyaan_kode="Q1",
        revisi_wawancara=detail["revisi"], revisi_jawaban=0,
        status_jawaban="dijawab", jawaban_responden="Sintetis",
        kutipan_responden="", kutipan_terpilih=False,
        catatan_interviewer="", kode_utama="konteks_osn",
        kode_tambahan=(), status_klarifikasi="tidak_perlu", sekarang=110,
    )
    store.simpan_jawaban(**args)
    store.simpan_jawaban(**args)  # replay operation ID + payload yang sama aman
    with pytest.raises(store.KonflikRiset):
        store.simpan_jawaban(**{**args, "jawaban_responden": "payload berbeda"})
    with pytest.raises(store.KonflikRiset):
        store.simpan_jawaban(**{**args, "operasi_id": "op_" + "4" * 32})
    detail_baru = store.detail_wawancara(db, identitas)
    with pytest.raises(ValueError, match="kode jawaban"):
        store.simpan_jawaban(**{
            **args, "operasi_id": "op_" + "5" * 32,
            "pertanyaan_kode": "Q2", "revisi_wawancara": detail_baru["revisi"],
            "kode_utama": "konteks_osn",
        })


def test_finalisasi_hanya_perlu_status_semua_topik(db):
    identitas = _buat(db)
    for i in range(1, 10):
        _simpan(
            db, identitas, "Q%d" % i, operasi="%x" % (i + 40),
            status="tidak_dibahas", jawaban="", catatan="", sekarang=110 + i,
        )
    detail = store.detail_wawancara(db, identitas)
    store.finalisasi(
        db, actor_id=ACTOR, operasi_id="op_" + "f" * 32,
        wawancara_id=identitas, revisi=detail["revisi"], sekarang=200,
    )
    akhir = store.detail_wawancara(db, identitas)
    assert akhir["status"] == "final" and akhir["difinalkan"] == 200
    assert store.ringkasan(db, sekarang=200)["final"] == 1


def test_tarik_consent_menghapus_semua_teks_tapi_audit_tanpa_payload(db):
    identitas = _buat(db)
    _simpan(
        db, identitas, "Q3", operasi="6", jawaban="teks-yang-harus-hilang",
        kutipan="kutipan-yang-harus-hilang", catatan="catatan-yang-harus-hilang",
        utama="sulit_menjelaskan",
    )
    detail = store.detail_wawancara(db, identitas)
    store.tarik_consent(
        db, actor_id=ACTOR, operasi_id="op_" + "7" * 32,
        wawancara_id=identitas, revisi=detail["revisi"], sekarang=300,
    )
    akhir = store.detail_wawancara(db, identitas)
    assert akhir["status"] == "ditarik" and akhir["jawaban"] == {}
    dump = db.read_bytes()
    for rahasia in (b"teks-yang-harus-hilang", b"kutipan-yang-harus-hilang", b"catatan-yang-harus-hilang"):
        assert rahasia not in dump
    with store.buka_baca(db) as kon:
        audit = tuple(dict(r) for r in kon.execute("SELECT * FROM audit_riset"))
    assert audit[-1]["aksi"] == "tarik_consent"
    assert set(audit[-1]) == {
        "operasi_id", "actor_id", "aksi", "target_id", "sidik_perintah", "hasil", "dibuat",
    }


def test_retensi_bounded_menghapus_teks(db):
    identitas = _buat(db)
    _simpan(db, identitas, "Q1", operasi="8", jawaban="hapus-saat-retensi")
    assert store.hapus_retensi(
        db, actor_id=ACTOR, sekarang=100 + 91 * 86400, batas=1,
        buat_operasi=lambda: "op_" + "9" * 32,
    ) == 1
    assert store.detail_wawancara(db, identitas)["status"] == "ditarik"
    assert b"hapus-saat-retensi" not in db.read_bytes()


def test_ekspor_csv_netral_formula_dan_tidak_membawa_actor(db):
    identitas = _buat(db)
    for i in range(1, 10):
        _simpan(
            db, identitas, "Q%d" % i, operasi="%x" % (i + 60),
            jawaban="=FORMULA" if i == 1 else "Jawaban %d" % i,
            kutipan="+KUTIPAN" if i == 1 else "", terpilih=i == 1,
            catatan="@CATATAN" if i == 1 else "", sekarang=120 + i,
        )
    detail = store.detail_wawancara(db, identitas)
    store.finalisasi(db, actor_id=ACTOR, operasi_id="op_" + "e" * 32,
                     wawancara_id=identitas, revisi=detail["revisi"], sekarang=200)
    csv = layanan.ekspor_csv(db).decode("utf-8-sig")
    js = layanan.ekspor_json(db).decode()
    assert "'=FORMULA" in csv
    assert "+KUTIPAN" in csv and "@CATATAN" in csv
    assert ACTOR not in csv and ACTOR not in js
    assert "bukan bukti PMF" in js
