"""Penutupan tagihan v1 kedaluwarsa ber-audit: guard adopsi, replay, migrator.

Fixture sintetis; invoice v1 memakai quote() dari test_subscription_service
(kedaluwarsa T0+1000) di atas admin8, sama seperti kondisi produksi tertahan.
"""
import sqlite3

import pytest
import admin_store
import subscription as d
import subscription_schema as schema
import subscription_store as lama
import subscription_package_store as paket
from test_subscription_service import keluarga, quote
from test_subscription_store import ON, T0

KEDALUWARSA = T0 + 1000


def siapkan_tertahan(k):
    inv = quote(k)
    admin_store.siapkan(k.admin, paket_v2=True)
    return inv


def tutup(k, inv, *, operasi='op_' + '1' * 32, sekarang=KEDALUWARSA, actor=None):
    return lama.tutup_tagihan(
        k.admin, k.principal.id_akun, inv['invoice_id'], operasi_id=operasi,
        actor_id=actor or k.principal.id_akun, actor_revisi=k.principal.revisi_auth,
        sekarang=sekarang, sakelar=ON)


def bukti(inv, transaksi='trx_tertahan_sintetis'):
    return d.Pembayaran('midtrans', transaksi, inv['invoice_id'], inv['akun_id'],
                        inv['rupiah'], 'IDR', 'qris', inv['merchant'], 'settlement', True)


def test_regresi_guard_lama_menahan_lalu_penutupan_beraudit_diterima(keluarga):
    """Merah sebelum fitur: adopsi tertahan; hijau: tertutup ber-audit diterima."""
    k = keluarga
    inv = siapkan_tertahan(k)
    with pytest.raises(lama.KonflikLangganan, match='tagihan lama'):
        paket.adopsi(k.admin, k.principal.id_akun, operasi_id='adopsi_sintetis',
                     sekarang=KEDALUWARSA, sakelar=ON)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    baris = tutup(k, inv)
    assert baris['invoice_id'] == inv['invoice_id']
    assert baris['alasan'] == schema.ALASAN_PENUTUPAN
    assert baris['dibuat'] == KEDALUWARSA
    assert baris['sidik'] == lama.sidik_penutupan(
        baris['operasi_id'], inv['invoice_id'], k.principal.id_akun,
        schema.ALASAN_PENUTUPAN, k.principal.id_akun, k.principal.revisi_auth, KEDALUWARSA)
    hasil = paket.adopsi(k.admin, k.principal.id_akun, operasi_id='adopsi_sintetis',
                         sekarang=KEDALUWARSA + 1, sakelar=ON)
    assert hasil['akun_id'] == k.principal.id_akun


def test_tutup_wajib_kedaluwarsa_tanpa_efek(keluarga):
    k = keluarga
    inv = siapkan_tertahan(k)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    awal = k.admin.read_bytes()
    with pytest.raises(lama.KonflikLangganan, match='kedaluwarsa'):
        tutup(k, inv, sekarang=KEDALUWARSA - 1)
    assert k.admin.read_bytes() == awal


def test_tutup_wajib_tanpa_grant(keluarga):
    k = keluarga
    inv = siapkan_tertahan(k)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    lama.terapkan_pembayaran(k.admin, k.principal.id_akun, bukti(inv),
                             sekarang=T0 + 3, sakelar=ON)
    with pytest.raises(lama.KonflikLangganan, match='grant'):
        tutup(k, inv)


def test_tutup_wajib_tanpa_receipt(keluarga):
    k = keluarga
    inv = siapkan_tertahan(k)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    # Pembayaran terlambat: receipt perlu_diperiksa tanpa grant.
    assert lama.terapkan_pembayaran(k.admin, k.principal.id_akun, bukti(inv),
                                    sekarang=KEDALUWARSA, sakelar=ON) == 'perlu_diperiksa'
    with pytest.raises(lama.KonflikLangganan, match='receipt'):
        tutup(k, inv)


def test_replay_idempoten_dan_operasi_lain_ditolak(keluarga):
    k = keluarga
    inv = siapkan_tertahan(k)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    a = tutup(k, inv)
    setelah = k.admin.read_bytes()
    b = tutup(k, inv, sekarang=KEDALUWARSA + 9)
    assert b == a and b['dibuat'] == KEDALUWARSA
    assert k.admin.read_bytes() == setelah
    with pytest.raises(lama.KonflikLangganan, match='berbeda'):
        tutup(k, inv, operasi='op_' + '2' * 32)


def test_baris_penutupan_immutable(keluarga):
    k = keluarga
    inv = siapkan_tertahan(k)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    tutup(k, inv)
    with sqlite3.connect(k.admin) as kon:
        for sql in ('UPDATE penutupan_tagihan SET alasan=alasan',
                    'DELETE FROM penutupan_tagihan',
                    'INSERT OR REPLACE INTO penutupan_tagihan SELECT * FROM penutupan_tagihan'):
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute(sql)


def test_invoice_paket_bukan_jalur_penutupan(keluarga):
    from test_subscription_package_store import siapkan, invoice
    k = keluarga
    siapkan(k)
    v2 = invoice(k, kini=T0 + 3)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    with pytest.raises(lama.KonflikLangganan, match='paket'):
        lama.tutup_tagihan(k.admin, k.principal.id_akun, v2['invoice_id'],
                           operasi_id='op_' + '4' * 32, actor_id=k.principal.id_akun,
                           actor_revisi=k.principal.revisi_auth, sekarang=T0 + 5, sakelar=ON)


