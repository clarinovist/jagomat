"""Mutation guard admin jadwal Private: tiap guard dimatikan di salinan source terisolasi (harness `harian_mutasi_kit`).

Setiap kasus memastikan tes terkait HIJAU, MERAH karena perilaku setelah guard dinonaktifkan, lalu HIJAU lagi setelah
dipulihkan. Workspace asli tidak disentuh.
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES_HTTP = "test_jadwal_private_admin_http.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES_HTTP)
RUTE_HTTP = "jadwal_private_admin_http.py"
PAGES = "jadwal_private_admin_pages.py"

# (nama, berkas, [(lama, baru), ...], ekspresi -k)
KASUS = (
    ("rute_private_wajib_admin", RUTE_HTTP, [
        ("    principal = h._principal_admin(penangan)\n    if principal is None:\n        h._tidak_ada(penangan)\n"
         "        return True\n    _get(penangan, principal)",
         "    principal = h._principal_admin(penangan)\n    if False:\n        h._tidak_ada(penangan)\n"
         "        return True\n    _get(penangan, principal)"),
    ], "test_anonim_dan_guru_404_identik_untuk_semua_rute_private"),
    ("id_target_dari_form_bukan_tinjauan", RUTE_HTTP, [
        ('    pid = dsr.periksa_id(tinjauan["data"].get(KUNCI_TINJAUAN_ID), "target")\n    if data[FIELD_ID] != str(pid):',
         '    pid = dsr.periksa_id(int(data[FIELD_ID]), "target")\n    if False:'),
    ], "test_id_form_berbeda_dari_tinjauan_ditolak_tanpa_efek"),
    ("setujui_tampil_untuk_pengajuan_basi", PAGES, [
        ('    if entri.basi:\n        return ""', '    if False:\n        return ""'),
    ], "test_setujui_pengajuan_basi_ditolak_dan_tombolnya_tidak_tampil"),
)


@pytest.mark.parametrize("nama,berkas,ganti,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_jadwal_private_admin_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, tes):
    uji_mutasi(tmp_path, berkas, ganti, TES_HTTP, tes, SALIN_TES)
