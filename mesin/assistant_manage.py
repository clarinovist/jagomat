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
from datetime import datetime

DASAR = '/pendamping/kelola'
_CHAT = re.compile(DASAR + r'/chat/(chat_[0-9a-f]{32})/hapus\Z')
_RETENSI = (
    ('Akses aktif', 'chat yang dihapus tidak dapat dibuka atau dilanjutkan.'),
    ('Penyimpanan lokal', 'isi fisik dijadwalkan dihapus oleh pemeliharaan berkala, '
     'bukan dijamin hilang seketika. Salinan cadangan dapat bertahan maksimal 30 hari.'),
    ('Tetap ada', 'memori terkonfirmasi, sesi latihan yang sudah dibuat, '
     'dan catatan pencegah aksi ganda tidak ikut dihapus.'),
    ('Data tambahan', 'kategori topik chat dibersihkan secara berkala menurut '
     'aturan sensor yang terpisah, bukan serentak dengan chat.'),
    ('Layanan AI', 'penghapusan lokal tidak menarik data yang sudah dikirim ke provider; '
     'retensi provider mengikuti kebijakannya.'),
)


def _butir(*indeks):
    return ''.join(f'<li><b>{_RETENSI[i][0]}:</b> {_RETENSI[i][1]}</li>' for i in indeks)


# Halaman konfirmasi: konsekuensi selalu terlihat penuh, tidak dilipat.
RETENSI = '<ul class="akun-retensi-st">' + _butir(0, 1, 2, 3, 4) + '</ul>'


def _retensi_ringkas():
    """Halaman utama: satu kalimat langsung terlihat, sisanya dilipat per topik."""
    def lipat(judul, *indeks):
        return f'<details class="akun-retensi-lipat-st"><summary>{judul}</summary><ul class="akun-retensi-st">{_butir(*indeks)}</ul></details>'
    return ('<section class="kartu-st"><h2>Apa yang terjadi saat Anda menghapus</h2>'
            f'<p class="akun-catatan-st"><b>Langsung:</b> {_RETENSI[0][1]}</p>'
            + lipat('Penyimpanan dan cadangan', 1) + lipat('Yang tetap ada', 2, 3) + lipat('Layanan AI', 4)
            + '</section>')


def _page(isi, *, pesan='', pengguna='guru'):
    from teacher_pages import _halaman
    return _halaman(
        'Kelola data Pendamping',
        '<div class="jejak"><a href="/akun">← Kembali ke Akun</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">AKUN KELUARGA · PENDAMPING AI</p>'
        '<h1 id="judul-pendamping">Data Pendamping</h1>'
        '<p class="sub">Kontrol ini tidak memanggil AI dan tidak memerlukan kuota balasan.</p></header>'
        + (f'<p class="akun-catatan-st" role="alert">{html.escape(pesan)}</p>' if pesan else '')
        + isi,
        ident=(pengguna, 'guru'), stitch=True, kelas_bungkus='pendamping-editorial-st akun-editorial-st akun-sempit-st',
        id_utama='judul-pendamping', privat=True)


def _kartu_izin(aktif):
    return ('<section class="kartu-st akun-izin-st" aria-labelledby="judul-izin-ai"><div>'
            '<h2 id="judul-izin-ai">Izin pengiriman AI</h2>'
            f'<p class="sub">{"Ada izin tercatat." if aktif else "Izin pengiriman AI tidak aktif."}</p></div>'
            + ('<span class="akun-chip-st akun-chip-ok-st">Ada izin</span>'
               f'<a class="akun-tombol-garis-st" href="{DASAR}/cabut">Tinjau pencabutan izin AI</a>' if aktif
               else '<span class="akun-chip-st">Tidak aktif</span>')
            + '</section>')


def _baris_chat(chat):
    waktu = datetime.fromtimestamp(chat.dibuat, tz=assistant_view._WIB)
    label = html.escape(assistant_view.label_chat(chat), quote=True)
    return ('<div class="akun-chat-st"><div><span class="akun-chat-judul-st">'
            + html.escape(assistant_view.jenis_chat(chat)) + '</span>'
            f'<span class="akun-chat-waktu-st">{waktu:%H.%M} WIB</span></div>'
            f'<a class="akun-tombol-garis-st" href="{DASAR}/chat/{chat.id}/hapus" '
            f'aria-label="Tinjau dan hapus chat {label}">Tinjau &amp; hapus</a></div>')


