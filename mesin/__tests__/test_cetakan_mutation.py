"""Mutation guard mesin dan store cetakan pada salinan sintetis terisolasi, tanpa jaringan.

Tiap mutasi menonaktifkan satu guard di salinan modul (bukan workspace) dan memastikan tes
terkait MERAH lewat kegagalan asersi atau galat perilaku (bukan galat import/fixture).
Kelompok: keamanan evaluator, kebenaran kunci, kelayakan saat setujui, konkurensi/revisi, skema.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
TES_POLA = 'test_cetakan_pola.py'
TES_STORE = 'test_cetakan_store.py'
# (nama, berkas modul, tes yang memuat, teks lama, teks baru, nama tes yang harus merah)
MUTASI = (
    # (a) evaluator: daftar putih
    ('whitelist-aritmetika-call-attribute', 'cetakan_pola.py', TES_POLA,
     '    else:\n        raise _galat(bidang, f"unsur {type(node).__name__} tidak diizinkan di rumus aritmetika.")',
     '    elif False:\n        raise _galat(bidang, "")',
     'test_serangan_ditolak_sebagai_kunci'),
    ('whitelist-boolean', 'cetakan_pola.py', TES_POLA,
     '    else:\n        raise _galat(bidang, "syarat harus berupa perbandingan (boleh digabung and/or).")',
     '    elif False:\n        raise _galat(bidang, "")',
     'test_syarat_harus_boolean_bertipe'),
    ('konstanta-bool-float', 'cetakan_pola.py', TES_POLA,
     '        if type(nilai) is not int or not 0 <= nilai <= BATAS_KONSTANTA:',
     '        if not 0 <= nilai <= BATAS_KONSTANTA:',
     'test_serangan_ditolak_sebagai_kunci'),
    ('operator-binop', 'cetakan_pola.py', TES_POLA,
     '        if not isinstance(node.op, _OP_ARITMETIKA):',
     '        if False:',
     'test_serangan_ditolak_sebagai_kunci'),
    ('batas-panjang-ekspresi', 'cetakan_pola.py', TES_POLA,
     '    if len(teks) > MAKS_EKSPRESI:', '    if False:',
     'test_batas_panjang_ekspresi_120_sah_121_ditolak'),
    ('batas-node', 'cetakan_pola.py', TES_POLA,
     '    if sum(isinstance(node, ast.expr) for node in ast.walk(pohon)) > MAKS_NODE:', '    if False:',
     'test_batas_jumlah_node_40_sah_41_ditolak'),
    ('placeholder-kurung-sisa', 'cetakan_pola.py', TES_POLA,
     '    if "{" in _PLACEHOLDER.sub("", teks) or "}" in _PLACEHOLDER.sub("", teks):', '    if False:',
     'test_placeholder_tak_terdaftar_atau_rusak_ditolak'),
    ('variabel-harus-tampil', 'cetakan_pola.py', TES_POLA,
     '    if tak_tampil:', '    if False:',
     'test_variabel_harus_muncul_di_teks'),
    # (b) kebenaran kunci
    ('floordiv-tanpa-cek-habis', 'cetakan_pola.py', TES_POLA,
     '        if kiri % kanan != 0:', '        if False:',
     'test_pembagian_selalu_habis_dan_kunci_bulat_tepat'),
    ('pembagi-nol', 'cetakan_pola.py', TES_POLA,
     '    if kanan == 0:', '    if False:',
     'test_pembagi_nol_tak_pernah_menjadi_soal'),
    ('operan-negatif-bagi-sisa', 'cetakan_pola.py', TES_POLA,
     '    if kiri < 0 or kanan < 0:', '    if False:',
     'test_operan_negatif_pada_bagi_dan_sisa_diundi_ulang'),
    ('batas-nilai-antara', 'cetakan_pola.py', TES_POLA,
     '    if abs(nilai) > BATAS_ANTARA:', '    if False:',
     'test_nilai_antara_di_atas_10_pangkat_12_ditolak'),
    ('kunci-negatif', 'cetakan_pola.py', TES_POLA,
     '    if kunci < 0:', '    if False:',
     'test_kunci_negatif_ditandai_bukan_dibulatkan'),
    ('ambang-unik', 'cetakan_pola.py', TES_POLA,
     '    if unik < MIN_UNIK:', '    if False:',
     'test_uji_kelayakan_domain_kecil_gagal_walau_nama_menggandakan_teks'),
    ('syarat-diabaikan', 'cetakan_pola.py', TES_POLA,
     '            if not _hitung(_ekspresi_tervalidasi(syarat, nama_var, "syarat"), parameter):\n                return None',
     '            if False:\n                return None',
     'test_syarat_berantai_dan_boolop_dipatuhi'),
    # (c) setujui tanpa uji kelayakan
    ('setujui-tanpa-kelayakan', 'cetakan_store.py', TES_STORE,
     '        if wajib_layak:', '        if False:',
     'test_setujui_gagal_bila_kelayakan_gagal_tanpa_efek'),
    ('aktifkan-kembali-tanpa-kelayakan', 'cetakan_store.py', TES_STORE,
     '"diaktifkan kembali", actor_id=actor_id,\n                          revisi_diharapkan=revisi_diharapkan, path=path, wajib_layak=True)',
     '"diaktifkan kembali", actor_id=actor_id,\n                          revisi_diharapkan=revisi_diharapkan, path=path, wajib_layak=False)',
     'test_aktifkan_kembali_juga_menguji_kelayakan'),
    # (d) revisi dan transisi
    ('cek-revisi', 'cetakan_store.py', TES_STORE,
     '    if revisi_kini != revisi_diharapkan:', '    if False:',
     'test_klien_basi_tidak_bisa_menimpa_setelah_perubahan_lain'),
    ('ubah-hanya-draf', 'cetakan_store.py', TES_STORE,
     '        if baris["status"] != STATUS_DRAF:', '        if False:',
     'test_transisi_terlarang_ditolak_tanpa_efek'),
    ('status-asal-transisi', 'cetakan_store.py', TES_STORE,
     '        if baris["status"] != dari:', '        if False:',
     'test_transisi_terlarang_ditolak_tanpa_efek'),
    # skema dan baca
    ('skema-asing-tulis', 'cetakan_store.py', TES_STORE,
     '    if versi not in (0, VERSI_SKEMA):', '    if False:',
     'test_tulis_ke_user_version_asing_galat_dan_berkas_tak_berubah'),
    ('transisi-tidak-membuat-berkas', 'cetakan_store.py', TES_STORE,
     '            if not boleh_membuat:', '            if False:',
     'test_transisi_pada_berkas_tak_ada_ditolak_tanpa_membuat_berkas'),
    ('kolom-kelas-bab-cocok', 'cetakan_store.py', TES_STORE,
     '        if baris["kelas"] != cetakan.kelas or baris["bab"] != cetakan.bab:', '        if False:',
     'test_baris_rusak_dilewati_baris_lain_tetap'),
    ('status-asing-dibaca', 'cetakan_store.py', TES_STORE,
     '        if (type(id_cetakan) is not int or baris["status"] not in STATUS_SAH', '        if (False and baris["status"] not in STATUS_SAH',
     'test_baris_rusak_dilewati_baris_lain_tetap'),
)
TANDA_MERAH = ('DID NOT RAISE', 'AssertionError', 'ZeroDivisionError', 'TypeError')


@pytest.mark.parametrize('name,berkas,tes_file,old,new,test', MUTASI, ids=[x[0] for x in MUTASI])
def test_mutation_cetakan(tmp_path, name, berkas, tes_file, old, new, test):
    mesin = tmp_path / 'mesin'
    mesin.mkdir()
    for p in (ROOT / 'mesin').glob('*.py'):
        shutil.copy2(p, mesin / p.name)
    tests = mesin / '__tests__'
    tests.mkdir()
    for n in ('conftest.py', tes_file):
        shutil.copy2(ROOT / 'mesin/__tests__' / n, tests / n)
    source = (ROOT / 'mesin' / berkas).read_text()
    assert source.count(old) == 1
    (mesin / berkas).write_text(source.replace(old, new))
    r = subprocess.run([sys.executable, '-B', '-m', 'pytest', str(tests / tes_file),
                        '-k', test, '-q', '-W', 'error', '-p', 'no:cacheprovider'],
                       cwd=tmp_path, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 1, r.stdout + r.stderr
    assert any(tanda in r.stdout for tanda in TANDA_MERAH), r.stdout + r.stderr
    assert 'ERROR collecting' not in r.stdout
