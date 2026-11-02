"""Kontrak jeda 28 hari pada checkpoint fokus diagnosis.

Spesifikasi siklus belajar memasang checkpoint pertama 28 hari setelah evaluasi
sukses. Test ini mengunci sisi penerimaan bukti: checkpoint yang dikonfirmasi
1-2 hari setelah evaluasi lulus bukan retensi, walaupun kedua bagian occurrence
lengkap dan seluruh probe benar.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from learning_cycle import rencana_berikutnya  # noqa: E402
from test_learning_cycle import (  # noqa: E402
    _bukti,
    _evaluasi,
    _outcome,
    _putaran_fokus_deret,
    _sesi_domain,
)


def _checkpoint(identitas_awal, tanggal_awal, tanggal_akhir, occurrence=1):
    """Checkpoint dua bagian lengkap dengan tiga probe benar per bagian."""
    return tuple(
        _sesi_domain(
            identitas_awal + urutan,
            tanggal,
            tujuan="checkpoint",
            bagian=urutan + 1,
            occurrence=occurrence,
            outcomes=tuple(
                _outcome("deret", benar=True, paham="bisa_menjelaskan")
                for _ in range(3)
            ),
        )
        for urutan, tanggal in enumerate((tanggal_awal, tanggal_akhir))
    )


def test_checkpoint_lima_hari_setelah_evaluasi_bukan_retensi():
    evaluasi = _evaluasi(1, "2026-09-08", True)
    checkpoint = _checkpoint(2, "2026-09-12", "2026-09-13")

    rencana = rencana_berikutnya(
        _bukti(evaluasi, *checkpoint, putaran=_putaran_fokus_deret()),
        1,
        date(2026, 9, 14),
    )

    assert rencana.putaran.fokus[0].status == "mulai_membaik"
    assert rencana.tindakan == "tunggu_checkpoint"
    assert rencana.tersedia_pada == date(2026, 10, 6)


def test_checkpoint_bagian_pertama_terlalu_dini_bukan_occurrence_berjalan():
    evaluasi = _evaluasi(1, "2026-09-08", True)
    bagian_1 = _checkpoint(2, "2026-09-12", "2026-09-13")[0]

    rencana = rencana_berikutnya(
        _bukti(evaluasi, bagian_1, putaran=_putaran_fokus_deret()),
        1,
        date(2026, 9, 14),
    )

    assert rencana.tindakan == "tunggu_checkpoint"
    assert rencana.bagian_checkpoint is None
    assert rencana.tersedia_pada == date(2026, 10, 6)


def test_checkpoint_setelah_tiga_puluh_dua_hari_diterima_sebagai_bertahan():
    evaluasi = _evaluasi(1, "2026-09-08", True)
    checkpoint = _checkpoint(2, "2026-10-10", "2026-10-11")

    rencana = rencana_berikutnya(
        _bukti(evaluasi, *checkpoint, putaran=_putaran_fokus_deret()),
        1,
        date(2026, 11, 1),
    )

    assert rencana.putaran.fokus[0].status == "bertahan"
    assert rencana.tindakan == "tunggu_checkpoint"
    assert rencana.tersedia_pada == date(2026, 11, 8)


def test_checkpoint_tepat_dua_puluh_delapan_hari_tetap_diterima():
    evaluasi = _evaluasi(1, "2026-09-08", True)
    checkpoint = _checkpoint(2, "2026-10-06", "2026-10-07")

    rencana = rencana_berikutnya(
        _bukti(evaluasi, *checkpoint, putaran=_putaran_fokus_deret()),
        1,
        date(2026, 10, 8),
    )

    assert rencana.putaran.fokus[0].status == "bertahan"
    assert rencana.tindakan == "tunggu_checkpoint"
    assert rencana.tersedia_pada == date(2026, 11, 4)
