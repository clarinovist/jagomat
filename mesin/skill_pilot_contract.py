"""Kontrak pilot homogen versi1; bukan codec sesi campuran v2.

Metadata dibekukan sebelum pengerjaan dan diikat fingerprint konfirmasi baru.
Kontrak persiapan tanpa seed hanya untuk audit, bukan untuk penulis aplikasi.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Optional, Tuple

from skill_pilot import KonteksPilot, KunciFokus, validasi_fokus


@dataclass(frozen=True)
class ButirKontrakPilot:
    nomor: int
    sesi_soal_id: int
    konteks: Optional[KonteksPilot]
    sidik_variasi: Optional[str]
    fingerprint_penyajian: str
    target_fokus: Optional[KunciFokus] = None

    def __post_init__(self):
        if any(type(n) is not int or n < 1 for n in (self.nomor,self.sesi_soal_id)):
            raise ValueError("identitas butir pilot tidak sah")
        _sidik(self.fingerprint_penyajian)
        if self.konteks is None:
            if self.sidik_variasi is not None or self.target_fokus is not None:
                raise ValueError("pembanding bukan bukti tuntutan/fokus")
        else:
            if type(self.konteks) is not KonteksPilot:
                raise ValueError("konteks butir pilot tidak sah")
            _sidik(self.sidik_variasi)
            if self.target_fokus is not None:
                validasi_fokus(self.konteks,self.target_fokus)


@dataclass(frozen=True)
class KontrakPilot:
    siswa_id: int
    sesi_id: int
    profil_parameter: str
    versi_generator: int
    butir: Tuple[ButirKontrakPilot, ...]
    versi: int = 1
    seed: Optional[int] = None
    tujuan: str = "bebas"
    putaran_id: Optional[int] = None
    sumber_konfirmasi: Tuple[int, ...] = ()

    def __post_init__(self):
        if (type(self.versi) is not int or self.versi != 1
                or any(type(n) is not int or n < 1 for n in (self.siswa_id,self.sesi_id))
                or type(self.profil_parameter) is not str or self.profil_parameter not in ("P3","P4","P5","P6")
                or type(self.versi_generator) is not int or self.versi_generator not in (1, 2)
                or type(self.butir) is not tuple or not self.butir
                or any(type(b) is not ButirKontrakPilot for b in self.butir)):
            raise ValueError("kontrak pilot tidak sah")
        if (tuple(b.nomor for b in self.butir) != tuple(range(1,len(self.butir)+1))
                or len({b.sesi_soal_id for b in self.butir}) != len(self.butir)):
            raise ValueError("butir pilot harus lengkap dan unik")
        if not any(b.konteks is not None for b in self.butir):
            raise ValueError("kontrak tidak memuat tuntutan pilot")
        if (self.seed is not None and (type(self.seed) is not int or self.seed < 0)):
            raise ValueError("seed kontrak tidak sah")
        if (type(self.tujuan) is not str or self.tujuan not in (
                'bebas','pemetaan','pengenalan','latihan_terbimbing','penguatan','evaluasi','checkpoint')
                or (self.putaran_id is not None and (type(self.putaran_id) is not int or self.putaran_id < 1))
                or type(self.sumber_konfirmasi) is not tuple
                or any(type(n) is not int or n < 1 for n in self.sumber_konfirmasi)
                or len(set(self.sumber_konfirmasi)) != len(self.sumber_konfirmasi)):
            raise ValueError("envelope atau sumber kontrak tidak sah")
        fokus={}
        for b in self.butir:
            if b.konteks is not None and b.konteks.profil_parameter != self.profil_parameter:
                raise ValueError("pilot belum mendukung campuran profil")
            if b.target_fokus is not None:
                if b.target_fokus in fokus and fokus[b.target_fokus] != b.konteks:
                    raise ValueError("satu kunci fokus tidak boleh dua tuntutan")
                fokus[b.target_fokus]=b.konteks
        if len(fokus)>2:
            raise ValueError("maksimal dua fokus pilot")


def _sidik(nilai):
    if (type(nilai) is not str or len(nilai)!=64
            or any(c not in "0123456789abcdef" for c in nilai)):
        raise ValueError("sidik pilot tidak sah")


def serialisasi(kontrak):
    if type(kontrak) is not KontrakPilot:
        raise ValueError("kontrak pilot tidak sah")
    return json.dumps(asdict(kontrak),sort_keys=True,ensure_ascii=False,separators=(",",":"))


def fingerprint(kontrak):
    return hashlib.sha256(serialisasi(kontrak).encode()).hexdigest()


def _objek_unik(pasangan):
    hasil={}
    for k,v in pasangan:
        if k in hasil: raise ValueError("field pilot duplikat")
        hasil[k]=v
    return hasil


def _field(isi,nama):
    if type(isi) is not dict or set(isi)!=set(nama):
        raise ValueError("field pilot tidak lengkap atau asing")


def deserialisasi(teks):
    if type(teks) is not str: raise ValueError("kontrak pilot wajib JSON")
    try:
        isi=json.loads(teks,object_pairs_hook=_objek_unik)
    except (json.JSONDecodeError,RecursionError) as galat:
        raise ValueError("JSON pilot tidak sah") from galat
    _field(isi,("siswa_id","sesi_id","profil_parameter","versi_generator","butir","versi",
                "seed","tujuan","putaran_id","sumber_konfirmasi"))
    if type(isi['sumber_konfirmasi']) is not list:
        raise ValueError('sumber konfirmasi wajib larik')
    if type(isi["butir"]) is not list: raise ValueError("butir pilot wajib larik")
    butir=[]
    for b in isi["butir"]:
        _field(b,("nomor","sesi_soal_id","konteks","sidik_variasi","fingerprint_penyajian","target_fokus"))
        k=b["konteks"]
        if k is not None:
            _field(k,("tuntutan_id","profil_parameter","mode_representasi","versi_rubrik"))
            k=KonteksPilot(**k)
        fokus=b["target_fokus"]
        if fokus is not None:
            if type(fokus) is not list: raise ValueError("fokus pilot wajib larik")
            fokus=tuple(fokus)
        butir.append(ButirKontrakPilot(b["nomor"],b["sesi_soal_id"],k,b["sidik_variasi"],
                                      b["fingerprint_penyajian"],fokus))
    return KontrakPilot(isi["siswa_id"],isi["sesi_id"],isi["profil_parameter"],
                        isi["versi_generator"],tuple(butir),isi["versi"],isi['seed'],
                        isi['tujuan'],isi['putaran_id'],tuple(isi['sumber_konfirmasi']))
