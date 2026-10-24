"""Paket backup operasional privat; capture hanya sesudah quiesce terverifikasi.

Tidak menghentikan layanan, memasang jadwal, memangkas retensi atau restore live.
Core memakai validator admin_backup existing; riset/lampiran terpisah di envelope.
"""
from contextlib import ExitStack, closing
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'mesin'))
import admin_backup

ID = re.compile(r'^[a-z0-9][a-z0-9-]{1,79}$')
SHA = re.compile(r'^[0-9a-f]{40}$')
DIGEST = re.compile(r'^sha256:[0-9a-f]{64}$')
MANIFEST = 'operational-manifest.json'
CORE = tuple(admin_backup.BERKAS_WAJIB.values())


class Ditolak(RuntimeError):
    """Kegagalan aman; pesan tidak memuat data privat."""


def regular(path, directory=False, private=False):
    info = path.lstat()
    valid = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1
    if not valid:
        raise Ditolak('bukan berkas/direktori biasa')
    if private and stat.S_IMODE(info.st_mode) & ~(0o700 if directory else 0o600):
        raise Ditolak('izin backup tidak privat')
    return info


def trusted_path(path, *, data_source=False):
    """Tolak ancestor symlink/writable asing sebelum mengikuti path data privat."""
    path = Path(os.path.abspath(str(path)))
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise Ditolak('ancestor symlink ditolak; gunakan path kanonis')
        source_owner = (data_source and os.geteuid() == 0
                        and part == path == Path('/opt/osn/data') and info.st_uid == 10001)
        if info.st_uid not in (0, os.geteuid()) and not source_owner:
            raise Ditolak('pemilik ancestor tidak tepercaya')
        if stat.S_ISDIR(info.st_mode) and info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX:
            raise Ditolak('ancestor dapat ditulis pihak lain')


def hash_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def sync_dir(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sync_tree(root):
    for path in sorted((p for p in root.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        sync_dir(path)
    sync_dir(root)


def attachment_links(database, directory):
    """Setiap metadata foto wajib menunjuk file privat di dalam direktori sesi."""
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        rows = db.execute('SELECT sesi_id,nama_berkas FROM lampiran').fetchall()
    for sid, name in rows:
        if (type(sid) is not int or sid < 1 or not isinstance(name, str)
                or not re.fullmatch(r'[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp|img)', name)):
            raise Ditolak('referensi lampiran tidak aman')
        regular(directory / str(sid), directory=True, private=True)
        regular(directory / str(sid) / name, private=True)
    return len(rows)


def write_json(path, data):
    with path.open('x', encoding='utf-8') as f:
        os.chmod(path, 0o600)
        json.dump(data, f, ensure_ascii=False, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())


def read_json(path):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise Ditolak('key manifest duplikat')
            result[k] = v
        return result
    regular(path, private=True)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise Ditolak('manifest terlalu besar')
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Ditolak('angka manifest invalid')))


def inventory(root):
    regular(root, directory=True, private=True)
    files, dirs = {}, []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise Ditolak('symlink backup ditolak')
        if path.is_dir():
            regular(path, directory=True, private=True)
            dirs.append(rel)
        else:
            regular(path, private=True)
            if rel != MANIFEST:
                files[rel] = {'bytes': path.stat().st_size, 'sha256': hash_file(path)}
    return files, dirs


def copy_file(source, target):
    regular(source)
    with source.open('rb') as src, target.open('xb') as dst:
        os.chmod(target, 0o600)
        shutil.copyfileobj(src, dst)
        dst.flush()
        os.fsync(dst.fileno())


def copy_tree(source, target):
    regular(source, directory=True)
    target.mkdir(mode=0o700)
    for p in sorted(source.iterdir()):
        if p.is_symlink():
            raise Ditolak('symlink lampiran ditolak')
        if p.is_dir():
            copy_tree(p, target / p.name)
        else:
            copy_file(p, target / p.name)
    sync_dir(target)


def sqlite_copy(source, target):
    regular(source)
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(str(target))) as dst:
            src.backup(dst)
    os.chmod(target, 0o600)
    with target.open('rb') as f:
        os.fsync(f.fileno())


def sqlite_check(path):
    regular(path, private=True)
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or db.execute('PRAGMA foreign_key_check').fetchone():
            raise Ditolak('integrity/FK gagal')


