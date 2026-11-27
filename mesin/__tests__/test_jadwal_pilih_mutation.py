"""Mutation guard BARU pilih jadwal oleh orang tua (butir QA #4): sekali saja, kepemilikan, kuota/penutupan, token terikat kelompok.

Tiap kasus menonaktifkan satu guard di salinan source terisolasi dan memastikan tes terkait MERAH karena perilaku, lalu hijau
setelah dipulihkan (harness bersama: `harian_mutasi_kit`). Workspace asli tidak disentuh.

Sengaja TIDAK dimutasi (mutan setara): cek "sudah ditempatkan" dan kuota di `pilih_kelompok` yang juga dijaga PRIMARY KEY
`jadwal_penempatan.order_id` dan trigger kuota skema; di sana mutan hanya berganti jenis galat, bukan efek. Guard yang sama di
sisi DAFTAR pilihan (`pilihan_untuk`) dimutasi di bawah.
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES_DOMAIN = "test_jadwal_pilih.py"
TES_HTTP = "test_jadwal_pilih_http.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES_DOMAIN, TES_HTTP)

DOMAIN = "jadwal_pilih.py"
MURID = "kelas_murid_http.py"

# (nama, berkas, [(lama, baru), ...], berkas tes, ekspresi -k)
KASUS = (
    ("daftar_menawarkan_anak_yang_sudah_ditempatkan", DOMAIN, [
        ("            return None            # sudah ditempatkan (admin atau pilihan sendiri): sekali saja",
         "            pass"),
    ], TES_DOMAIN, "test_tanpa_order_mini_aktif_yang_belum_ditempatkan_tidak_ada_pilihan"),
    ("pilih_tanpa_cek_kepemilikan_anak", DOMAIN, [
        ("    with d.tulis(kon):\n        kelas_store._wajib_anak_milik(kon, akun_id, siswa_id)\n        order = _order_mini",
         "    with d.tulis(kon):\n        order = _order_mini"),
    ], TES_DOMAIN, "test_pilih_anak_milik_akun_lain_tidak_ditemukan"),
    ("daftar_tanpa_cek_kepemilikan_anak", DOMAIN, [
        ("    kelas_store._wajib_anak_milik(kon, akun_id, siswa_id)\n    order = _order_mini_tanpa_jadwal(kon, akun_id, siswa_id, kini)\n    if order is None:\n        return ()",
         "    order = _order_mini_tanpa_jadwal(kon, akun_id, siswa_id, kini)\n    if order is None:\n        return ()"),
    ], TES_DOMAIN, "test_tanpa_order_mini_aktif_yang_belum_ditempatkan_tidak_ada_pilihan"),
    ("daftar_kelompok_penuh_tidak_ditandai_penuh", DOMAIN, [
        ("    penuh = isi >= kelompok[\"kuota\"]\n", "    penuh = False\n"),
    ], TES_DOMAIN, "test_kelompok_penuh_tetap_tampil_bertanda_penuh_dan_tidak_bisa_dipilih"),
    ("daftar_menawarkan_kelompok_ditutup", DOMAIN, [
        ("    if berikut is None or js._jumlah_sudah_mulai(kon, kid, kini) >= js.TUTUP_SETELAH_PERTEMUAN_MULAI:\n        return None",
         "    if berikut is None:\n        return None"),
    ], TES_DOMAIN, "test_kelompok_ditutup_atau_selesai_atau_lewat_akses_tidak_ditawarkan"),
    ("daftar_menawarkan_kelompok_lewat_akses", DOMAIN, [
        ("    if terakhir is not None and batas is not None and terakhir > batas:\n        return None\n",
         "    if False:\n        return None\n"),
    ], TES_DOMAIN, "test_kelompok_ditutup_atau_selesai_atau_lewat_akses_tidak_ditawarkan"),
    ("pilih_menerima_paket_bukan_mini", DOMAIN, [
        ("            \"SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? AND paket=? ORDER BY dibuat DESC,id DESC\"\n            % ks.KOLOM_ORDER, (akun_id, siswa_id, schema_jadwal.KODE_PAKET_MINI)).fetchall():",
         "            \"SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? AND paket<>? ORDER BY dibuat DESC,id DESC\"\n            % ks.KOLOM_ORDER, (akun_id, siswa_id, schema_jadwal.KODE_PAKET_MINI)).fetchall():"),
    ], TES_DOMAIN, "test_pilih_tanpa_order_mini_aktif_konflik or test_tanpa_order_mini_aktif_yang_belum_ditempatkan_tidak_ada_pilihan"),
    ("pilih_menerima_order_belum_aktif", DOMAIN, [
        ("        if ks.status_dari(order, ks.fakta_order(kon, order[\"id\"]), kini) != dasar.STATUS_AKTIF:\n            continue\n        if kon.execute(\"SELECT 1 FROM jadwal_penempatan",
         "        if kon.execute(\"SELECT 1 FROM jadwal_penempatan"),
    ], TES_DOMAIN, "test_tanpa_order_mini_aktif_yang_belum_ditempatkan_tidak_ada_pilihan"),
    ("http_token_tidak_terikat_kelompok", MURID, [
        ("halaman.AKSI_JADWAL + kelompok, data[\"token\"]", "halaman.AKSI_JADWAL, data[\"token\"]"),
    ], TES_HTTP, "test_pilih_ditolak_tanpa_efek"),
    ("http_form_longgar", MURID, [
        ("    if data is None or set(data) != KUNCI_FORM_JADWAL:", "    if data is None:"),
    ], TES_HTTP, "test_pilih_ditolak_tanpa_efek"),
    ("http_post_jadwal_tanpa_gerbang_sakelar", MURID, [
        ("    if jalur not in _POST or not paket_belajar_gate.aktif():", "    if jalur not in _POST:"),
    ], TES_HTTP, "test_sakelar_mati_rute_jadwal_menjawab_seperti_rute_lain"),
)


@pytest.mark.parametrize("nama,berkas,ganti,berkas_tes,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_pilih_jadwal_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, berkas_tes, tes):
    uji_mutasi(tmp_path, berkas, ganti, berkas_tes, tes, SALIN_TES)
