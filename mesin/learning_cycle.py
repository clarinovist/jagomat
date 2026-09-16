"""Reducer murni untuk siklus belajar terpandu.

Modul ini tidak membaca atau menulis basis data. Lapisan penyimpanan mengubah
snapshot dan kejadian append-only menjadi struktur immutable di bawah ini.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Set, Tuple

from cycle_recovery import intervensi_setelah_gagal, bukti_setelah_intervensi
from cycle_representations import (
    bukti_satu_representasi, sesi_satu_representasi, satu_mode, sesi_bukti_sah,
)

KunciFokus = Tuple[str, str, Optional[str]]


@dataclass(frozen=True)
class OutcomeSiklus:
    template_id: str
    benar: Optional[bool]
    kode_final: Optional[str] = None
    malrule_id: Optional[str] = None
    dilewati: bool = False
    cek_pemahaman: Optional[str] = None
    target_fokus: Optional[KunciFokus] = None
    mode_representasi: str = "teks-v1"
    fingerprint_penyajian: Optional[str] = None
    fingerprint_matematis: Optional[str] = None


@dataclass(frozen=True)
class SesiSiklus:
    id: int
    siswa_id: int
    level: str
    tujuan: str
    tanggal: date
    dibuat: str = ""
    selesai: Optional[str] = None
    direview: Optional[str] = None
    dikonfirmasi: Optional[str] = None
    putaran_id: Optional[int] = None
    bagian_checkpoint: Optional[int] = None
    dibatalkan: Optional[str] = None
    outcomes: Tuple[OutcomeSiklus, ...] = ()
    target_fokus: Tuple[KunciFokus, ...] = ()
    occurrence: Optional[int] = None
    konfirmasi_id: Optional[int] = None
    selesai_pada: Optional[date] = None
    dikonfirmasi_pada: Optional[date] = None
    mode: str = "diagnostik"
    pola_tersedia: Tuple[str, ...] = ()
    format_jawaban: str = 'isian'


@dataclass(frozen=True)
class KejadianSiklus:
    id: int
    jenis: str
    tanggal: date
    putaran_id: Optional[int] = None
    sesi_id: Optional[int] = None
    konfirmasi_id: Optional[int] = None
    data: Tuple[Tuple[str, object], ...] = ()

    def nilai(self, kunci: str, bawaan=None):
        return dict(self.data).get(kunci, bawaan)


@dataclass(frozen=True)
class PutaranSiklus:
    id: int
    siswa_id: int
    level: str
    dibuka: date
    fokus: Tuple[KunciFokus, ...] = ()


@dataclass(frozen=True)
class BuktiSiklus:
    siswa_id: int
    level_aktif: str
    sesi: Tuple[SesiSiklus, ...] = ()
    putaran: Tuple[PutaranSiklus, ...] = ()
    kejadian: Tuple[KejadianSiklus, ...] = ()
    pendekatan_tersedia: Tuple[Tuple[KunciFokus, Tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class Intervensi:
    kode: str
    tindakan: str
    tahap_berikutnya: str


@dataclass(frozen=True)
class StatusFokus:
    kunci: KunciFokus
    status: str
    jumlah_sesi: int = 0
    terakhir: Optional[date] = None
    pendekatan_berikutnya: Optional[str] = None
    evaluasi_probe_minimum: int = 4
    checkpoint_probe_minimum: int = 3


@dataclass(frozen=True)
class PutaranFokus:
    id: Optional[int]
    level: str
    fokus: Tuple[StatusFokus, ...]
    tanggal_pemetaan: Tuple[date, ...] = ()


@dataclass(frozen=True)
class RencanaBelajar:
    tindakan: str
    alasan: str
    putaran: Optional[PutaranFokus] = None
    sesi_id: Optional[int] = None
    kandidat: Tuple[KunciFokus, ...] = ()
    intervensi: Optional[Intervensi] = None
    tersedia_pada: Optional[date] = None
    jumlah_probe_minimum: int = 0
    bagian_checkpoint: Optional[int] = None


_INTERVENSI = {
    "B": Intervensi("B", "Tandai informasi dan ucapkan ulang yang ditanya", "latihan_terbimbing"),
    "K": Intervensi("K", "Gunakan konsep konkret atau visual dan contoh terbimbing", "latihan_terbimbing"),
    "H": Intervensi("H", "Tulis langkah dan periksa ulang perhitungan", "latihan_terbimbing"),
    "E": Intervensi("E", "Cocokkan hasil kerja dengan jawaban akhir", "latihan_terbimbing"),
    "N": Intervensi("N", "Tanyakan: dapat dari mana?", "probe_pemahaman"),
    "T": Intervensi("T", "Kenalkan materi dengan contoh sederhana", "pengenalan"),
}


def intervensi_untuk(kode: str) -> Intervensi:
    """Kembalikan tindakan berbeda untuk setiap kode diagnosis."""
    try:
        return _INTERVENSI[kode]
    except KeyError as exc:
        raise ValueError("kode diagnosis tidak dikenal") from exc


def _putaran_aktif(bukti: BuktiSiklus) -> Optional[PutaranSiklus]:
    tertutup = {
        e.putaran_id
        for e in bukti.kejadian
        if e.jenis in {"putaran_ditutup", "diganti_level", "override_ditutup"}
    }
    kandidat = [
        p for p in bukti.putaran if p.level == bukti.level_aktif and p.id not in tertutup
    ]
    return max(kandidat, key=lambda p: (p.dibuka, p.id)) if kandidat else None


def _sesi_pemblokir(
    bukti: BuktiSiklus, putaran: Optional[PutaranSiklus]
) -> List[SesiSiklus]:
    if putaran is None:
        return []
    return sorted(
        (
            s
            for s in bukti.sesi
            if s.siswa_id == bukti.siswa_id
            and s.format_jawaban == 'isian'
            and s.putaran_id == putaran.id
            and s.tujuan != "bebas"
            and s.dibatalkan is None
            and s.level == putaran.level == bukti.level_aktif
        ),
        key=lambda s: (s.dibuat, s.tanggal, s.id),
    )


def sesi_berjalan(bukti: BuktiSiklus) -> Optional[SesiSiklus]:
    """Sesi terpandu belum selesai, memakai metadata saja tanpa outcome.

    Beranda anak dan reducer berbagi prioritas ini. Tidak membutuhkan fokus,
    alasan internal, atau snapshot jawaban untuk memilih sesi yang sudah ada.
    """
    return next(
        (s for s in _sesi_pemblokir(bukti, _putaran_aktif(bukti))
         if s.selesai is None),
        None,
    )


def _sesi_bukti_pemetaan(
    bukti: BuktiSiklus, putaran: Optional[PutaranSiklus]
) -> Tuple[SesiSiklus, ...]:
    bukti = bukti_satu_representasi(bukti, putaran)
    opt_in = {
        (e.sesi_id, e.konfirmasi_id)
        for e in bukti.kejadian
        if e.jenis == "sertakan_pemetaan"
        and e.sesi_id is not None
        and e.konfirmasi_id is not None
    }
    hasil = []
    for sesi in bukti.sesi:
        if sesi.format_jawaban != 'isian' or sesi.siswa_id != bukti.siswa_id or sesi.level != bukti.level_aktif:
            continue
        if sesi.dibatalkan is not None or sesi.selesai is None or sesi.dikonfirmasi is None:
            continue
        if sesi.tujuan in {"pemetaan"} and (
            putaran is None or sesi.putaran_id == putaran.id
        ):
            hasil.append(sesi)
        elif (
            sesi.tujuan == "bebas"
            and sesi.konfirmasi_id is not None
            and (sesi.id, sesi.konfirmasi_id) in opt_in
        ):
            hasil.append(sesi)
    return tuple(hasil)


def _kunci_outcome(outcome: OutcomeSiklus) -> Optional[KunciFokus]:
    if outcome.dilewati:
        return None
    if outcome.kode_final in {"K", "H"}:
        return (outcome.template_id, outcome.kode_final, outcome.malrule_id)
    if outcome.kode_final == "N" and outcome.cek_pemahaman in {"ragu", "menghafal"}:
        return (outcome.template_id, "K", outcome.malrule_id)
    return None


def _ringkas_kandidat(
    sesi: Iterable[SesiSiklus],
) -> Tuple[Tuple[KunciFokus, int, date], ...]:
    sesi_per_kunci: Dict[KunciFokus, Set[int]] = {}
    terakhir: Dict[KunciFokus, date] = {}
    for satu in sesi_satu_representasi(sesi):
        dalam_sesi = {
            kunci for kunci in (_kunci_outcome(o) for o in satu.outcomes) if kunci
        }
        for kunci in dalam_sesi:
            sesi_per_kunci.setdefault(kunci, set()).add(satu.id)
            terakhir[kunci] = max(terakhir.get(kunci, satu.tanggal), satu.tanggal)
    hasil = [
        (kunci, len(sesi_ids), terakhir[kunci])
        for kunci, sesi_ids in sesi_per_kunci.items()
    ]
    return tuple(
        sorted(
            hasil,
            key=lambda item: (
                -item[1],
                0 if item[0][1] == "K" else 1,
                -item[2].toordinal(),
                item[0],
            ),
        )
    )


def _status_putaran(
    putaran: Optional[PutaranSiklus],
    level: str,
    tanggal: Iterable[date],
    ringkasan: Tuple[Tuple[KunciFokus, int, date], ...],
) -> PutaranFokus:
    kunci_tersimpan = putaran.fokus if putaran and putaran.fokus else tuple(
        item[0] for item in ringkasan if item[1] >= 2
    )[:2]
    lookup = {kunci: (jumlah, terakhir) for kunci, jumlah, terakhir in ringkasan}
    fokus = tuple(
        StatusFokus(
            kunci,
            "perlu_dipelajari",
            lookup.get(kunci, (0, None))[0],
            lookup.get(kunci, (0, None))[1],
        )
        for kunci in kunci_tersimpan[:2]
    )
    return PutaranFokus(
        None if putaran is None else putaran.id,
        level,
        fokus,
        tuple(sorted(set(tanggal))),
    )


def _urut_anchor(
    ringkasan: Tuple[Tuple[KunciFokus, int, date], ...]
) -> Tuple[KunciFokus, ...]:
    pantau = [item for item in ringkasan if item[1] == 1]
    pantau.sort(
        key=lambda item: (
            0 if item[0][1] == "K" else 1,
            -item[2].toordinal(),
            item[0],
        )
    )
    return tuple(item[0] for item in pantau)


def _putaran_dengan_override(
    putaran: Optional[PutaranSiklus], kejadian: Tuple[KejadianSiklus, ...]
) -> Optional[PutaranSiklus]:
    if putaran is None:
        return None
    pertama_intervensi = min(
        (e.id for e in kejadian
         if e.putaran_id == putaran.id and e.jenis == "intervensi_selesai"),
        default=float("inf"),
    )
    override = [
        e for e in kejadian
        if e.putaran_id == putaran.id and e.jenis == "fokus_diubah"
        and e.id < pertama_intervensi
    ]
    if override:
        fokus = tuple(override[-1].nilai("fokus", ()))[:2]
        return replace(putaran, fokus=fokus)
    return putaran


def _hasil_fokus(sesi: SesiSiklus, kunci: KunciFokus) -> Tuple[OutcomeSiklus, ...]:
    """Ambil probe hanya bila sesi menyatakan target fokus kanonis itu.

    Outcome benar memang tidak membawa kode/malrule, sehingga template saja
    tidak cukup untuk membedakan dua miskonsepsi pada template yang sama.
    Metadata kosong adalah default aman: sesi tidak diklaim sebagai probe.
    """
    if kunci not in sesi.target_fokus:
        return ()
    target_template = tuple(
        target for target in sesi.target_fokus if target[0] == kunci[0]
    )
    return tuple(
        outcome
        for outcome in sesi.outcomes
        if outcome.template_id == kunci[0]
        and not outcome.dilewati
        and (
            outcome.target_fokus == kunci
            or (outcome.target_fokus is None and len(target_template) == 1)
        )
    )


def _lulus(outcomes: Tuple[OutcomeSiklus, ...], minimum: int, semua_benar: bool = False) -> bool:
    if len(outcomes) < minimum or not satu_mode(outcomes):
        return False
    benar = sum(o.benar is True for o in outcomes)
    rasio_ok = benar == len(outcomes) if semua_benar else benar / len(outcomes) >= 0.75
    return (
        rasio_ok
        and all(o.kode_final != "K" for o in outcomes)
        and all(o.cek_pemahaman == "bisa_menjelaskan" for o in outcomes)
    )


def _evaluasi_fokus(
    bukti: BuktiSiklus, putaran: PutaranSiklus, kunci: KunciFokus
) -> Tuple[Tuple[SesiSiklus, bool], ...]:
    bukti = bukti_satu_representasi(bukti, putaran)
    hasil = []
    for sesi in sorted(bukti.sesi, key=lambda s: (s.tanggal, s.id)):
        if (
            sesi.putaran_id == putaran.id
            and sesi.siswa_id == bukti.siswa_id
            and sesi.level == putaran.level == bukti.level_aktif
            and sesi.selesai is not None
            and sesi.tujuan == "evaluasi"
            and sesi.dibatalkan is None
            and sesi.dikonfirmasi is not None
        ):
            outcomes = _hasil_fokus(sesi, kunci)
            if len(outcomes) >= 4:
                hasil.append((sesi, _lulus(outcomes, 4)))
    return tuple(hasil)


def _checkpoint_sukses(
    bukti: BuktiSiklus, putaran: PutaranSiklus, kunci: KunciFokus
) -> Tuple[Optional[date], Tuple[int, ...]]:
    """Nilai checkpoint per occurrence dan fokus kanonis.

    Dua bagian dari occurrence berbeda tidak pernah dipasangkan. Metadata
    occurrence kosong tidak cukup untuk membuktikan checkpoint baru.
    """
    bukti = bukti_satu_representasi(bukti, putaran)
    evaluasi = _evaluasi_fokus(bukti, putaran, kunci)
    if not evaluasi or not evaluasi[-1][1]:
        return None, ()
    evaluasi_terakhir = evaluasi[-1][0]
    evaluasi_sah = (evaluasi_terakhir,)
    per_occurrence: Dict[int, Dict[int, SesiSiklus]] = {}
    for sesi in sorted(bukti.sesi, key=lambda s: (s.tanggal, s.id)):
        if (
            sesi.putaran_id != putaran.id
            or sesi.siswa_id != bukti.siswa_id
            or sesi.level != putaran.level
            or (sesi.tanggal, sesi.id) <= (evaluasi_terakhir.tanggal, evaluasi_terakhir.id)
            or sesi.tujuan != "checkpoint"
            or sesi.dibatalkan is not None
            or sesi.dikonfirmasi is None
            or sesi.bagian_checkpoint not in {1, 2}
            or sesi.occurrence is None
            or kunci not in sesi.target_fokus
        ):
            continue
        per_occurrence.setdefault(sesi.occurrence, {})[int(sesi.bagian_checkpoint)] = sesi

    sukses: List[date] = []
    occurrence_aktif: Optional[int] = None
    bagian_aktif: Tuple[int, ...] = ()
    for occurrence in sorted(per_occurrence):
        bagian = per_occurrence[occurrence]
        if set(bagian) == {1, 2}:
            outcomes = tuple(
                outcome
                for nomor in (1, 2)
                for outcome in _hasil_fokus(bagian[nomor], kunci)
            )
            awal = min(s.tanggal for s in bagian.values())
            cocok = any(s.tanggal <= awal and satu_mode((*_hasil_fokus(s, kunci), *outcomes))
                        for s in evaluasi_sah)
            if cocok and _lulus(outcomes, 3, semua_benar=True):
                sukses.append(max(sesi.tanggal for sesi in bagian.values()))
            continue
        occurrence_aktif = occurrence
        bagian_aktif = tuple(sorted(bagian))

    if occurrence_aktif is None and per_occurrence:
        occurrence_aktif = max(per_occurrence) + 1
    return (max(sukses) if sukses else None, bagian_aktif)


def _pendekatan_berikutnya(
    bukti: BuktiSiklus, putaran: PutaranSiklus, kunci: KunciFokus
) -> Optional[str]:
    tersedia = dict(bukti.pendekatan_tersedia).get(kunci, ())
    dipakai = {
        e.nilai("pendekatan_id")
        for e in bukti.kejadian
        if e.putaran_id == putaran.id
        and e.jenis == "intervensi_selesai"
        and tuple(e.nilai("fokus", ())) == kunci
    }
    return next((p for p in tersedia if p not in dipakai), None)


def _kunci_event(event: KejadianSiklus) -> Tuple[object, ...]:
    fokus = event.nilai("fokus", ())
    return tuple(fokus) if isinstance(fokus, tuple) else ()


def _intervensi_selesai(
    bukti: BuktiSiklus, putaran: PutaranSiklus, kunci: KunciFokus
) -> bool:
    return any(
        e.putaran_id == putaran.id
        and e.jenis == "intervensi_selesai"
        and _kunci_event(e) == kunci
        for e in bukti.kejadian
    )


def _sesi_tahap_fokus(
    bukti: BuktiSiklus,
    putaran: PutaranSiklus,
    tujuan: str,
    kunci: KunciFokus,
) -> Tuple[SesiSiklus, ...]:
    return tuple(
        sesi
        for sesi in bukti.sesi
        if sesi.putaran_id == putaran.id
        and sesi.tujuan == tujuan
        and sesi.dibatalkan is None
        and sesi.dikonfirmasi is not None
        and kunci in sesi.target_fokus
    )


def _dasar_jeda_evaluasi(sesi: SesiSiklus) -> date:
    if sesi.selesai_pada is None or sesi.dikonfirmasi_pada is None:
        raise ValueError("waktu selesai dan konfirmasi penguatan wajib berupa tanggal domain")
    return max(sesi.selesai_pada, sesi.dikonfirmasi_pada)


def _rencana_fokus(
    bukti: BuktiSiklus,
    putaran: PutaranSiklus,
    status_awal: PutaranFokus,
    hari: date,
) -> Optional[RencanaBelajar]:
    bukti = bukti_satu_representasi(bukti, putaran)
    statuses = []
    evaluasi_per_fokus = {}
    checkpoint_per_fokus = {}
    pemulihan_per_fokus = {}
    for fokus in status_awal.fokus:
        evaluasi = _evaluasi_fokus(bukti, putaran, fokus.kunci)
        evaluasi_per_fokus[fokus.kunci] = evaluasi
        pemulihan_per_fokus[fokus.kunci] = intervensi_setelah_gagal(
            bukti, putaran, fokus.kunci, evaluasi
        )
        checkpoint = _checkpoint_sukses(bukti, putaran, fokus.kunci)
        checkpoint_per_fokus[fokus.kunci] = checkpoint
        status = fokus.status
        pendekatan = None
        if evaluasi:
            status = "mulai_membaik" if evaluasi[-1][1] else "perlu_diperkuat"
        if checkpoint[0] is not None:
            status = "bertahan"
        if evaluasi and not evaluasi[-1][1]:
            pendekatan = _pendekatan_berikutnya(bukti, putaran, fokus.kunci)
        statuses.append(replace(fokus, status=status, pendekatan_berikutnya=pendekatan))
    status_putaran = replace(status_awal, fokus=tuple(statuses))

    # Kekambuhan wajib cocok dengan seluruh kunci kanonis, bukan template saja.
    for fokus in statuses:
        if fokus.status != "bertahan":
            continue
        tanggal_checkpoint = checkpoint_per_fokus[fokus.kunci][0]
        sesi_baru = [
            sesi
            for sesi in sesi_bukti_sah(bukti, putaran)
            if tanggal_checkpoint is not None
            and sesi.tanggal > tanggal_checkpoint
            and sesi.dikonfirmasi is not None
        ]
        kambuh = any(
            _kunci_outcome(outcome) == fokus.kunci
            for sesi in sesi_baru
            for outcome in sesi.outcomes
        )
        pola_gagal = {
            sesi.id
            for sesi in sesi_baru
            if fokus.kunci in sesi.target_fokus
            and any(
                outcome.template_id == fokus.kunci[0]
                and outcome.benar is False
                for outcome in sesi.outcomes
            )
        }
        if kambuh or len(pola_gagal) >= 2:
            baru = PutaranFokus(
                None,
                putaran.level,
                (replace(fokus, status="perlu_dipelajari"),),
            )
            return RencanaBelajar(
                "putaran_baru", "Fokus bertahan menunjukkan kekambuhan", putaran=baru
            )

    gagal_terbaru = []
    for fokus in statuses:
        beruntun = 0
        for _, lulus in reversed(evaluasi_per_fokus[fokus.kunci]):
            if lulus:
                break
            beruntun += 1
        if beruntun:
            gagal_terbaru.append((fokus, beruntun))
    if any(
        jumlah >= 2 or (fokus.pendekatan_berikutnya is None
                        and pemulihan_per_fokus[fokus.kunci] is None)
        for fokus, jumlah in gagal_terbaru
    ):
        return RencanaBelajar(
            "eskalasi",
            "Evaluasi gagal berulang atau pendekatan alternatif tidak tersedia",
            putaran=status_putaran,
        )

    # Setiap fokus membentuk kandidat sendiri; nomor lebih kecil lebih prioritas.
    kandidat_rencana = []
    for urutan, fokus in enumerate(statuses):
        kunci = fokus.kunci
        evaluasi = evaluasi_per_fokus[kunci]
        checkpoint_terakhir, bagian = checkpoint_per_fokus[kunci]

        pemulihan = pemulihan_per_fokus[kunci]
        bukti_latihan = bukti_setelah_intervensi(bukti, pemulihan)
        if evaluasi and not evaluasi[-1][1] and pemulihan is None:
            kandidat_rencana.append(
                (
                    6,
                    urutan,
                    RencanaBelajar(
                        "intervensi",
                        "Evaluasi perlu diperkuat dengan pendekatan berbeda",
                        putaran=status_putaran,
                        kandidat=(kunci,),
                        intervensi=intervensi_untuk(kunci[1]),
                    ),
                )
            )
            continue

        if fokus.status in {"mulai_membaik", "bertahan"}:
            dasar = checkpoint_terakhir or max(
                sesi.tanggal for sesi, lulus in evaluasi if lulus
            )
            jatuh_tempo = dasar + timedelta(days=28)
            bagian_aktif = set(bagian)
            if bagian_aktif == {1}:
                kandidat_rencana.append(
                    (
                        8,
                        urutan,
                        RencanaBelajar(
                            "checkpoint",
                            "Lengkapi bagian kedua checkpoint",
                            putaran=status_putaran,
                            kandidat=(kunci,),
                            jumlah_probe_minimum=3,
                            bagian_checkpoint=2,
                        ),
                    )
                )
            elif hari >= jatuh_tempo:
                kandidat_rencana.append(
                    (
                        8,
                        urutan,
                        RencanaBelajar(
                            "checkpoint",
                            "Checkpoint fokus sudah jatuh tempo",
                            putaran=status_putaran,
                            kandidat=(kunci,),
                            jumlah_probe_minimum=3,
                            bagian_checkpoint=1,
                        ),
                    )
                )
            else:
                kandidat_rencana.append(
                    (
                        99,
                        urutan,
                        RencanaBelajar(
                            "tunggu_checkpoint",
                            "Checkpoint belum jatuh tempo",
                            putaran=status_putaran,
                            kandidat=(kunci,),
                            tersedia_pada=jatuh_tempo,
                        ),
                    )
                )
            continue

        if not _intervensi_selesai(bukti, putaran, kunci):
            kandidat_rencana.append(
                (
                    6,
                    urutan,
                    RencanaBelajar(
                        "intervensi",
                        "Fokus memerlukan tindakan sebelum latihan",
                        putaran=status_putaran,
                        kandidat=(kunci,),
                        intervensi=intervensi_untuk(kunci[1]),
                    ),
                )
            )
            continue

        if not _sesi_tahap_fokus(bukti_latihan, putaran, "latihan_terbimbing", kunci):
            kandidat_rencana.append(
                (
                    7,
                    urutan,
                    RencanaBelajar(
                        "latihan_terbimbing",
                        "Intervensi dilanjutkan contoh terbimbing",
                        putaran=status_putaran,
                        kandidat=(kunci,),
                    ),
                )
            )
            continue

        penguatan = _sesi_tahap_fokus(bukti_latihan, putaran, "penguatan", kunci)
        if not penguatan:
            kandidat_rencana.append(
                (
                    7,
                    urutan,
                    RencanaBelajar(
                        "penguatan",
                        "Latihan terbimbing dilanjutkan penguatan mandiri",
                        putaran=status_putaran,
                        kandidat=(kunci,),
                    ),
                )
            )
            continue

        dasar = max(_dasar_jeda_evaluasi(sesi) for sesi in penguatan)
        jatuh_tempo = dasar + timedelta(days=3)
        tindakan = "evaluasi" if hari >= jatuh_tempo else "tunggu_evaluasi"
        kandidat_rencana.append(
            (
                5 if tindakan == "evaluasi" else 99,
                urutan,
                RencanaBelajar(
                    tindakan,
                    "Evaluasi berjeda sudah jatuh tempo"
                    if tindakan == "evaluasi"
                    else "Evaluasi tersedia tiga hari setelah penguatan",
                    putaran=status_putaran,
                    kandidat=(kunci,),
                    tersedia_pada=None if tindakan == "evaluasi" else jatuh_tempo,
                    jumlah_probe_minimum=4 if tindakan == "evaluasi" else 0,
                ),
            )
        )

    if not kandidat_rencana:
        return None
    return min(kandidat_rencana, key=lambda item: (item[0], item[1]))[2]


def _materi_t(
    bukti: BuktiSiklus, sesi_pemetaan: Tuple[SesiSiklus, ...]
) -> Tuple[Tuple[KunciFokus, date], ...]:
    hasil: List[Tuple[KunciFokus, date]] = []
    for sesi in sorted(sesi_pemetaan, key=lambda s: (s.tanggal, s.id)):
        for outcome in sesi.outcomes:
            if outcome.kode_final == "T":
                item = ((outcome.template_id, "T", None), sesi.tanggal)
                if item[0] not in {kunci for kunci, _ in hasil}:
                    hasil.append(item)
    return tuple(hasil)


def _progres_materi_t(
    bukti: BuktiSiklus,
    putaran: Optional[PutaranSiklus],
    materi: Tuple[Tuple[KunciFokus, date], ...],
) -> Tuple[Tuple[KunciFokus, ...], Tuple[KunciFokus, ...]]:
    """Pisahkan materi yang belum dikenalkan dan yang menunggu probe sah."""
    belum_dikenalkan = []
    menunggu_probe = []
    for kunci, tanggal_bukti in materi:
        pengenalan = [
            event
            for event in bukti.kejadian
            if event.jenis == "pengenalan_selesai"
            and event.putaran_id == (None if putaran is None else putaran.id)
            and event.tanggal >= tanggal_bukti
            and _kunci_event(event) == kunci
        ]
        if not pengenalan:
            belum_dikenalkan.append(kunci)
            continue
        tanggal_pengenalan = max(event.tanggal for event in pengenalan)
        probe_sah = any(
            sesi.tujuan == "pemetaan"
            and sesi.dikonfirmasi is not None
            and sesi.dibatalkan is None
            and sesi.tanggal > tanggal_pengenalan
            and kunci in sesi.target_fokus
            for sesi in bukti.sesi
        )
        if not probe_sah:
            menunggu_probe.append(kunci)
    return tuple(belum_dikenalkan), tuple(menunggu_probe)


def rencana_berikutnya(
    bukti: BuktiSiklus, siswa_id: int, hari_ini: Optional[date] = None
) -> RencanaBelajar:
    """Turunkan satu rekomendasi deterministik tanpa side effect."""
    if siswa_id != bukti.siswa_id:
        raise ValueError("bukti bukan milik siswa")
    from cycle_carry import bukti_lanjutan
    hari = hari_ini or date.today()
    putaran = _putaran_dengan_override(_putaran_aktif(bukti), bukti.kejadian)

    pemblokir = _sesi_pemblokir(bukti, putaran)
    sesi = sesi_berjalan(bukti)
    if sesi is not None:
        return RencanaBelajar(
            "lanjutkan_sesi", "Sesi terpandu aktif belum selesai", sesi_id=sesi.id
        )
    belum_sah = [
        s for s in pemblokir if s.selesai is not None and s.dikonfirmasi is None
    ]
    if belum_sah:
        sesi = belum_sah[0]
        return RencanaBelajar(
            "konfirmasi_hasil", "Hasil sesi belum dikonfirmasi guru", sesi_id=sesi.id
        )

    # Prioritas sesi asli diputuskan sebelum proyeksi referensi historis.
    bukti = bukti_satu_representasi(bukti_lanjutan(bukti), putaran)
    sesi_pemetaan = _sesi_bukti_pemetaan(bukti, putaran)
    tanggal = tuple(s.tanggal for s in sesi_pemetaan)
    ringkasan = _ringkas_kandidat(sesi_pemetaan)
    status = _status_putaran(putaran, bukti.level_aktif, tanggal, ringkasan)
    anchor = _urut_anchor(ringkasan)

    # Fokus yang sudah dipersistenkan menandai pemetaan putaran telah ditutup.
    # Kandidat otomatis tetap harus menunggu tiga tanggal pemetaan lengkap.
    if putaran is not None and putaran.fokus and status.fokus:
        rencana_fokus = _rencana_fokus(bukti, putaran, status, hari)
        if rencana_fokus is not None:
            return rencana_fokus

    materi_t = _materi_t(bukti, sesi_pemetaan)
    belum_dikenalkan, menunggu_probe = _progres_materi_t(
        bukti, putaran, materi_t
    )

    if len(set(tanggal)) < 3:
        if tanggal and max(tanggal) >= hari:
            return RencanaBelajar(
                "tunggu_pemetaan",
                "Pemetaan harus dilakukan pada tanggal berbeda",
                putaran=status,
                kandidat=anchor[:5],
                tersedia_pada=max(tanggal) + timedelta(days=1),
            )
        return RencanaBelajar(
            "pemetaan",
            "Lanjutkan pemetaan level aktif",
            putaran=status,
            kandidat=anchor[:5],
        )

    if status.fokus:
        fokus = status.fokus[0]
        return RencanaBelajar(
            "intervensi",
            "Fokus berulang pada minimal dua sesi",
            putaran=status,
            intervensi=intervensi_untuk(fokus.kunci[1]),
        )
    if anchor:
        return RencanaBelajar(
            "probe_diagnostik",
            "Kandidat pantauan masih memerlukan bukti sesi kedua",
            putaran=status,
            kandidat=anchor[:5],
        )
    if menunggu_probe:
        return RencanaBelajar(
            "probe_setelah_pengenalan",
            "Materi yang dikenalkan harus diprobe sampai hasil terkonfirmasi",
            putaran=status,
            kandidat=menunggu_probe[:5],
        )
    if belum_dikenalkan:
        return RencanaBelajar(
            "pengenalan",
            "Materi baru perlu dikenalkan sebelum probe",
            putaran=status,
            kandidat=belum_dikenalkan[:1],
            intervensi=intervensi_untuk("T"),
        )
    return RencanaBelajar("mixed_maintenance", "Tidak ada fokus aktif", putaran=status)


@dataclass(frozen=True)
class StatusPolaMateri:
    template_id: str
    status: str
    sesi_ids: Tuple[int, ...] = ()
    terakhir: Optional[date] = None


@dataclass(frozen=True)
class StatusTargetMateri:
    id: str
    status: str
    pola: Tuple[StatusPolaMateri, ...]


def _lulus_pola_materi(outcomes, minimum):
    """Pakai ambang reducer, dengan penolakan eksplisit outcome belum jelas."""
    return (_lulus(outcomes, minimum)
            and all(not o.dilewati and (
                (o.benar is True and o.kode_final is None)
                or (o.benar is False and o.kode_final in {"B", "H", "E"})
            ) for o in outcomes))


def _sidik_beragam(outcomes, minimum):
    """Parafrase atau pengulangan parameter sama tidak menjadi probe baru."""
    sidik = tuple(o.fingerprint_matematis for o in outcomes)
    return (len(sidik) >= minimum and all(sidik)
            and len(set(sidik)) == len(sidik))


def _sesi_peta_materi(bukti, hari):
    """Bukti seluruh target kelas aktif; bukan hanya dua fokus putaran aktif."""
    opt_in = {(e.sesi_id, e.konfirmasi_id) for e in bukti.kejadian
              if e.jenis == "sertakan_pemetaan" and e.konfirmasi_id is not None}
    putaran = {p.id for p in bukti.putaran
               if p.siswa_id == bukti.siswa_id and p.level == bukti.level_aktif}
    # Kembali ke kelas lama tidak menghidupkan sertifikasi kelas lama.
    batas = max((e.tanggal for e in bukti.kejadian if e.jenis == "diganti_level"), default=None)
    return tuple(s for s in bukti.sesi
                 if s.siswa_id == bukti.siswa_id and s.level == bukti.level_aktif
                 and s.format_jawaban == 'isian'
                 and s.mode == "diagnostik" and s.dibatalkan is None
                 and s.selesai is not None and s.dikonfirmasi is not None
                 and s.konfirmasi_id is not None and s.tanggal <= hari
                 and (batas is None or s.tanggal > batas)
                 and ((s.tujuan == "bebas" and (s.id, s.konfirmasi_id) in opt_in)
                      or (s.tujuan in {"pemetaan", "evaluasi", "checkpoint"}
                          and s.putaran_id in putaran)))


def _pola_terkoreksi(bukti):
    """Invalidasi bukan hasil buruk, tetapi bukti lama tidak lagi cukup pasti."""
    ids = {e.sesi_id for e in bukti.kejadian if e.jenis == "konfirmasi_dibatalkan"}
    # Koreksi drill/latihan terbimbing tidak menginvalidasi bukti penguasaan.
    opt_in = {e.sesi_id for e in bukti.kejadian if e.jenis == "sertakan_pemetaan"}
    batas = max((e.tanggal for e in bukti.kejadian if e.jenis == "diganti_level"), default=None)
    return frozenset(t for s in bukti.sesi
                     if s.id in ids and s.siswa_id == bukti.siswa_id
                     and s.level == bukti.level_aktif and s.dibatalkan is None
                     and s.format_jawaban == 'isian'
                     and s.mode == "diagnostik" and (batas is None or s.tanggal > batas)
                     and (s.tujuan in {"pemetaan", "evaluasi", "checkpoint"}
                          or (s.tujuan == "bebas" and s.id in opt_in))
                     and s.dikonfirmasi is None
                     for t in s.pola_tersedia)


def _pola_fokus_tertahan(bukti, hari):
    """Dua miskonsepsi satu pola tidak boleh lulus karena salah satunya pulih."""
    terbaru = {}
    batas = max((e.tanggal for e in bukti.kejadian if e.jenis == "diganti_level"), default=None)
    for p in sorted(bukti.putaran, key=lambda p: (p.dibuka, p.id)):
        if (p.siswa_id != bukti.siswa_id or p.level != bukti.level_aktif
                or (batas is not None and p.dibuka <= batas)):
            continue
        efektif = _putaran_dengan_override(p, bukti.kejadian)
        for kunci in efektif.fokus:
            terbaru[kunci] = efektif
    tertahan = set()
    # Fokus otomatis yang sudah disarankan juga belum selesai hanya karena
    # ada latihan benar berikutnya; pemulihan tetap mengikuti reducer fokus.
    aktif = _putaran_aktif(bukti)
    kandidat = _ringkas_kandidat(_sesi_bukti_pemetaan(bukti, aktif))
    tertahan.update(k[0] for k, jumlah, _ in kandidat if jumlah >= 2 and k not in terbaru)
    for kunci, p in terbaru.items():
        status = PutaranFokus(p.id, p.level, (StatusFokus(kunci, "perlu_dipelajari"),))
        rencana = _rencana_fokus(bukti, replace(p, fokus=(kunci,)), status, hari)
        baik = (rencana is not None and rencana.putaran is not None
                and rencana.tindakan != "putaran_baru"
                and rencana.putaran.fokus[0].status in {"mulai_membaik", "bertahan"})
        if not baik:
            tertahan.add(kunci[0])
    return frozenset(tertahan)


def _nilai_pola_materi(template_id, sesi, bukti, hari, tertahan, dikoreksi):
    relevan = tuple(s for s in sesi
                    if any(o.template_id == template_id and not o.dilewati for o in s.outcomes))
    if not relevan:
        return StatusPolaMateri(template_id, "perlu_cek" if template_id in dikoreksi else "belum_dinilai")
    # Pelewatan seluruh probe baru tidak membuktikan gagal, tetapi jangan
    # tampilkan sertifikasi lama seolah pemeriksaan terbaru sudah berhasil.
    pemeriksaan_terbaru = max(
        (s for s in sesi if any(o.template_id == template_id for o in s.outcomes)
         and (s.tujuan in {"pemetaan", "bebas"}
              or any(k[0] == template_id for k in s.target_fokus))),
        key=lambda s: (s.tanggal, s.id), default=None,
    )
    if pemeriksaan_terbaru is not None:
        probe = tuple(o for o in pemeriksaan_terbaru.outcomes if o.template_id == template_id)
        if probe and all(o.dilewati for o in probe):
            return StatusPolaMateri(template_id, "perlu_cek", (pemeriksaan_terbaru.id,), pemeriksaan_terbaru.tanggal)
    # Mode terbaru dipilih sesudah palang bukti; mode ambigu tidak boleh kembali
    # ke mode lama yang lebih menguntungkan.
    terpilih = sesi_satu_representasi(relevan)
    relevan = tuple(s for s in terpilih
                    if any(o.template_id == template_id and not o.dilewati for o in s.outcomes))
    if not relevan:
        return StatusPolaMateri(template_id, "perlu_cek")
    urut = sorted(relevan, key=lambda s: (s.tanggal, s.id))
    # Soal pembanding evaluasi/checkpoint boleh menjadi catatan paparan, tetapi
    # tidak mengubah kelulusan atau tanggal bukti pola lain.
    pemetaan = []
    keberhasilan = None
    penghalang = None
    dipakai = ()
    putaran = {p.id: p for p in bukti.putaran}
    for s in urut:
        outcomes = tuple(o for o in s.outcomes if o.template_id == template_id and not o.dilewati)
        if s.tujuan in {"pemetaan", "bebas"}:
            pemetaan.append(s)
            # Dua pemeriksaan terbaru, bukan mengambil empat terbaik dari histori.
            pasangan = pemetaan[-2:]
            bukti_pasangan = tuple(o for p in pasangan for o in p.outcomes
                                  if o.template_id == template_id and not o.dilewati)
            baik = (len(pasangan) == 2
                    and (pasangan[1].tanggal - pasangan[0].tanggal).days >= 3
                    and all(_lulus_pola_materi(tuple(o for o in p.outcomes
                                         if o.template_id == template_id), 1)
                            for p in pasangan)
                    and _sidik_beragam(bukti_pasangan, 4)
                    and _lulus_pola_materi(bukti_pasangan, 4))
            if baik:
                keberhasilan, dipakai = (s.tanggal, s.id), tuple(p.id for p in pasangan)
            elif any(o.dilewati or o.benar is not True or o.kode_final is not None
                     or o.cek_pemahaman != "bisa_menjelaskan"
                     for o in s.outcomes if o.template_id == template_id):
                penghalang = (s.tanggal, s.id)
        elif s.tujuan == "evaluasi":
            fokus = tuple(k for k in s.target_fokus if k[0] == template_id)
            # Soal pembanding tidak mensertifikasi pola yang bukan target evaluasi.
            if not fokus:
                continue
            baik = (not any(o.dilewati for o in s.outcomes if o.template_id == template_id)
                    and all(_lulus_pola_materi(_hasil_fokus(s, k), 4)
                            and _sidik_beragam(_hasil_fokus(s, k), 4) for k in fokus))
            if baik:
                keberhasilan, dipakai = (s.tanggal, s.id), (s.id,)
            else:
                penghalang = (s.tanggal, s.id)
        elif s.tujuan == "checkpoint":
            fokus = tuple(k for k in s.target_fokus if k[0] == template_id)
            p = putaran.get(s.putaran_id)
            if not fokus or p is None or s.bagian_checkpoint != 2:
                continue
            sebelum = replace(bukti, sesi=tuple(x for x in sesi
                               if (x.tanggal, x.id) <= (s.tanggal, s.id)))
            bagian = tuple(x for x in sebelum.sesi if x.putaran_id == p.id
                           and x.tujuan == "checkpoint" and x.occurrence == s.occurrence
                           and x.bagian_checkpoint in {1, 2})
            if {x.bagian_checkpoint for x in bagian} != {1, 2}:
                continue
            baik = (not any(o.dilewati for x in bagian for o in x.outcomes
                            if o.template_id == template_id)
                    and all(_checkpoint_sukses(sebelum, p, k)[0] == s.tanggal
                            and _sidik_beragam(tuple(o for x in bagian for o in _hasil_fokus(x, k)), 3)
                            for k in fokus))
            if baik:
                keberhasilan, dipakai = (s.tanggal, s.id), tuple(x.id for x in bagian)
            else:
                penghalang = (s.tanggal, s.id)
    akhir = urut[-1].tanggal
    semua_ids = tuple(s.id for s in urut)
    if template_id in dikoreksi:
        return StatusPolaMateri(template_id, "perlu_cek", semua_ids, akhir)
    if (keberhasilan is None or template_id in tertahan
            or (penghalang is not None and penghalang >= keberhasilan)):
        return StatusPolaMateri(template_id, "dipelajari", semua_ids, akhir)
    if (hari - keberhasilan[0]).days >= 28:
        return StatusPolaMateri(template_id, "perlu_cek", dipakai, keberhasilan[0])
    return StatusPolaMateri(template_id, "terbukti", dipakai, keberhasilan[0])


def penguasaan_target(bukti: BuktiSiklus, siswa_id: int, target,
                      hari_ini: Optional[date] = None) -> Tuple[StatusTargetMateri, ...]:
    """Progres target katalog, bukan skor kecerdasan atau rekomendasi baru.

    Setiap pola dalam satu target wajib terbukti. Target belum diuji tetap di
    denominator katalog tetapi dilabel belum dinilai, bukan tidak mampu.
    """
    if siswa_id != bukti.siswa_id:
        raise ValueError("bukti bukan milik siswa")
    hari = hari_ini or date.today()
    sesi = _sesi_peta_materi(bukti, hari)
    sumber = replace(bukti, sesi=sesi)
    from cycle_carry import bukti_lanjutan
    # Carry dipakai untuk status fokus saja; jangan gandakan probe di katalog.
    tertahan = _pola_fokus_tertahan(bukti_lanjutan(sumber), hari)
    dikoreksi = _pola_terkoreksi(bukti)
    pola = {tid: _nilai_pola_materi(tid, sesi, sumber, hari, tertahan, dikoreksi)
            for item in target for tid in item.pola}
    hasil = []
    for item in target:
        rincian = tuple(pola[t] for t in item.pola)
        status = {p.status for p in rincian}
        if status == {"terbukti"}:
            nilai = "terbukti"
        elif status == {"belum_dinilai"}:
            nilai = "belum_dinilai"
        elif "dipelajari" in status or "belum_dinilai" in status:
            nilai = "dipelajari"
        else:
            nilai = "perlu_cek"
        hasil.append(StatusTargetMateri(item.id, nilai, rincian))
    return tuple(hasil)
