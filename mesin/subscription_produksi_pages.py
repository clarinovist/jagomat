"""Halaman checkout PRODUKSI tanpa JavaScript atau aset pihak ketiga.

Teks mengikuti keputusan 26 Sep 2026: harga total termasuk pajak bila berlaku
(bukan faktur pajak), disclosure Midtrans QRIS + merchant, kegagalan/kedaluwarsa
tidak menahan dana, dan dukungan lewat teks statis tanpa menyimpan kontak.
"""

import html
import json
from datetime import datetime

import design_tokens as T
import subscription as d
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


def nominal(rupiah):
    d.bilangan(rupiah, 1)
    return "Rp" + format(rupiah, ",").replace(",", ".")


def tanggal_wib(detik):
    d.waktu(detik)
    return datetime.fromtimestamp(detik, d.WIB).strftime("%d-%m-%Y %H:%M WIB")


def _catatan(sebab):
    if sebab == "belum_aktif":
        return ('Pembayaran online belum diaktifkan pengelola. Halaman ini hanya '
                'menampilkan status; tidak ada tagihan yang dibuat.')
    if sebab == "eksperimen":
        return 'Pembayaran online sedang ditahan sementara oleh pengelola.'
    return 'Pembayaran online belum tersedia untuk akun ini.'


def bingkai(isi, *, pengguna=None, judul="Langganan", privat=True):
    return _halaman(
        judul,
        '<style>' + GAYA + '</style>'
        '<div class="langganan-panel"><p><a href="/akun">← Akun saya</a></p>'
        '<header><h1 id="judul-langganan">' + html.escape(judul) + '</h1></header>'
        + isi + '</div>',
        ident=(pengguna, "guru") if pengguna else None, stitch=True,
        id_utama="judul-langganan", privat=privat)


def _disclosure(merchant):
    return ('<p class="sub">Pembayaran diproses Midtrans (QRIS) — merchant '
            + html.escape(merchant, quote=True)
            + '. Harga yang tampil adalah total yang dibayarkan dan sudah termasuk '
            'pajak bila berlaku.</p>')


def _bantuan():
    return ('<section class="kartu"><h2>Bantuan</h2>'
            '<p>Butuh bantuan pembayaran? Hubungi pengelola layanan lewat kanal yang '
            'biasa kamu pakai. Aplikasi ini tidak menyimpan email atau nomor telepon. '
            'Rincian data ada di <a href="/kebijakan-privasi">Kebijakan Privasi</a>.</p>'
            '</section>')


def form(aksi, token, label, tambahan=""):
    if type(token) is not str or type(label) is not str:
        raise ValueError("form produksi tidak sah")
    return ('<form method="post" action="' + html.escape(aksi, quote=True) + '">'
            '<input type="hidden" name="token" value="'
            + html.escape(token, quote=True) + '">'
            + tambahan + '<button type="submit">' + html.escape(label) + '</button></form>')


def belum_aktif(pengguna, sebab="belum_aktif"):
    isi = ('<section class="kartu"><h2>Belum aktif</h2>'
           '<p class="peringatan">' + html.escape(_catatan(sebab)) + '</p></section>'
           + _bantuan())
    return bingkai(isi, pengguna=pengguna)


def ringkasan(pengguna, profil, invoice, token, *, merchant, aktif):
    """Profil keluarga + titik mulai; tanpa enrollment pemilik tidak melihat form."""
    kartu = []
    if invoice:
        kartu.append('<section class="kartu"><h2>Tagihan berjalan</h2>'
                     '<p>Lanjutkan tagihan yang sudah dibuat. Muat ulang tidak membuat '
                     'pembayaran kedua.</p><a class="tombol" href="/langganan/'
                     + html.escape(invoice["invoice_id"], quote=True)
                     + '">Buka tagihan</a></section>')
    elif profil and aktif:
        pilihan = ('<fieldset><legend>Profil yang dicakup</legend>'
                   '<p class="sub">Pilih satu sampai tiga profil.</p>' + ''.join(
                       '<label><input type="checkbox" name="profil" value="%d">%s</label>'
                       % (sid, html.escape(nama)) for sid, nama in profil) + '</fieldset>')
        kartu.append('<section class="kartu"><h2>Siapkan tagihan</h2>'
                     '<p>Pilih profil, lalu tinjau nominal sebelum membuat QRIS. '
                     'Nominal dihitung server dari tarif langganan.</p>'
                     + form("/langganan/siapkan", token, "Tinjau tagihan", pilihan)
                     + '</section>')
    elif not profil:
        kartu.append('<section class="kartu"><h2>Belum ada profil</h2>'
                     '<p>Tambahkan profil anak dulu di menu Siswa.</p></section>')
    else:
        kartu.append('<section class="kartu"><h2>Pembayaran belum dibuka</h2>'
                     '<p class="peringatan">' + html.escape(_catatan("belum_aktif"))
                     + '</p></section>')
    if invoice is None and profil and aktif:
        kartu.append(_disclosure(merchant))
    return bingkai(''.join(kartu) + _bantuan(), pengguna=pengguna)


