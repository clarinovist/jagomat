"""Proyeksi immutable satu tuntutan; status tetap diputuskan learning_cycle.

Adapter persistensi kelak wajib mencocokkan metadata dengan snapshot aktif.
Tipe murni bukan bukti ownership atau izin menerima metadata dari HTTP.
"""
from dataclasses import dataclass, replace
from typing import Optional, Tuple

from skill_pilot import KonteksPilot, KunciFokus, validasi_fokus


@dataclass(frozen=True)
class ButirBuktiPilot:
    sesi_id: int
    nomor: int
    konfirmasi_id: Optional[int]
    konteks: KonteksPilot
    sidik_variasi: str

    def __post_init__(self):
        if (type(self.sesi_id) is not int or self.sesi_id < 1
                or type(self.nomor) is not int or self.nomor < 1
                or (self.konfirmasi_id is not None and
                    (type(self.konfirmasi_id) is not int or self.konfirmasi_id < 1))
                or type(self.konteks) is not KonteksPilot
                or type(self.sidik_variasi) is not str or len(self.sidik_variasi) != 64
                or any(c not in "0123456789abcdef" for c in self.sidik_variasi)):
            raise ValueError("metadata butir bukti pilot tidak sah")


@dataclass(frozen=True)
class FokusBuktiPilot:
    putaran_id: int
    kunci: KunciFokus
    konteks: KonteksPilot

    def __post_init__(self):
        if type(self.putaran_id) is not int or self.putaran_id < 1:
            raise ValueError("putaran fokus pilot tidak sah")
        validasi_fokus(self.konteks, self.kunci)


@dataclass(frozen=True)
class SumberFokusDicabut:
    putaran_id: int
    konteks: KonteksPilot
    sesi_ids: Tuple[int, ...]

    def __post_init__(self):
        if (type(self.putaran_id) is not int or self.putaran_id < 1
                or type(self.konteks) is not KonteksPilot or type(self.sesi_ids) is not tuple
                or not self.sesi_ids or any(type(n) is not int or n < 1 for n in self.sesi_ids)
                or len(set(self.sesi_ids)) != len(self.sesi_ids)):
            raise ValueError('metadata sumber fokus dicabut tidak sah')


@dataclass(frozen=True)
class BuktiPilot:
    bukti: object
    butir: Tuple[ButirBuktiPilot, ...] = ()
    fokus: Tuple[FokusBuktiPilot, ...] = ()
    sumber_dicabut: Tuple[SumberFokusDicabut, ...] = ()

    def __post_init__(self):
        from learning_cycle import BuktiSiklus
        if type(self.bukti) is not BuktiSiklus:
            raise ValueError("bukti siklus pilot tidak sah")
        if (type(self.butir) is not tuple or any(type(b) is not ButirBuktiPilot for b in self.butir)
                or len({(b.sesi_id,b.nomor) for b in self.butir}) != len(self.butir)
                or type(self.fokus) is not tuple or any(type(f) is not FokusBuktiPilot for f in self.fokus)
                or len({(f.putaran_id,f.kunci) for f in self.fokus}) != len(self.fokus)):
            raise ValueError("metadata pilot duplikat atau mutable")
        for pid in {f.putaran_id for f in self.fokus}:
            if sum(f.putaran_id == pid for f in self.fokus) > 2:
                raise ValueError("maksimal dua fokus kanonis")
        sesi = {s.id:s for s in self.bukti.sesi}
        putaran = {p.id:p for p in self.bukti.putaran}
        if (type(self.sumber_dicabut) is not tuple
                or any(type(m) is not SumberFokusDicabut for m in self.sumber_dicabut)
                or len({m.putaran_id for m in self.sumber_dicabut}) != len(self.sumber_dicabut)):
            raise ValueError('metadata masalah sumber duplikat atau tidak sah')
        for m in self.sumber_dicabut:
            if (m.putaran_id not in putaran
                    or not any(f.putaran_id == m.putaran_id and f.konteks == m.konteks for f in self.fokus)
                    or any(sid not in sesi or sesi[sid].siswa_id != self.bukti.siswa_id for sid in m.sesi_ids)):
                raise ValueError('masalah sumber bukan milik konteks putaran')
        for sid in {b.sesi_id for b in self.butir}:
            butir_sesi = tuple(b for b in self.butir if b.sesi_id == sid)
            s = sesi.get(sid)
            # Snapshot yang diketahui pilot harus lengkap. Metadata sebagian
            # dapat menyembunyikan kegagalan pada varian lain pola yang sama.
            if (s is not None and s.konfirmasi_id is not None
                    and any(o.template_id in {b.konteks.template_id for b in butir_sesi}
                            and n not in {b.nomor for b in butir_sesi}
                            for n, o in enumerate(s.outcomes, 1))):
                raise ValueError("metadata tuntutan outcome tidak lengkap")
        for b in self.butir:
            s = sesi.get(b.sesi_id)
            if s is None or s.siswa_id != self.bukti.siswa_id or s.level != b.konteks.profil_parameter:
                raise ValueError("metadata bukan konteks sumber sesi")
            if s.konfirmasi_id != b.konfirmasi_id:
                raise ValueError("konfirmasi metadata bukan konfirmasi aktif")
            if s.konfirmasi_id is not None:
                if not 1 <= b.nomor <= len(s.outcomes):
                    raise ValueError("nomor outcome tidak cocok")
                o = s.outcomes[b.nomor-1]
                if (o.template_id != b.konteks.template_id
                        or o.mode_representasi != b.konteks.mode_representasi
                        or o.profil_parameter != b.konteks.profil_parameter):
                    raise ValueError("konteks outcome tidak cocok")
        for b in self.butir:
            s = sesi[b.sesi_id]
            if s.konfirmasi_id is not None:
                target = s.outcomes[b.nomor-1].target_fokus
                if target is not None and not any(
                    f.putaran_id == s.putaran_id and f.kunci == target and f.konteks == b.konteks
                    for f in self.fokus
                ):
                    raise ValueError("target outcome tidak cocok konteks fokus sumber")
        for f in self.fokus:
            p = putaran.get(f.putaran_id)
            if (p is None or p.siswa_id != self.bukti.siswa_id
                    or p.level != f.konteks.profil_parameter or f.kunci not in p.fokus):
                raise ValueError("konteks fokus tidak cocok putaran")


