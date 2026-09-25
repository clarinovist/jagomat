"""Backup, no-hook, ownership dan probe rilis hanya pada fixture sintetis."""

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest
import admin_backup
import admin_store
import subscription as d
import subscription_store as s
from test_subscription_store import ledger, invoice, bukti, dump, AKUN, ON, T0
from test_admin_backup import _buat_bundle, _buat_ai_v2
from test_profile_release_probe import _python, _modul


def test_profil_asing_ditolak_sebelum_ledger(ledger):
    sebelum = dump(ledger)
    with pytest.raises(LookupError, match="profil tidak ditemukan"):
        s.atur_cakupan(ledger, AKUN, (999,), operasi_id="cakupan_asing", revisi=1,
                      sekarang=T0, pemilik_profil=lambda _: "akun_"+"f"*32, sakelar=ON)
    assert dump(ledger) == sebelum


def test_backup_ledger_berisi_receipt_grant_tetap_durable(tmp_path):
    bundle = _buat_bundle(tmp_path)
    p = bundle / "admin-control.db"
    s.enroll(p, AKUN, sumber_id="daftar_backup", asal="publik", mulai=T0, peran="guru", sakelar=ON)
    s.atur_cakupan(p, AKUN, (1,), operasi_id="cakupan_backup", revisi=0, sekarang=T0,
                  pemilik_profil=lambda _: AKUN, sakelar=ON)
    inv = invoice(p)
    s.terapkan_pembayaran(p, AKUN, bukti(inv), sekarang=T0+1, sakelar=ON)
    (bundle / "manifest.json").unlink()  # Manifest fixture lama, bukan backup pengguna.
    admin_backup.buat_manifest(bundle, bundle_id="backup-ledger", cutoff=T0+2)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.iterdir()}
    hasil = admin_backup.validasi_bundle(bundle)
    assert hasil.versi_admin == 7 and hasil.perlu_rekonsiliasi
    ulang = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)
    assert ulang.perlu_rekonsiliasi and ulang.versi_admin == 7
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.iterdir()} == hashes
    pulih = tmp_path / "pulih.db"
    with sqlite3.connect(p) as sumber, sqlite3.connect(pulih) as tujuan:
        sumber.backup(tujuan)
    admin_store.siapkan(pulih)
    assert s.baca(pulih, AKUN) == s.baca(p, AKUN)
    assert s.terapkan_pembayaran(pulih, AKUN, bukti(inv), sekarang=T0+3, sakelar=ON) == "grant"
    assert dump(pulih) == dump(p)


def test_backup_menolak_trigger_billing_hilang(tmp_path):
    bundle = _buat_bundle(tmp_path)
    with sqlite3.connect(bundle / "admin-control.db") as kon:
        kon.execute("DROP TRIGGER langganan_receipt_tolak_replace")
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-rusak", cutoff=2)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.validasi_bundle(bundle)


def test_reader_menolak_link_grant_rusak(ledger):
    inv = invoice(ledger)
    s.terapkan_pembayaran(ledger, AKUN, bukti(inv), sekarang=T0+1, sakelar=ON)
    with sqlite3.connect(ledger) as kon:
        trigger = kon.execute("SELECT sql FROM sqlite_master WHERE name='langganan_grant_tolak_update'").fetchone()[0]
        kon.execute('DROP TRIGGER langganan_grant_tolak_update')
        kon.execute("UPDATE langganan_grant SET profil_json='[99]'")
        kon.execute(trigger)
    sebelum = dump(ledger)
    with pytest.raises(s.KonflikLangganan):
        s.baca(ledger, AKUN)
    assert dump(ledger) == sebelum


def test_probe_langganan_dijalankan_dan_verifier_tidak_boleh_skip(tmp_path):
    helper = _modul("release_subscription_probe")
    hasil = _python(helper.SUMBER_UJI_LANGGANAN + '\nassert uji_langganan("uji") == 4\n', tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    from test_release_image import jalankan_probe
    hasil = jalankan_probe(tmp_path, injeksi=(
        'def gagal(*args):\n    raise RuntimeError("ledger_gagal")\n'
        'ruang["uji_langganan"] = gagal\n'))
    assert hasil.returncode != 0
    assert json.loads(hasil.stdout) == {"ok": False, "kode": "probe_gagal"}


def test_source_tidak_punya_hook_user_network_env_billing():
    akar = Path(__file__).resolve().parents[1]
    izin = {"subscription", "subscription_store", "subscription_schema", "midtrans_contract", "admin_store", "admin_backup", "subscription_service", "subscription_registration", "midtrans_sandbox", "subscription_checkout", "subscription_http", "subscription_preview", "admin_launch_service", "admin_subscription", "admin_operations", "midtrans_secret", "midtrans_produksi", "subscription_produksi", "subscription_callback", "subscription_worker"}
    for p in akar.glob("*.py"):
        pohon = ast.parse(p.read_text())
        for node in ast.walk(pohon):
            if isinstance(node, ast.Import):
                modul = [n.name.split('.')[0] for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                modul = [(node.module or '').split('.')[0]]
            else:
                continue
            if "midtrans_sandbox" in modul:
                assert p.stem == "subscription_preview", p.name
            if "subscription_http" in modul:
                assert p.stem in {"web", "subscription_preview", "admin_subscription"}, p.name
            if set(modul) & {"subscription", "subscription_store", "subscription_schema", "midtrans_contract", "subscription_service", "subscription_registration", "subscription_checkout"}:
                assert p.stem in izin, p.name
    for nama in ("subscription.py", "subscription_store.py", "midtrans_contract.py", "subscription_service.py", "subscription_registration.py"):
        teks = (akar / nama).read_text()
        assert "os.environ" not in teks and "getenv(" not in teks
        assert "import socket" not in teks and "urllib.request" not in teks
    for nama in ("midtrans_secret.py", "midtrans_produksi.py", "subscription_produksi.py", "subscription_callback.py", "subscription_worker.py"):
        teks = (akar / nama).read_text()
        assert "os.environ" not in teks and "getenv(" not in teks
        assert "import socket" not in teks and "urllib.request" not in teks
    preview = (akar / "subscription_preview.py").read_text()
    runtime = (akar / "subscription_http.py").read_text()
    assert "ThreadingHTTPServer(('127.0.0.1', 0)" in preview
    assert "config.lingkungan != \"sandbox\"" in runtime
    assert "getattr(penangan.server, 'langganan_sandbox', None)" in runtime
    assert "OSN_MIDTRANS" not in preview + runtime and "MIDTRANS_SERVER" not in preview + runtime
    assert d.SAKELAR == d.Sakelar(False, False, False, False)
    root = akar.parent
    config = json.loads((root / 'scripts/release-metadata.json').read_text())
    assert config['mode'] in ('persiapan', 'migrasi')
    assert '    if: ${{ false }}' in (root / '.github/workflows/deploy.yml').read_text().split('  pasang:\n')[1]
