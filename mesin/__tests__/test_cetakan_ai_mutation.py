"""Mutation guard draf AI cetakan (C3) pada salinan sintetis terisolasi, tanpa jaringan.

Tiap mutasi menonaktifkan satu guard di salinan aplikasi (bukan workspace) lalu memastikan tes terkait MERAH
lewat kegagalan asersi (bukan galat import/fixture). Guard: cek kuota (`>=`, cek dihapus, batas hari WIB,
atomik lewat `BEGIN IMMEDIATE`, slot terpakai walau gagal), fail-closed DB kuota, cek kunci API, batas ukuran
balasan, batas timeout, bentuk balasan, pemotongan tiga kandidat, kelas/bab dipaksa dari tinjauan, uji kelayakan,
sumber "ai", himpunan field + batas field, sandi ulang, gerbang tombol (kunci, kuota, fail-closed), kecocokan
ringkasan dengan bab, dan escape alasan penolakan.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
STORE = 'cetakan_ai_store.py'
KLIEN = 'cetakan_ai.py'
HTTP_AI = 'admin_kurikulum_cetakan_ai_http.py'
PAGES_AI = 'admin_kurikulum_cetakan_ai_pages.py'
HTTP = 'admin_kurikulum_cetakan_http.py'
MERDEKA_HTTP = 'admin_kurikulum_merdeka_http.py'
ADMIN = 'admin_http.py'
TES_STORE = 'test_cetakan_ai_store.py'
TES_KLIEN = 'test_cetakan_ai.py'
TES_HTTP = 'test_admin_kurikulum_cetakan_ai.py'
TES_SEMUA = (TES_STORE, TES_KLIEN, TES_HTTP)
# Kegagalan perilaku (asersi, `pytest.raises` yang tak terpicu, galat tak tertangkap), bukan galat import/fixture
# (yang ditolak lewat 'ERROR collecting' dan baris ringkasan akhir).
TANDA_MERAH = ('AssertionError', 'assert ', 'DID NOT RAISE', 'TypeError')
# (nama, berkas modul, teks lama, teks baru, berkas tes, kunci -k tes yang harus merah)
MUTASI = (
    # kuota
    ('kuota-lebih-besar-sama-jadi-lebih-besar', STORE, "if _terpakai(kon, hari) >= BATAS_HARIAN:",
     "if _terpakai(kon, hari) > BATAS_HARIAN:", TES_STORE, 'test_batas_harian_dua_puluh_dan_reservasi_ke_21_kuota_habis'),
    ('kuota-cek-dihapus', STORE, "if _terpakai(kon, hari) >= BATAS_HARIAN:", "if False:",
     TES_STORE, 'test_batas_harian_dua_puluh_dan_reservasi_ke_21_kuota_habis'),
    ('kuota-hari-utc-bukan-wib', STORE, "return _waktu(sekarang).astimezone(WIB).date().isoformat()",
     "return _waktu(sekarang).astimezone(timezone.utc).date().isoformat()", TES_STORE,
     'test_batas_hari_memakai_wib_bukan_utc or test_pukul_2330_utc_sudah_hari_wib_berikutnya'),
    ('kuota-hitung-tanpa-gagal', STORE, '"SELECT COUNT(*) FROM permintaan WHERE hari_wib = ?", (hari,)',
     '"SELECT COUNT(*) FROM permintaan WHERE hari_wib = ? AND status != \'gagal\'", (hari,)', TES_HTTP,
     'test_slot_terpakai_walau_ai_gagal_dan_kuota_habis_oleh_kegagalan'),
    ('kuota-tanpa-transaksi-immediate', STORE, '            kon.execute("BEGIN IMMEDIATE")\n', "",
     TES_STORE, 'test_reservasi_serentak_atomik_tepat_dua_puluh_lolos'),
    ('kuota-sisa-bukan-fail-closed', STORE, "    except GalatKuota:\n        return None\n    return BATAS_HARIAN - min(",
     "    except GalatKuota:\n        return BATAS_HARIAN\n    return BATAS_HARIAN - min(", TES_STORE,
     'test_db_rusak_atau_asing_fail_closed_dan_berkas_tak_berubah'),
    ('kuota-skema-asing-tak-dicek-sebelum-wal', STORE, "        _periksa_skema_baca(tujuan)\n        with closing(sqlite3.connect(str(tujuan)",
     "        with closing(sqlite3.connect(str(tujuan)", TES_STORE,
     'test_db_rusak_atau_asing_fail_closed_dan_berkas_tak_berubah'),
    # klien
    ('klien-batas-ukuran-dihapus', KLIEN, "    if len(mentah) > BATAS_RESPONS_BYTE:\n",
     "    if False:\n", TES_KLIEN, 'test_balasan_8192_byte_diterima_dan_8193_ditolak'),
    ('klien-batas-ukuran-lebih-besar-sama', KLIEN, "    if len(mentah) > BATAS_RESPONS_BYTE:\n",
     "    if len(mentah) >= BATAS_RESPONS_BYTE:\n", TES_KLIEN, 'test_balasan_8192_byte_diterima_dan_8193_ditolak'),
    ('klien-baca-tanpa-batas', KLIEN, "resp.read(BATAS_RESPONS_BYTE + 1)", "resp.read()",
     TES_KLIEN, 'test_pembacaan_dibatasi_8193_byte_walau_balasan_sangat_besar'),
    ('klien-timeout-dilonggarkan', KLIEN, "BATAS_WAKTU_DETIK = 30", "BATAS_WAKTU_DETIK = 300",
     TES_KLIEN, 'test_permintaan_post_ke_chat_completions_dengan_header_badan_dan_timeout'),
    ('klien-tanpa-cek-kunci', KLIEN, '    if not konf["api_key"]:\n        raise GalatAI(COPY_TANPA_KUNCI)\n', "",
     TES_KLIEN, 'test_tanpa_kunci_galat_tanpa_memanggil_jaringan'),
    ('klien-response-format-dihapus', KLIEN, '        "response_format": {"type": "json_object"},\n', "",
     TES_KLIEN, 'test_permintaan_post_ke_chat_completions_dengan_header_badan_dan_timeout'),
    ('klien-lebih-dari-tiga-tak-dipotong', KLIEN, "return tuple(daftar[:MAKS_KANDIDAT])", "return tuple(daftar)",
     TES_KLIEN, 'test_lebih_dari_tiga_kandidat_diambil_tiga_pertama'),
    ('klien-content-bukan-teks-lolos', KLIEN, "    if not isinstance(isi, str):\n        raise GalatAI(COPY_BUKAN_JSON)\n", "",
     TES_KLIEN, 'test_balasan_rusak_menjadi_galat_ai_bukan_galat_lain'),
    ('klien-alamat-tak-dicek', KLIEN, "    if not konf[\"base_url\"].startswith(SKEMA_URL_SAH):\n        raise GalatAI(COPY_ALAMAT)\n", "",
     TES_KLIEN, 'test_alamat_bukan_http_ditolak_tanpa_memanggil_jaringan'),
    ('klien-sub-materi-tak-dikirim', KLIEN, '    sub = "\\n".join("- %s" % materi for materi in bab.sub_materi)\n',
     '    sub = ""\n', TES_KLIEN, 'test_muatan_dua_pesan_dengan_struktur_dan_isi_yang_diharapkan'),
    # alur HTTP
    ('http-kelas-bab-dari-ai', HTTP_AI, '    isi = {**mentah, "kelas": kelas, "bab": bab.nomor}\n',
     '    isi = {"kelas": kelas, "bab": bab.nomor, **mentah}\n', TES_HTTP,
     'test_kelas_dan_bab_dipaksa_dari_tinjauan_bukan_dari_ai'),
    ('http-uji-kelayakan-dilewati', HTTP_AI, "    if not hasil.lolos:\n", "    if False:\n",
     TES_HTTP, 'test_kandidat_tak_layak_ditolak_dengan_alasan_kelayakan'),
    ('http-sumber-bukan-ai', HTTP_AI, 'SUMBER_AI = "ai"', 'SUMBER_AI = "manual"',
     TES_HTTP, 'test_alur_lengkap_lewat_form_halaman_prg_ringkasan_dan_draf_ai'),
    ('http-tanpa-cek-kunci', HTTP_AI, "    if not cetakan_ai.aktif():\n", "    if False:\n",
     TES_HTTP, 'test_tanpa_kunci_post_ditolak_503_tanpa_urlopen_reservasi_dan_cetakan'),
    ('http-kuota-habis-diteruskan', HTTP_AI, "    except kuota.KuotaHabis:\n        h._galat(penangan, 429, ui_ai.COPY_KUOTA_HABIS_POST)\n",
     "    except kuota.KuotaHabis:\n        return 0\n", TES_HTTP,
     'test_kuota_dua_puluh_permintaan_lolos_dan_ke_21_ditolak_429_tanpa_urlopen'),
    ('http-db-kuota-rusak-diteruskan', HTTP_AI, "    except kuota.GalatKuota:\n        h._galat(penangan, 503, ui_ai.COPY_KUOTA_TIDAK_SIAP)\n",
     "    except kuota.GalatKuota:\n        return 0\n", TES_HTTP,
     'test_db_kuota_rusak_fail_closed_tombol_hilang_post_503_tanpa_urlopen'),
    # field + batas field (masing-masing berlapis; dimatikan bersama agar terbukti ada yang menjaga)
    ('http-field-asing-batas-dan-wajib-field-dilonggarkan', HTTP_AI,
     "    tinjauan, data = aksi.terima_form(penangan, principal, ui_ai.AKSI_DRAF_AI, maksimum_field=MAKS_FIELD_DRAF_AI)\n"
     "    aksi.wajib_field(data, frozenset())\n",
     "    tinjauan, data = aksi.terima_form(penangan, principal, ui_ai.AKSI_DRAF_AI, maksimum_field=MAKS_FIELD_DRAF_AI + 50)\n",
     TES_HTTP, 'test_field_asing_ditolak_400_dan_target_di_form_diabaikan'),
    ('sandi-ulang-dihapus', ADMIN, '    if not _reauth(principal, data.pop("reauth", "")):\n',
     '    if False and not _reauth(principal, data.pop("reauth", "")):\n', TES_HTTP,
     'test_token_cacat_403_tanpa_reservasi_urlopen_atau_cetakan'),
    # gerbang tombol
    ('tombol-tanpa-cek-kunci', HTTP, "    kunci_ada = cetakan_ai.aktif()\n", "    kunci_ada = True\n",
     TES_HTTP, 'test_tanpa_kunci_tombol_tak_tampil_dan_tabel_tanpa_tautan'),
    ('tombol-kuota-nol-masih-tampil', PAGES_AI, "    if sisa <= 0:\n", "    if sisa < 0:\n",
     TES_HTTP, 'test_kuota_habis_tombol_hilang_dengan_catatan_dan_tabel_tanpa_tautan'),
    ('tombol-db-kuota-rusak-dianggap-penuh', HTTP,
     "    sisa = kuota_ai.sisa_hari_ini() if kunci_ada else None\n",
     "    sisa = (lambda s: 20 if s is None else s)(kuota_ai.sisa_hari_ini()) if kunci_ada else None\n", TES_HTTP,
     'test_db_kuota_rusak_fail_closed_tombol_hilang_post_503_tanpa_urlopen'),
    ('tabel-db-kuota-rusak-dianggap-penuh', MERDEKA_HTTP,
     "    return cetakan_ai.aktif() and (kuota_ai.sisa_hari_ini() or 0) > 0",
     "    return cetakan_ai.aktif() and (kuota_ai.sisa_hari_ini() or 20) > 0", TES_HTTP,
     'test_db_kuota_rusak_fail_closed_tombol_hilang_post_503_tanpa_urlopen'),
    ('tabel-tanpa-cek-kunci', MERDEKA_HTTP, "    return cetakan_ai.aktif() and (kuota_ai.sisa_hari_ini() or 0) > 0",
     "    return (kuota_ai.sisa_hari_ini() or 0) > 0", TES_HTTP,
     'test_tanpa_kunci_tombol_tak_tampil_dan_tabel_tanpa_tautan'),
    ('tabel-kuota-nol-masih-tertaut', MERDEKA_HTTP, "    return cetakan_ai.aktif() and (kuota_ai.sisa_hari_ini() or 0) > 0",
     "    return cetakan_ai.aktif()", TES_HTTP,
     'test_kuota_habis_tombol_hilang_dengan_catatan_dan_tabel_tanpa_tautan'),
    # ringkasan
    ('ringkasan-tak-dicocokkan-dengan-bab', HTTP,
     "    if permintaan is None or (permintaan.kelas, permintaan.bab) != (kelas, bab.nomor):\n",
     "    if permintaan is None:\n", TES_HTTP, 'test_ringkasan_hanya_tampil_bila_kelas_bab_permintaan_cocok'),
    ('ringkasan-alasan-tanpa-escape', PAGES_AI, '"".join("<li>%s</li>" % e(a) for a in alasan)',
     '"".join("<li>%s</li>" % a for a in alasan)', TES_HTTP, 'test_alasan_penolakan_dari_db_ter_escape_di_halaman'),
    ('ringkasan-alasan-gagal-tanpa-escape', PAGES_AI, "'Slot kuota tetap terpakai.</p><p class=\"admin-meta\">Alasan: %s</p></section>' % e(alasan))",
     "'Slot kuota tetap terpakai.</p><p class=\"admin-meta\">Alasan: %s</p></section>' % alasan)", TES_HTTP,
     'test_alasan_gagal_dari_db_ter_escape_di_halaman'),
)


def _salin_aplikasi(tujuan: Path) -> Path:
    mesin = tujuan / 'mesin'
    shutil.copytree(ROOT / 'mesin', mesin, ignore=shutil.ignore_patterns(
        '.venv', '__pycache__', 'cadangan', '__tests__'))
    tests = mesin / '__tests__'
    tests.mkdir()
    for p in (ROOT / 'mesin/__tests__').iterdir():
        if p.is_file() and not p.name.startswith('test_'):
            shutil.copy2(p, tests / p.name)
    for nama in TES_SEMUA:
        shutil.copy2(ROOT / 'mesin/__tests__' / nama, tests / nama)
    return mesin


@pytest.mark.parametrize('name,berkas,old,new,tes,kunci', MUTASI, ids=[x[0] for x in MUTASI])
def test_mutation_cetakan_ai(tmp_path, name, berkas, old, new, tes, kunci):
    mesin = _salin_aplikasi(tmp_path)
    sumber = (ROOT / 'mesin' / berkas).read_text()
    assert sumber.count(old) == 1
    (mesin / berkas).write_text(sumber.replace(old, new))
    r = subprocess.run([sys.executable, '-B', '-m', 'pytest', str(mesin / '__tests__' / tes),
                        '-k', kunci, '-q', '-W', 'error', '-p', 'no:cacheprovider'],
                       cwd=tmp_path, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 1, r.stdout + r.stderr
    assert any(tanda in r.stdout for tanda in TANDA_MERAH), r.stdout + r.stderr
    assert 'ERROR collecting' not in r.stdout and ' error' not in r.stdout.splitlines()[-1], r.stdout
    assert 'failed' in r.stdout.splitlines()[-1]
