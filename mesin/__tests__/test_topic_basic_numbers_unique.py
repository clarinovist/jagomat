"""R2: tidak ada soal kembar sebelum domain habis; RNG topik lama tetap."""
from dataclasses import replace
import random

import pytest

import database
import generator
import topics
from choice_generation import buat_lembar_pilihan

TOPIK = "bilangan-dasar"
JENIS = "tambah_dasar"


def _tanda(soal):
    return [s.tanda_tangan for s in soal]


@pytest.mark.parametrize("level", ("P1", "P2"))
@pytest.mark.parametrize("jumlah", (10, 15, 20, 25, 30))
def test_lembar_tanpa_kembar(level, jumlah):
    kembar = []
    for seed in range(200):
        lembar = generator.buat_lembar(seed, level=level, topik=TOPIK, jumlah_soal=jumlah)
        assert len(lembar.soal) == jumlah
        if len(set(_tanda(lembar.soal))) != jumlah:
            kembar.append(seed)
        assert lembar == generator.buat_lembar(seed, level=level, topik=TOPIK, jumlah_soal=jumlah)
        # Seluruh pasangan sah punya dua pengecoh: PG tidak mengganti slot.
        assert lembar == buat_lembar_pilihan(seed, level=level, topik=TOPIK, jumlah_soal=jumlah)
    assert not kembar, ("soal kembar", level, jumlah, len(kembar), kembar[:10])


@pytest.mark.parametrize("level,kapasitas", (("P1", 45), ("P2", 145)))
@pytest.mark.parametrize("tambahan", (0, 1, 5, 50))
def test_domain_habis_boleh_ulang_setelah_seluruh_domain_terpakai(level, kapasitas, tambahan):
    for seed in (0, 7, 42):
        jumlah = kapasitas + tambahan
        lembar = generator.buat_lembar(seed, level=level, topik=TOPIK, jumlah_soal=jumlah)
        assert len(lembar.soal) == jumlah
        tanda = _tanda(lembar.soal)
        assert len(set(tanda[:kapasitas])) == kapasitas
        assert set(tanda[kapasitas:]) <= set(tanda[:kapasitas])
        assert lembar == generator.buat_lembar(seed, level=level, topik=TOPIK, jumlah_soal=jumlah)


def test_retry_terbatas_tidak_mengira_domain_habis(monkeypatch):
    paket = topics.ambil(TOPIK)
    hitungan = []

    def macet(tid, rng, level):
        hitungan.append(tid)
        return {"a": 1, "b": 1}

    monkeypatch.setattr(generator, "_BATAS_UNDI_UNIK", 2)
    paket = replace(paket, parameter_untuk=macet)
    lembar = generator.buat_lembar(7, level="P1", topik=paket, jumlah_soal=50)
    assert len(set(_tanda(lembar.soal[:45]))) == 45
    assert len(lembar.soal) == 50
    # Pertama1, berikutnya44x2 lalu fallback enumerator; domain habis5x1.
    assert len(hitungan) == 1 + 44 * 2 + 5
    assert lembar == generator.buat_lembar(7, level="P1", topik=paket, jumlah_soal=50)


def test_sampler_keluar_domain_tidak_disamarkan():
    paket = replace(topics.ambil(TOPIK), parameter_untuk=lambda *a: {"a": 6, "b": 5})
    with pytest.raises(ValueError, match="sampler keluar domain"):
        generator.buat_lembar(0, level="P1", topik=paket)


def test_opt_in_memerlukan_domain_dan_tetap_menolak_soal_tanpa_malrule():
    paket = topics.ambil(TOPIK)
    with pytest.raises(ValueError, match="domain"):
        generator.buat_lembar(0, level="P1", topik=replace(paket, domain_parameter=None))
    with pytest.raises(ValueError, match="domain"):
        generator.buat_lembar(0, level="P1", topik=replace(paket, domain_parameter=lambda *a: ()))
    with pytest.raises(RuntimeError, match="malrule"):
        generator.buat_lembar(0, level="P1", topik=replace(
            paket, templates={JENIS: lambda **p: replace(paket.templates[JENIS](**p), malrule=())}))


@pytest.mark.parametrize("level", ("P1", "P2"))
def test_urutan_eksplisit_writer_dan_paket_tunggal(level):
    paket = topics.ambil(TOPIK)
    assert topics.gabungan([TOPIK, TOPIK]) is paket
    assert topics.paket_untuk_template([JENIS]) is paket
    writer = replace(paket, komposisi_writer={lv: (JENIS,) * 25 for lv in paket.komposisi})
    for seed in range(25):
        for lembar in (generator.buat_lembar(seed, urutan=(JENIS,) * 30, level=level, topik=paket),
                       generator.buat_lembar(seed, level=level, topik=writer)):
            assert len(set(_tanda(lembar.soal))) == len(lembar.soal)
        assert len(generator.buat_lembar(seed, level=level, topik=writer).soal) == 25


