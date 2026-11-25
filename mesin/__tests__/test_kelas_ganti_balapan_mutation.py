"""Mutation guard BARU serialisasi unggah/ganti dan urutan tagihan terbaru (butir QA #3): tes terkait harus MERAH bila guard dimatikan."""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES_BALAPAN = "test_kelas_ganti_balapan.py"
TES_DOMAIN = "test_kelas_ganti.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES_BALAPAN, TES_DOMAIN)
MURID = "kelas_murid_http.py"
STATUS = "kelas_status.py"

KASUS = (
    ("unggah_tanpa_kunci", MURID, [
        ("    with _kunci_anak(akun_id, siswa_id), _buka(tulis=True) as kon:", "    with _buka(tulis=True) as kon:"),
    ], TES_BALAPAN, "test_ganti_yang_masuk_saat_unggah_berjalan_menunggu_lalu_ditolak_karena_bukti_sudah_ada"),
    ("ganti_tanpa_kunci", MURID, [
        ("        with _kunci_anak(principal.id_akun, siswa_id), _buka(tulis=True) as kon:", "        with _buka(tulis=True) as kon:"),
    ], TES_BALAPAN, "test_ganti_yang_masuk_saat_unggah_berjalan_menunggu_lalu_ditolak_karena_bukti_sudah_ada"),
    ("terbaru_menurut_waktu_buat", STATUS, [
        ('"ORDER BY rowid DESC" % KOLOM_ORDER, (akun_id, siswa_id)).fetchall():\n        fakta = fakta_order',
         '"ORDER BY dibuat DESC,rowid DESC" % KOLOM_ORDER, (akun_id, siswa_id)).fetchall():\n        fakta = fakta_order'),
    ], TES_DOMAIN, "test_tagihan_terbaru_menang_walau_jam_server_mundur"),
)


@pytest.mark.parametrize("nama,berkas,ganti,berkas_tes,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_balapan_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, berkas_tes, tes):
    uji_mutasi(tmp_path, berkas, ganti, berkas_tes, tes, SALIN_TES)
