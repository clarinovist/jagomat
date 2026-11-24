"""Penyimpanan laporan Peta Kemampuan untuk orang tua (D1-1): semua SQL tabel `peta_laporan` ada di sini.

Satu laporan per anak. Siklus: draf (`buat_draf`) -> catatan Guru (`simpan_catatan`) -> terbit (`terbitkan`); draf
boleh dihapus (`hapus_draf`), laporan terbit tidak. Isi snapshot dibangun server (`peta_laporan_snapshot`) dan
DIPERIKSA ulang tiap ditulis dan tiap dibaca, jadi baris dengan isi di luar allowlist tidak pernah sampai ke
pemanggil. Semua fungsi memakai koneksi DB belajar milik pemanggil dan TIDAK commit sendiri (transaksi pemanggil).
Waktu disuntik (`sekarang` = epoch detik, bukan bool) dan disimpan seperti `parent_report_store` (WIB).
Pemeriksaan kepemilikan anak oleh Guru adalah tugas pemanggil; kunci `siswa_id` selalu dari sisi server.
"""
from __future__ import annotations

import json

from peta_laporan_snapshot import periksa_isi

BATAS_CATATAN = 2000
BATAS_GURU = 64
_SPASI = " \t\n\r"
_KOLOM = "id, siswa_id, isi, catatan, guru, dibuat, diterbitkan, diterbitkan_oleh"


def _epoch(sekarang) -> int:
    if type(sekarang) is not int:
        raise ValueError("sekarang harus epoch detik bilangan bulat")
    return sekarang


def _guru(guru) -> str:
    if type(guru) is not str or not 1 <= len(guru) <= BATAS_GURU:
        raise ValueError("akun guru tidak sah")
    return guru


def _baris_ke_dict(baris) -> dict:
    kunci = ("id", "siswa_id", "isi", "catatan", "guru", "dibuat", "diterbitkan", "diterbitkan_oleh")
    laporan = {k: baris[i] for i, k in enumerate(kunci)}
    try:
        laporan["isi"] = periksa_isi(json.loads(laporan["isi"]))
    except json.JSONDecodeError:
        raise ValueError("isi laporan peta rusak") from None
    return laporan


def buat_draf(kon, siswa_id: int, guru: str, isi: dict, sekarang) -> int:
    """Draf baru untuk anak ini; draf/laporan kedua untuk anak yang sama = ValueError."""
    isi_bersih = periksa_isi(isi)
    akun = _guru(guru)
    waktu = _epoch(sekarang)
    if kon.execute("SELECT 1 FROM peta_laporan WHERE siswa_id = ?", (siswa_id,)).fetchone() is not None:
        raise ValueError("anak ini sudah punya laporan peta")
    cur = kon.execute(
        """INSERT INTO peta_laporan (siswa_id, isi, guru, dibuat)
           VALUES (?, ?, ?, datetime(?, 'unixepoch', '+7 hours'))""",
        (siswa_id, json.dumps(isi_bersih, ensure_ascii=False, sort_keys=True), akun, waktu),
    )
    return cur.lastrowid


def ambil(kon, siswa_id: int):
    """Laporan anak ini (draf atau terbit) dengan isi tervalidasi ulang, atau None. Isi tak sah = ValueError."""
    baris = kon.execute(
        "SELECT %s FROM peta_laporan WHERE siswa_id = ?" % _KOLOM, (siswa_id,),
    ).fetchone()
    return None if baris is None else _baris_ke_dict(baris)


def simpan_catatan(kon, siswa_id: int, catatan: str) -> None:
    """Ganti catatan Guru pada DRAF; laporan terbit atau tidak ada = ValueError."""
    if type(catatan) is not str or len(catatan) > BATAS_CATATAN:
        raise ValueError("catatan terlalu panjang")
    cur = kon.execute(
        "UPDATE peta_laporan SET catatan = ? WHERE siswa_id = ? AND diterbitkan IS NULL",
        (catatan, siswa_id),
    )
    if cur.rowcount != 1:
        raise ValueError("laporan bukan draf milik anak ini")


def terbitkan(kon, siswa_id: int, guru: str, sekarang) -> str:
    """Terbitkan draf yang catatannya tidak kosong; mengembalikan waktu terbit. Terbit kedua kali = ValueError."""
    akun = _guru(guru)
    waktu = _epoch(sekarang)
    laporan = ambil(kon, siswa_id)
    if laporan is None or laporan["diterbitkan"] is not None:
        raise ValueError("laporan bukan draf milik anak ini")
    if not laporan["catatan"].strip(_SPASI):
        raise ValueError("catatan wajib diisi sebelum terbit")
    cur = kon.execute(
        """UPDATE peta_laporan SET diterbitkan = datetime(?, 'unixepoch', '+7 hours'), diterbitkan_oleh = ?
           WHERE siswa_id = ? AND diterbitkan IS NULL""",
        (waktu, akun, siswa_id),
    )
    if cur.rowcount != 1:
        raise ValueError("laporan bukan draf milik anak ini")
    return kon.execute("SELECT diterbitkan FROM peta_laporan WHERE siswa_id = ?", (siswa_id,)).fetchone()[0]


def hapus_draf(kon, siswa_id: int) -> bool:
    """Hapus DRAF anak ini; True bila terhapus, False bila tidak ada. Laporan terbit = ValueError (tidak dihapus)."""
    laporan = ambil(kon, siswa_id)
    if laporan is None:
        return False
    if laporan["diterbitkan"] is not None:
        raise ValueError("laporan terbit tidak dihapus")
    return kon.execute(
        "DELETE FROM peta_laporan WHERE siswa_id = ? AND diterbitkan IS NULL", (siswa_id,),
    ).rowcount == 1


def terbit_terakhir(kon, siswa_id: int):
    """Laporan TERBIT untuk halaman orang tua: isi tervalidasi, catatan, waktu terbit; None bila draf/tidak ada.

    Tidak memuat akun Guru (pembuat maupun penerbit); kolom itu tidak dibaca sama sekali.
    """
    baris = kon.execute(
        "SELECT isi, catatan, diterbitkan FROM peta_laporan WHERE siswa_id = ? AND diterbitkan IS NOT NULL",
        (siswa_id,),
    ).fetchone()
    if baris is None:
        return None
    try:
        isi = periksa_isi(json.loads(baris[0]))
    except json.JSONDecodeError:
        raise ValueError("isi laporan peta rusak") from None
    return {"isi": isi, "catatan": baris[1], "diterbitkan": baris[2]}
