"""Resolver hak Pendamping murni; clock/snapshot/sakelar berasal server.

Tidak memberi enrollment atau menafsirkan grant v1 sebagai paket baru. Adapter
baca_status di ujung modul hanya membaca store; GET tidak membuat jendela kuota.
"""
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Optional, Tuple

import subscription as lama
import subscription_packages as paket

FITUR = ("balasan_pendamping", "pembacaan_foto")
STATUS_BERHAK = ("trial_aktif", "pro_aktif")


@dataclass(frozen=True)
class GrantHak:
    akun_id: str
    invoice_id: str
    paket: str
    penagihan: str
    mulai: int
    akhir: int
    jangkar_mulai: int
    indeks_bulan: int
    balasan: int
    foto: int
    versi: str = paket.VERSI


@dataclass(frozen=True)
class SnapshotHak:
    akun_id: str
    trial_mulai: Optional[int] = None
    transisi_mulai: Optional[int] = None
    grants: Tuple[GrantHak, ...] = ()
    # Hak lama dipertahankan, bukan dikonversi menjadi Pro/kuota buatan.
    periode_lama: Tuple[Tuple[int, int], ...] = ()
    terverifikasi: bool = True


@dataclass(frozen=True)
class Pemakaian:
    jendela_id: str
    fitur: str
    digunakan: int = 0
    direservasi: int = 0


@dataclass(frozen=True)
class StatusHak:
    status: str
    fitur: str
    akun_id: str
    paket: Optional[str] = None
    sumber: Optional[str] = None
    sumber_id: Optional[str] = None
    entitlement_sidik: Optional[str] = None
    entitlement_mulai: Optional[int] = None
    entitlement_akhir: Optional[int] = None
    jendela_id: Optional[str] = None
    jendela_mulai: Optional[int] = None
    jendela_akhir: Optional[int] = None
    limit: int = 0
    digunakan: int = 0
    direservasi: int = 0
    tersisa: int = 0
    isi_ulang: Optional[int] = None
    penegakan: bool = False

    @property
    def boleh(self):
        """OFF hanya bypass paywall, bukan izin melewati consent/pagu provider."""
        return not self.penegakan or self.status in STATUS_BERHAK


