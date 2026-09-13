"""Riwayat AI tingkat operasi; pembacaan tidak membuat storage."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import re
import sqlite3
import time


@dataclass(frozen=True)
class EntriRiwayatAI:
    sumber: str
    operasi_id: Optional[str]
    actor_id: Optional[str]
    aksi: str
    status: str
    dibuat: int
    revisi: Optional[int]


@dataclass(frozen=True)
class HalamanRiwayatAI:
    item: Tuple[EntriRiwayatAI, ...]
    total: int
    halaman: int
    per_halaman: int
    jumlah_halaman: int


def riwayat_operasi(path, *, actor_id='', aksi='', mulai=None, selesai=None,
                    halaman=1, per_halaman=25, sekarang=None):
    """Group konfigurasi per revisi, tes dengan actor hanya sejak cutover."""
    if (type(halaman) is not int or halaman < 1 or type(per_halaman) is not int
            or not 1 <= per_halaman <= 100):
        raise ValueError('Paginasi audit tidak sah.')
    if actor_id and (type(actor_id) is not str or re.fullmatch(r'akun_[0-9a-f]{32}', actor_id) is None):
        raise ValueError('Filter pengelola tidak sah.')
    if aksi not in ('', 'ai_settings_update', 'ai_synthetic_test'):
        raise ValueError('Filter aksi tidak sah.')
    for batas in (mulai, selesai):
        if batas is not None and (type(batas) is not int or batas < 0):
            raise ValueError('Waktu tidak sah.')
    if mulai is not None and selesai is not None and mulai > selesai:
        raise ValueError('Rentang waktu tidak sah.')
    kini = int(time.time()) if sekarang is None else sekarang
    query = """SELECT 'ai_config' AS sumber,o.operasi_id,o.actor_id,
                 'ai_settings_update' AS aksi,'succeeded' AS status,o.dibuat,o.revisi_hasil AS revisi
               FROM operasi_pengaturan_admin o
               UNION ALL
               SELECT 'ai_config',NULL,a.actor_id,'ai_settings_update','succeeded',MAX(a.dibuat),a.revisi
               FROM audit_konfigurasi a WHERE NOT EXISTS (
                 SELECT 1 FROM operasi_pengaturan_admin o WHERE o.revisi_hasil=a.revisi)
               GROUP BY a.revisi,a.actor_id
               UNION ALL
               SELECT 'ai_test',operasi_id,actor_id,'ai_synthetic_test',
                 CASE status WHEN 'selesai' THEN 'succeeded' WHEN 'dicadangkan' THEN 'pending'
                 WHEN 'dibatalkan' THEN 'cancelled' ELSE 'uncertain' END,dibuat,NULL
               FROM audit_uji_admin
               UNION ALL
               SELECT 'ai_test',l.operasi_id,NULL,'ai_synthetic_test',
                 CASE l.status WHEN 'selesai' THEN 'succeeded' WHEN 'dicadangkan' THEN 'pending'
                 WHEN 'dibatalkan' THEN 'cancelled' ELSE 'uncertain' END,l.dibuat,NULL
               FROM ledger l WHERE l.fitur='uji_sintetis' AND NOT EXISTS (
                 SELECT 1 FROM audit_uji_admin a WHERE a.operasi_id=l.operasi_id)"""
    clauses=['(dibuat>=? OR status=?)'];args=[kini-180*86400,'pending']
    for key,value,op in [('actor_id',actor_id,'='),('aksi',aksi,'='),('dibuat',mulai,'>='),('dibuat',selesai,'<=')]:
        if value is not None and value!='':
            clauses.append(key+op+'?');args.append(value)
    where=' WHERE '+' AND '.join(clauses)
    kon=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        kon.execute('PRAGMA query_only=ON')
        total=kon.execute('SELECT COUNT(*) FROM ('+query+')'+where,args).fetchone()[0]
        rows=kon.execute('SELECT * FROM ('+query+')'+where+' ORDER BY dibuat DESC,sumber,revisi DESC,operasi_id DESC LIMIT ? OFFSET ?',args+[per_halaman,(halaman-1)*per_halaman]).fetchall()
        item=tuple(EntriRiwayatAI(*row) for row in rows)
        return HalamanRiwayatAI(item,total,halaman,per_halaman,max(1,(total+per_halaman-1)//per_halaman))
    finally:
        kon.close()
