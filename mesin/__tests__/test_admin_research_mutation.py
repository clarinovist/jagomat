"""Mutation guard aplikasi interviewer pada salinan source temp terisolasi.

Setiap kasus mematikan satu guard lewat jalur yang benar-benar dipanggil test
domain/HTTP, membuktikan test merah, lalu memulihkan dan membuktikan hijau.
Tidak menyentuh DB pengguna atau database riset live.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[1]
KASUS = [
    # Principal/akses: hapus pemeriksaan cookie hidup pada GET.
    ("admin_research_http.py", "    try:\n        h._wajib_cookie(penangan, principal)\n    except PermissionError:\n        return None",
     "    return principal", "test_admin_research_http.py",
     "test_dashboard_privat_hanya_cookie_admin_dan_get_hilang_tidak_bootstrap", "cookie admin hidup wajib"),
    # Pemisahan bukti: jangan buang bukti saat status nonnarasi.
    ("research_store.py", "        if any((jawaban_responden, kutipan_responden, kode_utama, kode_tambahan, kutipan_terpilih)):\n            raise ValueError(\"jawaban nonnarasi tidak boleh membawa bukti\")",
     "        if False:\n            raise ValueError(\"jawaban nonnarasi tidak boleh membawa bukti\")",
     "test_admin_research_store.py",
     "test_status_nonnarasi_menolak_membawa_bukti", "IntegrityError"),
    # Retensi: jangan hapus isi jawaban saat purge.
    ("research_store.py", "            kon.execute(\"DELETE FROM jawaban_riset WHERE wawancara_id=?\", (identitas,))",
     "            pass", "test_admin_research_store.py",
     "test_retensi_bounded_menghapus_teks", "assert"),
    # Penarikan consent: jangan hapus jawaban.
    ("research_store.py", "        kon.execute(\"DELETE FROM jawaban_riset WHERE wawancara_id=?\", (wawancara_id,))",
     "        pass", "test_admin_research_store.py",
     "test_tarik_consent_menghapus_semua_teks_tapi_audit_tanpa_payload", "assert"),
    # Ekspor: jangan netralkan formula spreadsheet.
    ("admin_research_service.py", "    if teks.startswith((\"=\", \"+\", \"-\", \"@\", \"\\t\", \"\\r\")):\n        return \"'\" + teks",
     "    if False:\n        return \"'\" + teks", "test_admin_research_store.py",
     "test_ekspor_csv_netral_formula_dan_tidak_membawa_actor", "'=FORMULA"),
    # CSRF wajib pada form buat.
    ("admin_research_http.py", "    h._cek_csrf(akun, sesi, csrf)", "    pass",
     "test_admin_research_http.py",
     "test_buat_wawancara_memerlukan_consent_csrf_dan_tidak_duplikat", "assert 303 == 403"),
    # Reauth wajib pada penarikan consent.
    ("admin_research_http.py", "    if not h._reauth(principal, sandi):\n        raise PermissionError(\"Autentikasi ulang tidak sah.\")",
     "    if False:\n        raise PermissionError(\"Autentikasi ulang tidak sah.\")",
     "test_admin_research_http.py",
     "test_tarik_consent_perlu_reauth_dan_menghapus_teks", "assert 303 == 403"),
    # Revisi optimistik: jangan diam-diam memakai revisi server untuk tab lama.
    ("research_store.py", "        if int(wawancara[\"revisi\"]) != revisi_wawancara:\n            raise KonflikRiset(\"wawancara telah berubah\")",
     "        revisi_wawancara = int(wawancara[\"revisi\"])",
     "test_admin_research_store.py", "test_tab_lama_ditolak_setelah_perubahan_lain", "DID NOT RAISE"),
    # Backup riset: jangan validasi hash.
    ("research_backup.py", "    if db.stat().st_size != info[\"ukuran\"] or _sha256(db) != info[\"sha256\"]:\n        raise BackupRisetTidakSah(\"hash/ukuran backup riset tidak cocok\")",
     "    if False:\n        raise BackupRisetTidakSah(\"hash/ukuran backup riset tidak cocok\")",
     "test_admin_research_backup.py", "test_backup_hash_berubah_ditolak", "DID NOT RAISE"),
    # Instrumen immutable: jangan tolak update snapshot.
    ("research_schema.py", "CREATE TRIGGER instrumen_riset_tolak_update BEFORE UPDATE ON instrumen_riset\nBEGIN SELECT RAISE(ABORT,'instrumen riset immutable'); END;",
     "CREATE TRIGGER instrumen_riset_tolak_update BEFORE UPDATE ON instrumen_riset\nBEGIN SELECT 1; END;",
     "test_admin_research_store.py", "test_bootstrap_idempoten_instrumen_immutable_dan_get_tidak_membuat", "DID NOT RAISE"),
]


@pytest.mark.parametrize("modul,lama,baru,berkas,test,marker", KASUS)
def test_mutasi_guard_riset(tmp_path, modul, lama, baru, berkas, test, marker):
    target = tmp_path / "mesin"
    target.mkdir()
    for sumber in AKAR.glob("*.py"):
        shutil.copyfile(sumber, target / sumber.name)
    shutil.copytree(AKAR / "__tests__", target / "__tests__", ignore=shutil.ignore_patterns("__pycache__"))
    p = target / modul
    teks = p.read_text()
    assert teks.count(lama) == 1, modul
    p.write_text(teks.replace(lama, baru, 1))
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    node = str(target / "__tests__" / berkas) + "::" + test
    hasil = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "-W", "error", "-p", "no:cacheprovider"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert hasil.returncode == 1, hasil.stdout + hasil.stderr
    assert marker in hasil.stdout, hasil.stdout
    p.write_text(teks)
    pulih = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "-W", "error", "-p", "no:cacheprovider"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert pulih.returncode == 0, pulih.stdout + pulih.stderr
