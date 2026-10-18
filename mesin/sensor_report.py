"""Proyeksi agregat sensor: sel kecil ditahan, tanpa drill-down keluarga."""
import sqlite3

import sensor_domain as d
import sensor_store as store


TAHAP = (
    ('disiapkan', 'Latihan disiapkan'),
    ('pekerjaan_disimpan', 'Pekerjaan disimpan'),
    ('dikirim', 'Latihan dikirim'),
    ('tinjauan_disimpan', 'Tinjauan disimpan'),
    ('dikonfirmasi', 'Hasil dikonfirmasi'),
    ('lanjutan_disiapkan', 'Latihan terpandu berikutnya disiapkan'),
    ('lembar_disajikan', 'Lembar cetak disajikan'),
    ('dibatalkan', 'Sesi dibatalkan'),
)


def laporan(path, *, siap, sekarang):
    """Semua query dibatasi consent boot kini, TTL, dan ≥5 keluarga per sel."""
    sehat = store.kesehatan(path, siap=siap, sekarang=sekarang)
    hasil = {'status': sehat['status'], 'tahap': (), 'hasil': None, 'chat': (), 'hambatan': ()}
    if sehat['status'] != 'siap_best_effort':
        return hasil
    try:
        with store.buka(path) as kon:
            basis = (store.BOOT, sekarang, sekarang-d.RETENSI_DETAIL)
            batas = (' FROM sensor_episode e JOIN sensor_peserta p ON p.generasi=e.peserta '
                     "WHERE p.boot=? AND p.berakhir>? AND e.mulai>? AND e.jalur='terpandu' "
                     "AND NOT EXISTS(SELECT 1 FROM sensor_event cetak WHERE cetak.peserta=e.peserta "
                     "AND cetak.token=e.token AND cetak.kode='lembar_disajikan') ")
            keluarga = kon.execute('SELECT COUNT(DISTINCT e.peserta)' + batas, basis).fetchone()[0]
            if keluarga < 5:
                hasil['status'] = 'sampel_kecil'
                return hasil
            # Tidak tampilkan total yang memungkinkan sel tersembunyi dihitung balik.
            tahap=[]
            for kode, label in TAHAP:
                row=kon.execute('SELECT COUNT(*),COUNT(DISTINCT e.peserta)' + batas +
                    'AND EXISTS(SELECT 1 FROM sensor_event v WHERE v.peserta=e.peserta AND v.token=e.token AND v.kode=?)',
                    (*basis,kode)).fetchone()
                tahap.append((label,row[0] if row[1]>=5 else None))
            hasil['tahap']=tuple(tahap)
            outcomes=[]
            for kolom,label in (('benar','Jawaban benar'),('belum_jelas','Dilewati/belum jelas'),
                                ('kode_b','Baca'),('kode_k','Konsep'),('kode_h','Hitung'),
                                ('kode_e','Tulis akhir'),('kode_n','Cara belum terbukti/menebak'),('kode_t','Pengenalan')):
                outcome=kon.execute(
                    'SELECT COUNT(DISTINCT e.peserta),SUM(h.' + kolom + ') '
                    'FROM sensor_hasil h JOIN sensor_episode e ON e.peserta=h.peserta AND e.token=h.token '
                    'JOIN sensor_peserta p ON p.generasi=e.peserta '
                    'WHERE p.boot=? AND p.berakhir>? AND e.mulai>? AND p.hasil=1 AND h.' + kolom + '>0', basis).fetchone()
                outcomes.append((label,outcome[1] if outcome[0]>=5 else None))
            hasil['hasil']=tuple(outcomes)
            chat=[]
            for kategori in sorted(d.KATEGORI_CHAT):
                row=kon.execute(
                    'SELECT COUNT(*),COUNT(DISTINCT c.peserta) FROM sensor_chat c '
                    'JOIN sensor_peserta p ON p.generasi=c.peserta '
                    'WHERE p.boot=? AND p.berakhir>? AND p.chat=1 AND c.jam>? AND c.kategori=?',
                    (store.BOOT,sekarang,(sekarang-d.RETENSI_DETAIL)//3600,kategori)).fetchone()
                chat.append((kategori,row[0] if row[1]>=5 else None))
            hasil['chat']=tuple(chat)
            # Usia ≥48 jam adalah kesempatan observasi, bukan janji SLA/diagnosis.
            sinyal=[]
            for awal, akhir, label in (
                ('disiapkan','dikirim','Latihan berusia ≥48 jam tanpa pengiriman teramati'),
                ('dikirim','dikonfirmasi','Pengiriman ≥48 jam tanpa konfirmasi teramati'),
            ):
                row=kon.execute('SELECT COUNT(*),COUNT(DISTINCT e.peserta)' + batas +
                    "AND NOT EXISTS(SELECT 1 FROM sensor_event b WHERE b.peserta=e.peserta AND b.token=e.token AND b.kode='dibatalkan') "
                    'AND EXISTS(SELECT 1 FROM sensor_event a WHERE a.peserta=e.peserta AND a.token=e.token AND a.kode=? AND a.jam<=?) '
                    'AND NOT EXISTS(SELECT 1 FROM sensor_event z WHERE z.peserta=e.peserta AND z.token=e.token AND z.kode=?)',
                    (*basis,awal,sekarang//3600-49,akhir)).fetchone()
                sinyal.append((label,row[0] if row[1]>=5 else None))
            hasil['hambatan']=tuple(sinyal)
            return hasil
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        return {'status':'tidak_teramati','tahap':(),'hasil':None,'chat':(),'hambatan':()}
