"""Kontrak murni snapshot pertanyaan untuk penyajian visual aman."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional

from templates import LEVEL
from measurement_scale_data import validasi_skala
from combinatorics_visual_data import validasi_venn, validasi_susunan
from measurement_combinatorics_visual_data import validasi_petak, validasi_waktu
from statistics_visual_data import VALIDATOR_STATISTIKA
from adegan_awal_data import validasi_adegan_awal
from number_patterns_visual_data import validasi_korek, validasi_titik
from plane_geometry_visual_data import validasi_data as validasi_geometri_datar
from solid_geometry_visual_data import validasi_data as validasi_geometri_ruang

PENYAJIAN_VERSI = 1
RENDERER_VERSI = 1
ASAL_TEKS = frozenset({"warisan", "bawaan", "cerita"})
STATUS_VISUAL = frozenset({"tanpa_visual", "siap", "warisan", "tidak_valid"})

_KUNCI_TERLARANG = frozenset({
    "kunci", "key", "answer", "jawaban", "malrule", "diagnosis", "diagnosa",
    "reason", "alasan", "pembahasan", "html", "svg", "markup",
})
_MARKUP_RAW = re.compile(r"<[^>]*>")
_EVENT_HANDLER = re.compile(r"(?:^|[^a-z0-9_])on[a-z]+\s*=", re.I)
_SIDIK_SHA256 = re.compile(r"[0-9a-f]{64}")
_PANJANG_LABEL_PLACEHOLDER_MAKS = 200


def _normalisasi_kunci(kunci: str) -> str:
    """Normalisasi nama field untuk pemeriksaan batas descriptor."""
    bentuk = unicodedata.normalize("NFKC", kunci)
    bentuk = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", bentuk).casefold()
    return re.sub(r"[^a-z0-9]+", "_", bentuk).strip("_")


def _kunci_terlarang(kunci: str) -> bool:
    normal = _normalisasi_kunci(kunci)
    token = tuple(bagian for bagian in normal.split("_") if bagian)
    bentuk_rapat = normal.replace("_", "")
    for rahasia in _KUNCI_TERLARANG:
        rahasia_normal = _normalisasi_kunci(rahasia)
        if rahasia_normal in token or bentuk_rapat == rahasia_normal:
            return True
    return bentuk_rapat in {"correctanswer", "answerkey"}


def _iter_mapping(nilai: Mapping[Any, Any], jalur: str):
    terlihat = set()
    for kunci, isi in nilai.items():
        if not isinstance(kunci, str):
            raise ValueError(f"kunci mapping wajib berupa string di {jalur}")
        if kunci in terlihat:
            raise ValueError(f"kunci mapping duplikat di {jalur}: {kunci}")
        terlihat.add(kunci)
        yield kunci, isi


def _bekukan(nilai: Any) -> Any:
    if isinstance(nilai, Mapping):
        return MappingProxyType({k: _bekukan(v) for k, v in _iter_mapping(nilai, "data")})
    if isinstance(nilai, (list, tuple)):
        return tuple(_bekukan(v) for v in nilai)
    return nilai


def _ke_json(nilai: Any, jalur: str = "nilai") -> Any:
    if isinstance(nilai, Mapping):
        return {
            kunci: _ke_json(isi, f"{jalur}.{kunci}")
            for kunci, isi in _iter_mapping(nilai, jalur)
        }
    if isinstance(nilai, (list, tuple)):
        return [_ke_json(v, f"{jalur}[]") for v in nilai]
    if isinstance(nilai, (str, int, bool)) or nilai is None:
        return nilai
    if isinstance(nilai, float) and math.isfinite(nilai):
        return nilai
    raise ValueError(f"nilai tidak dapat diserialisasi secara kanonis: {nilai!r}")


def serialisasi_kanonis(nilai: Any) -> str:
    """JSON UTF-8 logis dengan key stabil dan tanpa spasi tidak bermakna."""
    try:
        return json.dumps(
            _ke_json(nilai),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as galat:
        raise ValueError("nilai bukan JSON kanonis yang didukung") from galat


def _hash(nilai: Any) -> str:
    return hashlib.sha256(serialisasi_kanonis(nilai).encode("utf-8")).hexdigest()


def fingerprint_matematis(
    versi: int,
    template_id: str,
    level: str,
    parameter: Mapping[str, Any],
) -> str:
    """Identitas SHA-256 atas versi, template, level, dan parameter kanonis."""
    if not isinstance(versi, int) or isinstance(versi, bool) or versi < 1:
        raise ValueError("versi matematis harus bilangan bulat positif")
    if not isinstance(template_id, str) or not template_id:
        raise ValueError("template id wajib diisi")
    if level not in LEVEL:
        raise ValueError(f"level tidak dikenal: {level!r}")
    if not isinstance(parameter, Mapping):
        raise ValueError("parameter wajib berupa mapping")
    return _hash({
        "versi": versi,
        "template_id": template_id,
        "level": level,
        "parameter": parameter,
    })


def _validasi_descriptor(nilai: Any, jalur: str = "data") -> None:
    if isinstance(nilai, Mapping):
        normal_terlihat = set()
        for kunci, isi in _iter_mapping(nilai, jalur):
            normal = _normalisasi_kunci(kunci)
            if normal in normal_terlihat:
                raise ValueError(
                    f"kunci descriptor duplikat setelah normalisasi di {jalur}: {kunci}"
                )
            normal_terlihat.add(normal)
            if _kunci_terlarang(kunci):
                raise ValueError(f"field descriptor terlarang: {jalur}.{kunci}")
            _validasi_descriptor(isi, f"{jalur}.{kunci}")
        return
    if isinstance(nilai, (list, tuple)):
        for indeks, isi in enumerate(nilai):
            _validasi_descriptor(isi, f"{jalur}[{indeks}]")
        return
    if isinstance(nilai, str) and (
        _MARKUP_RAW.search(nilai) or _EVENT_HANDLER.search(nilai)
    ):
        raise ValueError(f"markup HTML/SVG raw dilarang di {jalur}")
    if isinstance(nilai, float) and not math.isfinite(nilai):
        raise ValueError(f"angka non-finite dilarang di {jalur}")
    if not isinstance(nilai, (str, int, float, bool, type(None))):
        raise ValueError(f"tipe descriptor tidak didukung di {jalur}")


def _validasi_placeholder_v1(data: Mapping[str, Any]) -> None:
    if set(data) != {"label"}:
        raise ValueError("data placeholder v1 wajib tepat memiliki field label")
    label = data["label"]
    if not isinstance(label, str) or not label.strip():
        raise ValueError("label placeholder wajib berupa teks yang tidak kosong")
    if len(label) > _PANJANG_LABEL_PLACEHOLDER_MAKS:
        raise ValueError(
            "label placeholder maksimal "
            f"{_PANJANG_LABEL_PLACEHOLDER_MAKS} karakter"
        )


def _validasi_bilangan_bulat_dalam_rentang(
    data: Mapping[str, Any],
    nama: str,
    minimum: int,
    maksimum: int,
) -> None:
    nilai = data[nama]
    if type(nilai) is not int or not minimum <= nilai <= maksimum:
        raise ValueError(
            f"{nama} wajib bilangan bulat {minimum}..{maksimum}"
        )


def _validasi_korek_v1(data: Mapping[str, Any]) -> None:
    if set(data) != {"n_tampil", "awal", "tambah"}:
        raise ValueError(
            "data korek v1 wajib tepat memiliki field n_tampil, awal, tambah"
        )
    _validasi_bilangan_bulat_dalam_rentang(data, "n_tampil", 1, 7)
    _validasi_bilangan_bulat_dalam_rentang(data, "awal", 3, 7)
    _validasi_bilangan_bulat_dalam_rentang(data, "tambah", 2, 4)


def _validasi_titik_v1(data: Mapping[str, Any]) -> None:
    if set(data) != {"n_tampil"}:
        raise ValueError("data titik v1 wajib tepat memiliki field n_tampil")
    _validasi_bilangan_bulat_dalam_rentang(data, "n_tampil", 1, 7)


_SKEMA_DESCRIPTOR = {
    ("placeholder", 1): _validasi_placeholder_v1,
    ("korek", 1): _validasi_korek_v1,
    ("titik", 1): _validasi_titik_v1,
    ("korek", 2): validasi_korek,
    ("titik", 2): validasi_titik,
    ("geometri_datar", 1): validasi_geometri_datar,
    ("geometri_ruang", 1): validasi_geometri_ruang,
    ("jalur_petak", 1): validasi_petak,
    ("linimasa_jam", 1): validasi_waktu,
    ("skala_peta", 1): validasi_skala,
    ("venn_dua", 1): validasi_venn,
    ("susunan_objek", 1): validasi_susunan,
    ("adegan_awal", 1): validasi_adegan_awal,
    **{(jenis, 1): validator for jenis, validator in VALIDATOR_STATISTIKA.items()},
}


def _validasi_schema_descriptor(
    jenis: str,
    versi: int,
    data: Mapping[str, Any],
) -> None:
    validator = _SKEMA_DESCRIPTOR.get((jenis, versi))
    if validator is None:
        raise ValueError(f"jenis/versi descriptor tidak didukung: {jenis!r} v{versi!r}")
    validator(data)


@dataclass(frozen=True)
class DescriptorVisual:
    """Instruksi visual typed; hanya data aman, tanpa markup hasil render."""

    jenis: str
    versi: int
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.jenis, str) or not self.jenis:
            raise ValueError("jenis descriptor wajib diisi")
        if not isinstance(self.versi, int) or isinstance(self.versi, bool) or self.versi < 1:
            raise ValueError("versi descriptor harus bilangan bulat positif")
        if not isinstance(self.data, Mapping):
            raise ValueError("data descriptor wajib berupa mapping")
        _validasi_descriptor(self.data)
        _validasi_schema_descriptor(self.jenis, self.versi, self.data)
        object.__setattr__(self, "data", _bekukan(self.data))

    def ke_dict(self) -> dict[str, Any]:
        return {"jenis": self.jenis, "versi": self.versi, "data": _ke_json(self.data)}


@dataclass(frozen=True)
class PenyajianPertanyaan:
    """Snapshot lengkap pengalaman pertanyaan anak, immutable."""

    penyajian_versi: int
    renderer_versi: int
    teks_soal: str
    bagian_soal: str
    tantangan_soal: bool
    minta_restatement: bool
    asal_teks: str
    status_visual: str
    mode_representasi: str
    descriptor: Optional[DescriptorVisual]
    fingerprint_matematis: str
    fingerprint_penyajian: str = field(repr=False)

    def __post_init__(self) -> None:
        _validasi_penyajian(self)


def _validasi_domain(
    penyajian_versi: Any,
    renderer_versi: Any,
    teks_soal: Any,
    bagian_soal: Any,
    tantangan_soal: Any,
    minta_restatement: Any,
    asal_teks: Any,
    status_visual: Any,
    mode_representasi: Any,
    descriptor: Optional[DescriptorVisual],
) -> None:
    if type(penyajian_versi) is not int or penyajian_versi != PENYAJIAN_VERSI:
        raise ValueError(f"versi penyajian tidak didukung: {penyajian_versi!r}")
    if type(renderer_versi) is not int or renderer_versi != RENDERER_VERSI:
        raise ValueError(f"versi renderer tidak didukung: {renderer_versi!r}")
    if not isinstance(teks_soal, str) or not teks_soal:
        raise ValueError("teks soal wajib diisi")
    if not isinstance(bagian_soal, str):
        raise ValueError("bagian soal wajib berupa teks")
    if type(tantangan_soal) is not bool or type(minta_restatement) is not bool:
        raise ValueError("flag penyajian wajib boolean")
    if asal_teks not in ASAL_TEKS:
        raise ValueError(f"asal teks tidak dikenal: {asal_teks!r}")
    if status_visual not in STATUS_VISUAL:
        raise ValueError(f"status visual tidak dikenal: {status_visual!r}")
    if not isinstance(mode_representasi, str) or not mode_representasi:
        raise ValueError("mode representasi wajib diisi")
    if descriptor is not None and not isinstance(descriptor, DescriptorVisual):
        raise ValueError("descriptor wajib bertipe DescriptorVisual")
    if descriptor is not None:
        if not isinstance(descriptor.jenis, str) or not descriptor.jenis:
            raise ValueError("jenis descriptor wajib diisi")
        if type(descriptor.versi) is not int or descriptor.versi < 1:
            raise ValueError("versi descriptor harus bilangan bulat positif")
        if not isinstance(descriptor.data, Mapping):
            raise ValueError("data descriptor wajib berupa mapping")
        _validasi_descriptor(descriptor.data)
        _validasi_schema_descriptor(
            descriptor.jenis, descriptor.versi, descriptor.data
        )
    if status_visual == "siap" and descriptor is None:
        raise ValueError("descriptor wajib ada untuk visual siap")
    if status_visual != "siap" and descriptor is not None:
        raise ValueError("descriptor hanya boleh ada untuk visual siap")
    if status_visual in {"tanpa_visual", "warisan"} and mode_representasi != "teks-v1":
        raise ValueError("mode representasi nonvisual wajib teks-v1")


def _muatan_tanpa_fingerprint(
    penyajian_versi: int,
    renderer_versi: int,
    teks_soal: str,
    bagian_soal: str,
    tantangan_soal: bool,
    minta_restatement: bool,
    asal_teks: str,
    status_visual: str,
    mode_representasi: str,
    descriptor: Optional[DescriptorVisual],
    sidik_matematis: str,
) -> dict[str, Any]:
    return {
        "penyajian_versi": penyajian_versi,
        "renderer_versi": renderer_versi,
        "teks_soal": teks_soal,
        "bagian_soal": bagian_soal,
        "tantangan_soal": tantangan_soal,
        "minta_restatement": minta_restatement,
        "asal_teks": asal_teks,
        "status_visual": status_visual,
        "mode_representasi": mode_representasi,
        "descriptor": None if descriptor is None else descriptor.ke_dict(),
        "fingerprint_matematis": sidik_matematis,
    }


def _validasi_sidik(nilai: Any, nama: str) -> None:
    if not isinstance(nilai, str) or not _SIDIK_SHA256.fullmatch(nilai):
        raise ValueError(f"fingerprint {nama} tidak valid")


def _validasi_penyajian(penyajian: PenyajianPertanyaan) -> None:
    """Validasi lengkap juga untuk konstruksi langsung dan serialisasi."""
    _validasi_domain(
        penyajian.penyajian_versi,
        penyajian.renderer_versi,
        penyajian.teks_soal,
        penyajian.bagian_soal,
        penyajian.tantangan_soal,
        penyajian.minta_restatement,
        penyajian.asal_teks,
        penyajian.status_visual,
        penyajian.mode_representasi,
        penyajian.descriptor,
    )
    _validasi_sidik(penyajian.fingerprint_matematis, "matematis")
    _validasi_sidik(penyajian.fingerprint_penyajian, "penyajian")
    muatan = _muatan_tanpa_fingerprint(
        penyajian.penyajian_versi,
        penyajian.renderer_versi,
        penyajian.teks_soal,
        penyajian.bagian_soal,
        penyajian.tantangan_soal,
        penyajian.minta_restatement,
        penyajian.asal_teks,
        penyajian.status_visual,
        penyajian.mode_representasi,
        penyajian.descriptor,
        penyajian.fingerprint_matematis,
    )
    if penyajian.fingerprint_penyajian != _hash(muatan):
        raise ValueError("fingerprint penyajian tidak cocok")


def buat_penyajian(
    *,
    template_id: str,
    level: str,
    parameter: Mapping[str, Any],
    teks_soal: str,
    bagian_soal: str = "",
    tantangan_soal: bool = False,
    minta_restatement: bool = False,
    asal_teks: str = "bawaan",
    status_visual: str = "tanpa_visual",
    mode_representasi: str = "teks-v1",
    descriptor: Optional[DescriptorVisual] = None,
    penyajian_versi: int = PENYAJIAN_VERSI,
    renderer_versi: int = RENDERER_VERSI,
) -> PenyajianPertanyaan:
    """Bangun snapshot dari allow-list field aman; parameter hanya di-hash."""
    if level not in LEVEL:
        raise ValueError(f"level tidak dikenal: {level!r}")
    _validasi_domain(
        penyajian_versi, renderer_versi, teks_soal, bagian_soal,
        tantangan_soal, minta_restatement, asal_teks, status_visual,
        mode_representasi, descriptor,
    )
    sidik_matematis = fingerprint_matematis(
        penyajian_versi, template_id, level, parameter
    )
    muatan = _muatan_tanpa_fingerprint(
        penyajian_versi, renderer_versi, teks_soal, bagian_soal,
        tantangan_soal, minta_restatement, asal_teks, status_visual,
        mode_representasi, descriptor, sidik_matematis,
    )
    return PenyajianPertanyaan(
        penyajian_versi=penyajian_versi,
        renderer_versi=renderer_versi,
        teks_soal=teks_soal,
        bagian_soal=bagian_soal,
        tantangan_soal=tantangan_soal,
        minta_restatement=minta_restatement,
        asal_teks=asal_teks,
        status_visual=status_visual,
        mode_representasi=mode_representasi,
        descriptor=descriptor,
        fingerprint_matematis=sidik_matematis,
        fingerprint_penyajian=_hash(muatan),
    )


def _ke_muatan(penyajian: PenyajianPertanyaan) -> dict[str, Any]:
    muatan = _muatan_tanpa_fingerprint(
        penyajian.penyajian_versi,
        penyajian.renderer_versi,
        penyajian.teks_soal,
        penyajian.bagian_soal,
        penyajian.tantangan_soal,
        penyajian.minta_restatement,
        penyajian.asal_teks,
        penyajian.status_visual,
        penyajian.mode_representasi,
        penyajian.descriptor,
        penyajian.fingerprint_matematis,
    )
    muatan["fingerprint_penyajian"] = penyajian.fingerprint_penyajian
    return muatan


def serialisasi_penyajian(penyajian: PenyajianPertanyaan) -> str:
    """Serialisasi snapshot sebagai JSON kanonis."""
    if not isinstance(penyajian, PenyajianPertanyaan):
        raise ValueError("objek bukan PenyajianPertanyaan")
    _validasi_penyajian(penyajian)
    muatan = _ke_muatan(penyajian)
    sidik = muatan.pop("fingerprint_penyajian")
    if sidik != _hash(muatan):
        raise ValueError("fingerprint penyajian tidak cocok")
    muatan["fingerprint_penyajian"] = sidik
    return serialisasi_kanonis(muatan)


_FIELD = frozenset({
    "penyajian_versi", "renderer_versi", "teks_soal", "bagian_soal",
    "tantangan_soal", "minta_restatement", "asal_teks", "status_visual",
    "mode_representasi", "descriptor", "fingerprint_matematis",
    "fingerprint_penyajian",
})


def deserialisasi_penyajian(teks: str) -> PenyajianPertanyaan:
    """Parse ketat: bentuk, domain, versi, canonical form, dan hash wajib sah."""
    if not isinstance(teks, str):
        raise ValueError("snapshot wajib berupa teks JSON")
    try:
        muatan = json.loads(teks)
    except (TypeError, json.JSONDecodeError) as galat:
        raise ValueError("snapshot bukan JSON valid") from galat
    if not isinstance(muatan, dict):
        raise ValueError("snapshot wajib berupa objek JSON")
    if set(muatan) != _FIELD:
        hilang = sorted(_FIELD - set(muatan))
        tambahan = sorted(set(muatan) - _FIELD)
        raise ValueError(f"field snapshot tidak tepat; hilang={hilang}, tambahan={tambahan}")
    if serialisasi_kanonis(muatan) != teks:
        raise ValueError("snapshot JSON tidak kanonis")

    descriptor_raw = muatan["descriptor"]
    descriptor = None
    if descriptor_raw is not None:
        if not isinstance(descriptor_raw, dict) or set(descriptor_raw) != {"jenis", "versi", "data"}:
            raise ValueError("descriptor tidak valid")
        descriptor = DescriptorVisual(
            descriptor_raw["jenis"], descriptor_raw["versi"], descriptor_raw["data"]
        )
    _validasi_domain(
        muatan["penyajian_versi"], muatan["renderer_versi"],
        muatan["teks_soal"], muatan["bagian_soal"], muatan["tantangan_soal"],
        muatan["minta_restatement"], muatan["asal_teks"],
        muatan["status_visual"], muatan["mode_representasi"], descriptor,
    )
    sidik_matematis = muatan["fingerprint_matematis"]
    _validasi_sidik(sidik_matematis, "matematis")
    sidik = muatan["fingerprint_penyajian"]
    tanpa_sidik = dict(muatan)
    tanpa_sidik.pop("fingerprint_penyajian")
    _validasi_sidik(sidik, "penyajian")
    if sidik != _hash(tanpa_sidik):
        raise ValueError("fingerprint penyajian tidak cocok")
    return PenyajianPertanyaan(
        penyajian_versi=muatan["penyajian_versi"],
        renderer_versi=muatan["renderer_versi"],
        teks_soal=muatan["teks_soal"],
        bagian_soal=muatan["bagian_soal"],
        tantangan_soal=muatan["tantangan_soal"],
        minta_restatement=muatan["minta_restatement"],
        asal_teks=muatan["asal_teks"],
        status_visual=muatan["status_visual"],
        mode_representasi=muatan["mode_representasi"],
        descriptor=descriptor,
        fingerprint_matematis=sidik_matematis,
        fingerprint_penyajian=sidik,
    )
