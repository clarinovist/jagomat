"""Mutation guard cetakan soal berpola di admin (C2) pada salinan sintetis terisolasi, tanpa jaringan.

Tiap mutasi menonaktifkan satu guard di salinan aplikasi (bukan workspace) lalu memastikan tes terkait MERAH
lewat kegagalan asersi (bukan galat import/fixture). Guard: target dari tinjauan (bukan form), himpunan field
persis untuk aksi pindah, sandi ulang, batas field eksplisit, token halaman 400 terikat revisi yang diajukan,
escape di semua permukaan (stored-XSS), dan hanya cetakan AKTIF yang dibaca tabel/Buat soal.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
HTTP = 'admin_kurikulum_cetakan_http.py'
PAGES = 'admin_kurikulum_cetakan_pages.py'
ADMIN = 'admin_http.py'
HITUNG = 'kurikulum_kelas_hitung.py'
BUAT = 'kurikulum_buat_soal.py'
TABEL_PAGES = 'admin_kurikulum_merdeka_pages.py'
BUAT_PAGES = 'admin_kurikulum_buat_pages.py'
TES_ADMIN = 'test_admin_kurikulum_cetakan.py'
TES_TAMPIL = 'test_admin_kurikulum_cetakan_tampil.py'
TES_SEMUA = (TES_ADMIN, TES_TAMPIL)
TANDA_MERAH = ('AssertionError', 'assert ')
MUTASI = (
    # Tiga lapis melindungi buat/ubah (batas field, himpunan field persis, indeks ketat `ke_isi`); id/kelas/bab dari
    # form hanya bisa lolos bila batas dinaikkan DAN himpunan field dilonggarkan, jadi keduanya dimatikan bersama.
    ('ubah-id-dari-form', HTTP,
     "    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_UBAH, maksimum_field=MAKS_FIELD_CETAKAN)\n"
     "    aksi.wajib_field(data, ui.FIELD_UBAH)\n    id_cetakan, revisi = _id_dari_tinjauan(tinjauan)\n",
     "    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_UBAH, maksimum_field=MAKS_FIELD_CETAKAN + 5)\n"
     "    id_cetakan, revisi = _id_dari_tinjauan(tinjauan)\n    id_cetakan = int(data.pop('id', id_cetakan))\n",
     TES_ADMIN, 'test_field_asing_ditolak_400_dan_id_kelas_bab_di_form_diabaikan'),
    ('buat-kelas-bab-dari-form', HTTP,
     "    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_BUAT, maksimum_field=MAKS_FIELD_CETAKAN)\n"
     "    aksi.wajib_field(data, ui.FIELD_BUAT)\n    kelas, bab = _bab_dari_tinjauan(tinjauan)\n",
     "    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_BUAT, maksimum_field=MAKS_FIELD_CETAKAN + 5)\n"
     "    kelas, bab = _bab_dari_tinjauan(tinjauan)\n    kelas, bab = _bab_dari_query({'kelas': data.pop('kelas', "
     "str(kelas)), 'bab': data.pop('bab', str(bab.nomor))})\n",
     TES_ADMIN, 'test_field_asing_ditolak_400_dan_id_kelas_bab_di_form_diabaikan'),
    # Sendirian (batas field tetap) dimatikan pun terbunuh, tetapi secara tak langsung: field kurang menjadi KeyError,
    # yang `jalankan_aman` petakan ke 404 (LookupError dahulu) alih-alih 400.
    ('buat-tanpa-wajib-field', HTTP, "    aksi.wajib_field(data, ui.FIELD_BUAT)\n", "",
     TES_ADMIN, 'test_field_kurang_ditolak_400'),
    ('ubah-tanpa-wajib-field', HTTP, "    aksi.wajib_field(data, ui.FIELD_UBAH)\n", "",
     TES_ADMIN, 'test_field_kurang_ditolak_400'),
    ('pindah-tanpa-wajib-field', HTTP,
     "    aksi.wajib_field(data, frozenset())\n", "",
     TES_ADMIN, 'test_field_asing_ditolak_400_dan_id_kelas_bab_di_form_diabaikan'),
    ('sandi-ulang-dihapus', ADMIN,
     '    if not _reauth(principal, data.pop("reauth", "")):\n',
     '    if False and not _reauth(principal, data.pop("reauth", "")):\n',
     TES_ADMIN, 'test_token_cacat_403_tanpa_mengubah_store'),
    ('batas-field-dinaikkan', HTTP,
     "MAKS_FIELD_CETAKAN = len(form.FIELD_ISI) + 3", "MAKS_FIELD_CETAKAN = len(form.FIELD_ISI) + 300",
     TES_ADMIN, 'test_batas_field_cetakan_eksplisit_26_field_ditolak_sebelum_token_diperiksa'),
    ('token-400-revisi-baca-ulang', HTTP,
     "_tampilkan_periksa(penangan, principal, item, revisi, str(galat), data)",
     "_tampilkan_periksa(penangan, principal, item, item.revisi, str(galat), data)",
     TES_ADMIN, 'test_token_halaman_400_ubah_terikat_revisi_yang_diajukan_bukan_baca_ulang'),
    ('escape-teks-soal-dihapus', PAGES,
     "% (e(soal.teks), e(_tampil_angka(soal.kunci)), pembahasan))",
     "% (soal.teks, e(_tampil_angka(soal.kunci)), pembahasan))",
     TES_TAMPIL, 'test_karakter_html_di_isi_cetakan_ter_escape_di_semua_permukaan'),
    ('escape-pembahasan-soal-dihapus', PAGES,
     "('<p class=\"admin-meta\">Pembahasan: %s</p>' % e(soal.pembahasan))",
     "('<p class=\"admin-meta\">Pembahasan: %s</p>' % soal.pembahasan)",
     TES_TAMPIL, 'test_karakter_html_di_isi_cetakan_ter_escape_di_semua_permukaan'),
    ('escape-judul-daftar-dihapus', PAGES,
     "% (e(url_periksa(item.id)), e(item.cetakan.judul), e(LABEL_STATUS[item.status]),",
     "% (e(url_periksa(item.id)), item.cetakan.judul, e(LABEL_STATUS[item.status]),",
     TES_TAMPIL, 'test_karakter_html_di_isi_cetakan_ter_escape_di_semua_permukaan'),
    ('escape-galat-dihapus', PAGES,
     "role=\"alert\">%s</p>' % e(galat)", "role=\"alert\">%s</p>' % galat",
     TES_TAMPIL, 'test_renderer_langsung_meng_escape_item_yang_berisi_markup'),
    ('escape-nilai-form-dihapus', PAGES,
     "e(label), nama, e(nilai[nama]), _atribut_placeholder(nama)", "e(label), nama, nilai[nama], _atribut_placeholder(nama)",
     TES_TAMPIL, 'test_markup_di_isian_ditolak_validasi_dan_ter_escape_saat_dipantulkan'),
    ('escape-judul-tabel-dihapus', TABEL_PAGES,
     'baris += ["Cetakan: %s" % e(c.cetakan.judul) for c in b.cetakan]',
     'baris += ["Cetakan: %s" % c.cetakan.judul for c in b.cetakan]',
     TES_TAMPIL, 'test_karakter_html_di_isi_cetakan_ter_escape_di_semua_permukaan'),
    ('escape-judul-buat-soal-dihapus', BUAT_PAGES,
     'item.nomor, e("Cetakan: %s" % item.judul), baris_soal(item.soal))',
     'item.nomor, "Cetakan: %s" % item.judul, baris_soal(item.soal))',
     TES_TAMPIL, 'test_karakter_html_di_isi_cetakan_ter_escape_di_semua_permukaan'),
    ('tabel-baca-semua-status', HITUNG,
     "cetakan_store.aktif_untuk_bab(kelas, bab.nomor)", "cetakan_store.daftar(kelas=kelas, bab=bab.nomor)",
     TES_TAMPIL, 'test_draf_dan_nonaktif_tidak_pernah_tampil_di_tabel_dan_buat_soal'),
    ('buat-soal-baca-semua-status', BUAT,
     "cetakan_store.aktif_untuk_bab(kelas, bab.nomor)", "cetakan_store.daftar(kelas=kelas, bab=bab.nomor)",
     TES_TAMPIL, 'test_draf_dan_nonaktif_tidak_pernah_tampil_di_tabel_dan_buat_soal'),
    ('status-sebagian-dihapus', HITUNG,
     "return STATUS_SEBAGIAN if status == STATUS_BELUM and cetakan else status", "return status",
     TES_TAMPIL, 'test_cetakan_aktif_menjadikan_bab_belum_menjadi_sebagian_dengan_jenis_variasi_dan_tautan'),
    ('variasi-cetakan-bukan-banyak', HITUNG,
     "return replace(variasi, ada_banyak=True) if cetakan else variasi", "return variasi",
     TES_TAMPIL, 'test_cetakan_aktif_menjadikan_bab_belum_menjadi_sebagian_dengan_jenis_variasi_dan_tautan'),
    ('buat-soal-lewati-seed-gagal-dihapus', BUAT,
     "        except ValueError:  # termasuk KunciNegatif dan \"syarat terlalu ketat\"\n            gagal += 1\n            continue\n",
     "        except ZeroDivisionError:\n            gagal += 1\n            continue\n",
     TES_TAMPIL, 'test_buat_soal_melewati_seed_gagal_tanpa_500'),
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
def test_mutation_cetakan_admin(tmp_path, name, berkas, old, new, tes, kunci):
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
