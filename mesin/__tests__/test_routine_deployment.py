"""Policy rutin dan recovery diuji pada adapter subprocess yang sama dengan migrasi."""

import contextlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_deployer import (AKAR, KANDIDAT, RECOVERY, ID_KANDIDAT, ID_LAMA,
                           RunnerPalsu, d, kasus, fstat_root)

PERINTAH_RUTIN = "deploy-rutin-v1 " + KANDIDAT + " " + RECOVERY


def policy(**perubahan):
    isi = dict(enabled=True, schema_target=4, deployer_sha256=d.hash_deployer(),
               contract_sha256="f" * 64, recovery_revision="b" * 40)
    isi.update(perubahan)
    return json.dumps(isi)


@pytest.fixture
def rutin(kasus):
    kasus.b.policy = policy()
    kasus.b.policy_baru = None
    kasus.b.policy_calls = 0
    def baca():
        assert kasus.b.terkunci
        kasus.b.policy_calls += 1
        kasus.b.catat("policy" + str(kasus.b.policy_calls))
        mentah = kasus.b.policy_baru if kasus.b.policy_calls > 1 and kasus.b.policy_baru is not None else kasus.b.policy
        return d.validasi_policy_rutin(mentah)
    kasus.b.policy_rutin = baca
    jalan_lama = kasus.jalan
    kasus.jalan = lambda teks=PERINTAH_RUTIN, **kw: jalan_lama(teks, **kw)
    return kasus


def test_rutin_sukses_tanpa_approval_migrasi_dengan_urutan_guard(rutin):
    assert rutin.jalan() == 0
    jejak = rutin.jejak
    assert not rutin.b.consumed
    assert not any(x.startswith("approval") or x == "consume" for x in jejak)
    assert jejak.index("probe-recovery") < jejak.index("contract-lama")
    assert jejak.index("contract-candidate") < jejak.index("schema-lama")
    assert jejak.index("contract-recovery") < jejak.index("schema-lama")
    assert jejak.index("schema-lama") < jejak.index("policy2") < jejak.index("stop-lama")
    assert jejak.index("policy2") < jejak.index("pasangan") < jejak.index("stop-lama")
    assert rutin.b.pasangan[3] == "rutin"
    assert jejak[-1] == "unlock"
    assert "deploy rutin selesai" in rutin.pesan[-1]
    for argv, opsi in rutin.r.calls:
        if opsi.get("input") == d.PROBE_KONTRAK:
            assert "--mount" not in argv and "--env-file" not in argv
            assert "--network" in argv and "none" in argv and "--read-only" in argv
            assert "DEEPSEEK_API_KEY" not in opsi["env"]


@pytest.mark.parametrize("perubahan", [{"enabled": False}, {"enabled": 1}, {"enabled": "true"},
    {"schema_target": 3}, {"schema_target": 5}, {"schema_target": 4.0}, {"schema_target": True},
    {"deployer_sha256": "0" * 64}, {"contract_sha256": ""}, {"contract_sha256": "A" * 64},
    {"contract_sha256": None}, {"recovery_revision": "a" * 39}, {"recovery_revision": "latest"},
    {"recovery_revision": None}, {"backup_pair": "tidak-perlu-di-rutin"}])
def test_policy_salah_tanpa_docker(rutin, perubahan):
    rutin.b.policy = policy(**perubahan)
    assert rutin.jalan() == 2
    assert rutin.r.calls == []


@pytest.mark.parametrize("isi", ["{}", "[]", "null", "{rusak", policy().replace(
    '"enabled": true', '"enabled": false, "enabled": true')])
def test_policy_json_gagal_tertutup(rutin, isi):
    rutin.b.policy = isi
    assert rutin.jalan() == 2
    assert not rutin.r.calls


@pytest.mark.parametrize("tahap", ["policy1", "policy2", "disk", "config", "lock"])
def test_policy_dan_host_gagal_tidak_stop(rutin, tahap):
    rutin.b.gagal = tahap
    assert rutin.jalan() == 2
    assert not any(x.startswith(("stop-", "run-", "rm-")) for x in rutin.jejak)


@pytest.mark.parametrize("tahap", ["contract-lama", "contract-candidate", "contract-recovery", "schema-lama", "revision-recovery"])
@pytest.mark.parametrize("jenis", ["gagal", "timeout", "beda"])
def test_kontrak_dan_skema_dicek_sebelum_swap(rutin, tahap, jenis):
    if jenis == "beda": rutin.r.malformed[tahap] = "0" * 64
    else:
        rutin.r.gagal = {tahap}
        rutin.r.raise_mode = jenis == "timeout"
    assert rutin.jalan() == 2
    assert "stop-lama" not in rutin.jejak and "run-candidate" not in rutin.jejak
    assert rutin.r.current == "lama" and rutin.r.running