def validate(root):
    """Hanya membaca; tidak memperbaiki bundle rusak atau mengesahkan quiesce."""
    root = Path(root)
    trusted_path(root)
    regular(root, directory=True, private=True)
    m = read_json(root / MANIFEST)
    keys = {'version', 'id', 'cutoff', 'revision', 'image', 'coherence', 'files', 'directories', 'excluded'}
    if not isinstance(m, dict) or set(m) != keys or type(m['version']) is not int or m['version'] != 1:
        raise Ditolak('manifest operasional invalid')
    if (not isinstance(m['id'], str) or not ID.fullmatch(m['id'])
            or type(m['cutoff']) is not int or m['cutoff'] < 0
            or not isinstance(m['revision'], str) or not SHA.fullmatch(m['revision'])
            or not isinstance(m['image'], str) or not DIGEST.fullmatch(m['image'])
            or m['coherence'] != 'stopped-writers-checked'
            or m['excluded'] != ['sessions', 'transient', 'generated', 'provider_credentials']):
        raise Ditolak('metadata operasional invalid')
    if {p.name for p in root.iterdir()} != {'bundle', 'riset-separate.db', 'lampiran', MANIFEST}:
        raise Ditolak('inventaris root invalid')
    actual, dirs = inventory(root)
    if m['files'] != actual or m['directories'] != dirs:
        raise Ditolak('hash/ukuran/inventaris tidak cocok')
    core = admin_backup.validasi_bundle(root / 'bundle', bundle_id=m['id'])
    core_m = read_json(root / 'bundle' / 'manifest.json')
    if core_m['cutoff'] != m['cutoff']:
        raise Ditolak('cutoff core berbeda')
    sqlite_check(root / 'riset-separate.db')
    import research_store
    try:
        with research_store.buka_baca(root / 'riset-separate.db'):
            pass
    except RuntimeError:
        raise Ditolak('schema riset tidak lengkap') from None
    attachment_links(root / 'bundle' / 'latihan.db', root / 'lampiran')
    return {'ok': True, 'id': m['id'], 'files': len(actual),
            'attachments': sum(k.startswith('lampiran/') for k in actual),
            'core_files': len(core.berkas), 'research_separate': True,
            'needs_reconciliation': core.perlu_rekonsiliasi}


