"""Rincian bukti per konteks warisan tanpa penyebut kemampuan buatan."""
import html

from learning_cycle import penguasaan_konteks
from question_context import daftar_konteks, label_profil_parameter
from template_labels import nama_tipe_soal
from report_navigation import halaman_daftar, navigasi_halaman, url_laporan

_LABEL = {'terbukti': 'Menunjukkan pemahaman', 'dipelajari': 'Masih dipelajari',
          'perlu_cek': 'Perlu cek kembali', 'belum_dinilai': 'Belum dinilai'}


def render_konteks(bukti, siswa_id, tanggal, *, halaman='1', hari_ini=None):
    """Status selalu dari reducer; filter tampilan bukan daftar target wajib."""
    hasil = penguasaan_konteks(bukti, siswa_id, daftar_konteks(), hari_ini)
    tercatat = tuple(h for h in hasil if h.hasil.status != 'belum_dinilai')
    bagian, nomor, jumlah = halaman_daftar(tercatat, halaman, 12)
    baris = []
    for item in bagian:
        nilai = item.hasil
        kapan = ' · ' + tanggal(nilai.terakhir.isoformat()) if nilai.terakhir else ''
        sumber = ', '.join(f'<a href="/sesi/{sid}">#{sid}</a>' for sid in nilai.sesi_ids)
        baris.append('<li><b>' + html.escape(nama_tipe_soal(item.konteks.template_id)) + '</b>'
                     + '<p>' + _LABEL[nilai.status] + kapan + '</p>'
                     + '<p>' + html.escape(label_profil_parameter(item.konteks.profil_parameter)) + '</p>'
                     + '<details><summary>Rincian bukti dan pengaturan</summary>'
                     + '<p>Kode konfigurasi: ' + html.escape(item.konteks.profil_parameter) + '</p>'
                     + (f'<p>Sumber: {sumber}</p>' if sumber else '') + '</details></li>')
    return (
        '<section class="kartu peta-materi-st" id="bukti-per-konteks">'
        '<h2>Bukti per konteks latihan</h2>'
        '<p>Hasil dibaca per keterampilan dan variasi soal, bukan sebagai kelas atau '
        'jenjang kemampuan anak. Bukti pada satu variasi tidak otomatis berlaku untuk variasi lain.</p>'
        '<p>Rincian ini menampilkan konteks dengan catatan penilaian yang relevan. '
        'Konteks lain belum dinilai, bukan berarti anak tidak mampu. Tidak ada persentase '
        'atau jumlah target wajib dari daftar pola dan variasi.</p>'
        + ('<ul class="peta-target">' + ''.join(baris) + '</ul>' if baris
           else '<p>Belum ada bukti konteks yang dapat dinilai. Latihan manual tetap tersedia; '
           'hasilnya bukan bukti tanpa konfirmasi dan opt-in pemetaan yang sah.</p>')
        + navigasi_halaman(nomor, jumlah,
                           lambda n: url_laporan(siswa_id, 'penguasaan', tampilan='konteks', halaman=n))
        + '</section>'
    )
