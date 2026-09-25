"""Checkout sandbox opt-in pada server preview loopback, bukan aktivasi produksi."""

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit

import admin_security
import admin_store
import auth
import database
import midtrans_contract as midtrans
import sessions
import subscription as d
import subscription_checkout as checkout
import subscription_pages as halaman
import subscription_service as layanan
import subscription_store as store

POLA = re.compile(r"/langganan/(inv_[0-9a-f]{32})(?:/(buat|periksa|qr))?\Z")
ON = d.Sakelar(True, True, True, False)


@dataclass(repr=False)
class RuntimeSandbox:
    """Dibuat launcher sintetis; server biasa tidak mempunyai runtime ini."""
    akar: Path
    config: midtrans.Konfigurasi = field(repr=False)
    transport: object = field(repr=False)
    gambar: object = field(repr=False)
    kunci: bytes = field(default_factory=lambda: secrets.token_bytes(32), repr=False)
    kunci_kerja: object = field(default_factory=threading.Lock, repr=False)
    permintaan: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        if self.config.lingkungan != "sandbox" or not callable(self.transport) or not callable(self.gambar):
            raise ValueError("runtime hanya sandbox")
        self.akar = Path(self.akar).resolve()

    def paths(self):
        return (self.akar / 'admin-control.db', self.akar / 'sandi.json', self.akar / 'belajar.db')


def runtime(penangan):
    r = getattr(penangan.server, 'langganan_sandbox', None)
    if not isinstance(r, RuntimeSandbox):
        return None
    if penangan.server.server_address[0] not in ('127.0.0.1', '::1'):
        return None
    harap = r.paths()
    aktual = (admin_store.BAWAAN, auth.BERKAS_SANDI, database.BAWAAN)
    if tuple(Path(p).resolve() for p in aktual) != harap:
        return None
    if Path(sessions.BERKAS_SESI).resolve() != r.akar / 'sesi.json':
        return None
    return r


def _principal(penangan, r):
    token = penangan._ambil_token()
    p = sessions.ambil_principal(token, path=r.akar / 'sesi.json', path_akun=r.akar / 'sandi.json')
    if p is None or p.peran != 'guru':
        raise LookupError('resource tidak ditemukan')
    return auth.PrincipalAkun(p.pengguna, p.peran, p.id_akun, p.revisi_auth)


def _recheck(penangan, r, principal):
    if _principal(penangan, r) != principal:
        raise LookupError('resource tidak ditemukan')


def _token(r, sesi, principal, aksi, invoice='', *, sekarang=None):
    kini = int(time.time()) if sekarang is None else sekarang
    isi = {'aksi': aksi, 'invoice': invoice, 'op': secrets.token_hex(16), 'exp': kini + 900}
    tubuh = json.dumps(isi, sort_keys=True, separators=(',', ':')).encode().hex()
    ikat = ':'.join((sesi, principal.id_akun, str(principal.revisi_auth), tubuh))
    return tubuh + '.' + hmac.new(r.kunci, ikat.encode(), hashlib.sha256).hexdigest()


def _periksa_token(r, sesi, principal, token, aksi, invoice='', *, sekarang=None):
    try:
        if type(token) is not str or len(token) > 1024:
            raise ValueError()
        tubuh, signature = token.split('.')
        ikat = ':'.join((sesi, principal.id_akun, str(principal.revisi_auth), tubuh))
        harap = hmac.new(r.kunci, ikat.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, harap):
            raise ValueError()
        data = json.loads(bytes.fromhex(tubuh))
        kini = int(time.time()) if sekarang is None else sekarang
        if (set(data) != {'aksi', 'invoice', 'op', 'exp'} or data['aksi'] != aksi
                or data['invoice'] != invoice or type(data['exp']) is not int
                or not kini < data['exp'] <= kini + 900
                or type(data['op']) is not str or re.fullmatch(r'[0-9a-f]{32}', data['op']) is None):
            raise ValueError()
        return data
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise PermissionError('form tidak sah') from None


