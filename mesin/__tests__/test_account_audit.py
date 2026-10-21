"""Regresi audit akun memakai profil dan pilihan data sintetis saja."""
import base64
import hashlib
import re
from types import SimpleNamespace

import pytest
import account_pages
import auth
import database
import policy_store
import sensor_http
from test_akun import siap


def halaman(kon, section='siswa'):
    return account_pages.halaman_akun(kon, pengguna='guru', section=section).decode()


def test_hapus_riwayat_nonaktif_dan_login_terlihat(siap):
    with database.buka(siap) as kon:
        sid = database.tambah_siswa(kon, 'Demo', pemilik='guru')
        auth.tambah_akun('demo-login', 'sandi-sintetis-123', 'murid', siswa_id=sid)
        database.buat_sesi(kon, sid, seed=1)
        h = halaman(kon)
    assert 'Punya 1 sesi latihan; tidak bisa dihapus.' in h
    assert re.search(r'<button[^>]*disabled[^>]*>Hapus Demo</button>', h)
    assert 'Login: demo-login' in h
    assert 'id="perbaikan-login"' not in h


def test_hapus_receipt_nonaktif(siap):
    import admin_registration
    admin_registration.migrasikan_profil_registrasi(siap)
    with database.buka(siap) as kon:
        sid = database.tambah_siswa(kon, 'Receipt', pemilik='guru')
        kon.execute('INSERT INTO registrasi_profil_anak VALUES(?,?,?,?,?,?)',
                    ('operasi_audit_receipt', 'akun_' + 'c' * 32, sid, 'a' * 64, 'b' * 64, 5))
        h = halaman(kon)
    assert 'Profil pendaftaran dilindungi; tidak bisa dihapus di sini.' in h
    assert re.search(r'<button[^>]*disabled[^>]*>Hapus Receipt</button>', h)


def test_tombol_hapus_tidak_aktif_bila_ada_alasan(siap):
    with database.buka(siap) as kon:
        sid = database.tambah_siswa(kon, 'Terlindungi', pemilik='guru')
        database.buat_sesi(kon, sid, seed=1)
        h = halaman(kon)
    assert re.search(r'<button[^>]*disabled[^>]*>Hapus Terlindungi</button>', h)
    assert 'value="siswa_hapus"' not in h


def test_konfirmasi_nama_di_escape_bukan_handler_inline(siap):
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, 'Demo " & <uji>', pemilik='guru')
        h = halaman(kon)
    assert 'data-konfirmasi="Hapus anak Demo &quot; &amp; &lt;uji&gt;' in h
    assert 'onsubmit=' not in h
    assert '>Hapus Demo &quot; &amp; &lt;uji&gt;</button>' in h


def test_copy_dan_form_akun(siap):
    with database.buka(siap) as kon:
        h = halaman(kon)
        akun = halaman(kon, 'akun')
    assert 'boleh sama polanya' not in h
    assert 'berbeda dari kata sandi orang tua' in h
    assert 'Rp10.000' not in h
    assert '<h2>Daftar anak</h2>' in h
    assert 'Pilih kelas (opsional)' in h
    assert 'target="_blank" rel="noopener"' in h
    assert 'name="persetujuan_ortu"' not in h
    assert 'persetujuan awal' in h
    assert 'Menambah anak tidak mengubah pilihan penggunaan data tambahan' in h
    assert 'class="tombol-utama-akun">Buat anak' in h
    assert '/lupa-sandi' in akun
    assert 'autocomplete="current-password"' in akun
    assert 'minlength="12"' in akun


def test_semua_tab_akun_tanpa_font_eksternal_dengan_skrip_terbatas(siap):
    from teacher_style import SKRIP_MATA_SANDI
    with database.buka(siap) as kon:
        for section in ('akun', 'siswa', 'langganan'):
            h = halaman(kon, section)
            assert 'fonts.googleapis.com' not in h
            assert SKRIP_MATA_SANDI in h
            assert 'window.confirm(' in h
            assert len(re.findall(r'<script>', h)) == 1