def test_flag_mati_mempertahankan_pemakaian_rng_lama():
    for nama in topics.daftar_topik():
        paket = topics.ambil(nama)
        assert paket.unik_per_lembar is (nama == TOPIK)
        if nama == TOPIK:
            continue
        for level in paket.komposisi:
            for seed in (0, 7, 42):
                rng = random.Random(seed)
                urutan = generator._acak_urutan(paket.komposisi_untuk(level), rng)
                lama = tuple(generator._soal_layak(paket, tid, rng, level) for tid in urutan)
                assert generator.buat_lembar(seed, level=level, topik=paket).soal == lama


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "bilangan-sintetis.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        yield kon


def _cek_bank(kon, sesi, jumlah, kapasitas):
    isi = database.isi_sesi(kon, sesi)
    ids = [b["soal_id"] for b in isi]
    assert len(ids) == jumlah
    assert len(set(ids[:min(jumlah, kapasitas)])) == min(jumlah, kapasitas)
    if jumlah > kapasitas:
        assert set(ids[kapasitas:]) <= set(ids[:kapasitas])
    return ids


@pytest.mark.parametrize("level,kapasitas", (("P1", 45), ("P2", 145)))
@pytest.mark.parametrize("jumlah", tuple(range(10, 51, 5)))
@pytest.mark.parametrize("format_jawaban", ("isian", "pilihan_ganda"))
def test_sesi_manual_dan_bank_deterministik(db, level, kapasitas, jumlah, format_jawaban):
    siswa = database.tambah_siswa(db, "Sintetis", tingkat="P3", pemilik="guru")
    kwargs = dict(topik=TOPIK, level=level, jumlah_soal=jumlah, format_jawaban=format_jawaban)
    sesi = database.buat_sesi(db, siswa, 7, **kwargs)
    ids = _cek_bank(db, sesi, jumlah, kapasitas)
    ulang = database.buat_sesi(db, siswa, 7, **kwargs)
    assert _cek_bank(db, ulang, jumlah, kapasitas) == ids
    assert db.execute("SELECT COUNT(*) FROM soal").fetchone()[0] == min(jumlah, kapasitas)


@pytest.mark.parametrize("level", ("P1", "P2"))
@pytest.mark.parametrize("format_jawaban", ("isian", "pilihan_ganda"))
def test_seed_baru_dan_gabungan_tunggal(db, monkeypatch, level, format_jawaban):
    import teacher_pages
    siswa = database.tambah_siswa(db, "Sintetis", tingkat="P3", pemilik="guru")
    monkeypatch.setattr(teacher_pages.random, "randint", lambda *a: 77)
    sesi = teacher_pages.buat_sesi_seed_baru(db, siswa, level=level, topik=TOPIK,
                                            jumlah_soal=30, format_jawaban=format_jawaban)
    ids = _cek_bank(db, sesi, 30, 45)
    gabungan = database.buat_sesi_gabungan(db, siswa, 77, [TOPIK], level=level,
                                          jumlah_soal=30, format_jawaban=format_jawaban)
    assert _cek_bank(db, gabungan, 30, 45) == ids


@pytest.mark.parametrize("level", ("P1", "P2"))
def test_sesi_urutan_remedial_dan_snapshot_terpilih(db, level):
    siswa = database.tambah_siswa(db, "Sintetis", tingkat="P3", pemilik="guru")
    sumber = database.buat_sesi_dari_urutan(db, siswa, 7, (JENIS,) * 30, topik=TOPIK, level=level)
    _cek_bank(db, sumber, 30, 45)
    item = database.isi_sesi(db, sumber)[0]
    jid = database.simpan_jawaban(db, item["sesi_soal_id"], jawaban="999")
    database.simpan_diagnosis(db, jid, benar=False, kode_usulan="K", kode_final="K", alasan="Sintetis")
    database.tandai_selesai(db, sumber)
    db.execute("UPDATE sesi SET direview = '2026-10-30 10:00:00' WHERE id = ?", (sumber,))
    remedial = database.buat_sesi_remedial(db, siswa, seed=8, level=level, jumlah_soal=30,
                                         template_ids=[JENIS], sumber_sesi_id=sumber)
    assert remedial is not None
    _cek_bank(db, remedial, 30, 45)
    # Jalur ini menyimpan soal otoritatif, bukan mengundi ulang: pastikan
    # lembar unik yang sudah dipilih tidak diganti walau seed berbeda.
    dipilih = generator.buat_lembar(42, level=level, topik=TOPIK).soal
    sesi = database.buat_sesi_dari_urutan(db, siswa, 99, (JENIS,) * 10, topik=TOPIK,
                                        level=level, soal_terpilih=dipilih)
    isi = database.isi_sesi(db, sesi)
    assert [b["teks_soal"] for b in isi] == [s.teks for s in dipilih]
    _cek_bank(db, sesi, 10, 45)
