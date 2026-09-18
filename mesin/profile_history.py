"""Query riwayat profil terbatasi; caller wajib mengotorisasi siswa dahulu.

Tidak membuka koneksi sendiri dan tidak menulis DB. Semua filter nilai memakai
parameter SQL; pagination dijalankan sebelum proyeksi metadata per sesi.
"""
from dataclasses import dataclass, replace
from datetime import date
import re
from urllib.parse import parse_qsl, urlencode

from topics import daftar_topik

PER_HALAMAN = 20
TINJAUAN = (
    ('semua', 'Semua status'), ('belum_dikirim', 'Belum dikirim'),
    ('belum_ditinjau', 'Belum ditinjau'), ('dibuka', 'Sudah dibuka'),
    ('draf', 'Draf tinjauan'), ('dikonfirmasi', 'Hasil dikonfirmasi'),
    ('ulang', 'Perlu konfirmasi ulang'), ('dibatalkan', 'Dibatalkan'),
)


@dataclass(frozen=True)
class FilterProfil:
    section: str = 'latihan'
    halaman: int = 1
    mulai: str = ''
    sampai: str = ''
    topik: str = ''
    jenis: str = 'semua'
    tinjauan: str = 'semua'

    def tautan(self, siswa_id, halaman=None):
        nilai = {'section': 'riwayat'}
        for nama in ('mulai', 'sampai', 'topik', 'jenis', 'tinjauan'):
            isi = getattr(self, nama)
            if isi and isi != 'semua':
                nilai[nama] = isi
        nilai['halaman'] = self.halaman if halaman is None else halaman
        return '/anak/%d?%s' % (siswa_id, urlencode(nilai))


