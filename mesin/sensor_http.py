"""Adapter sensor first-party: otorisasi sumber, consent, lalu turunan minimal."""
import html
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import admin_store
import auth
import database
import sensor_domain as d
import sensor_store as store

SIAP = os.environ.get('SENSOR_KOLEKSI_SIAP', '0') == '1'
_WIB = timezone(timedelta(hours=7))
_GALAT = (OSError, ValueError, RuntimeError, LookupError, sqlite3.Error)


def _waktu_sumber(teks):
    return int(datetime.fromisoformat(teks).replace(tzinfo=_WIB).timestamp())


def izin_akun(akun_id, *, sekarang=None):
    import policy_store
    if not SIAP or not policy_store.epoch_sah():
        return None
    kini = int(time.time()) if sekarang is None else sekarang
    try:
        akun = next((a for a in auth.muat_akun() if a.get('id_akun') == akun_id), None)
        if not akun or akun.get('peran', 'guru') != 'guru' or akun.get('dinonaktifkan'):
            return None
        return store.izin(admin_store.BAWAAN, akun_id, sekarang=kini)
    except _GALAT:
        store.gangguan()
        return None


def sesi(sesi_id, kode, *, pengguna=None, peran=None, konfirmasi_id=None):
    """Caller telah memverifikasi akses; adapter memeriksa pemilik dan state committed."""
    if not SIAP or peran == 'admin':
        return
    try:
        kini = int(time.time())
        # SQLite lokal memerlukan handle rw untuk lock rollback-journal ketika
        # request berikutnya mulai menulis; query_only tetap melarang SQL write.
        # mode=rw tidak membuat berkas baru. Tidak memakai immutable/WAL snapshot.
        kon = sqlite3.connect(Path(database.BAWAAN).resolve().as_uri() + '?mode=rw', uri=True, timeout=.05)
        kon.row_factory = sqlite3.Row
        try:
            kon.execute('PRAGMA query_only=ON')
            kon.execute('BEGIN')
            row = kon.execute('SELECT s.dibuat,s.selesai,s.dikonfirmasi_guru,s.fingerprint_konfirmasi,s.dibatalkan,s.tujuan,w.pemilik FROM sesi s JOIN siswa w ON w.id=s.siswa_id WHERE s.id=?', (sesi_id,)).fetchone()
            if row is None or (peran == 'guru' and pengguna != row['pemilik']):
                return
            akun = auth.cari_akun(row['pemilik'])
            if not akun:
                return
            izin = izin_akun(akun['id_akun'], sekarang=kini)
            if izin is None or _waktu_sumber(row['dibuat']) <= izin.mulai:
                return
            if kode == 'dikirim' and not row['selesai']:
                return
            if kode == 'lanjutan_disiapkan' and not row['dikonfirmasi_guru']:
                return
            if kode == 'dikonfirmasi':
                first = kon.execute('SELECT id FROM konfirmasi_hasil WHERE sesi_id=? ORDER BY nomor_urut LIMIT 1', (sesi_id,)).fetchone()
                if first is None or first['id'] != konfirmasi_id:
                    return
            if kode == 'dibatalkan' and not row['dibatalkan']:
                return
            # Selesaikan snapshot read sebelum menunggu sink agar pengecekan sumber
            # di bawah lock consent melihat penghapusan terbaru.
            kon.rollback()
            def sumber_ada():
                return kon.execute('SELECT 1 FROM sesi WHERE id=?', (sesi_id,)).fetchone() is not None
            def hasil_pertama():
                outcomes = kon.execute('SELECT benar,kode_final,dilewati FROM snapshot_outcome WHERE konfirmasi_id=?', (konfirmasi_id,)).fetchall()
                return d.ringkas_hasil(outcomes)
            store.catat_sesi(admin_store.BAWAAN, izin, sesi_id, kode=kode,
                            dibuat=_waktu_sumber(row['dibuat']),
                            jalur='manual' if row['tujuan'] == 'bebas' else 'terpandu',
                            sekarang=kini, hasil=hasil_pertama if kode == 'dikonfirmasi' else None,
                            validasi_sumber=sumber_ada)
        finally:
            kon.close()
    except _GALAT:
        store.gangguan()


def chat_selesai(izin, request_id, teks, *, dibuat, sumber_valid=None):
    """Dipanggil hanya untuk commit pesan baru; tidak untuk replay/provider gagal."""
    if not SIAP or izin is None or not izin.chat:
        return
    try:
        kini = int(time.time())
        # Periksa ulang sebelum isi diproses; transaksi sink memeriksa lagi.
        if izin_akun(izin.akun_id, sekarang=kini) != izin:
            return
        store.catat_chat(admin_store.BAWAAN, izin, request_id, dibuat=dibuat,
                         sekarang=kini, kategori=lambda: d.kategori_chat(teks),
                         validasi_sumber=sumber_valid)
    except _GALAT:
        store.gangguan()


