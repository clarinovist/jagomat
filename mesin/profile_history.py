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
    ('semua', 'Semua status'), ('perlu_tinjauan', 'Perlu ditinjau'),
    ('belum_dikirim', 'Belum dikirim'),
    ('belum_ditinjau', 'Perlu ditinjau · belum dibuka'), ('dibuka', 'Perlu ditinjau · sudah dibuka'),
    ('draf', 'Draf tersimpan'), ('dikonfirmasi', 'Selesai'),
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
    q: str = ''

    def tautan(self, siswa_id, halaman=None):
        nilai = {'section': 'riwayat'}
        for nama in ('mulai', 'sampai', 'topik', 'jenis', 'tinjauan', 'q'):
            isi = getattr(self, nama)
            if isi and isi != 'semua':
                nilai[nama] = isi
        nilai['halaman'] = self.halaman if halaman is None else halaman
        return '/anak/%d?%s' % (siswa_id, urlencode(nilai))


def parse_filter(query):
    """Tolak query ambigu; pesan/sorot warisan tetap ditangani router."""
    if len(query) > 2048 or re.search(r'%(?![0-9a-fA-F]{2})', query):
        raise ValueError('Parameter profil tidak sah.')
    pasangan = parse_qsl(query, keep_blank_values=True, errors='strict', max_num_fields=24)
    if len(pasangan) != len({k for k, _ in pasangan}):
        raise ValueError('Parameter profil ganda.')
    nilai = dict(pasangan)
    if set(nilai) - {'section', 'bagian', 'halaman', 'mulai', 'sampai', 'topik', 'jenis', 'tinjauan', 'q', 'pesan', 'sorot', 'periode', 'materi', 'status', 'tampilan', 'rincian', 'mode_latihan'}:
        raise ValueError('Parameter profil tidak dikenal.')
    # Bare profil membuka Berikutnya. URL warisan PRG yang hanya membawa
    # ``sorot`` tetap membuka alat latihan agar sesi baru tidak terasa hilang.
    section = nilai.get('section', 'latihan' if 'sorot' in nilai else 'rencana')
    if section == 'perkembangan':
        # Tab laporan punya fallback aman sendiri (periode/halaman/materi tak sah
        # kembali ke default, bukan 500/404); tolak hanya query ganda/asing di atas.
        return FilterProfil(section='perkembangan', halaman=1)
    halaman = nilai.get('halaman', '1')
    if section not in ('latihan', 'rencana', 'riwayat', 'perkembangan') or not re.fullmatch(r'[1-9][0-9]{0,5}', halaman):
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
    cari = nilai.get('q', '').strip()
    if cari and (len(cari) > 64 or not re.fullmatch(r'[A-Za-z0-9 .#\-]{1,64}', cari)):
        raise ValueError('Pencarian riwayat tidak sah.')
    return FilterProfil(section, int(halaman), mulai, sampai, topik, jenis, tinjauan, cari)


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


_BENTUK_WAKTU = "%Y-%m-%d %H:%M:%S"


def durasi_detik(mulai, selesai, dicatat_awal=None, dicatat_akhir=None):
    """Detik pengerjaan: selesai - mulai, lalu jatuh ke rentang waktu jawaban tercatat.

    None bila tidak ada jejak waktu yang bermakna; durasi tidak pernah dikarang.
    """
    from datetime import datetime
    for awal, akhir in ((mulai, selesai), (dicatat_awal, dicatat_akhir)):
        if not awal or not akhir:
            continue
        try:
            detik = int((datetime.strptime(str(akhir), _BENTUK_WAKTU)
                         - datetime.strptime(str(awal), _BENTUK_WAKTU)).total_seconds())
        except ValueError:
            continue
        if detik > 0:
            return detik
    return None


def jumlah_sesi(kon, siswa_id):
    return kon.execute('SELECT COUNT(*) FROM sesi WHERE siswa_id=?', (siswa_id,)).fetchone()[0]


