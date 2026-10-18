"""Sensor privat best-effort: consent terpisah, sumber baru, tanpa teks mentah."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
from pathlib import Path
import secrets
import sqlite3
import threading

import admin_store
import sensor_domain as d
import sensor_schema

import policy_store

# Epoch host berada di luar bundle DB: stabil saat restart, wajib dirotasi
# sebelum restore. Jalur legacy tetap terisolasi untuk reader recovery lama.
BOOT = policy_store.EPOCH
GAGAL = False
_kunci = threading.Lock()


@dataclass(frozen=True)
class Izin:
    akun_id: str
    generasi: str
    salt: str
    mulai: int
    berakhir: int
    hasil: bool
    chat: bool


def waktu(nilai):
    if type(nilai) is not int or not 0 <= nilai <= 253370000000:
        raise ValueError('waktu sensor tidak sah')
    return nilai


def gangguan():
    global GAGAL
    with _kunci:
        GAGAL = True


@contextmanager
def buka(path, *, tulis=False):
    kon = sqlite3.connect(Path(path).resolve().as_uri() + ('?mode=rw' if tulis else '?mode=ro'),
                          uri=True, timeout=.05)
    kon.row_factory = sqlite3.Row
    try:
        kon.execute('PRAGMA foreign_keys=ON')
        if not tulis:
            kon.execute('PRAGMA query_only=ON')
        kon.execute('BEGIN IMMEDIATE' if tulis else 'BEGIN')
        if not sensor_schema.validasi(kon):
            raise admin_store.StoreBelumSiap('sensor belum dipasang')
        yield kon
        if tulis:
            kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()


def _izin(row, sekarang):
    if (not policy_store.epoch_sah() or row is None or row['boot'] != BOOT or row['versi_consent'] != d.CONSENT
            or not row['mulai'] <= sekarang < row['berakhir']):
        return None
    return Izin(row['akun_id'], row['generasi'], row['salt'], row['mulai'],
                row['berakhir'], bool(row['hasil']), bool(row['chat']))


def izin(path, akun_id, *, sekarang):
    waktu(sekarang)
    with buka(path) as kon:
        return _izin(kon.execute('SELECT * FROM sensor_peserta WHERE akun_id=?', (akun_id,)).fetchone(), sekarang)


def setuju(path, path_auth, principal, *, hasil, chat, sekarang):
    """Setiap perubahan izin memulai cohort baru dan menghapus derivasi lama."""
    import admin_launch_service
    waktu(sekarang)
    if not policy_store.epoch_sah() or type(hasil) is not bool or type(chat) is not bool:
        raise ValueError('pilihan sensor tidak sah')
    with admin_launch_service.kunci_principal(path_auth, principal, 'guru'):
        with buka(path, tulis=True) as kon:
            kon.execute('DELETE FROM sensor_peserta WHERE akun_id=?', (principal.id_akun,))
            kon.execute('INSERT INTO sensor_peserta VALUES(?,?,?,?,?,?,?,?,?)', (
                principal.id_akun, secrets.token_hex(16), secrets.token_hex(32), BOOT,
                sekarang, sekarang + d.RETENSI_CONSENT, d.CONSENT, int(hasil), int(chat)))


def cabut(path, path_auth, principal):
    import admin_launch_service
    with admin_launch_service.kunci_principal(path_auth, principal, 'guru'):
        with buka(path, tulis=True) as kon:
            kon.execute('DELETE FROM sensor_peserta WHERE akun_id=?', (principal.id_akun,))
            policy_store.cabut_dalam_transaksi(kon, principal.id_akun)


def token(izin_sumber, jenis, identitas):
    """HMAC namespace + sumber kanonis, salt berbeda setiap consent."""
    if jenis not in ('sesi', 'chat') or not str(identitas) or len(str(identitas)) > 200:
        raise ValueError('sumber sensor tidak sah')
    return hmac.new(bytes.fromhex(izin_sumber.salt),
                    (jenis + ':' + str(identitas)).encode(), hashlib.sha256).hexdigest()


def _masih_sah(kon, sumber, sekarang):
    row = kon.execute('SELECT * FROM sensor_peserta WHERE akun_id=?', (sumber.akun_id,)).fetchone()
    return _izin(row, sekarang) == sumber


def catat_sesi(path, sumber, sesi_id, *, kode, dibuat, jalur, sekarang, hasil=None,
               validasi_sumber=None):
    """Milestone sekali per episode; tidak merekonstruksi milestone yang hilang."""
    waktu(sekarang); waktu(dibuat)
    if kode not in d.EVENT or jalur not in ('manual', 'terpandu'):
        raise ValueError('event sensor tidak sah')
    if dibuat <= sumber.mulai or dibuat > sekarang or sekarang >= dibuat + d.RETENSI_DETAIL:
        return False
    ref = token(sumber, 'sesi', sesi_id)
    with buka(path, tulis=True) as kon:
        if not _masih_sah(kon, sumber, sekarang):
            return False
        if validasi_sumber is not None and not validasi_sumber():
            return False
        if kode == 'disiapkan':
            kon.execute('INSERT OR IGNORE INTO sensor_episode VALUES(?,?,?,?)',
                        (sumber.generasi, ref, jalur, sekarang))
        episode = kon.execute('SELECT mulai FROM sensor_episode WHERE peserta=? AND token=?',
                              (sumber.generasi, ref)).fetchone()
        if episode is None or sekarang >= episode['mulai'] + d.RETENSI_DETAIL:
            return False
        cursor = kon.execute('INSERT OR IGNORE INTO sensor_event VALUES(?,?,?,?)',
                             (sumber.generasi, ref, kode, sekarang // 3600))
        if cursor.rowcount and kode == 'dikonfirmasi' and hasil is not None and sumber.hasil:
            hasil = hasil() if callable(hasil) else hasil
            if hasil is None:
                return bool(cursor.rowcount)
            keys = ('jumlah','benar','belum_jelas','kode_b','kode_k','kode_h','kode_e','kode_n','kode_t')
            if set(hasil) != set(keys) or any(type(hasil[k]) is not int for k in keys):
                raise ValueError('ringkasan hasil tidak sah')
            if sum(hasil[k] for k in keys[1:]) != hasil['jumlah']:
                raise ValueError('komposisi hasil tidak sah')
            kon.execute('INSERT INTO sensor_hasil VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (sumber.generasi, ref, *(hasil[k] for k in keys)))
        return bool(cursor.rowcount)


def catat_chat(path, sumber, request_id, *, dibuat, sekarang, kategori, validasi_sumber=None):
    waktu(dibuat); waktu(sekarang)
    if not callable(kategori) and kategori not in d.KATEGORI_CHAT:
        raise ValueError('kategori chat tidak sah')
    if not sumber.chat or dibuat <= sumber.mulai or dibuat > sekarang:
        return False
    with buka(path, tulis=True) as kon:
        if not _masih_sah(kon, sumber, sekarang):
            return False
        ref = token(sumber, 'chat', request_id)
        if kon.execute('SELECT 1 FROM sensor_chat WHERE peserta=? AND token=?', (sumber.generasi, ref)).fetchone():
            return False
        if validasi_sumber is not None and not validasi_sumber():
            return False
        kategori = kategori() if callable(kategori) else kategori
        if kategori not in d.KATEGORI_CHAT:
            raise ValueError('kategori chat tidak sah')
        cursor = kon.execute('INSERT OR IGNORE INTO sensor_chat VALUES(?,?,?,?)',
                             (sumber.generasi, ref, kategori, sekarang // 3600))
        return bool(cursor.rowcount)


def retensi(path, *, sekarang):
    waktu(sekarang)
    # Optional namespace: janitor sebelum migrasi tetap sah.
    with admin_store.buka_baca(path) as kon:
        if not sensor_schema.validasi(kon):
            return
    with buka(path, tulis=True) as kon:
        kon.execute('DELETE FROM sensor_peserta WHERE rowid IN (SELECT rowid FROM sensor_peserta WHERE berakhir<=? LIMIT 500)', (sekarang,))
        kon.execute('DELETE FROM sensor_episode WHERE rowid IN (SELECT rowid FROM sensor_episode WHERE mulai<=? LIMIT 500)', (sekarang - d.RETENSI_DETAIL,))
        kon.execute('DELETE FROM sensor_chat WHERE rowid IN (SELECT rowid FROM sensor_chat WHERE jam<=? LIMIT 500)', ((sekarang - d.RETENSI_DETAIL) // 3600,))



def hapus_sumber_sesi(path, akun_id, sesi_id):
    """Purge sumber yang sudah dihapus; berlaku juga saat OFF/boot lama."""
    with buka(path, tulis=True) as kon:
        row = kon.execute('SELECT * FROM sensor_peserta WHERE akun_id=?', (akun_id,)).fetchone()
        if row is None:
            return
        sumber = Izin(row['akun_id'],row['generasi'],row['salt'],row['mulai'],row['berakhir'],bool(row['hasil']),bool(row['chat']))
        kon.execute('DELETE FROM sensor_episode WHERE peserta=? AND token=?',
                    (sumber.generasi, token(sumber,'sesi',sesi_id)))


def kesehatan(path, *, siap, sekarang):
    """Kesiapan bukan bukti delivery lengkap; zero-data tidak berarti zero-use."""
    waktu(sekarang)
    try:
        with admin_store.buka_baca(path) as kon:
            tersedia = sensor_schema.validasi(kon)
        if not tersedia:
            return {'status': 'belum_dipasang', 'peserta': None}
        with buka(path) as kon:
            aktif = kon.execute('SELECT COUNT(*) FROM sensor_peserta WHERE boot=? AND mulai<=? AND berakhir>?',
                                (BOOT, sekarang, sekarang)).fetchone()[0]
            lama = kon.execute('SELECT COUNT(*) FROM sensor_peserta WHERE boot!=? AND berakhir>?',
                               (BOOT, sekarang)).fetchone()[0]
        status = ('nonaktif' if not siap or not policy_store.epoch_sah() else 'terganggu' if GAGAL else
                  'menunggu_izin_ulang' if lama and not aktif else
                  'menunggu_peserta' if not aktif else 'siap_best_effort')
        return {'status': status, 'peserta': aktif}
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        return {'status': 'tidak_teramati', 'peserta': None}