def proyeksi_bukti(paket, konteks):
    """Filter satu konteks sekaligus semua sumber invalidasi/fokusnya.

    Tidak memalsukan template_id untuk memecah fokus. Sesi/pola yang tidak
    memiliki metadata pilot tetap histori; tidak ditafsirkan menjadi tuntutan.
    """
    if type(paket) is not BuktiPilot or type(konteks) is not KonteksPilot:
        raise ValueError("bukti atau konteks pilot tidak sah")
    rusak = {m.putaran_id for m in paket.sumber_dicabut}
    sesi_rusak = {s.id for s in paket.bukti.sesi if s.putaran_id in rusak}
    cocok = {(b.sesi_id,b.nomor):b for b in paket.butir
             if b.konteks == konteks and b.sesi_id not in sesi_rusak}
    ids = {s for s,_ in cocok}
    fokus = {f.putaran_id:tuple(x.kunci for x in paket.fokus
                               if x.putaran_id == f.putaran_id and x.konteks == konteks)
             for f in paket.fokus if f.konteks == konteks and f.putaran_id not in rusak}
    sesi = []
    for s in paket.bukti.sesi:
        if s.id not in ids:
            continue
        outcomes = tuple(replace(o, fingerprint_matematis=cocok[(s.id,n)].sidik_variasi)
                         for n,o in enumerate(s.outcomes,1) if (s.id,n) in cocok)
        target = tuple(k for k in s.target_fokus if k in fokus.get(s.putaran_id,()))
        sesi.append(replace(s,outcomes=outcomes,target_fokus=target,pilot=False,tuntutan_pilot=True,
                            pola_tersedia=(konteks.template_id,)))
    pids = {s.putaran_id for s in sesi if s.putaran_id is not None} | set(fokus)
    putaran = tuple(replace(p,fokus=fokus.get(p.id,()),pilot=False) for p in paket.bukti.putaran if p.id in pids)
    kejadian = []
    for e in paket.bukti.kejadian:
        if not (e.jenis == "diganti_level" or e.sesi_id in ids
                or (e.sesi_id is None and e.putaran_id in pids)):
            continue
        # Override dan event intervensi putaran yang sama bisa mengenai tuntutan
        # lain. Jangan membiarkannya masuk melalui kunci pola yang sama.
        data = dict(e.data)
        kunci = data.get("fokus")
        if kunci and e.sesi_id is None:
            sah = fokus.get(e.putaran_id, ())
            if e.jenis == "fokus_diubah":
                data["fokus"] = tuple(k for k in kunci if k in sah)
                if not data["fokus"]:
                    continue
                e = replace(e, data=tuple(sorted(data.items())))
            elif kunci not in sah:
                continue
        kejadian.append(e)
    return replace(paket.bukti, level_aktif=konteks.profil_parameter,
                   sesi=tuple(sesi),putaran=putaran,kejadian=tuple(kejadian))
