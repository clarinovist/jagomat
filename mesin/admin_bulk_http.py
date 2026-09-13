"""Pilihan dan transport native batch admin; mutasi tetap layanan domain."""
from __future__ import annotations

import html
import secrets

import admin_bulk
import admin_pages
import admin_security
import auth
from admin_contracts import AKSI_CABUT_SESI, AKSI_RESET_SANDI

BATAS_BODY = 64 * 1024


def _e(nilai):
    return html.escape(str(nilai), quote=True)


def _hidden(nama, nilai):
    return '<input type="hidden" name="%s" value="%s">' % (_e(nama), _e(nilai))


def _snapshot(akun):
    return [akun['id_akun'], auth.revisi_auth(akun), akun['peran']]


def _render(penangan, principal, *, peran, pilihan, cari='', halaman=1):
    import admin_http as H
    if peran not in ('guru', 'murid') or not 1 <= halaman <= 100000:
        raise ValueError('Pilihan tidak sah.')
    if len(cari) > 80 or any(ord(c) < 32 for c in cari):
        raise ValueError('Pencarian tidak sah.')
    akun, sesi = H._akun_principal(principal), H._wajib_cookie(penangan, principal)
    semua = [a for a in auth.muat_akun() if a.get('peran') == peran]
    indeks = {a['id_akun']: a for a in semua}
    cocok = sorted((a for a in semua if cari.casefold() in a['pengguna'].casefold()),
                   key=lambda a: (a['pengguna'].casefold(), a['id_akun']))
    jumlah_halaman = max(1, (len(cocok) + 24) // 25)
    halaman = min(halaman, jumlah_halaman)
    daftar = cocok[(halaman - 1) * 25:halaman * 25]
    token = admin_security.buat_tinjauan(akun, sesi, 'bulk_selection',
                                        {'pilihan': pilihan, 'target_peran': peran})
    token_halaman = admin_security.buat_tinjauan(akun, sesi, 'bulk_page',
        {'pilihan': [_snapshot(a) for a in daftar], 'target_peran': peran})
    dasar = _hidden('pilihan', token) + _hidden('csrf', H._csrf(akun, sesi))
    opsi = ''.join('<label><input type="checkbox" name="target" value="%s"> %s</label>'
                   % (_e(a['id_akun']), _e(a['pengguna'])) for a in daftar)
    dipilih = ''.join('<label><input type="checkbox" name="hapus" value="%s"> %s%s</label>' % (
        _e(x[0]), _e(indeks[x[0]]['pengguna'] if x[0] in indeks else x[0]),
        ' — berubah, tinjau ulang' if x[0] not in indeks or _snapshot(indeks[x[0]]) != x else '',
    ) for x in pilihan)
    isi = (
        '<section class="admin-kartu"><h2>Pilih akun %s</h2>'
        '<p>Maksimal 100 akun. Filter dan pindah halaman tidak mengubah pilihan.</p>'
        '<form method="post" action="/admin/bulk/pilih">%s%s'
        '<label>Cari alias<input name="cari" maxlength="80" value="%s"></label>'
        '<button name="mode" value="cari" class="admin-tombol">Cari</button></form>'
        '<form method="post" action="/admin/bulk/pilih">%s%s%s%s'
        '<fieldset><legend>Halaman %d dari %d</legend>%s</fieldset>'
        '<button name="mode" value="tambah" class="admin-tombol">Tambahkan yang dicentang</button>'
        '<button name="mode" value="halaman" class="admin-tombol">Tambahkan halaman ini ke pilihan</button>'
        '</form>'
        % ('orang tua' if peran == 'guru' else 'murid', dasar, _hidden('halaman', 1), _e(cari),
           dasar, _hidden('halaman_token', token_halaman), _hidden('halaman', halaman), _hidden('cari', cari),
           halaman, jumlah_halaman, opsi or '<p>Tidak ada hasil.</p>')
    )
    for tujuan, label in ((halaman - 1, 'Sebelumnya'), (halaman + 1, 'Berikutnya')):
        if 1 <= tujuan <= jumlah_halaman:
            isi += '<form method="post" action="/admin/bulk/pilih">%s%s%s<button name="mode" value="cari">%s</button></form>' % (
                dasar, _hidden('halaman', tujuan), _hidden('cari', cari), label)
    isi += ('</section><section class="admin-kartu"><h2>Pilihan: %d akun</h2>'
        '<form method="post" action="/admin/bulk/pilih">%s%s'
        '<button name="mode" value="hapus">Hapus yang dicentang dari pilihan</button>'
        '<button name="mode" value="kosongkan">Kosongkan pilihan</button></form>'
        '<form method="post" action="/admin/bulk/pilih">%s'
        '<label>Aksi<select name="aksi"><option value="account_password_reset">Setel ulang sandi unik</option>'
        '<option value="account_session_revoke">Keluarkan semua perangkat</option></select></label>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" autocomplete="current-password" required></label>'
        '<button name="mode" value="tinjau" class="admin-tombol">Tinjau pilihan</button></form></section>'
        % (len(pilihan), dasar, dipilih or '<p>Belum ada pilihan.</p>', dasar))
    H._kirim_privat(penangan, H._halaman_admin(principal, 'keluarga' if peran == 'guru' else 'siswa', isi, skrip=True), skrip=True)


def get_pilihan(penangan, principal):
    import admin_http as H
    query = H._query(penangan, diizinkan={'peran'})
    _render(penangan, principal, peran=query.get('peran', 'guru'), pilihan=[])


def post_pilihan(penangan, principal, data):
    import admin_http as H
    akun, sesi = H._akun_principal(principal), H._wajib_cookie(penangan, principal)
    H._cek_csrf(akun, sesi, data.pop('csrf', None))
    signed = admin_security.periksa_tinjauan(akun, sesi, data.pop('pilihan', None))
    if signed['aksi'] != 'bulk_selection':
        raise PermissionError('Pilihan tidak sah.')
    pilihan = signed['data']['pilihan']
    peran = signed['data']['target_peran']
    mode = data.pop('mode', '')
    fields = {
        'cari': {'halaman', 'cari'},
        'tambah': {'halaman', 'cari', 'target', 'halaman_token'},
        'halaman': {'halaman', 'cari', 'target', 'halaman_token'},
        'hapus': {'hapus'}, 'kosongkan': {'hapus'},
        'tinjau': {'aksi', 'reauth'},
    }
    if mode not in fields or set(data) - fields[mode]:
        raise ValueError('Field tidak dikenal untuk tindakan ini.')
    halaman = H._angka(data.pop('halaman', '1'))
    cari = data.pop('cari', '')
    target = data.pop('target', [])
    hapus = data.pop('hapus', [])
    if len(target) != len(set(target)) or len(hapus) != len(set(hapus)):
        raise ValueError('ID ganda tidak sah.')
    if mode in ('tambah', 'halaman'):
        page = admin_security.periksa_tinjauan(akun, sesi, data.pop('halaman_token', None))
        if page['aksi'] != 'bulk_page' or page['data']['target_peran'] != peran:
            raise PermissionError('Halaman tidak cocok.')
        daftar = page['data']['pilihan']
        tersedia = {x[0]: x for x in daftar}
        if set(target) - set(tersedia):
            raise ValueError('Target di luar halaman.')
        tambah = daftar if mode == 'halaman' else [tersedia[x] for x in target]
        ada = {x[0] for x in pilihan}
        pilihan = pilihan + [x for x in tambah if x[0] not in ada]
        if len(pilihan) > 100:
            raise ValueError('Maksimal 100 target.')
    elif mode == 'hapus':
        if set(hapus) - {x[0] for x in pilihan}:
            raise ValueError('Target di luar pilihan.')
        pilihan = [x for x in pilihan if x[0] not in hapus]
    elif mode == 'kosongkan':
        pilihan = []
    elif mode == 'tinjau':
        aksi = data.pop('aksi', '')
        if not H._reauth(principal, data.pop('reauth', '')):
            raise PermissionError('Autentikasi ulang gagal.')
        if aksi not in (AKSI_RESET_SANDI, AKSI_CABUT_SESI) or not pilihan or data or target or hapus:
            raise ValueError('Tinjauan tidak sah.')
        semua = {a['id_akun']: a for a in auth.muat_akun()}
        if any(x[2] != peran or x[0] not in semua or _snapshot(semua[x[0]]) != x for x in pilihan):
            raise H.admin_store.KonflikOperasi('Target berubah.')
        targets = tuple(admin_bulk.TargetBulk('item_' + secrets.token_hex(16),
            'op_' + secrets.token_hex(16), x[0], x[1], peran) for x in pilihan)
        return H.buat_tinjauan_batch(penangan, principal, aksi, peran, targets)
    elif mode != 'cari':
        raise ValueError('Aksi pilihan tidak sah.')
    if data:
        raise ValueError('Field tidak dikenal.')
    _render(penangan, principal, peran=peran, pilihan=pilihan, cari=cari, halaman=halaman)
