"""Replay debit memakai parameter tersimpan tanpa mengubah soal atau kuncinya."""
import random
from dataclasses import asdict

import pytest

import database
import question_views
import rumus
import topics
import visual_renderer
from diagnosis import diagnosa
from generator import buat_soal
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji
from templates import REGISTRI
from topic_advanced_arithmetic import debit


@pytest.mark.parametrize("varian,kunci", [
    ("cari_debit", "12"), ("cari_volume", "60"), ("cari_waktu", "5"),
])
def test_replay_parameter_tersimpan_identik(varian, kunci):
    awal = debit(varian, 60, 5, 12)
    ulang = debit(**awal.parameter)
    assert asdict(ulang) == asdict(awal)
    assert ulang.kunci == kunci
    assert ulang.parameter == {"varian": varian, "volume": 60, "waktu": 5, "debit": 12}


@pytest.mark.parametrize("nilai", [0, -1, True, "12", 1.5])
def test_alias_debit_tidak_sah_ditolak(nilai):
    with pytest.raises(ValueError):
        debit("cari_volume", 60, 5, debit=nilai)


def test_alias_berkonflik_ditolak_dan_alias_identik_diterima():
    with pytest.raises(ValueError):
        debit("cari_volume", 60, 5, 12, debit=13)
    assert debit("cari_volume", 60, 5, 12, debit=12) == debit("cari_volume", 60, 5, 12)
    with pytest.raises(ValueError):
        debit("cari_volume", 60, 5)


@pytest.fixture
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def test_replay_debit_lewat_http_guru_dan_murid(server):
    with server.buka() as kon:
        siswa = database.tambah_siswa(kon, "feby", "P5", pemilik="guru")
        sesi = database.buat_sesi_dari_urutan(
            kon, siswa, seed=713, urutan=("debit",), topik="aritmatika-lanjut", level="P5",
        )
        baris = database.isi_sesi(kon, sesi)[0]
        tersimpan = dict(baris)
        hasil = question_views.soal_dari_baris(baris)
        assert hasil.kunci == baris["kunci"]
    kode, isi, _ = server.minta(f"/sesi/{sesi}", auth=("guru", SANDI_GURU))
    assert kode == 200 and "Debit" in isi
    kode, isi, _ = server.minta(f"/murid/kerjakan/{sesi}", auth=("feby", SANDI_MURID))
    assert kode == 200 and "jawab-" in isi
    with server.buka() as kon:
        sekarang = dict(database.isi_sesi(kon, sesi)[0])
    for nama in ("parameter", "kunci", "cerita", "soal_id"):
        assert sekarang[nama] == tersimpan[nama]


def test_debit_lintas_seed_level_diagnosis_dan_replay():
    for level in topics.ambil("aritmatika-lanjut").komposisi:
        for seed in range(25):
            soal = buat_soal("debit", seed, level=level, topik="aritmatika-lanjut")
            ulang = debit(**soal.parameter)
            assert ulang.kunci == soal.kunci
            assert ulang.teks == soal.teks
            assert ulang.malrule == soal.malrule
            assert ulang.pembahasan == soal.pembahasan
            assert buat_soal("debit", seed, level=level, topik="aritmatika-lanjut") == soal
            assert diagnosa(soal.kunci, soal.kunci, "Menghitung sendiri", "", False, []).benar
            assert any(m.kode == "K" for m in soal.malrule)
            for m in soal.malrule:
                malrule = dict(asdict(m), malrule_id=m.id)
                hasil = diagnosa(soal.kunci, m.jawaban, "Menghitung sendiri", "", False, [malrule])
                assert (hasil.kode, hasil.malrule_id) == (m.kode, m.id)


def test_topik_aritmatika_lanjut_render_lintas_seed_level():
    paket = topics.ambil("aritmatika-lanjut")
    for level, komposisi in paket.komposisi.items():
        for tid in sorted(set(komposisi)):
            for seed in range(25):
                parameter = paket.parameter_untuk(tid, random.Random(seed), level)
                soal = REGISTRI[tid](**parameter)
                assert soal == REGISTRI[tid](**parameter)
                assert soal.pembahasan and rumus.kartu_untuk(tid)
                assert visual_renderer.render_pertanyaan(
                    question_views.penyajian_dari_soal(soal), gaya="guru", namespace="uji",
                )