def _muat(kon, siswa_id, where, parameter, limit, offset=0, *, terlama=False):
    # Arah hanya konstanta internal; urutan diterapkan sebelum pembatasan CTE.
    urutan = 's.tanggal ASC,s.id ASC' if terlama else 's.tanggal DESC,s.id DESC'
    return kon.execute('WITH pilihan AS (SELECT s.id FROM sesi s WHERE s.siswa_id=? ' + where +
                       ' ORDER BY ' + urutan + ' LIMIT ? OFFSET ?) SELECT ' + _PROYEKSI +
                       ' FROM sesi s JOIN pilihan p ON p.id=s.id ORDER BY ' + urutan,
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
    if filter_data.tinjauan == 'perlu_tinjauan':
        syarat.append('(' + _STATUS + ") IN ('belum_ditinjau','dibuka','draf','ulang')")
    elif filter_data.tinjauan != 'semua':
        syarat.append('(' + _STATUS + ')=?')
        parameter.append(filter_data.tinjauan)
    if filter_data.q:
        bagian_cari, param_cari = _syarat_cari(filter_data.q)
        syarat.append(bagian_cari)
        parameter.extend(param_cari)
    where = ''.join(' AND ' + s for s in syarat)
    total = kon.execute('SELECT COUNT(*) FROM sesi s WHERE s.siswa_id=?' + where,
                        (siswa_id,) + tuple(parameter)).fetchone()[0]
    halaman = min(filter_data.halaman, max(1, (total + PER_HALAMAN-1)//PER_HALAMAN))
    filter_data = replace(filter_data, halaman=halaman)
    return _muat(kon,siswa_id,where,parameter,PER_HALAMAN,(halaman-1)*PER_HALAMAN), total, filter_data


def _syarat_cari(cari):
    """Cari nomor sesi ("sesi #132"/"132") ATAU potongan slug topik; OR antar-bagian."""
    digit = re.sub(r'\D', '', cari)
    kata = [k for k in re.split(r'[^A-Za-z\-]{1,}', cari) if len(k) >= 3]
    bagian, param = [], []
    if digit:
        bagian.append('CAST(s.id AS TEXT) LIKE ?')
        param.append('%' + digit + '%')
    for k in kata[:4]:
        bagian.append('s.topik LIKE ?')
        param.append('%' + k.lower() + '%')
    if not bagian:
        bagian.append('s.topik LIKE ?')
        param.append('%' + cari.lower() + '%')
    return '(' + ' OR '.join(bagian) + ')', param


def ringkasan_riwayat(kon, siswa_id):
    """Jumlah per status untuk filter riwayat; gagal aman menghasilkan None."""
    try:
        hitung_status = dict(kon.execute(
            'SELECT (' + _STATUS + '), COUNT(*) FROM sesi s '
            'WHERE s.siswa_id=? GROUP BY 1', (siswa_id,),
        ).fetchall())
    except Exception:
        return None
    menunggu = sum(hitung_status.get(k, 0) for k in ('belum_ditinjau', 'dibuka', 'draf', 'ulang'))
    terlama = tinjauan_terlama(kon, siswa_id) if menunggu else []
    return {'hitung_status': hitung_status, 'menunggu': menunggu,
            'terlama_id': terlama[0]['id'] if terlama else None}


def tinjauan_terlama(kon, siswa_id, *, kecuali=None):
    """Beranda: terkirim, bukan dibatalkan/terkonfirmasi, terlama dahulu."""
    where = ' AND s.dibatalkan IS NULL AND s.selesai IS NOT NULL AND NOT COALESCE(' + _AKTIF + ',0)'
    parameter = ()
    if kecuali is not None:
        where += ' AND s.id<>?'
        parameter = (int(kecuali),)
    return _muat(kon, siswa_id, where, parameter, 3, terlama=True)


def tugas_terbaru(kon, siswa_id, sorot=None, kecuali=None):
    """Maksimal tiga tugas sekunder; sesi CTA reducer dikecualikan eksplisit."""
    where = " AND (s.dibatalkan IS NULL AND (s.selesai IS NULL OR NOT COALESCE(" + _AKTIF + ",0)))"
    parameter = ()
    if kecuali is not None:
        where += " AND s.id<>?"
        parameter = (int(kecuali),)
    baris = _muat(kon, siswa_id, where, parameter, 3)
    if sorot and sorot != kecuali and all(r['id'] != sorot for r in baris):
        terpilih = _muat(kon, siswa_id, ' AND s.id=?', (sorot,), 1)
        if terpilih:
            baris = terpilih + baris[:2]
    return baris
