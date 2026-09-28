"""Mutation guard percobaan foto memakai sourcecopy dan DB sintetis terisolasi."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR=Path(__file__).resolve().parents[2]
KASUS=(
 ('quota_admission','attachments.py',"ikatan = kuota.reservasi(akun_id, fitur='pembacaan_foto', identitas=operasi_id, sekarang=kini)",
  "ikatan = object()",'test_admission_habis_tertahan_sebelum_provider','AssertionError'),
 ('parent_mapping','attachments.py',"akun_id = parent['id_akun']","akun_id = principal.id_akun",
  'test_foto_valid_commit_sebelum_finalisasi_parent_account[child]','AssertionError'),
 ('replay','attachments.py',"replay = dict(row)","replay = None",
  'test_replay_tertahan_sebelum_reservasi_kedua','AssertionError'),
 ('commit_sebelum_final','attachments.py',"(bacaan.status, lid, kini, operasi_id))",
  "(bacaan.status, lid, kini, operasi_id))\n            if bacaan.status == 'result':\n                kuota.finalisasi(ikatan, sekarang=kini)",
  'test_foto_valid_commit_sebelum_finalisasi_parent_account[parent]','AssertionError'),
 ('reserve_commit_lookup','attachments.py',
  "        _pulihkan_release_foto(akun_id, operasi_id, kini)\n        return None, PESAN_FOTO_TERTAHAN",
  "        return None, PESAN_FOTO_TERTAHAN",'test_reservasi_commit_lalu_adapter_gagal_release_exact_tanpa_provider','AssertionError'),
 ('callback_milestone','llm.py',"raise FotoBelumDikirim('pembacaan belum dikirim') from galat",
  "raise RuntimeError('pembacaan belum dikirim') from galat",'test_callback_commit_sent_lalu_gagal_sebelum_transport_release','AssertionError'),
 ('pointer_semantik','database.py',"    if kon.execute('''SELECT 1 FROM operasi_foto_baca o LEFT JOIN lampiran l ON l.id=o.hasil_id",
  "    if False and kon.execute('''SELECT 1 FROM operasi_foto_baca o LEFT JOIN lampiran l ON l.id=o.hasil_id",
  'test_semantik_pointer_receipt_harus_sesi_sama','DID NOT RAISE'),
 ('pointer_write','schema.py',"WHEN NEW.hasil_id IS NOT NULL AND NOT EXISTS(\n SELECT 1 FROM lampiran WHERE id=NEW.hasil_id AND sesi_id=NEW.sesi_id)\nBEGIN SELECT RAISE(ABORT,'pointer receipt foto tidak sah'); END;\nCREATE TRIGGER operasi_foto_baca_hasil_update",
  "WHEN 0\nBEGIN SELECT RAISE(ABORT,'pointer receipt foto tidak sah'); END;\nCREATE TRIGGER operasi_foto_baca_hasil_update",
  'test_trigger_pointer_receipt_tolak_sesi_lain','DID NOT RAISE'),
 ('schema_parsial','database.py',"if struktur(kon) != struktur(acuan):",
  "if False:", 'test_migrasi_optin_idempotent_preservasi_dan_parsial','DID NOT RAISE'),
 ('hasil_valid','attachments.py',"if sah is None or not llm.verifikasi_ekstraksi(sah, len(konteks)):",
  "if False:", 'test_result_dto_invalid_tidak_menjadi_completed','DID NOT RAISE'),
 ('final_fence','attachments.py',"or _sidik_foto(ctx) != context_hash or baru_fence != fence)",
  "or _sidik_foto(ctx) != context_hash)",
  'test_reread_fence_mencegah_late_result_menimpa_applied','DID NOT RAISE'),
)


@pytest.mark.parametrize('nama,berkas,lama,baru,tes,pesan',KASUS,ids=[x[0] for x in KASUS])
def test_guard_foto_merah_pulih(tmp_path,nama,berkas,lama,baru,tes,pesan):
    source=tmp_path/'mesin';source.mkdir()
    for p in (AKAR/'mesin').glob('*.py'):shutil.copy2(p,source/p.name)
    tests=tmp_path/'test_photo_attempts.py'
    shutil.copy2(Path(__file__).with_name('test_photo_attempts.py'),tests)
    target=source/berkas;asli=target.read_text()
    assert asli.count(lama)==(2 if nama=='final_fence' else 1)
    # Final fence dimatikan pada kedua titik agar assertion membuktikan invariant.
    target.write_text(asli.replace(lama,baru))
    argv=[sys.executable,'-B','-m','pytest',str(tests),'-k',tes,'-q','-W','error','-p','no:cacheprovider']
    env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(source),'PYTHONDONTWRITEBYTECODE':'1'}
    merah=subprocess.run(argv,cwd=tmp_path,env=env,capture_output=True,text=True,timeout=30)
    assert merah.returncode==1 and pesan in merah.stdout,merah.stdout+merah.stderr
    assert 'ImportError' not in merah.stdout and 'ModuleNotFoundError' not in merah.stdout
    target.write_text(asli)
    hijau=subprocess.run(argv,cwd=tmp_path,env=env,capture_output=True,text=True,timeout=30)
    assert hijau.returncode==0,hijau.stdout+hijau.stderr
