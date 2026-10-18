"""Rekonsiliasi sumber sensor memakai ID saja; tidak membaca isi keluarga."""
from contextlib import closing
from pathlib import Path
import sqlite3

import sensor_schema
import sensor_store as s

# Cursor proses hanya optimasi jadwal; restart mulai lagi, bukan memperpanjang TTL.
_cursor = {}


def bersihkan(path_admin, path_belajar, path_pendamping, path_auth, *, sekarang):
    """Batch berjalan maju; snapshot sumber dan kandidat purge diserialkan sink."""
    import admin_store
    import auth
    with admin_store.buka_baca(path_admin) as kon:
        if not sensor_schema.validasi(kon):
            return
    key = str(Path(path_admin).resolve())
    with s.buka(path_admin) as kon:
        peserta = list(kon.execute('SELECT akun_id FROM sensor_peserta WHERE akun_id>? ORDER BY akun_id LIMIT 100', (_cursor.get(key, ''),)))
    if not peserta:
        _cursor.pop(key, None)
        return
    akun_aktif = {a.get('id_akun'): a for a in auth.muat_akun(Path(path_auth))}
    for kandidat in peserta:
        # Urutan lock: sink sensor, kemudian reader metadata. Hook menggunakan
        # urutan sama setelah transaksi domain selesai; tidak menahan writer belajar.
        with s.buka(path_admin, tulis=True) as kon:
            p = kon.execute('SELECT * FROM sensor_peserta WHERE akun_id=?', (kandidat['akun_id'],)).fetchone()
            if p is None:
                _cursor[key] = kandidat['akun_id']
                continue
            sumber = s.Izin(p['akun_id'],p['generasi'],p['salt'],p['mulai'],p['berakhir'],bool(p['hasil']),bool(p['chat']))
            akun = akun_aktif.get(p['akun_id'])
            sesi_sah = set(); chat_sah = set()
            if akun and not akun.get('dinonaktifkan'):
                with closing(sqlite3.connect(Path(path_belajar).resolve().as_uri()+'?mode=rw',uri=True,timeout=.05)) as c:
                    c.execute('PRAGMA query_only=ON')
                    sesi_sah = {s.token(sumber,'sesi',r[0]) for r in c.execute(
                        'SELECT x.id FROM sesi x JOIN siswa w ON w.id=x.siswa_id WHERE w.pemilik=?',
                        (akun['pengguna'],))}
                if p['chat'] and Path(path_pendamping).exists():
                    with closing(sqlite3.connect(Path(path_pendamping).resolve().as_uri()+'?mode=rw',uri=True,timeout=.05)) as c:
                        c.execute('PRAGMA query_only=ON')
                        chat_sah = {s.token(sumber,'chat',r[0]) for r in c.execute(
                            "SELECT o.request_id FROM operasi o JOIN chat c ON c.id=o.chat_id "
                            "WHERE o.account_id=? AND o.status='selesai' AND c.dihapus IS NULL "
                            "AND EXISTS(SELECT 1 FROM persetujuan p WHERE p.account_id=o.account_id "
                            "AND p.kategori='chat_umum' AND p.dicabut IS NULL)", (p['akun_id'],))}
            for row in list(kon.execute('SELECT token FROM sensor_episode WHERE peserta=?',(p['generasi'],))):
                if row['token'] not in sesi_sah:
                    kon.execute('DELETE FROM sensor_episode WHERE peserta=? AND token=?',(p['generasi'],row['token']))
            for row in list(kon.execute('SELECT token FROM sensor_chat WHERE peserta=?',(p['generasi'],))):
                if row['token'] not in chat_sah:
                    kon.execute('DELETE FROM sensor_chat WHERE peserta=? AND token=?',(p['generasi'],row['token']))
        _cursor[key] = kandidat['akun_id']