def test_tabel_belum_dimigrasikan_fail_closed(keluarga):
    k = keluarga
    inv = siapkan_tertahan(k)
    with pytest.raises(admin_store.StoreBelumSiap, match='dimigrasikan'):
        tutup(k, inv)


def test_migrator_eksplisit_idempoten_dan_preservasi(tmp_path):
    from test_subscription_store import dump
    path = tmp_path / 'admin-control.db'
    admin_store.siapkan(path, sekarang=T0)
    awal = dump(path)
    with admin_store.buka_baca(path) as kon:
        assert not schema.tersedia_penutupan(kon)
    admin_store.migrasikan_penutupan_tagihan(path)
    with admin_store.buka_baca(path) as kon:
        assert schema.tersedia_penutupan(kon)
    sesudah = dump(path)
    assert [b for b in awal if b not in sesudah] == []
    assert all('penutupan_tagihan' in b for b in sesudah if b not in awal)
    admin_store.migrasikan_penutupan_tagihan(path)
    assert dump(path) == sesudah


def test_penutupan_parsial_ditolak_fail_closed(tmp_path):
    path = tmp_path / 'admin-control.db'
    admin_store.siapkan(path, sekarang=T0)
    admin_store.migrasikan_penutupan_tagihan(path)
    with sqlite3.connect(path) as kon:
        kon.execute('DROP TRIGGER penutupan_tagihan_tolak_update')
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(path):
            pass
    with pytest.raises(admin_store.StoreBelumSiap):
        admin_store.migrasikan_penutupan_tagihan(path)


def _sisip(k, inv, *, dibuat, sidik=None, actor_revisi=1):
    baris = ('op_' + '5' * 32, inv['invoice_id'], k.principal.id_akun,
             schema.ALASAN_PENUTUPAN, k.principal.id_akun, actor_revisi, dibuat,
             sidik if sidik is not None else lama.sidik_penutupan(
                 'op_' + '5' * 32, inv['invoice_id'], k.principal.id_akun,
                 schema.ALASAN_PENUTUPAN, k.principal.id_akun, actor_revisi, dibuat))
    with sqlite3.connect(k.admin) as kon:
        kon.execute('INSERT INTO penutupan_tagihan VALUES(?,?,?,?,?,?,?,?)', baris)


def test_validator_menolak_penutupan_saat_invoice_masih_aktif(keluarga):
    k = keluarga
    inv = siapkan_tertahan(k)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    _sisip(k, inv, dibuat=KEDALUWARSA - 10)
    with pytest.raises(lama.KonflikLangganan, match='penutupan'):
        lama.baca(k.admin, k.principal.id_akun)


def test_validator_menolak_sidik_penutupan_rusak(keluarga):
    k = keluarga
    inv = siapkan_tertahan(k)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    _sisip(k, inv, dibuat=KEDALUWARSA, sidik='a' * 64)
    with pytest.raises(lama.KonflikLangganan, match='penutupan'):
        lama.baca(k.admin, k.principal.id_akun)


def test_receipt_terlambat_membatalkan_penutupan_untuk_adopsi(keluarga):
    """Pembayaran lewat tenggat tetap tercatat; adopsi kembali ditahan review."""
    k = keluarga
    inv = siapkan_tertahan(k)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    tutup(k, inv)
    assert lama.terapkan_pembayaran(k.admin, k.principal.id_akun, bukti(inv),
                                    sekarang=KEDALUWARSA + 1, sakelar=ON) == 'perlu_diperiksa'
    with pytest.raises(lama.KonflikLangganan, match='tagihan lama'):
        paket.adopsi(k.admin, k.principal.id_akun, operasi_id='adopsi_sintetis',
                     sekarang=KEDALUWARSA + 2, sakelar=ON)


def test_v9_penutupan_dan_guard(keluarga):
    """Alur yang sama berlaku setelah migrasi kuota admin9."""
    k = keluarga
    inv = siapkan_tertahan(k)
    admin_store.migrasikan_kuota_pendamping(k.admin)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    tutup(k, inv)
    paket.adopsi(k.admin, k.principal.id_akun, operasi_id='adopsi_sintetis',
                 sekarang=KEDALUWARSA + 1, sakelar=ON)
    with admin_store.buka_baca(k.admin) as kon:
        assert kon.execute('PRAGMA user_version').fetchone()[0] == 9
        assert kon.execute('SELECT COUNT(*) FROM penutupan_tagihan').fetchone()[0] == 1


def test_rehearsal_target_penutupan_optin_preservasi(tmp_path):
    import ai_store
    import admin_backup
    from test_admin_backup import _buat_bundle
    b = _buat_bundle(tmp_path)
    awal = {p.name: p.read_bytes() for p in b.iterdir()}
    admin_backup.rehearsal_bundle(b, migrator_ai=ai_store.siapkan)
    admin_backup.rehearsal_bundle(b, migrator_ai=ai_store.siapkan, target_penutupan=True)
    assert awal == {p.name: p.read_bytes() for p in b.iterdir()}


def test_rehearsal_menolak_mematikan_penutupan_yang_ada(tmp_path):
    import ai_store
    import admin_backup
    from test_admin_backup import _buat_bundle
    b = _buat_bundle(tmp_path)
    admin_store.migrasikan_penutupan_tagihan(b / 'admin-control.db')
    (b / 'manifest.json').unlink()
    admin_backup.buat_manifest(b, bundle_id='backup-sintetis-001', cutoff=100)
    admin_backup.rehearsal_bundle(b, migrator_ai=ai_store.siapkan)
    with pytest.raises(admin_backup.BackupTidakSah, match='penutupan'):
        admin_backup.rehearsal_bundle(b, migrator_ai=ai_store.siapkan, target_penutupan=False)
