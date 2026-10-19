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

def dashboard(r):
    """Rincian hanya dari DTO tersupresi; tidak menghitung balik sel kecil."""
    def tabel(rows, unit):
        return ('<div class="admin-tabel-wrap"><table class="admin-tabel sensor-tabel"><thead><tr><th scope="col">Sinyal</th><th scope="col">'
                +html.escape(unit)+'</th></tr></thead><tbody>'+''.join(
                    '<tr><td>'+html.escape(label)+'</td><td>'+(str(n) if n is not None else 'Ditahan (&lt;5 keluarga)')+'</td></tr>'
                    for label,n in rows)+'</tbody></table></div>')
    isi=kesehatan(r['status'])
    if r['tahap']:
        isi+=('<section class="admin-kartu"><h2>Siklus teramati setelah opt-in</h2>'
              '<p>Episode terpandu 30 hari terakhir, tanpa penanda cetak. Satu milestone per sesi; '
              'baris bukan langkah wajib berurutan. Manual/pilot/CLI di luar cakupan funnel ini.</p>'
              +tabel(r['tahap'],'Episode')+'</section>')
    if r['hambatan']:
        isi+=('<section class="admin-kartu"><h2>Petunjuk hambatan, bukan vonis</h2>'
              +tabel(r['hambatan'],'Episode')+
              '<p>Waktu tunggu bukan waktu kerja orang tua. Periksa kejelasan akses dan beban tinjauan; '
              'jangan menyimpulkan anak kesulitan dari ketidakaktifan. Ketiadaan event bisa akibat jeda atau pencatatan terlewat.</p></section>')
    if r['hasil']:
        isi+=('<section class="admin-kartu"><h2>Potret konfirmasi pertama</h2>'
              '<p>Semua episode berizin hasil, termasuk manual. Hitungan butir historis; '
              'bukan nilai aktif, efektivitas intervensi, atau penguasaan. Koreksi berikutnya tidak dihitung ulang.</p>'
              +tabel(r['hasil'],'Butir')+'</section>')
    if r['chat']:
        labels={'penjelasan':'Penjelasan konsep','latihan':'Permintaan latihan','hasil':'Hasil/perkembangan',
                'penggunaan':'Penggunaan aplikasi','belum_diketahui':'Belum diketahui/ambigu'}
        isi+=('<section class="admin-kartu"><h2>Topik bantuan yang teramati</h2>'
              '<p>Pesan baru berizin yang berhasil tersimpan. Aturan kata lokal adalah proksi dan dapat keliru; '
              'bukan kepuasan atau profil anak.</p>'
              +tabel(tuple((labels[k],n) for k,n in r['chat']),'Pesan')+'</section>')
    isi+=('<p class="admin-meta">Tidak ada drill-down keluarga/anak. Setiap sel perlu sedikitnya 5 keluarga berbeda. '
          'Sel ditahan tidak boleh dibaca sebagai nol. Sumber yang dihapus dibersihkan melalui hook dan janitor; '
          'ada jeda rekonsiliasi. Perubahan produk tetap perlu pembanding dan pemeriksaan hasil belajar.</p>')
    return isi
