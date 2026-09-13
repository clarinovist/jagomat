"""Proyeksi readonly audit AI untuk admin; tanpa payload atau panggilan provider."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from typing import Optional, Tuple

import ai_policy


@dataclass(frozen=True)
class EntriAI:
    sumber: str
    id: str
    actor_id: str
    aksi: str
    status: str
    dibuat: int
    field: Optional[str] = None


@dataclass(frozen=True)
class HalamanAI:
    item: Tuple[EntriAI, ...]
    total: int
    halaman: int
    per_halaman: int


def daftar_riwayat(path, *, actor_id='', aksi='', mulai=None, selesai=None,
                    halaman=1, per_halaman=25):
    """Baca konfigurasi dan tes dari sumber AI sendiri, bukan salinan audit."""
    if (type(halaman) is not int or halaman < 1 or type(per_halaman) is not int
            or not 1 <= per_halaman <= 100):
        raise ValueError('Paginasi audit AI tidak sah.')
    if actor_id and (type(actor_id) is not str or re.fullmatch(r'akun_[0-9a-f]{32}', actor_id) is None):
        raise ValueError('Filter pengelola tidak sah.')
    if aksi not in ('', 'ai_settings_update', 'ai_synthetic_test'):
        raise ValueError('Filter aksi AI tidak sah.')
    for batas in (mulai, selesai):
        if batas is not None and (type(batas) is not int or batas < 0):
            raise ValueError('Waktu audit AI tidak sah.')
    if mulai is not None and selesai is not None and mulai > selesai:
        raise ValueError('Rentang waktu tidak sah.')
    query = """SELECT 'konfigurasi' AS sumber, CAST(id AS TEXT) AS id, actor_id,
                      'ai_settings_update' AS aksi, 'selesai' AS status, dibuat, field
               FROM audit_konfigurasi
               UNION ALL
               SELECT 'tes',operasi_id,actor_id,'ai_synthetic_test',status,dibuat,NULL
               FROM audit_uji_admin"""
    kondisi=[]; args=[]
    for nama, nilai, op in (('actor_id',actor_id,'='), ('aksi',aksi,'='),
                           ('dibuat',mulai,'>='), ('dibuat',selesai,'<=')):
        if nilai is not None and nilai != '':
            kondisi.append(nama + op + '?'); args.append(nilai)
    where=' WHERE '+' AND '.join(kondisi) if kondisi else ''
    kon=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)
    kon.row_factory=sqlite3.Row
    try:
        kon.execute('PRAGMA query_only=ON')
        total=kon.execute('SELECT COUNT(*) FROM ('+query+')'+where,args).fetchone()[0]
        rows=kon.execute('SELECT * FROM ('+query+')'+where+' ORDER BY dibuat DESC,sumber,id DESC LIMIT ? OFFSET ?',
                         args+[per_halaman,(halaman-1)*per_halaman]).fetchall()
    finally:
        kon.close()
    fields={'dihentikan','request_akun_harian','uji_harian','uji_cooldown_detik'}
    fields |= {f'aktif_{f}' for f in ai_policy.FITUR}
    fields |= {f'{periode}_{f}' for periode in ('harian','bulanan') for f in ('global',*ai_policy.FITUR)}
    item=tuple(EntriAI(r['sumber'],r['id'],r['actor_id'],r['aksi'],r['status'],r['dibuat'],
                      r['field'] if r['field'] in fields else None) for r in rows)
    return HalamanAI(item,total,halaman,per_halaman)
