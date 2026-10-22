"""Notice satu layar: ringkas, tujuan spesifik, pilihan opsional tetap terlihat."""
import html
from datetime import datetime, timedelta, timezone

import policy_store as store
from format_tanggal import waktu_wib

_WIB = timezone(timedelta(hours=7))
_OPSI = (
    ('alur', 'Aktivitas penggunaan aplikasi',
     'Alur layar: persiapan, penyimpanan pekerjaan, pengiriman, tinjauan, konfirmasi, pembatalan, dan kelanjutan latihan.'),
    ('hasil', 'Ringkasan hasil belajar',
     'Tidak menyalin jawaban mentah; bukan penilaian penguasaan terkini.'),
    ('chat', 'Kategori topik percakapan',
     'Isi pesan tidak disalin; kategori otomatis berbasis kata dapat keliru.'),
)


def bidang(*, revisi=0, operasi='', pilihan=(False,False,False)):
    checks=[]
    for nama,label,checked in (
        ('alur','Aktivitas alur untuk menemukan hambatan aplikasi',pilihan[0]),
        ('hasil','Ringkasan jawaban, hasil dan pola kesalahan untuk evaluasi produk',pilihan[1]),
        ('chat','Kategori topik pesan Pendamping untuk memperbaiki bantuan',pilihan[2]),
    ):
        checks.append('<label class="koreksi-centang-st"><input type="checkbox" name="policy_'+nama+'" value="1"'+(' checked' if checked else '')+'><span>'+label+'</span></label>')
    return ('<section class="policy-notice" aria-labelledby="judul-policy"><h2 id="judul-policy">Kesepakatan penggunaan Jagomat</h2>'
            '<p><b>Layanan inti:</b> aktivitas, jawaban dan hasil digunakan untuk menyediakan latihan, riwayat, '
            'serta rekomendasi berbasis bukti. Orang tua/wali bertanggung jawab memberi izin penggunaan data anak.</p>'
            '<p><b>Perbaikan Jagomat — opsional:</b> kami dapat menganalisis alur, ringkasan hasil, dan kategori '
            'pesan baru di server Jagomat. Tidak menyalin teks mentah atau mengirim data ke AI untuk analitik; '
            'bukan untuk iklan atau pelatihan model pihak ketiga. Detail maksimal 30 hari, izin sensor maksimal '
            '90 hari. Tidak memproses histori sebelum izin. Izin tidak hilang saat restart biasa.</p>'
            '<p>Dengan menekan tombol persetujuan, saya menyatakan sebagai orang tua/wali atau pendidik yang '
            'memiliki izin wali, menerima <a href="/syarat-penggunaan" target="_blank" rel="noopener">Syarat Penggunaan</a> '
            'dan memahami <a href="/kebijakan-privasi" target="_blank" rel="noopener">Kebijakan Privasi</a>. '
            '<b>Setuju &amp; aktifkan semua</b> juga menyetujui ketiga penggunaan opsional di atas.</p>'
            '<button type="submit" disabled hidden aria-hidden="true"></button>'
            '<input type="hidden" name="policy_versi" value="'+store.VERSI+'">'
            '<input type="hidden" name="policy_epoch" value="'+store.EPOCH+'">'
            '<input type="hidden" name="policy_revisi" value="'+str(revisi)+'">'
            '<input type="hidden" name="policy_operasi" value="'+html.escape(operasi,quote=True)+'">'
            '<details><summary>Atur pilihan penggunaan tambahan</summary><p>Menolak tidak mengurangi fitur belajar inti. '
            'Hasil/chat memerlukan pencatatan alur. Pilihan dapat diubah kapan saja di Akun.</p>'
            +''.join(checks)+'<button type="submit" name="policy_aksi" value="pilihan">Setuju dengan pilihan ini</button></details>'
            '<button class="masuk-tombol-st" type="submit" name="policy_aksi" value="semua">Setuju &amp; aktifkan semua</button>'
            '<p class="daftar-petunjuk-st">Izin penyedia AI pada fitur Pendamping tetap terpisah. Tidak ada hak penggunaan data tanpa batas.</p></section>')


