"""Adapter pembaca penyajian soal warisan dan snapshot Fase 1."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from typing import Any

from generator import LEVEL_BAWAAN
from templates import REGISTRI, Soal
from topic_statistics_visual import proyeksi_statistika
from visual_contract import (
    PenyajianPertanyaan,
    buat_penyajian,
    deserialisasi_penyajian,
    fingerprint_matematis,
)


KOLOM_SNAPSHOT = (
    "teks_soal",
    "bagian_soal",
    "tantangan_soal",
    "minta_restatement",
    "penyajian_json",
    "penyajian_versi",
    "renderer_versi",
    "asal_teks",
    "status_visual",
    "mode_representasi",
    "fingerprint_matematis",
    "fingerprint_penyajian",
)


def _ambil(baris, kolom: str, bawaan: Any = None) -> Any:
    """Baca sqlite3.Row/dict; kolom migrasi yang belum ada dianggap NULL."""
    try:
        return baris[kolom]
    except (IndexError, KeyError):
        return bawaan


def _parameter_level(baris) -> tuple[dict[str, Any], str]:
    try:
        parameter = json.loads(baris["parameter"])
    except (KeyError, TypeError, json.JSONDecodeError) as galat:
        raise ValueError("parameter soal tidak valid") from galat
    if not isinstance(parameter, dict):
        raise ValueError("parameter soal wajib berupa objek JSON")
    return parameter, _ambil(baris, "level", LEVEL_BAWAAN) or LEVEL_BAWAAN


def _ke_bool_db(nilai: Any, nama: str) -> bool:
    if nilai not in (0, 1, False, True):
        raise ValueError(f"kolom snapshot {nama} bukan boolean")
    return bool(nilai)


def _klasifikasi_snapshot(baris) -> str:
    nilai = [_ambil(baris, nama) for nama in KOLOM_SNAPSHOT]
    if all(isi is None for isi in nilai):
        return "warisan"
    if any(isi is None for isi in nilai):
        raise ValueError("snapshot penyajian parsial ditolak")
    return "lengkap"


def _penyajian_warisan(baris) -> PenyajianPertanyaan:
    parameter, level = _parameter_level(baris)
    try:
        soal = REGISTRI[baris["template_id"]](**parameter)
    except KeyError as galat:
        raise ValueError("template soal warisan tidak dikenal") from galat
    soal = replace(soal, level=level)
    cerita = (_ambil(baris, "cerita", "") or "").strip()
    teks = cerita or soal.teks
    return buat_penyajian(
        template_id=baris["template_id"],
        level=level,
        parameter=parameter,
        teks_soal=teks,
        bagian_soal=soal.bagian,
        tantangan_soal=soal.tantangan,
        minta_restatement=soal.minta_restatement,
        asal_teks="cerita" if cerita else "bawaan",
        status_visual="warisan",
        mode_representasi="teks-v1",
    )


def _penyajian_snapshot(baris) -> PenyajianPertanyaan:
    try:
        penyajian = deserialisasi_penyajian(baris["penyajian_json"])
    except (KeyError, TypeError, ValueError) as galat:
        raise ValueError(f"snapshot penyajian tidak valid: {galat}") from galat

    pasangan = {
        "teks_soal": penyajian.teks_soal,
        "bagian_soal": penyajian.bagian_soal,
        "tantangan_soal": penyajian.tantangan_soal,
        "minta_restatement": penyajian.minta_restatement,
        "penyajian_versi": penyajian.penyajian_versi,
        "renderer_versi": penyajian.renderer_versi,
        "asal_teks": penyajian.asal_teks,
        "status_visual": penyajian.status_visual,
        "mode_representasi": penyajian.mode_representasi,
        "fingerprint_matematis": penyajian.fingerprint_matematis,
        "fingerprint_penyajian": penyajian.fingerprint_penyajian,
    }
    for nama, harapan in pasangan.items():
        aktual = baris[nama]
        if nama in ("tantangan_soal", "minta_restatement"):
            aktual = _ke_bool_db(aktual, nama)
        if aktual != harapan:
            raise ValueError(f"kolom snapshot {nama} tidak cocok dengan JSON")

    parameter, level = _parameter_level(baris)
    sidik = fingerprint_matematis(
        penyajian.penyajian_versi, baris["template_id"], level, parameter
    )
    if sidik != penyajian.fingerprint_matematis:
        raise ValueError("fingerprint matematis snapshot tidak cocok dengan soal")
    return penyajian


def _proyeksi_visual_aktif(soal: Soal):
    """Validasi seluruh allow-list sebelum memilih proyektor snapshot baru."""
    from topic_plane_geometry_visual import proyeksi_geometri_datar
    from topic_solid_geometry_visual import proyeksi_geometri_ruang
    from topic_combinatorics_visual import proyeksi_kombinatorik
    from topic_measurement_visual import proyeksi_pengukuran
    from topic_number_patterns_visual import proyeksi_pola

    konfigurasi = os.environ.get("OSN_VISUAL_KELUARGA", "").strip()
    if not konfigurasi:
        return None
    keluarga = frozenset(nama.strip() for nama in konfigurasi.split(","))
    proyektor = {
        "statistika": proyeksi_statistika,
        "geometri-datar": proyeksi_geometri_datar,
        "geometri-ruang": proyeksi_geometri_ruang,
        "kombinatorik": proyeksi_kombinatorik,
        "pengukuran": proyeksi_pengukuran,
        "pola-bilangan": proyeksi_pola,
    }
    asing = keluarga - proyektor.keys()
    if asing:
        raise ValueError(f"keluarga visual tidak dikenal: {sorted(asing)!r}")
    for nama in sorted(keluarga):
        hasil = proyektor[nama](soal.template_id, soal.parameter)
        if hasil is not None:
            return hasil
    return None


def penyajian_dari_soal(soal: Soal) -> PenyajianPertanyaan:
    """Proyeksikan soal baru; default teks dan visual hanya lewat opt-in."""
    proyeksi = _proyeksi_visual_aktif(soal)

    teks = soal.teks
    status_visual = "tanpa_visual"
    mode_representasi = "teks-v1"
    descriptor = None
    if proyeksi is not None:
        teks, descriptor = proyeksi
        status_visual = "siap"
        mode_representasi = f"{descriptor.jenis}-v{descriptor.versi}"
    else:
        # Bank statis hanya untuk snapshot BARU. Reader warisan/snapshot di
        # bawah tidak memanggilnya, sehingga teks riwayat tetap exact.
        from story_frames import untuk_snapshot_baru
        kalimat = untuk_snapshot_baru(soal)
        if kalimat is not None:
            teks = kalimat.teks

    return buat_penyajian(
        template_id=soal.template_id,
        level=soal.level,
        parameter=soal.parameter,
        teks_soal=teks,
        bagian_soal=soal.bagian,
        tantangan_soal=soal.tantangan,
        minta_restatement=soal.minta_restatement,
        asal_teks="bawaan",
        status_visual=status_visual,
        mode_representasi=mode_representasi,
        descriptor=descriptor,
    )


def penyajian_dari_baris(baris) -> PenyajianPertanyaan:
    """Baca field penyajian aman; snapshot rusak selalu gagal tertutup."""
    if _klasifikasi_snapshot(baris) == "warisan":
        return _penyajian_warisan(baris)
    return _penyajian_snapshot(baris)


def penyajian_sesi_aman(kon, sesi_id: int) -> tuple[PenyajianPertanyaan, ...]:
    """Baca konteks pertanyaan tanpa kolom diagnosis atau kunci."""
    kolom = ", ".join("ss." + nama for nama in KOLOM_SNAPSHOT)
    baris = kon.execute(
        f"""SELECT {kolom}, s.template_id, s.parameter, s.level, s.cerita
            FROM sesi_soal ss JOIN soal s ON s.id = ss.soal_id
            WHERE ss.sesi_id = ? ORDER BY ss.nomor""",
        (sesi_id,),
    ).fetchall()
    return tuple(penyajian_dari_baris(b) for b in baris)


def soal_dari_baris(baris) -> Soal:
    """Kembalikan ``Soal`` untuk pemanggil lama, dengan penyajian dari adapter."""
    keadaan = _klasifikasi_snapshot(baris)
    penyajian = (
        _penyajian_warisan(baris)
        if keadaan == "warisan"
        else _penyajian_snapshot(baris)
    )
    parameter, level = _parameter_level(baris)
    try:
        soal = REGISTRI[baris["template_id"]](**parameter)
    except KeyError as galat:
        raise ValueError("template soal tidak dikenal") from galat
    return replace(
        soal,
        level=level,
        teks=penyajian.teks_soal,
        bagian=penyajian.bagian_soal,
        tantangan=penyajian.tantangan_soal,
        minta_restatement=penyajian.minta_restatement,
        penyajian=penyajian,
    )