def hapus_sesi(sesi_id, pemilik):
    """Purge sumber tidak bergantung sakelar koleksi atau consent aktif."""
    try:
        akun = auth.cari_akun(pemilik)
        if akun is None:
            return
        import sensor_schema
        with admin_store.buka_baca() as kon:
            if not sensor_schema.validasi(kon):
                return
        store.hapus_sumber_sesi(admin_store.BAWAAN, akun['id_akun'], sesi_id)
    except _GALAT:
        store.gangguan()


def form_akun(penangan):
    import policy_http
    import policy_store
    if policy_http.tersedia():
        p=penangan._principal()
        row=policy_store.baca(admin_store.BAWAAN,p.id_akun)
        izin = izin_akun(p.id_akun)
        status = '<p>Belum ada persetujuan yang berlaku. Penggunaan tambahan tidak aktif.</p>'
        if row is not None:
            pilihan = ''.join(
                '<li>' + label + ': ' + ('diizinkan' if row[kunci] else 'tidak diizinkan') + '</li>'
                for kunci, label in (('alur', 'Aktivitas penggunaan aplikasi'),
                                     ('hasil', 'Ringkasan hasil belajar'),
                                     ('chat', 'Kategori topik percakapan'))
            )
            status = '<p><b>Pilihan tersimpan:</b></p><ul>' + pilihan + '</ul>'
            if row['dibuat']:
                tanggal = datetime.fromtimestamp(row['dibuat'], _WIB).strftime('%d-%m-%Y %H:%M WIB')
                status += '<p>Tanggal persetujuan terakhir: ' + tanggal + '.</p>'
            if not policy_store.berlaku(row):
                status += '<p>Persetujuan perlu ditinjau ulang. Penggunaan tambahan tidak aktif.</p>'
            elif not row['alur']:
                status += '<p><b>Penggunaan tambahan tidak diizinkan.</b></p>'
            elif izin is None:
                status += '<p><b>Penggunaan tambahan tidak aktif.</b> Izin kedaluwarsa atau pencatatan sedang tidak tersedia.</p>'
            else:
                tanggal = datetime.fromtimestamp(izin.berakhir, _WIB).strftime('%d-%m-%Y %H:%M WIB')
                status += '<p><b>Penggunaan tambahan aktif</b> sampai ' + tanggal + '.</p>'
        import product_analytics_http as lama
        cabut_token=lama._token(p,penangan._ambil_token(),'sensor-cabut')
        return ('<section class="kartu-st akun-pilihan-data" id="sensor"><h2>Kesepakatan dan pilihan data</h2>'+status+
                '<p class="sub">Data tambahan membantu memperbaiki Jagomat: aktivitas penggunaan, ringkasan hasil, '
                'dan kategori topik percakapan. Tidak menyalin jawaban atau isi pesan mentah ke analitik.</p>'
                '<p><a href="/persetujuan">Tinjau atau ubah persetujuan</a></p>'
                '<p class="sub">Menolak penggunaan tambahan tidak mengurangi fitur belajar inti.</p>'
                '<form method="post" action="/analitik/sensor-cabut" data-konfirmasi="Cabut izin penggunaan tambahan dan hapus data analitik tambahan? Data belajar dan percakapan asli tetap ada.">'
                '<input type="hidden" name="token" value="'+html.escape(cabut_token)+'">'
                '<label class="akun-label-persetujuan"><input type="checkbox" name="konfirmasi" value="1" required>'
                '<span>Saya ingin mencabut izin dan menghapus data analitik tambahan. Data belajar dan percakapan asli tetap ada.</span></label>'
                '<button type="submit" class="tombol-bahaya-akun">Cabut izin dan hapus data tambahan</button></form></section>')
    import product_analytics_http as lama
    p = lama._principal(penangan)
    try:
        with store.buka(admin_store.BAWAAN) as kon:
            row = kon.execute('SELECT boot,berakhir,hasil,chat FROM sensor_peserta WHERE akun_id=?', (p.id_akun,)).fetchone()
    except _GALAT:
        return '<section class="kartu-st"><h2>Pilihan data tambahan</h2><p>Belum tersedia. Tidak ada pengumpulan baru.</p></section>'
    status = 'Belum memberikan izin.' if row is None else (
        'Persetujuan perlu diperbarui setelah restart atau kedaluwarsa.'
        if row['boot'] != store.BOOT or row['berakhir'] <= int(time.time()) else 'Persetujuan tercatat.')
    isi = '<section class="kartu-st akun-pilihan-data" id="sensor"><h2>Data untuk perbaikan Jagomat — opsional</h2><p>' + status + '</p>'
    if row is not None:
        isi += '<p>Pilihan tersimpan: alur; hasil belajar ' + ('diizinkan' if row['hasil'] else 'tidak diizinkan') + '; kategori chat ' + ('diizinkan' if row['chat'] else 'tidak diizinkan') + '.</p>'
    isi += ('<p>Untuk keluarga lama maupun baru. Penolakan tidak mengurangi fitur belajar. '
            'Hanya aktivitas setelah persetujuan baru yang dianalisis di server Jagomat; '
            'tidak dikirim ke penyedia AI untuk analitik. ID sumber dipseudonimkan, bukan anonim. '
            'Detail maksimal 30 hari, persetujuan maksimal 90 hari; restart memerlukan izin ulang. '
            'Dashboard hanya merinci kelompok sedikitnya 5 keluarga. Cadangan mengikuti retensi operasi dan tidak mengaktifkan izin saat dipulihkan.</p>')
    if SIAP:
        token = lama._token(p, penangan._ambil_token(), 'sensor-setuju')
        isi += ('<form method="post" action="/analitik/sensor-setuju"><input type="hidden" name="token" value="' + html.escape(token) + '">'
                '<label><input type="checkbox" name="alur" value="1" required> Saya menyetujui sensor alur: persiapan, penyimpanan pekerjaan, pengiriman, tinjauan, konfirmasi, pembatalan, dan kelanjutan latihan.</label>'
                '<label><input type="checkbox" name="hasil" value="1"> Saya juga mengizinkan ringkasan dari jawaban/nilai dan pola kesalahan pada konfirmasi pertama. Tidak menyalin jawaban mentah; bukan penilaian penguasaan terkini.</label>'
                '<label><input type="checkbox" name="chat" value="1"> Saya juga mengizinkan kategori topik dari pesan Pendamping baru yang berhasil tersimpan. Isi pesan tidak disalin; kategori otomatis berbasis kata dapat keliru.</label>'
                '<p>Menyimpan pilihan baru menghapus seluruh detail sensor lama dan memulai pengamatan baru. Izin ini terpisah dari izin provider Pendamping dan KPI uji coba.</p>'
                '<button type="submit">Simpan persetujuan sensor</button></form>')
    else:
        isi += '<p>Koleksi nonaktif — tidak teramati, bukan nol penggunaan.</p>'
    if row is not None:
        token = lama._token(p, penangan._ambil_token(), 'sensor-cabut')
        isi += ('<form method="post" action="/analitik/sensor-cabut" data-konfirmasi="Cabut izin dan hapus data analitik tambahan? Data belajar dan percakapan asli tetap ada."><input type="hidden" name="token" value="' + html.escape(token) + '">'
                '<label class="akun-label-persetujuan"><input type="checkbox" name="konfirmasi" value="1" required><span>Cabut izin dan hapus data analitik tambahan saya. Data belajar dan percakapan asli tetap ada.</span></label>'
                '<button type="submit" class="tombol-bahaya-akun">Cabut izin dan hapus data tambahan</button></form>')
    return isi + '</section>'


