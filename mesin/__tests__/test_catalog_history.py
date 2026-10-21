"""Versi katalog memisahkan writer baru dari reader bank dan snapshot lama."""
from dataclasses import replace
import random

import pytest

import database
from generator import buat_soal
from question_views import soal_dari_baris
from templates import REGISTRI
import teacher_print_pages


PARAMETER_UMUR = {"a": 44, "b": 8, "k": 5, "n": 1, "tanya": "kali_umur"}


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "katalog-sintetis.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        yield kon


def test_identitas_baru_tidak_meminjam_kunci_bank_lama(db, monkeypatch):
    lama = replace(REGISTRI["soal_umur"](**PARAMETER_UMUR), level="P6")
    assert lama.kunci == "40"  # Fixture cacat historis: sengaja tidak dikoreksi.
    lama_id = database.simpan_soal(db, lama)
    bank_lama = tuple(tuple(r) for r in db.execute("SELECT * FROM soal ORDER BY id"))
    aturan_lama = tuple(tuple(r) for r in db.execute("SELECT * FROM malrule ORDER BY id"))
    monkeypatch.setenv("OSN_KATALOG_VERSI", "2")
    baru = buat_soal("soal_umur", 0, "P6", "logika")
    assert baru.tanda_tangan != lama.tanda_tangan, "identitas konten baru bertabrakan dengan histori"
    baru_id = database.simpan_soal(db, baru)
    assert baru_id != lama_id
    assert database.simpan_soal(db, baru) == baru_id
    assert tuple(tuple(r) for r in db.execute("SELECT * FROM soal WHERE id = ?", (lama_id,))) == bank_lama
    assert tuple(tuple(r) for r in db.execute("SELECT * FROM malrule WHERE soal_id = ? ORDER BY id", (lama_id,))) == aturan_lama
    assert db.execute("SELECT kunci FROM soal WHERE id = ?", (baru_id,)).fetchone()[0] == "5"


@pytest.mark.parametrize("flag", ("1", "tidak-valid"))
def test_reader_histori_tidak_mengikuti_flag_writer(db, monkeypatch, flag):
    monkeypatch.setenv("OSN_KATALOG_VERSI", "2")
    baru = buat_soal("soal_umur", 0, "P6", "logika")
    assert baru.kunci == "5"
    lama = replace(REGISTRI["soal_umur"](**PARAMETER_UMUR), level="P6")
    siswa = database.tambah_siswa(db, "Fixture Katalog", "P6", pemilik="guru")
    sesi = database.buat_sesi_dari_urutan(db, siswa, seed=0,
        urutan=("soal_umur", "soal_umur"), topik="logika", level="P6", soal_terpilih=(lama, baru))
    sebelum = tuple(dict(b) for b in database.isi_sesi(db, sesi))
    cetak = teacher_print_pages.halaman_lembar(db, sesi, untuk_guru=True)
    monkeypatch.setenv("OSN_KATALOG_VERSI", flag)
    pulih = tuple(soal_dari_baris(b) for b in database.isi_sesi(db, sesi))
    assert tuple(s.kunci for s in pulih) == ("40", "5")
    assert tuple(s.pembahasan for s in pulih) == (lama.pembahasan, baru.pembahasan)
    assert teacher_print_pages.halaman_lembar(db, sesi, untuk_guru=True) == cetak
    assert tuple(dict(b) for b in database.isi_sesi(db, sesi)) == sebelum


