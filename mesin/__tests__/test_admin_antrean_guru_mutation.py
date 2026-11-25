"""Mutation guard BARU butir antrean "guru baru belum masuk lembaga": penanda, pengecualian, galat baca, tingkat, jalur.

Tiap kasus menonaktifkan satu guard di salinan source terisolasi; tes terkait harus MERAH karena perilaku, lalu hijau lagi.
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES = "test_admin_antrean_guru.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES)
G = "admin_antrean_guru.py"
A = "admin_antrean.py"

KASUS = (
    ("receipt_dengan_profil_ikut_terhitung", G, [
        ("and op not in profil\n", "and True\n"),
    ], "test_penanda_hanya_receipt_guru_tanpa_profil or test_guru_mandiri_nyata"),
    ("akun_anak_ikut_terhitung", G, [
        ('r.get("hasil_kode") == KODE_GURU', 'r.get("hasil_kode") is not None'),
    ], "test_penanda_hanya_receipt_guru_tanpa_profil"),
    ("terikat_lembaga_tetap_dihitung", G, [
        ('and a.get("pengguna") not in terikat', "and True"),
    ], "test_hitungan_mengecualikan_terikat_lembaga_pemilik_siswa_nonaktif_dan_peran_lain"),
    ("pemilik_siswa_tetap_dihitung", G, [
        ('and str(a.get("pengguna", "")).casefold() not in pemilik_siswa)', ")"),
    ], "test_hitungan_mengecualikan_terikat_lembaga_pemilik_siswa_nonaktif_dan_peran_lain"),
    ("nonaktif_tetap_dihitung", G, [
        ('and not a.get("dinonaktifkan")', ""),
    ], "test_hitungan_mengecualikan_terikat_lembaga_pemilik_siswa_nonaktif_dan_peran_lain"),
    ("peran_lain_tetap_dihitung", G, [
        ('a.get("peran", "guru") == "guru" and', "True and"),
    ], "test_hitungan_mengecualikan_terikat_lembaga_pemilik_siswa_nonaktif_dan_peran_lain"),
    ("galat_baca_menjatuhkan_halaman", G, [
        ("    except Exception:           # noqa: BLE001 - penanda antrean tidak boleh menjatuhkan halaman admin\n        return 0",
         "    except ZeroDivisionError:\n        return 0"),
    ], "test_galat_baca_berarti_nol"),
    ("butir_jadi_penting", A, [
        ('return (ItemAntrean("tinjau", "%d guru baru belum masuk lembaga"', 'return (ItemAntrean("penting", "%d guru baru belum masuk lembaga"'),
    ], "test_butir_antrean_tinjau_tanpa_menambah_perlu_keputusan"),
    ("butir_tidak_ikut_total", A, [
        ("+ len(belum_tempat) + len(guru_baru) + len(lain),", "+ len(belum_tempat) + len(lain),"),
    ], "test_butir_antrean_tinjau_tanpa_menambah_perlu_keputusan"),
)


@pytest.mark.parametrize("nama,berkas,ganti,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_antrean_guru_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, tes):
    uji_mutasi(tmp_path, berkas, ganti, TES, tes, SALIN_TES)