@pytest.mark.parametrize("status,jalan,health", [("exited", "false", "healthy"),
    ("running", "true", "unhealthy"), ("running", "true", "missing"),
    ("restarting", "true", "healthy")])
def test_current_tidak_sehat_bukan_izin_rutin(rutin, status, jalan, health):
    rutin.r.proses["lama"] = (status, jalan)
    rutin.r.health["lama"] = health
    assert rutin.jalan() == 2
    assert "stop-lama" not in rutin.jejak


def test_http_current_wajib401(rutin):
    assert rutin.jalan(http=lambda: False) == 2
    assert "stop-lama" not in rutin.jejak


@pytest.mark.parametrize("perubahan", [{"enabled": False}, {"contract_sha256": "e" * 64},
                                       {"recovery_revision": "a" * 40}])
def test_policy_dicabut_atau_berubah_selama_pull(rutin, perubahan):
    rutin.b.policy_baru = policy(**perubahan)
    assert rutin.jalan() == 2
    assert "stop-lama" not in rutin.jejak


@pytest.mark.parametrize("gagal,harapan", [({"run-candidate"}, 1), ({"schema-candidate"}, 1),
    ({"run-candidate", "run-recovery"}, 2), ({"run-candidate", "stop-candidate"}, 2),
    ({"stop-lama"}, 2), ({"rm-lama"}, 2)])
def test_rutin_pakai_state_machine_recovery_yang_sama(rutin, gagal, harapan):
    rutin.r.gagal = gagal
    assert rutin.jalan() == harapan
    runs = [a for a, _ in rutin.r.calls if "--detach" in a]
    if harapan == 1:
        assert runs[0][:-1] == runs[1][:-1]
        assert runs[1][-1] == d.REGISTRI + "@" + RECOVERY
        assert "Writehold" not in rutin.pesan[-1]
    if "stop-candidate" in gagal:
        assert "run-recovery" not in rutin.jejak


def test_noop_masih_menegakkan_policy_schema_dan_kontrak(rutin):
    rutin.r.current = "candidate"
    assert rutin.jalan() == 0
    assert "schema-candidate" in rutin.jejak and "policy2" in rutin.jejak
    assert "pasangan" in rutin.jejak and rutin.b.pasangan[3] == "rutin"
    assert not any(x.startswith(("stop-", "rm-")) for x in rutin.jejak)
    assert "tidak ada swap" in rutin.pesan[-1]


@pytest.mark.parametrize("teks", [PERINTAH_RUTIN + "\n", PERINTAH_RUTIN + ";id",
    PERINTAH_RUTIN.replace(KANDIDAT, RECOVERY), PERINTAH_RUTIN + " --policy /tmp/x",
    PERINTAH_RUTIN.replace(" ", "\t"), PERINTAH_RUTIN.replace(KANDIDAT, "latest")])
def test_rutin_request_invalid_nol_io(rutin, teks):
    assert rutin.jalan(teks) == 2
    assert not rutin.jejak and not rutin.r.calls


def test_policy_nyata_root0600_lock_dan_tidak_memakai_approval(tmp_path, fstat_root, monkeypatch):
    monkeypatch.setattr(d, "POLICY_RUTIN", tmp_path / "routine.json")
    monkeypatch.setattr(d, "LOCK", tmp_path / "lock")
    fs = d.Berkas()
    d.POLICY_RUTIN.write_text(policy())
    d.POLICY_RUTIN.chmod(0o600)
    with pytest.raises(d.Ditolak): fs.policy_rutin()
    with fs.kunci():
        assert fs.policy_rutin()["enabled"] is True
        d.POLICY_RUTIN.chmod(0o644)
        with pytest.raises(d.Ditolak): fs.policy_rutin()
        d.POLICY_RUTIN.unlink()
        with pytest.raises(FileNotFoundError): fs.policy_rutin()
        asal = tmp_path / "asal"
        asal.write_text(policy()); asal.chmod(0o600)
        d.POLICY_RUTIN.symlink_to(asal)
        with pytest.raises(OSError): fs.policy_rutin()


def jalankan_kontrak(akar):
    script = d.PROBE_KONTRAK.replace("Path('/app')", "Path(" + repr(str(akar)) + ")")
    return subprocess.run([sys.executable, "-E", "-B", "-"], input=script,
                          capture_output=True, text=True, timeout=15)


