"""Palang verifier image dengan Docker palsu dan probe stdlib tanpa Docker nyata."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
BERKAS = ROOT / 'scripts' / 'verify_release_image.py'
IMAGE = 'ghcr.io/clarinovist/osn-mesin-latihan@sha256:' + 'a' * 64
REVISION = 'b' * 40
RECOVERY_REVISION = 'bc9c973b50eb1fb04edd37df62f71ba0123f29c6'


@pytest.fixture
def verifier():
    spesifikasi = importlib.util.spec_from_file_location('verifier_rilis_uji', BERKAS)
    modul = importlib.util.module_from_spec(spesifikasi)
    spesifikasi.loader.exec_module(modul)
    return modul


def metadata(revision=REVISION):
    # Config ID sengaja BUKAN digest manifest; keduanya tidak boleh tertukar.
    return [{'Id': 'sha256:' + 'c' * 64, 'RepoDigests': [IMAGE],
             'Config': {'Labels': {'org.opencontainers.image.revision': revision},
                        'Volumes': {'/data': {}}}}]


def docker_palsu(monkeypatch, verifier, *, inspect=None, run=None,
                 revision=REVISION):
    panggilan = []
    def jalankan(argv, **opsi):
        panggilan.append((argv, opsi))
        assert opsi['shell'] is False
        assert opsi['capture_output'] is True
        assert opsi['check'] is False
        assert opsi['text'] is True
        assert isinstance(argv, list)
        if argv[:3] == ['docker', 'image', 'inspect']:
            return subprocess.CompletedProcess(argv, 0, json.dumps(metadata(revision) if inspect is None else inspect), '')
        if argv[:3] == ['docker', 'container', 'rm']:
            return subprocess.CompletedProcess(argv, 0, '', '')
        assert argv[:2] == ['docker', 'run']
        if isinstance(run, BaseException):
            raise run
        return run or subprocess.CompletedProcess(argv, 0, json.dumps(verifier.RINGKASAN), '')
    monkeypatch.setattr(verifier.subprocess, 'run', jalankan)
    return panggilan


def test_digest_dan_argv_terkunci_tanpa_mount_host(verifier, monkeypatch):
    panggilan = docker_palsu(monkeypatch, verifier)
    hasil = verifier.verifikasi(IMAGE, REVISION)
    assert hasil == {
        'ok': True, 'image': IMAGE, 'revision': REVISION,
        'probe': verifier.ringkasan_untuk_revision(REVISION),
    }
    assert len(panggilan) == 2
    assert panggilan[0][0] == ['docker', 'image', 'inspect', IMAGE]
    argv, opsi = panggilan[1]
    nama = argv[argv.index('--name') + 1]
    assert nama.startswith('osn-release-probe-')
    assert argv == [
        'docker', 'run', '--rm', '--interactive', '--pull', 'never', '--name', nama,
        '--network', 'none', '--read-only', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--user', '10001:10001',
        '--tmpfs', '/data:rw,uid=10001,gid=10001', '--tmpfs', '/tmp',
        '--env', 'TMPDIR=/data', '--env', 'OSN_RELEASE_REVISION=' + REVISION,
        '--no-healthcheck', '--workdir', '/app',
        '--entrypoint', 'python', IMAGE, '-B', '-',
    ]
    assert opsi['input'] == verifier.SUMBER_PROBE
    assert opsi['timeout'] == 180
    assert panggilan[0][1]['timeout'] == 30


def test_verifier_recovery_memilih_kontrak_pinned_dan_meneruskan_revision(
    verifier, monkeypatch,
):
    ringkasan = verifier.ringkasan_untuk_revision(RECOVERY_REVISION)
    panggilan = docker_palsu(
        monkeypatch, verifier, revision=RECOVERY_REVISION,
        run=subprocess.CompletedProcess([], 0, json.dumps(ringkasan), ""),
    )
    hasil = verifier.verifikasi(IMAGE, RECOVERY_REVISION)
    assert hasil["probe"]["http_contract"] == verifier.KONTRAK_RECOVERY_LEGACY
    argv = panggilan[1][0]
    assert "OSN_RELEASE_REVISION=" + RECOVERY_REVISION in argv


@pytest.mark.parametrize('image,revision', [
    (IMAGE.replace('@sha256:', ':sha-'), REVISION),
    (IMAGE.split('@')[0] + ':latest', REVISION),
    (IMAGE.replace('clarinovist', 'asing'), REVISION),
    (IMAGE.replace('ghcr.io', 'docker.io'), REVISION),
    (IMAGE.replace('@sha256:', ':tag@sha256:'), REVISION),
    (IMAGE.upper(), REVISION), (IMAGE + '\n', REVISION),
    (IMAGE[:-1], REVISION), ('--privileged', REVISION),
    (IMAGE, REVISION[:7]), (IMAGE, REVISION.upper()),
    (IMAGE, REVISION + '; echo data'), (IMAGE, REVISION + '\n'),
])
def test_rujukan_tidak_sah_tidak_memanggil_docker(verifier, monkeypatch, image, revision):
    panggilan = docker_palsu(monkeypatch, verifier)
    with pytest.raises(verifier.GalatVerifikasi):
        verifier.verifikasi(image, revision)
    assert panggilan == []


@pytest.mark.parametrize('perubahan', ['revision', 'digest', 'digest_string', 'config_id', 'label_hilang', 'volume', 'dua', 'null'])
def test_inspect_salah_menolak_sebelum_run(verifier, monkeypatch, perubahan):
    data = metadata()
    if perubahan == 'revision':
        data[0]['Config']['Labels']['org.opencontainers.image.revision'] = 'd' * 40
    elif perubahan == 'digest':
        data[0]['RepoDigests'] = [IMAGE.replace('a' * 64, 'c' * 64)]
    elif perubahan == 'digest_string':
        data[0]['RepoDigests'] = IMAGE
    elif perubahan == 'config_id':
        data[0]['Id'] = IMAGE
    elif perubahan == 'label_hilang':
        data[0]['Config']['Labels'] = None
    elif perubahan == 'volume':
        data[0]['Config']['Volumes']['/app'] = {}
    elif perubahan == 'dua':
        data *= 2
    else:
        data = {}
    panggilan = docker_palsu(monkeypatch, verifier, inspect=data)
    with pytest.raises(verifier.GalatVerifikasi, match='identitas_image_tidak_cocok'):
        verifier.verifikasi(IMAGE, REVISION)
    assert len(panggilan) == 1


@pytest.mark.parametrize('isi', [
    '', 'bukan-json-sintetis', '[]', '{}', '{"ok": true}',
    '{"ok": false, "kode": "detail-sintetis"}',
])
def test_ringkasan_tidak_lengkap_bukan_lulus(verifier, monkeypatch, capsys, isi):
    docker_palsu(monkeypatch, verifier,
                 run=subprocess.CompletedProcess([], 0, isi, 'stderr-sintetis'))
    assert verifier.main(['--image', IMAGE, '--revision', REVISION]) == 1
    tangkapan = capsys.readouterr()
    assert json.loads(tangkapan.out) == {'ok': False, 'kode': 'ringkasan_tidak_sah'}
    assert tangkapan.err == ''


@pytest.mark.parametrize('ubah', [{'provider_calls': 1}, {'http_checks': 0}, {'skema': 3},
                                   {'skenario_tindakan': 0}, {'records': ['rahasia-sintetis']},
                                   {'ok': 1}, {'provider_calls': False},
                                   {'profil_checks': 0}, {'profil_checks': True},
                                   {'admin_schema': 4}, {'admin_schema': None}])
def test_ringkasan_harus_exact_dan_tidak_mengeluarkan_record(verifier, monkeypatch, capsys, ubah):
    docker_palsu(monkeypatch, verifier, run=subprocess.CompletedProcess(
        [], 0, json.dumps({**verifier.RINGKASAN, **ubah}), ''))
    assert verifier.main(['--image', IMAGE, '--revision', REVISION]) == 1
    tangkapan = capsys.readouterr()
    assert json.loads(tangkapan.out) == {'ok': False, 'kode': 'ringkasan_tidak_sah'}
    assert tangkapan.err == ''


def test_inspect_gagal_tidak_run_dan_output_aman(verifier, monkeypatch, capsys):
    panggilan = []
    def gagal(argv, **opsi):
        panggilan.append(argv)
        return subprocess.CompletedProcess(argv, 1, 'record-sintetis', 'record-sintetis')
    monkeypatch.setattr(verifier.subprocess, 'run', gagal)
    assert verifier.main(['--image', IMAGE, '--revision', REVISION]) == 1
    assert panggilan == [['docker', 'image', 'inspect', IMAGE]]
    tangkapan = capsys.readouterr()
    assert json.loads(tangkapan.out) == {'ok': False, 'kode': 'inspect_gagal'}
    assert tangkapan.err == ''


def test_cli_sukses_hanya_json_agregat(verifier, monkeypatch, capsys):
    docker_palsu(monkeypatch, verifier)
    assert verifier.main(['--image', IMAGE, '--revision', REVISION]) == 0
    tangkapan = capsys.readouterr()
    assert json.loads(tangkapan.out) == {
        'ok': True, 'image': IMAGE, 'revision': REVISION,
        'probe': verifier.ringkasan_untuk_revision(REVISION),
    }
    assert tangkapan.err == ''


def test_gagal_run_dan_timeout_membersihkan_hanya_container_sendiri(verifier, monkeypatch, capsys):
    for kegagalan in (subprocess.CompletedProcess([], 9, 'detail-sintetis', 'detail-sintetis'),
                      subprocess.TimeoutExpired(['docker', 'run'], 180, output='detail-sintetis'),
                      OSError('detail-sintetis')):
        panggilan = docker_palsu(monkeypatch, verifier, run=kegagalan)
        assert verifier.main(['--image', IMAGE, '--revision', REVISION]) == 1
        argv = panggilan[1][0]
        nama = argv[argv.index('--name') + 1]
        assert panggilan[-1][0] == ['docker', 'container', 'rm', '--force', nama]
        tangkapan = capsys.readouterr()
        assert 'detail-sintetis' not in tangkapan.out
        assert json.loads(tangkapan.out)['ok'] is False
        assert tangkapan.err == ''


@pytest.mark.parametrize('argv', [[], ['--image', 'rahasia-sintetis'],
                                  ['--unknown', 'rahasia-sintetis'],
                                  ['--image', IMAGE, '--revision', 'rahasia-sintetis']])
def test_cli_galat_tidak_echo_argumen(verifier, monkeypatch, capsys, argv):
    panggilan = docker_palsu(monkeypatch, verifier)
    assert verifier.main(argv) == 1
    tangkapan = capsys.readouterr()
    assert json.loads(tangkapan.out)['ok'] is False
    assert 'rahasia-sintetis' not in tangkapan.out
    assert tangkapan.err == ''
    assert panggilan == []


def jalankan_probe(tmp_path, sumber=ROOT / 'mesin', *, revision=REVISION,
                   injeksi='', diagnostik=False):
    """Interpreter baru menjalankan exec probe; tidak ada Docker atau impor DB host."""
    # PYTHONPATH hanya source salinan; env tidak mewarisi credential/proxy host.
    peluncur = (
        'import importlib.util\n'
        's = importlib.util.spec_from_file_location("verifier", ' + repr(str(BERKAS)) + ')\n'
        'm = importlib.util.module_from_spec(s)\n'
        's.loader.exec_module(m)\n'
        'ruang = {"__name__": "probe_uji"}\n'
        'exec(compile(m.SUMBER_PROBE, "<probe>", "exec"), ruang)\n'
        + injeksi + '\n' + (
            'import tempfile\n'
            'from pathlib import Path\n'
            'with tempfile.TemporaryDirectory() as t:\n'
            '    try: ruang["jalankan_probe"](Path(t))\n'
            '    except Exception as e:\n'
            '        print(str(e) if type(e) is RuntimeError and str(e) in ' + repr({
                'skema_bukan_v4', 'sesi_ganda', 'guard_tidak_menolak',
                'aset_hilang', 'provider_dilarang', 'dns_dilarang',
                'network_dilarang', 'http_redirect_candidate',
                'http_inline_frame_candidate', 'http_status', 'http_frame',
            }) + ' else "galat_tidak_dikenal")\n'
            '        raise SystemExit(1)\n'
            if diagnostik else 'raise SystemExit(ruang["main"]())\n'
        )
    )
    return subprocess.run([sys.executable, '-B', '-c', peluncur],
        env={'PYTHONPATH': str(sumber), 'TMPDIR': str(tmp_path),
             'PYTHONDONTWRITEBYTECODE': '1', 'OSN_RELEASE_REVISION': revision},
        cwd=str(tmp_path), capture_output=True, text=True, timeout=90, shell=False, check=False)


def test_probe_sintetis_migrasi_ledger_http_tanpa_docker(verifier, tmp_path):
    hasil = jalankan_probe(tmp_path)
    assert hasil.returncode == 0
    assert json.loads(hasil.stdout) == verifier.ringkasan_untuk_revision(REVISION)
    assert hasil.stderr == ''
    assert list(tmp_path.iterdir()) == []  # DB/auth/server sekali pakai sudah ditutup.


def ekstrak_tar_aman(paket, tujuan):
    """Ekstrak hanya direktori/file regular; kompatibel Python 3.9 dan 3.12."""
    tujuan = tujuan.resolve()
    for item in paket.getmembers():
        if not (item.isdir() or item.isfile()):
            raise ValueError("jenis anggota arsip tidak aman")
        sasaran = (tujuan / item.name).resolve()
        try:
            sasaran.relative_to(tujuan)
        except ValueError:
            raise ValueError("jalur anggota arsip tidak aman") from None
        if item.isdir():
            sasaran.mkdir(parents=True, exist_ok=True)
            continue
        sasaran.parent.mkdir(parents=True, exist_ok=True)
        sumber = paket.extractfile(item)
        if sumber is None:
            raise ValueError("isi anggota arsip tidak tersedia")
        with sumber, sasaran.open("wb") as keluaran:
            shutil.copyfileobj(sumber, keluaran)


def source_recovery_dari_git_archive(tmp_path):
    """Ekstrak revision recovery pinned; tidak memakai working tree atau Docker."""
    arsip = tmp_path / "recovery.tar"
    with arsip.open("wb") as keluaran:
        hasil = subprocess.run(
            ["git", "-C", str(ROOT), "archive", RECOVERY_REVISION, "mesin"],
            stdout=keluaran, stderr=subprocess.PIPE, check=False,
        )
    assert hasil.returncode == 0 and hasil.stderr == b""
    akar = tmp_path / "recovery"
    akar.mkdir()
    with tarfile.open(arsip) as paket:
        ekstrak_tar_aman(paket, akar)
    arsip.unlink()
    return akar / "mesin"


def test_ekstraksi_recovery_tidak_memakai_extractall_dan_menolak_link_traversal(
    tmp_path,
):
    import io

    arsip = tmp_path / "jahat.tar"
    with tarfile.open(arsip, "w") as paket:
        isi = b"aman"
        file_aman = tarfile.TarInfo("mesin/aman.py")
        file_aman.size = len(isi)
        paket.addfile(file_aman, io.BytesIO(isi))
        tautan = tarfile.TarInfo("mesin/tautan.py")
        tautan.type = tarfile.SYMTYPE
        tautan.linkname = "../../rahasia"
        paket.addfile(tautan)
    with tarfile.open(arsip) as paket, mock.patch.object(
        paket, "extractall", side_effect=AssertionError("extractall terlarang")
    ):
        with pytest.raises(ValueError, match="jenis anggota arsip tidak aman"):
            ekstrak_tar_aman(paket, tmp_path / "tujuan")
    assert (tmp_path / "tujuan/mesin/aman.py").read_bytes() == b"aman"
    assert not (tmp_path / "rahasia").exists()


def test_ekstraksi_recovery_menolak_path_traversal(tmp_path):
    import io

    arsip = tmp_path / "traversal.tar"
    with tarfile.open(arsip, "w") as paket:
        item = tarfile.TarInfo("../keluar.py")
        item.size = 1
        paket.addfile(item, io.BytesIO(b"x"))
    with tarfile.open(arsip) as paket:
        with pytest.raises(ValueError, match="jalur anggota arsip tidak aman"):
            ekstrak_tar_aman(paket, tmp_path / "tujuan")
    assert not (tmp_path / "keluar.py").exists()


def test_probe_http_lintas_source_candidate_dan_recovery_pinned(verifier, tmp_path):
    (tmp_path / "candidate").mkdir()
    candidate = jalankan_probe(tmp_path / "candidate", revision=REVISION)
    assert candidate.returncode == 0
    assert json.loads(candidate.stdout)["http_contract"] == verifier.KONTRAK_CANDIDATE

    sumber_recovery = source_recovery_dari_git_archive(tmp_path)
    (tmp_path / "recovery-run").mkdir()
    recovery = jalankan_probe(
        tmp_path / "recovery-run", sumber=sumber_recovery,
        revision=RECOVERY_REVISION,
    )
    assert recovery.returncode == 0
    assert json.loads(recovery.stdout) == verifier.ringkasan_untuk_revision(
        RECOVERY_REVISION
    )
    assert recovery.stderr == ""


@pytest.mark.parametrize("revision,ringkasan_salah", [
    (REVISION, {**{"ok": True, "kontrak": 1, "skema": 4,
                  "skenario_migrasi": 2, "skenario_tindakan": 7,
                  "http_checks": 7, "provider_calls": 0},
                "http_contract": "recovery-standalone-v1"}),
    (RECOVERY_REVISION, {**{"ok": True, "kontrak": 1, "skema": 4,
                           "skenario_migrasi": 2, "skenario_tindakan": 7,
                           "http_checks": 7, "provider_calls": 0},
                         "http_contract": "candidate-inline-v1"}),
    (REVISION, {**{"ok": True, "kontrak": 1, "skema": 4,
                  "skenario_migrasi": 2, "skenario_tindakan": 7,
                  "provider_calls": 0, "http_contract": "candidate-inline-v1"},
                "http_checks": 6}),
])
def test_verifier_menolak_kontrak_http_revision_yang_salah(
    verifier, monkeypatch, revision, ringkasan_salah,
):
    panggilan = docker_palsu(
        monkeypatch, verifier, revision=revision,
        run=subprocess.CompletedProcess([], 0, json.dumps(ringkasan_salah), ""),
    )
    with pytest.raises(verifier.GalatVerifikasi, match="ringkasan_tidak_sah"):
        verifier.verifikasi(IMAGE, revision)
    assert panggilan[-1][0][:2] == ["docker", "run"]


def test_probe_candidate_mendeteksi_redirect_dan_header_privat_rusak(tmp_path):
    sumber = salin_sumber(tmp_path)
    web = sumber / "assistant_http.py"
    teks = web.read_text()
    assert "_redirect(penangan, '/guru')" in teks
    web.write_text(teks.replace("_redirect(penangan, '/guru')", "_redirect(penangan, '/akun')", 1))
    (tmp_path / "run-redirect").mkdir()
    hasil = jalankan_probe(tmp_path / "run-redirect", sumber=sumber, diagnostik=True)
    assert hasil.returncode == 1 and hasil.stdout.strip() == "http_redirect_candidate"

    shutil.rmtree(sumber)
    sumber = salin_sumber(tmp_path)
    web = sumber / "web.py"
    teks = web.read_text()
    assert 'self.send_header("X-Frame-Options", "DENY")' in teks
    web.write_text(teks.replace('self.send_header("X-Frame-Options", "DENY")',
                                 'self.send_header("X-Frame-Options", "ALLOW")', 1))
    (tmp_path / "run-header").mkdir()
    hasil = jalankan_probe(tmp_path / "run-header", sumber=sumber, diagnostik=True)
    assert hasil.returncode == 1 and hasil.stdout.strip() == "http_inline_frame_candidate"


def test_probe_recovery_mendeteksi_status_dan_header_privat_rusak(tmp_path):
    sumber = source_recovery_dari_git_archive(tmp_path)
    (tmp_path / "run-status").mkdir()
    salah_status = jalankan_probe(
        tmp_path / "run-status", sumber=sumber, revision=REVISION,
        diagnostik=True,
    )
    assert salah_status.returncode == 1
    assert salah_status.stdout.strip() == "http_status"

    sumber_http = sumber / "assistant_http.py"
    teks = sumber_http.read_text()
    assert 'penangan.send_header("X-Frame-Options", "DENY")' in teks
    sumber_http.write_text(teks.replace(
        'penangan.send_header("X-Frame-Options", "DENY")',
        'penangan.send_header("X-Frame-Options", "ALLOW")', 1,
    ))
    (tmp_path / "run-header-recovery").mkdir()
    salah_header = jalankan_probe(
        tmp_path / "run-header-recovery", sumber=sumber,
        revision=RECOVERY_REVISION, diagnostik=True,
    )
    assert salah_header.returncode == 1
    assert salah_header.stdout.strip() == "http_frame"


def salin_sumber(tmp_path):
    sumber = tmp_path / 'source'
    sumber.mkdir()
    for berkas in (ROOT / 'mesin').glob('*.py'):
        shutil.copy2(berkas, sumber / berkas.name)
    shutil.copytree(ROOT / 'mesin' / 'aset', sumber / 'aset')
    return sumber


@pytest.mark.parametrize('mutasi', ['skema', 'sesi_ganda', 'owner', 'consent', 'aset'])
def test_probe_mendeteksi_app_rusak_di_salinan_temp(tmp_path, mutasi):
    sumber = salin_sumber(tmp_path)
    if mutasi == 'skema':
        berkas = sumber / 'assistant_schema.py'
        lama, baru = 'VERSI_SKEMA = 4', 'VERSI_SKEMA = 3'
    elif mutasi == 'sesi_ganda':
        berkas = sumber / 'assistant_actions.py'
        # Fault pada jalur aktual: retry tetap mengembalikan ID ledger lama,
        # tetapi menambah sesi ekstra. Pemeriksaan ID saja tidak cukup.
        lama = '        return sesi_id\n'
        baru = ("        if sekarang >= 9000:\n"
                "            with database.buka() as kon_ganda:\n"
                "                database.buat_sesi_dari_urutan(kon_ganda, siswa_id, 99, ('deret_aritmetika',), level='P3')\n"
                "        return sesi_id\n")
        # Ada return lain pada lookup; mutasi hanya return di fungsi konfirmasi.
        teks = berkas.read_text()
        posisi = teks.index('def konfirmasi_dan_buat_sesi(')
        assert teks[posisi:].count(lama) == 1
        berkas.write_text(teks[:posisi] + teks[posisi:].replace(lama, baru))
    elif mutasi == 'owner':
        berkas = sumber / 'assistant_actions.py'
        lama = '            siswa_id = _pemilik_sumber(kon_data, chat, pemilik)\n            _periksa_izin(kon_pendamping, catatan, chat)'
        baru = ("            # Mutan replay hasil sebelum otorisasi owner.\n"
                "            if kon_data.execute('SELECT pemilik FROM siswa LIMIT 1').fetchone()[0] != pemilik:\n"
                "                return kon_data.execute('SELECT sesi_id FROM eksekusi_pendamping LIMIT 1').fetchone()[0]\n"
                "            siswa_id = _pemilik_sumber(kon_data, chat, pemilik)\n"
                "            _periksa_izin(kon_pendamping, catatan, chat)")
    elif mutasi == 'consent':
        berkas = sumber / 'assistant_actions.py'
        lama = 'def _periksa_izin(kon, catatan, chat) -> None:\n'
        baru = lama + '    return  # mutan mengabaikan pencabutan izin\n'
    else:
        (sumber / 'aset' / 'favicon.svg').unlink()
    if mutasi not in ('sesi_ganda', 'aset'):
        teks = berkas.read_text()
        assert teks.count(lama) == 1
        berkas.write_text(teks.replace(lama, baru))
    hasil = jalankan_probe(tmp_path, sumber)
    assert hasil.returncode == 1
    assert json.loads(hasil.stdout) == {'ok': False, 'kode': 'probe_gagal'}
    assert hasil.stderr == ''
    # Jangan menerima merah karena fixture/import rusak. Identifikasi guard
    # dengan allow-list kode konstan di proses sintetis terpisah, tanpa trace.
    detail = jalankan_probe(tmp_path, sumber, diagnostik=True)
    assert detail.returncode == 1
    assert detail.stdout.strip() == {
        'skema': 'skema_bukan_v4', 'sesi_ganda': 'sesi_ganda',
        'owner': 'guard_tidak_menolak', 'consent': 'guard_tidak_menolak',
        'aset': 'aset_hilang',
    }[mutasi]
    assert detail.stderr == ''


@pytest.mark.parametrize('jenis,kode', [
    ('provider', 'provider_dilarang'), ('dns', 'dns_dilarang'),
    ('connect', 'network_dilarang'), ('connect_ex', 'network_dilarang'),
])
def test_probe_memblokir_provider_dan_network_outbound(tmp_path, jenis, kode):
    # Masuk hook yang dipanggil SETELAH provider/network dikunci oleh probe.
    aksi = {
        'provider': 'import assistant_service; assistant_service.panggil_provider_default([])',
        'dns': 'import socket; socket.getaddrinfo("provider.invalid", 443)',
        'connect': 'import socket; s = socket.socket(); s.connect(("192.0.2.1", 443))',
        'connect_ex': 'import socket; s = socket.socket(); s.connect_ex(("192.0.2.1", 443))',
    }[jenis]
    injeksi = 'def dilarang(*args):\n    ' + aksi + '\nruang["uji_tindakan"] = dilarang\n'
    hasil = jalankan_probe(tmp_path, injeksi=injeksi, diagnostik=True)
    assert hasil.returncode == 1
    assert hasil.stdout.strip() == kode
    assert hasil.stderr == ''


def test_probe_galat_tidak_mencetak_data(tmp_path):
    injeksi = (
        'def gagal(akar):\n'
        '    raise RuntimeError("record-sintetis-jangan-log")\n'
        'ruang["jalankan_probe"] = gagal\n'
    )
    hasil = jalankan_probe(tmp_path, injeksi=injeksi)
    assert hasil.returncode == 1
    assert json.loads(hasil.stdout) == {'ok': False, 'kode': 'probe_gagal'}
    assert hasil.stderr == ''
