"""Saga registrasi orang tua+profil sintetis, tanpa enrollment/provider."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
import admin_registration as r
import admin_store
import auth
import database
import learning_profile


@pytest.fixture
def kasus(tmp_path):
    paths=(tmp_path/'admin.db',tmp_path/'auth.json',tmp_path/'belajar.db')
    admin_store.siapkan(paths[0]);database.siapkan(paths[2]);r.migrasikan_profil_registrasi(paths[2])
    auth.tambah_akun('admin-sintetis','sandi-admin-sintetis','admin',paths[1])
    kw=dict(operasi_id='registrasi_profil_001',alias='ortu-sintetis',sandi='sandi-sintetis',
            token_form='x'*64,sekarang=1800000000,nama_anak='Anak Sintetis',kelas_sekolah=4,profil_parameter='P4')
    return paths,kw


def daftar(kasus,**ubah):
    paths,kw=kasus
    return r.daftar_dengan_profil(*paths,**{**kw,**ubah})


def test_registrasi_profil_satu_pasangan_replay(kasus):
    paths,kw=kasus;a=daftar(kasus)
    assert a.baru and a.siswa_id
    awal=paths[1].read_bytes();b=daftar(kasus)
    assert b.id_akun==a.id_akun and b.siswa_id==a.siswa_id and not b.baru
    assert paths[1].read_bytes()==awal
    with database.buka(paths[2]) as c:
        row=c.execute('SELECT * FROM siswa').fetchone()
        assert row['nama']==kw['nama_anak'] and row['pemilik']==kw['alias'] and row['tingkat']=='P4'
        assert learning_profile.baca(c,a.siswa_id,pemilik=kw['alias']).kelas_sekolah==4
        assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==1
    receipt=json.loads(awal)['registrasi_profil']
    assert kw['nama_anak'] not in json.dumps(receipt) and kw['sandi'] not in json.dumps(receipt)
    with admin_store.buka_baca(paths[0]) as c:assert not c.execute('SELECT 1 FROM langganan_enrollment').fetchone()


@pytest.mark.parametrize('titik',['sebelum_intent','setelah_intent','setelah_db','setelah_auth'])
def test_crash_replay_tidak_yatim_atau_ganda(kasus,titik):
    paths,kw=kasus
    with pytest.raises(r.RegistrasiBelumSelesai):daftar(kasus,failpoint=titik)
    data=json.loads(paths[1].read_text())
    if titik!='setelah_auth':assert auth.cari_akun(kw['alias'],paths[1]) is None
    if titik in ('setelah_intent','setelah_db'):assert kw['operasi_id'] in data['registrasi_profil']
    a=daftar(kasus)
    assert a.siswa_id and auth.autentikasi(kw['alias'],kw['sandi'],paths[1])
    with database.buka(paths[2]) as c:assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==1


@pytest.mark.parametrize('ubah',[dict(nama_anak='Anak Lain'),dict(kelas_sekolah=5),dict(profil_parameter='P5'),dict(sandi='sandi-diubah')])
def test_binding_replay_berbeda_ditolak_tanpa_efek(kasus,ubah):
    paths,_=kasus;daftar(kasus);awal=paths[1].read_bytes()
    with pytest.raises(ValueError):daftar(kasus,**ubah)
    assert paths[1].read_bytes()==awal
    with database.buka(paths[2]) as c:assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==1


def test_pending_tidak_mengambil_profil_asing(kasus):
    paths,kw=kasus
    with pytest.raises(r.RegistrasiBelumSelesai):daftar(kasus,failpoint='setelah_db')
    with database.buka(paths[2]) as c:c.execute("UPDATE siswa SET pemilik='lain'")
    awal=paths[1].read_bytes()
    with pytest.raises(ValueError):daftar(kasus)
    assert paths[1].read_bytes()==awal and auth.cari_akun(kw['alias'],paths[1]) is None


def test_selesai_profil_dihapus_tidak_diciptakan_ulang(kasus):
    paths,_=kasus;a=daftar(kasus)
    with database.buka(paths[2]) as c:c.execute('DELETE FROM siswa WHERE id=?',(a.siswa_id,))
    with pytest.raises(ValueError):daftar(kasus)
    with database.buka(paths[2]) as c:assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==0


def test_profil_sama_tanpa_receipt_tidak_diambil_alih(kasus):
    paths,kw=kasus
    with pytest.raises(r.RegistrasiBelumSelesai):daftar(kasus,failpoint='setelah_intent')
    intent=json.loads(paths[1].read_text())['registrasi_profil'][kw['operasi_id']]
    with database.buka(paths[2]) as c:
        c.execute('INSERT INTO siswa(id,nama,tingkat,pemilik) VALUES(?,?,?,?)',
                  (intent['siswa_id'],kw['nama_anak'],kw['profil_parameter'],kw['alias']))
        learning_profile.simpan_kelas(c,intent['siswa_id'],kw['kelas_sekolah'],revisi=0,pemilik=kw['alias'])
    try:daftar(kasus)
    except ValueError:pass
    assert auth.cari_akun(kw['alias'],paths[1]) is None
    with database.buka(paths[2]) as c:assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==1


def test_pending_tidak_mewarisi_profil_nama_lain_dengan_alias_sama(kasus):
    paths,kw=kasus
    with pytest.raises(r.RegistrasiBelumSelesai):daftar(kasus,failpoint='setelah_intent')
    with database.buka(paths[2]) as c:database.tambah_siswa(c,'Profil Tak Terkait','P3',pemilik=kw['alias'])
    try:daftar(kasus)
    except ValueError:pass
    assert auth.cari_akun(kw['alias'],paths[1]) is None
    with database.buka(paths[2]) as c:assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==1


def test_retry_pending_id_dipakai_keluarga_lain_alokasikan_baru(kasus):
    paths,kw=kasus
    with pytest.raises(r.RegistrasiBelumSelesai):daftar(kasus,failpoint='setelah_intent')
    with database.buka(paths[2]) as c:asing=database.tambah_siswa(c,'Profil Asing','P3',pemilik='asing')
    a=daftar(kasus)
    assert a.siswa_id!=asing
    with database.buka(paths[2]) as c:
        assert c.execute('SELECT pemilik FROM siswa WHERE id=?',(asing,)).fetchone()[0]=='asing'
        assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==2


def test_gagal_commit_db_intent_dapat_pulih_tanpa_akun(kasus,monkeypatch):
    paths,kw=kasus;connect=sqlite3.connect
    class Koneksi(sqlite3.Connection):
        def commit(self):raise sqlite3.OperationalError('commit gagal sintetis')
    def gagal(*a,**k):
        if str(a[0]).startswith(paths[2].resolve().as_uri()):k['factory']=Koneksi
        return connect(*a,**k)
    with monkeypatch.context() as m:
        m.setattr(sqlite3,'connect',gagal)
        with pytest.raises(admin_store.StoreBelumSiap):daftar(kasus)
    assert auth.cari_akun(kw['alias'],paths[1]) is None
    with database.buka(paths[2]) as c:assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==0
    assert daftar(kasus).siswa_id


def test_receipt_db_immutable(kasus):
    paths,_=kasus;daftar(kasus)
    with database.buka(paths[2]) as c:
        for sql in ('DELETE FROM registrasi_profil_anak','UPDATE registrasi_profil_anak SET siswa_id=siswa_id',
                    'INSERT OR REPLACE INTO registrasi_profil_anak SELECT * FROM registrasi_profil_anak'):
            with pytest.raises(sqlite3.IntegrityError):c.execute(sql)


def test_schema_registrasi_optin_idempotent_parsial(tmp_path):
    path=tmp_path/'db';database.siapkan(path)
    with database.buka(path) as c:
        with pytest.raises(admin_store.StoreBelumSiap):r.validasi_schema_profil(c)
    r.migrasikan_profil_registrasi(path);r.migrasikan_profil_registrasi(path)
    with database.buka(path) as c:
        assert not c.execute('SELECT 1 FROM registrasi_profil_anak').fetchone()
        c.execute('DROP TRIGGER registrasi_profil_anak_tolak_update')
    with pytest.raises(admin_store.StoreBelumSiap):r.migrasikan_profil_registrasi(path)


def test_pending_hilang_setelah_commit_sequence_maju_ditolak(kasus):
    paths,kw=kasus
    with pytest.raises(r.RegistrasiBelumSelesai):daftar(kasus,failpoint='setelah_db')
    with database.buka(paths[2]) as c:c.execute('DELETE FROM siswa')
    with pytest.raises(ValueError):daftar(kasus)
    assert auth.cari_akun(kw['alias'],paths[1]) is None


def test_pending_alias_id_lain_tidak_mengambil_operasi(kasus):
    paths,kw=kasus
    with pytest.raises(r.RegistrasiBelumSelesai):daftar(kasus,failpoint='setelah_intent')
    awal=paths[1].read_bytes()
    with pytest.raises(ValueError):daftar(kasus,operasi_id='registrasi_profil_lain')
    assert paths[1].read_bytes()==awal
    assert daftar(kasus).siswa_id


def test_replay_auth_reset_tidak_menghidupkan_sesi(kasus):
    import sessions
    paths,kw=kasus;daftar(kasus)
    auth.simpan_sandi('sandi-reset-sintetis',kw['alias'],paths[1])
    a=daftar(kasus)
    assert a.revisi_auth==1
    assert sessions.buat_dari_principal(a,path=paths[1].parent/'sesi.json',path_akun=paths[1]) is None


def test_auth_replace_gagal_sesudah_write_dapat_direplay(kasus,monkeypatch):
    paths,kw=kasus;asli=auth._tulis_akun_atomik;calls=[]
    def tulis(*a,**kw):
        asli(*a,**kw);calls.append(1)
        if len(calls)==2:raise OSError('fsync sintetis')
    monkeypatch.setattr(auth,'_tulis_akun_atomik',tulis)
    with pytest.raises(OSError):daftar(kasus)
    assert daftar(kasus).siswa_id
    with database.buka(paths[2]) as c:assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==1


def test_publish_tidak_mewarisi_tambahan_profil_asing(kasus,monkeypatch):
    paths,kw=kasus;asli=r._gagal_registrasi
    def ubah(f,t):
        if t=='setelah_db':
            with database.buka(paths[2]) as c:database.tambah_siswa(c,'Profil Tambahan','P3',pemilik=kw['alias'])
        asli(f,t)
    monkeypatch.setattr(r,'_gagal_registrasi',ubah)
    with pytest.raises(ValueError):daftar(kasus)
    assert auth.cari_akun(kw['alias'],paths[1]) is None


def test_publish_recheck_menolak_owner_berubah_setelah_db(kasus,monkeypatch):
    paths,kw=kasus;asli=r._gagal_registrasi
    def ubah(f,t):
        if t=='setelah_db':
            with database.buka(paths[2]) as c:c.execute("UPDATE siswa SET pemilik='asing'")
        asli(f,t)
    monkeypatch.setattr(r,'_gagal_registrasi',ubah)
    with pytest.raises(ValueError):daftar(kasus)
    assert auth.cari_akun(kw['alias'],paths[1]) is None


def test_dua_request_sama_id_tepat_satu_pasangan(kasus):
    with ThreadPoolExecutor(max_workers=2) as pool:hasil=list(pool.map(lambda _:daftar(kasus),range(2)))
    assert hasil[0].id_akun==hasil[1].id_akun and hasil[0].siswa_id==hasil[1].siswa_id


def test_kelas_opsional_tidak_default_dan_variasi_wajib(kasus):
    paths,_=kasus
    with pytest.raises(ValueError):daftar(kasus,profil_parameter='')
    with pytest.raises(ValueError):daftar(kasus,nama_anak='')
    a=daftar(kasus,kelas_sekolah=None)
    with database.buka(paths[2]) as c:assert learning_profile.baca(c,a.siswa_id,pemilik='ortu-sintetis').kelas_sekolah is None
