"""Launcher preview sandbox dalam proses tersendiri dengan seluruh state baru.

Jalankan python mesin/subscription_preview.py, isi key secara tersembunyi. Jangan
pakai serve.py atau DB produksi. Direktori sintetis disimpan untuk rekonsiliasi;
launcher tidak menerima root/DB existing, dan tidak melanjutkan order otomatis.
"""

import getpass
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import tempfile
import time

import admin_registration
import admin_store
import auth
import database
import midtrans_contract as midtrans
import midtrans_sandbox
import sessions
import subscription_http
import subscription_service
import subscription_store


def siapkan(config, *, akar=None):
    """Hanya proses preview: set path global sebelum server mulai menerima request."""
    if type(config) is not midtrans.Konfigurasi or config.lingkungan != 'sandbox':
        raise ValueError('preview hanya sandbox')
    akar = Path(tempfile.mkdtemp(prefix='jagomat-sandbox-') if akar is None else akar).resolve()
    akar.mkdir(mode=0o700, parents=False, exist_ok=True)
    akar.chmod(0o700)
    if any(akar.iterdir()):
        raise ValueError('direktori preview harus baru dan kosong')
    path_admin, path_auth, path_db = (akar / 'admin-control.db', akar / 'sandi.json', akar / 'belajar.db')
    # Hindari semua default aplikasi/env pengguna; tidak membaca/membuat state nyata.
    os.environ['AI_BERKAS_DB'] = str(akar / 'ai-control.db')
    os.environ['ADMIN_TRANSIENT_DB'] = str(akar / 'admin-drafts.db')
    admin_store.BAWAAN, auth.BERKAS_SANDI, database.BAWAAN = path_admin, path_auth, path_db
    sessions.BERKAS_SESI = akar / 'sesi.json'
    kini = int(time.time())
    admin_store.siapkan(path_admin, sekarang=kini)
    database.siapkan(path_db)
    sandi = secrets.token_urlsafe(18)
    operasi = 'daftar_' + secrets.token_hex(16)
    on = subscription_http.ON
    subscription_store.buat_kampanye(path_admin, 'preview_sintetis', mulai=kini, sakelar=on)
    admin_registration.daftar_publik(path_admin, path_auth, path_db, operasi_id=operasi,
        alias='ortu-sandbox', sandi=sandi, token_form=secrets.token_hex(32), sekarang=kini)
    p = auth.autentikasi('ortu-sandbox', sandi, path_auth)
    with database.buka(path_db) as kon:
        database.tambah_siswa(kon, 'Profil Sintetis A', 'P3', pemilik=p.pengguna)
        database.tambah_siswa(kon, 'Profil Sintetis B', 'P4', pemilik=p.pengguna)
    subscription_service.sinkron_pendaftaran(path_admin, path_auth, path_db, p,
        sumber_id=operasi, cutoff=kini, sekarang=kini, sakelar=on)
    # Identitas hanya untuk login preview, bukan key merchant; berkas mode600.
    fd = os.open(str(akar / 'login-sintetis.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump({'pengguna': p.pengguna, 'sandi': sandi}, f)
    transport = midtrans_sandbox.TransportSandbox(config)
    from web import Penangan
    class PenanganPreview(Penangan):
        def log_message(self, *args):
            pass  # URL invoice dan isi request tidak dicatat.
    server = ThreadingHTTPServer(('127.0.0.1', 0), PenanganPreview)
    server.langganan_sandbox = subscription_http.RuntimeSandbox(akar, config, transport, transport.gambar)
    return server, akar


def utama():
    try:
        merchant = getpass.getpass('Merchant ID sandbox (disembunyikan): ')
        key = getpass.getpass('Server Key sandbox (disembunyikan): ')
        server, akar = siapkan(midtrans.Konfigurasi('sandbox', key, merchant))
        print('Preview sintetis: http://127.0.0.1:%d/masuk' % server.server_address[1])
        print('Login sintetis dan state privat:', akar)
        print('Hanya simulator resmi, jangan bayar memakai saldo nyata. Ctrl-C untuk berhenti.')
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    except Exception:
        print('Preview gagal; detail kredensial tidak ditampilkan.')
        return 1


if __name__ == '__main__':
    raise SystemExit(utama())
