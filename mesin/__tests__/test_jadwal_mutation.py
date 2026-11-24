"""Mutation guard jadwal Paket Belajar pada SALINAN repo terisolasi (bukan workspace).

Menonaktifkan satu guard lalu menjalankan tes yang menjaganya: hasil harus MERAH karena asersi. Kontrol:
tanpa mutasi, tes yang sama hijau di salinan yang sama. Guard kuota berlapis (store + trigger) dimutasi
bersama supaya tidak tertutup lapis lain. Guard perpanjangan (pensiun penempatan lama, lepas Private, order bersesi, isolasi jadwal murid, kartu
jadwal) dimutasi juga. Guard paket perbaikan 25 Nov (batas akses, kelompok selesai, kembar,
waktu mulai) tidak punya lapis kedua di skema, jadi satu mutasi cukup.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

AKAR = Path(__file__).resolve().parents[2]
S = "mesin/__tests__/test_jadwal_store.py::"
D = "mesin/__tests__/test_jadwal_dasar.py::"
H = "mesin/__tests__/test_jadwal_admin_pages.py::"
P = "mesin/__tests__/test_jadwal_perpanjangan.py::"
K = "mesin/__tests__/test_kelas_pages.py::"
W = "mesin/__tests__/test_jadwal_murid_http.py::"
STORE = "mesin/jadwal_store.py"
SKEMA = "mesin/schema_jadwal.py"
DASAR = "mesin/jadwal_dasar.py"
HALAMAN = "mesin/jadwal_admin_pages.py"
KELAS_HALAMAN = "mesin/kelas_pages.py"
KELAS_MURID = "mesin/kelas_murid_http.py"

KASUS = (
    ("kuota-store-dan-trigger",
     ((STORE, '''            if _isi_kelompok(kon, kid) >= kelompok["kuota"]:
                raise jd.JadwalPenuh()
''', ""),
      (SKEMA, '''DDL += _trigger(
    "jadwal_penempatan_kuota", "jadwal_penempatan", "INSERT",
    "NEW.kelompok_id IS NOT NULL AND (SELECT COUNT(*) FROM jadwal_penempatan "
    "WHERE kelompok_id=NEW.kelompok_id) >= (SELECT kuota FROM jadwal_kelompok WHERE id=NEW.kelompok_id)",
    "kelompok penuh")
''', ""),),
     (S + "test_tempatkan_mini_sampai_kuota_penuh",)),
    ("anak-trigger",
     ((SKEMA, '''DDL += _trigger(
    "jadwal_penempatan_anak", "jadwal_penempatan", "INSERT",
    "EXISTS(SELECT 1 FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id "
    "JOIN kelas_order n ON n.id=NEW.order_id WHERE o.siswa_id=n.siswa_id)",
    "anak sudah punya penempatan")
''', ""),),
     (S + "test_anak_tidak_bisa_punya_dua_penempatan",)),
    ("hanya-order-aktif",
     ((STORE, '''    if ks.status_dari(order, ks.fakta_order(kon, order_id), kini) != dasar.STATUS_AKTIF:
''', "    if False:\n"),),
     (S + "test_hanya_order_aktif_yang_bisa_ditempatkan",)),
    ("akses-private-tempatkan",
     ((STORE, "        _pastikan_dalam_akses(jd.delapan_pertemuan(mulai)[-1], _batas_akses_order(kon, order_id))\n", ""),),
     (S + "test_private_pertemuan_terakhir_melewati_akses_ditolak_tanpa_tulis",)),
    ("akses-mini-tempatkan",
     ((STORE, "            _pastikan_dalam_akses(_pertemuan_aktif_terakhir(kon, kid), _batas_akses_order(kon, order_id))\n",
       ""),),
     (S + "test_mini_pertemuan_aktif_terakhir_melewati_akses_ditolak",)),
    ("akses-ubah-pertemuan",
     ((STORE, "        _pastikan_dalam_akses(mulai, _batas_akses_sesi(kon, sesi), PESAN_GESER_LEWAT_AKSES)\n", ""),),
     (S + "test_ubah_pertemuan_private_tidak_boleh_melewati_akses",
      S + "test_ubah_pertemuan_kelompok_dibatasi_akses_anggota_terpendek")),
    ("akses-kelompok-anggota-terpendek",
     ((STORE, "SELECT MIN(akhir) FROM (SELECT MAX(a.berakhir)", "SELECT MAX(akhir) FROM (SELECT MAX(a.berakhir)"),),
     (S + "test_ubah_pertemuan_kelompok_dibatasi_akses_anggota_terpendek",)),
    ("kelompok-selesai-ditolak",
     ((STORE, '''            if _pertemuan_mendatang(kon, kid, kini) is None:
                raise jd.JadwalKonflik("kelompok sudah selesai")
''', ""),),
     (S + "test_mini_kelompok_selesai_ditolak_tanpa_penempatan",
      S + "test_mini_kelompok_semua_pertemuan_dibatalkan_dianggap_selesai")),
    ("kelompok-kembar-ditolak",
     ((STORE, "        _tolak_kelompok_kembar(kon, nama, mulai)\n", ""),),
     (S + "test_buat_kelompok_kembar_ditolak_dan_klik_ganda_tidak_menulis",)),
    ("berikut-hanya-mendatang",
     ((STORE, "s.dibatalkan=0 AND s.mulai>=?) AS berikut", "s.dibatalkan=0 AND ?<>'') AS berikut"),),
     (S + "test_daftar_kelompok_berikut_adalah_pertemuan_aktif_mendatang",)),
    ("dropdown-sembunyikan-selesai",
     ((HALAMAN, 'if sisa > 0 and b.get("berikut"):', "if sisa > 0:"),),
     (H + "test_penempatan_mini_menyembunyikan_kelompok_selesai",)),
    ("pensiun-tidak-menyambung-akses",
     ((STORE, "    return mulai_baru is not None and akhir <= mulai_baru and not _sesi_lama_tersisa(kon, order_lama, kini)\n",
       "    return False\n"),),
     (P + "test_perpanjangan_private_memensiunkan_penempatan_lama_dan_sesinya_tetap_riwayat",
      P + "test_perpanjangan_mini_memensiunkan_anggota_lama_dan_sesi_kelompok_utuh",
      P + "test_pensiun_hanya_bila_akses_lama_berakhir_tepat_di_batas_atau_lebih_awal")),
    ("pensiun-tidak-memakai-waktu-sekarang",
     ((STORE, "    if akhir <= kini:\n        return True\n", ""),),
     (P + "test_penempatan_lama_yang_sudah_lewat_waktu_sekarang_dipensiunkan_walau_tak_menyambung",)),
    ("pensiun-abaikan-sesi-lama-tersisa",
     ((STORE, " and not _sesi_lama_tersisa(kon, order_lama, kini)\n", "\n"),),
     (P + "test_perpanjangan_dini_private_dengan_sesi_lama_tersisa_tetap_konflik_tanpa_efek",
      P + "test_perpanjangan_dini_mini_dengan_sesi_kelompok_tersisa_tetap_konflik_tanpa_efek")),
    ("lepas-private-hitung-sesi-dibatalkan",
     ((STORE, "WHERE order_id=? AND mulai<? AND dibatalkan=0 LIMIT 1", "WHERE order_id=? AND mulai<? LIMIT 1"),),
     (P + "test_lepas_private_diizinkan_bila_sesi_yang_sudah_lewat_semuanya_dibatalkan",)),
    ("pensiun-tanpa-syarat-akses",
     ((STORE, "    if not all(_akses_lama_berakhir(kon, ada, mulai_baru, kini) for ada in lama):\n        return\n", ""),),
     (P + "test_akses_lama_masih_berjalan_melewati_mulai_baru_tetap_konflik_tanpa_efek",)),
    ("pensiun-tidak-atomik",
     ((STORE, '        kon.execute("DELETE FROM jadwal_penempatan WHERE order_id=?", (ada,))\n',
       '        kon.execute("DELETE FROM jadwal_penempatan WHERE order_id=?", (ada,))\n        kon.commit()\n'),),
     (P + "test_perpanjangan_mini_ke_kelompok_penuh_dibatalkan_dan_pensiun_ikut_rollback",
      P + "test_pensiun_private_ikut_rollback_bila_penulisan_sesi_gagal")),
    ("private-order-bersesi-boleh-ditempatkan-ulang",
     ((STORE, '        if _punya_sesi(kon, order_id):\n'
              '            raise jd.JadwalKonflik("pertemuan order ini sudah pernah dijadwalkan")\n', ""),),
     (P + "test_private_order_yang_sudah_bersesi_tidak_bisa_ditempatkan_ulang",)),
    ("lepas-private-setelah-mulai-diizinkan",
     ((STORE, '            if _sesi_sudah_mulai(kon, order_id, kini):\n'
              '                raise jd.JadwalKonflik("sebagian pertemuan sudah berlangsung; penempatan tidak dilepas")\n',
       ""),),
     (P + "test_lepas_private_ditolak_setelah_ada_sesi_yang_sudah_mulai_tanpa_efek",
      P + "test_lepas_private_ditolak_bila_hanya_sebagian_sesi_yang_sudah_mulai")),
    ("lepas-private-batas-tepat-mulai",
     ((STORE, "WHERE order_id=? AND mulai<? AND dibatalkan=0 LIMIT 1", "WHERE order_id=? AND mulai<=? AND dibatalkan=0 LIMIT 1"),),
     (P + "test_lepas_private_diizinkan_bila_semua_sesi_di_masa_depan_dan_sesi_terhapus",)),
    ("jadwal-murid-bukan-milik-akun-dan-anak-sesi",
     ((STORE, 'FROM kelas_order WHERE akun_id=? AND siswa_id=? "', "FROM kelas_order WHERE ?<>'' AND ?<>0 \""),),
     (P + "test_jadwal_terbaru_murid_hanya_milik_akun_dan_anak_sendiri",
      W + "test_anak_lain_tidak_melihat_jadwal_anak_lain_dan_kueri_diabaikan")),
    ("jadwal-murid-gagal-diam",
     ((KELAS_MURID, "    except (admin_store_core.StoreBelumSiap, sqlite3.Error, ValueError):\n        return None\n",
       "    except ZeroDivisionError:\n        return None\n"),),
     (W + "test_jadwal_belum_dipasang_halaman_tetap_200_tanpa_kartu",
      W + "test_jadwal_rusak_parsial_halaman_tetap_200_tanpa_kartu")),
    ("kartu-jadwal-lokasi-tanpa-escape",
     ((KELAS_HALAMAN, "{_baris('Lokasi', jadwal['lokasi'])}",
       "<p>Lokasi: <strong>{jadwal['lokasi']}</strong></p>"),),
     (K + "test_kartu_jadwal_escape_lokasi_dan_tanpa_skrip", W + "test_lokasi_berbahaya_ter_escape")),
    ("kartu-jadwal-tanpa-label-dibatalkan",
     ((KELAS_HALAMAN, '    if sesi["dibatalkan"]:\n', "    if False:\n"),),
     (K + "test_kartu_jadwal_memuat_lokasi_delapan_pertemuan_waktu_wib_dan_label_dibatalkan",
      W + "test_kartu_jadwal_private_lokasi_online_dan_label_dibatalkan")),
    ("waktu-mulai-lampau-level-jam",
     ((DASAR, "if not izinkan_lampau and baku < sekarang:", "if False:"),),
     (D + "test_pertemuan_pertama_menolak_jam_yang_sudah_lewat_pada_hari_yang_sama",)),
    ("batas-atas-tanggal-mulai",
     ((DASAR, "if waktu.date() > h.tanggal_wib(sekarang) + timedelta(days=BATAS_MAJU_HARI):", "if False:"),),
     (D + "test_pertemuan_pertama_menolak_lebih_dari_366_hari_ke_depan",
      D + "test_tahun_ekstrem_jadwal_tidak_sah_bukan_overflow")),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("jadwal-mutasi") / "repo"
    shutil.copytree(AKAR / "mesin", akar / "mesin", ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json"))
    return akar


def _jalankan(akar: Path, sasaran):
    env = dict(os.environ, PYTHONPATH=str(akar / "mesin"),
               PYTHONDONTWRITEBYTECODE="1", OSN_PBKDF2_ITERASI="1000")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *sasaran, "-q", "-W", "error", "-p", "no:cacheprovider"],
        cwd=akar, env=env, text=True, capture_output=True, timeout=240)


def test_kontrol_tanpa_mutasi_hijau_di_salinan(salinan):
    sasaran = sorted({t for _, _, ts in KASUS for t in ts})
    hasil = _jalankan(salinan, sasaran)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_jadwal_menangkap_mutasi(salinan, nama, suntingan, sasaran):
    asli = {}
    try:
        for rel, lama, baru in suntingan:
            berkas = salinan / rel
            sumber = asli.setdefault(rel, berkas.read_text(encoding="utf-8"))
            terkini = berkas.read_text(encoding="utf-8")
            assert terkini.count(lama) == 1, "%s: pola mutasi harus unik di %s" % (nama, rel)
            berkas.write_text(terkini.replace(lama, baru), encoding="utf-8")
            assert sumber != berkas.read_text(encoding="utf-8")
        hasil = _jalankan(salinan, sasaran)
    finally:
        for rel, sumber in asli.items():
            (salinan / rel).write_text(sumber, encoding="utf-8")
    keluaran = hasil.stdout + hasil.stderr
    assert hasil.returncode == 1, keluaran
    assert re.search(r"\b\d+ failed", keluaran), keluaran
    assert not re.search(r"\b\d+ error", keluaran), keluaran
