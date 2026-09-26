"""Registrasi terisolasi: auth committed bukan bukti enrollment berhasil."""
import pytest
import admin_store
import auth
import database
import subscription as d
import subscription_registration as r
import subscription_service as s
import subscription_store as st
from test_subscription_store import ON, T0


@pytest.fixture
def baru(tmp_path):
    args=(tmp_path/'admin.db',tmp_path/'sandi.json',tmp_path/'belajar.db')
    admin_store.siapkan(args[0],sekarang=T0)
    database.siapkan(args[2])
    kw=dict(operasi_id='daftar_wrapper_001',alias='keluarga-wrapper',sandi='sandi-sintetis-wrapper',
            token_form='x'*64,cutoff=T0,sekarang=T0,sakelar=ON)
    return args,kw


def test_registrasi_dan_sinkron_replay(baru):
    args,kw=baru
    hasil=r.daftar(*args,**kw)
    assert hasil.status_langganan=='tersinkron'
    awal=args[1].read_bytes()
    ulang=r.daftar(*args,**{**kw,'sekarang':T0+1})
    assert ulang.akun.id_akun==hasil.akun.id_akun
    assert args[1].read_bytes()==awal
    assert st.baca(args[0],hasil.akun.id_akun).enrollment.mulai==T0


def test_crash_setelah_auth_recovery_sinkron_service(baru):
    args,kw=baru
    with pytest.raises(s.SinkronBelumSelesai): r.daftar(*args,**kw,failpoint='setelah_auth')
    principal=auth.autentikasi(kw['alias'],kw['sandi'],args[1])
    assert principal
    awal=args[1].read_bytes()
    e=s.sinkron_pendaftaran(*args,principal,sumber_id=kw['operasi_id'],cutoff=T0,sekarang=T0+1,sakelar=ON)
    assert e.mulai==T0 and args[1].read_bytes()==awal


def test_sink_gagal_tidak_menghapus_akun_atau_mengaku_trial(baru,monkeypatch):
    args,kw=baru
    def gagal(*a,**kw): raise admin_store.StoreBelumSiap('sink sintetis')
    asli=s.sinkron_pendaftaran
    monkeypatch.setattr(s,'sinkron_pendaftaran',gagal)
    hasil=r.daftar(*args,**kw)
    assert hasil.status_langganan=='belum_terverifikasi'
    assert auth.autentikasi(kw['alias'],kw['sandi'],args[1])
    monkeypatch.setattr(s,'sinkron_pendaftaran',asli)
    assert r.daftar(*args,**{**kw,'sekarang':T0+1}).status_langganan=='tersinkron'


def test_off_sebelum_akun_dibuat(tmp_path):
    with pytest.raises(d.FiturNonaktif):
        r.daftar(tmp_path/'admin',tmp_path/'auth',tmp_path/'db',operasi_id='daftar_off',alias='sintetis',
                 sandi='sandi-sintetis',token_form='x'*64,cutoff=T0,sekarang=T0)
    assert list(tmp_path.iterdir())==[]


def _daftar_web(args,kw,monkeypatch,*,cutoff,sakelar=None):
    monkeypatch.setattr(r,'CUTOFF_AKTIVASI',cutoff)
    return r.daftar_web(args[0],args[1],args[2],operasi_id=kw['operasi_id'],
                        alias=kw['alias'],sandi=kw['sandi'],token_form=kw['token_form'],
                        sekarang=kw['sekarang'],sakelar=sakelar)


def test_daftar_web_tanpa_aktivasi_tetap_mendaftar_tanpa_enrollment(baru,monkeypatch):
    args,kw=baru
    hasil=_daftar_web(args,kw,monkeypatch,cutoff=None,sakelar=ON)
    assert hasil.status_langganan=='belum_aktif'
    assert auth.autentikasi(kw['alias'],kw['sandi'],args[1])
    with admin_store.buka_baca(args[0]) as kon:
        assert not kon.execute('SELECT 1 FROM langganan_enrollment').fetchone()


def test_daftar_web_aktif_mensinkron_lewat_cutoff(baru,monkeypatch):
    args,kw=baru
    hasil=_daftar_web(args,kw,monkeypatch,cutoff=T0,sakelar=ON)
    assert hasil.status_langganan=='tersinkron','aktivasi publik'
    e=st.baca(args[0],hasil.akun.id_akun).enrollment
    assert e.mulai==T0
    with admin_store.buka_baca(args[0]) as kon:
        baris=kon.execute('SELECT asal FROM langganan_enrollment WHERE akun_id=?',
                          (hasil.akun.id_akun,)).fetchone()
        assert baris['asal']=='publik'


def test_daftar_web_aktif_tanpa_sakelar_efektif_tetap_mendaftar(baru,monkeypatch):
    args,kw=baru
    hasil=_daftar_web(args,kw,monkeypatch,cutoff=T0)
    assert hasil.status_langganan=='belum_aktif'
    assert auth.autentikasi(kw['alias'],kw['sandi'],args[1])
    with admin_store.buka_baca(args[0]) as kon:
        assert not kon.execute('SELECT 1 FROM langganan_enrollment').fetchone()
