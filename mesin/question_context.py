"""Konteks konfigurasi soal warisan, bukan klasifikasi kemampuan anak.

P3–P6 tetap identitas parameter historis. Konteks yang berbeda tidak menyatakan
urutan kesulitan atau kesetaraan bukti; penetapan tuntutan memerlukan rubrik terpisah.
"""
from dataclasses import dataclass
from typing import Tuple

import topics
from templates import LEVEL


@dataclass(frozen=True)
class KonteksSoal:
    template_id: str
    profil_parameter: str

    def __post_init__(self):
        if type(self.template_id) is not str or type(self.profil_parameter) is not str:
            raise ValueError('konteks soal tidak dikenal')
        pemilik = topics.pemilik_template(self.template_id)
        if (self.profil_parameter not in LEVEL or pemilik is None
                or self.template_id not in topics.ambil(pemilik).komposisi.get(self.profil_parameter, ())):
            raise ValueError('konteks soal tidak tersedia dalam komposisi warisan')

    @property
    def versi(self) -> int:
        return 1

    @property
    def id(self) -> str:
        return 'warisan-v1:{}:{}'.format(self.template_id, self.profil_parameter)

    @property
    def topik_id(self) -> str:
        return topics.pemilik_template(self.template_id)


def konteks_warisan(template_id: str, profil_parameter: str) -> KonteksSoal:
    """Tolak pasangan di luar komposisi; jangan fallback atau menebak kesulitan."""
    return KonteksSoal(template_id, profil_parameter)


def label_profil_parameter(profil: str) -> str:
    """Label konfigurasi, tidak menebak kelas sekolah atau kemampuan."""
    return 'Profil ' + profil if profil in LEVEL else 'Profil warisan: ' + str(profil)


def label_konteks(konteks: KonteksSoal) -> str:
    """Label pola dan konfigurasi sumber tanpa urutan kesulitan."""
    from template_labels import nama_tipe_soal
    return '{} · {}'.format(nama_tipe_soal(konteks.template_id),
                            label_profil_parameter(konteks.profil_parameter))


def profil_dari_form(data) -> str:
    """Pilihan formulir eksplisit; nilai ganda/kosong tidak memakai default anak."""
    nilai = data.get('profil_parameter')
    if not isinstance(nilai, list) or len(nilai) != 1 or nilai[0] not in LEVEL:
        raise ValueError('Pilih satu profil parameter latihan (P3–P6). Muat ulang form bila perlu.')
    return nilai[0]


def validasi_pilihan(topik_ids, profil: str) -> None:
    """Setiap topik harus tersedia; gabungan tidak menyembunyikan pilihan kosong."""
    if profil not in LEVEL or not topik_ids:
        raise ValueError('Pilih profil parameter dan materi latihan.')
    for topik_id in topik_ids:
        if (topik_id not in topics.daftar_topik()
                or profil not in topics.ambil(topik_id).komposisi):
            raise ValueError('Materi tidak tersedia pada profil ini. Pilih profil atau materi lain.')


def daftar_konteks() -> Tuple[KonteksSoal, ...]:
    """Inventaris komposisi deterministik; tidak membaca profil atau data anak."""
    return tuple(
        KonteksSoal(template_id, level)
        for topik_id in topics.daftar_topik() if topik_id != 'campuran'
        for level in LEVEL
        for template_id in sorted(set(topics.ambil(topik_id).komposisi.get(level, ())))
    )
