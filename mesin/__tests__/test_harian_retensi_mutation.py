"""Mutation guard retensi bukti langganan Latihan Harian pada salinan source terisolasi (harness: `harian_mutasi_kit`).

Tiap kasus mematikan satu guard (ambang 30 hari, bukti menunggu, urutan hapus-lalu-tandai, subfolder, pemilihan DB belajar,
exit code) dan memastikan tes terkait MERAH karena perilaku, lalu HIJAU setelah dipulihkan.
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES = "test_harian_bukti_retensi.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES)
RT = "harian_bukti_retensi.py"

# (nama, berkas, [(lama, baru), ...], ekspresi -k)
KASUS = (
    ("tandai_sebelum_hapus", "pesanan_retensi.py", [
        ('    try:\n        terhapus = bukti_berkas.hapus_berkas(bukti["berkas"], folder)\n',
         '    (tandai or pesanan_transfer.tandai_dihapus)(kon, bukti["bukti_id"], sekarang, hari)\n'
         '    try:\n        terhapus = bukti_berkas.hapus_berkas(bukti["berkas"], folder)\n'),
    ], "test_urutan_aman_berkas_dihapus_sebelum_bukti_ditandai"),
    ("ambang_30_hari_diabaikan", RT, [
        ("    kedaluwarsa = bukti_kedaluwarsa(kon, sekarang, hari)", '    kedaluwarsa = bukti_kedaluwarsa(kon, "2999-01-01T00:00:00", 1)'),
    ], "test_sapu_kurang_sedetik_dari_30_hari_tidak_menyentuh_apa_pun"),
    ("hari_tidak_diteruskan", RT, [
        ("    kedaluwarsa = bukti_kedaluwarsa(kon, sekarang, hari)", "    kedaluwarsa = bukti_kedaluwarsa(kon, sekarang)"),
    ], "test_hari_lebih_pendek_diteruskan_ke_penandaan"),
    ("bukti_menunggu_ikut_dihapus", RT, [
        ("AND EXISTS(SELECT 1 FROM harian_verifikasi v WHERE v.order_id=b.order_id \"\n        \"AND v.bukti_hingga_id>=b.id AND v.dibuat<=?)",
         "AND ? IS NOT NULL"),
    ], "test_bukti_menunggu_tidak_pernah_dihapus_walau_sangat_lama or test_bukti_ditolak_ikut_dihapus"),
    ("hitungan_dari_unggah_bukan_keputusan", RT, [
        ("v.dibuat<=?)", "v.dibuat<=? OR 1)"),
    ], "test_hitungan_30_hari_dari_keputusan_bukan_dari_unggah or test_sapu_kurang_sedetik_dari_30_hari"),
    ("subfolder_hilang_tetap_menandai", RT, [
        ("    if not sub.is_dir():", "    if False:"),
    ], "test_subfolder_tidak_ada_dengan_bukti_kedaluwarsa_tidak_menandai_apa_pun"),
    ("sapu_folder_induk_bukan_subfolder", RT, [
        ("    sub = Path(folder) / berkas.SUBFOLDER\n", "    sub = Path(folder)\n"),
    ], "test_sapu_menghapus_berkas_lalu_menandai_bukti_yang_sudah_30_hari"),
    ("penanda_tanpa_trigger_putusan", "schema_harian_langganan.py", [
        ('"NOT EXISTS(SELECT 1 FROM harian_verifikasi v WHERE v.bukti_hingga_id>=NEW.bukti_id "',
         '"0 AND NOT EXISTS(SELECT 1 FROM harian_verifikasi v WHERE v.bukti_hingga_id>=NEW.bukti_id "'),
    ], "test_penanda_bukti_belum_diputuskan_ditolak_skema"),
    ("penanda_tidak_append_only", "schema_harian_langganan.py", [
        ('"harian_akses", "harian_bukti_hapus")', '"harian_akses")'),
    ], "test_penanda_append_only_dan_tidak_bisa_ditimpa"),
    ("opsi_db_belajar_diabaikan", RT, [
        ("    if opsi:\n        return Path(opsi)\n", ""),
    ], "test_cli_opsi_database_belajar_mengalahkan_env_dan_samping"),
    ("env_db_belajar_diabaikan", RT, [
        ('    lingkungan = os.environ.get(NAMA_ENV_DB, "").strip()', '    lingkungan = ""'),
    ], "test_cli_env_osn_berkas_db_dipakai_bila_tanpa_opsi_dan_mengalahkan_samping"),
    ("db_belajar_bawaan_kode", RT, [
        ("else Path(path_admin).resolve().parent / NAMA_DB_SAMPING", "else database.BAWAAN"),
    ], "test_cli_menyapu_langganan_lewat_jalur_pesanan_retensi_dengan_db_belajar_di_samping"),
    ("db_belajar_tidak_ada_membuat_berkas", RT, [
        ("    if not path.is_file():\n        return False\n", ""),
    ], "test_cli_tanpa_db_belajar_dilewati_tanpa_membuat_berkas_dan_transfer_tetap_jalan"),
    ("tabel_belajar_tidak_diperiksa", RT, [
        ("    return _TABEL_WAJIB <= ada", "    return True"),
    ], "test_cli_db_belajar_tanpa_tabel_penanda_dilewati_tanpa_membuat_tabel"),
    ("gagal_langganan_exit_0", "pesanan_retensi.py", [
        ("    if hasil.gagal or gagal_langganan:", "    if hasil.gagal:"),
    ], "test_cli_gagal_langganan_keluar_1_dan_ledger_belajar_utuh"),
)


@pytest.mark.parametrize("nama,berkas,ganti,tes", KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_retensi_langganan_merah_lalu_pulih(tmp_path, nama, berkas, ganti, tes):
    uji_mutasi(tmp_path, berkas, ganti, TES, tes, SALIN_TES)
