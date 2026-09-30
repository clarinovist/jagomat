"""Mutation guard konfigurasi dukungan pada salinan source terisolasi."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[1]
KASUS = [
    ("admin_launch_service.py", "or auth.revisi_auth(cocok[0]) != principal.revisi_auth", "or False",
     "test_support_settings.py", "test_update_principal_hidup_dan_rollback_failpoint", "DID NOT RAISE"),
    ("support_settings.py", "if revisi != lama.revisi or sidik_awal != sidik_lama:", "if False:",
     "test_support_settings.py", "test_stale_revision_dan_operation_collision_tanpa_perubahan", "assert"),
    ("support_settings.py", "or digit in PLACEHOLDER", "or False",
     "test_support_settings.py", "test_nomor_invalid_dan_placeholder_ditolak", "DID NOT RAISE"),
    ("support_settings.py", "if audit is not None:", "if False:",
     "test_support_settings.py", "test_update_atomik_replay_stale_collision_audit_tanpa_nomor", "KonflikOperasi"),
    ("support_settings.py", "except (OSError, RuntimeError, ValueError, TypeError, KeyError, sqlite3.Error):", "except OSError:",
     "test_support_settings.py", "test_reader_missing_parsial_dan_nilai_rusak_fail_closed_tanpa_tulis", "StoreBelumSiap"),
    ("admin_launch_http.py", "data['csrf']=data.pop('csrf_dukungan',None)", "data['csrf']=h._csrf(h._akun_principal(p),h._wajib_cookie(penangan,p));data.pop('csrf_dukungan',None)",
     "test_support_settings_http.py", "test_http_dukungan_csrf_wajib", "assert 303 == 403"),
    ("admin_http.py", "if not _reauth(principal, data.pop(\"reauth\", \"\")):", "if False:",
     "test_support_settings_http.py", "test_http_dukungan_reauth_wajib", "assert 400 == 403"),
    ("admin_security.py", "if not hmac.compare_digest(signature, harap):", "if False:",
     "test_support_settings_http.py", "test_http_dukungan_signature_wajib", "assert 303 == 403"),
    ("landing.py", "html.escape(dukungan.whatsapp_url, quote=True)", "html.escape(dukungan.whatsapp_url + '?text=Nama%20anak', quote=True)",
     "test_support_public.py", "test_url_whatsapp_tidak_mengandung_identitas_keluarga", "assert \"text=\" not in body"),
    ("admin_accounts.py", 'if perintah.aksi == AKSI_RESET_SANDI:\n            target.update(hash_baru)\n            target["revisi_auth"] = revisi_hasil', 'if perintah.aksi == AKSI_RESET_SANDI:\n            target.update(hash_baru)\n            target["revisi_auth"] = perintah.target_revisi',
     "test_admin_http_c.py", "test_reset_revoke_delete_guru_actual_dan_replay_aman", "assert sessions.ambil_principal(token_target) is None"),
    ("admin_accounts.py", "target.update(hash_baru)", "akun[0].update(hash_baru)",
     "test_admin_http_c.py", "test_reset_guru_sandi_pendek_ditolak_lalu_sukses_terisolasi", "assert auth.periksa(\"Ortu-C\", data[\"sandi_baru\"])"),
]


@pytest.mark.parametrize("modul,lama,baru,berkas,test,marker", KASUS)
def test_mutasi_guard_dukungan(tmp_path, modul, lama, baru, berkas, test, marker):
    target = tmp_path / "mesin"
    target.mkdir()
    for sumber in AKAR.glob("*.py"):
        shutil.copyfile(sumber, target / sumber.name)
    shutil.copytree(AKAR / "__tests__", target / "__tests__", ignore=shutil.ignore_patterns("__pycache__"))
    p = target / modul
    teks = p.read_text()
    assert teks.count(lama) == 1
    p.write_text(teks.replace(lama, baru, 1))
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    node = str(target / "__tests__" / berkas) + "::" + test
    hasil = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "-W", "error", "-p", "no:cacheprovider"],
        capture_output=True, text=True, env=env, timeout=40,
    )
    assert hasil.returncode == 1, hasil.stdout + hasil.stderr
    assert marker in hasil.stdout, hasil.stdout
    p.write_text(teks)
    pulih = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "-W", "error", "-p", "no:cacheprovider"],
        capture_output=True, text=True, env=env, timeout=40,
    )
    assert pulih.returncode == 0, pulih.stdout + pulih.stderr