def parse_filter(query):
    """Tolak query ambigu; pesan/sorot warisan tetap ditangani router."""
    if len(query) > 2048 or re.search(r'%(?![0-9a-fA-F]{2})', query):
        raise ValueError('Parameter profil tidak sah.')
    pasangan = parse_qsl(query, keep_blank_values=True, errors='strict', max_num_fields=12)
    if len(pasangan) != len({k for k, _ in pasangan}):
        raise ValueError('Parameter profil ganda.')
    nilai = dict(pasangan)
    if set(nilai) - {'section', 'halaman', 'mulai', 'sampai', 'topik', 'jenis', 'tinjauan', 'pesan', 'sorot'}:
        raise ValueError('Parameter profil tidak dikenal.')
    section = nilai.get('section', 'latihan')
    halaman = nilai.get('halaman', '1')
    if section not in ('latihan', 'rencana', 'riwayat') or not re.fullmatch(r'[1-9][0-9]{0,5}', halaman):
        raise ValueError('Bagian atau halaman profil tidak sah.')
    for nama in ('mulai', 'sampai'):
        tanggal = nilai.get(nama, '')
        if tanggal and (not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', tanggal) or date.fromisoformat(tanggal).isoformat() != tanggal):
            raise ValueError('Tanggal tidak sah.')
    mulai, sampai = nilai.get('mulai', ''), nilai.get('sampai', '')
    if mulai and sampai and mulai > sampai:
        raise ValueError('Rentang tanggal terbalik.')
    topik = nilai.get('topik', '')
    jenis = nilai.get('jenis', 'semua')
    tinjauan = nilai.get('tinjauan', 'semua')
    if (topik and topik not in daftar_topik()) or jenis not in ('semua', 'bebas', 'terpandu') or tinjauan not in dict(TINJAUAN):
        raise ValueError('Filter riwayat tidak sah.')
    return FilterProfil(section, int(halaman), mulai, sampai, topik, jenis, tinjauan)


# Sama dengan badge profil: stamp tanpa snapshot atau fingerprint lama bukan bukti aktif.
_TERAKHIR = '(SELECT kh.fingerprint FROM konfirmasi_hasil kh WHERE kh.sesi_id=s.id ORDER BY kh.nomor_urut DESC, kh.id DESC LIMIT 1)'
_DRAF = 'EXISTS(SELECT 1 FROM tinjauan_guru tg JOIN sesi_soal ss ON ss.id=tg.sesi_soal_id WHERE ss.sesi_id=s.id)'
_AKTIF = '(s.dikonfirmasi_guru IS NOT NULL AND %s IS NOT NULL AND s.fingerprint_konfirmasi=%s)' % (_TERAKHIR, _TERAKHIR)
_STATUS = """CASE WHEN s.dibatalkan IS NOT NULL THEN 'dibatalkan'
 WHEN s.selesai IS NULL THEN 'belum_dikirim'
 WHEN COALESCE(%s,0) THEN 'dikonfirmasi'
 WHEN %s IS NOT NULL THEN 'ulang'
 WHEN %s THEN 'draf'
 WHEN s.direview IS NOT NULL THEN 'dibuka'
 ELSE 'belum_ditinjau' END""" % (_AKTIF, _TERAKHIR, _DRAF)
_PROYEKSI = """s.*, %s AS fingerprint_terakhir, %s AS ada_tinjauan,
 (SELECT COUNT(*) FROM sesi_soal ss WHERE ss.sesi_id=s.id) AS n,
 (SELECT COUNT(*) FROM sesi_soal ss JOIN jawaban j ON j.sesi_soal_id=ss.id WHERE ss.sesi_id=s.id) AS terisi,
 (SELECT MIN(j.dicatat) FROM sesi_soal ss JOIN jawaban j ON j.sesi_soal_id=ss.id WHERE ss.sesi_id=s.id) AS dicatat_awal,
 (SELECT MAX(j.dicatat) FROM sesi_soal ss JOIN jawaban j ON j.sesi_soal_id=ss.id WHERE ss.sesi_id=s.id) AS dicatat_akhir,
 (SELECT COUNT(*) FROM sesi_soal ss JOIN jawaban j ON j.sesi_soal_id=ss.id
 JOIN diagnosis d ON d.jawaban_id=j.id WHERE ss.sesi_id=s.id AND d.benar=1) AS benar
""" % (_TERAKHIR, _DRAF)


def jumlah_sesi(kon, siswa_id):
    return kon.execute('SELECT COUNT(*) FROM sesi WHERE siswa_id=?', (siswa_id,)).fetchone()[0]


def _muat(kon, siswa_id, where, parameter, limit, offset=0):
    # CTE mencegah metadata mahal dimuat untuk seluruh arsip.
    return kon.execute('WITH pilihan AS (SELECT s.id FROM sesi s WHERE s.siswa_id=? ' + where +
                       ' ORDER BY s.tanggal DESC,s.id DESC LIMIT ? OFFSET ?) SELECT ' + _PROYEKSI +
                       ' FROM sesi s JOIN pilihan p ON p.id=s.id ORDER BY s.tanggal DESC,s.id DESC',
                       (siswa_id,) + tuple(parameter) + (limit, offset)).fetchall()


def halaman_riwayat(kon, siswa_id, filter_data):
    """Kembalikan baris, total hasil, filter dengan halaman dijepit ke rentang."""
    syarat, parameter = [], []
    if filter_data.mulai:
        syarat.append('s.tanggal>=?')
        parameter.append(filter_data.mulai)
    if filter_data.sampai:
        syarat.append('substr(s.tanggal,1,10)<=?')
        parameter.append(filter_data.sampai)
    if filter_data.topik:
        syarat.append("(s.topik=? OR (s.topik LIKE 'gabungan:%' AND instr(','||substr(s.topik,10)||',',?)>0))")
        parameter.extend((filter_data.topik, ',' + filter_data.topik + ','))
    if filter_data.jenis != 'semua':
        syarat.append("s.tujuan='bebas'" if filter_data.jenis == 'bebas' else "s.tujuan<>'bebas'")
    if filter_data.tinjauan != 'semua':
        syarat.append('(' + _STATUS + ')=?')
        parameter.append(filter_data.tinjauan)
    where = ''.join(' AND ' + s for s in syarat)
    total = kon.execute('SELECT COUNT(*) FROM sesi s WHERE s.siswa_id=?' + where,
                        (siswa_id,) + tuple(parameter)).fetchone()[0]
    halaman = min(filter_data.halaman, max(1, (total + PER_HALAMAN-1)//PER_HALAMAN))
    filter_data = replace(filter_data, halaman=halaman)
    return _muat(kon,siswa_id,where,parameter,PER_HALAMAN,(halaman-1)*PER_HALAMAN), total, filter_data


def tugas_terbaru(kon, siswa_id, sorot=None):
    """Maksimal tiga sesi perlu tindakan; sorot PRG tetap child-bound."""
    where = " AND (s.dibatalkan IS NULL AND (s.selesai IS NULL OR NOT COALESCE(" + _AKTIF + ",0)))"
    baris = _muat(kon,siswa_id,where,(),3)
    if sorot and all(r['id'] != sorot for r in baris):
        terpilih = _muat(kon,siswa_id,' AND s.id=?',(sorot,),1)
        if terpilih:
            baris = terpilih + baris[:2]
    return baris
