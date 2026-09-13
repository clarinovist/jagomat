"""Deployer diuji tanpa Docker, jaringan, credential, atau DB keluarga asli."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
from types import SimpleNamespace
import urllib.error

import pytest

AKAR = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("deployer_uji", AKAR / "scripts" / "deploy.py")
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)
KANDIDAT = "sha256:" + "a" * 64
RECOVERY = "sha256:" + "b" * 64
ID_KANDIDAT = "sha256:" + "c" * 64
ID_RECOVERY = "sha256:" + "d" * 64
ID_LAMA = "sha256:" + "e" * 64
PERINTAH = "deploy-v2 " + KANDIDAT + " " + RECOVERY
RAHASIA = "kunci-sintetis-jangan-log"


def approval(**perubahan):
    isi = dict(candidate=KANDIDAT, recovery=RECOVERY, expires=200, issued=100,
               approval_id="1" * 32, deployer_sha256=d.hash_deployer(),
               backup_pair="sintetis-20260912", writes_held=True,
               maintenance_paused=True, schema_target=4)
    isi.update(perubahan)
    return json.dumps(isi)


class BerkasPalsu:
    def __init__(self, jejak):
        self.jejak = jejak
        self.gagal = None
        self.isi = approval()
        self.berikut = None
        self.hitungan = 0
        self.terkunci = False
        self.consumed = False
        self.konfig = (("/tmp/sintetis/visual.env", "/tmp/sintetis/pendamping.env"),
                       dict(d.LINGKUNGAN, DEEPSEEK_API_KEY=RAHASIA))

    def catat(self, tahap):
        self.jejak.append(tahap)
        if self.gagal == tahap:
            raise OSError("pesan privat " + RAHASIA)

    def periksa_host(self):
        self.catat("host")

    @contextlib.contextmanager
    def kunci(self):
        self.catat("lock")
        self.terkunci = True
        try:
            yield
        finally:
            self.terkunci = False
            self.jejak.append("unlock")

    @contextlib.contextmanager
    def konfigurasi(self):
        self.catat("config")
        yield self.konfig
        self.jejak.append("config-clean")

    def approval(self, kandidat, pemulihan, sekarang):
        assert self.terkunci
        if self.consumed:
            raise d.Ditolak()
        self.hitungan += 1
        self.catat("approval" + str(self.hitungan))
        isi = self.berikut if self.hitungan > 1 and self.berikut is not None else self.isi
        return d.validasi_approval(isi, kandidat, pemulihan, sekarang)

    def konsumsi(self, isi, sekarang):
        assert self.terkunci and not self.consumed
        self.catat("consume")
        self.consumed = True

    def ruang(self):
        self.catat("disk")


class RunnerPalsu:
    """Model daemon: semua failpoint melewati wrapper subprocess production."""

    def __init__(self, jejak):
        self.jejak = jejak
        self.calls = []
        self.gagal = set()
        self.raise_mode = False
        self.malformed = {}
        self.current = "lama"
        self.exists = True
        self.running = True
        self.health = {"candidate": "healthy", "recovery": "healthy"}
        self.proses = {}
        self.run_gagal_tanpa_create = False
        self.probes = {}
        self.probe_id = "f" * 64

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        assert argv[0] == d.DOCKER
        assert kwargs["shell"] is False
        assert kwargs["timeout"] > 0
        assert kwargs["stderr"] == kwargs["stdout"] == subprocess.PIPE
        assert RAHASIA not in repr(argv)
        a = argv[1:]
        hasil = ""
        if a[0] == "pull":
            label = "pull-" + self.image_nama(a[-1])
        elif a[:2] == ["image", "inspect"]:
            nama = self.image_nama(a[-1])
            label = ("repo-" if "RepoDigests" in a[3] else "image-") + nama
            hasil = (json.dumps([a[-1]]) if label.startswith("repo-") else self.image_id(nama))
            if "org.opencontainers.image.revision" in a[3]:
                label = "revision-" + nama
                hasil = "b" * 40
        elif a[0] == "run" and "--rm" in a:
            label = "probe-" + self.image_nama(a[a.index("--entrypoint") + 2])
            hasil = "OSN_IMAGE_ADMIN4_AI2_OK"
            if kwargs["input"] == d.PROBE_KONTRAK:
                label = "contract-" + self.image_nama(a[a.index("--entrypoint") + 2])
                hasil = "f" * 64
            nama = a[a.index("--name") + 1]
            token = a[a.index("--label") + 1].split("=", 1)[1]
            self.probes[self.probe_id] = "/" + nama + "|" + token
        elif a[0] == "run":
            nama = self.image_nama(a[-1])
            label = "run-" + nama
            assert not self.exists, "Tidak boleh create writer saingan"
            self.current = nama
            self.exists = not (self.run_gagal_tanpa_create and label in self.gagal)
            self.running = self.exists
        elif a[:2] == ["container", "inspect"] and a[-1] == self.probe_id:
            label = "probe-owner"
            hasil = self.probes[self.probe_id]
        elif a[:2] == ["container", "ls"] and "--no-trunc" in a:
            label = "probe-list"
            hasil = self.probe_id if self.probes else ""
        elif a[:2] == ["container", "inspect"]:
            label = "state-" + self.current
            status, jalan = self.proses.get(self.current, ("running", "true"))
            hasil = "|".join((status, jalan, self.health.get(self.current, "healthy"),
                              self.image_id(self.current)))
        elif a[:2] == ["container", "ls"]:
            label = "cleanup-list"
            hasil = json.dumps(d.KONTAINER) if self.exists else ""
        elif a[0] == "stop":
            label = "stop-" + self.current
            if label not in self.gagal:
                self.running = False
        elif a[0] == "rm":
            if a[-1] == self.probe_id:
                label = "probe-cleanup"
            else:
                label = "rm-" + self.current
                assert not self.running
                if label not in self.gagal:
                    self.exists = False
        elif a[0] == "exec":
            label = "schema-" + self.current
            hasil = "OSN_SCHEMA_ADMIN4_AI2_OK"
        else:
            raise AssertionError("argv tak dikenal")
        self.jejak.append(label)
        hasil = self.malformed.get(label, hasil)
        if label in self.gagal:
            if self.raise_mode:
                raise subprocess.TimeoutExpired(argv, 1, output=RAHASIA, stderr=RAHASIA)
            return subprocess.CompletedProcess(argv, 1, RAHASIA, RAHASIA)
        return subprocess.CompletedProcess(argv, 0, hasil, "")

    @staticmethod
    def image_nama(image):
        if image.endswith(KANDIDAT) or image == ID_KANDIDAT:
            return "candidate"
        if image.endswith(RECOVERY) or image == ID_RECOVERY:
            return "recovery"
        assert image == ID_LAMA
        return "lama"

    @staticmethod
    def image_id(nama):
        return {"candidate": ID_KANDIDAT, "recovery": ID_RECOVERY, "lama": ID_LAMA}[nama]


@pytest.fixture
def kasus():
    jejak = []
    runner = RunnerPalsu(jejak)
    berkas = BerkasPalsu(jejak)
    pesan = []
    jam = [100]

    def tidur(detik):
        jam[0] += detik

    def jalan(teks=PERINTAH, **tambahan):
        hasil = d.deploy(teks, docker=d.Docker(runner), berkas=berkas,
                         sekarang=lambda: jam[0], monotonic=lambda: jam[0],
                         tidur=tidur, http=tambahan.pop("http", lambda: True),
                         lapor=pesan.append, **tambahan)
        assert not berkas.terkunci
        assert RAHASIA not in repr(pesan)
        return hasil

    return SimpleNamespace(r=runner, b=berkas, jejak=jejak, pesan=pesan, jam=jam, jalan=jalan)


@pytest.mark.parametrize("teks", [
    "", None, KANDIDAT, "deploy-v2 " + KANDIDAT, PERINTAH + "\n", " " + PERINTAH,
    PERINTAH + " ", PERINTAH.replace(" ", "\t"), PERINTAH.replace(" ", "  ", 1),
    PERINTAH + ";touch /tmp/pwn", PERINTAH + " $(id)", PERINTAH + " --env X=1",
    PERINTAH.replace("deploy-v2", "deploy"), PERINTAH.replace("a" * 64, "A" * 64),
    PERINTAH.replace("a" * 64, "a" * 63), PERINTAH.replace("a" * 64, "a" * 65),
    PERINTAH.replace(KANDIDAT, RECOVERY), PERINTAH.replace(KANDIDAT, "latest"),
    PERINTAH.replace(KANDIDAT, "x/y@" + KANDIDAT), PERINTAH + "\x00",
])
def test_request_tidak_tepat_ditolak_tanpa_io(kasus, teks):
    assert kasus.jalan(teks) == 2
    assert kasus.jejak == []
    assert kasus.r.calls == []


@pytest.mark.parametrize("perubahan", [
    {"candidate": RECOVERY}, {"recovery": KANDIDAT},
    {"expires": 100, "issued": 90}, {"expires": 99, "issued": 90},
    {"expires": True}, {"expires": 201.0}, {"expires": "200"}, {"writes_held": False},
    {"writes_held": 1}, {"maintenance_paused": False}, {"maintenance_paused": "true"},
    {"schema_target": 3}, {"schema_target": 4.0}, {"backup_pair": ""},
    {"backup_pair": "../backup"}, {"backup_pair": "a\nb"}, {"backup_pair": None},
    {"unknown_flag": True}, {"issued": 101}, {"issued": -1}, {"issued": True},
    {"issued": 100.0}, {"issued": "100"}, {"issued": None},
    {"expires": 1001}, {"approval_id": ""}, {"approval_id": "../receipt"},
    {"approval_id": "A" * 32}, {"approval_id": "1" * 31}, {"approval_id": None},
    {"deployer_sha256": "a" * 64}, {"deployer_sha256": "latest"},
    {"deployer_sha256": None}, {"deployer_sha256": "A" * 64},
])
def test_approval_guard_sebelum_docker(kasus, perubahan):
    kasus.b.isi = approval(**perubahan)
    assert kasus.jalan() == 2
    assert kasus.r.calls == []


@pytest.mark.parametrize("isi", ["[]", "null", "{bad", "{}", approval().replace(
    '"writes_held": true', '"writes_held": false, "writes_held": true')])
def test_approval_json_tidak_ambigu(kasus, isi):
    kasus.b.isi = isi
    assert kasus.jalan() == 2
    assert kasus.r.calls == []


@pytest.mark.parametrize("tahap", ["host", "lock", "config", "approval1", "disk", "approval2", "consume"])
def test_preflight_filesystem_gagal_tidak_stop(kasus, tahap):
    kasus.b.gagal = tahap
    assert kasus.jalan() == 2
    assert not any(x.startswith(("stop-", "run-")) for x in kasus.jejak)


@pytest.mark.parametrize("tahap", [
    "pull-candidate", "image-candidate", "repo-candidate", "probe-candidate",
    "pull-recovery", "image-recovery", "repo-recovery", "probe-recovery",
    "state-lama", "image-lama",
])
@pytest.mark.parametrize("timeout", [False, True])
def test_semua_boundary_imageprep_gagal_tidak_sentuh_lama(kasus, tahap, timeout):
    kasus.r.gagal = {tahap}
    kasus.r.raise_mode = timeout
    assert kasus.jalan() == 2
    assert not any(x.startswith(("stop-", "run-")) for x in kasus.jejak)
    assert kasus.r.current == "lama" and kasus.r.running


@pytest.mark.parametrize("tahap,nilai", [
    ("image-candidate", "latest"), ("repo-candidate", "[]"),
    ("repo-candidate", "not-json"), ("probe-candidate", ""),
    ("image-recovery", ID_KANDIDAT), ("state-lama", "running|true|healthy|latest"),
    ("image-lama", ID_RECOVERY),
])
def test_inspect_dan_probe_bukan_hanya_exit0(kasus, tahap, nilai):
    kasus.r.malformed[tahap] = nilai
    assert kasus.jalan() == 2
    assert "stop-lama" not in kasus.jejak


@pytest.mark.parametrize("approval_baru", [approval(expires=99), approval(backup_pair="diganti")])
def test_approval_dicek_ulang_setelah_pull(kasus, approval_baru):
    kasus.b.berikut = approval_baru
    assert kasus.jalan() == 2
    assert "probe-recovery" in kasus.jejak
    assert "stop-lama" not in kasus.jejak


def test_migrasi_menolak_recovery_kontrak_berbeda_sebelum_stop(kasus):
    kasus.r.malformed['contract-recovery'] = 'e' * 64
    assert kasus.jalan() == 2
    assert 'stop' not in kasus.jejak
    assert kasus.r.current == 'lama' and kasus.r.running
    assert not kasus.b.consumed


def test_sukses_ordering_secret_dan_argv_tetap(kasus):
    assert kasus.jalan() == 0
    assert kasus.jejak == [
        "host", "lock", "config", "approval1", "disk",
        "pull-candidate", "image-candidate", "repo-candidate", "probe-candidate",
        "pull-recovery", "image-recovery", "repo-recovery", "probe-recovery",
        "contract-candidate", "contract-recovery",
        "state-lama", "image-lama", "disk", "approval2", "consume", "stop-lama", "rm-lama",
        "run-candidate", "state-candidate", "schema-candidate", "config-clean", "unlock",
    ]
    for argv, opsi in kasus.r.calls:
        assert argv[0] == "/usr/bin/docker"
        assert not any(x in argv for x in ("sh", "bash", "prune", "build", "latest"))
        assert RAHASIA not in repr(argv)
        if argv[1] == "run":
            assert argv[argv.index("--pull") + 1] == "never"
        if argv[1] == "run" and "--detach" in argv:
            assert opsi["env"]["DEEPSEEK_API_KEY"] == RAHASIA
            assert argv[argv.index("--publish") + 1] == "127.0.0.1:8724:8724"
            assert argv[argv.index("--memory") + 1] == "512m"
            assert argv[argv.index("--cpus") + 1] == "1"
            assert argv[argv.index("--user") + 1] == "10001:10001"
            assert "DEEPSEEK_MODEL=deepseek-flash" in argv
            assert "DEEPSEEK_VISION_MODEL=deepseek-flash" in argv
            assert not any(x.startswith(("OSN_HTTPS=", "OSN_DIREKTORI_LAMPIRAN=")) for x in argv)
            assert "PENDAMPING_AKTIF=1" in argv
            assert "DEEPSEEK_API_KEY" in argv
            assert argv.count("--env-file") == 2
        else:
            assert "DEEPSEEK_API_KEY" not in opsi["env"]
        if "--rm" in argv:
            assert "--network" in argv and "none" in argv
            assert "--mount" not in argv and "--env-file" not in argv
            assert opsi["input"] in (d.PROBE_IMAGE, d.PROBE_KONTRAK)
        if argv[1] == "exec":
            assert "-B" in argv and "-E" in argv
            assert opsi["input"] == d.PROBE_SKEMA


@pytest.mark.parametrize("tahap", ["stop-lama", "rm-lama"])
@pytest.mark.parametrize("timeout", [False, True])
def test_gagal_stop_hapus_awal_tidak_run_saingan(kasus, tahap, timeout):
    kasus.r.gagal = {tahap}
    kasus.r.raise_mode = timeout
    assert kasus.jalan() == 2
    assert not any(x.startswith("run-") for x in kasus.jejak)
    if tahap == "stop-lama":
        assert not any(a[1] == "rm" for a, _ in kasus.r.calls)
    assert "intervensi manual" in kasus.pesan[-1]


@pytest.mark.parametrize("tahap", ["run-candidate", "state-candidate", "schema-candidate"])
@pytest.mark.parametrize("timeout", [False, True])
def test_regresi_run_dan_health_gagal_harus_recovery_nonzero(kasus, tahap, timeout):
    kasus.r.gagal = {tahap}
    kasus.r.raise_mode = timeout
    assert kasus.jalan() == 1
    assert kasus.jejak.index("stop-candidate") < kasus.jejak.index("rm-candidate")
    assert kasus.jejak.index("rm-candidate") < kasus.jejak.index("run-recovery")
    assert "schema-recovery" in kasus.jejak
    assert "recovery sehat" in kasus.pesan[-1]
    runs = [(a, o) for a, o in kasus.r.calls if "--detach" in a]
    assert len(runs) == 2
    assert runs[0][0][:-1] == runs[1][0][:-1]
    assert runs[0][1] == runs[1][1]
    assert runs[1][0][-1] == d.REGISTRI + "@" + RECOVERY
    assert ID_LAMA not in runs[1][0]


def test_run_gagal_sebelum_create_recovery_tetap_jalan(kasus):
    kasus.r.gagal = {"run-candidate"}
    kasus.r.run_gagal_tanpa_create = True
    assert kasus.jalan() == 1
    assert "cleanup-list" in kasus.jejak
    assert "stop-candidate" not in kasus.jejak
    assert "run-recovery" in kasus.jejak


@pytest.mark.parametrize("tahap", ["cleanup-list", "stop-candidate", "rm-candidate",
                                   "run-recovery", "state-recovery", "schema-recovery"])
@pytest.mark.parametrize("timeout", [False, True])
def test_recovery_gagal_selalu_manual_tidak_mengaku_sukses(kasus, tahap, timeout):
    kasus.r.gagal = {"run-candidate", tahap}
    kasus.r.raise_mode = timeout
    assert kasus.jalan() == 2
    assert "intervensi manual" in kasus.pesan[-1]
    if tahap in {"cleanup-list", "stop-candidate", "rm-candidate"}:
        assert "run-recovery" not in kasus.jejak


@pytest.mark.parametrize("status,jalan", [("exited", "false"), ("restarting", "true"),
                                         ("dead", "false"), ("running", "false")])
def test_proses_early_exit_bukan_tunggu_timeout(kasus, status, jalan):
    kasus.r.proses["candidate"] = (status, jalan)
    assert kasus.jalan() == 1
    assert kasus.jam[0] == 100


@pytest.mark.parametrize("health", ["unhealthy", "missing", "starting"])
def test_health_docker_gagal_atau_timeout(kasus, health):
    kasus.r.health["candidate"] = health
    assert kasus.jalan() == 1
    if health == "starting":
        assert kasus.jam[0] >= 220


def test_http_candidate_timeout_lalu_recovery(kasus):
    assert kasus.jalan(http=lambda: kasus.r.current == "recovery") == 1
    assert kasus.jam[0] >= 220


def test_http_recovery_timeout_manual(kasus):
    kasus.r.gagal = {"run-candidate"}
    assert kasus.jalan(http=lambda: False) == 2
    assert "intervensi manual" in kasus.pesan[-1]


@pytest.mark.parametrize("tahap,nilai", [("schema-candidate", "OK"),
                                        ("state-candidate", "running|true|healthy|" + ID_LAMA)])
def test_health_wajib_skema_dan_image_tepat(kasus, tahap, nilai):
    kasus.r.malformed[tahap] = nilai
    assert kasus.jalan() == 1


def info_berkas(**tambahan):
    isi = dict(st_mode=stat.S_IFREG | 0o600, st_uid=0, st_nlink=1)
    isi.update(tambahan)
    return SimpleNamespace(**isi)


@pytest.mark.parametrize("perubahan", [
    {"st_uid": 10001}, {"st_mode": stat.S_IFREG | 0o644}, {"st_mode": stat.S_IFREG | 0o400},
    {"st_mode": stat.S_IFLNK | 0o600}, {"st_mode": stat.S_IFIFO | 0o600},
    {"st_mode": stat.S_IFDIR | 0o600}, {"st_nlink": 2},
])
def test_metadata_root0600_regular_satu_link(perubahan):
    with pytest.raises(d.Ditolak):
        d.metadata_privat(info_berkas(**perubahan))
    d.metadata_privat(info_berkas())


@pytest.fixture
def fstat_root(monkeypatch):
    asli = d.os.fstat

    def root(fd):
        info = asli(fd)
        return SimpleNamespace(**{nama: (0 if nama == "st_uid" else getattr(info, nama))
                                  for nama in dir(info) if nama.startswith("st_")})

    monkeypatch.setattr(d.os, "fstat", root)


def test_baca_privat_nofollow_batas_dan_permissions(tmp_path, fstat_root):
    path = tmp_path / "approval.json"
    path.write_text(approval())
    path.chmod(0o600)
    assert d.baca_privat(path) == approval()
    with pytest.raises(d.Ditolak):
        d.baca_privat(path, batas=3)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        d.baca_privat(link)
    path.chmod(0o644)
    with pytest.raises(d.Ditolak):
        d.baca_privat(path)


def test_lock_nonblocking_tidak_unlink_dan_release_exception(tmp_path, fstat_root, monkeypatch):
    path = tmp_path / "deploy.lock"
    monkeypatch.setattr(d, "LOCK", path)
    fs = d.Berkas()
    with pytest.raises(RuntimeError):
        with fs.kunci():
            with pytest.raises(BlockingIOError):
                with fs.kunci():
                    pytest.fail("Lock kedua harus ditolak")
            raise RuntimeError()
    assert path.exists()
    with fs.kunci():
        pass


def test_lock_symlink_ditolak(tmp_path, fstat_root, monkeypatch):
    asli = tmp_path / "real"
    asli.touch(mode=0o600)
    link = tmp_path / "lock"
    link.symlink_to(asli)
    monkeypatch.setattr(d, "LOCK", link)
    with pytest.raises(OSError):
        with d.Berkas().kunci():
            pytest.fail("Symlink harus ditolak")


@pytest.mark.parametrize("mode", [0o600, 0o644])
def test_snapshot_config_dua_envfile_key_privat(tmp_path, fstat_root, monkeypatch, mode):
    monkeypatch.setattr(d, "AKAR", tmp_path)
    paths = (tmp_path / "visual.conf", tmp_path / "pendamping.conf")
    key = tmp_path / "key"
    for path, isi in zip((*paths, key), ("OSN_VISUAL_KELUARGA=pola-bilangan\n",
                                        "PENDAMPING_AKTIF=1\n", RAHASIA + "\n")):
        path.write_text(isi)
        path.chmod(0o600 if path == key else mode)
    monkeypatch.setattr(d, "ENVFILES", paths)
    monkeypatch.setattr(d, "KUNCI", key)
    baca_asli = d.baca_privat

    def baca_live(path, *args, **kwargs):
        if path == key:
            assert kwargs == {"kunci": True}
            return RAHASIA + "\n"
        return baca_asli(path, *args, **kwargs)

    monkeypatch.setattr(d, "baca_privat", baca_live)
    with d.Berkas().konfigurasi() as (snapshots, env):
        assert env["DEEPSEEK_API_KEY"] == RAHASIA
        for asal, salin in zip(paths, snapshots):
            assert Path(salin).read_bytes() == asal.read_bytes()
            assert stat.S_IMODE(Path(salin).stat().st_mode) == 0o600
        assert stat.S_IMODE(Path(snapshots[0]).parent.stat().st_mode) == 0o700
        paths[0].write_text("diubah di tengah deploy")
        assert Path(snapshots[0]).read_text() != paths[0].read_text()
    assert all(not Path(path).exists() for path in snapshots)
    paths[1].unlink()
    with pytest.raises(OSError):
        with d.Berkas().konfigurasi():
            pytest.fail("Envfile kedua wajib readable")


@pytest.mark.parametrize("isi", ["", "a\nb", "a\rb", "a\x00b"])
def test_key_kosong_atau_multiline_ditolak(monkeypatch, isi):
    monkeypatch.setattr(d, "baca_privat", lambda path, *args, **kw: isi if path == d.KUNCI else "X=1")
    with pytest.raises(d.Ditolak):
        with d.Berkas().konfigurasi():
            pytest.fail("Key invalid harus ditolak sebelum snapshot")


@pytest.mark.parametrize("mode,uid,bavail,favail", [
    (0o710, 10001, 3 * 1024 ** 3, 9000),  # live group beda tetap sah
    (0o777, 10001, 3 * 1024 ** 3, 9000),
    (0o710, 0, 3 * 1024 ** 3, 9000),
    (0o610, 10001, 3 * 1024 ** 3, 9000),
    (0o710, 10001, 100, 9000), (0o710, 10001, 3 * 1024 ** 3, 10),
])
def test_data_permission_dan_ruang_inode(monkeypatch, mode, uid, bavail, favail):
    class DataPalsu:
        def lstat(self):
            return SimpleNamespace(st_mode=stat.S_IFDIR | mode, st_uid=uid)

    monkeypatch.setattr(d, "DATA", DataPalsu())
    dicek = []

    def statvfs(path):
        dicek.append(path)
        return SimpleNamespace(f_bavail=bavail, f_frsize=1, f_favail=favail)

    monkeypatch.setattr(d.os, "statvfs", statvfs)
    if mode == 0o710 and uid == 10001 and bavail > 2 * 1024 ** 3 and favail > 8192:
        d.Berkas().ruang()
        assert dicek == [d.DATA, d.DISK_DOCKER]
    else:
        with pytest.raises(d.Ditolak):
            d.Berkas().ruang()


@pytest.mark.parametrize("status,expected", [(401, True), (200, False), (303, False), (500, False)])
def test_http_hanya401_tanpa_proxy_redirect_body(monkeypatch, status, expected):
    handlers = []

    class Pembuka:
        def open(self, url, timeout):
            assert url == "http://127.0.0.1:8724/akun" and timeout == 3
            raise urllib.error.HTTPError(url, status, "sintetis", {}, io.BytesIO(b""))

    def buka(*args):
        handlers.extend(args)
        return Pembuka()

    monkeypatch.setattr(d.urllib.request, "build_opener", buka)
    assert d.akun_terjaga() is expected
    assert handlers[0].proxies == {}
    assert isinstance(handlers[1], d._TanpaRedirect)
    assert handlers[1].redirect_request(None, None, 303, "", {}, "http://invalid") is None


def test_cli_mengabaikan_env_injeksi_dan_menerima_wrapper_satu_argumen(monkeypatch):
    panggilan = []
    monkeypatch.setattr(d, "deploy", lambda teks: panggilan.append(teks) or 0)
    lingkungan = {"SSH_ORIGINAL_COMMAND": PERINTAH, "DOCKER_HOST": "tcp://evil",
                   "OSN_DATA": "/evil", "OSN_BYPASS": "1"}
    assert d.main([], lingkungan) == 0
    assert d.main([PERINTAH], {"SSH_ORIGINAL_COMMAND": "teks-lain"}) == 0
    assert panggilan == [PERINTAH, PERINTAH]
    assert d.main(["--approval", "/evil"], lingkungan) == 2
    assert panggilan == [PERINTAH, PERINTAH]


def test_cli_subprocess_request_injection_tanpa_docker(tmp_path):
    marker = tmp_path / "tidak-boleh-ada"
    hasil = subprocess.run(
        [sys.executable, "-B", str(AKAR / "scripts" / "deploy.py")],
        env={"SSH_ORIGINAL_COMMAND": PERINTAH + ";touch " + str(marker)},
        capture_output=True, text=True, timeout=10, check=False, shell=False,
    )
    assert hasil.returncode == 2
    assert "Preflight ditolak" in hasil.stdout
    assert hasil.stderr == ""
    assert not marker.exists()


@pytest.mark.parametrize("versi,ledger,expected", [(4, True, 0), (3, True, 1),
                                                  (5, True, 1), (4, False, 1)])
def test_script_health_sql_readonly_dengan_db_sintetis(tmp_path, versi, ledger, expected):
    # Paths hanya diganti dalam string probe yang dijalankan di proses Python sintetis.
    # Tidak import aplikasi sehingga tidak mungkin menjalankan startup/migrasi.
    schema = tmp_path / "assistant_schema.py"
    schema.write_text("VERSI_SKEMA = 4\nraise RuntimeError('jangan import')\n")
    ai_schema = tmp_path / "ai_store.py"
    ai_schema.write_text("VERSI_SKEMA = 2\nraise RuntimeError('jangan import')\n")
    (tmp_path / 'admin_store.py').write_text("VERSI_SKEMA = 4\nraise RuntimeError('jangan import')\n")
    privat = tmp_path / "pendamping.db"
    belajar = tmp_path / "latihan.db"
    ai = tmp_path / "ai-control.db"
    with sqlite3.connect(privat) as kon:
        kon.execute("PRAGMA user_version = " + str(versi))
        kon.execute("CREATE TABLE tinjauan_usulan (id TEXT)")
    with sqlite3.connect(belajar) as kon:
        kon.execute("CREATE TABLE sesi (id INTEGER)")
        kon.execute("CREATE TABLE operasi_admin_siswa (id TEXT)")
        if ledger:
            kon.execute("CREATE TABLE eksekusi_pendamping (id TEXT)")
    with sqlite3.connect(ai) as kon:
        kon.execute("PRAGMA user_version = 2")
        for tabel in ('ledger','audit_uji_admin','operasi_pengaturan_admin'):
            kon.execute('CREATE TABLE '+tabel+' (id TEXT)')
    (tmp_path/'transient').mkdir()
    for nama, v, tables in (
        ('admin-control.db',4,('konfigurasi_pendaftaran','operasi_admin','receipt_admin','batch_admin','batch_admin_item','kelompok_admin','kelompok_admin_item','penyerahan_admin','penyerahan_admin_item')),
        ('transient/admin-drafts.db',2,('draft_bulk','item_bulk','kelompok_bulk')),
    ):
        with sqlite3.connect(tmp_path/nama) as kon:
            kon.execute('PRAGMA user_version='+str(v))
            for tabel in tables:kon.execute('CREATE TABLE '+tabel+' (id TEXT)')
    (tmp_path/'sandi.json').write_text(json.dumps({'akun':[{'id_akun':'akun_'+'a'*32,'revisi_auth':0}]}))
    sebelum = (privat.read_bytes(), belajar.read_bytes(), ai.read_bytes())
    script = d.PROBE_SKEMA.replace(
        "akar_app = Path('/app')", "akar_app = Path(" + repr(str(tmp_path)) + ")"
    ).replace("/data/", str(tmp_path) + "/")
    hasil = subprocess.run([sys.executable, "-E", "-B", "-"], input=script,
                           capture_output=True, text=True, timeout=10, check=False, shell=False)
    assert hasil.returncode == expected
    assert (privat.read_bytes(), belajar.read_bytes(), ai.read_bytes()) == sebelum
    if expected == 0:
        assert hasil.stdout.strip() == "OSN_SCHEMA_ADMIN4_AI2_OK"
    else:
        assert "AssertionError" in hasil.stderr
    assert "mode=ro" in d.PROBE_SKEMA and "query_only = ON" in d.PROBE_SKEMA
    assert "siapkan" not in d.PROBE_SKEMA


def test_approval_io_memakai_fd_privat(tmp_path, fstat_root, monkeypatch):
    path = tmp_path / "approval.json"
    path.write_text(approval())
    path.chmod(0o600)
    monkeypatch.setattr(d, "APPROVAL", path)
    monkeypatch.setattr(d, "AKAR", tmp_path)
    monkeypatch.setattr(d, "LOCK", tmp_path / "lock")
    fs = d.Berkas()
    with fs.kunci():
        assert fs.approval(KANDIDAT, RECOVERY, 100)["schema_target"] == 4
        path.chmod(0o644)
        with pytest.raises(d.Ditolak):
            fs.approval(KANDIDAT, RECOVERY, 100)


@pytest.mark.parametrize("uid,mode,pemilik", [(10001, 0o755, 0), (0, 0o777, 0),
                                            (0, 0o755, 10001), (0, 0o755, 0)])
def test_host_root_direktori_tidak_writable_pihak_lain(monkeypatch, uid, mode, pemilik):
    monkeypatch.setattr(d.os, "geteuid", lambda: uid)
    monkeypatch.setattr(d.Path, "lstat", lambda self: SimpleNamespace(
        st_mode=stat.S_IFDIR | mode, st_uid=pemilik))
    if uid == 0 and mode == 0o755 and pemilik == 0:
        d.Berkas().periksa_host()
    else:
        with pytest.raises(d.Ditolak):
            d.Berkas().periksa_host()


def test_disk_setelah_pull_gagal_tidak_stop(kasus):
    asli = kasus.b.ruang

    def ruang():
        asli()
        if "probe-recovery" in kasus.jejak:
            raise OSError()

    kasus.b.ruang = ruang
    assert kasus.jalan() == 2
    assert "stop-lama" not in kasus.jejak


def test_expiry_waktu_habis_selama_pull(kasus):
    asli = kasus.b.ruang

    def ruang():
        asli()
        if "probe-recovery" in kasus.jejak:
            kasus.jam[0] = 201

    kasus.b.ruang = ruang
    assert kasus.jalan() == 2
    assert "stop-lama" not in kasus.jejak


@pytest.mark.parametrize("jawaban", ['"container-lain"', 'invalid-json'])
def test_cleanup_daftar_tidak_pasti_jangan_run_recovery(kasus, jawaban):
    kasus.r.gagal = {"run-candidate"}
    kasus.r.malformed["cleanup-list"] = jawaban
    assert kasus.jalan() == 2
    assert "run-recovery" not in kasus.jejak


def test_probe_cleanup_gagal_tetap_preflight(kasus):
    kasus.r.gagal = {"probe-candidate", "probe-cleanup"}
    assert kasus.jalan() == 2
    assert "probe-cleanup" in kasus.jejak
    assert "stop-lama" not in kasus.jejak


@pytest.mark.parametrize("jenis", [KeyboardInterrupt, InterruptedError, OSError])
def test_interupsi_candidate_tetap_mencoba_recovery(kasus, jenis):
    def http():
        if kasus.r.current == "candidate":
            raise jenis()
        return True

    assert kasus.jalan(http=http) == 1
    assert "run-recovery" in kasus.jejak


@pytest.mark.parametrize("status,health", [("exited", "healthy"), ("running", "unhealthy"),
                                          ("running", "starting")])
def test_recovery_exit_atau_health_gagal_manual(kasus, status, health):
    kasus.r.gagal = {"run-candidate"}
    kasus.r.proses["recovery"] = (status, "true" if status == "running" else "false")
    kasus.r.health["recovery"] = health
    assert kasus.jalan() == 2
    assert "intervensi manual" in kasus.pesan[-1]


def test_health_starting_kemudian_healthy(kasus):
    kasus.r.health["candidate"] = "starting"
    asli = kasus.r.image_id

    def image_id(nama):
        if nama == "candidate" and kasus.jam[0] > 105:
            kasus.r.health["candidate"] = "healthy"
        return asli(nama)

    kasus.r.image_id = image_id
    assert kasus.jalan() == 0
    assert kasus.jam[0] > 105


def test_environment_host_tidak_bocor_ke_docker(kasus, monkeypatch):
    for nama in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "HTTP_PROXY",
                 "PYTHONPATH", "PYTHONOPTIMIZE", "DEEPSEEK_API_KEY"):
        monkeypatch.setenv(nama, "nilai-injeksi-sintetis")
    assert kasus.jalan() == 0
    for _, opsi in kasus.r.calls:
        assert "nilai-injeksi-sintetis" not in repr(opsi["env"])


def test_probe_image_synthetic_subprocess_python_saja(tmp_path):
    script = ("import sys\nsys.path.insert(0, " + repr(str(AKAR / "mesin")) + ")\n" +
              d.PROBE_IMAGE.replace("/data/", str(tmp_path) + "/"))
    hasil = subprocess.run([sys.executable, "-E", "-B", "-"], input=script,
                           cwd=tmp_path, capture_output=True, text=True,
                           timeout=30, check=False, shell=False)
    assert hasil.returncode == 0, hasil.stderr
    assert hasil.stdout.strip() == "OSN_IMAGE_ADMIN4_AI2_OK"
    assert (tmp_path / "latihan.db").exists()
    assert (tmp_path / "pendamping.db").exists()
    assert (tmp_path / "ai-control.db").exists()


@pytest.mark.parametrize('fault', ['admin', 'ai', 'auth', 'receipt', 'transient'])
def test_probe_image_menolak_kontrak_admin_rusak(tmp_path, fault):
    sumber = tmp_path / 'source'
    import shutil
    shutil.copytree(AKAR / 'mesin', sumber, ignore=shutil.ignore_patterns(
        '.git', '.venv', '__pycache__', '__tests__', '*.db*', '*sandi*.json', 'sesi.json', 'cadangan', 'lembar'))
    nama, lama, baru = {
        'admin': ('admin_store.py', 'VERSI_SKEMA = 4', 'VERSI_SKEMA = 3'),
        'ai': ('ai_store.py', 'VERSI_SKEMA = 2', 'VERSI_SKEMA = 1'),
        'auth': ('auth.py', 'def naikkan_revisi_auth(', 'def naikkan_revisi_auth_rusak('),
        'receipt': ('admin_students.py', 'CREATE TABLE IF NOT EXISTS operasi_admin_siswa', 'CREATE TABLE IF NOT EXISTS receipt_rusak'),
        'transient': ('admin_bulk.py', 'VERSI_TRANSIENT = 2', 'VERSI_TRANSIENT = 1'),
    }[fault]
    p = sumber / nama
    text = p.read_text(); assert lama in text; p.write_text(text.replace(lama, baru, 1))
    script = "import sys\nsys.path.insert(0," + repr(str(sumber)) + ")\n" + d.PROBE_IMAGE.replace('/data/', str(tmp_path / 'data') + '/')
    hasil = subprocess.run([sys.executable, '-B', '-'], input=script, cwd=tmp_path,
                           capture_output=True, text=True, timeout=30)
    assert hasil.returncode != 0
    assert 'OSN_IMAGE_ADMIN4_AI2_OK' not in hasil.stdout


def test_health_db_hilang_tidak_dibuat(tmp_path):
    schema = tmp_path / "assistant_schema.py"
    schema.write_text("VERSI_SKEMA = 4\n")
    ai_schema = tmp_path / "ai_store.py"
    ai_schema.write_text("VERSI_SKEMA = 2\n")
    (tmp_path/'admin_store.py').write_text("VERSI_SKEMA = 4\n")
    script = d.PROBE_SKEMA.replace(
        "akar_app = Path('/app')", "akar_app = Path(" + repr(str(tmp_path)) + ")"
    ).replace("file:/data/", "file:" + str(tmp_path) + "/")
    hasil = subprocess.run([sys.executable, "-E", "-B", "-"], input=script,
                           capture_output=True, text=True, timeout=10, check=False, shell=False)
    assert hasil.returncode != 0
    assert not list(tmp_path.glob("*.db"))


def test_http_koneksi_gagal_false(monkeypatch):
    class Pembuka:
        def open(self, url, timeout):
            raise urllib.error.URLError("sintetis")

    monkeypatch.setattr(d.urllib.request, "build_opener", lambda *args: Pembuka())
    assert d.akun_terjaga() is False


@pytest.mark.parametrize("field", ["approval_id", "issued", "deployer_sha256"])
def test_approval_field_baru_wajib(kasus, field):
    isi = json.loads(approval())
    del isi[field]
    kasus.b.isi = json.dumps(isi)
    assert kasus.jalan() == 2
    assert kasus.r.calls == []


def test_approval_ttl_batas_dan_clock_invalid():
    assert d.MAKS_TTL_APPROVAL == 900
    assert d.validasi_approval(approval(expires=1000), KANDIDAT, RECOVERY, 100)
    for jam in (99, 1000, float("inf"), float("nan")):
        with pytest.raises(d.Ditolak):
            d.validasi_approval(approval(expires=1000), KANDIDAT, RECOVERY, jam)


def test_hash_deployer_adalah_byte_source_bukan_input(monkeypatch, tmp_path):
    import hashlib
    asli = (AKAR / "scripts/deploy.py").read_bytes()
    assert d.hash_deployer() == hashlib.sha256(asli).hexdigest()
    record = approval()
    path = tmp_path / "deployer-synthetic.py"
    path.write_bytes(asli + b"\n# perubahan synthetic\n")
    monkeypatch.setattr(d, "__file__", str(path))
    with pytest.raises(d.Ditolak):
        d.validasi_approval(record, KANDIDAT, RECOVERY, 100)


@pytest.fixture
def fs_approval(tmp_path, fstat_root, monkeypatch):
    monkeypatch.setattr(d, "AKAR", tmp_path)
    monkeypatch.setattr(d, "APPROVAL", tmp_path / "approval.json")
    monkeypatch.setattr(d, "LOCK", tmp_path / "lock")
    d.APPROVAL.write_text(approval())
    d.APPROVAL.chmod(0o600)

    class FilesystemSintetis(d.Berkas):
        # Approval, lock, receipt memakai I/O source sebenarnya pada tmp_path.
        def periksa_host(self):
            pass

        def ruang(self):
            pass

        @contextlib.contextmanager
        def konfigurasi(self):
            yield (), dict(d.LINGKUNGAN, DEEPSEEK_API_KEY=RAHASIA)

    return FilesystemSintetis()


def jalan_fs(fs, runner):
    return d.deploy(PERINTAH, docker=d.Docker(runner), berkas=fs,
                    sekarang=lambda: 100, monotonic=lambda: 100,
                    tidur=lambda _: None, http=lambda: True, lapor=lambda _: None)


@pytest.mark.parametrize("gagal,expected", [([], 0), (["run-candidate"], 1),
    (["stop-lama"], 2), (["rm-lama"], 2), (["run-candidate", "run-recovery"], 2)])
def test_receipt_nyata_one_shot_semua_outcome(fs_approval, gagal, expected):
    record = d.APPROVAL.read_bytes()
    runner = RunnerPalsu([])
    runner.gagal = set(gagal)
    assert jalan_fs(fs_approval, runner) == expected
    jejak = []
    kedua = RunnerPalsu(jejak)
    assert jalan_fs(fs_approval, kedua) == 2
    assert kedua.calls == []  # replay bahkan tidak boleh pull/probe
    receipt = fs_approval.receipt(json.loads(record))
    assert receipt.exists()
    isi = json.loads(receipt.read_text())
    assert isi == {"approval": json.loads(record), "consumed": 100}
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600
    assert d.APPROVAL.read_bytes() == record  # tidak unlink/revoke approval secara otomatis
    # Root mengganti backup saja tidak me-reset approval_id yang sudah consumed.
    d.APPROVAL.write_text(approval(backup_pair="baru"))
    assert jalan_fs(fs_approval, kedua) == 2
    assert kedua.calls == []


def test_receipt_fsync_file_dan_parent_sebelum_stop_dengan_lock(fs_approval, monkeypatch):
    jejak = []
    runner = RunnerPalsu(jejak)
    sync = d.os.fsync

    def fsync(fd):
        assert fs_approval._lock_fd is not None
        jejak.append("sync-dir" if stat.S_ISDIR(d.os.fstat(fd).st_mode) else "sync-file")
        return sync(fd)

    monkeypatch.setattr(d.os, "fsync", fsync)
    assert jalan_fs(fs_approval, runner) == 0
    assert jejak.index("sync-file") < jejak.index("sync-dir") < jejak.index("stop-lama")


def test_expiry_selama_fsync_tetap_hangus_tanpa_stop(fs_approval, monkeypatch):
    jam = [100]
    asli = d.os.fsync

    def fsync(fd):
        asli(fd)
        jam[0] = 200

    monkeypatch.setattr(d.os, "fsync", fsync)
    runner = RunnerPalsu([])
    assert d.deploy(PERINTAH, docker=d.Docker(runner), berkas=fs_approval,
                    sekarang=lambda: jam[0], monotonic=lambda: jam[0],
                    http=lambda: True, tidur=lambda _: None, lapor=lambda _: None) == 2
    assert "stop-lama" not in runner.jejak
    assert fs_approval.receipt(json.loads(approval())).exists()


@pytest.mark.parametrize("nomor", [1, 2])
def test_receipt_gagal_durability_tidak_stop_tetap_bakar_approval(fs_approval, monkeypatch, nomor):
    calls = []

    def fsync(fd):
        calls.append(fd)
        if len(calls) == nomor:
            raise OSError("synthetic fsync failure")

    monkeypatch.setattr(d.os, "fsync", fsync)
    runner = RunnerPalsu([])
    assert jalan_fs(fs_approval, runner) == 2
    assert "stop-lama" not in runner.jejak
    assert fs_approval.receipt(json.loads(approval())).exists()
    kedua = RunnerPalsu([])
    assert jalan_fs(fs_approval, kedua) == 2
    assert kedua.calls == []


@pytest.mark.parametrize("jenis", ["regular", "symlink", "directory", "empty"])
def test_receipt_existing_apapun_ditolak_sebelum_docker(fs_approval, jenis):
    path = fs_approval.receipt(json.loads(approval()))
    if jenis == "symlink":
        path.symlink_to(d.AKAR / "absent")
    elif jenis == "directory":
        path.mkdir()
    else:
        path.write_text("" if jenis == "empty" else "consumed")
    runner = RunnerPalsu([])
    assert jalan_fs(fs_approval, runner) == 2
    assert runner.calls == []


def test_receipt_exclusive_create_race_tidak_truncate_atau_stop(fs_approval, monkeypatch):
    path = fs_approval.receipt(json.loads(approval()))
    asli = d.os.open

    def buka(p, flags, *args, **kw):
        if p == path:
            path.write_text("receipt-pihak-lain")  # sesudah recheck, sebelum O_EXCL
            path.chmod(0o600)  # sah metadata; harus gagal karena exclusive, bukan mode
        return asli(p, flags, *args, **kw)

    monkeypatch.setattr(d.os, "open", buka)
    runner = RunnerPalsu([])
    assert jalan_fs(fs_approval, runner) == 2
    assert "stop-lama" not in runner.jejak
    assert path.read_text() == "receipt-pihak-lain"


def test_approval_dan_konsumsi_wajib_lock(fs_approval):
    isi = json.loads(approval())
    with pytest.raises(d.Ditolak):
        fs_approval.approval(KANDIDAT, RECOVERY, 100)
    with pytest.raises(d.Ditolak):
        fs_approval.konsumsi(isi, 100)
    assert not fs_approval.receipt(isi).exists()


@pytest.mark.parametrize("perubahan,jam", [({"backup_pair": "berubah"}, 100),
    ({"deployer_sha256": "a" * 64}, 100), ({"issued": 101}, 100), ({}, 200)])
def test_konsumsi_revalidasi_record_dan_waktu(fs_approval, perubahan, jam):
    with fs_approval.kunci():
        isi = fs_approval.approval(KANDIDAT, RECOVERY, 100)
        d.APPROVAL.write_text(approval(**perubahan))
        with pytest.raises(d.Ditolak):
            fs_approval.konsumsi(isi, jam)
    assert not fs_approval.receipt(isi).exists()


def test_lock_nyata_tetap_di_docker_hingga_recovery(fs_approval):
    runner = RunnerPalsu([])
    runner.gagal = {"run-candidate"}

    def locked(argv, **kw):
        assert fs_approval._lock_fd is not None
        with pytest.raises(BlockingIOError):
            with d.Berkas().kunci():
                pytest.fail("Deploy saingan tidak boleh mengambil lock")
        return runner(argv, **kw)

    assert jalan_fs(fs_approval, locked) == 1
    assert "schema-recovery" in runner.jejak
    assert fs_approval._lock_fd is None


def test_preflight_gagal_belum_membakar_approval(fs_approval):
    runner = RunnerPalsu([])
    runner.gagal = {"pull-recovery"}
    assert jalan_fs(fs_approval, runner) == 2
    assert not fs_approval.receipt(json.loads(approval())).exists()
    assert jalan_fs(fs_approval, RunnerPalsu([])) == 0


@pytest.mark.parametrize("status,jalan,sah", [("exited", "false", True),
    ("running", "true", True), ("exited", "true", False), ("running", "false", False),
    ("dead", "false", False), ("created", "false", False), ("paused", "true", False),
    ("restarting", "true", False)])
def test_current_container_stopped_untuk_b2(kasus, status, jalan, sah):
    kasus.r.proses["lama"] = (status, jalan)
    kasus.r.running = jalan == "true"
    assert kasus.jalan() == (0 if sah else 2)
    if sah:
        assert kasus.jejak.index("probe-recovery") < kasus.jejak.index("stop-lama")
        assert kasus.jejak.index("consume") < kasus.jejak.index("stop-lama")
    else:
        assert "consume" not in kasus.jejak
        assert "stop-lama" not in kasus.jejak


@pytest.mark.parametrize("mode,uid,nlink", [(0o664, 0, 1), (0o646, 0, 1),
    (0o644, 10001, 1), (0o644, 0, 2), (0o755, 0, 1), (0o4644, 0, 1)])
def test_config_permission_tidak_aman_ditolak(mode, uid, nlink):
    with pytest.raises(d.Ditolak):
        d.metadata_config(info_berkas(st_mode=stat.S_IFREG | mode, st_uid=uid, st_nlink=nlink))


def test_config_644_symlink_dan_key_644_tetap_ditolak(tmp_path, fstat_root):
    path = tmp_path / "config"
    path.write_text("X=1")
    path.chmod(0o644)
    assert d.baca_privat(path, config=True) == "X=1"
    with pytest.raises(d.Ditolak):
        d.baca_privat(path)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        d.baca_privat(link, config=True)


@pytest.mark.parametrize("uid,gid,mode,nlink,sah", [
    (10001, 10002, 0o640, 1, True),
    (0, 10002, 0o640, 1, False),
    (10001, 0, 0o640, 1, False),
    (10001, 10002, 0o600, 1, False),
    (10001, 10002, 0o644, 1, False),
    (10001, 10002, 0o640, 2, False),
])
def test_metadata_kunci_live_dibatasi_owner_grup_mode(uid, gid, mode, nlink, sah):
    info = info_berkas(st_uid=uid, st_gid=gid,
                       st_mode=stat.S_IFREG | mode, st_nlink=nlink)
    if sah:
        d.metadata_kunci(info)
    else:
        with pytest.raises(d.Ditolak):
            d.metadata_kunci(info)


def test_baca_kunci_memilih_kontrak_khusus(monkeypatch, tmp_path):
    path = tmp_path / "key"
    path.write_text(RAHASIA)
    path.chmod(0o640)
    asli = d.os.fstat

    def milik_live(fd):
        info = asli(fd)
        return SimpleNamespace(**{nama: (
            10001 if nama == "st_uid" else 10002 if nama == "st_gid"
            else getattr(info, nama)
        ) for nama in dir(info) if nama.startswith("st_")})

    monkeypatch.setattr(d.os, "fstat", milik_live)
    assert d.baca_privat(path, kunci=True) == RAHASIA
    with pytest.raises(d.Ditolak):
        d.baca_privat(path)
    with pytest.raises(d.Ditolak):
        d.baca_privat(path, config=True, kunci=True)


def test_env_tetap_known_live_tanpa_semantic_baru():
    assert set(d.ENV_TETAP) == {
        "OSN_BERKAS_SANDI=/data/sandi.json", "OSN_BERKAS_SESI=/data/sesi.json",
        "OSN_BERKAS_DB=/data/latihan.db", "PENDAMPING_BERKAS_DB=/data/pendamping.db",
        "AI_BERKAS_DB=/data/ai-control.db", "OSN_FOLDER_LEMBAR=/data/lembar",
        "ADMIN_BERKAS_DB=/data/admin-control.db", "ADMIN_TRANSIENT_DB=/data/transient/admin-drafts.db",
        "PENDAMPING_AKTIF=1",
        "DEEPSEEK_MODEL=deepseek-flash", "DEEPSEEK_VISION_MODEL=deepseek-flash",
        "PYTHONDONTWRITEBYTECODE=1", "PYTHONUNBUFFERED=1",
    }


def test_probe_unik_per_invocation_dan_label_bukan_nama_tetap(kasus):
    assert kasus.jalan() == 0
    probes = [a for a, _ in kasus.r.calls if "--rm" in a]
    names = [a[a.index("--name") + 1] for a in probes]
    assert len(set(names)) == 4  # Dua probe image + dua fingerprint recovery.
    for a, nama in zip(probes, names):
        assert nama.startswith(d.PROBE + "-") and nama != d.PROBE
        assert a[a.index("--label") + 1] == d.LABEL_PROBE + "=" + nama[len(d.PROBE) + 1:]


@pytest.mark.parametrize("timeout", [False, True])
def test_probe_cleanup_own_id_bukan_nama(kasus, timeout):
    kasus.r.gagal = {"probe-candidate"}
    kasus.r.raise_mode = timeout
    assert kasus.jalan() == 2
    hapus = [a for a, _ in kasus.r.calls if a[1] == "rm"]
    assert hapus == [[d.DOCKER, "rm", "--force", kasus.r.probe_id]]
    assert kasus.jejak.index("probe-owner") < kasus.jejak.index("probe-cleanup")
    assert "stop-lama" not in kasus.jejak


@pytest.mark.parametrize("label,nilai", [("probe-owner", "/other|different-owner"),
    ("probe-owner", "/osn-deploy-probe|missing"), ("probe-list", ""),
    ("probe-list", "garbage"), ("probe-list", "f" * 64 + "\n" + "e" * 64)])
def test_probe_collision_atau_daftar_tidak_pasti_jangan_hapus(kasus, label, nilai):
    kasus.r.gagal = {"probe-candidate"}
    kasus.r.malformed[label] = nilai
    assert kasus.jalan() == 2
    assert not any(a[1] in ("rm", "stop") for a, _ in kasus.r.calls)


@pytest.mark.parametrize("field", [0, 1])
def test_probe_ownership_keduanya_wajib_cocok(kasus, field):
    kasus.r.gagal = {"probe-candidate"}

    def runner(argv, **kw):
        hasil = kasus.r(argv, **kw)
        if kasus.jejak[-1] == "probe-owner":
            bagian = hasil.stdout.split("|")
            bagian[field] = "bukan-milik-invocation"
            hasil.stdout = "|".join(bagian)
        return hasil

    assert d.deploy(PERINTAH, docker=d.Docker(runner), berkas=kasus.b,
                    sekarang=lambda: 100, lapor=kasus.pesan.append) == 2
    assert not any(a[1] in ("rm", "stop") for a, _ in kasus.r.calls)


@pytest.mark.parametrize("label", ["probe-list", "probe-owner"])
def test_probe_cleanup_daemon_gagal_jangan_hapus(kasus, label):
    kasus.r.gagal = {"probe-candidate", label}
    assert kasus.jalan() == 2
    assert not any(a[1] in ("rm", "stop") for a, _ in kasus.r.calls)
