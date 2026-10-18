"""Rehearsal sensor pada turunan, induk tidak diubah."""
import hashlib
import admin_backup
import ai_store
from test_admin_backup import _buat_bundle


def test_rehearsal_sensor_opt_in_preservasi(tmp_path):
    bundle=_buat_bundle(tmp_path)
    awal={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.iterdir()}
    assert not admin_backup.validasi_bundle(bundle).skema_sensor
    hasil=admin_backup.rehearsal_bundle(bundle,migrator_ai=ai_store.siapkan,target_sensor=True)
    assert hasil.skema_sensor
    assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.iterdir()}==awal
