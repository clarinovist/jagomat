"""Regresi + mutation Modul 2: penanda hitung_kertas & evaluasi pasangan diagnostik."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import diagnosis  # noqa: E402
import students  # noqa: E402
from templates import Malrule, Soal  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "modul2.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def test_hitung_kertas_menjaga_jalur_malrule_dan_ekuivalensi():
    soal = Soal(
        "pecahan_bagian_dasar",
        {"varian": "sisa_bagian", "penyebut": 8, "a": 3, "b": 0},
        "Teks",
        "5/8",
        [Malrule("pecahan_dasar.ambil_bagian_terpakai", "3/8", "K", "menulis bagian terpakai")],
    )
    malrule_dicts = [{"malrule_id": m.id, "jawaban": m.jawaban, "kode": m.kode, "alasan": m.alasan} for m in soal.malrule]
    # Tanpa kotak teks Caraku, cukup pilihan hitung_kertas -> K tetap terbaca!
    usulan = diagnosis.diagnosa(
        soal.kunci, "3/8", students.AWALAN_PILIHAN + "hitung_kertas", "", False, malrule_dicts, soal=soal
    )
    assert not usulan.benar
    assert usulan.kode == "K"
    assert usulan.malrule_id == "pecahan_dasar.ambil_bagian_terpakai"

    # Ekuivalensi pecahan sederhana diterima dengan hitung_kertas
    benar = diagnosis.diagnosa(
        soal.kunci, "10/16", students.AWALAN_PILIHAN + "hitung_kertas", "", False, malrule_dicts, soal=soal
    )
    assert benar.benar is True


def test_guard_cara_kosong_dan_tebak_tetap_n():
    mal = [{"malrule_id": "perkalian.dijumlahkan", "jawaban": "18", "kode": "K", "alasan": "dijumlahkan"}]
    soal = Soal("perkalian_dasar", {"a": 14, "b": 4, "varian": "hitung"}, "14 × 4", "56")
    kosong = diagnosis.diagnosa("56", "18", "", "", False, mal, soal=soal)
    assert kosong.kode == "N"

    tebak_benar = diagnosis.diagnosa(
        "56", "56", students.AWALAN_PILIHAN + "tebak", "", False, mal, soal=soal
    )
    assert tebak_benar.benar is False and tebak_benar.kode == "N"


def test_evaluasi_pasangan_diagnostik_membedakan_konsisten_vs_sekali_dan_triase():
    butir = [
        # Pasangan triase 1 (perkalian_dasar): 2x K -> konsisten_k + triase_macet=True
        {"template_id": "perkalian_dasar", "benar": 0, "kode_final": "K", "alasan": "menjumlahkan bilangan", "belum_pernah": 0, "dilewati": 0},
        {"template_id": "perkalian_dasar", "benar": 0, "kode_final": "K", "alasan": "menjumlahkan bilangan", "belum_pernah": 0, "dilewati": 0},
        # Pasangan pecahan: 1 benar + 1 K -> konsep_awal
        {"template_id": "pecahan_bagian_dasar", "benar": 1, "kode_final": None, "alasan": None, "belum_pernah": 0, "dilewati": 0},
        {"template_id": "pecahan_bagian_dasar", "benar": 0, "kode_final": "K", "alasan": "menjumlahkan penyebut", "belum_pernah": 0, "dilewati": 0},
        # Pasangan keliling: 1 benar + 1 H -> teliti
        {"template_id": "keliling_luas_datar", "benar": 1, "kode_final": None, "alasan": None, "belum_pernah": 0, "dilewati": 0},
        {"template_id": "keliling_luas_datar", "benar": 0, "kode_final": "H", "alasan": "kurang satu", "belum_pernah": 0, "dilewati": 0},
        # Pasangan deret: 2 benar -> kuat
        {"template_id": "deret_aritmetika", "benar": 1, "kode_final": None, "alasan": None, "belum_pernah": 0, "dilewati": 0},
        {"template_id": "deret_aritmetika", "benar": 1, "kode_final": None, "alasan": None, "belum_pernah": 0, "dilewati": 0},
    ]
    hasil = diagnosis.evaluasi_pasangan_diagnostik(butir, "P3")
    assert hasil["triase_macet"] is True
    peta = {r.template_id: r for r in hasil["ringkasan"]}
    assert peta["perkalian_dasar"].status == "konsisten_k"
    assert peta["perkalian_dasar"].pola_salah == "menjumlahkan bilangan"
    assert peta["pecahan_bagian_dasar"].status == "konsep_awal"
    assert peta["keliling_luas_datar"].status == "teliti"
    assert peta["deret_aritmetika"].status == "kuat"


def test_simpan_jawaban_pilihan_hitung_kertas_di_db(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Rafi Contoh", "P3", pemilik="guru")
        sesi_id = database.buat_sesi_diagnostik(kon, sid, seed=3, level="P3")
        isi = database.isi_sesi(kon, sesi_id)
        ssid = isi[0]["sesi_soal_id"]
        students.simpan_jawaban_murid(kon, sid, sesi_id, {
            f"jwb_{ssid}": str(int(isi[0]["kunci"]) + 1),
            f"pilih_{ssid}": "hitung_kertas",
        })
        tersimpan = database.isi_sesi(kon, sesi_id)[0]
        assert tersimpan["cara"] == students.AWALAN_PILIHAN + "hitung_kertas"


def test_mutation_tebak_atau_kosong_tidak_boleh_hilang(monkeypatch):
    # Simulasikan perilaku buruk: apabila penanda [pilihan] selalu diloloskan sebagai cara sah
    # bahkan ketika berisi tebak, jawaban kebetulan benar akan luput dari kode N.
    asli = diagnosis.diagnosa

    def rusak(kunci, jawaban, cara, *args, **kwargs):
        if cara.startswith(students.AWALAN_PILIHAN + "tebak"):
            return asli(kunci, jawaban, students.AWALAN_PILIHAN + "hitung_kertas", *args, **kwargs)
        return asli(kunci, jawaban, cara, *args, **kwargs)

    monkeypatch.setattr(diagnosis, "diagnosa", rusak)
    u = diagnosis.diagnosa("56", "56", students.AWALAN_PILIHAN + "tebak", "", False, [])
    assert u.kode != "N" and u.benar is True

