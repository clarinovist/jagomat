"""Mutation guard jadwal private (orang tua mengajukan, admin menyetujui): tiap guard dimatikan di salinan source terisolasi.

Setiap kasus memastikan tes terkait HIJAU, MERAH karena perilaku setelah guard dinonaktifkan, lalu HIJAU lagi setelah
dipulihkan (harness bersama: `harian_mutasi_kit`). Workspace asli tidak disentuh.
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES_DOMAIN = "test_jadwal_private.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES_DOMAIN)

BACA = "jadwal_private_baca.py"
DASAR = "jadwal_private_dasar.py"
TULIS = "jadwal_private.py"

# (nama, berkas, [(lama, baru), ...], ekspresi -k)
KASUS = (
    ("ajukan_order_orang_lain_tanpa_cek_kepemilikan", BACA, [
        ("WHERE akun_id=? AND siswa_id=? AND paket=? ORDER BY dibuat DESC,id DESC",
         "WHERE siswa_id=? AND paket=? ORDER BY dibuat DESC,id DESC"),
        ("% ks.KOLOM_ORDER, (akun_id, siswa_id, dsr.PAKET)).fetchall():",
         "% ks.KOLOM_ORDER, (siswa_id, dsr.PAKET)).fetchall():"),
        ("    kelas_store._wajib_anak_milik(kon_admin, akun, siswa)\n    oid = _order_privat_terbaru(kon_admin, akun, siswa, kini)\n"
         "    if oid is None:\n        return None\n    fakta = fakta_order(",
         "    oid = _order_privat_terbaru(kon_admin, akun, siswa, kini)\n    if oid is None:\n        return None\n    fakta = fakta_order("),
    ], "test_order_milik_akun_atau_anak_lain_tidak_bisa_mengajukan"),
    ("ajukan_tanpa_cek_24_jam", BACA, [
        ("    if slot.mulai < dsr.batas_pesan(kini):", "    if False:"),
    ], "test_slot_mulai_kurang_dari_24_jam_tidak_ditawarkan_dan_ditolak_saat_ajukan"),
    ("slot_tanpa_cek_masa_akses_pertemuan_ke8", DASAR, [
        ("    if jd.delapan_pertemuan(slot.mulai)[-1] > fakta.batas:", "    if False:"),
    ], "test_slot_pertemuan_ke8_melewati_masa_akses_tidak_ditawarkan"),
    ("setujui_lewati_cek_status_diajukan", TULIS, [
        ('        if pengajuan["status"] != dsr.STATUS_DIAJUKAN:', "        if False:"),
    ], "test_setujui_pengajuan_yang_sudah_ditolak_ditolak_tanpa_penempatan"),
    ("batalkan_pengajuan_tanpa_cek_milik_anak", TULIS, [
        ('        if baris["order_id"] in milik:', "        if True:"),
    ], "test_batalkan_pengajuan_hanya_milik_anak_itu"),
    ("pengajuan_basi_tetap_menahan_slot", BACA, [
        ('        if _basi_pengajuan(kon_admin, baris["order_id"], slot, kini, guru_sah, terisi) is None:',
         "        if True:"),
    ], "test_penempatan_manual_lain_membuat_pengajuan_basi_dan_setujui_ditolak"),
)


@pytest.mark.parametrize("nama,berkas,ganti,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_jadwal_private_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, tes):
    uji_mutasi(tmp_path, berkas, ganti, TES_DOMAIN, tes, SALIN_TES)
