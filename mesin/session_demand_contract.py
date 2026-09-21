"""Codec murni kontrak campuran v2, belum dihubungkan ke persistensi/selector.

Ini kontrak struktur, bukan izin aktivasi rubrik atau sertifikasi hasil. Adapter
kelak wajib memvalidasi kepemilikan, snapshot soal dan provenance sumber; reducer
menegakkan kuota, jeda, representasi, konfirmasi dan status. Guard v1 tetap utuh.
"""
import json
from dataclasses import asdict, dataclass
from typing import Optional, Tuple

from templates import LEVEL

KunciFokus = Tuple[str, str, Optional[str]]


def _teks(nilai):
    return type(nilai) is str and bool(nilai.strip()) and nilai == nilai.strip()


def _positif(nilai):
    return type(nilai) is int and nilai > 0


def _kunci(nilai):
    return (type(nilai) is tuple and len(nilai) == 3 and _teks(nilai[0])
            and _teks(nilai[1]) and nilai[1] in ("B", "K", "H", "E", "N", "T")
            and (nilai[2] is None or _teks(nilai[2])))


@dataclass(frozen=True)
class KonteksTuntutan:
    template_id: str
    profil_parameter: str
    mode_representasi: str
    versi_rubrik: str
    tuntutan_id: str

    def __post_init__(self):
        nilai = (self.template_id, self.profil_parameter, self.mode_representasi,
                 self.versi_rubrik, self.tuntutan_id)
        if (not all(_teks(v) for v in nilai)
                or self.profil_parameter not in LEVEL):
            raise ValueError("identitas konteks tuntutan tidak sah")


@dataclass(frozen=True)
class FokusTuntutan:
    kunci: KunciFokus
    konteks: KonteksTuntutan
    sumber_konfirmasi_ids: Tuple[int, ...]

    def __post_init__(self):
        if (not _kunci(self.kunci) or type(self.konteks) is not KonteksTuntutan
                or self.kunci[0] != self.konteks.template_id
                or type(self.sumber_konfirmasi_ids) is not tuple
                or not self.sumber_konfirmasi_ids
                or any(not _positif(n) for n in self.sumber_konfirmasi_ids)
                or len(set(self.sumber_konfirmasi_ids)) != len(self.sumber_konfirmasi_ids)):
            raise ValueError("fokus atau rujukan sumber tidak sah")
        object.__setattr__(self, "sumber_konfirmasi_ids", tuple(sorted(self.sumber_konfirmasi_ids)))


@dataclass(frozen=True)
class ButirTuntutan:
    nomor: int
    konteks: KonteksTuntutan
    target_fokus: Optional[KunciFokus] = None

    def __post_init__(self):
        if (not _positif(self.nomor) or type(self.konteks) is not KonteksTuntutan
                or (self.target_fokus is not None and not _kunci(self.target_fokus))):
            raise ValueError("butir tuntutan tidak sah")


@dataclass(frozen=True)
class KontrakSesiTuntutan:
    butir: Tuple[ButirTuntutan, ...]
    fokus: Tuple[FokusTuntutan, ...] = ()
    versi: int = 2

    def __post_init__(self):
        if type(self.versi) is not int or self.versi != 2:
            raise ValueError("versi kontrak tuntutan tidak dikenal")
        if (type(self.butir) is not tuple or not self.butir
                or any(type(b) is not ButirTuntutan for b in self.butir)
                or tuple(b.nomor for b in self.butir) != tuple(range(1, len(self.butir) + 1))):
            raise ValueError("nomor butir wajib berurutan dan lengkap")
        if (type(self.fokus) is not tuple or len(self.fokus) > 2
                or any(type(f) is not FokusTuntutan for f in self.fokus)
                or len({f.kunci for f in self.fokus}) != len(self.fokus)):
            raise ValueError("maksimal dua fokus kanonis yang berbeda")
        fokus = {f.kunci: f for f in self.fokus}
        terpakai = set()
        for butir in self.butir:
            if butir.target_fokus is None:
                continue
            sumber = fokus.get(butir.target_fokus)
            if sumber is None or butir.konteks != sumber.konteks:
                raise ValueError("tuntutan probe tidak cocok dengan konteks fokus sumber")
            terpakai.add(butir.target_fokus)
        if terpakai != set(fokus):
            raise ValueError("fokus tanpa butir sasaran")
        object.__setattr__(self, "fokus", tuple(sorted(
            self.fokus, key=lambda f: (f.kunci[0], f.kunci[1],
                                      f.kunci[2] is not None, f.kunci[2] or ""))))

    @property
    def profil_parameter(self) -> Tuple[str, ...]:
        return tuple(p for p in LEVEL if any(b.konteks.profil_parameter == p for b in self.butir))

    @property
    def ringkasan(self) -> str:
        profil = self.profil_parameter
        if len(profil) == 1:
            return "Profil " + profil[0]
        return "Profil campuran: " + ", ".join(profil)


def serialisasi(kontrak: KontrakSesiTuntutan) -> str:
    """Metadata dibekukan sebagai JSON kanonis, tanpa level global buatan."""
    if type(kontrak) is not KontrakSesiTuntutan:
        raise ValueError("kontrak sesi tuntutan tidak sah")
    return json.dumps(asdict(kontrak), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _objek_unik(pasangan):
    hasil = {}
    for nama, nilai in pasangan:
        if nama in hasil:
            raise ValueError("field kontrak duplikat")
        hasil[nama] = nilai
    return hasil


def _field(isi, wajib):
    if type(isi) is not dict or set(isi) != set(wajib):
        raise ValueError("field kontrak tidak lengkap atau tidak dikenal")


def _baca_konteks(isi):
    _field(isi, ("template_id", "profil_parameter", "mode_representasi", "versi_rubrik", "tuntutan_id"))
    return KonteksTuntutan(**isi)


def _baca_kunci(isi):
    if type(isi) is not list:
        raise ValueError("kunci fokus wajib larik")
    hasil = tuple(isi)
    if not _kunci(hasil):
        raise ValueError("kunci fokus tidak sah")
    return hasil


def deserialisasi(teks: str) -> KontrakSesiTuntutan:
    """Tolak downgrade v1, field tambahan dan metadata parsial; tidak menambal."""
    if type(teks) is not str:
        raise ValueError("kontrak JSON wajib teks")
    try:
        isi = json.loads(teks, object_pairs_hook=_objek_unik)
    except (json.JSONDecodeError, RecursionError) as galat:
        raise ValueError("kontrak JSON tidak sah") from galat
    _field(isi, ("versi", "butir", "fokus"))
    if type(isi["butir"]) is not list or type(isi["fokus"]) is not list:
        raise ValueError("butir dan fokus wajib larik")
    butir, fokus = [], []
    for b in isi["butir"]:
        _field(b, ("nomor", "konteks", "target_fokus"))
        butir.append(ButirTuntutan(b["nomor"], _baca_konteks(b["konteks"]),
                                  None if b["target_fokus"] is None else _baca_kunci(b["target_fokus"])))
    for f in isi["fokus"]:
        _field(f, ("kunci", "konteks", "sumber_konfirmasi_ids"))
        if type(f["sumber_konfirmasi_ids"]) is not list:
            raise ValueError("rujukan konfirmasi wajib larik")
        fokus.append(FokusTuntutan(_baca_kunci(f["kunci"]), _baca_konteks(f["konteks"]),
                                  tuple(f["sumber_konfirmasi_ids"])))
    return KontrakSesiTuntutan(tuple(butir), tuple(fokus), isi["versi"])
