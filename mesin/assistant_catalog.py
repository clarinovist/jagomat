"""Snapshot katalog kemampuan Jagomat untuk Pendamping.

Modul ini hanya membaca registry source dan kartu konsep resmi. Ia tidak membuka
basis data, membangkitkan soal, atau mengambil hasil belajar anak.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Optional

import rumus
from templates import LEVEL
import topics


BELUM_DIDESKRIPSIKAN = "belum_dideskripsikan"


@dataclass(frozen=True)
class KartuKatalog:
    """Salinan immutable dari kartu konsep resmi."""

    judul: str
    inti: str
    contoh: str
    bantuan_jenis: Optional[str]
    bantuan_versi: Optional[int]


@dataclass(frozen=True)
class TopikKatalog:
    """Identitas topik asli dan level yang benar-benar didukung."""

    id: str
    nama: str
    level: tuple[str, ...]


@dataclass(frozen=True)
class TemplateKatalog:
    """Kemampuan satu template tanpa parameter soal atau data hasil."""

    id: str
    topik_id: str
    level: tuple[str, ...]
    kartu: Optional[KartuKatalog]
    nama_ramah: Optional[str]
    status_nama_ramah: str
    variasi: tuple[str, ...]
    status_variasi: str


@dataclass(frozen=True)
class KatalogPendamping:
    """Snapshot lengkap yang aman diteruskan ke lapisan chat umum."""

    versi: int
    topik: tuple[TopikKatalog, ...]
    template: tuple[TemplateKatalog, ...]


@dataclass(frozen=True)
class UkuranKatalog:
    """Ukuran payload dan perkiraan kasar token tanpa tokenizer eksternal."""

    karakter: int
    byte: int
    perkiraan_token: int


def _level_topik(topik: topics.Topik) -> tuple[str, ...]:
    return tuple(level for level in LEVEL if topik.komposisi.get(level))


def _level_template(topik: topics.Topik, template_id: str) -> tuple[str, ...]:
    return tuple(
        level
        for level in LEVEL
        if template_id in topik.komposisi.get(level, ())
    )


def _salin_kartu(template_id: str) -> Optional[KartuKatalog]:
    kartu = rumus.kartu_untuk(template_id)
    if kartu is None:
        return None
    bantuan = kartu.bantuan
    return KartuKatalog(
        judul=kartu.judul,
        inti=kartu.inti,
        contoh=kartu.contoh,
        bantuan_jenis=bantuan.jenis if bantuan else None,
        bantuan_versi=bantuan.versi if bantuan else None,
    )


def buat_katalog(*, untuk_penawaran: bool = True) -> KatalogPendamping:
    """Bangun snapshot deterministik langsung dari registry aktif.

    Paket ``campuran`` hanya komposisi sintetis, sehingga tidak dicatat sebagai
    pemilik. Metadata ramah atau variasi yang belum mempunyai sumber eksplisit
    sengaja ditandai, bukan diterka dari ID maupun satu contoh soal.
    """
    topik_asli = tuple(
        topics.ambil(topik_id)
        for topik_id in topics.daftar_topik()
        if topik_id != "campuran"
    )
    pemilik = {}
    for topik in topik_asli:
        for template_id in topik.templates:
            if template_id in pemilik:
                raise ValueError(f"template_id duplikat lintas topik: {template_id}")
            pemilik[template_id] = topik

    registry = topics.registri()
    if set(pemilik) != set(registry):
        raise ValueError("pemilik template tidak sama dengan registry aktif")

    # Audit registry utuh dahulu; hanya snapshot penawaran ke AI yang disaring.
    from question_context import daftar_topik_latihan
    tersedia = set(daftar_topik_latihan() if untuk_penawaran else topics.daftar_topik())
    topik_asli = tuple(t for t in topik_asli if t.id in tersedia)
    registry = {tid: t for tid, t in registry.items() if pemilik[tid].id in tersedia}

    daftar_topik = tuple(
        TopikKatalog(id=topik.id, nama=topik.nama, level=_level_topik(topik))
        for topik in topik_asli
    )
    daftar_template = tuple(
        TemplateKatalog(
            id=template_id,
            topik_id=pemilik[template_id].id,
            level=_level_template(pemilik[template_id], template_id),
            kartu=_salin_kartu(template_id),
            nama_ramah=None,
            status_nama_ramah=BELUM_DIDESKRIPSIKAN,
            variasi=(),
            status_variasi=BELUM_DIDESKRIPSIKAN,
        )
        for template_id in sorted(registry)
    )
    return KatalogPendamping(
        versi=1,
        topik=daftar_topik,
        template=daftar_template,
    )


def serialisasi_ringkas(katalog: KatalogPendamping) -> str:
    """Serialisasi JSON stabil dan ringkas untuk pengukuran/payload berikutnya."""
    if type(katalog) is not KatalogPendamping:
        raise TypeError("katalog wajib KatalogPendamping")
    return json.dumps(
        asdict(katalog),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def ukur_katalog(katalog: KatalogPendamping) -> UkuranKatalog:
    """Ukur karakter/byte dan proxy konservatif satu token per empat karakter."""
    teks = serialisasi_ringkas(katalog)
    return UkuranKatalog(
        karakter=len(teks),
        byte=len(teks.encode("utf-8")),
        perkiraan_token=(len(teks) + 3) // 4,
    )
