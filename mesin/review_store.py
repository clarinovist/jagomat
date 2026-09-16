"""Tinjauan lokal guru dan palang provenance sebelum bukti disahkan."""
from __future__ import annotations

import hashlib
import json

from teacher_corrections import cara_dari_form

AWALAN = ('catatan_tinjauan_', 'provenance_', 'jawaban_bantuan_', 'versi_tinjauan_')
PROVENANCE = {'', 'penjelasan_asli', 'koreksi_transkripsi', 'setelah_bantuan'}
PEMAHAMAN = {'', 'bisa_menjelaskan', 'ragu', 'menghafal'}


class TinjauanTidakSah(ValueError):
    """Galat per butir dengan pesan yang bisa dipulihkan tanpa menebak."""
    def __init__(self, sid, pesan):
        super().__init__(pesan)
        self.sid = sid


def muat(kon, sesi_id):
    return {int(b['sesi_soal_id']): dict(b) for b in kon.execute(
        'SELECT t.* FROM tinjauan_guru t JOIN sesi_soal ss ON ss.id=t.sesi_soal_id WHERE ss.sesi_id=?', (sesi_id,))}


def pengiriman(kon, sesi_id):
    if kon.execute('SELECT 1 FROM pengiriman_sesi WHERE sesi_id=?', (sesi_id,)).fetchone():
        from choice_store import validasi_arsip
        validasi_arsip(kon, sesi_id)
    return {int(b['sesi_soal_id']): dict(b) for b in kon.execute(
        'SELECT * FROM pengiriman_butir WHERE sesi_id=?', (sesi_id,))}


def tanda(kon, sid):
    b = kon.execute('SELECT jawaban,cara,restatement,belum_pernah FROM jawaban WHERE sesi_soal_id=?', (sid,)).fetchone()
    d = kon.execute('SELECT benar,kode_final,manual FROM diagnosis WHERE jawaban_id=(SELECT id FROM jawaban WHERE sesi_soal_id=?)', (sid,)).fetchone()
    t = kon.execute('SELECT * FROM tinjauan_guru WHERE sesi_soal_id=?', (sid,)).fetchone()
    return hashlib.sha256(json.dumps([tuple(x) if x else None for x in (b, d, t)], ensure_ascii=False).encode()).hexdigest()


def batalkan_bukti(kon, sesi_id):
    sesi = kon.execute('SELECT siswa_id,putaran_id,dikonfirmasi_guru FROM sesi WHERE id=?', (sesi_id,)).fetchone()
    if sesi is None or not sesi['dikonfirmasi_guru']:
        return
    kh = kon.execute('SELECT id FROM konfirmasi_hasil WHERE sesi_id=? ORDER BY id DESC LIMIT 1', (sesi_id,)).fetchone()
    kon.execute("""INSERT INTO kejadian_belajar(siswa_id,putaran_id,sesi_id,konfirmasi_id,jenis,data)
        VALUES (?,?,?,?,'konfirmasi_dibatalkan','{"alasan":"tinjauan_diubah"}')""",
        (sesi['siswa_id'], sesi['putaran_id'], sesi_id, kh['id']))
    kon.execute('UPDATE sesi SET dikonfirmasi_guru=NULL,fingerprint_konfirmasi=NULL WHERE id=?', (sesi_id,))


