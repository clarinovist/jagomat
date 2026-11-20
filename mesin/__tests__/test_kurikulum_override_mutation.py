"""Mutation guard store override kurikulum pada salinan sintetis terisolasi, tanpa jaringan.

Tiap mutasi menonaktifkan satu guard di salinan modul (bukan workspace) dan memastikan
tes terkait MERAH lewat kegagalan asersi (bukan galat import/fixture).
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
BERKAS = 'kurikulum_override.py'
MUTASI = (
    ('validasi-baca-baris', "    return _normalkan_isi_cp(isi)\n\n\ndef _normalkan_format_label",
     "    return tuple(tuple(p) for p in isi)\n\n\ndef _normalkan_format_label",
     'test_baca_baris_rusak_memakai_bawaan_sedang_baris_lain_tetap_override'),
    ('validasi-baca-label', "            valid[topik_id] = _normalkan_format_label(label)",
     "            valid[topik_id] = label",
     'test_baca_baris_rusak_memakai_bawaan_sedang_baris_lain_tetap_override'),
    ('cek-revisi', "    if revisi_kini != revisi_diharapkan:", "    if False:",
     'test_konflik_revisi_digulung_balik_tanpa_audit_atau_perubahan'),
    ('aba-revisi-tidak-naik', "revisi_baru, kini = revisi_kini + 1, _utc_iso()\n        tersimpan = None if target == sekarang.bawaan else _cp_ke_json(target)",
     "revisi_baru, kini = max(revisi_kini, 1), _utc_iso()\n        tersimpan = None if target == sekarang.bawaan else _cp_ke_json(target)",
     'test_kembalikan_cp_ke_bawaan_revisi_naik_dan_aba_tertutup'),
    ('unik-label', "        if lain != topik_id and _kunci_unik(nilai) == unik:", "        if False:",
     'test_validasi_tolak_label_duplikat_casefold_terhadap_bawaan_topik_lain'),
    ('skema-asing-tulis', "    if versi not in (0, VERSI_SKEMA):", "    if False:",
     'test_tulis_ke_user_version_asing_galat_dan_berkas_tak_berubah'),
    ('batas-pasangan', "    if len(isi) > MAKS_PASANGAN_CP:", "    if False:",
     'test_validasi_tolak_isi_cp_tak_sah'),
)


@pytest.mark.parametrize('name,old,new,test', MUTASI, ids=[x[0] for x in MUTASI])
def test_mutation_kurikulum_override(tmp_path, name, old, new, test):
    mesin = tmp_path / 'mesin'
    mesin.mkdir()
    for p in (ROOT / 'mesin').glob('*.py'):
        shutil.copy2(p, mesin / p.name)
    tests = mesin / '__tests__'
    tests.mkdir()
    for n in ('conftest.py', 'test_kurikulum_override.py'):
        shutil.copy2(ROOT / 'mesin/__tests__' / n, tests / n)
    source = (ROOT / 'mesin' / BERKAS).read_text()
    assert source.count(old) == 1
    (mesin / BERKAS).write_text(source.replace(old, new))
    r = subprocess.run([sys.executable, '-B', '-m', 'pytest', str(tests / 'test_kurikulum_override.py'),
                        '-k', test, '-q', '-W', 'error', '-p', 'no:cacheprovider'],
                       cwd=tmp_path, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1, r.stdout + r.stderr
    assert 'DID NOT RAISE' in r.stdout or 'AssertionError' in r.stdout, r.stdout + r.stderr
    assert 'ERROR collecting' not in r.stdout