def tagihan(pengguna, inv, *, token, status, merchant, boleh_buat=False, boleh_periksa=False,
            qr_tersedia=False, qr_kedaluwarsa=False, periode=None, diterima=None,
            boleh_ulang=False, kode_belum_ada=False):
    """Halaman tagihan: status, QR (bila pending), form, dan ringkasan pembayaran."""
    jumlah = len(json.loads(inv["profil_json"]))
    isi = ['<section class="kartu"><h2>Tagihan untuk %d profil</h2>' % jumlah,
           '<p class="nominal">' + nominal(inv["rupiah"]) + '</p>',
           '<p>QRIS · IDR · ' + ("Tarif promo" if inv["promo"] else "Tarif lanjutan") + '</p>',
           _disclosure(merchant)]
    if status == "lunas":
        detail = ['<p role="status"><strong>Pembayaran diterima.</strong> '
                  'Akses periode ini sudah aktif.</p>'
                  '<p>Merchant: ' + html.escape(merchant, quote=True) + ' · '
                  'Tanggal: ' + html.escape(tanggal_wib(diterima)) + ' · '
                  'Deskripsi: langganan latihan %d profil · Total: ' % jumlah
                  + nominal(inv["rupiah"]) + '</p>']
        if periode is not None:
            detail.append('<p>Periode aktif sampai ' + html.escape(tanggal_wib(periode)) + '.</p>')
        detail.append('<p class="sub">Ringkasan pembayaran ini bukan faktur pajak.</p>')
        isi.extend(detail)
    elif status == "perlu_diperiksa":
        isi.append('<p role="status">Pembayaran tercatat tetapi perlu diperiksa pengelola. '
                   'Akses tidak bertambah otomatis dari halaman ini; tidak ada dana tambahan '
                   'yang tertahan.</p>')
    else:
        if qr_kedaluwarsa:
            isi.append('<p role="status">Masa berlaku tagihan ini sudah lewat tanpa dana '
                       'tertahan. Jangan membuat atau membayar tagihan kedua; periksa tagihan '
                       'yang sama atau hubungi pengelola.</p>')
        elif status == "pending":
            isi.append('<p role="status">Menunggu pembayaran QRIS. Nominal dan masa berlaku '
                       'tetap; selesaikan sebelum masa berlaku habis.</p>')
        elif status == "belum_terverifikasi" and inv.get("create_dicoba"):
            isi.append('<p role="status">Status belum terverifikasi. Gunakan tagihan '
                       'yang sama; jangan membuat atau membayar tagihan kedua.</p>')
        if qr_tersedia:
            isi.append('<img class="qr" src="/langganan/' + html.escape(inv["invoice_id"], quote=True)
                       + '/qr" width="280" height="280" alt="Kode QRIS untuk tagihan ini">')
        if boleh_ulang and not kode_belum_ada:
            # Provider sudah pernah menerbitkan kode (transaksi pernah ada):
            # jelaskan kode lama mati. Tanpa transaksi (create gagal) → pesan netral.
            isi.append('<p>Kode pembayaran sebelumnya tidak lagi berlaku menurut penyedia '
                       'dan tidak ada dana tertahan. Anda dapat membuat kode baru untuk '
                       'tagihan yang sama — nominal dan cakupan profil tidak berubah.</p>')
        elif boleh_ulang:
            isi.append('<p>Kode pembayaran untuk tagihan ini belum berhasil dibuat oleh '
                       'penyedia dan tidak ada dana tertahan. Tekan tombol untuk membuat '
                       'kode baru — nominal dan cakupan profil tidak berubah.</p>')
        if boleh_ulang:
            isi.append(form("/langganan/" + inv["invoice_id"] + "/ulang", token, "Buat ulang QR"))
        if boleh_buat:
            isi.append('<p>Belum ada QRIS untuk tagihan ini. Tekan tombol untuk membuat '
                       'kode pembayaran; tidak ada dana yang tertahan bila gagal.</p>')
            isi.append(form("/langganan/" + inv["invoice_id"] + "/buat", token, "Buat QRIS"))
        if boleh_periksa:
            isi.append(form("/langganan/" + inv["invoice_id"] + "/periksa", token,
                            "Periksa pembayaran"))
            isi.append('<p class="sub">Periksa memakai order yang sama; tidak membuat '
                       'pembayaran baru.</p>')
    isi.append('</section>')
    return bingkai(''.join(isi) + _bantuan(), pengguna=pengguna)


def galat(pengguna, pesan, *, privat=True):
    return bingkai('<section class="kartu"><p role="alert">' + html.escape(pesan)
                   + '</p></section>', pengguna=pengguna, judul="Langganan", privat=privat)