def simpan(kon, sesi_id, data, guru='guru'):
    """Validasi semua butir sebelum tulis; data absen tidak berarti dikosongkan."""
    from database import isi_sesi
    from teacher_corrections import pilihan_tersimpan
    butir = {int(b['sesi_soal_id']): b for b in isi_sesi(kon, sesi_id)}
    from choice_store import daftar_pilihan
    for sid, p in daftar_pilihan(kon, sesi_id).items():
        if f'jwb_{sid}' in data:
            nilai = data[f'jwb_{sid}'].strip()
            if nilai and nilai not in {o.nilai for o in p.opsi}:
                raise TinjauanTidakSah(sid, 'Jawaban harus sesuai opsi pada lembar.')
    tinjauan = muat(kon, sesi_id)
    arsip = pengiriman(kon, sesi_id)
    for nama in data:
        if nama.startswith(AWALAN):
            sid = nama.rsplit('_', 1)[-1]
            if not sid.isdigit() or int(sid) not in butir:
                raise ValueError('Referensi tinjauan tidak dikenal.')
    perubahan = []
    for sid, b in butir.items():
        lama = tinjauan.get(sid, {})
        baru = {
            'catatan': data.get(f'catatan_tinjauan_{sid}', lama.get('catatan', '')).strip(),
            'provenance': data.get(f'provenance_{sid}', lama.get('provenance', '')),
            'jawaban_bantuan': data.get(f'jawaban_bantuan_{sid}', lama.get('jawaban_bantuan', '')).strip(),
            'pemahaman': data.get(f'cek_pemahaman_{sid}', lama.get('pemahaman', '')),
            'dilewati': int(f'dilewati_{sid}' in data) if f'jwb_{sid}' in data or f'hadir_dilewati_{sid}' in data else int(bool(lama.get('dilewati', 0)) or f'dilewati_{sid}' in data),
        }
        if baru['provenance'] not in PROVENANCE or baru['pemahaman'] not in PEMAHAMAN:
            raise TinjauanTidakSah(sid, 'Pilihan tinjauan tidak dikenal.')
        if any(len(baru[k]) > 8000 for k in ('catatan', 'jawaban_bantuan')):
            raise TinjauanTidakSah(sid, 'Catatan tinjauan terlalu panjang.')
        if baru['provenance'] in {'koreksi_transkripsi', 'setelah_bantuan'} and not baru['catatan']:
            raise TinjauanTidakSah(sid, 'Catat sumber koreksi atau bantuan yang diberikan.')
        if baru['jawaban_bantuan'] and baru['provenance'] != 'setelah_bantuan':
            raise TinjauanTidakSah(sid, 'Jawaban setelah dibantu harus dicatat sebagai hasil bantuan.')
        jwb = data.get(f'jwb_{sid}', b['jawaban'] or '').strip()
        cara = cara_dari_form(data.get(f'cara_{sid}', b['cara'] or '').strip(), b['cara'] or '')
        awal = arsip.get(sid)
        if awal:
            berubah_jwb = jwb != awal['jawaban'].strip()
            berubah_cara = cara != awal['cara'].strip()
            if berubah_jwb and baru['provenance'] != 'koreksi_transkripsi':
                raise TinjauanTidakSah(sid, 'Jawaban saat dikirim tidak boleh ditimpa hasil bantuan. Catat koreksi transkripsi atau hasil bantuan terpisah.')
            if berubah_cara and baru['provenance'] not in {'penjelasan_asli', 'koreksi_transkripsi'}:
                raise TinjauanTidakSah(sid, 'Jelaskan apakah catatan ini pekerjaan asli atau koreksi transkripsi.')
        beda = any(baru[k] != lama.get(k, 0 if k == 'dilewati' else '') for k in baru)
        beda_jawaban = (jwb != (b['jawaban'] or '') or cara != (b['cara'] or '')
                       or data.get(f'kode_{sid}', pilihan_tersimpan(b)) != pilihan_tersimpan(b)
                       or ((f'belum_{sid}' in data if f'jwb_{sid}' in data else bool(b['belum_pernah']) or f'belum_{sid}' in data) != bool(b['belum_pernah'])))
        versi = data.get(f'versi_tinjauan_{sid}')
        if (versi is not None and versi != tanda(kon, sid) or versi is None and lama) and (beda or beda_jawaban):
            raise TinjauanTidakSah(sid, 'Tinjauan berubah di halaman lain. Muat ulang agar catatan baru tidak tertimpa.')
        if beda:
            perubahan.append((sid, int(lama.get('revisi', 0)) + 1, baru))
    if perubahan:
        batalkan_bukti(kon, sesi_id)
    for sid, revisi, baru in perubahan:
        kon.execute('''INSERT INTO tinjauan_guru
            (sesi_soal_id,revisi,catatan,provenance,jawaban_bantuan,pemahaman,dilewati,guru)
            VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(sesi_soal_id) DO UPDATE SET
            revisi=excluded.revisi,catatan=excluded.catatan,provenance=excluded.provenance,
            jawaban_bantuan=excluded.jawaban_bantuan,pemahaman=excluded.pemahaman,
            dilewati=excluded.dilewati,guru=excluded.guru''',
            (sid, revisi, baru['catatan'], baru['provenance'], baru['jawaban_bantuan'], baru['pemahaman'], baru['dilewati'], guru))
    return len(perubahan)


def validasi_bukti(kon, sesi_id, outcome, dilewati):
    """Palang domain, juga untuk caller konfirmasi langsung tanpa formulir."""
    tinjauan = muat(kon, sesi_id)
    arsip = pengiriman(kon, sesi_id)
    for b in outcome:
        sid = int(b['sesi_soal_id'])
        if sid in dilewati:
            continue
        t = tinjauan.get(sid, {})
        awal = arsip.get(sid)
        if b['kode_final'] == 'T' and not b['manual']:
            raise TinjauanTidakSah(sid, 'Pengalaman anak belum dipastikan guru; tinjau sebelum memilih pengenalan.')
        if t.get('provenance') == 'setelah_bantuan':
            raise TinjauanTidakSah(sid, 'Hasil setelah bantuan bukan bukti jawaban mandiri. Gunakan probe berikutnya.')
        if awal:
            berubah = ((b['jawaban'] or '').strip() != awal['jawaban'].strip())
            if berubah and not (t.get('provenance') == 'koreksi_transkripsi' and t.get('catatan')):
                raise TinjauanTidakSah(sid, 'Perubahan jawaban harus memiliki sumber koreksi transkripsi.')
            cara_berubah = (b['cara'] or '').strip() != awal['cara'].strip()
            if cara_berubah and t.get('provenance') not in {'penjelasan_asli', 'koreksi_transkripsi'}:
                raise TinjauanTidakSah(sid, 'Penjelasan pekerjaan asli harus dicatat sumbernya sebelum disahkan.')
        if b['benar'] and not (b['jawaban'] or '').strip():
            raise TinjauanTidakSah(sid, 'Jawaban kosong tidak dapat disahkan benar tanpa rekaman pekerjaan asli.')
    # Snapshot hanya data lokal; tidak dibawa ke konteks Pendamping.
    return [{k: t[k] for k in ('sesi_soal_id', 'revisi', 'catatan', 'provenance', 'jawaban_bantuan', 'pemahaman', 'dilewati', 'guru')}
            for _, t in sorted(tinjauan.items())]
