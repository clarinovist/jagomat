"""Penanda keluarga paket kelas: admin menautkan dua anak sebagai satu keluarga (dasar diskon anak kedua).

Pembeli TIDAK memilih sendiri status anak kedua (mencegah klaim diskon sepihak): satu-satunya jalur menulis
`kelas_keluarga` adalah fungsi ini, dipanggil admin. `siswa_id` ada di DB belajar (DB lain), jadi kebenaran bahwa kedua
anak memang satu keluarga adalah tanggung jawab admin; lapisan ini hanya menjaga bentuk datanya (satu anak paling
banyak satu keluarga; dua keluarga yang sudah ada tidak dilebur). Semua tulis dalam satu `BEGIN IMMEDIATE`.
"""
from __future__ import annotations

from typing import Optional

import kelas_dasar as k
import pesanan_dasar as d


def _keluarga_anak(kon, siswa_id: int) -> Optional[str]:
    baris = kon.execute("SELECT keluarga_id FROM kelas_keluarga WHERE siswa_id=?", (siswa_id,)).fetchone()
    return None if baris is None else baris["keluarga_id"]


def _tambah(kon, keluarga_id: str, siswa_id: int, admin_id: str, kini: str) -> None:
    kon.execute("INSERT INTO kelas_keluarga(keluarga_id,siswa_id,ditautkan_oleh,waktu) VALUES(?,?,?,?)",
                (keluarga_id, siswa_id, admin_id, kini))


def tautkan_keluarga(kon, admin_id, siswa_a, siswa_b, sekarang) -> dict:
    """Tautkan dua anak sebagai satu keluarga; idempoten. Mengembalikan {keluarga_id, baru}.

    Salah satu sudah punya keluarga: yang lain bergabung ke sana. Keduanya sudah satu keluarga: tidak menulis
    (baru False). Keduanya di keluarga BERBEDA: KelasKonflik tanpa tulis (peleburan bukan fitur). Anak yang sama
    atau id tidak sah: PesananDataTidakSah.
    """
    d.periksa_koneksi(kon)
    d.periksa_pelaku(admin_id)
    k.periksa_siswa_id(siswa_a)
    k.periksa_siswa_id(siswa_b)
    if siswa_a == siswa_b:
        raise d.PesananDataTidakSah("dua anak harus berbeda")
    kini = k.ke_baku(sekarang)
    with d.tulis(kon):
        ka, kb = _keluarga_anak(kon, siswa_a), _keluarga_anak(kon, siswa_b)
        if ka is not None and kb is not None:
            if ka != kb:
                raise k.KelasKonflik("kedua anak sudah di keluarga yang berbeda")
            return {"keluarga_id": ka, "baru": False}
        keluarga = ka or kb or k.id_keluarga_baru()
        for siswa, ada in ((siswa_a, ka), (siswa_b, kb)):
            if ada is None:
                _tambah(kon, keluarga, siswa, admin_id, kini)
        return {"keluarga_id": keluarga, "baru": True}
