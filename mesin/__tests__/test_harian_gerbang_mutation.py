"""Mutation guard gerbang sakelar langganan Latihan Harian: admin selalu terbuka, murid mati = 404 rute tak dikenal.

Tiap kasus memasang ulang/menghapus satu gerbang di salinan source terisolasi dan memastikan tes terkait MERAH karena
perilaku, lalu hijau setelah dipulihkan (harness bersama: `harian_mutasi_kit`).
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES_ADMIN = "test_harian_langganan_admin.py"
TES_MURID = "test_harian_langganan_murid_http.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + (
    "conftest.py", TES_ADMIN, TES_MURID)

_IMPOR = "import akses_harian\nimport bukti_berkas\n"
_GET_ADMIN = "    if jalur not in RUTE_GET:\n        return False\n"
_POST_ADMIN = "    if jalur not in _AKSI_POST:\n        return False\n"
_ADMIN_TERBUKA = "test_sakelar_mati_antrean_detail_dan_pratinjau_admin_tetap_terbuka"
_ADMIN_PUTUSAN = "test_sakelar_mati_admin_tetap_bisa_setujui_bukti_yang_sudah_masuk or test_sakelar_mati_admin_tetap_bisa_tolak_bukti_yang_sudah_masuk"
_GERBANG_MURID = "test_sakelar_mati_semua_rute_sama_dengan_jalur_murid_tak_dikenal"

# (nama, berkas, [(lama, baru), ...], berkas tes, ekspresi -k)
KASUS = (
    ("admin_get_kembali_dibatasi_sakelar", "harian_langganan_admin_http.py", [
        ("import bukti_berkas\n", _IMPOR),
        (_GET_ADMIN, "    if jalur not in RUTE_GET or not akses_harian.aktif():\n        return False\n"),
    ], TES_ADMIN, _ADMIN_TERBUKA),
    ("admin_post_kembali_dibatasi_sakelar", "harian_langganan_admin_http.py", [
        ("import bukti_berkas\n", _IMPOR),
        (_POST_ADMIN, "    if jalur not in _AKSI_POST or not akses_harian.aktif():\n        return False\n"),
    ], TES_ADMIN, _ADMIN_PUTUSAN),
    ("murid_get_tanpa_gerbang_sakelar", "harian_langganan_murid_http.py", [
        ("    if jalur not in _GET or not akses_harian.aktif():", "    if jalur not in _GET:"),
    ], TES_MURID, _GERBANG_MURID),
    ("murid_post_tanpa_gerbang_sakelar", "harian_langganan_murid_http.py", [
        ("    if jalur not in _POST or not akses_harian.aktif():", "    if jalur not in _POST:"),
    ], TES_MURID, _GERBANG_MURID),
)


@pytest.mark.parametrize("nama,berkas,ganti,berkas_tes,tes", KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_gerbang_sakelar_langganan_merah_lalu_pulih(tmp_path, nama, berkas, ganti, berkas_tes, tes):
    uji_mutasi(tmp_path, berkas, ganti, berkas_tes, tes, SALIN_TES)