def halaman(*, token, operasi, revisi, lanjut='/guru', pilihan=(False,False,False), galat=''):
    from landing import _halaman_publik_stitch,_topbar_publik_st
    pesan='<p role="alert">'+html.escape(galat)+'</p>' if galat else ''
    isi=('<main class="daftar-editorial-st">'+_topbar_publik_st()+'<div class="publik-bungkus-st">'
         '<section class="publik-kartu-st lebar"><h1>Satu persetujuan, lalu lanjut belajar</h1>'
         '<p>Tinjau kesepakatan dan pilihan data sekali di awal. Tidak perlu mengaktifkan sensor satu per satu di Akun.</p>'
         +pesan+'<form method="post" action="/persetujuan">'
         '<input type="hidden" name="token" value="'+html.escape(token,quote=True)+'">'
         '<input type="hidden" name="lanjut" value="'+html.escape(lanjut,quote=True)+'">'
         +bidang(revisi=revisi,operasi=operasi,pilihan=pilihan)+'</form>'
         '<form method="post" action="/keluar"><button type="submit">Keluar tanpa menyetujui</button></form></section></div></main>')
    return _halaman_publik_stitch('Persetujuan — Jagomat',isi)


def _status_tinjau(pilihan, dibuat, berakhir, aktif):
    if not pilihan[0]:
        judul = 'Penggunaan tambahan tidak diizinkan'
    elif not aktif or berakhir is None:
        judul = 'Penggunaan tambahan tidak aktif'
    else:
        judul = 'Penggunaan tambahan sedang aktif'
    rinci = []
    if dibuat:
        rinci.append('Disetujui ' + waktu_wib(datetime.fromtimestamp(dibuat, _WIB)))
    if pilihan[0] and aktif and berakhir is not None:
        rinci.append('berlaku sampai ' + waktu_wib(datetime.fromtimestamp(berakhir, _WIB)))
    elif pilihan[0]:
        rinci.append('izin kedaluwarsa atau pencatatan sedang tidak tersedia')
    return judul, ' · '.join(rinci)


