"""Kelayakan kelompok dan anak untuk tautan kode anak guru. Hanya SELECT.

`kelompok_pesan_tutup` mengulang syarat terbuka dari `jadwal_pilih._kelompok_bisa_dimasuki` (pertemuan mendatang ada,
belum dua pertemuan mulai, masih ada kursi) supaya guru pemilik mendapat pesan spesifik tentang kelompoknya sendiri.
`anak_bisa_masuk` memakai `jadwal_pilih.pilihan_untuk` apa adanya, sehingga syarat per anak (order Mini aktif,
belum ditempatkan, masa akses) tetap ditegakkan di satu tempat. Penegakan sebenarnya tetap di `pilih_kelompok`.
"""

from __future__ import annotations

from typing import Optional

import jadwal_pilih
import jadwal_store as js

PESAN_SELESAI = "Kelompok ini sudah selesai, jadi belum bisa menerima anak baru."
PESAN_PENUH = "Kelompok ini sudah penuh, jadi belum bisa menerima anak baru."


def _kuota(kon, kelompok_id: str) -> Optional[int]:
    baris = kon.execute("SELECT kuota FROM jadwal_kelompok WHERE id=?", (kelompok_id,)).fetchone()
    return None if baris is None else int(baris[0])


def kelompok_pesan_tutup(kon, kelompok_id: str, kini: str) -> Optional[str]:
    """Alasan kelompok belum menerima anak sekarang (teks untuk guru pemiliknya), atau None bila terbuka."""
    kuota = _kuota(kon, kelompok_id)
    if kuota is None or js._pertemuan_mendatang(kon, kelompok_id, kini) is None:
        return PESAN_SELESAI
    if js._jumlah_sudah_mulai(kon, kelompok_id, kini) >= js.TUTUP_SETELAH_PERTEMUAN_MULAI:
        return js.PESAN_DITUTUP
    if js._isi_kelompok(kon, kelompok_id) >= kuota:
        return PESAN_PENUH
    return None


def anak_bisa_masuk(kon, akun_id: str, siswa_id: int, kelompok_id: str, kini: str) -> bool:
    """True bila order Mini aktif anak yang belum ditempatkan boleh masuk kelompok ini (`pilihan_untuk`)."""
    return any(pilihan.kelompok_id == kelompok_id
               for pilihan in jadwal_pilih.pilihan_untuk(kon, akun_id, siswa_id, kini))