def _kirim(penangan, isi, kode=200, *, png=False, lokasi=None):
    penangan.send_response(kode)
    for k, v in admin_security.header_privat().items():
        penangan.send_header(k, v)
    penangan.send_header('X-Content-Type-Options', 'nosniff')
    penangan.send_header('Content-Type', 'image/png' if png else 'text/html; charset=utf-8')
    if lokasi:
        penangan.send_header('Location', lokasi)
    penangan.send_header('Content-Length', str(len(isi)))
    penangan.end_headers()
    penangan.wfile.write(isi)


def _tidak_ada(penangan):
    # Identik, tanpa identitas/nama pengguna atau status invoice.
    _kirim(penangan, halaman.bingkai('<section class="kartu"><h2>Halaman tidak ada</h2></section>'), 404)


def _transport(penangan, r, principal):
    @contextmanager
    def kirim(req, **kw):
        _recheck(penangan, r, principal)
        with r.transport(req, **kw) as respons:
            yield respons
        _recheck(penangan, r, principal)
    return kirim


def _status(penangan, r, principal, inv):
    hasil = midtrans.Hasil()
    if inv['create_dicoba'] and inv['status'] != 'lunas':
        hasil = midtrans.periksa_status(r.config, inv, akun_id=principal.id_akun,
                    transport=_transport(penangan, r, principal), sakelar=ON)
    _recheck(penangan, r, principal)
    inv = checkout.baca_tagihan(*r.paths(), principal, inv['invoice_id'], sakelar=ON)
    return inv, hasil


