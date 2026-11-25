"""Mutation guard BARU jadwal Private orang tua (gerbang tirai, sakelar, form, dan pemilik anak).

Tiap kasus: tes HTTP terarah hijau pada salinan source terisolasi, lalu merah setelah guard dinonaktifkan lewat
jalur yang dipanggil tes, lalu hijau lagi setelah dipulihkan (`harian_mutasi_kit.uji_mutasi`).
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES = "test_jadwal_private_murid_http.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES)
MURID = "kelas_murid_http.py"
PRIVAT = "jadwal_private_murid_http.py"
BACA = "jadwal_private_baca.py"

KASUS = (
    ("post_tanpa_gerbang_tirai", MURID, [
        ("    if _tirai_tertutup(penangan, *pembeli):  # PIN terpasang dan tirai tertutup: tanpa efek", "    if False:"),
    ], "test_pin_tirai_tertutup_menolak_ajukan_dan_menyembunyikan_kartu"),
    ("tanpa_cek_sakelar", MURID, [
        ("    if jalur not in _POST or not paket_belajar_gate.aktif():", "    if jalur not in _POST:"),
    ], "test_sakelar_mati_jawab_seperti_rute_murid_tanpa_efek"),
    ("kunci_form_menerima_order", PRIVAT, [
        ('KUNCI_FORM_AJUKAN = frozenset({"token", "slot"})', 'KUNCI_FORM_AJUKAN = frozenset({"token", "slot", "order"})'),
    ], "test_form_atau_token_salah_ditolak_tanpa_efek"),
    ("tanpa_cek_pemilik_anak", BACA, [
        ("    kelas_store._wajib_anak_milik(kon_admin, akun, siswa)\n    oid = _order_privat_terbaru(kon_admin, akun, siswa, kini)\n    if oid is None:\n        return None\n    fakta = fakta_order",
         "    oid = _order_privat_terbaru(kon_admin, akun, siswa, kini)\n    if oid is None:\n        return None\n    fakta = fakta_order"),
        ('"SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? AND paket=? ORDER BY dibuat DESC,id DESC"',
         '"SELECT %s FROM kelas_order WHERE siswa_id=? AND paket=? ORDER BY dibuat DESC,id DESC"'),
        ("% ks.KOLOM_ORDER, (akun_id, siswa_id, dsr.PAKET)).fetchall():", "% ks.KOLOM_ORDER, (siswa_id, dsr.PAKET)).fetchall():"),
    ], "test_anak_tanpa_order_private_dan_akun_terhubung_tidak_bisa_mengajukan"),
)


@pytest.mark.parametrize("nama,berkas,ganti,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_jadwal_private_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, tes):
    uji_mutasi(tmp_path, berkas, ganti, TES, tes, SALIN_TES)