def capture(data, output, revision, image, check_quiescent):
    """Caller memegang lock deploy dan mempertahankan maintenance sepanjang fungsi."""
    data, output = Path(data), Path(output)
    if not ID.fullmatch(output.name) or not SHA.fullmatch(revision) or not DIGEST.fullmatch(image):
        raise Ditolak('identitas capture invalid')
    trusted_path(data, data_source=True)
    trusted_path(output)
    regular(data, directory=True)
    regular(output.parent, directory=True, private=True)
    if output.exists() or output.is_symlink():
        raise Ditolak('output sudah ada')
    check_quiescent()
    stage = output.parent / ('.partial-' + output.name + '-' + secrets.token_hex(6))
    stage.mkdir(mode=0o700)
    core = stage / 'bundle'
    core.mkdir(mode=0o700)
    try:
        with ExitStack() as stack:
            for name in ('latihan.db', 'sandi.json', 'admin-control.db', 'ai-control.db', 'pendamping.db', 'riset-konsumen.db'):
                regular(data / name)
                if name == 'sandi.json':
                    fd = os.open(str(data / '.sandi.json.lock'), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
                    lock = stack.enter_context(os.fdopen(fd, 'a+b'))
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise Ditolak('sidecar lock bukan file biasa')
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    c = stack.enter_context(closing(sqlite3.connect((data / name).resolve().as_uri() + '?mode=rw', uri=True, timeout=1)))
                    c.execute('BEGIN IMMEDIATE')
            cutoff = int(time.time())
            for name in CORE:
                if name.endswith('.db'):
                    sqlite_copy(data / name, core / name)
                else:
                    copy_file(data / name, core / name)
            sqlite_copy(data / 'riset-konsumen.db', stage / 'riset-separate.db')
            if (data / 'lampiran').exists() or (data / 'lampiran').is_symlink():
                copy_tree(data / 'lampiran', stage / 'lampiran')
            else:
                (stage / 'lampiran').mkdir(mode=0o700)
            attachment_links(core / 'latihan.db', stage / 'lampiran')
            check_quiescent()
            admin_backup.buat_manifest(core, bundle_id=output.name, cutoff=cutoff)
            files, dirs = inventory(stage)
            write_json(stage / MANIFEST, dict(version=1, id=output.name, cutoff=cutoff,
                revision=revision, image=image, coherence='stopped-writers-checked', files=files,
                directories=dirs, excluded=['sessions', 'transient', 'generated', 'provider_credentials']))
            validate(stage)
            sync_tree(stage)
            if output.exists() or output.is_symlink():
                raise Ditolak('output sudah ada')
            os.rename(stage, output)
            sync_dir(output.parent)
        return validate(output)
    except BaseException:
        # Partial privat dipertahankan untuk diagnosis, tidak dipublikasikan sebagai sukses.
        raise


def run(args, allowed=(0,)):
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if r.returncode not in allowed:
        raise Ditolak('precheck command gagal')
    return r


def host_quiescent():
    """Target fixed: maintenance+cron tertahan, app stopped, tidak ada writer mount."""
    info = json.loads(run(['docker', 'inspect', 'osn-mesin']).stdout)[0]
    if info['State']['Running'] or info['State']['Status'] != 'exited':
        raise Ditolak('aplikasi belum dihentikan')
    hold = 'respond "Jagomat sedang diperbarui. Silakan coba beberapa menit lagi." 503'
    if hold not in Path('/etc/caddy/Caddyfile').read_text():
        raise Ditolak('maintenance belum terpasang')
    for name in ('osn-pendamping-retensi', 'osn-rekonsiliasi-langganan'):
        lines = Path('/etc/cron.d', name).read_text().splitlines()
        if any(line.strip() and not line.lstrip().startswith('#') for line in lines):
            raise Ditolak('cron writer belum ditahan')
    ids = run(['docker', 'ps', '-q']).stdout.split()
    if ids:
        all_info = json.loads(run(['docker', 'inspect', *ids]).stdout)
        if any(m['Source'] == '/opt/osn/data' or m['Source'].startswith('/opt/osn/data/')
               or '/opt/osn/data'.startswith(m['Source'].rstrip('/') + '/')
               for c in all_info for m in c['Mounts']):
            raise Ditolak('writer container lain aktif')
    paths = [str(Path('/opt/osn/data') / n) for n in (*CORE, 'riset-konsumen.db')]
    r = run(['fuser', *paths], allowed=(0, 1))
    pids = r.stdout.split()
    if r.returncode == 0 and (not pids or any(not p.isdigit() or int(p) != os.getpid() for p in pids)):
        raise Ditolak('writer file masih aktif')
    if r.returncode == 1 and (r.stdout.strip() or r.stderr.strip()):
        raise Ditolak('pemeriksaan writer tidak pasti')


def make_private_dir(path):
    """Buat hanya parent yang hilang; tidak chmod parent existing milik pengguna."""
    path = Path(path)
    if path.exists() or path.is_symlink():
        regular(path, directory=True)
        return
    make_private_dir(path.parent)
    path.mkdir(mode=0o700)


def fetch(ident, host, destination):
    """Tarik paket lengkap lewat SSH existing; transfer gagal tidak dipublikasikan."""
    if not ID.fullmatch(ident) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', host):
        raise Ditolak('ID/host fetch invalid')
    destination = Path(destination)
    trusted_path(destination)
    make_private_dir(destination)
    regular(destination, directory=True, private=True)
    target = destination / ident
    if target.exists() or target.is_symlink():
        raise Ditolak('output sudah ada')
    temp = destination / ('.transfer-' + secrets.token_hex(8))
    temp.mkdir(mode=0o700)
    archive = temp / 'backup.tar'
    command = 'sudo -n python3 -B /opt/osn/backup-tool/scripts/operational_backup.py export --id ' + ident
    with archive.open('xb') as f:
        os.chmod(archive, 0o600)
        r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', host, command],
                           stdout=f, stderr=subprocess.PIPE, timeout=300)
        f.flush()
        os.fsync(f.fileno())
    if r.returncode:
        raise Ditolak('transfer SSH gagal; partial privat bukan backup sukses')
    result = unpack(archive, target)
    if result['id'] != ident:
        raise Ditolak('ID bundle tidak sesuai permintaan')
    archive.unlink()
    temp.rmdir()
    return result


