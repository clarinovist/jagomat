"""Pembuatan sesi untuk satu rekomendasi siklus belajar."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Iterable, Optional, Tuple

import topics
from generator import buat_lembar
from learning_cycle import KunciFokus, RencanaBelajar

JUMLAH_PEMETAAN = 15
JUMLAH_LATIHAN = 10

_TINDAKAN_SESI = {
    "pemetaan",
    "probe_diagnostik",
    "latihan_terbimbing",
    "penguatan",
    "evaluasi",
    "checkpoint",
    "pengenalan",
    "probe_setelah_pengenalan",
    "mixed_maintenance",
}


def _unik(daftar: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(daftar))


def _fokus_rencana(rencana: RencanaBelajar) -> Tuple[KunciFokus, ...]:
    if rencana.kandidat:
        mentah = rencana.kandidat
    elif rencana.putaran is not None:
        mentah = tuple(item.kunci for item in rencana.putaran.fokus)
    else:
        mentah = ()
    hasil = tuple(dict.fromkeys(tuple(kunci) for kunci in mentah))
    if rencana.tindakan in {"pemetaan", "probe_diagnostik"}:
        hasil = hasil[:5]
    elif len(hasil) > 2:
        raise ValueError("fokus rencana maksimal 2")
    for template_id, kode, _malrule_id in hasil:
        if kode not in "BKHENT":
            raise ValueError("kode fokus tidak dikenal")
        if topics.pemilik_template(template_id) is None:
            raise ValueError("template fokus tidak dikenal")
    return hasil


def _template_lintas_topik(level: str, jumlah: int, kecuali=()) -> list[str]:
    """Ambil template round-robin lintas paket pada level aktif."""
    terlarang = set(kecuali)
    paket = [
        topics.ambil(topik_id)
        for topik_id in topics.daftar_topik()
        if topik_id != "campuran"
    ]
    per_topik = [
        _unik(t.komposisi_untuk(level))
        for t in paket
        if level in t.komposisi
    ]
    hasil: list[str] = []
    indeks = 0
    while len(hasil) < jumlah and per_topik:
        bertambah = False
        for daftar in per_topik:
            if indeks >= len(daftar):
                continue
            template_id = daftar[indeks]
            if template_id not in terlarang and template_id not in hasil:
                hasil.append(template_id)
                bertambah = True
                if len(hasil) == jumlah:
                    break
        indeks += 1
        if indeks >= max(map(len, per_topik)) and not bertambah:
            break
    if len(hasil) < jumlah:
        cadangan = [
            template_id
            for daftar in per_topik
            for template_id in daftar
            if template_id not in terlarang
        ]
        if not cadangan:
            raise ValueError("tidak ada template pembanding untuk level aktif")
        while len(hasil) < jumlah:
            hasil.extend(cadangan)
    return hasil[:jumlah]


def _ulang_seimbang(template_ids: Tuple[str, ...], jumlah: int) -> list[str]:
    if not template_ids:
        raise ValueError("rencana tahap fokus tidak memiliki target")
    hasil: list[str] = []
    while len(hasil) < jumlah:
        hasil.extend(template_ids)
    return hasil[:jumlah]


def _urutan_rencana(
    rencana: RencanaBelajar, fokus: Tuple[KunciFokus, ...], level: str
) -> tuple[str, ...]:
    tindakan = rencana.tindakan
    template = tuple(kunci[0] for kunci in fokus)
    if tindakan == "pemetaan":
        anchor = tuple(kunci[0] for kunci in fokus[:5])
        sisa = _template_lintas_topik(
            level, JUMLAH_PEMETAAN - len(anchor), set(anchor)
        )
        return anchor + tuple(sisa)
    if tindakan == "probe_diagnostik":
        kandidat = tuple(_unik(template))[:5]
        return tuple(_ulang_seimbang(kandidat, JUMLAH_LATIHAN))
    if tindakan == "latihan_terbimbing":
        if not fokus:
            raise ValueError("rencana tahap fokus tidak memiliki target")
        return tuple(kunci[0] for kunci in fokus)
    if tindakan == "penguatan":
        return tuple(_ulang_seimbang(tuple(_unik(template)), JUMLAH_LATIHAN))
    if tindakan == "evaluasi":
        minimum = max(4, rencana.jumlah_probe_minimum)
        fokus_soal = [tid for tid in template for _ in range(minimum)]
        pembanding = _template_lintas_topik(
            level, JUMLAH_LATIHAN - len(fokus_soal), template
        )
        return tuple(fokus_soal + pembanding)
    if tindakan == "checkpoint":
        minimum_pasangan = max(3, rencana.jumlah_probe_minimum)
        if rencana.bagian_checkpoint == 1:
            minimum = (minimum_pasangan + 1) // 2
        else:
            minimum = minimum_pasangan // 2
        fokus_soal = [tid for tid in template for _ in range(minimum)]
        pembanding = _template_lintas_topik(
            level, JUMLAH_LATIHAN - len(fokus_soal), template
        )
        return tuple(fokus_soal + pembanding)
    if tindakan in {"pengenalan", "probe_setelah_pengenalan"}:
        jumlah = 1 if tindakan == "pengenalan" else 5
        return tuple(_ulang_seimbang(tuple(_unik(template)), jumlah))
    if tindakan == "mixed_maintenance":
        return tuple(_template_lintas_topik(level, JUMLAH_LATIHAN))
    raise ValueError("tindakan rencana tidak membuat sesi")


def _tujuan_sesi(tindakan: str) -> tuple[str, str]:
    if tindakan in {"pemetaan", "probe_diagnostik", "probe_setelah_pengenalan"}:
        return "pemetaan", "biasa"
    if tindakan == "latihan_terbimbing":
        return tindakan, "remedial"
    if tindakan == "penguatan":
        return tindakan, "remedial"
    if tindakan in {"evaluasi", "checkpoint", "pengenalan"}:
        return tindakan, "biasa"
    if tindakan == "mixed_maintenance":
        return "maintenance", "biasa"
    raise ValueError("tindakan rencana tidak dikenal")


def _kunci_idempotensi(
    siswa_id: int,
    tindakan: str,
    putaran_id: int,
    fokus: Tuple[KunciFokus, ...],
    sumber_sesi_id: Optional[int],
    bagian_checkpoint: Optional[int],
    occurrence: int,
) -> str:
    isi = json.dumps(
        [
            siswa_id,
            tindakan,
            putaran_id,
            sorted((a, b, c or "") for a, b, c in fokus),
            sumber_sesi_id,
            bagian_checkpoint,
            occurrence,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(isi.encode("utf-8")).hexdigest()


def _target_per_nomor(
    urutan: tuple[str, ...], fokus: Tuple[KunciFokus, ...]
) -> dict[str, list[Optional[str]]]:
    """Tandai probe secara deterministik, termasuk dua fokus satu template."""
    per_template: dict[str, list[KunciFokus]] = {}
    for kunci in fokus:
        per_template.setdefault(kunci[0], []).append(kunci)
    posisi: dict[str, int] = {}
    hasil = {}
    for nomor, template_id in enumerate(urutan, start=1):
        kandidat = per_template.get(template_id, [])
        if not kandidat:
            continue
        indeks = posisi.get(template_id, 0)
        target = kandidat[indeks % len(kandidat)]
        posisi[template_id] = indeks + 1
        hasil[str(nomor)] = [target[0], target[1], target[2]]
    return hasil


def tandai_pengenalan_selesai(
    kon: sqlite3.Connection,
    siswa_id: int,
    putaran_id: int,
    fokus: KunciFokus,
    pendekatan_id: str,
) -> None:
    """Catat pengenalan sekali; reducer akan meminta probe diagnostik sesudahnya."""
    putaran = kon.execute(
        "SELECT siswa_id FROM putaran_fokus WHERE id = ?", (putaran_id,)
    ).fetchone()
    if putaran is None or int(putaran["siswa_id"]) != siswa_id:
        raise ValueError("siswa dan putaran tidak cocok")
    if fokus[1] != "T" or topics.pemilik_template(fokus[0]) is None:
        raise ValueError("fokus pengenalan tidak sah")
    import interventions

    pendekatan_sah = {
        item.pendekatan_id
        for item in interventions.pilihan_untuk_fokus(fokus)
        if item.tersedia
    }
    if pendekatan_id not in pendekatan_sah:
        raise ValueError("pendekatan pengenalan tidak sah")
    pengenalan = False
    baris_pengenalan = kon.execute(
        """SELECT kb.data FROM sesi se
           JOIN kejadian_belajar kb ON kb.sesi_id = se.id
           WHERE se.siswa_id = ? AND se.putaran_id = ?
             AND se.tujuan = 'pengenalan' AND se.dibatalkan IS NULL
             AND kb.jenis = 'sesi_dibuat'
           ORDER BY se.id DESC""",
        (siswa_id, putaran_id),
    ).fetchall()
    for baris in baris_pengenalan:
        data_sesi = json.loads(baris["data"] or "{}")
        fokus_sesi = data_sesi.get("fokus", []) if isinstance(data_sesi, dict) else []
        if list(fokus) in fokus_sesi:
            pengenalan = True
            break
    if not pengenalan:
        raise ValueError("sesi pengenalan belum dibuat")
    data = json.dumps(
        {"fokus": list(fokus), "pendekatan_id": pendekatan_id},
        ensure_ascii=False,
        sort_keys=True,
    )
    ada = kon.execute(
        """SELECT 1 FROM kejadian_belajar
           WHERE siswa_id = ? AND putaran_id = ?
             AND jenis = 'pengenalan_selesai' AND data = ?""",
        (siswa_id, putaran_id, data),
    ).fetchone()
    if ada is None:
        kon.execute(
            """INSERT INTO kejadian_belajar
                   (siswa_id, putaran_id, jenis, data)
               VALUES (?, ?, 'pengenalan_selesai', ?)""",
            (siswa_id, putaran_id, data),
        )


def _tanda_tangan_lama(
    kon: sqlite3.Connection, siswa_id: int, template_ids: Iterable[str]
) -> set[str]:
    daftar = tuple(dict.fromkeys(template_ids))
    if not daftar:
        return set()
    baris = kon.execute(
        """SELECT DISTINCT so.template_id, so.tanda_tangan
           FROM soal so
           JOIN sesi_soal ss ON ss.soal_id = so.id
           JOIN sesi se ON se.id = ss.sesi_id
           WHERE se.siswa_id = ?""",
        (siswa_id,),
    ).fetchall()
    terpilih = set(daftar)
    return {
        item["tanda_tangan"] for item in baris if item["template_id"] in terpilih
    }


def _soal_tanpa_soal_lama(
    kon: sqlite3.Connection,
    siswa_id: int,
    seed: int,
    urutan: tuple[str, ...],
    paket,
    level: str,
    fokus: Tuple[KunciFokus, ...],
) -> tuple:
    """Pilih butir fokus baru secara deterministik tanpa mengubah generator umum."""
    template_fokus = {kunci[0] for kunci in fokus}
    lama = _tanda_tangan_lama(kon, siswa_id, template_fokus)
    lembar = buat_lembar(seed, urutan=urutan, level=level, topik=paket)
    hasil = ()
    dipakai = frozenset(lama)
    for nomor, soal in enumerate(lembar.soal):
        if soal.template_id in template_fokus and soal.tanda_tangan in dipakai:
            soal = _butir_baru(seed + nomor, soal.template_id, paket, level, dipakai)
        hasil = (*hasil, soal)
        if soal.template_id in template_fokus:
            dipakai = dipakai | {soal.tanda_tangan}
    return hasil


def _butir_baru(seed, template_id, paket, level, dipakai):
    """Ganti hanya butir bentrok; jangan membuang butir baru satu lembar penuh."""
    for calon in range(seed, seed + 500):
        soal = buat_lembar(calon, urutan=(template_id,), level=level, topik=paket).soal[0]
        if soal.tanda_tangan not in dipakai:
            return soal
    raise ValueError(
        "Soal fokus baru belum cukup tersedia. Gunakan latihan manual atau tinjau fokus bersama."
    )


def buat_sesi_dari_rencana(
    kon: sqlite3.Connection,
    siswa_id: int,
    rencana: RencanaBelajar,
    *,
    putaran_id: int,
    seed: int,
    occurrence: int = 1,
) -> int:
    """Validasi ulang lalu simpan satu sesi rekomendasi secara idempoten."""
    if kon.execute('SELECT 1 FROM pilot_putaran WHERE putaran_id=?',(putaran_id,)).fetchone():
        raise ValueError('Putaran pilot harus memakai penulis konteks pilot.')
    if rencana.tindakan not in _TINDAKAN_SESI:
        raise ValueError("rencana tidak dapat dibuat menjadi sesi")
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("seed harus bilangan bulat nonnegatif")
    if not isinstance(occurrence, int) or occurrence < 1:
        raise ValueError("occurrence harus bilangan bulat positif")
    putaran = kon.execute(
        "SELECT siswa_id, level FROM putaran_fokus WHERE id = ?", (putaran_id,)
    ).fetchone()
    siswa = kon.execute(
        "SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)
    ).fetchone()
    if siswa is None or putaran is None or putaran["siswa_id"] != siswa_id:
        raise ValueError("siswa dan putaran tidak cocok")
    if putaran["level"] != siswa["tingkat"]:
        raise ValueError("level putaran bukan level aktif")
    if rencana.putaran is not None:
        if rencana.putaran.id not in (None, putaran_id):
            raise ValueError("identitas putaran rencana tidak cocok")
        if rencana.putaran.level != putaran["level"]:
            raise ValueError("level rencana tidak cocok")

    fokus = _fokus_rencana(rencana)
    tindakan_berfokus = _TINDAKAN_SESI - {"pemetaan", "mixed_maintenance"}
    if rencana.tindakan in tindakan_berfokus and not fokus:
        raise ValueError("rencana tahap fokus tidak memiliki target")
    bagian = rencana.bagian_checkpoint
    if rencana.tindakan == "checkpoint" and bagian not in {1, 2}:
        raise ValueError("bagian checkpoint harus 1 atau 2")
    if rencana.tindakan != "checkpoint" and bagian is not None:
        raise ValueError("bagian checkpoint hanya untuk checkpoint")
    if rencana.tindakan == "penguatan":
        sumber = rencana.sesi_id
    else:
        sumber = None
    if sumber is not None:
        sumber_baris = kon.execute(
            "SELECT siswa_id, putaran_id FROM sesi WHERE id = ?", (sumber,)
        ).fetchone()
        if (
            sumber_baris is None
            or int(sumber_baris["siswa_id"]) != siswa_id
            or sumber_baris["putaran_id"] != putaran_id
        ):
            raise ValueError("sumber sesi bukan milik siswa dan putaran")
    kunci = _kunci_idempotensi(
        siswa_id, rencana.tindakan, putaran_id, fokus, sumber, bagian, occurrence
    )
    lama = kon.execute(
        """SELECT id FROM sesi
           WHERE kunci_idempotensi = ? AND dibatalkan IS NULL""",
        (kunci,),
    ).fetchone()
    if lama is not None:
        return int(lama["id"])

    urutan = _urutan_rencana(rencana, fokus, putaran["level"])
    paket = topics.paket_untuk_template(urutan)
    soal_terpilih = None
    if rencana.tindakan in {
        "pemetaan",
        "latihan_terbimbing",
        "penguatan",
        "evaluasi",
        "checkpoint",
        "pengenalan",
        "probe_setelah_pengenalan",
    }:
        soal_terpilih = _soal_tanpa_soal_lama(
            kon,
            siswa_id,
            seed,
            urutan,
            paket,
            putaran["level"],
            fokus,
        )
    tujuan, jenis = _tujuan_sesi(rencana.tindakan)

    import database

    kon.execute("SAVEPOINT buat_sesi_siklus")
    try:
        sesi_id = database.buat_sesi_dari_urutan(
            kon,
            siswa_id,
            seed,
            urutan,
            topik=paket,
            level=putaran["level"],
            mode="diagnostik",
            jenis=jenis,
            sumber_sesi_id=sumber if jenis == "remedial" else None,
            soal_terpilih=soal_terpilih,
        )
        urutan_aktual = tuple(
            baris["template_id"] for baris in database.isi_sesi(kon, sesi_id)
        )
        kon.execute(
            """UPDATE sesi
               SET tujuan = ?, putaran_id = ?, bagian_checkpoint = ?,
                   kunci_idempotensi = ?
               WHERE id = ?""",
            (tujuan, putaran_id, bagian, kunci, sesi_id),
        )
        import context_store
        target_nomor = _target_per_nomor(urutan_aktual, fokus)
        konteks = context_store.proyeksi(kon, sesi_id, {int(n): k for n, k in target_nomor.items()})
        kon.execute(
            """INSERT INTO kejadian_belajar
                   (siswa_id, putaran_id, sesi_id, jenis, data)
               VALUES (?, ?, ?, 'sesi_dibuat', ?)""",
            (
                siswa_id,
                putaran_id,
                sesi_id,
                json.dumps(
                    {
                        "tindakan": rencana.tindakan,
                        "fokus": [list(item) for item in fokus],
                        "target_per_nomor": target_nomor,
                        "konteks_latihan": konteks,
                        "occurrence": occurrence,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        )
        kon.execute("RELEASE SAVEPOINT buat_sesi_siklus")
        return sesi_id
    except sqlite3.IntegrityError:
        kon.execute("ROLLBACK TO SAVEPOINT buat_sesi_siklus")
        kon.execute("RELEASE SAVEPOINT buat_sesi_siklus")
        lama = kon.execute(
            """SELECT id FROM sesi
               WHERE kunci_idempotensi = ? AND dibatalkan IS NULL""",
            (kunci,),
        ).fetchone()
        if lama is not None:
            return int(lama["id"])
        raise
