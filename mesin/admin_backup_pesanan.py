"""Opt-in skema pesanan v1, `transfer_*`, `rekening_*`, `purna_*`, `kelas_*`, `jadwal_*`, dan `harga_*` pada validator/rehearsal backup.

Urutan tetap (pesanan, transfer, rekening, purna, kelas, jadwal): transfer bergantung pada ledger pesanan, purna
bergantung pada pesanan dan transfer, kelas bergantung pada ledger pesanan (dan memakai purna saat lunas),
jadwal bergantung pada kelas, harga berdiri sendiri (tanpa kunci asing).
Semua fungsi murni terhadap koneksi/path yang diberikan; galat input memakai ValueError agar
`admin_backup` menerjemahkannya menjadi `BackupTidakSah`.
"""
from __future__ import annotations

from typing import Optional, Tuple

Skema = Tuple[bool, bool, bool, bool]
TIDAK_ADA: Skema = (False, False, False, False)


def deteksi(kon) -> Skema:
    """(pesanan, transfer, rekening, purna) yang terpasang dan sah; parsial -> ValueError."""
    import pesanan_rekening
    import schema_pesanan
    import schema_purna
    import schema_transfer
    return (schema_pesanan.validasi(kon), schema_transfer.validasi(kon),
            pesanan_rekening.validasi_schema(kon), schema_purna.validasi(kon))


def tentukan_target(awal: Skema, pesanan: Optional[bool], transfer: Optional[bool],
                    rekening: Optional[bool], purna: Optional[bool] = None) -> Skema:
    """None mempertahankan skema backup; purna menyeret transfer, transfer menyeret pesanan; tidak boleh menurun."""
    purna = awal[3] if purna is None else purna
    if transfer is None:
        transfer = awal[1] or purna is True
    if pesanan is None:
        pesanan = awal[0] or transfer is True
    rekening = awal[2] if rekening is None else rekening
    target = (pesanan, transfer, rekening, purna)
    if any(type(nilai) is not bool for nilai in target):
        raise ValueError("target pesanan tidak sah")
    if any(sebelum and not sesudah for sebelum, sesudah in zip(awal, target)):
        raise ValueError("target pesanan tidak boleh menurun")
    if target[1] and not target[0]:
        raise ValueError("transfer memerlukan pesanan")
    if target[3] and not target[1]:
        raise ValueError("purna memerlukan pesanan dan transfer")
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
    if target[3]:
        import schema_purna
        schema_purna.migrasikan(path)


def deteksi_kelas(kon) -> bool:
    """Namespace `kelas_*` terpasang dan sah (True), absen (False), parsial/berbeda -> ValueError."""
    import schema_kelas
    return schema_kelas.validasi(kon)


def migrasikan_kelas(path) -> None:
    """Pasang skema `kelas_*` (idempoten) pada salinan temp; mensyaratkan ledger pesanan."""
    import schema_kelas
    schema_kelas.migrasikan(path)


def deteksi_jadwal(kon) -> bool:
    """Namespace `jadwal_*` terpasang dan sah (True), absen (False), parsial/berbeda/tanpa kelas -> ValueError."""
    import schema_jadwal
    return schema_jadwal.validasi(kon)


def migrasikan_jadwal(path) -> None:
    """Pasang skema `jadwal_*` (idempoten) pada salinan temp; mensyaratkan `kelas_*` sudah terpasang."""
    import schema_jadwal
    schema_jadwal.migrasikan(path)


def deteksi_harga(kon) -> bool:
    """Namespace `harga_*` terpasang dan sah (True), absen (False), parsial/berbeda -> ValueError."""
    import schema_harga
    return schema_harga.validasi(kon)


def migrasikan_harga(path) -> None:
    """Pasang skema `harga_*` (idempoten) pada salinan temp; tidak mensyaratkan ledger lain."""
    import schema_harga
    schema_harga.migrasikan(path)