def _tangani(penangan, jalur, *, post):
    if jalur != '/langganan' and not jalur.startswith('/langganan/'):
        return False
    r = runtime(penangan)
    if r is None:
        _tidak_ada(penangan)
        return True
    terkunci = False
    try:
        p = _principal(penangan, r)
        cocok = POLA.fullmatch(jalur)
        if urlsplit(penangan.path).query or (jalur not in ('/langganan', '/langganan/siapkan') and not cocok):
            raise LookupError()
        # Serial hanya preview: bounded laju/global sebelum jaringan, tanpa antrean.
        terkunci = r.kunci_kerja.acquire(blocking=False)
        if not terkunci:
            _kirim(penangan, halaman.bingkai('<p role="alert">Permintaan lain sedang diproses. Coba lagi sebentar.</p>'), 429)
            return True
        kini = int(time.time())
        args = (*r.paths(), p)
        if post:
            try:
                host = urlsplit('//' + str(penangan.headers.get('Host', ''))).hostname
            except ValueError:
                host = None
            if not penangan._di_https() and host not in ('127.0.0.1', 'localhost', '::1'):
                raise PermissionError('transport tidak aman')
            if jalur == '/langganan/siapkan':
                aksi, invoice = 'siapkan', ''
            elif cocok and cocok.group(2) in ('buat', 'periksa'):
                invoice, aksi = cocok.groups()
                checkout.baca_tagihan(*args, invoice, sakelar=ON)
            else:
                raise LookupError()
            data = admin_security.baca_form(penangan, berulang=('profil',), maksimum_field=34)
            if set(data) != ({'token', 'profil'} if aksi == 'siapkan' else {'token'}):
                raise ValueError()
            token = _periksa_token(r, penangan._ambil_token(), p, data['token'], aksi, invoice)
            profil = None
            if aksi == 'siapkan':
                if any(re.fullmatch(r'[1-9][0-9]{0,18}', n) is None for n in data['profil']):
                    raise ValueError()
                profil = tuple(int(n) for n in data['profil'])
                if not 1 <= len(profil) <= 3:
                    raise ValueError()
                d.profil_kanonis(profil)
            _limiti(r)
            if aksi == 'siapkan':
                inv = checkout.siapkan_tagihan(*args, profil, invoice_id='inv_' + token['op'],
                    operasi_id='op_' + token['op'], merchant=r.config.merchant, sekarang=kini,
                    kedaluwarsa=kini + 86400, sakelar=ON)
                invoice = inv['invoice_id']
            else:
                fungsi = layanan.mulai_pembayaran if aksi == 'buat' else layanan.periksa_pembayaran
                fungsi(*args, invoice, config=r.config, transport=_transport(penangan, r, p),
                       sekarang=kini, sakelar=ON, cek_sesi=lambda: _recheck(penangan, r, p))
            _recheck(penangan, r, p)
            _kirim(penangan, b'', 303, lokasi='/langganan/' + invoice)
        elif jalur == '/langganan':
            _, profil, inv = checkout.ringkasan(*args, sakelar=ON)
            token = _token(r, penangan._ambil_token(), p, 'siapkan')
            _kirim(penangan, halaman.ringkasan(p.pengguna, profil, inv, token))
        elif cocok and cocok.group(2) in (None, 'qr'):
            invoice, aksi = cocok.groups()
            inv = checkout.baca_tagihan(*args, invoice, sakelar=ON)
            _limiti(r)
            inv, hasil = _status(penangan, r, p, inv)
            if aksi == 'qr':
                if hasil.status != 'pending' or not hasil.qr or inv['perlu_diperiksa'] or inv['status'] == 'lunas':
                    raise LookupError()
                gambar = r.gambar(hasil.qr)
                _recheck(penangan, r, p)
                checkout.baca_tagihan(*args, invoice, sakelar=ON)
                _kirim(penangan, gambar, png=True)
            else:
                boleh_buat = not inv['create_dicoba'] and inv['status'] != 'lunas' and kini < inv['kedaluwarsa']
                token = _token(r, penangan._ambil_token(), p, 'buat' if boleh_buat else 'periksa', invoice)
                status = ('perlu_diperiksa' if inv['perlu_diperiksa'] else
                          ('lunas' if inv['status'] == 'lunas' else
                           ('settlement_terdeteksi' if hasil.status == 'lunas' else hasil.status)))
                _kirim(penangan, halaman.tagihan(p.pengguna, inv, token=token, status=status,
                    boleh_buat=boleh_buat, qr_url=hasil.qr if hasil.status == 'pending' else ''))
        else:
            raise LookupError()
    except LookupError:
        _tidak_ada(penangan)
    except PermissionError as galat:
        pesan = ('Terlalu banyak permintaan. Coba lagi sebentar.' if str(galat) == 'batas laju'
                 else 'Form tidak sah atau kedaluwarsa. Buka ulang halaman.')
        _kirim(penangan, halaman.bingkai('<p role="alert">' + pesan + '</p>'),
               429 if str(galat) == 'batas laju' else 403)
    except store.KonflikLangganan:
        _kirim(penangan, halaman.bingkai('<p role="alert">Tagihan sudah dibekukan atau berubah. <a href="/langganan">Buka tagihan yang ada</a>.</p>'), 409)
    except midtrans.KontrakTidakSah:
        _kirim(penangan, halaman.bingkai('<p role="alert">QR sementara tidak tersedia. Periksa tagihan yang sama nanti.</p>'), 503)
    except (ValueError, TypeError):
        _kirim(penangan, halaman.bingkai('<p role="alert">Isian tidak sah. Muat ulang dan pilih profil.</p>'), 400)
    except (admin_store.StoreBelumSiap, sqlite3.Error, OSError, RuntimeError):
        _kirim(penangan, halaman.bingkai('<p role="alert">Pembayaran sementara belum terverifikasi. Periksa tagihan yang sama nanti.</p>'), 503)
    finally:
        if terkunci:
            r.kunci_kerja.release()
    return True


def _limiti(r):
    kini = time.monotonic()
    r.permintaan[:] = [t for t in r.permintaan if kini - t < 60]
    if len(r.permintaan) >= 30:
        raise PermissionError('batas laju')
    r.permintaan.append(kini)


def tangani_get(penangan, jalur):
    return _tangani(penangan, jalur, post=False)


def tangani_post(penangan, jalur):
    return _tangani(penangan, jalur, post=True)
