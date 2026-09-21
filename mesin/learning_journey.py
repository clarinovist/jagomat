"""Proyeksi immutable perjalanan siklus untuk profil dan laporan.

Proyeksi ini tidak menghitung ulang ambang pedagogis. Rekomendasi dan status
kelulusan tetap berasal dari reducer :mod:`learning_cycle`; modul ini hanya
membentuk tahap per fokus, bukti singkat, dan histori putaran tertutup.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import List, Optional, Tuple

import learning_cycle as lc
from learning_history import catatan_histori_beda_level


@dataclass(frozen=True)
class BuktiFokusPerjalanan:
    tanggal: date
    sesi_id: Optional[int]
    jenis: str
    cek_pemahaman: Tuple[str, ...] = ()
    status: str = "terkonfirmasi"
    hasil: Optional[str] = None


@dataclass(frozen=True)
class FokusPerjalanan:
    kunci: lc.KunciFokus
    tahap: str
    bukti: Tuple[BuktiFokusPerjalanan, ...] = ()


@dataclass(frozen=True)
class HistoriPutaran:
    id: int
    level: str
    dibuka: date
    ditutup: date
    alasan_penutupan: str
    fokus: Tuple[lc.KunciFokus, ...]
    bukti: Tuple[BuktiFokusPerjalanan, ...] = ()
    status_bukti: str = "tersedia"
    perjalanan_fokus: Tuple[FokusPerjalanan, ...] = ()


@dataclass(frozen=True)
class PerjalananBelajar:
    rekomendasi: lc.RencanaBelajar
    fokus: Tuple[FokusPerjalanan, ...] = ()
    histori: Tuple[HistoriPutaran, ...] = ()
    putaran_id: Optional[int] = None
    tanggal_pemetaan: Tuple[date, ...] = ()
    catatan: Tuple[str, ...] = ()


_PENUTUP = {"putaran_ditutup", "diganti_level", "override_ditutup"}
_JENIS_BUKTI = {
    "latihan_terbimbing",
    "penguatan",
    "evaluasi",
    "checkpoint",
}


def _ringkasan_dasar(
    bukti: lc.BuktiSiklus, putaran: Optional[lc.PutaranSiklus]
) -> Tuple[
    Tuple[lc.SesiSiklus, ...],
    Tuple[Tuple[lc.KunciFokus, int, date], ...],
    lc.PutaranFokus,
]:
    sesi_pemetaan = lc._sesi_bukti_pemetaan(bukti, putaran)
    ringkasan = lc._ringkas_kandidat(sesi_pemetaan)
    status = lc._status_putaran(
        putaran,
        bukti.level_aktif,
        (sesi.tanggal for sesi in sesi_pemetaan),
        ringkasan,
    )
    return sesi_pemetaan, ringkasan, status


def _status_satu_fokus(
    bukti: lc.BuktiSiklus,
    putaran: lc.PutaranSiklus,
    status: lc.StatusFokus,
    hari: date,
) -> Tuple[str, lc.RencanaBelajar]:
    """Minta reducer menilai satu fokus agar CTA global tidak meratakan tahap."""
    putaran_satu = replace(putaran, fokus=(status.kunci,))
    status_satu = lc.PutaranFokus(
        putaran.id,
        putaran.level,
        (status,),
    )
    rencana = lc._rencana_fokus(bukti, putaran_satu, status_satu, hari)
    if rencana is None:
        return "perlu_dipelajari", lc.RencanaBelajar("intervensi", "")

    status_reducer = (
        rencana.putaran.fokus[0].status
        if rencana.putaran is not None and rencana.putaran.fokus
        else status.status
    )
    if rencana.tindakan == "eskalasi":
        return "perlu_eskalasi", rencana
    if status_reducer == "bertahan":
        return "bertahan", rencana
    if status_reducer == "mulai_membaik":
        return "mulai_membaik", rencana
    if status_reducer == "perlu_diperkuat":
        return "perlu_diperkuat", rencana
    if rencana.tindakan == "latihan_terbimbing":
        return "latihan_terbimbing", rencana
    if rencana.tindakan == "penguatan":
        return "penguatan", rencana
    if rencana.tindakan in {"tunggu_evaluasi", "evaluasi"}:
        return "menunggu_evaluasi", rencana
    return "perlu_dipelajari", rencana


def _pemahaman(outcomes: Tuple[lc.OutcomeSiklus, ...]) -> Tuple[str, ...]:
    return tuple(
        sorted(
            {
                outcome.cek_pemahaman
                for outcome in outcomes
                if outcome.cek_pemahaman is not None
            }
        )
    )


def _bukti_fokus(
    bukti: lc.BuktiSiklus,
    putaran: lc.PutaranSiklus,
    kunci: lc.KunciFokus,
    sesi_pemetaan: Tuple[lc.SesiSiklus, ...],
) -> Tuple[BuktiFokusPerjalanan, ...]:
    hasil: List[BuktiFokusPerjalanan] = []
    for sesi in sesi_pemetaan:
        cocok = tuple(
            outcome
            for outcome in sesi.outcomes
            if lc._kunci_outcome(outcome) == kunci
        )
        if cocok:
            hasil.append(
                BuktiFokusPerjalanan(
                    sesi.tanggal,
                    sesi.id,
                    "pemetaan",
                    _pemahaman(cocok),
                )
            )

    for event in bukti.kejadian:
        if (
            event.putaran_id == putaran.id
            and event.jenis == "intervensi_selesai"
            and lc._kunci_event(event) == kunci
        ):
            hasil.append(
                BuktiFokusPerjalanan(event.tanggal, event.sesi_id, "intervensi")
            )

    for sesi in bukti.sesi:
        if (
            sesi.siswa_id != bukti.siswa_id
            or sesi.level != putaran.level
            or sesi.putaran_id != putaran.id
            or sesi.tujuan not in _JENIS_BUKTI
            or sesi.selesai is None
            or sesi.dibatalkan is not None
            or sesi.dikonfirmasi is None
        ):
            continue
        outcomes = lc._hasil_fokus(sesi, kunci)
        if outcomes:
            hasil.append(
                BuktiFokusPerjalanan(
                    sesi.tanggal,
                    sesi.id,
                    sesi.tujuan,
                    _pemahaman(outcomes),
                )
            )
    return tuple(sorted(hasil, key=lambda item: (item.tanggal, item.sesi_id or 0, item.jenis)))


def _bukti_fokus_otomatis(
    kunci: lc.KunciFokus,
    sesi_pemetaan: Tuple[lc.SesiSiklus, ...],
) -> Tuple[BuktiFokusPerjalanan, ...]:
    hasil = []
    for sesi in sesi_pemetaan:
        cocok = tuple(
            outcome
            for outcome in sesi.outcomes
            if lc._kunci_outcome(outcome) == kunci
        )
        if cocok:
            hasil.append(
                BuktiFokusPerjalanan(
                    sesi.tanggal,
                    sesi.id,
                    "pemetaan",
                    _pemahaman(cocok),
                )
            )
    return tuple(hasil)


def _fokus_aktif(
    bukti: lc.BuktiSiklus,
    putaran: Optional[lc.PutaranSiklus],
    status: lc.PutaranFokus,
    sesi_pemetaan: Tuple[lc.SesiSiklus, ...],
    rekomendasi: lc.RencanaBelajar,
    hari: date,
) -> Tuple[FokusPerjalanan, ...]:
    # Fokus persisted sah walau rekomendasi sedang tidak membawa putaran karena
    # sesi pemblokir. Fokus otomatis mengikuti keputusan reducer, bukan ambang
    # tanggal kedua di lapisan proyeksi.
    if putaran is None or not putaran.fokus:
        if rekomendasi.tindakan != "intervensi":
            return ()
        return tuple(
            FokusPerjalanan(
                item.kunci,
                "perlu_dipelajari",
                _bukti_fokus_otomatis(item.kunci, sesi_pemetaan),
            )
            for item in status.fokus[:2]
        )

    hasil = []
    for item in status.fokus[:2]:
        tahap, _ = _status_satu_fokus(bukti, putaran, item, hari)
        hasil.append(
            FokusPerjalanan(
                item.kunci,
                tahap,
                tuple(_hasil_saat_bukti(bukti, putaran, item.kunci, satu)
                      for satu in _bukti_fokus(bukti, putaran, item.kunci, sesi_pemetaan)),
            )
        )
    return tuple(hasil)


def _sebelum_penutup(
    event: lc.KejadianSiklus, penutup: lc.KejadianSiklus
) -> bool:
    return (event.tanggal, event.id) <= (penutup.tanggal, penutup.id)


def _tanggal_teks(nilai: Optional[str]) -> Optional[date]:
    if not nilai:
        return None
    try:
        return datetime.fromisoformat(nilai).date()
    except ValueError:
        return None


def _sesi_sebelum_penutup(
    bukti: lc.BuktiSiklus,
    sesi: lc.SesiSiklus,
    penutup: lc.KejadianSiklus,
) -> bool:
    konfirmasi = [
        event
        for event in bukti.kejadian
        if event.jenis == "hasil_dikonfirmasi"
        and event.putaran_id == penutup.putaran_id
        and (
            (sesi.konfirmasi_id is not None
             and event.konfirmasi_id == sesi.konfirmasi_id)
            or (sesi.konfirmasi_id is None and event.sesi_id == sesi.id)
        )
    ]
    if konfirmasi:
        return any(_sebelum_penutup(event, penutup) for event in konfirmasi)

    waktu = sesi.dikonfirmasi_pada or _tanggal_teks(sesi.dikonfirmasi)
    if waktu is None:
        waktu = sesi.selesai_pada or _tanggal_teks(sesi.selesai) or sesi.tanggal
    return waktu <= penutup.tanggal


def _sumber_histori(
    bukti: lc.BuktiSiklus,
    putaran: lc.PutaranSiklus,
    penutup: lc.KejadianSiklus,
) -> lc.BuktiSiklus:
    sesi = tuple(
        satu
        for satu in bukti.sesi
        if satu.siswa_id == bukti.siswa_id
        and satu.level == putaran.level
        and satu.putaran_id == putaran.id
        and satu.selesai is not None
        and satu.dikonfirmasi is not None
        and satu.dibatalkan is None
        and _sesi_sebelum_penutup(bukti, satu, penutup)
    )
    kejadian = tuple(
        sorted(
            (
                event
                for event in bukti.kejadian
                if event.putaran_id != putaran.id
                or _sebelum_penutup(event, penutup)
                or event.jenis == "konfirmasi_dibatalkan"
            ),
            key=lambda event: (event.tanggal, event.id),
        )
    )
    efektif = lc._putaran_dengan_override(putaran, kejadian)
    assert efektif is not None
    return replace(
        bukti,
        level_aktif=putaran.level,
        sesi=sesi,
        putaran=(efektif,),
        kejadian=kejadian,
    )


def _bukti_histori(
    bukti: lc.BuktiSiklus,
    putaran: lc.PutaranSiklus,
    bukti_terkini: lc.BuktiSiklus,
) -> Tuple[Tuple[BuktiFokusPerjalanan, ...], str]:
    hasil: List[BuktiFokusPerjalanan] = []
    invalidasi = [
        event
        for event in bukti.kejadian
        if event.putaran_id == putaran.id
        and event.jenis == "konfirmasi_dibatalkan"
    ]
    for event in invalidasi:
        sesi_aktif = next(
            (
                sesi
                for sesi in bukti_terkini.sesi
                if sesi.id == event.sesi_id
                and sesi.siswa_id == bukti.siswa_id
                and sesi.putaran_id == putaran.id
                and sesi.level == putaran.level
                and sesi.dikonfirmasi is not None
                and sesi.dibatalkan is None
            ),
            None,
        )
        hasil.append(
            BuktiFokusPerjalanan(
                event.tanggal,
                event.sesi_id,
                "bukti_dibatalkan",
                (),
                "riwayat_invalidasi"
                if sesi_aktif is not None
                else "perlu_konfirmasi_ulang",
            )
        )

    # Histori adalah ringkasan bukti aktif saat ini, bukan snapshot pada tanggal
    # penutupan. Event invalidasi tetap dipertahankan sebagai provenance.
    for sesi in bukti.sesi:
        if (
            sesi.siswa_id != bukti.siswa_id
            or sesi.putaran_id != putaran.id
            or sesi.level != putaran.level
            or sesi.selesai is None
            or sesi.dikonfirmasi is None
            or sesi.dibatalkan is not None
        ):
            continue
        hasil.append(
            BuktiFokusPerjalanan(
                sesi.tanggal,
                sesi.id,
                sesi.tujuan,
                _pemahaman(sesi.outcomes),
            )
        )
    masih_pending = any(item.status == "perlu_konfirmasi_ulang" for item in hasil)
    status = "perlu_konfirmasi_ulang" if masih_pending else (
        "tersedia" if hasil else "bukti_tidak_tersedia"
    )
    return tuple(sorted(hasil, key=lambda item: (item.tanggal, item.sesi_id or 0))), status


def _sumber_putaran(bukti, putaran):
    sesi = tuple(
        satu for satu in bukti.sesi
        if satu.siswa_id == bukti.siswa_id and satu.level == putaran.level
        and satu.putaran_id == putaran.id and satu.selesai is not None
        and satu.dikonfirmasi is not None and satu.dibatalkan is None
    )
    return replace(bukti, level_aktif=putaran.level, sesi=sesi)


def _hasil_saat_bukti(bukti, putaran, kunci, item):
    if item.jenis not in {"evaluasi", "checkpoint"}:
        return item
    sumber = _sumber_putaran(bukti, putaran)
    sebelum = replace(sumber, sesi=tuple(
        sesi for sesi in sumber.sesi
        if (sesi.tanggal, sesi.id) <= (item.tanggal, item.sesi_id or 0)
    ))
    if item.jenis == "evaluasi":
        evaluasi = lc._evaluasi_fokus(sebelum, putaran, kunci)
        hasil = next(("mulai_membaik" if baik else "perlu_diperkuat"
                      for sesi, baik in evaluasi if sesi.id == item.sesi_id), None)
    else:
        sesi_item = next(sesi for sesi in sebelum.sesi if sesi.id == item.sesi_id)
        rangkaian = replace(sebelum, sesi=tuple(
            sesi for sesi in sebelum.sesi
            if sesi.tujuan == "evaluasi" or (
                sesi.tujuan == "checkpoint" and sesi.occurrence == sesi_item.occurrence
            )
        ))
        terakhir, _ = lc._checkpoint_sukses(rangkaian, putaran, kunci)
        hasil = "bertahan" if terakhir == item.tanggal else None
    return replace(item, hasil=hasil)


def _fokus_histori(bukti, putaran, tanggal):
    sumber = _sumber_putaran(bukti, putaran)
    pemetaan, _, status = _ringkasan_dasar(sumber, putaran)
    return tuple(
        FokusPerjalanan(
            item.kunci, _status_satu_fokus(sumber, putaran, item, tanggal)[0],
            tuple(_hasil_saat_bukti(sumber, putaran, item.kunci, satu)
                  for satu in _bukti_fokus(sumber, putaran, item.kunci, pemetaan)),
        )
        for item in status.fokus
    )


def _histori_putaran(bukti: lc.BuktiSiklus) -> Tuple[HistoriPutaran, ...]:
    hasil = []
    for putaran in sorted(bukti.putaran, key=lambda item: (item.dibuka, item.id)):
        if putaran.siswa_id != bukti.siswa_id:
            continue
        penutup = sorted(
            (
                event
                for event in bukti.kejadian
                if event.putaran_id == putaran.id and event.jenis in _PENUTUP
            ),
            key=lambda event: (event.tanggal, event.id),
        )
        if not penutup:
            continue
        event = penutup[0]
        sumber = _sumber_histori(bukti, putaran, event)
        efektif = sumber.putaran[0]
        bukti_ringkas, status = _bukti_histori(sumber, efektif, bukti)
        hasil.append(
            HistoriPutaran(
                putaran.id,
                putaran.level,
                putaran.dibuka,
                event.tanggal,
                event.jenis,
                efektif.fokus[:2],
                bukti_ringkas,
                status,
                _fokus_histori(sumber, efektif, event.tanggal),
            )
        )
    return tuple(hasil)


def _catatan_bukti(
    bukti: lc.BuktiSiklus,
    putaran: Optional[lc.PutaranSiklus],
) -> Tuple[str, ...]:
    if putaran is None:
        return ()
    sesi_pending = {
        sesi.id
        for sesi in bukti.sesi
        if sesi.siswa_id == bukti.siswa_id
        and sesi.putaran_id == putaran.id
        and sesi.level == putaran.level
        and sesi.selesai is not None
        and sesi.dikonfirmasi is None
        and sesi.dibatalkan is None
    }
    dikoreksi = any(
        event.jenis == "konfirmasi_dibatalkan"
        and event.putaran_id == putaran.id
        and event.sesi_id in sesi_pending
        for event in bukti.kejadian
    )
    return ("Bukti dikoreksi; perlu konfirmasi ulang.",) if dikoreksi else ()


def perjalanan_belajar(
    bukti: lc.BuktiSiklus,
    siswa_id: int,
    hari_ini: Optional[date] = None,
) -> PerjalananBelajar:
    """Proyeksikan rekomendasi, tahap tiap fokus, dan histori tanpa mutasi."""
    from cycle_carry import bukti_lanjutan

    asli = bukti
    bukti = bukti_lanjutan(lc.tanpa_pilot(bukti))
    hari = hari_ini or date.today()
    rekomendasi = lc.rencana_berikutnya(asli, siswa_id, hari)
    putaran = lc._putaran_dengan_override(lc._putaran_aktif(bukti), bukti.kejadian)
    from cycle_representations import CATATAN_PEMISAHAN, bukti_satu_representasi
    terpilih = bukti_satu_representasi(bukti, putaran)
    catatan_representasi = (() if terpilih == bukti else (
        CATATAN_PEMISAHAN,
    ))
    bukti = terpilih
    sesi_pemetaan, _, status = _ringkasan_dasar(bukti, putaran)
    fokus = _fokus_aktif(
        bukti,
        putaran,
        status,
        sesi_pemetaan,
        rekomendasi,
        hari,
    )
    return PerjalananBelajar(
        rekomendasi,
        fokus,
        _histori_putaran(asli),
        None if putaran is None else putaran.id,
        status.tanggal_pemetaan,
        _catatan_bukti(bukti, putaran) + catatan_representasi
        + catatan_histori_beda_level(
            bukti,
            mulai_dari_awal=(
                rekomendasi.tindakan == "pemetaan"
                and bool(rekomendasi.putaran)
                and not rekomendasi.putaran.tanggal_pemetaan
            ),
        ),
    )
