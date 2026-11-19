"""Opt-in skema pesanan v1, `transfer_*`, dan `rekening_*` pada validator/rehearsal backup.

Urutan tetap (pesanan, transfer, rekening): transfer bergantung pada ledger pesanan.
Semua fungsi murni terhadap koneksi/path yang diberikan; galat input memakai ValueError
agar `admin_backup` menerjemahkannya menjadi `BackupTidakSah`.
"""
from __future__ import annotations

from typing import Optional, Tuple

Skema = Tuple[bool, bool, bool]
TIDAK_ADA: Skema = (False, False, False)


def deteksi(kon) -> Skema:
    """(pesanan, transfer, rekening) yang terpasang dan sah; parsial -> ValueError."""
    import pesanan_rekening
    import schema_pesanan
    import schema_transfer
    return (schema_pesanan.validasi(kon), schema_transfer.validasi(kon),
            pesanan_rekening.validasi_schema(kon))


def tentukan_target(awal: Skema, pesanan: Optional[bool], transfer: Optional[bool],
                    rekening: Optional[bool]) -> Skema:
    """None mempertahankan skema backup; transfer menyeret pesanan; tidak boleh menurun."""
    if transfer is None:
        transfer = awal[1]
    if pesanan is None:
        pesanan = awal[0] or transfer is True
    rekening = awal[2] if rekening is None else rekening
    target = (pesanan, transfer, rekening)
    if any(type(nilai) is not bool for nilai in target):
        raise ValueError("target pesanan tidak sah")
    if any(sebelum and not sesudah for sebelum, sesudah in zip(awal, target)):
        raise ValueError("target pesanan tidak boleh menurun")
    if target[1] and not target[0]:
        raise ValueError("transfer memerlukan pesanan")
    return target


def migrasikan(path, target: Skema, sekarang: int) -> None:
    """Pasang skema yang ditargetkan (idempoten) pada salinan temp."""
    if target[0]:
        import schema_pesanan
        schema_pesanan.migrasikan(path)
    if target[1]:
        import schema_transfer
        schema_transfer.migrasikan(path)
    if target[2]:
        import pesanan_rekening
        pesanan_rekening.migrasikan(path, sekarang=sekarang)