@pytest.mark.parametrize('pilihan,aktif,expected', [
    ((1, 0, 1), True, 'Penggunaan tambahan aktif'),
    ((1, 0, 1), False, 'Penggunaan tambahan tidak aktif'),
    ((0, 0, 0), False, 'Penggunaan tambahan tidak diizinkan'),
])
def test_status_pilihan_dan_izin_efektif(monkeypatch, pilihan, aktif, expected):
    row = dict(alur=pilihan[0], hasil=pilihan[1], chat=pilihan[2], dibuat=1700000000)
    monkeypatch.setattr('policy_http.tersedia', lambda: True)
    monkeypatch.setattr(policy_store, 'baca', lambda *a: row)
    monkeypatch.setattr(policy_store, 'berlaku', lambda r: True)
    monkeypatch.setattr('product_analytics_http._token', lambda *a: 'token-sintetis')
    monkeypatch.setattr(sensor_http, 'izin_akun', lambda *a: SimpleNamespace(berakhir=1800000000) if aktif else None)
    p = SimpleNamespace(_principal=lambda: SimpleNamespace(id_akun='sintetis'), _ambil_token=lambda: 'sintetis')
    h = sensor_http.form_akun(p)
    assert expected in h
    assert 'Ringkasan hasil belajar: tidak diizinkan' in h
    assert 'Tanggal persetujuan terakhir:' in h
    assert 'Tanggal pencabutan' not in h
    assert 'class="kartu-st' in h
    assert 'class="tombol-bahaya-akun"' in h
    assert 'data-konfirmasi=' in h
    assert 'Data belajar dan percakapan asli tetap ada' in h


def test_csp_akun_hanya_hash_skrip_statis(siap):
    import account_http
    with database.buka(siap) as kon:
        body = halaman(kon, 'akun').encode()
    headers = {}
    from io import BytesIO
    p = SimpleNamespace(send_response=lambda code: None, send_header=headers.__setitem__,
                        end_headers=lambda: None, wfile=BytesIO())
    account_http._kirim_akun(p, body)
    script = re.search(rb'<script>(.*?)</script>', body, re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(script).digest()).decode()
    csp = headers['Content-Security-Policy']
    assert "script-src 'sha256-" + digest + "'" in csp
    assert "default-src 'none'" in csp
    assert 'https:' not in csp
    assert headers['Cache-Control'] == 'no-store'
    assert p.wfile.getvalue() == body


def test_tambah_anak_tidak_mengklaim_receipt_checkbox_lama(siap):
    with database.buka(siap) as kon:
        pesan, galat = account_pages.proses_akun(kon, dict(
            aksi='anak_baru', nama='Contoh', sandi_anak='sandi-contoh-123',
            persetujuan_ortu='1'), 'guru')
    assert not galat
    assert 'persetujuan orang tua dicatat' not in pesan
    assert 'Beranda' in pesan


def test_enhancement_hanya_lokal_dan_fallback_native(siap):
    from account_browser import SKRIP_AKUN
    with database.buka(siap) as kon:
        h = halaman(kon)
    assert 'novalidate' not in h.split('<script>', 1)[0].lower()
    assert 'f.noValidate=true' in SKRIP_AKUN
    assert "Perubahan kelas belum disimpan." in SKRIP_AKUN
    assert 'fetch(' not in SKRIP_AKUN
    assert 'XMLHttpRequest' not in SKRIP_AKUN


def test_langganan_nonaktif_menampilkan_profil_sendiri(siap, monkeypatch):
    import account_http
    import subscription
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, 'Sendiri', pemilik='guru')
        database.tambah_siswa(kon, 'Bukan milik', pemilik='lain')
    monkeypatch.setattr('subscription_produksi_http.ada', lambda p: True)
    def nonaktif(p):
        raise subscription.FiturNonaktif()
    monkeypatch.setattr('subscription_produksi_http._runtime', nonaktif)
    h = account_http._fragmen_langganan(None, ('guru', 'guru'))
    assert 'Profil anak yang digunakan: <b>1</b>' in h
    assert 'Tidak ada penagihan baru' in h
    assert 'Bukan milik' not in h


def test_kontras_teks_akun_memenuhi_empat_setengah():
    import design_tokens as T
    def luminansi(warna):
        warna = warna.lstrip('#')
        if len(warna) == 3:
            warna = ''.join(x * 2 for x in warna)
        rgb = [int(warna[i:i+2], 16) / 255 for i in (0, 2, 4)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
        return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))
    for depan, belakang in ((T.TEKS_VARIAN, T.LATAR_KARTU),
                            (T.TEKS_GALAT, T.LATAR_GALAT),
                            (T.TEKS_PUTIH, T.AKSEN_TEAL_TUA)):
        a, b = sorted((luminansi(depan), luminansi(belakang)))
        assert (b + .05) / (a + .05) >= 4.5
