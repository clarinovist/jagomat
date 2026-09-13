"""Pemeliharaan bounded untuk audit admin dan draft batch transient."""

from dataclasses import dataclass

import admin_bulk
import admin_store


@dataclass(frozen=True)
class HasilPemeliharaan:
    audit_dihapus: int
    draft_dihapus: int


def jalankan(
    path_admin,
    path_transient,
    *,
    sekarang=None,
    batas_audit=500,
    batas_batch=100,
) -> HasilPemeliharaan:
    """Purge sekali secara bounded; lifecycle/thread tetap milik caller."""
    audit = admin_store.purge_audit(
        path_admin, sekarang=sekarang, batas_baris=batas_audit
    )
    draft = admin_bulk.purge_draft(
        path_transient, sekarang=sekarang, batas_batch=batas_batch
    )
    return HasilPemeliharaan(audit, draft)
