"""Kelas sekolah terpisah dari konfigurasi soal dan bukti belajar.

Pemilik harus berasal dari identitas terautentikasi oleh caller; modul ini tidak
memberi bypass admin. Permukaan admin memvalidasi actor dengan kontraknya sendiri
sebelum memakai pemilik resource.
"""
from dataclasses import dataclass
from typing import Optional


class ProfilTidakDitemukan(ValueError):
    """Resource tidak ada atau bukan milik pemanggil; pesan sengaja identik."""


class KonflikProfil(ValueError):
    """Revisi berubah; muat ulang sebelum menyimpan agar tab lama tidak menimpa."""


@dataclass(frozen=True)
class ProfilBelajar:
    siswa_id: int
    kelas_sekolah: Optional[int] = None
    revisi: int = 0


def label_kelas_sekolah(kelas_sekolah: Optional[int]) -> str:
    """Label metadata faktual, tidak mengubah Pn menjadi kelas atau kemampuan."""
    if kelas_sekolah is None:
        return 'Kelas belum diisi'
    if type(kelas_sekolah) is not int or not 1 <= kelas_sekolah <= 6:
        raise ValueError('kelas sekolah harus kosong atau bilangan bulat 1–6')
    return 'Kelas %d' % kelas_sekolah


def baca(kon, siswa_id: int, *, pemilik: str) -> ProfilBelajar:
    """Baca metadata saja tanpa membuat baris atau memuat jawaban anak."""
    if type(siswa_id) is not int or siswa_id < 1 or type(pemilik) is not str or not pemilik:
        raise ProfilTidakDitemukan('Profil tidak ditemukan.')
    baris = kon.execute(
        '''SELECT s.id, p.kelas_sekolah, COALESCE(p.revisi, 0) AS revisi
           FROM siswa s LEFT JOIN profil_belajar p ON p.siswa_id = s.id
           WHERE s.id = ? AND s.pemilik = ?''', (siswa_id, pemilik),
    ).fetchone()
    if baris is None:
        raise ProfilTidakDitemukan('Profil tidak ditemukan.')
    return ProfilBelajar(baris['id'], baris['kelas_sekolah'], baris['revisi'])


def simpan_kelas(kon, siswa_id: int, kelas_sekolah: Optional[int], *,
                 revisi: int, pemilik: str) -> ProfilBelajar:
    """Simpan dengan compare-and-swap; tidak commit transaksi atau mengubah bukti."""
    if kelas_sekolah is not None and (type(kelas_sekolah) is not int or not 1 <= kelas_sekolah <= 6):
        raise ValueError('kelas sekolah harus kosong atau bilangan bulat 1–6')
    if type(revisi) is not int or revisi < 0:
        raise ValueError('revisi profil harus bilangan bulat nonnegatif')
    profil = baca(kon, siswa_id, pemilik=pemilik)
    if profil.revisi != revisi:
        raise KonflikProfil('Profil berubah. Muat ulang sebelum menyimpan.')
    if profil.kelas_sekolah == kelas_sekolah:
        return profil
    # Satu statement membatasi owner dan revisi pada saat menulis juga. Jangan
    # mengandalkan pembacaan sebelumnya atau commit transaksi milik pemanggil.
    hasil = kon.execute(
        '''INSERT INTO profil_belajar (siswa_id, kelas_sekolah, revisi)
           SELECT id, ?, 1 FROM siswa
           WHERE id = ? AND pemilik = ? AND
             COALESCE((SELECT revisi FROM profil_belajar WHERE siswa_id = siswa.id), 0) = ?
           ON CONFLICT(siswa_id) DO UPDATE
           SET kelas_sekolah = excluded.kelas_sekolah, revisi = profil_belajar.revisi + 1
           WHERE profil_belajar.revisi = ?''',
        (kelas_sekolah, siswa_id, pemilik, revisi, revisi),
    )
    if hasil.rowcount != 1:
        raise KonflikProfil('Profil berubah. Muat ulang sebelum menyimpan.')
    return ProfilBelajar(siswa_id, kelas_sekolah, revisi + 1)
