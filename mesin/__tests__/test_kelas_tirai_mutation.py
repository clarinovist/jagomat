"""Mutation guard BARU tirai PIN pada tindakan /murid/paket (butir QA #4)."""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES = "test_kelas_tirai_http.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES)
MURID = "kelas_murid_http.py"
TIRAI = "tirai_aksi.py"

KASUS = (
    ("post_tanpa_gerbang_tirai", MURID, [
        ("    if _tirai_tertutup(penangan, *pembeli):  # PIN terpasang dan tirai tertutup: tanpa efek", "    if False:"),
    ], "test_pin_terpasang_basic_tidak_bisa_daftar_paket_dan_tanpa_efek or test_hapus_jadwal_dan_bukti_juga_ditahan_saat_tirai_tertutup"),
    ("hapus_dikecualikan_dari_tirai", MURID, [
        ("    if _tirai_tertutup(penangan, *pembeli):  # PIN terpasang dan tirai tertutup: tanpa efek",
         "    if _tirai_tertutup(penangan, *pembeli) and jalur != halaman.RUTE_HAPUS:  # PIN terpasang dan tirai tertutup: tanpa efek"),
    ], "test_hapus_jadwal_dan_bukti_juga_ditahan_saat_tirai_tertutup or test_hapus_tagihan_ditahan_tirai_dan_tanpa_tombol_saat_tertutup"),
    ("pin_tak_terbaca_dianggap_terbuka", TIRAI, [
        ("    except sqlite3.Error:\n        return True\n    token = penangan._ambil_token()", "    except sqlite3.Error:\n        return False\n    token = penangan._ambil_token()"),
    ], "test_pin_tidak_terbaca_gagal_tertutup"),
    ("tirai_diabaikan", TIRAI, [
        ("    return not (token is not None and tirai.terbuka(token, principal.id_akun, siswa_id))", "    return False"),
    ], "test_pin_terpasang_basic_tidak_bisa_daftar_paket_dan_tanpa_efek"),
    ("token_cookie_dipakai_untuk_principal_basic", TIRAI, [
        ('penangan._ambil_token() if principal.metode == "cookie" else None', "penangan._ambil_token()"),
    ], "test_cookie_mati_bersama_basic_tidak_mewarisi_tirai_yang_terbuka"),
    ("tirai_tidak_terikat_sesi", TIRAI, [
        ("    return not (token is not None and tirai.terbuka(token, principal.id_akun, siswa_id))", "    return False if token is not None else True"),
    ], "test_tirai_dibuka_untuk_sesi_cookie_mengizinkan_tindakan_dan_tidak_untuk_sesi_lain"),
    ("pin_diabaikan_sebagai_syarat", TIRAI, [
        ("            if not pin_store.ada_pin(kon, siswa_id):\n                return False\n", "            pass\n"),
    ], "test_tanpa_pin_tindakan_berjalan_seperti_biasa"),
    ("kabar_terkunci_tidak_muncul_dan_pilihan_tetap", MURID, [
        ("    if tertutup:\n        kabar =", "    if False:\n        kabar ="),
    ], "test_halaman_paket_memberi_kabar_terkunci_dan_menyembunyikan_pilihan_jadwal"),
)


@pytest.mark.parametrize("nama,berkas,ganti,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_tirai_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, tes):
    uji_mutasi(tmp_path, berkas, ganti, TES, tes, SALIN_TES)
