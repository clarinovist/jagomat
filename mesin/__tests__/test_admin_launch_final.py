"""Regresi final panel layanan dengan penyimpanan dan provider sintetis."""

import sqlite3

import pytest
import admin_store
import admin_subscription
import auth
import product_analytics_http as analitik
import product_analytics_store as kpi
import subscription as domain
import subscription_store
from test_admin_http_c import server, _login, _minta, _hidden, SANDI_ADMIN
from test_subscription_http import FormParser
from test_subscription_store import ON, T0
from test_admin_launch_domain import layanan, aktif
from test_subscription_service import keluarga


def test_pencarian_langganan_berpaginasi_tanpa_nama_di_url(server):
    for nomor in range(26):
        nama = 'keluarga-cari-%02d' % nomor
        p = auth.tambah_akun_dan_principal(nama, 'sandi-uji-panjang', 'guru')
        subscription_store.enroll(admin_store.BAWAAN, p.id_akun,
            sumber_id='enroll_cari_%02d' % nomor, asal='publik', mulai=T0,
            peran='guru', sakelar=ON)
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    body = _minta(server, '/admin?section=langganan', cookie=token)[1]
    data = dict(csrf=_hidden(body, 'csrf'), cari='keluarga-cari', halaman='2')
    code, body, headers = _minta(server, '/admin/layanan/cari', cookie=token, data=data)
    assert code == 200
    assert 'Halaman 2' in body and 'Sebelumnya' in body
    assert body.count('href="/admin?section=langganan&amp;id=') == 1
    assert 'keluarga-cari' not in headers.get('Location', '')
    assert 'name="cari"' in body and 'name="halaman"' in body


def test_kegagalan_baca_config_menahan_kpi_hijau(layanan, monkeypatch):
    k = layanan
    aktif(k)
    monkeypatch.setattr(analitik, 'KOLEKSI_SIAP', True)
    monkeypatch.setattr(admin_store, 'BAWAAN', k.admin)
    baca = kpi.baca_config
    def gagal(*args):
        raise admin_store.StoreBelumSiap('gagal sintetis')
    monkeypatch.setattr(kpi, 'baca_config', gagal)
    assert not analitik.aktif()
    assert kpi.PENCATATAN_GAGAL
    monkeypatch.setattr(kpi, 'baca_config', baca)
    assert not kpi.laporan(k.admin, sekarang=T0, bulan='2026-09')[1].kualitas


def test_reader_sakelar_galat_sql_fail_closed(monkeypatch):
    def gagal(*args):
        raise sqlite3.OperationalError('gagal sintetis')
    monkeypatch.setattr(admin_store, 'buka_baca', gagal)
    assert admin_subscription.sakelar_runtime('sintetis') == domain.SAKELAR


def test_runtime_produksi_readiness_hilang_tidak_memberi_izin(layanan, monkeypatch):
    from types import SimpleNamespace
    from midtrans_contract import Konfigurasi
    k = layanan
    monkeypatch.setattr(admin_store, 'BAWAAN', k.admin)
    with admin_store._transaksi(k.admin) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap='rekonsiliasi'")
    r = admin_subscription.RuntimePembayaran(
        Konfigurasi('production', 'key-sintetis', 'M_SINTETIS'),
        lambda *a, **kw: pytest.fail('provider tidak boleh dipanggil'),
        domain.Sakelar(True,True,True,True),
        dict(provider_produksi=False,callback=False,recovery=False,kebijakan=False))
    p = SimpleNamespace(server=SimpleNamespace(pembayaran_runtime=r))
    assert admin_subscription.runtime_penangan(p).sakelar == domain.SAKELAR
