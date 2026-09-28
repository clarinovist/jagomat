"""Mutation guard registrasi memakai source dan DB sintetis terisolasi."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR=Path(__file__).resolve().parents[2]
KASUS=(
 ('binding',"nama_anak, kelas_sekolah, profil_parameter))",
  "'profil-tidak-diikat',))",'test_binding_replay_berbeda_ditolak_tanpa_efek','DID NOT RAISE'),
 ('provenance',"if lama['status'] != 'pending' or alias_pemilik_ada(kon, alias):",
  'if False:','test_pending_tidak_mewarisi_profil_nama_lain_dengan_alias_sama','AssertionError'),
 ('final_owner',"if _sidik_profil_registrasi(kon, siswa_id, token_form) != lama['profil_sidik']:",
  'if False:','test_publish_recheck_menolak_owner_berubah_setelah_db','DID NOT RAISE'),
 ('publish_alias',"if kon.execute('SELECT 1 FROM siswa WHERE lower(pemilik)=lower(?) AND id!=? LIMIT 1',",
  "if False and kon.execute('SELECT 1 FROM siswa WHERE lower(pemilik)=lower(?) AND id!=? LIMIT 1',",
  'test_publish_tidak_mewarisi_tambahan_profil_asing','DID NOT RAISE'),
 ('pending_alias',"if any(r['alias_sidik'] == alias_sidik for r in intent.values()):",
  'if False:','test_pending_alias_id_lain_tidak_mengambil_operasi','DID NOT RAISE'),
)


@pytest.mark.parametrize('nama,lama,baru,tes,pesan',KASUS,ids=[k[0] for k in KASUS])
def test_guard_registrasi_merah_pulih(tmp_path,nama,lama,baru,tes,pesan):
    source=tmp_path/'mesin';source.mkdir()
    for f in (AKAR/'mesin').glob('*.py'):shutil.copy2(f,source/f.name)
    tesfile=tmp_path/'test_registration_profile.py';shutil.copy2(Path(__file__).with_name(tesfile.name),tesfile)
    target=source/'admin_registration.py';asli=target.read_text()
    assert asli.count(lama)==(2 if nama=='final_owner' else 1)
    target.write_text(asli.replace(lama,baru))
    argv=[sys.executable,'-B','-m','pytest',str(tesfile),'-k',tes,'-q','-W','error','-p','no:cacheprovider']
    env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(source),'PYTHONDONTWRITEBYTECODE':'1','OSN_PBKDF2_ITERASI':'1000'}
    def run():return subprocess.run(argv,env=env,cwd=tmp_path,capture_output=True,text=True,timeout=30)
    merah=run();assert merah.returncode==1 and pesan in merah.stdout,merah.stdout+merah.stderr
    assert 'ImportError' not in merah.stdout
    target.write_text(asli)
    hijau=run();assert hijau.returncode==0,hijau.stdout+hijau.stderr
