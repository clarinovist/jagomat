"""Mutation guard BARU pemilihan tagihan penerima bukti di dalam transaksi dan urutan tagihan terbaru (butir QA #3).

Tidak dimutasi (setara): cek jendela bayar (status turunan sudah menyingkirkan order kedaluwarsa) dan cek berkas kembar antar-tagihan
(indeks unik sha256 di skema menolak dengan hasil yang sama, KelasKonflik).
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES_BALAPAN = "test_kelas_ganti_balapan.py"
TES_DOMAIN = "test_kelas_ganti.py"
TES_MURID = "test_kelas_murid_http.py"
TES_UNGGAH = "test_kelas_unggah.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + (
    "conftest.py", TES_BALAPAN, TES_DOMAIN, TES_MURID, TES_UNGGAH)
UNGGAH = "kelas_unggah.py"
MURID = "kelas_murid_http.py"
STATUS = "kelas_status.py"

KASUS = (
    ("bukti_ke_tagihan_terlama", UNGGAH, [
        ("next(iter(ks.order_terbuka_siswa(kon, akun_id, siswa_id, kini)), None)",
         "next(iter(reversed(list(ks.order_terbuka_siswa(kon, akun_id, siswa_id, kini)))), None)"),
    ], TES_BALAPAN, "test_ganti_yang_menyelip_di_antara_baca_dan_tulis_tidak_membuat_bukti_jatuh_ke_tagihan_lama"),
    ("unggah_kembali_memakai_kode_paket_lama", MURID, [
        ("        hasil = kelas_unggah.catat_bukti_terbaru(kon, akun_id, siswa_id, mime, len(isi),\n                                                 hashlib.sha256(isi).hexdigest(), nama, kini)",
         "        hasil = store.catat_bukti(kon, akun_id, siswa_id, 'mini', mime, len(isi),\n                                  hashlib.sha256(isi).hexdigest(), nama, kini)"),
    ], TES_BALAPAN, "test_ganti_yang_menyelip_di_antara_baca_dan_tulis_tidak_membuat_bukti_jatuh_ke_tagihan_lama"),
    ("batas_bukti_tidak_dicek", UNGGAH, [
        ("        if fakta.jumlah_bukti >= k.MAKS_BUKTI:\n            raise k.BatasBukti()\n", ""),
    ], TES_UNGGAH, "test_batas_bukti_tercapai_melempar_batas_bukti"),
    ("berkas_sama_menunggu_ditulis_ganda", UNGGAH, [
        ("        if sama is not None:\n            return", "        if False:\n            return"),
    ], TES_UNGGAH, "test_berkas_sama_menunggu_mengembalikan_bukti_yang_ada"),
    ("terbaru_menurut_waktu_buat", STATUS, [
        ('"ORDER BY rowid DESC" % KOLOM_ORDER, (akun_id, siswa_id)).fetchall():\n        fakta = fakta_order',
         '"ORDER BY dibuat DESC,rowid DESC" % KOLOM_ORDER, (akun_id, siswa_id)).fetchall():\n        fakta = fakta_order'),
    ], TES_DOMAIN, "test_tagihan_terbaru_menang_walau_jam_server_mundur"),
)


@pytest.mark.parametrize("nama,berkas,ganti,berkas_tes,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_balapan_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, berkas_tes, tes):
    uji_mutasi(tmp_path, berkas, ganti, berkas_tes, tes, SALIN_TES)