def sidik(nilai):
    return hashlib.sha256(json.dumps(
        nilai, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")).hexdigest()


def validasi_fitur(fitur):
    if type(fitur) is not str or fitur not in FITUR:
        raise ValueError("fitur kuota tidak sah")
    return fitur


def _validasi_snapshot(s, akun_id, sekarang):
    if not isinstance(s, SnapshotHak) or s.terverifikasi is not True or s.akun_id != akun_id:
        raise ValueError("snapshot hak tidak sah")
    if type(s.grants) is not tuple or type(s.periode_lama) is not tuple:
        raise ValueError("daftar hak tidak sah")
    if s.trial_mulai is None:
        if s.transisi_mulai is not None or s.grants or s.periode_lama:
            raise ValueError("hak tanpa enrollment")
        return
    lama.waktu(s.trial_mulai)
    batas = paket.akhir_coba(s.trial_mulai)
    if sekarang < s.trial_mulai:
        raise ValueError("clock mendahului enrollment")
    if s.transisi_mulai is not None:
        lama.waktu(s.transisi_mulai)
        if not s.trial_mulai <= s.transisi_mulai <= sekarang:
            raise ValueError("clock transisi tidak sah")
    elif s.grants:
        raise ValueError("grant tanpa adopsi paket")
    for rentang in s.periode_lama:
        if type(rentang) is not tuple or len(rentang) != 2:
            raise ValueError("periode lama tidak sah")
        awal, akhir = rentang
        lama.waktu(awal); lama.waktu(akhir)
        if not batas <= awal < akhir:
            raise ValueError("hak lama bertumpuk")
        batas = akhir
    identitas = set()
    for g in s.grants:
        if not isinstance(g, GrantHak) or g.akun_id != akun_id:
            raise ValueError("pemilik grant berbeda")
        lama.identitas(g.invoice_id, "invoice")
        if g.invoice_id in identitas:
            raise ValueError("grant ganda")
        identitas.add(g.invoice_id)
        p = paket.ambil_paket(g.paket, versi=g.versi)
        bulan = paket.jumlah_bulan(g.penagihan)
        lama.bilangan(g.indeks_bulan, 0, 120_000)
        for nilai in (g.mulai, g.akhir, g.jangkar_mulai):
            lama.waktu(nilai)
        for nilai in (g.balasan, g.foto):
            lama.bilangan(nilai)
        if (g.mulai < batas or g.mulai < s.transisi_mulai
                or g.mulai != paket.batas_bulan(g.jangkar_mulai, g.indeks_bulan)
                or g.akhir != paket.batas_bulan(g.jangkar_mulai, g.indeks_bulan + bulan)
                or (g.balasan, g.foto) != (p.kuota.balasan, p.kuota.foto)):
            raise ValueError("snapshot grant tidak sah")
        batas = g.akhir


def selesaikan(akun_id, snapshot, *, fitur, sekarang, pemakaian=(), penegakan=False):
    """Proyeksi deterministik; bukan bukti autentikasi atau admission jaringan.

    Pemakaian harus berasal ledger terverifikasi pada snapshot baca yang sama.
    Snapshot/rentang/pemakaian rusak memberi storage_tidak_terverifikasi. Parameter
    pemrograman (ID/fitur/clock/sakelar) salah ditolak, bukan dinormalisasi diam-diam.
    """
    lama.identitas(akun_id, "akun")
    validasi_fitur(fitur)
    lama.waktu(sekarang)
    if type(penegakan) is not bool:
        raise ValueError("sakelar penegakan tidak sah")
    kosong = dict(akun_id=akun_id, fitur=fitur, penegakan=penegakan)
    try:
        _validasi_snapshot(snapshot, akun_id, sekarang)
        if type(pemakaian) is not tuple:
            raise ValueError("pemakaian bukan snapshot")
        terlihat = set()
        for item in pemakaian:
            if not isinstance(item, Pemakaian):
                raise ValueError("pemakaian tidak sah")
            validasi_fitur(item.fitur)
            lama.bilangan(item.digunakan); lama.bilangan(item.direservasi)
            if (type(item.jendela_id) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", item.jendela_id) is None):
                raise ValueError("identitas jendela tidak sah")
            kunci = (item.jendela_id, item.fitur)
            if kunci in terlihat:
                raise ValueError("pemakaian ganda")
            terlihat.add(kunci)
        if snapshot.transisi_mulai is None:
            return StatusHak("belum_ditransisikan", **kosong)
        if any(a <= sekarang < b for a, b in snapshot.periode_lama):
            return StatusHak("belum_ditransisikan", **kosong)
        sumber = None
        batas_trial = paket.akhir_coba(snapshot.trial_mulai)
        if snapshot.trial_mulai <= sekarang < batas_trial:
            sumber, sumber_id, kode = "trial", "trial", "coba_gratis"
            awal, akhir = snapshot.trial_mulai, batas_trial
            kiri, kanan = awal, akhir
            kuota = paket.KUOTA_COBA
            balasan, foto = kuota.balasan, kuota.foto
            data = (akun_id, sumber, awal, akhir, balasan, foto)
            status = "trial_aktif"
        else:
            for g in snapshot.grants:
                if g.mulai <= sekarang < g.akhir:
                    sumber, sumber_id, kode = "grant_paket", g.invoice_id, g.paket
                    awal, akhir = g.mulai, g.akhir
                    balasan, foto = g.balasan, g.foto
                    data = (akun_id, sumber, g.invoice_id, g.versi, g.paket, g.penagihan,
                            awal, akhir, g.jangkar_mulai, g.indeks_bulan, balasan, foto)
                    status = "pro_aktif" if kode == "jago_pro" else "jago_tanpa_ai"
                    for n in range(g.indeks_bulan, g.indeks_bulan + paket.jumlah_bulan(g.penagihan)):
                        kiri = paket.batas_bulan(g.jangkar_mulai, n)
                        kanan = paket.batas_bulan(g.jangkar_mulai, n + 1)
                        if kiri <= sekarang < kanan:
                            break
                    break
        if sumber is None:
            return StatusHak("akses_berakhir", **kosong)
        batas = balasan if fitur == FITUR[0] else foto
        entitlement_sidik = sidik(data)
        jendela_id = sidik((entitlement_sidik, kiri, kanan))
        digunakan = direservasi = 0
        for item in pemakaian:
            if (item.jendela_id, item.fitur) == (jendela_id, fitur):
                digunakan, direservasi = item.digunakan, item.direservasi
        if digunakan + direservasi > batas:
            raise ValueError("ledger melebihi batas kuota")
        tersisa = batas - digunakan - direservasi
        isi_ulang = None
        if kanan < akhir and kode == "jago_pro":
            isi_ulang = kanan
        elif any(g.mulai == kanan and g.paket == "jago_pro" for g in snapshot.grants):
            isi_ulang = kanan
        if status in STATUS_BERHAK and tersisa == 0:
            status = "kuota_habis"
        return StatusHak(
            status, **kosong, paket=kode, sumber=sumber, sumber_id=sumber_id,
            entitlement_sidik=entitlement_sidik, entitlement_mulai=awal,
            entitlement_akhir=akhir, jendela_id=jendela_id,
            jendela_mulai=kiri, jendela_akhir=kanan, limit=batas,
            digunakan=digunakan, direservasi=direservasi, tersisa=tersisa,
            isi_ulang=isi_ulang,
        )
    except (ValueError, TypeError, AttributeError, OverflowError):
        return StatusHak("storage_tidak_terverifikasi", **kosong)


def baca_status(path, akun_id, *, fitur, sekarang, penegakan=False):
    """Adapter read-only; ledger belum terpasang tidak dianggap pemakaian nol."""
    from assistant_quota_store import baca_status as baca
    return baca(path, akun_id, fitur=fitur, sekarang=sekarang, penegakan=penegakan)
