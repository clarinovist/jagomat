"""Mutation guard BARU gerbang tirai PIN bersama (tirai_aksi) dan pemasangannya di langganan Harian serta pesanan Peta (butir QA 4)."""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES_UNIT = "test_tirai_aksi.py"
TES_HARIAN = "test_harian_tirai_http.py"
TES_PESANAN = "test_pesanan_murid_tirai_http.py"
KIT = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py")))
SALIN_TES = KIT + ("conftest.py", TES_UNIT, TES_HARIAN, TES_PESANAN)
TIRAI = "tirai_aksi.py"
HARIAN = "harian_langganan_murid_http.py"
PESANAN = "pesanan_murid_http.py"

KASUS = (
    ("pin_diabaikan_sebagai_syarat", TIRAI, [
        ("            if not pin_store.ada_pin(kon, siswa_id):\n                return False\n", "            pass\n"),
    ], TES_UNIT, "test_tanpa_pin_tidak_tertutup"),
    ("pin_tak_terbaca_dianggap_terbuka", TIRAI, [
        ("    except sqlite3.Error:\n        return True\n", "    except sqlite3.Error:\n        return False\n"),
    ], TES_UNIT, "test_pin_tak_terbaca_gagal_tertutup"),
    ("tirai_diabaikan", TIRAI, [
        ("    return not (token is not None and tirai.terbuka(token, principal.id_akun, siswa_id))", "    return False"),
    ], TES_UNIT, "test_pin_dan_tirai_tertutup_menolak"),
    ("token_cookie_dipakai_untuk_basic", TIRAI, [
        ('penangan._ambil_token() if principal.metode == "cookie" else None', "penangan._ambil_token()"),
    ], TES_UNIT, "test_principal_basic_tidak_memakai_token_cookie_yang_terbuka"),
    ("harian_tanpa_gerbang_tirai", HARIAN, [
        ("    if tirai_aksi.tertutup(penangan, *pembeli):", "    if False:"),
    ], TES_HARIAN, "test_pin_terpasang_basic_tidak_bisa_buat_tagihan_dan_tanpa_efek or test_unggah_bukti_juga_ditahan"),
    ("pesanan_tanpa_gerbang_tirai", PESANAN, [
        ("    if _tirai_tertutup(penangan, principal):  # PIN terpasang dan tirai tertutup: tanpa efek", "    if False:"),
    ], TES_PESANAN, "test_pin_terpasang_basic_tidak_bisa_memesan_dan_ledger_tetap_kosong or test_rute_pembayaran_lain_juga_ditahan"),
)


@pytest.mark.parametrize("nama,berkas,ganti,berkas_tes,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_tirai_bersama_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, berkas_tes, tes):
    uji_mutasi(tmp_path, berkas, ganti, berkas_tes, tes, SALIN_TES)
