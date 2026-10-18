"""Notice satu layar: ringkas, tujuan spesifik, pilihan opsional tetap terlihat."""
import html

import policy_store as store


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
