"""Kendali lokal Pendamping; tidak bergantung provider/entitlement atau membuka transkrip."""
import html
import re
import sqlite3
import time
import urllib.parse
from contextlib import closing

import assistant_schema
import design_tokens as T
import assistant_store
import assistant_view
from assistant_http_common import (
    GalatForm, _baca_form, _batasi_laju, _kirim_privat, _principal,
    _redirect, _tidak_ada, _tolak_login,
)
from assistant_pages import _bingkai

DASAR = '/pendamping/kelola'
_CHAT = re.compile(DASAR + r'/chat/(chat_[0-9a-f]{32})/hapus\Z')
RETENSI = (
    '<ul><li><b>Akses aktif:</b> chat yang dihapus tidak dapat dibuka atau dilanjutkan.</li>'
    '<li><b>Penyimpanan lokal:</b> isi fisik dijadwalkan dihapus oleh pemeliharaan berkala, '
    'bukan dijamin hilang seketika. Salinan cadangan dapat bertahan maksimal 30 hari.</li>'
    '<li><b>Tetap ada:</b> memori terkonfirmasi, sesi latihan yang sudah dibuat, '
    'dan catatan pencegah aksi ganda tidak ikut dihapus.</li>'
    '<li><b>Data tambahan:</b> kategori topik chat dibersihkan secara berkala menurut '
    'aturan sensor yang terpisah, bukan serentak dengan chat.</li>'
    '<li><b>Layanan AI:</b> penghapusan lokal tidak menarik data yang sudah dikirim ke provider; '
    'retensi provider mengikuti kebijakannya.</li></ul>'
)
_GAYA = f'''<style>
.pendamping-kelola a {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; }}
.pendamping-kelola li {{ margin-block: {T.SP_2}; }}
.pendamping-kelola .pendamping-cek {{ min-height: {T.TARGET_SENTUH}; }}
</style>'''


def _page(isi, *, pesan=''):
    return _bingkai('Kelola data Pendamping',
        '<section class="pendamping-panel pendamping-kelola"><h1 id="judul-pendamping">Kelola data Pendamping</h1>'
        '<p>Kontrol ini tidak memanggil AI dan tidak memerlukan kuota balasan.</p>'
        + (f'<p role="alert">{html.escape(pesan)}</p>' if pesan else '')
        + isi + '<p><a href="/akun">Kembali ke Akun</a></p></section>').replace(b'</head>', _GAYA.encode() + b'</head>', 1)


def _open(*, tulis=False):
    # Tidak bootstrap/migrate dari GET atau membuat file kosong pada race path hilang.
    uri = assistant_schema.BAWAAN.resolve().as_uri() + ('?mode=rw' if tulis else '?mode=ro')
    kon = sqlite3.connect(uri, uri=True)
    kon.row_factory = sqlite3.Row
    kon.execute('PRAGMA foreign_keys=ON')
    try:
        if not tulis:
            kon.execute('PRAGMA query_only=ON')
        if kon.execute('PRAGMA user_version').fetchone()[0] != assistant_schema.VERSI_SKEMA:
            raise ValueError('skema belum tersedia')
        return kon
    except Exception:
        kon.close()
        raise


def _chat_milik(kon, principal, identitas):
    chat = assistant_store.ambil_chat(kon, principal.id_akun, identitas)
    if chat is None:
        return None
    if chat.context_kind is None:
        return chat if all(v is None for v in (chat.context_id, chat.context_version, chat.context_resource_version)) else None
    if type(chat.context_id) is not str or chat.context_kind not in ('anak', 'sesi', 'soal'):
        return None
    import database
    with database.buka() as data:
        sumber = assistant_view.sumber_tampilan(data, chat.context_kind, chat.context_id, pemilik=principal.pengguna)
    return chat if sumber is not None else None


def cabut_semua(kon, account_id, versi, *, sekarang):
    """Satu transaksi caller: cabut grant lama tanpa menghidupkan grant sebelumnya."""
    if type(versi) is not int or versi < 1:
        raise GalatForm('Versi izin tidak sah.', 400)
    if assistant_store.versi_persetujuan(kon, account_id) != versi:
        raise GalatForm('Izin berubah. Tinjau ulang sebelum mencabut.', 409)
    grants = kon.execute("SELECT id,versi FROM persetujuan WHERE account_id=? AND kategori='chat_umum' AND dicabut IS NULL", (account_id,)).fetchall()
    if not grants:
        raise GalatForm('Tidak ada izin aktif yang perlu dicabut.', 409)
    for row in grants:
        if not assistant_store.cabut_persetujuan(kon, account_id, row['id'], versi_diharapkan=row['versi'], sekarang=sekarang):
            raise GalatForm('Izin berubah. Tinjau ulang sebelum mencabut.', 409)
    konteks = kon.execute('SELECT id,versi FROM persetujuan_konteks WHERE account_id=? AND dicabut IS NULL', (account_id,)).fetchall()
    for row in konteks:
        if not assistant_store.cabut_persetujuan_konteks(kon, account_id, row['id'], versi_diharapkan=row['versi'], sekarang=sekarang):
            raise GalatForm('Izin sumber berubah. Tinjau ulang.', 409)


def _form(action, versi, label):
    return (f'<form method="post" action="{action}"><input type="hidden" name="versi" value="{int(versi)}">'
            '<label class="pendamping-cek"><input type="checkbox" name="konfirmasi" value="1" required>'
            '<span>Saya memahami konsekuensi tindakan ini.</span></label>'
            f'<button type="submit" class="pendamping-tombol">{label}</button></form>'
            f'<p><a href="{DASAR}">Batal</a></p>')


