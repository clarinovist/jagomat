"""Mutation guard halaman Guru laporan Peta (D1-2) pada SALINAN repo terisolasi (bukan workspace).

Meniru `test_admin_pesanan_purna_mutation.py`: tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang
menjaganya; hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama harus
HIJAU di salinan yang sama. Pola mutasi harus unik di berkasnya (count == 1). Salinan tidak memuat `.venv`, cadangan,
`*.db`, atau `*.json` (tanpa data/sandi nyata). Tiap kasus = satu param, jadi bisa dijalankan dengan `-k`.
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
T = "mesin/__tests__/test_peta_laporan_guru_http.py::"
HTTP = "mesin/peta_laporan_guru_http.py"
HAL = "mesin/peta_laporan_guru_pages.py"
TOKO = "mesin/peta_laporan_store.py"
ORDER = "mesin/pesanan_admin_order.py"
KASUS = (
    ("a-kepemilikan-guru-dilepas",
     ((HTTP, "    if siswa is None or not penangan._bisa_lihat_siswa(kon, anak_id):\n        return None\n",
       "    if siswa is None:\n        return None\n"),),
     (T + "test_bukan_pemilik_404_byte_identik_dengan_anak_tak_ada_dan_tanpa_efek",)),
    ("b-gerbang-order-sudah-dibayar-dilepas",
     ((HTTP, '            if order is None or not po.kartu_cek_berlaku(order["status"]):\n                return order, None\n',
       "            if order is None:\n                return order, None\n"),),
     (T + "test_order_belum_lunas_halaman_info_tanpa_form_dan_post_409_tanpa_efek",
      T + "test_order_ditahan_halaman_info_dan_post_409_tanpa_efek",
      T + "test_order_direfund_halaman_info_dan_post_409_walau_draf_sudah_ada")),
    ("c-order-dicari-bukan-per-anak",
     ((ORDER, '"SELECT order_id FROM pesanan_order WHERE siswa_id=?", (siswa_id,)).fetchone()',
       '"SELECT order_id FROM pesanan_order WHERE ?=?", (siswa_id, siswa_id)).fetchone()'),),
     (T + "test_anak_tanpa_order_404_identik_dan_tanpa_efek",)),
    ("d-peran-guru-pada-post-dilepas",
     ((HTTP, '        if not ident or ident[1] != "guru":\n            from support_pages',
       "        if not ident:\n            from support_pages"),),
     (T + "test_admin_hanya_melihat_post_403_tanpa_efek",)),
    ("e-konfirmasi-terbit-dilepas",
     ((HTTP, '    if data["konfirmasi"] != "1":\n        return _galat_form(ctx, PESAN_KONFIRMASI)\n    kon.execute("BEGIN IMMEDIATE")\n    try:\n        laporan = toko.ambil',
       '    kon.execute("BEGIN IMMEDIATE")\n    try:\n        laporan = toko.ambil'),),
     (T + "test_terbit_tanpa_centang_ditolak_400_tanpa_efek_lalu_dengan_centang_berhasil",)),
    ("f-konfirmasi-hapus-dilepas",
     ((HTTP, '    if data["konfirmasi"] != "1":\n        return _galat_form(ctx, PESAN_KONFIRMASI)\n    kon.execute("BEGIN IMMEDIATE")\n    try:\n        terhapus = toko.hapus_draf',
       '    kon.execute("BEGIN IMMEDIATE")\n    try:\n        terhapus = toko.hapus_draf'),),
     (T + "test_hapus_draf_butuh_centang_lalu_boleh_buat_ulang",)),
    ("g-purna-catat-terbit-tidak-dipanggil",
     ((HTTP, '            purna.catat_terbit(kon, order_id, _pelaku(laporan["diterbitkan_oleh"]), terbit)\n', "            pass\n"),),
     (T + "test_siklus_penuh_buat_catatan_terbit_dan_purna_tercatat_oleh_guru",
      T + "test_pelaku_purna_memakai_akun_guru_sesi_bukan_admin")),
    ("h-pengulangan-sinkron-dilepas",
     ((HTTP, '    perlu = (ident and ident[1] == "guru" and laporan is not None and laporan["diterbitkan"]\n             and purna_ringkas["terpasang"] and purna_ringkas["terbit"] is None)\n',
       "    perlu = False\n"),),
     (T + "test_pengulangan_saat_guru_membuka_halaman_dengan_waktu_terbit_laporan",)),
    ("i-pengulangan-juga-oleh-admin",
     ((HTTP, 'perlu = (ident and ident[1] == "guru" and laporan', "perlu = (ident and laporan"),),
     (T + "test_admin_membuka_halaman_tidak_mengulang_pencatatan_purna",)),
    ("j-snapshot-bukan-dari-pembangun",
     ((HTTP, "        isi = snapshot.bangun(cek)\n", "        isi = cek\n"),),
     (T + "test_isi_draf_dibangun_server_sama_dengan_snapshot_pembaca_allowlist",
      T + "test_siklus_penuh_buat_catatan_terbit_dan_purna_tercatat_oleh_guru")),
    ("k-buat-menerima-field-form",
     ((HTTP, "        return _buat(ctx) if not data else _galat_form(ctx, PESAN_FORM)\n", "        return _buat(ctx)\n"),),
     (T + "test_buat_dengan_field_apa_pun_400_isi_tidak_pernah_dari_form",)),
    ("l-batas-catatan-dilepas",
     ((TOKO, "    if len(catatan) > BATAS_CATATAN:\n        return CATATAN_PANJANG\n", ""),),
     (T + "test_catatan_2000_karakter_boleh_2001_ditolak_400_tanpa_efek",)),
    ("m-escape-dilepas",
     ((HAL, "    return html.escape(str(nilai), quote=True)\n", "    return str(nilai)\n"),),
     (T + "test_catatan_dan_nama_anak_di_escape_di_halaman",)),
    ("n-waktu-terbit-purna-bukan-waktu-laporan",
     ((HTTP, "    return (datetime.strptime(waktu_wib, _FORMAT_WIB) - _SELISIH_WIB).strftime(_FORMAT_BAKU)\n",
       "    return (datetime.strptime(waktu_wib, _FORMAT_WIB) - timedelta(0)).strftime(_FORMAT_BAKU)\n"),),
     (T + "test_siklus_penuh_buat_catatan_terbit_dan_purna_tercatat_oleh_guru",
      T + "test_pengulangan_saat_guru_membuka_halaman_dengan_waktu_terbit_laporan")),
    ("o-kegagalan-purna-membatalkan-laporan",
     ((HTTP, "    except Exception as galat:  # noqa: BLE001\n", "    except OSError as galat:  # noqa: BLE001\n"),),
     (T + "test_pencatatan_purna_gagal_laporan_tetap_terbit_303_dan_log_hanya_tipe",)),
    ("p-kartu-tidak-toleran-galat-ledger",
     ((HTTP, '    except (OrderTakTerbaca, ValueError, sqlite3.Error):\n        return ""\n',
       '    except (ValueError, sqlite3.Error):\n        return ""\n'),),
     (T + "test_kartu_toleran_galat_ledger_halaman_anak_tetap_200_tanpa_kartu",)),
    ("q-kartu-tanpa-gerbang-lunas",
     ((HTTP, '        if order is None or purna_ringkas is None:\n            return ""\n', '        if order is None:\n            return ""\n'),),
     (T + "test_kartu_tidak_ada_tanpa_order_atau_belum_lunas",)),
    ("r-ledger-tak-terbaca-jadi-500",
     ((HTTP, "        _log.warning(\"ledger Peta tidak terbaca: %s\", type(galat).__name__)\n        raise OrderTakTerbaca() from None\n",
       "        _log.warning(\"ledger Peta tidak terbaca: %s\", type(galat).__name__)\n        raise\n"),),
     (T + "test_ledger_tak_terbaca_halaman_belum_bisa_dibuka_503_tanpa_efek",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("peta-laporan-guru-mutasi") / "repo"
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
def test_guard_peta_guru_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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
