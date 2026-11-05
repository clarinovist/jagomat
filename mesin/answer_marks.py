"""Tanda "ditandai benar dari lembar" pada diagnosis guru.

Guru boleh mencentang "jawaban anak benar" di halaman isi dari lembar
(``attachments.terapkan``). Jawaban disimpan sebagai kunci dan diagnosisnya
manual benar dengan ``diagnosis.catatan = PENANDA_DITANDAI_BENAR``.

Modul ini sengaja di luar berkas kontrak persistensi (nama tanpa store/schema/
migrat/database): perilaku tanda tidak boleh menggeser sidik kontrak yang harus
identik dengan recovery yang di-pin. Penanda tidak memakai
``tinjauan_guru.provenance`` karena kolom itu dikunci CHECK skema.

Palang: tanda hanya sah selama jawaban tersimpan masih kunci. Bila anak
mengubah jawabannya sesudah dicentang, ``reports.diagnosa_murid`` melepas tanda
dan menilai ulang butir itu seperti jawaban biasa (``tanda_basi``).
"""
from __future__ import annotations

PENANDA_DITANDAI_BENAR = 'ditandai_benar'


def ditandai_benar(b) -> bool:
    """Butir manual benar yang berasal dari centang lembar, bukan ketikan."""
    try:
        return (bool(b['manual']) and bool(b['benar'])
                and b['catatan'] == PENANDA_DITANDAI_BENAR)
    except (KeyError, IndexError):
        return False


def tanda_basi(b) -> bool:
    """Tanda benar yang jawabannya tidak lagi kunci: harus dilepas dan dinilai ulang.

    Baris tanpa kolom kunci/jawaban dianggap basi (gagal tertutup): lebih aman
    dinilai ulang mesin daripada mempertahankan "benar" yang tidak diperiksa.
    """
    if not ditandai_benar(b):
        return False
    try:
        return (b['jawaban'] or '').strip() != (b['kunci'] or '').strip()
    except (KeyError, IndexError):
        return True