def tangani(penangan, jalur, *, post=False):
    if jalur != DASAR and not jalur.startswith(DASAR + '/'):
        return False
    principal = _principal(penangan)
    if principal is None:
        _tolak_login(penangan)
        return True
    try:
        cocok = _CHAT.fullmatch(jalur)
        if jalur not in (DASAR, DASAR + '/cabut') and not cocok:
            raise LookupError()
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(penangan.path).query, keep_blank_values=True, max_num_fields=2)
        if any(len(v) != 1 for v in q.values()) or set(q) - {'halaman'} or (q and (post or jalur != DASAR)):
            raise LookupError()
        halaman = int(q.get('halaman', ['1'])[0])
        if not 1 <= halaman <= 501:
            raise LookupError()
        data = None
        if post:
            _batasi_laju(penangan, principal.id_akun)
            data = _baca_form(penangan)
            if set(data) != {'versi', 'konfirmasi'} or not re.fullmatch(r'[0-9]{1,18}', data['versi']) or data['konfirmasi'] != '1':
                raise GalatForm('Centang konfirmasi pada formulir yang baru ditinjau.', 400)
        if not assistant_schema.BAWAAN.exists():
            if post or cocok:
                raise LookupError()
            _kirim_privat(penangan, _page('<p>Belum ada data Pendamping untuk dikelola.</p>'))
            return True
        with closing(_open(tulis=post)) as kon:
            if post:
                with kon:
                    kon.execute('BEGIN IMMEDIATE')
                    if cocok:
                        chat = _chat_milik(kon, principal, cocok[1])
                        if chat is None:
                            raise LookupError()
                        if not assistant_store.hapus_chat(kon, principal.id_akun, chat.id,
                                versi_diharapkan=int(data['versi']), sekarang=int(time.time()), retensi_detik=0):
                            raise GalatForm('Chat berubah. Tinjau ulang sebelum menghapus.', 409)
                    elif jalur == DASAR + '/cabut':
                        cabut_semua(kon, principal.id_akun, int(data['versi']), sekarang=int(time.time()))
                    else:
                        raise LookupError()
                _redirect(penangan, DASAR)
                return True
            if cocok:
                chat = _chat_milik(kon, principal, cocok[1])
                if chat is None:
                    raise LookupError()
                isi = '<h2>Hapus satu chat</h2><p>' + html.escape(assistant_view.label_chat(chat)) + '</p>'
                isi += RETENSI + _form(jalur, chat.versi, 'Hapus chat ini')
            elif jalur == DASAR + '/cabut':
                isi = ('<h2>Cabut izin Pendamping AI</h2><p>Izin pengiriman pesan dan seluruh izin sumber Pendamping akun ini akan dicabut. '
                       'Permintaan yang sudah dikirim tidak dapat ditarik kembali. Chat dan memori tidak otomatis dihapus.</p>'
                       '<p>Transkrip lama tidak dapat dibuka selama izinnya tidak sah; metadata dan kontrol hapus tetap tersedia di sini. '
                       'Memberi izin provider lagi tidak menghidupkan izin sumber lama. Izin sensor internal terpisah.</p>')
                isi += _form(jalur, assistant_store.versi_persetujuan(kon, principal.id_akun), 'Cabut izin AI')
            else:
                chats, lagi = assistant_view.riwayat(kon, principal.id_akun, halaman=halaman)
                daftar = ''.join('<li>' + html.escape(assistant_view.label_chat(chat))
                    + f' · <a href="{DASAR}/chat/{chat.id}/hapus">Tinjau &amp; hapus</a></li>'
                    for chat in chats if _chat_milik(kon, principal, chat.id) is not None)
                aktif = kon.execute("SELECT 1 FROM persetujuan WHERE account_id=? AND kategori='chat_umum' AND dicabut IS NULL LIMIT 1",(principal.id_akun,)).fetchone()
                isi = ('<p>Izin pengiriman AI: <b>' + ('ada izin tercatat' if aktif else 'tidak aktif') + '</b>.</p>'
                       + (f'<p><a href="{DASAR}/cabut">Tinjau pencabutan izin AI</a></p>' if aktif else '')
                       + '<h2>Chat tersimpan</h2><p>Daftar ini hanya metadata, bukan isi percakapan.</p>'
                       + ('<ul>' + daftar + '</ul>' if daftar else '<p>Tidak ada chat yang dapat dikelola pada halaman ini.</p>')
                       + RETENSI)
                if halaman > 1:
                    isi += f'<a href="{DASAR}?halaman={halaman-1}">Sebelumnya</a> '
                if lagi:
                    isi += f'<a href="{DASAR}?halaman={halaman+1}">Berikutnya</a>'
            _kirim_privat(penangan, _page(isi))
    except GalatForm as e:
        _kirim_privat(penangan, _page(f'<p><a href="{DASAR}">Tinjau kembali</a></p>', pesan=str(e)), e.status)
    except (LookupError, ValueError):
        _tidak_ada(penangan)
    except (OSError, sqlite3.Error):
        _kirim_privat(penangan, _page('<p>Penyimpanan lokal belum dapat diakses. Tidak ada perubahan yang dikonfirmasi.</p>'), 503)
    return True
