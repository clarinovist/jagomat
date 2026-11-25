"""Mutation guard BARU jatah pendaftaran guru: batas per IP, batas global, jendela, plafon memori."""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES = "test_jatah_pendaftaran.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES)
J = "jatah_pendaftaran.py"

KASUS = (
    ("batas_per_ip_dilewati", J, [
        ("or len(milik) >= BATAS_PER_IP:", "or False:"),
    ], "test_per_ip_lima_lalu_habis_dan_pulih_setelah_jendela or test_atomik_di_bawah_permintaan_paralel"),
    ("batas_global_dilewati", J, [
        ("if len(_GLOBAL) >= BATAS_GLOBAL or", "if False or"),
    ], "test_batas_global_menahan_banyak_ip_berbeda"),
    ("jendela_tidak_memulihkan", J, [
        ("    return [t for t in daftar if kini - t < JENDELA_DETIK]", "    return list(daftar)"),
    ], "test_per_ip_lima_lalu_habis_dan_pulih_setelah_jendela"),
    ("plafon_kunci_dilewati", J, [
        ("    if len(_PER_IP) <= BATAS_KUNCI:\n        return\n", "    return\n"),
    ], "test_memori_dibatasi_oleh_plafon_kunci"),
    ("ipv6_tidak_dinormalkan", J, [
        ("        return str(ipaddress.ip_network((alamat, 64), strict=False))", "        return str(alamat)"),
    ], "test_ipv6_dalam_satu_blok_64_berbagi_jatah_dan_ipv4_mapped_sama_dengan_ipv4"),
    ("jatah_tidak_dicatat", J, [
        ("        milik.append(kini)\n        _PER_IP[kunci_ip_] = milik\n        _GLOBAL.append(kini)\n", "        _PER_IP[kunci_ip_] = milik\n"),
    ], "test_per_ip_lima_lalu_habis_dan_pulih_setelah_jendela"),
)


@pytest.mark.parametrize("nama,berkas,ganti,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_jatah_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, tes):
    uji_mutasi(tmp_path, berkas, ganti, TES, tes, SALIN_TES)
