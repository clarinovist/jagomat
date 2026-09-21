"""Receipt profil sekolah admin, terpisah dari receipt level historis."""
import sqlite3
import time
from pathlib import Path

import admin_accounts
from admin_contracts import HASIL_PER_AKSI, ReceiptProfilSiswa, receipt_cocok, sidik_perintah
import learning_profile


DDL = '''
CREATE TABLE IF NOT EXISTS operasi_admin_profil (
    operasi_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    siswa_id INTEGER NOT NULL,
    revisi_awal INTEGER NOT NULL CHECK(revisi_awal >= 0),
    revisi_hasil INTEGER NOT NULL CHECK(revisi_hasil >= revisi_awal),
    kelas_lama TEXT NOT NULL CHECK(kelas_lama IN ('','1','2','3','4','5','6')),
    kelas_baru TEXT NOT NULL CHECK(kelas_baru IN ('','1','2','3','4','5','6')),
    sidik_perintah TEXT NOT NULL CHECK(length(sidik_perintah)=64),
    dibuat INTEGER NOT NULL
);
'''


def _receipt(baris, perintah):
    if baris is None:
        return None
    from admin_students import KonflikSiswa
    receipt = ReceiptProfilSiswa(
        1, baris['operasi_id'], baris['actor_id'], perintah.aksi,
        'student_%d' % baris['siswa_id'], None, baris['revisi_awal'],
        baris['revisi_hasil'], HASIL_PER_AKSI[perintah.aksi], baris['dibuat'],
        baris['sidik_perintah'], (('student_school_grade', baris['kelas_lama'], baris['kelas_baru']),),
    )
    kelas = '' if perintah.kelas_sekolah is None else str(perintah.kelas_sekolah)
    if not receipt_cocok(receipt, perintah) or baris['kelas_baru'] != kelas:
        raise KonflikSiswa('receipt profil tidak cocok')
    return receipt


def baca_receipt(path_db, path_auth, perintah):
    """Replay wajib actor mutakhir, dengan urutan lock DB→auth."""
    from admin_students import DomainSiswaTidakSah
    kon = sqlite3.connect(Path(path_db).resolve().as_uri() + '?mode=rw', uri=True, timeout=5)
    kon.row_factory = sqlite3.Row
    try:
        kon.execute('BEGIN IMMEDIATE')
        with admin_accounts.kunci_actor(path_auth, perintah):
            hasil = _receipt(kon.execute('SELECT * FROM operasi_admin_profil WHERE operasi_id=?', (perintah.operasi_id,)).fetchone(), perintah)
        return hasil
    except sqlite3.Error as galat:
        raise DomainSiswaTidakSah('receipt profil tidak tersedia') from galat
    finally:
        kon.rollback()
        kon.close()


def ubah_domain(path_db, path_auth, perintah, *, sekarang=None, failpoint=None):
    """Kelas+receipt atomik; tidak ada pemanggilan ganti_level atau tulis bukti."""
    from admin_students import KonflikSiswa
    kon = sqlite3.connect(Path(path_db).resolve().as_uri() + '?mode=rw', uri=True, timeout=5)
    kon.row_factory = sqlite3.Row
    try:
        kon.execute('PRAGMA foreign_keys=ON')
        kon.execute('BEGIN IMMEDIATE')
        with admin_accounts.kunci_actor(path_auth, perintah):
            lama = _receipt(kon.execute('SELECT * FROM operasi_admin_profil WHERE operasi_id=?', (perintah.operasi_id,)).fetchone(), perintah)
            if lama is not None:
                return lama
            siswa = kon.execute('SELECT pemilik FROM siswa WHERE id=?', (perintah.siswa_id,)).fetchone()
            if siswa is None:
                raise KonflikSiswa('profil tidak tersedia')
            # Actor admin telah terkunci; owner berasal dari resource DB, bukan payload.
            sebelum = learning_profile.baca(kon, perintah.siswa_id, pemilik=siswa['pemilik'])
            sesudah = learning_profile.simpan_kelas(
                kon, perintah.siswa_id, perintah.kelas_sekolah,
                revisi=perintah.revisi_profil, pemilik=siswa['pemilik'],
            )
            kelas_lama = '' if sebelum.kelas_sekolah is None else str(sebelum.kelas_sekolah)
            kelas_baru = '' if sesudah.kelas_sekolah is None else str(sesudah.kelas_sekolah)
            kon.execute('INSERT INTO operasi_admin_profil VALUES(?,?,?,?,?,?,?,?,?)', (
                perintah.operasi_id, perintah.actor_id, perintah.siswa_id,
                sebelum.revisi, sesudah.revisi, kelas_lama, kelas_baru,
                sidik_perintah(perintah), int(time.time()) if sekarang is None else int(sekarang),
            ))
            receipt = _receipt(kon.execute('SELECT * FROM operasi_admin_profil WHERE operasi_id=?', (perintah.operasi_id,)).fetchone(), perintah)
            if failpoint == 'sebelum_commit':
                raise RuntimeError('failpoint profil sebelum commit')
            kon.commit()
        if failpoint == 'setelah_commit':
            raise RuntimeError('failpoint profil setelah commit')
        return receipt
    except (learning_profile.KonflikProfil, learning_profile.ProfilTidakDitemukan) as galat:
        raise KonflikSiswa('profil berubah atau tidak tersedia') from galat
    finally:
        if kon.in_transaction:
            kon.rollback()
        kon.close()