def test_rule_umur_mengikuti_prosedur_bukan_nudge(monkeypatch):
    monkeypatch.setenv("OSN_KATALOG_VERSI", "2")
    for level in ("P3", "P6"):
        for seed in range(600):
            s = buat_soal("soal_umur", seed, level, "logika")
            p = s.parameter
            fakta = {
                "umur.umur_anak_kali_umur": p["b"] + p["n"],
                "umur.umur_ayah_kali_umur": p["a"] + p["n"],
                "umur.lupa_penyebut_n_tahun": p["a"] - p["k"] * p["b"],
                "umur.selisih_umur_n_tahun": p["a"] - p["b"],
            }
            for m in s.malrule:
                if m.kode == "H":
                    assert abs(int(m.jawaban) - int(s.kunci)) == 1
                else:
                    # ID warisan juga dipahami oracle agar regresi/mutation
                    # gagal pada nilai, bukan sekadar pergantian nama rule.
                    alias = {
                        "umur.salah_rumus_n_tahun": "umur.lupa_penyebut_n_tahun",
                        "umur.kelipatan_lain_n_tahun": "umur.selisih_umur_n_tahun",
                        "umur.salah_rumus_kali_umur": "umur.umur_anak_kali_umur",
                        "umur.kelipatan_lain_kali_umur": "umur.umur_ayah_kali_umur",
                    }
                    ident = alias.get(m.id, m.id)
                    assert ident in fakta, "rule harus punya oracle prosedur"
                    assert int(m.jawaban) == fakta[ident], (seed, p, m)


def test_writer_lama_tetap_konsumsi_rng_yang_sama(monkeypatch):
    import topic_logic
    monkeypatch.setenv("OSN_KATALOG_VERSI", "1")
    for seed in range(50):
        a, b = random.Random(seed), random.Random(seed)
        aktual = topic_logic._parameter("soal_umur", a, "P6")
        # Jalur warisan dipertahankan oleh decorator, bukan salinan expected rumus.
        lama = topic_logic._parameter.__wrapped__("soal_umur", b, "P6")
        assert aktual == lama
        assert a.getstate() == b.getstate()


@pytest.mark.parametrize("flag", ("0", "3", "salah", "", " "))
def test_flag_asing_menolak_writer_tidak_mematikan_reader(monkeypatch, flag):
    monkeypatch.setenv("OSN_KATALOG_VERSI", flag)
    with pytest.raises(ValueError, match="OSN_KATALOG_VERSI"):
        buat_soal("soal_umur", 0, "P6", "logika")
    assert REGISTRI["soal_umur"](**PARAMETER_UMUR).kunci == "40"
    assert REGISTRI["soal_umur"](**PARAMETER_UMUR, versi_katalog=2).kunci == "5"


@pytest.mark.parametrize("versi", (0, 3, "2", True, None))
def test_versi_konten_asing_gagal_tertutup(versi):
    with pytest.raises(ValueError, match="versi katalog"):
        REGISTRI["soal_umur"](**PARAMETER_UMUR, versi_katalog=versi)


@pytest.mark.parametrize("ganti", ({"a": 45}, {"b": 0}, {"k": 1}, {"n": True}, {"tanya": "lain"}))
def test_fakta_umur_tidak_konsisten_ditolak(ganti):
    with pytest.raises(ValueError):
        REGISTRI["soal_umur"](**dict(PARAMETER_UMUR, **ganti), versi_katalog=2)


def test_bawaan_recovery_tetap_writer1(monkeypatch):
    monkeypatch.delenv("OSN_KATALOG_VERSI", raising=False)
    soal = buat_soal("soal_umur", 0, "P6", "logika")
    assert "versi_katalog" not in soal.parameter
    assert soal.kunci == "40"


