"""Halaman checkout sandbox tanpa JavaScript atau aset pembayaran pihak ketiga."""

import html
import json

from subscription_style import GAYA_LANGGANAN as GAYA
from teacher_pages import _halaman


def bingkai(isi, *, pengguna=None, selesai=False):
    return _halaman("Langganan sandbox", '<style>' + GAYA + '</style>'
        '<div class="langganan-panel"><p><a href="/akun">← Akun saya</a></p>'
        '<header><p>UJI PEMBAYARAN</p><h1 id="judul-langganan">Langganan sandbox</h1></header>'
        '<p class="peringatan"><strong>Simulasi, bukan tagihan sungguhan.</strong> '
        + ('Simulasi telah selesai tanpa perpindahan uang nyata. ' if selesai else
           'QR yang nanti dibuat hanya boleh diproses melalui simulator resmi Midtrans, bukan aplikasi bank atau e-wallet. ')
        + 'Akses belajar dan saldo nyata tidak berubah.</p>' + isi + '</div>',
        ident=(pengguna, "guru") if pengguna else None, stitch=True,
        id_utama="judul-langganan", privat=True)


def form(aksi, token, label, tambahan=""):
    return ('<form method="post" action="' + html.escape(aksi, quote=True) + '">'
            '<input type="hidden" name="token" value="' + html.escape(token, quote=True) + '">'
            + tambahan + '<button type="submit">' + html.escape(label) + '</button></form>')


def isi_ringkasan(profil, invoice, token):
    """Fragmen kartu ringkasan tanpa bingkai halaman (untuk embed /akun)."""
    if invoice:
        isi = ('<section class="kartu"><h2>Tagihan simulasi</h2><p>Lanjutkan tagihan yang sudah dibuat. '
               'Muat ulang tidak membuat pembayaran kedua.</p><a class="tombol" href="/langganan/'
               + invoice["invoice_id"] + '">Buka tagihan</a></section>')
    elif profil:
        pilihan = '<fieldset><legend>Profil yang dicakup simulasi</legend><p class="sub">Pilih satu sampai tiga profil.</p>' + ''.join(
            '<label><input type="checkbox" name="profil" value="%d">%s</label>' % (sid, html.escape(nama))
            for sid, nama in profil) + '</fieldset>'
        isi = ('<section class="kartu"><h2>Siapkan tagihan</h2><p>Pilih profil, lalu tinjau nominal '
               'sebelum membuat QR. Nominal dihitung server dari tarif langganan; pajak dan total '
               'checkout komersial belum ditetapkan.</p>'
               + form('/langganan/siapkan', token, 'Tinjau tagihan simulasi', pilihan) + '</section>')
    else:
        isi = '<section class="kartu"><h2>Belum ada profil</h2><p>Siapkan profil sintetis di preview sebelum menguji pembayaran.</p></section>'
    return isi


def ringkasan(pengguna, profil, invoice, token):
    return bingkai(isi_ringkasan(profil, invoice, token), pengguna=pengguna)


def tagihan(pengguna, inv, *, token, status, boleh_buat=False, qr_url=""):
    jumlah = len(json.loads(inv['profil_json']))
    nominal = 'Rp' + format(inv['rupiah'], ',').replace(',', '.')
    isi = ('<section class="kartu"><h2>Tagihan simulasi untuk %d profil</h2>' % jumlah
           + '<p class="nominal">' + nominal + '</p><p>QRIS · IDR · '
           + ('Tarif promo' if inv['promo'] else 'Tarif lanjutan') + '</p>')
    if status == 'perlu_diperiksa':
        isi += '<p role="status">Pembayaran tercatat tetapi perlu diperiksa. Hak akses simulasi tidak otomatis bertambah.</p>'
    elif status == 'settlement_terdeteksi':
        isi += '<p role="status">Pembayaran terdeteksi. Tekan tombol di bawah untuk mencatat hasil terverifikasi pada ledger sintetis.</p>'
        isi += form('/langganan/' + inv['invoice_id'] + '/periksa', token, 'Catat pembayaran terverifikasi')
    elif status == 'lunas':
        isi += '<p role="status"><strong>LUNAS · SANDBOX.</strong> Status telah diverifikasi ke Midtrans dan dicatat sebagai transaksi simulasi.</p>'
    elif boleh_buat:
        isi += '<p>Nominal simulasi ini tetap. Tombol berikut hanya membuat QR sandbox, bukan memotong saldo.</p>'
        isi += form('/langganan/' + inv['invoice_id'] + '/buat', token, 'Buat QR sandbox')
    else:
        isi += ('<p role="status">Menunggu pembayaran melalui simulator.</p>' if status == 'pending' else
                '<p role="status">Status belum terverifikasi. Periksa lagi tagihan yang sama; jangan membuat atau membayar tagihan kedua.</p>')
        if qr_url:
            isi += '<img class="qr" src="/langganan/' + inv['invoice_id'] + '/qr" width="280" height="280" alt="QR khusus simulasi Midtrans, bukan untuk pembayaran nyata">'
            isi += ('<label for="url-qr">Alamat gambar untuk simulator resmi</label>'
                    '<input id="url-qr" type="url" readonly value="' + html.escape(qr_url, quote=True) + '">'
                    '<p><a href="https://simulator.sandbox.midtrans.com/v2/qris/index">Buka simulator resmi Midtrans</a>, lalu salin alamat di atas. Referensi ini hanya berisi transaksi sandbox, tanpa key atau kontak.</p>')
        isi += form('/langganan/' + inv['invoice_id'] + '/periksa', token, 'Periksa pembayaran')
    if status != 'lunas':
        isi += '<p class="sub">Pajak dan total komersial belum final. Halaman ini tidak mengubah akses belajar.</p>'
    isi += '</section>'
    return bingkai(isi, pengguna=pengguna, selesai=status == 'lunas')