def halaman_tinjau(*, pengguna, token, operasi, revisi, pilihan, dibuat, berakhir, aktif,
                   token_cabut, lanjut='/guru', galat=''):
    """Mode tinjau untuk akun dengan persetujuan berlaku; POST sama dengan gate.

    Teks persetujuan hukum tetap ada di mode gate (`bidang`); di sini hanya paragraf
    kesepakatan yang sama dan pilihan opsional. Gate dan /daftar tidak berubah.
    """
    from teacher_pages import _halaman
    judul, rinci = _status_tinjau(pilihan, dibuat, berakhir, aktif)
    opsi = ''.join(
        '<div class="akun-opsi-st"><input type="checkbox" id="policy-' + nama + '" name="policy_' + nama
        + '" value="1"' + (' checked' if pilihan[i] else '') + '><label for="policy-' + nama + '">'
        '<span class="akun-opsi-judul-st">' + label + '</span><span class="akun-opsi-isi-st">' + isi + '</span></label></div>'
        for i, (nama, label, isi) in enumerate(_OPSI)
    )
    pesan = '<p class="akun-catatan-st" role="alert">' + html.escape(galat) + '</p>' if galat else ''
    isi = (
        '<div class="jejak"><a href="/akun?section=akun">← Kembali ke Akun</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">AKUN KELUARGA · PERSETUJUAN DATA</p>'
        '<h1 id="judul-persetujuan">Pilihan data Anda</h1>'
        '<p class="sub">Ubah kapan saja. Fitur belajar inti tetap berjalan apa pun pilihan Anda.</p></header>'
        + pesan +
        '<section class="kartu-st akun-status-data-st" aria-labelledby="judul-status-data">'
        '<h2 id="judul-status-data">' + judul + '</h2>'
        + ('<p class="sub">' + html.escape(rinci) + '</p>' if rinci else '') + '</section>'
        '<form method="post" action="/persetujuan">'
        '<input type="hidden" name="token" value="' + html.escape(token, quote=True) + '">'
        '<input type="hidden" name="lanjut" value="' + html.escape(lanjut, quote=True) + '">'
        '<input type="hidden" name="policy_versi" value="' + store.VERSI + '">'
        '<input type="hidden" name="policy_epoch" value="' + store.EPOCH + '">'
        '<input type="hidden" name="policy_revisi" value="' + str(revisi) + '">'
        '<input type="hidden" name="policy_operasi" value="' + html.escape(operasi, quote=True) + '">'
        '<section class="kartu-st"><h2>Penggunaan tambahan (opsional)</h2>'
        '<p class="sub">Membantu memperbaiki Jagomat. Tidak menyalin teks mentah, tidak dikirim ke AI untuk analitik, '
        'bukan untuk iklan atau pelatihan model pihak ketiga.</p>' + opsi +
        '<p class="sub">Hasil dan chat memerlukan pencatatan alur. Menyimpan pilihan baru menghapus detail pengamatan lama '
        'dan memulai pengamatan baru.</p>'
        '<div class="akun-aksi-baris-st"><button type="submit" class="tombol-utama-akun" name="policy_aksi" value="pilihan">Simpan pilihan</button>'
        '<a class="akun-tautan-st" href="/akun?section=akun">Batal</a></div></section></form>'
        '<details class="kartu-st"><summary>Detail kesepakatan penggunaan Jagomat</summary>'
        '<p class="sub"><b>Layanan inti:</b> aktivitas, jawaban dan hasil digunakan untuk menyediakan latihan, riwayat, '
        'serta rekomendasi berbasis bukti. Orang tua/wali bertanggung jawab memberi izin penggunaan data anak.</p>'
        '<p class="sub"><b>Perbaikan Jagomat — opsional:</b> kami dapat menganalisis alur, ringkasan hasil, dan kategori '
        'pesan baru di server Jagomat. Tidak menyalin teks mentah atau mengirim data ke AI untuk analitik; '
        'bukan untuk iklan atau pelatihan model pihak ketiga. Detail maksimal 30 hari, izin sensor maksimal '
        '90 hari. Tidak memproses histori sebelum izin. Izin tidak hilang saat restart biasa.</p>'
        '<p class="sub">Berlaku <a href="/syarat-penggunaan" target="_blank" rel="noopener">Syarat Penggunaan</a> '
        'dan <a href="/kebijakan-privasi" target="_blank" rel="noopener">Kebijakan Privasi</a>. '
        'Izin penyedia AI pada fitur Pendamping tetap terpisah dan dikelola di '
        '<a href="/pendamping/kelola">Data Pendamping</a>. Tidak ada hak penggunaan data tanpa batas.</p></details>'
        '<section class="kartu-st akun-bahaya-kartu-st" aria-labelledby="judul-cabut-semua"><h2 id="judul-cabut-semua">Cabut semua izin</h2>'
        '<p class="sub">Menghapus data analitik tambahan. Data belajar dan percakapan asli tetap ada.</p>'
        '<form method="post" action="/analitik/sensor-cabut">'
        '<input type="hidden" name="token" value="' + html.escape(token_cabut, quote=True) + '">'
        '<label class="akun-label-persetujuan"><input type="checkbox" name="konfirmasi" value="1" required>'
        '<span>Saya ingin mencabut izin dan menghapus data analitik tambahan. Data belajar dan percakapan asli tetap ada.</span></label>'
        '<button type="submit" class="tombol-bahaya-akun">Cabut izin dan hapus data tambahan</button></form></section>'
    )
    return _halaman('Persetujuan data', isi, ident=(pengguna, 'guru'), stitch=True,
                    kelas_bungkus='pendamping-editorial-st akun-editorial-st', id_utama='judul-persetujuan',
                    privat=True)
