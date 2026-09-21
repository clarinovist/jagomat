"""Bekukan konteks konfigurasi aktual tanpa menyatakan tingkat kemampuan.

Caller domain telah mengotorisasi resource. Semua penulisan mengikuti transaksi
sesi/konfirmasi milik caller; tidak membaca kelas sekolah atau membuat bukti.
"""
import json

from question_context import konteks_warisan


def _id_konteks(template_id, profil):
    try:
        return konteks_warisan(template_id, profil).id
    except ValueError:
        # Komposisi eksplisit/remedial warisan boleh di luar inventaris. Catat
        # konfigurasi aktual, tetapi jangan menyebutnya tuntutan terkalibrasi.
        return None


def simpan_butir(kon, sesi_id, butir_id, soal):
    """Tandai sesi baru dan simpan konfigurasi tiap butir secara atomik."""
    if kon.execute('SELECT 1 FROM konteks_sesi WHERE sesi_id=?', (sesi_id,)).fetchone() is None:
        kon.execute('INSERT INTO konteks_sesi VALUES (?,1)', (sesi_id,))
    kon.execute('INSERT INTO konteks_butir VALUES (?,?,?,?)',
                (butir_id, soal.template_id, soal.level, _id_konteks(soal.template_id, soal.level)))


def proyeksi(kon, sesi_id, target_per_nomor):
    """Validasi sumber sebelum fingerprint; None khusus sesi historis tanpa marker."""
    marker = kon.execute('SELECT versi FROM konteks_sesi WHERE sesi_id=?', (sesi_id,)).fetchone()
    if marker is None:
        return None
    if marker['versi'] != 1:
        raise ValueError('versi konteks sesi tidak dikenal')
    baris = kon.execute(
        '''SELECT ss.id, ss.nomor, so.template_id, so.level, se.level AS level_sesi,
                  kb.template_id AS pola_sumber, kb.profil_parameter, kb.konteks_id
           FROM sesi_soal ss JOIN sesi se ON se.id=ss.sesi_id
           JOIN soal so ON so.id=ss.soal_id
           LEFT JOIN konteks_butir kb ON kb.sesi_soal_id=ss.id
           WHERE ss.sesi_id=? ORDER BY ss.nomor''', (sesi_id,),
    ).fetchall()
    if not baris or not set(target_per_nomor) <= {b['nomor'] for b in baris}:
        raise ValueError('konteks butir atau target tidak lengkap')
    hasil = []
    for b in baris:
        if (b['pola_sumber'] != b['template_id'] or b['profil_parameter'] != b['level']
                or b['profil_parameter'] != b['level_sesi']
                or b['konteks_id'] != _id_konteks(b['template_id'], b['level'])):
            raise ValueError('konteks butir tidak cocok sumber')
        fokus = target_per_nomor.get(b['nomor'])
        if fokus is not None and (len(fokus) != 3 or fokus[0] != b['template_id']
                                  or fokus[1] not in ('B', 'K', 'H', 'E', 'N', 'T')
                                  or (fokus[2] is not None and type(fokus[2]) is not str)):
            raise ValueError('konteks fokus tidak cocok butir')
        hasil.append({'sesi_soal_id': b['id'], 'nomor': b['nomor'],
                      'template_id': b['template_id'], 'profil_parameter': b['level'],
                      'konteks_id': b['konteks_id'],
                      'target_fokus': None if fokus is None else list(fokus)})
    isi = {'versi': 1, 'butir': hasil}
    event = kon.execute(
        "SELECT data FROM kejadian_belajar WHERE sesi_id=? AND jenis='sesi_dibuat' ORDER BY id DESC LIMIT 1",
        (sesi_id,),
    ).fetchone()
    if event is not None:
        data = json.loads(event['data'] or '{}')
        if isinstance(data, dict) and 'konteks_latihan' in data and data['konteks_latihan'] != isi:
            raise ValueError('konteks fokus berubah dari rencana sumber')
    return isi


def arsipkan(kon, konfirmasi_id, isi):
    """Arsip terikat fingerprint; retry harus identik, bukan menulis ulang."""
    if isi is None:
        return
    serial = json.dumps(isi, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    lama = kon.execute('SELECT snapshot_json FROM konteks_konfirmasi WHERE konfirmasi_id=?',
                       (konfirmasi_id,)).fetchone()
    if lama is not None:
        if lama['snapshot_json'] != serial:
            raise ValueError('arsip konteks konfirmasi tidak cocok')
        return
    kon.execute('INSERT INTO konteks_konfirmasi VALUES (?,?)', (konfirmasi_id, serial))


def validasi_arsip(kon, sesi_id, konfirmasi_id, target_per_nomor):
    """Pembaca tidak menambal metadata hilang atau memakai snapshot versi asing."""
    isi = proyeksi(kon, sesi_id, target_per_nomor)
    lama = kon.execute('SELECT snapshot_json FROM konteks_konfirmasi WHERE konfirmasi_id=?',
                       (konfirmasi_id,)).fetchone()
    if isi is None:
        if lama is not None:
            raise ValueError('arsip konteks tanpa sumber')
        return
    serial = json.dumps(isi, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    if lama is None or lama['snapshot_json'] != serial:
        raise ValueError('arsip konteks konfirmasi tidak cocok')
    outcomes = kon.execute(
        'SELECT sesi_soal_id, nomor, template_id, level_efektif FROM snapshot_outcome '
        'WHERE konfirmasi_id=? ORDER BY nomor', (konfirmasi_id,),
    ).fetchall()
    if len(outcomes) != len(isi['butir']) or any(
        (o['sesi_soal_id'], o['nomor'], o['template_id'], o['level_efektif'])
        != (b['sesi_soal_id'], b['nomor'], b['template_id'], b['profil_parameter'])
        for o, b in zip(outcomes, isi['butir'])
    ):
        raise ValueError('konteks outcome tidak cocok arsip')
