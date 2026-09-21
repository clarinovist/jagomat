"""Transport dan tinjauan bertanda tangan khusus panel admin.

Bukan pengganti principal/otorisasi domain: caller wajib memakai akun mutakhir
pada setiap mint/verifikasi dan memverifikasi sandi admin untuk mutasi sensitif.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from urllib.parse import parse_qs, urlsplit

BATAS_FORM = 8192
UMUR_TINJAUAN = 900


def _asal_sama(headers):
    if any(len(headers.get_all(nama, [])) > 1 for nama in ('Origin', 'Host', 'Sec-Fetch-Site')):
        raise PermissionError('Asal permintaan ambigu.')
    asal = headers.get('Origin')
    situs = headers.get('Sec-Fetch-Site', '')
    if situs == 'cross-site':
        raise PermissionError('Permintaan lintas situs ditolak.')
    # Form native Chromium dengan Referrer-Policy:no-referrer dapat membawa
    # Origin:null. Hanya terima jika Fetch Metadata memastikan same-origin;
    # caller tetap wajib memverifikasi token signed, bukan mempercayai null.
    if asal == 'null' and situs == 'same-origin':
        return
    if asal:
        try:
            parsed = urlsplit(asal)
            host = urlsplit('//' + headers.get('Host', ''))
            cocok = (parsed.scheme in ('http', 'https') and parsed.hostname
                     and parsed.hostname == host.hostname
                     and parsed.port == host.port and not parsed.username
                     and not parsed.password and not parsed.query
                     and not parsed.fragment and parsed.path in ('', '/'))
        except ValueError:
            cocok = False
        if not cocok:
            raise PermissionError('Permintaan lintas situs ditolak.')


def baca_form(penangan, *, batas=BATAS_FORM, maksimum_field=32, berulang=()):
    """Baca form scalar terbatas; payload ambigu ditolak sebelum domain write."""
    headers = penangan.headers
    _asal_sama(headers)
    if headers.get('Transfer-Encoding'):
        raise ValueError('Format isian tidak sah.')
    panjang_semua = headers.get_all('Content-Length', [])
    panjang = panjang_semua[0] if len(panjang_semua) == 1 else ''
    if not panjang.isascii() or not panjang.isdigit() or not 0 < int(panjang) <= batas:
        raise ValueError('Ukuran isian tidak sah.')
    if (len(headers.get_all('Content-Type', [])) != 1
            or headers.get_content_type() != 'application/x-www-form-urlencoded'):
        raise ValueError('Format isian tidak sah.')
    raw = penangan.rfile.read(int(panjang))
    if len(raw) != int(panjang):
        raise ValueError('Isian tidak lengkap.')
    try:
        teks = raw.decode('utf-8', 'strict')
        if re.search(r'%(?![0-9a-fA-F]{2})', teks):
            raise ValueError('Encoding tidak sah.')
        parsed = parse_qs(teks, keep_blank_values=True, strict_parsing=True,
                          max_num_fields=maksimum_field, encoding='utf-8', errors='strict')
    except (UnicodeError, ValueError):
        raise ValueError('Format isian tidak sah.') from None
    if any(len(v) != 1 for k, v in parsed.items() if k not in berulang):
        raise ValueError('Isian ganda ditolak.')
    return {k: v if k in berulang else v[0] for k, v in parsed.items()}


def _kunci(akun):
    if akun.get('peran') != 'admin' or not isinstance(akun.get('id_akun'), str):
        raise PermissionError('Tinjauan tidak sah.')
    revisi = akun.get('revisi_auth', 0)
    if type(revisi) is not int or revisi < 0:
        raise PermissionError('Tinjauan tidak sah.')
    try:
        bahan = bytes.fromhex(akun['kunci'])
        if len(bahan) < 32:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise PermissionError('Tinjauan tidak sah.') from None
    return hmac.new(bahan, b'jagomat-admin-review-v1', hashlib.sha256).digest()


def _ikat(akun, token_sesi):
    ident = '%s:%d' % (akun['id_akun'], akun.get('revisi_auth', 0))
    return hashlib.sha256((ident + ':' + ('cookie:' + token_sesi if token_sesi else 'basic')).encode()).hexdigest()


def _encode(data):
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def buat_tinjauan(akun, token_sesi, aksi, payload=None, *, sekarang=None,
                   operasi_id=None):
    """Tandatangani metadata nonrahasia; token hanya berada di form, bukan URL."""
    isi = dict(payload or {})
    if set(isi) - {'target_id', 'target_revisi', 'target_peran', 'siswa_id', 'tingkat', 'revisi', 'batch_id', 'section', 'pilihan', 'halaman', 'item_ids', 'login_id', 'login_revisi', 'revisi_profil'}:
        raise ValueError('Metadata tinjauan tidak dikenal.')
    if not isinstance(aksi, str) or not re.fullmatch(r'[a-z_]{1,64}', aksi):
        raise ValueError('Aksi tinjauan tidak sah.')
    if any(type(v) not in (str, int) for k, v in isi.items() if k != 'pilihan'):
        raise ValueError('Metadata tinjauan tidak sah.')
    if 'pilihan' in isi:
        pilihan = isi['pilihan']
        if (type(pilihan) is not list or len(pilihan) > 100
                or any(type(x) is not list or len(x) != 3
                       or type(x[0]) is not str or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}', x[0])
                       or type(x[1]) is not int or x[1] < 0
                       or x[2] not in ('guru', 'murid') for x in pilihan)):
            raise ValueError('Pilihan tidak sah.')
    if operasi_id is not None and (
        type(operasi_id) is not str
        or re.fullmatch(r'op_[0-9a-f]{32}', operasi_id) is None
    ):
        raise ValueError('ID operasi tinjauan tidak sah.')
    kini = int(time.time()) if sekarang is None else sekarang
    data = {'v': 1, 'aksi': aksi, 'data': isi,
            'op': operasi_id or 'op_' + secrets.token_hex(16),
            'exp': kini + UMUR_TINJAUAN, 'ikat': _ikat(akun, token_sesi)}
    tubuh = _encode(json.dumps(data, separators=(',', ':'), sort_keys=True).encode())
    return tubuh + '.' + _encode(hmac.new(_kunci(akun), tubuh.encode(), hashlib.sha256).digest())


def periksa_tinjauan(akun, token_sesi, token, *, sekarang=None):
    """Verifikasi signature, expiry dan ikatan sesi/principal tanpa tulis state."""
    try:
        if not isinstance(token, str) or len(token) > 32768:
            raise ValueError()
        tubuh, signature = token.split('.')
        harap = _encode(hmac.new(_kunci(akun), tubuh.encode('ascii'), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, harap):
            raise ValueError()
        data = json.loads(base64.b64decode(tubuh + '=' * (-len(tubuh) % 4), altchars=b'-_', validate=True))
        kini = int(time.time()) if sekarang is None else sekarang
        if (set(data) != {'v', 'aksi', 'data', 'op', 'exp', 'ikat'} or data['v'] != 1
                or type(data['exp']) is not int or not kini < data['exp'] <= kini + UMUR_TINJAUAN
                or data['ikat'] != _ikat(akun, token_sesi)):
            raise ValueError()
        return data
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise PermissionError('Form kedaluwarsa atau tidak sah. Buka ulang tinjauan.') from None


def header_privat(*, skrip_sandi=''):
    """CSP tanpa aset eksternal; hanya script mata-sandi yang diberikan source."""
    script = "'none'"
    if skrip_sandi:
        script = "'sha256-%s'" % base64.b64encode(hashlib.sha256(skrip_sandi.encode()).digest()).decode()
    return {
        'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
        'X-Robots-Tag': 'noindex, nofollow', 'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; script-src %s; form-action 'self'; base-uri 'none'; frame-ancestors 'none'" % script,
    }