def test_bukti_terkonfirmasi_lama_tetap_utuh(db, monkeypatch):
    lama = replace(REGISTRI["soal_umur"](**PARAMETER_UMUR), level="P6")
    siswa = database.tambah_siswa(db, "Fixture Bukti Katalog", "P6", pemilik="guru")
    sesi = database.buat_sesi_dari_urutan(db, siswa, seed=0, urutan=("soal_umur",),
                                        topik="logika", level="P6", soal_terpilih=(lama,))
    butir = database.isi_sesi(db, sesi)[0]
    jawaban = database.simpan_jawaban(db, butir["sesi_soal_id"], "40")
    database.simpan_diagnosis(db, jawaban, True, None, None, None, "fixture lama")
    database.tandai_selesai(db, sesi)
    database.konfirmasi_hasil(db, sesi, "guru")
    tabel = ("jawaban", "diagnosis", "konfirmasi_hasil", "snapshot_outcome",
             "penyajian_outcome", "kejadian_belajar", "konteks_butir", "konteks_konfirmasi")
    def rekaman():
        return tuple(tuple(tuple(r) for r in db.execute("SELECT * FROM " + t + " ORDER BY 1")) for t in tabel)
    awal = rekaman()
    bukti = database.muat_bukti_siklus(db, siswa)
    monkeypatch.setenv("OSN_KATALOG_VERSI", "2")
    database.simpan_soal(db, buat_soal("soal_umur", 0, "P6", "logika"))
    assert rekaman() == awal
    assert database.muat_bukti_siklus(db, siswa) == bukti
    monkeypatch.setenv("OSN_KATALOG_VERSI", "1")
    assert database.muat_bukti_siklus(db, siswa) == bukti
    assert rekaman() == awal


@pytest.mark.parametrize("level", ("P3", "P6"))
def test_pg_dan_bank_variasi_memakai_writer_baru(db, monkeypatch, level):
    from choice_store import daftar_pilihan
    from similar_practice import _pilih_soal_baru
    monkeypatch.setenv("OSN_KATALOG_VERSI", "2")
    siswa = database.tambah_siswa(db, "Fixture PG Katalog", level, pemilik="guru")
    for seed in range(25):
        sesi = database.buat_sesi(db, siswa, seed, topik="logika", level=level,
                                 format_jawaban="pilihan_ganda")
        pilihan = daftar_pilihan(db, sesi)
        for b in database.isi_sesi(db, sesi):
            soal = soal_dari_baris(b)
            if soal.template_id == "soal_umur":
                assert soal.parameter["versi_katalog"] == 2
                assert soal.kunci == b["kunci"]
                assert sum(o.nilai == soal.kunci for o in pilihan[b["sesi_soal_id"]].opsi) == 1
        assert teacher_print_pages.halaman_lembar(db, sesi, untuk_guru=True)
        assert teacher_print_pages.halaman_lembar(db, sesi, untuk_guru=False)
    variasi, topik = _pilih_soal_baru("soal_umur", level, 1, set())
    assert topik == "logika"
    assert len({s.tanda_tangan for s in variasi}) == 5
    assert all(s.parameter["versi_katalog"] == 2 for s in variasi)


@pytest.mark.parametrize("versi", ("1", "2"))
def test_sweep_registry_logika_render_deterministik(monkeypatch, versi):
    from topics import ambil
    from render import _badan_soal
    monkeypatch.setenv("OSN_KATALOG_VERSI", versi)
    paket = ambil("logika")
    for level, komposisi in paket.komposisi.items():
        for tid in set(komposisi):
            for seed in range(25):
                p = paket.parameter_untuk(tid, random.Random(seed), level)
                soal = replace(paket.templates[tid](**p), level=level)
                assert soal == replace(REGISTRI[tid](**p), level=level)
                assert soal == buat_soal(tid, seed, level, "logika")
                assert _badan_soal(soal, paket)
                assert soal.pembahasan


@pytest.mark.parametrize("level", ("P3", "P6"))
def test_variasi_dan_jalur_k_umur_tidak_dipalsukan(monkeypatch, level):
    monkeypatch.setenv("OSN_KATALOG_VERSI", "2")
    soal = [buat_soal("soal_umur", seed, level, "logika") for seed in range(1, 501)]
    # Batas existing, tanpa menambah field acak atau melebarkan rentang.
    assert len({s.tanda_tangan for s in soal}) >= 200
    assert sum(not any(m.kode == "K" for m in s.malrule) for s in soal) <= 10


def test_kartu_umur_mengajarkan_rasio_pada_waktu_yang_sama():
    from rumus import kartu_untuk
    kartu = kartu_untuk("soal_umur")
    assert "umur" in kartu.inti.lower()
    assert "rasio" in kartu.inti.lower()
    assert "45 : 9 = 5" in kartu.contoh
