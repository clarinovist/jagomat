"""Kartu kesehatan sensor; tanpa angka anak atau keluarga individual."""
import html

STATUS = {
    'nonaktif': ('Koleksi nonaktif', 'Aktivitas tidak teramati, bukan nol penggunaan.'),
    'belum_dipasang': ('Sensor belum dipasang', 'Penyimpanan belum dimigrasikan. Tidak ada koleksi baru.'),
    'tidak_teramati': ('Sensor tidak dapat diperiksa', 'Jangan menarik kesimpulan penggunaan dari data ini.'),
    'terganggu': ('Pencatatan terganggu', 'Ada kegagalan sink pada proses ini. Angka ditahan agar tidak menyesatkan.'),
    'menunggu_izin_ulang': ('Menunggu persetujuan ulang', 'Restart/pemulihan tidak mewarisi izin lama.'),
    'menunggu_peserta': ('Menunggu peserta sukarela', 'Keluarga dapat memilih sensor di Akun. Tidak ada enrollment otomatis.'),
    'siap_best_effort': ('Sensor siap — best-effort', 'Pencatatan tersedia, bukan jaminan tidak ada kejadian yang hilang.'),
    'sampel_kecil': ('Belum cukup keluarga teramati', 'Kurang dari 5 keluarga dengan episode aktif. Rincian ditahan, bukan nol.'),
}


def kesehatan(status):
    judul,isi=STATUS.get(status,STATUS['tidak_teramati'])
    return ('<section class="admin-kartu" aria-labelledby="sensor-judul">'
            '<h2 id="sensor-judul">Sensor perbaikan Jagomat</h2><p><strong>'
            +html.escape(judul)+'</strong></p><p>'+html.escape(isi)+'</p>'
            '<p class="admin-meta">KPI uji coba lama terpisah. Sensor hanya aktivitas baru setelah opt-in, '
            'tanpa backfill. Detail maksimal 30 hari dan consent maksimal 90 hari.</p></section>')
