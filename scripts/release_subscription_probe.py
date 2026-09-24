"""Probe ledger admin6 untuk image network-none; tidak membaca data host."""

SUMBER_UJI_LANGGANAN = r'''
def uji_langganan(akar):
    import sqlite3
    from pathlib import Path
    import admin_store, subscription as d, subscription_store as s
    akar = Path(akar)
    akar.mkdir(parents=True, exist_ok=True)
    p = akar / 'admin-control.db'
    akun = 'akun_' + 'a'*32
    inv = 'inv_' + 'b'*32
    on = d.Sakelar(True, True, True, False)
    try:
        s.baca(p, akun)
    except admin_store.StoreBelumSiap:
        pass
    else:
        raise AssertionError('reader_missing_diterima')
    assert not p.exists()
    with sqlite3.connect(p) as kon:
        admin_store._jalankan_ddl(kon, admin_store._DDL)
        kon.execute("INSERT INTO konfigurasi_pendaftaran VALUES(1,7,0,'closed_standard',1)")
        kon.execute('PRAGMA user_version=5')
    for _ in range(2):
        admin_store.siapkan(p, sekarang=1)
    with admin_store.buka_baca(p) as kon:
        assert kon.execute('PRAGMA user_version').fetchone()[0] == 6
        assert kon.execute('SELECT revisi FROM konfigurasi_pendaftaran').fetchone()[0] == 7
    try:
        s.enroll(p, akun, sumber_id='daftar_probe', asal='publik', mulai=1, peran='guru')
    except d.FiturNonaktif:
        pass
    else:
        raise AssertionError('default_off_dilewati')
    s.enroll(p, akun, sumber_id='daftar_probe', asal='publik', mulai=1, peran='guru', sakelar=on)
    s.atur_cakupan(p, akun, (1,), operasi_id='cakupan_probe', revisi=0, sekarang=1, pemilik_profil=lambda _: akun, sakelar=on)
    s.buat_invoice(p, akun, invoice_id=inv, idempotency_key='idem_probe', provider='fake', channel='qris', merchant='M', sekarang=1, kedaluwarsa=100, sakelar=on)
    b = d.Pembayaran('fake','trx_probe',inv,akun,35000,'IDR','qris','M','settlement',True)
    for _ in range(2):
        assert s.terapkan_pembayaran(p, akun, b, sekarang=2, sakelar=on) == 'grant'
    snap = s.baca(p, akun)
    assert len(snap.grants) == 1
    assert d.akses(snap.enrollment, snap.grants, sekarang=snap.grants[0].periode.mulai).status == 'paid'
    assert d.akses(snap.enrollment, snap.grants, sekarang=snap.grants[0].periode.akhir).status == 'expired'
    with admin_store.buka_baca(p) as kon:
        assert kon.execute('SELECT COUNT(*) FROM langganan_receipt').fetchone()[0] == 1
        assert not kon.execute('PRAGMA foreign_key_check').fetchall()
        assert kon.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    with sqlite3.connect(p) as kon:
        try:
            kon.execute('DELETE FROM langganan_grant')
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError('grant_mutable')
    return 4
'''
