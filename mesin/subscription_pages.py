"""Halaman checkout sandbox tanpa JavaScript atau aset pembayaran pihak ketiga."""

import html
import json

import design_tokens as T
from teacher_pages import _halaman

GAYA = f"""
.langganan-panel {{max-width:{T.LEBAR_KONTEN};margin:0 auto}}
.langganan-panel .kartu {{padding:{T.SP_5};margin:{T.SP_4} 0;background:{T.LATAR_KARTU};border:1px solid {T.BORDER_HALUS};border-radius:{T.RADIUS_KARTU_BESAR}}}
.langganan-panel .peringatan {{padding:{T.SP_4};border-left:4px solid {T.AKSEN_MURID_AMBER};background:{T.LATAR_CATATAN};color:{T.TEKS_UTAMA}}}
.langganan-panel label {{display:flex;gap:.75rem;align-items:center;min-height:{T.TARGET_SENTUH}}}
.langganan-panel input[type=checkbox] {{width:1.25rem;height:1.25rem;flex-shrink:0}}
.langganan-panel button,.langganan-panel .tombol {{min-height:{T.TARGET_SENTUH};display:inline-flex;align-items:center;justify-content:center;padding:{T.SP_3} {T.SP_4};border-radius:{T.RADIUS_KECIL}}}
.langganan-panel .qr {{display:block;width:280px;max-width:100%;height:auto;margin:{T.SP_4} auto}}
.langganan-panel .nominal {{font-size:2rem;font-weight:800;color:{T.TEKS_JUDUL}}}
.langganan-panel fieldset {{border:0;padding:0;margin:1rem 0}}
.langganan-panel :focus-visible {{outline:3px solid {T.TEKS_JUDUL};outline-offset:3px}}
.langganan-panel p,.langganan-panel a {{overflow-wrap:anywhere}}
@media(max-width:480px) {{.langganan-panel .kartu {{padding:1rem}} .langganan-panel button {{width:100%}}}}
"""


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


def ringkasan(pengguna, profil, invoice, token):
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
    return bingkai(isi, pengguna=pengguna)


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
