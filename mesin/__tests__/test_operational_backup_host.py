"""Guard host/fetch diuji memakai doubles; tidak ada SSH/Docker sungguhan."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_operational_backup import backup, sumber, buat


@pytest.fixture
def host(monkeypatch):
    state = dict(running=False, status='exited', active_cron=False, maintenance=True,
                 mounts=[], pids='', fuser_code=1, fuser_stderr='')
    def text(path, *args, **kwargs):
        if str(path) == '/etc/caddy/Caddyfile':
            return 'respond "Jagomat sedang diperbarui. Silakan coba beberapa menit lagi." 503' if state['maintenance'] else 'normal'
        return '* * * * * root writer' if state['active_cron'] else '# hold\n'
    def run(args, allowed=(0,)):
        if args[:3] == ['docker', 'inspect', 'osn-mesin']:
            return SimpleNamespace(stdout=json.dumps([{'State': {'Running':state['running'], 'Status':state['status']}}]))
        if args[:3] == ['docker', 'ps', '-q']:
            return SimpleNamespace(stdout='other' if state['mounts'] else '')
        if args[:2] == ['docker', 'inspect']:
            return SimpleNamespace(stdout=json.dumps([{'Mounts':[{'Source':m} for m in state['mounts']]}]))
        assert args[0] == 'fuser'
        return SimpleNamespace(returncode=state['fuser_code'], stdout=state['pids'], stderr=state['fuser_stderr'])
    monkeypatch.setattr(backup.Path, 'read_text', text)
    monkeypatch.setattr(backup, 'run', run)
    return state


def test_host_menerima_hanya_stopped_quiescent_dan_fd_sendiri(host):
    backup.host_quiescent()
    host.update(fuser_code=0, pids=str(os.getpid()), fuser_stderr='label berkas saja')
    backup.host_quiescent()


@pytest.mark.parametrize('changes', (
    {'running':True}, {'status':'paused'}, {'maintenance':False}, {'active_cron':True},
    {'mounts':['/opt/osn/data']}, {'mounts':['/opt/osn/data/lampiran']}, {'mounts':['/opt']},
    {'fuser_code':0,'pids':'999999'}, {'fuser_code':0,'pids':''},
    {'fuser_code':1,'fuser_stderr':'permission denied'},
))
def test_host_tolak_state_tidak_pasti(host, changes):
    host.update(changes)
    with pytest.raises(backup.Ditolak):
        backup.host_quiescent()


def test_fetch_ssh_gagal_tidak_publikasi(tmp_path, monkeypatch):
    def fail(args, **kwargs):
        kwargs['stdout'].write(b'partial')
        return SimpleNamespace(returncode=255)
    monkeypatch.setattr(backup.subprocess, 'run', fail)
    target = tmp_path / 'fresh-checkout' / 'mesin' / 'cadangan' / 'operasional'
    with pytest.raises(backup.Ditolak, match='transfer'):
        backup.fetch('backup-uji', 'host.invalid', target)
    assert not (target / 'backup-uji').exists()
    partial = next(target.glob('.transfer-*'))
    assert partial.stat().st_mode & 0o077 == 0
    assert (partial / 'backup.tar').stat().st_mode & 0o077 == 0


def test_unpack_id_tidak_sesuai_tidak_publikasi(sumber, tmp_path):
    root = buat(sumber, tmp_path)
    archive = tmp_path / 'backup.tar'
    with archive.open('wb') as f:
        backup.export(root, f)
    with pytest.raises(backup.Ditolak, match='ID bundle'):
        backup.unpack(archive, tmp_path / 'salah-id')
    assert not (tmp_path / 'salah-id').exists()


def test_fetch_menolak_host_injection(tmp_path):
    for host in ('-oProxyCommand=oops', 'abc;touch /tmp/oops', 'a b'):
        with pytest.raises(backup.Ditolak, match='host'):
            backup.fetch('backup-uji', host, tmp_path)


def test_uid_data_kanonis_hanya_di_source_bukan_output(monkeypatch):
    import stat
    uid = {'/opt/osn/data':10001}
    def info(path):
        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=uid.get(str(path),0))
    monkeypatch.setattr(backup.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(backup.Path, 'lstat', info)
    backup.trusted_path('/opt/osn/data', data_source=True)
    with pytest.raises(backup.Ditolak, match='pemilik'):
        backup.trusted_path('/opt/osn/data')
    uid['/opt/osn/data'] = 12345
    with pytest.raises(backup.Ditolak, match='pemilik'):
        backup.trusted_path('/opt/osn/data', data_source=True)
    uid['/opt/osn/data'] = 10001
    uid['/opt/osn'] = 10001
    with pytest.raises(backup.Ditolak, match='pemilik'):
        backup.trusted_path('/opt/osn/data', data_source=True)


def test_sync_directory_sebelum_publish(sumber, tmp_path, monkeypatch):
    calls = []
    original_sync = backup.sync_dir
    original_rename = backup.os.rename
    def sync(path):
        calls.append(('sync', Path(path).name))
        original_sync(path)
    def rename(source, target):
        assert ('sync', '1') in calls and ('sync', 'lampiran') in calls and ('sync', 'bundle') in calls
        calls.append(('rename', Path(target).name))
        original_rename(source, target)
    monkeypatch.setattr(backup, 'sync_dir', sync)
    monkeypatch.setattr(backup.os, 'rename', rename)
    buat(sumber, tmp_path)
    assert calls[-2][0] == 'rename' and calls[-1][0] == 'sync'