def _kartu_chat(chats, halaman, lagi):
    if not chats:
        daftar = '<p class="sub">Tidak ada chat yang dapat dikelola pada halaman ini.</p>'
    else:
        daftar, tanggal = '', None
        for chat in chats:
            waktu = datetime.fromtimestamp(chat.dibuat, tz=assistant_view._WIB)
            if waktu.date() != tanggal:
                tanggal = waktu.date()
                daftar += (f'<p class="akun-grup-tanggal-st">{tanggal.day:02d} '
                           f'{assistant_view._BULAN[tanggal.month - 1].upper()} {tanggal.year}</p>')
            daftar += _baris_chat(chat)
    nav = ''
    if halaman > 1:
        nav += f'<a class="akun-tautan-st" href="{DASAR}?halaman={halaman-1}">Sebelumnya</a>'
    if lagi:
        nav += f'<a class="akun-tautan-st" href="{DASAR}?halaman={halaman+1}">Berikutnya</a>'
    return ('<section class="kartu-st" aria-labelledby="judul-chat-tersimpan"><h2 id="judul-chat-tersimpan">Chat tersimpan</h2>'
            '<p class="sub">Daftar ini hanya metadata, bukan isi percakapan.</p>'
            + daftar + (f'<div class="akun-aksi-baris-st">{nav}</div>' if nav else '') + '</section>')


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
            '<label class="akun-label-persetujuan"><input type="checkbox" name="konfirmasi" value="1" required>'
            '<span>Saya memahami konsekuensi tindakan ini.</span></label>'
            '<div class="akun-aksi-baris-st">'
            f'<button type="submit" class="tombol-bahaya-akun">{label}</button>'
            f'<a class="akun-tautan-st" href="{DASAR}">Batal</a></div></form>')


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
            _kirim_privat(penangan, _page('<section class="kartu-st"><p class="sub">Belum ada data Pendamping untuk dikelola.</p></section>', pengguna=principal.pengguna))
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
                isi = ('<section class="kartu-st"><h2>Hapus satu chat</h2><p class="sub">'
                       + html.escape(assistant_view.label_chat(chat)) + '</p>'
                       + RETENSI + _form(jalur, chat.versi, 'Hapus chat ini') + '</section>')
            elif jalur == DASAR + '/cabut':
                isi = ('<section class="kartu-st"><h2>Cabut izin Pendamping AI</h2><p class="sub">Izin pengiriman pesan dan seluruh izin sumber Pendamping akun ini akan dicabut. '
                       'Permintaan yang sudah dikirim tidak dapat ditarik kembali. Chat dan memori tidak otomatis dihapus.</p>'
                       '<p class="sub">Transkrip lama tidak dapat dibuka selama izinnya tidak sah; metadata dan kontrol hapus tetap tersedia di sini. '
                       'Memberi izin provider lagi tidak menghidupkan izin sumber lama. Izin sensor internal terpisah.</p>')
                isi += _form(jalur, assistant_store.versi_persetujuan(kon, principal.id_akun), 'Cabut izin AI') + '</section>'
            else:
                chats, lagi = assistant_view.riwayat(kon, principal.id_akun, halaman=halaman)
                aktif = kon.execute("SELECT 1 FROM persetujuan WHERE account_id=? AND kategori='chat_umum' AND dicabut IS NULL LIMIT 1",(principal.id_akun,)).fetchone()
                isi = _kartu_izin(bool(aktif)) + _kartu_chat(
                    [c for c in chats if _chat_milik(kon, principal, c.id) is not None], halaman, lagi,
                ) + _retensi_ringkas()
            _kirim_privat(penangan, _page(isi, pengguna=principal.pengguna))
    except GalatForm as e:
        _kirim_privat(penangan, _page(f'<section class="kartu-st"><a class="akun-tautan-st" href="{DASAR}">Tinjau kembali</a></section>', pesan=str(e), pengguna=principal.pengguna), e.status)
    except (LookupError, ValueError):
        _tidak_ada(penangan)
    except (OSError, sqlite3.Error):
        _kirim_privat(penangan, _page('<section class="kartu-st"><p class="sub">Penyimpanan lokal belum dapat diakses. Tidak ada perubahan yang dikonfirmasi.</p></section>', pengguna=principal.pengguna), 503)
    return True
