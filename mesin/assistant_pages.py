"""Renderer Pendamping server-side; teks model dan proyeksi UI selalu di-escape."""

from __future__ import annotations

import html
import re
from urllib.parse import urlencode

import assistant_policy
import brand
import design_tokens as T
from assistant_style import GAYA_PENDAMPING


def _esc(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _lokal(url: str) -> str:
    """Pertahanan markup; otorisasi sumber tetap tugas handler/proyeksi."""
    if (not isinstance(url, str) or not url.startswith("/") or url.startswith("//")
            or "\\" in url or any(ord(h) < 33 for h in url)):
        return ""
    return url


def _hidden(nama: str, nilai) -> str:
    return f'<input type="hidden" name="{_esc(nama)}" value="{_esc(nilai)}">'


def _tautan(url: str, label: str, kelas: str = "pendamping-tautan") -> str:
    aman = _lokal(url)
    return f'<a class="{_esc(kelas)}" href="{_esc(aman)}">{_esc(label)}</a>' if aman else ""


def _galat(teks: str) -> str:
    return (f'<p class="pendamping-galat" id="galat-pendamping" role="alert">{_esc(teks)}</p>'
            if teks else "")


def _kembali_id(kembali: str) -> str:
    return kembali if re.fullmatch(r"chat_[0-9a-f]{32}", kembali or "") else ""


def _memori_url(jalur: str, kembali: str) -> str:
    nilai = _kembali_id(kembali)
    return jalur + ("?" + urlencode({"kembali": nilai}) if nilai else "")


def _daftar_riwayat(chats, chat_id: str = "") -> str:
    if not chats:
        return '<p class="pendamping-catatan">Belum ada percakapan.</p>'
    from assistant_view import label_chat

    baris = []
    for chat in chats:
        aktif = ' aria-current="page"' if chat.id == chat_id else ""
        jenis = {"anak": "Ringkasan anak", "sesi": "Ringkasan sesi", "soal": "Soal resmi"}.get(
            chat.context_kind, "Obrolan umum · tanpa catatan anak")
        if chat.mode_memori == "tanpa_memori":
            jenis += " · tanpa memori"
        baris.append(
            f'<a href="/pendamping/chat/{_esc(chat.id)}"{aktif}>'
            f'<strong>{_esc(label_chat(chat))}</strong><small>{_esc(jenis)}</small></a>'
        )
    return '<nav class="pendamping-daftar-riwayat" aria-label="Daftar percakapan">' + "".join(baris) + '</nav>'


def _riwayat(chats, chat_id: str = "") -> str:
    return ('<details class="pendamping-riwayat"><summary>Riwayat</summary>'
            '<div class="pendamping-rincian">' + (_daftar_riwayat(chats, chat_id) if chats else '')
            + _tautan('/pendamping/riwayat', 'Lihat semua riwayat') + '</div></details>')


def _bingkai(judul: str, isi: str, *, chats=(), chat_id: str = "",
             jenis: str = "halaman", navigasi: bool = False) -> bytes:
    menu = ""
    if navigasi:
        riwayat = (_tautan('/pendamping/riwayat', 'Riwayat') if jenis == 'riwayat'
                   else _riwayat(chats, chat_id))
        menu = (
            '<nav class="pendamping-navigasi" aria-label="Navigasi Pendamping">'
            f'{riwayat}{_tautan("/pendamping", "＋ Chat baru")}'
            '<details class="pendamping-menu"><summary>Menu chat</summary>'
            '<nav aria-label="Pilihan chat">'
            f'{_tautan("/pendamping/tanpa-memori", "Chat tanpa memori")}'
            f'{_tautan(_memori_url("/pendamping/memori", chat_id), "Pengaturan memori")}'
            f'{_tautan("/guru", "Kembali ke ruang belajar")}</nav></details></nav>'
        )
    jenis_aman = jenis if jenis in ('awal', 'chat', 'riwayat') else 'kontrol'
    marker = ' pendamping-kosong' if jenis == 'awal' else ''
    return f'''<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(brand.judul(judul))}</title>{brand.tag_kepala()}
<style>{GAYA_PENDAMPING}</style></head><body class="pendamping-halaman">
<a class="pendamping-lewati" href="#utama">Lewati ke isi utama</a>
<header class="pendamping-kepala"><div class="pendamping-baris-kepala">
<div class="pendamping-merek">
{brand.mark()}<strong>{_esc(T.NAMA_PRODUK)}</strong><span>Pendamping</span></div>{menu}</div></header>
<main id="utama" tabindex="-1" class="pendamping-bungkus pendamping-{jenis_aman}{marker}"
 aria-labelledby="judul-pendamping">{isi}</main></body></html>'''.encode('utf-8')


def halaman_tidak_aktif() -> bytes:
    return _bingkai(
        "Pendamping belum aktif",
        '<h1 id="judul-pendamping">Pendamping belum aktif</h1>'
        '<p>Pengiriman AI belum tersedia. Ini tidak berarti riwayat atau memori terhapus.</p>'
        '<p>Latihan Jagomat tetap dapat digunakan seperti biasa.</p>'
        + _tautan('/guru', 'Kembali ke ruang belajar'),
    )


def _sumber(sumber, *, tautan: bool = True) -> str:
    if not sumber:
        return ""
    label = ' · '.join(str(sumber[k]) for k in ('label', 'nama', 'level') if sumber.get(k))
    link = _tautan(sumber.get('url', ''), 'Buka sumber') if tautan else ""
    return f'<div class="pendamping-sumber"><p>{_esc(label)}</p>{link}</div>'


def halaman_konteks_berubah(*, sumber=None) -> bytes:
    return _bingkai(
        "Konteks berubah",
        '<h1 id="judul-pendamping">Konteks belajar berubah</h1>'
        '<p>Data yang dipilih sudah berubah atau tidak lagi tersedia. Buka sumber '
        'belajar lagi, tinjau konteks terbaru, lalu mulai chat baru.</p>' + _sumber(sumber),
        navigasi=bool(sumber),
    )


def halaman_pilih_konteks(konteks, *, sumber=None) -> bytes:
    label = {"anak": "Gunakan ringkasan anak?", "sesi": "Gunakan ringkasan sesi?",
             "soal": "Bahas soal resmi ini?"}[konteks.jenis]
    isi_izin = ("Teks satu soal, kunci, dan pembahasan resmi akan dikirim ke DeepSeek."
                if konteks.jenis == 'soal' else
                "Ringkasan netral dari sumber ini akan dikirim ke DeepSeek, bukan seluruh catatan anak.")
    batal = _tautan((sumber or {}).get('url', ''), 'Batal, kembali ke sumber')
    return _bingkai(
        "Pilih konteks",
        f'<h1 id="judul-pendamping">{label}</h1>'
        '<section class="pendamping-panel">' + _sumber(sumber, tautan=False)
        + f'<p>{isi_izin}</p><p>Nama sumber ditampilkan di halaman ini untuk membantu '
        'mengenali pilihan, bukan ditambahkan ke muatan AI.</p>'
        '<p>Izin ini terpisah dari izin chat umum. Berpindah anak atau melepas '
        'konteks akan membuka chat baru, bukan mencabut izin.</p>'
        '<form method="post" action="/pendamping/konteks/pilih">'
        + _hidden('jenis', konteks.jenis) + _hidden('resource_id', konteks.resource_id)
        + _hidden('resource_version', konteks.versi) + _hidden('kategori', konteks.kategori)
        + _hidden('mode', 'aktif')
        + '<div class="pendamping-aksi"><button class="pendamping-tombol" type="submit">'
        'Gunakan di chat baru</button>' + batal + '</div></form></section>', navigasi=True,
    )


def halaman_persetujuan(galat: str = "", *, lanjut: str = "", sumber=None) -> bytes:
    tujuan = ""
    if lanjut:
        from assistant_navigation import tujuan_lanjut
        tujuan = tujuan_lanjut(lanjut)
    return _bingkai(
        "Persetujuan Pendamping",
        '<h1 id="judul-pendamping">Sebelum mulai</h1>'
        '<section class="pendamping-panel"><p>Pesan chat akan dikirim ke DeepSeek untuk membuat jawaban. '
        'Jangan menulis email, nomor telepon, sandi, token, atau data pribadi anak.</p>'
        '<p>Riwayat chat disimpan sampai 180 hari sejak aktivitas terakhir. '
        'Penghapusan aktif dilakukan segera; salinan cadangan dapat bertahan maksimal 30 hari.</p>'
        '<p>Jawaban AI dapat keliru. Izin sumber belajar akan diminta terpisah sebelum sumber digunakan.</p>'
        + _galat(galat) + '<form method="post" action="/pendamping/persetujuan">'
        + _hidden('kebijakan', assistant_policy.VERSI_KEBIJAKAN)
        + (_hidden('lanjut', tujuan) if tujuan else '')
        + '<label class="pendamping-cek"><input type="checkbox" name="setuju" value="1" required>'
        '<span>Saya memahami dan setuju mengirim chat ke DeepSeek.</span></label>'
        '<div class="pendamping-aksi"><button class="pendamping-tombol" type="submit">'
        'Setuju dan lanjutkan</button>'
        + _tautan((sumber or {}).get('url') or '/guru', 'Batal') + '</div></form></section>',
    )


def _composer(action: str, request_id: str, *, awal: bool = False,
              mode: str = "aktif", galat: str = "") -> str:
    nama = 'pesan_awal' if awal else 'pesan'
    label = 'Tulis pesan untuk Pendamping' if awal else 'Pesan untuk Pendamping'
    placeholder = 'Apa yang bisa dibantu hari ini?' if awal else 'Tulis pesanmu di sini…'
    label_kelas = 'pendamping-sr' if awal else 'pendamping-label'
    galat_atribut = ' aria-invalid="true"' if galat else ''
    petunjuk = 'petunjuk-pesan' + (' galat-pendamping' if galat else '')
    return (
        f'<form class="pendamping-form" method="post" action="{_esc(action)}">'
        + _galat(galat) + _hidden('request_id', request_id)
        + (_hidden('mode', mode) if awal else '')
        + f'<label class="{label_kelas}" for="pesan">{label}</label>'
        '<div class="pendamping-composer-kotak">'
        f'<textarea class="pendamping-input" id="pesan" name="{nama}" rows="3" '
        f'placeholder="{placeholder}" maxlength="8000" required '
        f'aria-describedby="{petunjuk}"{galat_atribut}></textarea>'
        '<button class="pendamping-tombol pendamping-kirim" type="submit" aria-label="Kirim pesan">'
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6"/></svg></button></div>'
        '<p class="pendamping-composer-meta" id="petunjuk-pesan">Enter membuat baris baru. '
        'Gunakan tombol kirim untuk mengirim pesan.</p></form>'
    )


def halaman_awal(chats, galat: str = "", request_id: str = "", *, mode: str = "aktif") -> bytes:
    if mode not in ('aktif', 'tanpa_memori'):
        raise ValueError('Mode chat tidak dikenal.')
    status = ('<p class="pendamping-status">Chat tanpa memori</p>' if mode == 'tanpa_memori' else '')
    catatan = ('Chat tanpa memori tetap tersimpan sebagai riwayat, tetapi tidak membaca atau menambah '
               'memori lintas chat.' if mode == 'tanpa_memori' else 'Obrolan umum · tanpa catatan anak')
    return _bingkai(
        'Pendamping', '<h1 class="pendamping-sr" id="judul-pendamping">Chat baru</h1>'
        + status + _composer('/pendamping/chat-baru', request_id, awal=True, mode=mode, galat=galat)
        + f'<p class="pendamping-catatan">{catatan}</p>',
        chats=chats, jenis='awal', navigasi=True,
    )


def halaman_riwayat(chats, *, halaman: int = 1, ada_lagi: bool = False, chat_id: str = '') -> bytes:
    if type(halaman) is not int or not 1 <= halaman <= 501:
        raise ValueError('Halaman riwayat tidak sah.')
    paginasi = ''
    if halaman > 1:
        paginasi += _tautan(f'/pendamping/riwayat?halaman={halaman - 1}', 'Sebelumnya')
    if ada_lagi and halaman < 501:
        paginasi += _tautan(f'/pendamping/riwayat?halaman={halaman + 1}', 'Berikutnya')
    return _bingkai(
        'Riwayat chat', '<h1 id="judul-pendamping">Riwayat chat</h1>'
        '<p class="pendamping-catatan">Waktu mulai dan kode chat tetap, tanpa cuplikan percakapan.</p>'
        + _daftar_riwayat(chats, chat_id)
        + f'<p class="pendamping-catatan">Halaman {halaman}</p>'
        + (f'<nav class="pendamping-aksi" aria-label="Halaman riwayat">{paginasi}</nav>' if paginasi else ''),
        jenis='riwayat', navigasi=True,
    )


def _draft_memori(item, kembali: str = '') -> str:
    field = _hidden('versi', item.versi) + _hidden('kembali', _kembali_id(kembali))
    return (
        '<aside class="pendamping-panel pendamping-memori">'
        '<h2>Simpan preferensi ini?</h2><p class="pendamping-catatan">Belum menjadi memori. '
        'Hanya digunakan setelah kamu mengonfirmasi.</p>'
        f'<p class="pendamping-teks">{_esc(item.isi)}</p><div class="pendamping-aksi">'
        f'<form method="post" action="/pendamping/memori/{_esc(item.id)}/konfirmasi">{field}'
        '<button class="pendamping-tombol pendamping-sekunder" type="submit">Konfirmasi memori</button></form>'
        f'<form method="post" action="/pendamping/memori/{_esc(item.id)}/hapus">{field}'
        + _hidden('persetujuan_hapus', '1') +
        '<button class="pendamping-tombol pendamping-sekunder" type="submit">Abaikan</button>'
        '</form></div></aside>'
    )


def _daftar_memori(memori, kembali: str = '') -> str:
    if not memori:
        return '<p class="pendamping-catatan">Belum ada preferensi tersimpan.</p>'
    baris = []
    for item in memori:
        if not item.dikonfirmasi:
            baris.append(_draft_memori(item, kembali))
            continue
        dasar = f'/pendamping/memori/{item.id}'
        baris.append(
            '<article class="pendamping-panel pendamping-memori">'
            '<p class="pendamping-catatan">Tersimpan · Preferensi orang tua</p>'
            f'<p class="pendamping-teks">{_esc(item.isi)}</p>'
            '<div class="pendamping-aksi">'
            + _tautan(_memori_url(dasar + '/ubah', kembali), 'Ubah')
            + _tautan(_memori_url(dasar + '/hapus', kembali), 'Hapus', 'pendamping-tautan pendamping-bahaya')
            + '</div></article>'
        )
    return ''.join(baris)


def halaman_memori(memori, *, aktif: bool, versi: int, galat: str = '', kembali: str = '') -> bytes:
    memori = tuple(memori)
    jumlah = sum(bool(item.dikonfirmasi) for item in memori)
    status = ('Memori aktif' if aktif else 'Memori nonaktif') + (
        f' · {jumlah} catatan' if jumlah else ' · belum ada catatan')
    aksi = 'nonaktifkan' if aktif else 'aktifkan'
    label = 'Nonaktifkan penggunaan' if aktif else 'Aktifkan penggunaan'
    kembali_chat = _kembali_id(kembali)
    return _bingkai(
        'Memori Pendamping', '<h1 id="judul-pendamping">Memori Pendamping</h1>'
        '<p>Hanya preferensi cara Pendamping menjawab. Memori tidak menyimpan '
        'profil, diagnosis, kontak, atau ringkasan curhatan anak.</p>'
        + _galat(galat) + f'<p class="pendamping-status">{status}</p>'
        '<p class="pendamping-catatan">Menonaktifkan penggunaan tidak menghapus catatan. '
        'Kamu tetap dapat melihat, mengoreksi, atau menghapusnya. Saat nonaktif, Pendamping tidak memakai '
        'atau menambah memori. Catatan belum dikonfirmasi tidak digunakan.</p>'
        f'<form method="post" action="/pendamping/memori/{aksi}">'
        + _hidden('versi', versi) + _hidden('kembali', kembali_chat)
        + f'<button class="pendamping-tombol pendamping-sekunder" type="submit">{label}</button></form>'
        + _daftar_memori(memori, kembali)
        + '<div class="pendamping-aksi">'
        + (_tautan(_memori_url('/pendamping/memori/hapus-semua', kembali), 'Hapus semua memori',
                   'pendamping-tautan pendamping-bahaya') if memori else '')
        + (_tautan(f'/pendamping/chat/{kembali_chat}', 'Kembali ke chat') if kembali_chat else '')
        + '</div>', navigasi=True, chat_id=kembali_chat,
    )


def halaman_edit_memori(item, *, galat: str = '', kembali: str = '') -> bytes:
    isi = '' if galat else _esc(item.isi)
    invalid = ' aria-invalid="true"' if galat else ''
    deskripsi = 'petunjuk-memori' + (' galat-pendamping' if galat else '')
    return _bingkai(
        'Ubah preferensi', '<h1 id="judul-pendamping">Ubah preferensi</h1>'
        '<p id="petunjuk-memori">Tuliskan preferensi cara menjawab, bukan cerita atau data pribadi. '
        'Contoh yang didukung: “Jawab ringkas dengan contoh konkret.”</p>'
        + _galat(galat)
        + f'<form method="post" action="/pendamping/memori/{_esc(item.id)}/ubah">'
        + _hidden('versi', item.versi) + _hidden('kembali', _kembali_id(kembali))
        + '<label class="pendamping-label" for="isi-memori">Isi preferensi</label>'
        f'<textarea class="pendamping-input pendamping-input-pendek pendamping-editor" id="isi-memori" name="isi" '
        f'required maxlength="500" aria-describedby="{deskripsi}"{invalid}>{isi}</textarea>'
        '<div class="pendamping-aksi"><button class="pendamping-tombol" type="submit">Simpan koreksi</button>'
        + _tautan(_memori_url('/pendamping/memori', kembali), 'Batal') + '</div></form>',
        navigasi=True, chat_id=_kembali_id(kembali),
    )


def halaman_hapus_memori(memori, *, versi: int, semua: bool = False, kembali: str = '') -> bytes:
    memori = tuple(memori)
    if not memori or (not semua and len(memori) != 1):
        raise ValueError('Tinjauan hapus membutuhkan catatan yang sah.')
    judul = 'Hapus semua memori?' if semua else 'Hapus catatan ini?'
    action = '/pendamping/memori/hapus-semua' if semua else f'/pendamping/memori/{memori[0].id}/hapus'
    rincian = (f'<p>{len(memori)} catatan akan dihapus, termasuk draft yang belum dikonfirmasi.</p>'
               if semua else f'<p class="pendamping-teks">{_esc(memori[0].isi)}</p>')
    return _bingkai(judul,
        f'<h1 id="judul-pendamping">{judul}</h1><section class="pendamping-panel">{rincian}'
        '<p>Chat lama tetap ada. Menghapus memori tidak menghapus isi percakapan sumber. '
        'Salinan cadangan dapat bertahan maksimal 30 hari.</p>'
        f'<form method="post" action="{_esc(action)}">'
        + _hidden('versi', versi) + _hidden('kembali', _kembali_id(kembali))
        + '<label class="pendamping-cek"><input type="checkbox" name="persetujuan_hapus" value="1" required>'
        '<span>Saya memahami catatan memori ini akan dihapus.</span></label>'
        '<div class="pendamping-aksi"><button class="pendamping-tombol pendamping-bahaya" type="submit">'
        + ('Hapus semua memori' if semua else 'Hapus memori ini') + '</button>'
        + _tautan(_memori_url('/pendamping/memori', kembali), 'Batal') + '</div></form></section>',
        navigasi=True, chat_id=_kembali_id(kembali),
    )


def _kartu_usulan(usulan) -> str:
    if not usulan:
        return ''
    from assistant_view import ringkasan_usulan

    kartu = []
    for item in usulan:
        data = ringkasan_usulan(item.payload_json)
        selesai = item.sesi_id is not None
        kartu.append(
            '<aside class="pendamping-panel pendamping-usulan"><h2>'
            + ('Hasil latihan' if selesai else 'Usulan latihan') + '</h2>'
            f'<p>{_esc(data["topik"])} · {_esc(data["level"])} · {_esc(data["jumlah"])} soal</p>'
            '<p class="pendamping-catatan">'
            + ('Latihan sudah pernah dibuat. Buka hasil untuk memeriksa sesi yang tersedia.' if selesai else
               'Usulan sudah divalidasi Jagomat. Belum ada sesi yang dibuat.') + '</p>'
            + _tautan(f'/pendamping/usulan/{item.id}', 'Buka hasil latihan' if selesai else 'Tinjau usulan',
                      'pendamping-tombol pendamping-sekunder') + '</aside>'
        )
    return ''.join(kartu)


def halaman_tinjau_usulan(usulan, chat, konteks, *, request_id: str, sumber=None, pesan_sumber=None) -> bytes:
    from assistant_view import ringkasan_usulan

    data = ringkasan_usulan(usulan.payload_json)
    materi = ''.join(f'<li>{_esc(label)} · {_esc(jumlah)} soal</li>' for label, jumlah, _ in data['materi'])
    rincian = ''.join(f'<li><code>{_esc(template)}</code></li>' for _, _, template in data['materi'])
    pesan = '<p class="pendamping-catatan">Sumber permintaan: konteks belajar yang dipilih.</p>'
    if pesan_sumber is not None:
        pesan = ('<section class="pendamping-sumber"><h2>Sumber permintaan</h2>'
                 f'<blockquote class="pendamping-teks">{_esc(pesan_sumber.teks)}</blockquote>'
                 + _tautan(f'/pendamping/chat/{chat.id}#pesan-{pesan_sumber.id}', 'Lihat pesan sumber') + '</section>')
    if usulan.sesi_id is not None:
        aksi = '<p role="status">Latihan sudah pernah dibuat.</p>' + _tautan(
            f'/pendamping/usulan/{usulan.id}', 'Buka hasil latihan', 'pendamping-tombol')
    else:
        aksi = (
            f'<form method="post" action="/pendamping/usulan/{_esc(usulan.id)}/konfirmasi">'
            + _hidden('versi', usulan.versi) + _hidden('hash', usulan.hash_usulan)
            + _hidden('request_id', request_id)
            + '<div class="pendamping-aksi"><button class="pendamping-tombol" type="submit">'
            'Konfirmasi dan buat latihan</button>' + _tautan(f'/pendamping/chat/{chat.id}', 'Batal, kembali ke chat')
            + '</div></form>'
        )
    return _bingkai(
        'Tinjau usulan latihan', '<h1 id="judul-pendamping">Tinjau usulan latihan</h1>'
        + _sumber(sumber) + pesan + '<section class="pendamping-panel pendamping-usulan">'
        f'<dl><dt>Topik</dt><dd>{_esc(data["topik"])}</dd><dt>Level</dt><dd>{_esc(data["level"])}</dd>'
        f'<dt>Jumlah</dt><dd>{_esc(data["jumlah"])} soal</dd></dl><h2>Materi latihan</h2><ul>{materi}</ul>'
        '<p class="pendamping-catatan">Pilihan di atas tidak dapat diubah di sini. '
        'Untuk meminta perubahan, kembali ke chat.</p><details><summary>Rincian teknis</summary>'
        f'<ul>{rincian}</ul></details></section>'
        '<p>Konfirmasi berikut membuat satu sesi latihan manual/bebas. '
        'Sesi ini tidak mengubah bukti atau putaran siklus belajar.</p>' + aksi, navigasi=True,
    )


def halaman_hasil_usulan(usulan, *, sesi_id: int, sumber=None) -> bytes:
    if type(sesi_id) is not int or sesi_id < 1:
        raise ValueError('Hasil membutuhkan ID sesi yang sudah divalidasi server.')
    return _bingkai(
        'Latihan siap', f'<h1 id="judul-pendamping">Latihan #{sesi_id} siap</h1>'
        + _sumber(sumber) + '<section class="pendamping-panel pendamping-hasil">'
        f'<p class="pendamping-status">Sesi #{sesi_id}</p>'
        '<p>Ini latihan bebas, bukan bukti kemajuan dan tidak otomatis mengubah rencana belajar.</p>'
        '<p>Membuka hasil ini lagi tidak membuat latihan kedua.</p><div class="pendamping-aksi">'
        + _tautan(f'/sesi/{sesi_id}', 'Buka latihan', 'pendamping-tombol')
        + _tautan(f'/pendamping/chat/{usulan.chat_id}', 'Kembali ke chat') + '</div></section>', navigasi=True,
    )


def halaman_status_operasi(status: str, *, chat_id: str, request_id: str) -> bytes:
    if status not in ('pending', 'gagal'):
        raise ValueError('Status operasi tidak dikenal.')
    pending = status == 'pending'
    judul = 'Jawaban masih ditunggu' if pending else 'Jawaban belum tersedia'
    isi = ('Status permintaan belum selesai. Jangan kirim ulang pesan yang sama. '
           'Periksa status untuk membuka jawaban bila sudah tersedia.' if pending else
           'Permintaan ini gagal. Tidak ada jawaban yang dibuat-buat. '
           'Kembali ke chat untuk menulis pesan baru saat siap.')
    aksi = _tautan(f'/pendamping/operasi/{request_id}', 'Periksa status', 'pendamping-tombol') if pending else _tautan(
        f'/pendamping/chat/{chat_id}', 'Kembali ke chat', 'pendamping-tombol')
    return _bingkai('Status jawaban', f'<h1 id="judul-pendamping">{judul}</h1><p role="status">{isi}</p>' + aksi,
                    navigasi=True)


def halaman_chat(chat, pesan, chats, *, galat: str = '', request_id: str, draft=(), konteks=None,
                 usulan=(), status_memori: str = '', sumber=None, hanya_baca: bool = False,
                 operasi_url: str = '') -> bytes:
    daftar = ''.join(
        f'<article class="pendamping-pesan {"pengguna" if item.peran == "pengguna" else "asisten"}" '
        f'id="pesan-{_esc(item.id)}"><h2 class="pendamping-peran">'
        f'{"Kamu" if item.peran == "pengguna" else "Pendamping"}</h2>'
        f'<p class="pendamping-teks">{_esc(item.teks)}</p></article>' for item in pesan
    )
    tanpa_memori = chat.mode_memori == 'tanpa_memori'
    status = 'Chat tanpa memori' if tanpa_memori else (status_memori or 'Pengaturan memori tersedia di Menu chat')
    sumber_html = _sumber(sumber)
    if not sumber_html:
        label = {"anak": "Ringkasan anak terpilih", "sesi": "Sesi belajar terpilih", "soal": "Soal resmi terpilih"}.get(
            getattr(konteks, 'jenis', None) or chat.context_kind, 'Obrolan umum · tanpa catatan anak')
        sumber_html = f'<p class="pendamping-catatan">{label}</p>'
    if sumber or konteks is not None or chat.context_kind:
        sumber_html += (
            '<details class="pendamping-ganti-sumber"><summary>Ganti atau lepas sumber</summary>'
            '<div class="pendamping-rincian"><p>Untuk mengganti sumber, buka sumber di atas '
            'atau pilih sumber lain dari ruang belajar, lalu tinjau izin untuk chat baru.</p>'
            '<p>Untuk melepas sumber, gunakan Chat baru di header. Percakapan ini tetap '
            'memakai sumber asal; tindakan tersebut bukan mencabut izin.</p>'
            '<p>Tutup rincian ini untuk tetap di chat yang sama.</p></div></details>')
    aksi = ''
    pemberitahuan = ''
    if hanya_baca:
        pemberitahuan = ('<p class="pendamping-info" role="status">Konteks telah berubah. Percakapan ini hanya dapat dibaca. '
                'Untuk melanjutkan, buka sumber dan tinjau konteks terbaru.</p>' + _galat(galat))
        aksi = _kartu_usulan(tuple(item for item in usulan
                                  if item.status == 'selesai' and item.sesi_id is not None))
    elif operasi_url:
        pemberitahuan = ('<div class="pendamping-info" role="status"><p>Jawaban masih ditunggu. '
                'Jangan kirim ulang pesan yang sama.</p>'
                + _tautan(operasi_url, 'Periksa status') + '</div>' + _galat(galat))
    else:
        aksi = (''.join(_draft_memori(item, chat.id) for item in draft) if not tanpa_memori else '')
        aksi += _kartu_usulan(usulan)
        aksi += _composer(f'/pendamping/chat/{chat.id}/pesan', request_id, galat=galat)
    catatan = ('<p class="pendamping-catatan">Chat tetap tersimpan sebagai riwayat, tetapi tidak membaca atau '
               'menambah memori lintas chat.</p>' if tanpa_memori else '')
    return _bingkai(
        'Chat Pendamping', '<h1 class="pendamping-sr" id="judul-pendamping">Pendamping</h1>'
        + sumber_html + f'<p class="pendamping-catatan">{_esc(status)}</p>' + catatan + pemberitahuan
        + '<div class="pendamping-transkrip">' + daftar + '</div>' + aksi,
        chats=chats, chat_id=chat.id, jenis='chat', navigasi=True,
    )
