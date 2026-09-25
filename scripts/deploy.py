#!/usr/bin/env python3
"""Artefak forced-command v2; belum merupakan izin memasang/menjalankan di VPS.

Hanya stdlib. Tidak ada shell, restore DB atau pelepasan writehold. Deploy-v2
memerlukan approval migrasi setelah drain/backup; deploy-rutin-v1 memerlukan
policy root dan kontrak persistensi identik pada current/candidate/recovery.
Pesan statis: output Docker dan isi berkas privat tidak diteruskan ke log.
Exit 0 = candidate sehat, 1 = gagal tetapi recovered, 2 = ditolak/manual.
Lihat docs/production-release.md sebelum instalasi atau pengaktifan.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

REGISTRI = "ghcr.io/clarinovist/osn-mesin-latihan"
DOCKER = "/usr/bin/docker"
AKAR = Path("/opt/osn")
DATA = AKAR / "data"
# Mount rahasia pembayaran: host-controlled, dibaca read-only oleh container
# sebagai /run/secrets/midtrans. Isi (secret + artefak pasangan) dimiliki uid
# 10001 (user container) tanpa bit group/other; deployer TIDAK membuat/memperbaiki.
MIDTRANS = AKAR / "midtrans"
PASANGAN = MIDTRANS / "recovery-pair.json"
APPROVAL = AKAR / "rollout-approval.json"
POLICY_RUTIN = AKAR / "routine-policy.json"
KUNCI = DATA / "deepseek.key"
ENVFILES = (AKAR / "visual.conf", AKAR / "pendamping.conf")
LOCK = AKAR / "deploy.lock"
DISK_DOCKER = Path("/var/lib/docker")
KONTAINER = "osn-mesin"
PROBE = "osn-deploy-probe"
LABEL_PROBE = "osn.deploy.probe"
MAKS_TTL_APPROVAL = 900  # detik; lease untuk mulai swap, bukan batas waktu recovery
DIGEST = r"sha256:[0-9a-f]{64}"
POLA_PERMINTAAN = re.compile(r"deploy-v2 (" + DIGEST + r") (" + DIGEST + r")")
POLA_RUTIN = re.compile(r"deploy-rutin-v1 (" + DIGEST + r") (" + DIGEST + r")")
LINGKUNGAN = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root", "LANG": "C.UTF-8"}
BATAS_HEALTH = 120
JEDA_HEALTH = 3
FORMAT_STATE = (
    "{{.State.Status}}|{{.State.Running}}|"
    "{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}|{{.Image}}"
)
PENGAMAN = ("--user", "10001:10001", "--cap-drop", "ALL", "--security-opt",
            "no-new-privileges", "--memory", "512m", "--cpus", "1", "--pids-limit", "128")
ENV_TETAP = (
    "OSN_BERKAS_SANDI=/data/sandi.json", "OSN_BERKAS_SESI=/data/sesi.json",
    "OSN_BERKAS_DB=/data/latihan.db", "PENDAMPING_BERKAS_DB=/data/pendamping.db",
    "AI_BERKAS_DB=/data/ai-control.db", "OSN_FOLDER_LEMBAR=/data/lembar",
    "ADMIN_BERKAS_DB=/data/admin-control.db",
    "ADMIN_TRANSIENT_DB=/data/transient/admin-drafts.db",
    "PENDAMPING_AKTIF=1",
    "DEEPSEEK_MODEL=deepseek-flash", "DEEPSEEK_VISION_MODEL=deepseek-flash",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTHONUNBUFFERED=1",
)

# Metadata wajib generasi pengiriman; tidak import aplikasi atau membuka rekaman.
PROBE_PENGIRIMAN_SKEMA = '''
kon = sqlite3.connect('file:/data/latihan.db?mode=ro', uri=True, timeout=2)
try:
    kon.execute('PRAGMA query_only = ON')
    wajib = {
        'refleksi_jawaban': {'sesi_soal_id', 'alasan'},
        'versi_pekerjaan': {'sesi_id', 'revisi'},
        'pengiriman_sesi': {'sesi_id', 'sumber', 'dibuat', 'lampiran_json'},
        'pengiriman_butir': {'sesi_id', 'sesi_soal_id', 'nomor', 'jawaban', 'cara',
                             'restatement', 'belum_pernah', 'alasan', 'penyajian_json'},
        'tinjauan_guru': {'sesi_soal_id', 'revisi', 'catatan', 'provenance',
                         'jawaban_bantuan', 'pemahaman', 'dilewati', 'guru'},
        'tinjauan_outcome': {'konfirmasi_id', 'data_json'},
    }
    for tabel, kolom in wajib.items():
        assert kolom <= {r[1] for r in kon.execute('PRAGMA table_info(' + tabel + ')')}
    trigger = {'pengiriman_butir_validasi'}
    for tabel in ('pengiriman_sesi', 'pengiriman_butir', 'tinjauan_outcome'):
        trigger.update(tabel + '_tolak_' + aksi for aksi in ('update', 'replace', 'delete'))
    for tabel in ('jawaban', 'refleksi_jawaban'):
        trigger.update(tabel + '_versi_' + aksi for aksi in ('insert', 'update', 'delete'))
    assert trigger <= {r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
finally:
    kon.close()
'''

# Metadata admin5/konteks; deployer tetap satu artefak mandiri di host.
PROBE_PROFIL_SKEMA = '''
kon = sqlite3.connect('file:/data/latihan.db?mode=ro', uri=True, timeout=2)
try:
    kon.execute('PRAGMA query_only = ON')
    wajib = {
        'profil_belajar': {'siswa_id', 'kelas_sekolah', 'revisi'},
        'operasi_admin_profil': {'operasi_id', 'actor_id', 'siswa_id', 'revisi_awal',
                                'revisi_hasil', 'kelas_lama', 'kelas_baru', 'sidik_perintah', 'dibuat'},
        'konteks_sesi': {'sesi_id', 'versi'},
        'konteks_butir': {'sesi_soal_id', 'template_id', 'profil_parameter', 'konteks_id'},
        'konteks_konfirmasi': {'konfirmasi_id', 'snapshot_json'},
        'pilot_aksi': {'kunci', 'siswa_id', 'tujuan'},
        'pilot_putaran': {'putaran_id', 'konteks_json'},
        'pilot_fokus_sumber': {'anggota_id', 'konfirmasi_id'},
        'pilot_sesi': {'sesi_id', 'versi', 'kontrak_json', 'fingerprint'},
        'pilot_konfirmasi': {'konfirmasi_id', 'sesi_id', 'kontrak_json', 'fingerprint'},
    }
    for tabel, kolom in wajib.items():
        assert kolom <= {r[1] for r in kon.execute('PRAGMA table_info(' + tabel + ')')}
    trigger = {'konteks_butir_validasi_insert', 'konteks_konfirmasi_validasi_insert',
               'pilot_konfirmasi_sumber'}
    trigger.update(t + '_tolak_' + a for t in
                   ('pilot_aksi','pilot_putaran','pilot_sesi','pilot_konfirmasi')
                   for a in ('update','replace','delete'))
    trigger.update('pilot_fokus_sumber_' + a for a in ('update','replace','delete'))
    trigger.update(t + '_immutable_' + a for t in ('konteks_sesi','konteks_butir','konteks_konfirmasi')
                   for a in ('update','replace','delete'))
    assert trigger <= {r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
finally:
    kon.close()
kon = sqlite3.connect('file:/data/admin-control.db?mode=ro', uri=True, timeout=2)
try:
    kon.execute('PRAGMA query_only = ON')
    assert kon.execute('PRAGMA user_version').fetchone()[0] == 7
    for tabel, kolom in {
        'operasi_admin': {'operasi_id','actor_id','aksi','jenis_target','target_id','revisi_target',
                         'sidik_perintah','status','hasil_kode','revisi_hasil'},
        'receipt_admin': {'operasi_id','actor_id','aksi','jenis_target','target_id','sidik_perintah','hasil_kode'},
        'audit_admin': {'operasi_id','actor_id','aksi','hasil_kode'},
    }.items():
        assert kolom <= {r[1] for r in kon.execute('PRAGMA table_info(' + tabel + ')')}
        ddl = kon.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tabel,)).fetchone()[0]
        token = 'student_school_grade_updated' if tabel == 'audit_admin' else 'student_school_grade_update'
        assert "'" + token + "'" in ddl
finally:
    kon.close()
'''

# Metadata ledger admin6: tanpa import aplikasi atau migrasi saat readiness.
PROBE_LANGGANAN_SKEMA = '''
kon = sqlite3.connect('file:/data/admin-control.db?mode=ro', uri=True, timeout=2)
try:
    kon.execute('PRAGMA query_only = ON')
    wajib = {
        'langganan_aturan': {'versi','hari_trial','periode_promo','pajak'},
        'langganan_kampanye': {'kampanye_id','mulai','akhir','kuota'},
        'langganan_enrollment': {'akun_id','sumber_id','asal','mulai','peserta_promo','versi'},
        'langganan_cakupan': {'operasi_id','akun_id','urutan','revisi','profil_json'},
        'langganan_invoice': {'invoice_id','akun_id','urutan','rupiah','profil_json','idempotency_key','pajak'},
        'langganan_receipt': {'provider','transaksi_id','invoice_id','akun_id','rupiah','hasil'},
        'langganan_grant': {'invoice_id','akun_id','urutan','provider','transaksi_id','mulai','akhir','jangkar','profil_json'},
        'langganan_rekonsiliasi': {'operasi_id','invoice_id','status','diamati','rujukan'},
    }
    for tabel, kolom in wajib.items():
        assert kolom <= {r[1] for r in kon.execute('PRAGMA table_info(' + tabel + ')')}
        for aksi in ('update','delete','replace'):
            trigger = kon.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (tabel+'_tolak_'+aksi,)).fetchone()
            assert trigger and 'RAISE(ABORT,' in trigger[0]
    for tabel, kunci in (('langganan_invoice', {'akun_id','urutan'}),
                         ('langganan_receipt', {'provider','transaksi_id'}),
                         ('langganan_grant', {'akun_id','urutan'})):
        indeks = [r[1] for r in kon.execute('PRAGMA index_list(' + tabel + ')') if r[2]]
        assert any({r[2] for r in kon.execute('PRAGMA index_info(' + i + ')')} == kunci for i in indeks)
finally:
    kon.close()
'''

# Hanya berjalan dalam container synthetic network-none, tanpa mount/secret host.
PROBE_IMAGE = '''import sqlite3
from pathlib import Path
import ai_store
import assistant_schema
import database
import admin_store
import admin_students
import admin_bulk
import auth
import sessions
assert assistant_schema.VERSI_SKEMA == 4
assert ai_store.VERSI_SKEMA == 2
assert admin_store.VERSI_SKEMA == 7
assert admin_bulk.VERSI_TRANSIENT == 2
for _ in range(2):
    assistant_schema.siapkan(Path('/data/pendamping.db'))
    database.siapkan(Path('/data/latihan.db'))
    ai_store.siapkan(Path('/data/ai-control.db'), sekarang=1)
    admin_store.siapkan(Path('/data/admin-control.db'), sekarang=1)
    admin_students.siapkan(Path('/data/latihan.db'))
    admin_bulk.siapkan_transient(Path('/data/transient/admin-drafts.db'))
with admin_store.buka_baca(Path('/data/admin-control.db')) as kon:
    assert kon.execute('PRAGMA user_version').fetchone()[0] == 7
with sqlite3.connect('file:/data/transient/admin-drafts.db?mode=ro', uri=True) as kon:
    assert kon.execute('PRAGMA user_version').fetchone()[0] == 2
with sqlite3.connect('file:/data/pendamping.db?mode=ro', uri=True) as kon:
    kon.execute('PRAGMA query_only = ON')
    assert kon.execute('PRAGMA user_version').fetchone()[0] == 4
    assert kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tinjauan_usulan'").fetchone()
with sqlite3.connect('file:/data/latihan.db?mode=ro', uri=True) as kon:
    kon.execute('PRAGMA query_only = ON')
    assert kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='eksekusi_pendamping'").fetchone()
    assert kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='operasi_admin_siswa'").fetchone()
with sqlite3.connect('file:/data/ai-control.db?mode=ro', uri=True) as kon:
    kon.execute('PRAGMA query_only = ON')
    assert kon.execute('PRAGMA user_version').fetchone()[0] == ai_store.VERSI_SKEMA
    assert kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ledger'").fetchone()
    if ai_store.VERSI_SKEMA == 2:
        assert kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_uji_admin'").fetchone()
        assert kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='operasi_pengaturan_admin'").fetchone()
# Probe autentikasi hanya data sintetis di tmpfs, bukan volume keluarga.
akun_path = Path('/data/probe-accounts.json')
sesi_path = Path('/data/probe-sessions.json')
auth.tambah_akun('probe-admin', 'sandi-sintetis-probe-123', 'admin', akun_path)
principal = auth.autentikasi('probe-admin', 'sandi-sintetis-probe-123', akun_path)
token = sessions.buat_dari_principal(principal, path=sesi_path, path_akun=akun_path)
assert sessions.ambil_principal(token, path=sesi_path, path_akun=akun_path)
auth.naikkan_revisi_auth(principal.id_akun, akun_path)
assert sessions.ambil_principal(token, path=sesi_path, path_akun=akun_path) is None
'''+ PROBE_PENGIRIMAN_SKEMA + PROBE_PROFIL_SKEMA + PROBE_LANGGANAN_SKEMA

# Tidak mengimpor aplikasi: import/startup tertentu dapat melakukan migrasi.
# Jangan immutable=1: DB belajar memakai WAL; mode=ro harus melihat WAL juga.
PROBE_SKEMA = '''import ast
import sqlite3
from pathlib import Path
akar_app = Path('/app')
def versi_source(nama):
    pohon = ast.parse((akar_app / nama).read_text())
    return [node.value.value for node in pohon.body
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
            and any(isinstance(t, ast.Name) and t.id == 'VERSI_SKEMA' for t in node.targets)]
assert versi_source('assistant_schema.py') == [4]
assert versi_source('ai_store.py') == [2]
assert versi_source('admin_store.py') == [7]
for nama, tabel in [('pendamping.db', 'tinjauan_usulan'), ('latihan.db', 'eksekusi_pendamping'),
                    ('latihan.db', 'operasi_admin_siswa')]:
    kon = sqlite3.connect('file:/data/' + nama + '?mode=ro', uri=True, timeout=2)
    try:
        kon.execute('PRAGMA query_only = ON')
        if nama == 'pendamping.db':
            assert kon.execute('PRAGMA user_version').fetchone()[0] == 4
        assert kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabel,)).fetchone()
    finally:
        kon.close()
kon = sqlite3.connect('file:/data/ai-control.db?mode=ro', uri=True, timeout=2)
try:
    kon.execute('PRAGMA query_only = ON')
    assert kon.execute('PRAGMA user_version').fetchone()[0] == 2
    for tabel in ('ledger', 'audit_uji_admin', 'operasi_pengaturan_admin'):
        assert kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabel,)).fetchone()
finally:
    kon.close()
for nama, versi, tabel in (
    ('admin-control.db',7,('konfigurasi_pendaftaran','operasi_admin','receipt_admin','batch_admin','batch_admin_item','kelompok_admin','kelompok_admin_item','penyerahan_admin','penyerahan_admin_item')),
    ('transient/admin-drafts.db',2,('draft_bulk','item_bulk','kelompok_bulk')),
):
    kon = sqlite3.connect('file:/data/' + nama + '?mode=ro', uri=True, timeout=2)
    try:
        assert kon.execute('PRAGMA user_version').fetchone()[0] == versi
        for nama_tabel in tabel:
            assert kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nama_tabel,)).fetchone()
    finally:
        kon.close()
# Baca metadata saja; tidak import aplikasi atau menampilkan isi akun.
import json
akun = json.loads(Path('/data/sandi.json').read_text())
for item in akun.get('akun', [akun]):
    assert type(item.get('revisi_auth')) is int and item['revisi_auth'] >= 0
    assert isinstance(item.get('id_akun'), str) and item['id_akun'].startswith('akun_')
'''+ PROBE_PENGIRIMAN_SKEMA + PROBE_PROFIL_SKEMA + PROBE_LANGGANAN_SKEMA


# Konservatif: perubahan byte pada schema/startup/persistensi perlu review ulang
# kompatibilitas. Tidak import aplikasi, tidak membaca /data. Modul schema/migrasi
# baru juga mengubah fingerprint; ini BUKAN analisis semantik seluruh kode Python.
PROBE_LAYANAN_SKEMA = '''
kon = sqlite3.connect('file:/data/admin-control.db?mode=ro', uri=True, timeout=2)
try:
    kon.execute('PRAGMA query_only=ON')
    wajib = {
        'pembayaran_konfigurasi': {'id','tahap','revisi','actor_id'},
        'pembayaran_audit': {'operasi_id','actor_id','tahap_lama','tahap_baru','revisi'},
        'layanan_operasi': {'operasi_id','actor_id','sidik','status','hasil'},
        'kpi_eksperimen': {'id','versi','mulai','koleksi','kualitas','boot_id'},
        'kpi_peserta': {'id','akun_id','t0','consent','versi_consent'},
        'kpi_aktivitas': {'peserta','hari','kode','jendela'},
        'kpi_survei': {'peserta','ditawari','jawaban'},
        'kpi_biaya': {'bulan','revisi','anggaran','lengkap'},
        'kpi_audit_biaya': {'operasi_id','snapshot'},
        'kpi_cakupan': {'eksperimen','dicabut','kedaluwarsa'},
        'kpi_agregat': {'eksperimen','minggu','peserta','hapus_setelah'},
    }
    for tabel, kolom in wajib.items():
        assert kolom <= {r[1] for r in kon.execute('PRAGMA table_info(' + tabel + ')')}
finally:
    kon.close()
'''
PROBE_IMAGE += PROBE_LAYANAN_SKEMA + "\nprint('OSN_IMAGE_ADMIN7_AI2_OK')\n"
PROBE_SKEMA += PROBE_LAYANAN_SKEMA + "\nprint('OSN_SCHEMA_ADMIN7_AI2_OK')\n"

PROBE_KONTRAK = '''import hashlib
import json
from pathlib import Path
akar = Path('/app')
nama = {
    'schema.py', 'assistant_schema.py', 'database.py', 'serve.py',
    'auth.py', 'sessions.py', 'assistant_store.py', 'assistant_actions.py',
    'assistant_maintenance.py', 'migrate_params.py', 'outcome_presentations.py',
    'question_views.py', 'visual_contract.py', 'templates.py',
}
nama.update(p.name for p in akar.glob('*.py')
            if any(k in p.stem for k in ('schema', 'migrat', 'database', 'store')))
hasil = {n: hashlib.sha256((akar / n).read_bytes()).hexdigest() for n in sorted(nama)}
print(hashlib.sha256(json.dumps(hasil, sort_keys=True).encode()).hexdigest())
'''


class Ditolak(Exception):
    """Kegagalan tertutup; jangan sertakan pesan exception sumber ke log."""


def parse_permintaan(teks):
    """Terima persis dua manifest digest berbeda, tanpa whitespace tambahan."""
    cocok = POLA_PERMINTAAN.fullmatch(teks) if isinstance(teks, str) else None
    if cocok is None or cocok[1] == cocok[2]:
        raise Ditolak()
    return cocok[1], cocok[2]


def parse_rutin(teks):
    """Protokol rutin terpisah; caller tidak boleh memasok policy/path/flag."""
    cocok = POLA_RUTIN.fullmatch(teks) if isinstance(teks, str) else None
    if cocok is None or cocok[1] == cocok[2]:
        raise Ditolak()
    return cocok[1], cocok[2]


def validasi_policy_rutin(mentah):
    """Izin tetap root, bukan approval migrasi yang direkayasa menjadi permanen."""
    isi = json.loads(mentah, object_pairs_hook=_tanpa_duplikat)
    if not isinstance(isi, dict) or set(isi) != {
        "enabled", "schema_target", "deployer_sha256", "contract_sha256", "recovery_revision",
    }:
        raise Ditolak()
    if (isi["enabled"] is not True
            or type(isi["schema_target"]) is not int or isi["schema_target"] != 4
            or isi["deployer_sha256"] != hash_deployer()
            or not isinstance(isi["contract_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", isi["contract_sha256"]) is None
            or not isinstance(isi["recovery_revision"], str)
            or re.fullmatch(r"[0-9a-f]{40}", isi["recovery_revision"]) is None):
        raise Ditolak()
    return isi


def _tanpa_duplikat(pasangan):
    hasil = {}
    for kunci, nilai in pasangan:
        if kunci in hasil:
            raise Ditolak()
        hasil[kunci] = nilai
    return hasil


def hash_deployer():
    # B2 memasang artefak ini pada path root-controlled melalui wrapper terpercaya.
    # Hash byte source yang sedang digunakan, bukan revision/tag atau input SSH.
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def validasi_approval(mentah, kandidat, pemulihan, sekarang):
    """Approval hanya attestasi operator, bukan pengganti backup/drain B2."""
    isi = json.loads(mentah, object_pairs_hook=_tanpa_duplikat)
    wajib = {"candidate", "recovery", "expires", "backup_pair", "writes_held",
             "maintenance_paused", "schema_target", "approval_id", "issued",
             "deployer_sha256"}
    if not isinstance(isi, dict) or set(isi) != wajib:
        raise Ditolak()
    if (isi["candidate"] != kandidat or isi["recovery"] != pemulihan
            or kandidat == pemulihan
            or isi["writes_held"] is not True or isi["maintenance_paused"] is not True
            or type(isi["schema_target"]) is not int or isi["schema_target"] != 4
            or type(isi["expires"]) is not int or not math.isfinite(sekarang)
            or isi["expires"] <= sekarang
            or type(isi["issued"]) is not int or not 0 <= isi["issued"] <= sekarang
            or not 0 < isi["expires"] - isi["issued"] <= MAKS_TTL_APPROVAL
            or not isinstance(isi["approval_id"], str)
            or re.fullmatch(r"[0-9a-f]{32}", isi["approval_id"]) is None
            or not isinstance(isi["deployer_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", isi["deployer_sha256"]) is None
            or isi["deployer_sha256"] != hash_deployer()
            or not isinstance(isi["backup_pair"], str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", isi["backup_pair"]) is None):
        raise Ditolak()
    return isi


def metadata_privat(info, mode=0o600):
    """Syarat fd: regular root-owned, satu hardlink, izin tepat."""
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != mode):
        raise Ditolak()


def metadata_kunci(info):
    """Kunci layanan live: owner aplikasi, grup deployer, mode 0640."""
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 10001
            or info.st_gid != 10002 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o640):
        raise Ditolak()


def metadata_config(info):
    # Config nonsecret live root0644 sah; key/approval/receipt tetap ketat0600.
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) not in (0o600, 0o644)):
        raise Ditolak()


def baca_privat(path, batas=16384, *, config=False, kunci=False):
    """NOFOLLOW dan fstat menutup symlink/FIFO serta TOCTOU lstat→open."""
    if config and kunci:
        raise Ditolak()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        pemeriksa = metadata_kunci if kunci else metadata_config if config else metadata_privat
        pemeriksa(os.fstat(fd))
        with os.fdopen(fd, "rb", closefd=False) as berkas:
            isi = berkas.read(batas + 1)
        if len(isi) > batas:
            raise Ditolak()
        return isi.decode("utf-8")
    finally:
        os.close(fd)


class Berkas:
    """I/O host tetap; test dapat mengganti adapter ini dengan filesystem sintetis."""

    def __init__(self):
        self._lock_fd = None

    def periksa_host(self):
        if os.geteuid() != 0:
            raise Ditolak()
        # /opt/osn harus dikendalikan root; data memang dimiliki UID aplikasi.
        for path in (Path("/opt"), AKAR):
            info = path.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                    or stat.S_IMODE(info.st_mode) & 0o022):
                raise Ditolak()
        # Direktori mount rahasia pembayaran: root-controlled, TANPA bit tulis
        # group/other, dan other-exec supaya uid 10001 bisa traversal membaca
        # berkasnya. Bukan tugas deployer membuat/memperbaiki izin.
        info = MIDTRANS.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                or (mode & 0o022) != 0 or (mode & 0o001) != 0o001):
            raise Ditolak()

    @contextlib.contextmanager
    def kunci(self):
        fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            metadata_privat(os.fstat(fd))
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd = fd
            yield
        finally:
            # close melepaskan flock; jangan unlink inode lock yang mungkin ditunggu proses lain.
            if self._lock_fd == fd:
                self._lock_fd = None
            os.close(fd)

    def _wajib_lock(self):
        if self._lock_fd is None:
            raise Ditolak()

    @staticmethod
    def receipt(isi):
        # approval_id tervalidasi; tidak ada path yang berasal dari caller SSH.
        return AKAR / (".approval-consumed-" + isi["approval_id"] + ".json")

    def approval(self, kandidat, pemulihan, sekarang):
        self._wajib_lock()
        isi = validasi_approval(baca_privat(APPROVAL), kandidat, pemulihan, sekarang)
        try:
            self.receipt(isi).lstat()
        except FileNotFoundError:
            return isi
        raise Ditolak()  # Termasuk receipt parsial, symlink, atau attempt gagal.

    def policy_rutin(self):
        self._wajib_lock()
        return validasi_policy_rutin(baca_privat(POLICY_RUTIN))

    def konsumsi(self, isi, sekarang):
        """Receipt durable sebelum stop. Tidak pernah dibersihkan/dipakai ulang."""
        self._wajib_lock()
        if self.approval(isi["candidate"], isi["recovery"], sekarang) != isi:
            raise Ditolak()
        fd = os.open(self.receipt(isi),
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            metadata_privat(os.fstat(fd))
            with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as berkas:
                json.dump({"approval": isi, "consumed": sekarang}, berkas, sort_keys=True)
                berkas.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
        folder = os.open(AKAR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)
        # Fsync failure membatalkan swap, tetapi receipt tetap ada (fail closed).

    def tulis_pasangan(self, revisi, digest, kontrak, mode):
        """Artefak pasangan recovery untuk runtime pembayaran; atomik + durable.

        Ditulis SEBELUM swap supaya container baru sudah dapat membacanya saat
        start (runtime dipasang sekali per proses). Isi hanya hash/identitas
        image — tanpa rahasia. Pemilik uid 10001 mode 0400 mengikuti kontrak
        baca_privat runtime (`os.geteuid()` di container).
        """
        self._wajib_lock()
        if (re.fullmatch(r"[0-9a-f]{40}", revisi or "") is None
                or re.fullmatch(DIGEST, digest or "") is None
                or re.fullmatch(r"[0-9a-f]{64}", kontrak or "") is None
                or mode not in ("migrasi", "rutin")):
            raise Ditolak()
        isi = {"versi": 1, "revisi": revisi, "digest": digest, "kontrak": kontrak,
               "pasangan_terverifikasi": True, "kompatibel": True, "mode": mode}
        sementara = MIDTRANS / (".recovery-pair.tmp-" + secrets.token_hex(16))
        try:
            fd = os.open(sementara, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                os.write(fd, json.dumps(isi, sort_keys=True).encode("utf-8"))
                os.fsync(fd)
                os.fchown(fd, 10001, 10001)
                os.fchmod(fd, 0o400)
            finally:
                os.close(fd)
            os.replace(sementara, PASANGAN)
        except BaseException:
            try:
                os.unlink(sementara)
            except OSError:
                pass
            raise
        folder = os.open(MIDTRANS, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)
        info = PASANGAN.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 10001
                or stat.S_IMODE(info.st_mode) != 0o400):
            raise Ditolak()

    def ruang(self):
        info = DATA.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 10001
                or stat.S_IMODE(info.st_mode) & 0o027
                or stat.S_IMODE(info.st_mode) & 0o700 != 0o700):
            raise Ditolak()
        for path, minimum in ((DATA, 1024 ** 3), (DISK_DOCKER, 2 * 1024 ** 3)):
            isi = os.statvfs(path)
            if isi.f_bavail * isi.f_frsize < minimum or isi.f_favail < 8192:
                raise Ditolak()

    @contextlib.contextmanager
    def konfigurasi(self):
        # Snapshot kedua envfile menjamin recovery memakai byte konfigurasi yang sama.
        isi_env = [baca_privat(path, 65536, config=True) for path in ENVFILES]
        rahasia = baca_privat(KUNCI, kunci=True).strip()
        if not rahasia or any(c in rahasia for c in "\r\n\x00"):
            raise Ditolak()
        lingkungan = dict(LINGKUNGAN, DEEPSEEK_API_KEY=rahasia)
        with tempfile.TemporaryDirectory(prefix=".deploy-", dir=AKAR) as folder:
            paths = []
            for urut, isi in enumerate(isi_env):
                path = Path(folder) / (str(urut) + ".env")
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as berkas:
                    berkas.write(isi)
                paths.append(str(path))
            yield tuple(paths), lingkungan


class Docker:
    """Wrapper argv privat, bukan executor shell atau perintah dari SSH."""

    def __init__(self, runner=subprocess.run):
        self.runner = runner

    def _panggil(self, argumen, *, batas=30, masukan=None, lingkungan=None):
        hasil = self.runner(
            [DOCKER, *argumen], input=masukan, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=batas, check=False,
            shell=False, env=dict(LINGKUNGAN if lingkungan is None else lingkungan),
        )
        if hasil.returncode != 0:
            raise Ditolak()
        return hasil.stdout.strip()

    def revision_image(self, identitas):
        return self._panggil([
            "image", "inspect", "--format",
            '{{index .Config.Labels "org.opencontainers.image.revision"}}', identitas,
        ])

    def kontrak_image(self, image):
        """Baca hanya source image dalam sandbox; tidak memberi akses volume produksi."""
        if re.fullmatch(DIGEST, image) is None:
            raise Ditolak()
        return self._probe(image, PROBE_KONTRAK)

    def _probe(self, image, sumber):
        token = secrets.token_hex(16)
        nama = PROBE + "-" + token
        try:
            return self._panggil([
                "run", "--pull", "never", "--rm", "-i", "--name", nama,
                "--label", LABEL_PROBE + "=" + token,
                "--network", "none", "--read-only",
                *PENGAMAN, "--tmpfs", "/data:rw,nosuid,nodev,noexec,uid=10001,gid=10001,mode=0700,size=64m",
                "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=16m", "--entrypoint", "python",
                image, "-E", "-B", "-",
            ], batas=60, masukan=sumber)
        except (Exception, KeyboardInterrupt):
            # Timeout client bukan bukti container berhenti. Hapus hanya probe sendiri.
            self.bersihkan_probe(nama, token)
            raise

    def siapkan_image(self, digest):
        image = REGISTRI + "@" + digest
        self._panggil(["pull", image], batas=300)
        identitas = self._panggil(["image", "inspect", "--format", "{{.Id}}", image])
        if re.fullmatch(DIGEST, identitas) is None:
            raise Ditolak()
        daftar = json.loads(self._panggil(
            ["image", "inspect", "--format", "{{json .RepoDigests}}", image]))
        if not isinstance(daftar, list) or image not in daftar:
            raise Ditolak()
        if self._probe(image, PROBE_IMAGE) != "OSN_IMAGE_ADMIN7_AI2_OK":
            raise Ditolak()
        return identitas

    def bersihkan_probe(self, nama, token):
        # Name conflict bukan bukti ownership. Timeout mungkin sudah create walau
        # CLI tidak memberi ID. Temukan exact name lalu buktikan label; hapus via ID
        # agar name reuse di antara inspect/rm tidak menghapus milik invocation lain.
        identitas = self._panggil([
            "container", "ls", "--all", "--no-trunc", "--filter", "name=^/" + nama + "$",
            "--format", "{{.ID}}",
        ])
        if not identitas:
            return
        if re.fullmatch(r"[0-9a-f]{64}", identitas) is None:
            raise Ditolak()
        pemilik = self._panggil([
            "container", "inspect", "--format",
            '{{.Name}}|{{index .Config.Labels "' + LABEL_PROBE + '"}}', identitas,
        ])
        if pemilik != "/" + nama + "|" + token:
            raise Ditolak()
        self._panggil(["rm", "--force", identitas])

    def state(self):
        jawaban = self._panggil(["container", "inspect", "--format", FORMAT_STATE, KONTAINER])
        bagian = jawaban.split("|")
        if len(bagian) != 4 or re.fullmatch(DIGEST, bagian[3]) is None:
            raise Ditolak()
        return tuple(bagian)

    def image_saat_ini(self):
        status, berjalan, _, identitas = self.state()
        # B2 dapat menahan writer dengan retained container yang sudah distop.
        if (status, berjalan) not in (("running", "true"), ("exited", "false")):
            raise Ditolak()
        hasil = self._panggil(["image", "inspect", "--format", "{{.Id}}", identitas])
        if hasil != identitas:
            raise Ditolak()
        return identitas

    def hentikan(self):
        self._panggil(["stop", "--time", "30", KONTAINER], batas=45)

    def hapus(self):
        # Tanpa --force: jangan membunuh writer yang status stop-nya tak pasti.
        self._panggil(["rm", KONTAINER])

    def bersihkan_gagal(self):
        # Run dapat gagal sebelum/SESUDAH create. Jangan menafsirkan semua inspect-error
        # sebagai absent (daemon mati/permission bukan bukti volume bebas writer).
        daftar = json.loads(self._panggil([
            "container", "ls", "--all", "--filter", "name=^/osn-mesin$",
            "--format", "{{json .Names}}",
        ]) or '""')
        if daftar == "":
            return
        if daftar != KONTAINER:
            raise Ditolak()
        self.hentikan()
        self.hapus()

    def jalankan(self, digest, konfigurasi):
        paths, lingkungan = konfigurasi
        argv = ["run", "--pull", "never", "--detach", "--name", KONTAINER,
                "--restart", "unless-stopped",
                *PENGAMAN, "--publish", "127.0.0.1:8724:8724",
                "--mount", "type=bind,src=/opt/osn/data,dst=/data",
                # Rahasia pembayaran read-only. Jalur utama DAN recovery memakai
                # fungsi ini, jadi konfigurasi tetap identik saat rollback.
                "--mount", "type=bind,src=" + str(MIDTRANS) + ",dst=/run/secrets/midtrans,readonly"]
        for path in paths:
            argv.extend(["--env-file", path])
        for nilai in ENV_TETAP:
            argv.extend(["--env", nilai])
        # Nilai key tidak masuk argv, output, atau lingkungan pull/probe/inspect.
        argv.extend(["--env", "DEEPSEEK_API_KEY", REGISTRI + "@" + digest])
        self._panggil(argv, batas=60, lingkungan=lingkungan)

    def skema_sehat(self):
        return self._panggil(
            ["exec", "-i", KONTAINER, "python", "-E", "-B", "-"],
            batas=10, masukan=PROBE_SKEMA,
        ) == "OSN_SCHEMA_ADMIN7_AI2_OK"


class _TanpaRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def akun_terjaga():
    """Loopback tanpa proxy, credential, redirect, atau pembacaan body akun."""
    pembuka = urllib.request.build_opener(urllib.request.ProxyHandler({}), _TanpaRedirect())
    try:
        with pembuka.open("http://127.0.0.1:8724/akun", timeout=3) as hasil:
            return hasil.status == 401
    except urllib.error.HTTPError as galat:
        try:
            return galat.code == 401
        finally:
            galat.close()
    except (OSError, urllib.error.URLError):
        return False


def tunggu_sehat(docker, identitas, http, monotonic, tidur):
    akhir = monotonic() + BATAS_HEALTH
    while monotonic() < akhir:
        status, berjalan, health, image = docker.state()
        # Early exit/restarting serta image yang keliru bukan sekadar health starting.
        if status != "running" or berjalan != "true" or image != identitas:
            return False
        if health in ("unhealthy", "missing"):
            return False
        if health == "healthy" and http() and docker.skema_sehat():
            return True
        tidur(JEDA_HEALTH)
    return False


def deploy(teks, *, docker=None, berkas=None, sekarang=time.time,
           monotonic=time.monotonic, tidur=time.sleep, http=akun_terjaga, lapor=print):
    """State machine: semua preflight selesai sebelum stop; recovery bukan rollback DB."""
    docker = Docker() if docker is None else docker
    berkas = Berkas() if berkas is None else berkas
    tahap = "preflight"
    try:
        rutin = isinstance(teks, str) and teks.startswith("deploy-rutin-v1 ")
        kandidat, pemulihan = parse_rutin(teks) if rutin else parse_permintaan(teks)
        berkas.periksa_host()
        with berkas.kunci(), berkas.konfigurasi() as konfigurasi:
            if rutin:
                policy = berkas.policy_rutin()
            else:
                approval = berkas.approval(kandidat, pemulihan, sekarang())
            berkas.ruang()
            id_kandidat = docker.siapkan_image(kandidat)
            id_pemulihan = docker.siapkan_image(pemulihan)
            if id_kandidat == id_pemulihan:
                raise Ditolak()
            # Berlaku pada rutin DAN deploy-v2. Approval operator tidak membuat
            # recovery lama kompatibel dengan schema/receipt kandidat baru.
            kontrak_kandidat = docker.kontrak_image(id_kandidat)
            if kontrak_kandidat != docker.kontrak_image(id_pemulihan):
                raise Ditolak()
            id_lama = docker.image_saat_ini()  # Bukan fallback otomatis schema3.
            berkas.ruang()  # Pull dapat menghabiskan ruang yang tadi masih tersedia.
            if rutin:
                # Build ulang SHA recovery dapat menghasilkan digest baru. Tetap
                # gunakan digest exact CI, tetapi policy mematok revision+kontrak.
                if docker.revision_image(id_pemulihan) != policy["recovery_revision"]:
                    raise Ditolak()
                for identitas in (id_lama, id_kandidat, id_pemulihan):
                    if docker.kontrak_image(identitas) != policy["contract_sha256"]:
                        raise Ditolak()
                # Readiness current nyata, bukan hanya deklarasi policy atau probe kosong.
                if not tunggu_sehat(docker, id_lama, http, monotonic, tidur):
                    raise Ditolak()
                if berkas.policy_rutin() != policy:
                    raise Ditolak()
                if id_lama == id_kandidat:
                    berkas.tulis_pasangan(docker.revision_image(id_kandidat), id_kandidat,
                                          kontrak_kandidat, "rutin")
                    lapor("Candidate sudah aktif dan sehat; tidak ada swap. Exit 0.")
                    return 0
            else:
                if berkas.approval(kandidat, pemulihan, sekarang()) != approval:
                    raise Ditolak()
                berkas.konsumsi(approval, sekarang())  # O_EXCL + fsync, di bawah lock
                # Fsync lambat tidak memperpanjang lease; receipt tetap hangus.
                validasi_approval(json.dumps(approval), kandidat, pemulihan, sekarang())
            # Artefak pasangan SEBELUM swap: container baru harus sudah dapat
            # membacanya saat start (runtime dipasang sekali per proses). Gagal
            # tulis = preflight ditolak; container lama tidak disentuh.
            berkas.tulis_pasangan(docker.revision_image(id_kandidat), id_kandidat,
                                  kontrak_kandidat, "rutin" if rutin else "migrasi")
            tahap = "stop-awal"
            docker.hentikan()
            tahap = "hapus-awal"
            docker.hapus()
            tahap = "candidate"
            try:
                docker.jalankan(kandidat, konfigurasi)
                if not tunggu_sehat(docker, id_kandidat, http, monotonic, tidur):
                    raise Ditolak()
            except (Exception, KeyboardInterrupt):
                tahap = "recovery"
                # Gagal cleanup => jangan menjalankan recovery dengan writer saingan.
                docker.bersihkan_gagal()
                docker.jalankan(pemulihan, konfigurasi)
                if not tunggu_sehat(docker, id_pemulihan, http, monotonic, tidur):
                    raise Ditolak()
                lapor("Rilis gagal; recovery sehat. Exit 1." if rutin else
                      "Rilis gagal; recovery sehat. Writehold/maintenance tetap; exit 1.")
                return 1
            lapor("Candidate sehat; deploy rutin selesai. Exit 0." if rutin else
                  "Candidate sehat. Writehold/maintenance tetap; exit 0.")
            return 0
    except (Exception, KeyboardInterrupt):
        if tahap == "preflight":
            lapor("Preflight ditolak; container lama tidak disentuh. Exit 2.")
        else:
            lapor("Deploy gagal; perlu intervensi manual. Exit 2." if rutin else
                  "Deploy gagal; perlu intervensi manual. Writehold/maintenance tetap; exit 2.")
        return 2


def main(argv=None, environ=None):
    """Terima forced-command langsung atau satu argumen dari wrapper sudo."""
    argv = sys.argv[1:] if argv is None else argv
    environ = os.environ if environ is None else environ
    if len(argv) > 1:
        print("Argumen CLI ditolak; gunakan forced-command. Exit 2.")
        return 2
    perintah = argv[0] if argv else environ.get("SSH_ORIGINAL_COMMAND", "")
    return deploy(perintah)


def _terputus(nomor, frame):
    # Hindari interupsi kedua ketika sedang memastikan cleanup/recovery.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    raise InterruptedError()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _terputus)
    signal.signal(signal.SIGHUP, _terputus)
    sys.exit(main())
