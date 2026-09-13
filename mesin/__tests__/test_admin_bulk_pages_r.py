"""Kontrak render fallback tanpa mengambil keputusan domain sendiri."""
from types import SimpleNamespace
import admin_pages


def test_fallback_tidak_menampilkan_alias_atau_aksi_proses_dari_pending():
    item = SimpleNamespace(item_id='item_demo', operasi_id='op_demo', target_id='akun_demo',
        target_revisi=1, alias_valid=None, status='pending', hasil_id=None, credential_status='not_applicable')
    batch = SimpleNamespace(batch_id='batch_demo', aksi='account_teacher_create', target_peran='guru',
        status='attention', item=(item,), draft_tersedia=False, boleh_proses=False, kelompok_aktif_id=None)
    isi = admin_pages.render_bulk_batch(batch, (), 'csrf', {'process':'p','stop':'s','handover':'h'}, {'akun_demo':'alias-tidak-boleh-fallback'})
    assert 'alias-tidak-boleh-fallback' not in isi
    assert 'akun_demo' in isi and 'Draft alias sudah tidak tersedia' in isi
    assert 'action="/admin/bulk/proses"' not in isi


def test_fresh_credential_tetap_berpasangan_alias_bila_janitor_hapus_draft_selesai():
    item = SimpleNamespace(item_id='item_demo', operasi_id='op_demo', target_id='candidate_demo',
        target_revisi=0, alias_valid=None, status='succeeded', hasil_id='akun_demo', credential_status='unconfirmed')
    batch = SimpleNamespace(batch_id='batch_demo', aksi='account_teacher_create', target_peran='guru',
        status='succeeded', item=(item,), draft_tersedia=False, boleh_proses=False, kelompok_aktif_id=None)
    hasil = (SimpleNamespace(item_id='item_demo', credential_sekali='sandi-sintetis-baru'),)
    isi = admin_pages.render_bulk_batch(batch, hasil, 'csrf', {'process':'p','stop':'s','handover':'h'}, {'akun_demo':'alias-fresh'})
    assert 'alias-fresh' in isi and 'sandi-sintetis-baru' in isi
    replay = admin_pages.render_bulk_batch(batch, (), 'csrf', {'process':'p','stop':'s','handover':'h'}, {'akun_demo':'alias-fresh'})
    assert 'alias-fresh' not in replay and 'sandi-sintetis-baru' not in replay


def test_running_recovery_hanya_jika_domain_mengizinkan_kelompok_sama():
    batch = SimpleNamespace(batch_id='batch_demo', aksi='account_session_revoke', target_peran='guru',
        status='running', item=(), draft_tersedia=True, boleh_proses=True, kelompok_aktif_id='op_kelompok_demo')
    isi = admin_pages.render_bulk_batch(batch, (), 'csrf', {'process':'p','stop':'s','handover':'h'}, {})
    assert 'Pulihkan kelompok yang sama' in isi
    batch.boleh_proses = False
    isi = admin_pages.render_bulk_batch(batch, (), 'csrf', {'process':'p','stop':'s','handover':'h'}, {})
    assert 'action="/admin/bulk/proses"' not in isi
