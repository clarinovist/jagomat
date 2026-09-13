"""Palang aset/modul dan pemisahan storage admin pada image."""
from pathlib import Path


def test_image_admin_memakai_storage_durable_dan_transient_terpisah():
    root=Path(__file__).resolve().parents[1]
    docker=(root/'Dockerfile').read_text()
    assert 'ADMIN_BERKAS_DB=/data/admin-control.db' in docker
    assert 'ADMIN_TRANSIENT_DB=/data/transient/admin-drafts.db' in docker
    assert 'COPY --chown=osn:osn *.py /app/' in docker
    for nama in ('admin_store.py','admin_bulk.py','admin_accounts.py','admin_students.py','json_storage.py','ai_admin_operations.py'):
        assert (root/nama).is_file()
    assert 'COPY . ' not in docker and 'COPY ./' not in docker
