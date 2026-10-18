"""Pemeliharaan bounded untuk audit admin dan draft batch transient."""

from dataclasses import dataclass
import sqlite3

import admin_bulk
import admin_store


@dataclass(frozen=True)
class HasilPemeliharaan:
    audit_dihapus: int
    draft_dihapus: int
    riset_dihapus: int = 0


def jalankan(
    path_admin,
    path_transient,
    *,
    path_riset=None,
    sekarang=None,
    batas_audit=500,
    batas_batch=100,
    actor_riset="sistem_retensi",
) -> HasilPemeliharaan:
    """Purge sekali secara bounded; lifecycle/thread tetap milik caller."""
    audit = admin_store.purge_audit(
        path_admin, sekarang=sekarang, batas_baris=batas_audit
    )
    draft = admin_bulk.purge_draft(
        path_transient, sekarang=sekarang, batas_batch=batas_batch
    )
    import time
    import product_analytics_store
    kini = int(time.time()) if sekarang is None else sekarang
    product_analytics_store.retensi(path_admin, sekarang=kini)
    import sensor_store
    sensor_store.retensi(path_admin, sekarang=kini)
    import sensor_cleanup
    import database
    import auth
    import assistant_schema
    try:
        sensor_cleanup.bersihkan(path_admin, database.BAWAAN, assistant_schema.BAWAAN,
                                  auth.BERKAS_SANDI, sekarang=kini)
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        sensor_store.gangguan()
    riset = 0
    if path_riset is not None:
        import research_store
        riset = research_store.hapus_retensi(
            path_riset, actor_id=actor_riset, sekarang=kini, batas=50,
        )
    return HasilPemeliharaan(audit, draft, riset)