def tangani_post(penangan, jalur):
    if jalur not in ('/analitik/sensor-setuju', '/analitik/sensor-cabut'):
        return False
    import product_analytics_http as lama
    import admin_security
    from support_pages import halaman_pesan
    try:
        p = lama._principal(penangan)
        data = admin_security.baca_form(penangan, maksimum_field=5)
        aksi = jalur.rsplit('/', 1)[-1]
        lama._cek(p, penangan._ambil_token(), aksi, data.pop('token', ''))
        if aksi == 'sensor-cabut':
            if data != {'konfirmasi': '1'}:
                raise ValueError('konfirmasi sensor tidak sah')
            store.cabut(admin_store.BAWAAN, auth.BERKAS_SANDI, p)
        else:
            raise ValueError('gunakan kesepakatan berversi')
        penangan.send_response(303)
        penangan.send_header('Location', '/akun?section=akun#sensor')
        penangan.send_header('Content-Length', '0')
        penangan.end_headers()
    except LookupError:
        penangan._kirim_privat(halaman_pesan('Tidak ada', '<h1>Halaman tidak ada</h1>'), 404)
    except PermissionError:
        penangan._kirim_privat(halaman_pesan('Form tidak sah', '<h1>Form tidak sah</h1>'), 403)
    except _GALAT:
        penangan._kirim_privat(halaman_pesan('Belum tersimpan', '<h1>Persetujuan belum tersimpan</h1><p>Coba kembali dari halaman Akun.</p>'), 400)
    return True