def test_fingerprint_source_bukan_import_atau_data(tmp_path):
    # Salin SOURCE tracked saja, bukan DB/credential atau import aplikasi.
    for p in (AKAR / "mesin").glob("*.py"):
        (tmp_path / p.name).write_bytes(p.read_bytes())
    awal = jalankan_kontrak(tmp_path)
    assert awal.returncode == 0 and len(awal.stdout.strip()) == 64
    assert awal.stdout == jalankan_kontrak(tmp_path).stdout
    p = tmp_path / "assistant_pages.py"
    p.write_text("raise RuntimeError('jangan import')\n")
    assert jalankan_kontrak(tmp_path).stdout == awal.stdout  # perubahan UI boleh
    (tmp_path / "schema_tambahan.py").write_text("# skema tambahan\n")
    assert jalankan_kontrak(tmp_path).stdout != awal.stdout
    (tmp_path / "schema_tambahan.py").unlink()
    p = tmp_path / "schema.py"
    p.write_bytes(p.read_bytes() + b"\n# kontrak baru\n")
    assert jalankan_kontrak(tmp_path).stdout != awal.stdout
    p.unlink()
    assert jalankan_kontrak(tmp_path).returncode != 0


@pytest.mark.parametrize("field", ["enabled", "schema_target", "deployer_sha256", "contract_sha256", "recovery_revision"])
def test_policy_field_wajib(rutin, field):
    isi = json.loads(policy())
    del isi[field]
    rutin.b.policy = json.dumps(isi)
    assert rutin.jalan() == 2
    assert not rutin.r.calls


def test_noop_kontrak_salah_tetap_ditolak(rutin):
    rutin.r.current = "candidate"
    rutin.r.malformed["contract-candidate"] = "e" * 64
    assert rutin.jalan() == 2
    assert not any(x.startswith(("stop-", "run-")) for x in rutin.jejak)


def test_rutin_io_policy_nyata_lock_sampai_recovery(tmp_path, fstat_root, monkeypatch):
    monkeypatch.setattr(d, "POLICY_RUTIN", tmp_path / "routine.json")
    monkeypatch.setattr(d, "LOCK", tmp_path / "lock")
    d.POLICY_RUTIN.write_text(policy())
    d.POLICY_RUTIN.chmod(0o600)
    class BerkasSintetis(d.Berkas):
        def periksa_host(self): pass
        def ruang(self): pass
        def tulis_pasangan(self, revisi, digest, kontrak, mode): pass
        @contextlib.contextmanager
        def konfigurasi(self): yield (), dict(d.LINGKUNGAN)
    fs = BerkasSintetis()
    runner = RunnerPalsu([])
    runner.gagal = {"run-candidate"}
    def locked(argv, **kw):
        assert fs._lock_fd is not None
        with pytest.raises(BlockingIOError):
            with d.Berkas().kunci():
                pytest.fail("Deploy saingan harus tertahan")
        return runner(argv, **kw)
    assert d.deploy(PERINTAH_RUTIN, docker=d.Docker(locked), berkas=fs,
                    sekarang=lambda: 100, monotonic=lambda: 100,
                    http=lambda: True, lapor=lambda _: None) == 1
    assert "schema-recovery" in runner.jejak
    assert fs._lock_fd is None
    assert not list(tmp_path.glob("*approval*"))


def test_cli_rutin_menerima_wrapper_tanpa_env_bypass(monkeypatch):
    panggilan = []
    monkeypatch.setattr(d, "deploy", lambda teks: panggilan.append(teks) or 0)
    assert d.main([PERINTAH_RUTIN], {"SSH_ORIGINAL_COMMAND": "perintah-lain"}) == 0
    assert panggilan == [PERINTAH_RUTIN]


def test_fingerprint_schema_pendamping_migrator_startup_dan_persistensi(tmp_path):
    for p in (AKAR / "mesin").glob("*.py"):
        (tmp_path / p.name).write_bytes(p.read_bytes())
    awal = jalankan_kontrak(tmp_path).stdout
    for nama in ("assistant_schema.py", "database.py", "migrate_params.py", "serve.py",
                 "auth.py", "sessions.py", "outcome_presentations.py", "assistant_actions.py"):
        p = tmp_path / nama
        asli = p.read_bytes()
        p.write_bytes(asli + b"\n# perubahan\n")
        assert jalankan_kontrak(tmp_path).stdout != awal, nama
        p.write_bytes(asli)
