"""Adapter konteks belajar minimum dan berizin untuk Pendamping.

Query di modul ini tidak mengambil nama anak, jawaban bebas, diagnosis, malrule,
catatan guru, atau foto. Seluruh resource diperiksa terhadap pemilik sebelum
diproyeksikan menjadi payload netral.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Optional

import database
import question_views
from learning_cycle import rencana_berikutnya


@dataclass(frozen=True)
class KonteksPendamping:
    jenis: str
    resource_id: str
    versi: str
    kategori: str
    muatan: dict


def _sidik(muatan: dict) -> str:
    teks = json.dumps(
        muatan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()


def _tahap_netral(tindakan: str) -> str:
    return {
        "lanjutkan_sesi": "Sesi belajar sedang berjalan",
        "konfirmasi_hasil": "Hasil menunggu tinjauan orang tua",
        "pemetaan": "Latihan awal",
        "tunggu_pemetaan": "Menunggu latihan awal berikutnya",
        "probe_diagnostik": "Pemeriksaan awal lanjutan",
        "intervensi": "Pelajari bersama",
        "latihan_terbimbing": "Latihan dengan bantuan",
        "penguatan": "Coba mandiri",
        "tunggu_evaluasi": "Menunggu pemeriksaan setelah jeda",
        "evaluasi": "Pemeriksaan setelah jeda",
        "tunggu_checkpoint": "Menunggu cek kembali pemahaman",
        "checkpoint": "Cek kembali pemahaman",
        "pengenalan": "Pengenalan materi",
        "probe_setelah_pengenalan": "Periksa pemahaman materi baru",
        "mixed_maintenance": "Latihan campuran",
        "putaran_baru": "Memulai langkah bantuan baru",
        "eskalasi": "Perlu pendampingan lebih lanjut",
    }.get(tindakan, "Langkah berikutnya tersedia")


def versi_ringkasan_anak(kon, siswa_id: int, *, pemilik: str) -> Optional[str]:
    """Versi murah untuk revalidasi tanpa merakit payload reducer penuh."""
    if not database.siswa_milik(kon, siswa_id, pemilik):
        return None
    baris = kon.execute(
        """SELECT w.tingkat,
                  (SELECT COALESCE(MAX(s.id), 0) FROM sesi s
                   WHERE s.siswa_id = w.id) AS sesi_terakhir,
                  (SELECT COALESCE(MAX(kh.id), 0) FROM konfirmasi_hasil kh
                   JOIN sesi s ON s.id = kh.sesi_id
                   WHERE s.siswa_id = w.id) AS konfirmasi_terakhir,
                  (SELECT COALESCE(MAX(kb.id), 0) FROM kejadian_belajar kb
                   WHERE kb.siswa_id = w.id) AS kejadian_terakhir
           FROM siswa w WHERE w.id = ?""",
        (siswa_id,),
    ).fetchone()
    return _sidik(dict(baris)) if baris is not None else None


def konteks_anak(
    kon,
    siswa_id: int,
    *,
    pemilik: str,
) -> Optional[KonteksPendamping]:
    """Ringkasan reducer satu anak tanpa nama, fokus, atau alasan internal."""
    if not database.siswa_milik(kon, siswa_id, pemilik):
        return None
    bukti = database.muat_bukti_siklus(kon, siswa_id)
    rencana = rencana_berikutnya(bukti, siswa_id)
    muatan = {
        "jenis": "ringkasan_anak",
        "level": bukti.level_aktif,
        "tahap": _tahap_netral(rencana.tindakan),
        "tersedia_pada": (
            rencana.tersedia_pada.isoformat()
            if rencana.tersedia_pada is not None else None
        ),
    }
    versi = versi_ringkasan_anak(kon, siswa_id, pemilik=pemilik)
    if versi is None:
        return None
    return KonteksPendamping(
        jenis="anak",
        resource_id=str(siswa_id),
        versi=versi,
        kategori="ringkasan_netral",
        muatan=muatan,
    )


def konteks_sesi(
    kon,
    sesi_id: int,
    *,
    pemilik: str,
) -> Optional[KonteksPendamping]:
    """Metadata netral satu sesi tanpa nama, jawaban, atau diagnosis."""
    if not database.sesi_milik(kon, sesi_id, pemilik):
        return None
    baris = kon.execute(
        """SELECT s.id, s.level, s.topik, s.tujuan, s.selesai,
                  s.dikonfirmasi_guru, s.dibatalkan,
                  COUNT(ss.id) AS jumlah_soal,
                  GROUP_CONCAT(ss.fingerprint_penyajian, ',') AS sidik_soal
           FROM sesi s JOIN sesi_soal ss ON ss.sesi_id = s.id
           WHERE s.id = ?
           GROUP BY s.id""",
        (sesi_id,),
    ).fetchone()
    if baris is None:
        return None
    status = (
        "dibatalkan" if baris["dibatalkan"] is not None
        else "dikonfirmasi" if baris["dikonfirmasi_guru"] is not None
        else "selesai" if baris["selesai"] is not None
        else "belum_selesai"
    )
    muatan = {
        "jenis": "ringkasan_sesi",
        "level": baris["level"],
        "topik": baris["topik"],
        "tahap": _tahap_netral(baris["tujuan"]),
        "status": status,
        "jumlah_soal": int(baris["jumlah_soal"]),
    }
    versi = _sidik({**muatan, "sidik_soal": baris["sidik_soal"]})
    return KonteksPendamping(
        jenis="sesi",
        resource_id=str(sesi_id),
        versi=versi,
        kategori="ringkasan_netral",
        muatan=muatan,
    )


def versi_sesi(kon, sesi_id: int, *, pemilik: str) -> Optional[str]:
    konteks = konteks_sesi(kon, sesi_id, pemilik=pemilik)
    return konteks.versi if konteks is not None else None


def konteks_soal(
    kon,
    sesi_id: int,
    nomor: int,
    *,
    pemilik: str,
) -> Optional[KonteksPendamping]:
    """Soal resmi dari snapshot yang dibuka, termasuk kunci dan pembahasan."""
    if not database.sesi_milik(kon, sesi_id, pemilik):
        return None
    kolom = ", ".join("ss." + nama for nama in question_views.KOLOM_SNAPSHOT)
    baris = kon.execute(
        f"""SELECT ss.nomor, {kolom}, s.template_id, s.parameter, s.level,
                   s.cerita, s.bagian, s.tantangan, s.kunci
            FROM sesi_soal ss JOIN soal s ON s.id = ss.soal_id
            WHERE ss.sesi_id = ? AND ss.nomor = ?""",
        (sesi_id, nomor),
    ).fetchone()
    if baris is None:
        return None
    penyajian = question_views.penyajian_dari_baris(baris)
    soal = question_views.soal_dari_baris(baris)
    descriptor = (
        penyajian.descriptor.ke_dict()
        if penyajian.descriptor is not None else None
    )
    muatan = {
        "jenis": "soal_resmi",
        "nomor": int(baris["nomor"]),
        "template_id": baris["template_id"],
        "level": baris["level"],
        "teks_soal": penyajian.teks_soal,
        "descriptor": descriptor,
        "kunci": soal.kunci,
        "pembahasan": soal.pembahasan,
        "fingerprint_penyajian": penyajian.fingerprint_penyajian,
    }
    return KonteksPendamping(
        jenis="soal",
        resource_id=f"{sesi_id}:{nomor}",
        versi=penyajian.fingerprint_penyajian,
        kategori="soal_resmi",
        muatan=muatan,
    )


def versi_soal(
    kon, sesi_id: int, nomor: int, *, pemilik: str
) -> Optional[str]:
    if not database.sesi_milik(kon, sesi_id, pemilik):
        return None
    baris = kon.execute(
        """SELECT ss.fingerprint_penyajian FROM sesi_soal ss
           WHERE ss.sesi_id = ? AND ss.nomor = ?""",
        (sesi_id, nomor),
    ).fetchone()
    return None if baris is None else baris["fingerprint_penyajian"]


def versi_resource(
    kon, jenis: str, resource_id: str, *, pemilik: str
) -> Optional[str]:
    try:
        if jenis == "anak":
            return versi_ringkasan_anak(kon, int(resource_id), pemilik=pemilik)
        if jenis == "sesi":
            return versi_sesi(kon, int(resource_id), pemilik=pemilik)
        if jenis == "soal":
            sesi, nomor = resource_id.split(":", 1)
            return versi_soal(kon, int(sesi), int(nomor), pemilik=pemilik)
    except (ValueError, OverflowError):
        return None
    return None


def ambil(
    kon,
    jenis: str,
    resource_id: str,
    *,
    pemilik: str,
) -> Optional[KonteksPendamping]:
    """Dispatch strict untuk resource yang sudah dipilih oleh orang tua."""
    try:
        if jenis == "anak":
            return konteks_anak(kon, int(resource_id), pemilik=pemilik)
        if jenis == "sesi":
            return konteks_sesi(kon, int(resource_id), pemilik=pemilik)
        if jenis == "soal":
            sesi, nomor = resource_id.split(":", 1)
            return konteks_soal(kon, int(sesi), int(nomor), pemilik=pemilik)
    except (ValueError, OverflowError):
        return None
    return None