def export(root, output):
    """Stream bundle tervalidasi saja; stdout berisi data privat untuk file tujuan."""
    root = Path(root)
    validate(root)
    files, _ = inventory(root)
    if sum(x['bytes'] for x in files.values()) > 2 * 1024**3 or len(files) > 100000:
        raise Ditolak('arsip terlalu besar')
    with tarfile.open(fileobj=output, mode='w|') as archive:
        for path in sorted(root.rglob('*')):
            archive.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)


def unpack(archive, output):
    """Tidak memakai extractall; tolak traversal, link, file khusus dan bom ukuran."""
    output = Path(output)
    trusted_path(output)
    trusted_path(archive)
    regular(archive)
    regular(output.parent, directory=True, private=True)
    if output.exists() or output.is_symlink():
        raise Ditolak('output sudah ada')
    stage = output.parent / ('.incoming-' + secrets.token_hex(8))
    stage.mkdir(mode=0o700)
    seen, total = set(), 0
    with tarfile.open(archive, mode='r:') as tf:
        for item in tf:
            parts = item.name.split('/')
            if (not item.name or item.name.startswith('/') or any(x in ('', '.', '..') for x in parts)
                    or item.name in seen or not (item.isfile() or item.isdir())
                    or len(seen) >= 100000):
                raise Ditolak('entri arsip tidak aman')
            seen.add(item.name)
            total += item.size
            if item.size < 0 or total > 2 * 1024**3:
                raise Ditolak('arsip terlalu besar')
            path = stage.joinpath(*parts)
            if item.isdir():
                path.mkdir(mode=0o700, parents=True, exist_ok=True)
            else:
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with tf.extractfile(item) as src, path.open('xb') as dst:
                    os.chmod(path, 0o600)
                    shutil.copyfileobj(src, dst)
                    dst.flush()
                    os.fsync(dst.fileno())
    result = validate(stage)
    if result['id'] != output.name:
        raise Ditolak('ID bundle tidak sesuai tujuan')
    if output.exists() or output.is_symlink():
        raise Ditolak('output sudah ada')
    sync_tree(stage)
    os.rename(stage, output)
    sync_dir(output.parent)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('validate')
    p.add_argument('path', type=Path)
    p = sub.add_parser('fetch')
    p.add_argument('--id', required=True)
    p.add_argument('--host', default='biznet-sekolahdesain')
    p.add_argument('--destination', type=Path, default=ROOT / 'mesin' / 'cadangan' / 'operasional')
    p = sub.add_parser('export')
    p.add_argument('--id', required=True)
    p = sub.add_parser('unpack')
    p.add_argument('archive', type=Path)
    p.add_argument('output', type=Path)
    p = sub.add_parser('capture')
    p.add_argument('--id', required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--image', required=True)
    a = parser.parse_args()
    try:
        if a.action == 'validate':
            result = validate(a.path)
        elif a.action == 'fetch':
            result = fetch(a.id, a.host, a.destination)
        elif a.action == 'unpack':
            result = unpack(a.archive, a.output)
        elif a.action == 'export':
            if not ID.fullmatch(a.id):
                raise Ditolak('ID export invalid')
            export(Path('/opt/osn/cadangan/operasional') / a.id, sys.stdout.buffer)
            return
        else:
            os.umask(0o077)
            if os.geteuid() != 0 or not ID.fullmatch(a.id):
                raise Ditolak('capture hanya operator root pada target terverifikasi')
            fd = os.open('/opt/osn/deploy.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'a+b') as lock:
                info_lock = os.fstat(fd)
                if not stat.S_ISREG(info_lock.st_mode) or info_lock.st_nlink != 1:
                    raise Ditolak('deploy lock bukan file biasa')
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                info = json.loads(run(['docker', 'inspect', 'osn-mesin']).stdout)[0]
                image = json.loads(run(['docker', 'image', 'inspect', info['Image']]).stdout)[0]
                if (image['Config']['Labels']['org.opencontainers.image.revision'] != a.revision
                        or 'ghcr.io/clarinovist/osn-mesin-latihan@' + a.image not in image['RepoDigests']):
                    raise Ditolak('revision/digest live tidak cocok')
                result = capture('/opt/osn/data', Path('/opt/osn/cadangan/operasional') / a.id,
                                 a.revision, a.image, host_quiescent)
        print(json.dumps(result))
    except (Ditolak, admin_backup.BackupTidakSah, OSError, ValueError, sqlite3.Error) as error:
        print('BACKUP_GAGAL ' + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
