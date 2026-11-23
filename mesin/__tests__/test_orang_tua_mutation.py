"""Mutation guard halaman orang tua (F3) pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang menjaganya: hasil harus MERAH karena
asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama HIJAU di salinan yang sama. Pola
mutasi harus unik di berkasnya. Salinan tidak memuat `.venv`, cadangan, `*.db`, atau `*.json`.
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
H = "mesin/__tests__/test_orang_tua_http.py::"
L = "mesin/__tests__/test_orang_tua_laporan.py::"
U = "mesin/__tests__/test_tirai_orang_tua.py::"
HTTP, DATA, TIRAI = "mesin/orang_tua_http.py", "mesin/orang_tua_data.py", "mesin/tirai_orang_tua.py"
STORE, SISWA, WEB = "mesin/parent_report_store.py", "mesin/student_http.py", "mesin/web.py"
_KUERI = '(urllib.parse.parse_qs(urllib.parse.urlparse(penangan.path).query).get("siswa_id") or [siswa_id])[0]'

KASUS = (
    ("F1-siswa-dari-query",
     ((HTTP, "    ctx = _konteks(penangan, principal, siswa_id)\n    _tampilkan(",
       "    ctx = _konteks(penangan, principal, int(%s))\n    _tampilkan(" % _KUERI),),
     (H + "test_siswa_hanya_dari_sesi_parameter_palsu_diabaikan",)),
    ("F2-siswa-dari-form",
     ((HTTP, "        siswa_id = _siswa_sesi(kon, principal)\n",
       '        siswa_id = int(data.get("siswa_id") or 0) or _siswa_sesi(kon, principal)\n'),),
     (H + "test_siswa_dari_form_diabaikan_pada_aksi_pin",)),
    ("F3-tirai-selalu-terbuka",
     ((HTTP, "        return self.token is not None and tirai.terbuka(self.token, self.id_akun, self.siswa_id)",
       "        return True"),),
     (H + "test_dengan_pin_form_dulu_tanpa_isi", H + "test_ganti_pin_saat_tertutup_ditolak_tanpa_efek_saat_terbuka_berhasil",
      H + "test_hapus_pin_butuh_tirai_terbuka_dan_konfirmasi")),
    ("F4-laju-pin-dimatikan",
     ((HTTP, "    if laju_masuk.sedang_diblokir(*kunci):", "    if False:"),),
     (H + "test_blokir_setelah_batas_laju_tanpa_menjalankan_pbkdf2",)),
    ("F5-kontak-dirender",
     ((HTTP, "    data = orang_tua_data.kumpulkan(kon, ctx.id_akun, ctx.siswa_id)\n    _kirim(penangan, halaman.halaman_isi(data, ada_pin, kabar=kabar, galat=galat), kode)",
       "    data = orang_tua_data.kumpulkan(kon, ctx.id_akun, ctx.siswa_id)\n    import kontak_akun\n"
       '    wa = (kontak_akun.ambil(kon, ctx.id_akun) or {}).get("wa", "")\n'
       '    _kirim(penangan, halaman.halaman_isi(data, ada_pin, kabar=kabar, galat=galat).replace(b"</main>", ("<p>" + wa + "</p></main>").encode(), 1), kode)'),),
     (H + "test_kontak_wa_tidak_pernah_dirender_dan_kalimat_ortu_ada",)),
    ("F6a-gerbang-get-dimatikan",
     ((HTTP, "    if not tersedia():\n        return False\n    principal = penangan._principal()\n    if principal is None:\n        return False",
       "    principal = penangan._principal()\n    if principal is None:\n        return False"),),
     (H + "test_sakelar_mati_get_identik_rute_murid_tak_dikenal",)),
    ("F6b-gerbang-post-dimatikan",
     ((HTTP, "    if jalur not in RUTE_POST or not tersedia():", "    if jalur not in RUTE_POST:"),),
     (H + "test_sakelar_mati_post_identik_rute_tak_dikenal_dan_tanpa_efek",)),
    ("F6c-gerbang-tombol-beranda-dimatikan",
     ((SISWA, "orang_tua=orang_tua_http.tersedia()", "orang_tua=True"),),
     (H + "test_tombol_beranda_hanya_saat_sakelar_hidup",)),
    ("F7-basic-berbagi-tirai",
     ((HTTP, 'token = penangan._ambil_token() if principal.metode == "cookie" else None',
       'token = penangan._ambil_token() or "basic"'),),
     (H + "test_basic_auth_dengan_pin_benar_tidak_pernah_membuka_tirai",)),
    ("F8-draf-terbaca",
     ((STORE, "WHERE l.siswa_id = ? AND l.diterbitkan IS NOT NULL", "WHERE l.siswa_id = ?"),),
     (L + "test_terbit_terbaru_none_tanpa_laporan_terbit", H + "test_laporan_terbit_terbaru_tampil_bukan_draf_atau_yang_lama")),
    ("F8b-dicabut-diabaikan",
     ((STORE, "WHERE siswa_id = ? AND dicabut IS NOT NULL", "WHERE siswa_id = ? AND dicabut IS NULL AND 0"),),
     (L + "test_tautan_dicabut_menyembunyikan_laporan_dan_halaman_menampilkan_kalimat_kosong",
      L + "test_laporan_tampil_lagi_setelah_tautan_diganti_atau_terbit_baru")),
    ("F9-atur-tanpa-cek-tirai",
     ((HTTP, "    return not pin_store.ada_pin(kon, ctx.siswa_id) or ctx.terbuka()", "    return True"),),
     (H + "test_ganti_pin_saat_tertutup_ditolak_tanpa_efek_saat_terbuka_berhasil",)),
    ("F10-tirai-tidak-kedaluwarsa",
     ((TIRAI, "        if habis <= kini:", "        if False:"),),
     (U + "test_kedaluwarsa_tepat_pada_batas_umur", H + "test_tirai_kedaluwarsa_tiga_puluh_menit_dengan_waktu_disuntik")),
    ("F11-hapus-tanpa-konfirmasi",
     ((HTTP, '    if data.get("konfirmasi") != "1":', "    if False:"),),
     (H + "test_hapus_pin_butuh_tirai_terbuka_dan_konfirmasi",)),
    ("F12-cek-akun-lain-dipakai",
     ((DATA, "cek_gratis.hasil_siswa(kon, id_akun, siswa_id)", "cek_gratis.baca_hasil(kon, id_akun)"),),
     (H + "test_cek_milik_akun_lain_tidak_tampil", H + "test_cek_anak_lain_di_akun_yang_sama_tidak_dipakai")),
    ("F13-pesanan-akun-lain-dipakai",
     ((DATA, '"SELECT order_id FROM pesanan_order WHERE akun_id = ? AND siswa_id = ?", (id_akun, siswa_id)',
       '"SELECT order_id FROM pesanan_order WHERE siswa_id = ? AND ? IS NOT NULL", (siswa_id, id_akun)'),
      (DATA, 'return pesanan_status.status_order(kon, baris["order_id"], id_akun, kini)["status"]',
       'return pesanan_status.status_dari_db(kon, pesanan_status.dict_order(pesanan_status.baris_order(kon, baris["order_id"])), '
       'pesanan_dasar.waktu_baku(kini))'),),
     (H + "test_tanpa_order_atau_order_akun_lain_kartu_tidak_tampil",)),
    ("F14-asal-post-tidak-diperiksa",
     ((WEB, "        if not (publik or siklus) and not self._asal_sama_post():", "        if False:"),),
     (H + "test_csrf_lintas_situs_ditolak_tanpa_efek",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("orang-tua-mutasi") / "repo"
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
    sasaran = sorted({t.split("::")[0] for _, _, ts in KASUS for t in ts})
    hasil = _jalankan(salinan, sasaran)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_orang_tua_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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
