"""Mutation guard edit label awam (3d) pada salinan sintetis terisolasi, tanpa jaringan.

Tiap mutasi menonaktifkan satu guard di salinan aplikasi (bukan workspace) lalu memastikan tes terkait
MERAH lewat kegagalan asersi (bukan galat import/fixture). Guard: isian form persis (`wajib_field`) dan
target dari tinjauan, konflik revisi di jalur HTTP, pembaca label saat request (`topik_awam.nama`, layar
anak, `dari_nama_lama`), dan penolakan label yang sama dengan nama resmi topik.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
HTTP = 'admin_kurikulum_label_http.py'
AWAM = 'topik_awam.py'
ANAK = 'cek_anak_komponen.py'
TES_HTTP = 'test_admin_kurikulum_label.py'
TES_AWAM = 'test_topik_awam_override.py'
MUTASI = (
    ('target-dari-form', HTTP,
     "    aksi.wajib_field(data, ui.FIELD_UBAH)\n    topik_id, revisi = _perintah(tinjauan)\n",
     "    topik_id, revisi = _perintah(tinjauan)\n    topik_id = data.get('topik_id', topik_id)\n",
     TES_HTTP, 'test_tinjauan_topik_x_dengan_field_topik_y_tidak_mengubah_keduanya'),
    ('tanpa-wajib-field-ubah', HTTP,
     "    aksi.wajib_field(data, ui.FIELD_UBAH)\n", "",
     TES_HTTP, 'test_target_dan_revisi_tak_bisa_diganti_lewat_field_form'),
    ('tanpa-wajib-field-kembalikan', HTTP,
     "    aksi.wajib_field(data, frozenset())\n", "",
     TES_HTTP, 'test_kembalikan_dengan_field_asing_atau_revisi_basi_ditolak'),
    ('bypass-konflik-revisi-http', HTTP,
     "actor_id=_actor(principal), revisi_diharapkan=revisi)\n    _selesai(penangan, topik_id, HASIL_TERSIMPAN)",
     "actor_id=_actor(principal),\n                  revisi_diharapkan=next(i.revisi for i in override.daftar_label() "
     "if i.topik_id == topik_id))\n    _selesai(penangan, topik_id, HASIL_TERSIMPAN)",
     TES_HTTP, 'test_dua_tinjauan_revisi_sama_yang_kedua_409_dan_store_memuat_hasil_pertama'),
    ('nama-abaikan-override', AWAM,
     "    return kurikulum_override.label_efektif().get(topik_id, bawaan)", "    return bawaan",
     TES_AWAM, 'test_nama_mengikuti_override_langsung_dan_kembali_saat_dikembalikan'),
    ('layar-anak-konstanta', ANAK,
     "    return topik_awam.nama(topik_id)", "    return topik_awam.NAMA_AWAM[topik_id]",
     TES_AWAM, 'test_layar_anak_memakai_label_baru_tanpa_restart_proses'),
    ('dari-nama-lama-konstanta', AWAM,
     "return label if topik_id is None else nama(topik_id)",
     "return label if topik_id is None else NAMA_AWAM[topik_id]",
     TES_AWAM, 'test_dari_nama_lama_nama_resmi_menjadi_label_efektif'),
    ('tanpa-tolak-nama-resmi', AWAM,
     "    return label in _peta_nama_resmi()", "    return False",
     TES_HTTP, 'nama_resmi'),
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
    for nama in (TES_HTTP, TES_AWAM):
        shutil.copy2(ROOT / 'mesin/__tests__' / nama, tests / nama)
    return mesin


@pytest.mark.parametrize('name,berkas,old,new,tes,kunci', MUTASI, ids=[x[0] for x in MUTASI])
def test_mutation_label_awam(tmp_path, name, berkas, old, new, tes, kunci):
    mesin = _salin_aplikasi(tmp_path)
    sumber = (ROOT / 'mesin' / berkas).read_text()
    assert sumber.count(old) == 1
    (mesin / berkas).write_text(sumber.replace(old, new))
    r = subprocess.run([sys.executable, '-B', '-m', 'pytest', str(mesin / '__tests__' / tes),
                        '-k', kunci, '-q', '-W', 'error', '-p', 'no:cacheprovider'],
                       cwd=tmp_path, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 1, r.stdout + r.stderr
    assert 'AssertionError' in r.stdout, r.stdout + r.stderr
    assert 'ERROR collecting' not in r.stdout and ' error' not in r.stdout.splitlines()[-1], r.stdout
    assert 'failed' in r.stdout.splitlines()[-1]
