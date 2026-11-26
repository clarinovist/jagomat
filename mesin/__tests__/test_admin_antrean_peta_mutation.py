"""Mutation guard BARU butir antrean "Peta dibayar, laporan belum terbit": sumber hitungan, tingkat, guard kosong, dan hitungan menu.

Tidak dimutasi (setara): saringan SQL "belum ada laporan terbit" dan "sudah lunas" (hanya penyaring awal; keadaan turunan `purna.keadaan`
menyaring hal yang sama). Mutan "tingkat selalu penting" tidak ada karena tingkatnya memang tetap tanpa cabang.
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES = "test_admin_antrean_peta.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES)
B = "admin_antrean_bayar.py"
A = "admin_antrean.py"

KASUS = (
    ("ditahan_dan_direfund_ikut_dihitung", B, [
        ("k.lunas and not k.direfund and not k.ditahan and k.terbit is None", "k.lunas and k.terbit is None"),
    ], "test_order_yang_direfund_tidak_dihitung"),
    ("terlambat_tidak_dihitung", B, [
        ("sum(1 for k in menanti if k.terlambat)", "0"),
    ], "test_lunas_lewat_janji_terlambat"),
    ("galat_baca_menjatuhkan_halaman", B, [
        ("    except menunggu.GALAT_BACA:\n        return 0, 0\n", "    except ZeroDivisionError:\n        return 0, 0\n"),
    ], "test_ledger_tak_terbaca_atau_purna_belum_dipasang_berarti_nol"),
    ("tingkat_selalu_tinjau", A, [
        ('ItemAntrean("penting", "%d Peta dibayar', 'ItemAntrean("tinjau", "%d Peta dibayar'),
    ], "test_antrean_peta_belum_terbit_selalu_penting_tanpa_masa_tunggu"),
    ("tingkat_ikut_janji_48_jam", A, [
        ('ItemAntrean("penting", "%d Peta dibayar', 'ItemAntrean("penting" if _terlambat else "tinjau", "%d Peta dibayar'),
    ], "test_antrean_peta_belum_terbit_selalu_penting_tanpa_masa_tunggu"),
    ("guard_kosong_dihapus", A, [
        ('    if not menanti:\n        return ()\n    return (ItemAntrean("penting"', '    return (ItemAntrean("penting"'),
    ], "test_antrean_kosong_bila_semua_terbit"),
    ("penting_tidak_masuk_perlu_keputusan", A, [
        ("for i in backup + tunggakan + belum_tempat + peta_belum + lain if", "for i in backup + tunggakan + belum_tempat + lain if"),
    ], "test_antrean_peta_belum_terbit_selalu_penting_tanpa_masa_tunggu"),
    ("butir_tidak_ikut_total", A, [
        ("len(belum_tempat) + len(peta_belum) + len(guru_baru) + len(privat) + len(lain),", "len(belum_tempat) + len(guru_baru) + len(privat) + len(lain),"),
    ], "test_antrean_peta_belum_terbit_selalu_penting_tanpa_masa_tunggu"),
)


@pytest.mark.parametrize("nama,berkas,ganti,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_antrean_peta_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, tes):
    uji_mutasi(tmp_path, berkas, ganti, TES, tes, SALIN_TES)
